@REM SPDX-License-Identifier: Apache-2.0
@REM Copyright 2026 杨振
@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if exist "dist\视频转Live图\视频转Live图.exe" (
    start "" "dist\视频转Live图\视频转Live图.exe"
    exit /b 0
)

if not exist ".venv\Scripts\pythonw.exe" (
    echo 尚未安装运行环境，请先双击“安装依赖.bat”。
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m livephoto
exit /b 0
