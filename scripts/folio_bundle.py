"""Pack an explicitly ordered set of scans for the Memo-Cardest PDF folio gate."""
import argparse
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path


def digest(fp):
    h = hashlib.sha256()
    for part in iter(lambda: fp.read(1024 * 1024), b""):
        h.update(part)
    return h.hexdigest()


def page_dpi(info, orientation):
    raw = info.get("dpi")
    try:
        dx, dy = map(float, raw)
        if not all(math.isfinite(x) and 1 <= x <= 10000 for x in (dx, dy)):
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        dx = dy = 150.0  # No physical size supplied; never resample image pixels.
    return (dy, dx) if orientation in (5, 6, 7, 8) else (dx, dy)


def embed(doc, frame, dpi, pdf):
    if frame.mode in ("P", "PA", "RGB", "RGBA", "L", "LA", "1"):
        # Explicitly keep the alpha channel as a separate PDF soft mask.
        alpha = None
        if "A" in frame.getbands() or "transparency" in frame.info:
            frame = frame.convert("RGBA")
            alpha = frame.getchannel("A")
            frame = frame.convert("RGB")
        if frame.mode == "P":
            frame = frame.convert("RGB")
        if frame.mode == "1":
            frame = frame.convert("L")
        cs = pdf.csRGB if frame.mode == "RGB" else pdf.csGRAY
    elif frame.mode == "CMYK":
        cs, alpha = pdf.csCMYK, None
    else:
        raise ValueError(f"Unsupported source pixel mode: {frame.mode}; no automatic downconversion")
    w, h = frame.size
    if not (0 < w <= 100000 and 0 < h <= 100000):
        raise ValueError("Unsupported source dimensions")
    page = doc.new_page(width=w * 72 / dpi[0], height=h * 72 / dpi[1])
    if alpha is None:
        pix = pdf.Pixmap(cs, w, h, frame.tobytes(), False)
        page.insert_image(page.rect, pixmap=pix, keep_proportion=False)
    else:
        import io
        img = io.BytesIO()
        mask = io.BytesIO()
        frame.save(img, format="PNG")
        alpha.save(mask, format="PNG")
        page.insert_image(page.rect, stream=img.getvalue(), mask=mask.getvalue(), keep_proportion=False)


def build(paths, out):
    from PIL import Image, ImageOps
    import pymupdf as pdf
    if not paths:
        raise ValueError("At least one image required")
    if out.exists():
        raise FileExistsError(f"Output directory already exists: {out}")
    rows = []
    out.parent.mkdir(parents=True, exist_ok=True)
    # Stage everything so a bad later frame never exposes a partial bundle.
    with tempfile.TemporaryDirectory(prefix="folio-bundle-", dir=out.parent) as tmp:
        stage = Path(tmp)
        with pdf.open() as doc:
            for path in paths:
                path = path.resolve(strict=True)
                with path.open("rb") as fp:
                    sha = digest(fp)
                    fp.seek(0)
                    head = fp.read(26)
                    fp.seek(0)
                    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 25 and head[24] > 8:
                        raise ValueError(f"{path}: high-bit-depth PNG needs explicit conversion")
                    with Image.open(fp) as im:
                        if im.format not in {"PNG", "TIFF", "JPEG", "BMP", "WEBP"}:
                            raise ValueError(f"{path}: unsupported format {im.format}")
                        n = getattr(im, "n_frames", 1)
                        if n != 1 and im.format != "TIFF":
                            raise ValueError(f"{path}: animated images are not paginated TIFFs")
                        for j in range(n):
                            im.seek(j)
                            if im.format == "TIFF":
                                bits = im.tag_v2.get(258, (1,))
                                if max(bits if isinstance(bits, tuple) else (bits,)) > 8:
                                    raise ValueError(f"{path}: high-bit-depth TIFF needs explicit conversion")
                            orientation = int(im.getexif().get(274, 1))
                            if not 1 <= orientation <= 8:
                                raise ValueError(f"{path}: unknown EXIF orientation {orientation}")
                            dpi = page_dpi(im.info, orientation)
                            # Pillow applies TIFF orientation while loading; this removes the tag.
                            im.load()
                            view = ImageOps.exif_transpose(im)
                            embed(doc, view, dpi, pdf)
                            rows.append({"scan":len(rows)+1,"source":str(path),"source_sha256":sha,
                                         "frame":j+1,"format":im.format,"orientation":orientation,
                                         "display_size":list(view.size),"dpi":list(dpi)})
            doc.save(stage / "bundle.pdf", deflate=True)
        with pdf.open(stage / "bundle.pdf") as check:
            if len(check) != len(rows):
                raise ValueError("Output page count mismatch")
            for pg, row in zip(check, rows):
                images = pg.get_images()
                if len(images) != 1 or list(images[0][2:4]) != row["display_size"]:
                    raise ValueError(f"Output page {row['scan']} did not preserve source pixel dimensions")
        with (stage / "bundle.pdf").open("rb") as fp:
            pdf_sha = digest(fp)
        (stage / "source-map.json").write_text(json.dumps({"schema":1,"pdf_sha256":pdf_sha,
            "pages": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        out.mkdir()  # refuse existing directories, also on racing runs
        for name in ("bundle.pdf", "source-map.json"):
            shutil.move(str(stage/name), out/name)
    return len(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path, help="new output directory")
    p.add_argument("images", nargs="*", type=Path, help="explicit page order")
    p.add_argument("--list", type=Path, help="UTF-8 paths, one per line, relative to list directory")
    a = p.parse_args()
    if bool(a.images) == bool(a.list):
        p.error("supply either image paths or --list")
    try:
        paths = a.images if a.images else [a.list.parent / line for line in
                    a.list.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        n = build(paths, a.out.resolve())
    except Exception as exc:
        p.exit(2, f"Bundle failed: {exc}\n")
    print(f"{n} page(s); run the page-order gate on {a.out.resolve() / 'bundle.pdf'}")


if __name__ == "__main__":
    main()
