# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from pathlib import Path

import pytest

from livephoto.qt_compat import prepare_qt_runtime

prepare_qt_runtime()

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget

from livephoto.core.models import OutputBundle, VideoInfo
from livephoto.ui.main_window import MainWindow
from livephoto.ui.worker import ConversionWorker
from scripts.capture_ui import load_capture_font


@pytest.fixture(scope="session")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_main_window_contains_beginner_workflow_controls(app):
    window = MainWindow()
    assert window.windowTitle() == "视频转 Live 图"
    assert window.input_edit.objectName() == "inputPath"
    assert window.drop_area.acceptDrops() is True
    assert window.duration_spin.value() == 3.0
    assert window.cover_spin.value() == 1.5
    assert window.quality_combo.currentData() == "balanced"
    assert window.convert_button.text() == "生成 Live 图兼容包"
    assert window.convert_button.isEnabled() is False
    assert window.progress_bar.value() == 0
    assert window.open_folder_button.isEnabled() is False
    assert window.log_edit.isReadOnly() is True
    assert window.findChild(QWidget, "scrollContent") is not None
    window.close()


def test_capture_font_loader_registers_a_chinese_font(app):
    family = load_capture_font(app)

    assert family
    assert app.font().family() == family


def test_video_info_updates_ranges_and_enables_conversion(app, tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "output"
    window = MainWindow()
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(output))
    window.apply_video_info(VideoInfo(8.0, 1920, 1080, 29.97, True))

    assert "1920 × 1080" in window.info_label.text()
    assert window.start_spin.maximum() == 5.0
    assert window.cover_spin.minimum() == 0.0
    assert window.cover_spin.maximum() == 3.0
    assert window.convert_button.isEnabled() is True
    window.close()


def test_async_video_probe_keeps_worker_alive_until_result(
    app, tmp_path: Path, monkeypatch
):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    expected = VideoInfo(8.0, 1920, 1080, 30.0, True)
    monkeypatch.setattr(
        "livephoto.ui.main_window.Toolchain.discover", lambda: object()
    )
    monkeypatch.setattr(
        "livephoto.ui.main_window.probe_video", lambda _path, _tools: expected
    )
    window = MainWindow()

    try:
        window.set_input_path(str(source))
        loop = QEventLoop()
        QTimer.singleShot(300, loop.quit)
        loop.exec()

        assert window._video_info == expected
        assert window.convert_button.isEnabled() is True
    finally:
        if window._probe_thread and window._probe_thread.isRunning():
            window._probe_thread.quit()
            window._probe_thread.wait(1000)
        window.close()


def test_time_sliders_and_spin_boxes_stay_synchronized(app, tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    window = MainWindow()
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(tmp_path / "out"))
    window.apply_video_info(VideoInfo(10.0, 1280, 720, 30.0, False))

    window.start_slider.setValue(2000)
    assert window.start_spin.value() == 2.0
    assert window.cover_spin.value() == pytest.approx(3.5)
    window.cover_spin.setValue(4.0)
    assert window.cover_slider.value() == 4000
    window.duration_spin.setValue(2.0)
    assert window.cover_spin.maximum() == 4.0
    window.close()


def test_busy_state_disables_editing_and_exposes_cancel(app):
    window = MainWindow()
    window.set_busy(True)
    assert window.convert_button.isEnabled() is False
    assert window.cancel_button.isEnabled() is True
    assert window.input_edit.isEnabled() is False
    window.set_busy(False)
    assert window.cancel_button.isEnabled() is False
    assert window.input_edit.isEnabled() is True
    window.close()


def test_conversion_worker_emits_progress_and_completion(tmp_path: Path):
    paths = [
        tmp_path / name
        for name in (
            "a.jpg",
            "a.mov",
            "aMP.jpg",
            "IMG_20260718_120000.jpg",
            "IMG_20260718_120000.mp4",
            "w.jpg",
            "w.mp4",
            "manifest.json",
        )
    ]
    bundle = OutputBundle(tmp_path, *paths)

    class FakeConverter:
        def convert(self, options, progress, cancel):
            progress(50, "处理中")
            assert cancel() is False
            return bundle

    worker = ConversionWorker(FakeConverter(), object())
    progress = []
    completed = []
    worker.progress.connect(lambda value, text: progress.append((value, text)))
    worker.completed.connect(completed.append)
    worker.run()
    assert progress == [(50, "处理中")]
    assert completed == [bundle]
