"""Tu kiem tra may (``AutoLabelStudioAI.exe --selftest``).

Chay headless toan bo luong nghiep vu cot loi tren may dich de xac nhan ban
dong goi hoat dong: moi truong -> tao project -> cat frame -> nap YOLO ->
suy luan -> gan nhan -> export. Ket qua ghi vao logs/selftest-report.txt.
"""

from __future__ import annotations

import platform
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

from app.constants import APP_NAME, APP_VERSION
from app.utils.paths import log_dir


class SelfTest:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.fails: list[str] = []
        self.tmp = Path(tempfile.mkdtemp(prefix="als_selftest_"))
        self.has_real_sample = False

    # ------------------------------------------------------------ helper ---
    def log(self, msg: str = "") -> None:
        self.lines.append(msg)

    def check(self, name: str, fn) -> None:
        t0 = time.time()
        try:
            detail = fn()
            extra = f" — {detail}" if detail else ""
            self.log(f"  [OK]   {name}{extra}  ({time.time() - t0:.1f}s)")
        except Exception as exc:
            self.fails.append(name)
            self.log(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
            self.log("         " + traceback.format_exc().strip().splitlines()[-1])

    # -------------------------------------------------------------- steps ---
    def run(self) -> int:
        self.log(f"{APP_NAME} v{APP_VERSION} — TU KIEM TRA MAY")
        self.log(f"Thoi gian: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(
            f"May: {platform.platform()} | Python {platform.python_version()} "
            f"| frozen={getattr(sys, 'frozen', False)}"
        )
        self.log("")

        self.log("== 1. Moi truong ==")
        self.check("import torch", self._env_torch)
        self.check("import ultralytics / opencv / shapely / PySide6", self._env_libs)
        self.check("thiet bi suy luan", self._env_device)

        self.log("")
        self.log("== 2. Project + du lieu ==")
        self.check("tao project tam", self._make_project)
        self.check("cat frame tu video tong hop (every_n_frames)", self._extract)

        self.log("")
        self.log("== 3. Model YOLO that ==")
        self.check("nap yolo11n.pt (tai ve neu chua co — can mang lan dau)", self._load_model)
        self.check("suy luan anh mau", self._predict)
        self.check("auto label ghi vao DB", self._autolabel)

        self.log("")
        self.log("== 4. Export ==")
        self.check("export YOLO detection", self._export)

        self.log("")
        ok = not self.fails
        if ok:
            self.log("KET QUA: PASS — may nay chay duoc AutoLabel Studio AI")
        else:
            self.log(f"KET QUA: FAIL ({len(self.fails)} loi): " + ", ".join(self.fails))
        try:
            if hasattr(self, "repo"):
                self.repo.close()
        except Exception:
            pass
        shutil.rmtree(self.tmp, ignore_errors=True)
        return 0 if ok else 1

    # ---------------------------------------------------------- 1. env ---
    def _env_torch(self):
        import torch

        cuda = "co" if torch.cuda.is_available() else "khong (dung CPU)"
        return f"torch {torch.__version__}, CUDA={cuda}"

    def _env_libs(self):
        import cv2
        import PySide6
        import shapely
        import ultralytics

        return (
            f"ultralytics {ultralytics.__version__}, opencv {cv2.__version__}, "
            f"shapely {shapely.__version__}, PySide6 {PySide6.__version__}"
        )

    def _env_device(self):
        from app.core.inference import device_label, resolve_device

        return f"{resolve_device('auto')} — {device_label('auto')}"

    # ------------------------------------------------------ 2. project ---
    def _make_project(self):
        import cv2
        import numpy as np

        from app.models.repository import ProjectRepository

        self.repo = ProjectRepository.create(self.tmp / "proj", "SelfTest", task="detect")
        # Anh mau co doi tuong that (bus.jpg cua Ultralytics) neu duoc dong goi kem
        sample = None
        try:
            from ultralytics.utils import ASSETS

            cand = Path(ASSETS) / "bus.jpg"
            if cand.exists():
                sample = cand
        except Exception:
            pass
        dst = self.repo.sub("images") / "sample.jpg"
        if sample is not None:
            shutil.copy2(sample, dst)
            self.has_real_sample = True
        else:
            rng = np.random.default_rng(1)
            img = (rng.random((480, 640, 3)) * 255).astype(np.uint8)
            cv2.imwrite(str(dst), img)
        im = cv2.imread(str(dst))
        self.sample_path = dst
        self.sample_id = self.repo.add_image(
            dst, width=im.shape[1], height=im.shape[0], source="import"
        )
        kind = "that" if self.has_real_sample else "tong hop"
        return f"{self.repo.root} (anh mau {kind})"

    def _extract(self):
        import cv2
        import numpy as np

        from app.core.frame_extractor import ExtractConfig, FrameExtractor

        base = cv2.imread(str(self.sample_path))
        h, w = base.shape[:2]
        video = self.tmp / "clip.mp4"
        vw = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
        for i in range(20):
            m = np.float32([[1, 0, i * 4], [0, 1, 0]])
            vw.write(cv2.warpAffine(base, m, (w, h)))
        vw.release()
        cfg = ExtractConfig(mode="every_n_frames", every_n_frames=5, remove_similar=False)
        res = FrameExtractor(cfg).extract(video, self.repo.sub("frames"))
        self.frame_ids = []
        for i, rec in enumerate(res.saved):
            self.frame_ids.append(
                self.repo.add_image(
                    rec["path"],
                    width=rec["width"],
                    height=rec["height"],
                    source="video",
                    frame_index=i,
                )
            )
        if not self.frame_ids:
            raise RuntimeError("khong cat duoc frame nao")
        return f"{len(self.frame_ids)} frame"

    # -------------------------------------------------------- 3. model ---
    def _load_model(self):
        from app.core.inference import YoloEngine

        self.engine = YoloEngine()
        self.engine.load(
            "yolo11n.pt", task="detect", device="auto", log_cb=lambda m: self.log("         " + m)
        )
        if not self.engine.loaded:
            raise RuntimeError("engine chua nap")
        return self.engine.describe()

    def _predict(self):
        from app.core.inference import InferenceConfig

        dets = self.engine.predict(str(self.sample_path), InferenceConfig(confidence=0.3))
        names = sorted({d.class_name for d in dets})
        if self.has_real_sample and not dets:
            raise RuntimeError("anh bus.jpg phai phat hien duoc doi tuong")
        return f"{len(dets)} detection {names}"

    def _autolabel(self):
        from app.core.inference import InferenceConfig
        from app.workers.autolabel_worker import AutoLabelWorker

        ids = [self.sample_id] + self.frame_ids
        worker = AutoLabelWorker(self.repo, self.engine, ids, InferenceConfig(confidence=0.3))
        res = worker.execute()
        n_db = sum(len(self.repo.annotations(i)) for i in ids)
        if n_db != res.n_objects:
            raise RuntimeError(f"DB {n_db} != worker {res.n_objects}")
        return f"{res.n_images} anh, {res.n_objects} doi tuong, class={list(res.per_class)}"

    # ------------------------------------------------------- 4. export ---
    def _export(self):
        from app.core.exporters import DatasetExporter, ExportConfig

        ecfg = ExportConfig(
            fmt="yolo_det",
            output_dir=str(self.tmp / "out"),
            dataset_name="ds",
            include_unlabeled=True,
        )
        res = DatasetExporter(self.repo, ecfg).run()
        labels = [p for p in (self.tmp / "out" / "ds").rglob("*.txt") if p.name != "classes.txt"]
        if not Path(res.yaml_path).exists():
            raise RuntimeError("thieu data.yaml")
        return f"{res.n_images} anh, {res.n_objects} doi tuong, {len(labels)} file nhan"


def run_selftest(show_dialog: bool = True) -> int:
    """Chay selftest, ghi bao cao, (tuy chon) hien hop thoai. Tra ve exit code."""
    st = SelfTest()
    try:
        code = st.run()
    except Exception:
        st.log("LOI NGOAI DU KIEN:\n" + traceback.format_exc())
        code = 2
    report = "\n".join(st.lines)
    out = log_dir() / "selftest-report.txt"
    try:
        out.write_text(report, encoding="utf-8")
    except Exception:
        pass
    try:
        print(report)
    except Exception:
        pass
    if show_dialog:
        try:
            from PySide6.QtWidgets import QMessageBox

            box = QMessageBox()
            box.setIcon(QMessageBox.Information if code == 0 else QMessageBox.Critical)
            box.setWindowTitle(f"{APP_NAME} — Tu kiem tra may")
            box.setText(st.lines[-1] if st.lines else "Khong co ket qua")
            box.setInformativeText(f"Bao cao day du: {out}")
            box.setDetailedText(report)
            box.exec()
        except Exception:
            pass
    return code
