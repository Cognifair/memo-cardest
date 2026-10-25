#!/usr/bin/env python3
"""Inventory, consented fast-forward updates and public Memo discovery; never installs new skills."""
import argparse
from contextlib import contextmanager
from functools import total_ordering
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
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
LOCK_WAIT_SECONDS = 2.0


class LockBusy(RuntimeError):
    """Another process is already syncing and holds the state lock."""


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
    return skill_metadata_text(path.read_text(encoding="utf-8-sig"))


def skill_metadata_text(text):
    if len(text.encode("utf-8")) > 262144:
        raise ValueError("Oversized SKILL.md")
    text = text.lstrip("\ufeff")
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
        source = item.get("install_source")
        if source not in ("platform_marketplace", "github_public_repository"):
            raise ValueError("Unsupported satellite installation source")
        if not isinstance(item.get("name"), str) or not isinstance(item.get("capability"), str):
            raise ValueError("Missing satellite description")
        if source == "github_public_repository":
            validate_repository_url(item.get("repository_url"))
            validate_branch(item.get("repository_branch", "main"))
            if item.get("marketplace_listing") is not None:
                raise ValueError("Public GitHub satellites are not marketplace listings")
        if item.get("version_url") is not None:
            validate_url(item["version_url"], hosts)
    discovery = cfg.get("new_skill_discovery")
    if discovery is not None:
        validate_discovery(discovery)
    return cfg


def validate_discovery(source):
    if (not isinstance(source, dict) or source.get("provider") != "github_public"
            or not isinstance(source.get("owner"), str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", source["owner"])
            or source.get("repo_prefix") != "memo-" or source.get("auto_check") is not False
            or type(source.get("max_pages")) is not int or not 1 <= source["max_pages"] <= 5
            or type(source.get("max_candidates")) is not int or not 1 <= source["max_candidates"] <= 20):
        raise ValueError("Invalid public Memo discovery source or request budget")


REPOSITORY = re.compile(r"/[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}\Z")


def validate_branch(branch):
    if (not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch)
            or ".." in branch or "//" in branch
            or any(part.startswith(".") or part.endswith((".", ".lock")) for part in branch.split("/"))
            or branch.endswith("/")):
        raise ValueError("Invalid repository branch")
    return branch


def validate_repository_url(url):
    """Accept only a plain public GitHub repository URL as an install source."""
    if not isinstance(url, str) or len(url) > 300:
        raise ValueError("Invalid satellite repository URL")
    value = urllib.parse.urlsplit(url)
    if (value.scheme != "https" or value.hostname != "github.com" or value.username or value.password
            or value.query or value.fragment or value.port not in (None, 443)
            or not REPOSITORY.fullmatch(value.path)):
        raise ValueError("Only https://github.com/<owner>/<repo> is supported")
    return url


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
        if response.status != 200 or response.headers.get_content_type() not in ("application/json", "text/plain"):
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
            "last_checks": {}, "missing_notices": {}, "auto_discover": False,
            "asked_discovery": False, "discovery_candidates": {}, "discovery_notices": [],
            "discovery_dismissed": [], "pending_once": False, "pending_discovery_once": False,
            "sync_mode": "unset", "sync_pending_once": False, "last_sync": None}


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
    if any(type(result[key]) is not bool for key in ("auto_check", "pitched", "asked_update", "declined",
                                                   "auto_discover", "asked_discovery",
                                                   "pending_once", "pending_discovery_once",
                                                   "sync_pending_once")):
        raise ValueError("Invalid consent state")
    if result["sync_mode"] not in ("unset", "once", "auto", "off"):
        raise ValueError("Invalid sync mode")
    if result["last_sync"] is not None and type(result["last_sync"]) not in (int, float):
        raise ValueError("Invalid sync timestamp")
    if not isinstance(result["last_checks"], dict) or not isinstance(result["missing_notices"], dict):
        raise ValueError("Invalid local state maps")
    if (not isinstance(result["discovery_candidates"], dict)
            or any(not isinstance(result[key], list) or any(not isinstance(item, str) for item in result[key])
                   for key in ("discovery_notices", "discovery_dismissed"))):
        raise ValueError("Invalid discovery state")
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
        if os.name == "nt":
            import msvcrt
            # Do not read the byte before locking: Windows byte locks are mandatory
            # and a read of the locked byte fails with PermissionError.
            if os.fstat(stream.fileno()).st_size < 1:
                stream.seek(0)
                stream.write(b"0")
                stream.flush()
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        delay = 0.1
        while True:
            try:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockBusy("Another sync is running; lock held: " + str(lock)) from None
                time.sleep(delay)
                delay = min(delay * 2, 0.4)
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
        row = dict(sat, installed=False, local_version=None, path=None, shadowed=[], copies=[],
                   git_checkout=False)
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
            row["copies"].append({"path": str(path), "version": value,
                                  "git_checkout": (path / ".git").exists()})
            if row["installed"]:
                row["shadowed"].append(str(path))
            else:
                row.update(installed=True, local_version=value, path=str(path),
                           git_checkout=(path / ".git").exists())
        row["version_source_configured"] = bool(row["version_url"])
        result.append(row)
    return result


