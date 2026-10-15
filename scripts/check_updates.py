#!/usr/bin/env python3
"""Local satellite inventory, consent state and HTTPS version checks; never installs."""
import argparse
from contextlib import contextmanager
from functools import total_ordering
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
import urllib.parse
import urllib.request

ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SEMVER = re.compile(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
                    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z")
MAX_BYTES = 16384
DEFAULT_STATE = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "Codex/MemoFramework"


@total_ordering
class Version:
    def __init__(self, value):
        match = SEMVER.fullmatch(value)
        if not match:
            raise ValueError("Expected a semantic X.Y.Z version")
        self.core = tuple(int(n) for n in match.groups()[:3])
        self.pre = match.group(4)
        parts = self.pre.split(".") if self.pre else []
        if any(p.isdigit() and len(p) > 1 and p[0] == "0" for p in parts):
            raise ValueError("Invalid numeric prerelease identifier")
        self.key = (self.core, self.pre is None,
                    tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts))

    def __eq__(self, other):
        return self.key == other.key

    def __lt__(self, other):
        return self.key < other.key


def skill_metadata(path):
    """Read a supported plain YAML frontmatter subset, never the body."""
    if path.is_symlink() or path.stat().st_size > 262144:
        raise ValueError("Unsafe or oversized SKILL.md")
    text = path.read_text(encoding="utf-8-sig")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        raise ValueError("Missing closed frontmatter")
    header = match.group(1)
    name = re.search(r"(?m)^name:[ \t]*['\"]?([a-z0-9-]+)['\"]?[ \t]*\r?$", header)
    if not name or not ID.fullmatch(name.group(1)):
        raise ValueError("Missing plain skill name")
    block = re.search(r"(?m)^metadata:[ \t]*\r?\n((?:[ \t]+[^\n]*(?:\n|$))*)", header + "\n")
    version = re.search(r"(?m)^  version:[ \t]*['\"]?([^'\"\s]+)['\"]?[ \t]*\r?$",
                        block.group(1)) if block else None
    if version is None:
        version = re.search(r"(?m)^version:[ \t]*['\"]?([^'\"\s]+)['\"]?[ \t]*\r?$", header)
    value = version.group(1) if version else None
    if value:
        Version(value)
    return name.group(1), value


def config(root):
    text = (root / "references/satellites.md").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^" + "\x60" * 3 + r"json[ \t]*\n(.*?)\n" + "\x60" * 3 + r"[ \t]*$", text)
    if not match:
        raise ValueError("Missing JSON satellite configuration")
    cfg = json.loads(match.group(1))
    if cfg.get("schema") != 1 or cfg.get("skill_id") != skill_metadata(root / "SKILL.md")[0]:
        raise ValueError("Host identity or configuration schema mismatch")
    if cfg.get("auto_check") is not False:
        raise ValueError("Distributed configuration must default to auto_check=false")
    if type(cfg.get("throttle_hours")) not in (int, float) or not 1 <= cfg["throttle_hours"] <= 8760:
        raise ValueError("Invalid throttle interval")
    satellites = cfg.get("satellites")
    hosts = cfg.get("allowed_version_hosts")
    if not isinstance(satellites, list) or len(satellites) > 20 or not isinstance(hosts, list):
        raise ValueError("Invalid satellite or domain list")
    if any(not isinstance(host, str) or not re.fullmatch(r"[a-z0-9.-]+", host) for host in hosts):
        raise ValueError("Invalid version domain")
    seen = set()
    for item in satellites:
        sid = item.get("id", "")
        if not ID.fullmatch(sid) or sid in seen or sid == cfg["skill_id"]:
            raise ValueError("Unsafe, duplicate or self-referential satellite ID")
        seen.add(sid)
        if item.get("install_source") != "platform_marketplace":
            raise ValueError("Satellite installation must remain marketplace-only")
        if not isinstance(item.get("name"), str) or not isinstance(item.get("capability"), str):
            raise ValueError("Missing satellite description")
        if item.get("version_url") is not None:
            validate_url(item["version_url"], hosts)
    return cfg


