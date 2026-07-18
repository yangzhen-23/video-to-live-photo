# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from livephoto.core.models import TARGET_ORDER, ConversionOptions, VideoInfo
from livephoto.core.pipeline import Converter
from livephoto.core.tools import Toolchain


def options(tmp_path: Path, **changes) -> ConversionOptions:
    source = tmp_path / "家庭 视频.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "输出"
    values = {
        "input_path": source,
        "output_dir": output,
        "start_time": 0.0,
        "duration": 3.0,
        "cover_time": 1.5,
    }
    values.update(changes)
    return ConversionOptions(**values)


def fake_dependencies(calls: list[str], fail_on_run: int | None = None):
    run_count = 0

    def probe(_path, _tools):
        calls.append("probe")
        return VideoInfo(6.0, 1280, 720, 30.0, True)

    def run(command, _duration, progress=None, cancel=None):
        nonlocal run_count
        run_count += 1
        calls.append(f"run:{Path(command[-1]).suffix}")
        if fail_on_run == run_count:
            raise RuntimeError("planned failure")
        target = Path(command[-1])
        if target.suffix.lower() in {".jpg", ".jpeg"}:
            Image.new("RGB", (32, 18), (20, 80, 160)).save(target)
        else:
            target.write_bytes(b"fake-video")
        if progress:
            progress(1.0)

    def apple_jpeg(source, output, _asset_id):
        calls.append("apple-jpeg")
        shutil.copy2(source, output)

    def apple_mov(source, output, _asset_id, _still, _duration):
        calls.append("apple-mov")
        shutil.copy2(source, output)

    def motion(still, video, output, _presentation):
        calls.append("android")
        output.write_bytes(still.read_bytes() + video.read_bytes())

    def vivo(still, video, output_jpeg, output_mp4, *, live_photo_id, image_time):
        calls.append(f"vivo:{image_time}")
        output_jpeg.write_bytes(still.read_bytes() + live_photo_id.encode("ascii"))
        output_mp4.write_bytes(video.read_bytes() + live_photo_id.encode("ascii"))

    def verify(paths, targets, _asset_id, _vivo_id):
        calls.append(f"verify:{','.join(sorted(targets))}")
        assert all(path.is_file() for path in paths.values())

    return dict(
        probe_fn=probe,
        ffmpeg_fn=run,
        apple_jpeg_fn=apple_jpeg,
        apple_mov_fn=apple_mov,
        motion_fn=motion,
        vivo_fn=vivo,
        verify_fn=verify,
    )


def test_converter_runs_stages_and_publishes_manifest(tmp_path: Path):
    calls: list[str] = []
    progress: list[tuple[int, str]] = []
    converter = Converter(
        Toolchain(Path("ffmpeg")), **fake_dependencies(calls)
    )

    bundle = converter.convert(options(tmp_path), progress=lambda value, text: progress.append((value, text)))

    assert bundle.directory.is_dir()
    apple_photo = bundle.by_role("iphone_photo")
    apple_video = bundle.by_role("iphone_video")
    android_photo = bundle.by_role("android_motion_photo")
    vivo_photo = bundle.by_role("vivo_live_photo_image")
    vivo_video = bundle.by_role("vivo_live_photo_video")
    assert apple_photo is not None and apple_video is not None
    assert apple_photo.stem == apple_video.stem
    assert android_photo is not None and android_photo.stem.endswith("MP")
    assert vivo_photo is not None and vivo_video is not None
    assert vivo_photo.stem == vivo_video.stem
    assert vivo_photo.stem.startswith("IMG_")
    assert bundle.instructions.is_file()
    instructions = bundle.instructions.read_text(encoding="utf-8")
    assert "vivo/iQOO OriginOS" in instructions
    assert vivo_photo.name in instructions
    assert "DCIM/Camera" in instructions
    assert calls == [
        "probe",
        "run:.mp4",
        "run:.jpg",
        "apple-jpeg",
        "apple-mov",
        "android",
        "vivo:45",
        "verify:android,iphone,vivo,windows",
    ]
    assert progress[0] == (0, "探测视频")
    assert progress[-1] == (100, "转换完成")
    assert [value for value, _text in progress] == sorted(value for value, _text in progress)

    manifest = json.loads(bundle.manifest.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["source_name"] == "家庭 视频.mp4"
    assert manifest["asset_id"]
    assert len(manifest["vivo_live_photo_id"]) == 28
    assert manifest["targets"] == list(TARGET_ORDER)
    assert {item["role"] for item in manifest["files"]} == {
        "iphone_photo",
        "iphone_video",
        "android_motion_photo",
        "vivo_live_photo_image",
        "vivo_live_photo_video",
        "windows_photo",
        "windows_video",
        "instructions",
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])


