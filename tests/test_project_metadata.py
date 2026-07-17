# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_project_declares_author_and_apache_license():
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["authors"] == [{"name": "杨振"}]
    assert project["license"] == {"text": "Apache-2.0"}
    assert project["readme"] == "README.md"
    assert "Dynamic Photos" in project["keywords"]


def test_windows_build_copies_legal_files():
    script = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")

    for name in (
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "COMPATIBILITY.md",
    ):
        assert name in script
