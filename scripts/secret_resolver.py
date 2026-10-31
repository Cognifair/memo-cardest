#!/usr/bin/env python3
"""Resolve Memo credentials without relying on a stale process environment.

Lookup order:
  1. process environment
  2. Windows HKCU\\Environment (user-level variable)
  3. %LOCALAPPDATA%\\MaimemoSecrets\\<name>
  4. <workspace>\\.memo-secrets\\<name> (and up to three parent directories)

The value is returned to the caller only. The CLI prints the source, never the secret.
"""
import argparse
import os
import sys
from pathlib import Path

FILE_NAME = {
    "MAIMEMO_TOKEN": "maimemo_token",
    "MINERU_TOKEN": "mineru_token",
    "MARKJI_TOKEN": "markji_token",
}


class SecretNotFound(RuntimeError):
    pass


def _read_user_env(name):
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value).strip() or None
    except Exception:
        return None


def _read_file(path):
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            return None
        value = path.read_text(encoding="utf-8", errors="strict").strip()
        if value and "\r" not in value and "\n" not in value:
            return value
    except Exception:
        return None
    return None


def _workspace_roots(workspace):
    base = Path(workspace) if workspace else Path.cwd()
    yield base
    for parent in list(base.parents)[:3]:
        yield parent


def get_secret(name, workspace=None):
    """Return (value, source). Raise SecretNotFound with checked sources, never the value."""
    name = str(name).strip().upper()
    if not FILE_NAME.get(name):
        raise ValueError("unsupported secret name: " + name)
    filename = FILE_NAME[name]
    checked = []

    value = os.environ.get(name, "").strip()
    if value:
        return value, "process environment"
    checked.append("process environment")

    value = _read_user_env(name)
    if value:
        return value, "Windows user environment"
    checked.append("Windows user environment")

    local = os.environ.get("LOCALAPPDATA")
    if local:
        path = Path(local) / "MaimemoSecrets" / filename
        value = _read_file(path)
        if value:
            return value, str(path)
        checked.append(str(path))

    for root in _workspace_roots(workspace):
        path = Path(root) / ".memo-secrets" / filename
        value = _read_file(path)
        if value:
            return value, str(path)
        checked.append(str(path))

    raise SecretNotFound(
        f"{name} not found. Checked: " + "; ".join(checked)
        + ". Configure a User environment variable or a private .memo-secrets file."
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="MAIMEMO_TOKEN, MINERU_TOKEN, or MARKJI_TOKEN")
    parser.add_argument("--workspace", type=Path, default=None,
                        help="Directory containing .memo-secrets (default: current directory)")
    args = parser.parse_args()
    try:
        _, source = get_secret(args.name, args.workspace)
    except (SecretNotFound, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{args.name}: found via {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
