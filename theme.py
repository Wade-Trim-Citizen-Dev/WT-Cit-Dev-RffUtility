"""Shared visual theme for the RFF Utilities UI.

A single light, flat theme applied application-wide via ``app.setStyleSheet``.
Colors are also exported as constants so non-QSS surfaces (the pyqtgraph plot,
the empty-list placeholder) can stay consistent with the rest of the UI.
"""

# --- Palette ---------------------------------------------------------------
ACCENT = "#2E8B57"          # primary action / brand green
ACCENT_HOVER = "#37A06A"
ACCENT_PRESSED = "#256F46"
ACCENT_SOFT = "#E4F1EA"     # selected-row / subtle accent fill

BG = "#F4F6F8"              # window background
SURFACE = "#FFFFFF"         # cards, inputs, lists
BORDER = "#DCDFE4"
HOVER = "#F0F2F5"
PRESSED = "#E6E8EB"

TEXT = "#2B2B2B"
TEXT_MUTED = "#6B7280"
PLACEHOLDER = "#9AA0A6"

STYLESHEET = f"""
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    color: {TEXT};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}}

QLabel#title {{
    font-size: 17pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#subtitle, QLabel#sectionHint, QLabel#statusLabel {{
    color: {TEXT_MUTED};
    font-size: 9pt;
}}

QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 2px 6px;
    color: {TEXT_MUTED};
}}

QListWidget, QTableWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 8px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background: {HOVER};
}}
QListWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}

QLineEdit {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
}}
QPushButton:hover {{
    background: {HOVER};
}}
QPushButton:pressed {{
    background: {PRESSED};
}}
QPushButton:disabled {{
    color: {PLACEHOLDER};
    background: {BG};
}}

QPushButton#mergeButton {{
    background: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#mergeButton:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#mergeButton:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton#mergeButton:disabled {{
    background: #A9CBB8;
    color: #F0F0F0;
}}

QProgressBar {{
    background: {PRESSED};
    border: none;
    border-radius: 5px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 5px;
}}

QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    min-width: 120px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QHeaderView::section {{
    background: {HOVER};
    color: {TEXT_MUTED};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}
QTableWidget {{
    gridline-color: #EEF0F2;
    alternate-background-color: #F7F9FA;
}}
QTableWidget::item {{
    padding: 6px 8px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C7CCD2;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEB4BC;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
