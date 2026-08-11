"""Plugin FastSAM - segment toan anh, nhanh hon SAM nhieu lan."""

from __future__ import annotations

import numpy as np

from app.constants import SHAPE_POLYGON
from app.core.inference import Detection, mask_to_polygons, resolve_device
from app.i18n import tr
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam


class FastSamPlugin(AnnotatorPlugin):
    info = PluginInfo(
        key="fastsam",
        name="FastSAM",
        version="1.0",
        author="AutoLabel Studio AI",
        description=tr(
            "plugins.fastsam.desc",
            "Segment toàn bộ đối tượng trong ảnh bằng FastSAM (nhanh gấp ~50 lần SAM). "
            "Có thể dùng ở chế độ 'refine' (bám theo box YOLO) hoặc 'generate' "
            "(sinh mới mask cho toàn ảnh để bạn gán class thủ công).",
        ),
        requires=["ultralytics", "torch"],
        kind="refine",
        accepts_prompt=True,
        homepage="https://docs.ultralytics.com/models/fast-sam/",
    )

    WEIGHTS = "FastSAM-s.pt"

    def config_schema(self) -> list[PluginParam]:
        return [
            PluginParam(
                key="weights",
                label=tr("plugins.fastsam.weights_label", "Trọng số FastSAM"),
                type="choice",
                default=self.WEIGHTS,
                options=["FastSAM-s.pt", "FastSAM-x.pt"],
                description=tr("plugins.fastsam.weights_desc", "Tên file trọng số FastSAM"),
            ),
            PluginParam(
                key="imgsz",
                label=tr("plugins.fastsam.imgsz_label", "Cỡ ảnh vào"),
                type="int",
                default=1024,
                min_value=320,
                max_value=2048,
                description=tr("plugins.fastsam.imgsz_desc", "Kích thước ảnh đưa vào FastSAM"),
            ),
            PluginParam(
                key="min_area",
                label=tr("plugins.fastsam.min_area_label", "Diện tích tối thiểu (px)"),
                type="float",
                default=60.0,
                min_value=0.0,
                max_value=5000.0,
                description=tr("plugins.fastsam.min_area_desc", "Bỏ qua các mask nhỏ hơn ngưỡng này"),
            ),
            PluginParam(
                key="simplify",
                label=tr("plugins.fastsam.simplify_label", "Độ giản lược polygon"),
                type="float",
                default=0.002,
                min_value=0.0,
                max_value=0.05,
                description=tr("plugins.fastsam.simplify_desc", "Tỷ lệ làm mịn đường viền polygon"),
            ),
            PluginParam(
                key="mode",
                label=tr("plugins.fastsam.mode_label", "Chế độ hoạt động"),
                type="choice",
                default="refine",
                options=["refine", "generate"],
                description=tr("plugins.fastsam.mode_desc", "Refine: tinh chỉnh box YOLO. Generate: tự tạo mask toàn ảnh"),
            ),
        ]

    def default_config(self) -> dict:
        return {p.key: p.default for p in self.config_schema()}

    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        import os

        from ultralytics import FastSAM

        from app.utils.paths import weights_dir

        prev = os.getcwd()
        try:
            os.chdir(weights_dir())
            if log_cb:
                log_cb(
                    tr(
                        "plugins.fastsam.loading_log",
                        "[FastSAM] Đang nạp {weights} ...",
                        weights=self.config("weights", self.WEIGHTS),
                    )
                )
            self._model = FastSAM(self.config("weights", self.WEIGHTS))
        finally:
            os.chdir(prev)
        device = resolve_device(ctx.device if ctx else "auto")
        try:
            self._model.to("cpu" if device == "cpu" else f"cuda:{device}")
        except Exception:
            pass
        self._loaded = True

    def annotate(self, ctx: PluginContext) -> list[Detection]:
        if self._model is None:
            self.load(ctx)
        source = ctx.image if ctx.image is not None else ctx.image_path
        kwargs = dict(
            imgsz=int(self.config("imgsz", 1024)),
            conf=ctx.confidence,
            verbose=False,
            retina_masks=True,
        )
        mode = self.config("mode", "refine")

        if mode == "refine" and ctx.detections:
            kwargs["bboxes"] = [d.bbox for d in ctx.detections]
        elif ctx.prompt:
            kwargs["texts"] = ctx.prompt

        results = self._model.predict(source, **kwargs)
        if not results:
            return ctx.detections

        masks = getattr(results[0], "masks", None)
        if masks is None or masks.data is None:
            return ctx.detections
        data = masks.data.cpu().numpy()
        min_area = float(self.config("min_area", 60))
        simplify = float(self.config("simplify", 0.002))

        if mode == "refine" and ctx.detections:
            out = []
            for i, det in enumerate(ctx.detections):
                new_det = Detection(
                    class_id=det.class_id,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox=list(det.bbox),
                    shape=det.shape,
                )
                if i < len(data):
                    polys = mask_to_polygons((data[i] > 0.5).astype(np.uint8), min_area, simplify)
                    if polys:
                        big = max(polys, key=len)
                        new_det.polygon = [float(v) for v in np.asarray(big).flatten()]
                        new_det.shape = SHAPE_POLYGON
                out.append(new_det)
            return out

        # Che do generate: moi mask thanh mot doi tuong chua gan class
        out = []
        name = ctx.class_names[0] if ctx.class_names else "object"
        for m in data:
            polys = mask_to_polygons((m > 0.5).astype(np.uint8), min_area, simplify)
            for p in polys:
                arr = np.asarray(p, dtype=np.float32)
                det = Detection(
                    class_id=0,
                    class_name=name,
                    confidence=0.5,
                    polygon=[float(v) for v in arr.flatten()],
                    shape=SHAPE_POLYGON,
                    bbox=[
                        float(arr[:, 0].min()),
                        float(arr[:, 1].min()),
                        float(arr[:, 0].max()),
                        float(arr[:, 1].max()),
                    ],
                )
                out.append(det)
        return out
