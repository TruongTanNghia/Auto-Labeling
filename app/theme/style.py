"""Fluent stylesheet hỗ trợ chủ đề Tối / Sáng / Theo hệ thống."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QApplication

from app.config import cfg
from app.constants import COLORS, DARK_COLORS, LIGHT_COLORS

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
#NavButton:hover { background: @surface_hi@; color: @text@; }
#NavButton:checked {
    background: @accent_soft@;
    color: @accent@;
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
QPushButton:hover { background: @surface_alt@; border-color: @border_hi@; }
QPushButton:pressed { background: @border@; }
QPushButton:disabled { background: @surface_alt@; color: @text_mute@; border-color: @border@; }

QPushButton#Primary {
    background: @accent@; color: @primary_text@; border: 1px solid @accent@;
}
QPushButton#Primary:hover { background: @accent_hi@; border-color: @accent_hi@; }
QPushButton#Primary:pressed { background: @accent_dim@; }
QPushButton#Primary:disabled { background: @surface_alt@; color: @text_mute@; border-color: @border@; }

QPushButton#Success { background: @success@; color: @primary_text@; border: 1px solid @success@; }
QPushButton#Success:hover { opacity: 0.9; }
QPushButton#Danger { background: @danger@; color: @primary_text@; border: 1px solid @danger@; }
QPushButton#Danger:hover { opacity: 0.9; }
QPushButton#Warning { background: @warning@; color: #FFFFFF; border: 1px solid @warning@; }

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
QPushButton#Link:hover { color: @accent@; }

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
QPushButton#Chip:checked { background: @accent_soft@; border-color: @accent@; color: @accent@; }

QPushButton#Tool {
    background: transparent; border: 1px solid @border@; border-radius: 8px;
    padding: 6px 10px; color: @text_dim@; font-weight: 600; font-size: 12px;
}
QPushButton#Tool:hover { background: @surface_hi@; color: @text@; }
QPushButton#Tool:checked { background: @accent_soft@; border-color: @accent@; color: @accent@; }

QPushButton#SubTab {
    background: transparent; border: none; border-radius: 8px;
    padding: 8px 12px; text-align: left; color: @text_dim@; font-weight: 600;
}
QPushButton#SubTab:hover { background: @surface_hi@; color: @text@; }
QPushButton#SubTab:checked { background: @accent_soft@; color: @accent@; }

QPushButton#GalleryThumb {
    background: @surface_alt@; border: 1px solid @border@; border-radius: 6px;
    padding: 2px; min-width: 60px; max-width: 60px; min-height: 60px; max-height: 60px;
}
QPushButton#GalleryThumb:hover { border-color: @accent@; background: @surface_hi@; }

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
    selection-color: @text@;
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
    background: @bg_alt@; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
    border: 2px solid @accent@;
}
QSlider::handle:horizontal:hover { background: @accent_hi@; }
QSlider::groove:vertical { width: 4px; background: @surface_hi@; border-radius: 2px; }
QSlider::handle:vertical { background: @bg_alt@; height: 14px; margin: 0 -6px; border-radius: 7px; }

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
    alternate-background-color: @surface_alt@;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px 8px; border-radius: 7px; color: @text_dim@;
}
QListWidget::item:hover, QTreeWidget::item:hover { background: @surface_hi@; }
QListWidget::item:selected, QTreeWidget::item:selected {
    background: @accent_soft@; color: @text@;
}
QTableWidget::item, QTableView::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected, QTableView::item:selected { background: @accent_soft@; color: @text@; }

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
    background: @border_hi@; min-height: 30px; border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: @accent_dim@; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 2px 2px 2px; }
QScrollBar::handle:horizontal { background: @border_hi@; min-width: 30px; border-radius: 5px; }
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
QTabBar::tab:selected { background: @surface@; color: @text@; border: 1px solid @border@; border-bottom: none; }

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
QMenu::item:selected { background: @accent_soft@; color: @text@; }
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
    background: @log_bg@; border: 1px solid @border@; border-radius: 10px;
    font-family: "Cascadia Mono", "JetBrains Mono", "Consolas", monospace;
    font-size: 11.5px; color: @log_text@; padding: 8px;
}

#Canvas { background: @canvas_bg@; border: 1px solid @border@; border-radius: 12px; }
#ThumbList { background: @bg_alt@; border: 1px solid @border@; border-radius: 10px; }
"""


