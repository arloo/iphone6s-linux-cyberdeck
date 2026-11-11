#!/usr/bin/env python3
"""Create 14x24 static bitmap ASCII glyphs from a locally installed TTF.

This script DOES NOT bundle or distribute font files. Provide a font that
you have the right to use when generating glyph data.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def rasterize(font_path: Path, output_path: Path):
    font = ImageFont.truetype(str(font_path), 18)
    lines = [
        "/* Generated locally; no TTF font file is redistributed. */",
        "#ifndef CYBERDECK_FONT_DATA_H",
        "#define CYBERDECK_FONT_DATA_H",
        "#include <stdint.h>",
        "static const uint16_t font14x24[95][24] = {",
    ]
    for code in range(32, 127):
        img = Image.new("L", (14, 24), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 0), chr(code), font=font, fill=255, anchor="lt")
        rows = []
        for y in range(24):
            bits = 0
            for x in range(14):
                if img.getpixel((x, y)) > 75:
                    bits |= 1 << (13 - x)
            rows.append(f"0x{bits:04x}")
        lines.append("    {" + ",".join(rows) + "}, /* char " + str(code) + " */")
    lines += ["};", "#endif"]
    output_path.write_text("\n".join(lines) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path,
                        default=Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rasterize(args.font, args.output)

if __name__ == "__main__":
    main()
