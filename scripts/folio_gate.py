"""Mandatory page-order evidence for a local, multipage PDF (no upload).

    folio_gate.py finalize ORIGINAL EVIDENCE.json NEW_DIR [--review REVIEW.json]
    folio_gate.py verify DOWNSTREAM_PDF RECEIPT.json

Machine reads are observations, never a declaration of a passing result.
Review JSON is bound to the original SHA-256. Use either readings (scan,
number, reason) or a complete reviewed order (scan, section, label, reason)
with a top-level reason for the special pagination.
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from itertools import groupby
from pathlib import Path


FORMAT = "memo-cardest.page-order.v1"


def _load(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def _dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _sha_chunks(stream)


def _sha_chunks(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def _require(ok, why):
    if not ok:
        raise ValueError(why)


def _int(n):
    return type(n) is int and n >= 1


def _note(s):
    return isinstance(s, str) and bool(s.strip())


def _machine_reading(row):
    from folio_read import number
    how, n = row.get("method"), row.get("printed")
    if how not in ("text", "ocr") or not _int(n):
        return None
    hits = row.get(how + "_candidates")
    if not isinstance(hits, list) or not hits:
        return None
    # The reader owns crop selection and OCR thresholds. Do not accept a
    # bare printed column, conflicting candidates, or raw text that says
    # something different from the candidate's numeric value.
    if how == "ocr" and row.get("text_candidates"):
        return None
    for hit in hits:
        if not isinstance(hit, dict) or not _int(hit.get("printed")) or hit["printed"] != n:
            return None
        if not isinstance(hit.get("text"), str) or number(hit["text"]) != n:
            return None
    return n


def _assess(ev, review, source_hash, count):
    """Return rows in scan order, final order (scan numbers), outstanding issues."""
    _require(isinstance(ev, dict) and ev.get("schema") == 1 and ev.get("source_sha256") == source_hash,
             "Evidence does not belong to this PDF")
    pages = ev.get("pages")
    _require(isinstance(pages, list) and len(pages) == count == ev.get("page_count") and count >= 1,
             "Evidence must cover every PDF page")
    scans = list(range(1, count + 1))
    _require(all(isinstance(row, dict) and type(row.get("scan")) is int and row["scan"] == i
                 for i, row in zip(scans, pages)), "Missing, duplicate or displaced scan record")
    rows = []
    for row in pages:
        rows.append(dict(scan=row["scan"], printed=_machine_reading(row),
                         method=row.get("method"), section="", reason=""))
    observed = set()
    if review is not None:
        _require(isinstance(review, dict) and review.get("source_sha256") == source_hash,
                 "Review does not belong to this PDF")
        _require(("order" in review) != ("readings" in review), "Review needs exactly one of readings and order")
        if "order" in review:
            supplied = review["order"]
            _require(_note(review.get("reason")) and isinstance(supplied, list) and len(supplied) == count,
                     "Special pagination needs a reason and a complete reviewed order")
            order, last, seen_sections, active = [], {}, set(), None
            for item in supplied:
                _require(isinstance(item, dict), "Invalid reviewed page")
                i, sec, label, why = (item.get(k) for k in ("scan", "section", "label", "reason"))
                _require(_int(i) and i <= count and i not in observed and _note(sec) and _note(why)
                         and (_note(label) or _int(label)), "Incomplete/duplicate reviewed page")
                sec, label = sec.strip(), str(label).strip()
                if sec != active:
                    _require(sec not in seen_sections, "A reviewed section cannot recur out of order")
                    seen_sections.add(sec)
                    active = sec
                if label.isascii() and label.isdigit():
                    n = int(label)
                    _require(n > last.get(sec, -1), "Printed numbers must increase within each reviewed section")
                    last[sec] = n
                rows[i-1].update(printed=label, method="reviewed_order", section=sec, reason=why)
                observed.add(i)
                order.append(i)
            return rows, order, []
        _require(isinstance(review["readings"], list), "readings must be a list")
        for item in review["readings"]:
            _require(isinstance(item, dict), "Invalid reading")
            i, n, why = (item.get(k) for k in ("scan", "number", "reason"))
            _require(_int(i) and i <= count and i not in observed and _int(n) and _note(why),
                     "Invalid/duplicate observation: supply scan, number and reason")
            rows[i-1].update(printed=n, method="reviewed_reading", reason=why)
            observed.add(i)
    nums = [row["printed"] for row in rows]
    value_counts = Counter(nums)
    values = sorted(v for v in value_counts if v is not None)
    issues = []

    def flag(kind, bad):
        if bad:
            issues.append({"issue": kind, "scans": bad})

    flag("unreadable", [i for i,n in zip(scans,nums) if n is None])
    flag("duplicate_folio", [i for i,n in zip(scans,nums) if n is not None and value_counts[n]>1])
    gaps = [[a,b] for a,b in zip(values,values[1:]) if b>a+1]
    if gaps:
        issues.append({"issue": "gap_or_outlier", "gap_between_printed_values": gaps})
    # Flag isolated readings even if another issue (e.g. a missing index) already blocks sorting.
    flag("isolated_reading", [i for i,n in zip(scans,nums) if i not in observed and n is not None and count > 1 and
         not any(0<=j<count and nums[j] is not None and abs(n-nums[j])==1 for j in (i-2,i))])
    if issues:
        return rows, [], issues
    order = sorted(scans, key=lambda i: nums[i-1])
    # For an automatic move require a monotone run of at least three consecutive
    # numbers; short/isolated swaps require actual reviewed readings.
    moved = {scan for pos,scan in zip(scans,order) if pos != scan}
    if moved:
        supported = set(observed)
        for delta, indices in groupby(range(count-1), key=lambda j: nums[j+1]-nums[j]):
            run = list(indices)
            if abs(delta) == 1 and len(run)>=2:
                supported.update(range(run[0]+1, run[-1]+3))
        flag("short_move_requires_review", sorted(moved - supported))
    return rows, [] if issues else order, issues


def _content(pg, fitz):
    # Test visible appearance, extracted text (including invisible OCR), dimensions and rotation.
    pix = pg.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csRGB, alpha=False)
    h = hashlib.sha256(pix.samples_mv)
    h.update(repr((tuple(pg.rect), tuple(pg.cropbox), tuple(pg.mediabox), pg.rotation,
                   pix.width, pix.height)).encode("ascii"))
    h.update(pg.get_text().encode("utf-8", "surrogatepass"))
    return h.digest()


def _prove_order(src, candidate, order, fitz):
    # Reopen both files: verify what the downstream tool will actually read.
    with fitz.open(src) as original, fitz.open(candidate) as final:
        _require(original.page_count == final.page_count == len(order), "Output page count changed")
        for position, scan in enumerate(order):
            _require(_content(original[scan-1], fitz) == _content(final[position], fitz),
                     f"Output page {position+1} differs from source scan {scan}")


def _write_map(path, rows, order):
    positions = {scan: i for i, scan in enumerate(order, 1)}
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["scan", "printed", "final_position", "method", "section", "reason"])
        for r in rows:
            fields = [r["scan"],r["printed"],positions.get(r["scan"]),r["method"],r["section"],r["reason"]]
            w.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for v in fields])


def finalize(source, evidence, directory, review=None):
    import pymupdf as fitz
    src, out = Path(source).resolve(), Path(directory).resolve()
    ev = _load(evidence)
    observations = _load(review) if review is not None else None
    source_hash = _sha(src)
    with fitz.open(src) as doc:
        _require(doc.is_pdf and not doc.needs_pass, "Source must be a readable PDF")
        count = doc.page_count
    rows, order, issues = _assess(ev, observations, source_hash, count)
    out.mkdir(parents=True, exist_ok=False)
    _write_map(out/"page-map.csv", rows, order)
    if issues:
        _dump(out/"needs-review.json", {"source_sha256": source_hash, "issues": issues})
        return {"ok":False, "status":"needs_review", "issues":issues, "report":str(out/"needs-review.json")}
    actual = src
    if order != list(range(1,count+1)):
        actual = out/"ordered.pdf"
        tmp = out/"pending.pdf"
        try:
            with fitz.open(src) as doc:
                doc.select([i-1 for i in order])
                doc.save(tmp)
            _prove_order(src,tmp,order,fitz)
            tmp.rename(actual)
        finally:
            if tmp.exists():
                tmp.unlink()
    _require(_sha(src) == source_hash, "Source changed while processing")
    receipt = {"format":FORMAT, "source":str(src), "source_sha256":source_hash,
               "input":str(actual), "input_sha256":_sha(actual), "page_count":count,
               "order":order, "evidence":ev, "review":observations}
    _dump(out/"receipt.json",receipt)
    return {"ok":True, "status":"original" if actual == src else "reordered",
            "input":str(actual), "receipt":str(out/"receipt.json"), "pages":count}


def verify_gate(input_pdf, receipt_path):
    """A missing, stale, inconsistent or wrong-input receipt blocks downstream."""
    try:
        import pymupdf as fitz
        _require(receipt_path is not None, "Page-order receipt required")
        gate = _load(receipt_path)
        _require(isinstance(gate, dict) and gate.get("format")==FORMAT, "Missing page-order evidence")
        src, actual = Path(gate["source"]), Path(input_pdf).resolve()
        _require(src.is_absolute() and actual.is_file(), "Missing source or input PDF")
        source_hash = _sha(src)
        actual_hash = source_hash if src==actual else _sha(actual)
        _require(source_hash==gate.get("source_sha256"), "Receipt source no longer matches original PDF")
        _require(actual_hash==gate.get("input_sha256"), "Use the checked downstream PDF, or rerun preflight")
        with fitz.open(src) as doc:
            _require(doc.is_pdf and not doc.needs_pass and doc.page_count==gate["page_count"], "Invalid PDF/page count")
        _, order, issues = _assess(gate["evidence"], gate.get("review"), source_hash, gate["page_count"])
        _require(not issues and order==gate["order"], "Receipt has unresolved or inconsistent page order")
        if order == list(range(1,len(order)+1)):
            _require(actual_hash==source_hash, "Expected byte-identical original PDF")
        else:
            _require(actual_hash!=source_hash, "Original PDF may not be used in place of reordered PDF")
            _prove_order(src,actual,order,fitz)
        return {"ok":True, "status":"original" if actual_hash==source_hash else "reordered",
                "input":str(actual), "pages":len(order)}
    except Exception as e:
        return {"ok":False, "status":"blocked", "reason":str(e)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="cmd", required=True)
    f = subs.add_parser("finalize")
    for name in ("source","evidence","directory"):
        f.add_argument(name)
    f.add_argument("--review")
    v = subs.add_parser("verify")
    v.add_argument("input_pdf")
    v.add_argument("receipt")
    a = ap.parse_args()
    try:
        result = (finalize(a.source,a.evidence,a.directory,a.review) if a.cmd=="finalize" else verify_gate(a.input_pdf,a.receipt))
        print(json.dumps(result,ensure_ascii=False))
        return 0 if result["ok"] else 2
    except Exception as e:
        print(json.dumps({"ok":False,"status":"error","reason":str(e)},ensure_ascii=False),file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
