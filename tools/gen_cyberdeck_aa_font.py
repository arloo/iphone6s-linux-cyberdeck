#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rasterize an operator-supplied TrueType font into baseline-aligned alpha glyphs.

Generated raster headers are local build artifacts, not distributed font assets.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate(font_path, output):
    lines = ['/* Generated locally from operator-supplied TTF. */',
             '#ifndef N71_FONT_AA_H', '#define N71_FONT_AA_H', '#include <stdint.h>']
    for name, size, width, height, baseline in [
            ('SMALL', 25, 18, 34, 26), ('LARGE', 40, 28, 52, 40)]:
        font = ImageFont.truetype(str(font_path), size)
        lines += [f'#define N71_FONT_{name}_W {width}',
                  f'#define N71_FONT_{name}_H {height}',
                  f'static const uint8_t font_{name.lower()}_alpha[95][{height}][{width}] = {{']
        for code in range(32, 127):
            image = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(image)
            char = chr(code)
            draw.text(((width - font.getlength(char)) / 2, baseline), char,
                      font=font, fill=255, anchor='ls')
            lines.append(' {')
            for row in range(height):
                lines.append('  {' + ','.join(str(image.getpixel((col, row)))
                                             for col in range(width)) + '},')
            lines.append(' },')
        lines.append('};')
    lines.append('#endif')
    output.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    generate(args.font, args.output)
