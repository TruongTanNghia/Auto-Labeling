"""Xuat dataset ra cac dinh dang pho bien.

Ho tro: YOLO Detection, YOLO Segmentation, COCO JSON, Pascal VOC XML, PNG Mask.
"""

from __future__ import annotations

import json
import random
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from app.constants import IMG_APPROVED, IMG_AUTO, IMG_REVIEW
from app.i18n import tr
from app.models.entities import Annotation, ClassDef, ImageRecord
from app.models.repository import ProjectRepository
from app.utils.logger import get_logger
from app.utils.paths import ensure_dir

log = get_logger(__name__)


@dataclass
class ExportConfig:
    fmt: str = "yolo_seg"
    output_dir: str = ""
    train_split: float = 0.8
    val_split: float = 0.2
    test_split: float = 0.0
    seed: int = 42
    copy_images: bool = True
    only_approved: bool = False
    include_unlabeled: bool = False
    exclude_duplicates: bool = True
    exclude_blurry: bool = False
    blur_threshold: float = 60.0
    min_confidence: float = 0.0
    class_ids: list[int] = field(default_factory=list)  # rong = tat ca
    dataset_name: str = "dataset"
    write_yaml: bool = True
    flat_layout: bool = False  # khong chia train/val


@dataclass
class ExportResult:
    output_dir: str = ""
    fmt: str = ""
    n_images: int = 0
    n_objects: int = 0
    n_classes: int = 0
    splits: dict = field(default_factory=dict)
    yaml_path: str = ""
    elapsed: float = 0.0
    cancelled: bool = False


