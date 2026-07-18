# 视频转 Live 图：项目源码详解与 Git/GitHub 初学者教程

> 面向读者：只掌握少量 Python 基础，希望学会阅读真实项目、理解桌面程序结构，并能独立使用 Git 和 GitHub。
>
> 项目作者：杨振
>
> 项目仓库：[yangzhen-23/video-to-live-photo](https://github.com/yangzhen-23/video-to-live-photo)
>
> 文档对应版本：v0.2.0 之后的 main 分支

---

## 目录

1. [如何使用这份报告](#1-如何使用这份报告)
2. [项目到底解决了什么问题](#2-项目到底解决了什么问题)
3. [先掌握几个必要概念](#3-先掌握几个必要概念)
4. [项目目录总览](#4-项目目录总览)
5. [一次完整转换是怎样发生的](#5-一次完整转换是怎样发生的)
6. [Python 程序入口详解](#6-python-程序入口详解)
7. [数据模型与参数校验](#7-数据模型与参数校验)
8. [FFmpeg 工具发现与视频探测](#8-ffmpeg-工具发现与视频探测)
9. [视频转码与封面提取](#9-视频转码与封面提取)
10. [文件命名与输出目录安全](#10-文件命名与输出目录安全)
11. [Android Motion Photo 原理](#11-android-motion-photo-原理)
12. [Apple Live Photo 原理](#12-apple-live-photo-原理)
13. [vivo/iQOO 动态照片原理](#13-vivoiqoo-动态照片原理)
14. [转换流水线 Converter 详解](#14-转换流水线-converter-详解)
15. [PySide6 图形界面详解](#15-pyside6-图形界面详解)
16. [命令行界面 CLI 详解](#16-命令行界面-cli-详解)
17. [辅助脚本逐个说明](#17-辅助脚本逐个说明)
18. [测试代码逐个说明](#18-测试代码逐个说明)
19. [依赖、打包、CI 和仓库配置](#19-依赖打包ci-和仓库配置)
20. [文档、许可与发布文件](#20-文档许可与发布文件)
21. [从零理解 Git](#21-从零理解-git)
22. [Git 安装与首次配置](#22-git-安装与首次配置)
23. [Git 最重要的四个区域](#23-git-最重要的四个区域)
24. [日常最常用 Git 命令](#24-日常最常用-git-命令)
25. [查看历史、比较差异和定位问题](#25-查看历史比较差异和定位问题)
26. [分支、合并和冲突](#26-分支合并和冲突)
27. [远程仓库与 GitHub](#27-远程仓库与-github)
28. [撤销操作：restore、revert 和 reset](#28-撤销操作restorerevert-和-reset)
29. [标签与 GitHub Release](#29-标签与-github-release)
30. [本项目推荐的 Git 工作流](#30-本项目推荐的-git-工作流)
31. [常见错误与排查方法](#31-常见错误与排查方法)
32. [建议的学习路线和练习](#32-建议的学习路线和练习)
33. [术语速查表](#33-术语速查表)

---

## 1. 如何使用这份报告

不要试图一次记住所有内容。建议分四轮阅读：

第一轮只读第 2～5 章，先弄清程序的目的、输入、输出和总体流程。

第二轮读第 6～16 章，打开对应 Python 文件，一边看解释一边看源码。此时不需要完全理解 MOV、JPEG 的二进制结构，只要知道每个模块负责什么。

第三轮读第 17～20 章，理解测试、打包、CI 和开源仓库为什么也是“程序的一部分”。

第四轮学习第 21 章之后的 Git 教程，并直接在这个项目里练习。

阅读源码时建议遵循一个原则：

> 先找入口，再看数据怎样流动，最后才研究底层实现。

推荐阅读顺序：

1. [__main__.py](../livephoto/__main__.py)
2. [app.py](../livephoto/app.py) 或 [cli.py](../livephoto/cli.py)
3. [models.py](../livephoto/core/models.py)
4. [pipeline.py](../livephoto/core/pipeline.py)
5. pipeline 调用的各个具体格式模块

不要直接从最长的 apple.py 或 main_window.py 开始，否则很容易被细节淹没。

---

## 2. 项目到底解决了什么问题

这个程序接收一段普通视频，让用户选择：

- 从第几秒开始；
- 截取多长时间；
- 哪一帧作为封面；
- 添加多少个独立片段；
- 生成 iPhone、Android、vivo/iQOO、Windows 中的哪些目标；
- 是否保留声音；
- 使用快速、均衡还是高画质。

程序随后只生成用户选中的一类或多类结果，每个片段对应一个独立成品目录：

| 平台 | 结果 | 核心特点 |
|---|---|---|
| iPhone/iPad | 同名 JPEG + MOV | 两个文件使用同一个 Apple 资产 UUID 配对 |
| 标准 Android | 一个以 MP.jpg 结尾的 JPEG | JPEG 后面附加 MP4，并在 XMP 中声明视频长度 |
| vivo/iQOO | 同名 IMG_*.jpg + IMG_*.mp4 | 两个文件写入相同的 28 位配对 ID 和 vivo 私有元数据 |
| Windows | 普通 JPEG + H.264/AAC MP4 | 不依赖厂商私有协议，常见查看器都能使用 |

为什么不能只生成一个“万能 Live 图”？

因为 Live Photo、Motion Photo、OriginOS 动态照片并不是同一个公开标准。它们的容器、元数据和识别方式不同。项目采用的设计是：

> 先把媒体内容标准化，再为每个平台制作它能识别的包装。

这也是项目名称中“兼容包”的真正含义。

---

## 3. 先掌握几个必要概念

### 3.1 文件扩展名不等于文件格式

把 video.mp4 改名为 video.jpg，不会把视频变成图片。扩展名只是名字的一部分，真正的格式由文件内部字节结构决定。

本项目不是简单改名，而是：

- 用 FFmpeg 真正编码 H.264 视频和 AAC 音频；
- 用 Pillow 真正生成 JPEG；
- 按不同平台要求写入 EXIF、XMP、MOV Atom 或 MP4 UUID Box；
- 写完后重新解析，检查结果是否符合预期。

### 3.2 容器和编码

MP4、MOV 是“容器”，类似一个盒子。盒子里可以放 H.264 视频轨、AAC 音频轨、时间信息、封面时刻和厂商元数据。

H.264 和 AAC 是“编码格式”。可以把容器理解成 ZIP 文件，把编码理解成 ZIP 里的具体文件格式，但这只是帮助理解的类比。

### 3.3 元数据

元数据是“描述数据的数据”。例如：

- 视频时长；
- 图片拍摄时间；
- 相机型号；
- Apple 配对 UUID；
- vivo 动态照片 ID；
- Android 内嵌视频长度。

动态照片能否被系统相册识别，关键往往不是画面本身，而是元数据是否正确。

### 3.4 哈希

SHA-256 会把任意文件计算成固定长度的十六进制字符串。文件只要改变一个字节，哈希通常就会完全不同。

项目在 manifest.json 中记录每个结果文件的文件名、角色、字节大小和 SHA-256，用来判断传输软件有没有改写文件。

### 3.5 GUI 主线程

图形界面必须不断处理鼠标、键盘、重绘等事件。如果在 GUI 主线程里直接运行耗时的 FFmpeg，窗口就会“未响应”。

本项目使用 QThread，把视频探测和转换放到后台线程，再用 Signal 把进度传回主线程。

### 3.6 回调

回调是“把一个函数交给另一个函数，等适当时机再调用”。

Converter 接收 progress 回调，每完成一点工作就调用它。GUI 传入 Signal.emit，CLI 传入 print，因此核心代码不必知道自己运行在什么界面中。

---

## 4. 项目目录总览

~~~text
视频转live图/
├─ .github/workflows/ci.yml       GitHub Actions 自动测试
├─ docs/                          用户和开发文档
│  ├─ ARCHITECTURE.md             架构概览
│  ├─ COMPATIBILITY.md            平台传输和兼容说明
│  ├─ DEVELOPMENT.md              开发、测试和构建
│  ├─ PROJECT_CODE_AND_GIT_GUIDE.md 本学习报告
│  └─ assets/application.png      README 界面截图
├─ livephoto/                     正式 Python 包
│  ├─ core/                       与界面无关的转换核心
│  ├─ ui/                         PySide6 图形界面
│  ├─ __main__.py                 python -m livephoto 入口
│  ├─ app.py                      GUI 入口
│  ├─ cli.py                      命令行入口
│  └─ qt_compat.py                Qt 兼容处理
├─ scripts/                       开发和验证脚本
├─ tests/                         pytest 自动测试
├─ build_windows.ps1              Windows 打包总脚本
├─ livephoto.spec                 PyInstaller 打包规则
├─ pyproject.toml                 Python 项目元数据
├─ requirements.txt               运行依赖
├─ requirements-dev.txt           开发依赖
├─ run_gui.py                     打包使用的 GUI 入口
├─ 安装依赖.bat                   初学者安装脚本
├─ 启动程序.bat                   初学者启动脚本
├─ README.md                      GitHub 首页
├─ LICENSE                        Apache-2.0 许可
├─ NOTICE                         作者和出处声明
└─ THIRD_PARTY_NOTICES.md         第三方组件说明
~~~

目录按职责分层，而不是把所有代码堆在一个 app.py 中：

- core 不依赖按钮，便于测试和 CLI 复用；
- ui 只负责用户交互，不直接实现二进制协议；
- scripts 是维护工具；
- tests 用自动化方式证明行为；
- docs、许可、CI 和打包配置共同组成可发布项目。

---

## 5. 一次完整转换是怎样发生的

### 5.1 GUI 调用链

~~~mermaid
flowchart TD
    A["用户选择视频"] --> B["MainWindow.set_input_path"]
    B --> C["Toolchain.discover 寻找 FFmpeg"]
    C --> D["ProbeWorker 后台读取视频信息"]
    D --> E["probe_video 返回 VideoInfo"]
    E --> F["用户添加片段并选择目标设备"]
    F --> G["MainWindow.start_conversion"]
    G --> H["每个片段创建一个 ConversionOptions"]
    H --> I["BatchConversionWorker 依次调用 Converter.convert"]
    I --> J["每个片段只转码一次并提取一次封面"]
    J --> K["只运行所选平台的封装"]
    K --> L["反向解析校验"]
    L --> M["写 manifest 和使用说明"]
    M --> N["临时目录改名为最终目录"]
    N --> O["GUI 显示完成"]
~~~

### 5.2 为什么要先写临时目录

Converter 不直接往最终目录逐个写文件，而是创建 .livephoto-xxxx 临时目录。

如果中途出现 FFmpeg 失败、用户取消、元数据校验失败或磁盘空间不足，程序会删除临时目录，不把半成品伪装成成功结果。

全部阶段成功后，才用 os.replace 把临时目录改名为正式目录。这种思路叫“先完整准备，再原子发布”。

### 5.3 进度划分

| 进度范围 | 工作 |
|---|---|
| 0%～5% | 探测视频、校验参数 |
| 5%～35% | 生成 Windows MP4 |
| 35%～60% | 生成 Apple MOV 来源 |
| 60%～70% | 提取 JPEG 封面 |
| 70%～82% | Apple 封装 |
| 82%～88% | Android 封装 |
| 88%～93% | vivo/iQOO 封装 |
| 93%～100% | 校验、清单和发布目录 |

report 内部保证进度不会倒退。FFmpeg 的小数进度会映射到对应阶段的百分比区间。

---

## 6. Python 程序入口详解

### 6.1 livephoto/__init__.py

[查看文件](../livephoto/__init__.py)

它标志 livephoto 是 Python 包并定义版本号。其他代码才能使用 import livephoto。

### 6.2 livephoto/__main__.py

[查看文件](../livephoto/__main__.py)

执行 python -m livephoto 时，Python 会寻找 __main__.py。

- 第一个参数是 convert：进入 CLI；
- 否则：启动 GUI。

因此一个包可以同时提供图形界面和命令行。

### 6.3 livephoto/app.py

[查看文件](../livephoto/app.py)

步骤：

1. 调用 prepare_qt_runtime；
2. 创建或复用 QApplication；
3. 设置应用名称；
4. 创建 MainWindow；
5. 显示窗口；
6. 进入 app.exec 事件循环。

特殊参数 --smoke-test 会在 800 毫秒后自动退出，用于判断打包后的 EXE 能否启动。

### 6.4 run_gui.py

[查看文件](../run_gui.py)

这是很薄的适配入口，只导入 livephoto.app.main。PyInstaller 从它开始分析依赖，正式逻辑仍留在可测试的包中。

---

## 7. 数据模型与参数校验

文件：[models.py](../livephoto/core/models.py)

### 7.1 为什么使用 dataclass

dataclass 适合表达一组相关数据。相比普通字典，它字段明确、类型提示清楚、IDE 能补全，也不容易把 width 拼错。

项目使用 frozen=True，表示创建后不应修改；slots=True 减少属性开销并阻止随意增加拼错的属性。

### 7.2 VideoInfo

| 字段 | 含义 |
|---|---|
| duration | 视频总时长，秒 |
| width、height | 考虑旋转后的宽高 |
| fps | 每秒帧数 |
| has_audio | 是否存在音频轨 |
| rotation | 原视频旋转角度 |

aspect_ratio 使用 property，因此写 info.aspect_ratio，而不是调用函数。

### 7.3 ConversionOptions

保存 input_path、output_dir、start_time、duration、cover_time、mute、quality、targets 和 segment_label。targets 是非空设备集合；segment_label 用于多片段目录中的“片段01”等编号。

validate 是统一守门员：

- 开始不能小于 0；
- 时长必须 1～5 秒；
- 片段不能超出源视频；
- 封面必须在片段内；
- 画质档位必须有效；
- 至少选择一个目标，而且目标名称必须有效。

无论参数来自 GUI 还是 CLI，都执行同一套校验。

### 7.4 OutputBundle

`OutputFile` 使用 role 和 path 描述一个实际成品。`OutputBundle.outputs` 只保存本次真正生成的平台文件，`by_role()` 可以按角色查询，未生成的角色返回 None；files 属性再附加 manifest 和说明文件。

---

## 8. FFmpeg 工具发现与视频探测

### 8.1 tools.py

文件：[tools.py](../livephoto/core/tools.py)

Toolchain.discover 按优先级寻找 FFmpeg：

1. 环境变量 LIVEPHOTO_FFMPEG；
2. 程序旁 tools/ffmpeg.exe；
3. PyInstaller 解包目录；
4. 系统 PATH；
5. imageio-ffmpeg 自带二进制。

FFprobe 不是绝对必需；找不到时会退回解析 FFmpeg 文字输出。

run_capture 使用 shell=False，用户路径只会作为参数，不会被 Shell 当成命令执行。Windows 下 CREATE_NO_WINDOW 避免弹出黑框。

### 8.2 probe.py

文件：[probe.py](../livephoto/core/probe.py)

首选 FFprobe JSON：

~~~text
ffprobe JSON → json.loads → 寻找音视频轨 → 处理旋转和帧率 → VideoInfo
~~~

帧率常写成 30000/1001。_rate 使用 Fraction 正确解析。

如果 FFprobe 不可用，parse_ffmpeg_banner 用正则从 FFmpeg 文本提取 Duration、分辨率、fps、Audio 和 rotation。

这是“优先结构化数据，必要时兼容文本”的设计。

---

## 9. 视频转码与封面提取

文件：[transcode.py](../livephoto/core/transcode.py)

### 9.1 画质档位

| 档位 | preset | CRF | 特点 |
|---|---|---|---|
| fast | veryfast | 24 | 编码快 |
| balanced | medium | 20 | 默认推荐 |
| high | slow | 18 | 编码慢、画质高 |

CRF 通常越小，质量越高、文件越大。

### 9.2 build_transcode_command

函数只构造命令列表，便于测试参数而不真的运行 FFmpeg。

| 参数 | 作用 |
|---|---|
| -ss | 截取起点 |
| -t | 截取时长 |
| -map 0:v:0 | 第一条视频轨 |
| scale=trunc(iw/2)*2 | 保证宽高为偶数 |
| libx264 | H.264 编码 |
| yuv420p | 提高设备兼容性 |
| -r 30 | 统一 30 fps |
| rotate=0 | 清除旧旋转标记 |
| aac | 音频编码 |
| +faststart | 把 MP4 索引放前面 |
| -progress pipe:1 | 输出机器可读进度 |

### 9.3 build_cover_command

从 cover_time 指定时刻提取一帧，以 JPEG 质量参数 2 保存。

### 9.4 run_ffmpeg

Popen 启动 FFmpeg 后逐行读取 out_time_us，并用“已输出时间 ÷ 目标时长”计算进度。

取消时 terminate 进程并抛出 ConversionCancelled。退出码非 0 时保留最后一段日志并抛出 TranscodeError。

---

## 10. 文件命名与输出目录安全

文件：[naming.py](../livephoto/core/naming.py)

Windows 禁止某些字符，也禁止 CON、PRN、AUX、NUL 等保留名。

safe_stem 会替换非法字符、合并空白、清理末尾句点、处理保留名、限制长度，并在空名称时返回“未命名”。

unique_bundle_dir 生成：

~~~text
假期_Live图_20260718_120000
~~~

如果同名目录存在，就添加 _2、_3，避免覆盖。

vivo_pair_stem 生成 OriginOS 相机常见的 IMG_日期_时间 格式。

## 11. Android Motion Photo 原理

相关文件：

- [android.py](../livephoto/core/android.py)
- [jpeg.py](../livephoto/core/jpeg.py)

### 11.1 文件布局

标准 Motion Photo 可以理解为：

~~~text
[正常 JPEG 字节][正常 MP4 字节]
~~~

普通查看器从 JPEG 开头读取，遇到 JPEG 结束标记就停止，因此仍能把文件当静态图片。支持 Motion Photo 的相册还会读取 XMP，知道文件末尾附加了一段 MP4。

### 11.2 XMP 记录什么

build_motion_xmp 写入：

- MotionPhoto=1；
- MotionPhotoVersion=1；
- 封面展示时间；
- MP4 字节长度；
- Primary 项是 image/jpeg；
- MotionPhoto 项是 video/mp4。

解析器用“整个文件长度减去声明的视频长度”找到 MP4 开始位置，并检查该位置附近是否出现 ftyp。

### 11.3 jpeg.py

JPEG 由 Marker Segment 组成。_segments 从 SOI 开始遍历，检查每段长度和边界。

insert_xmp：

- 已有标准 XMP 时替换；
- 否则在 APP0/APP1 附近插入 APP1；
- 不重新编码 JPEG 画面；
- 检查 APP1 最大长度。

extract_standard_xmp 反向找出 XMP，供校验器使用。

### 11.4 文件名限制

项目要求 Android 单文件以 MP.jpg 结尾。这是常见相机命名习惯，也帮助用户区分标准 Android 单文件和 vivo 双文件。

---

## 12. Apple Live Photo 原理

相关文件：

- [apple.py](../livephoto/core/apple.py)
- [iso_bmff.py](../livephoto/core/iso_bmff.py)

这是项目中二进制结构最复杂的部分。

### 12.1 Apple 配对原则

完整 Live Photo 至少需要：

- JPEG 中存在 Apple MakerNote；
- MOV 中存在 content identifier；
- JPEG 和 MOV 的 UUID 完全一致；
- MOV 中存在 still-image-time 定时元数据轨。

只复制 JPG 或只复制 MOV 都不能形成完整配对。

### 12.2 JPEG 侧

write_live_jpeg：

1. 用 Pillow 打开封面；
2. 转成 RGB；
3. 复制原 EXIF；
4. 写入 Make、Model；
5. 在 MakerNote tag 0x927C 写 Apple 结构和 UUID；
6. 保留 ICC 色彩配置；
7. 高质量保存。

inspect_live_jpeg 会重新读取 MakerNote，检查 tag、长度和 UUID。

### 12.3 MOV Atom

MOV/MP4 属于 ISO Base Media File Format，由嵌套 Atom 组成：

~~~text
ftyp
mdat
moov
 ├─ mvhd
 ├─ trak  视频轨
 │   └─ mdia
 │       └─ minf
 │           └─ stbl
 └─ trak  元数据轨
~~~

一个普通 Atom 通常是：

~~~text
[4 字节长度][4 字节类型][内容]
~~~

Atom 数据类记录 start、size、type 和 header_size，并提供 end、payload_start 和 raw。

parse_atoms 处理普通 32 位长度、扩展 64 位长度以及“延伸到文件末尾”的 size=0，并严格检查越界。

### 12.4 为什么修正 chunk offset

stco/co64 表记录媒体数据在整个文件中的绝对位置。程序移动 mdat 或插入新数据后，原地址会改变。

patch_chunk_offsets 递归遍历 moov，把每个 stco/co64 条目加上 delta，同时检查负数、位宽溢出和 Atom 边界。

如果不修正，播放器会到错误位置读取视频，可能黑屏或提示文件损坏。

### 12.5 still-image-time 元数据轨

_timed_metadata_track 手工构造：

- tkhd：轨道头；
- edts/elst：封面时刻编辑列表；
- tref/cdsc：声明它描述视频轨；
- mdhd：媒体时间基；
- hdlr：处理类型 meta；
- stbl：样本表；
- sample 值 -1。

write_live_mov 流程：

1. 解析 ftyp、mdat、moov；
2. 找视频轨和时间基；
3. 把封面秒数换算为 tick；
4. 给 mdat 追加定时 sample；
5. 修正原媒体 offset；
6. 给 moov 增加 content identifier 和 metadata track；
7. 写出新 MOV。

inspect_live_mov 会重新检查 UUID、视频轨、元数据轨、sample 偏移、sample 值和封面时间。

---

## 13. vivo/iQOO 动态照片原理

文件：[vivo.py](../livephoto/core/vivo.py)

### 13.1 配对方式

OriginOS 使用同名文件：

~~~text
IMG_20260718_120000.jpg
IMG_20260718_120000.mp4
~~~

两个文件必须包含相同的 28 位 live_photo_id。

### 13.2 ID 构成

generate_live_photo_id 生成：

~~~text
[13 位毫秒时间戳][7 位随机十六进制][8 个 0]
~~~

使用 secrets.token_hex 避免轻易产生重复 ID。

### 13.3 JPEG 侧

write_vivo_live_photo 先用 Pillow 写入：

- Make=vivo；
- Model=iQOO Neo8 Pro；
- 拍摄时间；
- UserComment=module: live_photo。

随后在 JPEG EOI 结束标记之后追加 vivo 私有 payload。

### 13.4 MP4 侧

MP4 末尾追加 uuid Box，内部包含 vivoMediaExtInfo 和私有 payload。视频 payload 比图片多 imageTime，代表封面帧索引。

cover_frame_index 近似计算“相对封面秒数 × 30 fps”，并限制在最后一帧以内。

### 13.5 私有 payload

~~~text
vivo
JSON
JSON 长度
cameralbum!
尾部长度
28 位配对 ID
4 个 FF
固定 Trailer Magic
~~~

_parse_payload 会检查前缀、JSON 长度、尾部长度、固定魔数、ID、机型、模块、版本和 imageTime。

### 13.6 为什么测试不提交手机原图

原始照片可能含 GPS、时间、设备和个人画面。测试代码构造最小脱敏同形结构，既保留协议特征，又不公开私人样本。

---

## 14. 转换流水线 Converter 详解

文件：[pipeline.py](../livephoto/core/pipeline.py)

Converter 是总导演，负责协调模块而不是重复实现每个平台协议。

### 14.1 依赖注入

构造函数允许替换 probe_fn、ffmpeg_fn、apple_jpeg_fn、apple_mov_fn、motion_fn、vivo_fn 和 verify_fn。

正式运行使用真实函数，单元测试传 Fake 函数。这叫依赖注入，能让 pipeline 测试不必真的运行 FFmpeg。

### 14.2 convert 阶段

1. 探测输入并校验参数；
2. 创建输出父目录；
3. 清洗文件名；
4. 创建最终路径和临时目录；
5. 生成 Apple UUID 与 vivo ID；
6. 转码一个共用 H.264/AAC MP4；
7. 提取一个共用 JPEG；
8. 按 targets 选择性封装 Apple、Android、vivo 或复制 Windows 文件；
9. 只反向校验所选目标；
10. 删除共用临时文件；
11. 写只包含所选设备章节的使用说明；
12. 计算实际输出的哈希并写 manifest；
13. 原子发布目录；
14. 返回按角色组织的 OutputBundle。

### 14.3 异常安全

主体放在 try/except BaseException 中。只要没有成功发布，临时目录就会被删除，然后使用 raise 继续抛出原异常。

### 14.4 manifest

schema_version 当前为 3，新增 segment_label 和有序 targets；配对 ID 可以为空，files 只记录实际生成的角色、名称、大小和哈希。

版本字段允许未来区分新旧清单结构。

---

## 15. PySide6 图形界面详解

相关文件：

- [main_window.py](../livephoto/ui/main_window.py)
- [worker.py](../livephoto/ui/worker.py)
- [time_spinbox.py](../livephoto/ui/time_spinbox.py)
- [theme.py](../livephoto/ui/theme.py)
- [qt_compat.py](../livephoto/qt_compat.py)

### 15.1 界面分区

MainWindow 使用卡片式流程：

1. 选择视频；
2. 用共享编辑区添加、切换片段并设置封面；
3. 选择一个或多个兼容设备；
4. 选择保存位置；
5. 显示进度、日志和按钮。

QScrollArea 让小屏幕可以滚动。

### 15.2 DropArea

DropArea 继承 QFrame，并声明 file_dropped Signal。

dragEnterEvent 判断拖入内容是否包含本地文件；dropEvent 取得路径并发出信号；MainWindow 的 set_input_path 接收信号。

发送者不必了解接收者内部实现，这就是 Signal/Slot 的解耦。

### 15.3 SpinBox 与 Slider 同步

片段开始和封面都有数值框与滑块。`TimeSpinBox` 用 `MM:SS.cc` 显示六十进制时间，超过一小时显示 `HH:MM:SS.cc`，内部 value 仍是总秒数。程序使用 blockSignals 防止数值框、滑块和片段列表更新时形成循环。

### 15.4 片段列表与设备选择

MainWindow 使用 `list[ClipSegment]` 保存各片段。添加片段时默认从当前片段末尾开始；切换列表项前先保存当前控件值；删除后重新编号。四个设备复选框默认都不选，至少选中一项后转换按钮才会启用。

### 15.5 视频探测线程

set_input_path：

1. 创建 QThread；
2. 创建 ProbeWorker；
3. worker.moveToThread；
4. thread.started 连接 worker.run；
5. succeeded 连接 apply_video_info；
6. failed 连接 _probe_failed；
7. finished 负责退出和 deleteLater。

MainWindow 保存 worker 和 thread 引用非常重要。局部对象若被垃圾回收，后台工作可能提前消失，这正是早期界面卡在“正在读取视频信息”的根源。

### 15.6 转换线程和取消

BatchConversionWorker 保存 threading.Event，并依次处理每个 ConversionOptions：

- cancel 调用 Event.set；
- Converter 定期调用 Event.is_set；
- 为 True 时停止 FFmpeg并清理临时目录。
- 每个片段的 0～100 进度会换算为整个批次的总进度。

Event 是线程安全的状态信号。

### 15.7 busy 状态

转换中禁用输入、片段列表、设备复选框、滑块、画质和目录选择，只允许取消，避免界面参数与后台实际参数不一致。

### 15.8 qt_compat.py

Conda 可能注入不兼容 ICU DLL。prepare_qt_runtime 在 Windows 预加载系统 ICU。_PRELOADED 保留 DLL 对象引用，防止立即释放。

### 15.9 theme.py

APP_STYLE 是 Qt Style Sheet，类似 CSS：

- QWidget 控制全局字体；
- #objectName 选择指定控件；
- :hover 和 :disabled 表示状态；
- QProgressBar::chunk 控制填充部分。

视觉样式与业务逻辑分开，修改颜色不必改转换代码。

---

## 16. 命令行界面 CLI 详解

文件：[cli.py](../livephoto/cli.py)

基本用法：

~~~powershell
python -m livephoto convert ".\input.mp4" --output ".\output"
~~~

完整用法：

~~~powershell
python -m livephoto convert ".\input.mp4" --output ".\output" --start 2.5 --duration 3 --cover 3.8 --quality high --target vivo --target windows
~~~

| 参数 | 必需 | 说明 |
|---|---|---|
| input | 是 | 输入视频 |
| --output | 是 | 输出父目录 |
| --start | 否 | 默认 0 秒 |
| --duration | 否 | 默认 3 秒 |
| --cover | 否 | 默认片段中点 |
| --mute | 否 | 移除声音 |
| --quality | 否 | fast、balanced、high |
| --target | 否 | iphone、android、vivo、windows；可重复，省略时生成全部 |
| --json | 否 | 输出机器可读 JSON |

CLI 和 GUI 都创建 ConversionOptions 并调用同一个 Converter。

退出码 0 表示成功，1 表示转换失败，2 表示命令使用错误。自动化程序应检查退出码。

---

## 17. 辅助脚本逐个说明

### 17.1 capture_ui.py

[查看文件](../scripts/capture_ui.py)

使用 offscreen 模式在没有真实屏幕时截图。load_capture_font 注册微软雅黑、等线或黑体，避免中文变方框。

### 17.2 make_sample_video.py

[查看文件](../scripts/make_sample_video.py)

使用 FFmpeg lavfi 生成 1280×720、30 fps 测试画面和 880 Hz 声音。素材完全人工生成，不含隐私。

### 17.3 verify_bundle.py

[查看文件](../scripts/verify_bundle.py)

独立验收 manifest、哈希、Apple UUID、Android 内嵌视频、vivo ID、JPEG 可读性、H.264/AAC 和时长。

### 17.4 dump_mov_atoms.py

[查看文件](../scripts/dump_mov_atoms.py)

只读打印 MOV/MP4 Atom 树，用于研究和排错。

### 17.5 check_markdown_links.py

[查看文件](../scripts/check_markdown_links.py)

检查 README 和 docs 的本地相对链接，发现不存在的目标时返回非零退出码。

### 17.6 check_repository.py

[查看文件](../scripts/check_repository.py)

防止私人样本名和超过 10 MiB 的公开文件进入仓库；忽略 .venv、release、private_samples 等本地目录。

---

## 18. 测试代码逐个说明

| 文件 | 主要验证内容 |
|---|---|
| test_models.py | 参数边界和数据模型 |
| test_naming.py | 非法字符、保留名、时间戳 |
| test_tools.py | FFmpeg 搜索优先级 |
| test_transcode.py | 媒体探测、命令、进度、取消 |
| test_android.py | XMP、视频附加、损坏数据 |
| test_apple.py | MakerNote、MOV 轨道、offset |
| test_vivo.py | 脱敏结构、ID、EXIF、配对 |
| test_pipeline.py | 阶段、manifest、失败清理 |
| test_ui.py | 控件、线程、同步、busy 状态 |
| test_cli.py | CLI 参数和 JSON |
| test_scripts.py | 辅助脚本直接运行 |
| test_documentation.py | Markdown 链接 |
| test_project_metadata.py | 作者、许可、打包、3.10 兼容 |
| test_repository_hygiene.py | 隐私、大文件、CI |

tmp_path 提供临时目录；monkeypatch 临时替换函数和环境；parametrize 用一份逻辑检查多组数据。

常用命令：

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py::test_converter_runs_stages_and_publishes_manifest -q
~~~

---

## 19. 依赖、打包、CI 和仓库配置

### 19.1 requirements.txt

[查看文件](../requirements.txt)

- Pillow：JPEG、EXIF；
- PySide6：GUI；
- imageio-ffmpeg：FFmpeg 二进制。

### 19.2 requirements-dev.txt

[查看文件](../requirements-dev.txt)

在运行依赖上增加 pytest、PyInstaller 和 Python 3.10 使用的 tomli。

### 19.3 pyproject.toml

[查看文件](../pyproject.toml)

定义包名、版本、作者杨振、Apache-2.0、Python 版本、依赖、命令行入口、setuptools 和 pytest 配置。

### 19.4 build_windows.ps1

[查看文件](../build_windows.ps1)

创建环境、安装依赖、复制 FFmpeg、运行 PyInstaller，并把 README、LICENSE、NOTICE、第三方声明和兼容说明放进 dist。

### 19.5 livephoto.spec

[查看文件](../livephoto.spec)

指定入口、FFmpeg、Qt 插件、qwindows.dll、排除模块、无控制台窗口和输出名称。

### 19.6 GitHub Actions

[查看文件](../.github/workflows/ci.yml)

main 推送和 Pull Request 在 Windows 的 Python 3.10、3.12 上安装依赖、运行 pytest、检查文档链接和仓库隐私。

PYTHONUTF8=1 解决英文 Windows Runner 输出中文的问题；QT_QPA_PLATFORM=offscreen 让 UI 测试不依赖显示器。

### 19.7 .gitignore

[查看文件](../.gitignore)

忽略虚拟环境、缓存、构建目录、发布包、私人样本、日志和编辑器配置。

注意：它只对尚未跟踪的文件生效，已提交文件不会自动消失。

### 19.8 .gitattributes

[查看文件](../.gitattributes)

统一 LF/CRLF，并把图片、视频、ZIP、EXE、DLL 标记为二进制，减少跨系统假差异。

---

## 20. 文档、许可与发布文件

| 文件 | 用途 |
|---|---|
| [README.md](../README.md) | GitHub 首页、下载和快速开始 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 简洁架构图 |
| [COMPATIBILITY.md](COMPATIBILITY.md) | 手机传输和限制 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 开发、测试和打包 |
| [CHANGELOG.md](../CHANGELOG.md) | 版本变化 |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 贡献规则 |
| [LICENSE](../LICENSE) | Apache-2.0 法律文本 |
| [NOTICE](../NOTICE) | 作者和出处 |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | 第三方组件 |

Apache-2.0 允许使用、修改和分发，但要求保留许可和相关 NOTICE。源码的 SPDX 和 Copyright 行让许可归属更明确。

## 21. 从零理解 Git

### 21.1 Git 是什么

Git 是分布式版本控制系统，主要回答：

- 我改了什么？
- 什么时候改的？
- 为什么改？
- 哪个版本能运行？
- 两个人的修改怎样合并？
- 出错后怎样安全恢复？

GitHub 是托管 Git 仓库的网站，并提供 Issue、Pull Request、Actions 和 Release。

Git 不等于 GitHub：

- 没网也能本地使用 Git；
- commit 发生在本地；
- push 才上传；
- GitHub 只是众多远程服务之一。

### 21.2 Git 保存快照

每个 commit 是项目快照，包含提交 SHA、作者、时间、说明、父提交和文件树。

提交通过父提交连接成历史图，而不是简单的“撤销次数”。

### 21.3 SHA

完整 SHA 示例：

~~~text
627fe748c73ff0b0378168be8dd1736a561b92ba
~~~

日常常用前 7～10 位：

~~~text
627fe74
~~~

只要仓库中不产生歧义，短 SHA 就能定位提交。

### 21.4 HEAD

HEAD 表示“你当前所在位置”。正常情况下 HEAD 指向当前分支，当前分支再指向最新提交。

~~~text
HEAD → main → 最新提交
~~~

---

## 22. Git 安装与首次配置

检查版本：

~~~powershell
git --version
~~~

配置身份：

~~~powershell
git config --global user.name "YangZhen"
git config --global user.email "你的邮箱@example.com"
~~~

查看：

~~~powershell
git config --global --list
~~~

global 对当前电脑用户的所有仓库生效；local 只对当前仓库：

~~~powershell
git config --local user.name "YangZhen"
~~~

初始化新仓库：

~~~powershell
git init -b main
~~~

克隆已有仓库：

~~~powershell
git clone https://github.com/yangzhen-23/video-to-live-photo.git
~~~

init 是把普通目录变成仓库；clone 是下载已有远程仓库。

---

## 23. Git 最重要的四个区域

~~~mermaid
flowchart LR
    A["工作区 Working Tree"] -->|"git add"| B["暂存区 Index"]
    B -->|"git commit"| C["本地仓库"]
    C -->|"git push"| D["远程 GitHub"]
    D -->|"git fetch / pull"| C
~~~

### 23.1 工作区

你正在编辑的真实文件。

### 23.2 暂存区

下一次 commit 准备包含的内容。git add 不是上传，也不是永久保存，而是在选择下次提交。

### 23.3 本地仓库

.git 目录保存提交、分支、标签和配置。git commit 只写本地。

### 23.4 远程仓库

GitHub 上的副本。git push 才上传。

### 23.5 一个文件的典型旅程

~~~text
新建 notes.md
  ↓
git status 显示 ??
  ↓
git add notes.md
  ↓
进入暂存区，显示 A
  ↓
git commit
  ↓
进入本地历史
  ↓
git push
  ↓
出现在 GitHub
~~~

---

## 24. 日常最常用 Git 命令

### 24.1 git status

~~~powershell
git status
git status --short
~~~

建议每次操作前后都运行。

| 标记 | 含义 |
|---|---|
| ?? | 新文件，未跟踪 |
| M | 已修改 |
| A | 已暂存新增 |
| D | 已删除 |
| !! | 被忽略，需 --ignored 才显示 |

短状态有两列：第一列是暂存区状态，第二列是工作区状态。例如 MM 表示文件已经暂存过，但暂存后又继续修改。

### 24.2 git diff

看工作区尚未暂存的变化：

~~~powershell
git diff
~~~

看准备提交的变化：

~~~powershell
git diff --cached
~~~

只看统计：

~~~powershell
git diff --stat
git diff --cached --stat
~~~

检查空白问题：

~~~powershell
git diff --check
git diff --cached --check
~~~

### 24.3 git add

一个文件：

~~~powershell
git add README.md
~~~

几个明确文件：

~~~powershell
git add livephoto\core\pipeline.py tests\test_pipeline.py
~~~

全部变化：

~~~powershell
git add .
~~~

初学阶段建议添加明确文件，再运行 git diff --cached，降低误提交隐私的风险。

交互式选择部分修改：

~~~powershell
git add -p
~~~

Git 会逐块询问是否暂存，适合把混在一起的修改拆成不同提交。

### 24.4 git commit

~~~powershell
git commit -m "fix: correct video probe error"
~~~

好说明应表达目的，不要只写“修改”或“更新”。

| 前缀 | 用途 |
|---|---|
| feat | 新功能 |
| fix | 修复 |
| docs | 文档 |
| test | 测试 |
| refactor | 不改变行为的重构 |
| build | 依赖或打包 |
| ci | CI |
| chore | 其他维护 |

### 24.5 完整日常循环

~~~powershell
git status
git diff
.\.venv\Scripts\python.exe -m pytest -q
git add 修改的文件
git diff --cached
git commit -m "清晰的说明"
git status
git push
~~~

### 24.6 .gitignore 不是删除工具

加入 .gitignore 只阻止未来未跟踪文件被 add。已跟踪文件需要先从索引移除：

~~~powershell
git rm --cached 文件名
~~~

对目录：

~~~powershell
git rm -r --cached 目录名
~~~

操作前先确认路径，尤其不要对宽泛目录盲目运行递归命令。

---

## 25. 查看历史、比较差异和定位问题

简洁历史：

~~~powershell
git log --oneline
~~~

分支图：

~~~powershell
git log --oneline --graph --decorate --all
~~~

最近五条：

~~~powershell
git log -5 --oneline
~~~

查看提交：

~~~powershell
git show 627fe74
~~~

比较两个提交：

~~~powershell
git diff b817173 627fe74
~~~

只看某文件历史：

~~~powershell
git log --oneline -- livephoto\core\pipeline.py
~~~

每行最后修改者：

~~~powershell
git blame livephoto\core\pipeline.py
~~~

搜索哪次提交引入文字：

~~~powershell
git log -S "generate_live_photo_id" --oneline
~~~

搜索提交说明：

~~~powershell
git log --grep="CI" --oneline
~~~

这些都是只读命令，可以放心练习。

### 25.1 文件在某提交时的内容

~~~powershell
git show 627fe74:README.md
~~~

它不会切换版本，只把历史内容打印出来。

### 25.2 判断问题从哪次提交开始

高级命令 git bisect 使用二分查找：

~~~powershell
git bisect start
git bisect bad
git bisect good 某个正常提交SHA
~~~

每次 Git 切到中间版本，你测试并标记 good 或 bad，直到定位第一个坏提交。结束后：

~~~powershell
git bisect reset
~~~

初学时先理解思想，不必急着使用。

---

## 26. 分支、合并和冲突

### 26.1 分支是什么

分支是指向提交的可移动名称。main 是主线。

创建并切换：

~~~powershell
git switch -c feature/add-preview
~~~

查看：

~~~powershell
git branch
git branch -vv
~~~

切回：

~~~powershell
git switch main
~~~

### 26.2 为什么使用分支

- main 保持可运行；
- 独立实验；
- 方便 Pull Request；
- 不满意时可以丢弃分支。

### 26.3 合并

~~~powershell
git switch main
git merge feature/add-preview
~~~

如果 main 没有分叉，Git 可能进行 fast-forward，只移动 main 指针。

如果两边都有提交，Git 会整合历史，必要时创建 merge commit。

### 26.4 冲突

两条分支修改同一文件同一位置时，可能出现：

~~~text
< < < < < < < HEAD
main 的内容
= = = = = = =
功能分支内容
> > > > > > > feature/add-preview
~~~

上面的标记为了避免被文档检查器误判，特意在每个符号之间加入了空格。Git 实际写入文件时，符号之间没有空格，即连续 7 个小于号、等号或大于号。

解决步骤：

1. 打开文件；
2. 理解两边意图；
3. 编辑成正确结果；
4. 删除标记；
5. 测试；
6. git add；
7. git commit。

取消正在进行的合并：

~~~powershell
git merge --abort
~~~

### 26.5 删除分支

删除已合并本地分支：

~~~powershell
git branch -d feature/add-preview
~~~

-d 会阻止删除未合并分支，比 -D 安全。

删除远程分支：

~~~powershell
git push origin --delete feature/add-preview
~~~

### 26.6 stash

工作做到一半但必须临时切分支：

~~~powershell
git stash push -m "正在做封面预览"
git switch main
~~~

恢复：

~~~powershell
git stash list
git stash pop
~~~

stash 是临时架子，不应代替正式 commit。

---

## 27. 远程仓库与 GitHub

查看远程：

~~~powershell
git remote -v
~~~

本项目 origin：

~~~text
https://github.com/yangzhen-23/video-to-live-photo.git
~~~

添加远程：

~~~powershell
git remote add origin https://github.com/用户名/仓库名.git
~~~

首次推送：

~~~powershell
git push -u origin main
~~~

-u 建立跟踪关系，以后只写 git push。

只下载远程信息：

~~~powershell
git fetch origin
~~~

下载并整合：

~~~powershell
git pull
~~~

pull 本质上是 fetch 再整合。想看清过程可以分开：

~~~powershell
git fetch origin
git log --oneline --graph --decorate --all
git merge origin/main
~~~

### 27.1 origin/main 是什么

origin 是远程名称；origin/main 是本地记录的“远程 main 上次已知位置”。fetch 会更新它。

它不是 GitHub 上实时移动的魔法指针；没有 fetch 时，本地可能不知道远程最新状态。

### 27.2 Pull Request

推荐流程：

1. 从 main 创建功能分支；
2. 修改、测试、commit；
3. push 功能分支；
4. GitHub 创建 Pull Request；
5. CI 运行；
6. 审查；
7. 合并。

~~~powershell
git push -u origin feature/add-preview
~~~

### 27.3 fork

没有原仓库写权限时，可以 Fork 到自己账号，在自己的副本创建分支和提交，再向原仓库发 PR。

常把原仓库命名为 upstream：

~~~powershell
git remote add upstream 原仓库地址
git fetch upstream
~~~

## 28. 撤销操作：restore、revert 和 reset

这是初学者最容易误操作的部分。操作前先运行 git status 和 git diff。

### 28.1 丢弃未暂存修改

~~~powershell
git diff 文件名
git restore 文件名
~~~

restore 会覆盖工作区修改，通常不可恢复。只有明确不要这些变化时才执行。

### 28.2 取消暂存但保留修改

~~~powershell
git restore --staged 文件名
~~~

文件内容不变，只从下次提交清单移出。

### 28.3 从历史恢复一个文件

~~~powershell
git restore --source 某提交SHA -- 文件名
~~~

这会把历史版本写到当前工作区，之后你可以检查、测试并作为新修改提交。

### 28.4 amend 最近提交

还没共享时补遗漏文件：

~~~powershell
git add 遗漏文件
git commit --amend
~~~

只改说明：

~~~powershell
git commit --amend -m "新的提交说明"
~~~

amend 会生成新 SHA。旧提交已经推送时要谨慎。

### 28.5 安全撤销已公开提交

~~~powershell
git revert 提交SHA
~~~

revert 创建一个反向修改的新提交，不删除历史。公共 main 上优先使用。

### 28.6 reset 三种模式

~~~powershell
git reset --soft HEAD~1
git reset --mixed HEAD~1
git reset --hard HEAD~1
~~~

| 模式 | 提交 | 暂存区 | 工作区 |
|---|---|---|---|
| --soft | 回退 | 保留 | 保留 |
| --mixed | 回退 | 取消暂存 | 保留 |
| --hard | 回退 | 丢弃 | 丢弃 |

在不完全理解前，不要使用 reset --hard，也不要对共享分支 force push。

### 28.7 HEAD~1

HEAD~1 表示当前提交的第一个父提交，也就是通常所说的“上一个提交”。HEAD~2 是沿父链再往前一个。

### 28.8 reflog

误移动本地分支后查看：

~~~powershell
git reflog
~~~

reflog 记录本机 HEAD 移动，有时能救回误删提交，但它不是永久备份，也不会上传到远程。

### 28.9 revert 与 reset 怎样选

| 情况 | 推荐 |
|---|---|
| 尚未 commit 的工作区错误 | restore，先看 diff |
| 暂存错文件 | restore --staged |
| 本地最近 commit 需补文件 | amend |
| 已推送公共提交需要撤销 | revert |
| 私有本地提交需要重排 | 理解后使用 reset/rebase |

---

## 29. 标签与 GitHub Release

### 29.1 标签

标签给某个提交稳定版本名：

~~~powershell
git tag -a v0.2.0 -m "v0.2.0"
git push origin v0.2.0
~~~

查看：

~~~powershell
git tag
git show v0.2.0
~~~

分支会随着提交移动，标签通常固定不动。

删除本地标签：

~~~powershell
git tag -d v0.2.0
~~~

删除远程标签属于影响发布历史的操作，应非常谨慎：

~~~powershell
git push origin --delete v0.2.0
~~~

### 29.2 Release

GitHub Release 通常包含：

- 标签；
- 版本说明；
- Windows ZIP；
- SHA-256；
- 自动生成的源码归档。

本项目发布前应：

1. pytest 全部通过；
2. Markdown 链接通过；
3. 仓库隐私检查通过；
4. 端到端转换通过；
5. 打包 EXE；
6. GUI 冒烟启动；
7. 校验 ZIP；
8. 更新 CHANGELOG；
9. 创建标签和 Release。

### 29.3 语义化版本

常见版本格式 major.minor.patch：

- major：不兼容的大变化；
- minor：向后兼容的新功能；
- patch：向后兼容的修复。

例如 0.2.0 仍处于 1.0 前开发阶段，minor 变化也可能较明显，应在 CHANGELOG 写清楚。

---

## 30. 本项目推荐的 Git 工作流

### 30.1 修改前

~~~powershell
git switch main
git pull
git status
git switch -c feature/你的功能名
~~~

### 30.2 开发中小步提交

~~~powershell
git add tests\相关测试.py
git commit -m "test: describe expected behavior"
git add livephoto\相关代码.py
git commit -m "feat: implement expected behavior"
~~~

一个提交尽量只做一件事。测试和实现也可以放在同一提交，只要目的单一、审查容易。

### 30.3 提交前检查

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\check_markdown_links.py
.\.venv\Scripts\python.exe scripts\check_repository.py
git diff --check
git status
~~~

然后：

~~~powershell
git add 明确的文件
git diff --cached
git diff --cached --check
git commit -m "说明"
~~~

### 30.4 推送和 PR

~~~powershell
git push -u origin feature/你的功能名
~~~

到 GitHub 创建 Pull Request，等 CI 变绿后合并。

### 30.5 具体例子：封面预览

~~~powershell
git switch main
git pull
git switch -c feature/cover-preview
~~~

先在 tests/test_ui.py 写失败测试，再修改 main_window.py。

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ui.py -q
git add tests\test_ui.py livephoto\ui\main_window.py
git diff --cached
git commit -m "feat: add cover frame preview"
git push -u origin feature/cover-preview
~~~

### 30.6 文档修改示例

~~~powershell
git switch -c docs/improve-learning-guide
git add docs\PROJECT_CODE_AND_GIT_GUIDE.md README.md
git diff --cached
git commit -m "docs: add code and Git learning guide"
git push -u origin docs/improve-learning-guide
~~~

---

## 31. 常见错误与排查方法

### 31.1 看见很多 __pycache__

确认 .gitignore 包含 __pycache__/。若已经跟踪，使用 git rm --cached 移出索引，但先确认目标。

### 31.2 push 提示 rejected

远程有本地没有的提交：

~~~powershell
git fetch origin
git log --oneline --graph --decorate --all
git pull
~~~

解决合并或冲突后再 push。不要一看到 rejected 就 force push。

### 31.3 误 add 大视频

尚未 commit：

~~~powershell
git restore --staged 大视频.mp4
~~~

再加入 .gitignore。

已经 commit 但没 push，可以重做本地提交；已经公开则涉及历史重写，初学者应先备份并寻求帮助。

### 31.4 中文路径显示转义

~~~powershell
git config --local core.quotepath false
~~~

### 31.5 整份文件都变化

常见原因是 LF/CRLF。先检查 .gitattributes，不要提交巨大无意义差异。

### 31.6 detached HEAD

如果 git status 提示 HEAD detached，说明当前直接停在某个提交而不是分支。

想保留修改应立即创建分支：

~~~powershell
git switch -c rescue/my-work
~~~

### 31.7 找不到 FFmpeg

~~~powershell
.\.venv\Scripts\python.exe -c "from livephoto.core.tools import Toolchain; print(Toolchain.discover())"
~~~

普通用户通常重新运行“安装依赖.bat”即可。

### 31.8 GUI 卡在视频分析

依次检查：

1. FFmpeg 是否存在；
2. ProbeWorker 是否仍有对象引用；
3. QThread 是否启动；
4. failed Signal 是否连接；
5. 日志是否显示异常；
6. test_ui 是否通过。

### 31.9 手机不识别

优先 USB 原文件传输，并检查：

- 文件是否改名；
- vivo JPG/MP4 是否同名；
- 是否都在 DCIM/Camera；
- manifest 哈希是否一致；
- 聊天软件是否压缩；
- 相册是否重新扫描。

### 31.10 GitHub Actions 本地通过、远程失败

常见原因：

- Python 版本不同；
- Windows 编码不同；
- 环境变量不同；
- 测试依赖漏写；
- 本地存在但未提交的文件；
- 路径大小写差异。

打开 Actions 失败任务，找到第一条真正的 traceback，不要只看最后的 exit code。

---

## 32. 建议的学习路线和练习

### 第一阶段：运行和观察

1. 源码启动 GUI；
2. 生成测试视频；
3. 运行一次 CLI；
4. 打开 manifest；
5. 比较平台文件大小。

### 第二阶段：读 Python 项目

1. 给 safe_stem 添加测试；
2. 修改一条错误提示；
3. CLI 增加 --version；
4. 理解 dataclass；
5. 理解回调和依赖注入。

### 第三阶段：学测试

1. 故意让断言失败；
2. 看 pytest 行号；
3. 使用 tmp_path；
4. 用 monkeypatch 替换函数；
5. 比较单元测试与端到端测试。

### 第四阶段：练 Git

~~~powershell
git switch -c learning/git-practice
~~~

练习：

1. 新建 learning_notes.md；
2. git status；
3. git diff；
4. git add；
5. git diff --cached；
6. commit；
7. 再改一次并 commit；
8. git log --oneline --graph；
9. git show；
10. 切回 main。

纯练习分支不要合并到 main。

### 第五阶段：媒体格式

1. dump_mov_atoms 查看普通 MOV；
2. 查看生成的 Apple MOV；
3. 比较多出的 meta/trak；
4. 用十六进制查看器找 ftyp、moov、mdat；
5. 阅读 Android XMP；
6. 观察 vivo JPEG EOI 后数据。

### 小功能练习

按难度：

1. 状态栏显示输出文件数量；
2. 添加“复制成品路径”；
3. CLI 增加 --version；
4. manifest 增加程序版本；
5. 增加封面预览；
6. 支持用户选择 fps；
7. 增加一键重新校验。

每个练习都先写测试、再实现、最后更新文档。

---

## 33. 术语速查表

| 术语 | 简单解释 |
|---|---|
| API | 模块提供给其他代码调用的接口 |
| Atom/Box | MOV/MP4 中带长度和类型的数据块 |
| AAC | 常见音频编码 |
| CLI | 命令行界面 |
| CI | 提交后自动安装和测试 |
| CRF | H.264 质量参数，通常越小质量越高 |
| dataclass | 表达结构化数据的 Python 类 |
| EXIF | JPEG 中的相机和拍摄信息 |
| FFmpeg | 音视频处理程序 |
| FFprobe | 读取媒体信息的工具 |
| fps | 每秒帧数 |
| frozen | dataclass 字段创建后不可改 |
| GUI | 图形用户界面 |
| H.264 | 广泛兼容的视频编码 |
| Hash | 根据文件内容生成的指纹 |
| ISO-BMFF | MP4/MOV 的基础容器结构 |
| MakerNote | EXIF 中厂商自定义区域 |
| manifest | 输出文件清单 |
| metadata | 描述媒体的信息 |
| pytest | Python 自动测试框架 |
| Qt/PySide6 | GUI 框架及 Python 绑定 |
| Signal/Slot | Qt 对象间传递事件的机制 |
| UUID | 通用唯一标识符 |
| XMP | 可嵌入图片的 XML 元数据 |
| 工作区 | 当前磁盘文件 |
| 暂存区 | 下一次 Git 提交准备包含的变化 |
| commit | Git 中的一次项目快照 |
| branch | 指向提交的开发线 |
| merge | 合并两条历史 |
| remote | 远程仓库地址 |
| origin | 常用默认远程名称 |
| fetch | 下载远程历史但不合并 |
| pull | 下载并整合远程变化 |
| push | 上传本地提交 |
| tag | 给提交固定版本名 |
| Pull Request | 请求审查和合并分支 |

---

## 结语

这个项目包含真实开源软件常见的主要组成：

- GUI 和 CLI；
- 核心业务模块；
- 外部工具调用；
- 二进制解析和写入；
- 异常处理与后台线程；
- 单元测试和端到端测试；
- 打包和 CI；
- 文档、许可和 Release。

真正值得掌握的是模块边界：

> UI 收集参数，模型表达数据，流水线组织步骤，格式模块完成封装，校验器证明结果，测试保护行为，Git 保存演进历史，CI 在远程重复验证。

当你能沿入口讲清一次转换，并独立完成 status、diff、add、commit、branch、push 和 revert，就已经跨过“只会写单个 Python 脚本”，开始具备维护完整项目的能力。