def same_remote(actual, expected):
    def norm(value):
        return (value or "").strip().rstrip("/").removesuffix(".git").lower()
    return norm(actual) == norm(expected)


def run_git(path, *arguments):
    result = subprocess.run(
        ["git", "-c", "http.sslBackend=openssl", "-c", "credential.helper=", *arguments],
        cwd=str(path), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def apply_update(row, target_version):
    try:
        return _apply_update(row, target_version)
    except subprocess.TimeoutExpired:
        return {"id": row["id"], "result": "failed", "reason": "git_timeout", "needs_verification": True}
    except OSError:
        return {"id": row["id"], "result": "failed", "reason": "git_or_file_unavailable", "needs_verification": True}


def _apply_update(row, target_version):
    """Fast-forward one installed satellite from its verified public repository."""
    path = Path(row["path"]) if row.get("path") else None
    if path is None or not path.is_dir() or not (path / ".git").exists():
        return {"id": row["id"], "result": "skipped", "reason": "not_a_git_checkout"}
    expected = row.get("repository_url")
    if not expected:
        return {"id": row["id"], "result": "skipped", "reason": "no_repository_url"}
    validate_repository_url(expected)
    branch = validate_branch(row.get("repository_branch", "main"))
    code, actual, _ = run_git(path, "remote", "get-url", "--all", "origin")
    if code != 0 or not same_remote(actual, expected):
        return {"id": row["id"], "result": "skipped", "reason": "remote_mismatch"}
    code, status, _ = run_git(path, "status", "--porcelain")
    if code != 0:
        return {"id": row["id"], "result": "failed", "reason": "git_status_failed"}
    if status:
        return {"id": row["id"], "result": "skipped", "reason": "dirty_worktree"}
    code, current, _ = run_git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    if code != 0 or current != branch:
        return {"id": row["id"], "result": "skipped", "reason": "branch_mismatch"}
    # Select the verified remote and branch explicitly; never use branch.*.remote/merge.
    code, _, _ = run_git(path, "fetch", "--no-tags", "origin", "refs/heads/" + branch)
    if code != 0:
        return {"id": row["id"], "result": "failed", "reason": "fetch_failed"}
    code, commit, _ = run_git(path, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
    if code != 0:
        return {"id": row["id"], "result": "failed", "reason": "fetch_head_invalid"}
    code, document, _ = run_git(path, "show", commit + ":SKILL.md")
    try:
        identity, version = skill_metadata_text(document)
    except ValueError:
        identity, version = None, None
    if code != 0 or identity != row["id"] or version != target_version:
        return {"id": row["id"], "result": "failed", "reason": "target_metadata_mismatch"}
    code, _, _ = run_git(path, "merge-base", "--is-ancestor", "HEAD", commit)
    if code != 0:
        return {"id": row["id"], "result": "skipped", "reason": "not_fast_forward"}
    code, _, _ = run_git(path, "merge", "--ff-only", commit)
    if code != 0:
        return {"id": row["id"], "result": "failed", "reason": "merge_failed", "needs_verification": True}
    try:
        identity, version = skill_metadata(path / "SKILL.md")
    except (OSError, ValueError):
        identity, version = None, None
    code, head, _ = run_git(path, "rev-parse", "HEAD")
    if code != 0 or head != commit or identity != row["id"] or version != target_version:
        return {"id": row["id"], "result": "failed", "reason": "update_verification_failed", "needs_verification": True}
    return {"id": row["id"], "result": "updated", "version": version, "commit": commit}


def run_sync(cfg, rows, state, now=None, fetcher=None):
    """Startup sync: authorized by the one-time prompt, never by silence."""
    mode = state.get("sync_mode", "unset")
    report = {"status": "off", "mode": mode, "checked": [], "updates": [],
              "updated": [], "skipped": [], "failed": []}
    if mode == "unset":
        report["status"] = "needs_consent"
        return report
    authorized_once = mode == "once" and bool(state.get("sync_pending_once"))
    if mode == "off" or (mode == "once" and not authorized_once):
        return report
    versions = check_versions(cfg, rows, state, manual=True, now=now, fetcher=fetcher)
    report["checked"] = versions["checked"]
    report["updates"] = versions["updates"]
    report["skipped"] = [dict(item, stage="version_check") for item in versions["skipped"]]
    report["failed"] = [dict(item, stage="version_check") for item in versions["failed"]]
    for item in versions["updates"]:
        row = next((candidate for candidate in rows if candidate["id"] == item["id"]), None)
        if row is None:
            continue
        outcome = apply_update(row, item["remote"])
        if outcome["result"] == "updated":
            report["updated"].append(outcome)
        elif outcome["result"] == "failed":
            report["failed"].append(dict(outcome, stage="update"))
        else:
            report["skipped"].append(outcome)
    if authorized_once:
        state["sync_pending_once"] = False
    state["last_sync"] = time.time() if now is None else now
    not_git = [item["id"] for item in report["skipped"] if item.get("reason") == "not_a_git_checkout"]
    if not_git:
        report["hint"] = ("这些支链不是 git 工作副本，自动同步无法更新：" + ", ".join(not_git)
                          + "。请用 git clone 重新安装（见 README「安装方式」）。")
    if report["failed"]:
        report["status"] = "partial"
    else:
        report["status"] = "done"
    return report


def complete_task(state, rows, task_id):
    if not state["first_task"]:
        state["first_task"] = task_id
    missing = [row for row in rows if not row["installed"]]
    if state["declined"]:
        return "none"
    if rows and missing and len(missing) == len(rows) and not state["pitched"]:
        return "pitch"
    return "none"


def check_versions(cfg, rows, state, manual=False, now=None, fetcher=None):
    now = time.time() if now is None else now
    fetcher = fetcher or fetch_manifest
    report = {"status": "disabled", "updates": [], "checked": [], "skipped": [], "failed": []}
    authorized_once = bool(state.get("pending_once")) and not manual
    if not manual and not state["auto_check"] and not authorized_once:
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
        if reason is None and last is not None and not manual and not authorized_once and now - last < cfg["throttle_hours"] * 3600:
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


def fetch_public(url, max_bytes, content_type):
    """Read only fixed GitHub public endpoints, without tokens, cookies or redirects."""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"api.github.com", "raw.githubusercontent.com"}
            or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("Unverified discovery endpoint")
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Discovery endpoint must resolve to public addresses")
    req = urllib.request.Request(url, headers={"Accept": content_type, "User-Agent": "memo-cardest-discovery/1.0"})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=6) as response:
        if response.status != 200:
            raise ValueError("Discovery endpoint unavailable")
        content = response.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError("Discovery response is too large")
    return content.decode("utf-8-sig")


