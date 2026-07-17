# 兼容性与传输说明

## 为什么需要多套文件

Apple Live Photo、Android Motion Photo、vivo/iQOO OriginOS 动态照片和 Windows 普通媒体没有统一容器。本程序为同一片段生成多套文件，并提供 MP4 作为通用回退。

## iPhone / iPad

使用同名 JPG 和 MOV：

1. 同时选择两个文件，不要只传其中一个。
2. 保持完全相同的主文件名。
3. 使用 iCloud 照片、PhotoSync 或支持 Live Photo 配对导入的工具。
4. 避免微信、QQ 等会压缩或拆分资源的软件。

MOV 包含 content identifier 与 still-image-time 元数据轨，JPEG MakerNote 中包含相同的资产标识。文件结构正确并不代表任意传输工具都能按配对资源导入。

## 标准 Android / Google Photos

使用以 MP.jpg 结尾的单文件：

1. 复制到手机内部存储的 DCIM/Camera。
2. 等待系统完成媒体扫描。
3. 使用 Google Photos 或明确支持 Motion Photo 的相册打开。

文件同时包含 Android Motion Photo 1.0 Camera XMP、GContainer 资源目录和旧版 MicroVideo 字段。部分厂商相册会忽略这些标准元数据，此时请播放 Windows MP4。

Android 官方格式说明：<https://developer.android.com/media/platform/motion-photo-format>

## vivo / iQOO OriginOS

使用同名 IMG_*.jpg 和 IMG_*.mp4：

1. 两个文件必须一起复制到 DCIM/Camera。
2. 不要改名，不要只复制其中一个。
3. 推荐使用 USB 文件传输。
4. 复制后重新打开 OriginOS 相册；必要时等待扫描或重启相册。
5. 打开照片并长按播放。

JPEG 和 MP4 中写入相同的 28 字符 vivo Live Photo ID。当前实现基于 iQOO Neo8 Pro 原生样本的私有尾部和 vivoMediaExtInfo UUID box；不同机型和 OriginOS 版本可能存在差异。

## Windows

- 使用“照片”打开 *_Windows封面.jpg。
- 使用“媒体播放器”或“照片”播放 *_Windows.mp4。

Windows 通常不会把 Apple 或 Android 专用格式统一显示成一项动态照片，因此普通 JPEG 和 MP4 是最可靠的回退。

## 常见问题

### 手机只显示静态图

确认使用了对应平台的文件组合，并检查是否完整复制到 DCIM/Camera。聊天软件中转后应重新使用原文件传输。

### iPhone 显示成两个项目

传输工具没有按 Live Photo 配对资源导入，或者主文件名/元数据被修改。请使用支持配对导入的工具重新导入 JPG 和 MOV。

### vivo/iQOO 显示两个项目

确认 JPG 与 MP4 主文件名完全一致，并使用 USB 一起复制。删除失败导入的旧文件后等待媒体扫描再试。

### 没有声音

确认转换时没有勾选“静音”，并确认源视频有音轨。系统长按播放时是否输出声音由相册决定；可播放 Windows MP4 检查音轨。

### 传输后文件是否完整

manifest.json 记录每个文件的大小和 SHA-256。开发者可以运行 scripts/verify_bundle.py 做结构校验。
