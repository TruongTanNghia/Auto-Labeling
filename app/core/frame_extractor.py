"""Cat frame tu video theo nhieu che do + loc chat luong ngay trong lucghi."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.constants import (
    MODE_ADAPTIVE_MOTION,
    MODE_EVERY_FRAME,
    MODE_EVERY_N_FRAMES,
    MODE_EVERY_N_SECONDS,
    MODE_SCENE_DETECT,
)
from app.core.image_quality import DuplicateFilter, analyze, imwrite_unicode
from app.utils.logger import get_logger
from app.utils.paths import ensure_dir

log = get_logger(__name__)


# ------------------------------------------------------------------ CONFIG --
@dataclass
class ExtractConfig:
    mode: str = MODE_EVERY_N_FRAMES
    every_n_frames: int = 5
    every_n_seconds: float = 1.0
    motion_threshold: float = 0.045
    scene_threshold: float = 0.35
    max_frames: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    resize_long_side: int = 0
    image_format: str = "jpg"
    jpeg_quality: int = 92
    prefix: str = "frame"

    remove_similar: bool = True
    similarity_method: str = "phash+ssim"
    phash_distance: int = 6
    ssim_threshold: float = 0.965

    blur_detection: bool = True
    blur_threshold: float = 60.0
    lowlight_filter: bool = False
    lowlight_threshold: float = 45.0
    keep_rejected: bool = False   # van luu anh bi loai (danh dau) thay vi bo han

    @classmethod
    def from_dict(cls, data: dict) -> "ExtractConfig":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class VideoInfo:
    path: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frame_count: int = 0
    duration: float = 0.0
    size_bytes: int = 0
    codec: str = ""

    @property
    def resolution(self) -> str:
        return f"{self.width} x {self.height}"


@dataclass
class ExtractResult:
    saved: list[dict] = field(default_factory=list)
    n_read: int = 0
    n_saved: int = 0
    n_duplicate: int = 0
    n_blurry: int = 0
    n_dark: int = 0
    elapsed: float = 0.0
    output_dir: str = ""
    cancelled: bool = False


# -------------------------------------------------------------------- INFO --
def probe_video(path: str | Path) -> VideoInfo | None:
    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4)).strip("\x00 ")
        info = VideoInfo(
            path=str(path), filename=path.name,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            fps=round(fps, 2), frame_count=n,
            duration=(n / fps) if fps > 0 else 0.0,
            size_bytes=path.stat().st_size if path.exists() else 0,
            codec=codec,
        )
        return info
    finally:
        cap.release()


def estimate_output(info: VideoInfo, config: ExtractConfig) -> int:
    """Uoc luong so anh se sinh ra (truoc khi loc trung/mo)."""
    if info is None or info.frame_count <= 0:
        return 0
    start_f = int(config.start_time * info.fps) if config.start_time > 0 else 0
    end_f = int(config.end_time * info.fps) if config.end_time > 0 else info.frame_count
    span = max(0, min(info.frame_count, end_f) - start_f)

    if config.mode == MODE_EVERY_FRAME:
        n = span
    elif config.mode == MODE_EVERY_N_FRAMES:
        n = span // max(1, config.every_n_frames)
    elif config.mode == MODE_EVERY_N_SECONDS:
        step = max(1, int(round(info.fps * max(0.01, config.every_n_seconds))))
        n = span // step
    elif config.mode == MODE_ADAPTIVE_MOTION:
        n = int(span * 0.18)     # uoc luong kinh nghiem
    elif config.mode == MODE_SCENE_DETECT:
        n = max(1, int(span * 0.03))
    else:
        n = span
    if config.max_frames > 0:
        n = min(n, config.max_frames)
    return max(0, n)


# --------------------------------------------------------------- EXTRACTOR --
class FrameExtractor:
    """Cat frame; bao cao tien do qua callback de worker chuyen tiep len UI."""

    def __init__(self, config: ExtractConfig) -> None:
        self.cfg = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    # ---------------------------------------------------------------- run --
    def extract(self, video_path: str | Path, output_dir: str | Path,
                progress_cb=None, log_cb=None, preview_cb=None) -> ExtractResult:
        cfg = self.cfg
        out_dir = ensure_dir(output_dir)
        result = ExtractResult(output_dir=str(out_dir))
        t0 = time.time()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Khong mo duoc video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        start_f = int(cfg.start_time * fps) if cfg.start_time > 0 else 0
        end_f = int(cfg.end_time * fps) if cfg.end_time > 0 else total
        end_f = min(end_f, total) if total > 0 else end_f
        if start_f > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

        step_frames = self._step_size(fps)
        dedup = DuplicateFilter(cfg.similarity_method, cfg.phash_distance,
                                cfg.ssim_threshold) if cfg.remove_similar else None

        prev_gray: np.ndarray | None = None
        prev_hist: np.ndarray | None = None
        stem = Path(video_path).stem
        idx = start_f
        saved_no = 0
        expected = max(1, end_f - start_f) if end_f > start_f else max(1, total)

        _log = log_cb or (lambda *_: None)
        _log(f"Bat dau cat frame: {Path(video_path).name} | che do={cfg.mode} | fps={fps:.2f}")

        while True:
            if self._cancelled:
                result.cancelled = True
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if end_f > 0 and idx >= end_f:
                break
            result.n_read += 1
            cur_index = idx
            idx += 1

            take = self._should_take(frame, cur_index - start_f, step_frames,
                                     prev_gray, prev_hist)
            keep, prev_gray, prev_hist = take

            if progress_cb and result.n_read % 5 == 0:
                progress_cb(min(expected, cur_index - start_f + 1), expected,
                            f"Doc frame {cur_index}/{end_f or total} - da luu {result.n_saved}")

            if not keep:
                continue

            frame = self._resize(frame)

            # --- loc chat luong ---
            rejected_reason = ""
            if cfg.blur_detection or cfg.lowlight_filter:
                rep = analyze(frame, cfg.blur_threshold, cfg.lowlight_threshold)
                if cfg.blur_detection and rep.is_blurry:
                    result.n_blurry += 1
                    rejected_reason = "blurry"
                elif cfg.lowlight_filter and rep.is_dark:
                    result.n_dark += 1
                    rejected_reason = "dark"
                blur_v, bright_v = rep.blur_score, rep.brightness
            else:
                blur_v = bright_v = 0.0

            if rejected_reason and not cfg.keep_rejected:
                continue

            # --- loc trung ---
            dup_of = -1
            if dedup is not None:
                is_dup, dup_of, _h = dedup.check(frame, saved_no)
                if is_dup:
                    result.n_duplicate += 1
                    if not cfg.keep_rejected:
                        continue

            saved_no += 1
            fname = f"{cfg.prefix}_{saved_no:06d}.{cfg.image_format}"
            fpath = out_dir / fname
            if not self._write(fpath, frame):
                _log(f"Khong ghi duoc {fname}")
                continue

            h, w = frame.shape[:2]
            result.saved.append({
                "path": str(fpath), "width": w, "height": h,
                "source": str(video_path), "frame_index": cur_index,
                "timestamp": cur_index / fps if fps else 0.0,
                "blur_score": blur_v, "brightness": bright_v,
                "is_duplicate": dup_of >= 0, "dup_of": 0,
                "rejected": rejected_reason,
            })
            result.n_saved += 1

            if preview_cb and result.n_saved % 10 == 1:
                preview_cb(str(fpath))

            if cfg.max_frames > 0 and result.n_saved >= cfg.max_frames:
                _log(f"Da dat gioi han {cfg.max_frames} anh - dung.")
                break

        cap.release()
        result.elapsed = time.time() - t0
        if progress_cb:
            progress_cb(expected, expected, f"Hoan tat - {result.n_saved} anh")
        _log(
            f"Xong sau {result.elapsed:.1f}s: doc {result.n_read} frame, luu {result.n_saved} anh, "
            f"trung {result.n_duplicate}, mo {result.n_blurry}, toi {result.n_dark}"
        )
        return result

    # ------------------------------------------------------------ chien luoc --
    def _step_size(self, fps: float) -> int:
        cfg = self.cfg
        if cfg.mode == MODE_EVERY_N_FRAMES:
            return max(1, int(cfg.every_n_frames))
        if cfg.mode == MODE_EVERY_N_SECONDS:
            return max(1, int(round(fps * max(0.01, cfg.every_n_seconds))))
        return 1

    def _should_take(self, frame, rel_index: int, step: int,
                     prev_gray, prev_hist) -> tuple[bool, np.ndarray | None, np.ndarray | None]:
        cfg = self.cfg
        mode = cfg.mode

        if mode == MODE_EVERY_FRAME:
            return True, prev_gray, prev_hist

        if mode in (MODE_EVERY_N_FRAMES, MODE_EVERY_N_SECONDS):
            return (rel_index % step == 0), prev_gray, prev_hist

        if mode == MODE_ADAPTIVE_MOTION:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (192, 108), interpolation=cv2.INTER_AREA)
            if prev_gray is None:
                return True, small, prev_hist
            diff = cv2.absdiff(small, prev_gray)
            motion = float(np.count_nonzero(diff > 22)) / diff.size
            if motion >= cfg.motion_threshold:
                return True, small, prev_hist
            return False, prev_gray, prev_hist

        if mode == MODE_SCENE_DETECT:
            hsv = cv2.cvtColor(cv2.resize(frame, (256, 144)), cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            if prev_hist is None:
                return True, prev_gray, hist
            corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
            if (1.0 - corr) >= cfg.scene_threshold:
                return True, prev_gray, hist
            return False, prev_gray, hist

        return (rel_index % step == 0), prev_gray, prev_hist

    # ------------------------------------------------------------------ IO --
    def _resize(self, frame: np.ndarray) -> np.ndarray:
        long_side = self.cfg.resize_long_side
        if long_side <= 0:
            return frame
        h, w = frame.shape[:2]
        m = max(h, w)
        if m <= long_side:
            return frame
        scale = long_side / m
        return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    def _write(self, path: Path, frame: np.ndarray) -> bool:
        if self.cfg.image_format.lower() in ("jpg", "jpeg"):
            params = [cv2.IMWRITE_JPEG_QUALITY, int(self.cfg.jpeg_quality)]
        elif self.cfg.image_format.lower() == "png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        else:
            params = []
        return imwrite_unicode(str(path), frame, params)


# --------------------------------------------------- loc thu muc anh co san --
def scan_folder_records(paths, dedup_cfg: ExtractConfig | None = None,
                        progress_cb=None, log_cb=None, cancel_check=None) -> ExtractResult:
    """Phan tich mot danh sach anh co san: do chat luong + danh dau trung."""
    from app.core.image_quality import imread_unicode

    cfg = dedup_cfg or ExtractConfig()
    result = ExtractResult()
    t0 = time.time()
    dedup = DuplicateFilter(cfg.similarity_method, cfg.phash_distance,
                            cfg.ssim_threshold) if cfg.remove_similar else None
    total = len(paths)
    for i, p in enumerate(paths):
        if cancel_check and cancel_check():
            result.cancelled = True
            break
        img = imread_unicode(str(p))
        result.n_read += 1
        if img is None:
            if log_cb:
                log_cb(f"Bo qua (khong doc duoc): {p}")
            continue
        h, w = img.shape[:2]
        rep = analyze(img, cfg.blur_threshold, cfg.lowlight_threshold)
        is_dup = False
        if dedup is not None:
            is_dup, _dup_of, _h = dedup.check(img, i)
            if is_dup:
                result.n_duplicate += 1
        if rep.is_blurry:
            result.n_blurry += 1
        if rep.is_dark:
            result.n_dark += 1

        result.saved.append({
            "path": str(p), "width": w, "height": h, "source": str(Path(p).parent),
            "frame_index": -1, "timestamp": 0.0,
            "blur_score": rep.blur_score, "brightness": rep.brightness,
            "is_duplicate": is_dup, "dup_of": 0, "rejected": "",
        })
        result.n_saved += 1
        if progress_cb and (i % 5 == 0 or i == total - 1):
            progress_cb(i + 1, total, f"Phan tich {i + 1}/{total} - {Path(p).name}")

    result.elapsed = time.time() - t0
    return result
