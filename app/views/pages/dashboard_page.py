"""Trang Dashboard: tong quan project, thong ke nhanh, thao tac nhanh."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    APP_NAME,
    APP_VERSION,
    COLORS,
    IMG_APPROVED,
    IMG_AUTO,
    IMG_REVIEW,
    IMG_UNLABELED,
    PAGE_AUTOLABEL,
    PAGE_EDITOR,
    PAGE_EXTRACT,
    PAGE_IMPORT,
    PAGE_STATS,
    PAGE_TRAIN,
)
from app.models.repository import PROJECT_DB_NAME
from app.theme import icons
from app.views.pages.base_page import BasePage
from app.views.widgets.charts import DonutChart, ProgressRing, Series, StackedProgress
from app.views.widgets.common import (
    Card,
    Field,
    LegendItem,
    StatCard,
    combo,
    ghost_button,
    hline,
    label,
    primary_button,
    section_label,
)
from app.utils.paths import default_projects_dir, human_size


class DashboardPage(BasePage):
    TITLE = "Dashboard"
    SUBTITLE = "Tổng quan dự án và thao tác nhanh"
    ICON = "dashboard"
    NEEDS_PROJECT = False

    navigate = Signal(str)

    def build(self) -> None:
        self.new_btn = primary_button("Tạo project mới", "plus")
        self.open_btn = ghost_button("Mở project", "folder_open")
        self.new_btn.clicked.connect(self.create_project_dialog)
        self.open_btn.clicked.connect(self.open_project_dialog)
        self.header.add_action(self.open_btn)
        self.header.add_action(self.new_btn)

        self._build_welcome()
        self._build_stats()
        self._build_middle()
        self._build_bottom()
        self.add_stretch()

        self.ctrl.projectOpened.connect(lambda *_: self.refresh())
        self.ctrl.projectClosed.connect(self.refresh)
        self.ctrl.projectChanged.connect(self.refresh)

    # ---------------------------------------------------------- welcome ----
    def _build_welcome(self) -> None:
        card = Card(margins=(20, 18, 20, 18))
        card.setStyleSheet(
            f"#Card {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f" stop:0 {COLORS['accent_soft']}, stop:1 {COLORS['surface']});"
            f" border: 1px solid {COLORS['border_hi']}; border-radius: 16px; }}")
        row = QHBoxLayout()
        row.setSpacing(16)

        col = QVBoxLayout()
        col.setSpacing(5)
        self.welcome_title = label("Chào mừng trở lại!", bold=True, size=19)
        self.welcome_sub = label(
            "Tạo dataset Computer Vision từ video chỉ trong vài bước.",
            size=12.5, color=COLORS["text_dim"])
        col.addWidget(self.welcome_title)
        col.addWidget(self.welcome_sub)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        for text, page, icon_name in (
            ("Nạp video", PAGE_IMPORT, "video"),
            ("Cắt frame", PAGE_EXTRACT, "film"),
            ("Gán nhãn tự động", PAGE_AUTOLABEL, "wand"),
            ("Sửa nhãn", PAGE_EDITOR, "pen"),
            ("Xuất / Huấn luyện", PAGE_TRAIN, "cpu"),
        ):
            b = ghost_button(text, icon_name)
            b.setFixedHeight(31)
            b.clicked.connect(lambda _=False, p=page: self.navigate.emit(p))
            chips.addWidget(b)
        chips.addStretch(1)
        col.addSpacing(6)
        col.addLayout(chips)
        row.addLayout(col, 1)

        self.progress_ring = ProgressRing(size=104, thickness=10)
        ring_box = QVBoxLayout()
        ring_box.setSpacing(4)
        ring_box.addWidget(self.progress_ring, 0, Qt.AlignCenter)
        ring_box.addWidget(label("Tiến độ gán nhãn", size=11,
                                 color=COLORS["text_mute"]), 0, Qt.AlignCenter)
        row.addLayout(ring_box)

        card.add(row)
        self.add(card)

    # ------------------------------------------------------------ stats ----
    def _build_stats(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        self.stat_images = StatCard("image", "0", "Tổng số ảnh", COLORS["accent"])
        self.stat_labeled = StatCard("check_circle", "0", "Đã gán nhãn", COLORS["success"])
        self.stat_objects = StatCard("target", "0", "Đối tượng", COLORS["warning"])
        self.stat_classes = StatCard("layers", "0", "Số lớp", COLORS["info"])
        for i, w in enumerate((self.stat_images, self.stat_labeled,
                               self.stat_objects, self.stat_classes)):
            grid.addWidget(w, 0, i)
        self.stat_images.clicked.connect(lambda: self.navigate.emit("dataset"))
        self.stat_labeled.clicked.connect(lambda: self.navigate.emit(PAGE_EDITOR))
        self.stat_objects.clicked.connect(lambda: self.navigate.emit(PAGE_STATS))
        self.stat_classes.clicked.connect(lambda: self.navigate.emit(PAGE_STATS))
        self.add(grid)

    # ----------------------------------------------------------- middle ----
    def _build_middle(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        # --- Project gan day ---
        self.recent_card = Card("Project gần đây", "Mở lại nhanh công việc đang dở",
                                "clock")
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(212)
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        self.recent_list.customContextMenuRequested.connect(self._recent_menu)
        self.recent_card.add(self.recent_list)
        row.addWidget(self.recent_card, 3)

        # --- Trang thai dataset ---
        self.status_card = Card("Trạng thái dataset", "Phân bố theo tiến độ gán nhãn",
                                "chart")
        self.status_donut = DonutChart(hole=0.66)
        self.status_donut.setMinimumHeight(158)
        self.status_card.add(self.status_donut)
        self.status_bar = StackedProgress(height=9)
        self.status_card.add(self.status_bar)
        self.legends: dict[str, LegendItem] = {}
        for key, text, color in (
            (IMG_APPROVED, "Đã duyệt", COLORS["success"]),
            (IMG_REVIEW, "Cần xem lại", COLORS["warning"]),
            (IMG_AUTO, "Máy gán nhãn", COLORS["info"]),
            (IMG_UNLABELED, "Chưa gán nhãn", COLORS["text_mute"]),
        ):
            item = LegendItem(color, text, "0")
            self.legends[key] = item
            self.status_card.add(item)
        row.addWidget(self.status_card, 2)

        self.add(row)

    # ----------------------------------------------------------- bottom ----
    def _build_bottom(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        # --- He thong ---
        self.system_card = Card("Hệ thống", "Thiết bị dùng để suy luận và huấn luyện", "cpu")
        self.gpu_name = label("...", bold=True, size=13.5)
        self.gpu_detail = label("...", size=11.5, color=COLORS["text_mute"])
        self.system_card.add(self.gpu_name)
        self.system_card.add(self.gpu_detail)
        self.system_card.add(hline())
        self.model_label = label("Model: chưa nạp", size=12, color=COLORS["text_dim"])
        self.system_card.add(self.model_label)
        refresh_btn = ghost_button("Kiểm tra lại thiết bị", "refresh")
        refresh_btn.clicked.connect(self._refresh_device)
        self.system_card.add(refresh_btn)
        self.system_card.add_stretch()
        row.addWidget(self.system_card, 2)

        # --- Hoat dong gan day ---
        self.history_card = Card("Hoạt động gần đây", "Lịch sử thao tác trên project",
                                 "list")
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(170)
        self.history_card.add(self.history_list)
        row.addWidget(self.history_card, 3)

        self.add(row)

    # =============================================================== DATA ===
    def refresh(self) -> None:
        self._refresh_recent()
        self._refresh_device()

        repo = self.repo
        if repo is None:
            self.welcome_title.setText("Chao mung den voi " + APP_NAME)
            self.welcome_sub.setText(
                "Chưa mở project nào. Tạo project mới để bắt đầu.")
            for s in (self.stat_images, self.stat_labeled,
                      self.stat_objects, self.stat_classes):
                s.set_value(0)
            self.progress_ring.set_value(0, "0%")
            self.status_donut.set_data([])
            self.status_bar.set_segments([])
            for lg in self.legends.values():
                lg.set_value("0")
            self.history_list.clear()
            return

        info = repo.refresh_stats()
        self.welcome_title.setText(f"Project: {info.name}")
        desc = info.description or "Chưa có mô tả"
        self.welcome_sub.setText(f"{desc}   ·   Cập nhật: {info.updated_at}")

        self.stat_images.set_value(f"{info.n_images:,}")
        self.stat_labeled.set_value(f"{info.n_labeled:,}")
        self.stat_objects.set_value(f"{info.n_objects:,}")
        self.stat_classes.set_value(info.n_classes)

        pct = info.n_labeled / info.n_images if info.n_images else 0.0
        self.progress_ring.set_value(pct, f"{int(pct * 100)}%")

        counts = repo.status_counts()
        series, segments = [], []
        for key, text, color in (
            (IMG_APPROVED, "Đã duyệt", COLORS["success"]),
            (IMG_REVIEW, "Cần xem lại", COLORS["warning"]),
            (IMG_AUTO, "Máy gán nhãn", COLORS["info"]),
            (IMG_UNLABELED, "Chưa gán nhãn", COLORS["text_mute"]),
        ):
            n = counts.get(key, 0)
            self.legends[key].set_value(f"{n:,}")
            if n:
                series.append(Series(text, n, color))
                segments.append((n, color))
        self.status_donut.set_data(series, f"{info.n_images:,}", "anh")
        self.status_bar.set_segments(segments)

        self.history_list.clear()
        for h in repo.history(30):
            item = QListWidgetItem(f"{h['ts']}   {_action_text(h['action'])}"
                                   + (f" — {h['detail']}" if h["detail"] else ""))
            item.setIcon(icons.icon(_action_icon(h["action"]), COLORS["text_mute"], 15))
            self.history_list.addItem(item)

    def _refresh_recent(self) -> None:
        self.recent_list.clear()
        recents = self.ctrl.recent_projects()
        if not recents:
            item = QListWidgetItem("Chưa có project nào. Bấm 'Tạo project mới' để bắt đầu.")
            item.setFlags(Qt.NoItemFlags)
            self.recent_list.addItem(item)
            return
        for r in recents:
            size = 0
            try:
                size = sum(f.stat().st_size for f in Path(r["dir"]).rglob("*")
                           if f.is_file())
            except Exception:
                pass
            ts = time.strftime("%d/%m/%Y %H:%M", time.localtime(r["mtime"]))
            item = QListWidgetItem(f"  {r['name']}\n  {ts}  •  {human_size(size)}")
            item.setIcon(icons.icon("folder", COLORS["accent_hi"], 20))
            item.setData(Qt.UserRole, r["path"])
            item.setSizeHint(QSize(0, 46))
            item.setToolTip(r["path"])
            self.recent_list.addItem(item)

    def _refresh_device(self) -> None:
        self.ctrl.refresh_device()
        d = self.ctrl.device
        color = COLORS["success"] if d["cuda"] else COLORS["warning"]
        self.gpu_name.setText(self.ctrl.gpu_text())
        self.gpu_name.setStyleSheet(f"font-weight: 700; font-size: 13.5px; color: {color};")
        self.gpu_detail.setText(self.ctrl.gpu_detail())
        eng = self.ctrl.engine
        self.model_label.setText(
            f"Model: {eng.describe()}" if eng.loaded else "Model: chưa nạp")

    # ============================================================= ACTIONS ==
    def create_project_dialog(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, folder, desc, task = dlg.values()
        if not name:
            self.toast("Tên project không được để trống", "error")
            return
        repo = self.ctrl.create_project(name, folder, desc, task)
        if repo:
            self.refresh()

    def open_project_dialog(self) -> None:
        start = cfg.get("general.projects_dir") or str(default_projects_dir())
        path, _ = QFileDialog.getOpenFileName(
            self, "Mở project AutoLabel Studio", start,
            f"Project AutoLabel (*.alsdb);;Tất cả file (*)")
        if not path:
            return
        if self.ctrl.open_project(path):
            self.refresh()

    def _open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path and self.ctrl.open_project(path):
            self.refresh()

    def _recent_menu(self, pos) -> None:
        item = self.recent_list.itemAt(pos)
        if item is None or not item.data(Qt.UserRole):
            return
        path = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_open = menu.addAction(icons.icon("folder_open", COLORS["text_dim"], 16), "Mở")
        act_folder = menu.addAction(icons.icon("folder", COLORS["text_dim"], 16),
                                    "Mở thư mục chứa project")
        menu.addSeparator()
        act_remove = menu.addAction(icons.icon("trash", COLORS["danger"], 16),
                                    "Bỏ khỏi danh sách")
        chosen = menu.exec(self.recent_list.mapToGlobal(pos))
        if chosen == act_open:
            self._open_recent(item)
        elif chosen == act_folder:
            import os
            os.startfile(str(Path(path).parent))  # noqa: S606 - Windows
        elif chosen == act_remove:
            cfg.drop_recent(path)
            self._refresh_recent()


# ================================================================= DIALOG ===
class NewProjectDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tạo project mới")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(13)

        lay.addWidget(label("Tạo project mới", bold=True, size=16))
        lay.addWidget(label(
            "Mỗi project là một thư mục riêng chứa ảnh, nhãn và cơ sở dữ liệu.",
            size=12, color=COLORS["text_mute"], wrap=True))
        lay.addWidget(hline())

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Vi du: Railway Crack Detection")
        lay.addWidget(Field("Tên project", self.name_edit, label_width=118))

        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self.folder_edit = QLineEdit(cfg.get("general.projects_dir")
                                     or str(default_projects_dir()))
        browse = ghost_button("Chọn…", "folder")
        browse.clicked.connect(self._browse)
        fr.addWidget(self.folder_edit, 1)
        fr.addWidget(browse)
        lay.addWidget(Field("Thư mục lưu", folder_row, label_width=118))

        self.task_combo = combo(
            [("segment", "Segmentation — mask polygon"),
             ("detect", "Detection — bounding box"),
             ("obb", "OBB — hộp xoay"),
             ("pose", "Pose — điểm khớp")],
            current=cfg.get("model.task", "segment"))
        lay.addWidget(Field("Loại bài toán", self.task_combo, label_width=118))

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Mô tả ngắn gọn (không bắt buộc)")
        self.desc_edit.setFixedHeight(72)
        lay.addWidget(Field("Mô tả", self.desc_edit, horizontal=False))

        self.path_hint = label("", size=11, color=COLORS["text_mute"])
        lay.addWidget(self.path_hint)
        self.name_edit.textChanged.connect(self._update_hint)
        self.folder_edit.textChanged.connect(self._update_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Tạo project")
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Huỷ")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._update_hint()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu project",
                                             self.folder_edit.text())
        if d:
            self.folder_edit.setText(d)

    def _update_hint(self) -> None:
        name = self.name_edit.text().strip() or "ten-project"
        self.path_hint.setText(f"Sẽ tạo tại: {Path(self.folder_edit.text()) / name}")

    def values(self) -> tuple[str, str, str, str]:
        return (self.name_edit.text().strip(), self.folder_edit.text().strip(),
                self.desc_edit.toPlainText().strip(), self.task_combo.currentData())


# ================================================================ HELPERS ===
_ACTION_TEXT = {
    "create_project": "Tạo project",
    "extract": "Cắt frame từ video",
    "import_images": "Nạp ảnh vào project",
    "auto_label": "Gán nhãn tự động",
    "export": "Xuất dataset",
    "add_class": "Thêm lớp",
    "delete_images": "Xoá ảnh",
}
_ACTION_ICON = {
    "create_project": "plus", "extract": "film", "import_images": "import",
    "auto_label": "wand", "export": "download", "add_class": "layers",
    "delete_images": "trash",
}


def _action_text(action: str) -> str:
    return _ACTION_TEXT.get(action, action)


def _action_icon(action: str) -> str:
    return _ACTION_ICON.get(action, "info")
