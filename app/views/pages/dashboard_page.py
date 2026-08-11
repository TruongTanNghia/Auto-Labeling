"""Trang Dashboard: tong quan project, thong ke nhanh, thao tac nhanh."""

from __future__ import annotations

import re
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
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
from app.i18n import tr
from app.theme import icons
from app.utils.paths import default_projects_dir, human_size
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
)


class DashboardPage(BasePage):
    TITLE = tr("dashboard.title", "Dashboard")
    SUBTITLE = tr("dashboard.subtitle", "Tổng quan dự án và thao tác nhanh")
    ICON = "dashboard"
    NEEDS_PROJECT = False

    navigate = Signal(str)

    def build(self) -> None:
        self.new_btn = primary_button(tr("main.new_project", "Tạo project mới"), "plus")
        self.open_btn = ghost_button(tr("main.open_project", "Mở project"), "folder_open")
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
            f" border: 1px solid {COLORS['border_hi']}; border-radius: 16px; }}"
        )
        row = QHBoxLayout()
        row.setSpacing(16)

        col = QVBoxLayout()
        col.setSpacing(5)
        self.welcome_title = label(
            tr("dashboard.welcome_title", "Chào mừng trở lại!"), bold=True, size=19
        )
        self.welcome_sub = label(
            tr("dashboard.welcome_sub", "Tạo dataset Computer Vision từ video chỉ trong vài bước."),
            size=12.5,
            color=COLORS["text_dim"],
        )
        col.addWidget(self.welcome_title)
        col.addWidget(self.welcome_sub)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        for text, page, icon_name in (
            (tr("dashboard.quick_actions_video", "Nạp video"), PAGE_IMPORT, "video"),
            (tr("dashboard.quick_actions_extract", "Cắt frame"), PAGE_EXTRACT, "film"),
            (tr("dashboard.quick_actions_autolabel", "Gán nhãn tự động"), PAGE_AUTOLABEL, "wand"),
            (tr("dashboard.quick_actions_editor", "Sửa nhãn"), PAGE_EDITOR, "pen"),
            (tr("dashboard.quick_actions_train", "Xuất / Huấn luyện"), PAGE_TRAIN, "cpu"),
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
        ring_box.addWidget(
            label(
                tr("dashboard.project_progress_subtitle", "Tiến độ gán nhãn"),
                size=11,
                color=COLORS["text_mute"],
            ),
            0,
            Qt.AlignCenter,
        )
        row.addLayout(ring_box)

        card.add(row)
        self.add(card)

    # ------------------------------------------------------------ stats ----
    def _build_stats(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        self.stat_images = StatCard(
            "image", "0", tr("dashboard.total_images", "Tổng số ảnh"), COLORS["accent"]
        )
        self.stat_labeled = StatCard(
            "check_circle", "0", tr("dashboard.labeled_images", "Đã gán nhãn"), COLORS["success"]
        )
        self.stat_objects = StatCard(
            "target", "0", tr("dashboard.objects", "Đối tượng"), COLORS["warning"]
        )
        self.stat_classes = StatCard(
            "layers", "0", tr("dashboard.classes", "Số lớp"), COLORS["info"]
        )
        for i, w in enumerate(
            (self.stat_images, self.stat_labeled, self.stat_objects, self.stat_classes)
        ):
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
        self.recent_card = Card(
            tr("dashboard.recent_projects", "Project gần đây"),
            tr("dashboard.recent_projects_subtitle", "Mở lại nhanh công việc đang dở"),
            "clock",
        )
        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(212)
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        self.recent_list.customContextMenuRequested.connect(self._recent_menu)
        self.recent_card.add(self.recent_list)
        row.addWidget(self.recent_card, 3)

        # --- Trang thai dataset ---
        self.status_card = Card(
            tr("dashboard.dataset_stats", "Trạng thái dataset"),
            tr("dashboard.dataset_stats_subtitle", "Phân bố theo tiến độ gán nhãn"),
            "chart",
        )
        self.status_donut = DonutChart(hole=0.66)
        self.status_donut.setMinimumHeight(158)
        self.status_card.add(self.status_donut)
        self.status_bar = StackedProgress(height=9)
        self.status_card.add(self.status_bar)
        self.legends: dict[str, LegendItem] = {}
        for key, text, color in (
            (IMG_APPROVED, tr("status.approved", "Đã duyệt"), COLORS["success"]),
            (IMG_REVIEW, tr("status.review", "Cần xem lại"), COLORS["warning"]),
            (IMG_AUTO, tr("status.auto", "Máy gán nhãn"), COLORS["info"]),
            (IMG_UNLABELED, tr("status.unlabeled", "Chưa gán nhãn"), COLORS["text_mute"]),
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
        self.system_card = Card(
            tr("dashboard.system", "Hệ thống"),
            tr("dashboard.system_subtitle", "Thiết bị dùng để suy luận và huấn luyện"),
            "cpu",
        )
        self.gpu_name = label("...", bold=True, size=13.5)
        self.gpu_detail = label("...", size=11.5, color=COLORS["text_mute"])
        self.system_card.add(self.gpu_name)
        self.system_card.add(self.gpu_detail)
        self.system_card.add(hline())
        self.model_label = label(
            tr("dashboard.model_none", "Model: chưa nạp"), size=12, color=COLORS["text_dim"]
        )
        self.system_card.add(self.model_label)
        refresh_btn = ghost_button(tr("dashboard.check_device", "Kiểm tra lại thiết bị"), "refresh")
        refresh_btn.clicked.connect(self._refresh_device)
        self.system_card.add(refresh_btn)
        self.system_card.add_stretch()
        row.addWidget(self.system_card, 2)

        # --- Hoat dong gan day ---
        self.history_card = Card(
            tr("dashboard.recent_activity", "Hoạt động gần đây"),
            tr("dashboard.recent_activity_subtitle", "Lịch sử thao tác trên project"),
            "list",
        )
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
            self.welcome_title.setText(
                tr("dashboard.welcome_to", "Chào mừng đến với {app}", app=APP_NAME)
            )
            self.welcome_sub.setText(
                tr("dashboard.no_project_desc", "Chưa mở project nào. Tạo project mới để bắt đầu.")
            )
            for s in (self.stat_images, self.stat_labeled, self.stat_objects, self.stat_classes):
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
        desc = info.description or tr("dashboard.no_desc", "Chưa có mô tả")
        self.welcome_sub.setText(
            tr(
                "dashboard.updated_at",
                "{desc}   ·   Cập nhật: {time}",
                desc=desc,
                time=info.updated_at,
            )
        )

        self.stat_images.set_value(f"{info.n_images:,}")
        self.stat_labeled.set_value(f"{info.n_labeled:,}")
        self.stat_objects.set_value(f"{info.n_objects:,}")
        self.stat_classes.set_value(info.n_classes)

        pct = info.n_labeled / info.n_images if info.n_images else 0.0
        self.progress_ring.set_value(pct, f"{int(pct * 100)}%")

        counts = repo.status_counts()
        series, segments = [], []
        for key, text, color in (
            (IMG_APPROVED, tr("status.approved", "Đã duyệt"), COLORS["success"]),
            (IMG_REVIEW, tr("status.review", "Cần xem lại"), COLORS["warning"]),
            (IMG_AUTO, tr("status.auto", "Máy gán nhãn"), COLORS["info"]),
            (IMG_UNLABELED, tr("status.unlabeled", "Chưa gán nhãn"), COLORS["text_mute"]),
        ):
            n = counts.get(key, 0)
            self.legends[key].set_value(f"{n:,}")
            if n:
                series.append(Series(text, n, color))
                segments.append((n, color))
        self.status_donut.set_data(series, f"{info.n_images:,}", tr("dashboard.images_unit", "ảnh"))
        self.status_bar.set_segments(segments)

        self.history_list.clear()
        for h in repo.history(30):
            dt = _detail_text(h["action"], h["detail"])
            item = QListWidgetItem(
                f"{h['ts']}   {_action_text(h['action'])}"
                + (f" — {dt}" if dt else "")
            )
            item.setIcon(icons.icon(_action_icon(h["action"]), COLORS["text_mute"], 15))
            self.history_list.addItem(item)

    def _refresh_recent(self) -> None:
        self.recent_list.clear()
        recents = self.ctrl.recent_projects()
        if not recents:
            item = QListWidgetItem(
                tr(
                    "dashboard.no_recent_projects",
                    "Chưa có project nào. Bấm 'Tạo project mới' để bắt đầu.",
                )
            )
            item.setFlags(Qt.NoItemFlags)
            self.recent_list.addItem(item)
            return
        for r in recents:
            size = 0
            try:
                size = sum(f.stat().st_size for f in Path(r["dir"]).rglob("*") if f.is_file())
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
            tr("dashboard.model_fmt", "Model: {name}", name=eng.describe())
            if eng.loaded
            else tr("dashboard.model_none", "Model: chưa nạp")
        )

    # ============================================================= ACTIONS ==
    def create_project_dialog(self) -> None:
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, folder, desc, task = dlg.values()
        if not name:
            self.toast(tr("dashboard.err_name_empty", "Tên project không được để trống"), "error")
            return
        repo = self.ctrl.create_project(name, folder, desc, task)
        if repo:
            self.refresh()

    def open_project_dialog(self) -> None:
        start = cfg.get("general.projects_dir") or str(default_projects_dir())
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dashboard.open_dialog_title", "Mở project AutoLabel Studio"),
            start,
            tr("dashboard.file_filter_alsdb", "Project AutoLabel (*.alsdb);;Tất cả file (*)"),
        )
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
        act_open = menu.addAction(
            icons.icon("folder_open", COLORS["text_dim"], 16), tr("common.open", "Mở")
        )
        act_folder = menu.addAction(
            icons.icon("folder", COLORS["text_dim"], 16),
            tr("dashboard.open_folder", "Mở thư mục chứa project"),
        )
        menu.addSeparator()
        act_remove = menu.addAction(
            icons.icon("trash", COLORS["danger"], 16),
            tr("dashboard.remove_from_list", "Bỏ khỏi danh sách"),
        )
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
        self.setWindowTitle(tr("dashboard.new_project_title", "Tạo project mới"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(13)

        lay.addWidget(
            label(tr("dashboard.new_project_title", "Tạo project mới"), bold=True, size=16)
        )
        lay.addWidget(
            label(
                tr(
                    "dashboard.new_project_subtitle",
                    "Mỗi project là một thư mục riêng chứa ảnh, nhãn và cơ sở dữ liệu.",
                ),
                size=12,
                color=COLORS["text_mute"],
                wrap=True,
            )
        )
        lay.addWidget(hline())

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            tr("dashboard.project_name_placeholder", "Ví dụ: Railway Crack Detection")
        )
        lay.addWidget(
            Field(tr("dashboard.project_name", "Tên project"), self.name_edit, label_width=118)
        )

        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self.folder_edit = QLineEdit(cfg.get("general.projects_dir") or str(default_projects_dir()))
        browse = ghost_button(tr("common.browse", "Duyệt..."), "folder")
        browse.clicked.connect(self._browse)
        fr.addWidget(self.folder_edit, 1)
        fr.addWidget(browse)
        lay.addWidget(Field(tr("dashboard.save_dir", "Thư mục lưu"), folder_row, label_width=118))

        self.task_combo = combo(
            [
                ("segment", "Segmentation — mask polygon"),
                ("detect", "Detection — bounding box"),
                ("obb", "OBB — hộp xoay"),
                ("pose", "Pose — điểm khớp"),
            ],
            current=cfg.get("model.task", "segment"),
        )
        lay.addWidget(
            Field(tr("dashboard.task_type", "Loại bài toán"), self.task_combo, label_width=118)
        )

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText(
            tr("dashboard.desc_placeholder", "Mô tả ngắn gọn (không bắt buộc)")
        )
        self.desc_edit.setFixedHeight(72)
        lay.addWidget(Field(tr("common.description", "Mô tả"), self.desc_edit, horizontal=False))

        self.path_hint = label("", size=11, color=COLORS["text_mute"])
        lay.addWidget(self.path_hint)
        self.name_edit.textChanged.connect(self._update_hint)
        self.folder_edit.textChanged.connect(self._update_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("dashboard.create_btn", "Tạo project"))
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setText(tr("common.cancel", "Hủy"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._update_hint()

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self,
            tr("dashboard.choose_save_dir", "Chọn thư mục lưu project"),
            self.folder_edit.text(),
        )
        if d:
            self.folder_edit.setText(d)

    def _update_hint(self) -> None:
        name = self.name_edit.text().strip() or "ten-project"
        self.path_hint.setText(
            tr(
                "dashboard.will_create_at",
                "Sẽ tạo tại: {path}",
                path=Path(self.folder_edit.text()) / name,
            )
        )

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.name_edit.text().strip(),
            self.folder_edit.text().strip(),
            self.desc_edit.toPlainText().strip(),
            self.task_combo.currentData(),
        )


# ================================================================ HELPERS ===
_ACTION_ICON = {
    "create_project": "plus",
    "extract": "film",
    "import_images": "import",
    "auto_label": "wand",
    "export": "download",
    "add_class": "layers",
    "delete_images": "trash",
}


def _action_text(action: str) -> str:
    mapping = {
        "create_project": tr("dashboard.action.create_project", "Tạo project"),
        "extract": tr("dashboard.action.extract", "Cắt frame từ video"),
        "import_images": tr("dashboard.action.import_images", "Nạp ảnh vào project"),
        "auto_label": tr("dashboard.action.auto_label", "Gán nhãn tự động"),
        "export": tr("dashboard.action.export", "Xuất dataset"),
        "add_class": tr("dashboard.action.add_class", "Thêm lớp"),
        "delete_images": tr("dashboard.action.delete_images", "Xoá ảnh"),
    }
    return mapping.get(action, action)


def _action_icon(action: str) -> str:
    return _ACTION_ICON.get(action, "info")


def _detail_text(action: str, detail: str) -> str:
    if not detail:
        return ""
    m = re.match(
        r"^(\d+)\s+(?:anh|ảnh|images),\s*(\d+)\s+(?:doi tuong|đối tượng|objects)$",
        detail,
        re.IGNORECASE,
    )
    if m:
        return tr(
            "history.auto_label",
            "{images} ảnh, {objects} đối tượng",
            images=m.group(1),
            objects=m.group(2),
        )
    m = re.match(
        r"^(\d+)\s+(?:anh|ảnh|images)\s+(?:tu|từ|from)\s+(\d+)\s+video(?:|\(s\))$",
        detail,
        re.IGNORECASE,
    )
    if m:
        return tr(
            "history.extract",
            "{saved} ảnh từ {videos} video",
            saved=m.group(1),
            videos=m.group(2),
        )
    m = re.match(r"^(\d+)\s+(?:anh|ảnh|images)$", detail, re.IGNORECASE)
    if m:
        if action == "delete_images":
            return tr("history.delete_images", "{count} ảnh", count=m.group(1))
        return tr("history.import_images", "{saved} ảnh", saved=m.group(1))
    return detail
