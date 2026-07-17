# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from pathlib import Path

from scripts.check_repository import find_repository_issues


EXPECTED_PRIVATE_SAMPLE_NAMES = {
    "6月22日.mp4",
    "IMG_20260717_043416.jpg",
    "IMG_20260717_043416.mp4",
}


def test_repository_check_reports_private_samples_and_large_files(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "IMG_20260717_043416.jpg").write_bytes(b"sample")
    (tmp_path / "public.bin").write_bytes(b"x" * 16)

    issues = find_repository_issues(tmp_path, max_file_bytes=8)

    assert any("IMG_20260717_043416.jpg" in issue for issue in issues)
    assert any("public.bin" in issue and "large" in issue.lower() for issue in issues)


def test_repository_check_skips_local_only_directories(tmp_path: Path):
    for directory in ("private_samples", "release", ".venv", "dist"):
        target = tmp_path / directory
        target.mkdir()
        (target / "IMG_20260717_043416.mp4").write_bytes(b"x" * 16)

    assert find_repository_issues(tmp_path, max_file_bytes=8) == []


def test_public_repository_configuration_exists():
    project_root = Path(__file__).resolve().parents[1]
    gitignore = (project_root / ".gitignore").read_text(encoding="utf-8")

    for entry in (
        "private_samples/",
        "release/",
        "verification/",
        "build_tools/",
        ".env",
    ):
        assert entry in gitignore

    workflow = project_root / ".github" / "workflows" / "ci.yml"
    assert workflow.is_file()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "windows-latest" in workflow_text
    assert "3.10" in workflow_text
    assert "3.12" in workflow_text
    assert "check_repository.py" in workflow_text


def test_private_sample_name_list_stays_in_sync():
    from scripts.check_repository import PRIVATE_SAMPLE_NAMES

    assert set(PRIVATE_SAMPLE_NAMES) == EXPECTED_PRIVATE_SAMPLE_NAMES
