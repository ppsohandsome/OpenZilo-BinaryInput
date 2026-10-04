from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from zilo_ring.domain import (
    DOWN_DOUBLE,
    DOWN_SINGLE,
    UP_SINGLE,
    DetectedAction,
    MorseDecoder,
)
from zilo_ring.presentation.qt.theme import (
    ACCENT,
    BORDER,
    DANGER,
    MUTED,
    SURFACE_RAISED,
    data_font,
    ui_font,
)
from zilo_ring.state import StoreSnapshot


ACTION_DISPLAY = {
    DOWN_SINGLE: "DOWN → 0",
    UP_SINGLE: "UP → 1",
    DOWN_DOUBLE: "DOUBLE DOWN → COMPILE",
}


class MorseInputPage(QWidget):
    page_id = "morse_input"
    title = "Morse Input"
    subtitle = "Down = 0 · Up = 1 · Double down = compile"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._decoder = MorseDecoder()
        self._seen_action_keys: set[tuple[int, int, str, str]] = set()

        self.bits_value = QLabel("—")
        self.bits_value.setFont(data_font(20, QFont.Weight.Medium))
        self.bits_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.symbols_value = QLabel("—")
        self.symbols_value.setFont(ui_font(18, QFont.Weight.Medium))
        self.text_value = QLabel("—")
        self.text_value.setFont(data_font(20, QFont.Weight.Medium))
        self.text_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        values = QGridLayout()
        values.setContentsMargins(0, 0, 0, 0)
        values.setHorizontalSpacing(16)
        values.setVerticalSpacing(8)
        values.addWidget(_field_label("BITS"), 0, 0)
        values.addWidget(self.bits_value, 0, 1)
        values.addWidget(_field_label("MORSE"), 0, 2)
        values.addWidget(self.symbols_value, 0, 3)
        values.addWidget(_field_label("TEXT"), 1, 0)
        values.addWidget(self.text_value, 1, 1, 1, 3)
        values.setColumnStretch(1, 1)
        values.setColumnStretch(3, 1)

        self.status = QLabel("Enter this page, then perform a gesture.")
        self.status.setStyleSheet(f"color: {MUTED};")

        self.undo_button = QPushButton("Undo bit")
        self.delete_button = QPushButton("Delete char")
        self.clear_button = QPushButton("Clear")
        self.copy_button = QPushButton("Copy text")
        for button in (
            self.undo_button,
            self.delete_button,
            self.clear_button,
            self.copy_button,
        ):
            button.setFixedWidth(112)
        self.undo_button.clicked.connect(self._undo_bit)
        self.delete_button.clicked.connect(self._delete_character)
        self.clear_button.clicked.connect(self._clear)
        self.copy_button.clicked.connect(self._copy_text)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(self.undo_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.clear_button)
        controls.addWidget(self.copy_button)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(values)
        layout.addWidget(self.status)
        layout.addLayout(controls)
        layout.addStretch(1)

    def activate(self, snapshot: StoreSnapshot) -> None:
        self._seen_action_keys = {
            _action_key(action) for action in snapshot.detected_actions
        }
        self.status.setText("Ready · waiting for a new recognized action")
        self.status.setStyleSheet(f"color: {MUTED};")

    def refresh(self, snapshot: StoreSnapshot) -> None:
        for action in snapshot.detected_actions:
            key = _action_key(action)
            if key in self._seen_action_keys:
                continue
            self._seen_action_keys.add(key)
            if not action.accepted or action.label not in ACTION_DISPLAY:
                continue
            self._decoder.feed(action.label)
            self._refresh_values()
            action_text = ACTION_DISPLAY[action.label]
            self.status.setText(
                f"{action_text} · conf {action.similarity:.2f} · "
                f"{self._decoder.message}"
            )
            color = DANGER if self._decoder.error else ACCENT
            self.status.setStyleSheet(f"color: {color};")

    def _undo_bit(self) -> None:
        self._decoder.undo_bit()
        self._refresh_values()
        self._show_decoder_message()

    def _delete_character(self) -> None:
        self._decoder.delete_character()
        self._refresh_values()
        self._show_decoder_message()

    def _clear(self) -> None:
        self._decoder.clear()
        self._refresh_values()
        self._show_decoder_message()

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self._decoder.text)
        self.status.setText("Translated text copied")
        self.status.setStyleSheet(f"color: {ACCENT};")

    def _refresh_values(self) -> None:
        self.bits_value.setText(self._decoder.bits or "—")
        self.symbols_value.setText(self._decoder.symbols or "—")
        self.text_value.setText(self._decoder.text or "—")

    def _show_decoder_message(self) -> None:
        color = DANGER if self._decoder.error else MUTED
        self.status.setText(self._decoder.message)
        self.status.setStyleSheet(f"color: {color};")


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFixedWidth(70)
    label.setStyleSheet(
        f"background: {SURFACE_RAISED}; color: {MUTED}; "
        f"border: 1px solid {BORDER}; padding: 5px 8px;"
    )
    return label


def _action_key(action: DetectedAction) -> tuple[int, int, str, str]:
    return (
        action.start_device_timestamp_ms,
        action.end_device_timestamp_ms,
        action.label,
        action.candidate_label,
    )
