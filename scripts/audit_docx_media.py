#!/usr/bin/env python3
"""Audit media references in a DOCX before turning them into [Pic#] cards.

This is a *review gate*, not an auto-approver. WMF/EMF metafiles, external
links, and relationship/content-type mismatches are always left for review.
The original media bytes are preserved in the manifest and, optionally, in an
assets directory so a dropped bracket cannot become a silently lost bracket.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
V_NS = "urn:schemas-microsoft-com:vml"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

R_ID = f"{{{R_NS}}}id"
R_EMBED = f"{{{R_NS}}}embed"
R_LINK = f"{{{R_NS}}}link"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"II*\x00") or data.startswith(b"MM\x00*"):
        return "tiff"
    if data.startswith(b"\xd7\xcd\xc6\x9a") or data.startswith(b"\x01\x00\x09\x00"):
        return "wmf"
    if len(data) >= 44 and data.startswith(b"\x01\x00\x00\x00") and data[40:44] == b" EMF":
        return "emf"
    return "unknown"


FORMAT_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "wmf": "image/x-wmf",
    "emf": "image/x-emf",
}


def extension(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    return {"jpg": "jpeg", "jpe": "jpeg"}.get(suffix, suffix)


def element_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{{{W_NS}}}t")).strip()


def parse_rels(raw: bytes) -> dict[str, dict]:
    root = ET.fromstring(raw)
    rels = {}
    for rel in root.findall(f"{REL_NS}Relationship"):
        rels[rel.get("Id")] = {
            "target": rel.get("Target", ""),
            "type": rel.get("Type", ""),
            "external": rel.get("TargetMode") == "External",
        }
    return rels


def parse_content_types(raw: bytes) -> dict[str, str]:
    root = ET.fromstring(raw)
    out = {}
    for node in root.findall(f"{{{CT_NS}}}Override"):
        out[node.get("PartName", "")] = node.get("ContentType", "")
    return out


def parse_length(value: str) -> float | None:
    match = re.match(r"^\s*([0-9.]+)\s*(pt|px|in|cm|mm)?\s*$", value or "")
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    factor = {"px": 1.0, "pt": 96 / 72, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}[unit]
    return round(number * factor, 2)


def vml_size(paragraph: ET.Element) -> tuple[float | None, float | None]:
    shape = next(paragraph.iter(f"{{{V_NS}}}shape"), None)
    if shape is None:
        return None, None
    style = shape.get("style", "")
    width = re.search(r"(?:^|;)width:([^;]+)", style, re.I)
    height = re.search(r"(?:^|;)height:([^;]+)", style, re.I)
    return (parse_length(width.group(1)) if width else None,
            parse_length(height.group(1)) if height else None)


def drawing_size(paragraph: ET.Element) -> tuple[float | None, float | None]:
    extent = next(paragraph.iter(f"{{{WP_NS}}}extent"), None)
    if extent is None:
        return None, None
    try:
        return (round(int(extent.get("cx")) / 9525, 2),
                round(int(extent.get("cy")) / 9525, 2))
    except (TypeError, ValueError):
        return None, None


def image_size(data: bytes, fmt: str) -> tuple[int | None, int | None]:
    if fmt not in {"png", "jpeg", "gif", "bmp", "webp", "tiff"}:
        return None, None
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            return image.width, image.height
    except Exception:
        return None, None


def audit(docx_path: Path, assets_dir: Path | None = None) -> dict:
    source_hash = sha256(docx_path.read_bytes())
    with zipfile.ZipFile(docx_path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        rels = parse_rels(archive.read("word/_rels/document.xml.rels"))
        content_types = parse_content_types(archive.read("[Content_Types].xml"))
        media_parts = {name for name in archive.namelist() if name.startswith("word/media/")}

        paragraphs = list(document.iter(f"{{{W_NS}}}p"))
        paragraph_texts = [element_text(p) for p in paragraphs]
        references = []
        for paragraph_index, paragraph in enumerate(paragraphs, 1):
            text = paragraph_texts[paragraph_index - 1]
            blips = list(paragraph.iter(f"{{{A_NS}}}blip"))
            vml_images = list(paragraph.iter(f"{{{V_NS}}}imagedata"))
            if not text and not blips and not vml_images:
                continue
            display_w, display_h = drawing_size(paragraph)
            if display_w is None:
                display_w, display_h = vml_size(paragraph)

            entries = []
            # Keep source order even when modern and legacy objects share a paragraph.
            for node in paragraph.iter():
                if node.tag == f"{{{A_NS}}}blip":
                    rid = node.get(R_EMBED) or node.get(R_LINK)
                    if rid:
                        entries.append((rid, "drawing"))
                elif node.tag == f"{{{V_NS}}}imagedata":
                    rid = node.get(R_ID)
                    if rid:
                        entries.append((rid, "vml"))

            for rid, embedding in entries:
                rel = rels.get(rid, {})
                reasons = []
                target = rel.get("target", "")
                external = rel.get("external", False)
                part = ""
                data = b""
                if external:
                    reasons.append("external_link")
                elif target:
                    part = posixpath.normpath(posixpath.join("word", target))
                    if part.startswith("../") or part not in media_parts:
                        reasons.append("missing_media_part")
                    else:
                        data = archive.read(part)
                else:
                    reasons.append("missing_relationship")

                fmt = detect_format(data) if data else "unknown"
                declared = content_types.get("/" + part, "") if part else ""
                if not declared and part:
                    ext = extension(part)
                    declared = f"image/{ext}" if ext else ""
                expected = FORMAT_MIME.get(fmt, "")
                declared_mime = declared.split(";")[0].strip().lower()
                if declared_mime and declared_mime.startswith("image/"):
                    aliases = {"image/wmf": "image/x-wmf", "image/emf": "image/x-emf"}
                    declared_norm = aliases.get(declared_mime, declared_mime)
                    if expected and declared_norm != expected:
                        reasons.append("declared_type_mismatch")
                if fmt in {"wmf", "emf"}:
                    reasons.append("vector_metafile")
                if fmt == "unknown" and data:
                    reasons.append("unknown_format")
                if not data:
                    reasons.append("empty_media")

                pixel_w, pixel_h = image_size(data, fmt)
                ratio = (round(pixel_w / display_w, 2)
                         if pixel_w and display_w else None)
                if ratio is not None and (ratio > 8 or ratio < 0.1):
                    reasons.append("size_ratio_outlier")
                source_name = f"{sha256(data)[:16]}.{fmt}" if data else ""
                if data and assets_dir is not None:
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    (assets_dir / source_name).write_bytes(data)

                references.append({
                    "paragraph_index": paragraph_index,
                    "embedding": embedding,
                    "relationship_id": rid,
                    "target": target,
                    "part": part,
                    "external": external,
                    "declared_content_type": declared,
                    "detected_format": fmt,
                    "source_sha256": sha256(data) if data else None,
                    "source_file": source_name,
                    "bytes": len(data),
                    "pixel_width": pixel_w,
                    "pixel_height": pixel_h,
                    "word_display_width_px": display_w,
                    "word_display_height_px": display_h,
                    "pixel_per_display_ratio": ratio,
                    "anchor_text": text[:400],
                    "context_before": (paragraph_texts[paragraph_index - 2]
                                       if paragraph_index >= 2 else "")[:300],
                    "context_after": (paragraph_texts[paragraph_index]
                                      if paragraph_index < len(paragraphs) else "")[:300],
                    "decision": "needs_review" if reasons else "candidate",
                    "review_reasons": reasons,
                })

        return {
            "docx": str(docx_path.resolve()),
            "docx_sha256": source_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "references": references,
            "summary": {
                "references": len(references),
                "candidates": sum(1 for r in references if r["decision"] == "candidate"),
                "needs_review": sum(1 for r in references if r["decision"] == "needs_review"),
                "vector_metafiles": sum(1 for r in references
                                        if "vector_metafile" in r["review_reasons"]),
            },
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="DOCX file")
    parser.add_argument("--out", required=True, help="media_audit.json")
    parser.add_argument("--assets-dir", help="preserve original media bytes here")
    args = parser.parse_args(argv)

    docx_path = Path(args.input).resolve(strict=True)
    assets = Path(args.assets_dir).resolve() if args.assets_dir else None
    result = audit(docx_path, assets)
    out = Path(args.out).resolve()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
