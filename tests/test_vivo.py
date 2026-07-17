# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
import json
from pathlib import Path

import pytest
from PIL import ExifTags, Image

from livephoto.core.iso_bmff import atom
from livephoto.core.vivo import (
    USER_TYPE,
    cover_frame_index,
    generate_live_photo_id,
    inspect_vivo_jpeg,
    inspect_vivo_mp4,
    verify_vivo_pair,
    write_vivo_live_photo,
)


NATIVE_ID = "1784234056107f83c52d00000000"
TRAILER_MAGIC = bytes.fromhex("1b2a39485766758493a2b3")


def make_sources(tmp_path: Path) -> tuple[Path, Path]:
    jpeg = tmp_path / "cover.jpg"
    Image.new("RGB", (32, 18), (30, 120, 210)).save(jpeg, "JPEG", quality=92)
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(
        b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2"
        b"\x00\x00\x00\x0cmdatDATA"
    )
    return jpeg, mp4


def _native_payload(document: dict[str, object]) -> bytes:
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    footer_size = 4 + len(NATIVE_ID) + 4 + len(TRAILER_MAGIC)
    return (
        b"vivo"
        + encoded
        + len(encoded).to_bytes(4, "big")
        + b"cameralbum!"
        + footer_size.to_bytes(4, "big")
        + NATIVE_ID.encode("ascii")
        + b"\xff" * 4
        + TRAILER_MAGIC
    )


def make_native_pair(tmp_path: Path) -> tuple[Path, Path]:
    jpeg, mp4 = make_sources(tmp_path)
    image_document: dict[str, object] = {
        "com.android.camera.takenmodel": "iQOO Neo8 Pro",
        "com.android.camera.camerafacing": "0",
        "com.android.camera.moduleid": "live_photo",
        "com.android.camera.livephoto": NATIVE_ID,
        "version": 2014,
    }
    video_document: dict[str, object] = {
        "com.android.camera.takenmodel": "iQOO Neo8 Pro",
        "com.android.camera.camerafacing": "0",
        "com.android.camera.imageTime": 43,
        "com.android.camera.moduleid": "live_photo",
        "com.android.camera.livephoto": NATIVE_ID,
        "version": 2014,
        "com.android.camera.faceInfo": {},
    }
    jpeg.write_bytes(jpeg.read_bytes() + _native_payload(image_document))
    mp4.write_bytes(
        mp4.read_bytes()
        + atom(b"uuid", USER_TYPE + _native_payload(video_document))
    )
    return jpeg, mp4


def test_reads_sanitized_iqoo_live_photo_pair(tmp_path: Path):
    jpeg_path, video_path = make_native_pair(tmp_path)
    jpeg = inspect_vivo_jpeg(jpeg_path)
    video = inspect_vivo_mp4(video_path)

    assert jpeg.live_photo_id == video.live_photo_id == NATIVE_ID
    assert jpeg.module_id == video.module_id == "live_photo"
    assert jpeg.model == video.model == "iQOO Neo8 Pro"
    assert jpeg.version == video.version == 2014
    assert jpeg.image_time is None
    assert video.image_time == 43


def test_generates_native_shaped_id_and_clamped_cover_frame():
    value = generate_live_photo_id(
        now_ms=1_784_234_056_107,
        random_hex="f83c52d",
    )

    assert value == "1784234056107f83c52d00000000"
    assert cover_frame_index(1.5, 30.0, 3.0) == 45
    assert cover_frame_index(3.0, 30.0, 3.0) == 89


def test_writes_readable_vivo_pair_with_matching_metadata(tmp_path: Path):
    source_jpeg, source_mp4 = make_sources(tmp_path)
    source_jpeg_bytes = source_jpeg.read_bytes()
    source_mp4_bytes = source_mp4.read_bytes()
    output_jpeg = tmp_path / "IMG_20260718_120000.jpg"
    output_mp4 = tmp_path / "IMG_20260718_120000.mp4"
    identifier = "1784234056107f83c52d00000000"

    pair = write_vivo_live_photo(
        source_jpeg,
        source_mp4,
        output_jpeg,
        output_mp4,
        live_photo_id=identifier,
        image_time=45,
    )

    assert pair.live_photo_id == identifier
    assert pair.image.live_photo_id == pair.video.live_photo_id == identifier
    assert pair.video.image_time == 45
    assert output_jpeg.stem == output_mp4.stem
    assert source_jpeg.read_bytes() == source_jpeg_bytes
    assert source_mp4.read_bytes() == source_mp4_bytes
    with Image.open(output_jpeg) as image:
        image.load()
        exif = image.getexif()
        assert exif[0x010F] == "vivo"
        assert exif[0x0110] == "iQOO Neo8 Pro"
        exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        assert "module: live_photo" in exif_ifd[0x9286]


def test_pair_verifier_rejects_different_stems(tmp_path: Path):
    source_jpeg, source_mp4 = make_sources(tmp_path)
    output_jpeg = tmp_path / "IMG_20260718_120000.jpg"
    output_mp4 = tmp_path / "IMG_20260718_120001.mp4"
    output_jpeg.write_bytes(source_jpeg.read_bytes())
    output_mp4.write_bytes(source_mp4.read_bytes())

    with pytest.raises(ValueError, match="同名"):
        verify_vivo_pair(output_jpeg, output_mp4)


@pytest.mark.parametrize(
    ("cover", "fps", "duration"),
    [(-0.1, 30.0, 3.0), (1.0, 0.0, 3.0), (1.0, 30.0, 0.0)],
)
def test_cover_frame_rejects_invalid_values(cover: float, fps: float, duration: float):
    with pytest.raises(ValueError, match="封面帧"):
        cover_frame_index(cover, fps, duration)
