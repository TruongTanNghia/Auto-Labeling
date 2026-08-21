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


def test_autolabel_plugin_controls(qapp, sample_data):
    """TC-UI-05 (BUG-05/06): combo SAM phai luu cfg khi doi; o prompt phai HIEN
    voi plugin nhan prompt van ban va an lai khi bo chon plugin."""
    from app.config import cfg
    from app.plugins.base import registry

    ctrl = AppController()
    win = MainWindow(ctrl)
    win.show()
    qapp.processEvents()

    try:
        win.go_to_page("autolabel")
        qapp.processEvents()
        page = win.pages["autolabel"]

        # BUG-05: doi trong so SAM tren trang Auto Label phai duoc luu vao cfg
        page.plugin_sam_combo.setCurrentIndex(1)  # sam2_b.pt
        qapp.processEvents()
        assert cfg.get("sam.weights") == page.plugin_sam_combo.currentData()

        # BUG-06: chon plugin nhan prompt -> o prompt phai hien va go duoc
        prompt_keys = [i.key for i in registry.infos() if i.accepts_prompt]
        assert prompt_keys, "khong co plugin nhan prompt de kiem thu"
        idx = page.plugin_combo.findData(prompt_keys[0])
        assert idx >= 0
        page.plugin_combo.setCurrentIndex(idx)
        qapp.processEvents()
        assert not page.plugin_prompt.isHidden()  # da duoc setVisible(True)
        assert page.plugin_prompt.isEnabled()

        # Bo chon plugin -> o prompt an di
        page.plugin_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert page.plugin_prompt.isHidden()
    finally:
        ctrl.shutdown()
        win.deleteLater()
        qapp.processEvents()
