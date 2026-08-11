"""Worker: xuat dataset."""

from __future__ import annotations

from app.core.exporters import DatasetExporter, ExportConfig, ExportResult
from app.models.repository import ProjectRepository
from app.workers.base import BaseWorker


class ExportWorker(BaseWorker):
    def __init__(self, repo: ProjectRepository, config: ExportConfig, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.cfg = config
        self._exporter: DatasetExporter | None = None

    def on_cancel(self) -> None:
        if self._exporter:
            self._exporter.cancel()

    def execute(self) -> ExportResult:
        self.stage.emit("Dang xuat dataset ...")
        self._exporter = DatasetExporter(self.repo, self.cfg)
        return self._exporter.run(
            progress_cb=lambda c, t, m: self.emit_progress(c, t, m),
            log_cb=self.emit_log,
        )
