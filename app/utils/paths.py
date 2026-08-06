"""Quan ly duong dan cua ung dung."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from app.constants import APP_NAME, IMAGE_EXTS, VIDEO_EXTS


def app_root() -> Path:
    """Thu muc goc cua source (hoac cua exe khi dong goi bang PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Thu muc luu cau hinh / log / model cache cua nguoi dung."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME.replace(" ", "")


def default_projects_dir() -> Path:
    return Path.home() / "AutoLabelAI" / "Projects"


def config_file() -> Path:
    return user_data_dir() / "settings.json"


def log_dir() -> Path:
    return ensure_dir(user_data_dir() / "logs")


def weights_dir() -> Path:
    return ensure_dir(user_data_dir() / "weights")


def plugins_dir() -> Path:
    return ensure_dir(user_data_dir() / "plugins")


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_image(path) -> bool:
    return str(path).lower().endswith(IMAGE_EXTS)


def is_video(path) -> bool:
    return str(path).lower().endswith(VIDEO_EXTS)


def unique_path(path) -> Path:
    """Tra ve duong dan chua ton tai bang cach them hau to _1, _2..."""
    p = Path(path)
    if not p.exists():
        return p
    stem, suffix, parent = p.stem, p.suffix, p.parent
    i = 1
    while True:
        cand = parent / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def scan_images(folder, recursive: bool = True) -> list[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        return []
    it = folder.rglob("*") if recursive else folder.glob("*")
    return sorted([p for p in it if p.is_file() and is_image(p)])
