"""Kiem thu luong nghiep vu Auto Label + cac loi hoi quy da va (2026-08).

Phan 1 (chay trong CI, khong can model that): fake engine.
Phan 2 (ALS_E2E=1): model YOLO that — xem huong dan trong docs/TAI-LIEU-KIEM-THU.md.

Ba loi hoi quy duoc chot o day:
  BUG-01  Tracker "bam" vao predict thuong sau mot phien tracking
          (nuot detection, spam canh bao GMC, gan track_id gia).
  BUG-02  purge_corrupt_weight xoa file model cua nguoi dung ngoai weights_dir.
  BUG-03  Re-run auto label khong con detection -> status anh van "auto".
"""

from __future__ import annotations

import os
from functools import partial
from pathlib import Path

import pytest

from app.constants import ANN_REVIEW, IMG_AUTO, IMG_REVIEW, IMG_UNLABELED
from app.core.inference import Detection, InferenceConfig, YoloEngine, purge_corrupt_weight
from app.models.repository import ProjectRepository
from app.workers.autolabel_worker import AutoLabelWorker


# ------------------------------------------------------------ fake engine ---
class FakeEngine:
    """Engine gia lap: tra ve detection dinh san, khong can torch/model."""

    def __init__(self, dets_per_call: list[list[Detection]] | None = None):
        self.names = {0: "person", 1: "car"}
        self.device = "cpu"
        self.class_names = ["person", "car"]
        self._queue = list(dets_per_call or [])
        self.n_predict_calls = 0

    def describe(self) -> str:
        return "fake-engine"

    def reset_tracker(self) -> None:
        pass

    def predict(self, source, config=None) -> list[Detection]:
        self.n_predict_calls += 1
        if self._queue:
            return self._queue.pop(0)
        return []


def _det(cid=0, name="person", conf=0.9, bbox=(10, 10, 100, 100)) -> Detection:
    return Detection(class_id=cid, class_name=name, confidence=conf, bbox=list(bbox))


# ================================================== TC-AL-01..04: luong chinh
def test_worker_writes_annotations_and_status(repo: ProjectRepository):
    """TC-AL-01: worker ghi annotation vao DB, dat status va thong ke dung."""
    imgs = repo.images()[:3]
    ids = [im.id for im in imgs]
    engine = FakeEngine(
        [
            [_det(conf=0.9), _det(cid=1, name="car", conf=0.7)],  # auto
            [_det(conf=0.4)],  # duoi review_threshold
            [],  # khong co gi
        ]
    )
    worker = AutoLabelWorker(
        repo, engine, ids, InferenceConfig(), review_threshold=0.6, low_conf_threshold=0.35
    )
    res = worker.execute()

    assert res.n_images == 3
    assert res.n_objects == 3
    assert res.n_review == 1
    assert res.n_empty == 1
    assert res.per_class.get("person") == 2

    # Anh 1: 2 nhan, status auto
    anns1 = repo.annotations(ids[0])
    assert len(anns1) == 2
    assert repo.image(ids[0]).status == IMG_AUTO
    assert repo.image(ids[0]).n_objects == 2
    # Anh 2: 1 nhan duoi nguong -> anh can review, annotation mang ANN_REVIEW
    anns2 = repo.annotations(ids[1])
    assert repo.image(ids[1]).status == IMG_REVIEW
    assert anns2[0].status == ANN_REVIEW


def test_worker_maps_model_class_to_project_class(repo: ProjectRepository):
    """TC-AL-02: class cua model duoc map/tao lazy trong project."""
    img = repo.images()[0]
    engine = FakeEngine([[_det(cid=1, name="car", conf=0.8)]])
    AutoLabelWorker(repo, engine, [img.id], InferenceConfig()).execute()

    names = [c.name for c in repo.classes(refresh=True)]
    assert "car" in names  # duoc tao lazy
    ann = repo.annotations(img.id)[0]
    assert ann.class_id == repo.class_by_name("car").id


def test_worker_overwrite_false_skips_labeled(repo: ProjectRepository):
    """TC-AL-03: overwrite=False bo qua anh da co nhan."""
    labeled = [im for im in repo.images() if im.n_objects > 0]
    engine = FakeEngine()
    res = AutoLabelWorker(
        repo, engine, [im.id for im in labeled], InferenceConfig(), overwrite=False
    ).execute()
    assert res.n_images == 0
    assert engine.n_predict_calls == 0


def test_worker_rerun_empty_resets_status(repo: ProjectRepository):
    """TC-AL-04 (BUG-03): re-run khong detect gi -> xoa nhan cu, status ve unlabeled."""
    img = next(im for im in repo.images() if im.n_objects > 0)
    engine = FakeEngine([[]])  # lan nay model khong thay gi
    AutoLabelWorker(repo, engine, [img.id], InferenceConfig(), overwrite=True).execute()

    assert repo.annotations(img.id) == []
    rec = repo.image(img.id)
    assert rec.n_objects == 0
    assert rec.status == IMG_UNLABELED  # truoc khi va: van la "auto"


