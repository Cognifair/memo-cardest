import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class ScanProgressTests(unittest.TestCase):
    def test_writes_and_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_registry = os.environ.get("MEMO_CARDEST_REGISTRY")
            old_session = os.environ.get("DSH_SESSION_ID")
            os.environ["MEMO_CARDEST_REGISTRY"] = str(Path(tmp) / "tasks")
            os.environ["DSH_SESSION_ID"] = "session-test"
            try:
                from scan_progress import ScanProgress
                progress = ScanProgress("scan-test", 20, "year-1")
                progress.update(3, "year-3")
                data = json.loads(progress.path.read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "scan")
                self.assertEqual(data["unit"], "chapters")
                self.assertEqual(data["done"], 3)
                progress.close()
                self.assertEqual(json.loads(progress.path.read_text(encoding="utf-8"))["phase"], "closed")
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
