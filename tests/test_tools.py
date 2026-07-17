# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path

import pytest

from livephoto.core.tools import Toolchain


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"binary")
    return path


def test_explicit_ffmpeg_environment_has_highest_priority(tmp_path: Path):
    explicit = touch(tmp_path / "explicit" / "ffmpeg.exe")
    adjacent = touch(tmp_path / "app" / "tools" / "ffmpeg.exe")
    found = Toolchain.discover(
        app_dir=tmp_path / "app",
        env={"LIVEPHOTO_FFMPEG": str(explicit)},
        which=lambda _name: str(adjacent),
        imageio_getter=lambda: str(adjacent),
    )
    assert found.ffmpeg == explicit.resolve()


def test_adjacent_tools_folder_precedes_path(tmp_path: Path):
    adjacent = touch(tmp_path / "app" / "tools" / "ffmpeg.exe")
    adjacent_probe = touch(tmp_path / "app" / "tools" / "ffprobe.exe")
    path_copy = touch(tmp_path / "path" / "ffmpeg.exe")
    found = Toolchain.discover(
        app_dir=tmp_path / "app",
        env={},
        which=lambda _name: str(path_copy),
        imageio_getter=None,
    )
    assert found.ffmpeg == adjacent.resolve()
    assert found.ffprobe == adjacent_probe.resolve()


def test_pyinstaller_internal_tools_folder_is_supported(tmp_path: Path, monkeypatch):
    app_dir = tmp_path / "dist"
    bundled_root = app_dir / "_internal"
    bundled_ffmpeg = touch(bundled_root / "tools" / "ffmpeg.exe")
    bundled_ffprobe = touch(bundled_root / "tools" / "ffprobe.exe")
    monkeypatch.setattr("livephoto.core.tools.sys._MEIPASS", str(bundled_root), raising=False)

    found = Toolchain.discover(
        app_dir=app_dir,
        env={},
        which=lambda _name: None,
        imageio_getter=None,
    )

    assert found.ffmpeg == bundled_ffmpeg.resolve()
    assert found.ffprobe == bundled_ffprobe.resolve()


def test_path_then_imageio_fallback(tmp_path: Path):
    path_copy = touch(tmp_path / "path" / "ffmpeg.exe")
    imageio_copy = touch(tmp_path / "imageio" / "ffmpeg.exe")
    from_path = Toolchain.discover(
        app_dir=tmp_path / "empty",
        env={},
        which=lambda name: str(path_copy) if name.startswith("ffmpeg") else None,
        imageio_getter=lambda: str(imageio_copy),
    )
    assert from_path.ffmpeg == path_copy.resolve()

    from_imageio = Toolchain.discover(
        app_dir=tmp_path / "empty",
        env={},
        which=lambda _name: None,
        imageio_getter=lambda: str(imageio_copy),
    )
    assert from_imageio.ffmpeg == imageio_copy.resolve()


def test_missing_ffmpeg_has_actionable_chinese_error(tmp_path: Path):
    with pytest.raises(RuntimeError, match="安装依赖"):
        Toolchain.discover(
            app_dir=tmp_path,
            env={},
            which=lambda _name: None,
            imageio_getter=None,
        )
