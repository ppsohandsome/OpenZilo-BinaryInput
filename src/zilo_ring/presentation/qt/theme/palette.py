from __future__ import annotations

from .typography import UI_FONT_FAMILY


BACKGROUND = "#000000"
SURFACE = "#050505"
SURFACE_RAISED = "#0b0a0b"
BORDER = "#242124"
GRID = "#191719"
GRID_STRONG = "#393438"
TEXT = "#f5f2f4"
MUTED = "#928a8e"
ACCENT = "#f04468"
ACCENT_HOVER = "#ff5d7c"
ACCENT_DARK = "#260d15"
SUCCESS = "#247a59"
DANGER = "#b73552"
AXIS_RED = "#f25776"
AXIS_GREEN = "#55d6a2"
AXIS_BLUE = "#6aa9ff"


def application_stylesheet() -> str:
    return f"""
        QMainWindow, QWidget {{
            background: {BACKGROUND};
            color: {TEXT};
            font-family: "{UI_FONT_FAMILY}";
            font-size: 13px;
        }}
        QFrame {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 2px;
        }}
        QLabel {{ border: none; }}
        #title {{
            color: {TEXT};
            border: none;
            letter-spacing: 2px;
        }}
        #sectionHeader {{
            background: {ACCENT_DARK};
            border: 1px solid {BORDER};
            border-left: 2px solid {ACCENT};
            border-radius: 1px;
        }}
        #sectionHeader QLabel {{
            background: transparent;
        }}
        #navigation {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 2px;
            padding: 10px;
            outline: none;
        }}
        #navigation::item {{
            color: {MUTED};
            padding: 11px 12px;
            margin: 2px 0;
            border: 1px solid transparent;
            border-radius: 1px;
        }}
        #navigation::item:hover {{
            background: {SURFACE_RAISED};
            color: {TEXT};
        }}
        #navigation::item:selected {{
            background: {ACCENT_DARK};
            color: {TEXT};
            border-left: 2px solid {ACCENT};
        }}
        #workspaceSplitter::handle {{ background: {BACKGROUND}; }}
        QPushButton {{
            background: {SURFACE_RAISED};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 1px;
            min-height: 32px;
            padding: 0 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background: #13080c;
            border-color: {ACCENT};
        }}
        QPushButton:pressed {{
            background: {ACCENT_DARK};
            border-color: {ACCENT_HOVER};
        }}
        QPushButton:disabled {{
            color: #514b4e;
            background: #070707;
            border-color: #181618;
        }}
        QPushButton#seriesToggle:checked {{
            background: {SUCCESS};
            border-color: {SUCCESS};
            color: white;
        }}
        QPushButton#seriesToggle:unchecked {{
            background: {DANGER};
            border-color: {DANGER};
            color: white;
        }}
        QPushButton#seriesToggle:hover {{
            border-color: {TEXT};
        }}
        QLineEdit, QComboBox {{
            background: {BACKGROUND};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: 1px;
            min-height: 32px;
            padding: 0 12px;
            font-weight: 400;
            selection-background-color: {ACCENT_DARK};
        }}
        QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
        QComboBox::drop-down {{
            border: none;
            width: 22px;
        }}
        QComboBox QAbstractItemView {{
            background: {SURFACE_RAISED};
            color: {TEXT};
            border: 1px solid {BORDER};
            selection-background-color: {ACCENT_DARK};
            outline: none;
        }}
        #statusBadge {{
            background: {SURFACE_RAISED};
            color: {MUTED};
            border: 1px solid {BORDER};
            border-radius: 1px;
            min-height: 24px;
            padding: 0 10px;
            font-weight: 500;
        }}
        #statusBadge[streaming="true"] {{
            background: {SUCCESS};
            color: #effff8;
        }}
        #batteryStatus {{
            background: {SURFACE_RAISED};
            color: {MUTED};
            border: 1px solid {BORDER};
            border-radius: 1px;
            min-height: 24px;
            padding: 0 10px;
        }}
        QToolTip {{
            background: {SURFACE_RAISED};
            color: {TEXT};
            border: 1px solid {ACCENT_DARK};
            padding: 5px;
        }}
    """
