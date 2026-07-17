# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振

from pathlib import Path

from scripts.check_markdown_links import find_broken_links


def test_markdown_link_checker_reports_missing_relative_target(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "[missing](docs/missing.md)\n[web](https://example.com)\n",
        encoding="utf-8",
    )

    assert find_broken_links(tmp_path, [readme]) == [
        "README.md -> docs/missing.md"
    ]


def test_public_documentation_links_are_valid():
    root = Path(__file__).resolve().parents[1]
    files = [root / "README.md", *sorted((root / "docs").glob("*.md"))]

    assert find_broken_links(root, files) == []
