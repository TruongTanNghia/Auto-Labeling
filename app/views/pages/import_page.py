"""Trang Import: nạp video hoặc thư mục ảnh vào project."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.constants import COLORS, PAGE_EXTRACT, VIDEO_EXTS
from app.core.frame_extractor import ExtractConfig, VideoInfo, probe_video
from app.core.importers import DatasetImporter, ImportConfig
from app.i18n import tr
from app.theme import icons
from app.utils.paths import human_duration, human_size, is_image, is_video, scan_images
from app.views.pages.base_page import BasePage
from app.views.widgets.common import (
    Card,
    KeyValueGrid,
    ProgressPanel,
    ToggleSwitch,
    danger_button,
    ghost_button,
    hline,
    label,
    primary_button,
)
from app.workers.extract_worker import ScanFolderWorker
from app.workers.import_worker import ImportWorker

ROLE_KIND = Qt.UserRole
ROLE_VALUE = Qt.UserRole + 1


class ImportPage(BasePage):
    TITLE = tr("nav.import", "Import")
    SUBTITLE = tr("import.subtitle", "Nạp video hoặc thư mục ảnh vào project")
    ICON = "import"
    # Cho phép chọn file trước khi có project; lúc bấm nạp mới hỏi tạo project.
    NEEDS_PROJECT = False

    videosSelected = Signal(list)  # gửi sang trang Frame Extractor
    navigate = Signal(str)

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self.videos: list[str] = []
        self.image_files: list[str] = []
        self._current_info: VideoInfo | None = None

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.add_video_btn = primary_button(tr("import.add_video", "Thêm video"), "video")
        self.add_folder_btn = ghost_button(
            tr("import.add_folder", "Thêm thư mục ảnh"), "folder_open"
        )
        self.add_video_btn.clicked.connect(self.choose_videos)
        self.add_folder_btn.clicked.connect(self.choose_folder)
        self.header.add_action(self.add_folder_btn)
        self.header.add_action(self.add_video_btn)

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._build_left(), 5)
        row.addWidget(self._build_right(), 4)
        self.add(row, 1)

        self.progress = ProgressPanel()
        self.progress.cancelled.connect(lambda: self.ctrl.cancel("scan"))
        self.add(self.progress)

        self.setAcceptDrops(True)
        self._enable_drop_everywhere()
        self._update_counts()

    def _build_left(self) -> QWidget:
        card = Card(
            tr("import.source_card", "Nguồn dữ liệu"),
            tr("import.source_card_sub", "Những gì bạn vừa chọn sẽ hiện ở đây"),
            "layers",
        )

        self.drop_hint = QLabel(
            tr("import.drop_hint", "Kéo thả video, ảnh hoặc cả thư mục vào đây")
        )
        self.drop_hint.setAlignment(Qt.AlignCenter)
        self.drop_hint.setMinimumHeight(46)
        self.drop_hint.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 12.5px;"
            f"border: 1.5px dashed {COLORS['border_hi']}; border-radius: 10px;"
        )
        card.add(self.drop_hint)

        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_list.setMinimumHeight(280)
        self.source_list.currentItemChanged.connect(self._on_source_changed)
        card.add(self.source_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.remove_btn = ghost_button(tr("import.remove_selected", "Bỏ mục đang chọn"), "minus")
        self.clear_btn = danger_button(tr("import.clear_all", "Xoá hết"), "trash")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        self.count_label = label(
            tr("import.count_empty", "Chưa có gì"), size=12, color=COLORS["text_mute"]
        )
        btn_row.addWidget(self.count_label)
        card.add(btn_row)
        return card

    def _build_right(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # --- Xem trước ---
        self.preview_card = Card(tr("import.preview_card", "Xem trước"), "", "image")
        self.preview_label = QLabel(
            tr("import.preview_hint", "Chọn một mục ở bên trái để xem trước")
        )
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setStyleSheet(
            f"background: {COLORS['bg']}; border: 1px solid {COLORS['border']};"
            f"border-radius: 10px; color: {COLORS['text_mute']};"
        )
        self.preview_card.add(self.preview_label, 1)
        self.info_grid = KeyValueGrid()
        self.preview_card.add(self.info_grid)
        lay.addWidget(self.preview_card, 1)

        # --- Bước tiếp theo ---
        action_card = Card(tr("import.next_steps", "Bước tiếp theo"), "", "bolt")
        self.status_label = label("", size=12.5, color=COLORS["text_dim"], wrap=True)
        action_card.add(self.status_label)
        action_card.add(hline())

        self.import_images_btn = primary_button(
            tr("import.btn_import", "Nạp ảnh vào project"), "import"
        )
        self.import_images_btn.clicked.connect(self.import_images)
        action_card.add(self.import_images_btn)

        self.to_extract_btn = primary_button(tr("import.btn_extract", "Cắt frame từ video"), "film")
        self.to_extract_btn.clicked.connect(self._go_extract)
        action_card.add(self.to_extract_btn)

        opt = QVBoxLayout()
        opt.setSpacing(8)
        self.copy_toggle = ToggleSwitch(False)
        self.dedup_toggle = ToggleSwitch(True)
        for text, hint, toggle in (
            (
                tr("import.opt_copy", "Sao chép ảnh vào thư mục project"),
                tr("import.opt_copy_hint", "Giữ nguyên vị trí gốc nếu tắt"),
                self.copy_toggle,
            ),
            (
                tr("import.opt_dedup", "Phát hiện ảnh trùng khi nạp"),
                tr("import.opt_dedup_hint", "So sánh bằng perceptual hash + SSIM"),
                self.dedup_toggle,
            ),
        ):
            r = QHBoxLayout()
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(text, size=12, color=COLORS["text_dim"]))
            col.addWidget(label(hint, size=11, color=COLORS["text_mute"]))
            r.addLayout(col)
            r.addStretch(1)
            r.addWidget(toggle)
            opt.addLayout(r)
        action_card.add(opt)
        lay.addWidget(action_card)

        # --- Nhập dataset có nhãn ---
        lay.addWidget(self._build_dataset_import_card())
        return wrap

    def _build_dataset_import_card(self) -> QWidget:
        self._ds_dir: str = ""
        card = Card(
            tr("import.dataset_card", "Nhập dataset có nhãn"),
            tr("import.dataset_card_sub", "YOLO hoặc COCO đã xuất từ Roboflow, CVAT, labelImg ..."),
            "layers",
        )

        # Dòng chọn thư mục
        dir_row = QHBoxLayout()
        self._ds_path_edit = QLineEdit()
        self._ds_path_edit.setReadOnly(True)
        self._ds_path_edit.setPlaceholderText(
            tr("import.dataset_dir_placeholder", "Chưa chọn thư mục dataset")
        )
        self._ds_path_edit.setStyleSheet(
            f"background:{COLORS['bg']}; border:1px solid {COLORS['border']};"
            f"border-radius:6px; padding:4px 8px; color:{COLORS['text_dim']}; font-size:12px;"
        )
        dir_btn = ghost_button(tr("import.choose_dataset_dir", "Chọn thư mục"), "folder_open")
        dir_btn.clicked.connect(self._choose_dataset_dir)
        dir_row.addWidget(self._ds_path_edit, 1)
        dir_row.addWidget(dir_btn)
        card.add(dir_row)

        # Dropdown định dạng
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(
            label(tr("import.dataset_fmt", "Định dạng:"), size=12, color=COLORS["text_dim"])
        )
        self._ds_fmt_combo = QComboBox()
        self._ds_fmt_combo.addItem("YOLO Segmentation", "yolo_seg")
        self._ds_fmt_combo.addItem("YOLO Detection", "yolo_det")
        self._ds_fmt_combo.addItem("COCO JSON", "coco")
        self._ds_fmt_combo.setStyleSheet(
            f"background:{COLORS['bg']}; border:1px solid {COLORS['border']};"
            f"border-radius:6px; padding:3px 8px; color:{COLORS['text']}; font-size:12px;"
        )
        fmt_row.addWidget(self._ds_fmt_combo)
        fmt_row.addStretch(1)
        card.add(fmt_row)

        # Vùng kết quả xem trước
        self._ds_preview_label = label("", size=12, color=COLORS["text_mute"], wrap=True)
        self._ds_preview_label.setVisible(False)
        card.add(self._ds_preview_label)

        # Nút hành động
        btn_row = QHBoxLayout()
        self._ds_preview_btn = ghost_button(tr("import.dataset_preview", "Xem trước"), "eye")
        self._ds_preview_btn.clicked.connect(self._preview_dataset)
        self._ds_import_btn = primary_button(
            tr("import.dataset_import", "Nhập vào project"), "import"
        )
        self._ds_import_btn.clicked.connect(self._import_dataset)
        btn_row.addWidget(self._ds_preview_btn)
        btn_row.addWidget(self._ds_import_btn)
        btn_row.addStretch(1)
        card.add(btn_row)
        return card

    # ================================================================= DND ==
    def _enable_drop_everywhere(self) -> None:
        """Cho phép thả file lên cả danh sách và vùng xem trước.

        Widget con (QListWidget, QLabel) mặc định "nuốt" sự kiện thả, khiến kéo
        file vào đúng chỗ tự nhiên nhất lại không ăn gì.
        """
        for w in (
            self.source_list,
            self.source_list.viewport(),
            self.preview_label,
            self.drop_hint,
        ):
            w.setAcceptDrops(True)
            w.installEventFilter(self)

    def eventFilter(self, obj, ev):  # noqa: D102
        if ev.type() in (QEvent.DragEnter, QEvent.DragMove):
            if ev.mimeData().hasUrls():
                ev.acceptProposedAction()
                return True
        elif ev.type() == QEvent.Drop:
            if ev.mimeData().hasUrls():
                self.accept_paths([u.toLocalFile() for u in ev.mimeData().urls()])
                ev.acceptProposedAction()
                return True
        return super().eventFilter(obj, ev)

    def dragEnterEvent(self, ev) -> None:  # noqa: D102
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev) -> None:  # noqa: D102
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:  # noqa: D102
        self.accept_paths([u.toLocalFile() for u in ev.mimeData().urls()])
        ev.acceptProposedAction()

    def accept_paths(self, paths) -> None:
        """Nhận danh sách đường dẫn bất kỳ (file hoặc thư mục) và phân loại.

        Có thể được gọi từ cửa sổ chính khi người dùng thả file lúc trang này
        chưa từng mở, nên phải bảo đảm giao diện đã dựng.
        """
        self.ensure_built()
        videos, images, folders = [], [], []
        for p in paths:
            if not p:
                continue
            if Path(p).is_dir():
                folders.append(p)
            elif is_video(p):
                videos.append(p)
            elif is_image(p):
                images.append(p)

        for f in folders:
            images.extend(str(x) for x in scan_images(f))
            videos.extend(str(x) for x in Path(f).rglob("*") if is_video(x))

        if videos:
            self.add_videos(videos)
        if images:
            self.add_images(images)
        if not videos and not images:
            self.toast(
                tr("import.no_files_found", "Không tìm thấy video hoặc ảnh nào trong thứ vừa thả."),
                "warning",
            )

    # ============================================================== ACTIONS ==
    def choose_videos(self) -> None:
        patterns = " ".join(f"*{e}" for e in VIDEO_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("import.choose_videos_title", "Chọn video"),
            "",
            f"Video ({patterns});;Tất cả file (*)",
        )
        if files:
            self.add_videos(files)

    def choose_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, tr("import.choose_folder_title", "Chọn thư mục chứa ảnh")
        )
        if not d:
            return
        found = scan_images(d)
        if not found:
            self.toast(tr("import.folder_no_images", "Thư mục này không chứa ảnh nào."), "warning")
            return
        self.add_images([str(p) for p in found])

    def add_videos(self, paths) -> None:
        added = 0
        for p in paths:
            if p in self.videos:
                continue
            self.videos.append(p)
            info = probe_video(p)
            sub = (
                f"{info.resolution}  ·  {info.fps:g} fps  ·  "
                f"{human_duration(info.duration)}  ·  {human_size(info.size_bytes)}"
                if info
                else tr("import.unreadable_video", "Không đọc được video này")
            )
            item = QListWidgetItem(f"{Path(p).name}\n{sub}")
            item.setIcon(icons.icon("video", COLORS["accent_hi"], 20))
            item.setData(ROLE_KIND, "video")
            item.setData(ROLE_VALUE, p)
            item.setSizeHint(QSize(0, 52))
            item.setToolTip(p)
            self.source_list.addItem(item)
            added += 1
        self._update_counts()
        if added:
            self.toast(
                tr(
                    "import.added_videos",
                    "Đã thêm {count} video. Bước tiếp theo: cắt frame.",
                    count=added,
                ),
                "success",
            )
            self.source_list.setCurrentRow(self.source_list.count() - 1)

    def add_images(self, paths) -> None:
        new = [p for p in paths if p not in self.image_files]
        if not new:
            self.toast(
                tr("import.images_already_in_list", "Những ảnh này đã có trong danh sách rồi."),
                "info",
            )
            return
        self.image_files.extend(new)

        folders: dict[str, int] = {}
        for p in new:
            folders[str(Path(p).parent)] = folders.get(str(Path(p).parent), 0) + 1
        existing = {
            self.source_list.item(i).data(ROLE_VALUE)
            for i in range(self.source_list.count())
            if self.source_list.item(i).data(ROLE_KIND) == "folder"
        }
        for folder, _n in folders.items():
            if folder in existing:
                continue
            total = sum(1 for p in self.image_files if str(Path(p).parent) == folder)
            item = QListWidgetItem(
                f"{Path(folder).name}\n{tr('import.images_count_unit', '{count} ảnh', count=total)}  ·  {folder}"
            )
            item.setIcon(icons.icon("folder_open", COLORS["success"], 20))
            item.setData(ROLE_KIND, "folder")
            item.setData(ROLE_VALUE, folder)
            item.setSizeHint(QSize(0, 52))
            item.setToolTip(folder)
            self.source_list.addItem(item)
        self._update_counts()
        self.toast(tr("import.added_images", "Đã thêm {count} ảnh.", count=len(new)), "success")

    def _remove_selected(self) -> None:
        items = self.source_list.selectedItems()
        if not items:
            self.toast(
                tr("import.select_item_to_remove", "Hãy chọn mục muốn bỏ ở danh sách bên trái."),
                "info",
            )
            return
        for item in items:
            kind, value = item.data(ROLE_KIND), item.data(ROLE_VALUE)
            if kind == "video" and value in self.videos:
                self.videos.remove(value)
            elif kind == "folder":
                self.image_files = [p for p in self.image_files if str(Path(p).parent) != value]
            self.source_list.takeItem(self.source_list.row(item))
        self._update_counts()

    def _clear_all(self) -> None:
        self.source_list.clear()
        self.videos.clear()
        self.image_files.clear()
        self._update_counts()
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText(
            tr("import.preview_hint", "Chọn một mục ở bên trái để xem trước")
        )
        self.info_grid.set_pairs([])

    # ======================================================== TRANG THAI UI ==
    def _update_counts(self) -> None:
        n_v, n_i = len(self.videos), len(self.image_files)
        parts = []
        if n_v:
            parts.append(tr("import.v_count", "{count} video", count=n_v))
        if n_i:
            parts.append(tr("import.i_count", "{count} ảnh", count=f"{n_i:,}"))
        self.count_label.setText(
            "  ·  ".join(parts) if parts else tr("import.count_empty", "Chưa có gì")
        )
        self.drop_hint.setVisible(not parts)

        has_project = self.ctrl.has_project
        self.import_images_btn.setVisible(bool(n_i))
        self.to_extract_btn.setVisible(bool(n_v))
        self.import_images_btn.setEnabled(bool(n_i))
        self.to_extract_btn.setEnabled(bool(n_v))

        # Giải thích rõ bước tiếp theo - đây là chỗ người dùng hay mắc kẹt
        if not n_v and not n_i:
            msg = tr(
                "import.msg_empty",
                "Chưa chọn gì. Dùng nút <b>Thêm video</b> / <b>Thêm thư mục ảnh</b> "
                "ở trên, hoặc kéo thả file vào cửa sổ.",
            )
        elif n_v and not n_i:
            msg = tr(
                "import.msg_only_video",
                "Đã chọn <b>{count} video</b>. Video <u>không</u> nạp thẳng vào project "
                "— phải cắt thành ảnh trước. Bấm <b>Cắt frame từ video</b> để sang bước đó.",
                count=n_v,
            )
        elif n_i and not n_v:
            msg = tr(
                "import.msg_only_images",
                "Đã chọn <b>{count} ảnh</b>. Bấm <b>Nạp ảnh vào project</b> để đưa "
                "vào project và bắt đầu gán nhãn.",
                count=f"{n_i:,}",
            )
        else:
            msg = tr(
                "import.msg_mixed",
                "Đã chọn <b>{count_v} video</b> và <b>{count_i} ảnh</b>. Nạp ảnh trước, "
                "rồi sang bước cắt frame cho video.",
                count_v=n_v,
                count_i=f"{n_i:,}",
            )
        if not has_project:
            msg += tr(
                "import.msg_no_project",
                "<br><span style='color:%s'>Chưa mở project — bấm nút bên dưới sẽ "
                "hỏi tạo project trước.</span>",
                color=COLORS["warning"],
            )
        self.status_label.setText(msg)

    def _go_extract(self) -> None:
        if not self.videos:
            return
        if not self._ensure_project():
            return
        # Sang trang trước để trang đó kịp dựng giao diện, rồi mới đẩy dữ liệu
        self.navigate.emit(PAGE_EXTRACT)
        self.videosSelected.emit(list(self.videos))
        self.toast(tr("import.moved_to_extract", "Đã chuyển video sang trang cắt frame."), "info")

    def _ensure_project(self) -> bool:
        return self.ensure_project()

    # ============================================================= PREVIEW ==
    def _on_source_changed(self, cur, _prev) -> None:
        if cur is None:
            return
        kind, value = cur.data(ROLE_KIND), cur.data(ROLE_VALUE)
        if kind == "video":
            self._preview_video(value)
        else:
            self._preview_folder(value)

    def _preview_video(self, path: str) -> None:
        info = probe_video(path)
        self._current_info = info
        if info is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(tr("import.cannot_open_video", "Không mở được video này"))
            self.info_grid.set_pairs([])
            return
        self._set_preview(_grab_frame(path, info.frame_count // 3 if info.frame_count else 0))
        self.info_grid.set_pairs(
            [
                (tr("import.file_name", "Tên file"), info.filename),
                (tr("import.resolution", "Độ phân giải"), info.resolution),
                (tr("import.fps", "FPS"), f"{info.fps:g}"),
                (tr("import.duration", "Thời lượng"), human_duration(info.duration)),
                (tr("import.total_frames", "Tổng số frame"), f"{info.frame_count:,}"),
                (tr("import.codec", "Codec"), info.codec or "?"),
                (tr("import.file_size", "Dung lượng"), human_size(info.size_bytes)),
            ]
        )

    def _preview_folder(self, folder: str) -> None:
        files = [p for p in self.image_files if str(Path(p).parent) == folder]
        self._current_info = None
        pm = QPixmap(files[0]) if files else QPixmap()
        if files:
            self._set_preview(pm)
        sample = files[:400]
        total_size = 0
        for f in sample:
            try:
                total_size += Path(f).stat().st_size
            except OSError:
                pass
        est = total_size / max(1, len(sample)) * len(files)
        self.info_grid.set_pairs(
            [
                (tr("import.folder_name", "Thư mục"), Path(folder).name),
                (tr("import.image_count", "Số ảnh"), f"{len(files):,}"),
                (
                    tr("import.first_image_size", "Kích thước ảnh đầu"),
                    f"{pm.width()} x {pm.height()}" if not pm.isNull() else "?",
                ),
                (tr("import.est_size", "Dung lượng (ước tính)"), human_size(est)),
            ]
        )

    def _set_preview(self, pm: QPixmap) -> None:
        if pm.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(tr("import.cannot_read_image", "Không đọc được ảnh"))
            return
        self.preview_label.setPixmap(
            pm.scaled(
                max(320, self.preview_label.width() - 12),
                max(180, self.preview_label.height() - 12),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    # ============================================================== IMPORT ==
    def import_images(self) -> None:
        if not self.image_files:
            return
        if not self._ensure_project():
            return
        if self.ctrl.is_running("scan"):
            self.toast(tr("import.loading_wait", "Đang nạp ảnh, vui lòng đợi."), "warning")
            return

        ecfg = ExtractConfig()
        ecfg.remove_similar = self.dedup_toggle.isChecked()
        ecfg.blur_detection = True
        ecfg.lowlight_filter = False
        ecfg.keep_rejected = True  # chỉ đánh dấu, không loại bỏ khi nạp thủ công

        worker = ScanFolderWorker(
            self.ctrl.repo,
            list(self.image_files),
            ecfg,
            copy_into_project=self.copy_toggle.isChecked(),
        )
        self.progress.start(
            tr(
                "import.loading_progress",
                "Đang nạp {count} ảnh vào project ...",
                count=f"{len(self.image_files):,}",
            )
        )
        self.import_images_btn.setEnabled(False)
        self.ctrl.run_worker(
            "scan",
            worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_done=self._on_import_done,
            on_fail=lambda _m: self._update_counts(),
        )

    def _on_import_done(self, result) -> None:
        self.progress.finish(tr("import.done", "Nạp ảnh hoàn tất"))
        if result is None:
            self._update_counts()
            return
        self.toast(tr("import.imported_toast", "Đã nạp ảnh thành công (trùng: {dup}, mờ: {blur}).", dup=result.n_duplicate, blur=result.n_blurry), "success")
        self.image_files.clear()
        for i in reversed(range(self.source_list.count())):
            if self.source_list.item(i).data(ROLE_KIND) == "folder":
                self.source_list.takeItem(i)
        self._update_counts()
        self.ctrl.notify_images_changed()

    # ======================================================= DATASET IMPORT ==
    def _choose_dataset_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, tr("import.choose_dataset_dir_title", "Chọn thư mục dataset")
        )
        if d:
            self._ds_dir = d
            self._ds_path_edit.setText(d)
            self._ds_preview_label.setVisible(False)

    def _preview_dataset(self) -> None:
        if not self._ds_dir:
            self.toast(tr("import.dataset_no_dir", "Hãy chọn thư mục dataset trước."), "warning")
            return
        fmt = self._ds_fmt_combo.currentData()
        cfg = ImportConfig(fmt=fmt, dataset_dir=self._ds_dir)
        info = DatasetImporter(None, cfg).preview()  # type: ignore[arg-type]
        if "error" in info:
            _danger = COLORS["danger"]
            self._ds_preview_label.setText(f"<span style='color:{_danger}'>{info['error']}</span>")
            self._ds_preview_label.setVisible(True)
            return
        lines = [
            tr(
                "import.dataset_preview_images",
                "Số ảnh phát hiện: <b>{n}</b>",
                n=info.get("n_images", 0),
            ),
            tr(
                "import.dataset_preview_anns",
                "Số vùng nhãn: <b>{n}</b>",
                n=info.get("n_annotations", 0),
            ),
            tr(
                "import.dataset_preview_cls_new",
                "Class mới sẽ thêm: <b>{n}</b> &nbsp;·&nbsp; Gộp vào class cũ: <b>{m}</b>",
                n=info.get("n_classes_new", 0),
                m=info.get("n_classes_merge", 0),
            ),
        ]
        self._ds_preview_label.setText("<br>".join(lines))
        self._ds_preview_label.setVisible(True)

    def _import_dataset(self) -> None:
        if not self._ds_dir:
            self.toast(tr("import.dataset_no_dir", "Hãy chọn thư mục dataset trước."), "warning")
            return
        if not self._ensure_project():
            return
        if self.ctrl.is_running("dataset_import"):
            self.toast(tr("import.loading_wait", "Đang nạp ảnh, vui lòng đợi."), "warning")
            return

        fmt = self._ds_fmt_combo.currentData()
        cfg = ImportConfig(
            fmt=fmt,
            dataset_dir=self._ds_dir,
            copy_images=True,
        )
        worker = ImportWorker(self.ctrl.repo, cfg)
        self.progress.start(
            tr(
                "import.dataset_loading",
                "Đang nhập dataset {fmt} ...",
                fmt=self._ds_fmt_combo.currentText(),
            )
        )
        self._ds_import_btn.setEnabled(False)
        self.ctrl.run_worker(
            "dataset_import",
            worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_done=self._on_dataset_import_done,
            on_fail=lambda _m: self._ds_import_btn.setEnabled(True),
        )

    def _on_dataset_import_done(self, result) -> None:
        self._ds_import_btn.setEnabled(True)
        self.progress.finish(tr("import.dataset_done", "Nhập dataset hoàn tất"))
        if result is None:
            return
        msg = tr(
            "import.dataset_result",
            "Đã nhập <b>{n_img} ảnh</b>, <b>{n_ann} vùng nhãn</b>, "
            "{n_cls} class mới. Bỏ qua: {n_skip} ảnh không tìm thấy.",
            n_img=result.n_images,
            n_ann=result.n_annotations,
            n_cls=result.n_classes_added,
            n_skip=result.n_skipped,
        )
        self.toast(msg, "success")
        self.ctrl.notify_images_changed()
        self.ctrl.notify_classes_changed()

    def refresh(self) -> None:
        self._update_counts()


def _grab_frame(path: str, index: int = 0) -> QPixmap:
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return QPixmap()
        if index > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return QPixmap()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QPixmap.fromImage(QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy())
    except Exception:
        return QPixmap()
