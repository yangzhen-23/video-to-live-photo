# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from .android import create_motion_photo, inspect_motion_photo
from .apple import inspect_live_jpeg, inspect_live_mov, write_live_jpeg, write_live_mov
from .models import ConversionOptions, OutputBundle, VideoInfo
from .naming import safe_stem, unique_bundle_dir, vivo_pair_stem
from .probe import probe_video
from .tools import Toolchain
from .transcode import (
    ConversionCancelled,
    build_cover_command,
    build_transcode_command,
    run_ffmpeg,
)
from .vivo import (
    cover_frame_index,
    generate_live_photo_id,
    verify_vivo_pair,
    write_vivo_live_photo,
)


ProgressCallback = Callable[[int, str], None]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_paths(root: Path, stem: str, vivo_stem: str) -> OutputBundle:
    return OutputBundle(
        directory=root,
        apple_photo=root / f"{stem}.jpg",
        apple_video=root / f"{stem}.mov",
        android_photo=root / f"{stem}MP.jpg",
        vivo_photo=root / f"{vivo_stem}.jpg",
        vivo_video=root / f"{vivo_stem}.mp4",
        windows_photo=root / f"{stem}_Windows封面.jpg",
        windows_video=root / f"{stem}_Windows.mp4",
        manifest=root / "manifest.json",
        instructions=root / "使用说明.txt",
    )


def _verify_outputs(
    photo: Path,
    movie: Path,
    motion: Path,
    vivo_photo: Path,
    vivo_video: Path,
    asset_id: str,
    vivo_id: str,
) -> None:
    jpeg_id = inspect_live_jpeg(photo)
    mov_info = inspect_live_mov(movie)
    if jpeg_id != asset_id or mov_info.asset_id != asset_id:
        raise ValueError("iPhone 配对文件的资产标识不一致")
    if mov_info.sample_value != -1:
        raise ValueError("iPhone MOV 的封面定时样本无效")
    inspect_motion_photo(motion)
    vivo_info = verify_vivo_pair(vivo_photo, vivo_video)
    if vivo_info.live_photo_id != vivo_id:
        raise ValueError("vivo/iQOO 配对文件的资产标识不一致")


def _instructions(stem: str, vivo_stem: str) -> str:
    return f"""{stem} 动态照片兼容包
============================

iPhone / iPad
-------------
同时传输 `{stem}.jpg` 和 `{stem}.mov`，两者必须保持相同主文件名。
推荐通过 iCloud 照片、PhotoSync 或电脑端照片导入工具一次选择这两个文件。
若某个聊天软件只发送了其中一个文件，Live 效果会丢失，请重新传输完整配对。

标准 Android / Google Photos
---------------------------
传输 `{stem}MP.jpg` 到手机的 DCIM/Camera 目录，再用支持 Motion Photo 的系统相册或 Google Photos 打开。
这是单文件 Motion Photo，不要与下面的 vivo/iQOO 双文件混用。

vivo/iQOO OriginOS
------------------
同时复制 `{vivo_stem}.jpg` 和 `{vivo_stem}.mp4` 到手机内部存储的 DCIM/Camera 目录。
这两个文件必须放在一起并保持完全相同的主文件名，不能只复制一个，也不要改名。
推荐使用 USB 文件传输；微信、QQ 等聊天软件可能改写图片或丢失配对信息。
复制完成后等待系统扫描，再重新打开 OriginOS 相册并长按照片播放；必要时重启相册。

若手机相册仍不支持，请直接播放 `{stem}_Windows.mp4`，内容和声音完全保留。

Windows
-------
用系统“照片”打开 `{stem}_Windows封面.jpg` 查看封面；双击 `{stem}_Windows.mp4` 播放动态内容。

隐私说明
--------
转换过程完全在本机完成，不上传视频。manifest.json 记录文件大小和 SHA-256，便于检查传输后文件是否完整。
"""


