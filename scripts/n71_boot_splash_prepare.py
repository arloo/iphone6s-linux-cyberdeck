#!/usr/bin/env python3
"""Build a RAM-only iPhone 6s boot splash from an operator-supplied PNG.

No USB access. No NAND writes. Explicit opt-in at runtime; debug remains default.
The compressed BGRX result is intended for /usr/lib/cyberdeck/splash.bgrx.gz
in a private, operator-controlled initramfs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path

from PIL import Image, ImageOps

WIDTH, HEIGHT = 750, 1334
RAW_BYTES = WIDTH * HEIGHT * 4


def prepare(input_png: Path, output_dir: Path) -> dict[str, str | int]:
    input_png = input_png.expanduser().resolve(strict=True)
    if input_png.is_symlink() or not input_png.is_file():
        raise ValueError("splash input must be an ordinary PNG file")
    with Image.open(input_png) as source:
        if source.format != "PNG":
            raise ValueError("input format is not PNG")
        original = source.convert("RGB")
    # Preserve all typography and artwork: center with black letterboxing.
    resized = ImageOps.contain(original, (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    canvas.paste(resized, ((WIDTH - resized.width) // 2, (HEIGHT - resized.height) // 2))
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = canvas.tobytes("raw", "BGRX")
    if len(raw) != RAW_BYTES:
        raise ValueError("unexpected framebuffer size")
    gz = output_dir / "splash.bgrx.gz"
    png = output_dir / "splash-iphone6s-750x1334.png"
    if gz.exists() or png.exists():
        raise FileExistsError("output exists; refusing to replace a previous tested asset")
    canvas.save(png, optimize=True)
    # Reproducible compressed data; no timestamps or filenames in gzip header.
    with gz.open("xb") as destination:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, mtime=0, fileobj=destination) as stream:
            stream.write(raw)
    digest = hashlib.sha256(gz.read_bytes()).hexdigest()
    (output_dir / "splash.sha256").write_text(digest + "  /usr/lib/cyberdeck/splash.bgrx.gz\n")
    (output_dir / "boot-mode").write_text("showcase\n")
    return {"raw_bytes": len(raw), "gzip_bytes": gz.stat().st_size, "sha256": digest, "preview": str(png)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("png", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    print(prepare(a.png, a.output))


if __name__ == "__main__":
    main()
