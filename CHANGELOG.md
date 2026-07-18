# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构。

## 0.3.0 - 2026-07-18

### 新增

- 可按需选择 iPhone/iPad、标准 Android、vivo/iQOO 和 Windows 输出目标。
- 支持为同一视频添加多个片段，每个片段生成一套独立 Live 图成品。
- 开始、时长和封面时间改为 `MM:SS.cc` / `HH:MM:SS.cc` 六十进制显示。
- CLI、manifest 与成品校验器支持选择性设备输出。

### 改进

- 片段列表明确显示每段开始、结束和封面时刻。
- 完成弹窗采用紧凑布局，并改善 Windows 深色主题下的文字对比度。
- 改善片段列表和设备复选框在普通、悬停与选中状态下的可读性。
- 更新 README 界面截图、兼容性说明、架构文档和初学者教程。

## 0.2.0 - 2026-07-18

### 新增

- vivo/iQOO OriginOS 同名 JPG+MP4 动态照片配对。
- 基于 iQOO Neo8 Pro 原生样本的 vivo JPEG 尾部和 MP4 UUID 元数据。
- 标准 Android 与 vivo/iQOO 两套 Android 输出同时保留。
- 独立 bundle 校验中的 vivo 配对检查。

### 改进

- 更新平台传输说明和 Windows 发布包。
- 增加 Apache-2.0、NOTICE、GitHub 文档与 CI。

## 0.1.1 - 2026-07-18

### 修复

- 修复选择视频后界面一直停留在“正在读取视频信息”的后台 worker 生命周期问题。

## 0.1.0 - 2026-07-18

### 新增

- PySide6 中文桌面界面和 CLI。
- Apple Live Photo、Android Motion Photo 1.0 与 Windows JPEG/MP4 输出。
- 本地 FFmpeg 转码、输出清单、SHA-256 和独立验证脚本。
