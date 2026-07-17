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
