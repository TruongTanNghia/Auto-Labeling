"""Controller trung tam - cau noi giua View va Model/Core.

Moi trang UI chi noi chuyen voi controller nay: mo/tao project, chay worker,
phat tin hieu khi du lieu thay doi. Nho vay View khong dung truc tiep vao DB.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from app.config import cfg
from app.core.inference import YoloEngine, device_info, shared_engine
from app.models.entities import ImageRecord
from app.models.repository import PROJECT_DB_NAME, ProjectRepository
from app.utils.logger import get_logger
from app.utils.paths import default_projects_dir, ensure_dir
from app.workers.base import BaseWorker

log = get_logger(__name__)


class AppController(QObject):
    """Trang thai ung dung + dieu phoi tac vu nen."""

    projectOpened = Signal(object)  # ProjectRepository
    projectClosed = Signal()
    projectChanged = Signal()  # du lieu anh/annotation thay doi
    classesChanged = Signal()
    imagesChanged = Signal()
    annotationsChanged = Signal(int)  # image_id
    statusMessage = Signal(str, str)  # text, kind (info/success/warning/error)
    busyChanged = Signal(bool)
    modelChanged = Signal()
    currentImageChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.repo: ProjectRepository | None = None
        self.engine: YoloEngine = shared_engine()
        self._workers: dict[str, BaseWorker] = {}
        self.current_image_id: int = 0
        self.device = device_info()

        self._autosave = QTimer(self)
        self._autosave.timeout.connect(self._do_autosave)
        self._apply_autosave_interval()

    # ============================================================= PROJECT ==
    @property
    def has_project(self) -> bool:
        return self.repo is not None

    def project_name(self) -> str:
        return self.repo.info.name if self.repo else ""

    def create_project(
        self, name: str, parent_dir: str = "", description: str = "", task: str = "segment"
    ) -> ProjectRepository | None:
        parent_dir = parent_dir or cfg.get("general.projects_dir") or str(default_projects_dir())
        root = Path(parent_dir) / _safe_name(name)
        if (root / PROJECT_DB_NAME).exists():
            self.statusMessage.emit(f"Project '{name}' da ton tai o thu muc nay.", "error")
            return None
        try:
            self.close_project()
            ensure_dir(root)
            self.repo = ProjectRepository.create(root, name, description, task)
        except Exception as exc:
            log.exception("Tao project loi")
            self.statusMessage.emit(f"Khong tao duoc project: {exc}", "error")
            return None
        cfg.push_recent(str(root / PROJECT_DB_NAME))
        self.current_image_id = 0
        self.projectOpened.emit(self.repo)
        self.statusMessage.emit(f"Da tao project '{name}'", "success")
        return self.repo

    def open_project(self, path: str) -> ProjectRepository | None:
        try:
            self.close_project()
            self.repo = ProjectRepository.open(path)
        except Exception as exc:
            log.exception("Mo project loi")
            self.statusMessage.emit(f"Khong mo duoc project: {exc}", "error")
            cfg.drop_recent(str(path))
            return None
        cfg.push_recent(str(Path(self.repo.info.db_path)))
        self.current_image_id = 0
        self.projectOpened.emit(self.repo)
        self.statusMessage.emit(f"Da mo project '{self.repo.info.name}'", "success")
        return self.repo

    def close_project(self) -> None:
        self.cancel_all()
        if self.repo is not None:
            try:
                self.repo.touch()
                self.repo.close()
            except Exception:
                pass
            self.repo = None
            self.current_image_id = 0
            self.projectClosed.emit()

    def save_project(self, silent: bool = False) -> None:
        if not self.repo:
            return
        self.repo.touch()
        self.repo.refresh_stats()
        if not silent:
            self.statusMessage.emit("Da luu project", "success")

    def backup_project(self) -> None:
        if not self.repo:
            return
        try:
            dest = self.repo.backup()
            self.statusMessage.emit(f"Da sao luu: {Path(dest).name}", "success")
        except Exception as exc:
            self.statusMessage.emit(f"Sao luu that bai: {exc}", "error")

    def recent_projects(self) -> list[dict]:
        out = []
        for p in cfg.get("general.recent_projects", []):
            path = Path(p)
            if not path.exists():
                continue
            out.append(
                {
                    "path": str(path),
                    "name": path.parent.name,
                    "dir": str(path.parent),
                    "mtime": path.stat().st_mtime,
                }
            )
        return out

    # ============================================================= AUTOSAVE ==
    def _apply_autosave_interval(self) -> None:
        minutes = int(cfg.get("general.autosave_minutes", 5) or 0)
        self._autosave.stop()
        if minutes > 0:
            self._autosave.start(minutes * 60 * 1000)

    def refresh_settings(self) -> None:
        self._apply_autosave_interval()

    def _do_autosave(self) -> None:
        if self.repo is None:
            return
        try:
            self.repo.touch()
            self.repo.backup()
            log.info("Autosave project '%s'", self.repo.info.name)
        except Exception as exc:
            log.warning("Autosave loi: %s", exc)

    # =============================================================== IMAGE ===
    def images(self, **kwargs) -> list[ImageRecord]:
        return self.repo.images(**kwargs) if self.repo else []

    def set_current_image(self, image_id: int) -> None:
        if image_id == self.current_image_id:
            return
        self.current_image_id = image_id
        self.currentImageChanged.emit(image_id)

    def notify_images_changed(self) -> None:
        if self.repo:
            self.repo.refresh_stats()
        self.imagesChanged.emit()
        self.projectChanged.emit()

    def notify_classes_changed(self) -> None:
        if self.repo:
            self.repo.classes(refresh=True)
        self.classesChanged.emit()
        self.projectChanged.emit()

    def notify_annotations_changed(self, image_id: int) -> None:
        if self.repo:
            self.repo.refresh_stats()
        self.annotationsChanged.emit(image_id)
        self.projectChanged.emit()

    # =============================================================== MODEL ===
    def model_ready(self) -> bool:
        return self.engine.loaded

    def refresh_device(self) -> None:
        self.device = device_info()

    def gpu_text(self) -> str:
        d = self.device
        if d["cuda"]:
            return f"GPU: {d['name']}"
        return "CPU (khong phat hien CUDA)"

    def gpu_detail(self) -> str:
        d = self.device
        if d["cuda"]:
            return f"{d['used_gb']:.1f} / {d['total_gb']:.1f} GB  |  CUDA {d['cuda_version']}"
        return f"torch {d['torch'] or 'chua cai'}"

    # ============================================================== WORKER ===
    def run_worker(
        self,
        key: str,
        worker: BaseWorker,
        on_done=None,
        on_fail=None,
        on_progress=None,
        on_log=None,
        on_stage=None,
    ) -> BaseWorker | None:
        """Chay worker, dam bao moi 'key' chi co mot tac vu tai mot thoi diem."""
        old = self._workers.get(key)
        if old is not None and old.isRunning():
            self.statusMessage.emit("Tac vu truoc do van dang chay.", "warning")
            return None

        self._workers[key] = worker
        if on_progress:
            worker.progress.connect(on_progress)
        if on_log:
            worker.message.connect(on_log)
        if on_stage:
            worker.stage.connect(on_stage)

        def _done(result):
            self._workers.pop(key, None)
            self.busyChanged.emit(bool(self.busy))
            if on_done:
                on_done(result)

        def _fail(msg):
            self._workers.pop(key, None)
            self.busyChanged.emit(bool(self.busy))
            self.statusMessage.emit(msg, "error")
            if on_fail:
                on_fail(msg)

        worker.finished_ok.connect(_done)
        worker.failed.connect(_fail)
        worker.finished.connect(worker.deleteLater)
        self.busyChanged.emit(True)
        worker.start()
        return worker

    def worker(self, key: str) -> BaseWorker | None:
        return self._workers.get(key)

    def is_running(self, key: str) -> bool:
        w = self._workers.get(key)
        return bool(w and w.isRunning())

    @property
    def busy(self) -> bool:
        return any(w.isRunning() for w in self._workers.values())

    def cancel(self, key: str) -> None:
        w = self._workers.get(key)
        if w and w.isRunning():
            w.cancel()

    def cancel_all(self) -> None:
        for w in list(self._workers.values()):
            try:
                w.stop_and_wait(4000)
            except Exception:
                pass
        self._workers.clear()
        self.busyChanged.emit(False)

    # ============================================================ SHUTDOWN ===
    def shutdown(self) -> None:
        self.cancel_all()
        try:
            from app.plugins.base import registry

            registry.unload_all()
        except Exception:
            pass
        self.engine.unload()
        self.close_project()
        cfg.save()


def _safe_name(name: str) -> str:
    keep = "-_() "
    out = "".join(c for c in name.strip() if c.isalnum() or c in keep).strip()
    return out or "project"
