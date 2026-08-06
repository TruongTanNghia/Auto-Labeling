"""Trang Dataset Manager: duyet, loc, don dep va quan ly anh + class."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    COLORS,
    IMG_APPROVED,
    IMG_AUTO,
    IMG_REVIEW,
    IMG_UNLABELED,
    PAGE_EDITOR,
)
from app.views.pages.base_page import BasePage
from app.views.widgets.charts import BarChart, DonutChart, Series
from app.views.widgets.common import (
    Card,
    SearchBox,
    StatCard,
    chip_button,
    combo,
    danger_button,
    ghost_button,
    hline,
    label,
    primary_button,
    section_label,
)
from app.views.widgets.image_list import ImageGallery


class DatasetPage(BasePage):
    TITLE = "Dataset Manager"
    SUBTITLE = "Quản lý ảnh, lớp đối tượng, ảnh trùng và ảnh kém chất lượng"
    ICON = "database"

    navigate = Signal(str)

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._filter = "all"
        self._images = []

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.cleanup_btn = ghost_button("Dọn dẹp", "sparkle")
        self.cleanup_btn.clicked.connect(self._cleanup_menu)
        self.open_editor_btn = primary_button("Mở trình sửa nhãn", "pen")
        self.open_editor_btn.clicked.connect(lambda: self.navigate.emit(PAGE_EDITOR))
        self.header.add_action(self.cleanup_btn)
        self.header.add_action(self.open_editor_btn)

        self._build_stats()
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_gallery(), 5)
        row.addWidget(self._build_side(), 3)
        self.add(row, 1)

        self.ctrl.imagesChanged.connect(self.refresh)
        self.ctrl.classesChanged.connect(self.refresh)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(11)
        self.stat_total = StatCard("image", "0", "Tổng số ảnh", COLORS["accent"])
        self.stat_labeled = StatCard("check_circle", "0", "Đã gán nhãn", COLORS["success"])
        self.stat_unlabeled = StatCard("alert", "0", "Chưa gán nhãn", COLORS["warning"])
        self.stat_objects = StatCard("target", "0", "Tổng đối tượng", COLORS["info"])
        self.stat_classes = StatCard("layers", "0", "Số lớp", COLORS["accent_hi"])
        self.stat_dup = StatCard("copy", "0", "Ảnh trùng", COLORS["danger"])
        for w in (self.stat_total, self.stat_labeled, self.stat_unlabeled,
                  self.stat_objects, self.stat_classes, self.stat_dup):
            row.addWidget(w)
        self.stat_unlabeled.clicked.connect(lambda: self._set_filter("unlabeled"))
        self.stat_dup.clicked.connect(lambda: self._set_filter("duplicate"))
        self.stat_labeled.clicked.connect(lambda: self._set_filter("labeled"))
        self.add(row)

    # -------------------------------------------------------------- gallery --
    def _build_gallery(self) -> QWidget:
        card = Card("Thư viện ảnh", "", "grid")

        bar = QHBoxLayout()
        bar.setSpacing(7)
        self.filter_buttons = {}
        for key, text in (("all", "Tất cả"), ("labeled", "Đã gán nhãn"),
                          ("unlabeled", "Chưa gán nhãn"), ("review", "Cần xem lại"),
                          ("approved", "Đã duyệt"), ("duplicate", "Trùng"),
                          ("blurry", "Mờ")):
            b = chip_button(text)
            b.setChecked(key == "all")
            b.clicked.connect(lambda _c=False, k=key: self._set_filter(k))
            self.filter_buttons[key] = b
            bar.addWidget(b)
        bar.addStretch(1)
        self.search = SearchBox("Tìm theo tên file …")
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(self.refresh)
        bar.addWidget(self.search)
        self.size_combo = combo([(118, "Nhỏ"), (150, "Vừa"), (198, "Lớn")], current=150)
        self.size_combo.setFixedWidth(88)
        self.size_combo.currentIndexChanged.connect(
            lambda: self.gallery.set_cell_size(self.size_combo.currentData()))
        bar.addWidget(self.size_combo)
        card.add(bar)

        self.gallery = ImageGallery(cell=150)
        self.gallery.imageActivated.connect(self._open_in_editor)
        self.gallery.selectionIds.connect(self._on_selection)
        card.add(self.gallery, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.sel_label = label("Chưa chọn ảnh nào", size=11.5, color=COLORS["text_mute"])
        actions.addWidget(self.sel_label)
        actions.addStretch(1)
        self.approve_btn = ghost_button("Duyệt", "check")
        self.approve_btn.clicked.connect(lambda: self._mark_status(IMG_APPROVED))
        self.review_btn = ghost_button("Đánh dấu xem lại", "alert")
        self.review_btn.clicked.connect(lambda: self._mark_status(IMG_REVIEW))
        self.delete_btn = danger_button("Xoá", "trash")
        self.delete_btn.clicked.connect(self._delete_selected)
        for b in (self.approve_btn, self.review_btn, self.delete_btn):
            actions.addWidget(b)
        card.add(actions)
        return card

    # ----------------------------------------------------------------- side --
    def _build_side(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        chart_card = Card("Đối tượng theo lớp", "", "chart")
        self.class_bar = BarChart(horizontal=True)
        self.class_bar.setMinimumHeight(180)
        chart_card.add(self.class_bar)
        lay.addWidget(chart_card)

        donut_card = Card("Tỷ lệ ảnh theo lớp", "", "pie")
        self.class_donut = DonutChart()
        self.class_donut.setMinimumHeight(190)
        donut_card.add(self.class_donut)
        lay.addWidget(donut_card)

        table_card = Card("Chi tiết từng lớp", "", "list")
        self.class_table = QTableWidget(0, 6)
        self.class_table.setHorizontalHeaderLabels(
            ["Lớp", "Ảnh", "Đối tượng", "Mask", "Diện tích TB", "Độ phủ"])
        self.class_table.verticalHeader().setVisible(False)
        self.class_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.class_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.class_table.setAlternatingRowColors(True)
        self.class_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        for c in range(1, 6):
            self.class_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeToContents)
        self.class_table.setMinimumHeight(200)
        table_card.add(self.class_table)
        lay.addWidget(table_card, 1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(wrap)
        return area

    # ================================================================ LOGIC ==
    def _set_filter(self, key: str) -> None:
        self._filter = key
        for k, b in self.filter_buttons.items():
            b.setChecked(k == key)
        self.refresh()

    def refresh(self) -> None:
        repo = self.repo
        if repo is None:
            return
        info = repo.refresh_stats()
        counts = repo.status_counts()
        self.stat_total.set_value(f"{info.n_images:,}")
        self.stat_labeled.set_value(f"{info.n_labeled:,}")
        self.stat_unlabeled.set_value(f"{counts.get(IMG_UNLABELED, 0):,}")
        self.stat_objects.set_value(f"{info.n_objects:,}")
        self.stat_classes.set_value(info.n_classes)
        self.stat_dup.set_value(f"{repo.duplicate_count():,}")

        self._images = self._filtered_images()
        self.gallery.set_images(self._images)

        stats = repo.class_stats()
        self.class_bar.set_data([
            Series(s["name"], s["objects"], s["color"]) for s in stats if s["objects"]
        ])
        self.class_donut.set_data(
            [Series(s["name"], s["images"], s["color"]) for s in stats if s["images"]],
            f"{info.n_images:,}", "anh")

        self.class_table.setRowCount(len(stats))
        for r, s in enumerate(stats):
            name_item = QTableWidgetItem("  " + s["name"])
            name_item.setForeground(QColor(s["color"]))
            self.class_table.setItem(r, 0, name_item)
            for c, value in enumerate([
                f"{s['images']:,}", f"{s['objects']:,}", f"{s['masks']:,}",
                f"{s['avg_area']:,.0f}", f"{s['coverage']:.1f}%",
            ], start=1):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.class_table.setItem(r, c, item)

    def _filtered_images(self):
        repo = self.repo
        search = self.search.text().strip() if hasattr(self, "search") else ""
        key = self._filter
        if key == "duplicate":
            images = [im for im in repo.images(search=search) if im.is_duplicate]
        elif key == "blurry":
            thr = cfg.get("extract.blur_threshold", 60.0)
            images = [im for im in repo.images(search=search)
                      if 0 < im.blur_score < thr]
        elif key in ("labeled", "unlabeled", "review", "approved"):
            images = repo.images(status=key, search=search)
        else:
            images = repo.images(search=search)
        return images

    def _on_selection(self, ids) -> None:
        self.sel_label.setText(f"Đang chọn {len(ids):,} ảnh" if ids
                               else "Chưa chọn ảnh nào")

    def _open_in_editor(self, image_id: int) -> None:
        self.ctrl.set_current_image(image_id)
        self.navigate.emit(PAGE_EDITOR)

    # ============================================================== ACTIONS ==
    def _mark_status(self, status: str) -> None:
        ids = self.gallery.selected_ids()
        if not ids:
            self.toast("Hãy chọn ảnh trước.", "warning")
            return
        if status == IMG_APPROVED:
            for i in ids:
                self.repo.approve_image(i)
        else:
            self.repo.set_images_status(ids, status)
        self.toast(f"Đã cập nhật {len(ids):,} ảnh.", "success")
        self.ctrl.notify_images_changed()

    def _delete_selected(self) -> None:
        ids = self.gallery.selected_ids()
        if not ids:
            self.toast("Hãy chọn ảnh trước.", "warning")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Xoá ảnh")
        box.setText(f"Xoá {len(ids):,} ảnh khỏi project?")
        box.setInformativeText("Chọn “Yes to All” để xoá luôn file ảnh trên ổ đĩa.")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.YesToAll | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        ret = box.exec()
        if ret == QMessageBox.Cancel:
            return
        n = self.repo.delete_images(ids, remove_files=(ret == QMessageBox.YesToAll))
        self.toast(f"Đã xoá {n:,} ảnh.", "success")
        self.ctrl.notify_images_changed()

    def _cleanup_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        from app.theme import icons

        menu = QMenu(self)
        a_dup = menu.addAction(icons.icon("copy", COLORS["warning"], 16),
                               "Xoá tất cả ảnh trùng")
        a_blur = menu.addAction(icons.icon("alert", COLORS["warning"], 16),
                                "Xoá ảnh mờ dưới ngưỡng")
        a_empty = menu.addAction(icons.icon("image", COLORS["text_dim"], 16),
                                 "Xoá ảnh chưa gán nhãn")
        menu.addSeparator()
        a_missing = menu.addAction(icons.icon("refresh", COLORS["text_dim"], 16),
                                   "Gỡ ảnh không còn tồn tại trên ổ đĩa")
        a_recount = menu.addAction(icons.icon("target", COLORS["text_dim"], 16),
                                   "Tính lại số đối tượng")
        a_backup = menu.addAction(icons.icon("save", COLORS["text_dim"], 16),
                                  "Sao lưu project")
        chosen = menu.exec(self.cleanup_btn.mapToGlobal(
            self.cleanup_btn.rect().bottomLeft()))

        if chosen == a_dup:
            ids = [im.id for im in self.repo.images() if im.is_duplicate]
            self._confirm_delete(ids, "ảnh trùng")
        elif chosen == a_blur:
            thr = cfg.get("extract.blur_threshold", 60.0)
            ids = [im.id for im in self.repo.images() if 0 < im.blur_score < thr]
            self._confirm_delete(ids, f"ảnh mờ (độ nét < {thr:.0f})")
        elif chosen == a_empty:
            ids = [im.id for im in self.repo.images(status=IMG_UNLABELED)]
            self._confirm_delete(ids, "ảnh chưa gán nhãn")
        elif chosen == a_missing:
            n = self.repo.purge_missing()
            self.toast(f"Đã gỡ {n:,} ảnh không còn tồn tại.", "success")
            self.ctrl.notify_images_changed()
        elif chosen == a_recount:
            self.repo.recount_all_images()
            self.toast("Đã tính lại số đối tượng.", "success")
            self.ctrl.notify_images_changed()
        elif chosen == a_backup:
            self.ctrl.backup_project()

    def _confirm_delete(self, ids, what: str) -> None:
        if not ids:
            self.toast(f"Không có {what} nào.", "info")
            return
        if QMessageBox.question(self, "Xác nhận",
                                f"Xoá {len(ids):,} {what}?") != QMessageBox.Yes:
            return
        n = self.repo.delete_images(ids)
        self.toast(f"Đã xoá {n:,} ảnh.", "success")
        self.ctrl.notify_images_changed()

    def on_hide(self) -> None:
        pass
