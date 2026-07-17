# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from livephoto.core.tools import Toolchain, run_capture


def make_sample(output: Path, duration: float = 5.0) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tools = Toolchain.discover()
    command = [
        tools.ffmpeg,
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(output),
    ]
    result = run_capture(command, timeout=max(60, duration * 10))
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])


def main() -> None:
    parser = argparse.ArgumentParser(description="生成端到端测试视频")
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()
    make_sample(args.output, args.duration)
    print(args.output)


if __name__ == "__main__":
    main()
