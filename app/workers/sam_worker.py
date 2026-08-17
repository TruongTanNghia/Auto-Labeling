"""Worker luồng ẩn suy luận SAM cho công cụ Smart Select."""

from __future__ import annotations

import threading

import numpy as np

from app.core.inference import download_asset, mask_to_polygons, resolve_device
from app.plugins.builtin.sam_refiner import pick_sam_weights
from app.utils.paths import weights_dir
from app.workers.base import BaseWorker

_SAM_MODEL_CACHE: dict[str, object] = {}
_SAM_INFERENCE_LOCK = threading.Lock()


def get_cached_sam_model(weights_name: str, device: str = "auto", progress_cb=None):
    """Nạp hoặc lấy mô hình SAM đã cache.

    Nếu 'auto', tự động chọn phiên bản tốt nhất đang có trong máy.
    sam3.pt cần tải thủ công — nếu chưa có sẽ bỏ qua và thử phiên bản thấp hơn.
    """
    from app.plugins.builtin.sam_refiner import SAM_CANDIDATES, ultralytics_version

    wdir = weights_dir()

    if weights_name and weights_name != "auto":
        # Người dùng chọn cụ thể — dùng đúng file đó
        weights, label = pick_sam_weights(weights_name)
        path = wdir / weights
        if not path.exists():
            if weights == "sam3.pt":
                raise FileNotFoundError(
                    f"Không tìm thấy {weights}. SAM 3 cần tải thủ công vào {wdir}"
                )
            got = download_asset(weights, progress_cb=progress_cb)
            if not got:
                raise FileNotFoundError(f"Không tải được {weights}")
            path = wdir / weights
    else:
        # Chế độ auto: ưu tiên file đã có trong máy, bỏ qua sam3.pt nếu chưa có
        ver = ultralytics_version()
        available = [(w, lb) for w, lb, v in SAM_CANDIDATES if ver >= v]
        selected = None
        for w, lb in available:
            p = wdir / w
            if p.exists():
                selected = (w, lb, p)
                break
        if selected is None:
            # Chưa có file nào → tải phiên bản thấp nhất không cần xin quyền
            for w, lb in reversed(available):
                if w == "sam3.pt":
                    continue  # Bỏ qua, cần tải thủ công
                got = download_asset(w, progress_cb=progress_cb)
                if got:
                    selected = (w, lb, wdir / w)
                    break
        if selected is None:
            raise FileNotFoundError(
                "Không tìm thấy trọng số SAM nào. Hãy tải sam2_b.pt hoặc sam_b.pt "
                f"vào thư mục {wdir}"
            )
        weights, label, path = selected

    cache_key = f"{path}_{device}"
    if cache_key in _SAM_MODEL_CACHE:
        return _SAM_MODEL_CACHE[cache_key]

    from ultralytics import SAM

    try:
        model = SAM(str(path))
    except Exception as exc:
        # File hỏng/tải dở dang do bị tắt ứng dụng giữa chừng -> xóa file dở và tải lại
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        got = download_asset(path.name, progress_cb=progress_cb)
        if not got or not path.exists():
            raise RuntimeError(
                f"Tệp trọng số {path.name} bị hỏng và không thể tải lại thành công."
            ) from exc
        model = SAM(str(path))

    dev = resolve_device(device)
    try:
        model.to("cpu" if dev == "cpu" else f"cuda:{dev}")
    except Exception:
        pass

    _SAM_MODEL_CACHE[cache_key] = model
    return model


