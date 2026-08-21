"""Train lai mo hinh Ultralytics ngay trong ung dung."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.i18n import tr
from app.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class TrainConfig:
    model: str = "yolo11m-seg.pt"
    data_yaml: str = ""
    epochs: int = 100
    batch: int = 16
    imgsz: int = 640
    optimizer: str = "auto"  # auto | SGD | Adam | AdamW | RMSProp | NAdam
    lr0: float = 0.01
    lrf: float = 0.01
    momentum: float = 0.937
    weight_decay: float = 0.0005
    patience: int = 50
    workers: int = 4
    device: str = "auto"
    augment: bool = True
    cache: bool = False
    resume: bool = False
    pretrained: bool = True
    seed: int = 0
    project_dir: str = ""
    run_name: str = "train"
    val: bool = True
    plots: bool = True
    # Dung khi tu sinh dataset tu project (khong truyen cho Ultralytics)
    val_split: float = 0.2
    test_split: float = 0.0
    # Tang cuong du lieu
    hsv_h: float = 0.015
    hsv_s: float = 0.7
    hsv_v: float = 0.4
    degrees: float = 0.0
    translate: float = 0.1
    scale: float = 0.5
    fliplr: float = 0.5
    flipud: float = 0.0
    mosaic: float = 1.0
    mixup: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> TrainConfig:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_ultralytics_kwargs(self) -> dict:
        from app.core.inference import resolve_device

        kw = dict(
            data=self.data_yaml,
            epochs=int(self.epochs),
            batch=int(self.batch),
            imgsz=int(self.imgsz),
            optimizer=self.optimizer,
            lr0=float(self.lr0),
            lrf=float(self.lrf),
            momentum=float(self.momentum),
            weight_decay=float(self.weight_decay),
            patience=int(self.patience),
            workers=int(self.workers),
            device=resolve_device(self.device),
            cache=bool(self.cache),
            resume=bool(self.resume),
            pretrained=bool(self.pretrained),
            seed=int(self.seed),
            val=bool(self.val),
            plots=bool(self.plots),
            exist_ok=True,
            verbose=True,
        )
        if self.project_dir:
            kw["project"] = self.project_dir
            kw["name"] = self.run_name
        if self.augment:
            kw.update(
                hsv_h=self.hsv_h,
                hsv_s=self.hsv_s,
                hsv_v=self.hsv_v,
                degrees=self.degrees,
                translate=self.translate,
                scale=self.scale,
                fliplr=self.fliplr,
                flipud=self.flipud,
                mosaic=self.mosaic,
                mixup=self.mixup,
            )
        else:
            kw.update(
                hsv_h=0.0,
                hsv_s=0.0,
                hsv_v=0.0,
                degrees=0.0,
                translate=0.0,
                scale=0.0,
                fliplr=0.0,
                flipud=0.0,
                mosaic=0.0,
                mixup=0.0,
            )
        return kw


def disable_integration_callbacks(log_cb=None) -> None:
    """Tat cac callback tich hop ben thu ba cua Ultralytics.

    Khi train, Ultralytics tu dong gan callback cho Ray Tune, W&B, Comet, DVC,
    MLflow, Neptune, ClearML... neu cac goi do co mat trong may. Chi can mot goi
    lech phien ban la callback do nem loi va lam SAP ca qua trinh train, du no
    khong lien quan gi den cong viec cua ta (vi du: ray moi bo
    `ray.train._internal.session._get_session`).

    Ung dung nay tu ghi log va bieu do rieng nen khong can cac tich hop do.
    """
    try:
        from ultralytics.utils import callbacks as ul_callbacks

        if getattr(ul_callbacks.add_integration_callbacks, "_als_patched", False):
            return

        def _noop(instance):  # noqa: ANN001
            return

        _noop._als_patched = True
        ul_callbacks.add_integration_callbacks = _noop
        if log_cb:
            log_cb(
                tr(
                    "trainer.disabled_callbacks_log",
                    "Đã tắt các callback tích hợp bên thứ ba (ray/wandb/comet/...) để tránh xung đột phiên bản.",
                )
            )
    except Exception as exc:  # pragma: no cover
        log.debug("Khong tat duoc integration callbacks: %s", exc)


@dataclass
class EpochMetrics:
    epoch: int = 0
    total_epochs: int = 0
    box_loss: float = 0.0
    seg_loss: float = 0.0
    cls_loss: float = 0.0
    dfl_loss: float = 0.0
    map50: float = 0.0
    map5095: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    lr: float = 0.0
    elapsed: float = 0.0

    def as_line(self) -> str:
        return (
            f"[{self.epoch}/{self.total_epochs}] "
            f"box={self.box_loss:.3f} seg={self.seg_loss:.3f} cls={self.cls_loss:.3f} | "
            f"mAP50={self.map50:.3f} mAP50-95={self.map5095:.3f} "
            f"P={self.precision:.3f} R={self.recall:.3f}"
        )


@dataclass
class TrainResult:
    ok: bool = False
    best_weights: str = ""
    last_weights: str = ""
    out_dir: str = ""
    best_map: float = 0.0
    epochs_done: int = 0
    elapsed: float = 0.0
    message: str = ""
    history: list[EpochMetrics] = field(default_factory=list)


class ModelTrainer:
    """Chay train + phat metric moi epoch qua callback."""

    def __init__(self, config: TrainConfig) -> None:
        self.cfg = config
        self._cancelled = False
        self._model = None
        self.history: list[EpochMetrics] = []

    def cancel(self) -> None:
        self._cancelled = True
        # Ultralytics kiem tra co stop_training cua trainer de dung som
        try:
            trainer = getattr(self._model, "trainer", None)
            if trainer is not None:
                trainer.stop_training = True
                trainer.stop = True
        except Exception:
            pass

    # -------------------------------------------------------------- chay ---
    def run(self, progress_cb=None, log_cb=None, metric_cb=None) -> TrainResult:
        _log = log_cb or (lambda *_: None)
        t0 = time.time()
        cfg = self.cfg
        result = TrainResult()

        if not cfg.data_yaml or not Path(cfg.data_yaml).exists():
            raise FileNotFoundError(
                tr(
                    "trainer.dataset_not_found",
                    "Không tìm thấy data.yaml: {path}",
                    path=cfg.data_yaml,
                )
            )

        # Xóa các file .cache cũ trong dataset để Ultralytics không dùng cache hỏng
        try:
            yaml_parent = Path(cfg.data_yaml).parent
            for cache_file in yaml_parent.rglob("*.cache"):
                cache_file.unlink(missing_ok=True)
        except Exception:
            pass

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                tr(
                    "trainer.ultralytics_not_installed",
                    "Chưa cài ultralytics: pip install ultralytics",
                )
            ) from exc

        from app.core.inference import (
            YoloEngine,
            configure_ultralytics,
            ensure_amp_asset,
            purge_corrupt_weight,
            resolve_device,
        )

        configure_ultralytics()
        disable_integration_callbacks(_log)
        if resolve_device(cfg.device) != "cpu":
            ensure_amp_asset(_log)
        weights = YoloEngine._resolve_weights(cfg.model, _log)
        try:
            self._model = YOLO(weights)
        except Exception as exc:
            from app.utils.paths import weights_dir

            candidate = weights if Path(weights).exists() else str(weights_dir() / weights)
            if purge_corrupt_weight(candidate):
                _log(
                    tr(
                        "trainer.corrupt_weights_log",
                        "File trọng số hỏng, đang tải lại: {name}",
                        name=Path(candidate).name,
                    )
                )
                self._model = YOLO(weights)
            else:
                raise RuntimeError(
                    tr(
                        "trainer.cannot_load_model",
                        "Không nạp được model '{weights}': {exc}",
                        weights=weights,
                        exc=exc,
                    )
                ) from exc

        _log(tr("trainer.base_model_log", "Model gốc: {weights}", weights=weights))
        _log(tr("trainer.dataset_path_log", "Dataset  : {path}", path=cfg.data_yaml))
        kwargs = cfg.to_ultralytics_kwargs()
        _log(
            tr(
                "trainer.device_params_log",
                "Thiết bị : {device} | epochs={epochs} batch={batch} imgsz={imgsz} optimizer={optimizer}",
                device=kwargs["device"],
                epochs=cfg.epochs,
                batch=cfg.batch,
                imgsz=cfg.imgsz,
                optimizer=cfg.optimizer,
            )
        )

        self._install_callbacks(progress_cb, _log, metric_cb, t0)

        try:
            self._model.train(**kwargs)
        except KeyboardInterrupt:
            result.message = tr("trainer.stopped_by_user", "Đã dừng theo yêu cầu.")
        except Exception as exc:
            result.ok = False
            result.message = str(exc)
            result.elapsed = time.time() - t0
            raise

        trainer = getattr(self._model, "trainer", None)
        if trainer is not None:
            save_dir = Path(getattr(trainer, "save_dir", ""))
            result.out_dir = str(save_dir)
            best = save_dir / "weights" / "best.pt"
            last = save_dir / "weights" / "last.pt"
            result.best_weights = str(best) if best.exists() else ""
            result.last_weights = str(last) if last.exists() else ""
        result.history = self.history
        result.epochs_done = len(self.history)
        result.best_map = max((m.map5095 for m in self.history), default=0.0)
        result.elapsed = time.time() - t0
        result.ok = not self._cancelled
        result.message = result.message or (
            tr("trainer.stopped_halfway", "Đã dừng giữa chừng.")
            if self._cancelled
            else tr("trainer.train_completed", "Train hoàn tất.")
        )
        _log(
            tr(
                "trainer.summary_log",
                "{msg} Thời gian: {minutes:.1f} phút",
                msg=result.message,
                minutes=result.elapsed / 60,
            )
        )
        if result.best_weights:
            _log(
                tr(
                    "trainer.best_weights_log",
                    "Trọng số tốt nhất: {path}",
                    path=result.best_weights,
                )
            )
        return result

    # ---------------------------------------------------------- callbacks ---
    def _install_callbacks(self, progress_cb, _log, metric_cb, t0) -> None:
        model = self._model
        total = int(self.cfg.epochs)
        # Dem batch train ke tu epoch-end gan nhat: epoch that luon co it nhat
        # mot batch truoc do, con lan callback "ao" trong final_eval thi khong.
        self._batches_since_epoch = 0

        def safe(fn):
            """Loi trong callback cua ta khong duoc phep lam sap qua trinh train."""

            def wrapper(trainer):
                try:
                    fn(trainer)
                except Exception as exc:  # pragma: no cover
                    log.warning("Callback %s loi: %s", fn.__name__, exc)

            wrapper.__name__ = getattr(fn, "__name__", "callback")
            return wrapper

        def on_epoch_end(trainer):
            if self._cancelled:
                trainer.stop_training = True
                trainer.stop = True
                return
            epoch = int(getattr(trainer, "epoch", 0)) + 1
            m = EpochMetrics(epoch=epoch, total_epochs=total, elapsed=time.time() - t0)

            losses = getattr(trainer, "label_loss_items", None)
            try:
                items = losses(getattr(trainer, "tloss", None), prefix="train") or {}
            except Exception:
                items = {}
            m.box_loss = float(items.get("train/box_loss", 0.0) or 0.0)
            m.seg_loss = float(items.get("train/seg_loss", 0.0) or 0.0)
            m.cls_loss = float(items.get("train/cls_loss", 0.0) or 0.0)
            m.dfl_loss = float(items.get("train/dfl_loss", 0.0) or 0.0)

            metrics = getattr(trainer, "metrics", None) or {}
            m.map50 = float(_first(metrics, "metrics/mAP50(B)", "metrics/mAP50(M)"))
            m.map5095 = float(_first(metrics, "metrics/mAP50-95(B)", "metrics/mAP50-95(M)"))
            m.precision = float(_first(metrics, "metrics/precision(B)", "metrics/precision(M)"))
            m.recall = float(_first(metrics, "metrics/recall(B)", "metrics/recall(M)"))
            try:
                lrs = getattr(trainer, "lr", {}) or {}
                m.lr = float(next(iter(lrs.values()))) if lrs else 0.0
            except Exception:
                m.lr = 0.0

            # Ultralytics goi them mot lan trong final_eval SAU khi vong train
            # ket thuc; luc do trainer.epoch da tang them 1 nen so sanh bang
            # epoch se truot va sinh "epoch ao" (vd hien 3/2). Nhan dien bang
            # viec khong co batch train nao ke tu epoch-end truoc, roi cap nhat
            # metric da validate lai vao epoch cuoi thay vi them epoch moi.
            if self.history and self._batches_since_epoch == 0:
                m.epoch = self.history[-1].epoch
                self.history[-1] = m
                return

            self._batches_since_epoch = 0
            self.history.append(m)
            _log(m.as_line())
            if metric_cb:
                metric_cb(m)
            if progress_cb:
                progress_cb(
                    epoch,
                    total,
                    tr(
                        "trainer.epoch_progress",
                        "Epoch {current}/{total}",
                        current=epoch,
                        total=total,
                    ),
                )

        def on_batch_end(trainer):
            self._batches_since_epoch += 1
            if self._cancelled:
                trainer.stop_training = True
                trainer.stop = True

        def on_train_start(trainer):
            _log(
                tr(
                    "trainer.start_train_log",
                    "Bắt đầu train - lưu kết quả tại: {dir}",
                    dir=getattr(trainer, "save_dir", "?"),
                )
            )

        try:
            model.add_callback("on_fit_epoch_end", safe(on_epoch_end))
            model.add_callback("on_train_batch_end", safe(on_batch_end))
            model.add_callback("on_train_start", safe(on_train_start))
        except Exception as exc:  # pragma: no cover
            log.warning("Khong gan duoc callback: %s", exc)


def _first(d: dict, *keys) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return 0.0


def validate_dataset(data_yaml: str) -> tuple[bool, str]:
    """Kiem tra nhanh data.yaml truoc khi train."""
    p = Path(data_yaml)
    if not p.exists():
        return False, tr("trainer.val_no_data_yaml", "Không tìm thấy data.yaml.")
    try:
        import yaml

        with open(p, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        return False, tr("trainer.val_read_error", "Đọc data.yaml lỗi: {exc}", exc=exc)

    names = data.get("names")
    if not names:
        return False, tr("trainer.val_missing_names", "data.yaml thiếu mục 'names'.")
    root = Path(data.get("path", p.parent))
    train_rel = data.get("train")
    if not train_rel:
        return False, tr("trainer.val_missing_train", "data.yaml thiếu mục 'train'.")
    train_dir = (root / train_rel) if not Path(train_rel).is_absolute() else Path(train_rel)
    if not train_dir.exists():
        return False, tr(
            "trainer.val_train_dir_not_found", "Không tìm thấy thư mục train: {dir}", dir=train_dir
        )
    n_img = sum(1 for _ in train_dir.glob("*.*"))
    if n_img == 0:
        return False, tr("trainer.val_no_images", "Thư mục train không có ảnh nào.")
    return True, tr(
        "trainer.val_ok",
        "OK - {images} ảnh train, {classes} class.",
        images=n_img,
        classes=len(names),
    )
