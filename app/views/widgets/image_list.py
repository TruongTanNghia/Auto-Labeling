"""Danh sach anh: che do list gon (co dot trang thai) va che do luoi thumbnail."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
)

from app.constants import COLORS, IMG_UNLABELED, get_image_status_label
from app.i18n import tr
from app.models.entities import ImageRecord
from app.theme import icons

ROLE_ID = Qt.UserRole + 1
ROLE_STATUS = Qt.UserRole + 2
ROLE_PATH = Qt.UserRole + 3
ROLE_NOBJ = Qt.UserRole + 4
ROLE_DUP = Qt.UserRole + 5
ROLE_CLASS_COLOR = Qt.UserRole + 6


# ======================================================== THUMBNAIL LOADER ===
class ThumbnailLoader(QThread):
    """Nap thumbnail o thread nen de cuon danh sach khong bi giat."""

    loaded = Signal(str, QPixmap)

    def __init__(self, size: int = 132, parent=None) -> None:
        super().__init__(parent)
        self._queue: list[str] = []
        self._size = size
        self._running = True

    def request(self, path: str) -> None:
        if path not in self._queue:
            self._queue.append(path)
        if not self.isRunning():
            self.start()

    def clear(self) -> None:
        self._queue.clear()

    def stop(self) -> None:
        self._running = False
        self._queue.clear()
        self.wait(1500)

    def run(self) -> None:  # noqa: D102
        while self._running:
            if not self._queue:
                self.msleep(40)
                continue
            path = self._queue.pop(0)
            try:
                pm = QPixmap(path)
                if not pm.isNull():
                    pm = pm.scaled(
                        self._size, self._size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.loaded.emit(path, pm)
            except Exception:
                pass


# ============================================================== DELEGATES ===
class _CompactDelegate(QStyledItemDelegate):
    """Mot dong: dot trang thai + ten file + so doi tuong."""

    def sizeHint(self, option, index) -> QSize:  # noqa: D102
        return QSize(120, 30)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: D102
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        from PySide6.QtWidgets import QStyle

        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        box = QRect(r.left() + 3, r.top() + 2, r.width() - 6, r.height() - 4)
        if selected:
            painter.setBrush(QColor(COLORS["accent_soft"]))
            painter.setPen(QPen(QColor(COLORS["accent"]), 1))
            painter.drawRoundedRect(box, 7, 7)
        elif hovered:
            painter.setBrush(QColor(COLORS["surface"]))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(box, 7, 7)

        class_color = index.data(ROLE_CLASS_COLOR)
        status = index.data(ROLE_STATUS) or IMG_UNLABELED
        n = index.data(ROLE_NOBJ) or 0
        if not selected and (n == 0 or status == IMG_UNLABELED or not class_color):
            color = COLORS["text_mute"]
        elif class_color:
            color = class_color
        else:
            _, color = get_image_status_label().get(status, ("", COLORS["text_mute"]))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        cy = r.center().y()
        painter.drawEllipse(r.left() + 12, cy - 3, 7, 7)

        name = index.data(Qt.DisplayRole) or ""
        painter.setPen(QPen(QColor(COLORS["text"] if selected else COLORS["text"])))
        painter.setFont(QFont("Segoe UI", 9))
        text_rect = QRect(r.left() + 26, r.top(), r.width() - 76, r.height())
        fm = painter.fontMetrics()
        painter.drawText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            fm.elidedText(str(name), Qt.ElideMiddle, text_rect.width()),
        )

        if n is not None:
            painter.setPen(QPen(QColor(COLORS["accent_hi"] if selected else COLORS["text_dim"])))
            painter.drawText(
                QRect(r.right() - 46, r.top(), 32, r.height()),
                Qt.AlignVCenter | Qt.AlignRight,
                str(n),
            )
        if index.data(ROLE_DUP):
            painter.drawPixmap(r.right() - 14, cy - 6, icons.pixmap("copy", COLORS["warning"], 12))
        painter.restore()


class _GalleryDelegate(QStyledItemDelegate):
    """O luoi: thumbnail + vien mau trang thai + ten file."""

    def __init__(self, cell: int = 148, parent=None) -> None:
        super().__init__(parent)
        self.cell = cell

    def sizeHint(self, option, index) -> QSize:  # noqa: D102
        return QSize(self.cell, self.cell + 24)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: D102
        from PySide6.QtWidgets import QStyle

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        r = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        class_color = index.data(ROLE_CLASS_COLOR)
        status = index.data(ROLE_STATUS) or IMG_UNLABELED
        n = index.data(ROLE_NOBJ) or 0
        if not selected and (n == 0 or status == IMG_UNLABELED or not class_color):
            color = COLORS["text_mute"]
        elif class_color:
            color = class_color
        else:
            _, color = get_image_status_label().get(status, ("", COLORS["text_mute"]))

        pad = 5
        img_box = QRect(
            r.left() + pad, r.top() + pad, r.width() - pad * 2, r.height() - pad * 2 - 20
        )
        painter.setBrush(QColor(COLORS["bg"]))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(img_box, 8, 8)

        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            pm = icon.pixmap(img_box.size())
        elif isinstance(icon, QPixmap):
            pm = icon
        else:
            pm = None
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(img_box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = img_box.left() + (img_box.width() - scaled.width()) // 2
            y = img_box.top() + (img_box.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.setPen(QPen(QColor(COLORS["text_mute"])))
            painter.drawText(img_box, Qt.AlignCenter, "…")

        pen_color = (
            QColor(color if selected else (COLORS["border_hi"] if hovered else COLORS["border"]))
        )
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(pen_color, 2 if selected else 1))
        painter.drawRoundedRect(img_box, 8, 8)

        # dai mau trang thai o goc tren
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRect(img_box.left() + 6, img_box.top() + 6, 22, 5), 3, 3)

        n = index.data(ROLE_NOBJ)
        if n:
            badge = QRect(img_box.right() - 26, img_box.top() + 5, 21, 15)
            painter.setBrush(QColor(0, 0, 0, 175))
            painter.drawRoundedRect(badge, 5, 5)
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(badge, Qt.AlignCenter, str(n))

        painter.setPen(QPen(QColor(COLORS["text"] if selected else COLORS["text_dim"])))
        painter.setFont(QFont("Segoe UI", 8))
        name_rect = QRect(r.left() + 4, img_box.bottom() + 3, r.width() - 8, 17)
        fm = painter.fontMetrics()
        painter.drawText(
            name_rect,
            Qt.AlignCenter,
            fm.elidedText(str(index.data(Qt.DisplayRole) or ""), Qt.ElideMiddle, name_rect.width()),
        )
        painter.restore()


# =========================================================== IMAGE LIST =====
class ImageListPanel(QListWidget):
    """Danh sach anh gon nhe - dung o trang Auto Label va Editor."""

    imageSelected = Signal(int)  # image_id
    selectionIds = Signal(list)

    def __init__(self, parent=None, multi: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("ThumbList")
        self.setItemDelegate(_CompactDelegate(self))
        self.setSelectionMode(
            QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection
        )
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self._by_id: dict[int, QListWidgetItem] = {}
        self.currentItemChanged.connect(self._on_current)
        self.itemSelectionChanged.connect(self._on_selection)

    # ---------------------------------------------------------------- API ---
    def set_images(
        self, records: list[ImageRecord], image_colors: dict[int, str] | None = None
    ) -> None:
        self.blockSignals(True)
        self.clear()
        self._by_id.clear()
        image_colors = image_colors or {}
        for rec in records:
            item = QListWidgetItem(rec.filename)
            item.setData(ROLE_ID, rec.id)
            item.setData(ROLE_STATUS, rec.status)
            item.setData(ROLE_PATH, rec.path)
            item.setData(ROLE_NOBJ, rec.n_objects)
            item.setData(ROLE_DUP, rec.is_duplicate)
            item.setData(ROLE_CLASS_COLOR, image_colors.get(rec.id, ""))
            obj_str = tr("image_list.objects_unit", "{count} đối tượng", count=rec.n_objects)
            status_str = tr(f"status.{rec.status}", rec.status)
            item.setToolTip(f"{rec.path}\n{rec.width}x{rec.height} | {obj_str} | {status_str}")
            self.addItem(item)
            self._by_id[rec.id] = item
        self.blockSignals(False)

    def update_item(
        self,
        image_id: int,
        status: str | None = None,
        n_objects: int | None = None,
        class_color: str | None = None,
    ) -> None:
        item = self._by_id.get(image_id)
        if item is None:
            return
        if status is not None:
            item.setData(ROLE_STATUS, status)
        if n_objects is not None:
            item.setData(ROLE_NOBJ, n_objects)
        if class_color is not None:
            item.setData(ROLE_CLASS_COLOR, class_color)
        self.viewport().update()

    def select_id(self, image_id: int) -> None:
        item = self._by_id.get(image_id)
        if item is not None:
            self.setCurrentItem(item)
            self.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    def current_id(self) -> int:
        item = self.currentItem()
        return int(item.data(ROLE_ID)) if item else 0

    def selected_ids(self) -> list[int]:
        return [int(i.data(ROLE_ID)) for i in self.selectedItems()]

    def all_ids(self) -> list[int]:
        return [int(self.item(i).data(ROLE_ID)) for i in range(self.count())]

    def step(self, delta: int) -> None:
        row = self.currentRow()
        nrow = max(0, min(self.count() - 1, row + delta))
        if nrow != row:
            self.setCurrentRow(nrow)

    # ------------------------------------------------------------- signals --
    def _on_current(self, cur, _prev) -> None:
        if cur is not None:
            self.imageSelected.emit(int(cur.data(ROLE_ID)))

    def _on_selection(self) -> None:
        self.selectionIds.emit(self.selected_ids())


# ============================================================== GALLERY =====
class ImageGallery(QListWidget):
    """Luoi thumbnail voi nap anh lazy - dung o Dataset Manager."""

    imageActivated = Signal(int)
    selectionIds = Signal(list)

    def __init__(self, parent=None, cell: int = 150) -> None:
        super().__init__(parent)
        self.setObjectName("ThumbList")
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSpacing(6)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setItemDelegate(_GalleryDelegate(cell, self))
        self.setIconSize(QSize(cell - 12, cell - 12))
        self._cell = cell
        self._by_path: dict[str, QListWidgetItem] = {}
        self._by_id: dict[int, QListWidgetItem] = {}

        self._loader = ThumbnailLoader(cell)
        self._loader.loaded.connect(self._on_thumb)
        self.itemDoubleClicked.connect(lambda it: self.imageActivated.emit(int(it.data(ROLE_ID))))
        self.itemSelectionChanged.connect(lambda: self.selectionIds.emit(self.selected_ids()))

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(90)
        self._scroll_timer.timeout.connect(self._request_visible)
        self.verticalScrollBar().valueChanged.connect(self._scroll_timer.start)

    # ---------------------------------------------------------------- API ---
    def set_images(self, records: list[ImageRecord]) -> None:
        self._loader.clear()
        self.blockSignals(True)
        self.clear()
        self._by_path.clear()
        self._by_id.clear()
        for rec in records:
            item = QListWidgetItem(rec.filename)
            item.setData(ROLE_ID, rec.id)
            item.setData(ROLE_STATUS, rec.status)
            item.setData(ROLE_PATH, rec.path)
            item.setData(ROLE_NOBJ, rec.n_objects)
            item.setData(ROLE_DUP, rec.is_duplicate)
            item.setSizeHint(QSize(self._cell, self._cell + 24))
            obj_str = tr("image_list.objects_unit", "{count} đối tượng", count=rec.n_objects)
            status_str = tr(f"status.{rec.status}", rec.status)
            item.setToolTip(
                f"{Path(rec.path).name}\n{rec.width}x{rec.height}\n"
                f"{obj_str} | {status_str}"
                + (f"\nBlur: {rec.blur_score:.0f}" if rec.blur_score else "")
            )
            self.addItem(item)
            self._by_path[rec.path] = item
            self._by_id[rec.id] = item
        self.blockSignals(False)
        QTimer.singleShot(30, self._request_visible)

    def set_cell_size(self, cell: int) -> None:
        self._cell = cell
        self.setItemDelegate(_GalleryDelegate(cell, self))
        self.setIconSize(QSize(cell - 12, cell - 12))
        for i in range(self.count()):
            self.item(i).setSizeHint(QSize(cell, cell + 24))
        self._request_visible()

    def selected_ids(self) -> list[int]:
        return [int(i.data(ROLE_ID)) for i in self.selectedItems()]

    def refresh_item(
        self, image_id: int, status: str | None = None, n_objects: int | None = None
    ) -> None:
        item = self._by_id.get(image_id)
        if item is None:
            return
        if status is not None:
            item.setData(ROLE_STATUS, status)
        if n_objects is not None:
            item.setData(ROLE_NOBJ, n_objects)
        self.viewport().update()

    def stop(self) -> None:
        self._loader.stop()

    # ------------------------------------------------------------- private --
    def _request_visible(self) -> None:
        rect = self.viewport().rect().adjusted(0, -240, 0, 240)
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.DecorationRole) is not None:
                continue
            if rect.intersects(self.visualItemRect(item)):
                self._loader.request(item.data(ROLE_PATH))

    def _on_thumb(self, path: str, pixmap: QPixmap) -> None:
        item = self._by_path.get(path)
        if item is not None:
            item.setData(Qt.DecorationRole, pixmap)

    def resizeEvent(self, ev) -> None:  # noqa: D102
        super().resizeEvent(ev)
        self._scroll_timer.start()
