# AutoLabel Studio AI

**Phần mềm Desktop tự động tạo dataset Computer Vision từ video bằng AI.**

Python + PySide6 · Dark Fluent UI · YOLOv8 / YOLO11 / YOLO12 · Kiến trúc MVC + đa luồng.

---

## Tính năng

### 1. Import

- Nạp **video** (mp4, avi, mov, mkv, webm…) hoặc **thư mục ảnh** có sẵn.
- Kéo–thả file/thư mục trực tiếp vào cửa sổ.
- Xem trước video (frame mẫu, độ phân giải, FPS, thời lượng, codec, dung lượng).
- Tuỳ chọn sao chép ảnh vào thư mục project.

### 2. Frame Extractor — 5 chế độ cắt frame

| Chế độ | Mô tả |
| --- | --- |
| Every Frame | Lấy toàn bộ frame |
| Every N Frames | Lấy 1 frame sau mỗi N frame |
| Every N Seconds | Lấy 1 frame sau mỗi N giây |
| Adaptive Motion | Chỉ lấy khi có chuyển động đáng kể (so sánh frame-diff) |
| Scene Detection | Lấy khi đổi cảnh (so sánh histogram HSV) |

Kèm theo:

- **Khử trùng lặp**: perceptual hash (pHash 64-bit dựa trên DCT) → xác nhận lại bằng **SSIM**.
- **Phát hiện ảnh mờ**: variance of Laplacian, có ngưỡng tuỳ chỉnh.
- **Phát hiện thiếu sáng / cháy sáng**: độ sáng trung bình.
- Giới hạn số ảnh, cắt theo khoảng thời gian, thu nhỏ cạnh dài, chọn JPG/PNG và chất lượng.
- Ước lượng số ảnh đầu ra **trước khi chạy**.

### 3. Auto Label

- Hỗ trợ **YOLOv8 / YOLO11 / YOLO12** với 4 nhiệm vụ: **Detection, Segmentation, OBB, Pose**.
- **Custom model**: `.pt`, `.onnx`, `.engine`, `.torchscript`.
- Tự động dùng **CUDA** nếu có, **fallback CPU** nếu không.
- Sinh **bounding box** hoặc **polygon mask**, hiển thị confidence trên ảnh.
- Dự đoán dưới ngưỡng được đánh dấu **Need Review**; dưới ngưỡng thấp hơn nữa là **Low Confidence**.
- Đơn giản hoá polygon (Douglas–Peucker), lọc theo diện tích tối thiểu, ghi đè hoặc giữ nhãn cũ.
- Có thể ghép **plugin tinh chỉnh** (SAM2 / FastSAM) để biến box thành mask sắc nét.

### 4. Annotation Editor

Công cụ: **Select · Polygon · Bounding Box · Brush · Eraser · Split · Pan**

- **Brush / Eraser** hoạt động trên hình học thật (Shapely): tô thêm hợp vùng, xoá cắt vùng.
  Xoá ở giữa tạo **lỗ**, được lưu bằng kỹ thuật *keyhole* để vẫn xuất được ra định dạng YOLO.
- **Split**: kẻ một đường cắt để tách một vùng thành nhiều vùng.
- **Merge**: gộp nhiều vùng đang chọn.
- **Simplify**: giảm số đỉnh polygon.
- Kéo đỉnh để chỉnh hình, nháy đúp lên cạnh để thêm đỉnh mới.
- **Undo / Redo** (60 bước), **Zoom / Pan**, **Navigator** (minimap có khung viewport).
- Đổi class và confidence cho nhiều đối tượng cùng lúc, đánh dấu review/duyệt.
- Điều hướng ảnh bằng `A` / `D`, duyệt và sang ảnh kế bằng `Enter`.

### 5. Dataset Manager

- Thư viện thumbnail (nạp lazy ở luồng nền, không giật khi cuộn).
- Lọc theo: Tất cả · Đã gán nhãn · Chưa gán nhãn · Cần review · Đã duyệt · Trùng · Mờ.
- Thống kê nhanh: tổng ảnh, đã gán nhãn, đối tượng, số class, ảnh trùng.
- Biểu đồ đối tượng / ảnh theo class + bảng chi tiết (ảnh, đối tượng, mask, diện tích TB, coverage).
- Thao tác hàng loạt: duyệt, đánh dấu review, xoá (tuỳ chọn xoá cả file).
- **Dọn dẹp**: xoá ảnh trùng / ảnh mờ / ảnh chưa gán nhãn, gỡ ảnh mất file,
  tính lại số đối tượng, sao lưu.

