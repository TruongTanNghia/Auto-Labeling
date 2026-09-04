"""Kiem thu giao dien lazy, chuyen trang, luong cat frame -> autolabel va i18n."""

from __future__ import annotations

from pathlib import Path

from app.constants import NAV_ITEMS
from app.controllers.app_controller import AppController
from app.core.frame_extractor import ExtractConfig, FrameExtractor, scan_folder_records
from app.i18n import get_language, set_language, tr
from app.models.repository import ProjectRepository
from app.views.main_window import MainWindow


def test_lazy_pages(qapp, sample_data):
    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        # Nhan video khi trang Frame Extractor chua tung mo
        win.pages["extract"].set_videos([str(video)])
        qapp.processEvents()
        assert len(win.pages["extract"].videos) == 1

        # Nhan file tha vao khi trang Import chua tung mo
        win.pages["import"].accept_paths([str(p) for p in sorted(img_dir.glob("*.jpg"))])
        qapp.processEvents()
        assert win.pages["import"].image_files

        # Phat tin hieu khi cac trang khac chua dung
        ctrl.notify_images_changed()
        ctrl.notify_classes_changed()
        ctrl.modelChanged.emit()
        qapp.processEvents()

        # Mo lan luot tat ca cac trang
        for key, _t, _i in NAV_ITEMS:
            win.go_to_page(key)
            qapp.processEvents()
        assert len(win.pages["extract"].videos) == 1
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_extract_to_autolabel(qapp, sample_data, tmp_dir: Path):
    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        proj = tmp_dir / "flow"
        r2 = ProjectRepository.create(proj, "Flow")
        r2.close()
        ctrl.open_project(proj / "project.alsdb")
        qapp.processEvents()

        old = scan_folder_records(
            [str(p) for p in sorted(img_dir.glob("*.jpg"))][:3],
            ExtractConfig(remove_similar=False),
        )
        ctrl.repo.add_images_bulk(old.saved)
        old_ids = {im.id for im in ctrl.repo.images()}
        assert len(old_ids) == 3

        cfg_ex = ExtractConfig(every_n_frames=6, remove_similar=False, blur_detection=False)
        res = FrameExtractor(cfg_ex).extract(video, tmp_dir / "flow_frames")
        ctrl.repo.add_images_bulk(res.saved)
        assert res.n_saved > 0

        ex = win.pages["extract"]
        ex.ensure_built()
        batch = ex._image_ids_of(res)
        assert len(batch) == res.n_saved
        assert not (set(batch) & old_ids)

        win.go_to_page("autolabel")
        qapp.processEvents()
        win.pages["autolabel"].set_batch(batch)
        qapp.processEvents()

        sel = set(win.pages["autolabel"].image_list.selected_ids())
        assert sel == set(batch)
        assert not (sel & old_ids)
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_i18n():
    set_language("vi")
    assert get_language() == "vi"
    assert tr("nav.dashboard") == "Dashboard"
    assert tr("settings.title") == "Settings"

    set_language("en")
    assert get_language() == "en"
    assert tr("settings.general.language") == "Language"
    assert tr("common.save") == "Save"

    set_language("vi")
    assert get_language() == "vi"


