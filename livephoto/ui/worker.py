# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot


class ProbeWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, probe_fn, path, toolchain) -> None:
        super().__init__()
        self.probe_fn = probe_fn
        self.path = path
        self.toolchain = toolchain

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self.probe_fn(self.path, self.toolchain))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ConversionWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, converter, options) -> None:
        super().__init__()
        self.converter = converter
        self.options = options
        self._cancel = Event()

    @Slot()
    def run(self) -> None:
        try:
            result = self.converter.convert(
                self.options,
                progress=self.progress.emit,
                cancel=self._cancel.is_set,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    @Slot()
    def cancel(self) -> None:
        self._cancel.set()


class BatchConversionWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, converter, options) -> None:
        super().__init__()
        self.converter = converter
        self.options = tuple(options)
        self._cancel = Event()

    @Slot()
    def run(self) -> None:
        bundles = []
        total = len(self.options)
        try:
            if total == 0:
                raise ValueError("没有可转换的片段")
            for index, option in enumerate(self.options):
                if self._cancel.is_set():
                    raise RuntimeError("用户取消了转换")
                prefix = f"[片段 {index + 1}/{total}]"

                def relay(value: int, text: str, *, item=index, label=prefix) -> None:
                    overall = round((item + value / 100) / total * 100)
                    self.progress.emit(overall, f"{label} {text}")

                bundle = self.converter.convert(
                    option,
                    progress=relay,
                    cancel=self._cancel.is_set,
                )
                bundles.append(bundle)
            self.completed.emit(tuple(bundles))
        except Exception as exc:
            original = str(exc)
            message = (
                original
                if "取消" in original
                else f"片段 {len(bundles) + 1}：{original}"
            )
            self.failed.emit(message)
        finally:
            self.finished.emit()

    @Slot()
    def cancel(self) -> None:
        self._cancel.set()
