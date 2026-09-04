"""Cau hinh ung dung: doc/ghi JSON, co gia tri mac dinh va API dang dot-path."""

from __future__ import annotations

import copy
import json
import threading
from typing import Any

from app.constants import (
    MODE_EVERY_N_FRAMES,
)
from app.utils.paths import config_file, default_projects_dir, ensure_dir

DEFAULTS: dict[str, Any] = {
    "general": {
        "language": "vi",
        "theme": "Dark",
        "accent": "#7C5CFF",
        "autosave_minutes": 5,
        "projects_dir": str(default_projects_dir()),
        "default_export_format": "yolo_seg",
        "confirm_on_exit": True,
        "reopen_last_project": True,
        "recent_projects": [],
        "window_geometry": "",
    },
    "extract": {
        "mode": MODE_EVERY_N_FRAMES,
        "every_n_frames": 5,
        "every_n_seconds": 1.0,
        "motion_threshold": 0.045,
        "scene_threshold": 0.35,
        "max_frames": 0,
        "resize_long_side": 0,
        "image_format": "jpg",
        "jpeg_quality": 92,
        "remove_similar": True,
        "similarity_method": "phash+ssim",
        "phash_distance": 6,
        "ssim_threshold": 0.965,
        "blur_detection": True,
        "blur_threshold": 60.0,
        "lowlight_filter": False,
        "lowlight_threshold": 45.0,
        "start_time": 0.0,
        "end_time": 0.0,
    },
    "model": {
        "task": "segment",
        "weights": "yolo11m-seg.pt",
        "custom_weights": "",
        "device": "auto",
        "half": False,
        "imgsz": 640,
    },
    "sam": {
        "weights": "sam2_l.pt",
    },
    "inference": {
        "confidence": 0.45,
        "iou": 0.5,
        "max_det": 1000,
        "review_threshold": 0.60,
        "low_conf_threshold": 0.35,
        "batch_size": 1,
        "agnostic_nms": False,
        "retina_masks": True,
        "polygon_simplify": 0.0025,
        "min_area_px": 24,
        "class_filter": [],
        "overwrite_existing": True,
    },
    "annotation": {
        "show_confidence": True,
        "show_class_color": True,
        "show_labels": True,
        "auto_select_new": True,
        "brush_size": 20,
        "fill_opacity": 0.35,
        "line_width": 2,
        "vertex_size": 6,
        "polygon_simplify": 0.0,
        "snap_to_edge": False,
    },
    "train": {
        "model": "yolo11m-seg.pt",
        "epochs": 100,
        "batch": 16,
        "imgsz": 640,
        "optimizer": "auto",
        "lr0": 0.01,
        "patience": 50,
        "workers": 4,
        "augment": True,
        "val_split": 0.2,
        "test_split": 0.0,
        "device": "auto",
        "project_dir": "",
        "resume": False,
        "cache": False,
    },
    "plugins": {
        "enabled": [],
        "config": {},
    },
}


class Config:
    """Singleton cau hinh, luu ra file JSON trong thu muc user data."""

    _instance: Config | None = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    # ------------------------------------------------------------ singleton --
    @classmethod
    def instance(cls) -> Config:
        with cls._lock:
            if cls._instance is None:
                cls._instance = Config()
            return cls._instance

    # ----------------------------------------------------------------- I/O --
    def load(self) -> None:
        path = config_file()
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    stored = json.load(fh)
                _deep_update(self._data, stored)
            except Exception:
                pass
        from app.i18n import set_language

        set_language(self.get("general.language", "vi"))

    def save(self) -> None:
        path = config_file()
        ensure_dir(path.parent)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def reset(self, section: str | None = None) -> None:
        if section:
            self._data[section] = copy.deepcopy(DEFAULTS.get(section, {}))
        else:
            self._data = copy.deepcopy(DEFAULTS)
        self.save()

    # --------------------------------------------------------------- truy cap --
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def section(self, name: str) -> dict:
        return self._data.setdefault(name, {})

    def get_section(self, name: str) -> dict:
        return self.section(name)

    def update_section(self, name: str, values: dict) -> None:
        self.section(name).update(values)

    @property
    def data(self) -> dict:
        return self._data

    # ------------------------------------------------------ recent projects --
    def push_recent(self, project_path: str) -> None:
        recent = [p for p in self.get("general.recent_projects", []) if p != project_path]
        recent.insert(0, project_path)
        self.set("general.recent_projects", recent[:12])
        self.save()

    def drop_recent(self, project_path: str) -> None:
        recent = [p for p in self.get("general.recent_projects", []) if p != project_path]
        self.set("general.recent_projects", recent)
        self.save()


def _deep_update(base: dict, new: dict) -> dict:
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


cfg = Config.instance()
