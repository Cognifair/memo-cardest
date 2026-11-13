#!/usr/bin/env python3
"""Copy a merge plan into an existing Markji deck through the official API.

Read-only by default. A real write requires both --apply and --allow-upload.
This command never deletes, moves, or renames cards, chapters, or decks.
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from merge_plan import (  # noqa: E402
    BASE,
    ApiError,
    _request_json,
    fetch_deck_tree,
    list_decks,
    parse_references,
    sha256_text,
    stable_id,
)
from secret_resolver import SecretNotFound, get_secret  # noqa: E402


def _find_deck(token, deck_id):
    for deck in list_decks(token):
        if stable_id(deck.get("id")) == deck_id:
            return deck
    raise ValueError(f"target deck not found: {deck_id}")


def _chapter_map(target_tree):
    return {chapter["name"]: chapter for chapter in target_tree["chapters"] if chapter["name"]}


def _create_chapter(token, target_id, name):
    payload = _request_json(
        f"{BASE}/decks/{target_id}/chapters",
        token,
        method="POST",
        body={"deck": target_id, "name": name},
    )
    chapter = (payload.get("data") or {}).get("chapter") or {}
    chapter_id = stable_id(chapter.get("id"))
    if not chapter_id:
        raise ApiError(f"chapter creation returned no id for {name!r}")
    return {"id": chapter_id, "name": name, "cards": []}


def _create_card(token, target_id, chapter_id, card):
    payload = _request_json(
        f"{BASE}/decks/{target_id}/chapters/{chapter_id}/cards",
        token,
        method="POST",
        body={"card": {"content": card["content"], "grammar_version": card["grammar_version"]}},
    )
    created = (payload.get("data") or {}).get("card") or {}
    card_id = stable_id(created.get("id"))
    root_id = stable_id(created.get("root_id"))
    if not card_id:
        raise ApiError("card creation returned no card id")
    if not root_id:
        readback = _request_json(f"{BASE}/decks/{target_id}/cards/{card_id}", token)
        read = (readback.get("data") or {}).get("card") or {}
        root_id = stable_id(read.get("root_id"))
    return {
        "source_chapter_id": card["source_chapter_id"],
        "source_chapter_name": card["source_chapter_name"],
        "source_card_id": card["source_card_id"],
        "source_root_id": card["source_root_id"],
        "target_card_id": card_id,
        "target_root_id": root_id,
    }


def _need_decision(plan, args):
    duplicates = plan["conflicts"]["duplicate_cards"]
    if duplicates and not args.skip_duplicates:
        raise ValueError(f"plan has {len(duplicates)} duplicate groups; pass --skip-duplicates")
    links = plan["links"]["internal"]
    if links and not args.sample:
        raise ValueError("plan contains internal links; this first apply script does not rewrite links")


def _choose_cards(plan, args):
    cards = plan["cards"]
    if args.sample:
        if not cards:
            raise ValueError("plan has no cards")
        return cards[:1]
    if not args.skip_duplicates:
        return cards
    seen = set()
    chosen = []
    for card in cards:
        digest = card["content_sha256"]
        if digest in seen:
            continue
        seen.add(digest)
        chosen.append(card)
    return chosen


def apply_plan(plan, args, token):
    target_id = stable_id(plan["target"]["id"])
    _find_deck(token, target_id)
    _need_decision(plan, args)
    target_tree = fetch_deck_tree(token, {"id": target_id, "name": plan["target"]["name"]}, include_cards=False)
    chapters = _chapter_map(target_tree)
    cards = _choose_cards(plan, args)
    created = []
    dry_run = not (args.apply and args.allow_upload)

    current_chapter_id = None
    current_chapter_name = None
    for card in cards:
        source_chapter = card["source_chapter_name"]
        if source_chapter != current_chapter_name:
            current_chapter_name = source_chapter
            if dry_run:
                current_chapter_id = "DRY-RUN"
            elif source_chapter in chapters:
                current_chapter_id = chapters[source_chapter]["id"]
            else:
                chapter = _create_chapter(token, target_id, source_chapter)
                chapters[source_chapter] = chapter
                current_chapter_id = chapter["id"]
        if dry_run:
            created.append({
                "source_card_id": card["source_card_id"],
                "source_chapter_name": source_chapter,
                "action": "would-create",
            })
            continue
        created.append(_create_card(token, target_id, current_chapter_id, card))
        if args.sample:
            break

    if args.sample and not dry_run:
        target_tree = fetch_deck_tree(token, {"id": target_id, "name": plan["target"]["name"]}, include_cards=True)
        target_card = next((c for ch in target_tree["chapters"] for c in ch["cards"]
                            if c["id"] == created[0]["target_card_id"]), None)
        if not target_card:
            raise ApiError("sample card was created but cannot be read back")
        created[0]["content_sha256"] = sha256_text(target_card["content"])
        created[0]["source_content_sha256"] = cards[0]["content_sha256"]
        created[0]["content_matches"] = created[0]["content_sha256"] == cards[0]["content_sha256"]

    return {"dry_run": dry_run, "target": plan["target"], "created": created,
            "skipped_duplicates": len(plan["cards"]) - len(cards) if args.skip_duplicates and not args.sample else 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Copy a Markji merge plan; never deletes")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--apply", action="store_true", help="write cards; without it, dry-run")
    parser.add_argument("--allow-upload", action="store_true", help="explicit write authorization")
    parser.add_argument("--sample", action="store_true", help="copy exactly one card")
    parser.add_argument("--skip-duplicates", action="store_true", help="keep only the first card of each content hash")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if args.sample and not args.apply:
        print("sample requires --apply --allow-upload", file=sys.stderr)
        return 2
    try:
        token, _source = get_secret("MAIMEMO_TOKEN")
    except (SecretNotFound, OSError) as error:
        print(f"Cannot read MAIMEMO_TOKEN: {error}", file=sys.stderr)
        return 2
    if not token:
        print("Cannot read MAIMEMO_TOKEN", file=sys.stderr)
        return 2
    try:
        result = apply_plan(plan, args, token)
    except (ApiError, ValueError) as error:
        print(f"Cannot apply merge plan: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(("dry-run" if result["dry_run"] else "applied") + ": " + str(len(result["created"])) + " card(s)")
        for item in result["created"]:
            print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
