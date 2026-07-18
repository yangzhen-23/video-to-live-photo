# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import json
from pathlib import Path

from livephoto.cli import build_parser, main
from livephoto.core.models import OUTPUT_TARGETS, OutputBundle, OutputFile


def test_cli_parser_exposes_beginner_options():
    args = build_parser().parse_args(
        [
            "convert",
            "input.mp4",
            "--output",
            "out",
            "--start",
            "1",
            "--duration",
            "2",
            "--cover",
            "2",
            "--mute",
            "--quality",
            "high",
            "--target",
            "vivo",
            "--target",
            "windows",
        ]
    )
    assert args.command == "convert"
    assert (args.start, args.duration, args.cover, args.mute, args.quality) == (
        1.0,
        2.0,
        2.0,
        True,
        "high",
    )
    assert args.target == ["vivo", "windows"]


def test_cli_json_success_uses_middle_cover_by_default(monkeypatch, tmp_path: Path, capsys):
    captured = {}
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    photo = result_dir / "a.jpg"
    photo.write_bytes(b"x")
    bundle = OutputBundle(
        result_dir,
        (OutputFile("windows_photo", photo),),
        result_dir / "manifest.json",
        result_dir / "使用说明.txt",
    )

    class FakeConverter:
        def __init__(self, _tools):
            pass

        def convert(self, options, progress=None):
            captured["options"] = options
            return bundle

    monkeypatch.setattr("livephoto.cli.Toolchain.discover", lambda: object())
    monkeypatch.setattr("livephoto.cli.Converter", FakeConverter)
    code = main(
        [
            "convert",
            str(tmp_path / "input.mp4"),
            "--output",
            str(tmp_path),
            "--start",
            "1",
            "--duration",
            "2",
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert captured["options"].cover_time == 2.0
    assert captured["options"].targets == OUTPUT_TARGETS
    assert output["output_directory"] == str(result_dir)


def test_cli_passes_only_explicit_targets(monkeypatch, tmp_path: Path):
    captured = {}
    bundle = OutputBundle(
        tmp_path,
        (),
        tmp_path / "manifest.json",
        tmp_path / "使用说明.txt",
    )

    class FakeConverter:
        def __init__(self, _tools):
            pass

        def convert(self, options, progress=None):
            captured["options"] = options
            return bundle

    monkeypatch.setattr("livephoto.cli.Toolchain.discover", lambda: object())
    monkeypatch.setattr("livephoto.cli.Converter", FakeConverter)

    code = main(
        [
            "convert",
            str(tmp_path / "input.mp4"),
            "--output",
            str(tmp_path),
            "--target",
            "vivo",
            "--target",
            "windows",
            "--json",
        ]
    )

    assert code == 0
    assert captured["options"].targets == frozenset({"vivo", "windows"})
