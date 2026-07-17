# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path

import pytest
from PIL import Image

from livephoto.core.android import (
    build_motion_xmp,
    create_motion_photo,
    inspect_motion_photo,
)
from livephoto.core.jpeg import extract_standard_xmp, insert_xmp


def make_jpeg(path: Path) -> bytes:
    image = Image.new("RGB", (32, 18), (30, 120, 210))
    exif = Image.Exif()
    exif[0x010F] = "LivePhoto Test"
    image.save(path, "JPEG", quality=92, exif=exif)
    return path.read_bytes()


def fake_mp4() -> bytes:
    return (
        b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
        b"\x00\x00\x00\x0cmdatDATA"
    )


def test_insert_xmp_keeps_jpeg_readable_and_exif(tmp_path: Path):
    still = tmp_path / "still.jpg"
    original = make_jpeg(still)
    packet = build_motion_xmp(video_size=36, presentation_us=1_500_000)
    merged = insert_xmp(original, packet)
    output = tmp_path / "merged.jpg"
    output.write_bytes(merged)

    assert extract_standard_xmp(merged) == packet
    with Image.open(output) as image:
        image.load()
        assert image.size == (32, 18)
        assert image.getexif()[0x010F] == "LivePhoto Test"


def test_create_motion_photo_appends_exact_video_and_metadata(tmp_path: Path):
    still = tmp_path / "cover.jpg"
    make_jpeg(still)
    video = tmp_path / "clip.mp4"
    video.write_bytes(fake_mp4())
    output = tmp_path / "HolidayMP.jpg"

    create_motion_photo(still, video, output, presentation_us=1_500_000)
    info = inspect_motion_photo(output)

    assert info.motion_photo is True
    assert info.version == 1
    assert info.video_length == video.stat().st_size
    assert info.video_offset == output.stat().st_size - video.stat().st_size
    assert info.presentation_timestamp_us == 1_500_000
    assert output.read_bytes()[-video.stat().st_size :] == video.read_bytes()
    xmp = extract_standard_xmp(output.read_bytes())
    assert b'GContainerItem:Semantic="Primary"' in xmp
    assert b'GContainerItem:Semantic="MotionPhoto"' in xmp
    assert f'Camera:MicroVideoOffset="{video.stat().st_size}"'.encode() in xmp


def test_motion_photo_filename_must_follow_android_pattern(tmp_path: Path):
    still = tmp_path / "cover.jpg"
    make_jpeg(still)
    video = tmp_path / "clip.mp4"
    video.write_bytes(fake_mp4())
    with pytest.raises(ValueError, match="MP.jpg"):
        create_motion_photo(still, video, tmp_path / "wrong.jpg", 0)


def test_inspector_rejects_declared_video_that_is_not_mp4(tmp_path: Path):
    still = tmp_path / "badMP.jpg"
    make_jpeg(still)
    jpeg = insert_xmp(still.read_bytes(), build_motion_xmp(8, 0))
    still.write_bytes(jpeg + b"NOT_MP4!")
    with pytest.raises(ValueError, match="MP4"):
        inspect_motion_photo(still)


def test_insert_xmp_rejects_non_jpeg_and_oversized_packet():
    with pytest.raises(ValueError, match="JPEG"):
        insert_xmp(b"not an image", b"x")
    with pytest.raises(ValueError, match="过大"):
        insert_xmp(b"\xff\xd8\xff\xd9", b"x" * 70_000)
