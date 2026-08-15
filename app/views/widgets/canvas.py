"""Canvas annotation: ve/sua polygon, brush, eraser, split, merge, zoom/pan.

Toa do annotation luon la pixel cua anh goc. Bien doi hien thi:
    screen = image_point * scale + offset
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.constants import ANN_MANUAL, COLORS, SHAPE_POLYGON
from app.models.entities import Annotation

# ------------------------------------------------------------------ shapely --
try:
    from shapely.geometry import LineString, MultiPolygon, Point, Polygon
    from shapely.ops import split as shapely_split
    from shapely.ops import unary_union
    _HAS_SHAPELY = True
except Exception:  # pragma: no cover
    _HAS_SHAPELY = False


# ------------------------------------------------------------------- TOOLS ---
TOOL_SELECT = "select"
TOOL_POLYGON = "polygon"
TOOL_BRUSH = "brush"
TOOL_ERASER = "eraser"
TOOL_SPLIT = "split"
TOOL_BBOX = "bbox"
TOOL_PAN = "pan"

HANDLE_R = 4.6


@dataclass
class CanvasStyle:
    fill_opacity: float = 0.35
    line_width: float = 2.0
    vertex_size: float = 6.0
    show_labels: bool = True
    show_confidence: bool = True
    show_class_color: bool = True


class AnnotationCanvas(QWidget):
    """Vung ve chinh cua Annotation Editor."""

    annotationsChanged = Signal()
    selectionChanged = Signal(list)          # danh sach index dang chon
    statusMessage = Signal(str)
    zoomChanged = Signal(float)
    viewChanged = Signal()
    newShapeCreated = Signal(int)            # index cua shape moi
    doubleClickedEmpty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Canvas")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

        # --- du lieu ---
        self.pixmap: QPixmap | None = None
        self.img_w = 0
        self.img_h = 0
        self.annotations: list[Annotation] = []
        self.class_colors: dict[int, str] = {}
        self.class_names: dict[int, str] = {}
        self.hidden_classes: set[int] = set()
        self.active_class_id: int = 0
        self.style = CanvasStyle()

        # --- trang thai xem ---
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._panning = False
        self._pan_start = QPoint()
        self._space_held = False

        # --- trang thai chon / sua ---
        self.tool = TOOL_SELECT
        self.selected: set[int] = set()
        self._hover_idx = -1
        self._hover_vertex = (-1, -1)
        self._drag_vertex = (-1, -1)
        self._drag_shape = False
        self._drag_origin = QPointF()
        self._shape_snapshot: list[Annotation] = []

        # --- ve moi ---
        self._draft: list[QPointF] = []
        self._draft_cursor = QPointF()
        self._bbox_start: QPointF | None = None
        self._brush_path: list[QPointF] = []
        self.brush_size = 20.0
        self._split_line: list[QPointF] = []

        # --- undo/redo ---
        self._undo: list[list[Annotation]] = []
        self._redo: list[list[Annotation]] = []
        self._max_history = 60

    # =========================================================== DU LIEU ===
    def load_image(self, path: str, annotations: list[Annotation] | None = None,
                   fit: bool = True) -> bool:
        if not path:
            self.pixmap = None
            self.img_w = self.img_h = 0
            self.annotations = []
            self.update()
            return False
        pm = QPixmap(path)
        if pm.isNull():
            img = QImage(path)
            if img.isNull():
                self.pixmap = None
                self.img_w = self.img_h = 0
                self.annotations = []
                self.update()
                self.statusMessage.emit(f"Không đọc được ảnh: {path}")
                return False
            pm = QPixmap.fromImage(img)
        self.pixmap = pm
        self.img_w, self.img_h = pm.width(), pm.height()
        self.annotations = [a.clone() for a in (annotations or [])]
        self.selected.clear()
        self._undo.clear()
        self._redo.clear()
        self._reset_transient()
        if fit:
            self.fit_to_view()
        self.update()
        self.selectionChanged.emit([])
        return True

    def set_annotations(self, annotations: list[Annotation]) -> None:
        self.annotations = [a.clone() for a in annotations]
        self.selected.clear()
        self.update()
        self.selectionChanged.emit([])

    def get_annotations(self) -> list[Annotation]:
        return [a.clone() for a in self.annotations]

    def set_classes(self, classes) -> None:
        self.class_colors = {c.id: c.color for c in classes}
        self.class_names = {c.id: c.name for c in classes}
        self.hidden_classes = {c.id for c in classes if not c.visible}
        self.update()

    def set_style(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.style, k):
                setattr(self.style, k, v)
        self.update()

    # ============================================================= BIEN DOI ==
    def to_screen(self, p) -> QPointF:
        return QPointF(p.x() * self._scale + self._offset.x(),
                       p.y() * self._scale + self._offset.y())

    def to_image(self, p) -> QPointF:
        return QPointF((p.x() - self._offset.x()) / self._scale,
                       (p.y() - self._offset.y()) / self._scale)

    @property
    def scale(self) -> float:
        return self._scale

    def fit_to_view(self) -> None:
        if not self.pixmap or self.img_w == 0:
            return
        margin = 16
        sw = (self.width() - margin * 2) / self.img_w
        sh = (self.height() - margin * 2) / self.img_h
        self._scale = max(0.02, min(sw, sh))
        self._center_image()
        self.zoomChanged.emit(self._scale)
        self.viewChanged.emit()
        self.update()

    def zoom_to_actual(self) -> None:
        self.set_zoom(1.0)

    def set_zoom(self, scale: float, anchor: QPointF | None = None) -> None:
        scale = max(0.03, min(40.0, scale))
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        img_pt = self.to_image(anchor)
        self._scale = scale
        self._offset = QPointF(anchor.x() - img_pt.x() * scale,
                               anchor.y() - img_pt.y() * scale)
        self.zoomChanged.emit(self._scale)
        self.viewChanged.emit()
        self.update()

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        self.set_zoom(self._scale * factor, anchor)

    def _center_image(self) -> None:
        self._offset = QPointF(
            (self.width() - self.img_w * self._scale) / 2,
            (self.height() - self.img_h * self._scale) / 2,
        )

    def viewport_image_rect(self) -> QRectF:
        tl = self.to_image(QPointF(0, 0))
        br = self.to_image(QPointF(self.width(), self.height()))
        return QRectF(tl, br)

    def resizeEvent(self, ev) -> None:  # noqa: D102
        super().resizeEvent(ev)
        if self.pixmap and self._scale <= 0:
            self.fit_to_view()
        self.viewChanged.emit()

    # ============================================================== UNDO ====
    def push_undo(self) -> None:
        self._undo.append([a.clone() for a in self.annotations])
        if len(self._undo) > self._max_history:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            self.statusMessage.emit("Không còn thao tác nào để hoàn tác")
            return
        self._redo.append([a.clone() for a in self.annotations])
        self.annotations = self._undo.pop()
        self.selected = {i for i in self.selected if i < len(self.annotations)}
        self._reset_transient()
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit("Đã hoàn tác")

    def redo(self) -> None:
        if not self._redo:
            self.statusMessage.emit("Không còn thao tác nào để làm lại")
            return
        self._undo.append([a.clone() for a in self.annotations])
        self.annotations = self._redo.pop()
        self.selected = {i for i in self.selected if i < len(self.annotations)}
        self._reset_transient()
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit("Đã làm lại")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    # =============================================================== TOOL ===
    def set_tool(self, tool: str) -> None:
        if tool == self.tool:
            return
        self.cancel_draft()
        self.tool = tool
        cursors = {
            TOOL_SELECT: Qt.ArrowCursor,
            TOOL_POLYGON: Qt.CrossCursor,
            TOOL_BBOX: Qt.CrossCursor,
            TOOL_BRUSH: Qt.BlankCursor,
            TOOL_ERASER: Qt.BlankCursor,
            TOOL_SPLIT: Qt.CrossCursor,
            TOOL_PAN: Qt.OpenHandCursor,
        }
        self.setCursor(cursors.get(tool, Qt.ArrowCursor))
        self.update()

    def cancel_draft(self) -> None:
        had = bool(self._draft or self._brush_path or self._split_line or self._bbox_start)
        self._reset_transient()
        self.update()
        if had:
            self.statusMessage.emit("Đã huỷ thao tác đang vẽ")

    def _reset_transient(self) -> None:
        self._draft = []
        self._brush_path = []
        self._split_line = []
        self._bbox_start = None
        self._drag_vertex = (-1, -1)
        self._drag_shape = False

    # ========================================================== SELECTION ===
    def select_all(self) -> None:
        self.selected = set(range(len(self.annotations)))
        self.update()
        self.selectionChanged.emit(sorted(self.selected))

    def clear_selection(self) -> None:
        self.selected.clear()
        self.update()
        self.selectionChanged.emit([])

    def select_index(self, idx: int, additive: bool = False) -> None:
        if idx < 0 or idx >= len(self.annotations):
            if not additive:
                self.clear_selection()
            return
        if additive:
            self.selected.symmetric_difference_update({idx})
        else:
            self.selected = {idx}
        self.update()
        self.selectionChanged.emit(sorted(self.selected))

    def selected_annotations(self) -> list[Annotation]:
        return [self.annotations[i] for i in sorted(self.selected)
                if 0 <= i < len(self.annotations)]

    # ============================================================ THAO TAC ===
    def delete_selected(self) -> None:
        if not self.selected:
            return
        self.push_undo()
        for i in sorted(self.selected, reverse=True):
            if 0 <= i < len(self.annotations):
                del self.annotations[i]
        n = len(self.selected)
        self.selected.clear()
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit([])
        self.statusMessage.emit(f"Đã xoá {n} đối tượng")

    def set_class_for_selected(self, class_id: int) -> None:
        if not self.selected:
            self.active_class_id = class_id
            self.statusMessage.emit(f"Lớp mặc định: {self.class_names.get(class_id, '?')}")
            return
        self.push_undo()
        for i in self.selected:
            a = self.annotations[i]
            a.class_id = class_id
            a.class_name = self.class_names.get(class_id, "")
            a.status = ANN_MANUAL
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit(
            f"Đã gán lớp “{self.class_names.get(class_id, '?')}” cho "
            f"{len(self.selected)} đối tượng")

    def set_confidence_for_selected(self, conf: float) -> None:
        if not self.selected:
            return
        self.push_undo()
        for i in self.selected:
            self.annotations[i].confidence = float(conf)
        self.annotationsChanged.emit()
        self.update()

    def merge_selected(self) -> None:
        if len(self.selected) < 2:
            self.statusMessage.emit("Hãy chọn ít nhất 2 đối tượng để gộp")
            return
        if not _HAS_SHAPELY:
            self.statusMessage.emit("Cần thư viện shapely để gộp vùng")
            return
        idxs = sorted(self.selected)
        polys = []
        for i in idxs:
            g = _to_shapely(self.annotations[i])
            if g is not None and not g.is_empty:
                polys.append(g)
        if len(polys) < 2:
            self.statusMessage.emit("Không đủ hình hợp lệ để gộp")
            return
        merged = unary_union(polys)
        base = self.annotations[idxs[0]].clone()
        self.push_undo()
        for i in reversed(idxs):
            del self.annotations[i]

        pieces = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]
        new_indices = []
        for geom in pieces:
            pts = _from_shapely(geom)
            if len(pts) < 3:
                continue
            a = base.clone()
            a.id = 0
            a.shape = SHAPE_POLYGON
            a.status = ANN_MANUAL
            a.source = "manual"
            a.set_points(pts)
            self.annotations.append(a)
            new_indices.append(len(self.annotations) - 1)
        self.selected = set(new_indices)
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit(f"Đã gộp {len(idxs)} đối tượng thành {len(new_indices)} vùng")

    def simplify_selected(self, tolerance_px: float = 1.5) -> None:
        if not self.selected or not _HAS_SHAPELY:
            return
        self.push_undo()
        for i in self.selected:
            g = _to_shapely(self.annotations[i])
            if g is None:
                continue
            simple = g.simplify(tolerance_px, preserve_topology=True)
            pts = _from_shapely(simple)
            if len(pts) >= 3:
                self.annotations[i].set_points(pts)
        self.update()
        self.annotationsChanged.emit()
        self.statusMessage.emit("Đã giản lược polygon")

    def convert_selected_to_polygon(self) -> None:
        """Bien bbox thanh polygon 4 dinh de co the sua bang brush."""
        if not self.selected:
            return
        self.push_undo()
        for i in self.selected:
            a = self.annotations[i]
            if len(a.polygon) < 6:
                a.set_points(a.bbox_polygon())
                a.shape = SHAPE_POLYGON
                a.status = ANN_MANUAL
        self.update()
        self.annotationsChanged.emit()

    # ============================================================== PAINT ====
    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#0A0A10"))

        if self.pixmap is None:
            p.setPen(QPen(QColor(COLORS["text_mute"])))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Chưa mở ảnh nào\nChọn một ảnh ở danh sách bên trái")
            return

        # --- anh ---
        target = QRectF(self._offset.x(), self._offset.y(),
                        self.img_w * self._scale, self.img_h * self._scale)
        p.setRenderHint(QPainter.SmoothPixmapTransform, self._scale < 3.0)
        p.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        p.setPen(QPen(QColor(COLORS["border_hi"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(target)

        # --- annotation ---
        for i, ann in enumerate(self.annotations):
            if ann.class_id in self.hidden_classes:
                continue
            self._draw_annotation(p, i, ann)

        # --- doi tuong dang ve ---
        self._draw_draft(p)
        self._draw_brush_cursor(p)

    def _color_of(self, ann: Annotation) -> QColor:
        if not self.style.show_class_color:
            return QColor(COLORS["accent"])
        return QColor(self.class_colors.get(ann.class_id, COLORS["accent"]))

    def _draw_annotation(self, p: QPainter, idx: int, ann: Annotation) -> None:
        color = self._color_of(ann)
        selected = idx in self.selected
        hovered = idx == self._hover_idx
        pts = ann.effective_points()
        if len(pts) < 2:
            return

        poly = QPolygonF([self.to_screen(QPointF(x, y)) for x, y in pts])
        fill = QColor(color)
        alpha = self.style.fill_opacity + (0.16 if selected else 0.0)
        fill.setAlphaF(min(0.85, alpha))
        lw = self.style.line_width + (1.2 if selected else 0.0)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, lw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolygon(poly)

        if hovered and not selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 150), lw + 0.8))
            p.drawPolygon(poly)

        # keypoints (pose)
        if ann.keypoints:
            self._draw_keypoints(p, ann, color)

        # dinh polygon khi duoc chon
        if selected:
            p.setPen(QPen(QColor("#FFFFFF"), 1.4))
            for j, (x, y) in enumerate(pts):
                sp = self.to_screen(QPointF(x, y))
                is_hover = self._hover_vertex == (idx, j)
                r = self.style.vertex_size / 2 + (1.8 if is_hover else 0)
                p.setBrush(QColor(color.lighter(150) if is_hover else "#FFFFFF"))
                p.drawEllipse(sp, r, r)

        # nhan
        if self.style.show_labels:
            self._draw_label(p, ann, poly, color)

    def _draw_keypoints(self, p: QPainter, ann: Annotation, color: QColor) -> None:
        kp = ann.keypoints
        step = 3 if len(kp) % 3 == 0 else 2
        p.setPen(QPen(QColor("#FFFFFF"), 1.2))
        for i in range(0, len(kp) - step + 1, step):
            x, y = kp[i], kp[i + 1]
            v = kp[i + 2] if step == 3 else 1.0
            if v <= 0.2:
                continue
            sp = self.to_screen(QPointF(x, y))
            p.setBrush(color.lighter(140))
            p.drawEllipse(sp, 3.0, 3.0)

    def _draw_label(self, p: QPainter, ann: Annotation, poly: QPolygonF,
                    color: QColor) -> None:
        name = ann.class_name or self.class_names.get(ann.class_id, "?")
        text = name
        if self.style.show_confidence and ann.confidence < 1.0:
            text += f" {ann.confidence:.2f}"
        f = QFont()
        f.setPixelSize(0)
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text) + 10
        th = fm.height() + 4

        br = poly.boundingRect()
        x = br.left()
        y = br.top() - th - 2
        if y < 2:
            y = br.top() + 2
        box = QRectF(x, y, tw, th)

        path = QPainterPath()
        path.addRoundedRect(box, 4, 4)
        bg = QColor(color)
        bg.setAlpha(232)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawPath(path)
        p.setPen(QPen(_readable_text(color)))
        p.drawText(box, Qt.AlignCenter, text)

    def _draw_draft(self, p: QPainter) -> None:
        accent = QColor(self.class_colors.get(self.active_class_id, COLORS["accent"]))

        if self.tool == TOOL_POLYGON and self._draft:
            pts = [self.to_screen(q) for q in self._draft]
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            path.lineTo(self._draft_cursor)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(accent, 1.8, Qt.DashLine))
            p.drawPath(path)
            if len(pts) >= 2:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1.2, Qt.DotLine))
                p.drawLine(self._draft_cursor, pts[0])
            p.setPen(QPen(QColor("#FFFFFF"), 1.3))
            for i, q in enumerate(pts):
                p.setBrush(accent if i else QColor("#FFFFFF"))
                p.drawEllipse(q, 4.0, 4.0)

        if self.tool == TOOL_BBOX and self._bbox_start is not None:
            a = self.to_screen(self._bbox_start)
            b = self._draft_cursor
            rect = QRectF(a, b).normalized()
            fill = QColor(accent)
            fill.setAlphaF(0.22)
            p.setBrush(fill)
            p.setPen(QPen(accent, 1.8, Qt.DashLine))
            p.drawRect(rect)

        if self.tool in (TOOL_BRUSH, TOOL_ERASER) and len(self._brush_path) >= 1:
            color = accent if self.tool == TOOL_BRUSH else QColor(COLORS["danger"])
            pen = QPen(color, self.brush_size * self._scale, Qt.SolidLine,
                       Qt.RoundCap, Qt.RoundJoin)
            c = QColor(color)
            c.setAlphaF(0.42)
            pen.setColor(c)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            if len(self._brush_path) == 1:
                p.drawPoint(self.to_screen(self._brush_path[0]))
            else:
                path = QPainterPath(self.to_screen(self._brush_path[0]))
                for q in self._brush_path[1:]:
                    path.lineTo(self.to_screen(q))
                p.drawPath(path)

        if self.tool == TOOL_SPLIT and len(self._split_line) >= 1:
            p.setPen(QPen(QColor(COLORS["warning"]), 2.0, Qt.DashLine))
            a = self.to_screen(self._split_line[0])
            b = self._draft_cursor if len(self._split_line) == 1 else \
                self.to_screen(self._split_line[1])
            p.drawLine(a, b)

    def _draw_brush_cursor(self, p: QPainter) -> None:
        if self.tool not in (TOOL_BRUSH, TOOL_ERASER):
            return
        pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(pos):
            return
        r = self.brush_size * self._scale / 2
        color = QColor(COLORS["accent_hi"]) if self.tool == TOOL_BRUSH \
            else QColor(COLORS["danger"])
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, 1.6))
        p.drawEllipse(QPointF(pos), r, r)
        p.setPen(QPen(QColor(0, 0, 0, 140), 1.0))
        p.drawEllipse(QPointF(pos), r + 1.2, r + 1.2)

    # =============================================================== CHUOT ==
    def mousePressEvent(self, ev) -> None:  # noqa: D102
        pos = ev.position()
        img_pt = self.to_image(pos)

        if ev.button() == Qt.MiddleButton or self._space_held or self.tool == TOOL_PAN:
            self._panning = True
            self._pan_start = pos.toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if ev.button() == Qt.RightButton:
            if self.tool == TOOL_POLYGON and len(self._draft) >= 3:
                self._finish_polygon()
            else:
                self.cancel_draft()
            return

        if ev.button() != Qt.LeftButton:
            return

        if self.tool == TOOL_SELECT:
            self._press_select(pos, img_pt, ev.modifiers())
        elif self.tool == TOOL_POLYGON:
            self._draft.append(img_pt)
            self._draft_cursor = pos
            self.statusMessage.emit(
                f"Polygon: {len(self._draft)} đỉnh — chuột phải hoặc Enter để đóng hình")
            self.update()
        elif self.tool == TOOL_BBOX:
            self._bbox_start = img_pt
            self._draft_cursor = pos
        elif self.tool in (TOOL_BRUSH, TOOL_ERASER):
            self._brush_path = [img_pt]
            self.update()
        elif self.tool == TOOL_SPLIT:
            self._split_line = [img_pt]
            self._draft_cursor = pos
            self.update()

    def mouseMoveEvent(self, ev) -> None:  # noqa: D102
        pos = ev.position()
        img_pt = self.to_image(pos)
        self._draft_cursor = pos

        if self._panning:
            delta = pos.toPoint() - self._pan_start
            self._offset += QPointF(delta.x(), delta.y())
            self._pan_start = pos.toPoint()
            self.viewChanged.emit()
            self.update()
            return

        if self._drag_vertex[0] >= 0:
            ai, vi = self._drag_vertex
            if 0 <= ai < len(self.annotations):
                a = self.annotations[ai]
                pts = a.points()
                if 0 <= vi < len(pts):
                    pts[vi] = (self._clampx(img_pt.x()), self._clampy(img_pt.y()))
                    a.set_points(pts)
                    a.status = ANN_MANUAL
                    self.update()
            return

        if self._drag_shape and self.selected:
            delta = img_pt - self._drag_origin
            for k, i in enumerate(sorted(self.selected)):
                if k >= len(self._shape_snapshot):
                    break
                src = self._shape_snapshot[k]
                a = self.annotations[i]
                if len(src.polygon) >= 6:
                    pts = [(self._clampx(x + delta.x()), self._clampy(y + delta.y()))
                           for x, y in src.points()]
                    a.set_points(pts)
                else:
                    a.bbox = [self._clampx(src.bbox[0] + delta.x()),
                              self._clampy(src.bbox[1] + delta.y()),
                              self._clampx(src.bbox[2] + delta.x()),
                              self._clampy(src.bbox[3] + delta.y())]
                a.status = ANN_MANUAL
            self.update()
            return

        if self.tool in (TOOL_BRUSH, TOOL_ERASER):
            if ev.buttons() & Qt.LeftButton:
                if not self._brush_path or _dist(self._brush_path[-1], img_pt) > \
                        max(0.8, 1.5 / self._scale):
                    self._brush_path.append(img_pt)
            self.update()
            return

        if self.tool == TOOL_SPLIT and self._split_line:
            self.update()
            return

        if self.tool in (TOOL_POLYGON, TOOL_BBOX):
            self.update()
            return

        # hover highlight
        self._update_hover(pos, img_pt)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: D102
        pos = ev.position()
        img_pt = self.to_image(pos)

        if self._panning:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor if self.tool == TOOL_PAN
                           else self._tool_cursor())
            return

        if self._drag_vertex[0] >= 0:
            self._drag_vertex = (-1, -1)
            self.annotationsChanged.emit()
            self.selectionChanged.emit(sorted(self.selected))
            return

        if self._drag_shape:
            self._drag_shape = False
            self._shape_snapshot = []
            self.annotationsChanged.emit()
            self.selectionChanged.emit(sorted(self.selected))
            return

        if self.tool == TOOL_BBOX and self._bbox_start is not None:
            self._finish_bbox(img_pt)
            return

        if self.tool in (TOOL_BRUSH, TOOL_ERASER) and self._brush_path:
            self._apply_brush()
            return

        if self.tool == TOOL_SPLIT and self._split_line:
            self._split_line.append(img_pt)
            self._apply_split()
            return

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: D102
        if self.tool == TOOL_POLYGON and len(self._draft) >= 3:
            self._finish_polygon()
            return
        pos = ev.position()
        idx = self._hit_test(pos)
        if idx < 0:
            self.doubleClickedEmpty.emit()
        elif self.tool == TOOL_SELECT:
            # them dinh moi vao canh gan nhat
            self._insert_vertex(idx, self.to_image(pos))

    def wheelEvent(self, ev) -> None:  # noqa: D102
        delta = ev.angleDelta().y()
        if delta == 0:
            return
        mods = ev.modifiers()
        if mods & Qt.AltModifier and self.tool in (TOOL_BRUSH, TOOL_ERASER):
            self.set_brush_size(self.brush_size * (1.12 if delta > 0 else 0.89))
            return
        factor = 1.16 if delta > 0 else 1 / 1.16
        self.zoom_by(factor, ev.position())

    def leaveEvent(self, ev) -> None:  # noqa: D102
        self._hover_idx = -1
        self._hover_vertex = (-1, -1)
        self.update()

    def _tool_cursor(self):
        return {
            TOOL_SELECT: Qt.ArrowCursor, TOOL_POLYGON: Qt.CrossCursor,
            TOOL_BBOX: Qt.CrossCursor, TOOL_BRUSH: Qt.BlankCursor,
            TOOL_ERASER: Qt.BlankCursor, TOOL_SPLIT: Qt.CrossCursor,
            TOOL_PAN: Qt.OpenHandCursor,
        }.get(self.tool, Qt.ArrowCursor)

    # ============================================================ BAN PHIM ==
    def keyPressEvent(self, ev) -> None:  # noqa: D102
        key = ev.key()
        if key == Qt.Key_Space:
            self._space_held = True
            self.setCursor(Qt.OpenHandCursor)
            return
        if key in (Qt.Key_Return, Qt.Key_Enter) and self.tool == TOOL_POLYGON:
            if len(self._draft) >= 3:
                self._finish_polygon()
                return
        if key == Qt.Key_Escape:
            self.cancel_draft()
            return
        if key == Qt.Key_Backspace and self.tool == TOOL_POLYGON and self._draft:
            self._draft.pop()
            self.update()
            return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev) -> None:  # noqa: D102
        if ev.key() == Qt.Key_Space:
            self._space_held = False
            self.setCursor(self._tool_cursor())
            return
        super().keyReleaseEvent(ev)

    # =========================================================== HIT TEST ===
    def _hit_test(self, pos) -> int:
        """Tra ve index annotation duoi con tro (uu tien vung nho nhat)."""
        best, best_area = -1, float("inf")
        for i, ann in enumerate(self.annotations):
            if ann.class_id in self.hidden_classes:
                continue
            pts = ann.effective_points()
            if len(pts) < 3:
                continue
            poly = QPolygonF([self.to_screen(QPointF(x, y)) for x, y in pts])
            if poly.containsPoint(pos, Qt.OddEvenFill):
                area = abs(poly.boundingRect().width() * poly.boundingRect().height())
                if area < best_area:
                    best, best_area = i, area
        return best

    def _vertex_at(self, pos) -> tuple[int, int]:
        tol = max(6.0, self.style.vertex_size)
        for i in sorted(self.selected):
            if not (0 <= i < len(self.annotations)):
                continue
            pts = self.annotations[i].effective_points()
            for j, (x, y) in enumerate(pts):
                sp = self.to_screen(QPointF(x, y))
                if abs(sp.x() - pos.x()) <= tol and abs(sp.y() - pos.y()) <= tol:
                    return (i, j)
        return (-1, -1)

    def _update_hover(self, pos, img_pt) -> None:
        v = self._vertex_at(pos)
        idx = self._hit_test(pos)
        if v != self._hover_vertex or idx != self._hover_idx:
            self._hover_vertex = v
            self._hover_idx = idx
            if v[0] >= 0:
                self.setCursor(Qt.SizeAllCursor)
            elif idx >= 0:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(self._tool_cursor())
            self.update()

    def _press_select(self, pos, img_pt, modifiers) -> None:
        v = self._vertex_at(pos)
        if v[0] >= 0:
            self.push_undo()
            self._drag_vertex = v
            return
        idx = self._hit_test(pos)
        additive = bool(modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
        if idx < 0:
            if not additive:
                self.clear_selection()
            return
        if idx not in self.selected:
            self.select_index(idx, additive)
        elif additive:
            self.select_index(idx, True)
            return
        # bat dau di chuyen
        self.push_undo()
        self._drag_shape = True
        self._drag_origin = img_pt
        self._shape_snapshot = [self.annotations[i].clone() for i in sorted(self.selected)]

    def _insert_vertex(self, idx: int, img_pt: QPointF) -> None:
        a = self.annotations[idx]
        pts = a.effective_points()
        if len(pts) < 3:
            return
        best_i, best_d = 0, float("inf")
        for i in range(len(pts)):
            p1 = pts[i]
            p2 = pts[(i + 1) % len(pts)]
            d = _point_segment_distance((img_pt.x(), img_pt.y()), p1, p2)
            if d < best_d:
                best_d, best_i = d, i
        self.push_undo()
        pts.insert(best_i + 1, (img_pt.x(), img_pt.y()))
        a.set_points(pts)
        a.shape = SHAPE_POLYGON
        a.status = ANN_MANUAL
        self.update()
        self.annotationsChanged.emit()
        self.statusMessage.emit("Đã thêm đỉnh mới")

    # ======================================================== TAO HINH MOI ==
    def _new_annotation(self, pts) -> Annotation:
        a = Annotation(
            class_id=self.active_class_id,
            class_name=self.class_names.get(self.active_class_id, ""),
            shape=SHAPE_POLYGON, confidence=1.0, status=ANN_MANUAL, source="manual",
        )
        a.set_points(pts)
        return a

    def _finish_polygon(self) -> None:
        pts = [(self._clampx(q.x()), self._clampy(q.y())) for q in self._draft]
        self._draft = []
        if len(pts) < 3:
            self.update()
            return
        self.push_undo()
        a = self._new_annotation(pts)
        self.annotations.append(a)
        idx = len(self.annotations) - 1
        self.selected = {idx}
        self.update()
        self.annotationsChanged.emit()
        self.newShapeCreated.emit(idx)
        self.selectionChanged.emit([idx])
        self.statusMessage.emit(f"Đã tạo polygon {len(pts)} đỉnh")

    def _finish_bbox(self, end: QPointF) -> None:
        start = self._bbox_start
        self._bbox_start = None
        if start is None:
            return
        x1, x2 = sorted([self._clampx(start.x()), self._clampx(end.x())])
        y1, y2 = sorted([self._clampy(start.y()), self._clampy(end.y())])
        if (x2 - x1) < 3 or (y2 - y1) < 3:
            self.update()
            return
        self.push_undo()
        a = self._new_annotation([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        self.annotations.append(a)
        idx = len(self.annotations) - 1
        self.selected = {idx}
        self.update()
        self.annotationsChanged.emit()
        self.newShapeCreated.emit(idx)
        self.selectionChanged.emit([idx])
        self.statusMessage.emit("Đã tạo khung bao")

    # ============================================================== BRUSH ===
    def set_brush_size(self, size: float) -> None:
        self.brush_size = max(2.0, min(400.0, float(size)))
        self.statusMessage.emit(f"Cỡ cọ: {self.brush_size:.0f} px")
        self.update()

    def _stroke_geometry(self):
        if not _HAS_SHAPELY or not self._brush_path:
            return None
        r = self.brush_size / 2.0
        if len(self._brush_path) == 1:
            q = self._brush_path[0]
            return Point(q.x(), q.y()).buffer(r, quad_segs=8)
        line = LineString([(q.x(), q.y()) for q in self._brush_path])
        return line.buffer(r, quad_segs=8, cap_style=1, join_style=1)

    def _apply_brush(self) -> None:
        stroke = self._stroke_geometry()
        self._brush_path = []
        if stroke is None or stroke.is_empty:
            if not _HAS_SHAPELY:
                self.statusMessage.emit("Cần thư viện shapely cho Cọ vẽ / Tẩy")
            self.update()
            return

        erase = self.tool == TOOL_ERASER
        targets = sorted(self.selected) if self.selected else []
        if not targets and not erase:
            # khong chon gi -> tao vung moi tu net brush
            self.push_undo()
            pts = _from_shapely(stroke)
            if len(pts) >= 3:
                a = self._new_annotation([(self._clampx(x), self._clampy(y)) for x, y in pts])
                self.annotations.append(a)
                idx = len(self.annotations) - 1
                self.selected = {idx}
                self.annotationsChanged.emit()
                self.newShapeCreated.emit(idx)
                self.selectionChanged.emit([idx])
                self.statusMessage.emit("Đã tạo vùng mới bằng cọ vẽ")
            self.update()
            return

        if not targets:
            # eraser ap dung cho moi hinh giao voi net
            targets = [i for i, a in enumerate(self.annotations)
                       if a.class_id not in self.hidden_classes
                       and _intersects(_to_shapely(a), stroke)]
            if not targets:
                self.update()
                return

        self.push_undo()
        removed = []
        added_pieces: list[tuple[Annotation, list]] = []
        for i in targets:
            a = self.annotations[i]
            g = _to_shapely(a)
            if g is None:
                continue
            new_geom = g.difference(stroke) if erase else g.union(stroke)
            if new_geom.is_empty:
                removed.append(i)
                continue
            geoms = list(new_geom.geoms) if isinstance(new_geom, MultiPolygon) else [new_geom]
            geoms = [g2 for g2 in geoms if g2.area > 4]
            if not geoms:
                removed.append(i)
                continue
            main = max(geoms, key=lambda g2: g2.area)
            pts = _from_shapely(main)
            if len(pts) < 3:
                removed.append(i)
                continue
            a.set_points([(self._clampx(x), self._clampy(y)) for x, y in pts])
            a.shape = SHAPE_POLYGON
            a.status = ANN_MANUAL
            for extra in geoms:
                if extra is main:
                    continue
                epts = _from_shapely(extra)
                if len(epts) >= 3:
                    added_pieces.append((a.clone(), epts))

        for i in sorted(removed, reverse=True):
            del self.annotations[i]
        for base, pts in added_pieces:
            nb = base.clone()
            nb.id = 0
            nb.set_points([(self._clampx(x), self._clampy(y)) for x, y in pts])
            self.annotations.append(nb)

        self.selected = {i for i in self.selected if i < len(self.annotations)}
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit("Tẩy đã cập nhật vùng" if erase
                                else "Cọ vẽ đã cập nhật vùng")

    # ============================================================== SPLIT ===
    def _apply_split(self) -> None:
        if len(self._split_line) < 2 or not _HAS_SHAPELY:
            self._split_line = []
            if not _HAS_SHAPELY:
                self.statusMessage.emit("Cần thư viện shapely cho công cụ Cắt đôi")
            self.update()
            return
        a0, a1 = self._split_line[0], self._split_line[1]
        self._split_line = []
        if _dist(a0, a1) < 3:
            self.update()
            return

        # keo dai duong cat de chac chan cat het hinh
        dx, dy = a1.x() - a0.x(), a1.y() - a0.y()
        length = math.hypot(dx, dy) or 1.0
        ext = max(self.img_w, self.img_h) * 1.5
        ux, uy = dx / length, dy / length
        line = LineString([
            (a0.x() - ux * ext, a0.y() - uy * ext),
            (a1.x() + ux * ext, a1.y() + uy * ext),
        ])

        candidates = sorted(self.selected) if self.selected else [
            i for i, a in enumerate(self.annotations)
            if a.class_id not in self.hidden_classes and _intersects(_to_shapely(a), line)
        ]
        if not candidates:
            self.statusMessage.emit("Đường cắt không đi qua đối tượng nào")
            self.update()
            return

        self.push_undo()
        new_selection = set()
        for i in sorted(candidates, reverse=True):
            a = self.annotations[i]
            g = _to_shapely(a)
            if g is None or not line.intersects(g):
                continue
            try:
                pieces = list(shapely_split(g, line).geoms)
            except Exception:
                continue
            pieces = [p for p in pieces if p.area > 6]
            if len(pieces) < 2:
                continue
            del self.annotations[i]
            for piece in pieces:
                pts = _from_shapely(piece)
                if len(pts) < 3:
                    continue
                nb = a.clone()
                nb.id = 0
                nb.shape = SHAPE_POLYGON
                nb.status = ANN_MANUAL
                nb.source = "manual"
                nb.set_points(pts)
                self.annotations.append(nb)
                new_selection.add(len(self.annotations) - 1)

        self.selected = new_selection
        self.update()
        self.annotationsChanged.emit()
        self.selectionChanged.emit(sorted(self.selected))
        self.statusMessage.emit(f"Đã tách thành {len(new_selection)} vùng")

    # ============================================================= HELPERS ==
    def _clampx(self, v: float) -> float:
        return max(0.0, min(float(self.img_w), float(v)))

    def _clampy(self, v: float) -> float:
        return max(0.0, min(float(self.img_h), float(v)))


# ============================================================== NAVIGATOR ===
class Navigator(QWidget):
    """Minimap: anh thu nho + khung the hien vung dang xem."""

    navigate = Signal(QPointF)   # toa do anh nguoi dung click

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setCursor(Qt.PointingHandCursor)
        self._thumb: QPixmap | None = None
        self._img_size = (0, 0)
        self._view_rect = QRectF()
        self._annotations: list[tuple[list, str]] = []

    def set_image(self, pixmap: QPixmap | None) -> None:
        if pixmap is None or pixmap.isNull():
            self._thumb = None
            self._img_size = (0, 0)
        else:
            self._img_size = (pixmap.width(), pixmap.height())
            self._thumb = pixmap.scaled(360, 360, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation)
        self.update()

    def set_view_rect(self, rect: QRectF) -> None:
        self._view_rect = rect
        self.update()

    def set_annotations(self, annotations, colors: dict) -> None:
        self._annotations = []
        for a in annotations:
            pts = a.effective_points()
            if len(pts) >= 3:
                self._annotations.append((pts, colors.get(a.class_id, COLORS["accent"])))
        self.update()

    def _thumb_rect(self) -> QRectF:
        if self._thumb is None:
            return QRectF()
        tw, th = self._thumb.width(), self._thumb.height()
        scale = min((self.width() - 8) / tw, (self.height() - 8) / th, 1.0)
        w, h = tw * scale, th * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(COLORS["bg_alt"]))
        if self._thumb is None:
            p.setPen(QPen(QColor(COLORS["text_mute"])))
            p.drawText(self.rect(), Qt.AlignCenter, "Navigator")
            return

        tr = self._thumb_rect()
        p.drawPixmap(tr, self._thumb, QRectF(self._thumb.rect()))
        p.setPen(QPen(QColor(COLORS["border_hi"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(tr)

        iw, ih = self._img_size
        if iw and ih:
            sx, sy = tr.width() / iw, tr.height() / ih
            for pts, color in self._annotations:
                poly = QPolygonF([QPointF(tr.left() + x * sx, tr.top() + y * sy)
                                  for x, y in pts])
                c = QColor(color)
                c.setAlphaF(0.55)
                p.setBrush(c)
                p.setPen(QPen(QColor(color), 0.8))
                p.drawPolygon(poly)

            if not self._view_rect.isEmpty():
                r = QRectF(
                    tr.left() + max(0.0, self._view_rect.left()) * sx,
                    tr.top() + max(0.0, self._view_rect.top()) * sy,
                    min(iw, self._view_rect.width()) * sx,
                    min(ih, self._view_rect.height()) * sy,
                )
                p.setBrush(QColor(255, 255, 255, 22))
                p.setPen(QPen(QColor(COLORS["danger"]), 1.6))
                p.drawRect(r.intersected(tr))

    def mousePressEvent(self, ev) -> None:  # noqa: D102
        tr = self._thumb_rect()
        if tr.isEmpty() or not tr.contains(ev.position()):
            return
        iw, ih = self._img_size
        rel_x = (ev.position().x() - tr.left()) / tr.width()
        rel_y = (ev.position().y() - tr.top()) / tr.height()
        self.navigate.emit(QPointF(rel_x * iw, rel_y * ih))


# ============================================================== SHAPELY IO ==
def _to_shapely(ann: Annotation):
    if not _HAS_SHAPELY or ann is None:
        return None
    pts = ann.effective_points()
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if not poly.is_empty else None
    except Exception:
        return None


def _from_shapely(geom) -> list[tuple[float, float]]:
    """Doi hinh shapely thanh danh sach dinh.

    Dinh dang YOLO segmentation chi luu mot vong dinh, khong ho tro lo. Neu hinh
    co lo (vd sau khi dung Eraser o giua vung), ta noi lo vao vien ngoai bang ky
    thuat "keyhole": di theo vien ngoai toi diem gan nhat, vong quanh lo roi quay
    lai. Ket qua ve bang quy tac even-odd se hien dung phan lo bi khoet.
    """
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    try:
        ring = _ring(geom.exterior)
    except AttributeError:
        return []
    if not ring:
        return []
    for interior in getattr(geom, "interiors", []):
        hole = _ring(interior)
        if len(hole) >= 3:
            ring = _splice_hole(ring, hole)
    return ring


def _ring(linear_ring) -> list[tuple[float, float]]:
    coords = list(linear_ring.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]


def _splice_hole(outer: list, hole: list) -> list:
    """Noi mot vong lo vao vien ngoai tai cap dinh gan nhau nhat."""
    best = (0, 0, float("inf"))
    for i, (ox, oy) in enumerate(outer):
        for j, (hx, hy) in enumerate(hole):
            d = (ox - hx) ** 2 + (oy - hy) ** 2
            if d < best[2]:
                best = (i, j, d)
    i, j, _ = best
    return (outer[: i + 1] + hole[j:] + hole[: j + 1] + outer[i:])


def _intersects(geom, other) -> bool:
    if geom is None or other is None:
        return False
    try:
        return geom.intersects(other)
    except Exception:
        return False


def _dist(a: QPointF, b: QPointF) -> float:
    return math.hypot(a.x() - b.x(), a.y() - b.y())


def _point_segment_distance(p, a, b) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _readable_text(bg: QColor) -> QColor:
    lum = (0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()) / 255
    return QColor("#0B0B12") if lum > 0.62 else QColor("#FFFFFF")


__all__ = [
    "AnnotationCanvas", "Navigator", "CanvasStyle",
    "TOOL_SELECT", "TOOL_POLYGON", "TOOL_BRUSH", "TOOL_ERASER",
    "TOOL_SPLIT", "TOOL_BBOX", "TOOL_PAN",
]