def resolve_theme(theme_setting: str | None = None) -> str:
    """Xác định chủ đề thực tế: 'Dark' hoặc 'Light'."""
    if not theme_setting:
        theme_setting = cfg.get("general.theme", "Dark")
    s = str(theme_setting).strip().lower()
    if s in ("system", "theo hệ thống", "theo he thong", "auto"):
        app = QGuiApplication.instance()
        if app is not None:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "Dark"
            elif scheme == Qt.ColorScheme.Light:
                return "Light"
        return "Dark"
    if s in ("light", "sáng", "sang"):
        return "Light"
    return "Dark"


def get_theme_colors(theme_setting: str | None = None) -> dict[str, str]:
    """Trả về bảng token màu sắc tương ứng với chủ đề đã resolve."""
    resolved = resolve_theme(theme_setting)
    return dict(LIGHT_COLORS) if resolved == "Light" else dict(DARK_COLORS)


def apply_theme(
    app: QApplication | None = None,
    theme_setting: str | None = None,
    accent: str | None = None,
) -> str:
    """Áp dụng chủ đề mới cho toàn bộ ứng dụng động (đổi nóng)."""
    from app.theme.icons import icon, pixmap

    if theme_setting is None:
        theme_setting = cfg.get("general.theme", "Dark")
    if accent is None:
        accent = cfg.get("general.accent", None)

    resolved = resolve_theme(theme_setting)
    tokens = get_theme_colors(resolved)

    # Cập nhật từ điển COLORS toàn cục
    COLORS.clear()
    COLORS.update(tokens)

    # Xoá cache icon
    pixmap.cache_clear()
    icon.cache_clear()

    # Dọn dẹp cache file asset (png)
    from app.utils.paths import user_data_dir

    cache_dir = user_data_dir() / "cache"
    if cache_dir.exists():
        for f in cache_dir.glob("*.png"):
            try:
                f.unlink()
            except Exception:
                pass

    qss = build_stylesheet(accent=accent, theme_name=resolved)

    if app is None:
        app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(qss)

    return qss


def build_stylesheet(accent: str | None = None, theme_name: str | None = None) -> str:
    resolved = resolve_theme(theme_name)
    colors = get_theme_colors(resolved)

    if accent:
        colors["accent"] = accent
        colors["accent_hi"] = _shift(accent, 1.22)
        colors["accent_dim"] = _shift(accent, 0.78)
        colors["accent_soft"] = _mix(accent, colors["bg"], 0.26)

    qss = (
        _QSS.replace(
            "@check_icon@",
            _asset(
                f"check_{resolved}.png",
                "check",
                "#FFFFFF" if resolved == "Dark" else colors["accent"],
                14,
                3.0,
            ),
        )
        .replace(
            "@arrow_up@",
            _asset(f"chev_up_{resolved}.png", "chevron_up", colors["text_dim"], 12, 2.6),
        )
        .replace(
            "@arrow_down@",
            _asset(f"chev_down_{resolved}.png", "chevron_down", colors["text_dim"], 12, 2.6),
        )
    )
    # Add primary text color - white for dark mode, dark text for light mode
    primary_text_color = "#FFFFFF" if resolved == "Dark" else colors["text"]
    colors["primary_text"] = primary_text_color

    for key, val in colors.items():
        qss = qss.replace(f"@{key}@", val)
    # Dọn sạch token còn sót (nếu có)
    qss = re.sub(r"@[a-z_]+@", colors["text"], qss)
    return qss


def _asset(filename: str, icon_name: str, color: str, size: int, stroke: float) -> str:
    """Sinh (một lần) file PNG cho các phần tử mà QSS chỉ nhận qua url()."""
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
