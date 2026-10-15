"""Offline framework behavior tests; no live requests, installs or consent changes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

SPEC = importlib.util.spec_from_file_location("checker", Path(__file__).with_name("check_updates.py"))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)

class FrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = m.default_state()
        self.cfg = {"allowed_version_hosts": ["example.com"], "throttle_hours": 24}
        self.row = {"id": "memo-test", "name": "Test", "installed": True,
                    "version_url": "https://example.com/memo-test/version.json",
                    "local_version": "1.0.0", "install_source": "platform_marketplace",
                    "marketplace_listing": None}

    def test_semver(self):
        ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta", "1.0.0-rc.1", "1.0.0", "2.0.0"]
        self.assertEqual(sorted(ordered, key=m.Version), ordered)
        self.assertEqual(m.Version("1.0.0+abc"), m.Version("1.0.0+def"))
        for bad in ["1.0", "01.0.0", "1.0.0-01"]:
            with self.assertRaises(ValueError):
                m.Version(bad)

    def test_metadata_ignores_body_and_prefers_nested(self):
        file = self.base / "SKILL.md"
        file.write_text('---\nname: memo-test\nversion: "0.1.0"\nmetadata:\n  version: "1.2.0"\n---\nversion: 9.0.0\n', encoding="utf-8")
        self.assertEqual(m.skill_metadata(file), ("memo-test", "1.2.0"))
        file.write_text('---\nname: memo-test\nversion: "0.1.0"\n---\n', encoding="utf-8")
        self.assertEqual(m.skill_metadata(file)[1], "0.1.0")

    def test_disabled_makes_no_request(self):
        fetch = Mock(side_effect=AssertionError("No network"))
        self.assertEqual(m.check_versions(self.cfg, [self.row], self.state, fetcher=fetch)["status"], "disabled")
        fetch.assert_not_called()

    def test_unconfigured_or_absent_is_not_up_to_date(self):
        for changes, reason in [({"installed": False}, "not_installed"),
                                ({"version_url": None}, "version_source_unconfigured")]:
            row = dict(self.row, **changes)
            fetch = Mock(side_effect=AssertionError("No network"))
            result = m.check_versions(self.cfg, [row], self.state, manual=True, fetcher=fetch)
            self.assertEqual(result["status"], "not_configured")
            self.assertEqual(result["skipped"][0]["reason"], reason)
            fetch.assert_not_called()

    def test_throttle_and_manual_override(self):
        self.state["auto_check"] = True
        fetch = Mock(return_value="1.1.0")
        self.assertEqual(m.check_versions(self.cfg, [self.row], self.state, now=100, fetcher=fetch)["status"], "updates_available")
        self.assertEqual(m.check_versions(self.cfg, [self.row], self.state, now=101, fetcher=fetch)["status"], "throttled")
        self.assertEqual(fetch.call_count, 1)
        m.check_versions(self.cfg, [self.row], self.state, manual=True, now=102, fetcher=fetch)
        self.assertEqual(fetch.call_count, 2)

    def test_failed_requests_throttle(self):
        self.state["auto_check"] = True
        fetch = Mock(side_effect=OSError("offline"))
        self.assertEqual(m.check_versions(self.cfg, [self.row], self.state, now=100, fetcher=fetch)["status"], "failed")
        self.assertEqual(m.check_versions(self.cfg, [self.row], self.state, now=101, fetcher=fetch)["status"], "throttled")
        self.assertEqual(fetch.call_count, 1)

    def test_partial_is_not_global_latest(self):
        other = dict(self.row, id="memo-other")
        fetch = Mock(side_effect=["1.0.0", OSError("offline")])
        report = m.check_versions(self.cfg, [self.row, other], self.state, manual=True, fetcher=fetch)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["checked"], ["memo-test"])

    def test_url_restrictions(self):
        for url in ["http://example.com/version.json", "https://user:pass@example.com/version.json",
                    "https://example.com/version.json?q=1", "https://example.com:8443/version.json",
                    "https://127.0.0.1/version.json", "https://evil.com/version.json",
                    "https://example.com/code.py", "https://example.com/version.json#fragment"]:
            with self.assertRaises(ValueError):
                m.validate_url(url, ["example.com", "127.0.0.1"])
        self.assertEqual(m.validate_url(self.row["version_url"], ["example.com"]), "example.com")
        with self.assertRaises(ValueError):
            m.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com/version.json")

    def test_manifest_validation_without_network(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.headers.get_content_type.return_value = "application/json"
        opener = Mock()
        opener.open.return_value = response
        public = [(2, 1, 6, "", ("8.8.8.8", 443))]
        with patch.object(m.socket, "getaddrinfo", return_value=public), patch.object(m.urllib.request, "build_opener", return_value=opener):
            response.read.return_value = b'{"id":"memo-test","version":"1.1.0"}'
            self.assertEqual(m.fetch_manifest(self.row, ["example.com"]), "1.1.0")
            for raw in [b'{"id":"wrong","version":"1.1.0"}',
                        b'{"id":"memo-test","version":"1.1.0","command":"run"}', b"x" * (m.MAX_BYTES + 1)]:
                response.read.return_value = raw
                with self.assertRaises(ValueError):
                    m.fetch_manifest(self.row, ["example.com"])
        with patch.object(m.socket, "getaddrinfo", return_value=[(2,1,6,"",("127.0.0.1",443))]), patch.object(m.urllib.request, "build_opener") as factory:
            with self.assertRaises(ValueError):
                m.fetch_manifest(self.row, ["example.com"])
            factory.assert_not_called()

    def test_lifecycle_intro_then_separate_consent(self):
        missing = [dict(self.row, installed=False)]
        self.assertEqual(m.complete_task(self.state, missing, "task1"), "pitch")
        self.state.update(pitched=True, pitch_task="task1")
        self.assertEqual(m.complete_task(self.state, [self.row], "task1"), "none")
        self.assertEqual(m.complete_task(self.state, [self.row], "task2"), "ask_update_consent")
        self.state["asked_update"] = True
        self.assertEqual(m.complete_task(self.state, [self.row], "task3"), "none")
        self.state["declined"] = True
        self.assertEqual(m.complete_task(self.state, missing, "task4"), "none")

    def test_preinstalled_extensions_ask_on_second_task(self):
        self.assertEqual(m.complete_task(self.state, [self.row], "task1"), "none")
        self.assertEqual(m.complete_task(self.state, [self.row], "task2"), "ask_update_consent")

    def test_state_read_only_missing_and_invalid_fail_closed(self):
        file = self.base / "state/state.json"
        self.assertFalse(m.read_state(file)["auto_check"])
        self.assertFalse(file.parent.exists())
        m.save_state(file, self.state)
        self.assertEqual(m.read_state(file), self.state)
        file.write_text('{"schema":1,"auto_check":"yes"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            m.read_state(file)

    def test_inventory_reports_shadowed_without_writes(self):
        roots = [self.base / "one", self.base / "two"]
        for root in roots:
            path = root / "memo-test"
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text('---\nname: memo-test\nmetadata:\n  version: "1.0.0"\n---\n', encoding="utf-8")
        before = sorted(str(p) for p in self.base.rglob("*"))
        rows = m.inventory({"satellites": [self.row]}, roots)
        self.assertTrue(rows[0]["installed"])
        self.assertEqual(rows[0]["shadowed"], [str(roots[1] / "memo-test")])
        self.assertEqual(before, sorted(str(p) for p in self.base.rglob("*")))

    def test_lock_excludes_concurrent_writer(self):
        with m.locked(self.base / "state.json"):
            with self.assertRaises(OSError):
                with m.locked(self.base / "state.json"):
                    self.fail("Second writer acquired lock")

if __name__ == "__main__":
    unittest.main()

