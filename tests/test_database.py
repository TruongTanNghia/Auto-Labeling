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
