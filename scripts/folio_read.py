#!/usr/bin/env python3
"""Collect printed-page evidence locally. Collection never approves or reorders a PDF."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata


DEFAULT_BOXES = [(0, 0, 1, .085), (0, .90, 1, 1)]


def number(text):
    s = unicodedata.normalize("NFKC", text).strip().strip("-–—·•| ").strip()
    m = re.fullmatch(r"(?:第\s*([0-9]{1,6})\s*[页頁]|(?:page\s+)?([0-9]{1,6})(?:\s+of\s+[0-9]{1,6})?)", s, re.I)
    if m:
        n = int(m.group(1) or m.group(2))
        if n > 0:
            return n
    return None


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def within(box, center):
    x, y = center
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def text_hits(pg, boxes, fitz):
    # PDF words are returned in unrotated coordinates; render crops in displayed coordinates.
    pts = pg.rect
    words = pg.get_text("words")
    groups = {}
    for word in words:
        groups.setdefault(tuple(word[5:7]), []).append(word)
    hits = []
    for group in groups.values():
        group.sort(key=lambda w: w[7])
        bbox = fitz.Rect(group[0][:4])
        for w in group[1:]:
            bbox |= fitz.Rect(w[:4])
        bbox = bbox * pg.rotation_matrix
        center = ((bbox.x0 + bbox.x1 - 2 * pts.x0) / (2 * pts.width),
                  (bbox.y0 + bbox.y1 - 2 * pts.y0) / (2 * pts.height))
        raw = " ".join(w[4] for w in group)
        n = number(raw)
        if n is not None and any(within(box, center) for box in boxes):
            hits.append({"printed": n, "text": raw, "center": [round(v, 5) for v in center]})
    return hits


def candidate(hits):
    vals = {v["printed"] for v in hits}
    return vals.pop() if len(vals) == 1 else None


def crop(pg, boxes, out, scan, fitz):
    pts = pg.rect
    names = []
    for j, (x, y, X, Y) in enumerate(boxes, 1):
        rect = fitz.Rect(pts.x0 + x * pts.width, pts.y0 + y * pts.height,
                         pts.x0 + X * pts.width, pts.y0 + Y * pts.height)
        scale = min(3, 3600 / max(1, rect.width), 1300 / max(1, rect.height))
        pix = pg.get_pixmap(clip=rect, matrix=fitz.Matrix(scale, scale),
                            colorspace=fitz.csGRAY, alpha=False)
        name = f"crops/scan-{scan:05d}-box-{j}.png"
        pix.save(str(out / name))
        names.append(name)
    return names


def contact_sheets(rows, out, warnings):
    if not rows:
        return []
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        warnings.append("Pillow unavailable: open numbered crops individually.")
        return []
    sheets = []
    for start in range(0, len(rows), 8):
        tiles = []
        for row in rows[start:start+8]:
            parts = []
            for name in row["crops"]:
                with Image.open(out / name) as im:
                    a = im.convert("L")
                a.thumbnail((790, 160), Image.Resampling.LANCZOS)
                parts.append(a)
            tile = Image.new("L", (805, sum(p.height+4 for p in parts)+23), "white")
            ImageDraw.Draw(tile).text((4, 3), f"SCAN {row['scan']} (original index)", fill=0)
            y = 22
            for im in parts:
                tile.paste(im, (4, y))
                y += im.height + 4
            tiles.append(tile)
        height = max(t.height for t in tiles)
        sheet = Image.new("L", (1610, height * ((len(tiles) + 1) // 2)), 225)
        for i, tile in enumerate(tiles):
            sheet.paste(tile, ((i % 2) * 805, (i // 2) * height))
        name = f"overview-{start//8+1:04d}.png"
        sheet.save(out/name)
        sheets.append(name)
    return sheets


def tesseract_exe():
    exe = shutil.which("tesseract")
    if not exe and os.name == "nt":
        path = Path(os.environ.get("ProgramFiles", ""))/"Tesseract-OCR"/"tesseract.exe"
        if path.is_file():
            exe = str(path.resolve())
    return exe


def parse_tsv(payload, names):
    found = {name: [] for name in names}
    lines = {}
    seen = set()
    reader = csv.DictReader(io.StringIO(payload), delimiter="\t", quoting=csv.QUOTE_NONE)
    for r in reader:
        page = int(r["page_num"])
        if not 1 <= page <= len(names):
            raise ValueError("Invalid OCR page index")
        if r["level"] == "1":
            seen.add(page)
        if r["level"] == "5" and r["text"].strip():
            lines.setdefault((page, r["block_num"], r["par_num"], r["line_num"]), []).append(r)
    if seen != set(range(1, len(names)+1)):
        raise ValueError("Incomplete OCR batch; no indices trusted")
    for (page, *_), group in lines.items():
        # An exact line number is useful. Isolated words are also accepted at a
        # large physical gap (e.g. footer imprint and folio sharing one line).
        raw = " ".join(w["text"] for w in group)
        n = number(raw)
        trials = [(n, raw, min(float(w["conf"]) for w in group))] if n else []
        if not trials and len(group) > 1:
            words = sorted(group, key=lambda w: int(w["left"]))
            for i, w in enumerate(words):
                n = number(w["text"])
                if n is None:
                    continue
                left = int(w["left"])
                right = left + int(w["width"])
                gap = max(25, int(w["height"])*3)
                if (i == 0 or left-int(words[i-1]["left"])-int(words[i-1]["width"]) >= gap) and (
                    i+1 == len(words) or int(words[i+1]["left"])-right >= gap):
                    trials.append((n, w["text"], float(w["conf"])))
        for n, raw, conf in trials:
            if n is not None:
                found[names[page-1]].append({"printed": n, "text": raw, "confidence": round(conf,1),
                                             "crop": names[page-1]})
    return found


def run_ocr(rows, out, boxes, warnings):
    exe = tesseract_exe()
    if not exe:
        warnings.append("Tesseract unavailable: review the crops, or install local Tesseract with eng data.")
        return
    # Separate narrow user-selected numeric crops from broad margin bands.
    batches = {}
    for row in rows:
        for name, box in zip(row["crops"], boxes):
            focused = (box[2]-box[0] <= .4 and box[3]-box[1] <= .15)
            batches.setdefault(focused, []).append(name)
    found = {}
    for focused, group in batches.items():
        for i in range(0, len(group), 96):
            names = group[i:i+96]
            listing = out/"ocr-batch.txt"
            listing.write_text("\n".join(names)+"\n", encoding="ascii")
            # ASCII relative crop names avoid locale-dependent Tesseract list parsing.
            cmd = [exe, listing.name, "stdout", "-l", "eng", "--psm", "6" if focused else "11"]
            if focused:
                cmd.extend(["-c", "tessedit_char_whitelist=0123456789"])
            cmd.append("tsv")
            try:
                result = subprocess.run(cmd, cwd=out, capture_output=True, check=True, timeout=240)
                found.update(parse_tsv(result.stdout.decode("utf-8", errors="replace"), names))
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
                warnings.append(f"OCR batch unavailable ({type(exc).__name__}); corresponding pages need review.")
            finally:
                listing.unlink(missing_ok=True)
    for row in rows:
        if not all(n in found for n in row["crops"]):
            continue
        hits = [hit for name in row["crops"] for hit in found[name]]
        row["ocr_candidates"] = hits
        n = candidate(hits)
        if n is not None and max(h["confidence"] for h in hits) >= 60 and not row["text_candidates"]:
            row.update(printed=n, method="ocr")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("out", type=Path, help="New evidence directory")
    p.add_argument("--mode", choices=("visual", "ocr"), default="visual")
    p.add_argument("--box", type=float, nargs=4, action="append", metavar=("X0", "Y0", "X1", "Y1"),
                   help="Relative crop in displayed orientation (repeatable); default: top + bottom full width")
    p.add_argument("--all-crops", action="store_true", help="Also render proof images for text-layer hits")
    a = p.parse_args()
    if not a.source.is_file():
        p.error("PDF not found")
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            p.error("PyMuPDF is required")
    boxes = a.box or DEFAULT_BOXES
    if any(not (0 <= x < X <= 1 and 0 <= y < Y <= 1) for x,y,X,Y in boxes):
        p.error("Invalid relative crop")
    out = a.out.resolve()
    if out.exists():
        p.error("Use a new evidence directory")
    input_hash = digest(a.source)
    warnings, rows = [], []
    with fitz.open(a.source) as pdf:
        if not pdf.is_pdf or pdf.needs_pass or not len(pdf):
            p.error("An unlocked, nonempty PDF is required")
        (out/"crops").mkdir(parents=True)
        for scan, pg in enumerate(pdf, 1):
            hits = text_hits(pg, boxes, fitz)
            n = candidate(hits)
            method = "text" if n is not None else ("visual_required" if a.mode=="visual" else "review")
            row = {"scan": scan, "printed": n, "method": method, "text_candidates": hits}
            if n is None or a.all_crops:
                row["crops"] = crop(pg, boxes, out, scan, fitz)
            rows.append(row)
    if a.mode == "ocr":
        run_ocr([r for r in rows if r["printed"] is None], out, boxes, warnings)
    sheets = contact_sheets([r for r in rows if r.get("crops") and (a.all_crops or r["printed"] is None)], out, warnings)
    if digest(a.source) != input_hash:
        p.error("Source changed during collection; discard this run")
    evidence = {"schema": 1, "source_sha256": input_hash, "source_name": a.source.name,
                "page_count": len(rows), "boxes": boxes, "pages": rows, "overviews": sheets, "warnings": warnings}
    (out/"evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"evidence":"evidence.json", "pages":len(rows), "unread":sum(r["printed"] is None for r in rows),
                      "warnings":warnings}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
