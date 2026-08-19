"""Kiem thu DatasetExporter, DatasetImporter va round-trip 7 dinh dang."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exporters import DatasetExporter, ExportConfig
from app.core.importers import DatasetImporter, ImportConfig
from app.models.entities import Annotation
from app.models.repository import ProjectRepository


@pytest.mark.parametrize("fmt", ["yolo_seg", "yolo_det", "coco", "voc", "mask"])
def test_export_formats(repo: ProjectRepository, tmp_dir: Path, fmt: str):
    c = ExportConfig(
        fmt=fmt,
        output_dir=str(tmp_dir / f"exports_{fmt}"),
        dataset_name=fmt,
        val_split=0.25,
    )
    r = DatasetExporter(repo, c).run()
    assert r.n_images > 0 and r.n_objects > 0
    out = Path(r.output_dir)

    if fmt.startswith("yolo"):
        assert Path(r.yaml_path).exists()
        labels = list((out / "labels").rglob("*.txt"))
        assert labels and labels[0].read_text(encoding="utf-8").strip()
    elif fmt == "coco":
        j = json.loads((out / "annotations" / "instances_train.json").read_text(encoding="utf-8"))
        assert j["annotations"] and j["categories"]
    elif fmt == "voc":
        assert list((out / "Annotations").glob("*.xml"))
    elif fmt == "mask":
        assert list((out / "masks").rglob("*.png"))


def test_export_obb_pose(repo: ProjectRepository, tmp_dir: Path):
    img = repo.images()[0]
    cd = repo.classes()[0]
    a = Annotation(
        image_id=img.id,
        class_id=cd.id,
        class_name=cd.name,
        confidence=0.9,
        status="approved",
        source="manual",
    )
    a.set_points([(10, 20), (70, 10), (80, 60), (20, 70)])
    a.keypoints = [15.0, 25.0, 2.0, 60.0, 20.0, 2.0, 40.0, 60.0, 1.0]
    repo.replace_annotations(img.id, [a])

    for fmt, checker in (("yolo_obb", "obb"), ("yolo_pose", "pose")):
        c = ExportConfig(
            fmt=fmt,
            output_dir=str(tmp_dir / f"exports_{fmt}"),
            dataset_name=fmt,
            val_split=0.0,
            flat_layout=True,
        )
        r = DatasetExporter(repo, c).run()
        out = Path(r.output_dir)
        txt = out / "labels" / "all" / f"{Path(img.path).stem}.txt"
        assert txt.exists()
        parts = txt.read_text(encoding="utf-8").strip().split()
        vals = [float(v) for v in parts[1:]]
        assert all(0.0 <= v <= 1.0 for v in vals[:4])

        if checker == "obb":
            assert len(parts) == 9
        else:
            assert len(parts) == 1 + 4 + 9
            yaml_text = Path(r.yaml_path).read_text(encoding="utf-8")
            assert "kpt_shape: [3, 3]" in yaml_text

    # COCO Keypoints
    c = ExportConfig(
        fmt="coco",
        output_dir=str(tmp_dir / "exports_coco_kp"),
        dataset_name="coco_kp",
        val_split=0.0,
        flat_layout=True,
    )
    r = DatasetExporter(repo, c).run()
    j = json.loads(
        (Path(r.output_dir) / "annotations" / "instances_all.json").read_text(encoding="utf-8")
    )
    kp_anns = [x for x in j["annotations"] if x.get("keypoints")]
    assert kp_anns
    assert len(kp_anns[0]["keypoints"]) == 9
    assert kp_anns[0]["num_keypoints"] == 3
    assert j["categories"][0].get("keypoints")


@pytest.mark.parametrize("fmt", ["yolo_seg", "yolo_det", "coco"])
def test_import_roundtrip(repo: ProjectRepository, tmp_dir: Path, fmt: str):
    ecfg = ExportConfig(
        fmt=fmt,
        output_dir=str(tmp_dir / f"rt_exports_{fmt}"),
        dataset_name=f"rt_{fmt}",
        val_split=0.0,
        flat_layout=True,
        copy_images=True,
    )
    eres = DatasetExporter(repo, ecfg).run()
    assert eres.n_images > 0 and eres.n_objects > 0

    repo2 = ProjectRepository.create(tmp_dir / f"rt_proj_{fmt}", f"RT_{fmt}", task="segment")
    icfg = ImportConfig(fmt=fmt, dataset_dir=eres.output_dir, copy_images=False)
    imp = DatasetImporter(repo2, icfg)
    ires = imp.run()

    assert ires.n_images == eres.n_images
    assert ires.n_annotations == eres.n_objects
    assert ires.n_classes_added > 0

    imgs2 = repo2.images()
    assert imgs2
    anns2 = repo2.annotations(imgs2[0].id)
    assert anns2
    a2 = anns2[0]
    assert a2.bbox[2] > a2.bbox[0]
    repo2.close()
