# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

from .iso_bmff import atom, parse_atoms


USER_TYPE = b"vivoMediaExtInfo"
VIVO_PREFIX = b"vivo"
ALBUM_MARKER = b"cameralbum!"
TRAILER_MAGIC = bytes.fromhex("1b2a39485766758493a2b3")
LIVE_PHOTO_KEY = "com.android.camera.livephoto"
MODULE_KEY = "com.android.camera.moduleid"
MODEL_KEY = "com.android.camera.takenmodel"
IMAGE_TIME_KEY = "com.android.camera.imageTime"
_LIVE_PHOTO_ID = re.compile(r"[0-9a-f]{28}")
DEFAULT_MODEL = "iQOO Neo8 Pro"
DEFAULT_VERSION = 2014


@dataclass(frozen=True, slots=True)
class VivoMetadata:
    live_photo_id: str
    model: str
    module_id: str
    version: int
    image_time: int | None = None


@dataclass(frozen=True, slots=True)
class VivoPairInfo:
    image: VivoMetadata
    video: VivoMetadata

    @property
    def live_photo_id(self) -> str:
        return self.image.live_photo_id


def _validate_live_photo_id(identifier: str) -> str:
    if _LIVE_PHOTO_ID.fullmatch(identifier) is None:
        raise ValueError("vivo Live Photo ID 必须是 28 位小写十六进制字符")
    return identifier


def generate_live_photo_id(
    *,
    now_ms: int | None = None,
    random_hex: str | None = None,
) -> str:
    timestamp = int(time.time() * 1000) if now_ms is None else now_ms
    token = secrets.token_hex(4)[:7] if random_hex is None else random_hex.lower()
    if not 1_000_000_000_000 <= timestamp <= 9_999_999_999_999:
        raise ValueError("vivo Live Photo ID 时间戳必须是 13 位毫秒值")
    if re.fullmatch(r"[0-9a-f]{7}", token) is None:
        raise ValueError("vivo Live Photo ID 随机部分必须是 7 位十六进制字符")
    return f"{timestamp:013d}{token}00000000"


def cover_frame_index(cover_seconds: float, fps: float, duration: float) -> int:
    if cover_seconds < 0 or fps <= 0 or duration <= 0:
        raise ValueError("vivo 封面帧参数无效")
    last_frame = max(0, round(duration * fps) - 1)
    return min(round(cover_seconds * fps), last_frame)


def _build_payload(document: dict[str, object]) -> bytes:
    identifier = document.get(LIVE_PHOTO_KEY)
    if not isinstance(identifier, str):
        raise ValueError("vivo 私有元数据缺少配对 ID")
    identifier = _validate_live_photo_id(identifier)
    encoded_json = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    footer_length = 4 + len(identifier) + 4 + len(TRAILER_MAGIC)
    return (
        VIVO_PREFIX
        + encoded_json
        + len(encoded_json).to_bytes(4, "big")
        + ALBUM_MARKER
        + footer_length.to_bytes(4, "big")
        + identifier.encode("ascii")
        + b"\xff" * 4
        + TRAILER_MAGIC
    )


def _image_document(identifier: str, model: str) -> dict[str, object]:
    return {
        "com.android.camera.joint.fullview.orientation": 0,
        "com.android.camera.fisheye": -1,
        MODEL_KEY: model,
        "com.android.camera.watermarkVersion": None,
        "com.android.camera.camerafacing": "0",
        MODULE_KEY: "live_photo",
        LIVE_PHOTO_KEY: identifier,
        "version": DEFAULT_VERSION,
        "com.android.camera.joint.fullview": False,
    }


def _video_document(
    identifier: str,
    model: str,
    image_time: int,
) -> dict[str, object]:
    return {
        MODEL_KEY: model,
        "com.android.camera.camerafacing": "0",
        IMAGE_TIME_KEY: image_time,
        MODULE_KEY: "live_photo",
        LIVE_PHOTO_KEY: identifier,
        "version": DEFAULT_VERSION,
        "com.android.camera.faceInfo": {},
    }


