"""Nhap dataset da gan nhan san (YOLO / COCO) vao project.

Ho tro:
  - YOLO Segmentation (toa do chuan hoa -> polygon pixel)
  - YOLO Detection    (toa do chuan hoa -> bbox pixel)
  - COCO JSON         (bbox + segmentation polygon flat-list)

Logic xung dot class: tu dong gop vao class trung ten co san,
class moi thi tu tao moi — khong can can thiep thu cong.

Anh khong tim thay tren dia: bo qua, ghi log canh bao,
tiep tuc nhap cac anh con lai.
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.constants import ANN_AUTO, IMG_AUTO, SHAPE_BBOX, SHAPE_POLYGON
from app.models.entities import Annotation
from app.models.repository import ProjectRepository
from app.utils.logger import get_logger

log = get_logger(__name__)

# Cac duoi anh duoc coi la hop le
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


@dataclass
class ImportConfig:
    fmt: str = "yolo_seg"       # "yolo_seg" | "yolo_det" | "coco"
    dataset_dir: str = ""       # thu muc goc cua dataset
    copy_images: bool = True    # sao chep anh vao thu muc images/ cua project
    source_tag: str = "import"  # gia tri ghi vao truong source cua Annotation


@dataclass
class ImportResult:
    n_images: int = 0
    n_annotations: int = 0
    n_classes_added: int = 0
    n_classes_merged: int = 0
    n_skipped: int = 0
    elapsed: float = 0.0
    cancelled: bool = False
    warnings: list[str] = field(default_factory=list)


# ================================================================ IMPORTER ===
class DatasetImporter:
    def __init__(self, repo: ProjectRepository, config: ImportConfig) -> None:
        self.repo = repo
        self.cfg = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    # ------------------------------------------------------------ preview ---
    def preview(self) -> dict:
        """Phan tich so bo de hien thi trang xem truoc, KHONG ghi DB."""
        cfg = self.cfg
        d = Path(cfg.dataset_dir)
        if not d.exists():
            return {"error": f"Khong tim thay thu muc: {d}"}
        try:
            if cfg.fmt == "coco":
                return self._preview_coco(d)
            return self._preview_yolo(d)
        except Exception as exc:
            return {"error": str(exc)}

    def _preview_yolo(self, root: Path) -> dict:
        class_names, _ = _load_yolo_classes(root)
        label_files = list(root.rglob("labels/**/*.txt"))
        if not label_files:
            label_files = list(root.rglob("*.txt"))
            label_files = [f for f in label_files
                           if f.name not in ("classes.txt", "data.yaml")]
        n_ann = 0
        for lf in label_files:
            try:
                lines = [l for l in lf.read_text(encoding="utf-8").splitlines() if l.strip()]
                n_ann += len(lines)
            except Exception:
                pass
        existing = {c.name.lower() for c in self.repo.classes()}
        new_cls = [n for n in class_names if n.lower() not in existing]
        merge_cls = [n for n in class_names if n.lower() in existing]
        return {
            "fmt": self.cfg.fmt,
            "n_images": len(label_files),
            "n_annotations": n_ann,
            "n_classes_total": len(class_names),
            "n_classes_new": len(new_cls),
            "n_classes_merge": len(merge_cls),
            "class_names": class_names,
        }

    def _preview_coco(self, root: Path) -> dict:
        json_files = list(root.rglob("*.json"))
        if not json_files:
            return {"error": "Khong tim thay file JSON trong thu muc."}
        n_img, n_ann = 0, 0
        class_names: list[str] = []
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if "annotations" not in data:
                    continue
                n_img += len(data.get("images", []))
                n_ann += len(data["annotations"])
                for cat in data.get("categories", []):
                    name = cat.get("name", "")
                    if name and name not in class_names:
                        class_names.append(name)
            except Exception:
                pass
        existing = {c.name.lower() for c in self.repo.classes()}
        new_cls = [n for n in class_names if n.lower() not in existing]
        merge_cls = [n for n in class_names if n.lower() in existing]
        return {
            "fmt": "coco",
            "n_images": n_img,
            "n_annotations": n_ann,
            "n_classes_total": len(class_names),
            "n_classes_new": len(new_cls),
            "n_classes_merge": len(merge_cls),
            "class_names": class_names,
        }

    # --------------------------------------------------------------- chay ---
    def run(self, progress_cb=None, log_cb=None) -> ImportResult:
        t0 = time.time()
        _log = log_cb or (lambda *_: None)
        result = ImportResult()
        cfg = self.cfg
        root = Path(cfg.dataset_dir)
        if not root.exists():
            raise FileNotFoundError(f"Khong tim thay thu muc dataset: {root}")

        _log(f"Bat dau nhap {cfg.fmt} tu {root}")
        if cfg.fmt == "coco":
            self._run_coco(root, result, progress_cb, _log)
        else:
            self._run_yolo(root, result, progress_cb, _log)

        result.cancelled = self._cancelled
        result.elapsed = time.time() - t0
        if not self._cancelled:
            self.repo.recount_all_images()
            self.repo.log_history("import", f"{cfg.fmt} <- {root}")
        _log(
            f"Hoan tat sau {result.elapsed:.1f}s: "
            f"{result.n_images} anh, {result.n_annotations} annotation, "
            f"{result.n_classes_added} class moi, {result.n_skipped} bo qua."
        )
        return result

    # ========================================================= YOLO PARSER ==
    def _run_yolo(self, root: Path, result: ImportResult,
                  progress_cb, _log) -> None:
        class_names, _ = _load_yolo_classes(root)
        _log(f"Doc duoc {len(class_names)} class: {class_names}")

        # Tao / gop class
        class_map: dict[int, int] = {}   # yolo_index -> repo class_id
        for i, name in enumerate(class_names):
            cd = self._ensure_class(name, result)
            class_map[i] = cd.id

        # Tim tat ca file label
        label_files = sorted(root.rglob("labels/**/*.txt"))
        if not label_files:
            # flat layout: .txt nam cung cap voi anh
            label_files = sorted(
                f for f in root.rglob("*.txt")
                if f.name not in ("classes.txt",)
            )

        total = len(label_files)
        seg = self.cfg.fmt != "yolo_det"

        for done, lf in enumerate(label_files, start=1):
            if self._cancelled:
                return
            img_path = _find_image_for_label(lf, root)
            if img_path is None:
                msg = f"Khong tim thay anh cho nhan: {lf.name}"
                result.warnings.append(msg)
                _log(f"[CANH BAO] {msg}")
                result.n_skipped += 1
                if progress_cb:
                    progress_cb(done, total, lf.name)
                continue

            dest = self._resolve_dest(img_path)
            w, h = _image_size(dest)

            anns: list[Annotation] = []
            try:
                lines = [l.strip() for l in
                         lf.read_text(encoding="utf-8").splitlines() if l.strip()]
            except Exception as exc:
                _log(f"[CANH BAO] Doc nhan loi {lf.name}: {exc}")
                result.n_skipped += 1
                continue

            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                try:
                    yi = int(parts[0])
                    vals = [float(v) for v in parts[1:]]
                except ValueError:
                    continue
                class_id = class_map.get(yi)
                if class_id is None:
                    continue

                if seg and len(vals) >= 6:
                    # YOLO Seg: x1 y1 x2 y2 ... (chuan hoa)
                    poly = []
                    for k in range(0, len(vals) - 1, 2):
                        poly.append(vals[k] * w)
                        poly.append(vals[k + 1] * h)
                    a = Annotation(
                        image_id=0, class_id=class_id,
                        shape=SHAPE_POLYGON,
                        polygon=poly,
                        confidence=1.0, status=ANN_AUTO,
                        source=self.cfg.source_tag,
                    )
                    a.recompute()
                else:
                    # YOLO Det: cx cy bw bh (chuan hoa)
                    if len(vals) < 4:
                        continue
                    cx, cy, bw, bh = vals[:4]
                    x1 = (cx - bw / 2) * w
                    y1 = (cy - bh / 2) * h
                    x2 = (cx + bw / 2) * w
                    y2 = (cy + bh / 2) * h
                    a = Annotation(
                        image_id=0, class_id=class_id,
                        shape=SHAPE_BBOX,
                        bbox=[x1, y1, x2, y2],
                        confidence=1.0, status=ANN_AUTO,
                        source=self.cfg.source_tag,
                    )
                    a.area = max(0.0, (x2 - x1) * (y2 - y1))
                anns.append(a)

            img_id = self._write_image(dest, w, h, anns, result)
            if img_id:
                result.n_images += 1
                result.n_annotations += len(anns)

            if progress_cb:
                progress_cb(done, total, img_path.name)

    # ========================================================= COCO PARSER ==
    def _run_coco(self, root: Path, result: ImportResult,
                  progress_cb, _log) -> None:
        json_files = sorted(root.rglob("*.json"))
        if not json_files:
            raise FileNotFoundError("Khong tim thay file JSON trong thu muc.")

        for jf in json_files:
            if self._cancelled:
                return
            _log(f"Dang xu ly {jf.name} ...")
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except Exception as exc:
                _log(f"[CANH BAO] Loi doc {jf.name}: {exc}")
                continue
            if "annotations" not in data:
                continue

            # Map category_id -> repo class_id
            cat_map: dict[int, int] = {}
            for cat in data.get("categories", []):
                cd = self._ensure_class(cat["name"], result)
                cat_map[cat["id"]] = cd.id

            # Map image_id -> image info
            img_info: dict[int, dict] = {
                im["id"]: im for im in data.get("images", [])
            }

            # Nhom annotation theo image_id
            ann_by_img: dict[int, list[dict]] = {}
            for ann in data.get("annotations", []):
                ann_by_img.setdefault(ann["image_id"], []).append(ann)

            total_imgs = len(img_info)
            for done, (img_id_coco, im_meta) in enumerate(img_info.items(), start=1):
                if self._cancelled:
                    return
                img_path = _find_coco_image(im_meta["file_name"], jf.parent, root)
                if img_path is None:
                    msg = f"Khong tim thay anh: {im_meta['file_name']}"
                    result.warnings.append(msg)
                    _log(f"[CANH BAO] {msg}")
                    result.n_skipped += 1
                    if progress_cb:
                        progress_cb(done, total_imgs, im_meta["file_name"])
                    continue

                dest = self._resolve_dest(img_path)
                w = im_meta.get("width", 0) or _image_size(dest)[0]
                h = im_meta.get("height", 0) or _image_size(dest)[1]

                anns: list[Annotation] = []
                for raw in ann_by_img.get(img_id_coco, []):
                    class_id = cat_map.get(raw.get("category_id", -1))
                    if class_id is None:
                        continue
                    bbox_raw = raw.get("bbox", [])   # [x, y, w, h] COCO format
                    if len(bbox_raw) == 4:
                        x1 = float(bbox_raw[0])
                        y1 = float(bbox_raw[1])
                        x2 = x1 + float(bbox_raw[2])
                        y2 = y1 + float(bbox_raw[3])
                    else:
                        x1 = y1 = x2 = y2 = 0.0

                    segs = raw.get("segmentation", [])
                    poly: list[float] = []
                    if isinstance(segs, list) and segs and isinstance(segs[0], list):
                        # lay polygon lon nhat
                        poly = [float(v) for v in max(segs, key=len)]

                    if len(poly) >= 6:
                        a = Annotation(
                            image_id=0, class_id=class_id,
                            shape=SHAPE_POLYGON, polygon=poly,
                            bbox=[x1, y1, x2, y2],
                            confidence=float(raw.get("score", 1.0)),
                            status=ANN_AUTO, source=self.cfg.source_tag,
                        )
                        a.recompute()
                    else:
                        a = Annotation(
                            image_id=0, class_id=class_id,
                            shape=SHAPE_BBOX, bbox=[x1, y1, x2, y2],
                            confidence=float(raw.get("score", 1.0)),
                            area=max(0.0, (x2 - x1) * (y2 - y1)),
                            status=ANN_AUTO, source=self.cfg.source_tag,
                        )
                    anns.append(a)

                img_id = self._write_image(dest, w, h, anns, result)
                if img_id:
                    result.n_images += 1
                    result.n_annotations += len(anns)
                if progress_cb:
                    progress_cb(done, total_imgs, im_meta["file_name"])

    # ------------------------------------------------------------ phu tro ---
    def _ensure_class(self, name: str, result: ImportResult):
        existing = self.repo.class_by_name(name)
        if existing:
            result.n_classes_merged += 1
            return existing
        cd = self.repo.add_class(name)
        result.n_classes_added += 1
        return cd

    def _resolve_dest(self, src: Path) -> Path:
        """Sao chep anh vao project neu can, tra ve duong dan cuoi cung."""
        if self.cfg.copy_images:
            return self.repo.copy_into_project(src, "images")
        return src

    def _write_image(self, img_path: Path, w: int, h: int,
                     anns: list[Annotation], result: ImportResult) -> int:
        """Them anh vao DB neu chua co, ghi de annotation, tra ve image_id."""
        existing = self.repo.image_by_path(str(img_path))
        if existing:
            img_id = existing.id
        else:
            img_id = self.repo.add_image(str(img_path), width=w, height=h,
                                         source=self.cfg.source_tag)
        if not img_id:
            return 0
        for a in anns:
            a.image_id = img_id
        self.repo.replace_annotations(img_id, anns)
        if anns:
            self.repo.set_image_status(img_id, IMG_AUTO)
        return img_id


# ================================================================ HELPERS ===
def _load_yolo_classes(root: Path) -> tuple[list[str], Path | None]:
    """Doc ten class tu data.yaml hoac classes.txt."""
    # Uu tien data.yaml
    yaml_files = list(root.rglob("data.yaml"))
    if yaml_files:
        try:
            text = yaml_files[0].read_text(encoding="utf-8")
            names: list[str] = []
            in_names = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("names:"):
                    in_names = True
                    rest = stripped[6:].strip()
                    if rest.startswith("["):
                        # names: [a, b, c]
                        import ast
                        names = [str(x).strip() for x in ast.literal_eval(rest)]
                        in_names = False
                    continue
                if in_names:
                    if stripped.startswith("-") or (stripped and stripped[0].isdigit()):
                        val = stripped.lstrip("-").split(":", 1)[-1].strip()
                        if val:
                            names.append(val)
                    elif stripped and not stripped.startswith("#"):
                        in_names = False
            if names:
                return names, yaml_files[0]
        except Exception:
            pass

    # Fallback: classes.txt
    for cfile in root.rglob("classes.txt"):
        try:
            names = [l.strip() for l in cfile.read_text(
                encoding="utf-8").splitlines() if l.strip()]
            if names:
                return names, cfile
        except Exception:
            pass
    return [], None


def _find_image_for_label(label_file: Path, root: Path) -> Path | None:
    """Tim anh tuong ung voi file nhan YOLO."""
    # labels/train/img.txt -> images/train/img.{ext}
    # labels/img.txt       -> images/img.{ext} hoac cung cap
    stem = label_file.stem
    candidates: list[Path] = []

    # Doi duong labels -> images
    parts = label_file.parts
    try:
        li = parts.index("labels")
        img_parts = list(parts)
        img_parts[li] = "images"
        img_base = Path(*img_parts).with_suffix("")
        for ext in _IMAGE_EXTS:
            candidates.append(img_base.with_suffix(ext))
    except ValueError:
        pass

    # Cung thu muc voi file label
    for ext in _IMAGE_EXTS:
        candidates.append(label_file.parent / f"{stem}{ext}")

    # Tim trong toan bo cay thu muc
    for ext in _IMAGE_EXTS:
        for p in root.rglob(f"{stem}{ext}"):
            candidates.append(p)

    for c in candidates:
        if c.exists():
            return c
    return None


def _find_coco_image(filename: str, json_dir: Path, root: Path) -> Path | None:
    """Tim anh theo ten file trong COCO JSON."""
    name = Path(filename).name
    candidates = [
        json_dir / filename,
        json_dir / name,
        root / filename,
        root / name,
        root / "images" / name,
    ]
    # Tim trong tat ca thu muc con cua images/ (vi du images/train/, images/all/)
    img_root = root / "images"
    if img_root.is_dir():
        for sub in img_root.iterdir():
            if sub.is_dir():
                candidates.append(sub / name)

    # Tim rong rai toan bo cay
    for folder in root.rglob("images"):
        if folder.is_dir():
            candidates.append(folder / name)

    for c in candidates:
        if c.exists():
            return c
    return None


def _image_size(path: Path) -> tuple[int, int]:
    """Doc kich thuoc anh. Tra ve (0, 0) neu loi."""
    try:
        import cv2
        img = cv2.imread(str(path))
        if img is not None:
            return img.shape[1], img.shape[0]
    except Exception:
        pass
    try:
        from PIL import Image as PilImage
        with PilImage.open(path) as im:
            return im.size  # (width, height)
    except Exception:
        pass
    return 0, 0
