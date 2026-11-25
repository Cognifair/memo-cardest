import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_docx_media.py"
CHECK = ROOT / "scripts" / "check_media_refs.py"


def make_docx(path: Path):
    document = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<w:body>
<w:p><w:r><w:t>题干 [</w:t></w:r><w:r><w:drawing><wp:extent cx="190500" cy="190500"/>
<a:graphic><a:graphicData><a:blip r:embed="rId1"/></a:graphicData></a:graphic></w:drawing></w:r>
<w:r><w:t>] 结束</w:t></w:r></w:p>
<w:p><w:r><w:t>正常图</w:t></w:r><w:r><w:drawing><wp:extent cx="9525" cy="9525"/>
<a:graphic><a:graphicData><a:blip r:embed="rId2"/></a:graphicData></a:graphic></w:drawing></w:r></w:p>
</w:body></w:document>'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.wmf"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/>
</Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Override PartName="/word/media/image1.wmf" ContentType="image/x-wmf"/>
<Override PartName="/word/media/image2.png" ContentType="image/png"/>
</Types>'''
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                        "0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", rels)
        archive.writestr("word/media/image1.wmf", b"\xd7\xcd\xc6\x9a" + b"\x00" * 40)
        archive.writestr("word/media/image2.png", png)


class MediaAuditTests(unittest.TestCase):
    def test_wmf_is_review_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "sample.docx"
            out = Path(tmp) / "audit.json"
            assets = Path(tmp) / "assets"
            make_docx(docx)
            result = subprocess.run([sys.executable, "-B", str(AUDIT), str(docx),
                                     "--out", str(out), "--assets-dir", str(assets)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            refs = data["references"]
            self.assertEqual(len(refs), 2)
            wmf = next(r for r in refs if r["detected_format"] == "wmf")
            self.assertEqual(wmf["decision"], "needs_review")
            self.assertIn("vector_metafile", wmf["review_reasons"])
            self.assertIn("题干", wmf["anchor_text"])
            self.assertTrue((assets / wmf["source_file"]).exists())
            png = next(r for r in refs if r["detected_format"] == "png")
            self.assertEqual(png["decision"], "candidate")

    def test_media_refs_are_checked_per_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            cards = Path(tmp) / "cards.json"
            media = Path(tmp) / "media.json"
            cards.write_text(json.dumps([{
                "key": "B-1-1",
                "content": "---\n① [Pic#ID/good#]\n② [Pic#ID/missing#]\n③ [Pic#ID/bad#]\n",
            }]), encoding="utf-8")
            media.write_text(json.dumps({"files": {
                "good": {"decision": "accepted", "source_file": "a.png",
                         "source_sha256": "a" * 64, "converted_sha256": "b" * 64},
                "bad": {"decision": "accepted", "source_file": "b.wmf",
                        "source_sha256": "c" * 64, "converted_sha256": "d" * 64},
            }}), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", str(CHECK), str(cards),
                                     "--media-map", str(media)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing_media_record", result.stdout)
            self.assertIn("vector_source_not_traceable", result.stdout)
            self.assertNotIn("good", result.stdout)


if __name__ == "__main__":
    unittest.main()