class Converter:
    def __init__(
        self,
        toolchain: Toolchain,
        *,
        probe_fn: Callable[[Path, Toolchain], VideoInfo] = probe_video,
        ffmpeg_fn: Callable[..., None] = run_ffmpeg,
        apple_jpeg_fn: Callable[..., None] = write_live_jpeg,
        apple_mov_fn: Callable[..., None] = write_live_mov,
        motion_fn: Callable[..., None] = create_motion_photo,
        vivo_fn: Callable[..., object] = write_vivo_live_photo,
        verify_fn: Callable[..., None] = _verify_outputs,
    ) -> None:
        self.toolchain = toolchain
        self.probe_fn = probe_fn
        self.ffmpeg_fn = ffmpeg_fn
        self.apple_jpeg_fn = apple_jpeg_fn
        self.apple_mov_fn = apple_mov_fn
        self.motion_fn = motion_fn
        self.vivo_fn = vivo_fn
        self.verify_fn = verify_fn

    def convert(
        self,
        options: ConversionOptions,
        progress: ProgressCallback | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> OutputBundle:
        last_value = -1

        def report(value: float, text: str) -> None:
            nonlocal last_value
            integer = max(last_value, min(100, max(0, round(value))))
            if integer != last_value or text:
                last_value = integer
                if progress:
                    progress(integer, text)

        def check_cancel() -> None:
            if cancel and cancel():
                raise ConversionCancelled("用户取消了转换")

        report(0, "探测视频")
        info = self.probe_fn(options.input_path, self.toolchain)
        options.validate(info.duration)
        check_cancel()

        options.output_dir.mkdir(parents=True, exist_ok=True)
        stem = safe_stem(options.input_path.stem)
        final_dir = unique_bundle_dir(options.output_dir, stem)
        temp_dir = Path(tempfile.mkdtemp(prefix=".livephoto-", dir=options.output_dir))
        vivo_stem = vivo_pair_stem()
        paths = _bundle_paths(temp_dir, stem, vivo_stem)
        apple_source = temp_dir / ".apple-source.mov"
        asset_id = str(uuid.uuid4()).upper()
        vivo_id = generate_live_photo_id()

        try:
            report(5, "生成 Windows 兼容视频")
            self.ffmpeg_fn(
                build_transcode_command(options, info, self.toolchain, paths.windows_video),
                options.duration,
                progress=lambda fraction: report(5 + fraction * 30, "生成 Windows 兼容视频"),
                cancel=cancel,
            )
            check_cancel()

            report(35, "生成 iPhone 视频")
            self.ffmpeg_fn(
                build_transcode_command(options, info, self.toolchain, apple_source),
                options.duration,
                progress=lambda fraction: report(35 + fraction * 25, "生成 iPhone 视频"),
                cancel=cancel,
            )
            check_cancel()

            report(60, "提取封面")
            self.ffmpeg_fn(
                build_cover_command(options, self.toolchain, paths.windows_photo),
                1.0,
                progress=lambda fraction: report(60 + fraction * 10, "提取封面"),
                cancel=cancel,
            )
            check_cancel()

            report(70, "封装 iPhone Live Photo")
            self.apple_jpeg_fn(paths.windows_photo, paths.apple_photo, asset_id)
            relative_cover = options.cover_time - options.start_time
            self.apple_mov_fn(
                apple_source,
                paths.apple_video,
                asset_id,
                relative_cover,
                options.duration,
            )
            apple_source.unlink(missing_ok=True)
            check_cancel()

            report(82, "封装 Android Motion Photo")
            self.motion_fn(
                paths.windows_photo,
                paths.windows_video,
                paths.android_photo,
                round(relative_cover * 1_000_000),
            )
            check_cancel()

            report(88, "封装 vivo/iQOO OriginOS 动态照片")
            self.vivo_fn(
                paths.windows_photo,
                paths.windows_video,
                paths.vivo_photo,
                paths.vivo_video,
                live_photo_id=vivo_id,
                image_time=cover_frame_index(relative_cover, 30.0, options.duration),
            )
            check_cancel()

            report(93, "校验输出文件")
            self.verify_fn(
                paths.apple_photo,
                paths.apple_video,
                paths.android_photo,
                paths.vivo_photo,
                paths.vivo_video,
                asset_id,
                vivo_id,
            )
            paths.instructions.write_text(_instructions(stem, vivo_stem), encoding="utf-8")

            roles = [
                ("iphone_photo", paths.apple_photo),
                ("iphone_video", paths.apple_video),
                ("android_motion_photo", paths.android_photo),
                ("vivo_live_photo_image", paths.vivo_photo),
                ("vivo_live_photo_video", paths.vivo_video),
                ("windows_photo", paths.windows_photo),
                ("windows_video", paths.windows_video),
                ("instructions", paths.instructions),
            ]
            manifest = {
                "schema_version": 2,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_name": options.input_path.name,
                "asset_id": asset_id,
                "vivo_live_photo_id": vivo_id,
                "options": {
                    "start_time": options.start_time,
                    "duration": options.duration,
                    "cover_time": options.cover_time,
                    "mute": options.mute,
                    "quality": options.quality,
                },
                "video": {
                    "duration": info.duration,
                    "width": info.width,
                    "height": info.height,
                    "fps": info.fps,
                    "has_audio": info.has_audio,
                },
                "files": [
                    {
                        "role": role,
                        "name": path.name,
                        "size": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                    for role, path in roles
                ],
            }
            paths.manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            check_cancel()

            if final_dir.exists():
                final_dir = unique_bundle_dir(options.output_dir, stem)
            os.replace(temp_dir, final_dir)
            report(100, "转换完成")
            return _bundle_paths(final_dir, stem, vivo_stem)
        except BaseException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