### 6. Statistics & Export

Sáu mục: Tổng quan · Phân bố class · Kích thước object · **Bản đồ nhiệt** ·
Chất lượng ảnh · Xuất dataset.

- Biểu đồ cột, cột ngang, tròn/donut, histogram, đường và **heatmap mật độ vị trí đối tượng**.
- Phân bố confidence, phân bố độ nét, phân bố độ sáng, số đối tượng trên mỗi ảnh.
- **Xuất 7 định dạng**: YOLO Segmentation · YOLO Detection · **YOLO OBB** · **YOLO Pose** ·
  COCO JSON (kèm `keypoints`) · Pascal VOC XML · PNG Mask (kèm mask màu để xem bằng mắt).
  OBB tự quy về hộp xoay nhỏ nhất bao quanh polygon; Pose ghi kèm `kpt_shape` vào `data.yaml`.
- Chia train/val/test theo tỉ lệ + seed, lọc theo trạng thái duyệt / trùng / mờ /
  confidence tối thiểu, tự sinh `data.yaml` và `classes.txt`.

### 7. Train Model

- Train lại Ultralytics ngay trong ứng dụng, **tự dựng dataset từ project**
  (không cần export thủ công).
- Cấu hình: epochs, batch, imgsz, optimizer, learning rate, patience, workers,
  device, augmentation, cache.
- Theo dõi **thời gian thực**: vòng tiến độ, biểu đồ mAP50 / mAP50-95 / Precision / Recall,
  biểu đồ loss, log, thời gian đã chạy và ước tính còn lại.
- Lưu lịch sử các lần train; trọng số `best.pt` được ghi lại để nạp dùng ngay.

### 8. Settings

Chung · Model · Suy luận · Annotation · Plugin · Phím tắt · Giới thiệu.

Đổi màu nhấn, thư mục project, autosave, định dạng xuất mặc định, mọi ngưỡng của pipeline.

---

## Kiến trúc

```text
main.py                     Điểm khởi chạy
app/
├── constants.py            Hằng số, bảng màu, phím tắt
├── config.py               Cấu hình JSON (dot-path, có giá trị mặc định)
├── models/                 ── MODEL ──────────────────────────
│   ├── database.py         SQLite (WAL) an toàn đa luồng
│   ├── entities.py         ClassDef, ImageRecord, Annotation, ProjectInfo
│   └── repository.py       Toàn bộ nghiệp vụ truy xuất dữ liệu + thống kê
├── core/                   ── NGHIỆP VỤ ─────────────────────
│   ├── frame_extractor.py  5 chế độ cắt frame + lọc chất lượng
│   ├── image_quality.py    pHash, dHash, SSIM, blur, brightness, DuplicateFilter
│   ├── inference.py        YoloEngine (detect/segment/obb/pose), thiết bị, mask↔polygon
│   ├── exporters.py        YOLO / COCO / VOC / Mask
│   └── trainer.py          ModelTrainer + callback metric theo epoch
├── plugins/                ── PLUGIN ─────────────────────────
│   ├── base.py             AnnotatorPlugin, PluginContext, registry tự khám phá
│   └── builtin/            SAM Refiner · SAM 3 Concept · FastSAM · G-DINO · Florence-2
├── workers/                ── ĐA LUỒNG ───────────────────────
│   ├── base.py             BaseWorker (progress / log / stage / cancel)
│   ├── extract_worker.py   ExtractWorker, ScanFolderWorker
│   ├── autolabel_worker.py ModelLoadWorker, AutoLabelWorker, SingleImageInferWorker
│   ├── export_worker.py    ExportWorker
│   └── train_worker.py     TrainWorker
├── controllers/            ── CONTROLLER ─────────────────────
│   └── app_controller.py   Vòng đời project, điều phối worker, autosave, tín hiệu
└── views/                  ── VIEW ───────────────────────────
    ├── main_window.py      Cửa sổ frameless, title bar, điều hướng
    ├── sidebar.py
    ├── pages/              9 trang
    └── widgets/            canvas, charts, image_list, common
```

**Không tác vụ nặng nào chạy trên luồng giao diện.** Cắt frame, suy luận, xuất dataset
và train đều nằm trong `QThread` riêng, có tiến độ, log trực tiếp và nút huỷ.

