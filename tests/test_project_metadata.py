# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


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


def test_python_310_test_dependency_provides_tomllib_fallback():
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    assert 'tomli>=2; python_version < "3.11"' in requirements
