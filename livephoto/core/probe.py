# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path

from .models import VideoInfo
from .tools import Toolchain, run_capture


def _rate(value: str | int | float | None) -> float:
    if value in (None, "", "0/0"):
        return 0.0
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return 0.0


def parse_ffprobe_json(payload: str) -> VideoInfo:
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("FFprobe 返回的 JSON 无效") from exc
    streams = document.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("文件中没有视频轨")
    try:
        duration = float(document.get("format", {}).get("duration") or video.get("duration"))
        width = int(video["width"])
        height = int(video["height"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("无法读取视频时长或分辨率") from exc
    rotation = 0
    tags = video.get("tags") or {}
    if "rotate" in tags:
        rotation = int(float(tags["rotate"]))
    for side_data in video.get("side_data_list") or []:
        if "rotation" in side_data:
            rotation = int(float(side_data["rotation"]))
    rotation %= 360
    if rotation in {90, 270}:
        width, height = height, width
    fps = _rate(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    has_audio = any(item.get("codec_type") == "audio" for item in streams)
    return VideoInfo(duration, width, height, fps, has_audio, rotation)


def parse_ffmpeg_banner(text: str) -> VideoInfo:
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    video_line = next((line for line in text.splitlines() if "Video:" in line), "")
    resolution = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", video_line)
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps\b", video_line)
    if duration_match is None or resolution is None:
        raise ValueError("无法从 FFmpeg 输出中读取视频信息")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    width, height = map(int, resolution.groups())
    rotation_match = re.search(r"rotation of\s+(-?\d+(?:\.\d+)?)", text)
    if rotation_match is None:
        rotation_match = re.search(r"rotate\s*:\s*(-?\d+)", text)
    rotation = int(float(rotation_match.group(1))) % 360 if rotation_match else 0
    if rotation in {90, 270}:
        width, height = height, width
    fps = float(fps_match.group(1)) if fps_match else 0.0
    return VideoInfo(duration, width, height, fps, "Audio:" in text, rotation)


def probe_video(path: Path, toolchain: Toolchain) -> VideoInfo:
    if not path.is_file():
        raise ValueError(f"找不到输入视频：{path}")
    diagnostics: list[str] = []
    if toolchain.ffprobe:
        result = run_capture(
            [
                toolchain.ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                path,
            ]
        )
        if result.returncode == 0:
            return parse_ffprobe_json(result.stdout)
        diagnostics.append(result.stderr.strip())
    result = run_capture([toolchain.ffmpeg, "-hide_banner", "-i", path])
    try:
        return parse_ffmpeg_banner(result.stderr + "\n" + result.stdout)
    except ValueError as exc:
        detail = "\n".join(item for item in diagnostics + [result.stderr.strip()] if item)
        if len(detail) > 1200:
            detail = detail[-1200:]
        raise ValueError(f"无法读取视频信息。{detail}") from exc
