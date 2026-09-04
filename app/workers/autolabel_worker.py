"""Worker: tu dong gan nhan bang YOLO (+ plugin tinh chinh tuy chon)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Signal

from app.constants import (
    ANN_AUTO,
    ANN_REVIEW,
    IMG_AUTO,
    IMG_REVIEW,
    SHAPE_POLYGON,
)
from app.core.image_quality import imread_unicode
from app.core.inference import Detection, InferenceConfig, YoloEngine
from app.i18n import tr
from app.models.entities import Annotation
from app.models.repository import ProjectRepository
from app.plugins.base import PluginContext, registry
from app.utils.logger import get_logger
from app.workers.base import BaseWorker

log = get_logger(__name__)


@dataclass
class AutoLabelResult:
    n_images: int = 0
    n_objects: int = 0
    n_review: int = 0
    n_low_conf: int = 0
    n_empty: int = 0
    elapsed: float = 0.0
    per_class: dict = field(default_factory=dict)
    cancelled: bool = False

    @property
    def fps(self) -> float:
        return self.n_images / self.elapsed if self.elapsed > 0 else 0.0


class ModelLoadWorker(BaseWorker):
    """Nap model o thread rieng (tai file .pt lan dau co the mat vai chuc giay)."""

    def __init__(
        self, engine: YoloEngine, weights: str, task: str, device: str, parent=None
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.weights = weights
        self.task = task
        self.device = device

    def execute(self):
        self.stage.emit(tr("worker.loading_model", "Đang nạp model ..."))
        self.engine.load(self.weights, self.task, self.device, log_cb=self.emit_log)
        return self.engine


class AutoLabelWorker(BaseWorker):
    """Chay suy luan tren danh sach anh va ghi annotation vao project."""

    preview = Signal(str, object)  # image_path, list[Detection]
    image_done = Signal(int, int, float)  # image_id, n_objects, max_conf

    def __init__(
        self,
        repo: ProjectRepository,
        engine: YoloEngine,
        image_ids: list[int],
        infer_cfg: InferenceConfig,
        review_threshold: float = 0.6,
        low_conf_threshold: float = 0.35,
        overwrite: bool = True,
        plugin_key: str = "",
        plugin_prompt: str = "",
        class_name_map: dict | None = None,
        use_tracking: bool = False,
        tracker_type: str = "botsort.yaml",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self.engine = engine
        self.image_ids = list(image_ids)
        self.cfg = infer_cfg
        self.review_threshold = review_threshold
        self.low_conf_threshold = low_conf_threshold
        self.overwrite = overwrite
        self.plugin_key = plugin_key
        self.plugin_prompt = plugin_prompt
        self.class_name_map = class_name_map or {}
        self.use_tracking = use_tracking
        self.tracker_type = tracker_type
        # Bien theo doi tien do cat lat (cap nhat tu callback)
        self._tile_progress: tuple[int, int] = (0, 1)  # (hien tai, tong so o)

    # -------------------------------------------------------------- chay ---
    def execute(self) -> AutoLabelResult:
        res = AutoLabelResult()
        t0 = time.time()
        total = len(self.image_ids)
        if total == 0:
            self.emit_log(tr("worker.no_images_to_label", "Không có ảnh nào để gán nhãn."))
            return res

        if self.use_tracking:
            self.stage.emit(tr("worker.sorting_frames", "Sắp xếp ảnh theo thứ tự frame ..."))
            # Lay danh sach record de sap xep theo frame_index neu co
            records = [self.repo.image(iid) for iid in self.image_ids]
            records = [r for r in records if r is not None]
            records.sort(key=lambda r: (r.frame_index if r.frame_index >= 0 else 99999999, r.id))
            self.image_ids = [r.id for r in records]
            self.engine.reset_tracker()

        plugin = None
        if self.plugin_key:
            plugin = registry.get(self.plugin_key)
            if plugin is None:
                self.emit_log(
                    tr(
                        "worker.plugin_not_found",
                        "Không tìm thấy plugin '{name}' - bỏ qua.",
                        name=self.plugin_key,
                    )
                )
            else:
                ok, msg = plugin.is_available()
                if not ok:
                    self.emit_log(
                        tr(
                            "worker.plugin_not_available",
                            "Plugin {name} không khả dụng: {msg}",
                            name=plugin.info.name,
                            msg=msg,
                        )
                    )
                    plugin = None
                else:
                    self.stage.emit(
                        tr(
                            "worker.loading_plugin",
                            "Đang nạp plugin {name} ...",
                            name=plugin.info.name,
                        )
                    )
                    plugin.load(PluginContext(device=self.engine.device), log_cb=self.emit_log)

        # Dam bao class trong project khop voi class cua model
        self.stage.emit(tr("worker.syncing_classes", "Đang đồng bộ danh sách class ..."))
        class_lookup = self._sync_classes()

        self.stage.emit(tr("worker.inferring", "Đang suy luận ..."))
        mode_str = f"tracking ({self.tracker_type})" if self.use_tracking else "detect"
        self.emit_log(
            tr(
                "worker.start_autolabel_log",
                "Bắt đầu auto label {total} ảnh [{mode}] | {desc}",
                total=total,
                mode=mode_str,
                desc=self.engine.describe(),
            )
        )

        for i, image_id in enumerate(self.image_ids):
            if self.cancelled:
                res.cancelled = True
                break
            rec = self.repo.image(image_id)
            if rec is None or not Path(rec.path).exists():
                self.emit_log(
                    tr(
                        "worker.skip_missing_image",
                        "Bỏ qua ảnh không tồn tại (id={id})",
                        id=image_id,
                    )
                )
                continue
            if not self.overwrite and rec.n_objects > 0:
                continue

            try:
                if self.use_tracking:
                    dets = self.engine.track(
                        rec.path, tracker=self.tracker_type, config=self.cfg, persist=True
                    )
                elif self.cfg.sahi_enabled:

                    def _tile_cb(tile_idx: int, total_tiles: int, _i=i, _rec=rec) -> None:
                        self._tile_progress = (tile_idx, max(1, total_tiles))
                        # Phat tien do: moi anh chiem mot doan, trong do tung o la mot buoc nho
                        frac = tile_idx / max(1, total_tiles)
                        img_progress = _i + frac
                        self.emit_progress(
                            img_progress,
                            total,
                            f"{_i + 1}/{total} - {_rec.filename} - "
                            + tr(
                                "worker.tile_step",
                                "ô {idx}/{total_tiles}",
                                idx=tile_idx,
                                total_tiles=total_tiles,
                            ),
                        )

                    dets = self.engine.slice_predict(rec.path, self.cfg, progress_cb=_tile_cb)
                else:
                    dets = self.engine.predict(rec.path, self.cfg)
            except Exception as exc:
                self.emit_log(
                    tr(
                        "worker.infer_error",
                        "Lỗi suy luận {filename}: {exc}",
                        filename=rec.filename,
                        exc=exc,
                    )
                )
                continue

            if self.cancelled:
                res.cancelled = True
                break

            if plugin is not None:
                dets = self._apply_plugin(plugin, rec.path, dets)

            if self.cancelled:
                res.cancelled = True
                break

            try:
                anns, stats = self._to_annotations(image_id, dets, class_lookup)
                if self.repo:
                    self.repo.replace_annotations(image_id, anns)

                status = IMG_REVIEW if stats["need_review"] else IMG_AUTO
                if anns and self.repo:
                    self.repo.set_image_status(image_id, status)
            except Exception as exc:
                if self.cancelled:
                    res.cancelled = True
                    break
                log.warning("Loi luu annotation id=%s: %s", image_id, exc)
                continue

            res.n_images += 1
            res.n_objects += len(anns)
            res.n_review += 1 if stats["need_review"] else 0
            res.n_low_conf += stats["low_conf"]
            res.n_empty += 1 if not anns else 0
            for name in stats["classes"]:
                res.per_class[name] = res.per_class.get(name, 0) + 1

            self.image_done.emit(image_id, len(anns), stats["max_conf"])
            if i % 5 == 0 or total < 30:
                self.preview.emit(rec.path, dets)
            prog_text = tr(
                "worker.progress_status",
                "{current}/{total} - {filename} - {objects} đối tượng",
                current=i + 1,
                total=total,
                filename=rec.filename,
                objects=len(anns),
            )
            self.emit_progress(i + 1, total, prog_text)

        res.elapsed = time.time() - t0
        if not self.cancelled and self.repo:
            try:
                self.repo.refresh_stats()
                self.repo.log_history(
                    "auto_label",
                    tr(
                        "history.auto_label",
                        "{images} ảnh, {objects} đối tượng",
                        images=res.n_images,
                        objects=res.n_objects,
                    ),
                )
                self.repo.touch()
                self.emit_log(
                    tr(
                        "worker.done_log",
                        "Xong: {images} ảnh | {objects} đối tượng | cần review: {review} | không có đối tượng: {empty} | {fps:.1f} ảnh/s",
                        images=res.n_images,
                        objects=res.n_objects,
                        review=res.n_review,
                        empty=res.n_empty,
                        fps=res.fps,
                    )
                )
            except Exception:
                pass
        elif self.cancelled:
            if self.repo and res.n_images > 0:
                try:
                    self.repo.refresh_stats()
                    self.repo.touch()
                except Exception:
                    pass
            self.emit_log(tr("worker.autolabel_cancelled_log", "Đã dừng gán nhãn theo yêu cầu."))
        return res

    # ------------------------------------------------------------- helper ---
    def _sync_classes(self) -> dict[int, int]:
        """Map class_id cua model -> class_id trong project.

        Chi anh xa cac class DA co trong project. Class moi duoc tao lazy khi
        thuc su co du doan thuoc class do — tranh viec nap model COCO lam
        project sinh ra ca 80 class rong.
        """
        existing = {c.name.lower(): c for c in self.repo.classes(refresh=True)}
        lookup: dict[int, int] = {}
        for model_id, model_name in self.engine.names.items():
            display = self.class_name_map.get(model_name, model_name)
            cd = existing.get(str(display).lower())
            if cd is not None:
                lookup[int(model_id)] = cd.id
        return lookup

    def _apply_plugin(self, plugin, image_path: str, dets: list[Detection]) -> list[Detection]:
        try:
            img = imread_unicode(image_path)
            ctx = PluginContext(
                image_path=image_path,
                image=img,
                detections=dets,
                class_names=self.engine.class_names,
                prompt=self.plugin_prompt,
                device=self.engine.device,
                confidence=self.cfg.confidence,
            )
            out = plugin.annotate(ctx)
            return out if out else dets
        except Exception as exc:
            self.emit_log(
                tr(
                    "worker.plugin_error",
                    "Plugin lỗi ({filename}): {exc}",
                    filename=Path(image_path).name,
                    exc=exc,
                )
            )
            return dets

    def _to_annotations(
        self, image_id: int, dets: list[Detection], class_lookup: dict[int, int]
    ) -> tuple[list[Annotation], dict]:
        anns: list[Annotation] = []
        need_review = False
        low_conf = 0
        max_conf = 0.0
        classes = []

        for d in dets:
            class_id = class_lookup.get(d.class_id)
            if class_id is None:
                name = self.class_name_map.get(d.class_name, d.class_name) or f"class_{d.class_id}"
                class_id = self.repo.add_class(name).id
                class_lookup[d.class_id] = class_id
            status = ANN_AUTO
            if d.confidence < self.review_threshold:
                status = ANN_REVIEW
                need_review = True
            if d.confidence < self.low_conf_threshold:
                low_conf += 1
            max_conf = max(max_conf, d.confidence)
            classes.append(d.class_name)

            ann = Annotation(
                image_id=image_id,
                class_id=class_id,
                class_name=d.class_name,
                shape=SHAPE_POLYGON if len(d.polygon) >= 6 else d.shape,
                bbox=list(d.bbox),
                polygon=list(d.polygon),
                keypoints=list(d.keypoints),
                confidence=float(d.confidence),
                status=status,
                area=d.area,
                source="yolo",
                track_id=d.track_id,
            )
            anns.append(ann)

        return anns, {
            "need_review": need_review,
            "low_conf": low_conf,
            "max_conf": max_conf,
            "classes": classes,
        }


class SingleImageInferWorker(BaseWorker):
    """Suy luan mot anh - dung cho nut 'Auto label anh nay' trong Editor."""

    def __init__(
        self,
        engine: YoloEngine,
        image_path: str,
        infer_cfg: InferenceConfig,
        plugin_key: str = "",
        plugin_prompt: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.image_path = image_path
        self.cfg = infer_cfg
        self.plugin_key = plugin_key
        self.plugin_prompt = plugin_prompt

    def execute(self) -> list[Detection]:
        if self.cfg.sahi_enabled:
            dets = self.engine.slice_predict(self.image_path, self.cfg)
        else:
            dets = self.engine.predict(self.image_path, self.cfg)
        if self.plugin_key:
            plugin = registry.get(self.plugin_key)
            if plugin is not None:
                ok, msg = plugin.is_available()
                if ok:
                    plugin.load(PluginContext(device=self.engine.device), log_cb=self.emit_log)
                    ctx = PluginContext(
                        image_path=self.image_path,
                        image=imread_unicode(self.image_path),
                        detections=dets,
                        class_names=self.engine.class_names,
                        prompt=self.plugin_prompt,
                        device=self.engine.device,
                        confidence=self.cfg.confidence,
                    )
                    dets = plugin.annotate(ctx) or dets
                else:
                    self.emit_log(
                        tr(
                            "worker.plugin_not_available_msg",
                            "Plugin không khả dụng: {msg}",
                            msg=msg,
                        )
                    )
        return dets