def github_page(owner, page):
    url = f"https://api.github.com/users/{owner}/repos?per_page=100&page={page}"
    data = json.loads(fetch_public(url, 2_000_000, "application/json"))
    if not isinstance(data, list) or len(data) > 100 or any(not isinstance(row, dict) for row in data):
        raise ValueError("Invalid public repository listing")
    return data


def github_skill(owner, name, branch):
    url = f"https://raw.githubusercontent.com/{owner}/{name}/{urllib.parse.quote(branch, safe='')}/SKILL.md"
    return fetch_public(url, 262144, "text/plain")


def public_skill_metadata(text, expected_id):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        raise ValueError("Missing public skill frontmatter")
    header = match[1]
    name = re.search(r"(?m)^name:[ \t]*['\"]?([a-z0-9-]+)['\"]?[ \t]*\r?$", header)
    description = re.search(r"(?m)^description:[ \t]*(\S[^\r\n]*)", header)
    version = re.search(r"(?m)^  version:[ \t]*['\"]?([^'\"\s]+)['\"]?[ \t]*\r?$", header)
    if not name or name[1] != expected_id or not description or description[1] in {"|", ">"}:
        raise ValueError("Repository is not a verified skill with an inline description")
    if version:
        Version(version[1])
    # Content is untrusted metadata, never instructions. Bound and normalize display text.
    summary = " ".join(description[1].strip("'\"").split())[:800]
    return summary, version[1] if version else None


