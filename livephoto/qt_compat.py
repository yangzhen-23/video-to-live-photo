# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import os
from pathlib import Path


_PRELOADED: list[object] = []


def prepare_qt_runtime() -> None:
    """Prefer the Windows system ICU before Conda can inject an incompatible copy."""
    if os.name != "nt" or _PRELOADED:
        return
    import ctypes

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    icu = system_root / "System32" / "icuuc.dll"
    if icu.is_file():
        try:
            _PRELOADED.append(ctypes.WinDLL(str(icu)))
        except OSError:
            pass
