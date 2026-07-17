# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from .models import ConversionOptions, VideoInfo
from .tools import Toolchain


QUALITY = {
    "fast": ("veryfast", "24"),
    "balanced": ("medium", "20"),
    "high": ("slow", "18"),
}


class TranscodeError(RuntimeError):
    pass


class ConversionCancelled(RuntimeError):
    pass


def build_transcode_command(
    options: ConversionOptions,
    info: VideoInfo,
    toolchain: Toolchain,
    output: Path,
) -> list[str]:
    preset, crf = QUALITY[options.quality]
    command = [
        str(toolchain.ffmpeg),
        "-hide_banner",
        "-y",
        "-ss",
        f"{options.start_time:.6f}",
        "-i",
        str(options.input_path),
        "-t",
        f"{options.duration:.6f}",
        "-map",
        "0:v:0",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-profile:v",
        "high",
        "-level:v",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-metadata:s:v:0",
        "rotate=0",
    ]
    if info.has_audio and not options.mute:
        command.extend(
            ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "160k", "-ac", "2"]
        )
    else:
        command.append("-an")
    container = "mov" if output.suffix.lower() == ".mov" else "mp4"
    if container == "mp4":
        command.extend(["-movflags", "+faststart"])
    command.extend(
        [
            "-f",
            container,
            "-progress",
            "pipe:1",
            "-nostats",
            str(output),
        ]
    )
    return command


def build_cover_command(
    options: ConversionOptions,
    toolchain: Toolchain,
    output: Path,
) -> list[str]:
    return [
        str(toolchain.ffmpeg),
        "-hide_banner",
        "-y",
        "-ss",
        f"{options.cover_time:.6f}",
        "-i",
        str(options.input_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-q:v",
        "2",
        str(output),
    ]


def run_ffmpeg(
    command: Sequence[str | os.PathLike[str]],
    duration: float,
    progress: Callable[[float], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [str(item) for item in command],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=False,
        creationflags=creationflags,
    )
    assert process.stdout is not None
    last_progress = -1.0
    output_tail: list[str] = []
    for line in process.stdout:
        output_tail.append(line.rstrip())
        if len(output_tail) > 120:
            del output_tail[:20]
        if cancel and cancel():
            process.terminate()
            process.wait()
            raise ConversionCancelled("用户取消了转换")
        key, separator, value = line.strip().partition("=")
        current: float | None = None
        if separator and key in {"out_time_us", "out_time_ms"}:
            try:
                current = min(1.0, max(0.0, int(value) / 1_000_000 / duration))
            except (ValueError, ZeroDivisionError):
                current = None
        elif separator and key == "progress" and value == "end":
            current = 1.0
        if current is not None and current > last_progress:
            last_progress = current
            if progress:
                progress(current)
    returncode = process.wait()
    if returncode != 0:
        detail = "\n".join(output_tail).strip()[-2000:] or f"FFmpeg 退出代码 {returncode}"
        raise TranscodeError(f"视频处理失败：{detail}")
