"""Trang Auto Label: chay YOLO tren toan bo anh trong project."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    CLASS_PALETTE,
    COLORS,
    IMG_REVIEW,
    LABEL_W_NARROW,
    MODEL_ZOO,
    PAGE_EDITOR,
    YOLO_TASKS,
)
from app.core.inference import InferenceConfig, available_devices, device_label
from app.plugins.base import registry
from app.views.pages.base_page import BasePage
from app.views.widgets.common import (
    Card,
    Field,
    LegendItem,
    ProgressPanel,
    SliderField,
    ToggleSwitch,
    combo,
    ghost_button,
    hline,
    label,
    primary_button,
    spin,
)
from app.views.widgets.image_list import ROLE_ID, ImageListPanel
from app.workers.autolabel_worker import AutoLabelWorker, ModelLoadWorker


# ============================================================= PREVIEW ======
class DetectionPreview(QWidget):
    """Hien anh kem overlay ket qua suy luan."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        self._pixmap: QPixmap | None = None
        self._dets = []
        self._colors: dict[str, str] = {}
        self.show_conf = True

    def set_result(self, path: str, detections) -> None:
        pm = QPixmap(path) if path else QPixmap()
        self._pixmap = None if pm.isNull() else pm
        self._dets = list(detections or [])
        for d in self._dets:
            if d.class_name not in self._colors:
                self._colors[d.class_name] = CLASS_PALETTE[len(self._colors) % len(CLASS_PALETTE)]
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self._dets = []
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: D102
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(COLORS["bg"]))
        if self._pixmap is None:
            p.setPen(QPen(QColor(COLORS["text_mute"])))
            p.drawText(self.rect(), Qt.AlignCenter, "Kết quả suy luận sẽ hiện ở đây")
            return

        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min((self.width() - 8) / pw, (self.height() - 8) / ph)
        w, h = pw * scale, ph * scale
        ox, oy = (self.width() - w) / 2, (self.height() - h) / 2
        p.drawPixmap(QRectF(ox, oy, w, h), self._pixmap, QRectF(self._pixmap.rect()))

        f = QFont("Segoe UI", 8)
        f.setBold(True)
        p.setFont(f)
        for d in self._dets:
            color = QColor(self._colors.get(d.class_name, COLORS["accent"]))
            if len(d.polygon) >= 6:
                pts = [(d.polygon[i], d.polygon[i + 1]) for i in range(0, len(d.polygon) - 1, 2)]
                poly = QPolygonF([_pt(ox + x * scale, oy + y * scale) for x, y in pts])
                fill = QColor(color)
                fill.setAlphaF(0.34)
                p.setBrush(fill)
                p.setPen(QPen(color, 1.8))
                p.drawPolygon(poly)
                anchor = poly.boundingRect().topLeft()
            else:
                x1, y1, x2, y2 = d.bbox
                r = QRectF(ox + x1 * scale, oy + y1 * scale, (x2 - x1) * scale, (y2 - y1) * scale)
                fill = QColor(color)
                fill.setAlphaF(0.16)
                p.setBrush(fill)
                p.setPen(QPen(color, 1.8))
                p.drawRect(r)
                anchor = r.topLeft()

            text = d.class_name + (f" {d.confidence:.2f}" if self.show_conf else "")
            fm = p.fontMetrics()
            tw, th = fm.horizontalAdvance(text) + 8, fm.height() + 3
            box = QRectF(anchor.x(), max(oy, anchor.y() - th - 1), tw, th)
            bg = QColor(color)
            bg.setAlpha(230)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(box, 3, 3)
            p.setPen(QPen(QColor("#FFFFFF")))
            p.drawText(box, Qt.AlignCenter, text)


def _pt(x, y):
    from PySide6.QtCore import QPointF

    return QPointF(x, y)


from app.i18n import tr


