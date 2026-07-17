# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv .venv
}

if (-not $SkipInstall) {
    & $venvPython -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}

$ffmpegFolder = Join-Path $projectRoot '.venv\Lib\site-packages\imageio_ffmpeg\binaries'
$ffmpegSource = (Get-ChildItem -LiteralPath $ffmpegFolder -File -Filter 'ffmpeg*.exe' | Select-Object -First 1).FullName
if (-not $ffmpegSource -or -not (Test-Path -LiteralPath $ffmpegSource)) {
    throw 'Could not locate the imageio-ffmpeg binary'
}

$toolDir = Join-Path $projectRoot 'build_tools'
New-Item -ItemType Directory -Path $toolDir -Force | Out-Null
Copy-Item -LiteralPath $ffmpegSource -Destination (Join-Path $toolDir 'ffmpeg.exe') -Force

& $venvPython -m PyInstaller --noconfirm --clean livephoto.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }

$distRoot = Join-Path $projectRoot 'dist'
$distDir = (Get-ChildItem -LiteralPath $distRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
if (-not $distDir) { throw 'PyInstaller output directory was not found' }
$distributionFiles = @(
    'README.md',
    'LICENSE',
    'NOTICE',
    'THIRD_PARTY_NOTICES.md'
)
foreach ($relativePath in $distributionFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $relativePath) -Destination $distDir -Force
}
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\COMPATIBILITY.md') -Destination $distDir -Force

Write-Host "Build complete: $distDir" -ForegroundColor Green
