"""Trang Train: huan luyen lai model Ultralytics ngay trong ung dung."""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config import cfg
from app.constants import COLORS, LABEL_W, MODEL_ZOO
from app.core.inference import available_devices, device_label
from app.core.trainer import TrainConfig
from app.i18n import tr
from app.utils.paths import human_duration
from app.views.pages.base_page import BasePage
from app.views.widgets.charts import LineChart, ProgressRing
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
    label,
    primary_button,
    spin,
)
from app.workers.train_worker import TrainWorker


class TrainPage(BasePage):
    TITLE = tr("nav.train", "Huấn luyện")
    SUBTITLE = tr("train.subtitle", "Huấn luyện lại YOLO trên dataset vừa gán nhãn")
    ICON = "cpu"

    def __init__(self, controller, parent=None) -> None:
        super().__init__(controller, parent, scrollable=False)
        self._start_time = 0.0
        self._epoch = 0
        self._total_epochs = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ================================================================ BUILD ==
    def build(self) -> None:
        self.open_runs_btn = ghost_button(
            tr("train.open_runs", "Mở thư mục huấn luyện"), "folder_open"
        )
        self.open_runs_btn.clicked.connect(self._open_runs)
        self.start_btn = primary_button(tr("train.start", "Bắt đầu huấn luyện"), "play")
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = danger_button(tr("train.stop", "Dừng"), "stop")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setEnabled(False)
        for b in (self.open_runs_btn, self.stop_btn, self.start_btn):
            self.header.add_action(b)

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_settings(), 2)
        row.addWidget(self._build_monitor(), 3)
        self.add(row, 1)

    # ------------------------------------------------------------- settings --
    def _build_settings(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        model_card = Card(tr("train.model_data_tab", "Model & dữ liệu"), "", "cpu")
        self.task_combo = combo(
            [
                ("segment", "Segmentation"),
                ("detect", "Detection"),
                ("obb", tr("autolabel.task_obb", "OBB — hộp xoay")),
                ("pose", tr("autolabel.task_pose", "Pose — điểm khớp")),
            ],
            current=cfg.get("model.task", "segment"),
        )
        self.task_combo.currentIndexChanged.connect(self._reload_models)
        model_card.add(Field(tr("train.task", "Nhiệm vụ"), self.task_combo, label_width=LABEL_W))

        self.model_combo = combo([])
        model_card.add(Field(tr("train.model", "Model"), self.model_combo, label_width=LABEL_W))

        custom_row = QWidget()
        cr = QHBoxLayout(custom_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText(
            tr("train.custom_model_placeholder", "Đường dẫn file .pt / .onnx")
        )
        pick = browse_button()
        pick.clicked.connect(self._choose_model)
        cr.addWidget(self.custom_edit, 1)
        cr.addWidget(pick)
        model_card.add(
            Field(tr("train.custom_model", "Model riêng"), custom_row, label_width=LABEL_W)
        )

        yaml_row = QWidget()
        yr = QHBoxLayout(yaml_row)
        yr.setContentsMargins(0, 0, 0, 0)
        yr.setSpacing(8)
        self.yaml_edit = QLineEdit()
        self.yaml_edit.setPlaceholderText(
            tr("train.yaml_placeholder", "Mặc định: tự sinh dataset.yaml")
        )
        pick_yaml = browse_button()
        pick_yaml.clicked.connect(self._choose_yaml)
        yr.addWidget(self.yaml_edit, 1)
        yr.addWidget(pick_yaml)
        model_card.add(
            Field(tr("train.data_yaml", "File data.yaml"), yaml_row, label_width=LABEL_W)
        )

        self.build_toggle = ToggleSwitch(True)
        r = QHBoxLayout()
        r.addWidget(
            label(
                tr("train.build_dataset", "Tự sinh dataset từ project"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        r.addStretch(1)
        r.addWidget(self.build_toggle)
        model_card.add(r)

        self.approved_toggle = ToggleSwitch(False)
        r2 = QHBoxLayout()
        r2.addWidget(
            label(
                tr("train.approved_only", "Chỉ huấn luyện trên ảnh đã duyệt"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        r2.addStretch(1)
        r2.addWidget(self.approved_toggle)
        model_card.add(r2)
        lay.addWidget(model_card)

        hp_card = Card(tr("train.hyperparameters", "Siêu tham số"), "", "sliders")
        grid = QGridLayout()
        grid.setSpacing(9)
        self.epochs_spin = spin(cfg.get("train.epochs", 100), 1, 5000, 10, width=104)
        self.batch_spin = spin(cfg.get("train.batch", 16), 1, 512, 1, width=104)
        self.imgsz_spin = spin(cfg.get("train.imgsz", 640), 128, 2048, 32, width=104)
        self.patience_spin = spin(cfg.get("train.patience", 50), 0, 1000, 5, width=104)
        self.workers_spin = spin(cfg.get("train.workers", 4), 0, 32, 1, width=104)
        self.lr_spin = dspin(cfg.get("train.lr0", 0.01), 0.00001, 1.0, 0.001, 5, width=104)
        for i, (text, w) in enumerate(
            [
                (tr("train.epochs", "Số epoch"), self.epochs_spin),
                (tr("train.batch_size", "Cỡ batch"), self.batch_spin),
                (tr("train.imgsz", "Cỡ ảnh vào model"), self.imgsz_spin),
                (tr("train.patience", "Patience"), self.patience_spin),
                (tr("train.workers", "Số worker"), self.workers_spin),
                (tr("train.lr0", "Learning rate (lr0)"), self.lr_spin),
            ]
        ):
            grid.addWidget(label(text, size=12, color=COLORS["text_dim"]), i // 2, (i % 2) * 2)
            grid.addWidget(w, i // 2, (i % 2) * 2 + 1)
        hp_card.add(grid)

        self.optimizer_combo = combo(
            [
                ("auto", "Auto"),
                ("SGD", "SGD"),
                ("Adam", "Adam"),
                ("AdamW", "AdamW"),
                ("NAdam", "NAdam"),
                ("RMSProp", "RMSProp"),
            ],
            current=cfg.get("train.optimizer", "auto"),
        )
        hp_card.add(
            Field(tr("train.optimizer", "Optimizer"), self.optimizer_combo, label_width=LABEL_W)
        )
        self.device_combo = combo(available_devices(), current=cfg.get("train.device", "auto"))
        hp_card.add(Field(tr("train.device", "Thiết bị"), self.device_combo, label_width=LABEL_W))
        self.val_slider = SliderField(cfg.get("train.val_split", 0.2), 0.05, 0.5, 2)
        hp_card.add(
            Field(
                tr("train.val_split", "Tỷ lệ tập kiểm định"), self.val_slider, label_width=LABEL_W
            )
        )

        self.aug_toggle = ToggleSwitch(cfg.get("train.augment", True))
        r3 = QHBoxLayout()
        r3.addWidget(
            label(
                tr("train.augment", "Bật tăng cường dữ liệu (Augmentation)"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        r3.addStretch(1)
        r3.addWidget(self.aug_toggle)
        hp_card.add(r3)
        self.cache_toggle = ToggleSwitch(cfg.get("train.cache", False))
        r4 = QHBoxLayout()
        r4.addWidget(
            label(
                tr("train.cache", "Cache ảnh vào RAM để huấn luyện nhanh hơn"),
                size=12,
                color=COLORS["text_dim"],
            )
        )
        r4.addStretch(1)
        r4.addWidget(self.cache_toggle)
        hp_card.add(r4)
        lay.addWidget(hp_card)

        hist_card = Card(tr("train.history_tab", "Lịch sử huấn luyện"), "", "clock")
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(130)
        hist_card.add(self.history_list)
        lay.addWidget(hist_card)
        lay.addStretch(1)

        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(wrap)
        self._reload_models()
        return area

    # -------------------------------------------------------------- monitor --
    def _build_monitor(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(12)

        top = Card(tr("train.progress", "Tiến độ huấn luyện"), "", "target")
        row = QHBoxLayout()
        row.setSpacing(18)
        self.ring = ProgressRing(size=104, thickness=10)
        row.addWidget(self.ring)
        self.progress_info = KeyValueGrid(
            [
                (tr("train.epoch", "Epoch"), "0 / 0"),
                (tr("train.elapsed_time", "Thời gian đã chạy"), "00:00:00"),
                (tr("train.estimated_remaining", "Ước tính còn lại"), "--:--:--"),
                (tr("train.device", "Thiết bị"), device_label(cfg.get("train.device", "auto"))),
                (tr("train.status", "Trạng thái"), tr("common.ready", "Sẵn sàng")),
            ]
        )
        row.addWidget(self.progress_info, 1)
        top.add(row)
        lay.addWidget(top)

        metric_card = Card(
            tr("train.metric_tab", "Chỉ số đánh giá"),
            "mAP / Precision / Recall theo epoch",
            "chart",
        )
        self.metric_chart = LineChart(y_max=1.0)
        self.metric_chart.setMinimumHeight(210)
        metric_card.add(self.metric_chart)
        lay.addWidget(metric_card, 1)

        loss_card = Card(
            tr("train.loss_tab", "Hàm mất mát (Loss)"), "Loss huấn luyện theo epoch", "chart"
        )
        self.loss_chart = LineChart()
        self.loss_chart.setMinimumHeight(180)
        loss_card.add(self.loss_chart)
        lay.addWidget(loss_card, 1)

        log_card = Card(tr("train.log_tab", "Nhật ký huấn luyện"), "", "file")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(190)
        log_card.add(self.log_view)
        lay.addWidget(log_card, 1)

        scroll.setWidget(wrap)
        return scroll

    # ================================================================ LOGIC ==
    def _reload_models(self) -> None:
        task = self.task_combo.currentData()
        self.model_combo.clear()
        for m in MODEL_ZOO.get(task, []):
            self.model_combo.addItem(m, m)
        saved = cfg.get("train.model", "")
        idx = self.model_combo.findData(saved)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _choose_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("train.choose_model", "Chọn file model"), "", "PyTorch (*.pt);;Tất cả file (*)"
        )
        if path:
            self.custom_edit.setText(path)

    def _choose_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("train.choose_yaml", "Chọn file dataset.yaml"), "", "YAML (*.yaml *.yml)"
        )
        if path:
            self.yaml_edit.setText(path)
            self.build_toggle.setChecked(False)

    def _open_runs(self) -> None:
        if not self.repo:
            return
        path = self.repo.sub("runs")
        try:
            os.startfile(str(path))  # noqa: S606
        except Exception:
            self.toast(str(path), "info")

    # ================================================================== RUN ===
    def collect_config(self) -> TrainConfig:
        model = self.custom_edit.text().strip() or self.model_combo.currentData()
        return TrainConfig(
            model=model,
            data_yaml=self.yaml_edit.text().strip(),
            epochs=self.epochs_spin.value(),
            batch=self.batch_spin.value(),
            imgsz=self.imgsz_spin.value(),
            optimizer=self.optimizer_combo.currentData(),
            lr0=self.lr_spin.value(),
            patience=self.patience_spin.value(),
            workers=self.workers_spin.value(),
            device=self.device_combo.currentData(),
            augment=self.aug_toggle.isChecked(),
            cache=self.cache_toggle.isChecked(),
            val_split=self.val_slider.value(),
        )

    def start(self) -> None:
        if not self.ctrl.has_project:
            self.toast(tr("train.no_project", "Chưa mở project"), "warning")
            return
        if self.ctrl.is_running("train"):
            self.toast(tr("train.running", "Đang huấn luyện, vui lòng đợi."), "warning")
            return
        if self.ctrl.is_running("autolabel"):
            self.toast(
                tr(
                    "train.autolabel_conflict",
                    "Đang có tiến trình gán nhãn tự động chạy. Vui lòng dừng hoặc đợi hoàn tất trước khi huấn luyện.",
                ),
                "warning",
            )
            return
        info = self.repo.refresh_stats()
        if info.n_labeled < 2:
            self.toast(
                tr("train.not_enough_data", "Cần tối thiểu 2 ảnh đã gán nhãn để huấn luyện."),
                "warning",
            )
            return

        tcfg = self.collect_config()
        cfg.update_section(
            "train",
            {
                "model": self.model_combo.currentData() or "",
                "epochs": tcfg.epochs,
                "batch": tcfg.batch,
                "imgsz": tcfg.imgsz,
                "optimizer": tcfg.optimizer,
                "lr0": tcfg.lr0,
                "patience": tcfg.patience,
                "workers": tcfg.workers,
                "device": tcfg.device,
                "augment": tcfg.augment,
                "cache": tcfg.cache,
                "val_split": tcfg.val_split,
            },
        )
        cfg.save()

        self.log_view.clear()
        self.metric_chart.clear()
        self.loss_chart.clear()
        self._epoch = 0
        self._total_epochs = tcfg.epochs
        self._start_time = time.time()
        self.ring.set_value(0, "0%")
        self.progress_info.set_value(
            tr("train.status", "Trạng thái"), tr("train.preparing", "Đang chuẩn bị ...")
        )
        self.progress_info.set_value(tr("train.device", "Thiết bị"), device_label(tcfg.device))
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._timer.start()

        worker = TrainWorker(
            self.repo,
            tcfg,
            build_dataset=self.build_toggle.isChecked() or not tcfg.data_yaml,
            val_split=tcfg.val_split,
            only_approved=self.approved_toggle.isChecked(),
            task=self.task_combo.currentData(),
        )
        worker.epoch_metrics.connect(self._on_metrics)
        self.ctrl.run_worker(
            "train",
            worker,
            on_progress=self._on_progress,
            on_stage=lambda s: self.progress_info.set_value(tr("train.status", "Trạng thái"), s),
            on_log=self._log,
            on_done=self._on_done,
            on_fail=self._on_fail,
            on_cancelled=self._on_train_cancelled,
        )

    def stop(self) -> None:
        self.stop_btn.setEnabled(False)
        if not self.ctrl.is_running("train"):
            self._timer.stop()
            self.progress_info.set_value(tr("train.status", "Trạng thái"), "Đã dừng")
            self.start_btn.setEnabled(True)
            return
        self.ctrl.cancel("train")
        self.progress_info.set_value(tr("train.status", "Trạng thái"), "Đang dừng …")
        QTimer.singleShot(3500, self._check_cancel_timeout)

    def _check_cancel_timeout(self) -> None:
        if not self.ctrl.is_running("train"):
            self._on_train_cancelled()
        elif (
            hasattr(self, "progress_info")
            and self.progress_info.get_value(tr("train.status", "Trạng thái")) == "Đang dừng …"
        ):
            w = self.ctrl.worker("train")
            if w and w.isRunning():
                w.stop_and_wait(1000)
            self._on_train_cancelled()

    def _on_train_cancelled(self) -> None:
        self._timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_info.set_value(tr("train.status", "Trạng thái"), "Đã dừng")
        self.toast(tr("trainer.stopped_halfway", "Đã dừng giữa chừng."), "warning")
        self.refresh()

    # ---------------------------------------------------------- cap nhat UI --
    def _on_progress(self, cur: int, total: int, msg: str) -> None:
        if total > 1:
            self.ring.set_value(cur / total, f"{int(100 * cur / total)}%")

    def _on_metrics(self, m) -> None:
        self._epoch = m.epoch
        self._total_epochs = m.total_epochs or self._total_epochs
        self.progress_info.set_value(tr("train.epoch", "Epoch"), f"{m.epoch} / {m.total_epochs}")
        self.metric_chart.append("mAP50", m.map50, COLORS["success"])
        self.metric_chart.append("mAP50-95", m.map5095, COLORS["accent_hi"])
        self.metric_chart.append("Precision", m.precision, COLORS["info"])
        self.metric_chart.append("Recall", m.recall, COLORS["warning"])
        if m.box_loss:
            self.loss_chart.append("box_loss", m.box_loss, COLORS["accent"])
        if m.seg_loss:
            self.loss_chart.append("seg_loss", m.seg_loss, COLORS["success"])
        if m.cls_loss:
            self.loss_chart.append("cls_loss", m.cls_loss, COLORS["danger"])

    def _tick(self) -> None:
        if not self._start_time:
            return
        elapsed = time.time() - self._start_time
        self.progress_info.set_value(
            tr("train.elapsed_time", "Thời gian đã chạy"), human_duration(elapsed)
        )
        if self._epoch > 0 and self._total_epochs > 0:
            per_epoch = elapsed / self._epoch
            remain = per_epoch * (self._total_epochs - self._epoch)
            self.progress_info.set_value(
                tr("train.estimated_remaining", "Ước tính còn lại"), human_duration(remain)
            )

    def _log(self, text: str) -> None:
        self.log_view.appendPlainText(text)
        bar = self.log_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _on_done(self, result) -> None:
        self._timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if result is None or not getattr(result, "ok", False):
            self.progress_info.set_value(tr("train.status", "Trạng thái"), "Đã dừng")
            self.toast(tr("trainer.stopped_halfway", "Đã dừng giữa chừng."), "warning")
            self.refresh()
            return
        self.ring.set_value(1.0, "100%")
        self.progress_info.set_value(tr("train.status", "Trạng thái"), result.message)
        if result.best_weights:
            self._log(f"Best weights: {result.best_weights}")
            self.custom_edit.setText(result.best_weights)
        self.toast(
            f"Huấn luyện xong sau {result.elapsed / 60:.1f} phút — mAP50-95 tốt nhất "
            f"{result.best_map:.3f}.",
            "success",
        )
        self.refresh()

    def _on_fail(self, msg: str) -> None:
        self._timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_info.set_value(tr("train.status", "Trạng thái"), "Thất bại")
        self._log(tr("train.error_log", "LỖI: {msg}", msg=msg))

    # =============================================================== REFRESH ==
    def refresh(self) -> None:
        if not self.repo:
            return
        self.history_list.clear()
        for run in self.repo.train_runs(15):
            status = run.get("status", "")
            icon_color = {
                "done": COLORS["success"],
                "running": COLORS["info"],
                "failed": COLORS["danger"],
            }.get(status, COLORS["text_mute"])
            item = QListWidgetItem(
                f"  {run.get('started', '')}  •  {Path(run.get('model', '')).name}  •  "
                f"{run.get('epochs', 0)} epochs  •  mAP {run.get('best_map', 0):.3f}"
                f"  •  {status}"
            )
            from app.theme import icons

            item.setIcon(icons.icon("cpu", icon_color, 15))
            item.setToolTip(run.get("out_dir", ""))
            self.history_list.addItem(item)

        info = self.repo.refresh_stats()
        self.header.set_subtitle(
            tr(
                "train.header_subtitle",
                "{labeled} ảnh đã gán nhãn   ·   {objects} đối tượng   ·   {classes} lớp",
                labeled=f"{info.n_labeled:,}",
                objects=f"{info.n_objects:,}",
                classes=info.n_classes,
            )
        )
