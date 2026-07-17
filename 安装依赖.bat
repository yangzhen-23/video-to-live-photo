@REM SPDX-License-Identifier: Apache-2.0
@REM Copyright 2026 杨振
@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 未找到 Python。请先从 https://www.python.org/downloads/ 安装 Python 3.10 或更高版本。
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo 正在创建独立运行环境……
    python -m venv .venv
    if errorlevel 1 goto :failed
)

echo 正在安装界面和视频处理组件，请保持网络连接……
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo 安装完成。现在可以双击“启动程序.bat”。
pause
exit /b 0

:failed
echo.
echo 安装失败。请检查网络和磁盘空间后重试。
pause
exit /b 1
