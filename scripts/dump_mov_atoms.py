# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
"""Print an ISO-BMFF/MOV atom tree for format research and diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path


CONTAINERS = {
    b"moov",
    b"trak",
    b"mdia",
    b"minf",
    b"dinf",
    b"stbl",
    b"edts",
    b"tref",
    b"gmhd",
    b"udta",
    b"ilst",
}


def walk(data: bytes, start: int, end: int, depth: int = 0) -> None:
    position = start
    while position + 8 <= end:
        size = int.from_bytes(data[position : position + 4], "big")
        atom_type = data[position + 4 : position + 8]
        header = 8
        if size == 1:
            if position + 16 > end:
                return
            size = int.from_bytes(data[position + 8 : position + 16], "big")
            header = 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            return
        label = atom_type.decode("latin-1")
        print(f"{'  ' * depth}{position:10d} {size:10d} {label}")
        if atom_type in CONTAINERS:
            walk(data, position + header, position + size, depth + 1)
        elif atom_type == b"meta" and size >= header + 4:
            walk(data, position + header + 4, position + size, depth + 1)
        position += size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    payload = args.path.read_bytes()
    walk(payload, 0, len(payload))


if __name__ == "__main__":
    main()
