"""Plugin Florence-2 - VLM da nhiem vu cua Microsoft.

Ho tro cac task: <OD>, <DENSE_REGION_CAPTION>, <CAPTION_TO_PHRASE_GROUNDING>,
<REFERRING_EXPRESSION_SEGMENTATION>.
"""

from __future__ import annotations

from app.constants import SHAPE_BBOX, SHAPE_POLYGON
from app.core.inference import Detection, resolve_device
from app.plugins.base import AnnotatorPlugin, PluginContext, PluginInfo, PluginParam


def _ensure_transformers_compatibility() -> None:
    """Tương thích ngược với các phiên bản transformers mới (>= 4.45)."""
    try:
        import torch
        import transformers.cache_utils
        import transformers.configuration_utils
        import transformers.modeling_utils
        import transformers.tokenization_utils_base

        if not hasattr(transformers.configuration_utils.PretrainedConfig, "forced_bos_token_id"):
            transformers.configuration_utils.PretrainedConfig.forced_bos_token_id = None
        if not hasattr(
            transformers.tokenization_utils_base.PreTrainedTokenizerBase,
            "additional_special_tokens",
        ):
            transformers.tokenization_utils_base.PreTrainedTokenizerBase.additional_special_tokens = property(
                lambda self: getattr(self, "special_tokens_map", {}).get(
                    "additional_special_tokens", []
                )
            )
        transformers.modeling_utils.PreTrainedModel._sdpa_can_dispatch = lambda self, *a, **kw: (
            getattr(self, "_supports_sdpa", False)
        )

        def _cache_getitem(self, idx):
            target = getattr(self, "self_attention_cache", self)
            layers = getattr(target, "layers", [])
            if idx < len(layers):
                layer = layers[idx]
                if hasattr(layer, "keys") and hasattr(layer, "values"):
                    return (layer.keys, layer.values)
                if isinstance(layer, (tuple, list)):
                    return layer
            seq_len = self.get_seq_length() if hasattr(self, "get_seq_length") else 0
            dummy = torch.zeros(1, 1, seq_len, 1)
            return (dummy, dummy, dummy, dummy)

        if not hasattr(transformers.cache_utils.Cache, "__getitem__"):
            transformers.cache_utils.Cache.__getitem__ = _cache_getitem
    except Exception:
        pass


