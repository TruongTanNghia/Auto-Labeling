"""Trang Annotation Editor: sua nhan bang polygon / brush / eraser / split / merge."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QColorDialog,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    ANN_APPROVED,
    ANN_MANUAL,
    ANN_REVIEW,
    COLORS,
    IMG_APPROVED,
    SHAPE_POLYGON,
    get_image_status_label,
)
from app.core.inference import InferenceConfig
from app.i18n import tr
from app.models.entities import Annotation, ImageRecord
from app.theme import icons
from app.views.pages.base_page import BasePage
from app.views.widgets.canvas import (
    TOOL_BBOX,
    TOOL_BRUSH,
    TOOL_ERASER,
    TOOL_PAN,
    TOOL_POLYGON,
    TOOL_SELECT,
    TOOL_SMART_SELECT,
    TOOL_SPLIT,
    AnnotationCanvas,
    Navigator,
)
from app.views.widgets.common import (
    Card,
    Field,
    IconButton,
    SliderField,
    combo,
    dspin,
    ghost_button,
    hline,
    label,
    primary_button,
    vline,
)
from app.views.widgets.image_list import ImageListPanel, ROLE_ID
from app.workers.autolabel_worker import SingleImageInferWorker
from app.workers.sam_worker import SmartSelectWorker

CLASS_ROLE = Qt.UserRole + 11
OBJ_ROLE = Qt.UserRole + 12

_ACTIVE_SAM_WORKERS: set[object] = set()


class DraggableObjectMenuDialog(QDialog):
    """Menu thao tác đối tượng có thể kéo thả và tự động giới hạn khung hình."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup)
        self.setObjectName("DraggableObjectMenu")
        self.setStyleSheet(
            f"#DraggableObjectMenu {{"
            f"  background: {COLORS['surface_alt']};"
            f"  border: 1px solid {COLORS['border_hi']};"
            f"  border-radius: 10px;"
            f"}}"
        )
        self._drag_pos = QPoint()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(4, 2, 4, 4)
        hl.setSpacing(6)
        lbl = label(tr("editor.objects_on_image", "Đối tượng trên ảnh"), bold=True, size=11, color=COLORS["text_dim"])
        hl.addWidget(lbl)
        hl.addStretch(1)
        lay.addWidget(header)
        lay.addWidget(hline())

        self.buttons_lay = QVBoxLayout()
        self.buttons_lay.setSpacing(3)
        lay.addLayout(self.buttons_lay)

    def add_menu_action(self, title: str, icon_name: str = "", color: str = "", callback=None):
        btn = ghost_button(title, icon_name if icon_name else None)
        style = "QPushButton { text-align: left; padding: 6px 12px; border-radius: 6px; font-size: 12px; }"
        if color:
            style += f" QPushButton {{ color: {color}; }}"
        btn.setStyleSheet(style + f" QPushButton:hover {{ background: {COLORS['surface']}; }}")

        def _on_click():
            self.accept()
            if callback:
                callback()

        btn.clicked.connect(_on_click)
        self.buttons_lay.addWidget(btn)
        return btn

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            ev.accept()

    def mouseMoveEvent(self, ev) -> None:
        if ev.buttons() & Qt.LeftButton and not self._drag_pos.isNull():
            self.move(ev.globalPosition().toPoint() - self._drag_pos)
            ev.accept()


