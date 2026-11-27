import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MediaProgressTests(unittest.TestCase):
    def test_writes_and_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_registry = os.environ.get("MEMO_CARDEST_REGISTRY")
            old_session = os.environ.get("DSH_SESSION_ID")
            os.environ["MEMO_CARDEST_REGISTRY"] = str(Path(tmp) / "tasks")
            os.environ["DSH_SESSION_ID"] = "session-test"
            try:
                from media_progress import MediaProgress
                progress = MediaProgress("media-test", 10, "a")
                progress.update(3, "b")
                data = json.loads(progress.path.read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "media")
                self.assertEqual(data["session_id"], "session-test")
                self.assertEqual(data["done"], 3)
                progress.close()
                closed = json.loads(progress.path.read_text(encoding="utf-8"))
                self.assertEqual(closed["phase"], "closed")
            finally:
                if old_registry is None:
                    os.environ.pop("MEMO_CARDEST_REGISTRY", None)
                else:
                    os.environ["MEMO_CARDEST_REGISTRY"] = old_registry
                if old_session is None:
                    os.environ.pop("DSH_SESSION_ID", None)
                else:
                    os.environ["DSH_SESSION_ID"] = old_session


if __name__ == "__main__":
    unittest.main()
