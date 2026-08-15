"""Trang Statistics & Export: bieu do thong ke + xuat dataset."""
from __future__ import annotations

import os
from pathlib import Path
from app.i18n import tr
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import COLORS, EXPORT_FORMATS, LABEL_W_WIDE, get_export_formats
from app.core.exporters import ExportConfig
from app.views.pages.base_page import BasePage
from app.views.widgets.charts import (
    BarChart,
    DonutChart,
    Heatmap,
    Histogram,
    Series,
    StackedProgress,
)
from app.views.widgets.common import (
    Card,
    Field,
    KeyValueGrid,
    LegendItem,
    ProgressPanel,
    SliderField,
    StatCard,
    ToggleSwitch,
    browse_button,
    combo,
    ghost_button,
    hline,
    label,
    primary_button,
    section_label,
    spin,
)
from app.workers.export_worker import ExportWorker


class StatsPage(BasePage):
    TITLE = tr("nav.stats", "Thống kê & Xuất")
    SUBTITLE = tr("stats.subtitle", "Phân tích dataset và xuất ra định dạng huấn luyện")
    ICON = "chart"

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._last_exported_dir = ""
        self._fmt = cfg.get("general.default_export_format", "yolo_seg")
        self._tab = "overview"

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.refresh_btn = ghost_button(tr("stats.refresh", "Làm mới"), "refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.export_btn = primary_button(tr("stats.export_dataset", "Xuất dataset"), "download")
        self.export_btn.clicked.connect(lambda: self._select_tab("export"))
        self.header.add_action(self.refresh_btn)
        self.header.add_action(self.export_btn)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_tabs(), 0)
        row.addWidget(self._build_stack(), 1)
        self.add(row, 1)

        self.progress = ProgressPanel()
        self.progress.cancelled.connect(lambda: self.ctrl.cancel("export"))
        self.add(self.progress)
        self.ctrl.imagesChanged.connect(self.refresh)

    def _build_tabs(self) -> QWidget:
        wrap = QWidget()
        wrap.setFixedWidth(178)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(section_label(tr("stats.section", "Mục")))

        self.tab_group = QButtonGroup(self)
        self.tab_buttons = {}
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QPushButton

        from app.theme import icons
        for key, text, icon_name in (
            ("overview", tr("stats.tab_overview", "Tổng quan"), "dashboard"),
            ("classes", tr("stats.tab_classes", "Phân bố lớp"), "layers"),
            ("size", tr("stats.tab_size", "Kích thước đối tượng"), "crop"),
            ("heatmap", tr("stats.tab_heatmap", "Bản đồ nhiệt"), "grid"),
            ("quality", tr("stats.tab_quality", "Chất lượng ảnh"), "shield"),
            ("export", tr("stats.tab_export", "Xuất dataset"), "download"),
        ):
            b = QPushButton("  " + text)
            b.setObjectName("SubTab")
            b.setCheckable(True)
            b.setChecked(key == "overview")
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(icons.icon(icon_name, COLORS["text_dim"], 16))
            b.setIconSize(QSize(16, 16))
            b.clicked.connect(lambda _c=False, k=key: self._select_tab(k))
            self.tab_group.addButton(b)
            self.tab_buttons[key] = b
            lay.addWidget(b)
        lay.addStretch(1)
        return wrap

    def _build_stack(self) -> QWidget:
        self.stack = QStackedWidget()
        self.pages = {
            "overview": self._page_overview(),
            "classes": self._page_classes(),
            "size": self._page_size(),
            "heatmap": self._page_heatmap(),
            "quality": self._page_quality(),
            "export": self._page_export(),
        }
        self._order = list(self.pages)
        for w in self.pages.values():
            self.stack.addWidget(w)
        return self.stack

    def _scroll(self, inner: QWidget) -> QWidget:
        from PySide6.QtWidgets import QScrollArea
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(inner)
        return area

    # ---------------------------------------------------------- tong quan ---
    def _page_overview(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(11)
        self.s_images = StatCard("image", "0", tr("stats.total_images", "Tổng số ảnh"), COLORS["accent"])
        self.s_objects = StatCard("target", "0", tr("stats.total_objects", "Tổng đối tượng"), COLORS["info"])
        self.s_masks = StatCard("polygon", "0", tr("stats.total_masks", "Tổng số mask"), COLORS["success"])
        self.s_avg = StatCard("chart", "0", tr("stats.objects_per_image", "Đối tượng / ảnh"), COLORS["warning"])
        for i, s in enumerate((self.s_images, self.s_objects, self.s_masks, self.s_avg)):
            grid.addWidget(s, 0, i)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(12)
        c1 = Card(tr("stats.class_distribution", "Phân bố lớp"), "", "pie")
        self.ov_donut = DonutChart()
        self.ov_donut.setMinimumHeight(230)
        c1.add(self.ov_donut)
        row.addWidget(c1, 1)

        c2 = Card(tr("stats.size_distribution", "Phân bố kích thước đối tượng"), tr("stats.size_unit_hint", "Diện tích tính bằng px²"), "chart")
        self.ov_hist = Histogram()
        self.ov_hist.setMinimumHeight(230)
        c2.add(self.ov_hist)
        row.addWidget(c2, 1)
        lay.addLayout(row)

        c3 = Card(tr("stats.labeling_progress", "Tiến độ gán nhãn"), "", "check_circle")
        self.ov_bar = StackedProgress(height=12)
        c3.add(self.ov_bar)
        self.ov_legends = {}
        legend_row = QHBoxLayout()
        legend_row.setSpacing(20)
        for key, text, color in (
            ("approved", tr("status.approved", "Đã duyệt"), COLORS["success"]),
            ("review", tr("status.review", "Cần xem lại"), COLORS["warning"]),
            ("auto", tr("status.auto", "Máy gán nhãn"), COLORS["info"]),
            ("unlabeled", tr("status.unlabeled", "Chưa gán nhãn"), COLORS["text_mute"]),
        ):
            item = LegendItem(color, text, "0")
            self.ov_legends[key] = item
            legend_row.addWidget(item)
        c3.add(legend_row)
        lay.addWidget(c3)

        c4 = Card(tr("stats.project_info", "Thông tin project"), "", "info")
        self.ov_info = KeyValueGrid()
        c4.add(self.ov_info)
        lay.addWidget(c4)
        lay.addStretch(1)
        return self._scroll(w)

    # ------------------------------------------------------------- classes --
    def _page_classes(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        c1 = Card(tr("stats.objects_by_class", "Số đối tượng theo lớp"), "", "chart")
        self.cls_bar = BarChart()
        self.cls_bar.setMinimumHeight(250)
        c1.add(self.cls_bar)
        lay.addWidget(c1)

        row = QHBoxLayout()
        row.setSpacing(12)
        c2 = Card(tr("stats.images_per_class", "Số ảnh chứa mỗi lớp"), "", "image")
        self.cls_img_bar = BarChart(horizontal=True)
        self.cls_img_bar.setMinimumHeight(230)
        c2.add(self.cls_img_bar)
        row.addWidget(c2, 1)

        c3 = Card(tr("stats.data_balance", "Độ cân bằng dữ liệu"), tr("stats.data_balance_sub", "Tỷ lệ ảnh có chứa lớp đó"), "target")
        self.cls_cov = BarChart(horizontal=True)
        self.cls_cov.setMinimumHeight(230)
        c3.add(self.cls_cov)
        row.addWidget(c3, 1)
        lay.addLayout(row)

        c4 = Card(tr("stats.conf_dist", "Phân bố độ tin cậy"), tr("stats.conf_dist_sub", "Độ tin cậy của các dự đoán từ model"), "sliders")
        self.conf_hist = Histogram(color=COLORS["info"],
                                   x_labels=["0.0", "0.25", "0.5", "0.75", "1.0"])
        self.conf_hist.setMinimumHeight(200)
        c4.add(self.conf_hist)
        lay.addWidget(c4)
        lay.addStretch(1)
        return self._scroll(w)

    # ---------------------------------------------------------------- size --
    def _page_size(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        c1 = Card(tr("stats.mask_box_area_dist", "Phân bố diện tích mask / box"), tr("stats.x_axis_area", "Trục ngang: diện tích px²"), "crop")
        self.size_hist = Histogram()
        self.size_hist.setMinimumHeight(250)
        c1.add(self.size_hist)
        lay.addWidget(c1)

        c2 = Card(tr("stats.objects_per_img_chart", "Số đối tượng trên mỗi ảnh"), "", "layers")
        self.perimg_hist = Histogram(color=COLORS["success"])
        self.perimg_hist.setMinimumHeight(220)
        c2.add(self.perimg_hist)
        lay.addWidget(c2)

        c3 = Card(tr("stats.size_statistics", "Thống kê kích thước"), "", "info")
        self.size_info = KeyValueGrid()
        c3.add(self.size_info)
        lay.addWidget(c3)
        lay.addStretch(1)
        return self._scroll(w)

    # ------------------------------------------------------------- heatmap --
    def _page_heatmap(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        c1 = Card(tr("stats.heatmap_title", "Bản đồ nhiệt vị trí đối tượng"),
                  tr("stats.heatmap_sub", "Mật độ tâm đối tượng theo khung ảnh chuẩn hoá"), "grid")
        self.heatmap = Heatmap()
        self.heatmap.setMinimumHeight(360)
        c1.add(self.heatmap)
        row = QHBoxLayout()
        row.setSpacing(9)
        row.addWidget(label(tr("stats.grid_res", "Độ phân giải lưới"), size=12, color=COLORS["text_dim"]))
        self.grid_spin = spin(24, 6, 64, 2, width=90)
        self.grid_spin.valueChanged.connect(self.refresh)
        row.addWidget(self.grid_spin)
        row.addWidget(label(tr("stats.color_palette", "Bảng màu"), size=12, color=COLORS["text_dim"]))
        self.cmap_combo = combo([("purple", tr("stats.cmap_purple", "Tím")), ("fire", tr("stats.cmap_fire", "Nóng"))])
        self.cmap_combo.currentIndexChanged.connect(self._apply_cmap)
        row.addWidget(self.cmap_combo)
        row.addStretch(1)
        c1.add(row)
        lay.addWidget(c1, 1)

        c2 = Card(tr("stats.meaning", "Ý nghĩa"), "", "help")
        c2.add(label(
            tr("stats.heatmap_meaning_desc", "Vùng sáng cho biết đối tượng thường xuất hiện ở đó. Nếu đối tượng chỉ tập trung một góc, model có thể học nhầm vị trí thay vì đặc trưng — nên bổ sung dữ liệu đa dạng hơn hoặc bật tăng cường dịch chuyển khi huấn luyện."),
            size=12, color=COLORS["text_mute"], wrap=True))
        lay.addWidget(c2)
        return self._scroll(w)

    def _apply_cmap(self) -> None:
        self.heatmap.colormap = self.cmap_combo.currentData()
        self.heatmap.update()

    # ------------------------------------------------------------- quality --
    def _page_quality(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(11)
        self.q_dup = StatCard("copy", "0", tr("stats.dup_images", "Ảnh trùng lặp"), COLORS["warning"])
        self.q_blur = StatCard("alert", "0", tr("stats.blurry_images", "Ảnh mờ"), COLORS["danger"])
        self.q_dark = StatCard("eye_off", "0", tr("stats.dark_images", "Ảnh thiếu sáng"), COLORS["info"])
        self.q_ok = StatCard("check_circle", "0", tr("stats.valid_images", "Ảnh đạt chuẩn"), COLORS["success"])
        for i, s in enumerate((self.q_ok, self.q_dup, self.q_blur, self.q_dark)):
            grid.addWidget(s, 0, i)
        lay.addLayout(grid)

        c1 = Card(tr("stats.sharpness_dist", "Phân bố độ nét"), tr("stats.sharpness_dist_sub", "Đo bằng variance of Laplacian"), "sparkle")
        self.blur_hist = Histogram(color=COLORS["warning"])
        self.blur_hist.setMinimumHeight(220)
        c1.add(self.blur_hist)
        lay.addWidget(c1)

        c2 = Card(tr("stats.brightness_dist", "Phân bố độ sáng trung bình"), "", "eye")
        self.bright_hist = Histogram(color=COLORS["info"])
        self.bright_hist.setMinimumHeight(220)
        c2.add(self.bright_hist)
        lay.addWidget(c2)
        lay.addStretch(1)
        return self._scroll(w)

    # -------------------------------------------------------------- export --
    def _page_export(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)

        fmt_card = Card(tr("stats.export_fmt", "Định dạng xuất"), "", "download")
        self.fmt_group = QButtonGroup(self)
        from app.views.widgets.common import chip_button
        self.fmt_buttons = {}
        fgrid = QGridLayout()
        fgrid.setSpacing(8)
        for i, (key, text, hint) in enumerate(get_export_formats()):
            b = chip_button(text)
            b.setToolTip(hint)
            b.setChecked(key == cfg.get("general.default_export_format", "yolo_seg"))
            b.clicked.connect(lambda _c=False, k=key: self._set_format(k))
            self.fmt_group.addButton(b)
            self.fmt_buttons[key] = b
            fgrid.addWidget(b, i // 3, i % 3)
        fmt_card.add(fgrid)
        self.fmt_hint = label("", size=11.5, color=COLORS["text_mute"], wrap=True)
        fmt_card.add(self.fmt_hint)
        lay.addWidget(fmt_card)

        cfg_card = Card(tr("stats.config", "Cấu hình"), "", "sliders")
        name_row = QWidget()
        nr = QHBoxLayout(name_row)
        nr.setContentsMargins(0, 0, 0, 0)
        nr.setSpacing(8)
        self.ds_name = QLineEdit("dataset")
        nr.addWidget(self.ds_name)
        cfg_card.add(Field(tr("stats.ds_name", "Tên dataset"), name_row, label_width=LABEL_W_WIDE))

        out_row = QWidget()
        orow = QHBoxLayout(out_row)
        orow.setContentsMargins(0, 0, 0, 0)
        orow.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText(tr("stats.out_dir_placeholder", "Mặc định: thư mục exports của project"))
        browse = browse_button()
        browse.clicked.connect(self._choose_out)
        orow.addWidget(self.out_edit, 1)
        orow.addWidget(browse)
        cfg_card.add(Field(tr("stats.out_dir", "Thư mục xuất"), out_row, label_width=LABEL_W_WIDE))

        self.val_slider = SliderField(0.2, 0.0, 0.5, 2)
        cfg_card.add(Field(tr("train.val_split", "Tỷ lệ tập kiểm định"), self.val_slider, label_width=LABEL_W_WIDE))
        self.test_slider = SliderField(0.0, 0.0, 0.3, 2)
        cfg_card.add(Field(tr("stats.test_split", "Tỷ lệ tập kiểm tra"), self.test_slider, label_width=LABEL_W_WIDE))
        self.seed_spin = spin(42, 0, 99999, width=110)
        cfg_card.add(Field(tr("stats.random_seed", "Seed ngẫu nhiên"), self.seed_spin, label_width=LABEL_W_WIDE))
        self.minconf_slider = SliderField(0.0, 0.0, 0.99, 2)
        cfg_card.add(Field(tr("stats.min_conf", "Độ tin cậy tối thiểu"), self.minconf_slider, label_width=LABEL_W_WIDE))

        cfg_card.add(hline())
        self.only_approved = ToggleSwitch(False)
        self.excl_dup = ToggleSwitch(True)
        self.excl_blur = ToggleSwitch(False)
        self.copy_images = ToggleSwitch(True)
        self.flat_layout = ToggleSwitch(False)
        for text, toggle, hint in (
            (tr("train.approved_only", "Chỉ huấn luyện trên ảnh đã duyệt"), self.only_approved,
             tr("stats.approved_only_hint", "Bỏ qua ảnh máy gán nhãn hoặc cần xem lại")),
            (tr("extract.remove_dup", "Loại ảnh trùng lặp"), self.excl_dup, ""),
            (tr("extract.detect_blur", "Loại ảnh mờ"), self.excl_blur, ""),
            (tr("stats.copy_image_files", "Sao chép file ảnh"), self.copy_images,
             tr("stats.copy_image_files_hint", "Tắt để chỉ sinh file nhãn — nhanh hơn, tiết kiệm ổ đĩa")),
            (tr("stats.no_split", "Không chia train / val"), self.flat_layout,
             tr("stats.no_split_hint", "Xuất tất cả vào một thư mục “all” thay vì chia bộ")),
        ):
            r = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(text, size=12.5, color=COLORS["text"]))
            if hint:
                col.addWidget(label(hint, size=11, color=COLORS["text_mute"]))
            r.addLayout(col)
            r.addStretch(1)
            r.addWidget(toggle)
            cfg_card.add(r)
        lay.addWidget(cfg_card)

        run_card = Card(tr("stats.execute", "Thực hiện"), "", "play")
        row = QHBoxLayout()
        row.setSpacing(9)
        self.run_export_btn = primary_button(tr("stats.start_export", "Bắt đầu xuất"), "download")
        self.run_export_btn.clicked.connect(self.run_export)
        self.open_out_btn = ghost_button(tr("stats.open_result_dir", "Mở thư mục kết quả"), "folder_open")
        self.open_out_btn.clicked.connect(self._open_result)
        self.open_out_btn.setEnabled(False)
        row.addWidget(self.run_export_btn)
        row.addWidget(self.open_out_btn)
        row.addStretch(1)
        run_card.add(row)
        self.export_log = QPlainTextEdit()
        self.export_log.setObjectName("LogView")
        self.export_log.setReadOnly(True)
        self.export_log.setMinimumHeight(170)
        run_card.add(self.export_log)
        lay.addWidget(run_card, 1)

        self._set_format(cfg.get("general.default_export_format", "yolo_seg"))
        return self._scroll(w)

    # ================================================================ LOGIC ==
    def _select_tab(self, key: str) -> None:
        self._tab = key
        for k, b in self.tab_buttons.items():
            b.setChecked(k == key)
        self.stack.setCurrentIndex(self._order.index(key))
        self.refresh()

    def _set_format(self, key: str) -> None:
        self._fmt = key
        for k, b in self.fmt_buttons.items():
            b.setChecked(k == key)
        hint = next((h for k, _t, h in EXPORT_FORMATS if k == key), "")
        self.fmt_hint.setText(hint)

    def _choose_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất")
        if d:
            self.out_edit.setText(d)

    # =============================================================== REFRESH ==
    def refresh(self) -> None:
        repo = self.repo
        if repo is None:
            return
        info = repo.refresh_stats()
        stats = repo.class_stats()
        counts = repo.status_counts()

        # --- tong quan ---
        n_masks = sum(s["masks"] for s in stats)
        self.s_images.set_value(f"{info.n_images:,}")
        self.s_objects.set_value(f"{info.n_objects:,}")
        self.s_masks.set_value(f"{n_masks:,}")
        avg = info.n_objects / info.n_images if info.n_images else 0
        self.s_avg.set_value(f"{avg:.2f}")

        self.ov_donut.set_data(
            [Series(s["name"], s["objects"], s["color"]) for s in stats if s["objects"]],
            f"{info.n_objects:,}", "objects")
        edges, hist = repo.area_histogram(28)
        self.ov_hist.set_data(hist, edges)

        segments = []
        for key, color in (("approved", COLORS["success"]), ("review", COLORS["warning"]),
                           ("auto", COLORS["info"]), ("unlabeled", COLORS["text_mute"])):
            n = counts.get(key, 0)
            self.ov_legends[key].set_value(f"{n:,}")
            if n:
                segments.append((n, color))
        self.ov_bar.set_segments(segments)
        self.ov_info.set_pairs([
            ("Tên project", info.name),
            ("Thư mục", info.root_dir),
            ("Loại bài toán", info.task),
            ("Tạo lúc", info.created_at),
            ("Cập nhật", info.updated_at),
            ("Số lớp", str(info.n_classes)),
            ("Tổng diện tích mask", f"{repo.total_mask_area():,.0f} px²"),
        ])

        # --- classes ---
        self.cls_bar.set_data([Series(s["name"], s["objects"], s["color"]) for s in stats])
        self.cls_img_bar.set_data([Series(s["name"], s["images"], s["color"])
                                   for s in stats])
        self.cls_cov.set_data([Series(s["name"], round(s["coverage"], 1), s["color"])
                               for s in stats])
        self.conf_hist.set_data(repo.confidence_histogram(20))

        # --- size ---
        self.size_hist.set_data(hist, edges)
        per_img = repo.objects_per_image()
        if per_img:
            top = max(per_img)
            bins = min(20, max(1, top + 1))
            counts_pi = [0] * bins
            for v in per_img:
                counts_pi[min(bins - 1, v)] += 1
            self.perimg_hist.x_labels = ["0", str(bins // 2), f"{bins - 1}+"]
            self.perimg_hist.set_data(counts_pi)
        areas_edges, areas_counts = edges, hist
        if areas_edges:
            self.size_info.set_pairs([
                ("Diện tích nhỏ nhất", f"{areas_edges[0]:,.0f} px²"),
                ("Diện tích lớn nhất", f"{areas_edges[-1]:,.0f} px²"),
                ("Đối tượng / ảnh — trung bình", f"{avg:.2f}"),
                ("Đối tượng / ảnh — nhiều nhất", str(max(per_img) if per_img else 0)),
                ("Tổng số mask polygon", f"{n_masks:,}"),
            ])

        # --- heatmap ---
        self.heatmap.set_matrix(repo.object_heatmap(self.grid_spin.value()))

        # --- quality ---
        blur_thr = cfg.get("extract.blur_threshold", 60.0)
        dark_thr = cfg.get("extract.lowlight_threshold", 45.0)
        q = repo.quality_counts(blur_thr, dark_thr)
        self.q_dup.set_value(f"{q['duplicate']:,}")
        self.q_blur.set_value(f"{q['blurry']:,}")
        self.q_dark.set_value(f"{q['dark']:,}")
        self.q_ok.set_value(f"{max(0, info.n_images - q['duplicate'] - q['blurry']):,}")

        images = repo.images()
        self.blur_hist.set_data(*_hist([im.blur_score for im in images
                                        if im.blur_score > 0], 26))
        self.bright_hist.set_data(*_hist([im.brightness for im in images
                                          if im.brightness > 0], 26))

    # ================================================================ EXPORT ==
    def run_export(self) -> None:
        if not self.repo:
            return
        if self.ctrl.is_running("export"):
            self.toast("Đang xuất, vui lòng đợi.", "warning")
            return
        out_dir = self.out_edit.text().strip() or str(self.repo.sub("exports"))
        ecfg = ExportConfig(
            fmt=self._fmt,
            output_dir=out_dir,
            dataset_name=self.ds_name.text().strip() or "dataset",
            val_split=self.val_slider.value(),
            test_split=self.test_slider.value(),
            train_split=max(0.0, 1 - self.val_slider.value() - self.test_slider.value()),
            seed=self.seed_spin.value(),
            copy_images=self.copy_images.isChecked(),
            only_approved=self.only_approved.isChecked(),
            exclude_duplicates=self.excl_dup.isChecked(),
            exclude_blurry=self.excl_blur.isChecked(),
            blur_threshold=cfg.get("extract.blur_threshold", 60.0),
            min_confidence=self.minconf_slider.value(),
            flat_layout=self.flat_layout.isChecked(),
        )
        cfg.set("general.default_export_format", self._fmt)
        cfg.save()

        self.export_log.clear()
        self.progress.start("Đang xuất dataset …")
        self.run_export_btn.setEnabled(False)
        worker = ExportWorker(self.repo, ecfg)
        self.ctrl.run_worker(
            "export", worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_log=self._log,
            on_done=self._on_export_done,
            on_fail=lambda _m: self.run_export_btn.setEnabled(True),
        )

    def _log(self, text: str) -> None:
        self.export_log.appendPlainText(text)
        self.export_log.verticalScrollBar().setValue(
            self.export_log.verticalScrollBar().maximum())

    def _on_export_done(self, result) -> None:
        self.run_export_btn.setEnabled(True)
        self.progress.finish("Xuất dataset hoàn tất")
        if result is None:
            return
        self._result_dir = result.output_dir
        self.open_out_btn.setEnabled(True)
        splits = ", ".join(f"{k}={v}" for k, v in result.splits.items())
        self._log(f"Thư mục: {result.output_dir}")
        self.toast(
            f"Đã xuất {result.n_images:,} ảnh / {result.n_objects:,} đối tượng ({splits}).",
            "success")

    def _open_result(self) -> None:
        path = getattr(self, "_result_dir", "")
        if path and Path(path).exists():
            try:
                os.startfile(path)  # noqa: S606
            except Exception:
                self.toast(path, "info")


def _hist(values, bins: int = 26):
    if not values:
        return [], []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [len(values)], [lo]
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        counts[min(bins - 1, int((v - lo) / step))] += 1
    edges = [lo + step * i for i in range(bins)]
    return counts, edges
