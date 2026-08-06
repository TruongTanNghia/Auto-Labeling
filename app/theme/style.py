"""Dark Fluent stylesheet - sinh dong tu bang mau trong constants."""
from __future__ import annotations

import re

from PySide6.QtGui import QColor

from app.constants import COLORS

_QSS = """
/* ============================================================ CO BAN === */
* { outline: none; }

QWidget {
    background: transparent;
    color: @text@;
    font-family: "Segoe UI Variable Display", "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}

QMainWindow, #RootFrame { background: @bg@; }

QToolTip {
    background: @surface_hi@;
    color: @text@;
    border: 1px solid @border_hi@;
    border-radius: 6px;
    padding: 6px 9px;
}

/* ========================================================= TITLE BAR === */
#TitleBar { background: @bg_alt@; border-bottom: 1px solid @border@; }
#TitleBarTitle { color: @text_dim@; font-size: 12.5px; font-weight: 600; letter-spacing: 0.3px; }
#WinBtn {
    background: transparent; border: none; border-radius: 6px;
    min-width: 34px; max-width: 34px; min-height: 28px; max-height: 28px;
}
#WinBtn:hover { background: @surface_hi@; }
#WinBtnClose:hover { background: #E5484D; }

/* =========================================================== SIDEBAR === */
#Sidebar { background: @bg_alt@; border-right: 1px solid @border@; }
#BrandName { font-size: 15.5px; font-weight: 800; color: @text@; letter-spacing: 0.2px; }
#BrandSub { font-size: 10.5px; color: @text_mute@; letter-spacing: 0.2px; }

#NavButton {
    background: transparent;
    border: none;
    border-radius: 10px;
    color: @text_dim@;
    text-align: left;
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 500;
}
#NavButton:hover { background: @surface@; color: @text@; }
#NavButton:checked {
    background: @accent_soft@;
    color: #FFFFFF;
    font-weight: 650;
}

#NavIndex {
    background: @surface_hi@; color: @text_mute@;
    border-radius: 9px; min-width: 18px; max-width: 18px;
    min-height: 18px; max-height: 18px;
    font-size: 10px; font-weight: 700;
}

#SidebarFooter { color: @text_mute@; font-size: 11px; }

/* ============================================================= CARD === */
#Card {
    background: @surface@;
    border: 1px solid @border@;
    border-radius: 14px;
}
#CardFlat { background: @surface_alt@; border: 1px solid @border@; border-radius: 12px; }
#CardTitle { font-size: 14.5px; font-weight: 700; color: @text@; }
#CardSubtitle { font-size: 11.5px; color: @text_mute@; }
#SectionLabel {
    font-size: 10.5px; font-weight: 700; color: @text_mute@;
    letter-spacing: 1.1px;
}
#PageTitle { font-size: 21px; font-weight: 800; color: @text@; }
#PageSubtitle { font-size: 12.5px; color: @text_mute@; }
#Hint { color: @text_mute@; font-size: 11.5px; }
#StatValue { font-size: 22px; font-weight: 800; color: @text@; }
#StatLabel { font-size: 11.5px; color: @text_mute@; font-weight: 600; }
#BigNumber { font-size: 26px; font-weight: 800; color: @accent_hi@; }

QFrame[frameShape="4"], QFrame[frameShape="5"] { color: @border@; }
#Divider { background: @border@; max-height: 1px; border: none; }
#VDivider { background: @border@; max-width: 1px; border: none; }

/* =========================================================== BUTTON === */
QPushButton {
    background: @surface_hi@;
    color: @text@;
    border: 1px solid @border_hi@;
    border-radius: 9px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover { background: #30304A; border-color: #45455F; }
QPushButton:pressed { background: #24243A; }
QPushButton:disabled { background: @surface_alt@; color: @text_mute@; border-color: @border@; }

QPushButton#Primary {
    background: @accent@; color: #FFFFFF; border: 1px solid @accent@;
}
QPushButton#Primary:hover { background: @accent_hi@; border-color: @accent_hi@; }
QPushButton#Primary:pressed { background: @accent_dim@; }
QPushButton#Primary:disabled { background: #3A3358; color: #8A85A8; border-color: #3A3358; }

QPushButton#Success { background: @success@; color: #07281A; border: 1px solid @success@; }
QPushButton#Success:hover { background: #56E5A0; }
QPushButton#Danger { background: @danger@; color: #FFFFFF; border: 1px solid @danger@; }
QPushButton#Danger:hover { background: #FF6C84; }
QPushButton#Warning { background: @warning@; color: #2A1A00; border: 1px solid @warning@; }

/* Trang thai vo hieu hoa phai thay ro o moi loai nut */
QPushButton#Success:disabled, QPushButton#Danger:disabled,
QPushButton#Warning:disabled, QPushButton#Ghost:disabled,
QPushButton#Chip:disabled, QPushButton#Tool:disabled {
    background: @surface_alt@; color: @text_mute@; border: 1px solid @border@;
}

QPushButton#Ghost {
    background: transparent; border: 1px solid @border_hi@; color: @text_dim@;
}
QPushButton#Ghost:hover { background: @surface_hi@; color: @text@; }

QPushButton#Link {
    background: transparent; border: none; color: @accent_hi@;
    padding: 2px 4px; font-weight: 600; text-decoration: underline;
}
QPushButton#Link:hover { color: #B9A6FF; }

QPushButton#IconBtn {
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 6px; min-width: 30px; min-height: 30px;
}
QPushButton#IconBtn:hover { background: @surface_hi@; border-color: @border_hi@; }
QPushButton#IconBtn:checked { background: @accent_soft@; border-color: @accent@; }

QPushButton#Chip {
    background: @surface_alt@; border: 1px solid @border@; border-radius: 8px;
    padding: 6px 11px; font-size: 12px; font-weight: 600; color: @text_dim@;
}
QPushButton#Chip:hover { border-color: @accent@; color: @text@; }
QPushButton#Chip:checked { background: @accent_soft@; border-color: @accent@; color: #FFFFFF; }

QPushButton#Tool {
    background: transparent; border: 1px solid @border@; border-radius: 8px;
    padding: 6px 10px; color: @text_dim@; font-weight: 600; font-size: 12px;
}
QPushButton#Tool:hover { background: @surface_hi@; color: @text@; }
QPushButton#Tool:checked { background: @accent_soft@; border-color: @accent@; color: #FFFFFF; }

QPushButton#SubTab {
    background: transparent; border: none; border-radius: 8px;
    padding: 8px 12px; text-align: left; color: @text_dim@; font-weight: 600;
}
QPushButton#SubTab:hover { background: @surface_hi@; color: @text@; }
QPushButton#SubTab:checked { background: @accent_soft@; color: #FFFFFF; }

/* ============================================================ INPUT === */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: @bg_alt@;
    border: 1px solid @border@;
    border-radius: 8px;
    padding: 7px 10px;
    color: @text@;
    selection-background-color: @accent@;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: @border_hi@; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: @accent@; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: @text_mute@; background: @surface_alt@;
}
QLineEdit[readOnly="true"] { color: @text_dim@; }

QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: @surface_alt@;
    border: 1px solid @border_hi@;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: @accent_soft@;
    selection-color: #FFFFFF;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background: @surface_hi@; border: none; width: 16px; margin: 2px;
    border-radius: 4px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover { background: @accent@; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("@arrow_up@"); width: 9px; height: 9px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("@arrow_down@"); width: 9px; height: 9px;
}
QComboBox::down-arrow { image: url("@arrow_down@"); width: 11px; height: 11px; }

#SearchBox { padding-left: 32px; border-radius: 9px; }

/* ========================================================= CHECKBOX === */
QCheckBox, QRadioButton { spacing: 8px; color: @text_dim@; }
QCheckBox::indicator, QRadioButton::indicator { width: 17px; height: 17px; }
QCheckBox::indicator {
    border: 1.5px solid @border_hi@; border-radius: 5px; background: @bg_alt@;
}
QCheckBox::indicator:hover { border-color: @accent@; }
QCheckBox::indicator:checked {
    background: @accent@; border-color: @accent@;
    image: url("@check_icon@");
}
QCheckBox::indicator:indeterminate { background: @accent_dim@; border-color: @accent@; }
QRadioButton::indicator { border: 1.5px solid @border_hi@; border-radius: 9px; background: @bg_alt@; }
QRadioButton::indicator:checked { border: 5px solid @accent@; background: @bg_alt@; }

/* =========================================================== SLIDER === */
QSlider::groove:horizontal { height: 4px; background: @surface_hi@; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @accent@; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #FFFFFF; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
    border: 2px solid @accent@;
}
QSlider::handle:horizontal:hover { background: @accent_hi@; }
QSlider::groove:vertical { width: 4px; background: @surface_hi@; border-radius: 2px; }
QSlider::handle:vertical { background: #FFFFFF; height: 14px; margin: 0 -6px; border-radius: 7px; }

/* ========================================================= PROGRESS === */
QProgressBar {
    background: @surface_hi@; border: none; border-radius: 5px;
    height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background: @accent@; border-radius: 5px; }
QProgressBar#Thin { height: 5px; border-radius: 3px; }
QProgressBar#Thin::chunk { border-radius: 3px; }

/* ============================================================ LISTS === */
QListWidget, QTreeWidget, QTableWidget, QListView, QTreeView, QTableView {
    background: @bg_alt@;
    border: 1px solid @border@;
    border-radius: 10px;
    outline: none;
    alternate-background-color: #16161F;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px 8px; border-radius: 7px; color: @text_dim@;
}
QListWidget::item:hover, QTreeWidget::item:hover { background: @surface@; }
QListWidget::item:selected, QTreeWidget::item:selected {
    background: @accent_soft@; color: #FFFFFF;
}
QTableWidget::item, QTableView::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected, QTableView::item:selected { background: @accent_soft@; color: #FFFFFF; }

QHeaderView::section {
    background: @surface_alt@;
    color: @text_mute@;
    border: none;
    border-bottom: 1px solid @border@;
    border-right: 1px solid @border@;
    padding: 8px 10px;
    font-size: 11.5px;
    font-weight: 700;
}
QHeaderView::section:hover { color: @text@; }
QTableCornerButton::section { background: @surface_alt@; border: none; }

/* ======================================================= SCROLLBARS === */
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: #33334A; min-height: 30px; border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: @accent_dim@; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 2px 2px 2px; }
QScrollBar::handle:horizontal { background: #33334A; min-width: 30px; border-radius: 5px; }
QScrollBar::handle:horizontal:hover { background: @accent_dim@; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: none; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QScrollArea { border: none; background: transparent; }

/* ============================================================= TABS === */
QTabWidget::pane { border: 1px solid @border@; border-radius: 12px; top: -1px; background: @surface@; }
QTabBar::tab {
    background: transparent; color: @text_mute@;
    padding: 8px 16px; margin-right: 4px;
    border-top-left-radius: 9px; border-top-right-radius: 9px;
    font-weight: 600;
}
QTabBar::tab:hover { color: @text@; }
QTabBar::tab:selected { background: @surface@; color: #FFFFFF; border: 1px solid @border@; border-bottom: none; }

/* ============================================================ SPLIT === */
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 6px; }
QSplitter::handle:vertical { height: 6px; }
QSplitter::handle:hover { background: @accent_soft@; }

/* ============================================================ MENUS === */
QMenu {
    background: @surface_alt@; border: 1px solid @border_hi@;
    border-radius: 10px; padding: 6px;
}
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 7px; color: @text_dim@; }
QMenu::item:selected { background: @accent_soft@; color: #FFFFFF; }
QMenu::separator { height: 1px; background: @border@; margin: 5px 8px; }

QMenuBar { background: @bg_alt@; }
QMenuBar::item { padding: 6px 11px; border-radius: 7px; color: @text_dim@; }
QMenuBar::item:selected { background: @surface_hi@; color: @text@; }

/* ========================================================== DIALOGS === */
QDialog { background: @bg@; }
QMessageBox { background: @surface@; }
QMessageBox QLabel { color: @text@; }

/* ========================================================== BADGES ==== */
#Badge {
    border-radius: 8px; padding: 3px 9px; font-size: 11px; font-weight: 700;
}
#StatusDot { border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px; }

#LogView {
    background: #0B0B12; border: 1px solid @border@; border-radius: 10px;
    font-family: "Cascadia Mono", "JetBrains Mono", "Consolas", monospace;
    font-size: 11.5px; color: #B9B9CF; padding: 8px;
}

#Canvas { background: #0A0A10; border: 1px solid @border@; border-radius: 12px; }
#ThumbList { background: @bg_alt@; border: 1px solid @border@; border-radius: 10px; }
"""


