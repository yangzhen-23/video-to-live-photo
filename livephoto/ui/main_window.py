# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.models import TARGET_ORDER, ClipSegment, ConversionOptions, OutputBundle, VideoInfo
from ..core.pipeline import Converter
from ..core.probe import probe_video
from ..core.tools import Toolchain
from .theme import APP_STYLE
from .time_spinbox import TimeSpinBox, format_time
from .worker import BatchConversionWorker, ProbeWorker


TARGET_LABELS = {
    "iphone": "iPhone / iPad",
    "android": "标准 Android",
    "vivo": "vivo / iQOO",
    "windows": "Windows",
}


class DropArea(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(2)
        icon = QLabel("＋")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel("把视频拖到这里，或点击“浏览”选择")
        self.text.setObjectName("dropText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(self.text)

    def set_selected(self, path: Path) -> None:
        self.text.setText(f"已选择：{path.name}")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        local = next((url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()), "")
        if local:
            self.file_dropped.emit(local)
            event.acceptProposedAction()


class StepCard(QFrame):
    def __init__(self, number: str, title: str, hint: str) -> None:
        super().__init__()
        self.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 20)
        outer.setSpacing(14)
        header = QHBoxLayout()
        badge = QLabel(number)
        badge.setObjectName("stepBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headings = QVBoxLayout()
        headings.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        hint_label = QLabel(hint)
        hint_label.setObjectName("cardHint")
        hint_label.setWordWrap(True)
        headings.addWidget(title_label)
        headings.addWidget(hint_label)
        header.addWidget(badge)
        header.addLayout(headings, 1)
        outer.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        outer.addLayout(self.body)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("视频转 Live 图")
        self.resize(920, 820)
        self.setMinimumSize(760, 640)
        self.setStyleSheet(APP_STYLE)
        self._video_info: VideoInfo | None = None
        self._toolchain: Toolchain | None = None
        self._busy = False
        self._last_start = 0.0
        self._result_dir: Path | None = None
        self._probe_thread: QThread | None = None
        self._probe_worker: ProbeWorker | None = None
        self._convert_thread: QThread | None = None
        self._convert_worker: BatchConversionWorker | None = None
        self._segments = [ClipSegment()]
        self._current_segment_index = 0
        self._loading_segment = False
        self._build_ui()
        self._connect_signals()
        self.update_action_state()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("scrollContent")
        content = QVBoxLayout(container)
        content.setContentsMargins(42, 30, 42, 34)
        content.setSpacing(16)
        content.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("视频转 Live 图")
        title.setObjectName("appTitle")
        subtitle = QLabel("按需生成 iPhone、Android、vivo/iQOO 或 Windows 动态照片文件")
        subtitle.setObjectName("subtitle")
        content.addWidget(title)
        content.addWidget(subtitle)
        content.addSpacing(4)

        input_card = StepCard("1", "选择视频", "支持常见 MP4、MOV、MKV、AVI 等格式；转换全程在本机完成。")
        self.drop_area = DropArea()
        input_card.body.addWidget(self.drop_area)
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setObjectName("inputPath")
        self.input_edit.setPlaceholderText("尚未选择视频")
        self.browse_input_button = QPushButton("浏览视频")
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(self.browse_input_button)
        input_card.body.addLayout(input_row)
        self.info_label = QLabel("选择视频后会显示时长、分辨率和声音信息")
        self.info_label.setObjectName("infoPill")
        self.info_label.setWordWrap(True)
        input_card.body.addWidget(self.info_label)
        content.addWidget(input_card)

        trim_card = StepCard("2", "选择片段与封面", "默认 3 秒并保留声音；第一次使用保持默认即可。")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        self.start_spin = self._time_spin()
        self.duration_spin = self._time_spin()
        self.duration_spin.setRange(1.0, 5.0)
        self.duration_spin.setValue(3.0)
        self.cover_spin = self._time_spin()
        self.cover_spin.setValue(1.5)
        grid.addWidget(QLabel("片段开始"), 0, 0)
        grid.addWidget(self.start_spin, 0, 1)
        grid.addWidget(QLabel("片段时长"), 0, 2)
        grid.addWidget(self.duration_spin, 0, 3)
        grid.addWidget(QLabel("封面时刻"), 1, 0)
        grid.addWidget(self.cover_spin, 1, 1)
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("快速（文件较小）", "fast")
        self.quality_combo.addItem("均衡（推荐）", "balanced")
        self.quality_combo.addItem("高画质", "high")
        self.quality_combo.setCurrentIndex(1)
        grid.addWidget(QLabel("画质"), 1, 2)
        grid.addWidget(self.quality_combo, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        trim_card.body.addLayout(grid)
        trim_card.body.addWidget(QLabel("拖动选择片段开始位置"))
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider.setRange(0, 0)
        trim_card.body.addWidget(self.start_slider)
        trim_card.body.addWidget(QLabel("拖动选择静态封面位置"))
        self.cover_slider = QSlider(Qt.Orientation.Horizontal)
        self.cover_slider.setRange(0, 3000)
        self.cover_slider.setValue(1500)
        trim_card.body.addWidget(self.cover_slider)
        self.mute_check = QCheckBox("静音（不保留原视频声音）")
        trim_card.body.addWidget(self.mute_check)
        segment_header = QHBoxLayout()
        segment_header.addWidget(QLabel("片段列表（点击可切换编辑）"), 1)
        self.add_segment_button = QPushButton("＋ 添加片段")
        self.remove_segment_button = QPushButton("删除片段")
        segment_header.addWidget(self.add_segment_button)
        segment_header.addWidget(self.remove_segment_button)
        trim_card.body.addLayout(segment_header)
        self.segment_list = QListWidget()
        self.segment_list.setObjectName("segmentList")
        self.segment_list.setMaximumHeight(130)
        trim_card.body.addWidget(self.segment_list)
        content.addWidget(trim_card)

        target_card = StepCard(
            "3",
            "选择兼容设备",
            "可同时选择多个设备；成品中只保留所选设备需要的文件。",
        )
        target_layout = QGridLayout()
        self.target_checks: dict[str, QCheckBox] = {}
        target_hints = {
            "iphone": "同名 JPG + MOV",
            "android": "单文件 Motion Photo",
            "vivo": "OriginOS 同名 JPG + MP4",
            "windows": "普通封面 JPG + MP4",
        }
        for index, target in enumerate(TARGET_ORDER):
            check = QCheckBox(TARGET_LABELS[target])
            check.setObjectName(f"target_{target}")
            hint = QLabel(target_hints[target])
            hint.setObjectName("targetHint")
            row, column = divmod(index, 2)
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(check)
            cell.addWidget(hint)
            target_layout.addLayout(cell, row, column)
            self.target_checks[target] = check
        target_layout.setColumnStretch(0, 1)
        target_layout.setColumnStretch(1, 1)
        target_card.body.addLayout(target_layout)
        content.addWidget(target_card)

        output_card = StepCard("4", "选择保存位置", "程序会为每个片段新建成品文件夹，不会覆盖原文件。")
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setObjectName("outputPath")
        self.output_edit.setPlaceholderText("选择成品保存目录")
        self.browse_output_button = QPushButton("浏览目录")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_output_button)
        output_card.body.addLayout(output_row)
        content.addWidget(output_card)

        action_card = QFrame()
        action_card.setObjectName("card")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(22, 20, 22, 22)
        action_layout.setSpacing(12)
        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("statusLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("处理进度和提示会显示在这里")
        self.log_edit.setMaximumHeight(110)
        buttons = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.open_folder_button = QPushButton("打开成品文件夹")
        self.open_folder_button.setEnabled(False)
        self.convert_button = QPushButton("生成所选设备的 Live 图")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.convert_button, 1)
        action_layout.addWidget(self.status_label)
        action_layout.addWidget(self.progress_bar)
        action_layout.addWidget(self.log_edit)
        action_layout.addLayout(buttons)
        content.addWidget(action_card)
        scroll.setWidget(container)
        root_layout.addWidget(scroll)
        self._refresh_segment_list()

    @staticmethod
    def _time_spin() -> TimeSpinBox:
        return TimeSpinBox()

    def _connect_signals(self) -> None:
        self.browse_input_button.clicked.connect(self.choose_input)
        self.browse_output_button.clicked.connect(self.choose_output)
        self.drop_area.file_dropped.connect(self.set_input_path)
        self.input_edit.editingFinished.connect(self._typed_input_finished)
        self.input_edit.textChanged.connect(self.update_action_state)
        self.output_edit.textChanged.connect(self.update_action_state)
        self.start_spin.valueChanged.connect(self._start_changed)
        self.duration_spin.valueChanged.connect(self._duration_changed)
        self.cover_spin.valueChanged.connect(self._cover_changed)
        self.start_slider.valueChanged.connect(lambda value: self.start_spin.setValue(value / 1000))
        self.cover_slider.valueChanged.connect(lambda value: self.cover_spin.setValue(value / 1000))
        self.add_segment_button.clicked.connect(self.add_segment)
        self.remove_segment_button.clicked.connect(self.remove_segment)
        self.segment_list.currentRowChanged.connect(self._segment_selected)
        for check in self.target_checks.values():
            check.stateChanged.connect(self.update_action_state)
        self.convert_button.clicked.connect(self.start_conversion)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.open_folder_button.clicked.connect(self.open_result_folder)

    def choose_input(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频",
            "",
            "视频文件 (*.mp4 *.mov *.mkv *.avi *.m4v *.webm);;所有文件 (*.*)",
        )
        if filename:
            self.set_input_path(filename)

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择成品保存目录")
        if folder:
            self.output_edit.setText(folder)

    def _typed_input_finished(self) -> None:
        path = Path(self.input_edit.text().strip())
        if path.is_file() and (self._video_info is None):
            self.set_input_path(str(path))

    def set_input_path(self, filename: str) -> None:
        path = Path(filename)
        if not path.is_file():
            self.info_label.setText("找不到这个视频，请重新选择。")
            self._video_info = None
            self.update_action_state()
            return
        self.input_edit.setText(str(path))
        self.drop_area.set_selected(path)
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(path.parent / "Live图成品"))
        self.info_label.setText("正在读取视频信息…")
        self.status_label.setText("正在分析视频")
        self._video_info = None
        self.update_action_state()
        try:
            self._toolchain = Toolchain.discover()
        except Exception as exc:
            self._probe_failed(str(exc))
            return
        thread = QThread(self)
        worker = ProbeWorker(probe_video, path, self._toolchain)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self.apply_video_info)
        worker.failed.connect(self._probe_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._probe_thread = thread
        self._probe_worker = worker
        thread.finished.connect(self._probe_thread_finished)
        thread.start()

    def _probe_thread_finished(self) -> None:
        self._probe_thread = None
        self._probe_worker = None

    def apply_video_info(self, info: VideoInfo) -> None:
        duration = max(0.0, info.duration)
        if duration < 1.0:
            self._probe_failed("视频不足 1 秒，无法创建 Live 图片段")
            return
        self._video_info = info
        selected_duration = min(3.0, min(5.0, duration))
        midpoint = selected_duration / 2
        self._segments = [ClipSegment(0.0, selected_duration, midpoint)]
        self._current_segment_index = 0
        self._refresh_segment_list()
        self._load_segment(0)
        audio = "有声音" if info.has_audio else "无声音"
        self.info_label.setText(
            f"时长 {self._format_time(info.duration)}　｜　{info.width} × {info.height}　｜　"
            f"{info.fps:.2f} fps　｜　{audio}"
        )
        self.status_label.setText("视频已就绪")
        self.log_edit.append("✓ 视频信息读取完成")
        self.update_action_state()

    @staticmethod
    def _format_time(seconds: float) -> str:
        return format_time(seconds)

    def _save_current_segment(self) -> None:
        if (
            self._loading_segment
            or not 0 <= self._current_segment_index < len(self._segments)
        ):
            return
        self._segments[self._current_segment_index] = ClipSegment(
            self.start_spin.value(),
            self.duration_spin.value(),
            self.cover_spin.value(),
        )
        self._refresh_segment_list()

    def _refresh_segment_list(self) -> None:
        self.segment_list.blockSignals(True)
        self.segment_list.clear()
        for index, segment in enumerate(self._segments, start=1):
            end = segment.start_time + segment.duration
            self.segment_list.addItem(
                f"片段 {index}　{format_time(segment.start_time)} → "
                f"{format_time(end)}　封面 {format_time(segment.cover_time)}"
            )
        if self._segments:
            self.segment_list.setCurrentRow(self._current_segment_index)
        self.segment_list.blockSignals(False)
        self.remove_segment_button.setEnabled(
            not self._busy and len(self._segments) > 1
        )
        count = len(self._segments)
        self.convert_button.setText(
            "生成所选设备的 Live 图"
            if count == 1
            else f"生成 {count} 个片段的 Live 图"
        )

    def _load_segment(self, index: int) -> None:
        if not 0 <= index < len(self._segments):
            return
        segment = self._segments[index]
        source_duration = self._video_info.duration if self._video_info else 99_999.0
        max_duration = max(1.0, min(5.0, source_duration))
        max_start = max(0.0, source_duration - segment.duration)
        self._loading_segment = True
        for spin in (self.start_spin, self.duration_spin, self.cover_spin):
            spin.blockSignals(True)
        self.duration_spin.setRange(1.0, max_duration)
        self.duration_spin.setValue(segment.duration)
        self.start_spin.setRange(0.0, max_start)
        self.start_spin.setValue(segment.start_time)
        end = segment.start_time + segment.duration
        self.cover_spin.setRange(segment.start_time, end)
        self.cover_spin.setValue(segment.cover_time)
        for spin in (self.start_spin, self.duration_spin, self.cover_spin):
            spin.blockSignals(False)
        self.start_slider.setRange(0, round(max_start * 1000))
        self.start_slider.setValue(round(segment.start_time * 1000))
        self.cover_slider.setRange(round(segment.start_time * 1000), round(end * 1000))
        self.cover_slider.setValue(round(segment.cover_time * 1000))
        self._last_start = segment.start_time
        self._loading_segment = False
        self.update_action_state()

    def _segment_selected(self, row: int) -> None:
        if row < 0 or row == self._current_segment_index:
            return
        self._save_current_segment()
        self._current_segment_index = row
        self._load_segment(row)

    def add_segment(self) -> None:
        self._save_current_segment()
        current = self._segments[self._current_segment_index]
        source_duration = self._video_info.duration if self._video_info else 3.0
        proposed_start = current.start_time + current.duration
        remaining = source_duration - proposed_start
        if remaining >= 1.0:
            start = proposed_start
            duration = min(3.0, remaining)
        else:
            start = 0.0
            duration = min(3.0, source_duration)
        segment = ClipSegment(start, duration, start + duration / 2)
        self._segments.append(segment)
        self._current_segment_index = len(self._segments) - 1
        self._refresh_segment_list()
        self._load_segment(self._current_segment_index)

    def remove_segment(self) -> None:
        if len(self._segments) == 1:
            return
        index = self._current_segment_index
        del self._segments[index]
        self._current_segment_index = min(index, len(self._segments) - 1)
        self._refresh_segment_list()
        self._load_segment(self._current_segment_index)

    def _probe_failed(self, message: str) -> None:
        self._video_info = None
        self.info_label.setText(f"无法读取视频：{message}")
        self.status_label.setText("视频分析失败")
        self.log_edit.append(f"✗ {message}")
        self.update_action_state()

    def _start_changed(self, value: float) -> None:
        delta = value - self._last_start
        self._last_start = value
        self.start_slider.blockSignals(True)
        self.start_slider.setValue(round(value * 1000))
        self.start_slider.blockSignals(False)
        end = value + self.duration_spin.value()
        target = min(end, max(value, self.cover_spin.value() + delta))
        self.cover_spin.setRange(value, end)
        self.cover_spin.setValue(target)
        self.cover_slider.setRange(round(value * 1000), round(end * 1000))
        self._save_current_segment()
        self.update_action_state()

    def _duration_changed(self, value: float) -> None:
        if self._video_info:
            max_start = max(0.0, self._video_info.duration - value)
            self.start_spin.setMaximum(max_start)
            self.start_slider.setMaximum(round(max_start * 1000))
        start = self.start_spin.value()
        end = start + value
        self.cover_spin.setRange(start, end)
        if self.cover_spin.value() > end:
            self.cover_spin.setValue(end)
        self.cover_slider.setRange(round(start * 1000), round(end * 1000))
        self._save_current_segment()
        self.update_action_state()

    def _cover_changed(self, value: float) -> None:
        self.cover_slider.blockSignals(True)
        self.cover_slider.setValue(round(value * 1000))
        self.cover_slider.blockSignals(False)
        self._save_current_segment()
        self.update_action_state()

    def update_action_state(self, *_args) -> None:
        has_target = any(box.isChecked() for box in self.target_checks.values())
        ready = (
            not self._busy
            and self._video_info is not None
            and Path(self.input_edit.text().strip()).is_file()
            and bool(self.output_edit.text().strip())
            and has_target
        )
        self.convert_button.setEnabled(ready)
        if not self._busy and self._video_info is not None:
            if not has_target:
                self.status_label.setText("请至少选择一种兼容设备")
            elif self.status_label.text() == "请至少选择一种兼容设备":
                self.status_label.setText("视频已就绪")

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (
            self.input_edit,
            self.browse_input_button,
            self.drop_area,
            self.start_spin,
            self.start_slider,
            self.duration_spin,
            self.cover_spin,
            self.cover_slider,
            self.quality_combo,
            self.mute_check,
            self.output_edit,
            self.browse_output_button,
            self.segment_list,
            self.add_segment_button,
            self.remove_segment_button,
        ):
            widget.setEnabled(not busy)
        for check in self.target_checks.values():
            check.setEnabled(not busy)
        if not busy:
            self.remove_segment_button.setEnabled(len(self._segments) > 1)
        self.cancel_button.setEnabled(busy)
        self.update_action_state()

    def _build_conversion_options(self) -> tuple[ConversionOptions, ...]:
        if self._video_info is None:
            raise ValueError("请先选择并分析视频")
        self._save_current_segment()
        targets = frozenset(
            target for target, box in self.target_checks.items() if box.isChecked()
        )
        if not targets:
            raise ValueError("请至少选择一种兼容设备")
        input_path = Path(self.input_edit.text().strip())
        output_dir = Path(self.output_edit.text().strip())
        total = len(self._segments)
        results = []
        for index, segment in enumerate(self._segments, start=1):
            try:
                segment.validate(self._video_info.duration)
            except ValueError as exc:
                self.segment_list.setCurrentRow(index - 1)
                raise ValueError(f"片段 {index}：{exc}") from exc
            results.append(
                ConversionOptions(
                    input_path=input_path,
                    output_dir=output_dir,
                    start_time=segment.start_time,
                    duration=segment.duration,
                    cover_time=segment.cover_time,
                    mute=self.mute_check.isChecked(),
                    quality=str(self.quality_combo.currentData()),
                    targets=targets,
                    segment_label=f"片段{index:02d}" if total > 1 else "",
                )
            )
        return tuple(results)

    def start_conversion(self) -> None:
        if self._video_info is None or self._busy:
            return
        try:
            toolchain = self._toolchain or Toolchain.discover()
            options = self._build_conversion_options()
        except Exception as exc:
            QMessageBox.warning(self, "无法开始", str(exc))
            return
        self.progress_bar.setValue(0)
        self.status_label.setText("开始转换")
        self.log_edit.append(f"— 开始生成 {len(options)} 个独立片段 —")
        self.open_folder_button.setEnabled(False)
        self.set_busy(True)
        thread = QThread(self)
        worker = BatchConversionWorker(Converter(toolchain), options)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._conversion_thread_finished)
        self._convert_thread = thread
        self._convert_worker = worker
        thread.start()

    def _on_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(value)
        self.status_label.setText(text)
        if not self.log_edit.toPlainText().endswith(text):
            self.log_edit.append(f"{value:3d}%  {text}")

    def _on_completed(self, bundles: tuple[OutputBundle, ...]) -> None:
        self._result_dir = Path(self.output_edit.text().strip())
        self.progress_bar.setValue(100)
        self.status_label.setText("转换完成")
        for index, bundle in enumerate(bundles, start=1):
            self.log_edit.append(f"✓ 片段 {index} 已保存到：{bundle.directory}")
        self.set_busy(False)
        self.open_folder_button.setEnabled(True)
        QMessageBox.information(
            self,
            "转换完成",
            f"已生成 {len(bundles)} 个独立片段。\n可点击“打开成品文件夹”查看。",
        )

    def _on_failed(self, message: str) -> None:
        self.set_busy(False)
        self.status_label.setText("已取消" if "取消" in message else "转换失败")
        self.log_edit.append(f"✗ {message}")
        if "取消" not in message:
            QMessageBox.warning(self, "转换失败", message)

    def _conversion_thread_finished(self) -> None:
        self._convert_thread = None
        self._convert_worker = None

    def cancel_conversion(self) -> None:
        if self._convert_worker:
            self.status_label.setText("正在取消…")
            self.cancel_button.setEnabled(False)
            self._convert_worker.cancel()

    def open_result_folder(self) -> None:
        if self._result_dir and self._result_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._result_dir)))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy and self._convert_worker:
            self._convert_worker.cancel()
        super().closeEvent(event)
