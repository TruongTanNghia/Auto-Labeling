"""Engine suy luan YOLO (Ultralytics): detect / segment / obb / pose + custom model."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.constants import SHAPE_BBOX, SHAPE_OBB, SHAPE_POLYGON, SHAPE_POSE
from app.utils.logger import get_logger

log = get_logger(__name__)


# --------------------------------------------------------------- THIET BI ---
def device_info() -> dict:
    """Thong tin GPU/CPU, khong bat buoc phai co torch."""
    info = {
        "cuda": False,
        "name": "CPU",
        "count": 0,
        "total_gb": 0.0,
        "used_gb": 0.0,
        "torch": "",
        "cuda_version": "",
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda"] = bool(torch.cuda.is_available())
        info["cuda_version"] = torch.version.cuda or ""
        if info["cuda"]:
            info["count"] = torch.cuda.device_count()
            props = torch.cuda.get_device_properties(0)
            info["name"] = props.name
            info["total_gb"] = round(props.total_memory / 1024**3, 1)
            info["used_gb"] = round(torch.cuda.memory_reserved(0) / 1024**3, 1)
    except Exception as exc:  # pragma: no cover
        log.debug("Khong lay duoc thong tin GPU: %s", exc)
    return info


def resolve_device(preference: str = "auto") -> str:
    """'auto' -> '0' neu co CUDA, nguoc lai 'cpu'."""
    pref = (preference or "auto").strip().lower()
    if pref in ("cpu",):
        return "cpu"
    if pref in ("auto", "", "cuda"):
        return "0" if device_info()["cuda"] else "cpu"
    return preference


def device_label(preference: str = "auto") -> str:
    dev = resolve_device(preference)
    if dev == "cpu":
        return "CPU"
    info = device_info()
    return f"CUDA ({info['name']})"


_ULTRA_CONFIGURED = False


def configure_ultralytics() -> None:
    """Ep Ultralytics tai trong so ve thu muc cua ung dung.

    Neu khong lam viec nay, Ultralytics se tai cac file phu (vd yolo11n.pt cho
    buoc kiem tra AMP truoc khi train) vao thu muc lam viec hien tai, gay ban
    thu muc source va de sinh file tai do dang neu mang dut giua chung.
    """
    global _ULTRA_CONFIGURED
    if _ULTRA_CONFIGURED:
        return
    _ULTRA_CONFIGURED = True

    # Cam Ultralytics tu chay `pip install -U ...`. Neu de bat, buoc kiem tra
    # requirements cua no co the thay ban torch CUDA bang ban CPU tren PyPI,
    # lam mat kha nang chay GPU cua nguoi dung.
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    try:
        import ultralytics.utils.checks as _checks

        _checks.AUTOINSTALL = False
    except Exception:
        pass

    try:
        from ultralytics.utils import SETTINGS

        from app.utils.paths import ensure_dir, user_data_dir, weights_dir

        SETTINGS.update(
            {
                "weights_dir": str(weights_dir()),
                "datasets_dir": str(ensure_dir(user_data_dir() / "datasets")),
                "sync": False,
            }
        )
    except Exception as exc:  # pragma: no cover
        log.debug("Khong dat duoc thu muc weights cho Ultralytics: %s", exc)


_DOWNLOAD_LOCK = threading.Lock()


def download_asset(name: str, log_cb=None) -> str:
    """Tai mot trong so chuan cua Ultralytics VE THU MUC WEIGHTS cua ung dung.

    Ultralytics luon tai asset vao THU MUC LAM VIEC hien tai (tham so
    `download_dir` cua no chi ap dung cho URL day du), nen neu goi thang
    `YOLO("yolo11n-obb.pt")` thi file .pt se roi vao thu muc dang chay ung dung.
    Ham nay doi thu muc lam viec trong dung khoang thoi gian tai de file nam
    dung cho, roi tra ve duong dan tuyet doi.

    Tra ve chuoi rong neu khong tai duoc (de nguoi goi tu xu ly tiep).
    """
    from app.utils.paths import weights_dir

    target = weights_dir() / name
    if target.exists():
        return str(target)
    try:
        from ultralytics.utils.downloads import attempt_download_asset

        if log_cb:
            log_cb(f"Dang tai {name} ve {weights_dir()} ...")
        with _DOWNLOAD_LOCK:
            prev = os.getcwd()
            os.chdir(weights_dir())
            try:
                attempt_download_asset(name)
            finally:
                os.chdir(prev)
    except Exception as exc:
        log.debug("Khong tai duoc %s: %s", name, exc)
        if log_cb:
            log_cb(f"Khong tai duoc {name}: {exc}")
        return ""
    return str(target) if target.exists() else ""


def ensure_amp_asset(log_cb=None) -> None:
    """Dat san 'yolo11n.pt' trong thu muc weights truoc khi train tren GPU.

    Ultralytics chay kiem tra AMP bang cach nap 'yolo11n.pt'; neu file da co san
    trong weights_dir thi no tim thay va khong tai ve thu muc lam viec nua.
    """
    download_asset("yolo11n.pt", log_cb)


def purge_corrupt_weight(path: str) -> bool:
    """Xoa file trong so hong (tai do dang). Tra ve True neu da xoa."""
    try:
        p = Path(path)
        from app.utils.paths import weights_dir

        if (
            p.exists()
            and p.suffix == ".pt"
            and (p.parent == weights_dir() or p.stat().st_size < 1_000_000)
        ):
            p.unlink()
            log.warning("Da xoa file trong so hong: %s", p)
            return True
    except Exception:
        pass
    return False


def available_devices() -> list[tuple[str, str]]:
    out = [("auto", "Auto (uu tien GPU)"), ("cpu", "CPU")]
    info = device_info()
    for i in range(info["count"]):
        out.append((str(i), f"CUDA:{i} - {info['name']}"))
    return out


# --------------------------------------------------------------- KET QUA ----
@dataclass
class Detection:
    class_id: int = 0  # chi so class trong model
    class_name: str = ""
    confidence: float = 0.0
    bbox: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    polygon: list[float] = field(default_factory=list)  # [x1,y1,x2,y2,...] pixel
    keypoints: list[float] = field(default_factory=list)  # [x,y,v, ...]
    shape: str = SHAPE_BBOX
    track_id: int | None = None

    @property
    def area(self) -> float:
        if len(self.polygon) >= 6:
            pts = [
                (self.polygon[i], self.polygon[i + 1]) for i in range(0, len(self.polygon) - 1, 2)
            ]
            s = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                s += x1 * y2 - x2 * y1
            return abs(s) / 2.0
        return max(0.0, self.bbox[2] - self.bbox[0]) * max(0.0, self.bbox[3] - self.bbox[1])


@dataclass
class InferenceConfig:
    confidence: float = 0.45
    iou: float = 0.5
    max_det: int = 1000
    imgsz: int = 640
    half: bool = False
    agnostic_nms: bool = False
    retina_masks: bool = True
    polygon_simplify: float = 0.0025  # ti le so voi chu vi (0 = khong don gian hoa)
    min_area_px: float = 24.0
    class_filter: list[int] = field(default_factory=list)
    # --- Suy luan cat lat (SAHI) ---
    sahi_enabled: bool = False
    sahi_slice_size: int = 640  # chieu rong/cao moi o (px)
    sahi_overlap: float = 0.2  # ti le chong lan giua cac o (0.0 - 0.5)

    @classmethod
    def from_dict(cls, data: dict) -> InferenceConfig:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------- ENGINE ----
class YoloEngine:
    """Bao boc Ultralytics YOLO, nap mo hinh mot lan va tai su dung."""

    def __init__(self) -> None:
        self.model = None
        self.weights: str = ""
        self.task: str = "detect"
        self.device: str = "cpu"
        self.names: dict[int, str] = {}
        self._loaded = False

    # ------------------------------------------------------------- trang thai --
    @property
    def loaded(self) -> bool:
        return self._loaded and self.model is not None

    @property
    def class_names(self) -> list[str]:
        return [self.names[k] for k in sorted(self.names)]

    def describe(self) -> str:
        if not self.loaded:
            return "Chua nap model"
        return (
            f"{Path(self.weights).name} | task={self.task} | "
            f"device={self.device} | {len(self.names)} class"
        )

    def reset_tracker(self) -> None:
        """Reset trang thai theo doi truoc khi chay chuoi frame moi."""
        if self.loaded and hasattr(self.model, "predictor") and self.model.predictor:
            if hasattr(self.model.predictor, "trackers"):
                self.model.predictor.trackers = None

    # ------------------------------------------------------------------ nap --
    def load(self, weights: str, task: str = "detect", device: str = "auto", log_cb=None) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Chua cai ultralytics. Chay: pip install ultralytics") from exc

        weights = str(weights).strip()
        if not weights:
            raise ValueError("Chua chon file trong so.")

        resolved_dev = resolve_device(device)
        if (
            self.loaded
            and self.weights == weights
            and self.task == task
            and self.device == resolved_dev
        ):
            return  # da nap roi

        _log = log_cb or (lambda *_: None)
        _log(f"Dang nap model: {weights} (task={task}, device={resolved_dev}) ...")

        configure_ultralytics()
        weights = self._resolve_weights(weights, _log)
        suffix = Path(weights).suffix.lower()

        def _build(src: str):
            if suffix in (".onnx", ".engine", ".tflite", ".mlmodel", ".xml"):
                return YOLO(src, task=task)
            return YOLO(src)

        try:
            self.model = _build(weights)
        except Exception as exc:
            # File .pt tai do dang -> xoa va tai lai mot lan
            from app.utils.paths import weights_dir

            candidate = weights if Path(weights).exists() else str(weights_dir() / weights)
            if purge_corrupt_weight(candidate):
                _log(f"File trong so hong, dang tai lai: {Path(candidate).name}")
                self.model = _build(weights)
            else:
                raise RuntimeError(f"Khong nap duoc model '{weights}': {exc}") from exc

        try:
            real = getattr(getattr(self.model, "ckpt_path", None), "__str__", lambda: "")()
            if real and Path(real).exists():
                weights = real
        except Exception:
            pass

        try:
            if resolved_dev != "cpu":
                self.model.to(f"cuda:{resolved_dev}" if resolved_dev.isdigit() else resolved_dev)
            else:
                self.model.to("cpu")
        except Exception as exc:
            _log(f"Khong chuyen duoc sang {resolved_dev} ({exc}) - dung CPU.")
            resolved_dev = "cpu"
            self.model.to("cpu")

        self.weights = weights
        self.device = resolved_dev
        self.task = getattr(self.model, "task", task) or task
        raw_names = getattr(self.model, "names", {}) or {}
        if isinstance(raw_names, (list, tuple)):
            self.names = {i: n for i, n in enumerate(raw_names)}
        else:
            self.names = {int(k): v for k, v in raw_names.items()}
        self._loaded = True
        _log(f"Da nap: {self.describe()}")

    @staticmethod
    def _resolve_weights(weights: str, log_cb=None) -> str:
        """Tim file trong so: duong dan tuyet doi -> thu muc weights -> tai ve."""
        from app.utils.paths import weights_dir

        configure_ultralytics()
        p = Path(weights)
        if p.exists():
            return str(p)
        local = weights_dir() / p.name
        if local.exists():
            return str(local)
        if p.parent == Path("."):  # chi la ten model chuan -> tai ve weights_dir
            if log_cb:
                log_cb(f"Chua co '{p.name}' - se tai ve {weights_dir()}")
            downloaded = download_asset(p.name, log_cb)
            # Neu tai that bai thi van tra ve ten de Ultralytics tu xu ly tiep
            return downloaded or p.name
        raise FileNotFoundError(f"Khong tim thay file trong so: {weights}")

    def unload(self) -> None:
        self.model = None
        self._loaded = False
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    # -------------------------------------------------------------- du doan --
    def predict(self, source, config: InferenceConfig | None = None) -> list[Detection]:
        """source: duong dan anh hoac ndarray BGR. Tra ve danh sach Detection."""
        if not self.loaded:
            raise RuntimeError("Model chua duoc nap.")
        cfg = config or InferenceConfig()

        kwargs = dict(
            conf=float(cfg.confidence),
            iou=float(cfg.iou),
            max_det=int(cfg.max_det),
            imgsz=int(cfg.imgsz),
            verbose=False,
            device=self.device,
            agnostic_nms=bool(cfg.agnostic_nms),
        )
        if cfg.half and self.device != "cpu":
            kwargs["half"] = True
        if cfg.class_filter:
            kwargs["classes"] = list(cfg.class_filter)
        if self.task == "segment":
            kwargs["retina_masks"] = bool(cfg.retina_masks)

        results = self.model.predict(source, **kwargs)
        if not results:
            return []
        return self._parse(results[0], cfg)

    def track(
        self,
        source,
        tracker: str = "botsort.yaml",
        config: InferenceConfig | None = None,
        persist: bool = True,
    ) -> list[Detection]:
        """Suy luan ket hop tracking doi tuong qua frame."""
        if not self.loaded:
            raise RuntimeError("Model chua duoc nap.")
        cfg = config or InferenceConfig()

        kwargs = dict(
            conf=float(cfg.confidence),
            iou=float(cfg.iou),
            max_det=int(cfg.max_det),
            imgsz=int(cfg.imgsz),
            verbose=False,
            device=self.device,
            agnostic_nms=bool(cfg.agnostic_nms),
            tracker=tracker,
            persist=persist,
        )
        if cfg.half and self.device != "cpu":
            kwargs["half"] = True
        if cfg.class_filter:
            kwargs["classes"] = list(cfg.class_filter)
        if self.task == "segment":
            kwargs["retina_masks"] = bool(cfg.retina_masks)

        results = self.model.track(source, **kwargs)
        if not results:
            return []
        return self._parse(results[0], cfg)

    def predict_batch(
        self, sources: list, config: InferenceConfig | None = None
    ) -> list[list[Detection]]:
        if not self.loaded:
            raise RuntimeError("Model chua duoc nap.")
        cfg = config or InferenceConfig()
        kwargs = dict(
            conf=float(cfg.confidence),
            iou=float(cfg.iou),
            max_det=int(cfg.max_det),
            imgsz=int(cfg.imgsz),
            verbose=False,
            device=self.device,
            agnostic_nms=bool(cfg.agnostic_nms),
            stream=False,
        )
        if cfg.class_filter:
            kwargs["classes"] = list(cfg.class_filter)
        if self.task == "segment":
            kwargs["retina_masks"] = bool(cfg.retina_masks)
        results = self.model.predict(sources, **kwargs)
        return [self._parse(r, cfg) for r in results]

    # --------------------------------------------------------------- parse --
    def _parse(self, res, cfg: InferenceConfig) -> list[Detection]:
        out: list[Detection] = []

        # ---- OBB ----
        if getattr(res, "obb", None) is not None and len(res.obb) > 0:
            obb = res.obb
            polys = obb.xyxyxyxy.cpu().numpy()
            confs = obb.conf.cpu().numpy()
            clss = obb.cls.cpu().numpy().astype(int)
            obb_track_ids = None
            if getattr(obb, "id", None) is not None:
                try:
                    obb_track_ids = obb.id.int().cpu().numpy()
                except Exception:
                    pass

            for i, (poly, conf, cid) in enumerate(zip(polys, confs, clss)):
                pts = poly.reshape(-1, 2)
                flat = [float(v) for v in pts.flatten()]
                xs, ys = pts[:, 0], pts[:, 1]
                t_id = (
                    int(obb_track_ids[i])
                    if obb_track_ids is not None and i < len(obb_track_ids)
                    else None
                )
                det = Detection(
                    class_id=int(cid),
                    class_name=self.names.get(int(cid), str(cid)),
                    confidence=float(conf),
                    shape=SHAPE_OBB,
                    polygon=flat,
                    bbox=[float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())],
                    track_id=t_id,
                )
                if det.area >= cfg.min_area_px:
                    out.append(det)
            return out

        boxes = getattr(res, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return out

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)

        track_ids = None
        if getattr(boxes, "id", None) is not None:
            try:
                track_ids = boxes.id.int().cpu().numpy()
            except Exception:
                pass

        masks = getattr(res, "masks", None)
        polygons = None
        if masks is not None and getattr(masks, "xy", None) is not None:
            polygons = masks.xy

        kpts = getattr(res, "keypoints", None)
        kpt_data = None
        if kpts is not None and getattr(kpts, "data", None) is not None:
            kpt_data = kpts.data.cpu().numpy()

        for i in range(len(xyxy)):
            cid = int(clss[i])
            t_id = int(track_ids[i]) if track_ids is not None and i < len(track_ids) else None
            det = Detection(
                class_id=cid,
                class_name=self.names.get(cid, str(cid)),
                confidence=float(confs[i]),
                bbox=[float(v) for v in xyxy[i]],
                shape=SHAPE_BBOX,
                track_id=t_id,
            )
            if polygons is not None and i < len(polygons):
                poly = np.asarray(polygons[i], dtype=np.float32)
                if poly.ndim == 2 and len(poly) >= 3:
                    poly = simplify_polygon(poly, cfg.polygon_simplify)
                    det.polygon = [float(v) for v in poly.flatten()]
                    det.shape = SHAPE_POLYGON
            if kpt_data is not None and i < len(kpt_data):
                det.keypoints = [float(v) for v in kpt_data[i].flatten()]
                det.shape = SHAPE_POSE if not det.polygon else det.shape
            if det.area >= cfg.min_area_px:
                out.append(det)
        return out

    # -------------------------------------------------------- SAHI helpers --
    @staticmethod
    def _cross_tile_nms(dets: list[Detection], iou_thr: float, task: str) -> list[Detection]:
        """Greedy NMS xuyen o: loai box/polygon trung lap tu nhieu o khac nhau."""
        if len(dets) <= 1:
            return dets

        # Nhom theo class_id de chi so sanh cung class
        from collections import defaultdict

        by_class: dict[int, list] = defaultdict(list)
        for d in dets:
            by_class[d.class_id].append(d)

        kept: list[Detection] = []
        use_poly = task == "segment"

        for cls_dets in by_class.values():
            cls_dets = sorted(cls_dets, key=lambda d: d.confidence, reverse=True)
            suppressed = [False] * len(cls_dets)

            # Cache shapely polygons neu can
            if use_poly:
                try:
                    from shapely.geometry import Polygon as ShPoly

                    sh_polys = []
                    for d in cls_dets:
                        if len(d.polygon) >= 6:
                            pts = [
                                (d.polygon[i], d.polygon[i + 1])
                                for i in range(0, len(d.polygon) - 1, 2)
                            ]
                            try:
                                sh_polys.append(ShPoly(pts).buffer(0))
                            except Exception:
                                sh_polys.append(None)
                        else:
                            sh_polys.append(None)
                    _shapely_ok = True
                except ImportError:
                    _shapely_ok = False
                    sh_polys = [None] * len(cls_dets)
            else:
                _shapely_ok = False
                sh_polys = [None] * len(cls_dets)

            for i in range(len(cls_dets)):
                if suppressed[i]:
                    continue
                kept.append(cls_dets[i])
                bx1, by1, bx2, by2 = cls_dets[i].bbox
                ba = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

                for j in range(i + 1, len(cls_dets)):
                    if suppressed[j]:
                        continue
                    cx1, cy1, cx2, cy2 = cls_dets[j].bbox

                    # Tinh IoU bang polygon Shapely neu co
                    iou = 0.0
                    if _shapely_ok and sh_polys[i] is not None and sh_polys[j] is not None:
                        try:
                            inter = sh_polys[i].intersection(sh_polys[j]).area
                            union = sh_polys[i].area + sh_polys[j].area - inter
                            iou = inter / union if union > 0 else 0.0
                        except Exception:
                            iou = 0.0
                    else:
                        # Fallback: IoU box
                        ca = max(0.0, cx2 - cx1) * max(0.0, cy2 - cy1)
                        ix1 = max(bx1, cx1)
                        iy1 = max(by1, cy1)
                        ix2 = min(bx2, cx2)
                        iy2 = min(by2, cy2)
                        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
                        union = ba + ca - inter
                        iou = inter / union if union > 0 else 0.0

                    if iou >= iou_thr:
                        suppressed[j] = True

        return kept

    @staticmethod
    def _merge_boundary_polygons(
        dets: list[Detection], img_w: int, img_h: int, merge_dist: float = 8.0
    ) -> list[Detection]:
        """Gop cac manh polygon cung class nam sat ranh gioi o vao mot polygon lien tuc.

        Chi xu ly khi Shapely kha dung. Neu khong the gop, giu nguyen 2 manh cu.
        Chon exterior ring lon nhat de tranh multipolygon phuc tap.
        """
        try:
            from shapely.geometry import Polygon as ShPoly
            from shapely.ops import unary_union
        except ImportError:
            return dets

        if not dets:
            return dets

        # Phan loai: polygon co the nam sat bien anh/o hay khong
        def _is_boundary(poly_flat: list[float]) -> bool:
            """True neu co diem nao nam cach bien anh <= merge_dist."""
            for i in range(0, len(poly_flat) - 1, 2):
                x, y = poly_flat[i], poly_flat[i + 1]
                if (
                    x <= merge_dist
                    or y <= merge_dist
                    or x >= img_w - merge_dist
                    or y >= img_h - merge_dist
                ):
                    return True
            return False

        from collections import defaultdict

        boundary_by_class: dict[int, list[int]] = defaultdict(list)
        interior_idx: list[int] = []

        for idx, d in enumerate(dets):
            if len(d.polygon) >= 6 and _is_boundary(d.polygon):
                boundary_by_class[d.class_id].append(idx)
            else:
                interior_idx.append(idx)

        result: list[Detection] = [dets[i] for i in interior_idx]

        for _cls_id, idxs in boundary_by_class.items():
            if len(idxs) == 1:
                result.append(dets[idxs[0]])
                continue

            sh_polys = []
            valid_idxs = []
            for i in idxs:
                pts = [
                    (dets[i].polygon[k], dets[i].polygon[k + 1])
                    for k in range(0, len(dets[i].polygon) - 1, 2)
                ]
                try:
                    p = ShPoly(pts).buffer(0)
                    if p.is_valid and not p.is_empty:
                        sh_polys.append(p)
                        valid_idxs.append(i)
                    else:
                        result.append(dets[i])
                except Exception:
                    result.append(dets[i])

            if not sh_polys:
                continue

            # Thu gop; neu that bai giu nguyen cac manh
            try:
                merged = unary_union(sh_polys)
                # Lay exterior ring lon nhat neu la MultiPolygon
                if merged.geom_type == "MultiPolygon":
                    merged = max(merged.geoms, key=lambda g: g.area)
                if merged.geom_type != "Polygon" or merged.is_empty:
                    for i in valid_idxs:
                        result.append(dets[i])
                    continue
                coords = list(merged.exterior.coords)
                flat = [v for pt in coords[:-1] for v in pt]  # bo diem cuoi trung diem dau
                # Lay Detection co confidence cao nhat de ke thua metadata
                base = max((dets[i] for i in valid_idxs), key=lambda d: d.confidence)
                import copy

                merged_det = copy.copy(base)
                merged_det.polygon = flat
                xs = [flat[k] for k in range(0, len(flat), 2)]
                ys = [flat[k] for k in range(1, len(flat), 2)]
                merged_det.bbox = [min(xs), min(ys), max(xs), max(ys)]
                result.append(merged_det)
            except Exception:
                for i in valid_idxs:
                    result.append(dets[i])

        return result

    def slice_predict(
        self, source, config: InferenceConfig | None = None, progress_cb=None
    ) -> list[Detection]:
        """Suy luan cat lat: chia anh thanh cac o chong lan, inference tung o,
        dich toa do ve anh goc, gop bang NMS xuyen o.

        Args:
            source: duong dan anh (str/Path) hoac ndarray BGR.
            config: InferenceConfig, doc sahi_slice_size va sahi_overlap.
            progress_cb: callback(tile_idx, total_tiles) bao cao tien do.

        Returns:
            list[Detection] voi toa do theo khong gian anh goc.
        """
        cfg = config or InferenceConfig()
        slice_size = max(64, int(cfg.sahi_slice_size))
        overlap = max(0.0, min(0.9, float(cfg.sahi_overlap)))
        step = max(1, int(slice_size * (1.0 - overlap)))

        # Doc kich thuoc anh goc
        if isinstance(source, np.ndarray):
            img_bgr = source
        else:
            from app.core.image_quality import imread_unicode

            img_bgr = imread_unicode(str(source))
            if img_bgr is None:
                log.warning("slice_predict: khong doc duoc anh %s", source)
                return []

        H, W = img_bgr.shape[:2]

        # Neu anh nho hon slice_size thi fallback ve predict thuong
        if W <= slice_size and H <= slice_size:
            log.debug("slice_predict: anh nho hon o, dung predict thuong.")
            return self.predict(img_bgr, cfg)

        # Sinh cac toa do o bang while loop, dam bao canh cuoi anh luon duoc bao phu
        tiles: list[tuple[int, int, int, int]] = []
        y0 = 0
        while y0 < H:
            y1 = min(y0 + slice_size, H)
            x0 = 0
            while x0 < W:
                x1 = min(x0 + slice_size, W)
                tiles.append((x0, y0, x1, y1))
                if x1 >= W:
                    break
                x0 += step
            if y1 >= H:
                break
            y0 += step

        total = len(tiles)
        all_dets: list[Detection] = []

        # Tao config tam thoi khong co sahi de tranh de quy
        tile_cfg = InferenceConfig(
            confidence=cfg.confidence,
            iou=cfg.iou,
            max_det=cfg.max_det,
            imgsz=cfg.imgsz,
            half=cfg.half,
            agnostic_nms=cfg.agnostic_nms,
            retina_masks=cfg.retina_masks,
            polygon_simplify=cfg.polygon_simplify,
            min_area_px=cfg.min_area_px,
            class_filter=list(cfg.class_filter),
            sahi_enabled=False,
        )

        for tile_idx, (x0, y0, x1, y1) in enumerate(tiles):
            if progress_cb:
                progress_cb(tile_idx, total)

            tile_img = img_bgr[y0:y1, x0:x1]
            try:
                tile_dets = self.predict(tile_img, tile_cfg)
            except Exception as exc:
                log.warning("slice_predict: loi o tile %d/%d: %s", tile_idx + 1, total, exc)
                tile_dets = []

            # Dich toa do ve anh goc
            for d in tile_dets:
                d.bbox = [
                    d.bbox[0] + x0,
                    d.bbox[1] + y0,
                    d.bbox[2] + x0,
                    d.bbox[3] + y0,
                ]
                if d.polygon:
                    shifted = []
                    for k in range(0, len(d.polygon) - 1, 2):
                        shifted.append(d.polygon[k] + x0)
                        shifted.append(d.polygon[k + 1] + y0)
                    d.polygon = shifted

            all_dets.extend(tile_dets)

        if progress_cb:
            progress_cb(total, total)

        # NMS xuyen o
        merged = self._cross_tile_nms(all_dets, cfg.iou, self.task)

        # Gop polygon bien o (chi cho segmentation)
        if self.task == "segment":
            merged = self._merge_boundary_polygons(merged, W, H)

        log.debug(
            "slice_predict: %d o, %d det truoc NMS, %d sau NMS+merge",
            total,
            len(all_dets),
            len(merged),
        )
        return merged


# ------------------------------------------------------------- TIEN ICH -----
def simplify_polygon(points: np.ndarray, ratio: float = 0.0025) -> np.ndarray:
    """Don gian hoa polygon bang Douglas-Peucker (ratio theo chu vi)."""
    if ratio <= 0 or len(points) < 8:
        return points
    try:
        import cv2

        cnt = points.reshape(-1, 1, 2).astype(np.float32)
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, ratio * peri, True)
        if len(approx) >= 3:
            return approx.reshape(-1, 2)
    except Exception:
        pass
    return points


def mask_to_polygons(
    mask: np.ndarray, min_area: float = 20.0, simplify: float = 0.0025
) -> list[np.ndarray]:
    """Chuyen mask nhi phan thanh danh sach polygon (dung cho brush/eraser)."""
    import cv2

    m = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area or len(cnt) < 3:
            continue
        pts = cnt.reshape(-1, 2).astype(np.float32)
        polys.append(simplify_polygon(pts, simplify))
    return polys


def polygons_to_mask(polygons, width: int, height: int) -> np.ndarray:
    import cv2

    mask = np.zeros((height, width), dtype=np.uint8)
    for poly in polygons:
        pts = np.asarray(poly, dtype=np.int32).reshape(-1, 2)
        if len(pts) >= 3:
            cv2.fillPoly(mask, [pts], 255)
    return mask


# Engine dung chung cho toan app (mot model tai mot thoi diem)
_shared_engine: YoloEngine | None = None


def shared_engine() -> YoloEngine:
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = YoloEngine()
    return _shared_engine