---

## Cài đặt & Sử dụng

### Cách 1: Sử dụng file thực thi .exe (Dành cho người dùng cuối)

1. Truy cập trang **Releases** trên GitHub và tải file `AutoLabelStudioAI-windows-x64.zip`.
2. Giải nén file zip vào một thư mục bất kỳ.
3. Nháy đúp file `AutoLabelStudioAI.exe` để chạy ứng dụng ngay (không cần cài đặt Python).

> **Ghi chú về GPU / PyTorch**: Bản đóng gói `.exe` đính kèm PyTorch bản CPU để đảm bảo tương thích và chạy ngay trên mọi máy Windows sạch. Nếu bạn muốn sử dụng GPU CUDA để tăng tốc suy luận và huấn luyện, hãy sử dụng **Cách 2** với môi trường Python và cài đặt PyTorch CUDA.

### Cách 2: Chạy từ mã nguồn Python

```bash
pip install -r requirements.txt
```

Muốn dùng **GPU**, cài torch bản CUDA trước (thay `cu124` bằng phiên bản CUDA của bạn):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

> Ứng dụng đặt `YOLO_AUTOINSTALL=false` để Ultralytics **không** tự `pip install` đè lên
> môi trường của bạn — đây là nguyên nhân phổ biến khiến bản torch CUDA bị thay bằng bản CPU.

## Chạy từ mã nguồn

```bash
python main.py
```

hoặc nháy đúp `run.bat` (Windows).

Mở sẵn một project:

```bash
python main.py "duong/dan/project.alsdb"
```

## Kiểm thử

Chạy toàn bộ bộ test bằng `pytest`:

```bash
pytest -v --cov=app
```

Hoặc chạy một module test đơn lẻ:

```bash
pytest tests/test_exporters.py
```

Chạy không cần màn hình và không cần GPU. Kiểm tra: SQLite, 5 chế độ cắt frame,
pHash/SSIM/blur/khử trùng lặp, canvas (polygon · brush · eraser · split · merge · undo),
xuất đủ 7 định dạng (kiểm tra cả số cột nhãn của OBB/Pose và `kpt_shape`),
và vòng đời plugin (kể cả điểm tích hợp trong `AutoLabelWorker`).

### Giới hạn đã biết

- Giao diện chỉ có **tiếng Việt** ở bản 1.0 (ô chọn ngôn ngữ bị khoá thay vì hứa suông).
- **SAM Refiner** và **FastSAM** đã chạy thử với trọng số thật (box thô → mask bám vành).
  **Grounding DINO**, **Florence-2** và **SAM 3 Concept** mới kiểm tra vòng đời, chưa chạy
  với trọng số thật; lần đầu dùng sẽ tải model vài trăm MB.
- Tham số riêng của từng plugin (ví dụ `model_id`, `mode`) hiện chỉnh bằng code
  (`default_config()`), chưa có ô nhập trong Settings.

---

## Quy trình sử dụng

> **Mọi dữ liệu đều nằm trong một project.** Lần đầu chạy, ứng dụng mở ở Dashboard —
> bấm **Tạo project mới**. Những lần sau nó tự mở lại project gần nhất.
> Nếu vào thẳng một trang cần project, màn hình sẽ có sẵn hai nút
> *Tạo project mới* và *Mở project có sẵn*.

1. **Dashboard** → *Tạo project mới* (mỗi project là một thư mục riêng).
2. **Import** → thêm video hoặc thư mục ảnh — hoặc **kéo thả thẳng vào cửa sổ**,
   ứng dụng tự chuyển sang trang Import.
   - Ảnh → bấm **Nạp ảnh vào project** là xong.
   - Video → **không nạp thẳng được**, phải cắt thành ảnh trước; bấm
     **Cắt frame từ video** để sang bước 3. Trang Import luôn ghi rõ bước kế tiếp.
3. **Frame Extractor** → chọn chế độ, bật lọc trùng/mờ → *Bắt đầu cắt frame*.
4. **Auto Label** → chọn nhiệm vụ + trọng số → *Nạp model* → *Bắt đầu gán nhãn*.
5. **Annotation Editor** → lọc “Cần xem lại”, sửa bằng Cọ vẽ / Tẩy / Cắt đôi / Gộp,
   `Enter` để duyệt và sang ảnh kế.
