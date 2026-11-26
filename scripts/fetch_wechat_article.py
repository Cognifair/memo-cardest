#!/usr/bin/env python3
"""Fetch and normalize a WeChat public-account article as card material.

This is an ingest step, not a crawler: it handles one article (or a saved HTML
file), preserves the source, extracts text/images/sub-article links, and never
auto-inserts [Pic#] into cards. Lazy-loaded images are read from data-src.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BLOCK_TAGS = {"p", "br", "section", "div", "h1", "h2", "h3", "h4", "li", "tr", "blockquote"}


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", value).strip()


def safe_name(value: str, limit: int = 80) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "_", value).strip(" .")
    return (value[:limit] or "article")


class WeChatParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.account = ""
        self.in_title = False
        self.in_body = False
        self.div_depth = 0
        self.text_parts = []
        self.images = []
        self.links = []
        self._href = ""
        self._anchor_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1" and not self.title:
            self.in_title = True
        if tag == "div" and attrs.get("id") == "js_content":
            self.in_body = True
            self.div_depth = 1
        elif self.in_body and tag == "div":
            self.div_depth += 1

        if self.in_body:
            if tag in BLOCK_TAGS:
                self.text_parts.append("\n")
            if tag == "img":
                src = attrs.get("data-src") or attrs.get("src") or ""
                if src:
                    self.images.append({
                        "url": src.replace("&amp;", "&"),
                        "data_w": attrs.get("data-w") or "",
                        "data_ratio": attrs.get("data-ratio") or "",
                        "anchor_text": clean_text("".join(self.text_parts[-40:]))[-300:],
                    })
            if tag == "a":
                self._href = attrs.get("href") or ""
                self._anchor_text = []

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_title = False
        if tag == "a" and self._href:
            self.links.append({"url": self._href.replace("&amp;", "&"),
                               "text": clean_text("".join(self._anchor_text))})
            self._href = ""
        if self.in_body and tag == "div":
            self.div_depth -= 1
            if self.div_depth <= 0:
                self.in_body = False
        if self.in_body and tag in BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_body:
            self.text_parts.append(data)
            if self._href:
                self._anchor_text.append(data)


def fetch(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, "replace"), charset
    except LookupError:
        return raw.decode("utf-8", "replace"), "utf-8"


def parse_html(html: str) -> WeChatParser:
    parser = WeChatParser()
    parser.feed(html)
    if not parser.title:
        match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        if match:
            parser.title = match.group(1)
    if not parser.account:
        match = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)', html)
        if match:
            parser.account = match.group(1)
    return parser


def normalize_markdown(parts: list[str]) -> str:
    text = "".join(parts)
    lines = [clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines) + ("\n" if lines else "")


def download_image(url: str, out_dir: Path) -> dict:
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
        "Referer": "https://mp.weixin.qq.com/",
    })
    with urllib.request.urlopen(request, timeout=40) as response:
        data = response.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError("image too large")
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        suffix = ".jpg"
    path = out_dir / f"{digest[:16]}{suffix}"
    path.write_bytes(data)
    width = height = None
    try:
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.width, image.height
    except Exception:
        pass
    return {"sha256": digest, "file": str(path), "width": width, "height": height,
            "bytes": len(data)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--html-file")
    parser.add_argument("--out", required=True)
    parser.add_argument("--download-images", action="store_true")
    args = parser.parse_args(argv)
    if not args.url and not args.html_file:
        parser.error("provide --url or --html-file")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.html_file:
        html = Path(args.html_file).resolve(strict=True).read_text(encoding="utf-8")
        source_url = ""
    else:
        html, source_url = fetch(args.url)
    (out / "source.html").write_text(html, encoding="utf-8")
    parsed = parse_html(html)
    title = clean_text(parsed.title) or "微信公众号文章"

    images = []
    for index, item in enumerate(parsed.images, 1):
        entry = {"index": index, "url": item["url"],
                 "data_w": item["data_w"], "data_ratio": item["data_ratio"],
                 "anchor_text": item["anchor_text"], "decision": "needs_review"}
        if args.download_images:
            try:
                entry.update(download_image(item["url"], out / "images"))
                if entry.get("width") and entry.get("height"):
                    ratio = entry["width"] / entry["height"]
                    if entry["width"] < 200 or entry["height"] < 200 or ratio > 6 or ratio < 0.15:
                        entry["review_reason"] = "size_outlier"
            except Exception as error:
                entry["review_reason"] = f"download_failed: {error}"
        images.append(entry)

    sub_links = []
    seen = set()
    for link in parsed.links:
        url = urllib.parse.urljoin(args.url or "https://mp.weixin.qq.com", link["url"])
        if "mp.weixin.qq.com/s" not in url or url in seen:
            continue
        seen.add(url)
        sub_links.append({"url": url, "text": link["text"]})

    markdown = normalize_markdown(parsed.text_parts)
    (out / "article.md").write_text(f"# {title}\n\n{markdown}", encoding="utf-8")
    manifest = {
        "source_url": args.url or "",
        "title": title,
        "account": clean_text(parsed.account),
        "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "text_chars": len(markdown),
        "images": images,
        "sub_links": sub_links,
        "note": "images are review candidates; this script never creates [Pic#].",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps({"out": str(out), "title": title, "text_chars": len(markdown),
                      "images": len(images), "sub_links": len(sub_links)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
