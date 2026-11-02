"""Offline tests; all journals live in temporary directories; no real account."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import change_journal as cj


def snap(**changes):
    return {"deck_id": "deck-a", "chapter_id": "chapter-a", "card_id": "card-a",
            "content": "题面\n---\n答案\n", "grammar_version": 3, **changes}


def plan(operation="update"):
    return {"task_id": "offline-test", "account_alias": "mock-account",
            "items": [{"key": "source/ch1/q1", "operation": operation,
                       "baseline": None if operation == "create" else snap(content="旧正文"),
                       "expected": snap(card_id=None) if operation == "create" else snap()}]}


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.journal = cj.make_journal(plan())
        self.key = "source/ch1/q1"

    def begin(self):
        return cj.apply(self.journal, "begin", self.key)

    def test_plan_preserves_baseline_and_exact_expected(self):
        self.assertEqual(self.journal["items"][0]["baseline"]["content"], "旧正文")
        self.assertEqual(self.journal["items"][0]["expected"]["content"], snap()["content"])
        self.assertEqual(cj.validate_journal(self.journal), self.journal)

    def test_receipt_is_not_verified(self):
        self.begin()
        cj.apply(self.journal, "receipt", self.key, "card-a")
        self.assertEqual(self.journal["items"][0]["status"], "written")
        self.assertFalse(cj.report(self.journal)["all_verified"])

    def test_known_id_uncertain_can_be_verified_without_resend(self):
        self.begin()
        item = cj.apply(self.journal, "verify", self.key, actual=snap())
        self.assertEqual(item["status"], "verified")
        self.assertEqual(item["verification"]["observed"]["content_length"], len(snap()["content"]))
        self.assertEqual(cj.report(self.journal)["client_preview"], "not_checked")

    def test_create_binds_real_id_then_verifies(self):
        journal = cj.make_journal(plan("create"))
        cj.apply(journal, "begin", self.key)
        cj.apply(journal, "receipt", self.key, "new-real-id")
        cj.apply(journal, "verify", self.key, actual=snap(card_id="new-real-id"))
        self.assertTrue(cj.report(journal)["all_verified"])

    def test_unknown_create_id_cannot_be_guessed_from_body(self):
        journal = cj.make_journal(plan("create"))
        cj.apply(journal, "begin", self.key)
        with self.assertRaisesRegex(cj.JournalError, "requires_reconciliation"):
            cj.apply(journal, "verify", self.key, actual=snap())
        self.assertEqual(journal["items"][0]["status"], "uncertain")

    def test_no_state_can_be_begun_twice(self):
        for state in cj.STATES - {"planned"}:
            journal = cj.make_journal(plan())
            journal["items"][0]["status"] = state
            with self.subTest(state=state), self.assertRaisesRegex(cj.JournalError, "cannot_resend"):
                cj.apply(journal, "begin", self.key)

    def test_unstarted_item_cannot_be_verified(self):
        with self.assertRaisesRegex(cj.JournalError, "invalid_transition"):
            cj.apply(self.journal, "verify", self.key, actual=snap())

    def test_identity_changes_are_differences(self):
        for field in ("deck_id", "chapter_id", "card_id", "grammar_version"):
            actual = snap(**{field: 4 if field == "grammar_version" else "different-id"})
            self.assertIn(field, cj.compare(snap(), actual))

    def test_exact_whitespace_newline_unicode(self):
        for content in (snap()["content"].rstrip(), snap()["content"].replace("\n", "\r\n"),
                        snap()["content"].replace("\n", "\\n"), snap()["content"] + " "):
            self.assertIn("content", cj.compare(snap(), snap(content=content)))
        self.assertIn("content", cj.compare(snap(content="é"), snap(content="e\u0301")))

    def test_difference_location_handles_eof_and_newline(self):
        diff = cj.compare(snap(content="a\nb"), snap(content="a\n"))["content"]
        self.assertEqual(diff["first_difference"], {"offset": 2, "line": 2, "column": 1})
        self.assertNotIn("actual", diff)

    def test_missing_or_extra_fields_rejected(self):
        missing = snap()
        del missing["chapter_id"]
        for actual in (missing, {**snap(), "authorization": "not-a-real-token"}, None):
            self.begin() if self.journal["items"][0]["status"] == "planned" else None
            with self.assertRaises(cj.JournalError):
                cj.apply(self.journal, "verify", self.key, actual=actual)
            self.assertEqual(self.journal["items"][0]["status"], "uncertain")

    def test_grammar_version_strict_integer(self):
        for invalid in (True, "3", 3.0, None, 0):
            with self.subTest(value=invalid), self.assertRaises(cj.JournalError):
                cj.snapshot(snap(grammar_version=invalid))

    def test_mismatch_can_be_rechecked_but_never_resubmitted(self):
        self.begin()
        cj.apply(self.journal, "verify", self.key, actual=snap(content="wrong"))
        self.assertEqual(self.journal["items"][0]["status"], "mismatch")
        with self.assertRaises(cj.JournalError):
            self.begin()
        cj.apply(self.journal, "verify", self.key, actual=snap())
        self.assertEqual(self.journal["items"][0]["status"], "verified")

    def test_skip_and_definite_rejection_are_distinct(self):
        cj.apply(self.journal, "skip", self.key)
        self.assertFalse(cj.report(self.journal)["all_verified"])
        journal = cj.make_journal(plan())
        with self.assertRaises(cj.JournalError):
            cj.apply(journal, "reject", self.key)
        cj.apply(journal, "begin", self.key)
        with self.assertRaises(cj.JournalError):
            cj.apply(journal, "skip", self.key)
        cj.apply(journal, "reject", self.key)
        self.assertEqual(cj.report(journal)["counts"]["failed"], 1)

    def test_duplicate_keys_and_targets_rejected(self):
        for same_key in (True, False):
            value = plan()
            second = copy.deepcopy(value["items"][0])
            if not same_key:
                second["key"] = "source/ch1/q2"
            value["items"].append(second)
            with self.assertRaises(cj.JournalError):
                cj.make_journal(value)

    def test_receipt_cannot_rebind_existing_id(self):
        self.begin()
        with self.assertRaisesRegex(cj.JournalError, "identity_changed"):
            cj.apply(self.journal, "receipt", self.key, "different-id")

    def test_multiple_creates_cannot_bind_same_remote_card(self):
        value = plan("create")
        second = copy.deepcopy(value["items"][0])
        second["key"] = "source/ch1/q2"
        value["items"].append(second)
        journal = cj.make_journal(value)
        for key in (self.key, second["key"]):
            cj.apply(journal, "begin", key)
        cj.apply(journal, "receipt", self.key, "new-id")
        with self.assertRaisesRegex(cj.JournalError, "duplicate_target"):
            cj.apply(journal, "receipt", second["key"], "new-id")

    def test_operation_boundaries(self):
        value = plan()
        value["items"][0]["expected"]["chapter_id"] = "chapter-b"
        with self.assertRaises(cj.JournalError):
            cj.make_journal(value)
        value["items"][0]["operation"] = "move"
        with self.assertRaises(cj.JournalError):
            cj.make_journal(value)
        value["items"][0]["baseline"]["content"] = snap()["content"]
        journal = cj.make_journal(value)
        cj.apply(journal, "begin", self.key)
        cj.apply(journal, "verify", self.key, actual=snap(chapter_id="chapter-b"))
        self.assertTrue(cj.report(journal)["all_verified"])

    def test_plan_cannot_smuggle_http_envelope(self):
        value = plan()
        value["headers"] = {"Authorization": "mock-secret"}
        with self.assertRaises(cj.JournalError):
            cj.make_journal(value)

    def test_verified_journal_requires_evidence(self):
        self.journal["items"][0]["status"] = "verified"
        self.journal["items"][0]["history"].append({"at": cj.now(), "state": "verified"})
        with self.assertRaisesRegex(cj.JournalError, "missing_verification"):
            cj.validate_journal(self.journal)

    def test_verified_journal_reloads_with_evidence(self):
        self.begin()
        cj.apply(self.journal, "verify", self.key, actual=snap())
        cj.validate_journal(self.journal)
        self.journal["items"][0]["verification"]["observed"]["content_sha256"] = "bad"
        with self.assertRaises(cj.JournalError):
            cj.validate_journal(self.journal)

    def test_corrupt_mismatch_cannot_claim_verified(self):
        self.begin()
        cj.apply(self.journal, "verify", self.key, actual=snap(content="wrong"))
        cj.validate_journal(self.journal)
        item = self.journal["items"][0]
        item["status"] = "verified"
        item["history"].append({"at": cj.now(), "state": "verified"})
        with self.assertRaises(cj.JournalError):
            cj.validate_journal(self.journal)

    def test_partial_success_counts(self):
        value = plan()
        for index in (2, 3):
            entry = copy.deepcopy(value["items"][0])
            entry["key"] = f"q{index}"
            entry["expected"]["card_id"] = entry["baseline"]["card_id"] = f"card-{index}"
            value["items"].append(entry)
        journal = cj.make_journal(value)
        cj.apply(journal, "begin", self.key)
        cj.apply(journal, "verify", self.key, actual=snap())
        cj.apply(journal, "begin", "q2")
        cj.apply(journal, "reject", "q2")
        cj.apply(journal, "skip", "q3")
        result = cj.report(journal)
        self.assertEqual([result["counts"][s] for s in ("verified", "failed", "skipped")], [1, 1, 1])
        self.assertFalse(result["all_verified"])


class FileAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "journal.json"
        self.plan_path = self.directory / "plan.json"
        self.plan_path.write_text(json.dumps(plan(), ensure_ascii=False), encoding="utf-8")

    def cli(self, action, *args):
        result = subprocess.run([sys.executable, "-B", str(Path(cj.__file__)), action,
                                 "--journal", str(self.path), *args], capture_output=True, text=True)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def init(self):
        self.assertEqual(self.cli("init", "--plan", str(self.plan_path))[0], 0)

    def test_cli_roundtrip_persists_across_processes(self):
        self.init()
        self.cli("begin", "--key", "source/ch1/q1")
        self.cli("receipt", "--key", "source/ch1/q1", "--card-id", "card-a")
        actual = self.directory / "actual.json"
        actual.write_text(json.dumps(snap()), encoding="utf-8")
        code, result = self.cli("verify", "--key", "source/ch1/q1", "--snapshot", str(actual))
        self.assertEqual(code, 0)
        self.assertTrue(result["all_verified"])
        self.assertNotIn(snap()["content"], json.dumps(result, ensure_ascii=False))
        self.assertEqual(self.cli("report")[1], result)

    def test_init_never_overwrites_existing_journal(self):
        self.init()
        before = self.path.read_bytes()
        self.assertEqual(self.cli("init", "--plan", str(self.plan_path))[1]["code"], "journal_exists")
        self.assertEqual(before, self.path.read_bytes())

    def test_mismatch_exit_code_and_invalid_snapshot_preserve_state(self):
        self.init()
        self.cli("begin", "--key", "source/ch1/q1")
        actual = self.directory / "actual.json"
        actual.write_text(json.dumps(snap(content="different")), encoding="utf-8")
        self.assertEqual(self.cli("verify", "--key", "source/ch1/q1", "--snapshot", str(actual))[0], 2)
        before = self.path.read_bytes()
        actual.write_text('{"invalid": true}', encoding="utf-8")
        self.assertEqual(self.cli("verify", "--key", "source/ch1/q1", "--snapshot", str(actual))[0], 1)
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_get_file_never_marks_verified(self):
        self.init()
        self.cli("begin", "--key", "source/ch1/q1")
        code, _ = self.cli("verify", "--key", "source/ch1/q1", "--snapshot", str(self.directory / "absent.json"))
        self.assertEqual(code, 1)
        self.assertEqual(self.cli("report")[1]["counts"]["uncertain"], 1)

    def test_busy_lock_does_not_modify_data(self):
        self.init()
        before = self.path.read_bytes()
        lock = self.path.with_name(self.path.name + ".lock")
        lock.write_text("", encoding="utf-8")
        self.assertEqual(self.cli("begin", "--key", "source/ch1/q1")[1]["code"], "journal_busy")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(lock.exists())

    def test_replace_failure_preserves_previous_json_and_removes_temp(self):
        journal = cj.make_journal(plan())
        cj.save(self.path, journal)
        before = self.path.read_bytes()
        with patch.object(cj.os, "replace", side_effect=OSError("mock failure")):
            with self.assertRaises(OSError):
                cj.save(self.path, journal)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_corrupt_json_reports_code_without_echoing_input(self):
        self.path.write_text("mock-sensitive-contents-not-json", encoding="utf-8")
        code, result = self.cli("report")
        self.assertEqual(code, 1)
        self.assertEqual(result, {"ok": False, "code": "cannot_read_json"})

    def test_unsupported_schema_not_silently_reinitialized(self):
        self.init()
        value = cj.read_json(self.path)
        value["schema_version"] = 99
        self.path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(self.cli("report")[1]["code"], "unsupported_schema")


if __name__ == "__main__":
    unittest.main()
