#!/usr/bin/env python3
"""Owner-only N71 A9 file vault: durable Dell backup, phone RAM workspace.

This is NOT on-device NAND, a permanent Linux rootfs, or production recovery.
Authenticated pinned-host-key USB SSH is the only transport. No personal file
contents, device IDs, credentials or filenames are printed or added to Git.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile
import tempfile

CATEGORIES = ("Music", "Documents", "Projects", "Downloads", "Notes", "Kali")
ROOT = Path.home() / ".local/share/cyberdeck/file-vault"
CURRENT = ROOT / "current"
SSH_JSON = (Path.home() / "Documenti/cyberdeck-a9-linux/private-touch-live-test"
            / "n71-ssh-20261116/client-config-PRIVATE.json")
MAX_FILE = 256 * 1024 * 1024
# Keep the volatile phone workspace well below the 1 GiB ramfs limit.
MAX_TOTAL = 512 * 1024 * 1024
MAX_ARCHIVE = MAX_TOTAL + 64 * 1024 * 1024
MAX_FILES = 4096


def verify_private(path, directory=False):
    if path.is_symlink():
        raise ValueError("Symlinked vault path refused")
    info = path.stat(follow_symlinks=False)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Insecure vault ownership or permissions")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError("Expected private directory")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise ValueError("Expected private regular file")


def initialize():
    for path in (ROOT, CURRENT):
        if not path.exists():
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        verify_private(path, True)
    for folder in CATEGORIES:
        path = CURRENT / folder
        if not path.exists():
            path.mkdir(mode=0o700)
        verify_private(path, True)


def files_in(root=None):
    if root is None:
        root = CURRENT
    count = 0
    total = 0
    collected = []
    for category in CATEGORIES:
        for path in sorted((root / category).rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlinks are forbidden in a Cyberdeck archive")
            if path.is_dir():
                continue
            verify_private(path)
            size = path.stat().st_size
            if size > MAX_FILE:
                raise ValueError("A single file exceeds the bounded 256 MiB limit")
            count += 1
            total += size
            if count > MAX_FILES or total > MAX_TOTAL:
                raise ValueError("Cyberdeck vault exceeds its safety limits")
            collected.append(path)
    return collected, total


def ssh_args():
    import json
    config = json.loads(SSH_JSON.read_text())
    return ([arg for arg in config["ssh_common_args"] if arg != "-n"]
            + ["-i", config["identity_file"], config["target"]])


def validate_members(tar):
    found = set()
    total = 0
    count = 0
    for member in tar:
        name = member.name.removeprefix("./")
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] not in CATEGORIES
                or any(part in ("", ".", "..") for part in parts)
                or PurePosixPath(name).is_absolute()):
            raise ValueError("Unsafe archive pathname")
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise ValueError("Archive contains symlink or special device")
        if name in found:
            raise ValueError("Duplicate archive path")
        found.add(name)
        if member.isfile():
            count += 1
            total += member.size
            if member.size < 0 or member.size > MAX_FILE:
                raise ValueError("Archive member exceeds file-size limit")
            if count > MAX_FILES or total > MAX_TOTAL:
                raise ValueError("Archive exceeds file count/size limits")
    return count, total


def validate_archive(path):
    with tarfile.open(path, "r:gz") as archive:
        return validate_members(archive)


def ingest(src, category):
    if category not in CATEGORIES:
        raise ValueError("Unknown target folder")
    source = Path(src).expanduser()
    if source.is_symlink():
        raise ValueError("Symlink source refused")
    info = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Import requires a regular file owned by the operator")
    if source.stat().st_size > MAX_FILE:
        raise ValueError("File too large for RAM workspace")
    if source.name in ("", ".", "..") or "/" in source.name:
        raise ValueError("Invalid file name")
    target = CURRENT / category / source.name
    if target.exists() or target.is_symlink():
        raise FileExistsError("File already present: refuse silent overwrite")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".incoming-",
                                      delete=False) as temp:
        name = Path(temp.name)
        os.chmod(name, 0o600)
        with source.open("rb") as inp:
            shutil.copyfileobj(inp, temp, 256 * 1024)
        temp.flush()
        os.fsync(temp.fileno())
    try:
        os.replace(name, target)
    finally:
        if name.exists():
            name.unlink()
    files_in()
    return target


def pack_current():
    files, size = files_in()
    with tempfile.NamedTemporaryFile(dir=ROOT, suffix=".tar.gz", delete=False) as temp:
        archive_path = Path(temp.name)
        os.chmod(archive_path, 0o600)
    try:
        with tarfile.open(archive_path, "w:gz", format=tarfile.GNU_FORMAT) as archive:
            for category in CATEGORIES:
                archive.add(CURRENT / category, arcname=category, recursive=False)
            for path in files:
                archive.add(path, arcname=path.relative_to(CURRENT).as_posix(), recursive=False)
        if archive_path.stat().st_size > MAX_ARCHIVE:
            raise ValueError("Compressed archive too large")
        assert validate_archive(archive_path)[0] == len(files)
        return archive_path, size
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise


def restore():
    archive, raw_size = pack_current()
    try:
        device_command = (
            "umask 077; mkdir -p /data && chmod 700 /data && "
            "tar -xzf - -C /data && sync && "
            "printf N71_VAULT_RAM_RESTORED"
        )
        with archive.open("rb") as stream:
            done = subprocess.run(ssh_args() + [device_command], stdin=stream,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=180)
        if done.returncode != 0 or done.stdout.strip() != b"N71_VAULT_RAM_RESTORED":
            raise RuntimeError("SSH restoration refused or failed; no insecure fallback")
        print("CYBERDECK_RAM_WORKSPACE_RESTORED via_USB_SSH=yes"
              f" files={len(files_in()[0])} bytes={raw_size} persists_on_Dell=yes"
              " phone_NAND=no")
    finally:
        archive.unlink(missing_ok=True)


def safe_extract(archive_path, destination):
    with tarfile.open(archive_path, "r:gz") as archive:
        count, total = validate_members(archive)
        for member in archive:
            name = member.name.removeprefix("./")
            dest = destination / name
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            src = archive.extractfile(member)
            if src is None:
                raise ValueError("Missing file content")
            with dest.open("xb") as out:
                shutil.copyfileobj(src, out, 256 * 1024)
                out.flush()
                os.fsync(out.fileno())
            dest.chmod(0o600)
    return count, total


def backup():
    cmd = ("umask 077; test -d /data || exit 40; "
           "tar -czf - -C /data " + " ".join(CATEGORIES))
    with tempfile.NamedTemporaryFile(dir=ROOT, suffix=".incoming.tar.gz", delete=False) as tmp:
        path = Path(tmp.name)
        os.chmod(path, 0o600)
        with subprocess.Popen(ssh_args() + [cmd], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            copied = 0
            while True:
                block = process.stdout.read(256 * 1024)
                if not block:
                    break
                copied += len(block)
                if copied > MAX_ARCHIVE:
                    process.kill()
                    raise ValueError("Device backup stream exceeded maximum size")
                tmp.write(block)
            rc = process.wait(timeout=180)
            if rc:
                raise RuntimeError("Phone backup unavailable; leaving existing vault intact")
        tmp.flush()
        os.fsync(tmp.fileno())
    try:
        count, size = validate_archive(path)
        current_files, _ = files_in()
        if count == 0 and current_files:
            raise ValueError("Refusing to overwrite populated vault with empty device")
        stage = Path(tempfile.mkdtemp(prefix=".device-backup-", dir=ROOT))
        stage.chmod(0o700)
        for folder in CATEGORIES:
            (stage / folder).mkdir(mode=0o700)
        try:
            # Preserve files that may have been imported on the Dell but not
            # yet synced to the phone. Remote content overlays matching names.
            for local in current_files:
                relative = local.relative_to(CURRENT)
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                shutil.copy2(local, target)
                target.chmod(0o600)
            with tarfile.open(path, "r:gz") as archive:
                validate_members(archive)
                for item in archive:
                    if not item.isfile():
                        continue
                    dest = stage / item.name.removeprefix("./")
                    data = archive.extractfile(item)
                    if data is None:
                        raise ValueError("Archive member unreadable")
                    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as temp:
                        candidate = Path(temp.name)
                        os.chmod(candidate, 0o600)
                        shutil.copyfileobj(data, temp, 256 * 1024)
                        temp.flush()
                        os.fsync(temp.fileno())
                    os.replace(candidate, dest)
            files_in(stage)
            previous = ROOT / "previous"
            if previous.exists():
                shutil.rmtree(previous)
            os.replace(CURRENT, previous)
            os.replace(stage, CURRENT)
            print(f"CYBERDECK_DELL_BACKUP_UPDATED files={count} bytes={size}"
                  " from_USB_SSH=yes persistent_on_Dell=yes")
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    finally:
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Owner-private USB file sync; no phone NAND")
    parser.add_argument("action", choices=("init", "status", "import", "restore", "backup"))
    parser.add_argument("--file", help="local file to import into Dell vault")
    parser.add_argument("--folder", choices=CATEGORIES, default="Documents")
    args = parser.parse_args()
    initialize()
    if args.action == "init":
        print("N71_DELL_FILE_VAULT_READY folders=" + ",".join(CATEGORIES))
    elif args.action == "status":
        files, total = files_in()
        print(f"N71_VAULT_STATUS files={len(files)} bytes={total}"
              " host_persistent=yes phone_local_RAM_only=yes")
    elif args.action == "import":
        if not args.file:
            parser.error("--file required for import")
        ingest(args.file, args.folder)
        print("N71_FILE_IMPORTED_TO_PRIVATE_DELL_VAULT; use restore to send to phone RAM")
    elif args.action == "restore":
        restore()
    else:
        backup()


if __name__ == "__main__":
    main()
