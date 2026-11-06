"""Offline card change journal. No HTTP, credentials, retries, or automatic resume.

API-specific field extraction belongs to the caller using current official docs.
Only normalized card snapshots enter this module; never pass raw HTTP envelopes.
"""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1
FIELDS = ("deck_id", "chapter_id", "card_id", "content", "grammar_version")
STATES = {"planned", "uncertain", "written", "verified", "mismatch", "failed", "skipped"}


class JournalError(ValueError):
    """Messages are fixed codes, not copies of user data or exception payloads."""


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, code):
    if not condition:
        raise JournalError(code)


def keys(value, required, optional=()):
    require(isinstance(value, dict), "object_required")
    require(set(required) <= set(value) <= set(required) | set(optional), "invalid_fields")


def identifier(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 256,
            "invalid_identifier")
    return value


def snapshot(value, new=False):
    keys(value, FIELDS)
    for field in ("deck_id", "chapter_id"):
        identifier(value[field])
    if new:
        require(value["card_id"] is None, "create_id_must_be_null")
    else:
        identifier(value["card_id"])
    require(isinstance(value["content"], str), "content_must_be_string")
    require(type(value["grammar_version"]) is int and value["grammar_version"] > 0,
            "invalid_grammar_version")
    return {field: value[field] for field in FIELDS}


def make_journal(plan):
    keys(plan, ("task_id", "account_alias", "items"))
    identifier(plan["task_id"])
    identifier(plan["account_alias"])
    require(isinstance(plan["items"], list) and bool(plan["items"]), "items_required")
    items, seen, targets = [], set(), set()
    for entry in plan["items"]:
        keys(entry, ("key", "operation", "baseline", "expected"))
        key = identifier(entry["key"])
        require(key not in seen, "duplicate_source_key")
        seen.add(key)
        operation = entry["operation"]
        require(operation in ("create", "update", "move"), "unsupported_operation")
        expected = snapshot(entry["expected"], new=operation == "create")
        if operation == "create":
            require(entry["baseline"] is None, "create_baseline_must_be_null")
            baseline = None
        else:
            baseline = snapshot(entry["baseline"])
            require(all(baseline[f] == expected[f] for f in ("deck_id", "card_id")),
                    "identity_changed")
            if operation == "update":
                require(baseline["chapter_id"] == expected["chapter_id"], "update_cannot_move")
            else:
                require(all(baseline[f] == expected[f] for f in ("content", "grammar_version")),
                        "move_cannot_edit")
            target = (expected["deck_id"], expected["card_id"])
            require(target not in targets, "duplicate_target")
            targets.add(target)
        items.append({**entry, "baseline": baseline, "expected": expected,
                      "bound_card_id": expected["card_id"], "status": "planned",
                      "verification": None, "history": [{"at": now(), "state": "planned"}]})
    return {"schema_version": SCHEMA_VERSION, "task_id": plan["task_id"],
            "account_alias": plan["account_alias"], "created_at": now(), "items": items}


def validate_journal(journal):
    keys(journal, ("schema_version", "task_id", "account_alias", "created_at", "items"))
    require(type(journal["schema_version"]) is int and journal["schema_version"] == SCHEMA_VERSION,
            "unsupported_schema")
    require(isinstance(journal["items"], list), "invalid_journal")
    plan = {"task_id": journal["task_id"], "account_alias": journal["account_alias"],
            "items": []}
    for item in journal["items"]:
        keys(item, ("key", "operation", "baseline", "expected", "bound_card_id",
                    "status", "verification", "history"))
        require(item["status"] in STATES, "invalid_state")
        require(isinstance(item["history"], list) and bool(item["history"]), "invalid_history")
        for event in item["history"]:
            keys(event, ("at", "state"))
            require(event["state"] in STATES, "invalid_history")
        require(item["history"][-1]["state"] == item["status"], "invalid_history")
        if item["bound_card_id"] is not None:
            identifier(item["bound_card_id"])
        if item["operation"] != "create":
            require(item["bound_card_id"] == item["expected"]["card_id"], "identity_changed")
        if item["status"] in ("written", "verified", "mismatch"):
            require(item["bound_card_id"] is not None, "missing_bound_id")
        verification = item["verification"]
        if item["status"] in ("verified", "mismatch"):
            require(verification is not None, "missing_verification")
        if verification is not None:
            keys(verification, ("checked_at", "differences", "observed", "basis"))
            require(verification["basis"] == "caller_supplied_get_snapshot", "invalid_verification")
            require(isinstance(verification["differences"], dict)
                    and set(verification["differences"]) <= set(FIELDS), "invalid_verification")
            observed = verification["observed"]
            keys(observed, ("deck_id", "chapter_id", "card_id", "grammar_version",
                            "content_length", "content_sha256"))
            snapshot({**{f: observed[f] for f in FIELDS if f != "content"}, "content": ""})
            require(type(observed["content_length"]) is int and observed["content_length"] >= 0,
                    "invalid_verification")
            digest = observed["content_sha256"]
            require(isinstance(digest, str) and len(digest) == 64
                    and all(c in "0123456789abcdef" for c in digest), "invalid_verification")
            require((item["status"] == "verified" and not verification["differences"])
                    or (item["status"] == "mismatch" and bool(verification["differences"])),
                    "invalid_verification")
        plan["items"].append({f: item[f] for f in ("key", "operation", "baseline", "expected")})
    make_journal(plan)
    return journal


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        raise JournalError("cannot_read_json") from None


