"""Worker: nhap dataset da gan nhan san (YOLO / COCO)."""

from __future__ import annotations

from app.core.importers import DatasetImporter, ImportConfig, ImportResult
from app.models.repository import ProjectRepository
from app.workers.base import BaseWorker


class ImportWorker(BaseWorker):
    def __init__(self, repo: ProjectRepository, config: ImportConfig, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.cfg = config
        self._importer: DatasetImporter | None = None

    def on_cancel(self) -> None:
        if self._importer:
            self._importer.cancel()

    def execute(self) -> ImportResult:
        self.stage.emit("Dang nhap dataset ...")
        self._importer = DatasetImporter(self.repo, self.cfg)
        return self._importer.run(
            progress_cb=lambda c, t, m: self.emit_progress(c, t, m),
            log_cb=self.emit_log,
        )
