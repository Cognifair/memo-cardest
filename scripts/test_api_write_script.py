import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_api_write_script.py"


class ApiWriteScriptTests(unittest.TestCase):
    def run_script(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.py"
            path.write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, "-B", str(CHECK), str(path)],
                                  capture_output=True, text=True)

    def test_raw_writer_is_blocked(self):
        result = self.run_script(
            'import urllib.request\n'
            'req = urllib.request.Request("https://open.maimemo.com/open/api/v1/markji", data=b"{}")\n'
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("raw API writer", result.stdout)

    def test_registered_writer_passes(self):
        result = self.run_script(
            'from upload_task import UploadTask\n'
            'task = UploadTask.open("journal.json")\n'
            'task.begin("card-1")\n'
            'url = "https://open.maimemo.com/open/api/v1/markji"\n'
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_read_only_script_passes(self):
        result = self.run_script(
            'import urllib.request\n'
            'request = urllib.request.Request("https://open.maimemo.com/open/api/v1/markji/decks")\n'
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
