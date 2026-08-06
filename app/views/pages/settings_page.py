"""Trang Settings: cau hinh chung, model, suy luan, annotation, plugin, phim tat."""
from __future__ import annotations

import os
from pathlib import Path

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

from app.config import DEFAULTS, cfg
from app.constants import (
    LABEL_W_WIDE,
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    CLASS_PALETTE,
    COLORS,
    EXPORT_FORMATS,
    SHORTCUTS,
    YOLO_TASKS,
)
from app.core.inference import available_devices, device_info
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
    danger_button,
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
        self.reset_btn = ghost_button("Khôi phục mặc định", "refresh")
        self.reset_btn.clicked.connect(self._reset)
        self.save_btn = primary_button("Lưu cài đặt", "save")
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
        lay.addWidget(section_label("Mục cài đặt"))

        self.tab_group = QButtonGroup(self)
        self.tab_buttons = {}
        for key, text, icon_name in (
            ("general", "Chung", "settings"),
            ("model", "Model", "cpu"),
            ("inference", "Suy luận", "sliders"),
            ("annotation", "Gán nhãn", "pen"),
            ("plugins", "Plugin", "puzzle"),
            ("shortcuts", "Phím tắt", "keyboard"),
            ("about", "Giới thiệu", "info"),
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

    def _toggle_row(self, card: Card, text: str, toggle: ToggleSwitch,
                    hint: str = "") -> None:
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

        card = Card("Giao diện", "", "sparkle")
        # Ban 1.0 chi co tieng Viet - khong bay o chon gia de tranh hieu nham
        # Bản 1.0 chỉ có tiếng Việt — khoá lại thay vì hiện lựa chọn giả
        self.lang_combo = combo(["Tiếng Việt"], current="Tiếng Việt")
        self.lang_combo.setEnabled(False)
        self.lang_combo.setToolTip("Bản 1.0 chỉ hỗ trợ tiếng Việt")
        card.add(Field("Ngôn ngữ", self.lang_combo, label_width=LABEL_W_WIDE))
        self.theme_combo = combo(["Dark"], current="Dark")
        card.add(Field("Giao diện", self.theme_combo, label_width=LABEL_W_WIDE))

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
                f"border: 2px solid {'#FFFFFF' if color == self._accent else 'transparent'};")
            b.clicked.connect(lambda _c=False, col=color: self._set_accent(col))
            self.accent_buttons.append((b, color))
            ar.addWidget(b)
        custom = ghost_button("Màu khác…")
        custom.clicked.connect(self._pick_accent)
        ar.addWidget(custom)
        ar.addStretch(1)
        card.add(Field("Màu nhấn", accent_row, label_width=LABEL_W_WIDE))
        card.add(label("Đổi màu sẽ áp dụng sau khi khởi động lại ứng dụng.",
                       size=11, color=COLORS["text_mute"]))
        lay.addWidget(card)

        proj_card = Card("Project", "", "folder")
        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self.projects_edit = QLineEdit(cfg.get("general.projects_dir", ""))
        pick = browse_button()
        pick.clicked.connect(self._pick_projects_dir)
        fr.addWidget(self.projects_edit, 1)
        fr.addWidget(pick)
        proj_card.add(Field("Thư mục project", folder_row, label_width=LABEL_W_WIDE))

        self.autosave_spin = spin(cfg.get("general.autosave_minutes", 5), 0, 120,
                                  suffix=" phút", width=126)
        self.autosave_spin.setSpecialValueText("Tắt")
        proj_card.add(Field("Tự động lưu mỗi", self.autosave_spin, label_width=LABEL_W_WIDE))

        self.export_combo = combo([(k, t) for k, t, _h in EXPORT_FORMATS],
                                  current=cfg.get("general.default_export_format",
                                                  "yolo_seg"))
        proj_card.add(Field("Định dạng xuất mặc định", self.export_combo,
                            label_width=LABEL_W_WIDE))

        self.confirm_toggle = ToggleSwitch(cfg.get("general.confirm_on_exit", True))
        self._toggle_row(proj_card, "Hỏi trước khi thoát", self.confirm_toggle)
        self.reopen_toggle = ToggleSwitch(cfg.get("general.reopen_last_project", True))
        self._toggle_row(proj_card, "Mở lại project gần nhất khi khởi động",
                         self.reopen_toggle,
                         "Tắt nếu bạn muốn luôn bắt đầu từ màn hình trống")
        lay.addWidget(proj_card)

        path_card = Card("Đường dẫn hệ thống", "", "file")
        path_card.add(KeyValueGrid([
            ("Cấu hình và dữ liệu", str(user_data_dir())),
            ("Nhật ký", str(log_dir())),
            ("Trọng số tải về", str(weights_dir())),
            ("Plugin người dùng", str(plugins_dir())),
        ], value_bold=False))
        row = QHBoxLayout()
        row.setSpacing(8)
        for text, path in (("Mở thư mục dữ liệu", user_data_dir()),
                           ("Mở thư mục nhật ký", log_dir()),
                           ("Mở thư mục trọng số", weights_dir())):
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
                f"border: 2px solid {'#FFFFFF' if c == color else 'transparent'};")

    def _pick_accent(self) -> None:
        color = QColorDialog.getColor(QColor(self._accent), self, "Chọn màu nhấn")
        if color.isValid():
            self._set_accent(color.name())

    def _pick_projects_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu project",
                                             self.projects_edit.text())
        if d:
            self.projects_edit.setText(d)

    # ================================================================= MODEL ==
    def _page_model(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("Model mặc định", "Dùng khi mở trang Auto Label", "cpu")
        self.m_task = combo([(t, t.capitalize()) for t in YOLO_TASKS],
                            current=cfg.get("model.task", "segment"))
        card.add(Field("Nhiệm vụ", self.m_task, label_width=LABEL_W_WIDE))
        self.m_weights = QLineEdit(cfg.get("model.weights", "yolo11n-seg.pt"))
        card.add(Field("Trọng số", self.m_weights, label_width=LABEL_W_WIDE))

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
        card.add(Field("Model riêng", custom_row, label_width=LABEL_W_WIDE))

        self.m_device = combo(available_devices(), current=cfg.get("model.device", "auto"))
        card.add(Field("Thiết bị", self.m_device, label_width=LABEL_W_WIDE))
        self.m_imgsz = spin(cfg.get("model.imgsz", 640), 128, 4096, 32, width=118)
        card.add(Field("Cỡ ảnh vào model", self.m_imgsz, label_width=LABEL_W_WIDE))
        self.m_half = ToggleSwitch(cfg.get("model.half", False))
        self._toggle_row(card, "Dùng FP16 (nửa độ chính xác)", self.m_half,
                         "Nhanh hơn trên GPU có tensor core")
        lay.addWidget(card)

        gpu_card = Card("Thiết bị hiện tại", "", "bolt")
        d = device_info()
        gpu_card.add(KeyValueGrid([
            ("CUDA khả dụng", "Có" if d["cuda"] else "Không"),
            ("Tên thiết bị", d["name"]),
            ("Số GPU", str(d["count"])),
            ("VRAM", f"{d['total_gb']:.1f} GB" if d["total_gb"] else "-"),
            ("Phiên bản torch", d["torch"] or "chưa cài"),
            ("Phiên bản CUDA", d["cuda_version"] or "—"),
        ]))
        lay.addWidget(gpu_card)
        lay.addStretch(1)
        return self._scroll(w)

    def _pick_weights(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn trọng số", str(weights_dir()),
            "Model (*.pt *.onnx *.engine);;Tất cả file (*)")
        if path:
            self.m_custom.setText(path)

    # ============================================================= INFERENCE ==
    def _page_inference(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("Ngưỡng suy luận", "", "sliders")
        self.i_conf = SliderField(cfg.get("inference.confidence", 0.45), 0.01, 0.99, 2)
        card.add(Field("Độ tin cậy", self.i_conf, label_width=LABEL_W_WIDE))
        self.i_iou = SliderField(cfg.get("inference.iou", 0.5), 0.05, 0.95, 2)
        card.add(Field("IOU (khử trùng)", self.i_iou, label_width=LABEL_W_WIDE))
        self.i_review = SliderField(cfg.get("inference.review_threshold", 0.6), 0.05, 0.99, 2)
        card.add(Field("Ngưỡng cần xem lại", self.i_review, label_width=LABEL_W_WIDE))
        self.i_low = SliderField(cfg.get("inference.low_conf_threshold", 0.35), 0.01, 0.9, 2)
        card.add(Field("Ngưỡng tin cậy thấp", self.i_low, label_width=LABEL_W_WIDE))
        self.i_maxdet = spin(cfg.get("inference.max_det", 1000), 1, 30000, 50, width=118)
        card.add(Field("Số đối tượng tối đa", self.i_maxdet, label_width=LABEL_W_WIDE))
        lay.addWidget(card)

        poly_card = Card("Hậu xử lý", "", "polygon")
        self.i_simplify = SliderField(cfg.get("inference.polygon_simplify", 0.0025),
                                      0.0, 0.02, 4, 0.0005)
        poly_card.add(Field("Giản lược polygon", self.i_simplify, label_width=LABEL_W_WIDE))
        self.i_minarea = spin(cfg.get("inference.min_area_px", 24), 0, 100000, 4,
                              suffix=" px", width=118)
        poly_card.add(Field("Diện tích tối thiểu", self.i_minarea, label_width=LABEL_W_WIDE))
        self.i_retina = ToggleSwitch(cfg.get("inference.retina_masks", True))
        self._toggle_row(poly_card, "Mask độ phân giải cao", self.i_retina,
                         "Mask sắc nét hơn, chậm hơn một chút")
        self.i_agnostic = ToggleSwitch(cfg.get("inference.agnostic_nms", False))
        self._toggle_row(poly_card, "Khử trùng không phân biệt lớp", self.i_agnostic)
        self.i_overwrite = ToggleSwitch(cfg.get("inference.overwrite_existing", True))
        self._toggle_row(poly_card, "Ghi đè nhãn đã có khi gán nhãn tự động", self.i_overwrite)
        lay.addWidget(poly_card)
        lay.addStretch(1)
        return self._scroll(w)

    # ============================================================ ANNOTATION ==
    def _page_annotation(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("Hiển thị trên vùng vẽ", "", "eye")
        self.a_conf = ToggleSwitch(cfg.get("annotation.show_confidence", True))
        self._toggle_row(card, "Hiện độ tin cậy", self.a_conf)
        self.a_color = ToggleSwitch(cfg.get("annotation.show_class_color", True))
        self._toggle_row(card, "Tô màu theo lớp", self.a_color)
        self.a_labels = ToggleSwitch(cfg.get("annotation.show_labels", True))
        self._toggle_row(card, "Hiện tên lớp", self.a_labels)
        self.a_select = ToggleSwitch(cfg.get("annotation.auto_select_new", True))
        self._toggle_row(card, "Tự chọn đối tượng vừa tạo", self.a_select)
        lay.addWidget(card)

        tool_card = Card("Công cụ", "", "brush")
        self.a_brush = spin(cfg.get("annotation.brush_size", 20), 2, 300, 2,
                            suffix=" px", width=118)
        tool_card.add(Field("Cỡ cọ vẽ", self.a_brush, label_width=LABEL_W_WIDE))
        self.a_opacity = SliderField(cfg.get("annotation.fill_opacity", 0.35), 0.0, 0.9, 2)
        tool_card.add(Field("Độ đậm vùng tô", self.a_opacity, label_width=LABEL_W_WIDE))
        self.a_line = dspin(cfg.get("annotation.line_width", 2), 0.5, 8, 0.5, 1, width=118)
        tool_card.add(Field("Độ dày đường viền", self.a_line, label_width=LABEL_W_WIDE))
        self.a_vertex = dspin(cfg.get("annotation.vertex_size", 6), 2, 16, 1, 1, width=118)
        tool_card.add(Field("Cỡ điểm đỉnh", self.a_vertex, label_width=LABEL_W_WIDE))
        lay.addWidget(tool_card)
        lay.addStretch(1)
        return self._scroll(w)

    # =============================================================== PLUGINS ==
    def _page_plugins(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("Plugin gán nhãn tự động",
                    "Mở rộng chất lượng gán nhãn bằng các mô hình nền tảng", "puzzle")
        self.plugin_table = QTableWidget(0, 4)
        self.plugin_table.setHorizontalHeaderLabels(
            ["Plugin", "Loại", "Trạng thái", "Yêu cầu"])
        self.plugin_table.verticalHeader().setVisible(False)
        self.plugin_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.plugin_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.plugin_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 4):
            self.plugin_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeToContents)
        self.plugin_table.setMinimumHeight(190)
        self.plugin_table.currentCellChanged.connect(
            lambda r, *_: self._show_plugin_detail(r))
        card.add(self.plugin_table)

        row = QHBoxLayout()
        row.setSpacing(8)
        reload_btn = ghost_button("Quét lại plugin", "refresh")
        reload_btn.clicked.connect(lambda: (registry.discover(force=True),
                                            self._refresh_plugins()))
        folder_btn = ghost_button("Mở thư mục plugin", "folder_open")
        folder_btn.clicked.connect(lambda: _open_folder(plugins_dir()))
        row.addWidget(reload_btn)
        row.addWidget(folder_btn)
        row.addStretch(1)
        card.add(row)
        lay.addWidget(card)

        self.plugin_detail_card = Card("Chi tiết plugin", "", "info")
        self.plugin_detail = label("Chọn một plugin để xem chi tiết.",
                                   size=12, color=COLORS["text_dim"], wrap=True)
        self.plugin_detail_card.add(self.plugin_detail)
        self.plugin_install = label("", size=11.5, color=COLORS["text_mute"], wrap=True)
        self.plugin_detail_card.add(self.plugin_install)
        lay.addWidget(self.plugin_detail_card)

        guide = Card("Tự viết plugin", "", "book")
        guide.add(label(
            "Tạo file .py trong thư mục plugin với một lớp kế thừa AnnotatorPlugin, "
            "khai báo info = PluginInfo(...) và cài đặt phương thức annotate(ctx) "
            "trả về danh sách Detection. Ứng dụng sẽ tự nạp khi khởi động.",
            size=12, color=COLORS["text_mute"], wrap=True))
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
            self.plugin_table.setItem(r, 1, QTableWidgetItem(
                "Sinh mới" if info.kind == "generate" else "Tinh chỉnh"))
            status_item = QTableWidgetItem(msg)
            status_item.setForeground(QColor(COLORS["success"] if ok else COLORS["warning"]))
            self.plugin_table.setItem(r, 2, status_item)
            self.plugin_table.setItem(r, 3, QTableWidgetItem(", ".join(info.requires)))

    def _show_plugin_detail(self, row: int) -> None:
        infos = getattr(self, "_plugin_infos", [])
        if not (0 <= row < len(infos)):
            return
        info = infos[row]
        ok, msg = registry.status(info.key)
        self.plugin_detail.setText(
            f"{info.name} v{info.version}\n\n{info.description}\n\n"
            f"Trang chủ: {info.homepage or '—'}")
        if ok:
            self.plugin_install.setText("Plugin đã sẵn sàng sử dụng.")
            self.plugin_install.setStyleSheet(f"font-size: 11.5px; color: {COLORS['success']};")
        else:
            self.plugin_install.setText(
                f"{msg}. Cài đặt bằng lệnh: pip install " + " ".join(info.requires))
            self.plugin_install.setStyleSheet(f"font-size: 11.5px; color: {COLORS['warning']};")

    # ============================================================= SHORTCUTS ==
    def _page_shortcuts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        card = Card("Phím tắt", "Thao tác nhanh như CVAT hoặc Roboflow", "keyboard")
        table = QTableWidget(len(SHORTCUTS), 3)
        table.setHorizontalHeaderLabels(["Nhóm", "Phím", "Chức năng"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for r, (group, keys, desc) in enumerate(SHORTCUTS):
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
        col.addWidget(label(f"Phiên bản {APP_VERSION}", size=11.5,
                            color=COLORS["text_mute"]))
        head.addLayout(col)
        head.addStretch(1)
        card.add(head)
        card.add(hline())
        card.add(label(
            "AutoLabel Studio AI biến video thành dataset Computer Vision hoàn chỉnh: "
            "cắt frame thông minh, lọc ảnh trùng và ảnh kém chất lượng, tự động gán "
            "nhãn bằng YOLO, tinh chỉnh bằng công cụ polygon và cọ vẽ chuyên nghiệp, "
            "thống kê dataset rồi huấn luyện lại model — tất cả trong một ứng dụng.",
            size=12.5, color=COLORS["text_dim"], wrap=True))
        lay.addWidget(card)

        tech = Card("Công nghệ sử dụng", "", "layers")
        tech.add(KeyValueGrid([
            ("Giao diện", "PySide6 (Qt 6) — Fluent Dark"),
            ("Suy luận", "Ultralytics YOLOv8 / YOLO11 / YOLO12"),
            ("Xử lý ảnh", "OpenCV, scikit-image, NumPy"),
            ("Hình học", "Shapely — gộp, cắt, cọ vẽ"),
            ("Lưu trữ", "SQLite (WAL), tự lưu và sao lưu"),
            ("Kiến trúc", "MVC, worker QThread, hệ thống plugin"),
        ], value_bold=False))
        lay.addWidget(tech)

        credit = Card("Ghi chú", "", "info")
        credit.add(label(
            "Các mô hình YOLO của Ultralytics phát hành theo giấy phép AGPL-3.0. "
            "Hãy kiểm tra điều khoản trước khi dùng cho mục đích thương mại.",
            size=12, color=COLORS["text_mute"], wrap=True))
        lay.addWidget(credit)
        lay.addStretch(1)
        return self._scroll(w)

    # ================================================================== SAVE ==
    def save_all(self) -> None:
        cfg.update_section("general", {
            "accent": self._accent,
            "projects_dir": self.projects_edit.text().strip(),
            "autosave_minutes": self.autosave_spin.value(),
            "default_export_format": self.export_combo.currentData(),
            "confirm_on_exit": self.confirm_toggle.isChecked(),
            "reopen_last_project": self.reopen_toggle.isChecked(),
        })
        cfg.update_section("model", {
            "task": self.m_task.currentData(),
            "weights": self.m_weights.text().strip(),
            "custom_weights": self.m_custom.text().strip(),
            "device": self.m_device.currentData(),
            "imgsz": self.m_imgsz.value(),
            "half": self.m_half.isChecked(),
        })
        cfg.update_section("inference", {
            "confidence": self.i_conf.value(), "iou": self.i_iou.value(),
            "review_threshold": self.i_review.value(),
            "low_conf_threshold": self.i_low.value(),
            "max_det": self.i_maxdet.value(),
            "polygon_simplify": self.i_simplify.value(),
            "min_area_px": self.i_minarea.value(),
            "retina_masks": self.i_retina.isChecked(),
            "agnostic_nms": self.i_agnostic.isChecked(),
            "overwrite_existing": self.i_overwrite.isChecked(),
        })
        cfg.update_section("annotation", {
            "show_confidence": self.a_conf.isChecked(),
            "show_class_color": self.a_color.isChecked(),
            "show_labels": self.a_labels.isChecked(),
            "auto_select_new": self.a_select.isChecked(),
            "brush_size": self.a_brush.value(),
            "fill_opacity": self.a_opacity.value(),
            "line_width": self.a_line.value(),
            "vertex_size": self.a_vertex.value(),
        })
        cfg.save()
        self.ctrl.refresh_settings()
        self.toast("Đã lưu cài đặt.", "success")

    def _reset(self) -> None:
        if QMessageBox.question(
                self, "Khôi phục mặc định",
                "Đưa toàn bộ cài đặt về giá trị mặc định?") != QMessageBox.Yes:
            return
        cfg.reset()
        self.toast("Đã khôi phục mặc định. Khởi động lại để áp dụng đầy đủ.", "info")

    def refresh(self) -> None:
        self._refresh_plugins()


def _open_folder(path) -> None:
    try:
        os.startfile(str(path))  # noqa: S606 - Windows
    except Exception:
        pass
