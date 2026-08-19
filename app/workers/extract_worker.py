"""Worker: cat frame tu video / quet thu muc anh va nap vao project."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal

from app.core.frame_extractor import (
    ExtractConfig,
    ExtractResult,
    FrameExtractor,
    scan_folder_records,
)
from app.i18n import tr
from app.models.repository import ProjectRepository
from app.utils.paths import ensure_dir
from app.workers.base import BaseWorker


class ExtractWorker(BaseWorker):
    """Cat frame tu mot hoac nhieu video, sau do them anh vao project."""

    preview = Signal(str)  # duong dan anh de hien thi xem truoc

    def __init__(
        self,
        repo: ProjectRepository,
        videos: list[str],
        config: ExtractConfig,
        output_dir: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.videos = list(videos)
        self.cfg = config
        self.output_dir = output_dir
        self._extractor: FrameExtractor | None = None

    def on_cancel(self) -> None:
        if self._extractor:
            self._extractor.cancel()

    def execute(self) -> ExtractResult:
        total_result = ExtractResult()
        n_videos = len(self.videos)

        for vi, video in enumerate(self.videos, start=1):
            if self.cancelled:
                break
            name = Path(video).stem
            out_dir = ensure_dir(Path(self.output_dir or (self.repo.sub("frames") / name)))
            if n_videos > 1:
                out_dir = ensure_dir(Path(self.output_dir or self.repo.sub("frames")) / name)

            self.stage.emit(f"Video {vi}/{n_videos}: {Path(video).name}")
            self.emit_log(f"--- [{vi}/{n_videos}] {Path(video).name} ---")

            cfg = self.cfg
            cfg.prefix = name if n_videos > 1 else cfg.prefix
            self._extractor = FrameExtractor(cfg)
            res = self._extractor.extract(
                video,
                out_dir,
                progress_cb=lambda c, t, m: self.emit_progress(c, t, m),
                log_cb=self.emit_log,
                preview_cb=self.preview.emit,
            )

            total_result.saved.extend(res.saved)
            total_result.n_read += res.n_read
            total_result.n_saved += res.n_saved
            total_result.n_duplicate += res.n_duplicate
            total_result.n_blurry += res.n_blurry
            total_result.n_dark += res.n_dark
            total_result.elapsed += res.elapsed
            total_result.output_dir = str(out_dir)
            if res.cancelled:
                total_result.cancelled = True
                break

        if total_result.saved:
            self.stage.emit("Dang ghi vao co so du lieu ...")
            self.emit_log(f"Them {len(total_result.saved)} anh vao project ...")
            self.repo.add_images_bulk(total_result.saved)
            self.repo.refresh_stats()
            self.repo.log_history(
                "extract",
                tr(
                    "history.extract",
                    "{saved} ảnh từ {videos} video",
                    saved=total_result.n_saved,
                    videos=n_videos,
                ),
            )
            self.repo.touch()
        return total_result


class ScanFolderWorker(BaseWorker):
    """Quet thu muc anh co san: do chat luong, danh dau trung, nap vao project."""

    def __init__(
        self,
        repo: ProjectRepository,
        paths: list[str],
        config: ExtractConfig,
        copy_into_project: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.paths = list(paths)
        self.cfg = config
        self.copy = copy_into_project

    def execute(self) -> ExtractResult:
        paths = self.paths
        if self.copy:
            self.stage.emit("Dang sao chep anh vao project ...")
            copied = []
            for i, p in enumerate(paths):
                if self.cancelled:
                    break
                copied.append(str(self.repo.copy_into_project(p)))
                if i % 20 == 0:
                    self.emit_progress(i + 1, len(paths), f"Sao chep {i + 1}/{len(paths)}")
            paths = copied

        self.stage.emit("Dang phan tich chat luong anh ...")
        res = scan_folder_records(
            paths,
            self.cfg,
            progress_cb=lambda c, t, m: self.emit_progress(c, t, m),
            log_cb=self.emit_log,
            cancel_check=lambda: self.cancelled,
        )
        if res.saved:
            self.stage.emit("Dang ghi vao co so du lieu ...")
            self.repo.add_images_bulk(res.saved)
            self.repo.refresh_stats()
            self.repo.log_history(
                "import_images",
                tr("history.import_images", "{saved} ảnh", saved=res.n_saved),
            )
            self.repo.touch()
        self.emit_log(
            f"Da nap {res.n_saved} anh | trung: {res.n_duplicate} | "
            f"mo: {res.n_blurry} | toi: {res.n_dark}"
        )
        return res
