"""Plugin Grounding DINO - phat hien doi tuong theo mo ta bang van ban.

Dung ban tren HuggingFace transformers (IDEA-Research/grounding-dino-tiny|base).
"""
from __future__ import annotations

from app.constants import SHAPE_BBOX
from app.core.inference import Detection, resolve_device
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam


class GroundingDinoPlugin(AnnotatorPlugin):
    info = PluginInfo(
        key="grounding_dino",
        name="Grounding DINO",
        version="1.0",
        author="AutoLabel Studio AI",
        description=(
            "Zero-shot detection theo prompt van ban. Vi du prompt: "
            "'crack . rust . bolt .' se sinh box cho tung khai niem ma khong can "
            "train truoc. Ket hop voi SAM2/FastSAM de ra mask segmentation."
        ),
        requires=["transformers", "torch"],
        kind="generate",
        accepts_prompt=True,
        homepage="https://huggingface.co/IDEA-Research/grounding-dino-tiny",
    )

    MODEL_ID = "IDEA-Research/grounding-dino-tiny"

    def config_schema(self) -> list[PluginParam]:
        return [
            PluginParam(
                key="model_id",
                label="Model ID",
                type="choice",
                default=self.MODEL_ID,
                options=[
                    "IDEA-Research/grounding-dino-tiny",
                    "IDEA-Research/grounding-dino-base",
                ],
                description="Mô hình Grounding DINO trên Hugging Face",
            ),
            PluginParam(
                key="box_threshold",
                label="Ngưỡng Bounding Box",
                type="float",
                default=0.30,
                min_value=0.05,
                max_value=0.95,
                description="Ngưỡng lọc bounding box dự đoán",
            ),
            PluginParam(
                key="text_threshold",
                label="Ngưỡng khớp văn bản",
                type="float",
                default=0.25,
                min_value=0.05,
                max_value=0.95,
                description="Ngưỡng khớp văn bản mô tả với vùng ảnh",
            ),
        ]

    def default_config(self) -> dict:
        return {p.key: p.default for p in self.config_schema()}

    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        model_id = self.config("model_id", self.MODEL_ID)
        if log_cb:
            log_cb(f"[GroundingDINO] Dang tai {model_id} (lan dau se mat vai phut) ...")
        self._processor = AutoProcessor.from_pretrained(model_id)
        self._model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)
        device = resolve_device(ctx.device if ctx else "auto")
        self._device = "cpu" if device == "cpu" else f"cuda:{device}"
        self._model = self._model.to(self._device).eval()
        self._torch = torch
        self._loaded = True
        if log_cb:
            log_cb("[GroundingDINO] San sang.")

    def annotate(self, ctx: PluginContext) -> list[Detection]:
        prompt = (ctx.prompt or "").strip()
        if not prompt and ctx.class_names:
            prompt = " . ".join(ctx.class_names) + " ."
        if not prompt:
            return []
        if self._model is None:
            self.load(ctx)

        from PIL import Image

        if ctx.image is not None:
            import cv2
            pil = Image.fromarray(cv2.cvtColor(ctx.image, cv2.COLOR_BGR2RGB))
        else:
            pil = Image.open(ctx.image_path).convert("RGB")

        inputs = self._processor(images=pil, text=prompt.lower(), return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with self._torch.no_grad():
            outputs = self._model(**inputs)

        results = self._processor.post_process_grounded_object_detection(
            outputs,
            inputs["input_ids"],
            threshold=float(self.config("box_threshold", 0.30)),
            text_threshold=float(self.config("text_threshold", 0.25)),
            target_sizes=[pil.size[::-1]],
        )
        if not results:
            return []
        res = results[0]
        names = {n.lower(): i for i, n in enumerate(ctx.class_names)}
        out: list[Detection] = []
        for box, score, label in zip(res["boxes"], res["scores"], res["labels"]):
            label = str(label).strip(" .")
            cid = names.get(label.lower(), -1)
            x1, y1, x2, y2 = [float(v) for v in box.tolist()]
            out.append(Detection(
                class_id=cid if cid >= 0 else 0,
                class_name=label or (ctx.class_names[0] if ctx.class_names else "object"),
                confidence=float(score), bbox=[x1, y1, x2, y2], shape=SHAPE_BBOX,
            ))
        return out
