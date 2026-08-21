"""Kiem thu ModelTrainer: callback metric va loi hoi quy BUG-04.

BUG-04: Ultralytics goi on_fit_epoch_end them mot lan trong final_eval sau khi
vong train ket thuc, voi trainer.epoch DA tang them 1 -> sinh "epoch ao"
(hien thi 3/2, epochs_done sai). Luong train that da duoc chay E2E tren GPU
(xem docs/TAI-LIEU-KIEM-THU.md, nhom C).
"""

from __future__ import annotations

import time

from app.core.trainer import ModelTrainer, TrainConfig


class _FakeUltralyticsTrainer:
    """Gia lap doi tuong trainer ma Ultralytics truyen vao callback."""

    def __init__(self):
        self.epoch = 0
        self.metrics = {"metrics/mAP50(B)": 0.5, "metrics/mAP50-95(B)": 0.3}
        self.lr = {"lr/pg0": 0.001}
        self.tloss = None
        self.stop = False
        self.stop_training = False

    def label_loss_items(self, tloss, prefix="train"):
        return {f"{prefix}/box_loss": 1.0, f"{prefix}/cls_loss": 2.0}


def _install(epochs: int = 2):
    trainer = ModelTrainer(TrainConfig(epochs=epochs))
    callbacks: dict = {}

    class _FakeModel:
        def add_callback(self, name, fn):
            callbacks[name] = fn

    trainer._model = _FakeModel()
    trainer._install_callbacks(None, lambda *_: None, None, time.time())
    return trainer, callbacks


def test_final_eval_does_not_create_phantom_epoch():
    """TC-TR-01 (BUG-04): lan callback trong final_eval cap nhat epoch cuoi,
    khong duoc them epoch moi vuot tong."""
    trainer, cbs = _install(epochs=2)
    ul = _FakeUltralyticsTrainer()

    for epoch_idx in range(2):  # 2 epoch that, moi epoch co batch train
        for _ in range(3):
            cbs["on_train_batch_end"](ul)
        ul.epoch = epoch_idx
        cbs["on_fit_epoch_end"](ul)

    # final_eval: trainer.epoch da tang len 2, KHONG co batch train nao truoc do
    ul.epoch = 2
    ul.metrics = {"metrics/mAP50(B)": 0.6, "metrics/mAP50-95(B)": 0.4}
    cbs["on_fit_epoch_end"](ul)

    epochs = [m.epoch for m in trainer.history]
    assert epochs == [1, 2], f"epoch ao xuat hien: {epochs}"
    assert all(m.epoch <= m.total_epochs for m in trainer.history)
    # Metric validate cuoi cung duoc cap nhat vao epoch cuoi
    assert trainer.history[-1].map50 == 0.6


def test_early_stop_final_eval_updates_last_epoch():
    """TC-TR-02: dung som (patience) o epoch 3/10 — final_eval van khong sinh epoch 4."""
    trainer, cbs = _install(epochs=10)
    ul = _FakeUltralyticsTrainer()

    for epoch_idx in range(3):
        cbs["on_train_batch_end"](ul)
        ul.epoch = epoch_idx
        cbs["on_fit_epoch_end"](ul)

    ul.epoch = 3  # sau break, truoc final_eval
    cbs["on_fit_epoch_end"](ul)

    assert [m.epoch for m in trainer.history] == [1, 2, 3]


def test_epoch_metrics_values_parsed():
    """TC-TR-03: loss/mAP/lr duoc doc dung tu doi tuong trainer cua Ultralytics."""
    trainer, cbs = _install(epochs=1)
    ul = _FakeUltralyticsTrainer()
    cbs["on_train_batch_end"](ul)
    cbs["on_fit_epoch_end"](ul)

    m = trainer.history[0]
    assert m.box_loss == 1.0
    assert m.cls_loss == 2.0
    assert m.map50 == 0.5
    assert m.map5095 == 0.3
    assert m.lr == 0.001


def test_cancel_stops_ultralytics_loop():
    """TC-TR-04: cancel() lam trainer cua Ultralytics dung o batch/epoch ke tiep."""
    trainer, cbs = _install(epochs=5)
    ul = _FakeUltralyticsTrainer()
    trainer.cancel()
    cbs["on_train_batch_end"](ul)
    assert ul.stop_training is True and ul.stop is True
