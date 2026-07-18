# 项目架构

## 设计目标

项目把“视频处理”和“动态照片格式封装”分开：FFmpeg 只负责生成通用 JPEG、H.264/AAC MP4 和 MOV，Python 负责写入 Apple、Android 与 vivo/iQOO 所需的配对元数据。

UI 和 CLI 共用同一套核心流水线，避免出现“界面版与命令行版行为不一致”。

## 数据流

~~~mermaid
flowchart LR
    UI["PySide6 UI / CLI"] --> Targets["所选设备 + 一个或多个片段"]
    Targets --> Batch["BatchConversionWorker"]
    Batch --> Pipeline["每个片段调用一次 Converter"]
    Pipeline --> FFmpeg["FFmpeg transcode"]
    FFmpeg --> Apple["Apple Live Photo"]
    FFmpeg --> Android["Android Motion Photo"]
    FFmpeg --> Vivo["vivo/iQOO pair"]
    FFmpeg --> Windows["Windows JPEG + MP4"]
    Apple & Android & Vivo & Windows --> Manifest["manifest + SHA-256"]
~~~

## 目录职责

### livephoto/core

- models.py：转换目标、片段、视频信息和按角色组织的输出 bundle。
- tools.py：发现 FFmpeg/FFprobe，并适配源码和打包环境。
- probe.py：读取时长、尺寸、帧率、旋转和声音轨。
- transcode.py：生成 FFmpeg 命令并报告进度。
- pipeline.py：一次生成共用视频和封面，再按所选设备封装、校验、写清单并原子发布。
- apple.py：Apple JPEG MakerNote、MOV content identifier 和 still-image-time。
- android.py：Android Motion Photo 1.0 XMP 和尾部 MP4。
- vivo.py：vivo JPEG 私有尾部、MP4 vivoMediaExtInfo UUID box 和配对校验。
- jpeg.py、iso_bmff.py：底层 JPEG 分段与 ISO-BMFF atom 工具。

### livephoto/ui

- main_window.py：窗口布局、设备复选框、多片段列表、输入校验和用户交互。
- time_spinbox.py：在 `MM:SS.cc` 与内部浮点秒之间格式化和解析。
- worker.py：探测与 `BatchConversionWorker` 多片段后台任务，避免阻塞界面。
- theme.py：界面样式。

### scripts

- verify_bundle.py：独立读取成品，不依赖写入结果判断成功。
- make_sample_video.py：生成无隐私的 H.264/AAC 测试视频。
- capture_ui.py：生成 README 使用的初始界面截图。
- check_markdown_links.py：检查公开文档的相对链接。
- check_repository.py：检查大文件和私有样本是否误入公开树。

## 输出发布

Converter 为每个片段在保存目录建立唯一临时目录。共用 H.264/AAC MP4 和 JPEG 只生成一次，所选平台复用它们完成封装；未选择平台的封装函数不会运行。所有封装和校验完成后才使用原子目录替换发布最终成品；任一步失败都会清理当前临时目录，不留下半组配对文件。多片段批处理中，已经完整发布的前序片段会保留。

manifest.json 记录：

- 源文件名和转换参数；
- `schema_version: 3`、片段标签和目标设备列表；
- 实际需要的 Apple 与 vivo 配对 ID；
- 仅记录实际输出文件的角色、大小和 SHA-256；
- 原视频的基本流信息。

## 依赖边界

- PySide6 仅用于桌面 UI。
- Pillow 用于读取和写入 JPEG/EXIF。
- imageio-ffmpeg 提供可随应用携带的 FFmpeg。
- 核心封装器不依赖 UI，可直接被 CLI 和测试调用。

## 安全与隐私

转换不联网、不上传媒体。公开测试不包含真实手机照片或视频；厂商兼容结构使用运行时生成的微型脱敏夹具验证。个人样本只允许保存在被 Git 忽略的 private_samples 目录。
