# Tài liệu vận hành — AutoLabel Studio AI

> Phiên bản 1.0 · Cập nhật 2026-08 · Dành cho người cài đặt, sử dụng hàng ngày và xử lý sự cố.

## 1. Yêu cầu hệ thống

| Hạng mục | Tối thiểu | Khuyến nghị |
| --- | --- | --- |
| HĐH | Windows 10 / Ubuntu 22.04 | Windows 11 |
| Python | 3.10 | 3.12 |
| RAM | 8 GB | 16 GB |
| GPU | Không bắt buộc (fallback CPU) | NVIDIA ≥ 4GB VRAM, driver CUDA 12.x |
| Ổ đĩa | 5 GB trống | SSD (project video nhiều frame đọc/ghi liên tục) |

## 2. Cài đặt

```bash
git clone https://github.com/TruongTanNghia/Auto-Labeling.git
cd Auto-Labeling
python -m venv .venv && .venv\Scripts\activate    # Linux: source .venv/bin/activate

# Máy có GPU NVIDIA — cài torch CUDA TRƯỚC (thay cu124 theo phiên bản CUDA):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
# Máy không GPU:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

> ⚠️ App đặt `YOLO_AUTOINSTALL=false` để Ultralytics không tự `pip install` đè môi trường — đây là nguyên nhân phổ biến nhất khiến bản torch CUDA bị thay bằng bản CPU. **Không tự bật lại biến này.**

**Chạy:** `python main.py` (hoặc `run.bat` trên Windows). Mở sẵn project: `python main.py "duong\dan\project.alsdb"`.

**Kiểm tra GPU hoạt động**: Dashboard → thẻ "Hệ thống" phải hiện tên GPU + VRAM. Nếu hiện "CPU" trên máy có GPU → xem mục 6.1.

## 3. Dữ liệu nằm ở đâu

| Đường dẫn | Nội dung | Được xóa không? |
| --- | --- | --- |
| `<thư mục project>\project.alsdb` (+ `-wal`, `-shm`) | Toàn bộ nhãn, class, lịch sử | **KHÔNG** — mất là mất project |
| `<project>\frames\`, `images\` | Ảnh nguồn | Không, trừ khi dọn qua Dataset Manager |
| `<project>\exports\` | Dataset đã xuất | Được — sinh lại bằng Export |
| `<project>\runs\` | Kết quả train (`best.pt`) | Cân nhắc — giữ `best.pt` |
| `<project>\backups\` | Sao lưu tự động (10 bản gần nhất) | Được, nhưng nên giữ |
| `%LOCALAPPDATA%\AutoLabelStudioAI\settings.json` | Cấu hình app | Xóa = về mặc định |
| `%LOCALAPPDATA%\AutoLabelStudioAI\logs\` | Log chẩn đoán | Được |
| `%LOCALAPPDATA%\AutoLabelStudioAI\weights\` | Trọng số tải tự động | Được — tải lại khi cần |

### 3.1. Sao lưu & phục hồi

- **Tự động**: autosave mỗi 5 phút (đổi trong Settings) kèm backup xoay vòng vào `<project>\backups\`.
- **Thủ công trước thao tác rủi ro** (dọn dẹp hàng loạt, đổi cấu trúc class): copy nguyên thư mục project khi **app đã đóng** (để file `-wal` được gộp về `.alsdb`).
- **Phục hồi**: đóng app → chép file backup đè lên `project.alsdb` → mở lại. File backup đặt tên theo thời điểm.

## 4. Vận hành hàng ngày — quy trình chuẩn

1. **Dashboard** → tạo/mở project (task chọn đúng ngay từ đầu: detect / segment / obb / pose).
2. **Import** → kéo-thả video hoặc thư mục ảnh. Dataset có nhãn sẵn (YOLO/COCO) nhập ở mục "Nhập dataset có nhãn".
3. **Frame Extractor** → chọn chế độ (video giám sát tĩnh: Adaptive Motion; phim nhiều cảnh: Scene Detection), bật lọc trùng + mờ. Xem "ước lượng số ảnh" trước khi chạy.
4. **Auto Label** → nạp model → đặt confidence (0.35–0.5), bật SAHI nếu ảnh > 2000px hoặc đối tượng nhỏ, bật tracking nếu là chuỗi frame video → chạy.
5. **Editor** → lọc "Cần xem lại" → sửa → `Enter` duyệt từng ảnh.
6. **Dataset Manager** → dọn trùng/mờ, kiểm tra cân bằng class trước khi xuất.
7. **Statistics & Export** → xuất định dạng cần (lọc "chỉ ảnh đã duyệt" cho dataset sạch).
8. **Train** → train thử nhanh (10–20 epoch) đánh giá chất lượng nhãn trước khi train dài.

**Mẹo hiệu năng:**

- GPU 4GB: `imgsz=640`, batch ≤ 8 khi train; bật `half` khi suy luận.
- SAHI chậm hơn nhiều lần inference thường — chỉ bật cho ảnh lớn thật sự.
- Tracking chỉ hữu ích khi frame dày (Every Frame / N nhỏ); frame thưa làm tracker mất dấu.

## 5. CI/CD & phát hành

| Việc | Cách làm |
| --- | --- |
| CI mỗi push/PR | GitHub Actions [ci.yml](../.github/workflows/ci.yml): ruff (lint + format) → pytest + coverage trên Ubuntu/Windows × Python 3.10/3.12. PR đỏ CI thì không merge. |
| Test E2E model thật | Chạy tay trước phát hành: `ALS_E2E=1 pytest tests/test_autolabel_flow.py -k e2e` (cần mạng tải yolo11n.pt lần đầu) |
| Phát hành | Cập nhật version → `git tag v1.x.y && git push --tags` → workflow [release.yml](../.github/workflows/release.yml) tự build .exe (PyInstaller) và đính vào GitHub Release |
| Hotfix | Nhánh `fix/...` từ `main` → PR → CI xanh → merge → tag bản vá |

## 6. Xử lý sự cố (Troubleshooting)

### 6.1. App báo CPU dù máy có GPU NVIDIA

1. Kiểm tra: `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
2. Nếu in `2.x.x+cpu False` → torch bản CPU đã đè bản CUDA. Cài lại:
   `pip install --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cu124`
