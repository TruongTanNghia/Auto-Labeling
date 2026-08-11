"""Bo widget dung chung: card, badge, stat, toast, toggle, field ..."""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.constants import COLORS
from app.theme import icons


# ================================================================== LABEL ===
def label(
    text: str,
    obj: str = "",
    bold: bool = False,
    size: int | None = None,
    color: str = "",
    wrap: bool = False,
) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    style = []
    if bold:
        style.append("font-weight: 700")
    if size:
        style.append(f"font-size: {float(size):g}px")
    if color:
        style.append(f"color: {color}")
    if style:
        lb.setStyleSheet(";".join(style))
    lb.setWordWrap(wrap)
    return lb


def hline() -> QFrame:
    f = QFrame()
    f.setObjectName("Divider")
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {COLORS['border']};")
    return f


def vline() -> QFrame:
    f = QFrame()
    f.setObjectName("VDivider")
    f.setFixedWidth(1)
    f.setStyleSheet(f"background: {COLORS['border']};")
    return f


def spacer(w: int = 0, h: int = 0) -> QWidget:
    sp = QWidget()
    if w:
        sp.setFixedWidth(w)
    if h:
        sp.setFixedHeight(h)
    if not w and not h:
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return sp


def hstretch() -> QWidget:
    sp = QWidget()
    sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return sp


