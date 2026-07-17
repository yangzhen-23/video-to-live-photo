# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


_AUTO_IMAGEIO = object()


@dataclass(frozen=True, slots=True)
class Toolchain:
    ffmpeg: Path
    ffprobe: Path | None = None

    @classmethod
    def discover(
        cls,
        app_dir: Path | None = None,
        env: Mapping[str, str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
        imageio_getter: Callable[[], str] | None | object = _AUTO_IMAGEIO,
    ) -> "Toolchain":
        environment = os.environ if env is None else env
        root = app_dir or (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]
        )
        bundled_root = Path(getattr(sys, "_MEIPASS", root))
        ffmpeg_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        ffprobe_name = "ffprobe.exe" if os.name == "nt" else "ffprobe"

        explicit = environment.get("LIVEPHOTO_FFMPEG")
        candidates: list[Path] = []
        if explicit:
            candidates.append(Path(explicit))
        candidates.append(root / "tools" / ffmpeg_name)
        if bundled_root != root:
            candidates.append(bundled_root / "tools" / ffmpeg_name)
        path_value = which(ffmpeg_name) or which("ffmpeg")
        if path_value:
            candidates.append(Path(path_value))

        if imageio_getter is _AUTO_IMAGEIO:
            try:
                from imageio_ffmpeg import get_ffmpeg_exe

                getter: Callable[[], str] | None = get_ffmpeg_exe
            except ImportError:
                getter = None
        else:
            getter = imageio_getter  # type: ignore[assignment]
        if getter is not None:
            try:
                candidates.append(Path(getter()))
            except (RuntimeError, OSError):
                pass

        ffmpeg = next((item.resolve() for item in candidates if item.is_file()), None)
        if ffmpeg is None:
            raise RuntimeError(
                "找不到 FFmpeg。请先双击“安装依赖.bat”，再重新启动程序。"
            )

        probe_explicit = environment.get("LIVEPHOTO_FFPROBE")
        probe_candidates: list[Path] = []
        if probe_explicit:
            probe_candidates.append(Path(probe_explicit))
        probe_candidates.extend(
            [
                root / "tools" / ffprobe_name,
                bundled_root / "tools" / ffprobe_name,
                ffmpeg.with_name(ffprobe_name),
            ]
        )
        probe_path = which(ffprobe_name) or which("ffprobe")
        if probe_path:
            probe_candidates.append(Path(probe_path))
        ffprobe = next((item.resolve() for item in probe_candidates if item.is_file()), None)
        return cls(ffmpeg=ffmpeg, ffprobe=ffprobe)


def run_capture(
    args: Sequence[str | os.PathLike[str]], timeout: float = 60.0
) -> subprocess.CompletedProcess[str]:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(
        [str(item) for item in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
        creationflags=creationflags,
    )