def validate_url(url, allowed_hosts):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("Invalid version URL")
    value = urllib.parse.urlsplit(url)
    if (value.scheme != "https" or not value.hostname or value.username or value.password
            or value.query or value.fragment or value.port not in (None, 443)
            or not value.path.endswith("/version.json") or value.hostname not in allowed_hosts):
        raise ValueError("Only an explicitly allowlisted HTTPS version.json URL is supported")
    try:
        ipaddress.ip_address(value.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal endpoints are not supported")
    if "." not in value.hostname or value.hostname.endswith((".local", ".localhost")):
        raise ValueError("Local endpoints are not supported")
    return value.hostname


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirects are not allowed")


def fetch_manifest(item, allowed_hosts):
    host = validate_url(item["version_url"], allowed_hosts)
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Version domain did not resolve exclusively to public addresses")
    request = urllib.request.Request(item["version_url"],
                                     headers={"Accept": "application/json", "User-Agent": "memo-framework/1.0"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=6) as response:
        if response.status != 200 or "json" not in response.headers.get_content_type():
            raise ValueError("Expected a JSON response")
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Version response is too large")
    data = json.loads(content.decode("utf-8-sig"))
    if (not isinstance(data, dict) or set(data) - {"id", "version", "updated_at"}
            or data.get("id") != item["id"] or not isinstance(data.get("version"), str)):
        raise ValueError("Unexpected version manifest identity or fields")
    Version(data["version"])
    return data["version"]


def default_state():
    return {"schema": 1, "auto_check": False, "pitched": False, "asked_update": False,
            "declined": False, "first_task": None, "pitch_task": None,
            "last_checks": {}, "missing_notices": {}}


def read_state(path):
    if not path.exists():
        return default_state()
    if path.is_symlink():
        raise ValueError("State cannot be a symlink")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Invalid local state; no consent is inferred")
    result = default_state()
    result.update(data)
    if any(type(result[key]) is not bool for key in ("auto_check", "pitched", "asked_update", "declined")):
        raise ValueError("Invalid consent state")
    if not isinstance(result["last_checks"], dict) or not isinstance(result["missing_notices"], dict):
        raise ValueError("Invalid local state maps")
    return result


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("State cannot be a symlink")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(".lock")
    if lock.is_symlink():
        raise ValueError("Lock cannot be a symlink")
    with lock.open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def inventory(cfg, roots):
    result = []
    for sat in cfg["satellites"]:
        row = dict(sat, installed=False, local_version=None, path=None, shadowed=[])
        for root in roots:
            path = root / sat["id"]
            if path.is_symlink() or not (path / "SKILL.md").is_file():
                continue
            try:
                name, value = skill_metadata(path / "SKILL.md")
                if name != sat["id"]:
                    continue
            except (OSError, ValueError):
                continue
            if row["installed"]:
                row["shadowed"].append(str(path))
            else:
                row.update(installed=True, local_version=value, path=str(path))
        row["version_source_configured"] = bool(row["version_url"])
        result.append(row)
    return result


def complete_task(state, rows, task_id):
    if not state["first_task"]:
        state["first_task"] = task_id
    missing = [row for row in rows if not row["installed"]]
    installed = [row for row in rows if row["installed"]]
    if state["declined"]:
        return "none"
    if rows and not installed and missing and not state["pitched"]:
        return "pitch"
    prior_task = state["pitch_task"] or state["first_task"]
    if installed and not state["asked_update"] and task_id != prior_task:
        return "ask_update_consent"
    if state["auto_check"]:
        return "check_updates"
    return "none"


def check_versions(cfg, rows, state, manual=False, now=None, fetcher=None):
    now = time.time() if now is None else now
    fetcher = fetcher or fetch_manifest
    report = {"status": "disabled", "updates": [], "checked": [], "skipped": [], "failed": []}
    if not manual and not state["auto_check"]:
        return report
    for row in rows:
        sid = row["id"]
        reason = None
        if not row["installed"]:
            reason = "not_installed"
        elif not row["version_url"]:
            reason = "version_source_unconfigured"
        elif not row["local_version"]:
            reason = "local_version_unknown"
        key = sid + "|" + (row["version_url"] or "")
        last = state["last_checks"].get(key)
        if reason is None and last is not None and not manual and now - last < cfg["throttle_hours"] * 3600:
            reason = "throttled"
        if reason:
            report["skipped"].append({"id": sid, "reason": reason})
            continue
        state["last_checks"][key] = now  # Failed requests are throttled too.
        try:
            validate_url(row["version_url"], cfg["allowed_version_hosts"])
            remote = fetcher(row, cfg["allowed_version_hosts"])
            newer = Version(remote) > Version(row["local_version"])
        except Exception:
            report["failed"].append({"id": sid, "reason": "version_check_failed"})
            continue
        report["checked"].append(sid)
        if newer:
            report["updates"].append({"id": sid, "name": row["name"], "local": row["local_version"],
                                      "remote": remote, "install_source": row["install_source"],
                                      "marketplace_listing": row.get("marketplace_listing")})
    if report["failed"]:
        report["status"] = "partial" if report["checked"] else "failed"
    elif report["checked"]:
        report["status"] = "updates_available" if report["updates"] else "up_to_date"
    elif any(row["reason"] == "throttled" for row in report["skipped"]):
        report["status"] = "throttled"
    else:
        report["status"] = "not_configured"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--root", type=Path, action="append", help="Explicit installed-skill search root; repeatable")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("inventory")
    sub.add_parser("status")
    completion = sub.add_parser("complete")
    completion.add_argument("--task-id", required=True)
    record = sub.add_parser("record")
    record.add_argument("event", choices=["pitch", "declined", "update-asked"])
    record.add_argument("--task-id", required=True)
    consent = sub.add_parser("consent")
    consent.add_argument("choice", choices=["once", "auto", "off"])
    missing = sub.add_parser("missing")
    missing.add_argument("--id", required=True)
    missing.add_argument("--session-id", required=True)
    checking = sub.add_parser("check")
    checking.add_argument("--manual", action="store_true",
                          help="Only for an explicit one-time user request; bypasses auto-check and throttle")
    args = parser.parse_args()
    try:
        cfg = config(args.skill_root)
        roots = args.root or [Path.home() / ".codex/skills", Path.home() / ".agents/skills", args.skill_root.parent]
        roots = list(dict.fromkeys(root.resolve() for root in roots))
        rows = inventory(cfg, roots)
        state_path = args.state_dir / (cfg["skill_id"] + ".json")
        if args.action == "inventory":
            output = {"host": cfg["skill_id"], "satellites": rows}
        elif args.action == "status":
            output = {"host": cfg["skill_id"], "state": read_state(state_path), "satellites": rows}
        else:
            with locked(state_path):
                state = read_state(state_path)
                if args.action == "complete":
                    action = complete_task(state, rows, args.task_id)
                    output = {"next_action": action, "satellites": rows}
                elif args.action == "record":
                    if args.event == "pitch":
                        state.update(pitched=True, pitch_task=args.task_id)
                    elif args.event == "declined":
                        state.update(declined=True, pitched=True, auto_check=False, asked_update=True)
                    else:
                        state["asked_update"] = True
                    output = {"recorded": args.event}
                elif args.action == "consent":
                    state.update(asked_update=True, auto_check=args.choice == "auto", declined=False)
                    output = {"auto_check": state["auto_check"],
                              "check_once_next": args.choice in ("once", "auto")}
                elif args.action == "missing":
                    target = next((row for row in rows if row["id"] == args.id), None)
                    if target is None:
                        raise ValueError("Unknown satellite")
                    seen = state["missing_notices"].setdefault(args.session_id, [])
                    notify = not target["installed"] and args.id not in seen and not state["declined"]
                    if notify:
                        seen.append(args.id)
                    output = {"should_notify": notify, "satellite": target}
                else:
                    output = check_versions(cfg, rows, state, args.manual)
                save_state(state_path, state)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        print(json.dumps({"status": "error", "message": "Local configuration/state is invalid or busy; no installation performed."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

