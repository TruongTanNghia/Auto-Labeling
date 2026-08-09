"""Kiem thu ProjectRepository va thong ke co so du lieu."""
from __future__ import annotations

from pathlib import Path
from app.models.repository import ProjectRepository


def test_create_project(tmp_dir: Path):
    proj_dir = tmp_dir / "new_proj"
    repo = ProjectRepository.create(proj_dir, "Test Project", "Mo ta", "segment")
    assert repo.info.name == "Test Project"
    assert repo.info.task == "segment"
    repo.close()


def test_add_images_and_annotations(repo: ProjectRepository):
    assert repo.count_images() == 8
    assert repo.info.n_objects == 12
    assert len(repo.class_stats()) == 2
    assert repo.object_heatmap(12) is not None
    assert sum(repo.confidence_histogram()) == 12


def test_legacy_database_migration(tmp_dir: Path):
    import sqlite3
    from app.models.database import Database

    db_file = tmp_dir / "legacy.alsdb"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('schema_version', '1')")
    conn.execute("""
        CREATE TABLE annotation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER,
            class_id INTEGER,
            class_name TEXT,
            confidence REAL,
            status TEXT,
            area REAL,
            source TEXT
        )
    """)
    conn.commit()
    conn.close()

    db = Database(db_file)
    cols = [r[1] for r in db._conn.execute("PRAGMA table_info(annotation)").fetchall()]
    assert "track_id" in cols

