"""Plugin SAM - tinh chinh bounding box thanh mask sac net.

Tu chon phien ban SAM tot nhat dang co trong may:
  SAM 3 (sam3.pt)  ->  SAM 2 (sam2_b.pt)  ->  SAM 1 (sam_b.pt)

Voi loai prompt hinh hoc (box/point), ca ba phien ban dung chung lop
`ultralytics.SAM`, nen chi can doi ten file trong so.
"""

from __future__ import annotations

import numpy as np

from app.constants import SHAPE_POLYGON
from app.core.inference import Detection, mask_to_polygons, resolve_device
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam

#: (ten file trong so, nhan hien thi, phien ban ultralytics toi thieu)
SAM_CANDIDATES = [
    ("sam3.pt", "SAM 3", (8, 3, 237)),
    ("sam2_b.pt", "SAM 2", (8, 2, 0)),
    ("sam_b.pt", "SAM 1", (8, 0, 0)),
]


def ultralytics_version() -> tuple[int, ...]:
    try:
        import ultralytics

        parts = str(ultralytics.__version__).split(".")[:3]
        return tuple(int("".join(ch for ch in p if ch.isdigit()) or 0) for p in parts)
    except Exception:
        return (0, 0, 0)


def pick_sam_weights(preferred: str = "auto") -> tuple[str, str]:
    """Tra ve (ten_file_trong_so, nhan). 'auto' = chon ban tot nhat dung duoc."""
    from app.utils.paths import weights_dir

    if preferred and preferred != "auto":
        label = next((lb for w, lb, _v in SAM_CANDIDATES if w == preferred), preferred)
        return preferred, label

    ver = ultralytics_version()
    available = [(w, lb, v) for w, lb, v in SAM_CANDIDATES if ver >= v]
    # Uu tien ban da tai san trong may de khong phai tai lai
    for w, lb, _v in available:
        if (weights_dir() / w).exists():
            return w, lb
    if available:
        return available[0][0], available[0][1]
    return "sam_b.pt", "SAM 1"


class SamRefiner(AnnotatorPlugin):
    info = PluginInfo(
        key="sam",
        name="SAM Refiner (3 / 2)",
        version="1.1",
        author="AutoLabel Studio AI",
        description=(
            "Dung Segment Anything de chuyen bounding box cua YOLO thanh mask polygon "
            "bam sat vien doi tuong. Rat huu ich khi model detection chi cho ra box ma "
            "ban can dataset segmentation.\n\n"
            "Tu chon phien ban tot nhat dang co: SAM 3 (can ultralytics >= 8.3.237 va "
            "file sam3.pt tai thu cong tu Hugging Face) -> SAM 2 (sam2_b.pt, tu tai) -> "
            "SAM 1 (sam_b.pt)."
        ),
        requires=["ultralytics", "torch"],
        kind="refine",
        accepts_prompt=False,
        homepage="https://docs.ultralytics.com/models/sam-3/",
    )

    def config_schema(self) -> list[PluginParam]:
        return [
            PluginParam(
                key="weights",
                label="Trọng số SAM",
                type="choice",
                default="auto",
                options=["auto", "sam3.pt", "sam2_b.pt", "sam_b.pt"],
                description="Chọn phiên bản trọng số SAM thích hợp",
            ),
            PluginParam(
                key="min_area",
                label="Diện tích tối thiểu (px)",
                type="float",
                default=40.0,
                min_value=0.0,
                max_value=5000.0,
                description="Ngưỡng diện tích nhỏ nhất của polygon",
            ),
            PluginParam(
                key="simplify",
                label="Độ giản lược polygon",
                type="float",
                default=0.002,
                min_value=0.0,
                max_value=0.05,
                description="Mức độ làm mịn đường viền polygon",
            ),
        ]

    def default_config(self) -> dict:
        return {p.key: p.default for p in self.config_schema()}

    # -------------------------------------------------------------- trang thai --
    def is_available(self) -> tuple[bool, str]:
        ok, msg = super().is_available()
        if not ok:
            return ok, msg
        weights, label = pick_sam_weights(self.config("weights", "auto"))
        from app.utils.paths import weights_dir

        if (weights_dir() / weights).exists():
            return True, f"San sang ({label})"
        if weights == "sam3.pt":
            return False, (
                "Can dat sam3.pt vao thu muc weights "
                "(tai thu cong tu Hugging Face, Meta yeu cau xin quyen)"
            )
        return True, f"San sang ({label} - se tai {weights} lan dau)"

    # ------------------------------------------------------------------- nap --
    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        from ultralytics import SAM

        from app.core.inference import download_asset
        from app.utils.paths import weights_dir

        weights, label = pick_sam_weights(self.config("weights", "auto"))
        self.label = label
        path = weights_dir() / weights
        if not path.exists():
            if weights == "sam3.pt":
                raise FileNotFoundError(
                    f"Khong tim thay {weights}. SAM 3 khong tai tu dong duoc - hay tai "
                    f"tu Hugging Face roi dat vao {weights_dir()}"
                )
            if log_cb:
                log_cb(f"[SAM] Chua co {weights}, dang tai ...")
            got = download_asset(weights, log_cb)
            if not got:
                raise FileNotFoundError(f"Khong tai duoc {weights}")
            path = weights_dir() / weights

        if log_cb:
            log_cb(f"[SAM] Dang nap {label} ({weights}) ...")
        self._model = SAM(str(path))
        device = resolve_device(ctx.device if ctx else "auto")
        try:
            self._model.to("cpu" if device == "cpu" else f"cuda:{device}")
        except Exception:
            pass
        self._loaded = True
        if log_cb:
            log_cb(f"[SAM] {label} san sang.")

    # --------------------------------------------------------------- suy luan --
    def annotate(self, ctx: PluginContext) -> list[Detection]:
        if not ctx.detections:
            return []
        if self._model is None:
            self.load(ctx)

        boxes = [d.bbox for d in ctx.detections]
        source = ctx.image if ctx.image is not None else ctx.image_path
        results = self._model.predict(source, bboxes=boxes, verbose=False)
        if not results:
            return ctx.detections

        masks = getattr(results[0], "masks", None)
        if masks is None or masks.data is None:
            return ctx.detections

        data = masks.data.cpu().numpy()
        min_area = float(self.config("min_area", 40))
        simplify = float(self.config("simplify", 0.002))

        out: list[Detection] = []
        for i, det in enumerate(ctx.detections):
            new_det = Detection(
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=list(det.bbox),
                shape=det.shape,
            )
            if i < len(data):
                polys = mask_to_polygons(
                    (data[i] > 0.5).astype(np.uint8), min_area=min_area, simplify=simplify
                )
                if polys:
                    biggest = max(polys, key=len)
                    arr = np.asarray(biggest, dtype=np.float32)
                    new_det.polygon = [float(v) for v in arr.flatten()]
                    new_det.shape = SHAPE_POLYGON
                    new_det.bbox = [
                        float(arr[:, 0].min()),
                        float(arr[:, 1].min()),
                        float(arr[:, 0].max()),
                        float(arr[:, 1].max()),
                    ]
            out.append(new_det)
        return out
