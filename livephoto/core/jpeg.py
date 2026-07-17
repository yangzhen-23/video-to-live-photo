# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations


JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"
APP1 = b"\xff\xe1"
XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"


def _segments(jpeg: bytes):
    if not jpeg.startswith(JPEG_SOI):
        raise ValueError("输入不是有效的 JPEG 文件")
    position = 2
    while position + 1 < len(jpeg):
        if jpeg[position] != 0xFF:
            raise ValueError("JPEG 标记结构无效")
        while position < len(jpeg) and jpeg[position] == 0xFF:
            position += 1
        if position >= len(jpeg):
            break
        marker = jpeg[position]
        marker_start = position - 1
        if marker in (0xD9, 0xDA):
            break
        if marker == 0x00 or 0xD0 <= marker <= 0xD8:
            position += 1
            continue
        if position + 2 >= len(jpeg):
            raise ValueError("JPEG 分段长度缺失")
        length = int.from_bytes(jpeg[position + 1 : position + 3], "big")
        if length < 2:
            raise ValueError("JPEG 分段长度无效")
        segment_end = position + 1 + length
        if segment_end > len(jpeg):
            raise ValueError("JPEG 分段超出文件边界")
        payload_start = position + 3
        yield marker, marker_start, segment_end, payload_start
        position = segment_end


def extract_standard_xmp(jpeg: bytes) -> bytes:
    for marker, _start, end, payload_start in _segments(jpeg):
        payload = jpeg[payload_start:end]
        if marker == 0xE1 and payload.startswith(XMP_HEADER):
            return payload[len(XMP_HEADER) :]
    raise ValueError("JPEG 中没有标准 XMP 元数据")


def insert_xmp(jpeg: bytes, packet: bytes) -> bytes:
    """Insert or replace a standard XMP APP1 segment without re-encoding JPEG."""
    if not jpeg.startswith(JPEG_SOI):
        raise ValueError("输入不是有效的 JPEG 文件")
    payload = XMP_HEADER + packet
    if len(payload) > 65_533:
        raise ValueError("XMP 数据过大，无法放入 JPEG APP1 分段")
    segment = APP1 + (len(payload) + 2).to_bytes(2, "big") + payload

    insertion = 2
    for marker, start, end, payload_start in _segments(jpeg):
        old_payload = jpeg[payload_start:end]
        if marker == 0xE1 and old_payload.startswith(XMP_HEADER):
            return jpeg[:start] + segment + jpeg[end:]
        if marker in (0xE0, 0xE1):
            insertion = end
    return jpeg[:insertion] + segment + jpeg[insertion:]
