# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from livephoto.core.android import inspect_motion_photo
from livephoto.core.apple import inspect_live_jpeg, inspect_live_mov
from livephoto.core.probe import probe_video
from livephoto.core.tools import Toolchain, run_capture
from livephoto.core.vivo import verify_vivo_pair


REQUIRED_ROLES = {
    "iphone_photo",
    "iphone_video",
    "android_motion_photo",
    "vivo_live_photo_image",
    "vivo_live_photo_video",
    "windows_photo",
    "windows_video",
    "instructions",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_bundle(directory: Path) -> dict[str, object]:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = {item["role"]: item for item in manifest["files"]}
    if set(records) != REQUIRED_ROLES:
        raise ValueError("manifest 文件角色不完整")
    for record in records.values():
        path = directory / record["name"]
        data = path.read_bytes()
        if len(data) != record["size"] or sha256_bytes(data) != record["sha256"]:
            raise ValueError(f"哈希或大小不匹配：{path.name}")

    apple_photo = directory / records["iphone_photo"]["name"]
    apple_video = directory / records["iphone_video"]["name"]
    motion_path = directory / records["android_motion_photo"]["name"]
    vivo_photo = directory / records["vivo_live_photo_image"]["name"]
    vivo_video = directory / records["vivo_live_photo_video"]["name"]
    windows_photo = directory / records["windows_photo"]["name"]
    windows_video = directory / records["windows_video"]["name"]

    jpeg_id = inspect_live_jpeg(apple_photo)
    mov_info = inspect_live_mov(apple_video)
    if not (jpeg_id == mov_info.asset_id == manifest["asset_id"]):
        raise ValueError("Apple 配对 UUID 不一致")
    motion_info = inspect_motion_photo(motion_path)
    motion_data = motion_path.read_bytes()
    embedded = motion_data[motion_info.video_offset :]
    if sha256_bytes(embedded) != sha256_bytes(windows_video.read_bytes()):
        raise ValueError("Android 内嵌视频与 Windows MP4 不一致")
    vivo_info = verify_vivo_pair(vivo_photo, vivo_video)
    if vivo_info.live_photo_id != manifest.get("vivo_live_photo_id"):
        raise ValueError("vivo 配对 ID 与 manifest 不一致")
    if not vivo_video.read_bytes().startswith(windows_video.read_bytes()):
        raise ValueError("vivo MP4 的媒体内容与 Windows MP4 不一致")

    for path in (apple_photo, windows_photo, motion_path, vivo_photo):
        with Image.open(path) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                raise ValueError(f"图片尺寸无效：{path.name}")

    tools = Toolchain.discover()
    mp4_info = probe_video(windows_video, tools)
    mov_video_info = probe_video(apple_video, tools)
    codec_banner = run_capture(
        [tools.ffmpeg, "-hide_banner", "-i", windows_video], timeout=30
    ).stderr
    if "Video: h264" not in codec_banner or "Audio: aac" not in codec_banner:
        raise ValueError("Windows 输出不是预期的 H.264/AAC")
    if not (1.0 <= mp4_info.duration <= 5.1 and 1.0 <= mov_video_info.duration <= 5.1):
        raise ValueError("输出视频时长不在 Live Photo 范围")

    return {
        "asset_id": jpeg_id,
        "apple_still_time": mov_info.still_time,
        "android_video_length": motion_info.video_length,
        "vivo_live_photo_id": vivo_info.live_photo_id,
        "vivo_image_time": vivo_info.video.image_time,
        "video": {
            "duration": mp4_info.duration,
            "width": mp4_info.width,
            "height": mp4_info.height,
            "fps": mp4_info.fps,
            "has_audio": mp4_info.has_audio,
            "codecs": "H.264/AAC",
        },
        "verified_files": len(records) + 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="独立校验动态照片兼容包")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
