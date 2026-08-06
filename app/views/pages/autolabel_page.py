"""Trang Auto Label: chay YOLO tren toan bo anh trong project."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    LABEL_W_NARROW,
    CLASS_PALETTE,
    COLORS,
    IMG_REVIEW,
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
    section_label,
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
        pm = QPixmap(path)
        self._pixmap = None if pm.isNull() else pm
        self._dets = list(detections or [])
        for d in self._dets:
            if d.class_name not in self._colors:
                self._colors[d.class_name] = CLASS_PALETTE[
                    len(self._colors) % len(CLASS_PALETTE)]
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
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Kết quả suy luận sẽ hiện ở đây")
            return

        pw, ph = self._pixmap.width(), self._pixmap.height()
        scale = min((self.width() - 8) / pw, (self.height() - 8) / ph)
        w, h = pw * scale, ph * scale
        ox, oy = (self.width() - w) / 2, (self.height() - h) / 2
        p.drawPixmap(QRectF(ox, oy, w, h), self._pixmap, QRectF(self._pixmap.rect()))

        f = QFont()
        f.setPointSize(8)
        f.setBold(True)
        p.setFont(f)
        for d in self._dets:
            color = QColor(self._colors.get(d.class_name, COLORS["accent"]))
            if len(d.polygon) >= 6:
                pts = [(d.polygon[i], d.polygon[i + 1])
                       for i in range(0, len(d.polygon) - 1, 2)]
                poly = QPolygonF([_pt(ox + x * scale, oy + y * scale) for x, y in pts])
                fill = QColor(color)
                fill.setAlphaF(0.34)
                p.setBrush(fill)
                p.setPen(QPen(color, 1.8))
                p.drawPolygon(poly)
                anchor = poly.boundingRect().topLeft()
            else:
                x1, y1, x2, y2 = d.bbox
                r = QRectF(ox + x1 * scale, oy + y1 * scale,
                           (x2 - x1) * scale, (y2 - y1) * scale)
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


# ============================================================== PAGE ========
class AutoLabelPage(BasePage):
    TITLE = "Auto Label"
    SUBTITLE = "Tự động sinh nhãn bằng YOLO — Detection, Segmentation, OBB, Pose"
    ICON = "wand"

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._images = []
        self._pending_batch: list[int] = []

    # -------------------------------------------------- nhan anh tu buoc truoc --
    def set_batch(self, image_ids) -> None:
        """Nhận đúng loạt ảnh vừa cắt ra từ trang Frame Extractor.

        Có thể được gọi trước khi trang này dựng giao diện.
        """
        self.ensure_built()
        self._pending_batch = [int(i) for i in image_ids]
        if not self._pending_batch:
            return
        # Loạt ảnh mới cắt luôn là ảnh chưa gán nhãn -> lọc đúng nhóm đó
        idx = self.filter_combo.findData("unlabeled")
        if idx >= 0:
            self.filter_combo.blockSignals(True)
            self.filter_combo.setCurrentIndex(idx)
            self.filter_combo.blockSignals(False)
        self.refresh()
        self._apply_batch_selection()

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
                f"Đang chọn sẵn <b>{n:,} ảnh vừa cắt</b>. Bấm "
                f"<b>Bắt đầu gán nhãn</b> là chạy đúng loạt này.")
            self.batch_hint.setVisible(True)
            if first_row >= 0:
                self._on_image_selected(int(
                    self.image_list.item(first_row).data(ROLE_ID)))

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.load_model_btn = ghost_button("Nạp model", "download")
        self.load_model_btn.clicked.connect(self.load_model)
        self.start_btn = primary_button("Bắt đầu gán nhãn", "play")
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
        self.progress.cancelled.connect(lambda: self.ctrl.cancel("autolabel"))
        self.add(self.progress)

        self.ctrl.imagesChanged.connect(self.refresh)
        self.ctrl.projectOpened.connect(lambda *_: self.refresh())
        self._on_task_changed()

    # ------------------------------------------------------------- danh sach --
    def _build_list(self) -> QWidget:
        card = Card("Ảnh trong project", "", "image")
        self.filter_combo = combo([
            ("all", "Tất cả ảnh"), ("unlabeled", "Chưa gán nhãn"),
            ("review", "Cần xem lại"), ("approved", "Đã duyệt"),
            ("no_dup", "Bỏ qua ảnh trùng"),
        ])
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
        self.select_all_btn = ghost_button("Chọn tất cả")
        self.select_all_btn.clicked.connect(self.image_list.selectAll)
        row.addWidget(self.select_all_btn)
        row.addStretch(1)
        self.count_label = label("0 ảnh", size=11.5, color=COLORS["text_mute"])
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

        model_card = Card("Cấu hình model", "", "cpu")
        self.task_combo = combo(
            [(t, {"detect": "Detection", "segment": "Segmentation",
                  "obb": "OBB — hộp xoay", "pose": "Pose — điểm khớp"}[t]) for t in YOLO_TASKS],
            current=cfg.get("model.task", "segment"))
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        model_card.add(Field("Nhiệm vụ", self.task_combo, label_width=LABEL_W_NARROW))

        self.weights_combo = combo([])
        self.weights_combo.setEditable(False)
        model_card.add(Field("Trọng số", self.weights_combo, label_width=LABEL_W_NARROW))

        custom_row = QWidget()
        cr = QHBoxLayout(custom_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        self.custom_label = label("Không dùng", size=11.5, color=COLORS["text_mute"])
        pick = ghost_button("Chọn file", "folder")
        pick.clicked.connect(self._choose_weights)
        clear = ghost_button("Xoá")
        clear.clicked.connect(self._clear_weights)
        cr.addWidget(self.custom_label, 1)
        cr.addWidget(pick)
        cr.addWidget(clear)
        model_card.add(Field("Model riêng", custom_row, label_width=LABEL_W_NARROW,
                             hint="Hỗ trợ .pt, .onnx, .engine"))

        self.device_combo = combo(available_devices(),
                                  current=cfg.get("model.device", "auto"))
        model_card.add(Field("Thiết bị", self.device_combo, label_width=LABEL_W_NARROW))
        self.imgsz_spin = spin(cfg.get("model.imgsz", 640), 128, 4096, 32, width=110)
        model_card.add(Field("Cỡ ảnh vào model", self.imgsz_spin, label_width=LABEL_W_NARROW))

        self.model_status = label("Chưa nạp model", size=11.5, color=COLORS["warning"])
        model_card.add(hline())
        model_card.add(self.model_status)
        lay.addWidget(model_card)

        infer_card = Card("Tham số suy luận", "", "sliders")
        self.conf_slider = SliderField(cfg.get("inference.confidence", 0.45), 0.01, 0.99, 2)
        infer_card.add(Field("Độ tin cậy", self.conf_slider, label_width=LABEL_W_NARROW))
        self.iou_slider = SliderField(cfg.get("inference.iou", 0.5), 0.05, 0.95, 2)
        infer_card.add(Field("IOU (khử trùng)", self.iou_slider, label_width=LABEL_W_NARROW))
        self.review_slider = SliderField(cfg.get("inference.review_threshold", 0.6),
                                         0.05, 0.99, 2)
        infer_card.add(Field("Ngưỡng xem lại", self.review_slider, label_width=LABEL_W_NARROW,
                             hint="Dự đoán thấp hơn ngưỡng này sẽ bị đánh dấu Cần xem lại"))
        self.maxdet_spin = spin(cfg.get("inference.max_det", 1000), 1, 30000, 50, width=110)
        infer_card.add(Field("Số đối tượng tối đa", self.maxdet_spin, label_width=LABEL_W_NARROW))
        self.simplify_slider = SliderField(cfg.get("inference.polygon_simplify", 0.0025),
                                           0.0, 0.02, 4, 0.0005)
        infer_card.add(Field("Giản lược polygon", self.simplify_slider, label_width=LABEL_W_NARROW))
        self.minarea_spin = spin(cfg.get("inference.min_area_px", 24), 0, 100000, 4,
                                 suffix=" px", width=110)
        infer_card.add(Field("Diện tích tối thiểu", self.minarea_spin, label_width=LABEL_W_NARROW))

        self.overwrite_toggle = ToggleSwitch(cfg.get("inference.overwrite_existing", True))
        ow = QHBoxLayout()
        ow.addWidget(label("Ghi đè nhãn đã có", size=12, color=COLORS["text_dim"]))
        ow.addStretch(1)
        ow.addWidget(self.overwrite_toggle)
        infer_card.add(ow)
        lay.addWidget(infer_card)

        plugin_card = Card("Plugin tinh chỉnh", "Cải thiện chất lượng nhãn tự động",
                           "puzzle")
        items = [("", "Không dùng plugin")]
        for info in registry.infos():
            items.append((info.key, info.name))
        self.plugin_combo = combo(items)
        self.plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        plugin_card.add(self.plugin_combo)
        self.plugin_desc = label("", size=11.5, color=COLORS["text_mute"], wrap=True)
        plugin_card.add(self.plugin_desc)
        from PySide6.QtWidgets import QLineEdit
        self.plugin_prompt = QLineEdit()
        self.plugin_prompt.setPlaceholderText("Mô tả bằng chữ, ví dụ: crack, rust, bolt")
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
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        card = Card("Xem trước kết quả", "", "eye")
        self.preview = DetectionPreview()
        card.add(self.preview, 1)
        lay.addWidget(card, 1)

        stat_card = Card("Kết quả", "", "chart")
        self.leg_total = LegendItem(COLORS["accent"], "Ảnh đã xử lý", "0")
        self.leg_objects = LegendItem(COLORS["info"], "Đối tượng sinh ra", "0")
        self.leg_review = LegendItem(COLORS["warning"], "Ảnh cần xem lại", "0")
        self.leg_lowconf = LegendItem(COLORS["danger"], "Dự đoán độ tin cậy thấp", "0")
        self.leg_empty = LegendItem(COLORS["text_mute"], "Ảnh không có đối tượng", "0")
        for w in (self.leg_total, self.leg_objects, self.leg_review,
                  self.leg_lowconf, self.leg_empty):
            stat_card.add(w)
        stat_card.add(hline())
        self.review_btn = ghost_button("Mở trình sửa nhãn để xem lại", "pen")
        self.review_btn.clicked.connect(lambda: self.request_editor())
        stat_card.add(self.review_btn)
        lay.addWidget(stat_card)

        log_card = Card("Nhật ký", "", "file")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        log_card.add(self.log_view)
        lay.addWidget(log_card)
        return wrap

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
            self, "Chọn file trọng số", "",
            "Model (*.pt *.onnx *.engine *.torchscript);;Tất cả file (*)")
        if path:
            cfg.set("model.custom_weights", path)
            self.custom_label.setText(Path(path).name)
            self.custom_label.setToolTip(path)

    def _clear_weights(self) -> None:
        cfg.set("model.custom_weights", "")
        self.custom_label.setText("Không dùng")

    def _on_plugin_changed(self) -> None:
        key = self.plugin_combo.currentData()
        if not key:
            self.plugin_desc.setText("Chỉ dùng YOLO, không qua plugin.")
            self.plugin_status.setText("")
            self.plugin_prompt.setEnabled(False)
            return
        info = next((i for i in registry.infos() if i.key == key), None)
        if info is None:
            return
        self.plugin_desc.setText(info.description)
        self.plugin_prompt.setEnabled(info.accepts_prompt)
        ok, msg = registry.status(key)
        color = COLORS["success"] if ok else COLORS["warning"]
        self.plugin_status.setText(msg)
        self.plugin_status.setStyleSheet(f"font-size: 11.5px; color: {color};")

    def _on_image_selected(self, image_id: int) -> None:
        rec = self.repo.image(image_id) if self.repo else None
        if rec is None:
            return
        self.ctrl.set_current_image(image_id)
        anns = self.repo.annotations(image_id)
        dets = []
        for a in anns:
            from app.core.inference import Detection
            dets.append(Detection(
                class_id=a.class_id, class_name=a.class_name or "",
                confidence=a.confidence, bbox=list(a.bbox), polygon=list(a.polygon),
                shape=a.shape))
        self.preview.set_result(rec.path, dets)

    # ================================================================= MODEL ==
    def selected_weights(self) -> str:
        custom = cfg.get("model.custom_weights", "")
        if custom:
            return custom
        return self.weights_combo.currentData() or "yolo11n-seg.pt"

    def load_model(self) -> None:
        if self.ctrl.is_running("model"):
            return
        weights = self.selected_weights()
        task = self.task_combo.currentData()
        device = self.device_combo.currentData()
        cfg.update_section("model", {
            "task": task, "weights": self.weights_combo.currentData() or "",
            "device": device, "imgsz": self.imgsz_spin.value(),
        })
        cfg.save()

        self.model_status.setText("Đang nạp model …")
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['info']};")
        self.load_model_btn.setEnabled(False)

        worker = ModelLoadWorker(self.ctrl.engine, weights, task, device)
        self.ctrl.run_worker(
            "model", worker,
            on_log=self._append_log,
            on_done=self._on_model_loaded,
            on_fail=self._on_model_failed,
        )

    def _on_model_loaded(self, engine) -> None:
        self.load_model_btn.setEnabled(True)
        eng = self.ctrl.engine
        self.model_status.setText(eng.describe())
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        self.toast(f"Đã nạp model, chạy trên {device_label(eng.device)}.", "success")
        self.ctrl.modelChanged.emit()
        if getattr(self, "_pending_start", False):
            self._pending_start = False
            self.start()

    def _on_model_failed(self, msg: str) -> None:
        self.load_model_btn.setEnabled(True)
        self._pending_start = False
        self.model_status.setText("Nạp model thất bại")
        self.model_status.setStyleSheet(f"font-size: 11.5px; color: {COLORS['danger']};")

    # ================================================================== RUN ===
    def start(self) -> None:
        if not self.ctrl.has_project:
            self.toast("Hãy mở hoặc tạo project trước.", "warning")
            return
        if self.ctrl.is_running("autolabel"):
            self.toast("Đang gán nhãn, vui lòng đợi.", "warning")
            return
        if not self.ctrl.engine.loaded:
            self.toast("Đang nạp model trước khi chạy …", "info")
            self._pending_start = True
            self.load_model()
            return

        ids = self.image_list.selected_ids() or self.image_list.all_ids()
        if not ids:
            self.toast("Không có ảnh nào để gán nhãn.", "warning")
            return

        icfg = InferenceConfig(
            confidence=self.conf_slider.value(),
            iou=self.iou_slider.value(),
            max_det=self.maxdet_spin.value(),
            imgsz=self.imgsz_spin.value(),
            polygon_simplify=self.simplify_slider.value(),
            min_area_px=self.minarea_spin.value(),
            retina_masks=cfg.get("inference.retina_masks", True),
        )
        cfg.update_section("inference", {
            "confidence": icfg.confidence, "iou": icfg.iou, "max_det": icfg.max_det,
            "review_threshold": self.review_slider.value(),
            "polygon_simplify": icfg.polygon_simplify,
            "min_area_px": icfg.min_area_px,
            "overwrite_existing": self.overwrite_toggle.isChecked(),
        })
        cfg.save()

        self.log_view.clear()
        self.progress.start(f"Đang gán nhãn {len(ids):,} ảnh …")
        self.start_btn.setEnabled(False)

        worker = AutoLabelWorker(
            self.ctrl.repo, self.ctrl.engine, ids, icfg,
            review_threshold=self.review_slider.value(),
            low_conf_threshold=cfg.get("inference.low_conf_threshold", 0.35),
            overwrite=self.overwrite_toggle.isChecked(),
            plugin_key=self.plugin_combo.currentData() or "",
            plugin_prompt=self.plugin_prompt.text().strip(),
        )
        worker.preview.connect(self.preview.set_result)
        worker.image_done.connect(self._on_image_done)
        self.ctrl.run_worker(
            "autolabel", worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_log=self._append_log,
            on_done=self._on_done,
            on_fail=lambda _m: self.start_btn.setEnabled(True),
        )

    def _on_image_done(self, image_id: int, n_objects: int, max_conf: float) -> None:
        status = IMG_REVIEW if max_conf < self.review_slider.value() else "auto"
        self.image_list.update_item(image_id, status if n_objects else "unlabeled",
                                    n_objects)

    def _on_done(self, result) -> None:
        self.start_btn.setEnabled(True)
        self.progress.finish("Gán nhãn hoàn tất")
        if result is None:
            return
        self.leg_total.set_value(f"{result.n_images:,}")
        self.leg_objects.set_value(f"{result.n_objects:,}")
        self.leg_review.set_value(f"{result.n_review:,}")
        self.leg_lowconf.set_value(f"{result.n_low_conf:,}")
        self.leg_empty.set_value(f"{result.n_empty:,}")
        self.toast(
            f"Xong: {result.n_objects:,} đối tượng trên {result.n_images:,} ảnh "
            f"({result.fps:.1f} ảnh/giây).", "success")
        self.ctrl.notify_images_changed()
        self.ctrl.notify_classes_changed()
        self.refresh()

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum())

    # =============================================================== REFRESH ==
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
        self.image_list.set_images(self._images)
        self.count_label.setText(f"{len(self._images):,} ảnh")
        if self.ctrl.engine.loaded:
            self.model_status.setText(self.ctrl.engine.describe())
            self.model_status.setStyleSheet(
                f"font-size: 11.5px; color: {COLORS['success']};")
