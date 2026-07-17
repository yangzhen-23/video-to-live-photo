# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

from livephoto.core.models import ConversionOptions, VideoInfo
from livephoto.core.probe import parse_ffmpeg_banner, parse_ffprobe_json, probe_video
from livephoto.core.tools import Toolchain
from livephoto.core.transcode import (
    ConversionCancelled,
    TranscodeError,
    build_cover_command,
    build_transcode_command,
    run_ffmpeg,
)


def options(**changes) -> ConversionOptions:
    values = dict(
        input_path=Path("D:/中文 路径/输入.mov"),
        output_dir=Path("D:/输出"),
        start_time=2.25,
        duration=3.0,
        cover_time=3.75,
        mute=False,
        quality="balanced",
    )
    values.update(changes)
    return ConversionOptions(**values)


def tools() -> Toolchain:
    return Toolchain(Path("D:/tools/ffmpeg.exe"), Path("D:/tools/ffprobe.exe"))


def test_parse_ffprobe_json_normalizes_rotation_and_audio():
    payload = json.dumps(
        {
            "format": {"duration": "6.250"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                    "side_data_list": [{"rotation": 90}],
                },
                {"codec_type": "audio", "codec_name": "aac"},
            ],
        }
    )
    info = parse_ffprobe_json(payload)
    assert info.duration == pytest.approx(6.25)
    assert (info.width, info.height, info.rotation) == (1080, 1920, 90)
    assert info.fps == pytest.approx(29.97, rel=1e-3)
    assert info.has_audio is True


def test_parse_ffmpeg_banner_fallback():
    banner = """
Duration: 00:00:05.12, start: 0.000000, bitrate: 1200 kb/s
Stream #0:0: Video: h264, yuv420p, 1280x720, 25 fps, 25 tbr
Stream #0:1: Audio: aac, 44100 Hz, stereo
"""
    info = parse_ffmpeg_banner(banner)
    assert info.duration == pytest.approx(5.12)
    assert (info.width, info.height, info.fps, info.has_audio) == (1280, 720, 25.0, True)


def test_probe_video_uses_ffprobe_json(monkeypatch, tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    payload = json.dumps(
        {
            "format": {"duration": "3.0"},
            "streams": [
                {"codec_type": "video", "width": 640, "height": 360, "avg_frame_rate": "24/1"}
            ],
        }
    )
    monkeypatch.setattr(
        "livephoto.core.probe.run_capture",
        lambda _args: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )
    info = probe_video(source, tools())
    assert (info.duration, info.width, info.height) == (3.0, 640, 360)


def test_build_transcode_command_is_safe_and_compatible():
    info = VideoInfo(8.0, 1920, 1080, 29.97, True)
    command = build_transcode_command(options(), info, tools(), Path("D:/输出/片段.mp4"))
    assert command[0] == "D:\\tools\\ffmpeg.exe"
    assert command[command.index("-ss") + 1] == "2.250000"
    assert command[command.index("-t") + 1] == "3.000000"
    assert "libx264" in command
    assert "yuv420p" in command
    assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in command
    assert "aac" in command
    assert "-progress" in command
    assert str(options().input_path) in command


def test_muted_transcode_omits_audio_and_high_quality_changes_crf():
    info = VideoInfo(8.0, 1920, 1080, 30.0, True)
    command = build_transcode_command(
        options(mute=True, quality="high"), info, tools(), Path("clip.mov")
    )
    assert "-an" in command
    assert command[command.index("-crf") + 1] == "18"
    assert command[command.index("-f") + 1] == "mov"


def test_cover_command_uses_absolute_cover_time_and_one_frame():
    command = build_cover_command(options(), tools(), Path("cover.jpg"))
    assert command[command.index("-ss") + 1] == "3.750000"
    assert command[command.index("-frames:v") + 1] == "1"
    assert command[-1] == "cover.jpg"


class FakeProcess:
    def __init__(self, lines, returncode=0, error=""):
        self.stdout = iter(lines)
        self.stderr = type("Stderr", (), {"read": lambda _self: error})()
        self.returncode = returncode
        self.terminated = False

    def wait(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


def test_run_ffmpeg_reports_monotonic_progress(monkeypatch):
    fake = FakeProcess(["out_time_us=500000\n", "out_time_us=1500000\n", "progress=end\n"])
    captured = {}

    def popen(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return fake

    monkeypatch.setattr("livephoto.core.transcode.subprocess.Popen", popen)
    values = []
    run_ffmpeg(["ffmpeg", "-i", "in", "out"], 2.0, values.append)
    assert values == [0.25, 0.75, 1.0]
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["stderr"] is subprocess.STDOUT


def test_run_ffmpeg_raises_readable_error(monkeypatch):
    fake = FakeProcess(["encoder exploded\n"], returncode=1)
    monkeypatch.setattr("livephoto.core.transcode.subprocess.Popen", lambda *_a, **_k: fake)
    with pytest.raises(TranscodeError, match="encoder exploded"):
        run_ffmpeg(["ffmpeg"], 2.0)


def test_run_ffmpeg_can_cancel(monkeypatch):
    fake = FakeProcess(["out_time_us=1000\n"])
    monkeypatch.setattr("livephoto.core.transcode.subprocess.Popen", lambda *_a, **_k: fake)
    with pytest.raises(ConversionCancelled):
        run_ffmpeg(["ffmpeg"], 2.0, cancel=lambda: True)
    assert fake.terminated is True