3. Nguyên nhân thường gặp: một `pip install` khác kéo torch từ PyPI. Sau khi cài lại, không chạy `pip install -U ultralytics` mà không có `--no-deps`.

### 6.2. Nạp model báo lỗi / file trọng số hỏng

- Trọng số chuẩn tải dở (mất mạng): app tự xóa file hỏng **trong thư mục weights** và tải lại một lần. Nếu vẫn lỗi: xóa file trong `%LOCALAPPDATA%\AutoLabelStudioAI\weights\` rồi nạp lại.
- Model custom (`.pt` do bạn train): app **không bao giờ tự xóa** file của bạn. Lỗi nạp thường do lệch phiên bản ultralytics — thử `pip install -U ultralytics --no-deps`.

### 6.3. Auto label chạy nhưng ra rất ít / thừa đối tượng

- Ít: hạ confidence (0.25–0.35); đối tượng nhỏ trên ảnh lớn → bật SAHI; kiểm tra đúng task (model detect không ra polygon).
- Thừa/trùng: nâng confidence, nâng IoU NMS; kiểm tra `min_area_px`.
- Sau một phiên tracking mà detect thường ra ít bất thường → cập nhật bản mới (đã vá BUG-01, xem tài liệu kiểm thử).

### 6.4. App khởi động chậm / đứng khi nạp model lần đầu

Lần đầu nạp mỗi model phải tải trọng số (5MB–400MB tùy model) — xem log tiến độ ở panel log. Plugin Florence-2/G-DINO tải vài trăm MB từ Hugging Face.

### 6.5. Lỗi "database is locked"

- Chỉ mở **một** cửa sổ app trên một project.
- File project nằm trên ổ mạng/Google Drive sync → chuyển về ổ cục bộ (WAL không an toàn trên network share).

### 6.6. Giao diện đứng khi thao tác nặng

Không được xảy ra theo thiết kế (mọi việc nặng ở worker). Nếu gặp: ghi lại thao tác + log tại `%LOCALAPPDATA%\AutoLabelStudioAI\logs\` và mở issue theo mẫu 🐛.

### 6.7. Thu thập log để báo lỗi

1. Tái hiện lỗi.
2. Lấy file log mới nhất trong `%LOCALAPPDATA%\AutoLabelStudioAI\logs\`.
3. Mở issue kèm: log, HĐH, phiên bản Python/torch/ultralytics, GPU, các bước tái hiện.

## 7. Bảo trì định kỳ

| Chu kỳ | Việc |
| --- | --- |
| Hàng tuần (dự án đang chạy) | Dataset Manager → dọn ảnh trùng/mờ; kiểm tra dung lượng `backups/` |
| Trước mỗi đợt gán nhãn lớn | Backup thủ công project; kiểm tra ổ đĩa còn ≥ 2× dung lượng video nguồn |
| Mỗi tháng | Xem `logs/` có lỗi lặp lại; cập nhật dependency trên nhánh riêng và chạy full test trước khi merge |
| Khi nâng ultralytics | Chạy `ALS_E2E=1 pytest -k e2e` — API tracker/predict của Ultralytics từng đổi hành vi giữa các bản |
