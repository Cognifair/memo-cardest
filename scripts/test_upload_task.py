"""Offline callbacks only: never read credentials or call a real API."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import change_journal as cj
from upload_task import UploadTask, WriteResult, combine, identity_digest


def plan(n=1):
    return {"task_id": "fixture", "account_alias": "mock", "items": [
        {"key": str(k), "operation": "create", "baseline": None,
         "expected": {"deck_id": "d", "chapter_id": "c", "card_id": None,
                      "content": "mock", "grammar_version": 3}} for k in range(n)]}


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "any-name.json"
        cj.mutate(self.path, "init", plan=plan())

    def task(self, **kw):
        task = UploadTask.open(self.path, registry=self.root / "registry", allow_custom_registry=True, session_id="session-test", **kw)
        self.addCleanup(task.close)
        return task

    def snapshot(self, card="id"):
        return {**plan()["items"][0]["expected"], "card_id": card}

    def confirmed(self):
        return WriteResult("confirmed", "id")

    def test_automatic_registration_and_write_before_network(self):
        with self.task() as task:
            record = cj.read_json(task.path)
            self.assertEqual(record["session_id"], "session-test")
            self.assertNotIn("counts", record)
            def send():
                self.assertEqual(cj.read_json(self.path)["items"][0]["status"], "uncertain")
                return "mock response"
            task.execute_write("0", send, lambda r: self.confirmed())
            self.assertEqual(task.snapshot()["items"][0]["status"], "written")
            task.verify("0", self.snapshot)
        self.assertEqual(cj.read_json(task.path)["lifecycle"], "completed")

    def test_timeout_keeps_unknown_and_no_resend(self):
        with self.task() as task:
            def timeout(): raise TimeoutError()
            with self.assertRaises(TimeoutError): task.execute_write("0", timeout, lambda r: self.confirmed())
            self.assertEqual(task.snapshot()["items"][0]["status"], "uncertain")
            with self.assertRaises(cj.JournalError): task.execute_write("0", lambda: self.fail("resend"), lambda r: r)
        self.assertEqual(cj.read_json(task.path)["lifecycle"], "partial")

    def test_explicit_rate_limit_retry_bounded(self):
        with self.task() as task:
            task.execute_write("0", lambda: 429, lambda r: WriteResult("rejected"))
            with self.assertRaisesRegex(cj.JournalError, "authorized"):
                task.retry_rejected("0", lambda: 201, lambda r: self.confirmed())
            result = task.retry_rejected("0", lambda: 201, lambda r: self.confirmed(), authorized=True, max_retries=1)
            self.assertEqual(result.kind, "confirmed")
            self.assertEqual([h["state"] for h in task.snapshot()["items"][0]["history"]],
                             ["planned", "uncertain", "failed", "planned", "uncertain", "written"])

    def test_unknown_never_retry_rejected(self):
        with self.task() as task:
            task.execute_write("0", lambda: None, lambda r: WriteResult("uncertain"))
            with self.assertRaisesRegex(cj.JournalError, "definite_rejection"):
                task.retry_rejected("0", lambda: self.fail("called"), lambda r: r, authorized=True, max_retries=3)

    def test_registration_failure_prevents_first_request(self):
        with patch('upload_task.cj.save', side_effect=OSError()):
            with self.assertRaises(OSError): self.task()
        self.assertEqual(cj.read_json(self.path)["items"][0]["status"], "planned")

    def test_begin_failure_prevents_request_and_latches_executor(self):
        with self.task() as task:
            with patch('upload_task.cj.mutate', side_effect=OSError()):
                with self.assertRaises(OSError): task.execute_write("0", lambda: self.fail("called"), lambda r: r)
            with self.assertRaisesRegex(cj.JournalError, 'not_writable'):
                task.execute_write("0", lambda: self.fail("called"), lambda r: r)

    def test_heartbeat_failure_does_not_change_card_state(self):
        with self.task() as task:
            with patch('upload_task.cj.save', side_effect=OSError()), self.assertWarns(RuntimeWarning): task._persist()
            task.execute_write("0", lambda: 201, lambda r: self.confirmed())
            self.assertEqual(task.snapshot()["items"][0]["status"], "written")

    def test_single_executor_and_reopen_same_uuid(self):
        task = self.task()
        with self.assertRaisesRegex(cj.JournalError, 'busy'): self.task()
        uid = task.uuid
        task.close()
        with self.task() as again: self.assertEqual(again.uuid, uid)

    def test_session_binding_not_guessed(self):
        with patch.dict('os.environ', {}, clear=True):
            with UploadTask.open(self.path, registry=self.root / 'unbound', allow_custom_registry=True) as task:
                self.assertIsNone(task.record['session_id'])

    def test_get_failure_leaves_written_not_success(self):
        with self.task() as task:
            task.execute_write("0", lambda: 201, lambda r: self.confirmed())
            def bad_get(): raise KeyError('cards missing, e.g. with_cards not requested')
            with self.assertRaises(KeyError): task.verify("0", bad_get)
            self.assertEqual(task.finish()['counts']['written'], 1)
            self.assertEqual(task.record['lifecycle'], 'partial')
            task.verify("0", self.snapshot)

    def test_same_journal_reverify_after_completion(self):
        with self.task() as task:
            task.execute_write("0", lambda: 201, lambda r: self.confirmed())
            task.verify("0", self.snapshot)
        with self.task() as task:
            task.verify("0", lambda: {**self.snapshot(), 'content': 'different'})
            self.assertFalse(task.finish()['all_verified'])

    def test_successor_unknown_and_bound_id_protected(self):
        root = cj.read_json(self.path)
        cj.apply(root, 'begin', '0')
        child = cj.make_journal(plan())
        with self.assertRaisesRegex(cj.JournalError, 'unsafe_successor'): combine([root, child])
        cj.apply(root, 'receipt', '0', 'id')
        with self.assertRaisesRegex(cj.JournalError, 'bound_identity_lost'): combine([root, child])

    def test_explicit_successor_rejection_and_unique_total(self):
        with self.task() as task:
            task.execute_write("0", lambda: 429, lambda r: WriteResult('rejected'))
            uid = task.uuid
        child = self.root / 'retry.json'
        cj.mutate(child, 'init', plan=plan())
        with UploadTask.open(child, task_uuid=uid, registry=self.root/'registry', allow_custom_registry=True, session_id='session-test', authorize_successor_retry=True) as task:
            task.execute_write('0', lambda: 201, lambda r: self.confirmed())
            task.verify('0', self.snapshot)
            self.assertEqual(task.finish()['total'], 1)
        with self.assertRaisesRegex(cj.JournalError, 'superseded'): self.task()

    def test_duplicate_key_rejected(self):
        p = plan(); p['items'].append(copy.deepcopy(p['items'][0]))
        with self.assertRaisesRegex(cj.JournalError, 'duplicate'): cj.make_journal(p)

    def test_atomic_replace_failure_preserves_prior_json(self):
        before = self.path.read_bytes()
        with patch('change_journal.os.replace', side_effect=OSError()):
            with self.assertRaises(OSError): cj.mutate(self.path, 'begin', '0')
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse(self.path.with_suffix('.json.lock').exists())


if __name__ == '__main__': unittest.main()