def _safe_prepare_inputs_for_generation(self, decoder_input_ids, past_key_values=None, **kwargs):
    if past_key_values is not None:
        try:
            if (
                isinstance(past_key_values, (tuple, list))
                and len(past_key_values) > 0
                and past_key_values[0] is not None
                and past_key_values[0][0] is not None
            ):
                past_length = past_key_values[0][0].shape[2]
            elif hasattr(past_key_values, "get_seq_length"):
                past_length = past_key_values.get_seq_length()
            else:
                past_length = 0
        except Exception:
            past_length = 0

        if decoder_input_ids.shape[1] > past_length:
            remove_prefix_length = past_length
        else:
            remove_prefix_length = max(0, decoder_input_ids.shape[1] - 1)

        decoder_input_ids = decoder_input_ids[:, remove_prefix_length:]

    return {
        "input_ids": None,
        "encoder_outputs": kwargs.get("encoder_outputs"),
        "past_key_values": past_key_values,
        "decoder_input_ids": decoder_input_ids,
        "attention_mask": kwargs.get("attention_mask"),
        "decoder_attention_mask": kwargs.get("decoder_attention_mask"),
        "head_mask": kwargs.get("head_mask"),
        "decoder_head_mask": kwargs.get("decoder_head_mask"),
        "cross_attn_head_mask": kwargs.get("cross_attn_head_mask"),
        "use_cache": kwargs.get("use_cache"),
    }


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
        requires=["transformers", "torch", "einops", "timm"],
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

        _ensure_transformers_compatibility()

        model_id = self.config("model_id", self.MODEL_ID)
        if log_cb:
            log_cb(f"[Florence-2] Dang tai {model_id} ...")
        device = resolve_device(ctx.device if ctx else "auto")
        self._device = "cpu" if device == "cpu" else f"cuda:{device}"
        dtype = torch.float16 if self._device != "cpu" else torch.float32
        self._processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self._model = (
            AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, trust_remote_code=True)
            .to(self._device)
            .eval()
        )
        self._torch = torch
        self._dtype = dtype
        self._loaded = True
        if hasattr(self._model, "language_model"):
            type(
                self._model.language_model
            ).prepare_inputs_for_generation = _safe_prepare_inputs_for_generation
            decoder_cls = type(self._model.language_model.model.decoder)
            if not getattr(decoder_cls, "_patched", False):
                orig_decoder_forward = decoder_cls.forward

                def _safe_decoder_forward(self, *args, **kwargs):
                    args_list = list(args)
                    pkv = args_list[6] if len(args_list) > 6 else kwargs.get("past_key_values")
                    if pkv is not None:
                        is_valid = False
                        try:
                            if isinstance(pkv, (tuple, list)) and len(pkv) > 0:
                                first_layer = pkv[0]
                                if isinstance(first_layer, (tuple, list)) and len(first_layer) > 0:
                                    first_tensor = first_layer[0]
                                    if hasattr(first_tensor, "shape"):
                                        is_valid = True
                        except Exception:
                            pass
                        if not is_valid:
                            if len(args_list) > 6:
                                args_list[6] = None
                            kwargs["past_key_values"] = None
                    return orig_decoder_forward(self, *args_list, **kwargs)

                decoder_cls.forward = _safe_decoder_forward
                decoder_cls._patched = True

        if hasattr(self._model, "generation_config"):
            self._model.generation_config.return_legacy_cache = True
        if hasattr(self._model, "language_model") and hasattr(
            self._model.language_model, "generation_config"
        ):
            self._model.language_model.generation_config.return_legacy_cache = True

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

        # Florence-2 yeu cau anh dau vao vuong de ma hoa feature map (768x768)
        pil_input = (
            pil if pil.width == pil.height else pil.resize((768, 768), Image.Resampling.LANCZOS)
        )
        inputs = self._processor(text=task + text, images=pil_input, return_tensors="pt")
        inputs = {
            k: (
                v.to(self._device, self._dtype) if v.dtype.is_floating_point else v.to(self._device)
            )
            for k, v in inputs.items()
        }
        with self._torch.no_grad():
            ids = self._model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=int(self.config("max_new_tokens", 1024)),
                num_beams=3,
                do_sample=False,
            )
        raw = self._processor.batch_decode(ids, skip_special_tokens=False)[0]
        parsed = self._processor.post_process_generation(raw, task=task, image_size=pil.size)
        return self._to_detections(parsed.get(task, {}), ctx)

    # ---------------------------------------------------------------- parse --
    @staticmethod
    def _to_detections(data: dict, ctx: PluginContext) -> list[Detection]:
        names = {n.lower(): i for i, n in enumerate(ctx.class_names)}
        out: list[Detection] = []

        for box, label in zip(data.get("bboxes", []), data.get("labels", [])):
            x1, y1, x2, y2 = [float(v) for v in box]
            out.append(
                Detection(
                    class_id=names.get(str(label).lower(), 0),
                    class_name=str(label),
                    confidence=0.75,
                    bbox=[x1, y1, x2, y2],
                    shape=SHAPE_BBOX,
                )
            )

        for polys, label in zip(data.get("polygons", []), data.get("labels", [])):
            for poly in polys:
                flat = [float(v) for v in poly]
                if len(flat) < 6:
                    continue
                xs, ys = flat[0::2], flat[1::2]
                out.append(
                    Detection(
                        class_id=names.get(str(label).lower(), 0),
                        class_name=str(label),
                        confidence=0.75,
                        polygon=flat,
                        shape=SHAPE_POLYGON,
                        bbox=[min(xs), min(ys), max(xs), max(ys)],
                    )
                )
        return out
