"""Worker: chuan bi dataset roi train mo hinh Ultralytics."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal

from app.core.exporters import DatasetExporter, ExportConfig
from app.core.trainer import EpochMetrics, ModelTrainer, TrainConfig, TrainResult
from app.i18n import tr
from app.models.repository import ProjectRepository
from app.workers.base import BaseWorker


class TrainWorker(BaseWorker):
    """Tu dong build dataset YOLO tu project (neu can) roi goi train."""

    epoch_metrics = Signal(object)  # EpochMetrics

    #: loai bai toan -> dinh dang dataset YOLO tuong ung
    TASK_FORMAT = {
        "segment": "yolo_seg",
        "detect": "yolo_det",
        "obb": "yolo_obb",
        "pose": "yolo_pose",
    }

    def __init__(
        self,
        repo: ProjectRepository,
        config: TrainConfig,
        build_dataset: bool = True,
        val_split: float = 0.2,
        test_split: float = 0.0,
        only_approved: bool = False,
        task: str = "segment",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.cfg = config
        self.build_dataset = build_dataset
        self.val_split = val_split
        self.test_split = test_split
        self.only_approved = only_approved
        self.task = task
        self._trainer: ModelTrainer | None = None
        self._exporter: DatasetExporter | None = None
        self.run_id = 0

    def on_cancel(self) -> None:
        if self._exporter:
            self._exporter.cancel()
        if self._trainer:
            self._trainer.cancel()

    def execute(self) -> TrainResult:
        if self.build_dataset or not self.cfg.data_yaml:
            self.stage.emit(tr("worker.building_yolo_ds", "Đang dựng dataset YOLO ..."))
            self.emit_log(
                tr("worker.prep_dataset_log", "Chuẩn bị dataset train/val từ project ...")
            )
            ds_dir = self.repo.sub("runs") / "dataset"
            ecfg = ExportConfig(
                fmt=self.TASK_FORMAT.get(self.task, "yolo_seg"),
                output_dir=str(ds_dir.parent),
                dataset_name=ds_dir.name,
                val_split=self.val_split,
                test_split=self.test_split,
                train_split=max(0.05, 1.0 - self.val_split - self.test_split),
                only_approved=self.only_approved,
                copy_images=True,
                write_yaml=True,
            )
            self._exporter = DatasetExporter(self.repo, ecfg)
            eres = self._exporter.run(
                progress_cb=lambda c, t, m: self.emit_progress(c, t, f"Dataset: {m}"),
                log_cb=self.emit_log,
            )
            if self.cancelled:
                return TrainResult(
                    ok=False, message=tr("worker.cancelled_before_train", "Đã huỷ trước khi train.")
                )
            self.cfg.data_yaml = eres.yaml_path
            self.emit_log(
                tr(
                    "worker.dataset_prepared_log",
                    "Dataset: {images} ảnh, {objects} đối tượng.",
                    images=eres.n_images,
                    objects=eres.n_objects,
                )
            )

        if not self.cfg.project_dir:
            self.cfg.project_dir = str(self.repo.sub("runs"))
        self.cfg.run_name = _next_run_name(Path(self.cfg.project_dir))

        self.run_id = self.repo.start_train_run(
            self.cfg.model,
            self.cfg.epochs,
            {
                "batch": self.cfg.batch,
                "imgsz": self.cfg.imgsz,
                "optimizer": self.cfg.optimizer,
                "lr0": self.cfg.lr0,
            },
            str(Path(self.cfg.project_dir) / self.cfg.run_name),
        )

        self.stage.emit(tr("worker.training", "Đang train ..."))
        self._trainer = ModelTrainer(self.cfg)
        try:
            result = self._trainer.run(
                progress_cb=lambda c, t, m: self.emit_progress(c, t, m),
                log_cb=self.emit_log,
                metric_cb=self._on_metric,
            )
        except Exception:
            self.repo.finish_train_run(self.run_id, 0.0, "failed")
            raise

        self.repo.finish_train_run(
            self.run_id, result.best_map, "cancelled" if self.cancelled else "done"
        )
        if result.best_weights:
            self.repo.set_meta("last_best_weights", result.best_weights)
        return result

    def _on_metric(self, m: EpochMetrics) -> None:
        self.epoch_metrics.emit(m)


def _next_run_name(project_dir: Path) -> str:
    project_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in project_dir.iterdir() if p.is_dir()}
    i = 1
    while f"train{i}" in existing:
        i += 1
    return f"train{i}"
