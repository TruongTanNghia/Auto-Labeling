"""Thanh dieu huong ben trai."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_VERSION, COLORS
from app.theme import icons
from app.views.widgets.common import StatusDot, label


class NavButton(QPushButton):
    def __init__(self, index: int, text: str, icon_name: str, parent=None) -> None:
        # '&' trong text bi Qt hieu la phim tat -> phai nhan doi
        super().__init__("  " + text.replace("&", "&&"), parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(icons.icon(icon_name, COLORS["text_dim"], 18))
        self.setIconSize(QSize(18, 18))
        self.setMinimumHeight(38)
        self._icon_name = icon_name
        self._index = index
        self.setToolTip(f"{text}  (Ctrl+{index + 1})")
        self.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool) -> None:
        self.setIcon(icons.icon(self._icon_name, "#FFFFFF" if checked else COLORS["text_dim"], 18))


class Sidebar(QWidget):
    pageRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(214)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(4)

        # --- thuong hieu ---
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", COLORS["accent_hi"], 30, stroke=1.6))
        logo.setFixedSize(34, 34)
        brand.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        name = QLabel("AutoLabel Studio")
        name.setObjectName("BrandName")
        sub = QLabel("AI Dataset Builder")
        sub.setObjectName("BrandSub")
        col.addWidget(name)
        col.addWidget(sub)
        brand.addLayout(col)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(14)

        # --- dieu huong ---
        from app.constants import get_nav_items
        from app.i18n import tr

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, NavButton] = {}
        for i, (key, text, icon_name) in enumerate(get_nav_items()):
            b = NavButton(i, text, icon_name)
            b.clicked.connect(lambda _c=False, k=key: self.pageRequested.emit(k))
            self.group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b)
        lay.addStretch(1)

        # --- trang thai ---
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {COLORS['border']};")
        lay.addWidget(divider)
        lay.addSpacing(8)

        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(7)
        self.status_dot = StatusDot(COLORS["text_mute"], 8)
        self.status_row.addWidget(self.status_dot)
        self.device_label = label(
            tr("sidebar.checking", "Đang kiểm tra …"), size=11, color=COLORS["text_dim"]
        )
        self.status_row.addWidget(self.device_label, 1)
        lay.addLayout(self.status_row)

        self.project_label = label(
            tr("main.no_project", "Chưa mở project"), size=11, color=COLORS["text_mute"]
        )
        self.project_label.setWordWrap(True)
        lay.addWidget(self.project_label)
        lay.addSpacing(4)

        version = QLabel(
            f"{tr('settings.about.version', 'Phiên bản {version}', version=APP_VERSION)}"
        )
        version.setObjectName("SidebarFooter")
        lay.addWidget(version)

    # ------------------------------------------------------------------ API --
    def set_active(self, key: str) -> None:
        btn = self.buttons.get(key)
        if btn and not btn.isChecked():
            btn.setChecked(True)

    def set_device(self, text: str, ok: bool) -> None:
        self.device_label.setText(text)
        self.status_dot.set_color(COLORS["success"] if ok else COLORS["warning"])

    def set_project(self, text: str) -> None:
        self.project_label.setText(text)
