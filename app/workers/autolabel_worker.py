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
from app.models.entities import Annotation
from app.models.repository import ProjectRepository
from app.plugins.base import PluginContext, registry
from app.workers.base import BaseWorker


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

    def __init__(self, engine: YoloEngine, weights: str, task: str, device: str,
                 parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.weights = weights
        self.task = task
        self.device = device

    def execute(self):
        self.stage.emit("Dang nap model ...")
        self.engine.load(self.weights, self.task, self.device, log_cb=self.emit_log)
        return self.engine


class AutoLabelWorker(BaseWorker):
    """Chay suy luan tren danh sach anh va ghi annotation vao project."""

    preview = Signal(str, object)   # image_path, list[Detection]
    image_done = Signal(int, int, float)   # image_id, n_objects, max_conf

    def __init__(self, repo: ProjectRepository, engine: YoloEngine, image_ids: list[int],
                 infer_cfg: InferenceConfig, review_threshold: float = 0.6,
                 low_conf_threshold: float = 0.35, overwrite: bool = True,
                 plugin_key: str = "", plugin_prompt: str = "",
                 class_name_map: dict | None = None,
                 use_tracking: bool = False, tracker_type: str = "botsort.yaml",
                 parent=None) -> None:
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

    # -------------------------------------------------------------- chay ---
    def execute(self) -> AutoLabelResult:
        res = AutoLabelResult()
        t0 = time.time()
        total = len(self.image_ids)
        if total == 0:
            self.emit_log("Khong co anh nao de gan nhan.")
            return res

        if self.use_tracking:
            self.stage.emit("Sap xep anh theo thu tu frame ...")
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
                self.emit_log(f"Khong tim thay plugin '{self.plugin_key}' - bo qua.")
            else:
                ok, msg = plugin.is_available()
                if not ok:
                    self.emit_log(f"Plugin {plugin.info.name} khong kha dung: {msg}")
                    plugin = None
                else:
                    self.stage.emit(f"Dang nap plugin {plugin.info.name} ...")
                    plugin.load(PluginContext(device=self.engine.device),
                                log_cb=self.emit_log)

        # Dam bao class trong project khop voi class cua model
        self.stage.emit("Dang dong bo danh sach class ...")
        class_lookup = self._sync_classes()

        self.stage.emit("Dang suy luan ...")
        mode_str = f"tracking ({self.tracker_type})" if self.use_tracking else "detect"
        self.emit_log(f"Bat dau auto label {total} anh [{mode_str}] | {self.engine.describe()}")

        for i, image_id in enumerate(self.image_ids):
            if self.cancelled:
                res.cancelled = True
                break
            rec = self.repo.image(image_id)
            if rec is None or not Path(rec.path).exists():
                self.emit_log(f"Bo qua anh khong ton tai (id={image_id})")
                continue
            if not self.overwrite and rec.n_objects > 0:
                continue

            try:
                if self.use_tracking:
                    dets = self.engine.track(rec.path, tracker=self.tracker_type, config=self.cfg, persist=True)
                else:
                    dets = self.engine.predict(rec.path, self.cfg)
            except Exception as exc:
                self.emit_log(f"Loi suy luan {rec.filename}: {exc}")
                continue

            if plugin is not None:
                dets = self._apply_plugin(plugin, rec.path, dets)

            anns, stats = self._to_annotations(image_id, dets, class_lookup)
            self.repo.replace_annotations(image_id, anns)

            status = IMG_REVIEW if stats["need_review"] else IMG_AUTO
            if anns:
                self.repo.set_image_status(image_id, status)
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
            self.emit_progress(
                i + 1, total,
                f"{i + 1}/{total} - {rec.filename} - {len(anns)} doi tuong")

        res.elapsed = time.time() - t0
        self.repo.refresh_stats()
        self.repo.log_history(
            "auto_label", f"{res.n_images} anh, {res.n_objects} doi tuong")
        self.repo.touch()
        self.emit_log(
            f"Xong: {res.n_images} anh | {res.n_objects} doi tuong | "
            f"can review: {res.n_review} | khong co doi tuong: {res.n_empty} | "
            f"{res.fps:.1f} anh/s")
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
                image_path=image_path, image=img, detections=dets,
                class_names=self.engine.class_names, prompt=self.plugin_prompt,
                device=self.engine.device, confidence=self.cfg.confidence,
            )
            out = plugin.annotate(ctx)
            return out if out else dets
        except Exception as exc:
            self.emit_log(f"Plugin loi ({Path(image_path).name}): {exc}")
            return dets

    def _to_annotations(self, image_id: int, dets: list[Detection],
                        class_lookup: dict[int, int]) -> tuple[list[Annotation], dict]:
        anns: list[Annotation] = []
        need_review = False
        low_conf = 0
        max_conf = 0.0
        classes = []

        for d in dets:
            class_id = class_lookup.get(d.class_id)
            if class_id is None:
                name = self.class_name_map.get(
                    d.class_name, d.class_name) or f"class_{d.class_id}"
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
                image_id=image_id, class_id=class_id, class_name=d.class_name,
                shape=SHAPE_POLYGON if len(d.polygon) >= 6 else d.shape,
                bbox=list(d.bbox), polygon=list(d.polygon), keypoints=list(d.keypoints),
                confidence=float(d.confidence), status=status, area=d.area, source="yolo",
                track_id=d.track_id,
            )
            anns.append(ann)

        return anns, {"need_review": need_review, "low_conf": low_conf,
                      "max_conf": max_conf, "classes": classes}


class SingleImageInferWorker(BaseWorker):
    """Suy luan mot anh - dung cho nut 'Auto label anh nay' trong Editor."""

    def __init__(self, engine: YoloEngine, image_path: str,
                 infer_cfg: InferenceConfig, plugin_key: str = "",
                 plugin_prompt: str = "", parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.image_path = image_path
        self.cfg = infer_cfg
        self.plugin_key = plugin_key
        self.plugin_prompt = plugin_prompt

    def execute(self) -> list[Detection]:
        dets = self.engine.predict(self.image_path, self.cfg)
        if self.plugin_key:
            plugin = registry.get(self.plugin_key)
            if plugin is not None:
                ok, msg = plugin.is_available()
                if ok:
                    plugin.load(PluginContext(device=self.engine.device),
                                log_cb=self.emit_log)
                    ctx = PluginContext(
                        image_path=self.image_path, image=imread_unicode(self.image_path),
                        detections=dets, class_names=self.engine.class_names,
                        prompt=self.plugin_prompt, device=self.engine.device,
                        confidence=self.cfg.confidence,
                    )
                    dets = plugin.annotate(ctx) or dets
                else:
                    self.emit_log(f"Plugin khong kha dung: {msg}")
        return dets
