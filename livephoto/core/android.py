# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .jpeg import extract_standard_xmp, insert_xmp


CAMERA_NS = "http://ns.google.com/photos/1.0/camera/"
CONTAINER_NS = "http://ns.google.com/photos/1.0/container/"
ITEM_NS = "http://ns.google.com/photos/1.0/container/item/"


@dataclass(frozen=True, slots=True)
class MotionPhotoInfo:
    motion_photo: bool
    version: int
    presentation_timestamp_us: int
    video_length: int
    video_offset: int


def build_motion_xmp(video_size: int, presentation_us: int) -> bytes:
    if video_size <= 0:
        raise ValueError("Motion Photo 视频不能为空")
    if presentation_us < -1:
        raise ValueError("封面时间戳无效")
    xml = f'''<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
      xmlns:Camera="{CAMERA_NS}"
      xmlns:GContainer="{CONTAINER_NS}"
      xmlns:GContainerItem="{ITEM_NS}"
      Camera:MotionPhoto="1"
      Camera:MotionPhotoVersion="1"
      Camera:MotionPhotoPresentationTimestampUs="{presentation_us}"
      Camera:MicroVideo="1"
      Camera:MicroVideoVersion="1"
      Camera:MicroVideoOffset="{video_size}"
      Camera:MicroVideoPresentationTimestampUs="{presentation_us}">
      <GContainer:Directory>
        <rdf:Seq>
          <rdf:li rdf:parseType="Resource">
            <GContainer:Item GContainerItem:Mime="image/jpeg" GContainerItem:Semantic="Primary" GContainerItem:Length="0" GContainerItem:Padding="0" />
          </rdf:li>
          <rdf:li rdf:parseType="Resource">
            <GContainer:Item GContainerItem:Mime="video/mp4" GContainerItem:Semantic="MotionPhoto" GContainerItem:Length="{video_size}" GContainerItem:Padding="0" />
          </rdf:li>
        </rdf:Seq>
      </GContainer:Directory>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>'''
    return xml.encode("utf-8")


def _valid_motion_name(path: Path) -> bool:
    return (
        path.suffix.lower() in {".jpg", ".jpeg"}
        and path.stem.upper().endswith("MP")
        and not re.search(r"[\\/]", path.name)
    )


def create_motion_photo(
    jpeg_path: Path,
    mp4_path: Path,
    output_path: Path,
    presentation_us: int,
) -> None:
    if not _valid_motion_name(output_path):
        raise ValueError("Android 动态照片文件名必须以 MP.jpg 结尾")
    video = mp4_path.read_bytes()
    packet = build_motion_xmp(len(video), presentation_us)
    still = insert_xmp(jpeg_path.read_bytes(), packet)
    output_path.write_bytes(still + video)


def inspect_motion_photo(path: Path) -> MotionPhotoInfo:
    data = path.read_bytes()
    packet = extract_standard_xmp(data)
    try:
        root = ET.fromstring(packet)
    except ET.ParseError as exc:
        raise ValueError("Motion Photo XMP XML 无效") from exc

    description = root.find(
        ".//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description"
    )
    if description is None:
        raise ValueError("Motion Photo XMP 缺少描述节点")
    motion_photo = int(description.attrib.get(f"{{{CAMERA_NS}}}MotionPhoto", "0"))
    version = int(description.attrib.get(f"{{{CAMERA_NS}}}MotionPhotoVersion", "0"))
    presentation = int(
        description.attrib.get(
            f"{{{CAMERA_NS}}}MotionPhotoPresentationTimestampUs", "-1"
        )
    )

    video_length = 0
    for item in root.findall(f".//{{{CONTAINER_NS}}}Item"):
        if item.attrib.get(f"{{{ITEM_NS}}}Semantic") == "MotionPhoto":
            if item.attrib.get(f"{{{ITEM_NS}}}Mime") != "video/mp4":
                raise ValueError("Motion Photo 视频 MIME 类型无效")
            video_length = int(item.attrib.get(f"{{{ITEM_NS}}}Length", "0"))
            break
    if motion_photo != 1 or version != 1 or video_length <= 0:
        raise ValueError("文件没有完整的 Motion Photo 1.0 元数据")
    if video_length > len(data):
        raise ValueError("Motion Photo 声明的视频长度超出文件边界")
    video_offset = len(data) - video_length
    if video_offset + 8 > len(data) or data[video_offset + 4 : video_offset + 8] != b"ftyp":
        raise ValueError("Motion Photo 末尾不是有效的 MP4 视频")
    return MotionPhotoInfo(
        motion_photo=True,
        version=version,
        presentation_timestamp_us=presentation,
        video_length=video_length,
        video_offset=video_offset,
    )
