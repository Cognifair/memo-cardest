"""Persistent upload registration, with change_journal as the only card ledger.

No API URLs, credential handling, automatic write retries or unknown-ID recovery.
Import this module from the upload script; do not create a notifier process.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
import warnings

import change_journal as cj

PROTOCOL_VERSION = 1
HEARTBEAT_SECONDS = 5


REGISTRY_ENV = "MEMO_CARDEST_REGISTRY"
WORKSPACE_ENV = "MEMO_CARDEST_WORKSPACE"


class RegistryUnavailable(RuntimeError):
    """No upload registry directory that both this script and the island can see."""


def workspace_root():
    """Workspace root, never a guess: explicit env, else the nearest ancestor
    that already carries a .memo-cardest marker, else the current directory."""
    value = os.environ.get(WORKSPACE_ENV)
    if value:
        return Path(value).expanduser()
    start = Path.cwd()
    for candidate in [start, *start.parents][:6]:
        if (candidate / ".memo-cardest").exists():
            return candidate
    return start


def registry_candidates():
    """Discovery order shared with the island host: env override, home, workspace."""
    explicit = os.environ.get(REGISTRY_ENV)
    if explicit:
        return [Path(explicit).expanduser()]
    candidates = [workspace_root() / ".memo-cardest" / "progress" / "v1" / "tasks"]
    try:
        candidates.insert(0, Path.home() / ".memo-cardest" / "progress" / "v1" / "tasks")
    except (RuntimeError, OSError):
        pass  # no resolvable home directory: workspace fallback still works
    return candidates


def _ensure_writable(directory):
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / (".probe-" + uuid.uuid4().hex)
    probe.write_text("", encoding="utf-8")
    probe.unlink()
    return directory


def registry_dir():
    """First registry the host can also discover; otherwise fail loudly."""
    problems = []
    for candidate in registry_candidates():
        try:
            return _ensure_writable(candidate)
        except OSError as error:
            problems.append(f"{candidate} ({error.strerror or error})")
    raise RegistryUnavailable(
        "no writable upload registry the island can discover; tried "
        + "; ".join(problems)
        + ". Set " + REGISTRY_ENV + " to a directory both sides share, "
        + "or run the script from the workspace root."
    )


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def item_identity(item):
    return canonical({"key": item["key"], "operation": item["operation"], "expected": item["expected"]})


def identity_digest(journal):
    value = {"account_alias": journal["account_alias"], "items": sorted(
        [json.loads(item_identity(i)) for i in journal["items"]], key=lambda i: i["key"])}
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def combine(journals):
    """Explicit ordered successors only. Never infer lineage from a filename."""
    root = journals[0]
    current = {i["key"]: i for i in root["items"]}
    identities = {k: item_identity(i) for k, i in current.items()}
    for journal in journals[1:]:
        cj.require(journal["account_alias"] == root["account_alias"], "account_conflict")
        for item in journal["items"]:
            key = item["key"]
            cj.require(key in current and item_identity(item) == identities[key], "identity_conflict")
            old = current[key]
            if old["bound_card_id"] is not None:
                cj.require(item["bound_card_id"] == old["bound_card_id"], "bound_identity_lost")
            # A fresh child may retry a definite rejection, but cannot launder
            # an unknown/successful request into a new planned creation.
            if old["status"] in ("uncertain", "written", "verified", "mismatch"):
                cj.require(item["status"] not in ("planned", "failed", "skipped"), "unsafe_successor")
                cj.require(item["history"][:len(old["history"])] == old["history"], "history_lost")
            current[key] = item
    targets = set()
    for item in current.values():
        if item["bound_card_id"] is not None:
            target = (item["expected"]["deck_id"], item["bound_card_id"])
            cj.require(target not in targets, "duplicate_target")
            targets.add(target)
    return {**root, "items": list(current.values())}


@dataclass(frozen=True)
class WriteResult:
    # Only the adapter may assert definite rejection/success from API evidence.
    kind: str  # confirmed | rejected | uncertain
    card_id: str | None = None


class UploadTask:
    @classmethod
    def open(cls, journal, *, session_id=None, task_uuid=None, registry=None,
             rebind=False, authorize_successor_retry=False, execution=None,
             allow_custom_registry=False):
        self = cls()
        self.journal = Path(journal).resolve(strict=True)
        first = cj.validate_journal(cj.read_json(self.journal))
        if registry is None:
            self.registry = registry_dir()
        else:
            chosen = Path(registry).expanduser().resolve()
            allowed = {candidate.resolve() for candidate in registry_candidates()}
            if not allow_custom_registry and chosen not in allowed:
                raise RegistryUnavailable(
                    f"custom registry {chosen} is not discoverable by the island; "
                    "use the default registry, or pass allow_custom_registry=True "
                    "for tests and special deployments only."
                )
            self.registry = chosen
            self.registry.mkdir(parents=True, exist_ok=True)
        self.uuid = str(uuid.UUID(task_uuid)) if task_uuid else str(uuid.uuid5(
            uuid.NAMESPACE_URL, self.journal.as_uri() + "#" + first["task_id"] + "#" + first["created_at"]))
        self.path = self.registry / (self.uuid + ".json")
        self._mutex = threading.RLock()
        self._stop = threading.Event()
        self._closed = False
        self._broken = False
        self._lock = cj.locked(self.registry / (self.uuid + ".executor"))
        self._lock.__enter__()  # never reclaim stale ownership automatically
        try:
            session_id = session_id if session_id is not None else os.environ.get("DSH_SESSION_ID")
            cj.require(session_id is None or re.fullmatch(r"[\w.:-]{1,128}", session_id), "invalid_session_id")
            profile = os.environ.get("DSH_PROFILE_DIR") or os.environ.get("DSH_PROFILE")
            if self.path.exists():
                record = cj.read_json(self.path)
                cj.require(record.get("protocol_version") == 1 and record.get("task_uuid") == self.uuid,
                           "invalid_registration")
                cj.require(rebind or record["session_id"] == session_id, "session_binding_conflict")
                cj.require(rebind or record.get("profile") == profile, "profile_binding_conflict")
                paths = record["journals"]
                cj.require(isinstance(paths, list) and paths and len(paths) <= 64, "invalid_registration")
                journals = [cj.validate_journal(cj.read_json(p)) for p in paths]
                cj.require(identity_digest(journals[0]) == record["identity_digest"], "root_identity_changed")
                if str(self.journal) not in paths:
                    previous = combine(journals)
                    old = {i["key"]: i for i in previous["items"]}
                    if any(old.get(i["key"], {}).get("status") == "failed" and i["status"] == "planned"
                           for i in first["items"]):
                        cj.require(authorize_successor_retry, "retry_not_authorized")
                    combine(journals + [first])
                    paths.append(str(self.journal))
                cj.require(paths[-1] == str(self.journal), "superseded_journal")
                combine([cj.validate_journal(cj.read_json(p)) for p in paths])
            else:
                cj.require(task_uuid is None, "unknown_task_uuid")
                record = {"protocol_version": 1, "task_uuid": self.uuid,
                          "task_id": first["task_id"], "identity_digest": identity_digest(first),
                          "total": len(first["items"]), "journals": [str(self.journal)],
                          "created_at": cj.now(), "revision": 0}
            record.update(session_id=session_id, profile=profile, run_id=str(uuid.uuid4()),
                          pid=os.getpid(), started_at=cj.now(), ended_at=None,
                          lifecycle="running", heartbeat_at=cj.now(), wait_reason=None,
                          execution=self._execution(execution or {}), sample_after=cj.now())
            self.record = record
            self._persist(strict=True)
            self._thread = threading.Thread(target=self._heartbeat, daemon=True)
            self._thread.start()
            return self
        except BaseException:
            self._lock.__exit__(None, None, None)
            raise

    @staticmethod
    def _execution(value):
        allowed = {"request_interval_ms", "concurrency", "write_requests", "verify_requests",
                   "expected_latency_ms"}
        cj.require(isinstance(value, dict) and set(value) <= allowed, "invalid_execution_plan")
        for key, n in value.items():
            cj.require(type(n) in (int, float) and math.isfinite(n) and n >= 0, "invalid_execution_plan")
            if key in ("concurrency", "write_requests", "verify_requests"):
                cj.require(type(n) is int and (key != "concurrency" or n >= 1), "invalid_execution_plan")
        return dict(value)

    def _persist(self, strict=False):
        with self._mutex:
            self.record["revision"] += 1
            self.record["heartbeat_at"] = cj.now()
            try:
                with cj.locked(self.path):
                    cj.save(self.path, self.record)
            except (OSError, cj.JournalError):
                if strict:
                    raise
                warnings.warn("upload_registration_write_failed", RuntimeWarning)

    def _heartbeat(self):
        while not self._stop.wait(HEARTBEAT_SECONDS):
            self._persist()

    def __enter__(self):
        return self

    def _mutate(self, action, key, **kwargs):
        with self._mutex:
            cj.require(not self._closed and not self._broken, "executor_not_writable")
            try:
                # Revalidate all predecessors before each operation, not just open.
                self.snapshot()
                result = cj.mutate(self.journal, action, key, **kwargs)
            except Exception:
                self._broken = True
                raise
            self._persist()
            return result

    def snapshot(self):
        journals = [cj.validate_journal(cj.read_json(p)) for p in self.record["journals"]]
        cj.require(identity_digest(journals[0]) == self.record["identity_digest"], "root_identity_changed")
        return combine(journals)

    def execute_write(self, key, send, classify):
        self._mutate("begin", key)
        try:
            outcome = classify(send())
            cj.require(isinstance(outcome, WriteResult) and outcome.kind in
                       ("confirmed", "rejected", "uncertain"), "invalid_write_result")
        except Exception:
            # A thrown request/parser/classifier never proves rejection.
            self._persist()
            raise
        if outcome.kind == "confirmed":
            self._mutate("receipt", key, card_id=outcome.card_id)
        elif outcome.kind == "rejected":
            self._mutate("reject", key)
        return outcome

    def verify(self, key, fetch_snapshot):
        # Independent API GET callback, never the POST response or expected data.
        actual = fetch_snapshot()
        result = self._mutate("verify", key, actual=actual)
        return next(i["status"] for i in result["items"] if i["key"] == key)

    def retry_rejected(self, key, send, classify, *, authorized=False,
                       max_retries=0, retry_after_seconds=0):
        cj.require(authorized and type(max_retries) is int and 0 < max_retries <= 20,
                   "retry_not_authorized")
        cj.require(type(retry_after_seconds) in (int, float) and
                   math.isfinite(retry_after_seconds) and retry_after_seconds >= 0,
                   "invalid_retry_delay")
        item = next((i for i in self.snapshot()["items"] if i["key"] == key), None)
        cj.require(item is not None and item["status"] == "failed", "retry_requires_definite_rejection")
        retries = sum(e["state"] == "uncertain" for e in item["history"]) - 1
        cj.require(retries < max_retries, "retry_limit")
        with self.pause("rate_limit"):
            time.sleep(retry_after_seconds)
        self._mutate("retry-rejected", key)
        return self.execute_write(key, send, classify)

    @contextmanager
    def pause(self, reason="paused"):
        cj.require(reason in ("paused", "rate_limit", "network_wait"), "invalid_wait_reason")
        with self._mutex:
            self.record.update(lifecycle="paused", wait_reason=reason)
            self._persist()
        try:
            yield self
        finally:
            with self._mutex:
                self.record.update(lifecycle="running", wait_reason=None)
                self.record["sample_after"] = cj.now()
                self._persist()

    def finish(self):
        report = cj.report(self.snapshot())
        with self._mutex:
            self.record.update(lifecycle="completed" if report["all_verified"] else "partial",
                               ended_at=cj.now(), wait_reason=None)
            self._persist()
        return report

    def close(self):
        if not self._closed:
            if self.record["lifecycle"] in ("running", "paused"):
                self.record.update(lifecycle="interrupted", ended_at=cj.now(), wait_reason=None)
                self._persist()
            self._stop.set()
            self._thread.join(timeout=HEARTBEAT_SECONDS + 1)
            self._closed = True
            self._lock.__exit__(None, None, None)

    def __exit__(self, typ, value, traceback):
        try:
            if typ is None:
                self.finish()
            else:
                self.record.update(lifecycle="interrupted", ended_at=cj.now(), wait_reason=None)
                self._persist()
        finally:
            self.close()
        return False
