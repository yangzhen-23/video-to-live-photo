# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import struct
from pathlib import Path

import pytest
from PIL import Image

from livephoto.core.apple import (
    apple_maker_note,
    inspect_live_jpeg,
    inspect_live_mov,
    write_live_jpeg,
    write_live_mov,
)
from livephoto.core.iso_bmff import parse_atoms, patch_chunk_offsets


ASSET_ID = "12345678-1234-1234-1234-123456789ABC"


def box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


def minimal_source_mov() -> tuple[bytes, bytes]:
    """Create a tiny MOV with mdat before moov and one video chunk."""
    ftyp = box(b"ftyp", b"qt  \x00\x00\x02\x00qt  ")
    video_sample = b"FAKE-H264-SAMPLE"
    mdat = box(b"mdat", video_sample)
    chunk_offset = len(ftyp) + 8

    mvhd_payload = (
        b"\x00\x00\x00\x00"
        + struct.pack(">IIII", 0, 0, 600, 1800)
        + b"\x00" * 72
        + struct.pack(">I", 2)
    )
    tkhd_payload = (
        b"\x00\x00\x00\x0f"
        + struct.pack(">IIIII", 0, 0, 1, 0, 1800)
        + b"\x00" * 60
    )
    hdlr_payload = b"\x00" * 8 + b"vide" + b"\x00" * 12 + b"Video\x00"
    stco = box(b"stco", b"\x00" * 4 + struct.pack(">II", 1, chunk_offset))
    stbl = box(b"stbl", stco)
    minf = box(b"minf", stbl)
    mdia = box(b"mdia", box(b"hdlr", hdlr_payload) + minf)
    trak = box(b"trak", box(b"tkhd", tkhd_payload) + mdia)
    moov = box(b"moov", box(b"mvhd", mvhd_payload) + trak)
    return ftyp + mdat + moov, video_sample


def test_apple_maker_note_contains_tag_17_ascii_uuid():
    note = apple_maker_note(ASSET_ID)
    assert note.startswith(b"Apple iOS\x00\x00\x01MM\x00\x01\x00\x11")
    assert note[18:20] == b"\x00\x02"
    assert int.from_bytes(note[20:24], "big") == 37
    assert int.from_bytes(note[24:28], "big") == 32
    assert note[32:] == ASSET_ID.encode("ascii") + b"\x00"


def test_write_live_jpeg_is_readable_and_reports_identifier(tmp_path: Path):
    source = tmp_path / "cover-source.jpg"
    Image.new("RGB", (40, 24), (240, 80, 40)).save(source, quality=90)
    output = tmp_path / "IMG_0001.jpg"

    write_live_jpeg(source, output, ASSET_ID)

    with Image.open(output) as image:
        image.load()
        assert image.size == (40, 24)
        assert image.getexif()[0x010F] == "Apple"
        assert image.getexif()[0x0110] == "Video to Live Photo"
    assert inspect_live_jpeg(output) == ASSET_ID


def test_write_live_mov_adds_identifier_and_timed_metadata(tmp_path: Path):
    source_bytes, video_sample = minimal_source_mov()
    source = tmp_path / "source.mov"
    source.write_bytes(source_bytes)
    output = tmp_path / "IMG_0001.mov"

    write_live_mov(source, output, ASSET_ID, still_time=1.25, duration=3.0)
    info = inspect_live_mov(output)

    assert info.asset_id == ASSET_ID
    assert info.still_time == pytest.approx(1.25, abs=1 / 600)
    assert info.video_track_id == 1
    assert info.metadata_track_id == 2
    assert info.sample_value == -1
    assert output.read_bytes()[info.video_chunk_offset :][: len(video_sample)] == video_sample
    assert output.read_bytes()[info.metadata_chunk_offset : info.metadata_chunk_offset + 9] == (
        b"\x00\x00\x00\x09\x00\x00\x00\x01\xff"
    )


def test_mov_writer_relayouts_faststart_source_and_patches_video_offset(tmp_path: Path):
    source_bytes, video_sample = minimal_source_mov()
    atoms = parse_atoms(source_bytes)
    ftyp, mdat, moov = atoms
    moved_moov = patch_chunk_offsets(moov.raw(source_bytes), moov.size)
    faststart = ftyp.raw(source_bytes) + moved_moov + mdat.raw(source_bytes)
    source = tmp_path / "faststart.mov"
    source.write_bytes(faststart)
    output = tmp_path / "live.mov"

    write_live_mov(source, output, ASSET_ID, still_time=0.5, duration=3.0)
    info = inspect_live_mov(output)

    assert output.read_bytes()[info.video_chunk_offset :][: len(video_sample)] == video_sample
    assert info.still_time == pytest.approx(0.5, abs=1 / 600)


def test_mov_writer_rejects_missing_video_track(tmp_path: Path):
    mvhd_payload = (
        b"\x00\x00\x00\x00"
        + struct.pack(">IIII", 0, 0, 600, 1800)
        + b"\x00" * 72
        + struct.pack(">I", 1)
    )
    source = tmp_path / "invalid.mov"
    source.write_bytes(
        box(b"ftyp", b"qt  \x00\x00\x00\x00")
        + box(b"mdat", b"x")
        + box(b"moov", box(b"mvhd", mvhd_payload))
    )
    with pytest.raises(ValueError, match="视频轨"):
        write_live_mov(source, tmp_path / "out.mov", ASSET_ID, 1.0, 3.0)
