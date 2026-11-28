#!/usr/bin/env python3
"""Media-phase progress for Memo Studio.

This is deliberately separate from UploadTask/change_journal. Card progress
counts verified cards; media progress counts uploaded files. Mixing them would
make the island report fake cards.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from upload_task import registry_dir

MEDIA_DIR_NAME = "media"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _session_id() -> str:
    value = os.environ.get("DSH_SESSION_ID") or ""
    value = value.strip()
    if value and not value.startswith("session-"):
        value = "session-" + value
    return value


def media_dir() -> Path:
    tasks = registry_dir()
    target = tasks.parent / MEDIA_DIR_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def _atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Windows can transiently reject os.replace while the island is reading.
    last = None
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as error:
            last = error
            time.sleep(0.02 * (attempt + 1))
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    raise last


class MediaProgress:
    def __init__(self, task_id: str, total: int, current: str = ""):
        self.task_id = task_id
        self.total = max(0, int(total))
        self.done = 0
        self.current = current
        self.session_id = _session_id()
        digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()[:20]
        self.path = media_dir() / f"media-{digest}.json"
        self.started_at = _now()
        self._closed = False
        self.update(0, current)

    def update(self, done: int, current: str = "") -> None:
        if self._closed:
            return
        self.done = max(0, min(int(done), self.total))
        if current:
            self.current = current
        payload = {
            "protocol_version": 1,
            "kind": "media",
            "task_id": self.task_id,
            "session_id": self.session_id,
            "phase": "media",
            "total": self.total,
            "done": self.done,
            "current": self.current,
            "started_at": self.started_at,
            "updated_at": _now(),
            "pid": os.getpid(),
        }
        _atomic_write(self.path, payload)

    def close(self, done: int | None = None) -> None:
        if done is not None:
            self.update(done)
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                payload.update({"phase": "closed", "done": payload.get("done", self.done),
                                "updated_at": _now()})
                _atomic_write(self.path, payload)
            except Exception:
                pass
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
