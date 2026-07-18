# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core.models import OUTPUT_TARGETS, TARGET_ORDER, ConversionOptions
from .core.pipeline import Converter
from .core.tools import Toolchain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="video-to-live-photo", description="视频转 Live 图兼容包")
    subparsers = parser.add_subparsers(dest="command", required=True)
    convert = subparsers.add_parser("convert", help="转换一个视频")
    convert.add_argument("input", type=Path, help="输入视频")
    convert.add_argument("--output", type=Path, required=True, help="输出目录")
    convert.add_argument("--start", type=float, default=0.0, help="片段开始秒数")
    convert.add_argument("--duration", type=float, default=3.0, help="片段时长，1 到 5 秒")
    convert.add_argument("--cover", type=float, help="封面在原视频中的秒数，默认片段中点")
    convert.add_argument("--mute", action="store_true", help="移除声音")
    convert.add_argument("--quality", choices=("fast", "balanced", "high"), default="balanced")
    convert.add_argument(
        "--target",
        action="append",
        choices=TARGET_ORDER,
        help="输出目标，可重复使用；默认生成全部",
    )
    convert.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "convert":
        return 2
    cover = args.cover if args.cover is not None else args.start + args.duration / 2
    options = ConversionOptions(
        input_path=args.input,
        output_dir=args.output,
        start_time=args.start,
        duration=args.duration,
        cover_time=cover,
        mute=args.mute,
        quality=args.quality,
        targets=frozenset(args.target) if args.target else OUTPUT_TARGETS,
    )
    try:
        converter = Converter(Toolchain.discover())
        callback = None
        if not args.json:
            callback = lambda value, text: print(f"[{value:3d}%] {text}", file=sys.stderr)
        bundle = converter.convert(options, progress=callback)
        result = {
            "output_directory": str(bundle.directory),
            "manifest": str(bundle.manifest),
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"完成：{bundle.directory}")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"转换失败：{exc}", file=sys.stderr)
        return 1
