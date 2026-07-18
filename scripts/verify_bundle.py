# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from livephoto.core.android import inspect_motion_photo
from livephoto.core.apple import inspect_live_jpeg, inspect_live_mov
from livephoto.core.probe import probe_video
from livephoto.core.tools import Toolchain, run_capture
from livephoto.core.vivo import verify_vivo_pair


TARGET_ROLES = {
    "iphone": {"iphone_photo", "iphone_video"},
    "android": {"android_motion_photo"},
    "vivo": {"vivo_live_photo_image", "vivo_live_photo_video"},
    "windows": {"windows_photo", "windows_video"},
}


def required_roles(targets: list[str]) -> set[str]:
    unknown = set(targets) - set(TARGET_ROLES)
    if unknown:
        raise ValueError(f"manifest 包含未知目标：{', '.join(sorted(unknown))}")
    roles = {"instructions"}
    for target in targets:
        roles.update(TARGET_ROLES[target])
    return roles


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_bundle(directory: Path) -> dict[str, object]:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    targets = manifest.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("manifest 未记录有效的输出目标")
    records = {item["role"]: item for item in manifest["files"]}
    expected_roles = required_roles(targets)
    if set(records) != expected_roles:
        raise ValueError("manifest 文件角色与所选目标不一致")
    for record in records.values():
        path = directory / record["name"]
        data = path.read_bytes()
        if len(data) != record["size"] or sha256_bytes(data) != record["sha256"]:
            raise ValueError(f"哈希或大小不匹配：{path.name}")

    jpeg_id = None
    mov_info = None
    motion_info = None
    vivo_info = None
    embedded = None
    if "iphone" in targets:
        apple_photo = directory / records["iphone_photo"]["name"]
        apple_video = directory / records["iphone_video"]["name"]
        jpeg_id = inspect_live_jpeg(apple_photo)
        mov_info = inspect_live_mov(apple_video)
        if not (jpeg_id == mov_info.asset_id == manifest.get("asset_id")):
            raise ValueError("Apple 配对 UUID 不一致")
    if "android" in targets:
        motion_path = directory / records["android_motion_photo"]["name"]
        motion_info = inspect_motion_photo(motion_path)
        motion_data = motion_path.read_bytes()
        embedded = motion_data[motion_info.video_offset :]
    if "vivo" in targets:
        vivo_photo = directory / records["vivo_live_photo_image"]["name"]
        vivo_video = directory / records["vivo_live_photo_video"]["name"]
        vivo_info = verify_vivo_pair(vivo_photo, vivo_video)
        if vivo_info.live_photo_id != manifest.get("vivo_live_photo_id"):
            raise ValueError("vivo 配对 ID 与 manifest 不一致")
    if "windows" in targets:
        windows_photo = directory / records["windows_photo"]["name"]
        windows_video = directory / records["windows_video"]["name"]
        if embedded is not None and sha256_bytes(embedded) != sha256_bytes(
            windows_video.read_bytes()
        ):
            raise ValueError("Android 内嵌视频与 Windows MP4 不一致")
        if vivo_info is not None and not vivo_video.read_bytes().startswith(
            windows_video.read_bytes()
        ):
            raise ValueError("vivo MP4 的媒体内容与 Windows MP4 不一致")

    image_roles = {
        "iphone_photo",
        "android_motion_photo",
        "vivo_live_photo_image",
        "windows_photo",
    }
    for role in image_roles.intersection(records):
        path = directory / records[role]["name"]
        with Image.open(path) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                raise ValueError(f"图片尺寸无效：{path.name}")

    tools = Toolchain.discover()
    video_paths = [
        directory / records[role]["name"]
        for role in ("iphone_video", "vivo_live_photo_video", "windows_video")
        if role in records
    ]
    temporary_video = None
    temporary_directory = None
    if not video_paths and embedded is not None:
        temporary_directory = tempfile.TemporaryDirectory()
        temporary_video = Path(temporary_directory.name) / "embedded.mp4"
        temporary_video.write_bytes(embedded)
        video_paths.append(temporary_video)
    video_infos = []
    try:
        for path in video_paths:
            video_info = probe_video(path, tools)
            video_infos.append(video_info)
            codec_banner = run_capture(
                [tools.ffmpeg, "-hide_banner", "-i", path], timeout=30
            ).stderr
            if "Video: h264" not in codec_banner:
                raise ValueError(f"输出视频不是预期的 H.264：{path.name}")
            if not manifest.get("options", {}).get("mute") and "Audio: aac" not in codec_banner:
                raise ValueError(f"输出视频不是预期的 AAC 音频：{path.name}")
            if not 1.0 <= video_info.duration <= 5.1:
                raise ValueError(f"输出视频时长不在 Live Photo 范围：{path.name}")
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()

    result: dict[str, object] = {
        "targets": targets,
        "verified_files": len(records) + 1,
    }
    if jpeg_id is not None and mov_info is not None:
        result["asset_id"] = jpeg_id
        result["apple_still_time"] = mov_info.still_time
    if motion_info is not None:
        result["android_video_length"] = motion_info.video_length
    if vivo_info is not None:
        result["vivo_live_photo_id"] = vivo_info.live_photo_id
        result["vivo_image_time"] = vivo_info.video.image_time
    if video_infos:
        first = video_infos[0]
        result["video"] = {
            "duration": first.duration,
            "width": first.width,
            "height": first.height,
            "fps": first.fps,
            "has_audio": first.has_audio,
            "codecs": "H.264/AAC" if first.has_audio else "H.264",
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="独立校验动态照片兼容包")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_bundle(args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
