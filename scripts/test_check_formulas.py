import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_formulas.py"


class FormulaCheckerTests(unittest.TestCase):
    def run_cards(self, cards):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cards.json"
            path.write_text(json.dumps(cards), encoding="utf-8")
            return subprocess.run([sys.executable, "-B", str(SCRIPT), str(path)],
                                  capture_output=True, text=True)

    def test_clean_formula(self):
        result = self.run_cards([{
            "key": "B-1-1",
            "title": "已知 [E##f(t)=e^{-t}u(t)]",
            "content": "---\n① [E##f(t)=e^{-t}u(t)] 是因果信号\n",
        }])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("issues: 0", result.stdout)

    def test_trailing_operator_and_unclosed(self):
        result = self.run_cards([{
            "key": "B-2-1",
            "content": "---\n① [E##r(t) =] 全响应\n② [E##x(t)= 未完\n",
        }])
        self.assertEqual(result.returncode, 1)
        self.assertIn("trailing_operator", result.stdout)
        self.assertIn("unclosed_formula", result.stdout)

    def test_conjugate_star_is_not_trailing_operator(self):
        result = self.run_cards([{
            "key": "B-6-1",
            "content": "---\n① [E##z^*] 是共轭\n",
        }])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_formula_color(self):
        clean = self.run_cards([{
            "key": "B-1-6",
            "content": "---\n① [E##\\textcolor{#d16056}{E_k=\\frac{1}{2}mv^2}]\n",
        }])
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        bad = self.run_cards([{
            "key": "B-1-7",
            "content": "---\n① [E##\\textcolor{#d1605}{x}]\n",
        }])
        self.assertEqual(bad.returncode, 1)
        self.assertIn("invalid_formula_color", bad.stdout)

    def test_nested_cloze_allowbreak_rejected(self):
        result = self.run_cards([{
            "key": "B-1-4",
            "content": "---\n① [E##[F#1#\\text{长文本} \\allowbreak \\text{下一段}]]\n",
        }])
        self.assertEqual(result.returncode, 1)
        self.assertIn("nested_cloze_allowbreak", result.stdout)

    def test_v13_top_level_allowbreak_is_valid(self):
        result = self.run_cards([{
            "key": "B-1-5",
            "content": "---\n① [E##[F#1#\\text{第一块}]\\allowbreak[F#1#\\text{第二块}]]\n",
        }])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("nested_cloze_allowbreak", result.stdout)

    def test_dollar_and_suspicious(self):
        result = self.run_cards([{
            "key": "B-1-2",
            "content": "① 样本值 [E##\\{f(y)\\}]；残留 $x$；[E##e^{N f \\omega \\tau}]",
        }])
        self.assertEqual(result.returncode, 1)
        self.assertIn("dollar_residue", result.stdout)
        self.assertIn("suspicious_formula", result.stdout)


if __name__ == "__main__":
    unittest.main()