class EditorPage(BasePage):
    TITLE = tr("nav.editor", "Sửa nhãn")
    SUBTITLE = tr("editor.subtitle", "Kiểm tra và tinh chỉnh nhãn với bộ công cụ chuyên nghiệp")
    ICON = "pen"

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._images: list[ImageRecord] = []
        self._image_id: int = 0
        self.current_idx: int = -1
        self._dirty = False
        self._loading = False
        self._sam_worker: SmartSelectWorker | None = None
        self._sam_target_image_id: int | None = None
        self._sam_running: bool = False
        self._sam_last_msg: str = ""
        self._sam_last_prog: int = 0

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.autolabel_btn = ghost_button(tr("editor.autolabel_this", "Gán nhãn ảnh này"), "wand")
        self.autolabel_btn.clicked.connect(self.auto_label_current)
        self.save_btn = ghost_button(tr("editor.save_shortcut", "Lưu  (Ctrl+S)"), "save")
        self.save_btn.clicked.connect(lambda: self.save_current(toast=True))
        self.approve_btn = primary_button(
            tr("editor.approve_next", "Duyệt && sang ảnh sau"), "check"
        )
        self.approve_btn.clicked.connect(self.approve_and_next)
        for b in (self.autolabel_btn, self.save_btn, self.approve_btn):
            self.header.add_action(b)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {COLORS['surface_alt']}; border: 1px solid {COLORS['border']}; border-radius: 2px; }}"
            f"QSplitter::handle:hover {{ background: {COLORS['accent']}; }}"
        )
        self.main_splitter.addWidget(self._build_left())
        self.main_splitter.addWidget(self._build_center())
        self.main_splitter.addWidget(self._build_right())
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([240, 850, 310])
        self.add(self.main_splitter, 1)

        self._install_shortcuts()
        self.ctrl.imagesChanged.connect(self.refresh)
        self.ctrl.classesChanged.connect(self._reload_classes)
        self.ctrl.currentImageChanged.connect(self._external_image_change)

    # ------------------------------------------------------------- ben trai --
    def _build_left(self) -> QWidget:
        wrap = QWidget()
        wrap.setMinimumWidth(200)
        wrap.setMaximumWidth(450)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        img_card = Card(
            tr("editor.image_card", "Ảnh"), "", "image", margins=(12, 11, 12, 12), spacing=8
        )
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.filter_combo = combo(
            [
                ("all", tr("editor.filter_all", "Tất cả")),
                ("review", tr("editor.filter_review", "Cần xem lại")),
                ("unlabeled", tr("editor.filter_unlabeled", "Chưa gán nhãn")),
                ("approved", tr("editor.filter_approved", "Đã duyệt")),
            ]
        )
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.filter_combo, 1)

        self.delete_image_btn = IconButton(
            "trash", tr("editor.delete_image", "Xoá ảnh hiện tại khỏi project  (Shift+Del)")
        )
        self.delete_image_btn.clicked.connect(self._delete_current_image)
        filter_row.addWidget(self.delete_image_btn)
        img_card.add(filter_row)

        self.image_list = ImageListPanel(multi=False)
        self.image_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.image_list.customContextMenuRequested.connect(self._image_menu)
        self.image_list.imageSelected.connect(self.load_image)
        img_card.add(self.image_list, 1)
        lay.addWidget(img_card, 3)

        class_card = Card(
            tr("editor.class_card", "Lớp đối tượng"),
            "",
            "layers",
            margins=(12, 11, 12, 12),
            spacing=8,
        )
        self.class_list = QListWidget()
        self.class_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.class_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.class_list.customContextMenuRequested.connect(self._class_menu)
        self.class_list.currentItemChanged.connect(self._on_class_selected)
        self.class_list.itemDoubleClicked.connect(self._assign_class_to_selection)
        class_card.add(self.class_list, 1)
        add_class_btn = ghost_button(tr("editor.add_class", "Thêm lớp"), "plus")
        add_class_btn.clicked.connect(self._add_class)
        class_card.add(add_class_btn)
        lay.addWidget(class_card, 2)
        return wrap

    # ------------------------------------------------------------- o giua ----
    def _build_center(self) -> QWidget:
        wrap = QWidget()
        wrap.setMinimumWidth(400)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)

        lay.addWidget(self._build_toolbar())
        self.tool_options_bar = self._build_tool_options_bar()
        lay.addWidget(self.tool_options_bar)
        self.notif_banner = self._build_notification_banner()
        lay.addWidget(self.notif_banner)

        self.canvas = AnnotationCanvas()
        self.canvas.annotationsChanged.connect(self._on_canvas_changed)
        self.canvas.selectionChanged.connect(self._on_canvas_selection)
        self.canvas.statusMessage.connect(self._set_status)
        self.canvas.zoomChanged.connect(self._on_zoom)
        self.canvas.viewChanged.connect(self._sync_navigator)
        self.canvas.newShapeCreated.connect(lambda _i: self._refresh_object_list())
        self.canvas.smartSelectTriggered.connect(self._on_smart_select)
        lay.addWidget(self.canvas, 1)

        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(9)
        self.prev_btn = ghost_button(tr("editor.prev_image", "Ảnh trước  (A)"), "chevron_left")
        self.prev_btn.clicked.connect(lambda: self.step_image(-1))
        self.next_btn = ghost_button(tr("editor.next_image", "Ảnh sau  (D)"), "chevron_right")
        self.next_btn.clicked.connect(lambda: self.step_image(1))
        self.pos_label = label("0 / 0", bold=True, size=12.5)
        self.pos_label.setAlignment(Qt.AlignCenter)
        self.status_label = label("", size=11.5, color=COLORS["text_mute"])
        bl.addWidget(self.prev_btn)
        bl.addWidget(self.pos_label)
        bl.addWidget(self.next_btn)
        bl.addSpacing(14)
        bl.addWidget(self.status_label, 1)
        self.zoom_label = label("100%", size=11.5, color=COLORS["text_dim"])
        bl.addWidget(self.zoom_label)
        lay.addWidget(bottom)
        return wrap

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("CardFlat")
        bar.setStyleSheet(
            f"#CardFlat {{ background: {COLORS['surface_alt']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 11px; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(6)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.TOOL_META = {
            TOOL_SELECT: (
                "move",
                tr("editor.tool_select", "Chọn"),
                "V",
                tr(
                    "editor.tool_select_desc",
                    "Chọn đối tượng, kéo để di chuyển, kéo đỉnh để chỉnh hình.\nNháy đúp lên cạnh để thêm đỉnh mới.",
                ),
            ),
            TOOL_SMART_SELECT: (
                "wand",
                tr("editor.tool_smart_select", "Chọn thông minh"),
                "Q",
                tr(
                    "editor.tool_smart_select_desc",
                    "Nhấp điểm hoặc kéo khung bao để SAM tự động khoanh vùng đối tượng.",
                ),
            ),
            TOOL_POLYGON: (
                "polygon",
                tr("editor.tool_polygon", "Polygon"),
                "W",
                tr(
                    "editor.tool_polygon_desc",
                    "Bấm để thêm từng đỉnh. Chuột phải hoặc Enter để đóng hình,\nBackspace để bỏ đỉnh vừa thêm, Esc để huỷ.",
                ),
            ),
            TOOL_BBOX: (
                "crop",
                tr("editor.tool_bbox", "Hộp bao"),
                "",
                tr("editor.tool_bbox_desc", "Kéo chuột để tạo một khung bao chữ nhật."),
            ),
            TOOL_BRUSH: (
                "brush",
                tr("editor.tool_brush", "Cọ vẽ"),
                "B",
                tr(
                    "editor.tool_brush_desc",
                    "Tô thêm vào vùng đang chọn. Chưa chọn gì thì tạo vùng mới.\nAlt + cuộn chuột để đổi cỡ cọ.",
                ),
            ),
            TOOL_ERASER: (
                "eraser",
                tr("editor.tool_eraser", "Tẩy"),
                "E",
                tr("editor.tool_eraser_desc", "Xoá bớt vùng. Tẩy ở giữa sẽ tạo lỗ trong mask."),
            ),
            TOOL_SPLIT: (
                "split",
                tr("editor.tool_split", "Cắt đôi"),
                "S",
                "Kẻ một đường cắt ngang để tách vùng làm hai.",
            ),
            TOOL_PAN: (
                "hand",
                tr("editor.tool_pan", "Di chuyển"),
                "",
                "Kéo để di chuyển ảnh. Cách khác: giữ Space hoặc chuột giữa.",
            ),
        }
        self.tool_buttons: dict[str, IconButton] = {}
        for key, (icon_name, name, shortcut, tip) in self.TOOL_META.items():
            title = f"{name}  ({shortcut})" if shortcut else name
            b = IconButton(icon_name, f"{title}\n{tip}", 17, checkable=True)
            b.setFixedSize(34, 30)
            b.setChecked(key == TOOL_SELECT)
            b.clicked.connect(lambda _c=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            self.tool_buttons[key] = b
            lay.addWidget(b)

        lay.addStretch(1)
        self.merge_btn = IconButton(
            "merge",
            tr("editor.merge_regions", "Gộp vùng  (M)\nGộp các vùng đang chọn thành một"),
            17,
        )
        self.merge_btn.setFixedSize(34, 30)
        self.merge_btn.clicked.connect(lambda: self.canvas.merge_selected())
        lay.addWidget(self.merge_btn)
        self.simplify_btn = IconButton(
            "sparkle", tr("editor.simplify_polygon", "Giản lược\nGiảm số đỉnh của polygon"), 17
        )
        self.simplify_btn.setFixedSize(34, 30)
        self.simplify_btn.clicked.connect(lambda: self.canvas.simplify_selected(1.8))
        lay.addWidget(self.simplify_btn)
        self.delete_btn = IconButton(
            "trash",
            tr("editor.delete_object", "Xoá  (Delete)\nXoá đối tượng đang chọn"),
            17,
            color=COLORS["danger"],
        )
        self.delete_btn.setFixedSize(34, 30)
        self.delete_btn.clicked.connect(lambda: self.canvas.delete_selected())
        lay.addWidget(self.delete_btn)

        lay.addSpacing(4)
        lay.addWidget(vline())
        lay.addSpacing(4)
        self.undo_btn = IconButton("undo", tr("editor.undo", "Hoàn tác  (Ctrl+Z)"))
        self.undo_btn.clicked.connect(lambda: self.canvas.undo())
        self.redo_btn = IconButton("redo", tr("editor.redo", "Làm lại  (Ctrl+Y)"))
        self.redo_btn.clicked.connect(lambda: self.canvas.redo())
        self.zoom_in_btn = IconButton("zoom_in", tr("editor.zoom_in", "Phóng to  (Ctrl++)"))
        self.zoom_in_btn.clicked.connect(lambda: self.canvas.zoom_by(1.2))
        self.zoom_out_btn = IconButton("zoom_out", tr("editor.zoom_out", "Thu nhỏ  (Ctrl+-)"))
        self.zoom_out_btn.clicked.connect(lambda: self.canvas.zoom_by(1 / 1.2))
        self.fit_btn = IconButton("maximize", tr("editor.fit_view", "Vừa khung  (Ctrl+0)"))
        self.fit_btn.clicked.connect(lambda: self.canvas.fit_to_view())
        for b in (self.undo_btn, self.redo_btn, self.zoom_in_btn, self.zoom_out_btn, self.fit_btn):
            lay.addWidget(b)
        return bar

    # ------------------------------------------------------------- ben phai --
    def _build_right(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumWidth(260)
        scroll.setMaximumWidth(650)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(10)

        nav_card = Card(tr("editor.navigator", "Navigator"), "", "grid", margins=(12, 11, 12, 12), spacing=8)
        self.navigator = Navigator()
        self.navigator.setFixedHeight(150)
        self.navigator.navigate.connect(self._navigate_to)
        nav_card.add(self.navigator)
        lay.addWidget(nav_card)

        obj_card = Card(
            tr("editor.objects_on_image", "Đối tượng trên ảnh"),
            "",
            "target",
            margins=(12, 11, 12, 12),
            spacing=8,
        )
        self.object_list = QListWidget()
        self.object_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.object_list.itemSelectionChanged.connect(self._on_object_list_selection)
        self.object_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.object_list.customContextMenuRequested.connect(self._object_menu)
        self.object_list.setMinimumHeight(130)
        obj_card.add(self.object_list, 1)
        lay.addWidget(obj_card)

        info_card = Card(
            tr("editor.properties", "Thuộc tính"),
            "",
            "sliders",
            margins=(12, 11, 12, 12),
            spacing=8,
        )
        self.obj_class_combo = combo([])
        self.obj_class_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: #FFFFFF;"
            f"  color: #0F172A;"
            f"  border: 1.5px solid #CBD5E1;"
            f"  border-radius: 8px;"
            f"  padding: 5px 10px;"
            f"  font-weight: 600;"
            f"}}"
            f"QComboBox:hover {{"
            f"  border-color: {COLORS['accent']};"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background: #FFFFFF;"
            f"  color: #0F172A;"
            f"  border: 1px solid #CBD5E1;"
            f"  border-radius: 8px;"
            f"  padding: 4px;"
            f"  selection-background-color: #EEF2FF;"
            f"  selection-color: {COLORS['accent']};"
            f"}}"
        )
        self.obj_class_combo.currentIndexChanged.connect(self._apply_class_combo)
        info_card.add(Field(tr("editor.class", "Lớp"), self.obj_class_combo, label_width=75))
        self.obj_conf = dspin(1.0, 0.0, 1.0, 0.01, 3, width=90)
        self.obj_conf.valueChanged.connect(self._apply_confidence)
        info_card.add(Field(tr("editor.confidence", "Độ tin cậy"), self.obj_conf, label_width=75))
        self.obj_info = label(
            tr("editor.no_object_selected", "Chưa chọn đối tượng nào"),
            size=11.5,
            color=COLORS["text_mute"],
            wrap=True,
        )
        self.obj_info.setWordWrap(True)
        info_card.add(self.obj_info)
        self.apply_track_btn = ghost_button(
            tr("editor.apply_track", "Áp dụng sửa đổi cho track"), "layers"
        )
        self.apply_track_btn.setToolTip(
            tr(
                "editor.apply_track_tip",
                "Đổi lớp của tất cả các đối tượng thuộc cùng track trong dự án",
            )
        )
        self.apply_track_btn.clicked.connect(self._apply_class_to_track)
        self.apply_track_btn.setVisible(False)
        info_card.add(self.apply_track_btn)
        info_card.add(hline())

        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(7)
        self.mark_review_btn = ghost_button(tr("editor.mark_review", "Cần xem lại"), "alert")
        self.mark_review_btn.setToolTip(
            tr("editor.mark_review_tip", "Đánh dấu đối tượng đang chọn là cần xem lại")
        )
        self.mark_review_btn.clicked.connect(lambda: self._set_ann_status(ANN_REVIEW))
        self.mark_ok_btn = ghost_button(tr("editor.mark_ok", "Đã duyệt"), "check")
        self.mark_ok_btn.setToolTip(
            tr("editor.mark_ok_tip", "Đánh dấu đối tượng đang chọn là đã duyệt")
        )
        self.mark_ok_btn.clicked.connect(lambda: self._set_ann_status(ANN_APPROVED))
        self.status_row.addWidget(self.mark_review_btn)
        self.status_row.addWidget(self.mark_ok_btn)
        info_card.add(self.status_row)
        lay.addWidget(info_card)

        view_card = Card(
            tr("editor.display_card", "Hiển thị"), "", "eye", margins=(12, 11, 12, 12), spacing=8
        )
        from app.views.widgets.common import ToggleSwitch

        self.show_conf_toggle = ToggleSwitch(cfg.get("annotation.show_confidence", True))
        self.show_label_toggle = ToggleSwitch(cfg.get("annotation.show_labels", True))
        for text, toggle in (
            (tr("editor.show_confidence", "Hiện độ tin cậy"), self.show_conf_toggle),
            (tr("editor.show_class_name", "Hiện tên lớp"), self.show_label_toggle),
        ):
            r = QHBoxLayout()
            r.addWidget(label(text, size=12, color=COLORS["text_dim"]))
            r.addStretch(1)
            r.addWidget(toggle)
            view_card.add(r)
            toggle.toggled.connect(self._apply_view_settings)
        self.opacity_slider = SliderField(cfg.get("annotation.fill_opacity", 0.35), 0.0, 0.9, 2)
        self.opacity_slider.valueChanged.connect(self._apply_view_settings)
        view_card.add(
            Field(tr("editor.fill_opacity", "Độ đậm"), self.opacity_slider, label_width=75)
        )
        lay.addWidget(view_card)

        lay.addStretch(1)
        scroll.setWidget(wrap)
        return scroll

    # ============================================================ SHORTCUTS ==
    def _install_shortcuts(self) -> None:
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.WidgetWithChildrenShortcut)
            s.activated.connect(fn)
            return s

        sc("A", lambda: self.step_image(-1))
        sc("D", lambda: self.step_image(1))
        sc("V", lambda: self.set_tool(TOOL_SELECT))
        sc("Q", lambda: self.set_tool(TOOL_SMART_SELECT))
        sc("W", lambda: self.set_tool(TOOL_POLYGON))
        sc("B", lambda: self.set_tool(TOOL_BRUSH))
        sc("E", lambda: self.set_tool(TOOL_ERASER))
        sc("S", lambda: self.set_tool(TOOL_SPLIT))
        sc("M", lambda: self.canvas.merge_selected())
        sc("Del", lambda: self.canvas.delete_selected())
        sc("Ctrl+Z", lambda: self.canvas.undo())
        sc("Ctrl+Y", lambda: self.canvas.redo())
        sc("Ctrl+Shift+Z", lambda: self.canvas.redo())
        sc("Ctrl+A", lambda: self.canvas.select_all())
        sc("Ctrl++", lambda: self.canvas.zoom_by(1.2))
        sc("Ctrl+=", lambda: self.canvas.zoom_by(1.2))
        sc("Ctrl+-", lambda: self.canvas.zoom_by(1 / 1.2))
        sc("Ctrl+0", lambda: self.canvas.fit_to_view())
        sc("Return", self.approve_and_next)
        sc("Enter", self.approve_and_next)
        for i in range(1, 10):
            sc(str(i), lambda k=i: self._assign_class_index(k - 1))
        sc("Shift+Del", self._delete_current_image)

    # ========================================================== IMAGE ACTION ==
    def _image_menu(self, pos) -> None:
        item = self.image_list.itemAt(pos)
        if not item:
            return
        image_id = int(item.data(ROLE_ID))
        rec = self.repo.image(image_id) if self.repo else None
        if not rec:
            return

        menu = QMenu(self)
        a_del = menu.addAction(
            icons.icon("trash", COLORS["danger"], 16),
            tr("editor.delete_image_action", "Xoá ảnh này khỏi project"),
        )
        menu.addSeparator()
        a_review = menu.addAction(
            icons.icon("alert", COLORS["warning"], 16),
            tr("editor.mark_image_review", "Đánh dấu ảnh cần xem lại"),
        )
        a_ok = menu.addAction(
            icons.icon("check", COLORS["success"], 16),
            tr("editor.mark_image_approved", "Đánh dấu ảnh đã duyệt"),
        )

        chosen = menu.exec(self.image_list.mapToGlobal(pos))
        if chosen == a_del:
            self._confirm_delete_image(image_id, rec.filename)
        elif chosen == a_review:
            if self.repo:
                self.repo.set_image_status(image_id, IMG_REVIEW)
                self.refresh()
        elif chosen == a_ok:
            if self.repo:
                self.repo.set_image_status(image_id, IMG_APPROVED)
                self.refresh()

    def _delete_current_image(self) -> None:
        if not self._image_id or not self.repo:
            return
        rec = self.repo.image(self._image_id)
        if not rec:
            return
        self._confirm_delete_image(self._image_id, rec.filename)

    def _confirm_delete_image(self, image_id: int, filename: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(tr("editor.delete_image_title", "Xoá ảnh"))
        box.setText(f"Xoá ảnh '{filename}' khỏi project?")
        box.setInformativeText("Bạn có thể chọn chỉ gỡ khỏi project hoặc xoá luôn file gốc trên đĩa.")
        btn_del_db = box.addButton("Chỉ gỡ khỏi project", QMessageBox.AcceptRole)
        btn_del_file = box.addButton("Xoá luôn file trên đĩa", QMessageBox.DestructiveRole)
        btn_cancel = box.addButton("Huỷ", QMessageBox.RejectRole)
        box.setDefaultButton(btn_cancel)

        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_cancel or clicked is None:
            return

        remove_file = (clicked == btn_del_file)
        cur_idx = next((i for i, r in enumerate(self._images) if r.id == image_id), -1)

        self.repo.delete_images([image_id], remove_files=remove_file)
        self.toast(f"Đã xoá ảnh '{filename}'.", "success")

        self._images = [r for r in self._images if r.id != image_id]
        if self._image_id == image_id:
            self._dirty = False
            if self._images:
                next_idx = min(cur_idx, len(self._images) - 1) if cur_idx >= 0 else 0
                next_id = self._images[next_idx].id
                self.refresh()
                self.load_image(next_id)
            else:
                self._image_id = 0
                self.canvas.load_image("")
                self.refresh()
        else:
            self.refresh()

        self.ctrl.notify_images_changed()

    # ================================================================= DATA ==
    def refresh(self) -> None:
        if not self.repo:
            return
        key = self.filter_combo.currentData() if hasattr(self, "filter_combo") else "all"
        kwargs = {}
        if key in ("review", "unlabeled", "approved"):
            kwargs["status"] = key
        self._images = self.repo.images(**kwargs)

        img_colors = {}
        if self._images:
            c_map = {c.id: c.color for c in self.repo.classes()}
            rows = self.repo.db.query("SELECT image_id, class_id FROM annotation GROUP BY image_id")
            for r in rows:
                if r["class_id"] in c_map:
                    img_colors[r["image_id"]] = c_map[r["class_id"]]

        self.image_list.set_images(self._images, img_colors)
        self._reload_classes()
        if self._images:
            target = (
                self._image_id
                if any(i.id == self._image_id for i in self._images)
                else self._images[0].id
            )
            self.image_list.select_id(target)
            if target != self._image_id:
                self.load_image(target)
        else:
            self._image_id = 0
            self.canvas.load_image("")
            self.pos_label.setText("0 / 0")

    def _reload_classes(self) -> None:
        if not self.repo:
            return
        classes = self.repo.classes(refresh=True)
        self.canvas.set_classes(classes)

        self.class_list.blockSignals(True)
        current = self.canvas.active_class_id
        self.class_list.clear()
        for i, c in enumerate(classes):
            item = QListWidgetItem(f"  {c.name}")
            item.setIcon(_color_icon(c.color))
            item.setData(CLASS_ROLE, c.id)
            item.setSizeHint(QSize(0, 30))
            item.setToolTip(f"Phim tat: {i + 1}" if i < 9 else "")
            self.class_list.addItem(item)
            if c.id == current:
                self.class_list.setCurrentItem(item)
        self.class_list.blockSignals(False)
        if classes and not any(c.id == self.canvas.active_class_id for c in classes):
            self.canvas.active_class_id = classes[0].id
            self.class_list.setCurrentRow(0)

        self.obj_class_combo.blockSignals(True)
        self.obj_class_combo.clear()
        for c in classes:
            self.obj_class_combo.addItem(_color_icon(c.color), f" {c.name}", c.id)
        self.obj_class_combo.blockSignals(False)

    def load_image(self, image_id: int) -> None:
        if image_id == self._image_id and self.canvas.pixmap is not None:
            return
        if self._dirty:
            self.save_current()
        rec = self.repo.image(image_id) if self.repo else None
        if rec is None:
            return
        self._loading = True
        self._image_id = image_id
        self.ctrl.set_current_image(image_id)
        anns = self.repo.annotations(image_id)
        ok = self.canvas.load_image(rec.path, anns)
        self._loading = False
        self._dirty = False
        if not ok:
            self._set_status(f"Không đọc được ảnh {rec.filename}")
        self.navigator.set_image(self.canvas.pixmap)
        self._sync_navigator()
        self._refresh_object_list()
        self._apply_view_settings()

        # Duy trì trạng thái đang phân tích hoặc tải mô hình trên banner nếu tiến trình đang chạy
        if self._sam_running and hasattr(self, "notif_banner"):
            self.notif_banner.setVisible(True)
            self.notif_progress.setValue(self._sam_last_prog)
            self.notif_label.setText(self._sam_last_msg or "Ảnh đang được xử lý, vui lòng thử lại sau.")
            self.canvas.set_processing(True, self._sam_last_msg or "Ảnh đang được xử lý, vui lòng thử lại sau.")

        idx = next((i for i, r in enumerate(self._images) if r.id == image_id), -1)
        self.pos_label.setText(f"{idx + 1} / {len(self._images)}")
        status_text, color = get_image_status_label().get(rec.status, ("", COLORS["text_mute"]))
        self.header.set_subtitle(
            f"{rec.filename}   •   {rec.width}x{rec.height}   •   {status_text}"
        )

    def _external_image_change(self, image_id: int) -> None:
        if image_id and image_id != self._image_id and self.isVisible():
            self.image_list.select_id(image_id)

    def step_image(self, delta: int) -> None:
        if not self._images:
            return
        idx = next((i for i, r in enumerate(self._images) if r.id == self._image_id), 0)
        new = max(0, min(len(self._images) - 1, idx + delta))
        if new != idx:
            self.image_list.select_id(self._images[new].id)

    # ================================================================= SAVE ==
    def save_current(self, toast: bool = False) -> None:
        if not self.repo or not self._image_id:
            return
        anns = self.canvas.get_annotations()
        for a in anns:
            a.image_id = self._image_id
            a.recompute()
        self.repo.replace_annotations(self._image_id, anns)
        self._dirty = False
        class_color = ""
        if anns:
            class_color = self.canvas.class_colors.get(anns[0].class_id, "")
        self.image_list.update_item(
            self._image_id,
            n_objects=len(anns),
            status=self.repo.image(self._image_id).status,
            class_color=class_color,
        )
        self.ctrl.notify_annotations_changed(self._image_id)
        if toast:
            self.toast(f"Đã lưu {len(anns)} đối tượng.", "success")

    def approve_and_next(self) -> None:
        if not self.repo or not self._image_id:
            return
        self.save_current()
        self.repo.approve_image(self._image_id)
        self.image_list.update_item(self._image_id, status=IMG_APPROVED)
        self._set_status("Đã duyệt ảnh này")
        self.ctrl.notify_images_changed()
        self.step_image(1)

    # ============================================================== CANVAS ===
    def _build_tool_options_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ToolOptionsBar")
        bar.setStyleSheet(
            f"#ToolOptionsBar {{"
            f"  background: {COLORS['surface']};"
            f"  border: 1px solid {COLORS['border']};"
            f"  border-radius: 9px;"
            f"}}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 5, 12, 5)
        lay.setSpacing(16)

        # Tuy chon cho Co ve / Tay
        self.brush_setting_widget = QWidget()
        bsl = QHBoxLayout(self.brush_setting_widget)
        bsl.setContentsMargins(0, 0, 0, 0)
        bsl.setSpacing(10)
        bsl.addWidget(label(tr("editor.brush_size", "Cỡ cọ / tẩy:"), bold=True, size=11.5, color=COLORS["text"]))
        self.brush_slider = SliderField(cfg.get("annotation.brush_size", 20), 2, 200, 0, 1)
        self.brush_slider.setFixedWidth(220)
        self.brush_slider.valueChanged.connect(self.canvas_brush_changed)
        bsl.addWidget(self.brush_slider)
        lay.addWidget(self.brush_setting_widget)

        # Tuy chon cho SAM / Smart Select
        self.sam_setting_widget = QWidget()
        ssl = QHBoxLayout(self.sam_setting_widget)
        ssl.setContentsMargins(0, 0, 0, 0)
        ssl.setSpacing(10)
        ssl.addWidget(label("Mô hình SAM:", bold=True, size=11.5, color=COLORS["text"]))
        sam_presets = [
            ("sam2_l.pt", "SAM 2 Large — Mạnh mẽ nhất (300 MB)"),
            ("sam2_b.pt", "SAM 2 Base — Nhanh & Chính xác (148 MB)"),
            ("sam_b.pt", "SAM 1 Base — Chuẩn (366 MB)"),
            ("sam_l.pt", "SAM 1 Large — Độ phân giải cao (1.2 GB)"),
            ("FastSAM-s.pt", "FastSAM Small — Siêu tốc (25 MB)"),
            ("FastSAM-x.pt", "FastSAM Extra Large (140 MB)"),
        ]
        cur_sam = cfg.get("sam.weights", "sam2_l.pt")
        self.editor_sam_combo = combo(
            sam_presets,
            current=cur_sam if any(w == cur_sam for w, _ in sam_presets) else "sam2_l.pt",
        )
        self.editor_sam_combo.setFixedWidth(270)
        self.editor_sam_combo.currentIndexChanged.connect(self._on_editor_sam_changed)
        ssl.addWidget(self.editor_sam_combo)
        ssl.addWidget(label("Khoanh khung/nhấp điểm để tạo polygon", size=11.5, color=COLORS["text_dim"]))
        lay.addWidget(self.sam_setting_widget)

        lay.addStretch(1)
        bar.setVisible(False)
        return bar

    def _on_editor_sam_changed(self, idx: int) -> None:
        val = self.editor_sam_combo.currentData()
        if val:
            cfg.set("sam.weights", val)
            cfg.save()

    def set_tool(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        if self._sam_running and hasattr(self, "notif_banner"):
            self.notif_banner.setVisible(True)
            self.canvas.set_processing(True, self._sam_last_msg or "Ảnh đang được xử lý, vui lòng thử lại sau.")
        for key, btn in self.tool_buttons.items():
            btn.setChecked(key == tool)
        meta = self.TOOL_META.get(tool)
        if meta:
            if hasattr(self, "tool_name_label"):
                self.tool_name_label.setText(meta[1])
            self._set_status(meta[3].replace("\n", " "))

        show_brush = tool in (TOOL_BRUSH, TOOL_ERASER)
        show_sam = tool == TOOL_SMART_SELECT
        self.brush_setting_widget.setVisible(show_brush)
        self.sam_setting_widget.setVisible(show_sam)
        self.tool_options_bar.setVisible(show_brush or show_sam)

        self.canvas.setFocus()

    def canvas_brush_changed(self, value: float) -> None:
        self.canvas.set_brush_size(value)
        cfg.set("annotation.brush_size", int(value))

    def _on_canvas_changed(self) -> None:
        self._dirty = True
        self._refresh_object_list()
        self._sync_navigator()
        self.undo_btn.setEnabled(self.canvas.can_undo)
        self.redo_btn.setEnabled(self.canvas.can_redo)
        anns = self.canvas.get_annotations()
        class_color = ""
        if anns:
            class_color = self.canvas.class_colors.get(anns[0].class_id, "")
        if self._image_id:
            self.image_list.update_item(
                self._image_id,
                n_objects=len(anns),
                class_color=class_color,
            )

    def _on_canvas_selection(self, indices) -> None:
        self.object_list.blockSignals(True)
        for i in range(self.object_list.count()):
            self.object_list.item(i).setSelected(i in indices)
        self.object_list.blockSignals(False)
        self._update_object_info(indices)

    def _on_zoom(self, scale: float) -> None:
        self.zoom_label.setText(f"{scale * 100:.0f}%")

    def _sync_navigator(self) -> None:
        self.navigator.set_view_rect(self.canvas.viewport_image_rect())
        self.navigator.set_annotations(self.canvas.annotations, self.canvas.class_colors)

    def _navigate_to(self, image_point: QPointF) -> None:
        c = self.canvas
        c._offset = QPointF(
            c.width() / 2 - image_point.x() * c.scale, c.height() / 2 - image_point.y() * c.scale
        )
        c.update()
        self._sync_navigator()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _apply_view_settings(self, *_a) -> None:
        self.canvas.set_style(
            show_confidence=self.show_conf_toggle.isChecked(),
            show_labels=self.show_label_toggle.isChecked(),
            fill_opacity=self.opacity_slider.value(),
        )
        cfg.update_section(
            "annotation",
            {
                "show_confidence": self.show_conf_toggle.isChecked(),
                "show_labels": self.show_label_toggle.isChecked(),
                "fill_opacity": self.opacity_slider.value(),
            },
        )

    # ======================================================== DANH SACH OBJ ==
    def _refresh_object_list(self) -> None:
        self.object_list.blockSignals(True)
        self.object_list.clear()
        for i, a in enumerate(self.canvas.annotations):
            name = a.class_name or self.canvas.class_names.get(a.class_id, "?")
            conf = f"{a.confidence:.2f}" if a.confidence < 1.0 else "manual"
            track_str = f" [T#{a.track_id}]" if a.track_id is not None else ""
            item = QListWidgetItem(f"  #{i + 1}  {name}{track_str}   ·   {conf}")
            item.setIcon(_color_icon(self.canvas.class_colors.get(a.class_id, COLORS["accent"])))
            item.setData(OBJ_ROLE, i)
            item.setSizeHint(QSize(0, 27))
            if a.status == ANN_REVIEW:
                item.setForeground(QColor(COLORS["warning"]))
            self.object_list.addItem(item)
            item.setSelected(i in self.canvas.selected)
        self.object_list.blockSignals(False)

    def _on_object_list_selection(self) -> None:
        indices = {i.data(OBJ_ROLE) for i in self.object_list.selectedItems()}
        self.canvas.selected = set(indices)
        self.canvas.update()
        self._update_object_info(sorted(indices))

    def _update_object_info(self, indices) -> None:
        anns = [
            self.canvas.annotations[i] for i in indices if 0 <= i < len(self.canvas.annotations)
        ]
        if not anns:
            self.obj_info.setText(tr("editor.no_object_selected", "Chưa chọn đối tượng nào"))
            self.obj_class_combo.setEnabled(True)
            self.obj_class_combo.blockSignals(True)
            idx = self.obj_class_combo.findData(self.canvas.active_class_id)
            if idx >= 0:
                self.obj_class_combo.setCurrentIndex(idx)
            self.obj_class_combo.blockSignals(False)
            self.obj_conf.setEnabled(False)
            self.apply_track_btn.setVisible(False)
            return
        self.obj_class_combo.setEnabled(True)
        self.obj_conf.setEnabled(True)
        a = anns[0]
        self.obj_class_combo.blockSignals(True)
        idx = self.obj_class_combo.findData(a.class_id)
        if idx >= 0:
            self.obj_class_combo.setCurrentIndex(idx)
        self.obj_class_combo.blockSignals(False)
        self.obj_conf.blockSignals(True)
        self.obj_conf.setValue(a.confidence)
        self.obj_conf.blockSignals(False)

        if len(anns) == 1:
            track_text = f"   ·   Track: #{a.track_id}" if a.track_id is not None else ""
            new_text = tr("common.new", "mới")
            self.obj_info.setText(
                tr(
                    "editor.single_obj_info",
                    "Mã: {id}{track}   ·   {vertices} đỉnh\nKích thước: {width:.0f} × {height:.0f} px\nDiện tích: {area:,.0f} px²",
                    id=a.id or new_text,
                    track=track_text,
                    vertices=len(a.points()) or 4,
                    width=a.width,
                    height=a.height,
                    area=a.area,
                )
            )
            self.apply_track_btn.setVisible(a.track_id is not None)
        else:
            total = sum(x.area for x in anns)
            self.obj_info.setText(
                tr(
                    "editor.multi_obj_info",
                    "Đang chọn {count} đối tượng\nTổng diện tích: {total:,.0f} px²",
                    count=len(anns),
                    total=total,
                )
            )
            self.apply_track_btn.setVisible(False)

    def _object_menu(self, pos) -> None:
        if not self.object_list.selectedItems():
            return

        dlg = DraggableObjectMenuDialog(self)
        dlg.add_menu_action(
            tr("common.delete", "Xoá"),
            "trash",
            COLORS["danger"],
            lambda: self.canvas.delete_selected(),
        )
        dlg.add_menu_action(
            tr("editor.merge_regions_short", "Gộp vùng"),
            "merge",
            "",
            lambda: self.canvas.merge_selected(),
        )
        dlg.add_menu_action(
            tr("editor.simplify_short", "Giản lược"),
            "sparkle",
            "",
            lambda: self.canvas.simplify_selected(1.8),
        )
        dlg.add_menu_action(
            tr("editor.convert_to_polygon", "Chuyển thành polygon"),
            "polygon",
            "",
            lambda: self.canvas.convert_selected_to_polygon(),
        )

        selected_anns = self.canvas.selected_annotations()
        if selected_anns and selected_anns[0].track_id is not None:
            dlg.buttons_lay.addWidget(hline())
            dlg.add_menu_action(
                tr("editor.apply_track", "Áp dụng sửa đổi cho track"),
                "layers",
                COLORS["accent"],
                lambda: self._apply_class_to_track(),
            )

        dlg.adjustSize()
        screen_geo = self.screen().availableGeometry() if self.screen() else self.geometry()
        global_pos = self.object_list.mapToGlobal(pos)
        x = min(global_pos.x(), screen_geo.right() - dlg.width() - 10)
        y = min(global_pos.y(), screen_geo.bottom() - dlg.height() - 10)
        x = max(screen_geo.left() + 10, x)
        y = max(screen_geo.top() + 10, y)
        dlg.move(QPoint(x, y))

        dlg.exec()

    def _apply_class_to_track(self) -> None:
        if not self.canvas.selected or not self.repo:
            return
        selected_anns = self.canvas.selected_annotations()
        if not selected_anns:
            return
        target_ann = selected_anns[0]
        track_id = target_ann.track_id
        if track_id is None:
            self.toast("Đối tượng được chọn không thuộc chuỗi theo dõi nào.", "warning")
            return

        cid = self.obj_class_combo.currentData()
        if cid is None:
            return
        class_def = self.repo.class_by_id(int(cid))
        class_name = class_def.name if class_def else f"ID {cid}"

        reply = QMessageBox.question(
            self,
            "Xác nhận áp dụng sửa đổi cho track",
            f"Bạn có chắc chắn muốn đổi lớp đối tượng của tất cả nhãn thuộc Track #{track_id} thành '{class_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        updated_count = self.repo.update_track_class(track_id, int(cid))

        for a in self.canvas.annotations:
            if a.track_id == track_id:
                a.class_id = int(cid)
                a.class_name = class_name
                a.status = ANN_MANUAL

        self.save_current()
        self.canvas.update()
        self._refresh_object_list()
        self.toast(
            f"Đã cập nhật {updated_count} nhãn thuộc Track #{track_id} thành lớp '{class_name}'.",
            "success",
        )

    def _apply_class_combo(self) -> None:
        cid = self.obj_class_combo.currentData()
        if cid is None:
            return
        cid = int(cid)
        if self.canvas.selected:
            self.canvas.set_class_for_selected(cid)
        else:
            self.canvas.active_class_id = cid
            for r in range(self.class_list.count()):
                it = self.class_list.item(r)
                if it and it.data(CLASS_ROLE) == cid:
                    self.class_list.blockSignals(True)
                    self.class_list.setCurrentRow(r)
                    self.class_list.blockSignals(False)
                    break

    def _apply_confidence(self, value: float) -> None:
        if self.canvas.selected:
            self.canvas.set_confidence_for_selected(value)

    def _set_ann_status(self, status: str) -> None:
        if not self.canvas.selected:
            return
        for i in self.canvas.selected:
            self.canvas.annotations[i].status = status
        self._dirty = True
        self._refresh_object_list()
        self._set_status("Đã đổi trạng thái đối tượng đang chọn")

    # =============================================================== CLASSES ==
    def _on_class_selected(self, cur, _prev) -> None:
        if cur is None:
            return
        cid = cur.data(CLASS_ROLE)
        if cid is not None:
            self.canvas.active_class_id = int(cid)

    def _assign_class_to_selection(self, item) -> None:
        cid = item.data(CLASS_ROLE)
        if cid is not None:
            self.canvas.set_class_for_selected(int(cid))

    def _assign_class_index(self, index: int) -> None:
        if index < self.class_list.count():
            item = self.class_list.item(index)
            self.class_list.setCurrentItem(item)
            self._assign_class_to_selection(item)

    def _add_class(self) -> None:
        name, ok = QInputDialog.getText(self, tr("editor.add_class_title", "Thêm lớp"), tr("editor.class_name_label", "Tên lớp:"))
        if not ok or not name.strip():
            return
        self.repo.add_class(name.strip())
        self.ctrl.notify_classes_changed()

    def _class_menu(self, pos) -> None:
        item = self.class_list.itemAt(pos)
        if item is None:
            return
        cid = int(item.data(CLASS_ROLE))
        menu = QMenu(self)
        act_rename = menu.addAction(icons.icon("pen", COLORS["text_dim"], 16), tr("common.rename", "Đổi tên"))
        act_color = menu.addAction(icons.icon("sparkle", COLORS["text_dim"], 16), tr("common.change_color", "Đổi màu"))
        act_hide = menu.addAction(icons.icon("eye_off", COLORS["text_dim"], 16), tr("common.hide_show", "Ẩn / hiện"))
        menu.addSeparator()
        act_del = menu.addAction(icons.icon("trash", COLORS["danger"], 16), tr("common.delete_class", "Xoá lớp"))
        chosen = menu.exec(self.class_list.mapToGlobal(pos))

        if chosen == act_rename:
            name, ok = QInputDialog.getText(
                self, tr("editor.rename_class_title", "Đổi tên lớp"), tr("editor.new_name_label", "Tên mới:"), text=item.text().strip()
            )
            if ok and name.strip():
                self.repo.update_class(cid, name=name.strip())
                self.ctrl.notify_classes_changed()
        elif chosen == act_color:
            cd = self.repo.class_by_id(cid)
            color = QColorDialog.getColor(
                QColor(cd.color if cd else "#7C5CFF"), self, tr("editor.choose_class_color", "Chọn màu cho lớp")
            )
            if color.isValid():
                self.repo.update_class(cid, color=color.name())
                self.ctrl.notify_classes_changed()
        elif chosen == act_hide:
            cd = self.repo.class_by_id(cid)
            if cd:
                self.repo.update_class(cid, visible=not cd.visible)
                self.ctrl.notify_classes_changed()
        elif chosen == act_del:
            from PySide6.QtWidgets import QMessageBox

            if (
                QMessageBox.question(self, tr("editor.delete_class_title", "Xoá lớp"), tr("editor.delete_class_confirm", "Xoá lớp này và toàn bộ nhãn thuộc nó?"))
                == QMessageBox.Yes
            ):
                self.repo.delete_class(cid)
                self.ctrl.notify_classes_changed()
                self.ctrl.notify_images_changed()

    # =========================================================== AUTO LABEL ==
    def auto_label_current(self) -> None:
        if not self._image_id or not self.repo:
            return
        if not self.ctrl.engine.loaded:
            self.toast(tr("editor.load_model_first", "Hãy nạp model ở trang Auto Label trước."), "warning")
            return
        rec = self.repo.image(self._image_id)
        if rec is None:
            return
        w_name = cfg.get("model.custom_weights") or cfg.get("model.weights", "yolo11m-seg.pt")
        task = cfg.get("model.task", "segment")
        dev = cfg.get("model.device", "auto")

        try:
            self.ctrl.engine.load(w_name, task=task, device=dev)
        except Exception as exc:
            self.toast(f"Không nạp được mô hình '{w_name}': {exc}", "danger")
            return

        icfg = InferenceConfig(
            confidence=cfg.get("inference.confidence", 0.45),
            iou=cfg.get("inference.iou", 0.5),
            imgsz=cfg.get("model.imgsz", 640),
            polygon_simplify=cfg.get("inference.polygon_simplify", 0.0025),
            min_area_px=cfg.get("inference.min_area_px", 24),
        )
        self.autolabel_btn.setEnabled(False)
        self._set_status(tr("editor.inferring", "Đang suy luận …"))
        worker = SingleImageInferWorker(self.ctrl.engine, rec.path, icfg)
        self.ctrl.run_worker(
            "infer_one",
            worker,
            on_done=self._on_single_infer,
            on_fail=lambda _m: self.autolabel_btn.setEnabled(True),
        )

    def _on_single_infer(self, detections) -> None:
        self.autolabel_btn.setEnabled(True)
        if not detections:
            self._set_status(tr("editor.no_objects_found", "Không tìm thấy đối tượng nào"))
            return
        self.canvas.push_undo()
        classes = {c.name: c for c in self.repo.classes(refresh=True)}
        new_anns = list(self.canvas.annotations)
        for d in detections:
            cd = classes.get(d.class_name) or self.repo.add_class(d.class_name or "object")
            classes[cd.name] = cd
            a = Annotation(
                image_id=self._image_id,
                class_id=cd.id,
                class_name=cd.name,
                shape=d.shape,
                bbox=list(d.bbox),
                polygon=list(d.polygon),
                confidence=d.confidence,
                status="auto",
                source="yolo",
            )
            a.recompute()
            new_anns.append(a)
        self.canvas.annotations = new_anns
        self.canvas.update()
        self._dirty = True
        self._reload_classes()
        self._refresh_object_list()
        self._set_status(tr("editor.added_objects_count", "Đã thêm {count} đối tượng từ model", count=len(detections)))

    # ========================================================== SMART SELECT ==
    def _build_notification_banner(self) -> QWidget:
        banner = QFrame()
        banner.setObjectName("NotificationBanner")
        banner.setStyleSheet(
            f"#NotificationBanner {{"
            f"  background: {COLORS['surface_alt']};"
            f"  border: 1px solid {COLORS['accent']};"
            f"  border-radius: 9px;"
            f"  padding: 4px 10px;"
            f"}}"
        )
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        self.notif_icon = IconButton("wand", "", 16)
        self.notif_label = label("Đang tải mô hình ...", bold=True, size=11.5, color=COLORS["text"])
        self.notif_progress = QProgressBar()
        self.notif_progress.setRange(0, 100)
        self.notif_progress.setValue(0)
        self.notif_progress.setFixedHeight(10)
        self.notif_progress.setTextVisible(False)
        self.notif_progress.setStyleSheet(
            f"QProgressBar {{ background: {COLORS['bg']}; border-radius: 5px; border: none; }}"
            f"QProgressBar::chunk {{ background: {COLORS['accent']}; border-radius: 5px; }}"
        )

        lay.addWidget(self.notif_icon)
        lay.addWidget(self.notif_label)
        lay.addWidget(self.notif_progress, 1)

        banner.setVisible(False)
        return banner

    def _cancel_sam_worker(self) -> None:
        if hasattr(self, "_sam_worker") and self._sam_worker is not None:
            worker = self._sam_worker
            self._sam_worker = None
            self._sam_running = False
            try:
                worker.finished_ok.disconnect()
            except Exception:
                pass
            try:
                worker.failed.disconnect()
            except Exception:
                pass
            try:
                worker.progress.disconnect()
            except Exception:
                pass
            worker.cancel()

        if hasattr(self, "canvas"):
            self.canvas.set_processing(False)
        if hasattr(self, "notif_banner"):
            self.notif_banner.setVisible(False)

    def _on_smart_select(self, payload: dict) -> None:
        point = payload.get("point")
        bbox = payload.get("bbox")
        target_refine_idx = payload.get("target_idx")

        if not self._image_id or self.canvas.pixmap is None:
            return
        rec = self.repo.image(self._image_id) if self.repo else None
        if not rec or not rec.path:
            return

        target_image_id = self._image_id
        target_class_id = self.canvas.active_class_id
        target_class_name = self.canvas.class_names.get(target_class_id, "")

        self._sam_target_image_id = target_image_id
        self._sam_running = True
        self._sam_last_prog = 0
        self._sam_last_msg = "Ảnh đang được xử lý, vui lòng thử lại sau."

        msg = "Ảnh đang được xử lý, vui lòng thử lại sau."
        self._set_status(msg)
        self.canvas.set_processing(True, msg)
        self.notif_banner.setVisible(True)
        self.notif_progress.setValue(0)
        self.notif_label.setText(self._sam_last_msg)

        sam_w = cfg.get("sam.weights", "sam2_l.pt")
        sam_dev = cfg.get("model.device", "auto")

        worker = SmartSelectWorker(
            source=rec.path,
            point=point,
            bbox=bbox,
            weights=sam_w,
            device=sam_dev,
            parent=self,
        )
        self._sam_worker = worker
        _ACTIVE_SAM_WORKERS.add(worker)

        def _on_prog(cur: int, total: int, pmsg: str) -> None:
            self._sam_last_prog = int(cur)
            if pmsg:
                self._sam_last_msg = pmsg
            self.notif_banner.setVisible(True)
            self.notif_progress.setValue(int(cur))
            if pmsg:
                self.notif_label.setText(pmsg)
                self._set_status(pmsg)
                if self._image_id == target_image_id:
                    self.canvas.set_processing(True, pmsg)

        def _on_success(polygon_pts: list[tuple[float, float]]) -> None:
            self._sam_running = False
            self.notif_banner.setVisible(False)
            if self._image_id == target_image_id:
                self.canvas.set_processing(False)

            if not polygon_pts or len(polygon_pts) < 3:
                self._set_status("Không tìm thấy đối tượng hợp lệ tại vị trí này.")
                self.toast("Không nhận diện được đối tượng trong vùng chọn. Hãy thử khoanh rộng hơn.", "warning")
                return

            if self._image_id == target_image_id:
                # Đang đứng tại đúng ảnh đã chọn
                self.canvas.push_undo()
                if target_refine_idx is not None and 0 <= target_refine_idx < len(self.canvas.annotations):
                    a = self.canvas.annotations[target_refine_idx]
                    a.shape = SHAPE_POLYGON
                    a.status = ANN_MANUAL
                    a.set_points(polygon_pts)
                    self.canvas.selected = {target_refine_idx}
                    self._set_status(f"Đã tinh chỉnh viền đối tượng #{a.id or (target_refine_idx + 1)}")
                else:
                    a = Annotation()
                    a.image_id = target_image_id
                    a.class_id = target_class_id
                    a.class_name = target_class_name
                    a.shape = SHAPE_POLYGON
                    a.status = ANN_MANUAL
                    a.source = "sam_smart_select"
                    a.set_points(polygon_pts)
                    self.canvas.annotations.append(a)
                    self.canvas.selected = {len(self.canvas.annotations) - 1}
                    self._set_status("Đã tự động khoanh vùng đối tượng.")

                self.canvas.update()
                self._dirty = True
                self.canvas.annotationsChanged.emit()
                self.canvas.selectionChanged.emit(sorted(self.canvas.selected))
                self._refresh_object_list()
            else:
                # Đang xem ảnh khác trong lúc máy đang phân tích -> lưu thẳng vào kho dữ liệu của ảnh đích
                a = Annotation()
                a.image_id = target_image_id
                a.class_id = target_class_id
                a.class_name = target_class_name
                a.shape = SHAPE_POLYGON
                a.status = ANN_MANUAL
                a.source = "sam_smart_select"
                a.set_points(polygon_pts)
                if self.repo:
                    self.repo.add_annotation(a)
                    rec_t = self.repo.image(target_image_id)
                    fn = rec_t.filename if rec_t else f"#{target_image_id}"
                    self.toast(f"Đã khoanh vùng đối tượng thành công cho {fn}.", "success")

        def _on_fail(err: str) -> None:
            self._sam_running = False
            self.notif_banner.setVisible(False)
            self.canvas.set_processing(False)
            self._set_status(f"Lỗi Smart Select: {err}")
            self.toast(f"Không nạp được mô hình: {err}", "danger")

        def _cleanup():
            _ACTIVE_SAM_WORKERS.discard(worker)
            if getattr(self, "_sam_worker", None) == worker:
                self._sam_worker = None
                self._sam_running = False
                self.notif_banner.setVisible(False)
            worker.deleteLater()

        worker.progress.connect(_on_prog)
        worker.finished_ok.connect(_on_success)
        worker.failed.connect(_on_fail)
        worker.finished.connect(_cleanup)
        worker.start()

    # ================================================================= HOOKS ==
    def on_hide(self) -> None:
        if self._dirty:
            self.save_current()

    def on_show(self) -> None:
        super().on_show()
        if hasattr(self, "editor_sam_combo"):
            cur_sam = cfg.get("sam.weights", "sam2_l.pt")
            idx = self.editor_sam_combo.findData(cur_sam)
            if idx >= 0:
                self.editor_sam_combo.blockSignals(True)
                self.editor_sam_combo.setCurrentIndex(idx)
                self.editor_sam_combo.blockSignals(False)
        if self.ctrl.current_image_id and self._images:
            self.image_list.select_id(self.ctrl.current_image_id)
        self.canvas.setFocus()


def _color_icon(color: str, size: int = 12):
    from PySide6.QtGui import QIcon, QPainter

    pm = QPixmap(size + 4, size + 4)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(2, 2, size, size, 3, 3)
    p.end()
    return QIcon(pm)
