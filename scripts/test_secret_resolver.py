import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "secret_resolver.py"
SPEC = importlib.util.spec_from_file_location("secret_resolver", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecretResolverTests(unittest.TestCase):
    def test_process_environment_wins(self):
        with patch.dict(os.environ, {"MAIMEMO_TOKEN": "env-token"}, clear=True):
            self.assertEqual(MODULE.get_secret("MAIMEMO_TOKEN"), ("env-token", "process environment"))

    def test_user_environment_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
                MODULE, "_read_user_env", return_value="user-token"):
            self.assertEqual(MODULE.get_secret("MAIMEMO_TOKEN"), ("user-token", "Windows user environment"))

    def test_workspace_file_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = Path(tmp) / ".memo-secrets"
            secrets.mkdir()
            (secrets / "maimemo_token").write_text("file-token\n", encoding="utf-8")
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=True), patch.object(
                    MODULE, "_read_user_env", return_value=None):
                value, source = MODULE.get_secret("MAIMEMO_TOKEN", workspace=tmp)
            self.assertEqual(value, "file-token")
            self.assertTrue(source.endswith("maimemo_token"))

    def test_missing_secret_message_does_not_leak_a_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}, clear=True), patch.object(
                    MODULE, "_read_user_env", return_value=None):
                with self.assertRaises(MODULE.SecretNotFound) as caught:
                    MODULE.get_secret("MAIMEMO_TOKEN", workspace=tmp)
            self.assertIn("MAIMEMO_TOKEN not found", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
