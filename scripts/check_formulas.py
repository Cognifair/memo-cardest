#!/usr/bin/env python3
"""Check Markji card formulas before delivery.

Formula cards are fragile: OCR can split a formula into several ``[E##...]``
fragments, leave a trailing operator, or leave a dollar delimiter behind. This
checker never rewrites a formula; it flags cards that need human review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FORMULA = re.compile(r"\[E##(.*?)\]", re.S)
UNCLOSED = re.compile(r"\[E##[^\]]*$", re.S)
TRAILING_OPERATOR = re.compile(r"[+\-*/=<>]\s*$")
SUSPICIOUS = {
    r"\\sqrt\s*\\lbrack": "malformed sqrt delimiter",
    r"\\{f\(y\)\\}": "suspicious f(y) in a discrete-signal formula",
    r"N\s*f": "possible OCR of -j (N f -> -j)",
}


def brace_balance(formula: str) -> bool:
    depth = 0
    escaped = False
    for char in formula:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def inspect_card(card: dict, index: int) -> list[dict]:
    key = card.get("key") or card.get("num") or f"#{index + 1}"
    issues = []

    for field in ("title", "content"):
        text = card.get(field)
        if not isinstance(text, str):
            continue
        if "$" in text:
            issues.append({"key": key, "field": field, "kind": "dollar_residue",
                           "snippet": text[:180]})
        for line in text.splitlines():
            if re.search(r"\[F#\d+#[^\]]*\\allowbreak", line):
                issues.append({"key": key, "field": field,
                               "kind": "nested_cloze_allowbreak",
                               "snippet": line[:180]})
        if UNCLOSED.search(text):
            issues.append({"key": key, "field": field, "kind": "unclosed_formula",
                           "snippet": text[:180]})
        formulas = FORMULA.findall(text)
        for formula in formulas:
            raw = formula.strip()
            if not raw:
                issues.append({"key": key, "field": field, "kind": "empty_formula"})
                continue
            if TRAILING_OPERATOR.search(raw) and not re.search(r"\^\s*\*\s*$", raw):
                issues.append({"key": key, "field": field, "kind": "trailing_operator",
                               "formula": raw[:180]})
            if not brace_balance(raw):
                issues.append({"key": key, "field": field, "kind": "brace_imbalance",
                               "formula": raw[:180]})
            for pattern, reason in SUSPICIOUS.items():
                if re.search(pattern, raw):
                    issues.append({"key": key, "field": field, "kind": "suspicious_formula",
                                   "reason": reason, "formula": raw[:180]})
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="cards JSON: array of cards or {cards:[...]}")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    path = Path(args.input).resolve(strict=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data if isinstance(data, list) else data.get("cards", [])
    if not isinstance(cards, list):
        raise ValueError("cards JSON must be an array or contain a cards array")

    issues = []
    for index, card in enumerate(cards):
        if isinstance(card, dict):
            issues.extend(inspect_card(card, index))

    result = {"input": str(path), "cards": len(cards), "issues": issues,
              "ok": not issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"cards: {len(cards)} · issues: {len(issues)}")
        for issue in issues:
            detail = issue.get("reason") or issue.get("formula") or issue.get("snippet") or ""
            print(f"- {issue['key']} [{issue['field']}] {issue['kind']}: {detail}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
