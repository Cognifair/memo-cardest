import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_chapter_plan.py"


class ChapterPlanTests(unittest.TestCase):
    def run_plan(self, plan):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapter_plan.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            return subprocess.run([sys.executable, "-B", str(CHECK), str(path)],
                                  capture_output=True, text=True)

    def base(self):
        return {
            "task_id": "chem-2026",
            "source_material": "chemistry.docx",
            "split_mode": "explicit",
            "evidence": "按人教版教材章节创建",
            "chapters": [
                {"name": "必修一 第1章", "source_heading": "第一章"},
                {"name": "必修一 第2章", "source_heading": "第二章"},
            ],
        }

    def test_explicit_split_passes(self):
        result = self.run_plan(self.base())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unresolved_split_fails(self):
        plan = self.base()
        plan["split_mode"] = "unresolved"
        plan.pop("evidence", None)
        result = self.run_plan(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unresolved", result.stdout)

    def test_asked_split_requires_user_confirmation(self):
        plan = self.base()
        plan["split_mode"] = "asked"
        plan.pop("evidence", None)
        result = self.run_plan(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("confirmed_by=user", result.stdout)
        plan["confirmed_by"] = "user"
        plan["confirmation_id"] = "ask-123"
        result = self.run_plan(plan)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_chapters_fail(self):
        plan = self.base()
        plan["chapters"][1]["name"] = plan["chapters"][0]["name"]
        result = self.run_plan(plan)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate", result.stdout)


if __name__ == "__main__":
    unittest.main()
