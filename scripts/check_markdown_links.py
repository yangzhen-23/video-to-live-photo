# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote


MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
REMOTE_PREFIXES = ("http://", "https://", "mailto:", "data:")


def find_broken_links(root: Path, markdown_files: Iterable[Path]) -> list[str]:
    root = root.resolve()
    broken: list[str] = []
    for document in markdown_files:
        document = document.resolve()
        for target in MARKDOWN_LINK.findall(
            document.read_text(encoding="utf-8")
        ):
            clean = target.strip().split("#", 1)[0]
            if clean.startswith("<") and clean.endswith(">"):
                clean = clean[1:-1]
            if (
                not clean
                or clean.startswith(REMOTE_PREFIXES)
                or clean.startswith("../../releases/")
            ):
                continue
            resolved = (document.parent / unquote(clean)).resolve()
            if not resolved.exists():
                broken.append(
                    f"{document.relative_to(root).as_posix()} -> {clean}"
                )
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Markdown 相对链接")
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    root = args.root.resolve()
    files = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    broken = find_broken_links(root, files)
    if broken:
        print("Broken Markdown links:")
        for item in broken:
            print(f"- {item}")
        return 1
    print("All Markdown links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
