# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


QUALITY_LEVELS = frozenset({"fast", "balanced", "high"})


@dataclass(frozen=True, slots=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    rotation: int = 0

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    input_path: Path
    output_dir: Path
    start_time: float = 0.0
    duration: float = 3.0
    cover_time: float = 1.5
    mute: bool = False
    quality: str = "balanced"

    def validate(self, source_duration: float) -> None:
        if self.start_time < 0:
            raise ValueError("开始时间不能小于 0 秒")
        if not 1.0 <= self.duration <= 5.0:
            raise ValueError("片段时长必须在 1 到 5 秒之间")
        if source_duration <= 0:
            raise ValueError("视频时长无效")
        if self.start_time + self.duration > source_duration + 1e-6:
            raise ValueError("所选片段超出视频时长")
        if not self.start_time <= self.cover_time <= self.start_time + self.duration:
            raise ValueError("封面时刻必须位于所选片段内")
        if self.quality not in QUALITY_LEVELS:
            raise ValueError("画质档位无效")


@dataclass(frozen=True, slots=True)
class OutputBundle:
    directory: Path
    apple_photo: Path
    apple_video: Path
    android_photo: Path
    vivo_photo: Path
    vivo_video: Path
    windows_photo: Path
    windows_video: Path
    manifest: Path
    instructions: Path | None = None

    @property
    def files(self) -> tuple[Path, ...]:
        paths = (
            self.apple_photo,
            self.apple_video,
            self.android_photo,
            self.vivo_photo,
            self.vivo_video,
            self.windows_photo,
            self.windows_video,
            self.manifest,
        )
        return paths + ((self.instructions,) if self.instructions else ())
