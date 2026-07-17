# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from datetime import datetime
from pathlib import Path

from livephoto.core.naming import safe_stem, unique_bundle_dir, vivo_pair_stem


def test_safe_stem_handles_windows_illegal_characters():
    assert safe_stem('CON:<测试>?') == "CON_测试"


def test_safe_stem_handles_reserved_and_empty_names():
    assert safe_stem("CON") == "_CON"
    assert safe_stem("...  ") == "未命名"


def test_safe_stem_limits_length_without_trailing_separator():
    result = safe_stem("一" * 120, max_length=40)
    assert len(result) == 40
    assert not result.endswith((".", " ", "_"))


def test_unique_bundle_dir_uses_timestamp_and_suffix(tmp_path: Path):
    now = datetime(2026, 7, 18, 9, 8, 7)
    first = unique_bundle_dir(tmp_path, "假期", now=now)
    assert first.name == "假期_Live图_20260718_090807"
    first.mkdir()
    second = unique_bundle_dir(tmp_path, "假期", now=now)
    assert second.name == "假期_Live图_20260718_090807_2"


def test_vivo_pair_stem_uses_originos_camera_pattern():
    now = datetime(2026, 7, 18, 12, 34, 56)

    assert vivo_pair_stem(now) == "IMG_20260718_123456"
