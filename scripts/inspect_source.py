#!/usr/bin/env python3
"""G1.4: inspect only a checked reading order; never run OCR or upload."""
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


def blocked(kind, reason, recommendation="complete_page_order", **extra):
    return {"kind": kind, "status": "blocked", "page_order": "pending",
            "reason": reason, "recommendation": recommendation, **extra}


def inspect_pdf(path, max_pages, receipt=None):
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            PdfReader = None
        if PdfReader:
            with path.open("rb") as fp:
                reader = PdfReader(fp)
                pages = len(reader.pages)
        else:
            import pymupdf
            with pymupdf.open(path) as doc:
                pages = len(doc)
    except Exception as exc:
        return blocked("pdf", "unknown_page_count:" + type(exc).__name__)
    if pages < 1:
        return blocked("pdf", "empty_pdf")
    if pages > 1 or receipt is not None:
        if not receipt:
            return blocked("pdf", "page_order_receipt_required", pages=pages)
        try:
            from folio_gate import verify_gate
            proof = verify_gate(path, receipt)
            if not proof["ok"]:
                return blocked("pdf", proof["reason"], pages=pages)
        except Exception as exc:
            return blocked("pdf", "cannot_verify_receipt:" + type(exc).__name__, pages=pages)
    order_state = "checked" if pages > 1 else "not_applicable"
    try:
        if PdfReader:
            with path.open("rb") as fp:
                reader = PdfReader(fp)
                text = "".join((page.extract_text() or "") for page in reader.pages[:max_pages])
        else:
            with pymupdf.open(path) as doc:
                text = "".join(doc[i].get_text() for i in range(min(pages, max_pages)))
    except Exception as exc:
        return {"kind": "pdf", "pages": pages, "page_order": order_state, "text_layer": "unknown",
                "recommendation": "inspect_manually", "reason": type(exc).__name__}
    text = clean(text)
    if len(text) < 50:
        layer, recommendation = "absent", "ask_user_ocr_route"
    elif len(text) < 200:
        layer, recommendation = "sparse", "inspect_sample_or_ocr"
    else:
        layer, recommendation = "present", "continue"
    return {"kind": "pdf", "text_layer": layer, "pages": pages, "page_order": order_state,
            "text_chars": len(text), "sample": text[:200],
            "recommendation": recommendation}


def inspect(path, max_pages, receipt=None):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        result = inspect_docx(path)
        origin = {"kind": "docx", "original_docx": str(path.resolve()),
                  "card_write_requires": "docx_manifest"}
        result["material_origin"] = origin
        if result.get("image_count", 0) > 1 and result.get("text_layer") in ("absent", "sparse"):
            return blocked("docx", "possible_scan_sequence", "render_fixed_layout_pdf_then_check",
                           image_count=result["image_count"], material_origin=origin)
        return result
    if suffix == ".pdf":
        return inspect_pdf(path, max_pages, receipt)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}:
        try:
            from PIL import Image
            with Image.open(path) as im:
                frames = im.n_frames if hasattr(im, "n_frames") else 1
        except Exception as exc:
            return blocked("image", "unknown_frame_count:" + type(exc).__name__, "inspect_image_frames")
        if frames != 1:
            return blocked("image", "multi_frame_image", "bundle_images_then_check", frames=frames)
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


def checked_source(args):
    if len(args.path) != 1:
        return blocked("collection", "input_is_a_sequence", "bundle_related_pages_or_check_independent_files_separately")
    path = args.path[0]
    if not path.is_file():
        return blocked("unknown", "file_not_found", "check_input")
    result = inspect(path, max(1, args.max_pages), args.folio_receipt)
    if result.get("status") != "blocked":
        result.setdefault("page_order", "not_applicable" if result.get("text_layer") not in (None, "unknown") else "undetermined")
    result.update(file=path.name, size=path.stat().st_size)
    return result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="+")
    parser.add_argument("--folio-receipt", type=Path, help="G1.3 receipt for the actual input PDF")
    parser.add_argument("--max-pages", type=int, default=8)
    args = parser.parse_args()
    result = checked_source(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
