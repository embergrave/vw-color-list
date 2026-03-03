#!/usr/bin/env python3
"""Convert location map text entries to Photoshop ACO color swatches."""

import re
import struct
import sys
from collections import OrderedDict


def clamp(value: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, value))


def split_base_and_number(name: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)(\d+)$", name)
    if not match:
        return name, None
    return match.group(1), match.group(2)


def parse_locationmap(text: str) -> "OrderedDict[str, tuple[int, int, int]]":
    """Parse lines in format: Label: R,G,B.

    De-dupes by label (last value wins), preserving first-seen order.
    """
    swatches: OrderedDict[str, tuple[int, int, int]] = OrderedDict()
    line_pattern = re.compile(
        r"^\s*([^:#\r\n]+?)\s*:\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$"
    )

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = line_pattern.match(stripped)
        if not match:
            continue

        name = match.group(1).strip()
        r = clamp(int(match.group(2)))
        g = clamp(int(match.group(3)))
        b = clamp(int(match.group(4)))
        swatches[name] = (r, g, b)

    return swatches


def collapse_numbered_variants(
    swatches: "OrderedDict[str, tuple[int, int, int]]",
) -> "OrderedDict[str, tuple[int, int, int]]":
    """Collapse labels ending in digits when all variants share one RGB value.

    Example: Dolmen01/Dolmen02/Dolmen03 with same RGB => Dolmen.
    """
    variant_colors_by_base: dict[str, set[tuple[int, int, int]]] = {}
    variant_counts_by_base: dict[str, int] = {}

    for name, rgb in swatches.items():
        base, suffix = split_base_and_number(name)
        if suffix is None:
            continue
        variant_colors_by_base.setdefault(base, set()).add(rgb)
        variant_counts_by_base[base] = variant_counts_by_base.get(base, 0) + 1

    collapsible_bases = {
        base
        for base, colors in variant_colors_by_base.items()
        if variant_counts_by_base.get(base, 0) > 1 and len(colors) == 1
    }

    collapsed: OrderedDict[str, tuple[int, int, int]] = OrderedDict()
    used_collapsed_base: set[str] = set()

    for name, rgb in swatches.items():
        base, suffix = split_base_and_number(name)
        if suffix is not None and base in collapsible_bases:
            if base not in used_collapsed_base:
                collapsed[base] = rgb
                used_collapsed_base.add(base)
            continue

        collapsed[name] = rgb

    return collapsed


def write_aco(swatches: "OrderedDict[str, tuple[int, int, int]]", path: str) -> None:
    """Write a Photoshop .aco file (Version 1 + Version 2 with names)."""
    items = list(swatches.items())
    count = len(items)

    buffer = bytearray()

    # ---- Version 1 ----
    buffer += struct.pack(">HH", 1, count)
    for _name, (r, g, b) in items:
        buffer += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)

    # ---- Version 2 ----
    buffer += struct.pack(">HH", 2, count)
    for name, (r, g, b) in items:
        buffer += struct.pack(">HHHHH", 0, r * 257, g * 257, b * 257, 0)
        encoded_name = name.encode("utf-16-be")
        length_with_null = (len(encoded_name) // 2) + 1
        buffer += struct.pack(">I", length_with_null)
        buffer += encoded_name
        buffer += struct.pack(">H", 0)

    with open(path, "wb") as output_file:
        output_file.write(buffer)


def main() -> None:
    input_path = sys.argv[1] if len(sys.argv) > 1 else "locationmap.txt"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "swatches.aco"

    with open(input_path, "r", encoding="utf-8") as input_file:
        text = input_file.read()

    swatches = parse_locationmap(text)
    if not swatches:
        print("No valid swatches found.")
        sys.exit(1)

    swatches = collapse_numbered_variants(swatches)

    write_aco(swatches, output_path)
    names = list(swatches.keys())
    preview = ", ".join(names[:5])
    print(f"Wrote {len(swatches)} swatches to {output_path}")
    print(f"First 5: {preview}")


if __name__ == "__main__":
    main()