"""Bo bieu do tu ve bang QPainter (khong can thu vien ve do thi ben ngoai)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from app.constants import CLASS_PALETTE, COLORS


@dataclass
class Series:
    label: str
    value: float
    color: str = ""


class _ChartBase(QWidget):
    def __init__(self, parent=None, min_height: int = 160) -> None:
        super().__init__(parent)
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._grid_color = QColor(COLORS["border"])
        self._text_color = QColor(COLORS["text_mute"])
        self._font = QFont()
        self._font.setPointSize(8)

    def _painter(self) -> QPainter:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setFont(self._font)
        return p

    def _draw_empty(self, p: QPainter, text: str = "Chưa có dữ liệu") -> None:
        p.setPen(QPen(QColor(COLORS["text_mute"])))
        p.drawText(self.rect(), Qt.AlignCenter, text)


# ============================================================= BAR CHART ====
class BarChart(_ChartBase):
    """Bieu do cot doc, co gia tri tren dinh + nhan duoi truc."""

    barClicked = Signal(int)

    def __init__(self, parent=None, show_values: bool = True,
                 horizontal: bool = False) -> None:
        super().__init__(parent, 170)
        self.series: list[Series] = []
        self.show_values = show_values
        self.horizontal = horizontal
        self._hover = -1

    def set_data(self, series: list[Series]) -> None:
        self.series = list(series)
        for i, s in enumerate(self.series):
            if not s.color:
                s.color = CLASS_PALETTE[i % len(CLASS_PALETTE)]
        self.update()

    # ------------------------------------------------------------- ve ------
    def paintEvent(self, ev) -> None:  # noqa: D102
        p = self._painter()
        if not self.series:
            self._draw_empty(p)
            return
        if self.horizontal:
            self._paint_horizontal(p)
        else:
            self._paint_vertical(p)

    def _paint_vertical(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 8, 8, 22, 30
        plot = QRectF(pad_l, pad_t, w - pad_l - pad_r, h - pad_t - pad_b)
        vmax = max((s.value for s in self.series), default=1.0) or 1.0

        # luoi ngang
        p.setPen(QPen(self._grid_color, 1, Qt.DotLine))
        for i in range(1, 4):
            y = plot.bottom() - plot.height() * i / 4
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QPen(self._grid_color, 1))
        p.drawLine(QPointF(plot.left(), plot.bottom()), QPointF(plot.right(), plot.bottom()))

        n = len(self.series)
        slot = plot.width() / n
        bar_w = min(52.0, slot * 0.58)

        for i, s in enumerate(self.series):
            cx = plot.left() + slot * (i + 0.5)
            bh = plot.height() * (s.value / vmax)
            rect = QRectF(cx - bar_w / 2, plot.bottom() - bh, bar_w, max(2.0, bh))

            color = QColor(s.color)
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            top = QColor(color)
            if i == self._hover:
                top = top.lighter(125)
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 90))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            path = QPainterPath()
            path.addRoundedRect(rect, 5, 5)
            p.drawPath(path)

            if self.show_values and bh > 6:
                p.setPen(QPen(QColor(COLORS["text"])))
                p.drawText(QRectF(cx - slot / 2, rect.top() - 17, slot, 15),
                           Qt.AlignCenter, _fmt(s.value))
            p.setPen(QPen(self._text_color))
            p.drawText(QRectF(cx - slot / 2, plot.bottom() + 5, slot, 24),
                       int(Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap),
                       _short(s.label, 12))

    def _paint_horizontal(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        pad = 6
        label_w = 86
        plot = QRectF(pad + label_w, pad, w - label_w - pad * 2 - 44, h - pad * 2)
        vmax = max((s.value for s in self.series), default=1.0) or 1.0
        n = len(self.series)
        slot = plot.height() / max(1, n)
        bar_h = min(22.0, slot * 0.62)

        for i, s in enumerate(self.series):
            cy = plot.top() + slot * (i + 0.5)
            bw = plot.width() * (s.value / vmax)
            rect = QRectF(plot.left(), cy - bar_h / 2, max(2.0, bw), bar_h)

            p.setPen(QPen(self._text_color))
            p.drawText(QRectF(pad, cy - 9, label_w - 6, 18),
                       int(Qt.AlignRight | Qt.AlignVCenter), _short(s.label, 14))

            color = QColor(s.color)
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            grad.setColorAt(0.0, color if i != self._hover else color.lighter(125))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 110))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            path = QPainterPath()
            path.addRoundedRect(rect, 5, 5)
            p.drawPath(path)

            p.setPen(QPen(QColor(COLORS["text"])))
            p.drawText(QRectF(rect.right() + 6, cy - 9, 44, 18),
                       int(Qt.AlignLeft | Qt.AlignVCenter), _fmt(s.value))

    # ---------------------------------------------------------- tuong tac --
    def mouseMoveEvent(self, ev) -> None:  # noqa: D102
        idx = self._index_at(ev.position())
        if idx != self._hover:
            self._hover = idx
            self.update()
            if 0 <= idx < len(self.series):
                s = self.series[idx]
                QToolTip.showText(ev.globalPosition().toPoint(),
                                  f"{s.label}: {_fmt(s.value)}", self)

    def leaveEvent(self, ev) -> None:  # noqa: D102
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        idx = self._index_at(ev.position())
        if idx >= 0:
            self.barClicked.emit(idx)

    def _index_at(self, pos) -> int:
        if not self.series:
            return -1
        n = len(self.series)
        if self.horizontal:
            top, height = 6, self.height() - 12
            k = int((pos.y() - top) / max(1.0, height / n))
        else:
            left = 8
            width = self.width() - 16
            k = int((pos.x() - left) / max(1.0, width / n))
        return k if 0 <= k < n else -1


# =========================================================== DONUT CHART ====
class DonutChart(_ChartBase):
    """Bieu do tron/donut co ghi chu o giua."""

    sliceClicked = Signal(int)

    def __init__(self, parent=None, hole: float = 0.62, center_title: str = "",
                 center_sub: str = "") -> None:
        super().__init__(parent, 180)
        self.series: list[Series] = []
        self.hole = hole
        self.center_title = center_title
        self.center_sub = center_sub
        self._hover = -1

    def set_data(self, series: list[Series], center_title: str = "",
                 center_sub: str = "") -> None:
        self.series = [s for s in series if s.value > 0]
        for i, s in enumerate(self.series):
            if not s.color:
                s.color = CLASS_PALETTE[i % len(CLASS_PALETTE)]
        if center_title:
            self.center_title = center_title
        if center_sub:
            self.center_sub = center_sub
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = self._painter()
        if not self.series:
            self._draw_empty(p)
            return
        total = sum(s.value for s in self.series) or 1.0
        size = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)

        start = 90.0
        for i, s in enumerate(self.series):
            span = 360.0 * s.value / total
            grow = 4 if i == self._hover else 0
            r = rect.adjusted(-grow, -grow, grow, grow)
            color = QColor(s.color)
            p.setPen(QPen(QColor(COLORS["surface"]), 2))
            p.setBrush(color if i != self._hover else color.lighter(118))
            path = QPainterPath()
            path.moveTo(r.center())
            path.arcTo(r, start, -span)
            path.closeSubpath()
            p.drawPath(path)
            start -= span

        # Lo giua
        hole_size = size * self.hole
        hole_rect = QRectF((self.width() - hole_size) / 2, (self.height() - hole_size) / 2,
                           hole_size, hole_size)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(COLORS["surface"]))
        p.drawEllipse(hole_rect)

        title = self.center_title or _fmt(total)
        sub = self.center_sub
        f = QFont(self._font)
        f.setPointSize(max(10, int(hole_size / 7)))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(QColor(COLORS["text"])))
        p.drawText(hole_rect.adjusted(0, -6 if sub else 0, 0, -6 if sub else 0),
                   Qt.AlignCenter, title)
        if sub:
            f2 = QFont(self._font)
            f2.setPointSize(8)
            p.setFont(f2)
            p.setPen(QPen(QColor(COLORS["text_mute"])))
            p.drawText(hole_rect.adjusted(0, int(hole_size / 4), 0, 0),
                       Qt.AlignHCenter | Qt.AlignTop, sub)

    def mouseMoveEvent(self, ev) -> None:  # noqa: D102
        idx = self._index_at(ev.position())
        if idx != self._hover:
            self._hover = idx
            self.update()
            if 0 <= idx < len(self.series):
                s = self.series[idx]
                total = sum(x.value for x in self.series) or 1
                QToolTip.showText(
                    ev.globalPosition().toPoint(),
                    f"{s.label}: {_fmt(s.value)} ({100 * s.value / total:.1f}%)", self)

    def leaveEvent(self, ev) -> None:  # noqa: D102
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        idx = self._index_at(ev.position())
        if idx >= 0:
            self.sliceClicked.emit(idx)

    def _index_at(self, pos) -> int:
        if not self.series:
            return -1
        size = min(self.width(), self.height()) - 16
        cx, cy = self.width() / 2, self.height() / 2
        dx, dy = pos.x() - cx, pos.y() - cy
        dist = math.hypot(dx, dy)
        if dist > size / 2 + 4 or dist < size * self.hole / 2:
            return -1
        ang = (math.degrees(math.atan2(-dy, dx)) - 90) % 360
        ang = (360 - ang) % 360
        total = sum(s.value for s in self.series) or 1.0
        acc = 0.0
        for i, s in enumerate(self.series):
            acc += 360.0 * s.value / total
            if ang <= acc:
                return i
        return len(self.series) - 1


# ============================================================ LINE CHART ====
class LineChart(_ChartBase):
    """Bieu do duong nhieu series - dung cho metric khi train."""

    def __init__(self, parent=None, y_max: float | None = None,
                 x_label: str = "", show_legend: bool = True) -> None:
        super().__init__(parent, 190)
        self.lines: dict[str, tuple[str, list[float]]] = {}   # name -> (color, values)
        self.y_max = y_max
        self.x_label = x_label
        self.show_legend = show_legend

    def clear(self) -> None:
        self.lines.clear()
        self.update()

    def set_line(self, name: str, values: list[float], color: str) -> None:
        self.lines[name] = (color, list(values))
        self.update()

    def append(self, name: str, value: float, color: str = "") -> None:
        if name in self.lines:
            self.lines[name][1].append(value)
        else:
            self.lines[name] = (color or CLASS_PALETTE[len(self.lines) % len(CLASS_PALETTE)],
                                [value])
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = self._painter()
        if not self.lines or all(not v for _, v in self.lines.values()):
            self._draw_empty(p, "Chưa có dữ liệu huấn luyện")
            return

        pad_l, pad_r, pad_t = 34, 10, 12
        pad_b = 40 if self.show_legend else 22
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)

        n_max = max(len(v) for _, v in self.lines.values())
        v_max = self.y_max
        if v_max is None:
            v_max = max((max(v) if v else 0) for _, v in self.lines.values())
            v_max = max(0.001, v_max * 1.12)

        # luoi + nhan truc Y
        p.setPen(QPen(self._grid_color, 1, Qt.DotLine))
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QPen(self._text_color))
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.drawText(QRectF(0, y - 8, pad_l - 5, 16),
                       int(Qt.AlignRight | Qt.AlignVCenter), f"{v_max * i / 4:.2f}")

        # nhan truc X
        p.setPen(QPen(self._text_color))
        for i in range(5):
            x = plot.left() + plot.width() * i / 4
            v = int(n_max * i / 4)
            p.drawText(QRectF(x - 18, plot.bottom() + 3, 36, 14), Qt.AlignCenter, str(v))

        for name, (color, values) in self.lines.items():
            if len(values) < 1:
                continue
            path = QPainterPath()
            for i, v in enumerate(values):
                x = plot.left() + (plot.width() * i / max(1, n_max - 1)
                                   if n_max > 1 else plot.width() / 2)
                y = plot.bottom() - plot.height() * min(1.0, max(0.0, v / v_max))
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(color), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            if values:
                last_x = plot.left() + (plot.width() * (len(values) - 1) / max(1, n_max - 1)
                                        if n_max > 1 else plot.width() / 2)
                last_y = plot.bottom() - plot.height() * min(1.0, max(0.0, values[-1] / v_max))
                p.setBrush(QColor(color))
                p.setPen(QPen(QColor(COLORS["surface"]), 1.5))
                p.drawEllipse(QPointF(last_x, last_y), 3.4, 3.4)

        if self.show_legend:
            self._draw_legend(p, plot)

    def _draw_legend(self, p: QPainter, plot: QRectF) -> None:
        x = plot.left()
        y = self.height() - 16
        for name, (color, values) in self.lines.items():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x, y - 4, 7, 7))
            p.setPen(QPen(self._text_color))
            text = f"{name}"
            if values:
                text += f"  {values[-1]:.3f}"
            w = p.fontMetrics().horizontalAdvance(text)
            p.drawText(QPointF(x + 11, y + 3), text)
            x += w + 26
            if x > self.width() - 60:
                break


# =============================================================== HEATMAP ====
class Heatmap(_ChartBase):
    """Ban do nhiet mat do vi tri doi tuong (chuan hoa theo khung anh)."""

    def __init__(self, parent=None, colormap: str = "purple") -> None:
        super().__init__(parent, 180)
        self.matrix: list[list[float]] = []
        self.colormap = colormap

    def set_matrix(self, matrix) -> None:
        self.matrix = [list(row) for row in matrix]
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = self._painter()
        if not self.matrix or not self.matrix[0]:
            self._draw_empty(p, "Chưa có đối tượng nào")
            return
        rows, cols = len(self.matrix), len(self.matrix[0])
        vmax = max(max(r) for r in self.matrix) or 1.0

        side = min(self.width() - 12, self.height() - 12)
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2
        cw, ch = side / cols, side / rows

        for r in range(rows):
            for c in range(cols):
                v = self.matrix[r][c] / vmax
                p.setPen(Qt.NoPen)
                p.setBrush(self._color_for(v))
                p.drawRect(QRectF(ox + c * cw, oy + r * ch, cw + 0.6, ch + 0.6))

        p.setPen(QPen(QColor(COLORS["border_hi"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(ox, oy, side, side))
        # duong chia 3x3 giup uoc luong vi tri
        p.setPen(QPen(QColor(255, 255, 255, 26), 1, Qt.DashLine))
        for i in (1, 2):
            p.drawLine(QPointF(ox + side * i / 3, oy), QPointF(ox + side * i / 3, oy + side))
            p.drawLine(QPointF(ox, oy + side * i / 3), QPointF(ox + side, oy + side * i / 3))

    def _color_for(self, v: float) -> QColor:
        v = max(0.0, min(1.0, v))
        if self.colormap == "purple":
            stops = [(0.0, QColor("#12121C")), (0.35, QColor("#3B2C7A")),
                     (0.7, QColor("#7C5CFF")), (1.0, QColor("#E8DFFF"))]
        else:
            stops = [(0.0, QColor("#101018")), (0.4, QColor("#1D4E89")),
                     (0.75, QColor("#F5A524")), (1.0, QColor("#FFF3D6"))]
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= v <= t1:
                k = (v - t0) / max(1e-6, t1 - t0)
                return QColor(
                    int(c0.red() + (c1.red() - c0.red()) * k),
                    int(c0.green() + (c1.green() - c0.green()) * k),
                    int(c0.blue() + (c1.blue() - c0.blue()) * k),
                )
        return stops[-1][1]


# ============================================================= HISTOGRAM ====
class Histogram(_ChartBase):
    """Bieu do phan bo (vd: dien tich mask, confidence)."""

    def __init__(self, parent=None, color: str = "", log_x: bool = False,
                 x_labels: list[str] | None = None) -> None:
        super().__init__(parent, 170)
        self.counts: list[int] = []
        self.edges: list[float] = []
        self.color = color or COLORS["accent"]
        self.log_x = log_x
        self.x_labels = x_labels

    def set_data(self, counts, edges=None) -> None:
        self.counts = list(counts)
        self.edges = list(edges) if edges else []
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = self._painter()
        if not self.counts or max(self.counts) == 0:
            self._draw_empty(p)
            return
        pad_l, pad_r, pad_t, pad_b = 32, 8, 12, 24
        plot = QRectF(pad_l, pad_t, self.width() - pad_l - pad_r,
                      self.height() - pad_t - pad_b)
        vmax = max(self.counts) or 1

        p.setPen(QPen(self._grid_color, 1, Qt.DotLine))
        for i in range(1, 4):
            y = plot.bottom() - plot.height() * i / 4
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(QPen(self._text_color))
        for i in range(3):
            y = plot.bottom() - plot.height() * (i + 1) / 4 * 4 / 3
            p.drawText(QRectF(0, y - 8, pad_l - 4, 16),
                       int(Qt.AlignRight | Qt.AlignVCenter),
                       _fmt(vmax * (i + 1) / 3))

        n = len(self.counts)
        # Chi co mot gia tri duy nhat -> ve mot cot hep o giua cho de nhin
        bars = plot if n > 1 else QRectF(
            plot.center().x() - plot.width() * 0.09, plot.top(),
            plot.width() * 0.18, plot.height())
        bw = bars.width() / n
        base = QColor(self.color)
        for i, c in enumerate(self.counts):
            bh = plot.height() * c / vmax
            rect = QRectF(bars.left() + i * bw + 0.6, plot.bottom() - bh,
                          max(1.0, bw - 1.2), max(0.0, bh))
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, base)
            grad.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 70))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRect(rect)

        p.setPen(QPen(self._grid_color, 1))
        p.drawLine(QPointF(plot.left(), plot.bottom()), QPointF(plot.right(), plot.bottom()))

        labels = self.x_labels
        if labels is None and self.edges:
            labels = [_fmt(self.edges[0]),
                      _fmt(self.edges[len(self.edges) // 2]),
                      _fmt(self.edges[-1])]
        if labels:
            p.setPen(QPen(self._text_color))
            k = len(labels) - 1
            for i, text in enumerate(labels):
                x = plot.left() + plot.width() * (i / max(1, k))
                p.drawText(QRectF(x - 26, plot.bottom() + 4, 52, 15),
                           Qt.AlignCenter, text)


# ============================================================ PROGRESS RING ==
class ProgressRing(QWidget):
    """Vong tron tien do co chu o giua."""

    def __init__(self, parent=None, size: int = 92, thickness: int = 9,
                 color: str = "") -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value = 0.0
        self._thickness = thickness
        self._color = color or COLORS["accent"]
        self._label = ""

    def set_value(self, v: float, text: str = "") -> None:
        self._value = max(0.0, min(1.0, v))
        self._label = text
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self._thickness
        rect = QRectF(t / 2 + 1, t / 2 + 1, self.width() - t - 2, self.height() - t - 2)
        p.setPen(QPen(QColor(COLORS["surface_hi"]), t, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 0, 360 * 16)
        p.setPen(QPen(QColor(self._color), t, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 90 * 16, int(-360 * 16 * self._value))

        f = QFont()
        f.setBold(True)
        f.setPointSize(max(9, int(self.width() / 6)))
        p.setFont(f)
        p.setPen(QPen(QColor(COLORS["text"])))
        p.drawText(self.rect(), Qt.AlignCenter, self._label or f"{int(self._value * 100)}%")


# ============================================================ STACKED BAR ====
class StackedProgress(QWidget):
    """Thanh ngang nhieu doan mau - dung cho phan bo trang thai anh."""

    def __init__(self, parent=None, height: int = 10) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self.segments: list[tuple[float, str]] = []

    def set_segments(self, segments) -> None:
        self.segments = [(float(v), c) for v, c in segments if v > 0]
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        radius = r.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(COLORS["surface_hi"]))
        p.drawRoundedRect(r, radius, radius)
        if not self.segments:
            return
        total = sum(v for v, _ in self.segments) or 1.0
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        p.setClipPath(path)
        x = 0.0
        for v, color in self.segments:
            w = r.width() * v / total
            p.setBrush(QColor(color))
            p.drawRect(QRectF(x, 0, w + 0.5, r.height()))
            x += w


# ================================================================ HELPERS ===
def _fmt(v: float) -> str:
    v = float(v)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 10_000:
        return f"{v / 1000:.1f}K"
    if v >= 1000:
        return f"{v:,.0f}"
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}"


def _short(text: str, n: int) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"