def test_editor_page_initialization_on_show(qapp, tmp_dir: Path):
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()
    try:
        proj = tmp_dir / "editor_proj"
        r = ProjectRepository.create(proj, "EditorProj")
        r.close()
        ctrl.open_project(proj / "project.alsdb")
        qapp.processEvents()

        win.go_to_page("editor")
        qapp.processEvents()
        assert win.pages["editor"]._image_id == 0
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_extract_preview_reset_on_video_change(qapp, sample_data, tmp_dir: Path):
    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()
    try:
        ex = win.pages["extract"]
        ex.ensure_built()
        ex.set_videos([str(video)])
        qapp.processEvents()

        sample_img = next(img_dir.glob("*.jpg"))
        ex._on_preview(str(sample_img))
        qapp.processEvents()
        assert not ex.preview_label.pixmap().isNull()

        # Khi doi video khac trong cung phien lam viec
        other_video = tmp_dir / "other.mp4"
        ex.set_videos([str(other_video)])
        qapp.processEvents()

        # Khung xem truoc phai duoc reset ve trang thai ban dau
        assert ex.preview_label.pixmap().isNull()
        assert tr("extract.no_frame_yet", "Chưa có frame nào") in ex.preview_label.text()
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_extract_flow_to_autolabel_auto_start(qapp, sample_data, tmp_dir: Path):
    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        proj = tmp_dir / "flow_auto"
        r = ProjectRepository.create(proj, "FlowAuto")
        r.close()
        ctrl.open_project(proj / "project.alsdb")
        qapp.processEvents()

        cfg_ex = ExtractConfig(every_n_frames=6, remove_similar=False, blur_detection=False)
        res = FrameExtractor(cfg_ex).extract(video, tmp_dir / "flow_auto_frames")
        ctrl.repo.add_images_bulk(res.saved)

        ex = win.pages["extract"]
        ex.ensure_built()
        ex._on_done(res)
        qapp.processEvents()

        assert len(ex._last_batch) == res.n_saved

        # Mock engine de khong phai tai model nang trong unit test
        ctrl.engine._loaded = True
        ctrl.engine.model = object()
        ctrl.engine.names = {0: "object"}
        ctrl.engine.predict = lambda path, cfg: []

        # Click nut "Gán nhãn tự động cho ảnh vừa cắt"
        ex.to_autolabel_btn.click()
        assert ctrl.is_running("autolabel")
        qapp.processEvents()

        al = win.pages["autolabel"]
        assert win._current == "autolabel"
        assert al.filter_combo.currentData() == "all"
        assert len(al.image_list.selected_ids()) == res.n_saved
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_import_page_reset_on_project_changed(qapp, sample_data, tmp_dir: Path):
    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        p1 = tmp_dir / "proj1"
        p2 = tmp_dir / "proj2"
        r1 = ProjectRepository.create(p1, "Project 1")
        r1.close()
        r2 = ProjectRepository.create(p2, "Project 2")
        r2.close()

        ctrl.open_project(str(p1 / "project.alsdb"))
        qapp.processEvents()

        imp_page = win.pages["import"]
        imp_page.ensure_built()
        imp_page.accept_paths([str(video), str(img_dir)])
        qapp.processEvents()

        assert len(imp_page.videos) > 0
        assert len(imp_page.image_files) > 0
        assert imp_page.source_list.count() > 0

        # Chuyen sang du an khac
        ctrl.open_project(str(p2 / "project.alsdb"))
        qapp.processEvents()

        # Toan bo danh sach va trang thai import phai duoc reset
        assert len(imp_page.videos) == 0
        assert len(imp_page.image_files) == 0
        assert imp_page.source_list.count() == 0
        assert imp_page.preview_label.pixmap().isNull()
        assert not imp_page.gallery_card.isVisible()
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_autolabel_cancel_and_project_change(qapp, sample_data, tmp_dir: Path):
    import time

    img_dir, video = sample_data
    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        p1 = tmp_dir / "al_cancel_1"
        p2 = tmp_dir / "al_cancel_2"
        r1 = ProjectRepository.create(p1, "AL Cancel 1")
        r1.close()
        r2 = ProjectRepository.create(p2, "AL Cancel 2")
        r2.close()

        ctrl.open_project(str(p1 / "project.alsdb"))
        qapp.processEvents()

        imgs = sorted(img_dir.glob("*.jpg"))
        for p in imgs[:5]:
            ctrl.repo.add_image(str(p))
        qapp.processEvents()

        # Mock engine de chay inference cham de test cancel
        ctrl.engine._loaded = True
        ctrl.engine.model = object()
        ctrl.engine.names = {0: "object"}

        def mock_predict(path, cfg):
            time.sleep(0.05)
            return []

        ctrl.engine.predict = mock_predict

        win.go_to_page("autolabel")
        al = win.pages["autolabel"]
        al.refresh()
        qapp.processEvents()

        # Bat dau gan nhan
        al.start()
        qapp.processEvents()
        assert ctrl.is_running("autolabel")
        assert not al.start_btn.isEnabled()
        assert al.progress.isVisible()

        # Bam nut "Huy" tren thanh tien trinh
        al.progress.cancel_btn.click()
        qapp.processEvents()

        # Doi worker dung an toan
        worker = ctrl.worker("autolabel")
        if worker:
            worker.wait(3000)
        qapp.processEvents()

        # Sau khi dung: khong con chay, nut bat dau duoc enable lai, khong bao loi
        assert not ctrl.is_running("autolabel")
        assert al.start_btn.isEnabled()

        # Test tiep: khi doi project, nut bat dau van phai duoc enable va thanh tien trinh reset
        ctrl.open_project(str(p2 / "project.alsdb"))
        qapp.processEvents()
        assert al.start_btn.isEnabled()
        assert not al.progress.isVisible()
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_editor_mark_status(qapp, tmp_path):
    p = tmp_path / "proj_ed"
    repo = ProjectRepository.create(p, "ProjED", "", "detect")
    repo.add_class("car", "#ff0000")
    f1 = p / "f1.jpg"
    f2 = p / "f2.jpg"
    f1.write_bytes(b"fake1")
    f2.write_bytes(b"fake2")
    i1 = repo.add_image("f1.jpg", str(f1), 100, 100)
    i2 = repo.add_image("f2.jpg", str(f2), 100, 100)
    repo.set_image_status(i1, "review")
    repo.set_image_status(i2, "review")
    repo.close()

    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        ctrl.open_project(str(p / "project.alsdb"))
        win.go_to_page("editor")
        qapp.processEvents()
        ed = win.pages["editor"]

        # Chon anh va bam Duyet
        ed.load_image(i1)
        qapp.processEvents()
        ed.mark_ok_btn.click()
        qapp.processEvents()

        assert ctrl.repo.image(i1).status == "approved"

        # Bam Can xem lai
        ed.mark_review_btn.click()
        qapp.processEvents()
        assert ctrl.repo.image(i1).status == "review"
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()


def test_train_autolabel_conflict(qapp, tmp_path):
    p = tmp_path / "proj_train"
    repo = ProjectRepository.create(p, "ProjTrain", "", "detect")
    repo.close()

    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        ctrl.open_project(str(p / "project.alsdb"))
        tp = win.pages["train"]
        al = win.pages["autolabel"]

        # Fake mot worker autolabel dang chay trong ctrl
        from app.workers.base import BaseWorker

        class DummyWorker(BaseWorker):
            def execute(self):
                return None

        ctrl._workers["autolabel"] = DummyWorker()

        # Train page phai chan khong cho chay
        tp.start()
        qapp.processEvents()
        assert not ctrl.is_running("train")

        # Fake worker train dang chay
        ctrl._workers.pop("autolabel", None)
        ctrl._workers["train"] = DummyWorker()

        # Autolabel page phai chan khong cho chay
        al.start()
        qapp.processEvents()
        assert not ctrl.is_running("autolabel")
    finally:
        ctrl._workers.clear()
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()
