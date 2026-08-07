"""Plugin Florence-2 - VLM da nhiem vu cua Microsoft.

Ho tro cac task: <OD>, <DENSE_REGION_CAPTION>, <CAPTION_TO_PHRASE_GROUNDING>,
<REFERRING_EXPRESSION_SEGMENTATION>.
"""
from __future__ import annotations

from app.constants import SHAPE_BBOX, SHAPE_POLYGON
from app.core.inference import Detection, resolve_device
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam


class Florence2Plugin(AnnotatorPlugin):
    info = PluginInfo(
        key="florence2",
        name="Florence-2",
        version="1.0",
        author="AutoLabel Studio AI",
        description=(
            "Vision-Language Model da nhiem vu. Co the sinh box (<OD>), mo ta vung "
            "(<DENSE_REGION_CAPTION>), hoac mask theo cau mo ta "
            "(<REFERRING_EXPRESSION_SEGMENTATION>). Prompt de trong se dung <OD>."
        ),
        requires=["transformers", "torch"],
        kind="generate",
        accepts_prompt=True,
        homepage="https://huggingface.co/microsoft/Florence-2-base",
    )

    MODEL_ID = "microsoft/Florence-2-base"

    def config_schema(self) -> list[PluginParam]:
        return [
            PluginParam(
                key="model_id",
                label="Model ID",
                type="choice",
                default=self.MODEL_ID,
                options=["microsoft/Florence-2-base", "microsoft/Florence-2-large"],
                description="Mô hình Florence-2 trên Hugging Face",
            ),
            PluginParam(
                key="task",
                label="Nhiệm vụ mặc định",
                type="choice",
                default="<OD>",
                options=[
                    "<OD>",
                    "<DENSE_REGION_CAPTION>",
                    "<CAPTION_TO_PHRASE_GROUNDING>",
                    "<REFERRING_EXPRESSION_SEGMENTATION>",
                ],
                description="Tác vụ mặc định khi không nhập prompt",
            ),
            PluginParam(
                key="max_new_tokens",
                label="Số token tối đa",
                type="int",
                default=1024,
                min_value=128,
                max_value=4096,
                description="Độ dài tối đa chuỗi sinh ra",
            ),
        ]

    def default_config(self) -> dict:
        return {p.key: p.default for p in self.config_schema()}

    def load(self, ctx: PluginContext | None = None, log_cb=None) -> None:
        if self._model is not None:
            self._loaded = True
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        model_id = self.config("model_id", self.MODEL_ID)
        if log_cb:
            log_cb(f"[Florence-2] Dang tai {model_id} ...")
        device = resolve_device(ctx.device if ctx else "auto")
        self._device = "cpu" if device == "cpu" else f"cuda:{device}"
        dtype = torch.float16 if self._device != "cpu" else torch.float32
        self._processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=dtype, trust_remote_code=True).to(self._device).eval()
        self._torch = torch
        self._dtype = dtype
        self._loaded = True
        if log_cb:
            log_cb("[Florence-2] San sang.")

    def annotate(self, ctx: PluginContext) -> list[Detection]:
        if self._model is None:
            self.load(ctx)
        from PIL import Image

        if ctx.image is not None:
            import cv2
            pil = Image.fromarray(cv2.cvtColor(ctx.image, cv2.COLOR_BGR2RGB))
        else:
            pil = Image.open(ctx.image_path).convert("RGB")

        prompt = (ctx.prompt or "").strip()
        if prompt.startswith("<"):
            task, text = prompt.split(">", 1)
            task += ">"
            text = text.strip()
        elif prompt:
            task = "<CAPTION_TO_PHRASE_GROUNDING>"
            text = prompt
        else:
            task = self.config("task", "<OD>")
            text = ""

        inputs = self._processor(text=task + text, images=pil, return_tensors="pt")
        inputs = {k: (v.to(self._device, self._dtype) if v.dtype.is_floating_point
                      else v.to(self._device)) for k, v in inputs.items()}
        with self._torch.no_grad():
            ids = self._model.generate(
                input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                max_new_tokens=int(self.config("max_new_tokens", 1024)),
                num_beams=3, do_sample=False,
            )
        raw = self._processor.batch_decode(ids, skip_special_tokens=False)[0]
        parsed = self._processor.post_process_generation(
            raw, task=task, image_size=pil.size)
        return self._to_detections(parsed.get(task, {}), ctx)

    # ---------------------------------------------------------------- parse --
    @staticmethod
    def _to_detections(data: dict, ctx: PluginContext) -> list[Detection]:
        names = {n.lower(): i for i, n in enumerate(ctx.class_names)}
        out: list[Detection] = []

        for box, label in zip(data.get("bboxes", []), data.get("labels", [])):
            x1, y1, x2, y2 = [float(v) for v in box]
            out.append(Detection(
                class_id=names.get(str(label).lower(), 0), class_name=str(label),
                confidence=0.75, bbox=[x1, y1, x2, y2], shape=SHAPE_BBOX,
            ))

        for polys, label in zip(data.get("polygons", []), data.get("labels", [])):
            for poly in polys:
                flat = [float(v) for v in poly]
                if len(flat) < 6:
                    continue
                xs, ys = flat[0::2], flat[1::2]
                out.append(Detection(
                    class_id=names.get(str(label).lower(), 0), class_name=str(label),
                    confidence=0.75, polygon=flat, shape=SHAPE_POLYGON,
                    bbox=[min(xs), min(ys), max(xs), max(ys)],
                ))
        return out
