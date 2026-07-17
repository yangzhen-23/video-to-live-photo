# 开发指南

## 环境要求

- Windows 10/11
- Python 3.10–3.12
- PowerShell
- 可用磁盘空间至少 1 GB（安装 PySide6 和构建发布包时）

## 安装

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
~~~

requirements-dev.txt 会同时安装运行依赖、pytest 和 PyInstaller。

## 运行

GUI：

~~~powershell
.\.venv\Scripts\python.exe -m livephoto
~~~

CLI：

~~~powershell
.\.venv\Scripts\python.exe -m livephoto convert "输入.mp4" --output "输出目录"
~~~

## 测试

~~~powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
~~~

测试使用 tmp_path 和微型脱敏媒体，不依赖仓库中的真实照片或视频。vivo/iQOO 结构夹具独立构建，避免写入器与解析器共享同一个错误。

## 文档与仓库检查

~~~powershell
.\.venv\Scripts\python.exe scripts\check_markdown_links.py
.\.venv\Scripts\python.exe scripts\check_repository.py
.\.venv\Scripts\python.exe scripts\capture_ui.py docs\assets\application.png
~~~

提交截图前请确认其中没有本地文件路径、个人视频名或其他隐私信息。

## 端到端验证

~~~powershell
.\.venv\Scripts\python.exe scripts\make_sample_video.py verification\sample.mp4 --duration 5
.\.venv\Scripts\python.exe -m livephoto convert verification\sample.mp4 --output verification\output
$bundle = Get-ChildItem verification\output -Directory |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
.\.venv\Scripts\python.exe scripts\verify_bundle.py $bundle.FullName
~~~

独立校验结果应包含 9 个已验证项目、Apple/vivo 配对信息和 H.264/AAC 视频信息。

## Windows 构建

~~~powershell
.\build_windows.ps1
~~~

脚本会：

1. 安装开发依赖（可用 -SkipInstall 跳过）。
2. 准备内置 FFmpeg。
3. 使用 PyInstaller 生成 dist/视频转Live图。
4. 复制 README、LICENSE、NOTICE、第三方声明和兼容性文档。

发布时必须压缩整个 dist/视频转Live图 目录，不能只发布 EXE。

## 发布检查

- 完整测试通过。
- verify_bundle.py 通过。
- 打包 GUI 能正常启动。
- ZIP 中包含 EXE、FFmpeg、Qt、LICENSE、NOTICE 和 THIRD_PARTY_NOTICES.md。
- release、dist、verification 和 private_samples 不进入 Git。
- 更新 CHANGELOG.md 后再创建 GitHub Release。
