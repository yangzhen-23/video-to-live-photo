# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path

import pytest

import livephoto.core.models as models
from livephoto.core.models import ConversionOptions, OutputBundle, VideoInfo


def make_options(**changes):
    values = {
        "input_path": Path("输入.mp4"),
        "output_dir": Path("输出"),
        "start_time": 2.0,
        "duration": 3.0,
        "cover_time": 3.5,
        "mute": False,
        "quality": "balanced",
    }
    values.update(changes)
    return ConversionOptions(**values)


def test_options_accept_valid_clip():
    make_options().validate(8.0)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start_time": -0.1}, "开始时间"),
        ({"duration": 0.9}, "片段时长"),
        ({"duration": 5.1}, "片段时长"),
        ({"quality": "magic"}, "画质"),
        ({"cover_time": 1.9}, "封面时刻"),
        ({"cover_time": 5.1}, "封面时刻"),
    ],
)
def test_options_reject_invalid_values(changes, message):
    with pytest.raises(ValueError, match=message):
        make_options(**changes).validate(8.0)


def test_options_reject_clip_past_source_end():
    with pytest.raises(ValueError, match="超出视频时长"):
        make_options(start_time=4.0, duration=3.0, cover_time=5.0).validate(6.5)


def test_options_validate_selected_targets():
    make_options(targets=frozenset({"vivo", "windows"})).validate(8.0)

    with pytest.raises(ValueError, match="至少选择"):
        make_options(targets=frozenset()).validate(8.0)

    with pytest.raises(ValueError, match="输出目标"):
        make_options(targets=frozenset({"unknown"})).validate(8.0)


def test_clip_segment_reuses_time_validation():
    models.ClipSegment(2.0, 3.0, 3.5).validate(8.0)

    with pytest.raises(ValueError, match="超出视频时长"):
        models.ClipSegment(7.0, 2.0, 7.5).validate(8.0)


def test_data_models_keep_paths_and_stream_details():
    info = VideoInfo(duration=6.0, width=1920, height=1080, fps=30.0, has_audio=True)
    photo = Path("成品/IMG_20260718_120000.jpg")
    manifest = Path("成品/manifest.json")
    instructions = Path("成品/使用说明.txt")
    bundle = OutputBundle(
        directory=Path("成品"),
        outputs=(models.OutputFile("vivo_live_photo_image", photo),),
        manifest=manifest,
        instructions=instructions,
    )
    assert info.aspect_ratio == pytest.approx(16 / 9)
    assert bundle.by_role("vivo_live_photo_image") == photo
    assert bundle.by_role("iphone_photo") is None
    assert bundle.files == (photo, manifest, instructions)
    with pytest.raises(AttributeError):
        info.width = 1