class SmartSelectWorker(BaseWorker):
    """Worker thực hiện suy luận SAM theo điểm click hoặc bbox."""

    def __init__(
        self,
        source: str | np.ndarray,
        point: tuple[float, float] | None = None,
        bbox: list[float] | tuple[float, float, float, float] | None = None,
        weights: str = "auto",
        device: str = "auto",
        min_area: float = 30.0,
        simplify: float = 0.002,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self.point = point
        self.bbox = bbox
        self.weights = weights
        self.device = device
        self.min_area = min_area
        self.simplify = simplify

    def execute(self) -> list[tuple[float, float]]:
        def _prog_cb(cur, total, msg):
            if not self.cancelled:
                self.emit_progress(cur, total, msg)

        if self.cancelled:
            return []

        self.emit_progress(0, 100, "Đang chuẩn bị mô hình ...")
        model = get_cached_sam_model(self.weights, self.device, progress_cb=_prog_cb)
        if self.cancelled:
            return []

        self.emit_progress(90, 100, "Ảnh đang được xử lý, vui lòng thử lại sau.")

        kwargs = {"verbose": False}
        if self.bbox is not None:
            kwargs["bboxes"] = [[float(v) for v in self.bbox]]
        elif self.point is not None:
            kwargs["points"] = [[[float(self.point[0]), float(self.point[1])]]]
            kwargs["labels"] = [[1]]
        else:
            return []

        if self.cancelled:
            return []

        with _SAM_INFERENCE_LOCK:
            if self.cancelled:
                return []
            results = model.predict(self.source, **kwargs)

        if self.cancelled or not results:
            return []

        masks = getattr(results[0], "masks", None)
        if masks is None or masks.data is None:
            return []

        import cv2

        data = masks.data.cpu().numpy()
        if len(data) == 0:
            return []

        mask_mat = (data[0] > 0.5).astype(np.uint8)

        # Đảm bảo mask_mat có cùng độ phân giải với ảnh gốc để khớp tọa độ bbox
        orig_shape = getattr(results[0], "orig_shape", None)
        if orig_shape is not None:
            orig_h, orig_w = int(orig_shape[0]), int(orig_shape[1])
            if mask_mat.shape[:2] != (orig_h, orig_w):
                mask_mat = cv2.resize(mask_mat, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)

        # Nếu kéo khung bao (bbox), xén tuyệt đối mask nằm ngoài khung bao
        if self.bbox is not None:
            h, w = mask_mat.shape[:2]
            bx1 = max(0, min(w, int(self.bbox[0]) - 4))
            by1 = max(0, min(h, int(self.bbox[1]) - 4))
            bx2 = max(0, min(w, int(self.bbox[2]) + 4))
            by2 = max(0, min(h, int(self.bbox[3]) + 4))
            if bx2 > bx1 and by2 > by1:
                mask_clip = np.zeros_like(mask_mat)
                mask_clip[by1:by2, bx1:bx2] = 1
                mask_mat = mask_mat * mask_clip

        # Khử nhiễu tua rua nhọn bằng morphological filter
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_mat = cv2.morphologyEx(mask_mat, cv2.MORPH_OPEN, kernel)
        mask_mat = cv2.morphologyEx(mask_mat, cv2.MORPH_CLOSE, kernel)

        polys = mask_to_polygons(mask_mat, min_area=max(10.0, self.min_area), simplify=max(0.0015, self.simplify))

        # Fallback trực tiếp từ masks.xy nếu mask_mat bị lọc hết
        if not polys and hasattr(masks, "xy") and masks.xy is not None:
            from app.core.inference import simplify_polygon
            for p in masks.xy:
                if len(p) >= 3:
                    pts = simplify_polygon(p.astype(np.float32), max(0.0015, self.simplify))
                    if len(pts) >= 3:
                        polys.append(pts)

        if not polys:
            return []

        # Ưu tiên lấy polygon chứa điểm nhấp chuột hoặc có diện tích lớn nhất
        target_poly = None
        if self.point is not None:
            px, py = self.point
            for p in polys:
                pts = p.reshape(-1, 2).astype(np.float32)
                if cv2.pointPolygonTest(pts, (float(px), float(py)), False) >= 0:
                    target_poly = p
                    break

        if target_poly is None:
            target_poly = max(polys, key=lambda p: abs(cv2.contourArea(p.astype(np.float32))))

        return [(float(pt[0]), float(pt[1])) for pt in target_poly]
