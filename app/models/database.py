"""Lop truy cap SQLite: tao schema, migrate, connection an toan da luong."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.utils.logger import get_logger

log = get_logger(__name__)

SCHEMA_VERSION = 1

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS project (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    root_dir    TEXT DEFAULT '',
    task        TEXT DEFAULT 'segment',
    created_at  TEXT,
    updated_at  TEXT,
    meta        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS class (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    idx     INTEGER NOT NULL,
    name    TEXT NOT NULL UNIQUE,
    color   TEXT NOT NULL,
    visible INTEGER DEFAULT 1,
    locked  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS image (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path         TEXT NOT NULL UNIQUE,
    filename     TEXT NOT NULL,
    width        INTEGER DEFAULT 0,
    height       INTEGER DEFAULT 0,
    source       TEXT DEFAULT '',
    frame_index  INTEGER DEFAULT -1,
    timestamp    REAL DEFAULT 0,
    phash        TEXT DEFAULT '',
    blur_score   REAL DEFAULT 0,
    brightness   REAL DEFAULT 0,
    status       TEXT DEFAULT 'unlabeled',
    is_duplicate INTEGER DEFAULT 0,
    dup_of       INTEGER DEFAULT 0,
    n_objects    INTEGER DEFAULT 0,
    note         TEXT DEFAULT '',
    created_at   TEXT
);

CREATE TABLE IF NOT EXISTS annotation (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id    INTEGER NOT NULL REFERENCES image(id) ON DELETE CASCADE,
    class_id    INTEGER REFERENCES class(id) ON DELETE SET NULL,
    shape       TEXT DEFAULT 'polygon',
    bbox        TEXT DEFAULT '[]',
    polygon     TEXT DEFAULT '[]',
    keypoints   TEXT DEFAULT '[]',
    confidence  REAL DEFAULT 1.0,
    status      TEXT DEFAULT 'auto',
    area        REAL DEFAULT 0,
    source      TEXT DEFAULT 'manual',
    track_id    INTEGER DEFAULT NULL,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS history (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT,
    action   TEXT,
    detail   TEXT
);

CREATE TABLE IF NOT EXISTS train_run (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started   TEXT,
    finished  TEXT,
    model     TEXT,
    epochs    INTEGER,
    params    TEXT,
    best_map  REAL DEFAULT 0,
    out_dir   TEXT,
    status    TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS ix_ann_image ON annotation(image_id);
CREATE INDEX IF NOT EXISTS ix_ann_class ON annotation(class_id);
CREATE INDEX IF NOT EXISTS ix_img_status ON image(status);
CREATE INDEX IF NOT EXISTS ix_img_dup ON image(is_duplicate);
"""


class Database:
    """Bao boc sqlite3 voi khoa RLock de dung duoc tu nhieu QThread."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    # --------------------------------------------------------------- schema --
    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            # Migration check: Dam bao column track_id co trong table annotation
            try:
                cols = [
                    r[1] for r in self._conn.execute("PRAGMA table_info(annotation)").fetchall()
                ]
                if "track_id" not in cols:
                    self._conn.execute(
                        "ALTER TABLE annotation ADD COLUMN track_id INTEGER DEFAULT NULL"
                    )
                self._conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_ann_track ON annotation(track_id)"
                )
            except Exception as exc:
                log.warning("Loi migration DB (track_id): %s", exc)

            cur = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'")
            row = cur.fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            self._conn.commit()

    # ------------------------------------------------------------ thao tac --
    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur

    def executemany(self, sql: str, seq) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, seq)

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params=(), default=0):
        row = self.query_one(sql, params)
        if row is None or row[0] is None:
            return default
        return row[0]

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.commit()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass

    def vacuum(self) -> None:
        with self._lock:
            self._conn.execute("VACUUM")

    def backup_to(self, dest: str | Path) -> None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(str(dest))
            try:
                self._conn.backup(target)
            finally:
                target.close()

    # -------------------------------------------------------- context mgr --
    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
