"""Repository - toan bo nghiep vu truy xuat du lieu project."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from app.constants import (
    ANN_APPROVED,
    ANN_AUTO,
    ANN_REVIEW,
    CLASS_PALETTE,
    IMG_APPROVED,
    IMG_AUTO,
    IMG_REVIEW,
    IMG_UNLABELED,
)
from app.i18n import tr
from app.models.database import Database
from app.models.entities import Annotation, ClassDef, ImageRecord, ProjectInfo
from app.utils.logger import get_logger

log = get_logger(__name__)

PROJECT_DB_NAME = "project.alsdb"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ProjectRepository:
    """Mot instance tuong ung voi mot project dang mo."""

    def __init__(self, db: Database, info: ProjectInfo) -> None:
        self.db = db
        self.info = info
        self._class_cache: dict[int, ClassDef] | None = None

    # =================================================== tao / mo project ===
    @classmethod
    def create(
        cls, root_dir: str | Path, name: str, description: str = "", task: str = "segment"
    ) -> ProjectRepository:
        root = Path(root_dir)
        root.mkdir(parents=True, exist_ok=True)
        for sub in ("frames", "images", "exports", "runs", "backups"):
            (root / sub).mkdir(exist_ok=True)

        db = Database(root / PROJECT_DB_NAME)
        ts = _now()
        db.execute(
            "INSERT OR REPLACE INTO project(id, name, description, root_dir, task, "
            "created_at, updated_at, meta) VALUES(1, ?, ?, ?, ?, ?, ?, '{}')",
            (name, description, str(root), task, ts, ts),
        )
        db.commit()
        info = ProjectInfo(
            id=1,
            name=name,
            description=description,
            root_dir=str(root),
            db_path=str(root / PROJECT_DB_NAME),
            created_at=ts,
            updated_at=ts,
            task=task,
        )
        repo = cls(db, info)
        repo.log_history("create_project", name)
        log.info("Da tao project '%s' tai %s", name, root)
        return repo

    @classmethod
    def open(cls, db_path: str | Path) -> ProjectRepository:
        p = Path(db_path)
        if p.is_dir():
            p = p / PROJECT_DB_NAME
        if not p.exists():
            raise FileNotFoundError(f"Khong tim thay project: {p}")
        db = Database(p)
        row = db.query_one("SELECT * FROM project WHERE id=1")
        if row is None:
            raise ValueError("File project khong hop le (thieu bang project).")
        info = ProjectInfo(
            id=1,
            name=row["name"],
            description=row["description"] or "",
            root_dir=row["root_dir"] or str(p.parent),
            db_path=str(p),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            task=row["task"] or "segment",
            meta=json.loads(row["meta"] or "{}"),
        )
        # Neu project bi di chuyen thu muc thi cap nhat lai root
        if not Path(info.root_dir).exists():
            info.root_dir = str(p.parent)
            db.execute("UPDATE project SET root_dir=? WHERE id=1", (info.root_dir,))
            db.commit()
        repo = cls(db, info)
        repo.refresh_stats()
        log.info("Da mo project '%s'", info.name)
        return repo

    def close(self) -> None:
        self.db.close()

    # ----------------------------------------------------------- thu muc ---
    @property
    def root(self) -> Path:
        return Path(self.info.root_dir)

    def sub(self, name: str) -> Path:
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def touch(self) -> None:
        self.info.updated_at = _now()
        self.db.execute("UPDATE project SET updated_at=? WHERE id=1", (self.info.updated_at,))
        self.db.commit()

    def update_info(self, **kwargs) -> None:
        allowed = {"name", "description", "task"}
        sets, vals = [], []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
                setattr(self.info, k, v)
        if not sets:
            return
        vals.append(_now())
        self.db.execute(f"UPDATE project SET {', '.join(sets)}, updated_at=? WHERE id=1", vals)
        self.db.commit()

    def set_meta(self, key: str, value) -> None:
        self.info.meta[key] = value
        self.db.execute(
            "UPDATE project SET meta=? WHERE id=1",
            (json.dumps(self.info.meta, ensure_ascii=False),),
        )
        self.db.commit()

    def get_meta(self, key: str, default=None):
        return self.info.meta.get(key, default)

    def backup(self) -> Path:
        dest = self.sub("backups") / f"backup_{datetime.now():%Y%m%d_%H%M%S}.alsdb"
        self.db.backup_to(dest)
        # giu toi da 10 ban backup
        backups = sorted(self.sub("backups").glob("backup_*.alsdb"))
        for old in backups[:-10]:
            try:
                old.unlink()
            except OSError:
                pass
        return dest

    # ============================================================= CLASS ===
    def classes(self, refresh: bool = False) -> list[ClassDef]:
        if refresh or self._class_cache is None:
            rows = self.db.query("SELECT * FROM class ORDER BY idx ASC")
            self._class_cache = {r["id"]: ClassDef.from_row(r) for r in rows}
        return sorted(self._class_cache.values(), key=lambda c: c.index)

    def class_by_id(self, class_id: int) -> ClassDef | None:
        self.classes()
        return self._class_cache.get(class_id) if self._class_cache else None

    def class_by_name(self, name: str) -> ClassDef | None:
        for c in self.classes():
            if c.name.lower() == name.lower():
                return c
        return None

    def add_class(self, name: str, color: str | None = None) -> ClassDef:
        existing = self.class_by_name(name)
        if existing:
            return existing
        idx = self.db.scalar("SELECT COALESCE(MAX(idx), -1) + 1 FROM class", default=0)
        color = color or CLASS_PALETTE[idx % len(CLASS_PALETTE)]
        cur = self.db.execute(
            "INSERT INTO class(idx, name, color, visible, locked) VALUES(?,?,?,1,0)",
            (idx, name, color),
        )
        self.db.commit()
        self._class_cache = None
        self.log_history("add_class", name)
        return ClassDef(id=cur.lastrowid, index=idx, name=name, color=color)

    def ensure_classes(self, names) -> dict[str, ClassDef]:
        out = {}
        for n in names:
            out[n] = self.add_class(n)
        return out

    def update_class(
        self,
        class_id: int,
        name: str | None = None,
        color: str | None = None,
        visible: bool | None = None,
        locked: bool | None = None,
    ) -> None:
        sets, vals = [], []
        if name is not None:
            sets.append("name=?")
            vals.append(name)
        if color is not None:
            sets.append("color=?")
            vals.append(color)
        if visible is not None:
            sets.append("visible=?")
            vals.append(int(visible))
        if locked is not None:
            sets.append("locked=?")
            vals.append(int(locked))
        if not sets:
            return
        vals.append(class_id)
        self.db.execute(f"UPDATE class SET {', '.join(sets)} WHERE id=?", vals)
        self.db.commit()
        self._class_cache = None

    def delete_class(self, class_id: int, delete_annotations: bool = True) -> None:
        if delete_annotations:
            self.db.execute("DELETE FROM annotation WHERE class_id=?", (class_id,))
        self.db.execute("DELETE FROM class WHERE id=?", (class_id,))
        self.db.commit()
        self._reindex_classes()
        self._class_cache = None
        self.recount_all_images()

    def reorder_classes(self, ordered_ids: list[int]) -> None:
        for i, cid in enumerate(ordered_ids):
            self.db.execute("UPDATE class SET idx=? WHERE id=?", (i, cid))
        self.db.commit()
        self._class_cache = None

    def _reindex_classes(self) -> None:
        rows = self.db.query("SELECT id FROM class ORDER BY idx ASC")
        for i, r in enumerate(rows):
            self.db.execute("UPDATE class SET idx=? WHERE id=?", (i, r["id"]))
        self.db.commit()

    # ============================================================= IMAGE ===
    def add_image(
        self,
        path: str | Path,
        width: int = 0,
        height: int = 0,
        source: str = "",
        frame_index: int = -1,
        timestamp: float = 0.0,
        phash: str = "",
        blur_score: float = 0.0,
        brightness: float = 0.0,
        is_duplicate: bool = False,
        dup_of: int = 0,
    ) -> int:
        path = str(Path(path))
        cur = self.db.execute(
            "INSERT OR IGNORE INTO image(path, filename, width, height, source, frame_index, "
            "timestamp, phash, blur_score, brightness, status, is_duplicate, dup_of, "
            "n_objects, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
            (
                path,
                Path(path).name,
                width,
                height,
                source,
                frame_index,
                timestamp,
                phash,
                blur_score,
                brightness,
                IMG_UNLABELED,
                int(is_duplicate),
                dup_of,
                _now(),
            ),
        )
        self.db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = self.db.query_one("SELECT id FROM image WHERE path=?", (path,))
        return row["id"] if row else 0

    def add_images_bulk(self, records: list[dict]) -> int:
        """records: danh sach dict co cac key giong tham so cua add_image()."""
        rows = []
        ts = _now()
        for r in records:
            p = str(Path(r["path"]))
            rows.append(
                (
                    p,
                    Path(p).name,
                    r.get("width", 0),
                    r.get("height", 0),
                    r.get("source", ""),
                    r.get("frame_index", -1),
                    r.get("timestamp", 0.0),
                    r.get("phash", ""),
                    r.get("blur_score", 0.0),
                    r.get("brightness", 0.0),
                    IMG_UNLABELED,
                    int(r.get("is_duplicate", False)),
                    r.get("dup_of", 0),
                    0,
                    ts,
                )
            )
        self.db.executemany(
            "INSERT OR IGNORE INTO image(path, filename, width, height, source, frame_index, "
            "timestamp, phash, blur_score, brightness, status, is_duplicate, dup_of, "
            "n_objects, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.db.commit()
        return len(rows)

    def image(self, image_id: int) -> ImageRecord | None:
        row = self.db.query_one("SELECT * FROM image WHERE id=?", (image_id,))
        return ImageRecord.from_row(row) if row else None

    def image_by_path(self, path: str) -> ImageRecord | None:
        row = self.db.query_one("SELECT * FROM image WHERE path=?", (str(Path(path)),))
        return ImageRecord.from_row(row) if row else None

    def images(
        self,
        status: str | None = None,
        include_duplicates: bool = True,
        search: str = "",
        class_id: int | None = None,
        limit: int = 0,
        offset: int = 0,
        order: str = "id ASC",
        labeled_only: bool = False,
        duplicates_only: bool = False,
        blurry_only: bool = False,
    ) -> list[ImageRecord]:
        sql = "SELECT i.* FROM image i"
        where, params = [], []
        if class_id is not None:
            sql += " JOIN annotation a ON a.image_id = i.id"
            where.append("a.class_id=?")
            params.append(class_id)
        if labeled_only:
            where.append("i.status IN (?,?,?)")
            params.extend([IMG_AUTO, IMG_REVIEW, IMG_APPROVED])
        elif status:
            if status == "labeled":
                where.append("i.status IN (?,?,?)")
                params.extend([IMG_AUTO, IMG_REVIEW, IMG_APPROVED])
            else:
                where.append("i.status=?")
                params.append(status)
        if duplicates_only:
            where.append("i.is_duplicate=1")
        elif not include_duplicates:
            where.append("i.is_duplicate=0")
        if blurry_only:
            from app.config import cfg

            thr = float(cfg.get("extract.blur_threshold", 60.0))
            where.append("i.blur_score > 0 AND i.blur_score < ?")
            params.append(thr)
        if search:
            where.append("i.filename LIKE ?")
            params.append(f"%{search}%")
        if where:
            sql += " WHERE " + " AND ".join(where)
        if class_id is not None:
            sql += " GROUP BY i.id"
        sql += f" ORDER BY i.{order}"
        if limit:
            sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
        return [ImageRecord.from_row(r) for r in self.db.query(sql, params)]

    def image_ids(self, **kwargs) -> list[int]:
        return [im.id for im in self.images(**kwargs)]

    def count_images(self, status: str | None = None, include_duplicates: bool = True) -> int:
        sql = "SELECT COUNT(*) FROM image"
        where, params = [], []
        if status == "labeled":
            where.append("status IN (?,?,?)")
            params.extend([IMG_AUTO, IMG_REVIEW, IMG_APPROVED])
        elif status:
            where.append("status=?")
            params.append(status)
        if not include_duplicates:
            where.append("is_duplicate=0")
        if where:
            sql += " WHERE " + " AND ".join(where)
        return int(self.db.scalar(sql, params))

    def set_image_status(self, image_id: int, status: str) -> None:
        self.db.execute("UPDATE image SET status=? WHERE id=?", (status, image_id))
        self.db.commit()

    def set_images_status(self, image_ids, status: str) -> None:
        self.db.executemany(
            "UPDATE image SET status=? WHERE id=?", [(status, i) for i in image_ids]
        )
        self.db.commit()

    def mark_duplicate(self, image_id: int, dup_of: int, flag: bool = True) -> None:
        self.db.execute(
            "UPDATE image SET is_duplicate=?, dup_of=? WHERE id=?", (int(flag), dup_of, image_id)
        )
        self.db.commit()

    def set_image_note(self, image_id: int, note: str) -> None:
        self.db.execute("UPDATE image SET note=? WHERE id=?", (note, image_id))
        self.db.commit()

    def delete_images(self, image_ids, remove_files: bool = False) -> int:
        ids = list(image_ids)
        if not ids:
            return 0
        if remove_files:
            for i in ids:
                rec = self.image(i)
                if rec:
                    try:
                        Path(rec.path).unlink(missing_ok=True)
                    except OSError:
                        pass
        self.db.executemany("DELETE FROM annotation WHERE image_id=?", [(i,) for i in ids])
        self.db.executemany("DELETE FROM image WHERE id=?", [(i,) for i in ids])
        self.db.commit()
        self.log_history("delete_images", tr("history.delete_images", "{count} ảnh", count=len(ids)))
        return len(ids)

    def neighbor_image(
        self, image_id: int, direction: int = 1, include_duplicates: bool = True
    ) -> ImageRecord | None:
        op, order = (">", "ASC") if direction > 0 else ("<", "DESC")
        dup = "" if include_duplicates else " AND is_duplicate=0"
        row = self.db.query_one(
            f"SELECT * FROM image WHERE id {op} ?{dup} ORDER BY id {order} LIMIT 1",
            (image_id,),
        )
        return ImageRecord.from_row(row) if row else None

    # ======================================================== ANNOTATION ===
    def annotations(self, image_id: int) -> list[Annotation]:
        rows = self.db.query(
            "SELECT a.*, c.idx AS class_index, c.name AS class_name "
            "FROM annotation a LEFT JOIN class c ON c.id = a.class_id "
            "WHERE a.image_id=? ORDER BY a.id ASC",
            (image_id,),
        )
        return [Annotation.from_row(r) for r in rows]

    def annotation(self, ann_id: int) -> Annotation | None:
        row = self.db.query_one(
            "SELECT a.*, c.idx AS class_index, c.name AS class_name "
            "FROM annotation a LEFT JOIN class c ON c.id = a.class_id WHERE a.id=?",
            (ann_id,),
        )
        return Annotation.from_row(row) if row else None

    def add_annotation(self, ann: Annotation) -> int:
        ts = _now()
        cur = self.db.execute(
            "INSERT INTO annotation(image_id, class_id, shape, bbox, polygon, keypoints, "
            "confidence, status, area, source, track_id, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ann.image_id,
                ann.class_id,
                ann.shape,
                json.dumps(ann.bbox),
                json.dumps(ann.polygon),
                json.dumps(ann.keypoints),
                ann.confidence,
                ann.status,
                ann.area,
                ann.source,
                ann.track_id,
                ts,
                ts,
            ),
        )
        self.db.commit()
        ann.id = cur.lastrowid
        self.recount_image(ann.image_id)
        return ann.id

    def update_annotation(self, ann: Annotation) -> None:
        self.db.execute(
            "UPDATE annotation SET class_id=?, shape=?, bbox=?, polygon=?, keypoints=?, "
            "confidence=?, status=?, area=?, source=?, track_id=?, updated_at=? WHERE id=?",
            (
                ann.class_id,
                ann.shape,
                json.dumps(ann.bbox),
                json.dumps(ann.polygon),
                json.dumps(ann.keypoints),
                ann.confidence,
                ann.status,
                ann.area,
                ann.source,
                ann.track_id,
                _now(),
                ann.id,
            ),
        )
        self.db.commit()

    def delete_annotation(self, ann_id: int) -> None:
        row = self.db.query_one("SELECT image_id FROM annotation WHERE id=?", (ann_id,))
        self.db.execute("DELETE FROM annotation WHERE id=?", (ann_id,))
        self.db.commit()
        if row:
            self.recount_image(row["image_id"])

    def clear_annotations(self, image_id: int) -> None:
        self.db.execute("DELETE FROM annotation WHERE image_id=?", (image_id,))
        self.db.commit()
        self.recount_image(image_id)

    def replace_annotations(self, image_id: int, anns: list[Annotation]) -> None:
        """Ghi de toan bo annotation cua mot anh (dung cho auto label / editor save)."""
        self.db.execute("DELETE FROM annotation WHERE image_id=?", (image_id,))
        ts = _now()
        rows = [
            (
                image_id,
                a.class_id,
                a.shape,
                json.dumps(a.bbox),
                json.dumps(a.polygon),
                json.dumps(a.keypoints),
                a.confidence,
                a.status,
                a.area,
                a.source,
                a.track_id,
                ts,
                ts,
            )
            for a in anns
        ]
        if rows:
            self.db.executemany(
                "INSERT INTO annotation(image_id, class_id, shape, bbox, polygon, keypoints, "
                "confidence, status, area, source, track_id, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        self.db.commit()
        self.recount_image(image_id)

    def set_annotation_status(self, ann_id: int, status: str) -> None:
        self.db.execute(
            "UPDATE annotation SET status=?, updated_at=? WHERE id=?", (status, _now(), ann_id)
        )
        self.db.commit()

    def approve_image(self, image_id: int) -> None:
        self.db.execute("UPDATE annotation SET status=? WHERE image_id=?", (ANN_APPROVED, image_id))
        n = int(self.db.scalar("SELECT COUNT(*) FROM annotation WHERE image_id=?", (image_id,)))
        self.db.execute(
            "UPDATE image SET status=?, n_objects=? WHERE id=?", (IMG_APPROVED, n, image_id)
        )
        self.db.commit()

    def recount_image(self, image_id: int) -> int:
        n = int(self.db.scalar("SELECT COUNT(*) FROM annotation WHERE image_id=?", (image_id,)))
        row = self.db.query_one("SELECT status FROM image WHERE id=?", (image_id,))
        status = row["status"] if row else IMG_UNLABELED
        if n == 0 and status in (IMG_AUTO, IMG_REVIEW):
            status = IMG_UNLABELED
        elif n > 0 and status == IMG_UNLABELED:
            status = IMG_AUTO
        self.db.execute("UPDATE image SET n_objects=?, status=? WHERE id=?", (n, status, image_id))
        self.db.commit()
        return n

    def recount_all_images(self) -> None:
        self.db.execute(
            "UPDATE image SET n_objects = "
            "(SELECT COUNT(*) FROM annotation a WHERE a.image_id = image.id)"
        )
        self.db.execute(
            f"UPDATE image SET status='{IMG_UNLABELED}' "
            f"WHERE n_objects = 0 AND status IN ('{IMG_AUTO}', '{IMG_REVIEW}')"
        )
        self.db.commit()

    # ============================================================ THONG KE ==
    def refresh_stats(self) -> ProjectInfo:
        i = self.info
        i.n_images = self.count_images()
        i.n_labeled = self.count_images(status="labeled")
        i.n_objects = int(self.db.scalar("SELECT COUNT(*) FROM annotation"))
        i.n_classes = int(self.db.scalar("SELECT COUNT(*) FROM class"))
        return i

    def status_counts(self) -> dict[str, int]:
        rows = self.db.query("SELECT status, COUNT(*) AS n FROM image GROUP BY status")
        out = {k: 0 for k in (IMG_UNLABELED, IMG_AUTO, IMG_REVIEW, IMG_APPROVED)}
        for r in rows:
            out[r["status"]] = r["n"]
        return out

    def annotation_status_counts(self) -> dict[str, int]:
        rows = self.db.query("SELECT status, COUNT(*) AS n FROM annotation GROUP BY status")
        out = {ANN_AUTO: 0, ANN_REVIEW: 0, ANN_APPROVED: 0, "manual": 0}
        for r in rows:
            out[r["status"]] = r["n"]
        return out

    def class_stats(self) -> list[dict]:
        rows = self.db.query(
            "SELECT c.id, c.idx, c.name, c.color, "
            "  COUNT(a.id) AS n_obj, "
            "  COUNT(DISTINCT a.image_id) AS n_img, "
            "  COALESCE(AVG(a.area), 0) AS avg_area, "
            "  COALESCE(AVG(a.confidence), 0) AS avg_conf, "
            "  SUM(CASE WHEN a.shape='polygon' THEN 1 ELSE 0 END) AS n_mask "
            "FROM class c LEFT JOIN annotation a ON a.class_id = c.id "
            "GROUP BY c.id ORDER BY c.idx"
        )
        total_img = max(1, self.count_images())
        return [
            {
                "id": r["id"],
                "index": r["idx"],
                "name": r["name"],
                "color": r["color"],
                "objects": r["n_obj"],
                "images": r["n_img"],
                "masks": r["n_mask"] or 0,
                "avg_area": r["avg_area"],
                "avg_conf": r["avg_conf"],
                "coverage": 100.0 * r["n_img"] / total_img,
            }
            for r in rows
        ]

    def area_histogram(self, bins: int = 30) -> tuple[list[float], list[int]]:
        rows = self.db.query("SELECT area FROM annotation WHERE area > 0")
        areas = [r["area"] for r in rows]
        if not areas:
            return [], []
        lo, hi = min(areas), max(areas)
        if hi <= lo:
            return [lo], [len(areas)]
        step = (hi - lo) / bins
        counts = [0] * bins
        for a in areas:
            k = min(bins - 1, int((a - lo) / step))
            counts[k] += 1
        edges = [lo + step * i for i in range(bins)]
        return edges, counts

    def object_heatmap(self, grid: int = 24) -> list[list[float]]:
        """Ma tran mat do tam doi tuong theo toa do chuan hoa."""
        rows = self.db.query(
            "SELECT a.bbox, i.width, i.height FROM annotation a "
            "JOIN image i ON i.id = a.image_id WHERE i.width > 0 AND i.height > 0"
        )
        hm = [[0.0] * grid for _ in range(grid)]
        for r in rows:
            try:
                x1, y1, x2, y2 = json.loads(r["bbox"])
            except Exception:
                continue
            cx = (x1 + x2) / 2.0 / r["width"]
            cy = (y1 + y2) / 2.0 / r["height"]
            gx = min(grid - 1, max(0, int(cx * grid)))
            gy = min(grid - 1, max(0, int(cy * grid)))
            hm[gy][gx] += 1.0
        return hm

    def objects_per_image(self) -> list[int]:
        rows = self.db.query("SELECT n_objects FROM image")
        return [r["n_objects"] for r in rows]

    def confidence_histogram(self, bins: int = 20) -> list[int]:
        counts = [0] * bins
        for r in self.db.query("SELECT confidence FROM annotation"):
            c = max(0.0, min(0.999999, float(r["confidence"] or 0)))
            counts[int(c * bins)] += 1
        return counts

    def duplicate_count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM image WHERE is_duplicate=1"))

    def quality_counts(self, blur_threshold: float, dark_threshold: float) -> dict[str, int]:
        return {
            "blurry": int(
                self.db.scalar(
                    "SELECT COUNT(*) FROM image WHERE blur_score > 0 AND blur_score < ?",
                    (blur_threshold,),
                )
            ),
            "dark": int(
                self.db.scalar(
                    "SELECT COUNT(*) FROM image WHERE brightness > 0 AND brightness < ?",
                    (dark_threshold,),
                )
            ),
            "duplicate": self.duplicate_count(),
        }

    def total_mask_area(self) -> float:
        return float(self.db.scalar("SELECT COALESCE(SUM(area),0) FROM annotation"))

    def update_track_class(self, track_id: int, new_class_id: int) -> int:
        """Doi class cua tat ca annotation co cung track_id."""
        cur = self.db.execute(
            "UPDATE annotation SET class_id=?, updated_at=? WHERE track_id=?",
            (new_class_id, _now(), track_id),
        )
        self.db.commit()
        return cur.rowcount if cur else 0

    def track_stats(self) -> dict:
        """Thong ke so track va do dai track trung binh."""
        n_tracks = int(
            self.db.scalar(
                "SELECT COUNT(DISTINCT track_id) FROM annotation WHERE track_id IS NOT NULL AND track_id > 0"
            )
        )
        avg_len = float(
            self.db.scalar(
                "SELECT COALESCE(AVG(cnt), 0) FROM (SELECT COUNT(*) AS cnt FROM annotation "
                "WHERE track_id IS NOT NULL AND track_id > 0 GROUP BY track_id)"
            )
        )
        return {"n_tracks": n_tracks, "avg_track_len": round(avg_len, 1)}

    # ============================================================= LICH SU ==
    def log_history(self, action: str, detail: str = "") -> None:
        self.db.execute(
            "INSERT INTO history(ts, action, detail) VALUES(?,?,?)", (_now(), action, detail)
        )
        self.db.commit()

    def history(self, limit: int = 200) -> list[dict]:
        rows = self.db.query("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
        return [{"ts": r["ts"], "action": r["action"], "detail": r["detail"]} for r in rows]

    # =========================================================== TRAIN RUN ==
    def start_train_run(self, model: str, epochs: int, params: dict, out_dir: str) -> int:
        cur = self.db.execute(
            "INSERT INTO train_run(started, model, epochs, params, out_dir, status) "
            "VALUES(?,?,?,?,?,'running')",
            (_now(), model, epochs, json.dumps(params, ensure_ascii=False), out_dir),
        )
        self.db.commit()
        return cur.lastrowid

    def finish_train_run(self, run_id: int, best_map: float, status: str = "done") -> None:
        self.db.execute(
            "UPDATE train_run SET finished=?, best_map=?, status=? WHERE id=?",
            (_now(), best_map, status, run_id),
        )
        self.db.commit()

    def train_runs(self, limit: int = 20) -> list[dict]:
        rows = self.db.query("SELECT * FROM train_run ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # ================================================================ MISC ==
    def missing_files(self) -> list[ImageRecord]:
        return [im for im in self.images() if not Path(im.path).exists()]

    def purge_missing(self) -> int:
        missing = self.missing_files()
        return self.delete_images([m.id for m in missing])

    def copy_into_project(self, src: str | Path, subdir: str = "images") -> Path:
        src = Path(src)
        dest = self.sub(subdir) / src.name
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            i = 1
            while dest.exists():
                dest = self.sub(subdir) / f"{stem}_{i}{suffix}"
                i += 1
        shutil.copy2(src, dest)
        return dest
