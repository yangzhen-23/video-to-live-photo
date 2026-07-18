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
import livephoto.ui.worker as worker_module
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
    assert window.start_spin.text() == "00:00.00"
    assert window.duration_spin.text() == "00:03.00"
    assert window.quality_combo.currentData() == "balanced"
    assert window.segment_list.count() == 1
    assert window.segment_list.currentRow() == 0
    assert window.remove_segment_button.isEnabled() is False
    assert set(window.target_checks) == {"iphone", "android", "vivo", "windows"}
    assert all(not box.isChecked() for box in window.target_checks.values())
    assert window.convert_button.text() == "生成所选设备的 Live 图"
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
    assert window.convert_button.isEnabled() is False
    window.target_checks["vivo"].setChecked(True)
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
        assert window.convert_button.isEnabled() is False
        window.target_checks["vivo"].setChecked(True)
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


def test_segments_can_be_added_switched_and_deleted(app, tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    window = MainWindow()
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(tmp_path / "out"))
    window.apply_video_info(VideoInfo(20.0, 1920, 1080, 30.0, True))

    window.start_spin.setValue(2.0)
    window.duration_spin.setValue(3.0)
    window.cover_spin.setValue(3.0)
    window.add_segment()

    assert window.segment_list.count() == 2
    assert window.segment_list.currentRow() == 1
    assert window.start_spin.value() == pytest.approx(5.0)
    assert window.duration_spin.value() == pytest.approx(3.0)
    assert window.cover_spin.value() == pytest.approx(6.5)
    assert window.convert_button.text() == "生成 2 个片段的 Live 图"

    window.segment_list.setCurrentRow(0)
    assert window.start_spin.value() == pytest.approx(2.0)
    assert window.cover_spin.value() == pytest.approx(3.0)

    window.remove_segment()
    assert window.segment_list.count() == 1
    assert window.remove_segment_button.isEnabled() is False
    window.close()


def test_conversion_options_include_every_segment_and_selected_target(app, tmp_path: Path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    window = MainWindow()
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(tmp_path / "out"))
    window.apply_video_info(VideoInfo(20.0, 1920, 1080, 30.0, True))
    window.target_checks["vivo"].setChecked(True)
    window.target_checks["windows"].setChecked(True)
    window.add_segment()

    options = window._build_conversion_options()

    assert len(options) == 2
    assert [item.segment_label for item in options] == ["片段01", "片段02"]
    assert all(item.targets == frozenset({"vivo", "windows"}) for item in options)
    assert all(item.output_dir == tmp_path / "out" for item in options)
    window.close()


def test_busy_state_disables_editing_and_exposes_cancel(app):
    window = MainWindow()
    window.set_busy(True)
    assert window.convert_button.isEnabled() is False
    assert window.cancel_button.isEnabled() is True
    assert window.input_edit.isEnabled() is False
    assert window.segment_list.isEnabled() is False
    assert window.add_segment_button.isEnabled() is False
    assert all(not box.isEnabled() for box in window.target_checks.values())
    window.set_busy(False)
    assert window.cancel_button.isEnabled() is False
    assert window.input_edit.isEnabled() is True
    assert window.segment_list.isEnabled() is True
    assert window.add_segment_button.isEnabled() is True
    window.close()


def test_conversion_worker_emits_progress_and_completion(tmp_path: Path):
    bundle = OutputBundle(
        tmp_path,
        (),
        tmp_path / "manifest.json",
        tmp_path / "使用说明.txt",
    )

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


def _batch_bundle(tmp_path: Path, name: str) -> OutputBundle:
    directory = tmp_path / name
    return OutputBundle(
        directory,
        (),
        directory / "manifest.json",
        directory / "使用说明.txt",
    )


def test_batch_conversion_worker_runs_segments_and_aggregates_progress(tmp_path: Path):
    first = _batch_bundle(tmp_path, "first")
    second = _batch_bundle(tmp_path, "second")
    options = (type("Option", (), {"segment_label": "片段01"})(), type("Option", (), {"segment_label": "片段02"})())
    calls = []

    class FakeConverter:
        def convert(self, option, progress, cancel):
            calls.append(option.segment_label)
            assert cancel() is False
            progress(0, "开始")
            progress(50, "处理中")
            progress(100, "完成")
            return first if option.segment_label == "片段01" else second

    worker = worker_module.BatchConversionWorker(FakeConverter(), options)
    progress = []
    completed = []
    worker.progress.connect(lambda value, text: progress.append((value, text)))
    worker.completed.connect(completed.append)

    worker.run()

    assert calls == ["片段01", "片段02"]
    assert progress == [
        (0, "[片段 1/2] 开始"),
        (25, "[片段 1/2] 处理中"),
        (50, "[片段 1/2] 完成"),
        (50, "[片段 2/2] 开始"),
        (75, "[片段 2/2] 处理中"),
        (100, "[片段 2/2] 完成"),
    ]
    assert completed == [(first, second)]


def test_batch_conversion_worker_reports_failed_segment(tmp_path: Path):
    first = _batch_bundle(tmp_path, "first")
    options = (object(), object(), object())
    calls = []

    class FakeConverter:
        def convert(self, option, progress, cancel):
            calls.append(option)
            if len(calls) == 2:
                raise RuntimeError("planned failure")
            return first

    worker = worker_module.BatchConversionWorker(FakeConverter(), options)
    failed = []
    worker.failed.connect(failed.append)

    worker.run()

    assert calls == list(options[:2])
    assert failed == ["片段 2：planned failure"]


def test_batch_conversion_worker_cancel_stops_remaining_segments(tmp_path: Path):
    first = _batch_bundle(tmp_path, "first")
    options = (object(), object())
    calls = []

    class FakeConverter:
        def convert(self, option, progress, cancel):
            calls.append(option)
            worker.cancel()
            return first

    worker = worker_module.BatchConversionWorker(FakeConverter(), options)
    failed = []
    worker.failed.connect(failed.append)

    worker.run()

    assert calls == [options[0]]
    assert failed == ["用户取消了转换"]
