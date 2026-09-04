"""Trang Dataset Manager: duyet, loc, don dep va quan ly anh + class."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QMessageBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    COLORS,
    IMG_APPROVED,
    IMG_REVIEW,
    IMG_UNLABELED,
    PAGE_EDITOR,
)
from app.i18n import tr
from app.theme import icons
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
    label,
    primary_button,
)
from app.views.widgets.image_list import ImageGallery


class DatasetPage(BasePage):
    TITLE = tr("nav.dataset", "Dataset Manager")
    SUBTITLE = tr("dataset.subtitle", "Quản lý ảnh, lớp đối tượng, ảnh trùng và ảnh kém chất lượng")
    ICON = "database"

    navigate = Signal(str)

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._filter = "all"
        self._images = []

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.cleanup_btn = ghost_button(tr("dataset.cleanup", "Dọn dẹp"), "sparkle")
        self.cleanup_btn.clicked.connect(self._cleanup_menu)
        self.open_editor_btn = primary_button(tr("dataset.open_editor", "Mở trình sửa nhãn"), "pen")
        self.open_editor_btn.clicked.connect(lambda: self.navigate.emit(PAGE_EDITOR))
        self.header.add_action(self.cleanup_btn)
        self.header.add_action(self.open_editor_btn)

        self._build_stats()
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_gallery(), 5)
        row.addWidget(self._build_side(), 3)
        self.add(row, 1)

        self.ctrl.imagesChanged.connect(self._on_images_changed)
        self.ctrl.classesChanged.connect(self._on_images_changed)

    def _build_stats(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(11)
        self.stat_total = StatCard(
            "image", "0", tr("dataset.total_images", "Tổng số ảnh"), COLORS["accent"]
        )
        self.stat_labeled = StatCard(
            "check_circle", "0", tr("dataset.labeled_images", "Đã gán nhãn"), COLORS["success"]
        )
        self.stat_unlabeled = StatCard(
            "alert", "0", tr("dataset.unlabeled_images", "Chưa gán nhãn"), COLORS["warning"]
        )
        self.stat_objects = StatCard(
            "target", "0", tr("dataset.total_objects", "Tổng đối tượng"), COLORS["info"]
        )
        self.stat_classes = StatCard(
            "layers", "0", tr("dataset.classes_count", "Số lớp"), COLORS["accent_hi"]
        )
        self.stat_dup = StatCard(
            "copy", "0", tr("dataset.duplicate_images", "Ảnh trùng"), COLORS["danger"]
        )
        for w in (
            self.stat_total,
            self.stat_labeled,
            self.stat_unlabeled,
            self.stat_objects,
            self.stat_classes,
            self.stat_dup,
        ):
            row.addWidget(w)
        self.stat_unlabeled.clicked.connect(lambda: self._set_filter("unlabeled"))
        self.stat_dup.clicked.connect(lambda: self._set_filter("duplicate"))
        self.stat_labeled.clicked.connect(lambda: self._set_filter("labeled"))
        self.add(row)

    # -------------------------------------------------------------- gallery --
    def _build_gallery(self) -> QWidget:
        card = Card(tr("dataset.gallery", "Thư viện ảnh"), "", "grid")

        bar = QHBoxLayout()
        bar.setSpacing(7)
        self.filter_buttons = {}
        for key, text in (
            ("all", tr("editor.filter_all", "Tất cả")),
            ("labeled", tr("dataset.labeled_images", "Đã gán nhãn")),
            ("unlabeled", tr("dataset.unlabeled_images", "Chưa gán nhãn")),
            ("review", tr("editor.filter_review", "Cần xem lại")),
            ("approved", tr("editor.filter_approved", "Đã duyệt")),
            ("duplicate", tr("dataset.duplicate_images", "Trùng")),
            ("blurry", "Mờ"),
        ):
            b = chip_button(text)
            b.setChecked(key == "all")
            b.clicked.connect(lambda _c=False, k=key: self._set_filter(k))
            self.filter_buttons[key] = b
            bar.addWidget(b)
        bar.addStretch(1)
        self.search = SearchBox(tr("dataset.search_placeholder", "Tìm theo tên file …"))
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(self.refresh)
        bar.addWidget(self.search)
        self.size_combo = combo(
            [
                (118, tr("dataset.size_small", "Nhỏ")),
                (150, tr("dataset.size_medium", "Vừa")),
                (198, tr("dataset.size_large", "Lớn")),
            ],
            current=150,
        )
        self.size_combo.setFixedWidth(88)
        self.size_combo.currentIndexChanged.connect(
            lambda: self.gallery.set_cell_size(self.size_combo.currentData())
        )
        bar.addWidget(self.size_combo)
        card.add(bar)

        self.gallery = ImageGallery(cell=150)
        self.gallery.imageActivated.connect(self._open_in_editor)
        self.gallery.selectionIds.connect(self._on_selection)
        card.add(self.gallery, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.sel_label = label(
            tr("dataset.no_images_selected", "Chưa chọn ảnh nào"),
            size=11.5,
            color=COLORS["text_mute"],
        )
        actions.addWidget(self.sel_label)
        actions.addStretch(1)
        self.approve_btn = ghost_button(tr("dataset.approve", "Duyệt"), "check")
        self.approve_btn.clicked.connect(lambda: self._mark_status(IMG_APPROVED))
        self.review_btn = ghost_button(tr("dataset.mark_review", "Đánh dấu xem lại"), "alert")
        self.review_btn.clicked.connect(lambda: self._mark_status(IMG_REVIEW))
        self.delete_btn = danger_button(tr("dataset.delete", "Xoá"), "trash")
        self.delete_btn.clicked.connect(self._delete_selected)
        for b in (self.approve_btn, self.review_btn, self.delete_btn):
            b.setVisible(False)
            actions.addWidget(b)
        card.add(actions)
        return card

    # ----------------------------------------------------------------- side --
    def _build_side(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        chart_card = Card(tr("dataset.objects_by_class", "Đối tượng theo lớp"), "", "chart")
        self.class_bar = BarChart(horizontal=True)
        self.class_bar.setMinimumHeight(180)
        chart_card.add(self.class_bar)
        lay.addWidget(chart_card)

        donut_card = Card(tr("dataset.image_ratio_by_class", "Tỷ lệ ảnh theo lớp"), "", "pie")
        self.class_donut = DonutChart()
        self.class_donut.setMinimumHeight(190)
        donut_card.add(self.class_donut)
        lay.addWidget(donut_card)

        table_card = Card(tr("dataset.class_details", "Chi tiết từng lớp"), "", "list")
        self.class_table = QTableWidget(0, 6)
        self.class_table.setHorizontalHeaderLabels(
            [
                tr("dataset.col_class", "Lớp"),
                tr("dataset.col_images", "Ảnh"),
                tr("dataset.col_objects", "Đối tượng"),
                tr("dataset.col_masks", "Mask"),
                tr("dataset.col_avg_area", "Diện tích TB"),
                tr("dataset.col_coverage", "Độ phủ"),
            ]
        )
        self.class_table.verticalHeader().setVisible(False)
        self.class_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.class_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.class_table.setAlternatingRowColors(True)
        self.class_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 6):
            self.class_table.horizontalHeader().setSectionResizeMode(
                c, QHeaderView.ResizeToContents
            )
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

    def on_hide(self) -> None:
        super().on_hide()
        if hasattr(self, "gallery"):
            self._saved_selection = self.gallery.selected_ids()

    def on_project_changed(self) -> None:
        self._saved_selection = []
        self._filter = "all"
        if hasattr(self, "search"):
            self.search.clear()

    def on_show(self) -> None:
        super().on_show()
        if getattr(self, "_needs_refresh", False):
            self.refresh()
        elif getattr(self, "_saved_selection", None):
            self.gallery.select_ids(self._saved_selection)

    def _on_images_changed(self) -> None:
        if not self.isVisible():
            self._needs_refresh = True
            return
        self.refresh()

    def refresh(self) -> None:
        repo = self.repo
        if repo is None:
            return
        self._needs_refresh = False
        self._update_stats_only()

        prev_sel = self.gallery.selected_ids() or getattr(self, "_saved_selection", [])
        self._images = self._filtered_images()
        self.gallery.set_images(self._images, keep_selection=False)
        if prev_sel:
            self.gallery.select_ids(prev_sel)

        stats = repo.class_stats()
        self.class_bar.set_data(
            [Series(s["name"], s["objects"], s["color"]) for s in stats if s["objects"]]
        )
        info = repo.info
        self.class_donut.set_data(
            [Series(s["name"], s["images"], s["color"]) for s in stats if s["images"]],
            f"{info.n_images:,}",
            tr("dashboard.images_unit", "ảnh"),
        )

        self.class_table.setRowCount(len(stats))
        for r, s in enumerate(stats):
            name_item = QTableWidgetItem("  " + s["name"])
            name_item.setForeground(QColor(s["color"]))
            self.class_table.setItem(r, 0, name_item)
            self.class_table.setItem(r, 1, QTableWidgetItem(f"{s['images']:,}"))
            self.class_table.setItem(r, 2, QTableWidgetItem(f"{s['objects']:,}"))
            self.class_table.setItem(r, 3, QTableWidgetItem(f"{s['masks']:,}"))
            self.class_table.setItem(r, 4, QTableWidgetItem(f"{int(s['avg_area']):,} px²"))
            self.class_table.setItem(r, 5, QTableWidgetItem(f"{s['coverage'] * 100:.1f}%"))

        self._on_selection(self.gallery.selected_ids())

    def _update_stats_only(self) -> None:
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

    def _filtered_images(self) -> list:
        if not self.repo:
            return []
        kwargs = {}
        if self._filter == "labeled":
            kwargs["labeled_only"] = True
        elif self._filter == "unlabeled":
            kwargs["status"] = IMG_UNLABELED
        elif self._filter == "review":
            kwargs["status"] = IMG_REVIEW
        elif self._filter == "approved":
            kwargs["status"] = IMG_APPROVED
        elif self._filter == "duplicate":
            kwargs["duplicates_only"] = True
        elif self._filter == "blurry":
            kwargs["blurry_only"] = True
        txt = self.search.text().strip().lower()
        imgs = self.repo.images(**kwargs)
        if txt:
            imgs = [im for im in imgs if txt in Path(im.path).name.lower()]
        return imgs

    def _on_selection(self, ids: list[int]) -> None:
        has_sel = bool(ids)
        if not has_sel:
            self.sel_label.setText(tr("dataset.no_images_selected", "Chưa chọn ảnh nào"))
        else:
            self.sel_label.setText(
                tr("dataset.selected_count", "Đang chọn {count} ảnh", count=f"{len(ids):,}")
            )
        if hasattr(self, "approve_btn"):
            for b in (self.approve_btn, self.review_btn, self.delete_btn):
                b.setVisible(has_sel)

    def _open_in_editor(self, image_id: int) -> None:
        self.ctrl.set_current_image(image_id)
        self.navigate.emit(PAGE_EDITOR)

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

        if self._filter in ("all", "labeled"):
            for i in ids:
                self.gallery.refresh_item(i, status=status)
            self._update_stats_only()
        else:
            self.refresh()

        self.toast(f"Đã cập nhật trạng thái {len(ids)} ảnh.", "success")

    def _delete_selected(self) -> None:
        ids = self.gallery.selected_ids()
        if not ids:
            self.toast("Hãy chọn ảnh trước.", "warning")
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("dataset.delete", "Xoá"))
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
        menu = QMenu(self)
        a_dup = menu.addAction(icons.icon("copy", COLORS["warning"], 16), "Xoá tất cả ảnh trùng")
        a_blur = menu.addAction(
            icons.icon("alert", COLORS["warning"], 16), "Xoá ảnh mờ dưới ngưỡng"
        )
        a_empty = menu.addAction(
            icons.icon("image", COLORS["text_dim"], 16), "Xoá ảnh chưa gán nhãn"
        )
        menu.addSeparator()
        a_missing = menu.addAction(
            icons.icon("refresh", COLORS["text_dim"], 16), "Gỡ ảnh không còn tồn tại trên ổ đĩa"
        )
        a_recount = menu.addAction(
            icons.icon("target", COLORS["text_dim"], 16), "Tính lại số đối tượng"
        )
        a_backup = menu.addAction(icons.icon("save", COLORS["text_dim"], 16), "Sao lưu project")
        chosen = menu.exec(self.cleanup_btn.mapToGlobal(self.cleanup_btn.rect().bottomLeft()))

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
        if QMessageBox.question(self, "Xác nhận", f"Xoá {len(ids):,} {what}?") != QMessageBox.Yes:
            return
        n = self.repo.delete_images(ids)
        self.toast(f"Đã xoá {n:,} ảnh.", "success")
        self.ctrl.notify_images_changed()

    def on_hide(self) -> None:
        pass
