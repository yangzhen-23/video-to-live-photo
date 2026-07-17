# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from pathlib import Path


project_root = Path(SPECPATH)
ffmpeg_binary = project_root / "build_tools" / "ffmpeg.exe"
if not ffmpeg_binary.is_file():
    raise FileNotFoundError("请先运行 build_windows.ps1，让脚本准备 FFmpeg")

pyside_root = project_root / ".venv" / "Lib" / "site-packages" / "PySide6"
plugin_groups = ("platforms", "styles", "imageformats", "iconengines")
qt_plugin_binaries = [
    (str(plugin), f"PySide6/plugins/{group}")
    for group in plugin_groups
    for plugin in (pyside_root / "plugins" / group).glob("*.dll")
]
if not any(Path(source).name == "qwindows.dll" for source, _target in qt_plugin_binaries):
    raise FileNotFoundError("PySide6 的 Windows 平台插件 qwindows.dll 不存在")

a = Analysis(
    [str(project_root / "run_gui.py")],
    pathex=[str(project_root)],
    binaries=[(str(ffmpeg_binary), "tools"), *qt_plugin_binaries],
    datas=[],
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "numpy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="视频转Live图",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="视频转Live图",
)