@pytest.mark.parametrize(
    ("targets", "expected_roles", "forbidden_calls"),
    [
        (
            frozenset({"iphone"}),
            {"iphone_photo", "iphone_video", "instructions"},
            {"android", "vivo:45"},
        ),
        (
            frozenset({"android"}),
            {"android_motion_photo", "instructions"},
            {"apple-jpeg", "apple-mov", "vivo:45"},
        ),
        (
            frozenset({"vivo"}),
            {"vivo_live_photo_image", "vivo_live_photo_video", "instructions"},
            {"apple-jpeg", "apple-mov", "android"},
        ),
        (
            frozenset({"windows"}),
            {"windows_photo", "windows_video", "instructions"},
            {"apple-jpeg", "apple-mov", "android", "vivo:45"},
        ),
    ],
)
def test_converter_generates_only_selected_targets(
    tmp_path: Path,
    targets: frozenset[str],
    expected_roles: set[str],
    forbidden_calls: set[str],
):
    calls: list[str] = []
    converter = Converter(Toolchain(Path("ffmpeg")), **fake_dependencies(calls))

    bundle = converter.convert(options(tmp_path, targets=targets))

    manifest = json.loads(bundle.manifest.read_text(encoding="utf-8"))
    assert {item["role"] for item in manifest["files"]} == expected_roles
    assert {item.role for item in bundle.outputs} == expected_roles - {"instructions"}
    assert not forbidden_calls.intersection(calls)
    assert calls.count("run:.mp4") == 1
    assert calls.count("run:.jpg") == 1
    assert manifest["schema_version"] == 3
    assert manifest["targets"] == [target for target in TARGET_ORDER if target in targets]
    assert not any(path.name.startswith(".common") for path in bundle.directory.iterdir())


def test_converter_instructions_and_directory_follow_selection(tmp_path: Path):
    calls: list[str] = []
    converter = Converter(Toolchain(Path("ffmpeg")), **fake_dependencies(calls))

    bundle = converter.convert(
        options(
            tmp_path,
            targets=frozenset({"vivo"}),
            segment_label="片段02",
        )
    )

    instructions = bundle.instructions.read_text(encoding="utf-8")
    assert "片段02" in bundle.directory.name
    assert "vivo/iQOO OriginOS" in instructions
    assert "iPhone / iPad" not in instructions
    assert "标准 Android / Google Photos" not in instructions
    assert "Windows\n-------" not in instructions


def test_converter_failure_removes_temporary_directory_and_publishes_nothing(tmp_path: Path):
    calls: list[str] = []
    conversion = options(tmp_path)
    converter = Converter(
        Toolchain(Path("ffmpeg")), **fake_dependencies(calls, fail_on_run=2)
    )

    with pytest.raises(RuntimeError, match="planned failure"):
        converter.convert(conversion)

    assert conversion.output_dir.is_dir()
    assert list(conversion.output_dir.iterdir()) == []


def test_converter_honors_cancellation_between_stages(tmp_path: Path):
    calls: list[str] = []
    converter = Converter(
        Toolchain(Path("ffmpeg")), **fake_dependencies(calls)
    )
    with pytest.raises(RuntimeError, match="取消"):
        converter.convert(options(tmp_path), cancel=lambda: len(calls) >= 2)