# =============================================================== EXPORTER ===
class DatasetExporter:
    def __init__(self, repo: ProjectRepository, config: ExportConfig) -> None:
        self.repo = repo
        self.cfg = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    # ------------------------------------------------------------- pipeline --
    def run(self, progress_cb=None, log_cb=None) -> ExportResult:
        t0 = time.time()
        _log = log_cb or (lambda *_: None)
        cfg = self.cfg

        out_dir = ensure_dir(Path(cfg.output_dir) / cfg.dataset_name)
        classes = self._classes()
        images = self._select_images()
        if not images:
            raise RuntimeError(tr("exporter.no_images_error", "Không có ảnh nào thoả điều kiện để xuất."))

        _log(
            tr(
                "exporter.preparing_log",
                "Chuẩn bị xuất {images} ảnh, {classes} class -> {dir}",
                images=len(images),
                classes=len(classes),
                dir=out_dir,
            )
        )
        splits = self._split(images)
        for name, items in splits.items():
            _log(f"  {name}: {len(items)} " + tr("exporter.images_unit", "ảnh"))

        writer = {
            "yolo_seg": self._export_yolo,
            "yolo_det": self._export_yolo,
            "yolo_obb": self._export_yolo,
            "yolo_pose": self._export_yolo,
            "coco": self._export_coco,
            "voc": self._export_voc,
            "mask": self._export_mask,
        }.get(cfg.fmt)
        if writer is None:
            raise ValueError(tr("exporter.unsupported_format_error", "Định dạng không hỗ trợ: {fmt}", fmt=cfg.fmt))

        result = ExportResult(output_dir=str(out_dir), fmt=cfg.fmt, n_classes=len(classes))
        result.splits = {k: len(v) for k, v in splits.items()}
        writer(out_dir, splits, classes, result, progress_cb, _log)
        result.cancelled = self._cancelled
        result.elapsed = time.time() - t0
        _log(
            tr(
                "exporter.done_log",
                "Hoàn tất sau {elapsed:.1f}s: {images} ảnh, {objects} đối tượng.",
                elapsed=result.elapsed,
                images=result.n_images,
                objects=result.n_objects,
            )
        )
        self.repo.log_history("export", f"{cfg.fmt} -> {out_dir}")
        return result

    # ------------------------------------------------------------ chon anh --
    def _classes(self) -> list[ClassDef]:
        classes = self.repo.classes(refresh=True)
        if self.cfg.class_ids:
            classes = [c for c in classes if c.id in self.cfg.class_ids]
        return classes

    def _select_images(self) -> list[ImageRecord]:
        cfg = self.cfg
        status = IMG_APPROVED if cfg.only_approved else None
        images = self.repo.images(status=status, include_duplicates=not cfg.exclude_duplicates)
        if not cfg.only_approved and not cfg.include_unlabeled:
            images = [im for im in images if im.status in (IMG_AUTO, IMG_REVIEW, IMG_APPROVED)]
        if cfg.exclude_blurry:
            images = [im for im in images if not (0 < im.blur_score < cfg.blur_threshold)]
        return [im for im in images if Path(im.path).exists()]

    def _split(self, images: list[ImageRecord]) -> dict[str, list[ImageRecord]]:
        cfg = self.cfg
        if cfg.flat_layout:
            return {"all": images}
        items = list(images)
        random.Random(cfg.seed).shuffle(items)
        n = len(items)
        n_val = int(n * cfg.val_split)
        n_test = int(n * cfg.test_split)
        n_train = max(0, n - n_val - n_test)
        out = {"train": items[:n_train], "val": items[n_train : n_train + n_val]}
        if n_test:
            out["test"] = items[n_train + n_val :]
        return {k: v for k, v in out.items() if v}

    def _annotations(self, image: ImageRecord, class_map: dict[int, int]) -> list[Annotation]:
        anns = self.repo.annotations(image.id)
        out = []
        for a in anns:
            if a.class_id not in class_map:
                continue
            if a.confidence < self.cfg.min_confidence:
                continue
            out.append(a)
        return out

    def _copy_image(self, src: Path, dest_dir: Path) -> Path:
        dest = dest_dir / src.name
        if self.cfg.copy_images:
            if not dest.exists():
                shutil.copy2(src, dest)
        return dest

    # =========================================================== YOLO ======
    def _export_yolo(self, out_dir, splits, classes, result, progress_cb, _log):
        fmt = self.cfg.fmt
        seg = fmt == "yolo_seg"
        obb = fmt == "yolo_obb"
        pose = fmt == "yolo_pose"
        class_map = {c.id: i for i, c in enumerate(classes)}
        total = sum(len(v) for v in splits.values())
        done = 0
        kpt_shape = [0, 3]  # suy ra tu du lieu that de ghi vao data.yaml

        for split, items in splits.items():
            img_dir = ensure_dir(out_dir / "images" / split)
            lbl_dir = ensure_dir(out_dir / "labels" / split)
            for im in items:
                if self._cancelled:
                    return
                src = Path(im.path)
                self._copy_image(src, img_dir)
                lines = []
                for a in self._annotations(im, class_map):
                    ci = class_map[a.class_id]
                    w, h = max(1, im.width), max(1, im.height)
                    if seg and len(a.polygon) >= 6:
                        coords = []
                        for i in range(0, len(a.polygon) - 1, 2):
                            coords.append(_clip01(a.polygon[i] / w))
                            coords.append(_clip01(a.polygon[i + 1] / h))
                        lines.append(f"{ci} " + " ".join(f"{v:.6f}" for v in coords))
                    elif obb:
                        # YOLO OBB: class x1 y1 x2 y2 x3 y3 x4 y4 (chuan hoa)
                        corners = _obb_corners(a)
                        coords = []
                        for x, y in corners:
                            coords.append(_clip01(x / w))
                            coords.append(_clip01(y / h))
                        lines.append(f"{ci} " + " ".join(f"{v:.6f}" for v in coords))
                    elif pose:
                        # YOLO Pose: class cx cy w h  px py [v] ... (chuan hoa)
                        x1, y1, x2, y2 = a.bbox
                        parts = [
                            f"{_clip01(((x1 + x2) / 2) / w):.6f}",
                            f"{_clip01(((y1 + y2) / 2) / h):.6f}",
                            f"{_clip01((x2 - x1) / w):.6f}",
                            f"{_clip01((y2 - y1) / h):.6f}",
                        ]
                        kp, dim = _keypoints(a)
                        kpt_shape = [max(kpt_shape[0], len(kp)), dim]
                        for k in kp:
                            parts.append(f"{_clip01(k[0] / w):.6f}")
                            parts.append(f"{_clip01(k[1] / h):.6f}")
                            if dim == 3:
                                parts.append(f"{int(k[2])}")
                        lines.append(f"{ci} " + " ".join(parts))
                    else:
                        x1, y1, x2, y2 = a.bbox
                        cx = _clip01(((x1 + x2) / 2) / w)
                        cy = _clip01(((y1 + y2) / 2) / h)
                        bw = _clip01((x2 - x1) / w)
                        bh = _clip01((y2 - y1) / h)
                        lines.append(f"{ci} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                    result.n_objects += 1
                (lbl_dir / f"{src.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
                result.n_images += 1
                done += 1
                if progress_cb and done % 10 == 0:
                    progress_cb(done, total, f"{split}: {src.name}")

        if self.cfg.write_yaml:
            yaml_path = out_dir / "data.yaml"
            names = "\n".join(f"  {i}: {c.name}" for i, c in enumerate(classes))
            content = [
                f"# {self.cfg.dataset_name} - sinh boi AutoLabel Studio AI",
                f"path: {out_dir.as_posix()}",
            ]
            for split in splits:
                content.append(f"{split}: images/{split}")
            if "val" not in splits:
                content.append("val: images/train")
            content.append(f"nc: {len(classes)}")
            if pose and kpt_shape[0] > 0:
                # Ultralytics can kpt_shape de train duoc model pose
                content.append(f"kpt_shape: [{kpt_shape[0]}, {kpt_shape[1]}]")
            content.append("names:")
            content.append(names)
            yaml_path.write_text("\n".join(content) + "\n", encoding="utf-8")
            result.yaml_path = str(yaml_path)
            _log(f"Da ghi {yaml_path.name}")

        (out_dir / "classes.txt").write_text("\n".join(c.name for c in classes), encoding="utf-8")
        if progress_cb:
            progress_cb(total, total, "Hoan tat")

    # =========================================================== COCO ======
    def _export_coco(self, out_dir, splits, classes, result, progress_cb, _log):
        class_map = {c.id: i + 1 for i, c in enumerate(classes)}  # COCO id bat dau tu 1
        ann_dir = ensure_dir(out_dir / "annotations")
        total = sum(len(v) for v in splits.values())
        done = 0

        categories = [
            {"id": class_map[c.id], "name": c.name, "supercategory": "object"} for c in classes
        ]
        n_kpt = 0

        for split, items in splits.items():
            img_dir = ensure_dir(out_dir / "images" / split)
            coco = {
                "info": {
                    "description": self.cfg.dataset_name,
                    "version": "1.0",
                    "contributor": "AutoLabel Studio AI",
                    "date_created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                },
                "licenses": [{"id": 1, "name": "Unknown", "url": ""}],
                "images": [],
                "annotations": [],
                "categories": categories,
            }
            ann_id = 1
            for img_id, im in enumerate(items, start=1):
                if self._cancelled:
                    return
                src = Path(im.path)
                self._copy_image(src, img_dir)
                coco["images"].append(
                    {
                        "id": img_id,
                        "file_name": src.name,
                        "width": im.width,
                        "height": im.height,
                        "license": 1,
                    }
                )
                for a in self._annotations(im, class_map):
                    x1, y1, x2, y2 = a.bbox
                    w, h = max(0.0, x2 - x1), max(0.0, y2 - y1)
                    seg = []
                    if len(a.polygon) >= 6:
                        seg = [[round(float(v), 2) for v in a.polygon]]
                    entry = {
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": class_map[a.class_id],
                        "bbox": [round(x1, 2), round(y1, 2), round(w, 2), round(h, 2)],
                        "area": round(float(a.area or w * h), 2),
                        "segmentation": seg,
                        "iscrowd": 0,
                        "score": round(float(a.confidence), 4),
                    }
                    kp, _dim = _keypoints(a)
                    if kp:
                        flat = []
                        for x, y, v in kp:
                            flat.extend(
                                [
                                    round(float(x), 2),
                                    round(float(y), 2),
                                    int(v if v in (0, 1, 2) else 2),
                                ]
                            )
                        entry["keypoints"] = flat
                        entry["num_keypoints"] = sum(1 for _x, _y, v in kp if v > 0)
                        n_kpt = max(n_kpt, len(kp))
                    coco["annotations"].append(entry)
                    ann_id += 1
                    result.n_objects += 1
                result.n_images += 1
                done += 1
                if progress_cb and done % 10 == 0:
                    progress_cb(done, total, f"{split}: {src.name}")

            if n_kpt:
                for cat in coco["categories"]:
                    cat.setdefault("keypoints", [f"kpt_{i + 1}" for i in range(n_kpt)])
                    cat.setdefault("skeleton", [])
            path = ann_dir / f"instances_{split}.json"
            path.write_text(json.dumps(coco, ensure_ascii=False), encoding="utf-8")
            _log(f"Da ghi {path.name} ({len(coco['annotations'])} annotation)")
        if progress_cb:
            progress_cb(total, total, "Hoan tat")

    # ============================================================ VOC ======
    def _export_voc(self, out_dir, splits, classes, result, progress_cb, _log):
        class_map = {c.id: c.name for c in classes}
        img_dir = ensure_dir(out_dir / "JPEGImages")
        xml_dir = ensure_dir(out_dir / "Annotations")
        set_dir = ensure_dir(out_dir / "ImageSets" / "Main")
        total = sum(len(v) for v in splits.values())
        done = 0

        for split, items in splits.items():
            names = []
            for im in items:
                if self._cancelled:
                    return
                src = Path(im.path)
                self._copy_image(src, img_dir)
                anns = self._annotations(im, class_map)
                root = ET.Element("annotation")
                ET.SubElement(root, "folder").text = "JPEGImages"
                ET.SubElement(root, "filename").text = src.name
                ET.SubElement(root, "path").text = str(img_dir / src.name)
                source = ET.SubElement(root, "source")
                ET.SubElement(source, "database").text = "AutoLabel Studio AI"
                size = ET.SubElement(root, "size")
                ET.SubElement(size, "width").text = str(im.width)
                ET.SubElement(size, "height").text = str(im.height)
                ET.SubElement(size, "depth").text = "3"
                ET.SubElement(root, "segmented").text = (
                    "1" if any(len(a.polygon) >= 6 for a in anns) else "0"
                )

                for a in anns:
                    obj = ET.SubElement(root, "object")
                    ET.SubElement(obj, "name").text = class_map[a.class_id]
                    ET.SubElement(obj, "pose").text = "Unspecified"
                    ET.SubElement(obj, "truncated").text = "0"
                    ET.SubElement(obj, "difficult").text = "0"
                    ET.SubElement(obj, "confidence").text = f"{a.confidence:.4f}"
                    bnd = ET.SubElement(obj, "bndbox")
                    x1, y1, x2, y2 = a.bbox
                    ET.SubElement(bnd, "xmin").text = str(int(round(x1)))
                    ET.SubElement(bnd, "ymin").text = str(int(round(y1)))
                    ET.SubElement(bnd, "xmax").text = str(int(round(x2)))
                    ET.SubElement(bnd, "ymax").text = str(int(round(y2)))
                    if len(a.polygon) >= 6:
                        poly = ET.SubElement(obj, "polygon")
                        for i in range(0, len(a.polygon) - 1, 2):
                            ET.SubElement(poly, f"x{i // 2 + 1}").text = f"{a.polygon[i]:.1f}"
                            ET.SubElement(poly, f"y{i // 2 + 1}").text = f"{a.polygon[i + 1]:.1f}"
                    result.n_objects += 1

                _indent(root)
                ET.ElementTree(root).write(
                    xml_dir / f"{src.stem}.xml", encoding="utf-8", xml_declaration=True
                )
                names.append(src.stem)
                result.n_images += 1
                done += 1
                if progress_cb and done % 10 == 0:
                    progress_cb(done, total, f"{split}: {src.name}")
            (set_dir / f"{split}.txt").write_text("\n".join(names), encoding="utf-8")
        (out_dir / "classes.txt").write_text("\n".join(c.name for c in classes), encoding="utf-8")
        if progress_cb:
            progress_cb(total, total, "Hoan tat")

    # =========================================================== MASK ======
    def _export_mask(self, out_dir, splits, classes, result, progress_cb, _log):
        import cv2

        class_map = {c.id: i + 1 for i, c in enumerate(classes)}  # 0 = background
        total = sum(len(v) for v in splits.values())
        done = 0

        for split, items in splits.items():
            img_dir = ensure_dir(out_dir / "images" / split)
            mask_dir = ensure_dir(out_dir / "masks" / split)
            color_dir = ensure_dir(out_dir / "masks_color" / split)
            for im in items:
                if self._cancelled:
                    return
                src = Path(im.path)
                self._copy_image(src, img_dir)
                h, w = max(1, im.height), max(1, im.width)
                mask = np.zeros((h, w), dtype=np.uint8)
                color = np.zeros((h, w, 3), dtype=np.uint8)
                for a in self._annotations(im, class_map):
                    idx = class_map[a.class_id]
                    pts = np.asarray(a.effective_points(), dtype=np.int32).reshape(-1, 2)
                    if len(pts) < 3:
                        continue
                    cv2.fillPoly(mask, [pts], int(idx))
                    cd = self.repo.class_by_id(a.class_id)
                    rgb = _hex_to_bgr(cd.color if cd else "#FFFFFF")
                    cv2.fillPoly(color, [pts], rgb)
                    result.n_objects += 1
                cv2.imwrite(str(mask_dir / f"{src.stem}.png"), mask)
                cv2.imwrite(str(color_dir / f"{src.stem}.png"), color)
                result.n_images += 1
                done += 1
                if progress_cb and done % 10 == 0:
                    progress_cb(done, total, f"{split}: {src.name}")

        lines = ["0 background #000000"]
        for i, c in enumerate(classes, start=1):
            lines.append(f"{i} {c.name} {c.color}")
        (out_dir / "classes.txt").write_text("\n".join(lines), encoding="utf-8")
        _log("Mask duoc luu dang PNG 8-bit (gia tri pixel = chi so class).")
        if progress_cb:
            progress_cb(total, total, "Hoan tat")


# ================================================================ HELPERS ===
def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _obb_corners(ann) -> list[tuple[float, float]]:
    """4 dinh cua hop xoay. Polygon bat ky -> hop xoay nho nhat bao quanh."""
    pts = ann.points()
    if len(pts) == 4:
        return pts
    if len(pts) >= 3:
        try:
            import cv2

            rect = cv2.minAreaRect(np.asarray(pts, dtype=np.float32))
            return [(float(x), float(y)) for x, y in cv2.boxPoints(rect)]
        except Exception:
            pass
    x1, y1, x2, y2 = ann.bbox
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _keypoints(ann) -> tuple[list[tuple[float, float, float]], int]:
    """Tra ve (danh sach keypoint, so chieu 2 hoac 3)."""
    kp = ann.keypoints or []
    if not kp:
        return [], 3
    dim = 3 if len(kp) % 3 == 0 else 2
    out = []
    for i in range(0, len(kp) - dim + 1, dim):
        if dim == 3:
            out.append((kp[i], kp[i + 1], kp[i + 2]))
        else:
            out.append((kp[i], kp[i + 1], 2.0))
    return out, dim


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (255, 255, 255)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


def _indent(elem, level: int = 0) -> None:
    pad = "\n" + "  " * level
    if len(elem):
        if not (elem.text or "").strip():
            elem.text = pad + "  "
        for child in elem:
            _indent(child, level + 1)
        if not (child.tail or "").strip():
            child.tail = pad
    if level and not (elem.tail or "").strip():
        elem.tail = pad


def build_training_yaml(
    repo: ProjectRepository,
    out_dir: Path,
    val_split: float = 0.2,
    test_split: float = 0.0,
    seg: bool = True,
    only_approved: bool = False,
    progress_cb=None,
    log_cb=None,
) -> str:
    """Tien ich: dung nhanh dataset YOLO tu project de train ngay trong app."""
    cfg = ExportConfig(
        fmt="yolo_seg" if seg else "yolo_det",
        output_dir=str(out_dir.parent),
        dataset_name=out_dir.name,
        val_split=val_split,
        test_split=test_split,
        train_split=max(0.0, 1.0 - val_split - test_split),
        only_approved=only_approved,
        copy_images=True,
        write_yaml=True,
    )
    res = DatasetExporter(repo, cfg).run(progress_cb=progress_cb, log_cb=log_cb)
    return res.yaml_path
