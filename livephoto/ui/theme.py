# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
APP_STYLE = r"""
QMainWindow, QWidget#root, QWidget#scrollContent { background: #f4f7fb; color: #17233c; }
QWidget { color: #17233c; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
QScrollArea { border: none; background: #f4f7fb; }
QScrollArea > QWidget > QWidget { background: #f4f7fb; }
QFrame#card { background: #ffffff; border: 1px solid #dfe7f1; border-radius: 16px; }
QLabel#appTitle { font-size: 30px; font-weight: 700; color: #10213d; }
QLabel#subtitle { color: #66758f; font-size: 14px; }
QLabel#stepBadge {
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;
    border-radius: 15px; background: #1769e0; color: white; font-weight: 700;
}
QLabel#cardTitle { font-size: 18px; font-weight: 650; color: #17233c; }
QLabel#cardHint { color: #7a879e; }
QFrame#dropArea {
    border: 2px dashed #a9bbd4; border-radius: 12px; background: #f8fbff;
}
QFrame#dropArea:hover { border-color: #1769e0; background: #f1f7ff; }
QLabel#dropIcon { color: #1769e0; font-size: 28px; font-weight: 600; }
QLabel#dropText { color: #4f607b; }
QLineEdit, QDoubleSpinBox, QComboBox, QTextEdit {
    background: #f9fbfd; border: 1px solid #cfd9e7; border-radius: 8px;
    padding: 8px; color: #263650; selection-background-color: #1769e0;
}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #1769e0; background: #ffffff;
}
QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QTextEdit:disabled {
    color: #718096; background: #eef2f7; border-color: #dce3ec;
}
QPushButton {
    min-height: 36px; border-radius: 9px; padding: 0 18px;
    border: 1px solid #cbd6e5; background: #ffffff; color: #263650; font-weight: 600;
}
QPushButton:hover { background: #f1f6fc; border-color: #9db2ce; }
QPushButton:disabled { color: #9aa7ba; background: #eef2f7; border-color: #e0e6ee; }
QPushButton#primaryButton {
    min-height: 48px; border: none; border-radius: 12px;
    background: #1769e0; color: white; font-size: 16px; font-weight: 700;
}
QPushButton#primaryButton:hover { background: #0f5dcc; }
QPushButton#cancelButton { color: #b42318; border-color: #efc1bc; }
QProgressBar {
    min-height: 12px; max-height: 12px; border: none; border-radius: 6px;
    background: #e7edf5; text-align: center; color: transparent;
}
QProgressBar::chunk { border-radius: 6px; background: #19a995; }
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #dce5f0; }
QSlider::sub-page:horizontal { background: #1769e0; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 17px; height: 17px; margin: -6px 0; border-radius: 8px;
    background: #ffffff; border: 2px solid #1769e0;
}
QLabel#infoPill {
    color: #315272; background: #edf5ff; border-radius: 8px; padding: 7px 10px;
}
QLabel#statusLabel { color: #40516d; font-weight: 600; }
QCheckBox { spacing: 8px; color: #263650; }
QCheckBox:disabled { color: #718096; }
"""