def check_new_skills(cfg, roots, state, manual=False, now=None, lister=None, reader=None):
    report = {"status": "disabled", "new_skills": [], "unannounced": [], "checked": [], "failed": [],
              "coverage": "public_github_only", "marketplace_checked": False, "truncated": False,
              "catalog_pages_checked": 0, "repositories_seen": 0}
    authorized_once = bool(state.get("pending_discovery_once")) and not manual
    if not manual and not state["auto_discover"] and not authorized_once:
        return report
    source = cfg.get("new_skill_discovery")
    if source is None:
        report["status"] = "not_configured"
        return report
    validate_discovery(source)
    owner = source["owner"]
    report["source"] = f"https://github.com/{owner}"
    now = time.time() if now is None else now
    key = f"discovery|github_public|{owner.lower()}"
    last = state["last_checks"].get(key)
    if last is not None and not manual and not authorized_once and now - last < cfg["throttle_hours"] * 3600:
        report["status"] = "throttled"
        return report
    state["last_checks"][key] = now
    known = {cfg["skill_id"], *(row["id"] for row in cfg["satellites"])}
    # Exclude all actually installed Memo skills, not just the static satellite list.
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.name.startswith("memo-") and not path.is_symlink() and (path / "SKILL.md").is_file():
                try:
                    sid, _ = skill_metadata(path / "SKILL.md")
                    if sid == path.name:
                        known.add(sid)
                except (OSError, ValueError):
                    continue
    lister, reader = lister or github_page, reader or github_skill
    attempts, seen = 0, set()
    for page in range(1, source["max_pages"] + 1):
        try:
            repos = lister(owner, page)
            if not isinstance(repos, list) or len(repos) > 100 or any(not isinstance(repo, dict) for repo in repos):
                raise ValueError("Invalid public listing")
        except Exception:
            report["failed"].append({"stage": "public_catalog", "reason": "listing_failed"})
            break
        report["catalog_pages_checked"] += 1
        report["repositories_seen"] += len(repos)
        for repo in repos:
            sid = repo.get("name", "")
            if (not isinstance(sid, str) or not ID.fullmatch(sid) or not sid.startswith(source["repo_prefix"])
                    or sid in known or sid in seen or repo.get("private") is not False
                    or repo.get("fork") or repo.get("archived") or repo.get("disabled")
                    or str(repo.get("full_name", "")).lower() != (owner + "/" + sid).lower()):
                continue
            seen.add(sid)
            if attempts >= source["max_candidates"]:
                report["truncated"] = True
                break
            attempts += 1
            branch = repo.get("default_branch")
            try:
                if not isinstance(branch, str) or not branch or len(branch) > 255:
                    raise ValueError("Missing default branch")
                summary, version = public_skill_metadata(reader(owner, sid, branch), sid)
            except Exception:
                report["failed"].append({"id": sid, "stage": "skill_verification", "reason": "skill_unverified"})
                continue
            url = f"https://github.com/{owner}/{sid}"
            candidate = {"id": sid, "name": sid, "capability": summary, "version": version,
                         "source": url, "publication": "public_github_repository",
                         "marketplace_status": "unverified", "compatibility": "candidate_unreviewed"}
            report["checked"].append(sid)
            report["new_skills"].append(candidate)
            state["discovery_candidates"][sid] = {"source": url, "version": version}
            if url not in state["discovery_notices"] and url not in state["discovery_dismissed"]:
                report["unannounced"].append(candidate)
        if report["truncated"] or len(repos) < 100:
            break
        if page == source["max_pages"]:
            report["truncated"] = True
    if report["failed"] or report["truncated"]:
        report["status"] = "partial" if report["checked"] or report["truncated"] else "failed"
    else:
        report["status"] = "new_skills_available" if report["new_skills"] else "no_new_skills"
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
    record.add_argument("event", choices=["pitch", "declined", "update-asked", "discovery-asked",
                                          "discovery-notified", "discovery-dismissed"])
    record.add_argument("--task-id", required=True)
    record.add_argument("--id")
    consent = sub.add_parser("consent")
    consent.add_argument("choice", choices=["once", "auto", "off"])
    consent.add_argument("--scope", choices=["updates", "discovery", "both"], default="updates")
    sync_consent = sub.add_parser("sync-consent")
    sync_consent.add_argument("choice", choices=["once", "auto", "off"])
    sub.add_parser("sync")
    missing = sub.add_parser("missing")
    missing.add_argument("--id", required=True)
    missing.add_argument("--session-id", required=True)
    checking = sub.add_parser("check")
    checking.add_argument("--manual", action="store_true",
                          help="Only for an explicit one-time user request; bypasses auto-check and throttle")
    checking.add_argument("--include-new", action="store_true", help="Explicitly include discovery of new public Memo skills")
    discovering = sub.add_parser("discover")
    discovering.add_argument("--manual", action="store_true")
    args = parser.parse_args()
    stage = "configuration"
    output = None
    try:
        cfg = config(args.skill_root)
        roots = args.root or [args.skill_root.parent, Path.home() / ".agents/skills", Path.home() / ".codex/skills"]
        roots = list(dict.fromkeys(root.resolve() for root in roots))
        rows = inventory(cfg, roots)
        state_path = args.state_dir / (cfg["skill_id"] + ".json")
        if args.action == "inventory":
            output = {"host": cfg["skill_id"], "satellites": rows}
        elif args.action == "status":
            stage = "state_read"
            output = {"host": cfg["skill_id"], "state": read_state(state_path), "satellites": rows}
        else:
            stage = "state_lock"
            with locked(state_path):
                stage = "state_read"
                state = read_state(state_path)
                stage = "operation"
                if args.action == "complete":
                    action = complete_task(state, rows, args.task_id)
                    output = {"next_action": action, "satellites": rows}
                elif args.action == "record":
                    if args.event == "pitch":
                        state.update(pitched=True, pitch_task=args.task_id)
                    elif args.event == "declined":
                        state.update(declined=True, pitched=True, auto_check=False, auto_discover=False,
                                     asked_update=True, asked_discovery=True)
                    elif args.event == "update-asked":
                        state["asked_update"] = True
                    elif args.event == "discovery-asked":
                        state["asked_discovery"] = True
                    else:
                        candidate = state["discovery_candidates"].get(args.id)
                        if candidate is None:
                            raise ValueError("Only a verified discovery candidate can be recorded")
                        key = "discovery_notices" if args.event == "discovery-notified" else "discovery_dismissed"
                        if candidate["source"] not in state[key]:
                            state[key].append(candidate["source"])
                    output = {"recorded": args.event}
                elif args.action == "consent":
                    if args.scope in ("updates", "both"):
                        state.update(asked_update=True, auto_check=args.choice == "auto", declined=False,
                                     pending_once=args.choice == "once")
                    if args.scope in ("discovery", "both"):
                        state.update(asked_discovery=True, auto_discover=args.choice == "auto",
                                     pending_discovery_once=args.choice == "once")
                    output = {"auto_check": state["auto_check"],
                              "auto_discover": state["auto_discover"], "scope": args.scope,
                              "pending_once": state["pending_once"],
                              "pending_discovery_once": state["pending_discovery_once"],
                              "check_once_next": args.choice in ("once", "auto")}
                elif args.action == "sync-consent":
                    state["sync_mode"] = args.choice
                    state["sync_pending_once"] = args.choice == "once"
                    state["auto_check"] = args.choice == "auto"
                    output = {"sync_mode": state["sync_mode"], "pending": state["sync_pending_once"]}
                elif args.action == "sync":
                    # Verify writable state before network/mutations. Consume once durably
                    # before updating so a crash cannot replay one-time authorization.
                    stage = "state_preflight"
                    reserved = dict(state)
                    reserved["sync_pending_once"] = False
                    save_state(state_path, reserved)
                    stage = "sync"
                    output = run_sync(cfg, rows, state)
                elif args.action == "missing":
                    target = next((row for row in rows if row["id"] == args.id), None)
                    if target is None:
                        raise ValueError("Unknown satellite")
                    seen = state["missing_notices"].setdefault(args.session_id, [])
                    notify = not target["installed"] and args.id not in seen and not state["declined"]
                    if notify:
                        seen.append(args.id)
                    output = {"should_notify": notify, "satellite": target}
                elif args.action == "discover":
                    output = check_new_skills(cfg, roots, state, args.manual)
                    if not args.manual:
                        state["pending_discovery_once"] = False
                else:
                    output = check_versions(cfg, rows, state, args.manual)
                    discovery_requested = (args.include_new or state["auto_discover"]
                                           or (state["pending_discovery_once"] and not args.manual))
                    if discovery_requested:
                        output["discovery"] = check_new_skills(cfg, roots, state, args.manual and args.include_new)
                        if not args.manual:
                            state["pending_discovery_once"] = False
                    if not args.manual:
                        state["pending_once"] = False
                stage = "state_save"
                save_state(state_path, state)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except LockBusy as exc:
        print(json.dumps({"status": "busy", "reason": "sync_in_progress",
                          "message": str(exc),
                          "hint": "Another client/session is syncing; this run skipped sync. "
                                  "Continue business and retry later."},
                         ensure_ascii=False))
        return 1
    except Exception:
        error = {"status": "error", "reason": stage + "_failed",
                 "message": "Sync/check unavailable; preserve existing consent and continue independent card work."}
        if args.action == "sync" and output is not None:
            error["sync_report"] = output
            error["message"] = "State save failed after sync; inspect sync_report and local versions before retrying."
        print(json.dumps(error, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

