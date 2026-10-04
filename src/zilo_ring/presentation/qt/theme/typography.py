from __future__ import annotations

from PySide6.QtGui import QFont


UI_FONT_FAMILY = "Noto Sans CJK SC"
DATA_FONT_FAMILY = "Noto Sans Mono CJK SC"


def ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(UI_FONT_FAMILY, size, weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def data_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(DATA_FONT_FAMILY, size, weight)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
