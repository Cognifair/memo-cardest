#!/usr/bin/env python3
"""Inspect a source file for text layer vs image-only pages. Read-only; no OCR, no network."""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def inspect_docx(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            images = [name for name in names if name.startswith("word/media/")]
            document = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return {"kind": "docx", "text_layer": "unknown", "recommendation": "inspect_manually"}
    try:
        root = ElementTree.fromstring(document)
        text = "".join(node.text or "" for node in root.iter(WORD_NS + "t"))
    except ElementTree.ParseError:
        return {"kind": "docx", "text_layer": "unknown", "recommendation": "inspect_manually"}
    text = clean(text)
    if len(text) < 50 and images:
        layer, recommendation = "absent", "ask_user_ocr_route"
    elif len(text) < 200 and images:
        layer, recommendation = "sparse", "inspect_sample_or_ocr"
    else:
        layer, recommendation = "present", "continue"
    return {"kind": "docx", "text_layer": layer, "text_chars": len(text),
            "image_count": len(images), "sample": text[:200],
            "recommendation": recommendation}


def inspect_pdf(path, max_pages):
    try:
        import pypdf
    except ImportError:
        return {"kind": "pdf", "text_layer": "unknown", "recommendation": "inspect_manually",
                "reason": "pypdf_not_installed"}
    try:
        reader = pypdf.PdfReader(str(path))
        pages = len(reader.pages)
        text = "".join((page.extract_text() or "") for page in reader.pages[:max_pages])
    except Exception as exc:
        return {"kind": "pdf", "text_layer": "unknown", "recommendation": "inspect_manually",
                "reason": type(exc).__name__}
    text = clean(text)
    if len(text) < 50:
        layer, recommendation = "absent", "ask_user_ocr_route"
    elif len(text) < 200:
        layer, recommendation = "sparse", "inspect_sample_or_ocr"
    else:
        layer, recommendation = "present", "continue"
    return {"kind": "pdf", "text_layer": layer, "pages": pages,
            "text_chars": len(text), "sample": text[:200],
            "recommendation": recommendation}


def inspect(path, max_pages):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return inspect_docx(path)
    if suffix == ".pdf":
        return inspect_pdf(path, max_pages)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return {"kind": "image", "text_layer": "absent", "image_count": 1,
                "recommendation": "ask_user_ocr_route"}
    if suffix in {".txt", ".md", ".markdown", ".csv", ".json"}:
        try:
            text = clean(path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            return {"kind": "text", "text_layer": "unknown", "recommendation": "inspect_manually"}
        return {"kind": "text", "text_layer": "present" if text else "absent",
                "text_chars": len(text), "sample": text[:200],
                "recommendation": "continue" if text else "ask_user_for_source"}
    return {"kind": suffix.lstrip(".") or "unknown", "text_layer": "unknown",
            "recommendation": "ask_user_to_convert"}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-pages", type=int, default=8)
    args = parser.parse_args()
    if not args.path.is_file():
        print(json.dumps({"status": "error", "reason": "file_not_found"}, ensure_ascii=False))
        return 1
    result = inspect(args.path, max(1, args.max_pages))
    result["file"] = args.path.name
    result["size"] = args.path.stat().st_size
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
