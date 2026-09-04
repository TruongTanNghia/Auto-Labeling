"""Trang Settings: cau hinh chung, model, suy luan, annotation, plugin, phim tat."""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    CLASS_PALETTE,
    COLORS,
    EXPORT_FORMATS,
    LABEL_W_WIDE,
    YOLO_TASKS,
    get_shortcuts,
)
from app.core.inference import available_devices, device_info
from app.i18n import set_language, tr
from app.plugins.base import registry
from app.theme import icons
from app.utils.paths import log_dir, plugins_dir, user_data_dir, weights_dir
from app.views.pages.base_page import BasePage
from app.views.widgets.common import (
    Card,
    Field,
    KeyValueGrid,
    SliderField,
    ToggleSwitch,
    browse_button,
    combo,
    dspin,
    ghost_button,
    hline,
    label,
    primary_button,
    section_label,
    spin,
)


class SettingsPage(BasePage):
    TITLE = "Settings"
    SUBTITLE = "Tuỳ chỉnh ứng dụng theo quy trình làm việc của bạn"
    ICON = "settings"
    NEEDS_PROJECT = False

    def build(self) -> None:
        self.header.title_label.setText(tr("settings.title", "Settings"))
        if self.header.subtitle_label:
            self.header.subtitle_label.setText(
                tr("settings.subtitle", "Tuỳ chỉnh ứng dụng theo quy trình làm việc của bạn")
            )
        self.reset_btn = ghost_button(tr("settings.reset_btn", "Khôi phục mặc định"), "refresh")
        self.reset_btn.clicked.connect(self._reset)
        self.save_btn = primary_button(tr("settings.save_btn", "Lưu cài đặt"), "save")
        self.save_btn.clicked.connect(self.save_all)
        self.header.add_action(self.reset_btn)
        self.header.add_action(self.save_btn)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_tabs(), 0)
        row.addWidget(self._build_stack(), 1)
        self.add(row, 1)

    # --------------------------------------------------------------- tabs ---
    def _build_tabs(self) -> QWidget:
        wrap = QWidget()
        wrap.setFixedWidth(186)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(section_label(tr("settings.section_title", "Mục cài đặt")))

        self.tab_group = QButtonGroup(self)
        self.tab_buttons = {}
        for key, text, icon_name in (
            ("general", tr("settings.tab.general", "Chung"), "settings"),
            ("model", tr("settings.tab.model", "Model"), "cpu"),
            ("inference", tr("settings.tab.inference", "Suy luận"), "sliders"),
            ("annotation", tr("settings.tab.annotation", "Gán nhãn"), "pen"),
            ("plugins", tr("settings.tab.plugins", "Plugin"), "puzzle"),
            ("shortcuts", tr("settings.tab.shortcuts", "Phím tắt"), "keyboard"),
            ("about", tr("settings.tab.about", "Giới thiệu"), "info"),
        ):
            b = QPushButton("  " + text)
            b.setObjectName("SubTab")
            b.setCheckable(True)
            b.setChecked(key == "general")
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(icons.icon(icon_name, COLORS["text_dim"], 16))
            b.setIconSize(QSize(16, 16))
            b.clicked.connect(lambda _c=False, k=key: self._select(k))
            self.tab_group.addButton(b)
            self.tab_buttons[key] = b
            lay.addWidget(b)
        lay.addStretch(1)
        return wrap

    def _build_stack(self) -> QWidget:
        self.stack = QStackedWidget()
        self.pages = {
            "general": self._page_general(),
            "model": self._page_model(),
            "inference": self._page_inference(),
            "annotation": self._page_annotation(),
            "plugins": self._page_plugins(),
            "shortcuts": self._page_shortcuts(),
            "about": self._page_about(),
        }
        self._order = list(self.pages)
        for w in self.pages.values():
            self.stack.addWidget(w)
        return self.stack

    def _select(self, key: str) -> None:
        for k, b in self.tab_buttons.items():
            b.setChecked(k == key)
        self.stack.setCurrentIndex(self._order.index(key))
        if key == "plugins":
            self._refresh_plugins()

    def _scroll(self, inner: QWidget) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(inner)
        return area

    def _toggle_row(self, card: Card, text: str, toggle: ToggleSwitch, hint: str = "") -> None:
        r = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(text, size=12.5, color=COLORS["text"]))
        if hint:
            col.addWidget(label(hint, size=11, color=COLORS["text_mute"]))
        r.addLayout(col)
        r.addStretch(1)
        r.addWidget(toggle)
        card.add(r)

    # =============================================================== GENERAL ==
    def _page_general(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(tr("settings.general.interface", "Giao diện"), "", "sparkle")
        cur_lang = cfg.get("general.language", "vi")
        if cur_lang not in ("vi", "en"):
            cur_lang = "vi"
        self.lang_combo = combo([("vi", "Tiếng Việt"), ("en", "English")], current=cur_lang)
        self.lang_combo.setEnabled(True)
        card.add(
            Field(
                tr("settings.general.language", "Ngôn ngữ"),
                self.lang_combo,
                label_width=LABEL_W_WIDE,
            )
        )
        cur_theme = cfg.get("general.theme", "Dark")
        self.theme_combo = combo(
            [
                ("Dark", tr("settings.general.theme_dark", "Tối")),
                ("Light", tr("settings.general.theme_light", "Sáng")),
                ("System", tr("settings.general.theme_system", "Theo hệ thống")),
            ],
            current=cur_theme,
        )
        card.add(
            Field(
                tr("settings.general.theme", "Chủ đề"), self.theme_combo, label_width=LABEL_W_WIDE
            )
        )

        accent_row = QWidget()
        ar = QHBoxLayout(accent_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.setSpacing(7)
        self._accent = cfg.get("general.accent", COLORS["accent"])
        self.accent_buttons = []
        for color in CLASS_PALETTE[:8]:
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(color)
            b.setStyleSheet(
                f"background: {color}; border-radius: 8px;"
                f"border: 2px solid {'#FFFFFF' if color == self._accent else 'transparent'};"
            )
            b.clicked.connect(lambda _c=False, col=color: self._set_accent(col))
            self.accent_buttons.append((b, color))
            ar.addWidget(b)
        custom = ghost_button(tr("settings.general.other_color", "Màu khác…"))
        custom.clicked.connect(self._pick_accent)
        ar.addWidget(custom)
        ar.addStretch(1)
        card.add(
            Field(
                tr("settings.general.accent_color", "Màu nhấn"),
                accent_row,
                label_width=LABEL_W_WIDE,
            )
        )
        card.add(
            label(
                tr(
                    "settings.general.accent_hint",
                    "Đổi màu sẽ áp dụng sau khi khởi động lại ứng dụng.",
                ),
                size=11,
                color=COLORS["text_mute"],
            )
        )
        lay.addWidget(card)

        proj_card = Card(tr("settings.general.project", "Project"), "", "folder")
        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self.projects_edit = QLineEdit(cfg.get("general.projects_dir", ""))
        pick = browse_button()
        pick.clicked.connect(self._pick_projects_dir)
        fr.addWidget(self.projects_edit, 1)
        fr.addWidget(pick)
        proj_card.add(
            Field(
                tr("settings.general.project_dir", "Thư mục project"),
                folder_row,
                label_width=LABEL_W_WIDE,
            )
        )

        self.autosave_spin = spin(
            cfg.get("general.autosave_minutes", 5),
            0,
            120,
            suffix=" " + tr("settings.general.autosave_unit", "phút"),
            width=126,
        )
        self.autosave_spin.setSpecialValueText(tr("settings.general.autosave_off", "Tắt"))
        proj_card.add(
            Field(
                tr("settings.general.autosave", "Tự động lưu mỗi"),
                self.autosave_spin,
                label_width=LABEL_W_WIDE,
            )
        )

        self.export_combo = combo(
            [(k, t) for k, t, _h in EXPORT_FORMATS],
            current=cfg.get("general.default_export_format", "yolo_seg"),
        )
        proj_card.add(
            Field(
                tr("settings.general.default_export", "Định dạng xuất mặc định"),
                self.export_combo,
                label_width=LABEL_W_WIDE,
            )
        )

        self.confirm_toggle = ToggleSwitch(cfg.get("general.confirm_on_exit", True))
        self._toggle_row(
            proj_card,
            tr("settings.general.confirm_exit", "Hỏi trước khi thoát"),
            self.confirm_toggle,
        )
        self.reopen_toggle = ToggleSwitch(cfg.get("general.reopen_last_project", True))
        self._toggle_row(
            proj_card,
            tr("settings.general.reopen_last", "Mở lại project gần nhất khi khởi động"),
            self.reopen_toggle,
            tr(
                "settings.general.reopen_last_hint",
                "Tắt nếu bạn muốn luôn bắt đầu từ màn hình trống",
            ),
        )
        lay.addWidget(proj_card)

        path_card = Card(tr("settings.general.system_paths", "Đường dẫn hệ thống"), "", "file")
        path_card.add(
            KeyValueGrid(
                [
                    (
                        tr("settings.general.config_and_data", "Cấu hình và dữ liệu"),
                        str(user_data_dir()),
                    ),
                    (tr("settings.general.log_dir", "Nhật ký"), str(log_dir())),
                    (tr("settings.general.weights_dir", "Trọng số tải về"), str(weights_dir())),
                    (tr("settings.general.user_plugins", "Plugin người dùng"), str(plugins_dir())),
                ],
                value_bold=False,
            )
        )
        row = QHBoxLayout()
        row.setSpacing(8)
        for text, path in (
            (tr("settings.general.open_data_folder", "Mở thư mục dữ liệu"), user_data_dir()),
            (tr("settings.general.open_log_folder", "Mở thư mục nhật ký"), log_dir()),
            (tr("settings.general.open_weights_folder", "Mở thư mục trọng số"), weights_dir()),
        ):
            b = ghost_button(text, "folder_open")
            b.clicked.connect(lambda _c=False, p=path: _open_folder(p))
            row.addWidget(b)
        row.addStretch(1)
        path_card.add(row)
        lay.addWidget(path_card)
        lay.addStretch(1)
        return self._scroll(w)

    def _set_accent(self, color: str) -> None:
        self._accent = color
        for b, c in self.accent_buttons:
            b.setStyleSheet(
                f"background: {c}; border-radius: 8px;"
                f"border: 2px solid {'#FFFFFF' if c == color else 'transparent'};"
            )

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._accent), self, tr("settings.general.pick_accent", "Chọn màu nhấn")
        )
        if color.isValid():
            self._set_accent(color.name())

    def _pick_projects_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self,
            tr("settings.general.choose_project_dir", "Chọn thư mục lưu project"),
            self.projects_edit.text(),
        )
        if d:
            self.projects_edit.setText(d)

    # ================================================================= MODEL ==
    def _page_model(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(
            tr("settings.model.default_model", "Model mặc định"),
            tr("settings.model.default_model_hint", "Dùng khi mở trang Auto Label"),
            "cpu",
        )
        self.m_task = combo(
            [(t, t.capitalize()) for t in YOLO_TASKS], current=cfg.get("model.task", "segment")
        )
        card.add(
            Field(tr("settings.model.task", "Nhiệm vụ"), self.m_task, label_width=LABEL_W_WIDE)
        )

        # Presets YOLO
        yolo_presets = [
            ("yolo11n-seg.pt", "YOLO11 Nano — Siêu nhanh (6 MB)"),
            ("yolo11s-seg.pt", "YOLO11 Small — Cân bằng (22 MB)"),
            ("yolo11m-seg.pt", "YOLO11 Medium — Độ chính xác cao (50 MB)"),
            ("yolo11l-seg.pt", "YOLO11 Large — Mạnh mẽ (85 MB)"),
            ("yolo11x-seg.pt", "YOLO11 Extra Large — Tốt nhất (120 MB)"),
            ("yolov8n-seg.pt", "YOLOv8 Nano — Ổn định (7 MB)"),
            ("yolov8x-seg.pt", "YOLOv8 Extra Large (140 MB)"),
        ]
        cur_w = cfg.get("model.weights", "yolo11m-seg.pt")
        self.m_preset_combo = combo(
            yolo_presets,
            current=cur_w if any(w == cur_w for w, _ in yolo_presets) else "yolo11m-seg.pt",
        )
        self.m_preset_combo.currentIndexChanged.connect(self._on_yolo_preset_changed)
        card.add(
            Field(
                tr("settings.model.preset_select", "Chọn mô hình YOLO sẵn có"),
                self.m_preset_combo,
                label_width=LABEL_W_WIDE,
            )
        )

        self.m_weights = QLineEdit(cfg.get("model.weights", "yolo11m-seg.pt"))
        card.add(
            Field(
                tr("settings.model.weights", "Tên tệp trọng số"),
                self.m_weights,
                label_width=LABEL_W_WIDE,
            )
        )

        custom_row = QWidget()
        cr = QHBoxLayout(custom_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        self.m_custom = QLineEdit(cfg.get("model.custom_weights", ""))
        self.m_custom.setPlaceholderText(".pt / .onnx / .engine")
        pick = browse_button()
        pick.clicked.connect(self._pick_weights)
        cr.addWidget(self.m_custom, 1)
        cr.addWidget(pick)
        card.add(
            Field(
                tr("settings.model.custom_model", "Model riêng"),
                custom_row,
                label_width=LABEL_W_WIDE,
            )
        )

        self.m_device = combo(available_devices(), current=cfg.get("model.device", "auto"))
        card.add(
            Field(tr("settings.model.device", "Thiết bị"), self.m_device, label_width=LABEL_W_WIDE)
        )
        self.m_imgsz = spin(cfg.get("model.imgsz", 640), 128, 4096, 32, width=118)
        card.add(
            Field(
                tr("settings.model.imgsz", "Cỡ ảnh vào model"),
                self.m_imgsz,
                label_width=LABEL_W_WIDE,
            )
        )
        self.m_half = ToggleSwitch(cfg.get("model.half", False))
        self._toggle_row(
            card,
            tr("settings.model.half", "Dùng FP16 (nửa độ chính xác)"),
            self.m_half,
            tr("settings.model.half_hint", "Nhanh hơn trên GPU có tensor core"),
        )
        lay.addWidget(card)

        gpu_card = Card(tr("settings.model.current_device", "Thiết bị hiện tại"), "", "bolt")
        d = device_info()
        gpu_card.add(
            KeyValueGrid(
                [
                    (
                        tr("settings.model.cuda_avail", "CUDA khả dụng"),
                        "Có" if d["cuda"] else "Không",
                    ),
                    (tr("settings.model.device_name", "Tên thiết bị"), d["name"]),
                    (tr("settings.model.gpu_count", "Số GPU"), str(d["count"])),
                    (
                        tr("settings.model.vram", "VRAM"),
                        f"{d['total_gb']:.1f} GB" if d["total_gb"] else "-",
                    ),
                    (tr("settings.model.torch_ver", "Phiên bản torch"), d["torch"] or "chưa cài"),
                    (tr("settings.model.cuda_ver", "Phiên bản CUDA"), d["cuda_version"] or "—"),
                ]
            )
        )
        lay.addWidget(gpu_card)
        lay.addStretch(1)
        return self._scroll(w)

    def _on_yolo_preset_changed(self, idx: int) -> None:
        val = self.m_preset_combo.currentData()
        if val:
            self.m_weights.setText(val)

    def _pick_weights(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.model.choose_weights_title", "Chọn trọng số"),
            str(weights_dir()),
            tr("settings.model.weights_filter", "Model (*.pt *.onnx *.engine);;Tất cả file (*)"),
        )
        if path:
            self.m_custom.setText(path)

    # ============================================================= INFERENCE ==
    def _page_inference(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(tr("settings.inference.thresholds", "Ngưỡng suy luận"), "", "sliders")
        self.i_conf = SliderField(cfg.get("inference.confidence", 0.45), 0.01, 0.99, 2)
        card.add(
            Field(
                tr("settings.inference.conf", "Độ tin cậy"), self.i_conf, label_width=LABEL_W_WIDE
            )
        )
        self.i_iou = SliderField(cfg.get("inference.iou", 0.5), 0.05, 0.95, 2)
        card.add(
            Field(
                tr("settings.inference.iou", "IOU (khử trùng)"),
                self.i_iou,
                label_width=LABEL_W_WIDE,
            )
        )
        self.i_review = SliderField(cfg.get("inference.review_threshold", 0.6), 0.05, 0.99, 2)
        card.add(
            Field(
                tr("settings.inference.review_thresh", "Ngưỡng cần xem lại"),
                self.i_review,
                label_width=LABEL_W_WIDE,
            )
        )
        self.i_low = SliderField(cfg.get("inference.low_conf_threshold", 0.35), 0.01, 0.9, 2)
        card.add(
            Field(
                tr("settings.inference.low_conf_thresh", "Ngưỡng tin cậy thấp"),
                self.i_low,
                label_width=LABEL_W_WIDE,
            )
        )
        self.i_maxdet = spin(cfg.get("inference.max_det", 1000), 1, 30000, 50, width=118)
        card.add(
            Field(
                tr("settings.inference.max_det", "Số đối tượng tối đa"),
                self.i_maxdet,
                label_width=LABEL_W_WIDE,
            )
        )
        lay.addWidget(card)

        poly_card = Card(tr("settings.inference.postproc", "Hậu xử lý"), "", "polygon")
        self.i_simplify = SliderField(
            cfg.get("inference.polygon_simplify", 0.0025), 0.0, 0.02, 4, 0.0005
        )
        poly_card.add(
            Field(
                tr("settings.inference.simplify", "Giản lược polygon"),
                self.i_simplify,
                label_width=LABEL_W_WIDE,
            )
        )
        self.i_minarea = spin(
            cfg.get("inference.min_area_px", 24), 0, 100000, 4, suffix=" px", width=118
        )
        poly_card.add(
            Field(
                tr("settings.inference.min_area", "Diện tích tối thiểu"),
                self.i_minarea,
                label_width=LABEL_W_WIDE,
            )
        )
        self.i_retina = ToggleSwitch(cfg.get("inference.retina_masks", True))
        self._toggle_row(
            poly_card,
            tr("settings.inference.retina", "Mask độ phân giải cao"),
            self.i_retina,
            tr("settings.inference.retina_hint", "Mask sắc nét hơn, chậm hơn một chút"),
        )
        self.i_agnostic = ToggleSwitch(cfg.get("inference.agnostic_nms", False))
        self._toggle_row(
            poly_card,
            tr("settings.inference.agnostic", "Khử trùng không phân biệt lớp"),
            self.i_agnostic,
        )
        self.i_overwrite = ToggleSwitch(cfg.get("inference.overwrite_existing", True))
        self._toggle_row(
            poly_card,
            tr("settings.inference.overwrite", "Ghi đè nhãn đã có khi gán nhãn tự động"),
            self.i_overwrite,
        )
        lay.addWidget(poly_card)
        lay.addStretch(1)
        return self._scroll(w)

    # ============================================================ ANNOTATION ==
    def _page_annotation(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(tr("settings.annotation.display", "Hiển thị trên vùng vẽ"), "", "eye")
        self.a_conf = ToggleSwitch(cfg.get("annotation.show_confidence", True))
        self._toggle_row(card, tr("settings.annotation.show_conf", "Hiện độ tin cậy"), self.a_conf)
        self.a_color = ToggleSwitch(cfg.get("annotation.show_class_color", True))
        self._toggle_row(
            card, tr("settings.annotation.show_color", "Tô màu theo lớp"), self.a_color
        )
        self.a_labels = ToggleSwitch(cfg.get("annotation.show_labels", True))
        self._toggle_row(card, tr("settings.annotation.show_labels", "Hiện tên lớp"), self.a_labels)
        self.a_select = ToggleSwitch(cfg.get("annotation.auto_select_new", True))
        self._toggle_row(
            card, tr("settings.annotation.auto_select", "Tự chọn đối tượng vừa tạo"), self.a_select
        )
        lay.addWidget(card)

        tool_card = Card(tr("settings.annotation.tools", "Công cụ"), "", "brush")
        self.a_brush = spin(
            cfg.get("annotation.brush_size", 20), 2, 300, 2, suffix=" px", width=118
        )
        tool_card.add(
            Field(
                tr("settings.annotation.brush_size", "Cỡ cọ vẽ"),
                self.a_brush,
                label_width=LABEL_W_WIDE,
            )
        )
        self.a_opacity = SliderField(cfg.get("annotation.fill_opacity", 0.35), 0.0, 0.9, 2)
        tool_card.add(
            Field(
                tr("settings.annotation.fill_opacity", "Độ đậm vùng tô"),
                self.a_opacity,
                label_width=LABEL_W_WIDE,
            )
        )
        self.a_line = dspin(cfg.get("annotation.line_width", 2), 0.5, 8, 0.5, 1, width=118)
        tool_card.add(
            Field(
                tr("settings.annotation.line_width", "Độ dày đường viền"),
                self.a_line,
                label_width=LABEL_W_WIDE,
            )
        )
        self.a_vertex = dspin(cfg.get("annotation.vertex_size", 6), 2, 16, 1, 1, width=118)
        tool_card.add(
            Field(
                tr("settings.annotation.vertex_size", "Cỡ điểm đỉnh"),
                self.a_vertex,
                label_width=LABEL_W_WIDE,
            )
        )
        lay.addWidget(tool_card)
        lay.addStretch(1)
        return self._scroll(w)

    # =============================================================== PLUGINS ==
    def _page_plugins(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(
            tr("settings.plugins.title", "Plugin gán nhãn tự động"),
            tr(
                "settings.plugins.subtitle", "Mở rộng chất lượng gán nhãn bằng các mô hình nền tảng"
            ),
            "puzzle",
        )
        self.plugin_table = QTableWidget(0, 4)
        self.plugin_table.setHorizontalHeaderLabels(
            [
                tr("settings.plugins.col_name", "Plugin"),
                tr("settings.plugins.col_kind", "Loại"),
                tr("settings.plugins.col_status", "Trạng thái"),
                tr("settings.plugins.col_req", "Yêu cầu"),
            ]
        )
        self.plugin_table.verticalHeader().setVisible(False)
        self.plugin_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.plugin_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.plugin_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4):
            self.plugin_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeToContents
            )
        self.plugin_table.setMinimumHeight(190)
        self.plugin_table.currentCellChanged.connect(lambda r, *_: self._show_plugin_detail(r))
        card.add(self.plugin_table)

        row = QHBoxLayout()
        row.setSpacing(8)
        reload_btn = ghost_button(tr("settings.plugins.reload", "Quét lại plugin"), "refresh")
        reload_btn.clicked.connect(lambda: (registry.discover(force=True), self._refresh_plugins()))
        folder_btn = ghost_button(
            tr("settings.plugins.open_dir", "Mở thư mục plugin"), "folder_open"
        )
        folder_btn.clicked.connect(lambda: _open_folder(plugins_dir()))
        row.addWidget(reload_btn)
        row.addWidget(folder_btn)
        row.addStretch(1)
        card.add(row)
        lay.addWidget(card)

        self.plugin_detail_card = Card(tr("settings.plugins.detail", "Chi tiết plugin"), "", "")
        self.plugin_detail = label(
            tr("settings.plugins.detail_placeholder", "Chọn một plugin để xem chi tiết."),
            size=12,
            color=COLORS["text_dim"],
            wrap=True,
        )
        self.plugin_detail_card.add(self.plugin_detail)
        self.plugin_install = label("", size=11.5, color=COLORS["text_mute"], wrap=True)
        self.plugin_detail_card.add(self.plugin_install)
        lay.addWidget(self.plugin_detail_card)

        self.plugin_config_card = Card(
            tr("settings.plugins.config_title", "Cấu hình tham số plugin"), "", ""
        )
        self.plugin_config_wrap = QWidget()
        self.plugin_config_layout = QVBoxLayout(self.plugin_config_wrap)
        self.plugin_config_layout.setContentsMargins(0, 0, 0, 0)
        self.plugin_config_layout.setSpacing(10)
        self.plugin_config_card.add(self.plugin_config_wrap)

        self.plugin_reset_btn = ghost_button(
            tr("settings.plugins.reset_plugin", "Khôi phục mặc định plugin"), "refresh"
        )
        self.plugin_reset_btn.clicked.connect(self._reset_current_plugin)
        self.plugin_config_card.add(self.plugin_reset_btn)
        lay.addWidget(self.plugin_config_card)

        guide = Card(tr("settings.plugins.guide_title", "Tự viết plugin"), "", "")
        guide.add(
            label(
                tr(
                    "settings.plugins.guide_text",
                    "Tạo file .py trong thư mục plugin với một lớp kế thừa AnnotatorPlugin, "
                    "khai báo info = PluginInfo(...) và cài đặt phương thức annotate(ctx) "
                    "trả về danh sách Detection. Ứng dụng sẽ tự nạp khi khởi động.",
                ),
                size=12,
                color=COLORS["text_mute"],
                wrap=True,
            )
        )
        lay.addWidget(guide)
        lay.addStretch(1)
        return self._scroll(w)

    def _refresh_plugins(self) -> None:
        infos = registry.infos()
        self.plugin_table.setRowCount(len(infos))
        self._plugin_infos = infos
        for r, info in enumerate(infos):
            ok, msg = registry.status(info.key)
            self.plugin_table.setItem(r, 0, QTableWidgetItem("  " + info.name))
            self.plugin_table.setItem(
                r,
                1,
                QTableWidgetItem(
                    tr("settings.plugins.generate", "Sinh mới")
                    if info.kind == "generate"
                    else tr("settings.plugins.refine", "Tinh chỉnh")
                ),
            )
            status_item = QTableWidgetItem(msg)
            status_item.setForeground(QColor(COLORS["success"] if ok else COLORS["warning"]))
            self.plugin_table.setItem(r, 2, status_item)
            self.plugin_table.setItem(r, 3, QTableWidgetItem(", ".join(info.requires)))

    def _save_current_plugin_form(self) -> None:
        if not hasattr(self, "_selected_plugin_key") or not self._selected_plugin_key:
            return
        if not hasattr(self, "_plugin_form_controls") or not self._plugin_form_controls:
            return
        plugin_key = self._selected_plugin_key
        plugin_cfg = {}
        for p_key, (param, widget) in self._plugin_form_controls.items():
            if param.type == "int":
                plugin_cfg[p_key] = widget.value()
            elif param.type == "float":
                plugin_cfg[p_key] = widget.value()
            elif param.type == "bool":
                plugin_cfg[p_key] = widget.isChecked()
            elif param.type == "choice":
                plugin_cfg[p_key] = (
                    widget.currentData()
                    if widget.currentData() is not None
                    else widget.currentText()
                )
            elif param.type == "str":
                plugin_cfg[p_key] = widget.text().strip()
        cfg.set(f"plugins.config.{plugin_key}", plugin_cfg)
        plugin_inst = registry.get(plugin_key)
        if plugin_inst:
            eff = dict(plugin_inst.default_config())
            eff.update(plugin_cfg)
            plugin_inst.configure(eff)

    def _show_plugin_detail(self, row: int) -> None:
        self._save_current_plugin_form()

        infos = getattr(self, "_plugin_infos", [])
        if not (0 <= row < len(infos)):
            return
        info = infos[row]
        self._selected_plugin_key = info.key

        ok, msg = registry.status(info.key)
        self.plugin_detail.setText(
            f"{info.name} v{info.version}\n\n{info.description}\n\n"
            f"Trang chủ: {info.homepage or '—'}"
        )
        if ok:
            self.plugin_install.setText("Plugin đã sẵn sàng sử dụng.")
            self.plugin_install.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        else:
            self.plugin_install.setText(
                f"{msg}. Cài đặt bằng lệnh: pip install " + " ".join(info.requires)
            )
            self.plugin_install.setStyleSheet(f"font-size: 11.5px; color: {COLORS['warning']};")

        while self.plugin_config_layout.count():
            item = self.plugin_config_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._plugin_form_controls = {}
        plugin_inst = registry.get(info.key)
        schema = plugin_inst.config_schema() if plugin_inst else []

        if not schema:
            no_param_lbl = label(
                tr("settings.plugins.no_params", "Plugin này không có tham số cấu hình."),
                size=12,
                color=COLORS["text_dim"],
            )
            self.plugin_config_layout.addWidget(no_param_lbl)
            self.plugin_reset_btn.setVisible(False)
            return

        self.plugin_reset_btn.setVisible(True)
        user_cfg = cfg.get(f"plugins.config.{info.key}", {})

        for param in schema:
            cur_val = (
                user_cfg.get(param.key, plugin_inst.config(param.key, param.default))
                if plugin_inst
                else param.default
            )

            if param.type == "int":
                min_v = int(param.min_value) if param.min_value is not None else 0
                max_v = int(param.max_value) if param.max_value is not None else 999999
                widget = spin(int(cur_val), min_v, max_v, width=140)
            elif param.type == "float":
                min_v = float(param.min_value) if param.min_value is not None else 0.0
                max_v = float(param.max_value) if param.max_value is not None else 999999.0
                step = 0.001 if param.default < 0.01 else (0.01 if param.default < 1.0 else 0.1)
                decimals = 4 if param.default < 0.01 else 2
                widget = dspin(
                    float(cur_val), min_v, max_v, step=step, decimals=decimals, width=140
                )
            elif param.type == "bool":
                widget = ToggleSwitch(bool(cur_val))
            elif param.type == "choice":
                opts = param.options
                items = [(o, o) for o in opts] if isinstance(opts, list) else []
                widget = combo(items if items else opts, current=str(cur_val))
            else:
                widget = QLineEdit(str(cur_val))

            self._plugin_form_controls[param.key] = (param, widget)
            f_field = Field(param.label, widget, label_width=LABEL_W_WIDE)
            self.plugin_config_layout.addWidget(f_field)
            if param.description:
                desc_lbl = label(param.description, size=11, color=COLORS["text_mute"])
                desc_lbl.setContentsMargins(LABEL_W_WIDE + 12, 0, 0, 0)
                self.plugin_config_layout.addWidget(desc_lbl)

    def _reset_current_plugin(self) -> None:
        if not hasattr(self, "_selected_plugin_key") or not self._selected_plugin_key:
            return
        plugin_key = self._selected_plugin_key
        plugin_inst = registry.get(plugin_key)
        if plugin_inst is None:
            return
        msg = tr(
            "settings.plugins.reset_plugin_confirm",
            "Khôi phục plugin {plugin} về mặc định?",
            plugin=plugin_inst.info.name,
        )
        if (
            QMessageBox.question(
                self, tr("settings.plugins.reset_plugin", "Khôi phục mặc định plugin"), msg
            )
            != QMessageBox.Yes
        ):
            return
        cfg.set(f"plugins.config.{plugin_key}", {})
        cfg.save()
        plugin_inst.configure(plugin_inst.default_config())

        row = self.plugin_table.currentRow()
        if row >= 0:
            self._show_plugin_detail(row)
        self.toast(
            tr("settings.plugins.reset_done", "Đã khôi phục cài đặt mặc định cho plugin."), "info"
        )

    # ============================================================= SHORTCUTS ==
    def _page_shortcuts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card(
            tr("settings.shortcuts.title", "Phím tắt"),
            tr("settings.shortcuts.subtitle", "Thao tác nhanh như CVAT hoặc Roboflow"),
            "keyboard",
        )
        shortcuts_list = get_shortcuts()
        table = QTableWidget(len(shortcuts_list), 3)
        table.setHorizontalHeaderLabels(
            [
                tr("settings.shortcuts.col_group", "Nhóm"),
                tr("settings.shortcuts.col_keys", "Phím"),
                tr("settings.shortcuts.col_func", "Chức năng"),
            ]
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for r, (group, keys, desc) in enumerate(shortcuts_list):
            table.setItem(r, 0, QTableWidgetItem("  " + group))
            key_item = QTableWidgetItem("  " + keys)
            key_item.setForeground(QColor(COLORS["accent_hi"]))
            table.setItem(r, 1, key_item)
            table.setItem(r, 2, QTableWidgetItem("  " + desc))
        table.setMinimumHeight(460)
        card.add(table)
        lay.addWidget(card, 1)
        return self._scroll(w)

    # ================================================================= ABOUT ==
    def _page_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("", "", "")
        head = QHBoxLayout()
        head.setSpacing(14)
        from PySide6.QtWidgets import QLabel

        logo = QLabel()
        logo.setPixmap(icons.pixmap("logo", COLORS["accent_hi"], 56, stroke=1.5))
        logo.setFixedSize(60, 60)
        head.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(APP_NAME, bold=True, size=20))
        col.addWidget(label(APP_TAGLINE, size=12.5, color=COLORS["text_dim"]))
        col.addWidget(
            label(
                tr("settings.about.version", "Phiên bản {version}", version=APP_VERSION),
                size=11.5,
                color=COLORS["text_mute"],
            )
        )
        head.addLayout(col)
        head.addStretch(1)
        card.add(head)
        card.add(hline())
        card.add(
            label(
                tr(
                    "settings.about.description",
                    "AutoLabel Studio AI biến video thành dataset Computer Vision hoàn chỉnh: "
                    "cắt frame thông minh, lọc ảnh trùng và ảnh kém chất lượng, tự động gán "
                    "nhãn bằng YOLO, tinh chỉnh bằng công cụ polygon và cọ vẽ chuyên nghiệp, "
                    "thống kê dataset rồi huấn luyện lại model — tất cả trong một ứng dụng.",
                ),
                size=12.5,
                color=COLORS["text_dim"],
                wrap=True,
            )
        )
        lay.addWidget(card)

        tech = Card(tr("settings.about.tech_title", "Công nghệ sử dụng"), "", "layers")
        tech.add(
            KeyValueGrid(
                [
                    (tr("settings.about.tech_gui", "Giao diện"), "PySide6 (Qt 6) — Fluent Dark"),
                    (
                        tr("settings.about.tech_infer", "Suy luận"),
                        "Ultralytics YOLOv8 / YOLO11 / YOLO12",
                    ),
                    (tr("settings.about.tech_img", "Xử lý ảnh"), "OpenCV, scikit-image, NumPy"),
                    (tr("settings.about.tech_geo", "Hình học"), "Shapely — gộp, cắt, cọ vẽ"),
                    (tr("settings.about.tech_store", "Lưu trữ"), "SQLite (WAL), tự lưu và sao lưu"),
                    (
                        tr("settings.about.tech_arch", "Kiến trúc"),
                        "MVC, worker QThread, hệ thống plugin",
                    ),
                ],
                value_bold=False,
            )
        )
        lay.addWidget(tech)

        credit = Card(tr("settings.about.credit_title", "Ghi chú"), "", "info")
        credit.add(
            label(
                tr(
                    "settings.about.credit_text",
                    "Các mô hình YOLO của Ultralytics phát hành theo giấy phép AGPL-3.0. "
                    "Hãy kiểm tra điều khoản trước khi dùng cho mục đích thương mại.",
                ),
                size=12,
                color=COLORS["text_mute"],
                wrap=True,
            )
        )
        lay.addWidget(credit)
        lay.addStretch(1)
        return self._scroll(w)

    # ================================================================== SAVE ==
    def save_all(self) -> None:
        self._save_current_plugin_form()
        new_lang = self.lang_combo.currentData()
        new_theme = self.theme_combo.currentData()
        cfg.update_section(
            "general",
            {
                "language": new_lang,
                "theme": new_theme,
                "accent": self._accent,
                "projects_dir": self.projects_edit.text().strip(),
                "autosave_minutes": self.autosave_spin.value(),
                "default_export_format": self.export_combo.currentData(),
                "confirm_on_exit": self.confirm_toggle.isChecked(),
                "reopen_last_project": self.reopen_toggle.isChecked(),
            },
        )
        set_language(new_lang)
        from app.theme.style import apply_theme

        apply_theme(None, new_theme, self._accent)

        cfg.update_section(
            "model",
            {
                "task": self.m_task.currentData(),
                "weights": self.m_weights.text().strip(),
                "custom_weights": self.m_custom.text().strip(),
                "device": self.m_device.currentData(),
                "imgsz": self.m_imgsz.value(),
                "half": self.m_half.isChecked(),
            },
        )

        cfg.update_section(
            "inference",
            {
                "confidence": self.i_conf.value(),
                "iou": self.i_iou.value(),
                "review_threshold": self.i_review.value(),
                "low_conf_threshold": self.i_low.value(),
                "max_det": self.i_maxdet.value(),
                "polygon_simplify": self.i_simplify.value(),
                "min_area_px": self.i_minarea.value(),
                "retina_masks": self.i_retina.isChecked(),
                "agnostic_nms": self.i_agnostic.isChecked(),
                "overwrite_existing": self.i_overwrite.isChecked(),
            },
        )
        cfg.update_section(
            "annotation",
            {
                "show_confidence": self.a_conf.isChecked(),
                "show_class_color": self.a_color.isChecked(),
                "show_labels": self.a_labels.isChecked(),
                "auto_select_new": self.a_select.isChecked(),
                "brush_size": self.a_brush.value(),
                "fill_opacity": self.a_opacity.value(),
                "line_width": self.a_line.value(),
                "vertex_size": self.a_vertex.value(),
            },
        )
        cfg.save()
        self.ctrl.refresh_settings()
        self.toast(tr("settings.saved_toast"), "success")

    def _load_from_cfg(self) -> None:
        # General
        g = cfg.get_section("general")
        lang = g.get("language", "vi")
        idx = self.lang_combo.findData(lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        theme = g.get("theme", "Dark")
        idx = self.theme_combo.findData(theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        self._set_accent(g.get("accent", COLORS["accent"]))
        self.projects_edit.setText(g.get("projects_dir", ""))
        self.autosave_spin.setValue(int(g.get("autosave_minutes", 5)))

        exp_fmt = g.get("default_export_format", "yolo_seg")
        idx = self.export_combo.findData(exp_fmt)
        if idx >= 0:
            self.export_combo.setCurrentIndex(idx)

        self.confirm_toggle.setChecked(bool(g.get("confirm_on_exit", True)))
        self.reopen_toggle.setChecked(bool(g.get("reopen_last_project", True)))

        # Model
        m = cfg.get_section("model")
        task = m.get("task", "segment")
        idx = self.m_task.findData(task)
        if idx >= 0:
            self.m_task.setCurrentIndex(idx)
        w_val = m.get("weights", "yolo11m-seg.pt")
        self.m_weights.setText(w_val)
        idx = self.m_preset_combo.findData(w_val)
        if idx >= 0:
            self.m_preset_combo.setCurrentIndex(idx)
        self.m_custom.setText(m.get("custom_weights", ""))
        dev = m.get("device", "auto")
        idx = self.m_device.findData(dev)
        if idx >= 0:
            self.m_device.setCurrentIndex(idx)
        self.m_imgsz.setValue(int(m.get("imgsz", 640)))
        self.m_half.setChecked(bool(m.get("half", False)))

        # Inference
        inf = cfg.get_section("inference")
        self.i_conf.setValue(float(inf.get("confidence", 0.45)))
        self.i_iou.setValue(float(inf.get("iou", 0.50)))
        self.i_review.setValue(float(inf.get("review_threshold", 0.60)))
        self.i_low.setValue(float(inf.get("low_conf_threshold", 0.35)))
        self.i_maxdet.setValue(int(inf.get("max_det", 1000)))
        self.i_simplify.setValue(float(inf.get("polygon_simplify", 0.0025)))
        self.i_minarea.setValue(int(inf.get("min_area_px", 24)))
        self.i_retina.setChecked(bool(inf.get("retina_masks", True)))
        self.i_agnostic.setChecked(bool(inf.get("agnostic_nms", False)))
        self.i_overwrite.setChecked(bool(inf.get("overwrite_existing", True)))

        # Annotation
        ann = cfg.get_section("annotation")
        self.a_conf.setChecked(bool(ann.get("show_confidence", True)))
        self.a_color.setChecked(bool(ann.get("show_class_color", True)))
        self.a_labels.setChecked(bool(ann.get("show_labels", True)))
        self.a_select.setChecked(bool(ann.get("auto_select_new", True)))
        self.a_brush.setValue(int(ann.get("brush_size", 20)))
        self.a_opacity.setValue(float(ann.get("fill_opacity", 0.35)))
        self.a_line.setValue(int(ann.get("line_width", 2)))
        self.a_vertex.setValue(int(ann.get("vertex_size", 6)))

        # Plugins
        self._refresh_plugins()

    def _reset(self) -> None:
        if (
            QMessageBox.question(
                self,
                tr("settings.reset_confirm_title", "Khôi phục mặc định"),
                tr("settings.reset_confirm_msg", "Đưa toàn bộ cài đặt về giá trị mặc định?"),
            )
            != QMessageBox.Yes
        ):
            return
        cfg.reset()
        self._load_from_cfg()

        from app.i18n import set_language
        from app.theme.style import apply_theme

        new_lang = cfg.get("general.language", "vi")
        new_theme = cfg.get("general.theme", "Dark")
        new_accent = cfg.get("general.accent", COLORS["accent"])
        set_language(new_lang)
        apply_theme(None, new_theme, new_accent)
        self.ctrl.refresh_settings()

        self.toast(
            tr("settings.reset_toast", "Đã khôi phục mặc định toàn bộ cài đặt."),
            "success",
        )

    def refresh(self) -> None:
        self._load_from_cfg()


def _open_folder(path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 - Windows
    except Exception:
        pass
