# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


QUALITY_LEVELS = frozenset({"fast", "balanced", "high"})
TARGET_ORDER = ("iphone", "android", "vivo", "windows")
OUTPUT_TARGETS = frozenset(TARGET_ORDER)


def _validate_clip(
    start_time: float,
    duration: float,
    cover_time: float,
    source_duration: float,
) -> None:
    if start_time < 0:
        raise ValueError("开始时间不能小于 0 秒")
    if not 1.0 <= duration <= 5.0:
        raise ValueError("片段时长必须在 1 到 5 秒之间")
    if source_duration <= 0:
        raise ValueError("视频时长无效")
    if start_time + duration > source_duration + 1e-6:
        raise ValueError("所选片段超出视频时长")
    if not start_time <= cover_time <= start_time + duration:
        raise ValueError("封面时刻必须位于所选片段内")


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
class ClipSegment:
    start_time: float = 0.0
    duration: float = 3.0
    cover_time: float = 1.5

    def validate(self, source_duration: float) -> None:
        _validate_clip(
            self.start_time,
            self.duration,
            self.cover_time,
            source_duration,
        )


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    input_path: Path
    output_dir: Path
    start_time: float = 0.0
    duration: float = 3.0
    cover_time: float = 1.5
    mute: bool = False
    quality: str = "balanced"
    targets: frozenset[str] = OUTPUT_TARGETS
    segment_label: str = ""

    def validate(self, source_duration: float) -> None:
        _validate_clip(
            self.start_time,
            self.duration,
            self.cover_time,
            source_duration,
        )
        if self.quality not in QUALITY_LEVELS:
            raise ValueError("画质档位无效")
        if not self.targets:
            raise ValueError("请至少选择一种兼容设备")
        if not self.targets <= OUTPUT_TARGETS:
            raise ValueError("输出目标无效")


@dataclass(frozen=True, slots=True)
class OutputFile:
    role: str
    path: Path


@dataclass(frozen=True, slots=True)
class OutputBundle:
    directory: Path
    outputs: tuple[OutputFile, ...]
    manifest: Path
    instructions: Path

    def by_role(self, role: str) -> Path | None:
        return next((item.path for item in self.outputs if item.role == role), None)

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(item.path for item in self.outputs) + (
            self.manifest,
            self.instructions,
        )
