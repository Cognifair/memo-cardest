"""Consume a checked PDF in Memo-Cardest: extract text, run local OCR, or prepare a cloud job."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from inspect_source import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("text", "local", "prepare"))
    parser.add_argument("pdf", type=Path, help="The actual original or reordered file approved at G1.3")
    parser.add_argument("output", type=Path, help="New text file or new job/output directory")
    parser.add_argument("--folio-receipt", type=Path)
    args = parser.parse_args()
    src, dest = args.pdf.resolve(), args.output.resolve()
    if src.suffix.lower() != ".pdf" or not src.is_file():
        parser.error("Expected a local PDF; normalize image sequences first")
    decision = inspect(src, 8, args.folio_receipt)
    if decision.get("status") == "blocked":
        print(json.dumps(decision, ensure_ascii=False))
        return 2
    if dest.exists():
        parser.error("Refusing to overwrite output")
    if args.action == "text":
        import pymupdf
        pages = []
        with pymupdf.open(src) as doc:
            for n, pg in enumerate(doc, 1):
                pages.append({"page": n, "text": pg.get_text(sort=True)})
        if not any(p["text"].strip() for p in pages):
            parser.error("No text layer to extract; use the formal OCR checkpoint")
        with dest.open("x", encoding="utf-8") as fp:
            json.dump({"source": str(src), "pages": pages}, fp, ensure_ascii=False)
        return 0
    if args.action == "prepare":
        workflow = Path(__file__).resolve().parents[2] / "memo-mineruocr" / "scripts" / "workflow.py"
        if not workflow.is_file():
            parser.error("Sibling memo-mineruocr workflow is unavailable")
        # Offline preparation only. Authorization and submit stay in Memo-MinerUOCR.
        return subprocess.run([sys.executable, "-B", str(workflow), "prepare", str(src), str(dest)]).returncode
    engine = shutil.which("mineru")
    if not engine:
        parser.error("Local mineru CLI not available; no engine installed or route changed")
    return subprocess.run([engine, "-p", str(src), "-o", str(dest)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
