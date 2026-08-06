"""Plugin SAM 3 Concept - gan nhan theo mo ta bang van ban (open-vocabulary).

Diem moi cua SAM 3 so voi SAM 2: thay vi chi segment MOT doi tuong theo box/point,
no tim va segment TAT CA doi tuong khop voi mot khai niem mo ta bang chu.
Vi du prompt "crack" se sinh mask cho moi vet nut trong anh ma khong can train.

Yeu cau:
  - ultralytics >= 8.3.237
  - file sam3.pt dat trong thu muc weights (Meta yeu cau xin quyen tren Hugging Face,
    khong tai tu dong duoc)
"""
from __future__ import annotations

import numpy as np

from app.constants import SHAPE_BBOX, SHAPE_POLYGON
from app.core.inference import Detection, mask_to_polygons, resolve_device
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo
from app.plugins.builtin.sam_refiner import ultralytics_version

MIN_VERSION = (8, 3, 237)


class Sam3ConceptPlugin(AnnotatorPlugin):
    info = PluginInfo(
        key="sam3_concept",
        name="SAM 3 Concept (prompt van ban)",
        version="1.0",
        author="AutoLabel Studio AI",
        description=(
            "Sinh annotation cho TAT CA doi tuong khop voi mot khai niem mo ta bang chu, "
            "khong can train truoc. Vi du prompt: 'crack, rust, bolt'.\n\n"
            "Khac voi SAM 2 (chi bam theo box/point ban dua vao), SAM 3 tu tim doi tuong "
            "theo nghia cua tu. Dung khi ban co lop doi tuong ma YOLO COCO khong biet."
        ),
        requires=["ultralytics", "torch"],
        kind="generate",
        accepts_prompt=True,
        homepage="https://docs.ultralytics.com/models/sam-3/",
    )

    WEIGHTS = "sam3.pt"

    def default_config(self) -> dict:
        return {"weights": self.WEIGHTS, "min_area": 40, "simplify": 0.002}

    # -------------------------------------------------------------- trang thai --
    def is_available(self) -> tuple[bool, str]:
        ok, msg = super().is_available()
        if not ok:
            return ok, msg

        ver = ultralytics_version()
        if ver < MIN_VERSION:
            have = ".".join(str(v) for v in ver)
            need = ".".join(str(v) for v in MIN_VERSION)
            return False, (f"Can ultralytics >= {need} (dang co {have}). "
                           f"Nang cap: pip install -U ultralytics")
        try:
            from ultralytics.models.sam import SAM3SemanticPredictor  # noqa: F401
        except Exception:
            return False, "Ban ultralytics nay khong co SAM3SemanticPredictor"

        from app.utils.paths import weights_dir
        if not (weights_dir() / self.config("weights", self.WEIGHTS)).exists():
            return False, (f"Chua co {self.WEIGHTS} trong {weights_dir()} - "
                           f"Meta yeu cau xin quyen tren Hugging Face roi tai thu cong")
        return True, "San sang"

    # ------------------------------------------------------------------- nap --
    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        ok, msg = self.is_available()
        if not ok:
            raise RuntimeError(msg)

        from ultralytics.models.sam import SAM3SemanticPredictor

        from app.utils.paths import weights_dir

        path = weights_dir() / self.config("weights", self.WEIGHTS)
        device = resolve_device(ctx.device if ctx else "auto")
        if log_cb:
            log_cb(f"[SAM3] Dang nap {path.name} ...")
        self._model = SAM3SemanticPredictor(overrides={
            "model": str(path),
            "device": "cpu" if device == "cpu" else device,
            "conf": ctx.confidence if ctx else 0.35,
            "save": False,
            "verbose": False,
        })
        self._loaded = True
        if log_cb:
            log_cb("[SAM3] San sang.")

    # --------------------------------------------------------------- suy luan --
    def annotate(self, ctx: PluginContext) -> list[Detection]:
        concepts = self._concepts(ctx)
        if not concepts:
            return ctx.detections
        if self._model is None:
            self.load(ctx)

        source = ctx.image if ctx.image is not None else ctx.image_path
        try:
            self._model.set_image(source)
            results = self._model(text=concepts)
        except Exception as exc:
            raise RuntimeError(f"SAM 3 chay loi: {exc}") from exc
        if not results:
            return []
        return self._parse(results[0], concepts, ctx)

    # ------------------------------------------------------------------ phu tro --
    @staticmethod
    def _concepts(ctx: PluginContext) -> list[str]:
        raw = (ctx.prompt or "").strip()
        if raw:
            parts = [p.strip(" .") for p in raw.replace(".", ",").split(",")]
            return [p for p in parts if p]
        return [n for n in ctx.class_names if n]

    def _parse(self, res, concepts: list[str], ctx: PluginContext) -> list[Detection]:
        out: list[Detection] = []
        name_to_id = {n.lower(): i for i, n in enumerate(ctx.class_names)}
        min_area = float(self.config("min_area", 40))
        simplify = float(self.config("simplify", 0.002))

        boxes = getattr(res, "boxes", None)
        masks = getattr(res, "masks", None)
        mask_data = masks.data.cpu().numpy() if (
            masks is not None and getattr(masks, "data", None) is not None) else None
        names = getattr(res, "names", {}) or {}

        n = len(boxes) if boxes is not None else (
            len(mask_data) if mask_data is not None else 0)
        for i in range(n):
            label = concepts[0]
            conf = 1.0
            bbox = [0.0, 0.0, 0.0, 0.0]
            if boxes is not None and i < len(boxes):
                cid = int(boxes.cls[i].item()) if getattr(boxes, "cls", None) is not None else 0
                label = str(names.get(cid, concepts[min(cid, len(concepts) - 1)]))
                conf = float(boxes.conf[i].item()) if getattr(
                    boxes, "conf", None) is not None else 1.0
                bbox = [float(v) for v in boxes.xyxy[i].tolist()]

            det = Detection(
                class_id=name_to_id.get(label.lower(), 0), class_name=label,
                confidence=conf, bbox=bbox, shape=SHAPE_BBOX,
            )
            if mask_data is not None and i < len(mask_data):
                polys = mask_to_polygons((mask_data[i] > 0.5).astype(np.uint8),
                                         min_area=min_area, simplify=simplify)
                if polys:
                    arr = np.asarray(max(polys, key=len), dtype=np.float32)
                    det.polygon = [float(v) for v in arr.flatten()]
                    det.shape = SHAPE_POLYGON
                    det.bbox = [float(arr[:, 0].min()), float(arr[:, 1].min()),
                                float(arr[:, 0].max()), float(arr[:, 1].max())]
            out.append(det)
        return out
