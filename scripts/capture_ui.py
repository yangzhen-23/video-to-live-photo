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

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="保存 UI 验证截图")
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--dialog",
        action="store_true",
        help="截取强制深色系统调色板下的完成弹窗",
    )
    return parser


def _apply_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1f1f1f"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f3f4f6"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#191919"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f3f4f6"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#252525"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f3f4f6"))
    app.setPalette(palette)


def main() -> None:
    args = build_parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    load_capture_font(app)
    if args.dialog:
        _apply_dark_palette(app)
    window = MainWindow()
    window.show()
    app.processEvents()
    target = window
    dialog = None
    if args.dialog:
        dialog = QMessageBox(window)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle("转换完成")
        dialog.setText("已生成 2 个独立片段。\n可点击“打开成品文件夹”查看。")
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.show()
        app.processEvents()
        target = dialog
    if not target.grab().save(str(args.output)):
        raise RuntimeError("UI 截图保存失败")
    if dialog is not None:
        dialog.close()
    window.close()
    print(args.output)


if __name__ == "__main__":
    main()