def _parse_payload(payload: bytes, *, require_image_time: bool) -> VivoMetadata:
    if not payload.startswith(VIVO_PREFIX):
        raise ValueError("vivo 私有元数据缺少 vivo 前缀")

    marker_at = payload.find(ALBUM_MARKER, len(VIVO_PREFIX) + 4)
    json_length_at = marker_at - 4
    if marker_at < 0 or json_length_at < len(VIVO_PREFIX):
        raise ValueError("vivo 私有元数据缺少 cameralbum 标记")

    json_bytes = payload[len(VIVO_PREFIX) : json_length_at]
    declared_json_length = int.from_bytes(payload[json_length_at:marker_at], "big")
    if declared_json_length != len(json_bytes):
        raise ValueError("vivo 私有元数据 JSON 长度不一致")

    footer_length_at = marker_at + len(ALBUM_MARKER)
    if footer_length_at + 4 > len(payload):
        raise ValueError("vivo 私有元数据尾部长度缺失")
    footer_length = int.from_bytes(payload[footer_length_at : footer_length_at + 4], "big")
    footer_end = footer_length_at + footer_length
    if footer_end != len(payload):
        raise ValueError("vivo 私有元数据尾部长度不一致")

    identifier_at = footer_length_at + 4
    identifier_end = identifier_at + 28
    identifier_bytes = payload[identifier_at:identifier_end]
    suffix = payload[identifier_end:footer_end]
    if len(identifier_bytes) != 28 or suffix != b"\xff" * 4 + TRAILER_MAGIC:
        raise ValueError("vivo 私有元数据尾标无效")
    try:
        identifier = identifier_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("vivo Live Photo ID 不是 ASCII") from exc
    if _LIVE_PHOTO_ID.fullmatch(identifier) is None:
        raise ValueError("vivo Live Photo ID 格式无效")

    try:
        document = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("vivo 私有元数据 JSON 无效") from exc
    if not isinstance(document, dict):
        raise ValueError("vivo 私有元数据 JSON 必须是对象")
    if document.get(LIVE_PHOTO_KEY) != identifier:
        raise ValueError("vivo 私有元数据的配对 ID 不一致")

    image_time_value = document.get(IMAGE_TIME_KEY)
    if require_image_time and not isinstance(image_time_value, int):
        raise ValueError("vivo 视频元数据缺少 imageTime")
    if image_time_value is not None and (
        not isinstance(image_time_value, int) or image_time_value < 0
    ):
        raise ValueError("vivo 视频元数据 imageTime 无效")

    model = document.get(MODEL_KEY)
    module_id = document.get(MODULE_KEY)
    version = document.get("version")
    if not isinstance(model, str) or not model:
        raise ValueError("vivo 私有元数据缺少机型")
    if not isinstance(module_id, str) or module_id != "live_photo":
        raise ValueError("vivo 私有元数据模块不是 live_photo")
    if not isinstance(version, int) or version <= 0:
        raise ValueError("vivo 私有元数据版本无效")

    return VivoMetadata(identifier, model, module_id, version, image_time_value)


def inspect_vivo_jpeg(path: Path) -> VivoMetadata:
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("输入不是有效的 vivo JPEG")
    eoi_at = data.rfind(b"\xff\xd9")
    if eoi_at < 0:
        raise ValueError("vivo 动态照片 JPEG 缺少 EOI")
    return _parse_payload(data[eoi_at + 2 :], require_image_time=False)


def inspect_vivo_mp4(path: Path) -> VivoMetadata:
    data = path.read_bytes()
    matching = [
        item
        for item in parse_atoms(data)
        if item.type == b"uuid"
        and data[item.payload_start : item.payload_start + len(USER_TYPE)] == USER_TYPE
    ]
    if not matching:
        raise ValueError("MP4 缺少 vivoMediaExtInfo UUID box")
    box = matching[-1]
    payload = data[box.payload_start + len(USER_TYPE) : box.end]
    return _parse_payload(payload, require_image_time=True)


def verify_vivo_pair(jpeg_path: Path, mp4_path: Path) -> VivoPairInfo:
    if jpeg_path.stem != mp4_path.stem:
        raise ValueError("vivo 动态照片的 JPG 与 MP4 必须同名")
    if jpeg_path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("vivo 动态照片图片必须是 JPEG")
    if mp4_path.suffix.lower() != ".mp4":
        raise ValueError("vivo 动态照片视频必须是 MP4")
    image = inspect_vivo_jpeg(jpeg_path)
    video = inspect_vivo_mp4(mp4_path)
    if image.live_photo_id != video.live_photo_id:
        raise ValueError("vivo 动态照片 JPG 与 MP4 的配对 ID 不一致")
    if image.model != video.model:
        raise ValueError("vivo 动态照片 JPG 与 MP4 的机型信息不一致")
    return VivoPairInfo(image, video)


def write_vivo_live_photo(
    source_jpeg: Path,
    source_mp4: Path,
    output_jpeg: Path,
    output_mp4: Path,
    *,
    live_photo_id: str,
    image_time: int,
    model: str = DEFAULT_MODEL,
    captured_at: datetime | None = None,
) -> VivoPairInfo:
    identifier = _validate_live_photo_id(live_photo_id)
    if output_jpeg.stem != output_mp4.stem:
        raise ValueError("vivo 动态照片的 JPG 与 MP4 必须同名")
    if not isinstance(image_time, int) or image_time < 0:
        raise ValueError("vivo 视频元数据 imageTime 无效")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("vivo 动态照片机型不能为空")
    if not source_jpeg.is_file() or not source_mp4.is_file():
        raise ValueError("vivo 动态照片源文件不存在")

    taken_at = captured_at or datetime.now()
    date_text = taken_at.strftime("%Y:%m:%d %H:%M:%S")
    with Image.open(source_jpeg) as original:
        image = original.convert("RGB")
        exif = original.getexif()
        exif[0x010F] = "vivo"
        exif[0x0110] = model.strip()
        exif[0x0131] = "MediaTek Camera Application"
        exif[0x0132] = date_text
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        exif_ifd[0x9003] = date_text
        exif_ifd[0x9004] = date_text
        exif_ifd[0x9286] = "module: live_photo;"
        save_args: dict[str, object] = {
            "format": "JPEG",
            "quality": 95,
            "subsampling": 0,
            "exif": exif,
        }
        if original.info.get("icc_profile"):
            save_args["icc_profile"] = original.info["icc_profile"]
        image.save(output_jpeg, **save_args)

    output_jpeg.write_bytes(
        output_jpeg.read_bytes() + _build_payload(_image_document(identifier, model.strip()))
    )
    output_mp4.write_bytes(
        source_mp4.read_bytes()
        + atom(
            b"uuid",
            USER_TYPE + _build_payload(_video_document(identifier, model.strip(), image_time)),
        )
    )
    return verify_vivo_pair(output_jpeg, output_mp4)
