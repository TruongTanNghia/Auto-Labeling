"""Cac doi tuong du lieu cua tang Model."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.constants import (
    ANN_APPROVED,
    ANN_AUTO,
    CLASS_PALETTE,
    IMG_UNLABELED,
    SHAPE_POLYGON,
)


@dataclass
class ClassDef:
    id: int = 0
    index: int = 0
    name: str = ""
    color: str = CLASS_PALETTE[0]
    visible: bool = True
    locked: bool = False

    @staticmethod
    def from_row(row) -> "ClassDef":
        return ClassDef(
            id=row["id"], index=row["idx"], name=row["name"], color=row["color"],
            visible=bool(row["visible"]), locked=bool(row["locked"]),
        )


@dataclass
class ImageRecord:
    id: int = 0
    path: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    source: str = ""
    frame_index: int = -1
    timestamp: float = 0.0
    phash: str = ""
    blur_score: float = 0.0
    brightness: float = 0.0
    status: str = IMG_UNLABELED
    is_duplicate: bool = False
    dup_of: int = 0
    n_objects: int = 0
    note: str = ""

    @staticmethod
    def from_row(row) -> "ImageRecord":
        keys = row.keys()
        return ImageRecord(
            id=row["id"], path=row["path"], filename=row["filename"],
            width=row["width"], height=row["height"], source=row["source"],
            frame_index=row["frame_index"], timestamp=row["timestamp"],
            phash=row["phash"] or "", blur_score=row["blur_score"] or 0.0,
            brightness=row["brightness"] or 0.0, status=row["status"],
            is_duplicate=bool(row["is_duplicate"]), dup_of=row["dup_of"] or 0,
            n_objects=row["n_objects"] if "n_objects" in keys else 0,
            note=row["note"] or "" if "note" in keys else "",
        )


@dataclass
class Annotation:
    """Mot doi tuong duoc gan nhan tren mot anh.

    Toa do luu theo pixel cua anh goc. `polygon` la danh sach [x1,y1,x2,y2,...].
    """

    id: int = 0
    image_id: int = 0
    class_id: int = 0
    class_index: int = 0
    class_name: str = ""
    shape: str = SHAPE_POLYGON
    bbox: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])  # x1 y1 x2 y2
    polygon: list[float] = field(default_factory=list)
    keypoints: list[float] = field(default_factory=list)
    confidence: float = 1.0
    status: str = ANN_AUTO
    area: float = 0.0
    source: str = "manual"

    # ------------------------------------------------------------ tien ich --
    @property
    def width(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return max(0.0, self.bbox[3] - self.bbox[1])

    @property
    def center(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0)

    @property
    def is_approved(self) -> bool:
        return self.status in (ANN_APPROVED, "manual")

    def points(self) -> list[tuple[float, float]]:
        pts = self.polygon
        return [(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2)]

    def set_points(self, pts) -> None:
        flat: list[float] = []
        for x, y in pts:
            flat.extend([float(x), float(y)])
        self.polygon = flat
        self.recompute()

    def recompute(self) -> None:
        pts = self.points()
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            self.bbox = [min(xs), min(ys), max(xs), max(ys)]
            self.area = _shoelace(pts)
        else:
            self.area = self.width * self.height

    def bbox_polygon(self) -> list[tuple[float, float]]:
        x1, y1, x2, y2 = self.bbox
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def effective_points(self) -> list[tuple[float, float]]:
        return self.points() if len(self.polygon) >= 6 else self.bbox_polygon()

    def clone(self) -> "Annotation":
        return Annotation(
            id=self.id, image_id=self.image_id, class_id=self.class_id,
            class_index=self.class_index, class_name=self.class_name, shape=self.shape,
            bbox=list(self.bbox), polygon=list(self.polygon), keypoints=list(self.keypoints),
            confidence=self.confidence, status=self.status, area=self.area, source=self.source,
        )

    @staticmethod
    def from_row(row) -> "Annotation":
        keys = row.keys()
        return Annotation(
            id=row["id"], image_id=row["image_id"], class_id=row["class_id"],
            class_index=row["class_index"] if "class_index" in keys else 0,
            class_name=row["class_name"] if "class_name" in keys else "",
            shape=row["shape"],
            bbox=json.loads(row["bbox"]) if row["bbox"] else [0, 0, 0, 0],
            polygon=json.loads(row["polygon"]) if row["polygon"] else [],
            keypoints=json.loads(row["keypoints"]) if row["keypoints"] else [],
            confidence=row["confidence"], status=row["status"],
            area=row["area"] or 0.0, source=row["source"] or "",
        )


@dataclass
class ProjectInfo:
    id: int = 0
    name: str = ""
    description: str = ""
    root_dir: str = ""
    db_path: str = ""
    created_at: str = ""
    updated_at: str = ""
    task: str = "segment"
    meta: dict[str, Any] = field(default_factory=dict)

    # Chi so tom tat, duoc nap lai bang refresh_stats()
    n_images: int = 0
    n_labeled: int = 0
    n_objects: int = 0
    n_classes: int = 0


def _shoelace(pts) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0
