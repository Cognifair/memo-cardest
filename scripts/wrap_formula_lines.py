#!/usr/bin/env python3
"""Wrap formula-heavy answer lines into a whole-line Markji formula.

The output shape is the one validated in the signal-and-systems card session:

    ① [E##[F#1#\\text{...} \\allowbreak ...]]

It keeps the circled marker outside, turns plain Markji text into ``\\text{}``,
splits Chinese at safe 8-character/punctuation boundaries, and splits formulas
at top-level commas. It does not rewrite the source file in place.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
PUNCT = "。；：，、！？"
DEFAULT_BOLD_COLOR = "#d16056"
TEXT_ESCAPE = {
    "\\": r"\textbackslash{}",
    "%": r"\%",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "$": r"\$",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_text(text: str) -> str:
    return "".join(TEXT_ESCAPE.get(char, char) for char in text)


def runs_of(line: str):
    """Split a line into text / bold / math / unsupported-tag runs."""
    runs = []
    i = 0
    while i < len(line):
        if line.startswith("[T#", i):
            end = line.find("]", i)
            if end < 0:
                raise ValueError("unclosed text tag")
            tag = line[i:end + 1]
            body = re.sub(r"^\[T#[^#]*#", "", tag)[:-1]
            bold = bool(re.match(r"^\[T#B(?:,|#)", tag))
            runs.append(("bold" if bold else "text", body))
            i = end + 1
        elif line.startswith("[E##", i):
            end = line.find("]", i)
            if end < 0:
                raise ValueError("unclosed formula tag")
            runs.append(("math", line[i + 4:end]))
            i = end + 1
        elif line[i] == "[":
            end = line.find("]", i)
            if end < 0:
                raise ValueError("unclosed Markji tag")
            tag = line[i:end + 1]
            if tag.startswith(("[Pic#", "[Choice#", "[Card#", "[F#")):
                raise ValueError(f"unsupported tag in whole-line wrapper: {tag[:40]}")
            runs.append(("text", tag))
            i = end + 1
        else:
            end = line.find("[", i)
            if end < 0:
                runs.append(("text", line[i:]))
                break
            runs.append(("text", line[i:end]))
            i = end
    return runs


def chunk_text(text: str, width: int) -> list[str]:
    """Split Chinese text at punctuation or width, never inside a formula."""
    chunks = []
    current = ""
    for char in text:
        current += char
        if char in PUNCT or len(current) >= width:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def split_brackets(text: str) -> list[tuple[str, str]]:
    """Keep literal [ ] out of a Markji formula tag."""
    out = []
    buffer = ""
    for char in text:
        if char in "[]":
            if buffer:
                out.append(("text", buffer))
                buffer = ""
            out.append(("bracket", char))
        else:
            buffer += char
    if buffer:
        out.append(("text", buffer))
    return out


def split_math(latex: str, maxlen: int = 12) -> list[str]:
    """Split a formula at top-level commas; long fragments stay intact."""
    text = latex.strip()
    depth = 0
    parts = []
    current = ""
    i = 0
    while i < len(text):
        if text.startswith(r"\{", i) or text.startswith(r"\}", i):
            current += text[i:i + 2]
            i += 2
            continue
        char = text[i]
        current += char
        i += 1
        if char in "{(":
            depth += 1
        elif char in ")}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
    if current.strip():
        parts.append(current.strip())
    if len(parts) <= 1:
        return [text]
    return parts


def text_latex(text: str, bold: bool, width: int, bold_color: str) -> list[str]:
    parts = []
    for kind, value in split_brackets(text):
        if kind == "bracket":
            parts.append(r"\lbrack " if value == "[" else r"\rbrack ")
            continue
        for chunk in chunk_text(value, width):
            escaped = escape_text(chunk)
            if bold:
                parts.append(
                    r"\text{\textcolor{" + bold_color + r"}{\textbf{" + escaped + r"}}}"
                )
            else:
                parts.append(r"\text{" + escaped + "}")
    return parts


def build_parts(line: str, width: int, bold_color: str) -> list[str]:
    parts = []
    for kind, value in runs_of(line):
        if kind == "math":
            parts.extend(split_math(value))
        else:
            parts.extend(text_latex(value, kind == "bold", width, bold_color))
    return [part for part in parts if part.strip()]


def build_latex(line: str, width: int, bold_color: str) -> str:
    return r" \allowbreak ".join(build_parts(line, width, bold_color))


def wrap_content(content: str, width: int = 8, bold_color: str = DEFAULT_BOLD_COLOR,
                 mode: str = "v13"):
    if mode not in {"v13", "formula"}:
        raise ValueError("mode must be v13 or formula")
    if content.startswith("---\n"):
        head, separator, body = "", "---\n", content[4:]
    else:
        head, separator, body = content.partition("\n---\n")
    if not separator:
        return content, 0
    output = []
    groups = 0
    for line in body.split("\n"):
        if line and line[0] in CIRCLED:
            groups += 1
            marker, rest = line[0], line[1:].lstrip()
            if rest.startswith("[E##[F#"):
                output.append(line)
                continue
            parts = build_parts(rest, width, bold_color)
            if mode == "formula":
                inner = r" \allowbreak ".join(parts)
                output.append(f"{marker} [E##{inner}]")
            else:
                # v1.3: every part is a same-group cloze; allowbreak stays at
                # the formula top level, between cloze tags.
                inner = r" \allowbreak ".join(f"[F#{groups}#{part}]" for part in parts)
                output.append(f"{marker} [E##{inner}]")
        else:
            output.append(line)
    return head + separator + "\n".join(output), groups


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="cards JSON: array or {cards:[...]}")
    parser.add_argument("--output", required=True)
    parser.add_argument("--field", default="content")
    parser.add_argument("--output-field", default="content_wrapped")
    parser.add_argument("--width", type=int, default=8)
    parser.add_argument("--mode", choices=["v13", "formula"], default="v13",
                        help="v13: same-group cloze tags with top-level allowbreak; formula: pure [E##...] with allowbreak")
    parser.add_argument("--bold-color", default=DEFAULT_BOLD_COLOR)
    args = parser.parse_args(argv)
    if not 4 <= args.width <= 40:
        raise ValueError("--width must be 4..40")

    source = Path(args.input).resolve(strict=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    cards = data if isinstance(data, list) else data.get("cards", [])
    if not isinstance(cards, list):
        raise ValueError("input must contain a cards array")

    total = 0
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get(args.field), str):
            continue
        wrapped, groups = wrap_content(card[args.field], args.width, args.bold_color, args.mode)
        card[args.output_field] = wrapped
        card["wrap_groups"] = groups
        total += groups

    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite: {output}")
    output.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"output": str(output), "cards": len(cards), "groups": total,
                      "field": args.output_field}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
