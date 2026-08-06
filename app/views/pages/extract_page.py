"""Trang Frame Extractor: cau hinh cat frame va loc chat luong."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import (
    COLORS,
    LABEL_W,
    EXTRACT_MODES,
    MODE_ADAPTIVE_MOTION,
    MODE_EVERY_FRAME,
    MODE_EVERY_N_FRAMES,
    MODE_EVERY_N_SECONDS,
    MODE_SCENE_DETECT,
    PAGE_AUTOLABEL,
)
from app.core.frame_extractor import ExtractConfig, estimate_output, probe_video
from app.utils.paths import human_duration
from app.views.pages.base_page import BasePage
from app.views.widgets.common import (
    Card,
    Field,
    KeyValueGrid,
    ProgressPanel,
    SliderField,
    ToggleSwitch,
    chip_button,
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
from app.workers.extract_worker import ExtractWorker


class ExtractPage(BasePage):
    TITLE = "Frame Extractor"
    SUBTITLE = "Cắt frame từ video theo nhiều chiến lược và lọc chất lượng"
    ICON = "film"
    # Cho phép cấu hình trước khi có project; lúc bấm chạy mới hỏi tạo project.
    NEEDS_PROJECT = False

    #: gửi id loạt ảnh vừa cắt sang trang Auto Label
    batchReady = Signal(list)
    navigate = Signal(str)

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self.videos: list[str] = []
        self._last_batch: list[int] = []
        self._mode = cfg.get("extract.mode", MODE_EVERY_N_FRAMES)

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.pick_btn = ghost_button("Chọn video", "video")
        self.pick_btn.clicked.connect(self._choose_videos)
        self.start_btn = primary_button("Bắt đầu cắt frame", "play")
        self.start_btn.clicked.connect(self.start)
        self.header.add_action(self.pick_btn)
        self.header.add_action(self.start_btn)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_settings(), 5)
        row.addWidget(self._build_right(), 4)
        self.add(row, 1)

        self.progress = ProgressPanel()
        self.progress.cancelled.connect(lambda: self.ctrl.cancel("extract"))
        self.add(self.progress)
        self._sync_mode_ui()

    # ------------------------------------------------------------ settings --
    def _build_settings(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # ----- Che do cat -----
        mode_card = Card("Chế độ cắt frame", "Chọn chiến lược phù hợp với video",
                         "scissors")
        chips = QGridLayout()
        chips.setSpacing(8)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        icons_map = {
            MODE_EVERY_FRAME: "film", MODE_EVERY_N_FRAMES: "layers",
            MODE_EVERY_N_SECONDS: "clock", MODE_ADAPTIVE_MOTION: "move",
            MODE_SCENE_DETECT: "sparkle",
        }
        for i, (key, text, hint) in enumerate(EXTRACT_MODES):
            b = chip_button(text, icons_map.get(key, "layers"))
            b.setToolTip(hint)
            b.setProperty("mode", key)
            b.setChecked(key == self._mode)
            b.clicked.connect(lambda _c=False, k=key: self._set_mode(k))
            self.mode_group.addButton(b)
            chips.addWidget(b, i // 3, i % 3)
        mode_card.add(chips)
        mode_card.add(hline())

        self.n_frames_spin = spin(cfg.get("extract.every_n_frames", 5), 1, 10000,
                                  suffix=" frame", width=120)
        self.n_seconds_spin = dspin(cfg.get("extract.every_n_seconds", 1.0), 0.02, 600,
                                    0.1, 2, " giây", width=124)
        self.motion_slider = SliderField(cfg.get("extract.motion_threshold", 0.045),
                                         0.005, 0.4, 3, 0.005)
        self.scene_slider = SliderField(cfg.get("extract.scene_threshold", 0.35),
                                        0.05, 0.95, 2, 0.01)

        self.f_n_frames = Field("Lấy 1 frame mỗi", self.n_frames_spin, label_width=LABEL_W)
        self.f_n_seconds = Field("Lấy 1 frame mỗi", self.n_seconds_spin, label_width=LABEL_W)
        self.f_motion = Field("Ngưỡng chuyển động", self.motion_slider, label_width=LABEL_W,
                              hint="Càng thấp càng lấy nhiều frame")
        self.f_scene = Field("Ngưỡng đổi cảnh", self.scene_slider, label_width=LABEL_W,
                             hint="Càng thấp càng nhạy với thay đổi cảnh")
        for f in (self.f_n_frames, self.f_n_seconds, self.f_motion, self.f_scene):
            mode_card.add(f)

        self.max_frames_spin = spin(cfg.get("extract.max_frames", 0), 0, 1000000,
                                    suffix=" ảnh", width=168)
        self.max_frames_spin.setSpecialValueText("Không giới hạn")
        mode_card.add(Field("Giới hạn số ảnh", self.max_frames_spin, label_width=LABEL_W))

        time_row = QWidget()
        tl = QHBoxLayout(time_row)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        self.start_time = dspin(cfg.get("extract.start_time", 0.0), 0, 100000, 1, 1,
                                " s", width=100)
        self.end_time = dspin(cfg.get("extract.end_time", 0.0), 0, 100000, 1, 1,
                              " s", width=124)
        self.end_time.setSpecialValueText("Hết video")
        tl.addWidget(self.start_time)
        tl.addWidget(label("→", color=COLORS["text_mute"]))
        tl.addWidget(self.end_time)
        tl.addStretch(1)
        mode_card.add(Field("Khoảng thời gian", time_row, label_width=LABEL_W))
        lay.addWidget(mode_card)

        # ----- Loc chat luong -----
        filter_card = Card("Lọc chất lượng", "Loại bỏ ảnh trùng và ảnh kém chất lượng",
                           "filter")
        self.dedup_toggle = ToggleSwitch(cfg.get("extract.remove_similar", True))
        self.blur_toggle = ToggleSwitch(cfg.get("extract.blur_detection", True))
        self.dark_toggle = ToggleSwitch(cfg.get("extract.lowlight_filter", False))

        filter_card.add(self._toggle_row(
            "Loại ảnh trùng lặp", self.dedup_toggle,
            "So sánh bằng perceptual hash + SSIM"))
        self.dedup_method = combo(
            [("phash", "pHash — nhanh"), ("ssim", "SSIM — chính xác"),
             ("phash+ssim", "pHash + SSIM — khuyên dùng")],
            current=cfg.get("extract.similarity_method", "phash+ssim"))
        filter_card.add(Field("Phương pháp", self.dedup_method, label_width=LABEL_W))
        self.phash_spin = spin(cfg.get("extract.phash_distance", 6), 0, 32, width=124)
        filter_card.add(Field("Khoảng cách pHash", self.phash_spin, label_width=LABEL_W,
                              hint="Càng nhỏ càng chặt, 0 nghĩa là giống hệt"))
        self.ssim_slider = SliderField(cfg.get("extract.ssim_threshold", 0.965),
                                       0.7, 0.999, 3, 0.001)
        filter_card.add(Field("Ngưỡng SSIM", self.ssim_slider, label_width=LABEL_W))
        filter_card.add(hline())

        filter_card.add(self._toggle_row(
            "Phát hiện ảnh mờ", self.blur_toggle, "Đo độ nét bằng variance of Laplacian"))
        self.blur_spin = dspin(cfg.get("extract.blur_threshold", 60.0), 0, 5000, 5, 1,
                               width=120)
        filter_card.add(Field("Ngưỡng độ nét", self.blur_spin, label_width=LABEL_W))

        filter_card.add(self._toggle_row(
            "Lọc ảnh thiếu sáng", self.dark_toggle, "Độ sáng trung bình 0–255"))
        self.dark_spin = dspin(cfg.get("extract.lowlight_threshold", 45.0), 0, 255, 5, 1,
                               width=120)
        filter_card.add(Field("Ngưỡng độ sáng", self.dark_spin, label_width=LABEL_W))
        lay.addWidget(filter_card)

        # ----- Dau ra -----
        out_card = Card("Đầu ra", "", "save")
        self.format_combo = combo([("jpg", "JPG"), ("png", "PNG")],
                                  current=cfg.get("extract.image_format", "jpg"))
        out_card.add(Field("Định dạng", self.format_combo, label_width=LABEL_W))
        self.quality_slider = SliderField(cfg.get("extract.jpeg_quality", 92), 50, 100, 0, 1)
        out_card.add(Field("Chất lượng JPG", self.quality_slider, label_width=LABEL_W))
        self.resize_spin = spin(cfg.get("extract.resize_long_side", 0), 0, 8192,
                                suffix=" px", width=120)
        self.resize_spin.setSpecialValueText("Giữ nguyên")
        out_card.add(Field("Thu nhỏ cạnh dài", self.resize_spin, label_width=LABEL_W))

        folder_row = QWidget()
        fr = QHBoxLayout(folder_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Mặc định: thư mục frames của project")
        browse = browse_button()
        browse.clicked.connect(self._choose_output)
        fr.addWidget(self.out_edit, 1)
        fr.addWidget(browse)
        out_card.add(Field("Thư mục lưu", folder_row, label_width=LABEL_W))
        lay.addWidget(out_card)
        lay.addStretch(1)

        from PySide6.QtWidgets import QScrollArea
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(wrap)

        for w in (self.n_frames_spin, self.n_seconds_spin, self.max_frames_spin,
                  self.start_time, self.end_time):
            w.valueChanged.connect(self._update_estimate)
        return area

    def _toggle_row(self, text: str, toggle: ToggleSwitch, hint: str = "") -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(text, size=12.5, color=COLORS["text"]))
        if hint:
            col.addWidget(label(hint, size=11, color=COLORS["text_mute"]))
        row.addLayout(col)
        row.addStretch(1)
        row.addWidget(toggle)
        return w

    # --------------------------------------------------------------- right --
    def _build_right(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self.video_card = Card("Video đang xử lý", "", "video")
        self.video_info = KeyValueGrid([("Trạng thái", "Chưa chọn video")])
        self.video_card.add(self.video_info)
        lay.addWidget(self.video_card)

        self.estimate_card = Card("Ước lượng kết quả", "", "target")
        self.estimate_label = label("0", "BigNumber")
        self.estimate_label.setAlignment(Qt.AlignCenter)
        self.estimate_card.add(self.estimate_label)
        self.estimate_hint = label("ảnh sẽ được sinh ra (trước khi lọc)",
                                   size=11.5, color=COLORS["text_mute"])
        self.estimate_hint.setAlignment(Qt.AlignCenter)
        self.estimate_card.add(self.estimate_hint)
        lay.addWidget(self.estimate_card)

        # --- Bước tiếp theo (chỉ hiện sau khi cắt xong) ---
        self.next_step_card = Card("Bước tiếp theo", "", "bolt")
        self.next_step_label = label("", size=12.5, color=COLORS["text_dim"], wrap=True)
        self.next_step_card.add(self.next_step_label)
        self.to_autolabel_btn = primary_button("Gán nhãn tự động cho ảnh vừa cắt", "wand")
        self.to_autolabel_btn.clicked.connect(self._go_autolabel)
        self.next_step_card.add(self.to_autolabel_btn)
        self.next_step_card.setVisible(False)
        lay.addWidget(self.next_step_card)

        self.preview_card = Card("Xem trước frame", "", "image")
        self.preview_label = QLabel("Chưa có frame nào")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(180)
        self.preview_label.setStyleSheet(
            f"background: {COLORS['bg']}; border: 1px solid {COLORS['border']};"
            f"border-radius: 10px; color: {COLORS['text_mute']};")
        self.preview_card.add(self.preview_label)
        lay.addWidget(self.preview_card)

        self.log_card = Card("Nhật ký", "", "file")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(150)
        self.log_card.add(self.log_view)
        lay.addWidget(self.log_card, 1)
        return wrap

    # ================================================================ LOGIC ==
    def set_videos(self, videos: list[str]) -> None:
        """Nhận video từ trang Import.

        Có thể được gọi TRƯỚC khi trang này dựng giao diện (các trang dựng lazy
        ở lần mở đầu tiên), nên chỉ lưu dữ liệu; phần hiển thị để `refresh()`
        lo khi trang thực sự hiện ra.
        """
        self.ensure_built()
        self.videos = list(videos)
        self._update_video_info()
        self._update_estimate()

    def _choose_videos(self) -> None:
        from app.constants import VIDEO_EXTS
        patterns = " ".join(f"*{e}" for e in VIDEO_EXTS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn video", "", f"Video ({patterns});;Tất cả file (*)")
        if files:
            self.set_videos(files)

    def _choose_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu frame")
        if d:
            self.out_edit.setText(d)

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        for b in self.mode_group.buttons():
            b.setChecked(b.property("mode") == mode)
        self._sync_mode_ui()
        self._update_estimate()

    def _sync_mode_ui(self) -> None:
        self.f_n_frames.setVisible(self._mode == MODE_EVERY_N_FRAMES)
        self.f_n_seconds.setVisible(self._mode == MODE_EVERY_N_SECONDS)
        self.f_motion.setVisible(self._mode == MODE_ADAPTIVE_MOTION)
        self.f_scene.setVisible(self._mode == MODE_SCENE_DETECT)

    def _update_video_info(self) -> None:
        if not self.videos:
            self.video_info.set_pairs([("Trạng thái", "Chưa chọn video")])
            return
        if len(self.videos) == 1:
            info = probe_video(self.videos[0])
            if info is None:
                self.video_info.set_pairs([("Lỗi", "Không đọc được video này")])
                return
            self.video_info.set_pairs([
                ("Tên file", info.filename),
                ("Độ phân giải", info.resolution),
                ("FPS", f"{info.fps:g}"),
                ("Thời lượng", human_duration(info.duration)),
                ("Tổng số frame", f"{info.frame_count:,}"),
            ])
        else:
            total_frames = 0
            total_dur = 0.0
            for v in self.videos:
                info = probe_video(v)
                if info:
                    total_frames += info.frame_count
                    total_dur += info.duration
            self.video_info.set_pairs([
                ("Số video", str(len(self.videos))),
                ("Tổng số frame", f"{total_frames:,}"),
                ("Tổng thời lượng", human_duration(total_dur)),
            ])

    def _update_estimate(self, *_args) -> None:
        if not self.videos:
            self.estimate_label.setText("0")
            return
        cfg_obj = self.collect_config()
        total = 0
        for v in self.videos:
            info = probe_video(v)
            if info:
                total += estimate_output(info, cfg_obj)
        self.estimate_label.setText(f"{total:,}")

    # ------------------------------------------------------------- config ---
    def collect_config(self) -> ExtractConfig:
        c = ExtractConfig()
        c.mode = self._mode
        c.every_n_frames = self.n_frames_spin.value()
        c.every_n_seconds = self.n_seconds_spin.value()
        c.motion_threshold = self.motion_slider.value()
        c.scene_threshold = self.scene_slider.value()
        c.max_frames = self.max_frames_spin.value()
        c.start_time = self.start_time.value()
        c.end_time = self.end_time.value()
        c.resize_long_side = self.resize_spin.value()
        c.image_format = self.format_combo.currentData()
        c.jpeg_quality = int(self.quality_slider.value())
        c.remove_similar = self.dedup_toggle.isChecked()
        c.similarity_method = self.dedup_method.currentData()
        c.phash_distance = self.phash_spin.value()
        c.ssim_threshold = self.ssim_slider.value()
        c.blur_detection = self.blur_toggle.isChecked()
        c.blur_threshold = self.blur_spin.value()
        c.lowlight_filter = self.dark_toggle.isChecked()
        c.lowlight_threshold = self.dark_spin.value()
        return c

    def save_config(self) -> None:
        c = self.collect_config()
        cfg.update_section("extract", {
            "mode": c.mode, "every_n_frames": c.every_n_frames,
            "every_n_seconds": c.every_n_seconds, "motion_threshold": c.motion_threshold,
            "scene_threshold": c.scene_threshold, "max_frames": c.max_frames,
            "resize_long_side": c.resize_long_side, "image_format": c.image_format,
            "jpeg_quality": c.jpeg_quality, "remove_similar": c.remove_similar,
            "similarity_method": c.similarity_method, "phash_distance": c.phash_distance,
            "ssim_threshold": c.ssim_threshold, "blur_detection": c.blur_detection,
            "blur_threshold": c.blur_threshold, "lowlight_filter": c.lowlight_filter,
            "lowlight_threshold": c.lowlight_threshold,
            "start_time": c.start_time, "end_time": c.end_time,
        })
        cfg.save()

    # =================================================================== RUN ==
    def start(self) -> None:
        if not self.videos:
            self.toast("Chưa chọn video nào.", "warning")
            return
        if not self.ensure_project():
            return
        if self.ctrl.is_running("extract"):
            self.toast("Đang cắt frame, vui lòng đợi.", "warning")
            return

        self.save_config()
        config = self.collect_config()
        out_dir = self.out_edit.text().strip()

        self.log_view.clear()
        self.progress.start("Đang cắt frame …")
        self.start_btn.setEnabled(False)

        worker = ExtractWorker(self.ctrl.repo, self.videos, config, out_dir)
        worker.preview.connect(self._on_preview)
        self.ctrl.run_worker(
            "extract", worker,
            on_progress=self.progress.set_progress,
            on_stage=self.progress.set_stage,
            on_log=self._append_log,
            on_done=self._on_done,
            on_fail=lambda _m: self.start_btn.setEnabled(True),
        )

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum())

    def _on_preview(self, path: str) -> None:
        pm = QPixmap(path)
        if pm.isNull():
            return
        self.preview_label.setPixmap(pm.scaled(
            self.preview_label.width() or 340, 190, Qt.KeepAspectRatio,
            Qt.SmoothTransformation))

    def _on_done(self, result) -> None:
        self.start_btn.setEnabled(True)
        self.progress.finish("Cắt frame hoàn tất")
        if result is None:
            return
        self._append_log(
            f"KẾT QUẢ: lưu {result.n_saved} ảnh / đọc {result.n_read} frame")
        self.toast(
            f"Đã cắt {result.n_saved:,} ảnh trong {result.elapsed:.0f} giây "
            f"(bỏ {result.n_duplicate} ảnh trùng, {result.n_blurry} ảnh mờ).", "success")
        self.ctrl.notify_images_changed()

        # Lấy đúng id của loạt ảnh vừa cắt để chuyển sang bước gán nhãn
        self._last_batch = self._image_ids_of(result)
        self.next_step_card.setVisible(bool(self._last_batch))
        self.next_step_label.setText(
            f"Đã có <b>{len(self._last_batch):,} ảnh</b> trong project. "
            f"Bước tiếp theo là để AI gán nhãn cho chúng.")

    def _image_ids_of(self, result) -> list[int]:
        """Đổi danh sách file vừa cắt thành id ảnh trong project."""
        if not self.repo or not result or not result.saved:
            return []
        ids = []
        for rec in result.saved:
            if rec.get("rejected"):
                continue
            im = self.repo.image_by_path(rec["path"])
            if im is not None:
                ids.append(im.id)
        return ids

    def _go_autolabel(self) -> None:
        if not self._last_batch:
            return
        self.navigate.emit(PAGE_AUTOLABEL)
        self.batchReady.emit(list(self._last_batch))
        self.toast(f"Đã chọn sẵn {len(self._last_batch):,} ảnh vừa cắt.", "info")

    def refresh(self) -> None:
        self._update_video_info()
        self._update_estimate()