# ===================================================== TC-AL-05: tracker leak
def test_detach_tracker_removes_callbacks_and_state():
    """TC-AL-05 (BUG-01): predict() phai go callback tracking do model.track() cai."""

    def _fake_tracker_cb(predictor, persist=False):
        pass

    _fake_tracker_cb.__module__ = "ultralytics.trackers.track"

    def _user_cb(predictor):
        pass

    class _FakePredictor:
        pass

    class _FakeModel:
        def __init__(self):
            self.callbacks = {
                "on_predict_start": [partial(_fake_tracker_cb, persist=True), _user_cb],
                "on_predict_postprocess_end": [partial(_fake_tracker_cb, persist=True)],
            }
            self.predictor = _FakePredictor()
            self.predictor.trackers = ["<tracker-state>"]

    engine = YoloEngine()
    engine.model = _FakeModel()
    engine._detach_tracker()

    # Callback cua tracker bien mat, callback nguoi dung giu nguyen
    assert engine.model.callbacks["on_predict_start"] == [_user_cb]
    assert engine.model.callbacks["on_predict_postprocess_end"] == []
    # Trang thai trackers bi go de model.track() lan sau dang ky lai tu dau
    assert not hasattr(engine.model.predictor, "trackers")


# ================================================ TC-AL-06: purge weights an toan
def test_purge_corrupt_weight_never_touches_user_files(tmp_dir: Path):
    """TC-AL-06 (BUG-02): chi xoa .pt trong weights_dir; file nguoi dung bat kha xam pham."""
    from app.utils.paths import weights_dir

    # File model tuy chinh cua nguoi dung (nho hon 1MB) o NGOAI weights_dir
    user_model = tmp_dir / "my_tiny_model.pt"
    user_model.write_bytes(b"x" * 1000)
    assert purge_corrupt_weight(str(user_model)) is False
    assert user_model.exists()  # truoc khi va: bi xoa vi < 1MB

    # File hong trong weights_dir thi duoc phep xoa (tai lai duoc)
    broken = weights_dir() / "broken_download.pt"
    broken.write_bytes(b"x" * 10)
    assert purge_corrupt_weight(str(broken)) is True
    assert not broken.exists()


# ======================================= Phan 2: E2E model that (ALS_E2E=1) ==
requires_real_model = pytest.mark.skipif(
    os.environ.get("ALS_E2E") != "1",
    reason="Chay voi model that: dat bien moi truong ALS_E2E=1 (tai yolo11n.pt ~5.6MB)",
)


@requires_real_model
def test_e2e_real_model_detect_and_no_tracker_leak():
    """TC-E2E-01: model that detect ra doi tuong; sau track() predict van sach."""
    from ultralytics.utils import ASSETS

    bus = str(ASSETS / "bus.jpg")
    engine = YoloEngine()
    engine.load("yolo11n.pt", task="detect", device="auto")
    cfg = InferenceConfig(confidence=0.35)

    dets = engine.predict(bus, cfg)
    assert len(dets) >= 4  # bus + vai nguoi
    names = {d.class_name for d in dets}
    assert "bus" in names and "person" in names

    # Chay tracking 2 frame roi predict thuong: khong duoc dinh track_id,
    # va so detection khong duoc it hon truoc khi tracking (BUG-01).
    engine.reset_tracker()
    engine.track(bus, config=cfg)
    engine.track(bus, config=cfg)
    dets_after = engine.predict(bus, cfg)
    assert all(d.track_id is None for d in dets_after)
    assert len(dets_after) >= len(dets) - 1  # dung sai nho do non-determinism


@requires_real_model
def test_e2e_real_model_sahi_finds_more_small_objects():
    """TC-E2E-02: SAHI tren anh ghep lon tim duoc >= inference thuong."""
    import cv2
    import numpy as np
    from ultralytics.utils import ASSETS

    bus = cv2.imread(str(ASSETS / "bus.jpg"))
    mosaic = np.vstack([np.hstack([bus, bus]), np.hstack([bus, bus])])

    engine = YoloEngine()
    engine.load("yolo11n.pt", task="detect", device="auto")
    plain = engine.predict(mosaic, InferenceConfig(confidence=0.35))
    sahi = engine.slice_predict(
        mosaic,
        InferenceConfig(confidence=0.35, sahi_enabled=True, sahi_slice_size=640, sahi_overlap=0.2),
    )
    assert len(sahi) >= len(plain)
    assert len(sahi) > 0
    H, W = mosaic.shape[:2]
    for d in sahi:
        x1, y1, x2, y2 = d.bbox
        assert -2 <= x1 <= W + 2 and -2 <= y1 <= H + 2 and x2 <= W + 2 and y2 <= H + 2
