#!/usr/bin/env python3
"""Convert CSS custom properties (color swatches) to Photoshop ACO format."""

import re
import struct
import sys
from collections import OrderedDict


def clamp(value: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, value))


def parse_css_colors(css_text: str) -> "OrderedDict[str, tuple[int,int,int]]":
    """Extract --name: rgb/rgba/hex color definitions from CSS text.

    De-dupes by name (last value wins), but preserves first-seen order.
    """
    swatches: OrderedDict[str, tuple[int, int, int]] = OrderedDict()

    # Match  --name: rgb(r,g,b)  or  --name: rgba(r,g,b,a)
    rgb_pattern = re.compile(
        r"--([A-Za-z0-9_-]+)\s*:\s*rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
    )
    # Match  --name: #RRGGBB  or  --name: #RGB
    hex_pattern = re.compile(
        r"--([A-Za-z0-9_-]+)\s*:\s*#([0-9A-Fa-f]{3,8})\s*;"
    )

    for m in rgb_pattern.finditer(css_text):
        name = m.group(1)
        r, g, b = clamp(int(m.group(2))), clamp(int(m.group(3))), clamp(int(m.group(4)))
        if name in swatches:
            # Update value but keep original position
            swatches[name] = (r, g, b)
        else:
            swatches[name] = (r, g, b)

    for m in hex_pattern.finditer(css_text):
        name = m.group(1)
        hexval = m.group(2)
        if len(hexval) == 3:
            r = int(hexval[0] * 2, 16)
            g = int(hexval[1] * 2, 16)
            b = int(hexval[2] * 2, 16)
        elif len(hexval) in (6, 8):
            r = int(hexval[0:2], 16)
            g = int(hexval[2:4], 16)
            b = int(hexval[4:6], 16)
        else:
            continue
        r, g, b = clamp(r), clamp(g), clamp(b)
        if name in swatches:
            swatches[name] = (r, g, b)
        else:
            swatches[name] = (r, g, b)

    return swatches


def write_aco(swatches: "OrderedDict[str, tuple[int,int,int]]", path: str) -> None:
    """Write a Photoshop .aco file (Version 1 + Version 2 with names)."""
    items = list(swatches.items())
    count = len(items)

    buf = bytearray()

    # ---- Version 1 ----
    buf += struct.pack(">HH", 1, count)
    for _name, (r, g, b) in items:
        # colorspace 0 = RGB, values scaled to 0-65535 (multiply by 257 maps 0-255 → 0-65535)
        buf += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)

    # ---- Version 2 ----
    buf += struct.pack(">HH", 2, count)
    for name, (r, g, b) in items:
        buf += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)
        # Name record
        encoded = name.encode("utf-16-be")
        # Length = number of UTF-16 code units INCLUDING the null terminator
        code_units = len(encoded) // 2
        length_with_null = code_units + 1
        buf += struct.pack(">I", length_with_null)
        buf += encoded
        buf += struct.pack(">H", 0)  # null terminator

    with open(path, "wb") as f:
        f.write(buf)


def main() -> None:
    css_path = sys.argv[1] if len(sys.argv) > 1 else "swatches.css"
    aco_path = sys.argv[2] if len(sys.argv) > 2 else "swatches.aco"

    with open(css_path, "r", encoding="utf-8") as f:
        css_text = f.read()

    swatches = parse_css_colors(css_text)

    if not swatches:
        print("No color swatches found.")
        sys.exit(1)

    write_aco(swatches, aco_path)

    names = list(swatches.keys())
    preview = ", ".join(names[:5])
    print(f"Wrote {len(swatches)} swatches to {aco_path}")
    print(f"First 5: {preview}")


if __name__ == "__main__":
    main()
