# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_SEPARATORS = re.compile(r"[\s_]+")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_stem(text: str, max_length: int = 80) -> str:
    """Return a readable filename stem valid on Windows and mobile devices."""
    cleaned = _ILLEGAL.sub("_", text)
    cleaned = _SEPARATORS.sub("_", cleaned).strip(" ._")
    if not cleaned:
        return "未命名"
    if cleaned.upper() in _RESERVED:
        cleaned = f"_{cleaned}"
    cleaned = cleaned[:max_length].rstrip(" ._")
    return cleaned or "未命名"


def unique_bundle_dir(
    parent: Path, stem: str, now: datetime | None = None
) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_stem(stem)}_Live图_{stamp}"
    candidate = parent / base_name
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def vivo_pair_stem(now: datetime | None = None) -> str:
    """Return the filename pattern used by vivo/OriginOS camera live photos."""
    return (now or datetime.now()).strftime("IMG_%Y%m%d_%H%M%S")
