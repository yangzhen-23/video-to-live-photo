# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 杨振
from __future__ import annotations

import pytest

from livephoto.qt_compat import prepare_qt_runtime

prepare_qt_runtime()

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

from livephoto.ui.time_spinbox import TimeSpinBox, format_time, parse_time


@pytest.fixture(scope="session")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0.0, "00:00.00"),
        (3.0, "00:03.00"),
        (85.5, "01:25.50"),
        (3599.99, "59:59.99"),
        (3723.5, "01:02:03.50"),
    ],
)
def test_format_time_uses_sexagesimal_notation(seconds: float, text: str):
    assert format_time(seconds) == text


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("01:25.50", 85.5),
        ("75:00", 4500.0),
        ("01:02:03.50", 3723.5),
        ("3.25", 3.25),
    ],
)
def test_parse_time_accepts_colon_and_legacy_seconds(text: str, seconds: float):
    assert parse_time(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", ["", "-1", "00:60", "01:60:00", "a:b"])
def test_parse_time_rejects_invalid_values(text: str):
    with pytest.raises(ValueError):
        parse_time(text)


def test_time_spin_box_round_trips_seconds_and_text(app):
    spin = TimeSpinBox()
    spin.setValue(85.5)

    assert spin.text() == "01:25.50"
    assert spin.valueFromText("02:03.40") == pytest.approx(123.4)
    assert spin.singleStep() == pytest.approx(0.1)
    assert spin.decimals() == 2


def test_time_spin_box_marks_partial_input_as_intermediate(app):
    spin = TimeSpinBox()

    state, _text, _position = spin.validate("01:", 3)

    assert state == QValidator.State.Intermediate
