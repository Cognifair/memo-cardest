#!/usr/bin/env python3
"""Preflight a custom API write script before running it.

Memo Studio only sees progress from UploadTask + change-journal. A script that
POSTs cards with urllib/requests directly is not a plugin bug; it is an
unregistered writer and must be rewritten before running.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

WRITE_PATTERNS = [
    r"Request\s*\([^)]*\bdata\s*=",
    r"method\s*=\s*['\"](?:POST|PUT|PATCH|DELETE)",
    r"\brequests\.(?:post|put|patch|delete)\b",
    r"\.request\s*\(\s*['\"](?:POST|PUT|PATCH|DELETE)",
    r"\burlopen\s*\([^)]*data\s*=",
]
REGISTRATION_PATTERNS = [
    r"\bUploadTask\b",
    r"\bchange_journal\b",
    r"\bWriteResult\b",
]


def inspect_source(text: str) -> list[str]:
    issues = []
    if re.search(r"(?:open\.maimemo\.com|/markji/)", text):
        writes = [pattern for pattern in WRITE_PATTERNS if re.search(pattern, text)]
        registered = [pattern for pattern in REGISTRATION_PATTERNS if re.search(pattern, text)]
        if writes and not registered:
            issues.append("raw API writer detected without UploadTask/change_journal")
        if writes and registered and not re.search(r"\b(?:begin|open)\s*\(", text):
            issues.append("UploadTask imported but no begin/open call detected")
        if re.search(r"\b(?:POST|PUT|PATCH)\b", text) and not registered:
            issues.append("HTTP write method present without progress registration")
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", help="custom Python upload script")
    args = parser.parse_args(argv)
    path = Path(args.script).resolve(strict=True)
    issues = inspect_source(path.read_text(encoding="utf-8", errors="replace"))
    if issues:
        print(f"BLOCKED: {path}")
        for issue in issues:
            print(f"- {issue}")
        print("Rewrite with UploadTask or change_journal.py; do not run this script.")
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