def build_stylesheet(accent: str | None = None) -> str:
    colors = dict(COLORS)
    if accent:
        colors["accent"] = accent
        colors["accent_hi"] = _shift(accent, 1.22)
        colors["accent_dim"] = _shift(accent, 0.78)
        colors["accent_soft"] = _mix(accent, COLORS["bg"], 0.26)
    qss = (_QSS
           .replace("@check_icon@", _asset("check_white.png", "check", "#FFFFFF", 14, 3.0))
           .replace("@arrow_up@", _asset("chev_up.png", "chevron_up",
                                         COLORS["text_dim"], 12, 2.6))
           .replace("@arrow_down@", _asset("chev_down.png", "chevron_down",
                                           COLORS["text_dim"], 12, 2.6)))
    for key, val in colors.items():
        qss = qss.replace(f"@{key}@", val)
    # Don sach token con sot (neu co)
    qss = re.sub(r"@[a-z_]+@", COLORS["text"], qss)
    return qss


def _asset(filename: str, icon_name: str, color: str, size: int,
           stroke: float) -> str:
    """Sinh (mot lan) file PNG cho cac phan tu ma QSS chi nhan qua url()."""
    from app.theme.icons import pixmap
    from app.utils.paths import ensure_dir, user_data_dir

    path = ensure_dir(user_data_dir() / "cache") / filename
    if not path.exists():
        pixmap(icon_name, color, size, stroke=stroke, dpr=2.0).save(str(path), "PNG")
    return str(path).replace("\\", "/")


def _shift(hex_color: str, factor: float) -> str:
    c = QColor(hex_color)
    h, s, v, a = c.getHsv()
    c.setHsv(h, s, max(0, min(255, int(v * factor))), a)
    return c.name()


def _mix(a: str, b: str, ratio: float) -> str:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() * ratio + cb.red() * (1 - ratio)),
        int(ca.green() * ratio + cb.green() * (1 - ratio)),
        int(ca.blue() * ratio + cb.blue() * (1 - ratio)),
    ).name()