# =================================================================== CARD ===
class Card(QFrame):
    """Khung noi dung bo goc, co tieu de + vung header phu tuy chon."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        icon_name: str = "",
        icon_color: str = "",
        parent=None,
        flat: bool = False,
        margins: tuple = (16, 14, 16, 16),
        spacing: int = 12,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CardFlat" if flat else "Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(*margins)
        self._outer.setSpacing(spacing)

        self.header = QHBoxLayout()
        self.header.setSpacing(9)
        self._has_header = False
        self.title_label: QLabel | None = None
        self.subtitle_label: QLabel | None = None

        if icon_name:
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon_name, icon_color or COLORS["accent_hi"], 18))
            ic.setFixedSize(20, 20)
            self.header.addWidget(ic)
            self._has_header = True
        if title:
            box = QVBoxLayout()
            box.setSpacing(1)
            self.title_label = label(title, "CardTitle")
            box.addWidget(self.title_label)
            if subtitle:
                self.subtitle_label = label(subtitle, "CardSubtitle")
                box.addWidget(self.subtitle_label)
            self.header.addLayout(box)
            self._has_header = True
        if self._has_header:
            self.header.addStretch(1)
            self._outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setSpacing(spacing)
        # Khoang trong thua phai roi vao phan than, khong duoc day tieu de
        # xuong giua khi card cao hon noi dung.
        self._outer.addLayout(self.body, 1)

    # ---------------------------------------------------------------- API ---
    def add(self, widget_or_layout, stretch: int = 0) -> None:
        if isinstance(widget_or_layout, QWidget):
            self.body.addWidget(widget_or_layout, stretch)
        else:
            self.body.addLayout(widget_or_layout, stretch)

    def add_header_widget(self, widget: QWidget) -> None:
        if not self._has_header:
            self._outer.insertLayout(0, self.header)
            self.header.addStretch(1)
            self._has_header = True
        self.header.addWidget(widget)

    def add_stretch(self, n: int = 1) -> None:
        self.body.addStretch(n)

    def set_shadow(self, blur: int = 26, alpha: int = 130, dy: int = 6) -> None:
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(blur)
        eff.setOffset(0, dy)
        eff.setColor(QColor(0, 0, 0, alpha))
        self.setGraphicsEffect(eff)


# ============================================================== STAT CARD ===
class StatCard(QFrame):
    """O thong ke nho: icon + gia tri lon + nhan."""

    clicked = Signal()

    def __init__(self, icon_name: str, value: str, text: str, color: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFlat")
        self._color = color or COLORS["accent"]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(13, 11, 13, 11)
        lay.setSpacing(11)

        self.icon_box = QLabel()
        self.icon_box.setFixedSize(38, 38)
        self.icon_box.setAlignment(Qt.AlignCenter)
        self.icon_box.setPixmap(icons.pixmap(icon_name, self._color, 20))
        self.icon_box.setStyleSheet(
            f"background: {icons.with_alpha(self._color, 0.14).name(QColor.HexArgb)};"
            f"border-radius: 11px;"
        )
        lay.addWidget(self.icon_box)

        col = QVBoxLayout()
        col.setSpacing(0)
        self.value_label = label(value, "StatValue")
        self.text_label = label(text, "StatLabel")
        col.addWidget(self.value_label)
        col.addWidget(self.text_label)
        lay.addLayout(col)
        lay.addStretch(1)
        self.setCursor(Qt.PointingHandCursor)

    def set_value(self, value) -> None:
        self.value_label.setText(str(value))

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(ev)


# ================================================================= BADGE ====
class Badge(QLabel):
    def __init__(self, text: str, color: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Badge")
        self.set_color(color or COLORS["accent"])
        self.setAlignment(Qt.AlignCenter)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(
            f"color: {color};"
            f"background: {icons.with_alpha(color, 0.15).name(QColor.HexArgb)};"
            f"border: 1px solid {icons.with_alpha(color, 0.35).name(QColor.HexArgb)};"
            f"border-radius: 8px; padding: 3px 9px; font-size: 11px; font-weight: 700;"
        )


class StatusDot(QWidget):
    def __init__(self, color: str = "", size: int = 9, parent=None) -> None:
        super().__init__(parent)
        self._color = color or COLORS["success"]
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self._color))
        p.drawEllipse(self.rect())


class LegendItem(QWidget):
    def __init__(self, color: str, text: str, value: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self.dot = StatusDot(color, 9)
        lay.addWidget(self.dot)
        self.text_label = label(text, color=COLORS["text_dim"], size=12)
        lay.addWidget(self.text_label)
        lay.addStretch(1)
        self.value_label = label(value, bold=True, size=12, color=COLORS["text"])
        lay.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


# ============================================================ ICON BUTTON ===
class IconButton(QPushButton):
    def __init__(
        self,
        icon_name: str,
        tooltip: str = "",
        size: int = 18,
        checkable: bool = False,
        color: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IconBtn")
        self.setIcon(icons.icon(icon_name, color or COLORS["text_dim"], size))
        self.setIconSize(QSize(size, size))
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self._name = icon_name
        self._size = size

    def set_icon_name(self, name: str, color: str = "") -> None:
        self._name = name
        self.setIcon(icons.icon(name, color or COLORS["text_dim"], self._size))


class ToolButton(QPushButton):
    """Nut co icon + chu, dung cho thanh cong cu Editor."""

    def __init__(
        self, icon_name: str, text: str, tooltip: str = "", checkable: bool = True, parent=None
    ) -> None:
        super().__init__(text, parent)
        self.setObjectName("Tool")
        self.setIcon(icons.icon(icon_name, COLORS["text_dim"], 16))
        self.setIconSize(QSize(16, 16))
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)


def primary_button(text: str, icon_name: str = "", parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("Primary")
    btn.setCursor(Qt.PointingHandCursor)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, "#FFFFFF", 17))
        btn.setIconSize(QSize(17, 17))
    return btn


def ghost_button(text: str, icon_name: str = "", parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("Ghost")
    btn.setCursor(Qt.PointingHandCursor)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, COLORS["text_dim"], 17))
        btn.setIconSize(QSize(17, 17))
    return btn


def danger_button(text: str, icon_name: str = "", parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("Danger")
    btn.setCursor(Qt.PointingHandCursor)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, "#FFFFFF", 17))
        btn.setIconSize(QSize(17, 17))
    return btn


def browse_button(
    tooltip: str = "Chọn thư mục…", icon_name: str = "folder", parent=None
) -> QPushButton:
    """Nut duyet file/thu muc: chi co icon de khong bi cat chu."""
    btn = QPushButton(parent)
    btn.setObjectName("Ghost")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setIcon(icons.icon(icon_name, COLORS["text_dim"], 17))
    btn.setIconSize(QSize(17, 17))
    btn.setFixedSize(40, 34)
    btn.setToolTip(tooltip)
    return btn


def chip_button(text: str, icon_name: str = "", checkable: bool = True, parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setObjectName("Chip")
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, COLORS["text_dim"], 15))
        btn.setIconSize(QSize(15, 15))
    return btn


# =============================================================== FIELDS ====
class Field(QWidget):
    """Nhan + widget nhap, xep ngang hoac doc."""

    def __init__(
        self,
        text: str,
        widget: QWidget,
        horizontal: bool = True,
        label_width: int = 96,
        hint: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.widget = widget
        self.label_widget: QLabel | None = None
        if horizontal:
            lay = QHBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(9)
            lb = label(text, color=COLORS["text_dim"], size=12)
            lb.setFixedWidth(label_width)
            self.label_widget = lb
            lay.addWidget(lb)
            # Widget co be ngang co dinh thi can trai, khong de troi giua hang
            if widget.maximumWidth() < 16_777_215:
                lay.addWidget(widget)
                lay.addStretch(1)
            else:
                lay.addWidget(widget, 1)
        else:
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(5)
            lay.addWidget(label(text, color=COLORS["text_dim"], size=11.5))
            lay.addWidget(widget)
        if hint:
            widget.setToolTip(hint)


def combo(items, current=None, width: int = 0) -> QComboBox:
    cb = QComboBox()
    for it in items:
        if isinstance(it, (tuple, list)) and len(it) == 2:
            cb.addItem(str(it[1]), it[0])
        else:
            cb.addItem(str(it), it)
    if current is not None:
        idx = cb.findData(current)
        if idx < 0:
            idx = cb.findText(str(current))
        if idx >= 0:
            cb.setCurrentIndex(idx)
    if width:
        cb.setFixedWidth(width)
    cb.setCursor(Qt.PointingHandCursor)
    return cb


def spin(
    value: int, lo: int = 0, hi: int = 100000, step: int = 1, suffix: str = "", width: int = 0
) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setSingleStep(step)
    sb.setValue(int(value))
    if suffix:
        sb.setSuffix(suffix)
    if width:
        sb.setFixedWidth(width)
    sb.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return sb


def dspin(
    value: float,
    lo: float = 0.0,
    hi: float = 1.0,
    step: float = 0.01,
    decimals: int = 3,
    suffix: str = "",
    width: int = 0,
) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi)
    sb.setSingleStep(step)
    sb.setDecimals(decimals)
    sb.setValue(float(value))
    if suffix:
        sb.setSuffix(suffix)
    if width:
        sb.setFixedWidth(width)
    return sb


class SliderField(QWidget):
    """Slider + o so, dong bo hai chieu."""

    valueChanged = Signal(float)

    def __init__(
        self,
        value: float,
        lo: float = 0.0,
        hi: float = 1.0,
        decimals: int = 2,
        step: float = 0.01,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._scale = 10**decimals
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int(lo * self._scale), int(hi * self._scale))
        self.slider.setValue(int(value * self._scale))
        self.spin = dspin(value, lo, hi, step, decimals, width=84)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v: int) -> None:
        val = v / self._scale
        if abs(self.spin.value() - val) > 1e-9:
            self.spin.blockSignals(True)
            self.spin.setValue(val)
            self.spin.blockSignals(False)
        self.valueChanged.emit(val)

    def _from_spin(self, v: float) -> None:
        iv = int(round(v * self._scale))
        if self.slider.value() != iv:
            self.slider.blockSignals(True)
            self.slider.setValue(iv)
            self.slider.blockSignals(False)
        self.valueChanged.emit(v)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v: float) -> None:
        self.spin.setValue(v)


class SearchBox(QLineEdit):
    def __init__(self, placeholder: str = "Tim kiem ...", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self._icon = icons.pixmap("search", COLORS["text_mute"], 15)

    def paintEvent(self, ev) -> None:  # noqa: D102
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y = (self.height() - 15) // 2
        p.drawPixmap(10, y, self._icon)


class ToggleSwitch(QCheckBox):
    """Cong tac truot kieu iOS, ve bang QPainter."""

    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 22)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"handlePos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def get_handle_pos(self) -> float:
        return self._pos

    def set_handle_pos(self, v: float) -> None:
        self._pos = v
        self.update()

    handlePos = Property(float, get_handle_pos, set_handle_pos)

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        off = QColor(COLORS["surface_hi"])
        on = QColor(COLORS["accent"])
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(QPen(QColor(COLORS["border_hi"]), 1))
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        d = r.height() - 4
        x = r.left() + 2 + self._pos * (r.width() - d - 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRect(int(x), r.top() + 2, d, d))


# ================================================================= TOAST ====
class Toast(QFrame):
    """Thong bao noi goc duoi phai, tu bien mat."""

    KINDS = {
        "success": ("check_circle", COLORS["success"]),
        "error": ("alert", COLORS["danger"]),
        "warning": ("alert", COLORS["warning"]),
        "info": ("info", COLORS["info"]),
    }

    def __init__(self, text: str, kind: str = "info", parent=None, duration: int = 3200) -> None:
        super().__init__(parent)
        icon_name, color = self.KINDS.get(kind, self.KINDS["info"])
        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card {{ background: {COLORS['surface_alt']};"
            f"border: 1px solid {color}; border-radius: 11px; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(13, 11, 15, 11)
        lay.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 18))
        ic.setFixedSize(20, 20)
        lay.addWidget(ic)
        lb = label(text, color=COLORS["text"], size=12.5, wrap=True)
        lb.setMaximumWidth(420)
        lay.addWidget(lb, 1)

        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(30)
        eff.setOffset(0, 8)
        eff.setColor(QColor(0, 0, 0, 170))
        self.setGraphicsEffect(eff)

        self.adjustSize()
        self._duration = duration
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(230)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def show_at(self, target: QPoint) -> None:
        self.move(target + QPoint(0, 28))
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(target)
        self._anim.start()
        QTimer.singleShot(self._duration, self._fade_out)

    def _fade_out(self) -> None:
        self._out = QPropertyAnimation(self, b"pos", self)
        self._out.setDuration(200)
        self._out.setEasingCurve(QEasingCurve.InCubic)
        self._out.setStartValue(self.pos())
        self._out.setEndValue(self.pos() + QPoint(0, 24))
        self._out.finished.connect(self.deleteLater)
        self._out.start()


class ToastManager:
    """Quan ly xep chong nhieu toast tren mot cua so."""

    def __init__(self, host: QWidget) -> None:
        self.host = host
        self._items: list[Toast] = []

    def show(self, text: str, kind: str = "info", duration: int = 3200) -> None:
        toast = Toast(text, kind, self.host, duration)
        self._items = [t for t in self._items if not t.isHidden() and t.parent() is not None]
        offset = 0
        for t in reversed(self._items[-3:]):
            offset += t.height() + 9
        x = self.host.width() - toast.width() - 24
        y = self.host.height() - toast.height() - 24 - offset
        self._items.append(toast)
        toast.show_at(QPoint(max(12, x), max(12, y)))
        QTimer.singleShot(duration + 420, lambda: self._drop(toast))

    def _drop(self, toast: Toast) -> None:
        if toast in self._items:
            self._items.remove(toast)


# ============================================================ EMPTY STATE ===
class EmptyState(QWidget):
    """Trang thai rong: icon lon + tieu de + goi y + toi da 2 nut hanh dong."""

    action = Signal()
    action2 = Signal()

    def __init__(
        self,
        icon_name: str,
        title: str,
        hint: str = "",
        action_text: str = "",
        parent=None,
        action2_text: str = "",
    ) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(11)

        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, COLORS["border_hi"], 54, stroke=1.4))
        ic.setAlignment(Qt.AlignCenter)
        lay.addWidget(ic)

        t = label(title, bold=True, size=15, color=COLORS["text_dim"])
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)

        if hint:
            h = label(hint, size=12, color=COLORS["text_mute"], wrap=True)
            h.setAlignment(Qt.AlignCenter)
            h.setMaximumWidth(420)
            lay.addWidget(h, 0, Qt.AlignCenter)

        if action_text or action2_text:
            row = QHBoxLayout()
            row.setSpacing(9)
            row.addStretch(1)
            if action_text:
                btn = primary_button(action_text, "plus")
                btn.setMinimumWidth(180)
                btn.clicked.connect(self.action.emit)
                row.addWidget(btn)
            if action2_text:
                btn2 = ghost_button(action2_text, "folder_open")
                btn2.setMinimumWidth(180)
                btn2.clicked.connect(self.action2.emit)
                row.addWidget(btn2)
            row.addStretch(1)
            lay.addSpacing(4)
            lay.addLayout(row)


# ========================================================= PROGRESS PANEL ===
class ProgressPanel(QFrame):
    """Thanh tien do + trang thai + nut huy, dung o nhieu trang."""

    cancelled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFlat")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 13)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(9)
        from app.i18n import tr

        self.stage_label = label(tr("progress.preparing", "Đang chuẩn bị …"), bold=True, size=12.5)
        top.addWidget(self.stage_label)
        top.addStretch(1)
        self.percent_label = label("0%", bold=True, size=12.5, color=COLORS["accent_hi"])
        top.addWidget(self.percent_label)
        self.cancel_btn = ghost_button(tr("common.cancel", "Hủy"), "close")
        self.cancel_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        top.addWidget(self.cancel_btn)
        lay.addLayout(top)

        from PySide6.QtWidgets import QProgressBar

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)

        self.detail_label = label("", size=11.5, color=COLORS["text_mute"])
        self.detail_label.setMinimumHeight(15)
        lay.addWidget(self.detail_label)
        self.hide()

    def start(self, stage: str = "") -> None:
        from app.i18n import tr

        self.stage_label.setText(stage or tr("progress.processing", "Đang xử lý …"))
        self.bar.setValue(0)
        self.percent_label.setText("0%")
        self.detail_label.setText("")
        self.cancel_btn.setEnabled(True)
        self.show()

    def set_stage(self, text: str) -> None:
        self.stage_label.setText(text)

    def set_progress(self, cur: int, total: int, msg: str = "") -> None:
        pct = int(100 * cur / max(1, total))
        self.bar.setValue(min(100, pct))
        self.percent_label.setText(f"{min(100, pct)}%")
        if msg:
            self.detail_label.setText(msg)

    def finish(self, text: str = "") -> None:
        from app.i18n import tr

        self.bar.setValue(100)
        self.percent_label.setText("100%")
        self.stage_label.setText(text or tr("progress.done", "Hoàn tất"))
        self.cancel_btn.setEnabled(False)
        QTimer.singleShot(1600, self.hide)


# ========================================================= KEY VALUE GRID ===
class KeyValueGrid(QWidget):
    """Bang thong tin dang khoa - gia tri (vd: thong tin video)."""

    def __init__(
        self, pairs=None, parent=None, key_color: str = "", value_bold: bool = True
    ) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(7)
        self._grid.setColumnStretch(1, 1)
        self._rows: dict[str, QLabel] = {}
        self._key_color = key_color or COLORS["text_mute"]
        self._value_bold = value_bold
        if pairs:
            self.set_pairs(pairs)

    def set_pairs(self, pairs) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rows.clear()
        for i, (k, v) in enumerate(pairs):
            kl = label(str(k), size=11.5, color=self._key_color)
            vl = label(str(v), size=12, bold=self._value_bold, color=COLORS["text"])
            vl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._grid.addWidget(kl, i, 0)
            self._grid.addWidget(vl, i, 1)
            self._rows[str(k)] = vl

    def set_value(self, key: str, value) -> None:
        if key in self._rows:
            self._rows[key].setText(str(value))


# ============================================================= SECTION ======
def section_label(text: str) -> QLabel:
    return label(text.upper(), "SectionLabel")


class CollapsibleSection(QWidget):
    """Khoi co the thu gon, co animation chieu cao."""

    def __init__(self, title: str, expanded: bool = True, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.toggle = QPushButton(title)
        self.toggle.setObjectName("SubTab")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setIcon(
            icons.icon("chevron_down" if expanded else "chevron_right", COLORS["text_dim"], 15)
        )
        self.toggle.setIconSize(QSize(15, 15))
        outer.addWidget(self.toggle)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(6, 0, 0, 4)
        self.content_layout.setSpacing(9)
        outer.addWidget(self.content)
        self.content.setVisible(expanded)
        self.toggle.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.toggle.setIcon(
            icons.icon("chevron_down" if checked else "chevron_right", COLORS["text_dim"], 15)
        )

    def add(self, widget_or_layout) -> None:
        if isinstance(widget_or_layout, QWidget):
            self.content_layout.addWidget(widget_or_layout)
        else:
            self.content_layout.addLayout(widget_or_layout)


# ============================================================ PAGE HEADER ===
class PageHeader(QWidget):
    """Tieu de trang + mo ta + vung nut ben phai."""

    def __init__(self, title: str, subtitle: str = "", icon_name: str = "", parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        if icon_name:
            box = QLabel()
            box.setFixedSize(42, 42)
            box.setAlignment(Qt.AlignCenter)
            box.setPixmap(icons.pixmap(icon_name, COLORS["accent_hi"], 22))
            box.setStyleSheet(f"background: {COLORS['accent_soft']}; border-radius: 12px;")
            lay.addWidget(box)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.title_label = label(title, "PageTitle")
        col.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, "PageSubtitle")
        col.addWidget(self.subtitle_label)
        lay.addLayout(col)
        lay.addStretch(1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(9)
        lay.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)


def elide(text: str, n: int = 42) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def font_mono(size: int = 11) -> QFont:
    f = QFont("Cascadia Mono")
    if not f.exactMatch():
        f = QFont("Consolas")
    f.setPointSize(size)
    return f
