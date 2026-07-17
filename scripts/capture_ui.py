# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from livephoto.qt_compat import prepare_qt_runtime

prepare_qt_runtime()

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from livephoto.ui.main_window import MainWindow


def load_capture_font(app: QApplication) -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidates = (
        system_root / "Fonts" / "msyh.ttc",
        system_root / "Fonts" / "Deng.ttf",
        system_root / "Fonts" / "simhei.ttf",
    )
    for path in candidates:
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            family = families[0]
            app.setFont(QFont(family, 10))
            return family
    raise RuntimeError("无法加载用于 UI 截图的中文字体")


def main() -> None:
    parser = argparse.ArgumentParser(description="保存 UI 验证截图")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    load_capture_font(app)
    window = MainWindow()
    window.show()
    app.processEvents()
    if not window.grab().save(str(args.output)):
        raise RuntimeError("UI 截图保存失败")
    window.close()
    print(args.output)


if __name__ == "__main__":
    main()
