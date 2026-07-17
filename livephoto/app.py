# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import sys

from .qt_compat import prepare_qt_runtime

prepare_qt_runtime()

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(arguments)
    app.setApplicationName("视频转 Live 图")
    app.setOrganizationName("Local Tools")
    window = MainWindow()
    window.show()
    if "--smoke-test" in arguments:
        QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
