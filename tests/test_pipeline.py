"""Kiem thu tu dong khong can man hinh (offscreen).

Chay:  python tests/test_pipeline.py
Kiem tra: DB, cat frame (5 che do), do chat luong anh, khu trung lap, canvas
(polygon/brush/eraser/split/merge/undo), xuat 5 dinh dang, plugin registry.
Khong can GPU va khong tai model.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

# QUAN TRONG: cach ly hoan toan khoi cau hinh that cua nguoi dung.
# Phai dat TRUOC khi import app.* vi duong dan duoc tinh luc import.
_SANDBOX = Path(tempfile.mkdtemp(prefix="als_selftest_"))
if os.name == "nt":
    os.environ["LOCALAPPDATA"] = str(_SANDBOX / "AppData")
else:
    os.environ["XDG_DATA_HOME"] = str(_SANDBOX / "share")
(_SANDBOX / "AppData").mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

FAILS: list[tuple[str, str]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  [OK]   {name}")
    except Exception as exc:
        FAILS.append((name, traceback.format_exc()))
        print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")


def make_data(tmp: Path) -> tuple[Path, Path]:
    img_dir = tmp / "imgs"
    img_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    for i in range(8):
        img = (rng.random((240, 320, 3)) * 255).astype(np.uint8)
        cv2.rectangle(img, (40 + i * 5, 50), (160 + i * 5, 170), (30, 200, 90), -1)
        cv2.imwrite(str(img_dir / f"img_{i:03d}.jpg"), img)

    video = tmp / "clip.mp4"
    vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 15, (320, 240))
    for i in range(45):
        frame = (rng.random((240, 320, 3)) * 120).astype(np.uint8)
        cv2.circle(frame, (60 + i * 4, 120), 25, (200, 60, 200), -1)
        vw.write(frame)
    vw.release()
    return img_dir, video


def main() -> int:
    app = QApplication.instance() or QApplication([])
    tmp = Path(tempfile.mkdtemp(prefix="als_test_"))
    img_dir, video = make_data(tmp)

    from app.core.frame_extractor import (
        ExtractConfig,
        FrameExtractor,
        estimate_output,
        probe_video,
        scan_folder_records,
    )
    from app.core import image_quality as iq
    from app.constants import (
        MODE_ADAPTIVE_MOTION,
        MODE_EVERY_FRAME,
        MODE_EVERY_N_FRAMES,
        MODE_EVERY_N_SECONDS,
        MODE_SCENE_DETECT,
    )
    from app.models.entities import Annotation
    from app.models.repository import ProjectRepository

    print("\n== Project & co so du lieu ==")
    repo = ProjectRepository.create(tmp / "proj", "Test", "mo ta", "segment")
    check("tao project", lambda: repo.info.name == "Test" or _fail("ten sai"))

    res = scan_folder_records([str(p) for p in sorted(img_dir.glob("*.jpg"))],
                              ExtractConfig())
    repo.add_images_bulk(res.saved)
    check("nap 8 anh", lambda: _eq(repo.count_images(), 8))

    print("\n== Chat luong anh ==")

    def quality():
        a = cv2.imread(str(img_dir / "img_000.jpg"))
        _eq(len(iq.phash(a)), 16)
        _true(abs(iq.ssim(a, a) - 1.0) < 0.01, "ssim(a,a) phai bang 1")
        _true(iq.analyze(a).blur_score > 0, "blur_score phai > 0")
        df = iq.DuplicateFilter()
        _true(df.check(a, 0)[0] is False, "anh dau khong duoc coi la trung")
        _true(df.check(a, 1)[0] is True, "anh giong het phai bi coi la trung")
    check("phash / ssim / blur / dedupe", quality)

    print("\n== Cat frame ==")
    info = probe_video(video)
    check("doc thong tin video", lambda: _true(info and info.frame_count > 0, "khong doc duoc"))
    for mode in (MODE_EVERY_FRAME, MODE_EVERY_N_FRAMES, MODE_EVERY_N_SECONDS,
                 MODE_ADAPTIVE_MOTION, MODE_SCENE_DETECT):
        def run(m=mode):
            c = ExtractConfig(mode=m, every_n_frames=5, every_n_seconds=0.5,
                              remove_similar=False, blur_detection=False)
            estimate_output(info, c)
            r = FrameExtractor(c).extract(video, tmp / f"f_{m}")
            _true(r.n_saved > 0, "khong sinh anh nao")
        check(f"che do {mode}", run)

    print("\n== Class & annotation ==")

    def annotate():
        c1, c2 = repo.add_class("crack"), repo.add_class("rust")
        for k, im in enumerate(repo.images()[:6]):
            anns = []
            for j, cd in enumerate((c1, c2)):
                a = Annotation(image_id=im.id, class_id=cd.id, class_name=cd.name,
                               confidence=0.4 + 0.1 * j, status="auto", source="yolo")
                a.set_points([(20 + j * 40, 20), (100 + j * 40, 30),
                              (110 + j * 40, 90), (25 + j * 40, 80)])
                anns.append(a)
            repo.replace_annotations(im.id, anns)
        repo.refresh_stats()
        _eq(repo.info.n_objects, 12)
        _eq(len(repo.class_stats()), 2)
        _true(repo.object_heatmap(12), "heatmap rong")
        _eq(sum(repo.confidence_histogram()), 12)
    check("tao class + annotation + thong ke", annotate)

    print("\n== Canvas ==")
    from app.views.widgets.canvas import (
        TOOL_BRUSH,
        TOOL_ERASER,
        TOOL_POLYGON,
        TOOL_SPLIT,
        AnnotationCanvas,
    )

    def canvas_ops():
        cv = AnnotationCanvas()
        cv.resize(800, 600)
        im = repo.images()[0]
        _true(cv.load_image(im.path, repo.annotations(im.id)), "khong mo duoc anh")
        cv.set_classes(repo.classes())
        cv.active_class_id = repo.classes()[0].id

        n0 = len(cv.annotations)
        cv.set_tool(TOOL_POLYGON)
        cv._draft = [QPointF(10, 10), QPointF(90, 12), QPointF(80, 95), QPointF(12, 88)]
        cv._finish_polygon()
        _eq(len(cv.annotations), n0 + 1)

        cv.selected = {len(cv.annotations) - 1}
        cv.set_tool(TOOL_BRUSH)
        cv.brush_size = 14
        before = cv.annotations[-1].area
        cv._brush_path = [QPointF(85, 50), QPointF(130, 50), QPointF(150, 60)]
        cv._apply_brush()
        _true(cv.annotations[-1].area > before, "Brush phai mo rong vung")

        cv.set_tool(TOOL_ERASER)
        before = cv.annotations[-1].area
        cv._brush_path = [QPointF(30, 30), QPointF(50, 50)]
        cv._apply_brush()
        _true(cv.annotations[-1].area < before, "Eraser phai thu nho vung")

        cv.selected = {len(cv.annotations) - 1}
        cv.set_tool(TOOL_SPLIT)
        n_before = len(cv.annotations)
        cv._split_line = [QPointF(0, 55), QPointF(300, 55)]
        cv._apply_split()
        _true(len(cv.annotations) >= n_before, "Split loi")

        cv.selected = {0, 1}
        cv.merge_selected()
        n = len(cv.annotations)
        cv.undo()
        cv.redo()
        _eq(len(cv.annotations), n)

        cv.fit_to_view()
        cv.zoom_by(1.4)
        _true(cv.viewport_image_rect().width() > 0, "viewport rong")
    check("polygon / brush / eraser / split / merge / undo", canvas_ops)

    print("\n== Xuat dataset ==")
    from app.core.exporters import DatasetExporter, ExportConfig

    for fmt in ("yolo_seg", "yolo_det", "coco", "voc", "mask"):
        def run(f=fmt):
            c = ExportConfig(fmt=f, output_dir=str(tmp / "exports"),
                             dataset_name=f, val_split=0.25)
            r = DatasetExporter(repo, c).run()
            _true(r.n_images > 0 and r.n_objects > 0, "khong xuat duoc gi")
            out = Path(r.output_dir)
            if f.startswith("yolo"):
                _true(Path(r.yaml_path).exists(), "thieu data.yaml")
                labels = list((out / "labels").rglob("*.txt"))
                _true(labels and labels[0].read_text().strip(), "file label rong")
            elif f == "coco":
                import json
                j = json.loads((out / "annotations" / "instances_train.json")
                               .read_text(encoding="utf-8"))
                _true(j["annotations"] and j["categories"], "COCO rong")
            elif f == "voc":
                _true(list((out / "Annotations").glob("*.xml")), "thieu file XML")
            elif f == "mask":
                _true(list((out / "masks").rglob("*.png")), "thieu file mask")
        check(f"dinh dang {fmt}", run)

    def export_obb_pose():
        """OBB va Pose phai ra dung dinh dang nhan cua Ultralytics."""
        from app.core.exporters import DatasetExporter, ExportConfig

        # gan them keypoint + hop xoay cho anh dau
        img = repo.images()[0]
        cd = repo.classes()[0]
        a = Annotation(image_id=img.id, class_id=cd.id, class_name=cd.name,
                       confidence=0.9, status="approved", source="manual")
        a.set_points([(10, 20), (70, 10), (80, 60), (20, 70)])   # hop xoay 4 dinh
        a.keypoints = [15.0, 25.0, 2.0, 60.0, 20.0, 2.0, 40.0, 60.0, 1.0]
        repo.replace_annotations(img.id, [a])

        for fmt, checker in (("yolo_obb", "obb"), ("yolo_pose", "pose")):
            c = ExportConfig(fmt=fmt, output_dir=str(tmp / "exports2"),
                             dataset_name=fmt, val_split=0.0, flat_layout=True)
            r = DatasetExporter(repo, c).run()
            out = Path(r.output_dir)
            txt = out / "labels" / "all" / f"{Path(img.path).stem}.txt"
            _true(txt.exists(), f"{fmt}: khong co file nhan")
            parts = txt.read_text(encoding="utf-8").strip().split()
            vals = [float(v) for v in parts[1:]]
            _true(all(0.0 <= v <= 1.0 for v in vals[:4]),
                  f"{fmt}: toa do phai duoc chuan hoa")
            if checker == "obb":
                _eq(len(parts), 9)          # class + 8 toa do
            else:
                # class + cx cy w h + 3 keypoint x 3 gia tri
                _eq(len(parts), 1 + 4 + 9)
                yaml_text = Path(r.yaml_path).read_text(encoding="utf-8")
                _true("kpt_shape: [3, 3]" in yaml_text,
                      f"data.yaml thieu kpt_shape dung: {yaml_text}")

        # COCO phai mang theo keypoints
        c = ExportConfig(fmt="coco", output_dir=str(tmp / "exports2"),
                         dataset_name="coco_kp", val_split=0.0, flat_layout=True)
        r = DatasetExporter(repo, c).run()
        import json
        j = json.loads((Path(r.output_dir) / "annotations" / "instances_all.json")
                       .read_text(encoding="utf-8"))
        kp_anns = [x for x in j["annotations"] if x.get("keypoints")]
        _true(kp_anns, "COCO khong xuat keypoints")
        _eq(len(kp_anns[0]["keypoints"]), 9)
        _eq(kp_anns[0]["num_keypoints"], 3)
        _true(j["categories"][0].get("keypoints"), "COCO thieu ten keypoint")

    check("dinh dang yolo_obb / yolo_pose / coco keypoints", export_obb_pose)

    print("\n== Nhap dataset ==")
    from app.core.importers import DatasetImporter, ImportConfig

    def _roundtrip(fmt: str, export_fmt: str):
        """Xuat -> Nhap lai -> so sanh so lieu."""
        # Xuat dataset goc
        ecfg = ExportConfig(fmt=export_fmt, output_dir=str(tmp / "rt_exports"),
                            dataset_name=f"rt_{fmt}", val_split=0.0, flat_layout=True,
                            copy_images=True)
        eres = DatasetExporter(repo, ecfg).run()
        _true(eres.n_images > 0, f"Xuat {export_fmt}: khong co anh")
        _true(eres.n_objects > 0, f"Xuat {export_fmt}: khong co annotation")

        # Tao repo moi de nhap vao
        repo2 = ProjectRepository.create(tmp / f"rt_proj_{fmt}", f"RT_{fmt}", task="segment")

        # Nhap lai tu thu muc vua xuat
        icfg = ImportConfig(fmt=fmt, dataset_dir=eres.output_dir, copy_images=False)
        imp = DatasetImporter(repo2, icfg)
        ires = imp.run()
        _true(ires.n_images > 0, f"Nhap {fmt}: khong co anh nao duoc nhap")
        _true(ires.n_annotations > 0, f"Nhap {fmt}: khong co annotation nao")
        _true(ires.n_classes_added > 0, f"Nhap {fmt}: khong co class nao duoc tao")

        # So sanh round-trip: so annotation phai bang nhau
        _eq(ires.n_images, eres.n_images)
        _eq(ires.n_annotations, eres.n_objects)

        # Kiem tra sai so toa do < 1px tren it nhat 1 anh
        imgs2 = repo2.images()
        _true(imgs2, "repo moi khong co anh")
        anns2 = repo2.annotations(imgs2[0].id)
        _true(anns2, "anh dau khong co annotation sau khi nhap")
        a2 = anns2[0]
        _true(a2.bbox[2] > a2.bbox[0], "bbox phai hop le (x2 > x1)")
        repo2.close()

    check("round-trip yolo_seg (export -> import)", lambda: _roundtrip("yolo_seg", "yolo_seg"))
    check("round-trip yolo_det (export -> import)", lambda: _roundtrip("yolo_det", "yolo_det"))
    check("round-trip coco     (export -> import)", lambda: _roundtrip("coco", "coco"))

    print("\n== Plugin ==")

    def plugins():
        from app.plugins.base import registry
        registry.discover(force=True)
        keys = set(registry.keys())
        _true(keys >= {"sam", "sam3_concept", "fastsam", "grounding_dino", "florence2"},
              f"thieu plugin: {keys}")
        for k in sorted(keys):
            ok, msg = registry.status(k)
            print(f"         {k}: {'san sang' if ok else msg}")

        # SAM Refiner phai tu chon duoc phien ban theo ultralytics dang cai
        from app.plugins.builtin.sam_refiner import pick_sam_weights, ultralytics_version
        ver = ultralytics_version()
        w, lb = pick_sam_weights("auto")
        if ver > (0, 0, 0):
            print(f"         ultralytics {'.'.join(map(str, ver))} -> chon {lb} ({w})")
            _true(w.endswith(".pt"), "ten trong so SAM khong hop le")
            if ver < (8, 3, 237):
                _true(w != "sam3.pt", "khong duoc chon SAM 3 khi ultralytics qua cu")
        else:
            print("         ultralytics: chua cai (bo qua ver check)")
        _eq(pick_sam_weights("sam2_b.pt")[0], "sam2_b.pt")

    check("kham pha plugin", plugins)

    def plugin_roundtrip():
        """Plugin gia lap: kiem tra ca duong di goi plugin tu dau den cuoi."""
        from app.core.inference import Detection
        from app.plugins.base import (
            AnnotatorPlugin,
            PluginContext,
            PluginInfo,
            registry,
        )

        class _Dummy(AnnotatorPlugin):
            info = PluginInfo(key="_dummy", name="Dummy", kind="refine",
                              requires=[], accepts_prompt=True)
            last_prompt = None

            def annotate(self, ctx: PluginContext) -> list[Detection]:
                _true(ctx.image is not None, "khong nhan duoc anh")
                _Dummy.last_prompt = ctx.prompt
                out = []
                for d in ctx.detections:
                    d.polygon = [0.0, 0.0, 10.0, 0.0, 10.0, 10.0]
                    out.append(d)
                return out

        registry.register(_Dummy)
        plugin = registry.get("_dummy")
        _true(plugin is not None, "khong lay duoc plugin")
        _true(plugin.is_available()[0], "plugin phai kha dung")
        plugin.load(PluginContext(device="cpu"))

        img = cv2.imread(str(next(img_dir.glob("*.jpg"))))
        ctx = PluginContext(
            image_path="x.jpg", image=img,
            detections=[Detection(class_id=0, class_name="a", confidence=0.5,
                                  bbox=[0, 0, 10, 10])],
            class_names=["a"], prompt="test prompt", device="cpu",
        )
        res = plugin.annotate(ctx)
        _eq(len(res), 1)
        _true(len(res[0].polygon) == 6, "plugin khong tra ve polygon")
        _eq(_Dummy.last_prompt, "test prompt")

    check("goi plugin (round-trip)", plugin_roundtrip)

    def plugin_config_lifecycle():
        """Kiem tra vong doi cau hinh: doi config -> plugin nhan dung gia tri."""
        from app.config import cfg
        from app.plugins.base import registry

        florence = registry.get("florence2")
        _true(florence is not None, "khong lay duoc florence2")
        _eq(florence.config("model_id"), "microsoft/Florence-2-base")

        cfg.set("plugins.config.florence2.model_id", "microsoft/Florence-2-large")
        cfg.save()
        florence_updated = registry.get("florence2")
        _eq(florence_updated.config("model_id"), "microsoft/Florence-2-large")

        fastsam = registry.get("fastsam")
        _eq(fastsam.config("imgsz"), 1024)
        cfg.set("plugins.config.fastsam.imgsz", 640)
        cfg.set("plugins.config.fastsam.mode", "generate")
        fastsam_updated = registry.get("fastsam")
        _eq(fastsam_updated.config("imgsz"), 640)
        _eq(fastsam_updated.config("mode"), "generate")

        cfg.set("plugins.config.florence2", {})
        cfg.set("plugins.config.fastsam", {})
        cfg.save()
        _eq(registry.get("florence2").config("model_id"), "microsoft/Florence-2-base")
        _eq(registry.get("fastsam").config("imgsz"), 1024)

    check("vong doi cau hinh plugin (config lifecycle)", plugin_config_lifecycle)

    def plugin_in_worker():
        """Diem tich hop that: AutoLabelWorker goi plugin va ghi annotation."""
        from app.core.inference import Detection, InferenceConfig
        from app.plugins.base import registry
        from app.workers.autolabel_worker import AutoLabelWorker

        class _Engine:            # engine gia, khong can tai model
            names = {0: "crack"}
            device = "cpu"
            class_names = ["crack"]

            def describe(self):
                return "fake"

        img = repo.images()[0]
        worker = AutoLabelWorker(repo, _Engine(), [img.id], InferenceConfig())
        plugin = registry.get("_dummy")
        dets = [Detection(class_id=0, class_name="crack", confidence=0.8,
                          bbox=[5, 5, 60, 60])]

        out = worker._apply_plugin(plugin, img.path, dets)
        _true(len(out[0].polygon) == 6, "plugin khong duoc ap dung trong worker")

        lookup = worker._sync_classes()
        anns, stats = worker._to_annotations(img.id, out, lookup)
        _eq(len(anns), 1)
        _true(anns[0].class_id > 0, "khong gan duoc class")
        _true(stats["max_conf"] > 0, "khong tinh duoc confidence")

    check("plugin trong AutoLabelWorker", plugin_in_worker)

    print("\n== Giao dien: goi vao trang chua dung ==")

    def lazy_pages():
        """Cac trang dung giao dien lazy - goi tu ben ngoai khong duoc crash."""
        from app.controllers.app_controller import AppController
        from app.views.main_window import MainWindow

        ctrl = AppController()
        win = MainWindow(ctrl)
        win.show()
        app.processEvents()
        try:
            # 1. Nhan video khi trang Frame Extractor chua tung mo
            win.pages["extract"].set_videos([str(video)])
            app.processEvents()
            _eq(len(win.pages["extract"].videos), 1)

            # 2. Nhan file tha vao khi trang Import chua tung mo
            win.pages["import"].accept_paths(
                [str(p) for p in sorted(img_dir.glob("*.jpg"))])
            app.processEvents()
            _true(win.pages["import"].image_files, "khong nhan duoc anh")

            # 3. Phat tin hieu khi cac trang khac chua dung
            ctrl.notify_images_changed()
            ctrl.notify_classes_changed()
            ctrl.modelChanged.emit()
            app.processEvents()

            # 4. Mo lan luot tat ca cac trang
            from app.constants import NAV_ITEMS
            for key, _t, _i in NAV_ITEMS:
                win.go_to_page(key)
                app.processEvents()
            _eq(len(win.pages["extract"].videos), 1)   # du lieu khong bi mat
        finally:
            ctrl.shutdown()
            win.deleteLater()
            app.processEvents()

    check("khong crash khi trang chua dung giao dien", lazy_pages)

    def extract_to_autolabel():
        """Cat frame xong -> Auto Label phai chon dung loat anh vua cat."""
        from app.controllers.app_controller import AppController
        from app.core.frame_extractor import ExtractConfig, FrameExtractor
        from app.views.main_window import MainWindow

        ctrl = AppController()
        win = MainWindow(ctrl)
        win.show()
        app.processEvents()
        try:
            proj = tmp / "flow"
            r2 = ProjectRepository.create(proj, "Flow")
            r2.close()
            ctrl.open_project(proj / "project.alsdb")
            app.processEvents()

            # 3 anh cu lam nhieu
            old = scan_folder_records([str(p) for p in sorted(img_dir.glob("*.jpg"))][:3],
                                      ExtractConfig(remove_similar=False))
            ctrl.repo.add_images_bulk(old.saved)
            old_ids = {im.id for im in ctrl.repo.images()}
            _eq(len(old_ids), 3)

            # cat frame that
            cfg_ex = ExtractConfig(every_n_frames=6, remove_similar=False,
                                   blur_detection=False)
            res = FrameExtractor(cfg_ex).extract(video, tmp / "flow_frames")
            ctrl.repo.add_images_bulk(res.saved)
            _true(res.n_saved > 0, "khong cat duoc frame nao")

            ex = win.pages["extract"]
            ex.ensure_built()
            batch = ex._image_ids_of(res)
            _eq(len(batch), res.n_saved)
            _true(not (set(batch) & old_ids), "loat moi lan sang anh cu")

            # chuyen sang Auto Label
            win.go_to_page("autolabel")
            app.processEvents()
            win.pages["autolabel"].set_batch(batch)
            app.processEvents()

            sel = set(win.pages["autolabel"].image_list.selected_ids())
            _eq(sel, set(batch))
            _true(not (sel & old_ids), "chon nham anh cu")
        finally:
            ctrl.shutdown()
            win.deleteLater()
            app.processEvents()

    check("cat frame -> Auto Label lay dung loat anh vua cat", extract_to_autolabel)

    print("\n== Da ngon ngu (i18n) ==")

    def test_i18n():
        from app.i18n import get_language, set_language, tr
        set_language("vi")
        _eq(get_language(), "vi")
        _eq(tr("nav.dashboard"), "Dashboard")
        _eq(tr("settings.title"), "Settings")

        set_language("en")
        _eq(get_language(), "en")
        _eq(tr("settings.general.language"), "Language")
        _eq(tr("common.save"), "Save")

        set_language("vi")
        _eq(get_language(), "vi")

    check("tra cuu va chuyen doi ngon ngu i18n", test_i18n)

    print("\n== Thiet bi ==")
    from app.core.inference import device_info
    d = device_info()
    print(f"         CUDA={d['cuda']} | {d['name']} | torch {d['torch'] or 'chua cai'}")

    repo.close()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(_SANDBOX, ignore_errors=True)

    print("\n" + "=" * 58)
    if FAILS:
        print(f"CO {len(FAILS)} LOI:")
        for name, tb in FAILS:
            print(f"\n--- {name} ---\n{tb}")
        return 1
    print("TAT CA KIEM TRA DEU DAT")
    return 0


def _fail(msg: str):
    raise AssertionError(msg)


def _true(cond, msg: str = "dieu kien sai"):
    if not cond:
        raise AssertionError(msg)


def _eq(got, want):
    if got != want:
        raise AssertionError(f"mong doi {want}, nhan duoc {got}")


if __name__ == "__main__":
    sys.exit(main())
