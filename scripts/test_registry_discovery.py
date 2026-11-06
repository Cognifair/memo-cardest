# -*- coding: utf-8 -*-
"""Registry discovery: the script must land where the island host can look."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import upload_task  # noqa: E402
from upload_task import RegistryUnavailable, registry_candidates, registry_dir  # noqa: E402


class RegistryDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="memo-registry-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))

    def test_env_override_is_the_only_candidate(self):
        target = self.root / "custom"
        with mock.patch.dict(os.environ, {"MEMO_CARDEST_REGISTRY": str(target)}):
            self.assertEqual(registry_candidates(), [target])
            self.assertEqual(registry_dir(), target)
            self.assertTrue((target / "..").exists())
            self.assertTrue(target.is_dir())

    def test_home_unwritable_falls_back_to_workspace(self):
        workspace = self.root / "ws"
        workspace.mkdir()
        blocked = self.root / "home"
        blocked.write_text("not a directory", encoding="utf-8")  # mkdir under a file fails
        with mock.patch.dict(os.environ, {"MEMO_CARDEST_WORKSPACE": str(workspace)}, clear=False):
            os.environ.pop("MEMO_CARDEST_REGISTRY", None)
            with mock.patch.object(upload_task, "registry_candidates",
                                   return_value=[blocked / "tasks", workspace / ".memo-cardest" / "progress" / "v1" / "tasks"]):
                resolved = registry_dir()
        self.assertEqual(resolved, workspace / ".memo-cardest" / "progress" / "v1" / "tasks")
        self.assertTrue(resolved.is_dir())

    def test_nothing_writable_raises_actionable_error(self):
        blocked = self.root / "blocked"
        blocked.write_text("x", encoding="utf-8")
        with mock.patch.object(upload_task, "registry_candidates", return_value=[blocked / "tasks"]):
            with self.assertRaises(RegistryUnavailable) as caught:
                registry_dir()
        message = str(caught.exception)
        self.assertIn("island can discover", message)
        self.assertIn(str(blocked / "tasks"), message)
        self.assertIn("MEMO_CARDEST_REGISTRY", message)

    def test_custom_registry_is_refused_without_opt_in(self):
        import change_journal as cj
        journal = self.root / "j.json"
        cj.mutate(journal, "init", plan={"task_id": "t", "account_alias": "a", "items": [
            {"key": "k", "operation": "create", "baseline": None,
             "expected": {"deck_id": "d", "chapter_id": "c", "card_id": None,
                          "content": "x", "grammar_version": 3}}]})
        with mock.patch.dict(os.environ, {"MEMO_CARDEST_REGISTRY": str(self.root / "allowed")}):
            candidate = self.root / "elsewhere"
            with self.assertRaises(RegistryUnavailable) as caught:
                upload_task.UploadTask.open(journal, registry=candidate)
            self.assertIn("not discoverable", str(caught.exception))

    def test_workspace_candidate_is_the_default_location(self):
        workspace = self.root / "ws"
        workspace.mkdir()
        with mock.patch.dict(os.environ, {"MEMO_CARDEST_WORKSPACE": str(workspace)}):
            os.environ.pop("MEMO_CARDEST_REGISTRY", None)
            candidates = registry_candidates()
        self.assertEqual(candidates[-1], workspace / ".memo-cardest" / "progress" / "v1" / "tasks")


if __name__ == "__main__":
    unittest.main(verbosity=2)
