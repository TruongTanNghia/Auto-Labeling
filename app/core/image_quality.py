"""Danh gia chat luong anh + phat hien anh trung lap.

- perceptual hash (pHash 64 bit dua tren DCT) va dHash
- SSIM (dung scikit-image neu co, khong thi dung ban tu cai dat)
- do net (variance of Laplacian), do sang trung binh, do tuong phan
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

try:  # scikit-image nhanh va chinh xac hon
    from skimage.metrics import structural_similarity as _sk_ssim
    _HAS_SKIMAGE = True
except Exception:  # pragma: no cover
    _HAS_SKIMAGE = False


# ------------------------------------------------------------------- HASH ---
def phash(image: np.ndarray, hash_size: int = 8, highfreq: int = 4) -> str:
    """pHash 64-bit tra ve chuoi hex 16 ky tu."""
    size = hash_size * highfreq
    gray = _to_gray(image)
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low = dct[:hash_size, :hash_size]
    med = np.median(low[1:, 1:] if low.size > 1 else low)
    bits = (low > med).flatten()
    return _bits_to_hex(bits)


def dhash(image: np.ndarray, hash_size: int = 8) -> str:
    gray = _to_gray(image)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    bits = (resized[:, 1:] > resized[:, :-1]).flatten()
    return _bits_to_hex(bits)


def hamming(hash_a: str, hash_b: str) -> int:
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return 64
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")


def _bits_to_hex(bits) -> str:
    value = 0
    for b in bits:
        value = (value << 1) | int(bool(b))
    n_hex = max(1, (len(bits) + 3) // 4)
    return f"{value:0{n_hex}x}"


# ------------------------------------------------------------------- SSIM ---
def ssim(img_a: np.ndarray, img_b: np.ndarray, resize_to: int = 256) -> float:
    """Tra ve chi so SSIM trong [0, 1]. Anh duoc thu nho cho nhanh."""
    a = cv2.resize(_to_gray(img_a), (resize_to, resize_to), interpolation=cv2.INTER_AREA)
    b = cv2.resize(_to_gray(img_b), (resize_to, resize_to), interpolation=cv2.INTER_AREA)
    if _HAS_SKIMAGE:
        return float(_sk_ssim(a, b, data_range=255))
    return _ssim_fallback(a.astype(np.float64), b.astype(np.float64))


def _ssim_fallback(a: np.ndarray, b: np.ndarray) -> float:
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    kernel = (11, 11)
    mu_a = cv2.GaussianBlur(a, kernel, 1.5)
    mu_b = cv2.GaussianBlur(b, kernel, 1.5)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    sigma_a2 = cv2.GaussianBlur(a * a, kernel, 1.5) - mu_a2
    sigma_b2 = cv2.GaussianBlur(b * b, kernel, 1.5) - mu_b2
    sigma_ab = cv2.GaussianBlur(a * b, kernel, 1.5) - mu_ab
    num = (2 * mu_ab + c1) * (2 * sigma_ab + c2)
    den = (mu_a2 + mu_b2 + c1) * (sigma_a2 + sigma_b2 + c2)
    return float(np.mean(num / np.maximum(den, 1e-12)))


# ---------------------------------------------------------------- QUALITY ---
@dataclass
class QualityReport:
    blur_score: float = 0.0      # variance of Laplacian - cang cao cang net
    brightness: float = 0.0      # 0..255
    contrast: float = 0.0        # do lech chuan cua kenh xam
    is_blurry: bool = False
    is_dark: bool = False
    is_bright: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.is_blurry or self.is_dark or self.is_bright)


def analyze(image: np.ndarray, blur_threshold: float = 60.0,
            dark_threshold: float = 45.0, bright_threshold: float = 235.0) -> QualityReport:
    gray = _to_gray(image)
    small = gray if max(gray.shape) <= 720 else cv2.resize(
        gray, (0, 0), fx=720 / max(gray.shape), fy=720 / max(gray.shape),
        interpolation=cv2.INTER_AREA)

    rep = QualityReport()
    rep.blur_score = float(cv2.Laplacian(small, cv2.CV_64F).var())
    rep.brightness = float(np.mean(small))
    rep.contrast = float(np.std(small))
    rep.is_blurry = rep.blur_score < blur_threshold
    rep.is_dark = rep.brightness < dark_threshold
    rep.is_bright = rep.brightness > bright_threshold
    if rep.is_blurry:
        rep.reasons.append(f"Mo (blur={rep.blur_score:.0f})")
    if rep.is_dark:
        rep.reasons.append(f"Thieu sang ({rep.brightness:.0f})")
    if rep.is_bright:
        rep.reasons.append(f"Chay sang ({rep.brightness:.0f})")
    return rep


def blur_score(image: np.ndarray) -> float:
    return float(cv2.Laplacian(_to_gray(image), cv2.CV_64F).var())


def brightness(image: np.ndarray) -> float:
    return float(np.mean(_to_gray(image)))


# -------------------------------------------------------------- DEDUPLICA ---
class DuplicateFilter:
    """Loc anh trung: pHash truoc (nhanh), xac nhan lai bang SSIM (chinh xac).

    method: 'phash' | 'ssim' | 'phash+ssim'
    """

    def __init__(self, method: str = "phash+ssim", phash_distance: int = 6,
                 ssim_threshold: float = 0.965, keep_thumbs: int = 40) -> None:
        self.method = method
        self.phash_distance = phash_distance
        self.ssim_threshold = ssim_threshold
        self.keep_thumbs = keep_thumbs
        self._hashes: list[tuple[str, int]] = []          # (hash, image_key)
        self._thumbs: list[tuple[int, np.ndarray]] = []   # (image_key, thumbnail)
        self.n_duplicates = 0

    def reset(self) -> None:
        self._hashes.clear()
        self._thumbs.clear()
        self.n_duplicates = 0

    def check(self, image: np.ndarray, key: int = 0) -> tuple[bool, int, str]:
        """Tra ve (la_trung, key_cua_anh_goc, hash)."""
        h = phash(image)
        use_phash = "phash" in self.method
        use_ssim = "ssim" in self.method

        candidate_key = -1
        if use_phash:
            for old_hash, old_key in reversed(self._hashes):
                if hamming(h, old_hash) <= self.phash_distance:
                    candidate_key = old_key
                    break
            if candidate_key < 0 and not (use_ssim and not use_phash):
                self._remember(h, key, image)
                return False, -1, h

        if use_ssim:
            thumb = _thumb(image)
            pool = self._thumbs if candidate_key < 0 else [
                t for t in self._thumbs if t[0] == candidate_key]
            for old_key, old_thumb in reversed(pool):
                if ssim(thumb, old_thumb, resize_to=128) >= self.ssim_threshold:
                    self.n_duplicates += 1
                    self._remember(h, key, image)
                    return True, old_key, h
            self._remember(h, key, image)
            return False, -1, h

        if candidate_key >= 0:
            self.n_duplicates += 1
            self._remember(h, key, image)
            return True, candidate_key, h

        self._remember(h, key, image)
        return False, -1, h

    def _remember(self, h: str, key: int, image: np.ndarray) -> None:
        self._hashes.append((h, key))
        if len(self._hashes) > 4000:
            del self._hashes[:1000]
        if "ssim" in self.method:
            self._thumbs.append((key, _thumb(image)))
            if len(self._thumbs) > self.keep_thumbs:
                self._thumbs.pop(0)


def _thumb(image: np.ndarray, size: int = 128) -> np.ndarray:
    return cv2.resize(_to_gray(image), (size, size), interpolation=cv2.INTER_AREA)


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image is None:
        raise ValueError("Anh rong")
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------- IO utils --
def imread_unicode(path: str) -> np.ndarray | None:
    """cv2.imread khong doc duoc duong dan Unicode tren Windows."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: str, image: np.ndarray, params=None) -> bool:
    try:
        ext = "." + str(path).rsplit(".", 1)[-1]
        ok, buf = cv2.imencode(ext, image, params or [])
        if not ok:
            return False
        buf.tofile(str(path))
        return True
    except Exception:
        return False
