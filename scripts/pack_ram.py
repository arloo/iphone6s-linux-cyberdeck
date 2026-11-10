#!/usr/bin/env python3
"""Pack a RAM-only A9 m1n1 payload from explicit, local operator-owned inputs.

No download or iPhone/USB access. NEVER flashes or modifies NAND.
The upstream HoolockLinux boot format is concatenation:
    m1n1 + ASCII chosen.bootargs + DTB(s8000) + DTB(s8003) + Image.gz + initramfs.gz
The two DTBs being included does NOT imply either foundry variant was tested.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import struct

CHUNK = 1024 * 1024
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
GZIP_MAGIC = b"\x1f\x8b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validated_regular_file(value: str, kind: str) -> Path:
    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise ValueError(f"symlinked {kind} input refused")
    path = raw.resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing/empty/symlinked {kind} input")
    with path.open("rb") as stream:
        header = stream.read(8)
    if kind == "dtb":
        if header[:4] != FDT_MAGIC:
            raise ValueError("invalid FDT header")
        reported_length = struct.unpack(">I", header[4:8])[0]
        if reported_length < 40 or reported_length > path.stat().st_size:
            raise ValueError("invalid FDT total size")
    if kind in {"kernel", "initramfs"} and header[:2] != GZIP_MAGIC:
        raise ValueError(f"{kind}: gzip header missing")
    return path


def check_gzip(path: Path) -> None:
    # Read all compressed blocks to verify gzip CRC and trailer in constant memory.
    with gzip.open(path, "rb") as stream:
        for _ in iter(lambda: stream.read(CHUNK), b""):
            pass


def pack(
    m1n1: Path, dtb_s8000: Path, dtb_s8003: Path, image: Path,
    initramfs: Path, output: Path, bootargs: str
) -> str:
    if any(c in bootargs for c in "\r\n\x00") or len(bootargs) > 1024:
        raise ValueError("invalid boot arguments")
    if output.exists() or output.is_symlink():
        raise FileExistsError("refuse to overwrite an existing RAM payload")
    if any(output.resolve() == input_path for input_path in
           (m1n1, dtb_s8000, dtb_s8003, image, initramfs)):
        raise ValueError("refuse to overwrite an input file")
    output.parent.mkdir(parents=True, exist_ok=True)
    header = ("chosen.bootargs=" + bootargs + "\n").encode("ascii")
    try:
        with output.open("xb") as stream:
            for path in (m1n1,):
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(CHUNK), b""):
                        stream.write(chunk)
            stream.write(header)
            for path in (dtb_s8000, dtb_s8003, image, initramfs):
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(CHUNK), b""):
                        stream.write(chunk)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return sha256_file(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1n1", required=True)
    parser.add_argument("--dtb-s8000", required=True)
    parser.add_argument("--dtb-s8003", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--initramfs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootargs", default="console=tty0 hl_rd=shell")
    args = parser.parse_args()
    try:
        resources = {
            "m1n1": validated_regular_file(args.m1n1, "m1n1"),
            "dtb_s8000": validated_regular_file(args.dtb_s8000, "dtb"),
            "dtb_s8003": validated_regular_file(args.dtb_s8003, "dtb"),
            "image": validated_regular_file(args.image, "kernel"),
            "initramfs": validated_regular_file(args.initramfs, "initramfs"),
        }
        # Prove that compressed kernel/initramfs are intact before staging.
        check_gzip(resources["image"])
        check_gzip(resources["initramfs"])
        destination = Path(args.output).expanduser().absolute()
        digest = pack(*resources.values(), destination, args.bootargs)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    print(f"RAM_PAYLOAD_BUILT bytes={destination.stat().st_size} sha256={digest}")
    print("No physical device accessed. Keep operator-supplied licensed assets private.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
