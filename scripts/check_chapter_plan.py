#!/usr/bin/env python3
"""Validate a chapter-split confirmation before card generation/writes.

The checker cannot know whether a split is semantically correct. It only
enforces that an ambiguous split was actually confirmed by the user, and that
the plan has a traceable source and concrete chapters.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(plan: dict) -> list[str]:
    issues = []
    if not isinstance(plan, dict):
        return ["plan is not an object"]
    if not plan.get("task_id"):
        issues.append("missing task_id")
    if not plan.get("source_material"):
        issues.append("missing source_material")

    mode = plan.get("split_mode")
    if mode not in {"explicit", "asked", "default", "unresolved"}:
        issues.append("split_mode must be explicit|asked|default|unresolved")
    if mode == "unresolved":
        issues.append("chapter split is unresolved; ask the user and stop")
    if mode == "asked":
        if plan.get("confirmed_by") != "user":
            issues.append("asked split requires confirmed_by=user")
        if not plan.get("confirmation_id"):
            issues.append("asked split requires confirmation_id")
    if mode == "explicit":
        if not plan.get("evidence"):
            issues.append("explicit split requires the user's exact evidence")
    if mode == "default":
        issues.append("default split is not allowed for multi-chapter material")

    chapters = plan.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        issues.append("chapters must be a non-empty array")
    else:
        names = []
        for index, chapter in enumerate(chapters):
            if isinstance(chapter, str):
                name = chapter.strip()
            elif isinstance(chapter, dict):
                name = str(chapter.get("name") or "").strip()
                if not chapter.get("source_heading"):
                    issues.append(f"chapter[{index}] missing source_heading")
            else:
                issues.append(f"chapter[{index}] has unsupported shape")
                continue
            if not name:
                issues.append(f"chapter[{index}] has empty name")
            names.append(name)
        if len(names) != len(set(names)):
            issues.append("duplicate chapter names")
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", help="chapter_plan.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).resolve(strict=True).read_text(encoding="utf-8"))
    issues = validate(plan)
    result = {"plan": args.plan, "issues": issues, "ok": not issues}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"issues: {len(issues)}")
        for issue in issues:
            print(f"- {issue}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
