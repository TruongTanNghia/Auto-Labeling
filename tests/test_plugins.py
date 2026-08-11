"""Kiem thu he thong Plugin, SAM Refiner weight picker, Config Lifecycle va Worker integration."""

from __future__ import annotations

import cv2

from app.config import cfg
from app.core.inference import Detection, InferenceConfig
from app.models.repository import ProjectRepository
from app.plugins.base import (
    AnnotatorPlugin,
    PluginContext,
    PluginInfo,
    registry,
)
from app.plugins.builtin.sam_refiner import pick_sam_weights, ultralytics_version
from app.workers.autolabel_worker import AutoLabelWorker


def test_plugin_discovery():
    registry.discover(force=True)
    keys = set(registry.keys())
    assert keys >= {"sam", "sam3_concept", "fastsam", "grounding_dino", "florence2"}

    ver = ultralytics_version()
    w, lb = pick_sam_weights("auto")
    if ver > (0, 0, 0):
        assert w.endswith(".pt")
        if ver < (8, 3, 237):
            assert w != "sam3.pt"
    assert pick_sam_weights("sam2_b.pt")[0] == "sam2_b.pt"


def test_plugin_dummy_roundtrip(sample_data):
    img_dir, _ = sample_data

    class _Dummy(AnnotatorPlugin):
        info = PluginInfo(
            key="_dummy", name="Dummy", kind="refine", requires=[], accepts_prompt=True
        )
        last_prompt = None

        def annotate(self, ctx: PluginContext) -> list[Detection]:
            assert ctx.image is not None
            _Dummy.last_prompt = ctx.prompt
            out = []
            for d in ctx.detections:
                d.polygon = [0.0, 0.0, 10.0, 0.0, 10.0, 10.0]
                out.append(d)
            return out

    registry.register(_Dummy)
    plugin = registry.get("_dummy")
    assert plugin is not None
    assert plugin.is_available()[0] is True
    plugin.load(PluginContext(device="cpu"))

    img = cv2.imread(str(next(img_dir.glob("*.jpg"))))
    ctx = PluginContext(
        image_path="x.jpg",
        image=img,
        detections=[Detection(class_id=0, class_name="a", confidence=0.5, bbox=[0, 0, 10, 10])],
        class_names=["a"],
        prompt="test prompt",
        device="cpu",
    )
    res = plugin.annotate(ctx)
    assert len(res) == 1
    assert len(res[0].polygon) == 6
    assert _Dummy.last_prompt == "test prompt"


def test_plugin_config_lifecycle():
    florence = registry.get("florence2")
    assert florence is not None
    assert florence.config("model_id") == "microsoft/Florence-2-base"

    cfg.set("plugins.config.florence2.model_id", "microsoft/Florence-2-large")
    cfg.save()
    florence_updated = registry.get("florence2")
    assert florence_updated.config("model_id") == "microsoft/Florence-2-large"

    fastsam = registry.get("fastsam")
    assert fastsam.config("imgsz") == 1024
    cfg.set("plugins.config.fastsam.imgsz", 640)
    cfg.set("plugins.config.fastsam.mode", "generate")
    fastsam_updated = registry.get("fastsam")
    assert fastsam_updated.config("imgsz") == 640
    assert fastsam_updated.config("mode") == "generate"

    cfg.set("plugins.config.florence2", {})
    cfg.set("plugins.config.fastsam", {})
    cfg.save()
    assert registry.get("florence2").config("model_id") == "microsoft/Florence-2-base"
    assert registry.get("fastsam").config("imgsz") == 1024


def test_plugin_in_worker(repo: ProjectRepository):
    class _Engine:
        names = {0: "crack"}
        device = "cpu"
        class_names = ["crack"]

        def describe(self):
            return "fake"

    img = repo.images()[0]
    worker = AutoLabelWorker(repo, _Engine(), [img.id], InferenceConfig())
    plugin = registry.get("_dummy")
    dets = [Detection(class_id=0, class_name="crack", confidence=0.8, bbox=[5, 5, 60, 60])]

    out = worker._apply_plugin(plugin, img.path, dets)
    assert len(out[0].polygon) == 6

    lookup = worker._sync_classes()
    anns, stats = worker._to_annotations(img.id, out, lookup)
    assert len(anns) == 1
    assert anns[0].class_id > 0
    assert stats["max_conf"] > 0
