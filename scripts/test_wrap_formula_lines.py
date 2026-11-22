import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wrap_formula_lines.py"


class WrapFormulaLinesTests(unittest.TestCase):
    def run_wrap(self, cards):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cards.json"
            output = Path(tmp) / "wrapped.json"
            source.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(source),
                                     "--output", str(output)],
                                    capture_output=True, text=True)
            content = output.read_text(encoding="utf-8") if output.exists() else None
            return result, content

    def test_wraps_answer_line_and_preserves_head(self):
        result, output = self.run_wrap([{
            "key": "B-1-1",
            "content": "[T#B,!36b59d# 测试 ]\n---\n① [T#B#要点]信号是 [E##f(t)] 的函数\n② 普通说明\n",
        }])
        self.assertEqual(result.returncode, 0, result.stderr)
        card = json.loads(output)[0]
        wrapped = card["content_wrapped"]
        self.assertIn("① [E##[F#1#", wrapped)
        self.assertIn(r"\text{", wrapped)
        self.assertIn(r"\allowbreak", wrapped)
        self.assertIn("② [E##[F#2#", wrapped)
        self.assertIn("[T#B,!36b59d# 测试 ]", wrapped)

    def test_splits_math_at_top_level_comma(self):
        result, output = self.run_wrap([{
            "key": "B-1-2",
            "content": "---\n① [E##a=1,b=2]\n",
        }])
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapped = json.loads(output)[0]["content_wrapped"]
        self.assertIn(r"a=1,", wrapped)
        self.assertIn(r"b=2", wrapped)
        self.assertIn(r"\allowbreak", wrapped)

    def test_rejects_image_tags(self):
        result, _ = self.run_wrap([{
            "key": "B-1-3",
            "content": "---\n① [Pic#ID/abc#]\n",
        }])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported tag", result.stderr)


if __name__ == "__main__":
    unittest.main()
