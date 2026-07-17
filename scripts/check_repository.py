# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
"""Audit the repository for files that must not be published."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_PUBLIC_FILE_BYTES = 10 * 1024 * 1024

PRIVATE_SAMPLE_NAMES = frozenset(
    {
        "6月22日.mp4",
        "IMG_20260717_043416.jpg",
        "IMG_20260717_043416.mp4",
    }
)

LOCAL_ONLY_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        ".pytest_cache",
        "__pycache__",
        "build",
        "build_tools",
        "dist",
        "htmlcov",
        "private_samples",
        "release",
        "verification",
        "Live图成品",
    }
)


def _walk_public_files(root: Path) -> Iterable[Path]:
    """Yield files outside directories that are intentionally local-only."""

    for current, directories, files in os.walk(root, topdown=True):
        directories[:] = [
            name
            for name in directories
            if name not in LOCAL_ONLY_DIRECTORIES and not name.endswith(".egg-info")
        ]
        current_path = Path(current)
        for name in files:
            yield current_path / name


def find_repository_issues(
    root: Path,
    *,
    max_file_bytes: int = MAX_PUBLIC_FILE_BYTES,
) -> list[str]:
    """Return deterministic, human-readable repository hygiene issues."""

    root = root.resolve()
    issues: list[str] = []
    for path in _walk_public_files(root):
        relative = path.relative_to(root).as_posix()
        if path.name in PRIVATE_SAMPLE_NAMES:
            issues.append(f"private sample: {relative}")
        try:
            size = path.stat().st_size
        except OSError as error:
            issues.append(f"unreadable file: {relative} ({error})")
            continue
        if size > max_file_bytes:
            issues.append(
                f"large file: {relative} ({size / (1024 * 1024):.2f} MiB; "
                f"limit {max_file_bytes / (1024 * 1024):.2f} MiB)"
            )
    return sorted(issues)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check that a working tree is safe and small enough to publish."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=PROJECT_ROOT,
        help="repository root (defaults to the project root)",
    )
    parser.add_argument(
        "--max-mib",
        type=float,
        default=MAX_PUBLIC_FILE_BYTES / (1024 * 1024),
        help="maximum allowed public file size in MiB (default: 10)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_mib <= 0:
        raise SystemExit("--max-mib must be greater than zero")
    issues = find_repository_issues(
        args.root,
        max_file_bytes=int(args.max_mib * 1024 * 1024),
    )
    if issues:
        print("Repository check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Repository check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
