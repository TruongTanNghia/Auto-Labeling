# AutoLabel Studio AI

**Desktop Application to Automatically Build Computer Vision Datasets from Videos using AI.**

Python + PySide6 · Dark Fluent UI · YOLOv8 / YOLO11 / YOLO12 · MVC Architecture + Multithreading.

---

## Features

### 1. Import

- Load **videos** (mp4, avi, mov, mkv, webm…) or **image folders**.
- Drag & drop files/folders directly into the window.
- Video preview (sample frame, resolution, FPS, duration, codec, size).
- Option to copy images into the project directory.

### 2. Frame Extractor — 5 Extraction Modes

| Mode | Description |
| --- | --- |
| Every Frame | Extract all frames from video |
| Every N Frames | Extract 1 frame every N frames |
| Every N Seconds | Extract 1 frame every N seconds |
| Adaptive Motion | Extract only when significant motion occurs (frame difference) |
| Scene Detection | Extract when scene changes (HSV histogram comparison) |

Additional capabilities:

- **Deduplication**: Perceptual hash (64-bit pHash based on DCT) + **SSIM** verification.
- **Blur Detection**: Variance of Laplacian with configurable threshold.
- **Exposure Filtering**: Mean brightness thresholding.
- Output frame limit, time range cropping, long edge resizing, JPG/PNG quality settings.
- Output image estimation **before running**.

### 3. Auto Label

- Supports **YOLOv8 / YOLO11 / YOLO12** for 4 tasks: **Detection, Segmentation, OBB, Pose**.
- **Custom models**: `.pt`, `.onnx`, `.engine`, `.torchscript`.
- Automatic **CUDA** acceleration with CPU fallback.
- Generates **bounding boxes** or **polygon masks** with confidence overlays.
- Low-confidence predictions marked as **Need Review** or **Low Confidence**.
- Polygon simplification (Douglas–Peucker), minimum area filtering, overwrite or keep existing labels.
- Integrates **refinement plugins** (SAM2 / FastSAM) to convert coarse boxes into sharp masks.

### 4. Annotation Editor

Tools: **Select · Polygon · Bounding Box · Brush · Eraser · Split · Pan**

- **Brush / Eraser** operates on true geometry (Shapely): union additions, cut deletions.
  Erasing inside polygons creates **holes** preserved via keyhole topology for YOLO export.
- **Split**: Draw a cut line to split a polygon into multiple shapes.
- **Merge**: Combine multiple selected annotations.
- **Simplify**: Reduce vertex count of polygons.
- Drag vertices to reshape, double click edges to insert vertices.
- **Undo / Redo** (60 steps), **Zoom / Pan**, **Navigator** (minimap with viewport rectangle).
- Batch class and confidence modification, review/approve status marking.
- Keyboard navigation: `A` / `D` for previous/next, `Enter` to approve & move next.

### 5. Dataset Manager

- Lazy-loaded thumbnail gallery (smooth scrolling on background threads).
- Filtering: All · Labeled · Unlabeled · Need Review · Approved · Duplicates · Blurry.
- Statistics: total images, labeled count, object count, class breakdown, duplicate count.
- Class distribution charts + detailed image table (objects, masks, average area, coverage).
- Batch actions: approve, mark review, delete (with optional file deletion).
- **Cleanup**: purge duplicate / blurry / unlabeled images, recalculate object counts.

### 6. Statistics & Export

Six analytical sections: Overview · Class Distribution · Object Sizes · Position Heatmap · Image Quality · Export Dataset.

- Bar charts, donut charts, histograms, and **object position heatmap**.
- **Export to 7 Formats**: YOLO Segmentation · YOLO Detection · **YOLO OBB** · **YOLO Pose** · COCO JSON (with keypoints) · Pascal VOC XML · PNG Mask.
- Train/Val/Test split with random seed, filter by approval status / duplicates / blur / min confidence.
- Auto-generates `data.yaml` and `classes.txt`.

### 7. Train Model

- Retrain Ultralytics YOLO directly inside the application using project dataset.
- Training setup: epochs, batch size, imgsz, optimizer, learning rate, patience, workers, device, data augmentation.
- **Real-time Monitoring**: progress ring, mAP50 / mAP50-95 / Precision / Recall charts, loss curves, logs, estimated remaining time.
- Saves best weights (`best.pt`) for immediate inference loading.

### 8. Settings

General · Model · Inference · Annotation · Plugins · Shortcuts · About.

- Multi-language support (English & Vietnamese).
- Custom accent colors, project directory, autosave interval, default export format, threshold settings.

---

## Installation

```bash
pip install -r requirements.txt
```

For **GPU Acceleration**, install PyTorch with CUDA:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

## Running the Application

```bash
python main.py
```

Or open directly with a project:

```bash
python main.py "path/to/project.alsdb"
```

## Running Tests

```bash
python tests/test_pipeline.py
```

---

## License & Notes

Ultralytics YOLO models are released under **AGPL-3.0**. Please review licensing terms before commercial usage.
