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
from app.i18n import tr
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam
from app.plugins.builtin.sam_refiner import ultralytics_version

MIN_VERSION = (8, 3, 237)


class Sam3ConceptPlugin(AnnotatorPlugin):
    info = PluginInfo(
        key="sam3_concept",
        name=tr("plugins.sam3_concept.name", "SAM 3 Concept (prompt văn bản)"),
        version="1.0",
        author="AutoLabel Studio AI",
        description=tr(
            "plugins.sam3_concept.desc",
            "Sinh annotation cho TẤT CẢ đối tượng khớp với một khái niệm mô tả bằng chữ, "
            "không cần train trước. Ví dụ prompt: 'crack, rust, bolt'.\n\n"
            "Khác với SAM 2 (chỉ bấm theo box/point bạn đưa vào), SAM 3 tự tìm đối tượng "
            "theo nghĩa của từ. Dùng khi bạn có lớp đối tượng mà YOLO COCO không biết.",
        ),
        requires=["ultralytics", "torch"],
        kind="generate",
        accepts_prompt=True,
        homepage="https://docs.ultralytics.com/models/sam-3/",
    )

    WEIGHTS = "sam3.pt"

    def config_schema(self) -> list[PluginParam]:
        return [
            PluginParam(
                key="weights",
                label=tr("plugins.sam3_concept.weights_label", "Trọng số SAM 3"),
                type="str",
                default=self.WEIGHTS,
                description=tr(
                    "plugins.sam3_concept.weights_desc",
                    "Tên file trọng số SAM 3 trong thư mục weights",
                ),
            ),
            PluginParam(
                key="min_area",
                label=tr("plugins.sam3_concept.min_area_label", "Diện tích tối thiểu (px)"),
                type="float",
                default=40.0,
                min_value=0.0,
                max_value=5000.0,
                description=tr(
                    "plugins.sam3_concept.min_area_desc", "Ngưỡng diện tích nhỏ nhất của polygon"
                ),
            ),
            PluginParam(
                key="simplify",
                label=tr("plugins.sam3_concept.simplify_label", "Độ giản lược polygon"),
                type="float",
                default=0.002,
                min_value=0.0,
                max_value=0.05,
                description=tr(
                    "plugins.sam3_concept.simplify_desc", "Mức độ làm mịn đường viền polygon"
                ),
            ),
        ]

    def default_config(self) -> dict:
        return {p.key: p.default for p in self.config_schema()}

    def _resolve_weights_path(self):
        from pathlib import Path

        from app.utils.paths import app_root, weights_dir

        val = str(self.config("weights", self.WEIGHTS)).strip()
        if not val:
            val = self.WEIGHTS
        p = Path(val)
        if p.is_absolute() and p.exists():
            return p
        w_dir_path = weights_dir() / val
        if w_dir_path.exists():
            return w_dir_path
        app_models_path = app_root() / "app" / "models" / val
        if app_models_path.exists():
            return app_models_path
        return None

    # -------------------------------------------------------------- trang thai --
    def is_available(self) -> tuple[bool, str]:
        ok, msg = super().is_available()
        if not ok:
            return ok, msg

        ver = ultralytics_version()
        if ver < MIN_VERSION:
            have = ".".join(str(v) for v in ver)
            need = ".".join(str(v) for v in MIN_VERSION)
            return False, tr(
                "plugins.sam3_concept.need_ultralytics",
                "Cần ultralytics >= {need} (đang có {have}). Nâng cấp: pip install -U ultralytics",
                need=need,
                have=have,
            )
        try:
            from ultralytics.models.sam import SAM3SemanticPredictor  # noqa: F401
        except Exception:
            return False, tr(
                "plugins.sam3_concept.missing_predictor",
                "Bản ultralytics này không có SAM3SemanticPredictor",
            )

        if not self._resolve_weights_path():
            from app.utils.paths import weights_dir

            return False, tr(
                "plugins.sam3_concept.missing_weights",
                "Chưa có {weights} trong {dir} hoặc app/models/ - Meta yêu cầu xin quyền trên Hugging Face rồi tải thủ công",
                weights=self.WEIGHTS,
                dir=weights_dir(),
            )
        return True, tr("plugins.available", "Sẵn sàng")

    # ------------------------------------------------------------------- nap --
    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        ok, msg = self.is_available()
        if not ok:
            raise RuntimeError(msg)

        from ultralytics.models.sam import SAM3SemanticPredictor

        path = self._resolve_weights_path()
        if path is None:
            raise RuntimeError(f"Khong tim thay tep trong so {self.WEIGHTS}")

        device = resolve_device(ctx.device if ctx else "auto")
        if log_cb:
            log_cb(f"[SAM3] Dang nap {path.name} ...")
        self._model = SAM3SemanticPredictor(
            overrides={
                "model": str(path),
                "device": "cpu" if device == "cpu" else device,
                "conf": ctx.confidence if ctx else 0.35,
                "save": False,
                "verbose": False,
            }
        )
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
        mask_data = (
            masks.data.cpu().numpy()
            if (masks is not None and getattr(masks, "data", None) is not None)
            else None
        )
        names = getattr(res, "names", {}) or {}

        n = len(boxes) if boxes is not None else (len(mask_data) if mask_data is not None else 0)
        for i in range(n):
            label = concepts[0]
            conf = 1.0
            bbox = [0.0, 0.0, 0.0, 0.0]
            if boxes is not None and i < len(boxes):
                cid = int(boxes.cls[i].item()) if getattr(boxes, "cls", None) is not None else 0
                label = str(names.get(cid, concepts[min(cid, len(concepts) - 1)]))
                conf = (
                    float(boxes.conf[i].item()) if getattr(boxes, "conf", None) is not None else 1.0
                )
                bbox = [float(v) for v in boxes.xyxy[i].tolist()]

            det = Detection(
                class_id=name_to_id.get(label.lower(), 0),
                class_name=label,
                confidence=conf,
                bbox=bbox,
                shape=SHAPE_BBOX,
            )
            if mask_data is not None and i < len(mask_data):
                polys = mask_to_polygons(
                    (mask_data[i] > 0.5).astype(np.uint8), min_area=min_area, simplify=simplify
                )
                if polys:
                    arr = np.asarray(max(polys, key=len), dtype=np.float32)
                    det.polygon = [float(v) for v in arr.flatten()]
                    det.shape = SHAPE_POLYGON
                    det.bbox = [
                        float(arr[:, 0].min()),
                        float(arr[:, 1].min()),
                        float(arr[:, 0].max()),
                        float(arr[:, 1].max()),
                    ]
            out.append(det)
        return out