6. **Dataset Manager** → dọn ảnh trùng/mờ, kiểm tra cân bằng lớp.
7. **Statistics & Export** → xem thống kê → xuất YOLO / COCO / VOC / Mask.
8. **Train Model** → huấn luyện lại ngay trên dataset vừa tạo.

---

## Phím tắt

| Phím | Chức năng |
| --- | --- |
| `Ctrl+1` … `Ctrl+9` | Chuyển trang |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | Tạo / mở / lưu project |
| `A` / `D` | Ảnh trước / ảnh sau |
| `V` `W` `B` `E` `S` | Select · Polygon · Brush · Eraser · Split |
| `M` | Merge các vùng đang chọn |
| `1` … `9` | Gán class cho đối tượng đang chọn |
| `Enter` | Duyệt ảnh và sang ảnh kế |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl` `+` / `-` / `0` | Zoom in / out / fit |
| `Space` (giữ) | Pan ảnh |
| `Delete` | Xoá đối tượng đang chọn |
| `Esc` | Huỷ thao tác đang vẽ |
| `F5` | Bắt đầu Auto Label |
| `F11` | Toàn màn hình |

Alt + cuộn chuột khi dùng Brush/Eraser để đổi cỡ cọ.

---

## Plugin

Plugin mở rộng chất lượng auto annotation. Năm plugin đi kèm:

| Plugin | Loại | Yêu cầu |
| --- | --- | --- |
| **SAM Refiner (3 / 2)** | Tinh chỉnh box → mask sắc nét | `ultralytics`, `torch` |
| **SAM 3 Concept** | Sinh nhãn theo mô tả chữ (open-vocabulary) | `ultralytics ≥ 8.3.237` + `sam3.pt` |
| **FastSAM** | Tinh chỉnh hoặc sinh mask toàn ảnh | `ultralytics`, `torch` |
| **Grounding DINO** | Zero-shot detection theo prompt văn bản | `transformers`, `torch` |
| **Florence-2** | VLM đa nhiệm (OD, region caption, referring segmentation) | `transformers`, `torch` |

### Về phiên bản SAM

`SAM Refiner` **tự chọn bản tốt nhất đang có** theo thứ tự
`sam3.pt` → `sam2_b.pt` → `sam_b.pt`, dựa trên phiên bản `ultralytics` cài trong máy
và trọng số đã tải sẵn. Không cần chỉnh gì — nâng cấp `ultralytics` là plugin tự dùng bản mới.

SAM 3 (Meta, 19/11/2025) cần `ultralytics ≥ 8.3.237` và file `sam3.pt` **tải thủ công**
từ Hugging Face (Meta yêu cầu xin quyền, không tải tự động được). Khi chưa đủ điều kiện,
Settings → Plugin hiển thị đúng lý do và lệnh cần chạy, còn SAM 2 vẫn hoạt động bình thường.

### Viết plugin của bạn

Tạo file `.py` trong `%LOCALAPPDATA%\AutoLabelStudioAI\plugins\`:

```python
from app.plugins.base import AnnotatorPlugin, PluginInfo, PluginContext
from app.core.inference import Detection


class MyPlugin(AnnotatorPlugin):
    info = PluginInfo(
        key="my_plugin",
        name="Plugin cua toi",
        kind="refine",
        description="Mo ta ngan",
        requires=["numpy"],
    )

    def annotate(self, ctx: PluginContext) -> list[Detection]:
        # ctx.image (ndarray BGR), ctx.image_path, ctx.detections, ctx.prompt
        return ctx.detections
```

Ứng dụng tự khám phá plugin khi khởi động (*Settings → Plugin → Quét lại plugin*).

---

## Lưu trữ

- Mỗi project là một thư mục chứa `project.alsdb` (SQLite WAL) và các thư mục
  `frames/`, `images/`, `exports/`, `runs/`, `backups/`.
- **Autosave** theo chu kỳ (mặc định 5 phút) kèm sao lưu xoay vòng, giữ 10 bản gần nhất.
- Lịch sử thao tác được ghi lại và hiển thị ở Dashboard.

Đường dẫn hệ thống (Windows): `%LOCALAPPDATA%\AutoLabelStudioAI\`
— `settings.json`, `logs/`, `weights/`, `plugins/`, `cache/`.

---

## Ghi chú giấy phép

Mô hình YOLO của Ultralytics phát hành theo **AGPL-3.0**. Hãy kiểm tra điều khoản
trước khi sử dụng cho mục đích thương mại.
