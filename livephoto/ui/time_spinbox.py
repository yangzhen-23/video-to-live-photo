# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import math
import re

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QDoubleSpinBox


def format_time(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("时间必须是非负有限数值")
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, fraction = divmod(remainder, 100)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"
    return f"{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def parse_time(text: str) -> float:
    value = text.strip()
    if not value:
        raise ValueError("时间不能为空")
    parts = value.split(":")
    try:
        if len(parts) == 1:
            result = float(parts[0])
        elif len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            if minutes < 0 or not 0 <= seconds < 60:
                raise ValueError("分或秒超出范围")
            result = minutes * 60 + seconds
        elif len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                raise ValueError("时、分或秒超出范围")
            result = hours * 3600 + minutes * 60 + seconds
        else:
            raise ValueError("时间格式无效")
    except (TypeError, ValueError) as exc:
        raise ValueError("时间格式无效") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("时间必须是非负有限数值")
    return result


class TimeSpinBox(QDoubleSpinBox):
    _PARTIAL = re.compile(r"^\d*(?::\d*){0,2}(?:\.\d{0,2})?$")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDecimals(2)
        self.setSingleStep(0.1)
        self.setRange(0.0, 99_999.0)
        self.setGroupSeparatorShown(False)

    def textFromValue(self, value: float) -> str:
        return format_time(value)

    def valueFromText(self, text: str) -> float:
        return parse_time(text)

    def validate(
        self, text: str, position: int
    ) -> tuple[QValidator.State, str, int]:
        try:
            value = parse_time(text)
        except ValueError:
            state = (
                QValidator.State.Intermediate
                if self._PARTIAL.fullmatch(text.strip())
                else QValidator.State.Invalid
            )
            return state, text, position
        state = (
            QValidator.State.Acceptable
            if self.minimum() <= value <= self.maximum()
            else QValidator.State.Invalid
        )
        return state, text, position

    def fixup(self, text: str) -> str:
        try:
            return format_time(parse_time(text))
        except ValueError:
            return format_time(self.value())
