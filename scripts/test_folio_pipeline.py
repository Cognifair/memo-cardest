"""Regression tests for the material checkpoint and its three consumers (offline)."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

try:
    import pymupdf
except ImportError:
    pymupdf = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import folio_gate
import folio_read
import inspect_source
import use_source


def cli(module, *args):
    out = io.StringIO()
    with patch.object(sys, "argv", [module.__name__, *map(str, args)]), redirect_stdout(out):
        code = module.main()
    return code, json.loads(out.getvalue()) if out.getvalue().strip() else None


@unittest.skipUnless(pymupdf, "requires PyMuPDF")
class TestFolioPipeline(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def source(self, name, leaves):
        """Each fixture specifies body marker, printed number or None, raster folio flag."""
        path = self.root / (name + ".pdf")
        with pymupdf.open() as doc:
            for marker, n, raster in leaves:
                pg = doc.new_page(width=200, height=320)
                pg.insert_text((25, 110), marker)
                if n is None:
                    continue
                if not raster:
                    pg.insert_text((150, 305), str(n))
                else:
                    # Actual visible raster digit; no OCR or text object for this folio.
                    with pymupdf.open() as label:
                        canvas = label.new_page(width=40, height=20)
                        canvas.insert_text((4, 14), str(n))
                        pix = canvas.get_pixmap(matrix=pymupdf.Matrix(3, 3))
                        pg.insert_image(pymupdf.Rect(145, 289, 185, 309), stream=pix.tobytes("png"))
            doc.save(path)
        return path

    def evidence(self, pdf):
        folder = self.root / (pdf.stem + "-evidence")
        with patch.object(folio_read, "run_ocr", side_effect=AssertionError("visual must not invoke OCR")):
            self.assertEqual(cli(folio_read, pdf, folder, "--mode", "visual")[0], 0)
        path = folder / "evidence.json"
        return path, json.loads(path.read_text(encoding="utf8"))

    def review(self, source_hash, **values):
        path = self.root / "review.json"
        path.write_text(json.dumps({"source_sha256": source_hash, **values}), encoding="utf8")
        return path

    def extract(self, pdf, receipt, expected):
        dest = self.root / "result.json"
        args = ("--folio-receipt", receipt) if receipt else ()
        self.assertEqual(cli(use_source, "text", pdf, dest, *args)[0], 0)
        pages = json.loads(dest.read_text(encoding="utf8"))["pages"]
        self.assertEqual([p["text"].splitlines()[0] for p in pages], expected)

    def test_no_receipt_blocks_all_consumers_before_any_engine_or_file_write(self):
        pdf = self.source("unchecked", [("one", 1, False), ("two", 2, False)])
        self.assertEqual(cli(inspect_source, pdf)[0], 2)
        with patch.object(use_source.subprocess, "run", side_effect=AssertionError("launched an engine")), \
             patch.object(use_source.shutil, "which", side_effect=AssertionError("probed an engine")):
            for action in ("prepare", "local", "text"):
                with self.subTest(action=action):
                    dest = self.root / ("out-" + action)
                    code, info = cli(use_source, action, pdf, dest)
                    self.assertEqual((code, info["status"]), (2, "blocked"))
                    self.assertFalse(dest.exists())

    def test_text_and_visual_reads_work_together_and_wrong_file_is_blocked(self):
        pdf = self.source("mixed", [("alpha", 9, False), ("beta", 10, True), ("gamma", 11, False)])
        evfile, data = self.evidence(pdf)
        self.assertEqual([r["printed"] for r in data["pages"]], [9, None, 11])
        self.assertEqual(data["pages"][1]["method"], "visual_required")
        self.assertTrue(all((evfile.parent/n).is_file() for n in data["pages"][1]["crops"]))
        unchecked = self.root/"unchecked-result"
        self.assertEqual(cli(folio_gate, "finalize", pdf, evfile, unchecked)[0], 2)
        self.assertFalse((unchecked/"receipt.json").exists())
        rev = self.review(data["source_sha256"], readings=[
            {"scan": 2, "number": 10, "reason":"Raster footer on scan 2 shows 10"}])
        code, passed = cli(folio_gate, "finalize", pdf, evfile, self.root/"pass", "--review", rev)
        self.assertEqual((code, passed["status"]), (0, "original"))
        self.extract(pdf, passed["receipt"], ["alpha", "beta", "gamma"])
        other = self.source("changed", [("DIFFERENT", 9, False), ("beta", 10, True), ("gamma", 11, False)])
        self.assertEqual(cli(use_source, "text", other, self.root/"wrong", "--folio-receipt", passed["receipt"])[0], 2)
        self.assertFalse((self.root/"wrong").exists())

    def test_unprinted_cover_stays_first_and_g14_rejects_old_pdf_after_reorder(self):
        pdf = self.source("cover", [("Cover", None, False), ("Second", 8, False), ("First", 7, False)])
        evfile, data = self.evidence(pdf)
        self.assertEqual(cli(folio_gate, "finalize", pdf, evfile, self.root/"hold")[0], 2)
        rev = self.review(data["source_sha256"], reason="Unnumbered cover and separately numbered main text",
            order=[{"scan": 1, "section":"front", "label":"cover", "reason":"Cover artwork; keep first"},
                   {"scan": 3, "section":"text", "label":7, "reason":"Footer shows 7"},
                   {"scan": 2, "section":"text", "label":8, "reason":"Footer shows 8"}])
        code, passed = cli(folio_gate, "finalize", pdf, evfile, self.root/"processed", "--review", rev)
        self.assertEqual((code, passed["status"]), (0, "reordered"))
        self.assertEqual(cli(inspect_source, pdf, "--folio-receipt", passed["receipt"])[0], 2)
        self.extract(passed["input"], passed["receipt"], ["Cover", "First", "Second"])

    def test_single_page_does_not_require_a_receipt(self):
        pdf = self.source("one", [("standalone", None, False)])
        code, info = cli(inspect_source, pdf)
        self.assertEqual((code, info["page_order"]), (0, "not_applicable"))
        self.extract(pdf, None, ["standalone"])


if __name__ == "__main__":
    unittest.main()
