# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.verify_bundle as verifier


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_help(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / script), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_verify_bundle_script_can_run_directly():
    result = run_help("verify_bundle.py")
    assert result.returncode == 0, result.stderr


def test_make_sample_video_script_can_run_directly():
    result = run_help("make_sample_video.py")
    assert result.returncode == 0, result.stderr


def test_capture_ui_script_can_run_directly():
    result = run_help("capture_ui.py")
    assert result.returncode == 0, result.stderr


def test_markdown_link_checker_can_run_directly():
    result = run_help("check_markdown_links.py")
    assert result.returncode == 0, result.stderr


def test_repository_checker_can_run_directly():
    result = run_help("check_repository.py")
    assert result.returncode == 0, result.stderr


def test_verify_bundle_maps_targets_to_required_roles():
    assert verifier.TARGET_ROLES == {
        "iphone": {"iphone_photo", "iphone_video"},
        "android": {"android_motion_photo"},
        "vivo": {"vivo_live_photo_image", "vivo_live_photo_video"},
        "windows": {"windows_photo", "windows_video"},
    }
    assert verifier.required_roles(["vivo", "windows"]) == {
        "vivo_live_photo_image",
        "vivo_live_photo_video",
        "windows_photo",
        "windows_video",
        "instructions",
    }
