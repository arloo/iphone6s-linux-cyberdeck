#!/usr/bin/env python3
"""Fail closed if a public repository push might expose personal Git identities.

Run from any directory in the repository. Only checks author/committer metadata,
commit messages and current tracked text. No credential or personal email values
are printed to the console.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def allowed_identity(address: str) -> bool:
    local, sep, domain = address.strip().lower().rpartition("@")
    if not sep or not local:
        return False
    if domain == "users.noreply.github.com":
        return bool(re.fullmatch(r"(?:[0-9]+\+)?[a-z0-9][a-z0-9-]*", local))
    return address.strip().lower() == "noreply@github.com"


def run(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def check() -> list[str]:
    errors: list[str] = []
    try:
        cwd = Path(run("rev-parse", "--show-toplevel").decode().strip())
        email = run("config", "--get", "user.email").decode().strip()
        if not allowed_identity(email):
            errors.append("local Git email is not a supported noreply identity")
        history = run("log", "--all", "--format=%H%x09%ae%x09%ce%x09%B%x00")
        for record in history.split(b"\x00"):
            if not record.strip():
                continue
            line = record.decode("utf-8", "replace")
            fields = line.split("\t", 3)
            if len(fields) != 4:
                errors.append("unexpected commit metadata format")
                break
            commit_id, author, committer, message = fields
            if not allowed_identity(author) or not allowed_identity(committer):
                errors.append(f"commit {commit_id[:12]} has a non-noreply identity")
            if any(not allowed_identity(x) for x in EMAIL.findall(message)):
                errors.append(f"commit {commit_id[:12]} has a personal email in its message")
        filenames = run("ls-files", "-z").split(b"\x00")
        for raw in filter(None, filenames):
            candidate = cwd / raw.decode("utf-8", "surrogateescape")
            if not candidate.is_file() or candidate.stat().st_size > 4_000_000:
                continue
            data = candidate.read_bytes()
            if b"\x00" in data:
                continue
            for found in EMAIL.findall(data.decode("utf-8", "replace")):
                if not allowed_identity(found):
                    errors.append(f"tracked file has a personal email: {candidate.relative_to(cwd)}")
                    break
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        errors.append(f"unable to finish privacy audit: {type(exc).__name__}")
    return errors


def main() -> int:
    issues = check()
    if issues:
        for issue in issues[:30]:
            print(f"BLOCKED: {issue}", file=sys.stderr)
        print(f"Git identity privacy audit failed ({len(issues)} issue(s))", file=sys.stderr)
        return 1
    print("PASS: Git history, current author/committer and tracked text pass noreply privacy audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