@contextmanager
def locked(path):
    """No stale-lock reclamation: uncertain ownership requires human inspection."""
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise JournalError("journal_busy") from None
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def save(path, journal):
    descriptor, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(journal, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def compare(expected, actual):
    """Exact Unicode comparison: no trim, newline or normalization conversion."""
    snapshot(expected)
    snapshot(actual)
    differences = {}
    for field in FIELDS:
        wanted, got = expected[field], actual[field]
        if wanted == got:
            continue
        if field == "content":
            index = next((i for i, (a, b) in enumerate(zip(wanted, got)) if a != b),
                         min(len(wanted), len(got)))
            differences[field] = {
                "expected_length": len(wanted), "actual_length": len(got),
                "expected_sha256": hashlib.sha256(wanted.encode("utf-8")).hexdigest(),
                "actual_sha256": hashlib.sha256(got.encode("utf-8")).hexdigest(),
                "first_difference": {"offset": index,
                                     "line": wanted.count("\n", 0, index) + 1,
                                     "column": index - wanted.rfind("\n", 0, index)},
            }
        else:
            differences[field] = {"expected": wanted, "actual": got}
    return differences


def transition(item, state):
    item["status"] = state
    item["history"].append({"at": now(), "state": state})


def apply(journal, action, key, card_id=None, actual=None):
    item = next((i for i in journal["items"] if i["key"] == key), None)
    require(item is not None, "unknown_item")
    state = item["status"]
    if action == "begin":
        require(state == "planned", "cannot_resend")
        # Persist BEFORE the caller sends HTTP. A crash is then conservatively uncertain.
        transition(item, "uncertain")
    elif action == "receipt":
        require(state == "uncertain", "invalid_transition")
        identifier(card_id)
        require(item["bound_card_id"] in (None, card_id), "identity_changed")
        require(not any(other is not item and other["expected"]["deck_id"] == item["expected"]["deck_id"]
                        and other["bound_card_id"] == card_id for other in journal["items"]),
                "duplicate_target")
        item["bound_card_id"] = card_id
        transition(item, "written")
    elif action == "verify":
        require(state in ("uncertain", "written", "mismatch", "verified"), "invalid_transition")
        require(item["bound_card_id"] is not None, "unbound_create_requires_reconciliation")
        expected = {**item["expected"], "card_id": item["bound_card_id"]}
        differences = compare(expected, snapshot(actual))
        item["verification"] = {"checked_at": now(), "differences": differences,
                                "observed": {**{f: actual[f] for f in FIELDS if f != "content"},
                                             "content_length": len(actual["content"]),
                                             "content_sha256": hashlib.sha256(actual["content"].encode("utf-8")).hexdigest()},
                                "basis": "caller_supplied_get_snapshot"}
        transition(item, "mismatch" if differences else "verified")
    elif action == "reject":
        # Caller must have a definite rejection, NOT a timeout or lost response.
        require(state == "uncertain", "invalid_transition")
        transition(item, "failed")
    elif action == "retry-rejected":
        # Explicit caller authorization only; never reset an unknown result.
        require(state == "failed", "retry_requires_definite_rejection")
        transition(item, "planned")
    elif action == "skip":
        require(state == "planned", "invalid_transition")
        transition(item, "skipped")
    else:
        raise JournalError("unsupported_action")
    return item


def report(journal):
    counts = Counter(item["status"] for item in journal["items"])
    return {"task_id": journal["task_id"], "total": len(journal["items"]),
            "counts": {state: counts[state] for state in sorted(STATES)},
            "all_verified": counts["verified"] == len(journal["items"]),
            "automatic_resume": False, "client_preview": "not_checked",
            "items": [{"key": item["key"], "operation": item["operation"],
                       "card_id": item["bound_card_id"], "status": item["status"],
                       "verification": item["verification"]} for item in journal["items"]]}


def mutate(path, action, key=None, card_id=None, actual=None, plan=None):
    """Shared, atomic CLI/library mutation. A failed begin must prevent HTTP."""
    path = Path(path).resolve()
    require(path.parent.is_dir(), "journal_parent_missing")
    with locked(path):
        if action == "init":
            require(plan is not None, "plan_required")
            require(not path.exists(), "journal_exists")
            journal = make_journal(plan)
        else:
            require(key is not None, "key_required")
            journal = validate_journal(read_json(path))
            apply(journal, action, key, card_id, actual)
        validate_journal(journal)
        save(path, journal)
    return journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "begin", "receipt", "verify", "reject", "skip", "report", "retry-rejected"))
    parser.add_argument("--authorize-retry", action="store_true", help="Explicitly permit retry of a definite rejection only")
    parser.add_argument("--journal", required=True)
    parser.add_argument("--plan")
    parser.add_argument("--key")
    parser.add_argument("--card-id")
    parser.add_argument("--snapshot", help="Normalized fresh GET snapshot, not the write response")
    args = parser.parse_args(argv)
    try:
        path = Path(args.journal).resolve()
        require(path.parent.is_dir(), "journal_parent_missing")
        if args.action == "report":
            journal = validate_journal(read_json(path))
        else:
            require(args.action != "retry-rejected" or args.authorize_retry, "retry_not_authorized")
            journal = mutate(path, args.action, args.key, args.card_id,
                             read_json(args.snapshot) if args.snapshot else None,
                             read_json(args.plan) if args.plan else None)
        result = report(journal)
        print(json.dumps(result, ensure_ascii=True))
        return 2 if args.action == "verify" and any(
            item["key"] == args.key and item["status"] == "mismatch" for item in journal["items"]
        ) else 0
    except JournalError as error:
        print(json.dumps({"ok": False, "code": str(error)}))
        return 1
    except (OSError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"ok": False, "code": "journal_io_or_schema_error"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
