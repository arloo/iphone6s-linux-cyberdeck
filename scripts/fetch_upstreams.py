#!/usr/bin/env python3
"""Fetch or verify only the explicitly pinned public upstream source trees.

Never downloads firmware, calibration, IPAs, IPSWs, boot payloads or credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests/upstreams.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
GITHUB_URL = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$")


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported manifest version")
    sources = data.get("sources", {})
    if not isinstance(sources, dict) or not sources:
        raise ValueError("manifest has no upstream sources")
    for name, entry in sources.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("invalid upstream component name")
        if not isinstance(entry, dict) or not GITHUB_URL.fullmatch(entry.get("url", "")):
            raise ValueError(f"{name}: source is not an allowed HTTPS GitHub Git URL")
        if not HEX40.fullmatch(entry.get("commit", "")):
            raise ValueError(f"{name}: source commit must be a 40-hex SHA")
    return data


def git(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=cwd, text=True, stderr=subprocess.PIPE
    ).strip()


def verify_checkout(path: Path, source: dict) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ValueError("checkout must be a non-symlink directory")
    if git(["remote", "get-url", "origin"], cwd=path) != source["url"]:
        raise ValueError("upstream origin URL does not match source manifest")
    if git(["rev-parse", "HEAD"], cwd=path) != source["commit"]:
        raise ValueError("upstream HEAD does not match pinned commit")
    if git(["status", "--porcelain"], cwd=path):
        raise ValueError("upstream checkout is dirty; refuse to replace data")


def ensure_checkout(dest: Path, source: dict, verify_only: bool) -> None:
    if not dest.exists():
        if verify_only:
            raise ValueError("checkout not found")
        # A GitHub clone is public, pinned and produces no source modifications.
        git(["clone", "--filter=blob:none", "--no-checkout", source["url"], str(dest)])
        git(["fetch", "--depth=1", "origin", source["commit"]], cwd=dest)
        git(["checkout", "--detach", source["commit"]], cwd=dest)
    verify_checkout(dest, source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--component", default="all")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    sources = load_manifest()["sources"]
    if args.component != "all" and args.component not in sources:
        parser.error("unknown component")
    root = args.destination.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    selected = sources if args.component == "all" else {args.component: sources[args.component]}
    for name, source in selected.items():
        dest = root / name
        print(f"{name}: checking pinned commit {source['commit'][:12]}", flush=True)
        ensure_checkout(dest, source, args.verify_only)
        print(f"{name}: SOURCE_PIN_VERIFIED", flush=True)
    print("No private firmware or device data fetched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
