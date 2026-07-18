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


def test_public_documentation_describes_selective_multi_clip_workflow():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    compatibility = (root / "docs" / "COMPATIBILITY.md").read_text(encoding="utf-8")
    learning_guide = (root / "docs" / "PROJECT_CODE_AND_GIT_GUIDE.md").read_text(
        encoding="utf-8"
    )

    assert "选择一个或多个目标设备" in readme
    assert "00:03.00" in readme
    assert "--target vivo --target windows" in readme
    assert "BatchConversionWorker" in architecture
    assert "只生成所选设备" in compatibility
    assert "schema_version 当前为 3" in learning_guide
    assert "time_spinbox.py" in learning_guide
