#!/usr/bin/env python3
"""Read-only inventory and merge plan for Markji decks.

This command never creates, updates, moves, or deletes anything. It resolves the
source/target decks, reads chapters and cards, classifies links and media, and
writes a plan + preview for a later, separately authorized copy step.

Usage:
  python -B scripts/merge_plan.py --source <deck-id-or-name> --source <...> \
      --target <deck-id-or-name> --route api --output merge-plan.json \
      --preview merge-preview.md
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

try:
    from secret_resolver import SecretNotFound, get_secret
except ImportError:  # running from an unusual cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from secret_resolver import SecretNotFound, get_secret

BASE = "https://open.maimemo.com/open/api/v1/markji"
PAGE_LIMIT = 100
MAX_PAGES = 100
REF_RE = re.compile(r"\[Card#ID/([^#\]]+)#[^\]]*\]")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
AUDIO_RE = re.compile(r"(?:Audio#|\[Audio|\.mp3\b|\.wav\b|\.m4a\b|\.aac\b|\.ogg\b)", re.I)


class ApiError(RuntimeError):
    pass


_RATE_LOCK = None
_NEXT_REQUEST_AT = [0.0]


def _request_interval():
    try:
        return max(0.05, float(os.environ.get("MERGE_REQUEST_INTERVAL", "0.35")))
    except ValueError:
        return 0.35


def _throttle():
    global _RATE_LOCK
    import threading
    if _RATE_LOCK is None:
        _RATE_LOCK = threading.Lock()
    with _RATE_LOCK:
        now = time.monotonic()
        wait = max(0.0, _NEXT_REQUEST_AT[0] - now)
        _NEXT_REQUEST_AT[0] = max(now, _NEXT_REQUEST_AT[0]) + _request_interval()
    if wait:
        time.sleep(wait)


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(value):
    return str(value or "").strip()


def card_key(card):
    return stable_id(card.get("root_id")) or stable_id(card.get("id"))


def parse_references(content):
    return [m.group(1).strip() for m in REF_RE.finditer(content or "") if m.group(1).strip()]


def media_kind(content):
    text = content or ""
    kinds = []
    if IMAGE_RE.search(text):
        kinds.append("image")
    if AUDIO_RE.search(text):
        kinds.append("audio")
    return kinds


def _request_json(url, token, timeout=30, attempts=5, method="GET", body=None):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    payload = None
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(attempts):
        _throttle()
        req = urllib.request.Request(url, headers=headers, data=payload, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            body_text = ""
            try:
                body_text = error.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            last = ApiError(f"HTTP {error.code} from {url.split('?')[0]}: {body_text or error.reason}")
            if error.code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                time.sleep(4 * (attempt + 1))
                continue
            raise last from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last = ApiError(f"request failed: {error}")
            if attempt + 1 < attempts:
                time.sleep(2 * (attempt + 1))
                continue
            raise last from error
    raise last or ApiError("request failed")


def _get_page(token, path, key, page=1, limit=PAGE_LIMIT):
    query = urllib.parse.urlencode({"page": page, "limit": limit})
    payload = _request_json(f"{BASE}{path}?{query}", token)
    data = payload.get("data") or {}
    items = data.get(key)
    if items is None:
        # Be tolerant of a response that nests the collection one level deeper.
        for value in data.values():
            if isinstance(value, list):
                items = value
                break
    if not isinstance(items, list):
        raise ApiError(f"response for {path} has no {key} list")
    return items


def _paginate(token, path, key):
    items = []
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        chunk = _get_page(token, path, key, page=page)
        fresh = 0
        for item in chunk:
            marker = stable_id(item.get("id"))
            if marker and marker in seen:
                continue
            if marker:
                seen.add(marker)
            items.append(item)
            fresh += 1
        if len(chunk) < PAGE_LIMIT or fresh == 0:
            break
    return items


def list_decks(token):
    return _paginate(token, "/decks", "decks")


def resolve_deck(token, value):
    value = str(value or "").strip()
    if not value:
        raise ValueError("deck id/name cannot be empty")
    decks = list_decks(token)
    if value.startswith("mkjd_"):
        for deck in decks:
            if stable_id(deck.get("id")) == value:
                return deck
        raise ValueError(f"deck id not found: {value}")
    matches = [deck for deck in decks if str(deck.get("name") or "").strip() == value]
    if not matches:
        raise ValueError(f"deck name not found: {value}; create it in the client first")
    if len(matches) > 1:
        ids = ", ".join(stable_id(deck.get("id")) for deck in matches)
        raise ValueError(f"multiple decks named {value!r}: {ids}; use a deck id")
    return matches[0]


def _fetch_card(token, deck_id, card_id):
    payload = _request_json(f"{BASE}/decks/{deck_id}/cards/{card_id}", token)
    card = (payload.get("data") or {}).get("card")
    if not isinstance(card, dict):
        raise ApiError(f"card {card_id} response has no data.card")
    return {
        "id": stable_id(card.get("id")) or card_id,
        "root_id": stable_id(card.get("root_id")),
        "content": str(card.get("content") or ""),
        "grammar_version": card.get("grammar_version"),
    }


def _fetch_cards(token, deck_id, card_ids, workers=2):
    card_ids = [stable_id(card_id) for card_id in card_ids if stable_id(card_id)]
    if not card_ids:
        return []
    # The official list-card endpoint is not available; cards are addressed by
    # the ids carried on each chapter. Keep a small bounded read-only pool.
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(card_ids)))) as pool:
        return list(pool.map(lambda card_id: _fetch_card(token, deck_id, card_id), card_ids))


def _normalise_card(card):
    return {
        "id": stable_id(card.get("id")),
        "root_id": stable_id(card.get("root_id")),
        "content": str(card.get("content") or ""),
        "grammar_version": card.get("grammar_version"),
    }


def _chapter_cards(token, deck_id, chapter):
    chapter_id = stable_id(chapter.get("id"))
    # Official GET /chapters/{chapter} returns the chapter, its chapterset and
    # its cards in one read. This avoids one rate-limited request per card.
    payload = _request_json(f"{BASE}/decks/{deck_id}/chapters/{chapter_id}?with_cards=true", token)
    data = payload.get("data") or {}
    cards = data.get("cards")
    if isinstance(cards, list):
        return [_normalise_card(card) for card in cards if isinstance(card, dict)]
    embedded = chapter.get("cards")
    if isinstance(embedded, list) and embedded:
        return [_normalise_card(card) for card in embedded if isinstance(card, dict)]
    card_ids = chapter.get("card_ids")
    if isinstance(card_ids, list):
        return _fetch_cards(token, deck_id, card_ids)
    return []


def fetch_deck_tree(token, deck, include_cards=True):
    deck_id = stable_id(deck.get("id"))
    if not deck_id:
        raise ValueError("deck has no id")
    chapters = _paginate(token, f"/decks/{deck_id}/chapters", "chapters")
    result = []
    for chapter in chapters:
        chapter_id = stable_id(chapter.get("id"))
        if not chapter_id:
            raise ValueError(f"chapter in {deck_id} has no id")
        cards = _chapter_cards(token, deck_id, chapter) if include_cards else []
        result.append({
            "id": chapter_id,
            "name": str(chapter.get("name") or "").strip(),
            "order": chapter.get("order"),
            "cards": cards,
        })
    return {"id": deck_id, "name": str(deck.get("name") or "").strip(), "chapters": result}


def _chapter_names(deck):
    return [chapter["name"] for chapter in deck["chapters"] if chapter["name"]]


def _collect_cards(source_decks):
    cards = []
    for deck in source_decks:
        for chapter in deck["chapters"]:
            for card in chapter["cards"]:
                content = card["content"]
                cards.append({
                    "source_deck_id": deck["id"],
                    "source_deck_name": deck["name"],
                    "source_chapter_id": chapter["id"],
                    "source_chapter_name": chapter["name"],
                    "source_card_id": card["id"],
                    "source_root_id": card["root_id"],
                    "content": content,
                    "grammar_version": card["grammar_version"],
                    "content_sha256": sha256_text(content),
                    "references": parse_references(content),
                    "media": media_kind(content),
                })
    return cards


def _group_duplicates(cards):
    groups = {}
    for card in cards:
        groups.setdefault(card["content_sha256"], []).append(card)
    duplicates = []
    for digest, group in groups.items():
        if len(group) < 2:
            continue
        duplicates.append({
            "content_sha256": digest,
            "count": len(group),
            "cards": [{
                "source_deck_id": c["source_deck_id"],
                "source_chapter_id": c["source_chapter_id"],
                "source_card_id": c["source_card_id"],
                "source_root_id": c["source_root_id"],
            } for c in group],
        })
    return sorted(duplicates, key=lambda item: (-item["count"], item["content_sha256"]))


def _chapter_conflicts(source_decks, target_deck):
    names = {}
    for deck in source_decks:
        for chapter in deck["chapters"]:
            name = chapter["name"]
            if name:
                names.setdefault(name.casefold(), []).append({
                    "deck_id": deck["id"], "chapter_id": chapter["id"], "name": name,
                })
    duplicate_names = [items for items in names.values() if len(items) > 1]
    target_names = {str(chapter.get("name") or "").strip().casefold()
                    for chapter in target_deck.get("chapters", []) if chapter.get("name")}
    overlaps = [items for items in names.values()
                if items and items[0]["name"].casefold() in target_names]
    return duplicate_names, overlaps


def _link_report(cards, source_roots, inbound_cards=None):
    internal = []
    outbound = []
    unresolved = []
    for card in cards:
        for ref in card["references"]:
            entry = {
                "source_deck_id": card["source_deck_id"],
                "source_chapter_id": card["source_chapter_id"],
                "source_card_id": card["source_card_id"],
                "source_root_id": card["source_root_id"],
                "target_root_id": ref,
            }
            if ref in source_roots:
                internal.append(entry)
            elif ref:
                outbound.append(entry)
            else:
                unresolved.append(entry)
    inbound = []
    for item in inbound_cards or []:
        for ref in item.get("references", []):
            if ref in source_roots:
                inbound.append({
                    "deck_id": item.get("deck_id"),
                    "chapter_id": item.get("chapter_id"),
                    "card_id": item.get("card_id"),
                    "root_id": item.get("root_id"),
                    "target_source_root_id": ref,
                })
    return {
        "internal": internal,
        "outbound_external": outbound,
        "inbound_external": inbound,
        "unresolved": unresolved,
        "inbound_scanned": inbound_cards is not None,
    }


def _media_report(cards):
    images = [c for c in cards if "image" in c["media"]]
    audio = [c for c in cards if "audio" in c["media"]]
    return {
        "image_ref_cards": len(images),
        "audio_ref_cards": len(audio),
        "sample_cards": [{
            "source_deck_id": c["source_deck_id"],
            "source_chapter_id": c["source_chapter_id"],
            "source_card_id": c["source_card_id"],
            "kinds": c["media"],
        } for c in (images + audio)[:5]],
    }


def analyze(source_decks, target_deck, route="api", inbound_cards=None):
    cards = _collect_cards(source_decks)
    source_roots = {card["source_root_id"] for card in cards if card["source_root_id"]}
    duplicates = _group_duplicates(cards)
    duplicate_chapters, chapter_overlaps = _chapter_conflicts(source_decks, target_deck)
    empty_chapters = [{
        "source_deck_id": deck["id"],
        "source_deck_name": deck["name"],
        "chapter_id": chapter["id"],
        "chapter_name": chapter["name"],
    } for deck in source_decks for chapter in deck["chapters"] if not chapter["cards"]]
    links = _link_report(cards, source_roots, inbound_cards)
    media = _media_report(cards)
    warnings = []
    if not links["inbound_scanned"]:
        warnings.append("外部入链未扫描；删除源牌组前仍可能断链。需要完整检查时加 --scan-inbound。")
    if links["inbound_external"]:
        warnings.append(f"发现 {len(links['inbound_external'])} 条外部卡指向源卡；删除源牌组前需要处理或明确接受断链。")
    if links["unresolved"]:
        warnings.append(f"发现 {len(links['unresolved'])} 条无法解析的 Card 引用。")
    if media["image_ref_cards"] or media["audio_ref_cards"]:
        warnings.append("源卡含图片/音频；批量复制前必须先复制 1 张样本并在客户端验收。")
    if duplicates:
        warnings.append(f"发现 {len(duplicates)} 组重复内容；需要用户决定跳过还是保留。")
    if duplicate_chapters:
        warnings.append(f"发现 {len(duplicate_chapters)} 组同名源章节；需要用户决定合并或保留。")
    if chapter_overlaps:
        warnings.append("源章节名与目标牌组现有章节重叠；需要用户决定合并或重命名。")
    decisions = []
    if duplicates:
        decisions.append("duplicate_cards")
    if duplicate_chapters or chapter_overlaps:
        decisions.append("chapter_conflict")
    plan = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "route": route,
        "target": {"id": target_deck["id"], "name": target_deck["name"], "existing": True},
        "sources": [{"id": deck["id"], "name": deck["name"], "chapter_count": len(deck["chapters"])}
                    for deck in source_decks],
        "counts": {
            "source_decks": len(source_decks),
            "chapters": sum(len(deck["chapters"]) for deck in source_decks),
            "cards": len(cards),
        },
        "chapters": [{
            "source_deck_id": deck["id"],
            "source_deck_name": deck["name"],
            "chapter_id": chapter["id"],
            "chapter_name": chapter["name"],
            "card_count": len(chapter["cards"]),
        } for deck in source_decks for chapter in deck["chapters"]],
        "cards": cards,
        "conflicts": {
            "duplicate_cards": duplicates,
            "duplicate_chapters": duplicate_chapters,
            "target_chapter_overlap": chapter_overlaps,
            "empty_chapters": empty_chapters,
        },
        "links": links,
        "media": media,
        "warnings": warnings,
        "requires_decision": decisions,
        "notices": [
            "源牌组未修改；本流程不删除任何内容。",
            "学习进度不会迁移。",
            "请先验收目标牌组，再由用户手动删除源牌组。",
        ],
    }
    return plan


def _preview_markdown(plan):
    lines = [
        "# 牌组合并预览", "",
        f"- 目标牌组：**{plan['target']['name']}** (`{plan['target']['id']}`)",
        f"- 路线：`{plan['route']}`",
        f"- 源牌组：{plan['counts']['source_decks']} 个",
        f"- 章节：{plan['counts']['chapters']}",
        f"- 卡片：{plan['counts']['cards']}",
        "",
        "## 链接",
        f"- 内部引用：{len(plan['links']['internal'])}",
        f"- 源卡 → 外部：{len(plan['links']['outbound_external'])}",
        f"- 外部 → 源卡：{len(plan['links']['inbound_external'])}"
        + ("" if plan['links']['inbound_scanned'] else "（未扫描）"),
        f"- 未解析：{len(plan['links']['unresolved'])}",
        "",
        "## 风险",
    ]
    if plan["warnings"]:
        lines.extend("- " + warning for warning in plan["warnings"])
    else:
        lines.append("- 未发现需要额外处理的风险。")
    lines.extend(["", "## 源章节"])
    for chapter in plan["chapters"]:
        lines.append(f"- {chapter['source_deck_name']} / {chapter['chapter_name']}：{chapter['card_count']} 张")
    if plan["requires_decision"]:
        lines.extend(["", "## 需要用户决定"])
        lines.extend("- " + item for item in plan["requires_decision"])
    lines.extend([
        "", "## 安全边界",
        "- 本文件只读生成，没有写卡、移卡或删除。",
        "- 目标牌组由用户创建；官方 API 不能新建牌组。",
        "- 复制完成后请在客户端验收；确认后再手动删除源牌组。",
        "- 学习进度不会迁移。",
        "",
    ])
    return "\n".join(lines)


def _inbound_cards(token, all_decks, source_ids):
    source_ids = set(source_ids)
    result = []
    for deck in all_decks:
        deck_id = stable_id(deck.get("id"))
        if not deck_id or deck_id in source_ids:
            continue
        tree = fetch_deck_tree(token, deck)
        for chapter in tree["chapters"]:
            for card in chapter["cards"]:
                refs = parse_references(card["content"])
                if refs:
                    result.append({
                        "deck_id": deck_id,
                        "chapter_id": chapter["id"],
                        "card_id": card["id"],
                        "root_id": card["root_id"],
                        "references": refs,
                    })
    return result


def build_plan(token, source_values, target_value, route="api", scan_inbound=False):
    target = resolve_deck(token, target_value)
    source_decks = []
    seen = set()
    for value in source_values:
        deck = resolve_deck(token, value)
        deck_id = stable_id(deck.get("id"))
        if deck_id in seen:
            continue
        if deck_id == stable_id(target.get("id")):
            raise ValueError("target deck cannot also be a source deck")
        seen.add(deck_id)
        source_decks.append(fetch_deck_tree(token, deck))
    if not source_decks:
        raise ValueError("at least one source deck is required")
    target_tree = fetch_deck_tree(token, target, include_cards=False)
    inbound = _inbound_cards(token, list_decks(token), seen) if scan_inbound else None
    return analyze(source_decks, target_tree, route=route, inbound_cards=inbound)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Markji deck merge inventory")
    parser.add_argument("--source", action="append", required=True,
                        help="source deck id or exact name; repeat for each source")
    parser.add_argument("--target", required=True, help="existing target deck id or exact name")
    parser.add_argument("--route", choices=["api", "c"], default="api",
                        help="api = direct copy; c = TXT import then API repair")
    parser.add_argument("--scan-inbound", action="store_true",
                        help="also scan other decks for links into the source cards")
    parser.add_argument("--output", default="merge-plan.json")
    parser.add_argument("--preview", default="merge-preview.md")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    output = Path(args.output)
    preview = Path(args.preview)
    for path in (output, preview):
        if path.exists() and not args.overwrite:
            parser.error(f"refusing to overwrite {path}; pass --overwrite")

    try:
        token, _source = get_secret("MAIMEMO_TOKEN")
    except (SecretNotFound, OSError) as error:
        print(f"Cannot read MAIMEMO_TOKEN: {error}", file=sys.stderr)
        return 2
    if not token:
        print("Cannot read MAIMEMO_TOKEN", file=sys.stderr)
        return 2

    try:
        plan = build_plan(token, args.source, args.target,
                          route=args.route, scan_inbound=args.scan_inbound)
    except (ApiError, ValueError) as error:
        print(f"Cannot build merge plan: {error}", file=sys.stderr)
        return 1

    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    preview.write_text(_preview_markdown(plan), encoding="utf-8")
    summary = {
        "plan": str(output),
        "preview": str(preview),
        "target": plan["target"],
        "counts": plan["counts"],
        "warnings": plan["warnings"],
        "requires_decision": plan["requires_decision"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"plan: {output}")
        print(f"preview: {preview}")
        print(f"target: {plan['target']['name']} ({plan['target']['id']})")
        print(f"cards: {plan['counts']['cards']}")
        for warning in plan["warnings"]:
            print(f"warning: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
