#!/usr/bin/env python3
"""Read-only scan progress for Memo Studio.

Separate from media and card upload. It reports task-level units only, e.g.
chapters checked, not one progress tick per HTTP GET.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from upload_task import registry_dir

SCAN_DIR_NAME = "scan"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_id() -> str:
    value = (os.environ.get("DSH_SESSION_ID") or "").strip()
    if value and not value.startswith("session-"):
        value = "session-" + value
    return value


def scan_dir() -> Path:
    target = registry_dir().parent / SCAN_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def _atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class ScanProgress:
    def __init__(self, task_id: str, total: int, current: str = "", unit: str = "chapters"):
        self.task_id = task_id
        self.total = max(0, int(total))
        self.done = 0
        self.current = current
        self.unit = unit
        self.session_id = _session_id()
        digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:20]
        self.path = scan_dir() / f"scan-{digest}.json"
        self.started_at = _now()
        self._closed = False
        self.update(0, current)

    def update(self, done: int, current: str = "") -> None:
        if self._closed:
            return
        self.done = max(0, min(int(done), self.total))
        if current:
            self.current = current
        _atomic_write(self.path, {
            "protocol_version": 1,
            "kind": "scan",
            "task_id": self.task_id,
            "session_id": self.session_id,
            "phase": "scan",
            "unit": self.unit,
            "total": self.total,
            "done": self.done,
            "current": self.current,
            "started_at": self.started_at,
            "updated_at": _now(),
            "pid": os.getpid(),
        })

    def close(self, done: int | None = None) -> None:
        if done is not None:
            self.update(done)
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                payload.update({"phase": "closed", "updated_at": _now()})
                _atomic_write(self.path, payload)
            except Exception:
                pass
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