# ============================================================== PAGE ========
class AutoLabelPage(BasePage):
    TITLE = tr("nav.autolabel", "Auto Label")
    SUBTITLE = tr(
        "autolabel.subtitle", "Tự động sinh nhãn bằng YOLO — Detection, Segmentation, OBB, Pose"
    )
    ICON = "wand"

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._images = []
        self._pending_batch: list[int] = []

    # -------------------------------------------------- nhan anh tu buoc truoc --
    def set_batch(self, image_ids, auto_start: bool = False) -> None:
        """Nhận đúng loạt ảnh vừa cắt ra từ trang Frame Extractor.

        Có thể được gọi trước khi trang này dựng giao diện.
        """
        self.ensure_built()
        self._pending_batch = [int(i) for i in image_ids]
        if not self._pending_batch:
            return
        # Loạt ảnh mới cắt luôn là ảnh chưa gán nhãn -> chọn nhóm tất cả để không bị ẩn sau khi gán nhãn
        idx = self.filter_combo.findData("all")
        if idx >= 0:
            self.filter_combo.blockSignals(True)
            self.filter_combo.setCurrentIndex(idx)
            self.filter_combo.blockSignals(False)
        self.refresh()
        self._apply_batch_selection()
        if auto_start:
            self.start()

    def _apply_batch_selection(self) -> None:
        if not self._pending_batch:
            return
        wanted = set(self._pending_batch)
        self._pending_batch = []

        self.image_list.blockSignals(True)
        self.image_list.clearSelection()
        first_row = -1
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if int(item.data(ROLE_ID)) in wanted:
                item.setSelected(True)
                if first_row < 0:
                    first_row = i
        if first_row >= 0:
            # Đặt item hiện tại nhưng KHÔNG đụng vào vùng đang chọn.
            # setCurrentRow() sẽ xoá hết selection rồi chỉ chọn mỗi dòng đó.
            first_item = self.image_list.item(first_row)
            self.image_list.setCurrentItem(first_item, QItemSelectionModel.NoUpdate)
            self.image_list.scrollToItem(first_item)
        self.image_list.blockSignals(False)

        n = len(self.image_list.selectedItems())
        if n:
            self.batch_hint.setText(
                tr(
                    "autolabel.batch_hint_fmt",
                    "Đang chọn sẵn <b>{count} ảnh vừa cắt</b>. Bấm <b>Bắt đầu gán nhãn</b> là chạy đúng loạt này.",
                    count=f"{n:,}",
                )
            )
            self.batch_hint.setVisible(True)
            if first_row >= 0:
                self._on_image_selected(int(self.image_list.item(first_row).data(ROLE_ID)))

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.load_model_btn = ghost_button(tr("autolabel.load_model", "Nạp model"), "download")
        self.load_model_btn.clicked.connect(self.load_model)
        self.start_btn = primary_button(tr("autolabel.start_btn", "Bắt đầu gán nhãn"), "play")
        self.start_btn.clicked.connect(self.start)
        self.header.add_action(self.load_model_btn)
        self.header.add_action(self.start_btn)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_list(), 2)
        row.addWidget(self._build_settings(), 3)
        row.addWidget(self._build_preview(), 5)
        self.add(row, 1)

        self.progress = ProgressPanel()
        self.progress.cancelled.connect(self.cancel)
        self.add(self.progress)

        self.ctrl.imagesChanged.connect(self.refresh)
        self.ctrl.projectOpened.connect(lambda *_: self.refresh())
        self._on_task_changed()

    # ------------------------------------------------------------- danh sach --
    def _build_list(self) -> QWidget:
        card = Card(tr("autolabel.images_card", "Ảnh trong project"), "", "image")
        self.filter_combo = combo(
            [
                ("all", tr("autolabel.filter_all", "Tất cả ảnh")),
                ("unlabeled", tr("autolabel.filter_unlabeled", "Chưa gán nhãn")),
                ("review", tr("autolabel.filter_review", "Cần xem lại")),
                ("approved", tr("autolabel.filter_approved", "Đã duyệt")),
                ("no_dup", tr("autolabel.filter_no_dup", "Bỏ qua ảnh trùng")),
            ]
        )
        self.filter_combo.currentIndexChanged.connect(self.refresh)
        card.add(self.filter_combo)

        self.batch_hint = label("", size=11.5, color=COLORS["accent_hi"], wrap=True)
        self.batch_hint.setVisible(False)
        card.add(self.batch_hint)

        self.image_list = ImageListPanel()
        self.image_list.imageSelected.connect(self._on_image_selected)
        card.add(self.image_list, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.select_all_btn = ghost_button(tr("autolabel.select_all", "Chọn tất cả"))
        self.select_all_btn.clicked.connect(self.image_list.selectAll)
        row.addWidget(self.select_all_btn)
        row.addStretch(1)
        self.count_label = label(
            tr("autolabel.images_count", "{count} ảnh", count=0),
            size=11.5,
            color=COLORS["text_mute"],
        )
        row.addWidget(self.count_label)
        card.add(row)
        return card

    # ---------------------------------------------------------------- config --
    def _build_settings(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        model_card = Card(tr("autolabel.model_config", "Cấu hình model"), "", "cpu")
        self.task_combo = combo(
            [
                (
                    t,
                    {
                        "detect": "Detection",
                        "segment": "Segmentation",
                        "obb": "OBB — hộp xoay",
                        "pose": "Pose — điểm khớp",
                    }[t],
                )
                for t in YOLO_TASKS
            ],
            current=cfg.get("model.task", "segment"),
        )
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        model_card.add(
            Field(tr("autolabel.task", "Nhiệm vụ"), self.task_combo, label_width=LABEL_W_NARROW)
        )

        self.weights_combo = combo([])
        self.weights_combo.setEditable(False)
        model_card.add(
            Field(
                tr("autolabel.weights", "Trọng số"), self.weights_combo, label_width=LABEL_W_NARROW
            )
        )

        custom_row = QWidget()
        cr = QHBoxLayout(custom_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        self.custom_label = label(
            tr("autolabel.no_custom_weights", "Không dùng"), size=11.5, color=COLORS["text_mute"]
        )
        pick = ghost_button(tr("autolabel.choose_file", "Chọn file"), "folder")
        pick.clicked.connect(self._choose_weights)
        clear = ghost_button(tr("autolabel.clear", "Xoá"))
        clear.clicked.connect(self._clear_weights)
        cr.addWidget(self.custom_label, 1)
        cr.addWidget(pick)
        cr.addWidget(clear)
        model_card.add(
            Field(
                tr("autolabel.custom_model", "Model riêng"),
                custom_row,
                label_width=LABEL_W_NARROW,
                hint=tr("autolabel.custom_model_hint", "Hỗ trợ .pt, .onnx, .engine"),
            )
        )

        self.device_combo = combo(available_devices(), current=cfg.get("model.device", "auto"))
        model_card.add(
            Field(tr("autolabel.device", "Thiết bị"), self.device_combo, label_width=LABEL_W_NARROW)
        )
        self.imgsz_spin = spin(cfg.get("model.imgsz", 640), 128, 4096, 32, width=110)
        model_card.add(
            Field(
                tr("autolabel.imgsz", "Cỡ ảnh vào model"),
                self.imgsz_spin,
                label_width=LABEL_W_NARROW,
            )
        )

        self.model_status = label(
            tr("autolabel.model_unloaded", "Chưa nạp model"), size=11.5, color=COLORS["warning"]
        )
        model_card.add(hline())
        model_card.add(self.model_status)
        lay.addWidget(model_card)

        infer_card = Card(tr("autolabel.infer_params", "Tham số suy luận"), "", "sliders")
        self.conf_slider = SliderField(cfg.get("inference.confidence", 0.45), 0.01, 0.99, 2)
        infer_card.add(
            Field(tr("autolabel.conf", "Độ tin cậy"), self.conf_slider, label_width=LABEL_W_NARROW)
        )
        self.iou_slider = SliderField(cfg.get("inference.iou", 0.5), 0.05, 0.95, 2)
        infer_card.add(
            Field(
                tr("autolabel.iou", "IOU (khử trùng)"), self.iou_slider, label_width=LABEL_W_NARROW
            )
        )
        self.review_slider = SliderField(cfg.get("inference.review_threshold", 0.6), 0.05, 0.99, 2)
        infer_card.add(
            Field(
                tr("autolabel.review_thresh", "Ngưỡng xem lại"),
                self.review_slider,
                label_width=LABEL_W_NARROW,
                hint=tr(
                    "autolabel.review_thresh_hint",
                    "Dự đoán thấp hơn ngưỡng này sẽ bị đánh dấu Cần xem lại",
                ),
            )
        )
        self.maxdet_spin = spin(cfg.get("inference.max_det", 1000), 1, 30000, 50, width=110)
        infer_card.add(
            Field(
                tr("autolabel.max_det", "Số đối tượng tối đa"),
                self.maxdet_spin,
                label_width=LABEL_W_NARROW,
            )
        )
        self.simplify_slider = SliderField(
            cfg.get("inference.polygon_simplify", 0.0025), 0.0, 0.02, 4, 0.0005
        )
        infer_card.add(
            Field(
                tr("autolabel.simplify", "Giản lược polygon"),
                self.simplify_slider,
                label_width=LABEL_W_NARROW,
            )
        )
        self.minarea_spin = spin(
            cfg.get("inference.min_area_px", 24), 0, 100000, 4, suffix=" px", width=110
        )
        infer_card.add(
            Field(
                tr("autolabel.min_area", "Diện tích tối thiểu"),
                self.minarea_spin,
                label_width=LABEL_W_NARROW,
            )
        )

        self.overwrite_toggle = ToggleSwitch(cfg.get("inference.overwrite_existing", True))
        ow = QHBoxLayout()
        ow.addWidget(
            label(tr("autolabel.overwrite", "Ghi đè nhãn đã có"), size=12, color=COLORS["text_dim"])
        )
        ow.addStretch(1)
        ow.addWidget(self.overwrite_toggle)
        infer_card.add(ow)

        infer_card.add(hline())
        self.tracking_toggle = ToggleSwitch(cfg.get("inference.use_tracking", False))
        self.tracking_toggle.toggled.connect(self._on_tracking_toggled)
        tr_row = QHBoxLayout()
        tr_row.addWidget(
            label(
                tr("autolabel.use_tracking", "Theo dõi đối tượng qua frame"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        tr_row.addStretch(1)
        tr_row.addWidget(self.tracking_toggle)
        infer_card.add(tr_row)

        self.tracker_combo = combo(
            [
                ("botsort.yaml", "BoT-SORT"),
                ("bytetrack.yaml", "ByteTrack"),
            ],
            current=cfg.get("inference.tracker_type", "botsort.yaml"),
        )
        infer_card.add(
            Field(
                tr("autolabel.tracker_alg", "Thuật toán tracker"),
                self.tracker_combo,
                label_width=LABEL_W_NARROW,
            )
        )

        self.tracking_warning = label("", size=11, color=COLORS["warning"], wrap=True)
        infer_card.add(self.tracking_warning)

        lay.addWidget(infer_card)

        # --- Card: Suy luan cat lat ---
        sahi_card = Card(
            tr("autolabel.sahi_card", "Suy luận cắt lát (ảnh lớn)"),
            tr(
                "autolabel.sahi_card_sub",
                "Tăng khả năng phát hiện đối tượng nhỏ trên ảnh độ phân giải cao",
            ),
            "grid",
        )

        self.sahi_toggle = ToggleSwitch(cfg.get("inference.sahi_enabled", False))
        self.sahi_toggle.toggled.connect(self._on_sahi_toggled)
        sahi_row = QHBoxLayout()
        sahi_row.addWidget(
            label(
                tr("autolabel.sahi_enable", "Bật suy luận cắt lát"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        sahi_row.addStretch(1)
        sahi_row.addWidget(self.sahi_toggle)
        sahi_card.add(sahi_row)

        self.sahi_slice_spin = spin(
            cfg.get("inference.sahi_slice_size", 640), 64, 2048, 64, suffix=" px", width=110
        )
        sahi_card.add(
            Field(
                tr("autolabel.sahi_slice", "Cỡ ô"),
                self.sahi_slice_spin,
                label_width=LABEL_W_NARROW,
                hint=tr(
                    "autolabel.sahi_slice_hint",
                    "Khuyến nghị: bằng kích thước ảnh đầu vào model (mặc định 640)",
                ),
            )
        )

        self.sahi_overlap_slider = SliderField(
            cfg.get("inference.sahi_overlap", 0.2), 0.0, 0.5, 2, 0.05
        )
        sahi_card.add(
            Field(
                tr("autolabel.sahi_overlap", "Tỉ lệ chồng lấn"),
                self.sahi_overlap_slider,
                label_width=LABEL_W_NARROW,
                hint=tr(
                    "autolabel.sahi_overlap_hint",
                    "Tăng để bắt đối tượng sát biên ô, giảm để chạy nhanh hơn",
                ),
            )
        )

        self.sahi_hint = label(
            tr(
                "autolabel.sahi_perf_hint",
                "Ảnh 4K với ô 640px tạo ~35 ô — chậm hơn ~10–30 lần so với suy luận thường.",
            ),
            size=11,
            color=COLORS["text_mute"],
            wrap=True,
        )
        sahi_card.add(self.sahi_hint)

        lay.addWidget(sahi_card)
        self._on_sahi_toggled(self.sahi_toggle.isChecked())

        plugin_card = Card(
            tr("autolabel.refine_plugin", "Plugin tinh chỉnh"),
            tr("autolabel.refine_plugin_sub", "Cải thiện chất lượng nhãn tự động"),
            "puzzle",
        )
        items = [("", tr("autolabel.no_plugin", "Không dùng plugin"))]
        for info in registry.infos():
            items.append((info.key, info.name))
        self.plugin_combo = combo(items)
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        plugin_card.add(self.plugin_combo)
        self.plugin_desc = label("", size=11.5, color=COLORS["text_mute"], wrap=True)
        plugin_card.add(self.plugin_desc)
        sam_presets = [
            ("sam2_l.pt", "SAM 2 Large — Mạnh mẽ nhất (300 MB)"),
            ("sam2_b.pt", "SAM 2 Base — Nhanh & Chính xác (148 MB)"),
            ("sam_b.pt", "SAM 1 Base — Chuẩn (366 MB)"),
            ("sam_l.pt", "SAM 1 Large — Độ phân giải cao (1.2 GB)"),
            ("FastSAM-s.pt", "FastSAM Small — Siêu tốc (25 MB)"),
            ("FastSAM-x.pt", "FastSAM Extra Large (140 MB)"),
        ]
        cur_sam = cfg.get("sam.weights", "sam2_l.pt")
        self.plugin_sam_combo = combo(
            sam_presets,
            current=cur_sam if any(w == cur_sam for w, _ in sam_presets) else "sam2_l.pt",
        )
        self.plugin_sam_field = Field(
            tr("autolabel.sam_weights", "Trọng số SAM"),
            self.plugin_sam_combo,
            label_width=LABEL_W_NARROW,
        )
        self.plugin_sam_field.setVisible(False)
        plugin_card.add(self.plugin_sam_field)

        from PySide6.QtWidgets import QLineEdit

        self.plugin_prompt = QLineEdit()
        self.plugin_prompt.setPlaceholderText(
            tr("autolabel.prompt_placeholder", "Mô tả bằng chữ, ví dụ: crack, rust, bolt")
        )
        self.plugin_prompt.setVisible(False)
        plugin_card.add(self.plugin_prompt)

        self.plugin_status = label("", size=11.5, color=COLORS["text_mute"])
        plugin_card.add(self.plugin_status)
        lay.addWidget(plugin_card)
        lay.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(wrap)
        return area

    # --------------------------------------------------------------- preview --
    def _build_preview(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(12)

        card = Card(tr("autolabel.preview_results", "Xem trước kết quả"), "", "eye")
        self.preview = DetectionPreview()
        card.add(self.preview, 1)
        lay.addWidget(card, 1)

        stat_card = Card(tr("autolabel.results_card", "Kết quả"), "", "chart")
        self.leg_total = LegendItem(
            COLORS["accent"], tr("autolabel.processed_images", "Ảnh đã xử lý"), "0"
        )
        self.leg_objects = LegendItem(
            COLORS["info"], tr("autolabel.generated_objects", "Đối tượng sinh ra"), "0"
        )
        self.leg_review = LegendItem(
            COLORS["warning"], tr("autolabel.images_need_review", "Ảnh cần xem lại"), "0"
        )
        self.leg_lowconf = LegendItem(
            COLORS["danger"], tr("autolabel.low_conf_predictions", "Dự đoán độ tin cậy thấp"), "0"
        )
        self.leg_empty = LegendItem(
            COLORS["text_mute"], tr("autolabel.empty_images", "Ảnh không có đối tượng"), "0"
        )
        for w in (
            self.leg_total,
            self.leg_objects,
            self.leg_review,
            self.leg_lowconf,
            self.leg_empty,
        ):
            stat_card.add(w)
        stat_card.add(hline())
        self.review_btn = ghost_button(
            tr("autolabel.open_editor", "Mở trình sửa nhãn để xem lại"), "pen"
        )
        self.review_btn.clicked.connect(lambda: self.request_editor())
        stat_card.add(self.review_btn)
        lay.addWidget(stat_card)

        log_card = Card(tr("autolabel.log_card", "Nhật ký"), "", "file")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        log_card.add(self.log_view)
        lay.addWidget(log_card)

        scroll.setWidget(wrap)
        return scroll

    # =============================================================== EVENTS ==
    def request_editor(self) -> None:
        parent = self.window()
        if hasattr(parent, "go_to_page"):
            parent.go_to_page(PAGE_EDITOR)

    def _on_task_changed(self) -> None:
        task = self.task_combo.currentData()
        self.weights_combo.clear()
        for w in MODEL_ZOO.get(task, []):
            self.weights_combo.addItem(w, w)
        saved = cfg.get("model.weights", "")
        idx = self.weights_combo.findData(saved)
        if idx >= 0:
            self.weights_combo.setCurrentIndex(idx)

    def _choose_weights(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("autolabel.choose_weights_title", "Chọn file trọng số"),
            "",
            "Model (*.pt *.onnx *.engine *.torchscript);;Tất cả file (*)",
        )
        if path:
            cfg.set("model.custom_weights", path)
            self.custom_label.setText(Path(path).name)
            self.custom_label.setToolTip(path)

    def _clear_weights(self) -> None:
        cfg.set("model.custom_weights", "")
        self.custom_label.setText(tr("autolabel.no_custom_weights", "Không dùng"))

    def _on_plugin_changed(self) -> None:
        key = self.plugin_combo.currentData()
        if hasattr(self, "plugin_sam_field"):
            self.plugin_sam_field.setVisible(key == "sam")
        if not key:
            self.plugin_desc.setText(
                tr("autolabel.only_yolo_hint", "Chỉ dùng YOLO, không qua plugin.")
            )
            self.plugin_status.setText("")
            if hasattr(self, "plugin_prompt"):
                self.plugin_prompt.setEnabled(False)
            return
        info = next((i for i in registry.infos() if i.key == key), None)
        if info is None:
            return
        self.plugin_desc.setText(info.description)
        if hasattr(self, "plugin_prompt"):
            self.plugin_prompt.setEnabled(info.accepts_prompt)
        ok, msg = registry.status(key)
        color = COLORS["success"] if ok else COLORS["warning"]
        self.plugin_status.setText(msg)
        self.plugin_status.setStyleSheet(f"font-size: 11.5px; color: {color};")

    def _on_plugin_sam_changed(self, idx: int) -> None:
        val = self.plugin_sam_combo.currentData()
        if val:
            cfg.set("sam.weights", val)
            cfg.save()

    def _on_image_selected(self, image_id: int) -> None:
        rec = self.repo.image(image_id) if self.repo else None
        if rec is None:
            return
        self.ctrl.set_current_image(image_id)
        anns = self.repo.annotations(image_id)
        dets = []
        for a in anns:
            from app.core.inference import Detection

            dets.append(
                Detection(
                    class_id=a.class_id,
                    class_name=a.class_name or "",
                    confidence=a.confidence,
                    bbox=list(a.bbox),
                    polygon=list(a.polygon),
                    shape=a.shape,
                )
            )
        self.preview.set_result(rec.path, dets)

    # ================================================================= MODEL ==
    def selected_weights(self) -> str:
        custom = cfg.get("model.custom_weights", "")
        if custom:
            return custom
        return self.weights_combo.currentData() or "yolo11m-seg.pt"

    def cancel(self) -> None:
        self._pending_start = False
        if self.ctrl.is_running("model"):
            self.ctrl.cancel("model")
        if self.ctrl.is_running("autolabel"):
            self.ctrl.cancel("autolabel")

    def load_model(self) -> None:
        if self.ctrl.is_running("model"):
            return
        weights = self.selected_weights()
        task = self.task_combo.currentData()
        device = self.device_combo.currentData()
        cfg.update_section(
            "model",
            {
                "task": task,
                "weights": self.weights_combo.currentData() or "",
                "device": device,
                "imgsz": self.imgsz_spin.value(),
            },
        )
        cfg.save()

        self.model_status.setText(tr("autolabel.model_loading", "Đang nạp model …"))
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['info']};")
        self.load_model_btn.setEnabled(False)

        worker = ModelLoadWorker(self.ctrl.engine, weights, task, device)
        started = self.ctrl.run_worker(
            "model",
            worker,
            on_log=self._append_log,
            on_done=self._on_model_loaded,
            on_fail=self._on_model_failed,
            on_cancelled=self._on_model_cancelled,
        )
        if not started:
            self.load_model_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.progress.reset()
            self._pending_start = False

    def _on_model_loaded(self, engine) -> None:
        self.load_model_btn.setEnabled(True)
        eng = self.ctrl.engine
        self.model_status.setText(eng.describe())
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        self.toast(
            tr(
                "autolabel.loaded_toast",
                "Đã nạp model, chạy trên {device}.",
                device=device_label(eng.device),
            ),
            "success",
        )
        self.ctrl.modelChanged.emit()
        if getattr(self, "_pending_start", False):
            self._pending_start = False
            self.start()
        else:
            self.start_btn.setEnabled(True)

    def _on_model_failed(self, msg: str) -> None:
        self.load_model_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.progress.reset()
        self._pending_start = False
        self.model_status.setText(tr("autolabel.model_load_failed", "Nạp model thất bại"))
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['danger']};")

    def _on_model_cancelled(self) -> None:
        self.load_model_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.progress.reset()
        self._pending_start = False
        if self.ctrl.engine.loaded:
            self.model_status.setText(self.ctrl.engine.describe())
            self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        else:
            self.model_status.setText(tr("autolabel.model_cancelled", "Đã hủy nạp model"))
            self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['text_mute']};")

    # ================================================================== RUN ===
    def start(self) -> None:
        if not self.ctrl.has_project:
            self.toast(
                tr("autolabel.open_project_first", "Hãy mở hoặc tạo project trước."), "warning"
            )
            return
        if self.ctrl.is_running("autolabel"):
            self.toast(tr("autolabel.labeling_wait", "Đang gán nhãn, vui lòng đợi."), "warning")
            return
        if self.ctrl.is_running("train"):
            self.toast(
                tr(
                    "autolabel.train_conflict",
                    "Đang có tiến trình huấn luyện mô hình chạy. Vui lòng dừng hoặc đợi hoàn tất trước khi gán nhãn.",
                ),
                "warning",
            )
            return
        if not self.ctrl.engine.loaded:
            self.toast(
                tr("autolabel.loading_model_first", "Đang nạp model trước khi chạy …"), "info"
            )
            self._pending_start = True
            self.progress.start(tr("autolabel.model_loading", "Đang nạp model …"))
            self.start_btn.setEnabled(False)
            self.load_model()
            return

        ids = self.image_list.selected_ids() or self.image_list.all_ids()
        if not ids:
            self.start_btn.setEnabled(True)
            self.progress.finish()
            self.toast(
                tr("autolabel.no_images_to_label", "Không có ảnh nào để gán nhãn."), "warning"
            )
            return

        icfg = InferenceConfig(
            confidence=self.conf_slider.value(),
            iou=self.iou_slider.value(),
            max_det=self.maxdet_spin.value(),
            imgsz=self.imgsz_spin.value(),
            polygon_simplify=self.simplify_slider.value(),
            min_area_px=self.minarea_spin.value(),
            retina_masks=cfg.get("inference.retina_masks", True),
            sahi_enabled=self.sahi_toggle.isChecked(),
            sahi_slice_size=self.sahi_slice_spin.value(),
            sahi_overlap=self.sahi_overlap_slider.value(),
        )
        use_tracking = self.tracking_toggle.isChecked() and self.tracking_toggle.isEnabled()
        tracker_type = self.tracker_combo.currentData() or "botsort.yaml"

        cfg.update_section(
            "inference",
            {
                "confidence": icfg.confidence,
                "iou": icfg.iou,
                "max_det": icfg.max_det,
                "review_threshold": self.review_slider.value(),
                "polygon_simplify": icfg.polygon_simplify,
                "min_area_px": icfg.min_area_px,
                "overwrite_existing": self.overwrite_toggle.isChecked(),
                "use_tracking": use_tracking,
                "tracker_type": tracker_type,
                "sahi_enabled": icfg.sahi_enabled,
                "sahi_slice_size": icfg.sahi_slice_size,
                "sahi_overlap": icfg.sahi_overlap,
            },
        )
        cfg.save()

        self.log_view.clear()
        self.progress.start(
            tr("autolabel.labeling_progress", "Đang gán nhãn {count} ảnh …", count=f"{len(ids):,}")
        )
        self.start_btn.setEnabled(False)

        worker = AutoLabelWorker(
            self.ctrl.repo,
            self.ctrl.engine,
            ids,
            icfg,
            review_threshold=self.review_slider.value(),
            low_conf_threshold=cfg.get("inference.low_conf_threshold", 0.35),
            overwrite=self.overwrite_toggle.isChecked(),
            plugin_key=self.plugin_combo.currentData() or "",
            plugin_prompt=self.plugin_prompt.text().strip(),
            use_tracking=use_tracking,
            tracker_type=tracker_type,
        )
        worker.preview.connect(self.preview.set_result)
        worker.image_done.connect(self._on_image_done)
        started = self.ctrl.run_worker(
            "autolabel",
            worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_log=self._append_log,
            on_done=self._on_done,
            on_fail=self._on_autolabel_failed,
            on_cancelled=self._on_autolabel_cancelled,
        )
        if not started:
            self.start_btn.setEnabled(True)
            self.progress.reset()

    def _on_image_done(self, image_id: int, n_objects: int, max_conf: float) -> None:
        status = IMG_REVIEW if max_conf < self.review_slider.value() else "auto"
        class_color = ""
        if n_objects and self.repo:
            anns = self.repo.annotations(image_id)
            if anns:
                c_def = self.repo.class_by_id(anns[0].class_id)
                if c_def:
                    class_color = c_def.color
        self.image_list.update_item(
            image_id,
            status if n_objects else "unlabeled",
            n_objects,
            class_color=class_color,
        )

    def _on_done(self, result) -> None:
        self.start_btn.setEnabled(True)
        self.progress.finish(tr("autolabel.labeling_done", "Gán nhãn hoàn tất"))
        if hasattr(self, "batch_hint"):
            self.batch_hint.setVisible(False)
        if result is None:
            return
        self.leg_total.set_value(f"{result.n_images:,}")
        self.leg_objects.set_value(f"{result.n_objects:,}")
        self.leg_review.set_value(f"{result.n_review:,}")
        self.leg_lowconf.set_value(f"{result.n_low_conf:,}")
        self.leg_empty.set_value(f"{result.n_empty:,}")
        self.toast(
            tr(
                "autolabel.done_toast",
                "Xong: {objects} đối tượng trên {images} ảnh ({fps:.1f} ảnh/giây).",
                objects=f"{result.n_objects:,}",
                images=f"{result.n_images:,}",
                fps=result.fps,
            ),
            "success",
        )
        self.ctrl.notify_images_changed()
        self.ctrl.notify_classes_changed()
        self.refresh()

    def _on_autolabel_cancelled(self) -> None:
        self.start_btn.setEnabled(True)
        self.progress.reset()
        if hasattr(self, "batch_hint"):
            self.batch_hint.setVisible(False)
        self.toast(tr("autolabel.cancelled_toast", "Đã dừng gán nhãn an toàn."), "info")
        self.ctrl.notify_images_changed()
        self.refresh()

    def _on_autolabel_failed(self, msg: str) -> None:
        self.start_btn.setEnabled(True)
        self.progress.reset()
        self.refresh()

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _on_tracking_toggled(self, checked: bool) -> None:
        self.tracker_combo.setEnabled(checked)
        self._update_tracking_warning()

    def _on_sahi_toggled(self, checked: bool) -> None:
        self.sahi_slice_spin.setEnabled(checked)
        self.sahi_overlap_slider.setEnabled(checked)
        self.sahi_hint.setVisible(checked)

    def _update_tracking_warning(self) -> None:
        if not hasattr(self, "tracking_toggle"):
            return
        has_frames = any(im.frame_index >= 0 for im in self._images) if self._images else False
        self.tracking_toggle.setEnabled(has_frames)
        if not has_frames:
            self.tracking_toggle.setChecked(False)
            self.tracker_combo.setEnabled(False)
            self.tracking_warning.setText(
                tr(
                    "autolabel.no_frame_indices",
                    "Chỉ bật theo dõi khi ảnh có thứ tự frame (từ Frame Extractor).",
                )
            )
            return

        self.tracker_combo.setEnabled(self.tracking_toggle.isChecked())
        if self.tracking_toggle.isChecked():
            frame_indices = sorted([im.frame_index for im in self._images if im.frame_index >= 0])
            if len(frame_indices) >= 2:
                gaps = [
                    frame_indices[i + 1] - frame_indices[i] for i in range(len(frame_indices) - 1)
                ]
                avg_gap = sum(gaps) / len(gaps)
                if avg_gap > 3:
                    self.tracking_warning.setText(
                        tr(
                            "autolabel.sparse_frame_warn",
                            "Cảnh báo: Khoảng cách frame trung bình ({gap:.1f}) khá thưa, có thể làm giảm độ chính xác của tracking.",
                            gap=avg_gap,
                        )
                    )
                else:
                    self.tracking_warning.setText(
                        tr("autolabel.tracking_active_hint", "Đã bật theo dõi đối tượng qua frame.")
                    )
            else:
                self.tracking_warning.setText("")
        else:
            self.tracking_warning.setText("")

    # =============================================================== REFRESH ==
    def on_project_changed(self) -> None:
        self._pending_start = False
        if hasattr(self, "preview"):
            self.preview.clear()
        if hasattr(self, "log_view"):
            self.log_view.clear()
        if hasattr(self, "leg_total"):
            for lg in (self.leg_total, self.leg_objects, self.leg_review, self.leg_lowconf):
                lg.set_value("0")
        if hasattr(self, "start_btn"):
            self.start_btn.setEnabled(True)
        if hasattr(self, "progress"):
            self.progress.reset()

    def on_show(self) -> None:
        super().on_show()
        if hasattr(self, "start_btn"):
            is_busy = self.ctrl.is_running("autolabel") or self.ctrl.is_running("model")
            self.start_btn.setEnabled(not is_busy)
            if not is_busy and hasattr(self, "progress") and not self.progress.isHidden():
                self.progress.reset()

    def refresh(self) -> None:
        if not self.repo:
            return
        key = self.filter_combo.currentData() if hasattr(self, "filter_combo") else "all"
        kwargs = {}
        if key == "unlabeled":
            kwargs["status"] = "unlabeled"
        elif key == "review":
            kwargs["status"] = "review"
        elif key == "approved":
            kwargs["status"] = "approved"
        elif key == "no_dup":
            kwargs["include_duplicates"] = False
        self._images = self.repo.images(**kwargs)

        img_colors = {}
        if self._images:
            c_map = {c.id: c.color for c in self.repo.classes()}
            rows = self.repo.db.query("SELECT image_id, class_id FROM annotation GROUP BY image_id")
            for r in rows:
                if r["class_id"] in c_map:
                    img_colors[r["image_id"]] = c_map[r["class_id"]]

        self.image_list.set_images(self._images, img_colors)
        self.count_label.setText(
            tr("autolabel.images_count", "{count} ảnh", count=f"{len(self._images):,}")
        )
        if self.ctrl.engine.loaded:
            self.model_status.setText(self.ctrl.engine.describe())
            self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        self._update_tracking_warning()
