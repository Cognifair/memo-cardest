#!/usr/bin/env python3
"""Check that every card [Pic#ID/...] traces to an accepted media record.

This validates references, not counts: one accepted image may be reused by
several cards, but every reference must resolve to the same accepted source
and converted-file hashes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PIC = re.compile(r"\[Pic#ID/([^,#\]\s]+)")


def load_cards(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data if isinstance(data, list) else data.get("cards", [])
    if not isinstance(cards, list):
        raise ValueError("cards must be an array or contain a cards array")
    return [card for card in cards if isinstance(card, dict)]


def load_map(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files", data) if isinstance(data, dict) else {}
    if not isinstance(files, dict):
        raise ValueError("media map must be an object")
    return files


def inspect(cards: list[dict], files: dict) -> list[dict]:
    issues = []
    seen = set()
    for card in cards:
        key = card.get("key") or card.get("num") or "?"
        for field in ("content", "content_wrapped", "title"):
            text = card.get(field)
            if not isinstance(text, str):
                continue
            for media_id in PIC.findall(text):
                seen.add(media_id)
                record = files.get(media_id)
                if not isinstance(record, dict):
                    issues.append({"key": key, "field": field, "media_id": media_id,
                                   "kind": "missing_media_record"})
                    continue
                if record.get("decision") != "accepted":
                    issues.append({"key": key, "field": field, "media_id": media_id,
                                   "kind": "media_not_accepted",
                                   "decision": record.get("decision")})
                source = str(record.get("source_file") or "").lower()
                if source.endswith((".wmf", ".emf")):
                    issues.append({"key": key, "field": field, "media_id": media_id,
                                   "kind": "vector_source_not_traceable"})
                for hash_field in ("source_sha256", "converted_sha256"):
                    value = record.get(hash_field)
                    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                        issues.append({"key": key, "field": field, "media_id": media_id,
                                       "kind": f"missing_{hash_field}"})
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", help="cards JSON")
    parser.add_argument("--media-map", required=True, help="media id → accepted record JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cards = load_cards(Path(args.cards).resolve(strict=True))
    files = load_map(Path(args.media_map).resolve(strict=True))
    issues = inspect(cards, files)
    result = {"cards": len(cards), "media_records": len(files),
              "issues": issues, "ok": not issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"cards: {len(cards)} · media records: {len(files)} · issues: {len(issues)}")
        for issue in issues:
            print(f"- {issue['key']} {issue['media_id']} {issue['kind']}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
