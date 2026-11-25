import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "inspect_source.py"
SPEC = importlib.util.spec_from_file_location("inspect_source", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_docx(path, text, images=0):
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
        for index in range(images):
            archive.writestr(f"word/media/image{index}.png", b"not-a-real-png")


class InspectSourceTests(unittest.TestCase):
    def test_image_heavy_docx_requires_paginated_input_before_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image-only.docx"
            make_docx(path, "标题", images=3)
            result = MODULE.inspect(path, 8)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["image_count"], 3)
        self.assertEqual(result["recommendation"], "render_fixed_layout_pdf_then_check")

    def test_docx_with_text_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "text.docx"
            make_docx(path, "这是一段足够长的正文。" * 30)
            result = MODULE.inspect(path, 8)
        self.assertEqual(result["text_layer"], "present")
        self.assertEqual(result["recommendation"], "continue")

    def test_image_is_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.png"
            from PIL import Image
            Image.new("RGB", (12, 8), "white").save(path)
            self.assertEqual(MODULE.inspect(path, 8)["text_layer"], "absent")

    def test_text_file_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("这是一段正文。", encoding="utf-8")
            self.assertEqual(MODULE.inspect(path, 8)["text_layer"], "present")

    def test_unknown_extension_is_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.xyz"
            path.write_bytes(b"x")
            self.assertEqual(MODULE.inspect(path, 8)["recommendation"], "ask_user_to_convert")


if __name__ == "__main__":
    unittest.main()
