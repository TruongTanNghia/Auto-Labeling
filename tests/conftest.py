"""Cau hinh pytest: cach ly moi truong va dinh nghia cac fixture dung chung."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# QUAN TRONG: cach ly hoan toan khoi cau hinh cua nguoi dung.
# Phai thuc hien NGAY khi conftest.py duoc load, TRUOC KHI import app.*
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

_SANDBOX = Path(tempfile.mkdtemp(prefix="als_selftest_"))
if os.name == "nt":
    os.environ["LOCALAPPDATA"] = str(_SANDBOX / "AppData")
else:
    os.environ["XDG_DATA_HOME"] = str(_SANDBOX / "share")
(_SANDBOX / "AppData").mkdir(parents=True, exist_ok=True)

# Them thu muc goc cua du an vao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session", autouse=True)
def cleanup_sandbox():
    """Don dẹp thu muc sandbox sau khi chay xong tat ca cac test."""
    yield
    shutil.rmtree(_SANDBOX, ignore_errors=True)


@pytest.fixture(scope="session")
def qapp():
    """Fixture cung cap QApplication offscreen cho toàn bo pytest session."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def tmp_dir():
    """Fixture tao mot thu muc tam thoi sach se cho moi test."""
    tmp = Path(tempfile.mkdtemp(prefix="als_pytest_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_data(tmp_dir: Path):
    """Fixture sinh 8 anh va 1 video mau phuc vu kiem thu."""
    import cv2
    import numpy as np

    img_dir = tmp_dir / "imgs"
    img_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    for i in range(8):
        img = (rng.random((240, 320, 3)) * 255).astype(np.uint8)
        cv2.rectangle(img, (40 + i * 5, 50), (160 + i * 5, 170), (30, 200, 90), -1)
        cv2.imwrite(str(img_dir / f"img_{i:03d}.jpg"), img)

    video = tmp_dir / "clip.mp4"
    vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 15, (320, 240))
    for i in range(45):
        frame = (rng.random((240, 320, 3)) * 120).astype(np.uint8)
        cv2.circle(frame, (60 + i * 4, 120), 25, (200, 60, 200), -1)
        vw.write(frame)
    vw.release()

    return img_dir, video


@pytest.fixture
def repo(tmp_dir: Path, sample_data):
    """Fixture khoi tao ProjectRepository da co san 8 anh va 2 class."""
    from app.core.frame_extractor import ExtractConfig, scan_folder_records
    from app.models.entities import Annotation
    from app.models.repository import ProjectRepository

    img_dir, _ = sample_data
    r = ProjectRepository.create(tmp_dir / "proj", "Test", "mo ta", "segment")

    res = scan_folder_records([str(p) for p in sorted(img_dir.glob("*.jpg"))], ExtractConfig())
    r.add_images_bulk(res.saved)

    c1, c2 = r.add_class("crack"), r.add_class("rust")
    for _k, im in enumerate(r.images()[:6]):
        anns = []
        for j, cd in enumerate((c1, c2)):
            a = Annotation(
                image_id=im.id,
                class_id=cd.id,
                class_name=cd.name,
                confidence=0.4 + 0.1 * j,
                status="auto",
                source="yolo",
            )
            a.set_points(
                [(20 + j * 40, 20), (100 + j * 40, 30), (110 + j * 40, 90), (25 + j * 40, 80)]
            )
            anns.append(a)
        r.replace_annotations(im.id, anns)
    r.refresh_stats()
    return r
