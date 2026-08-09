# Đóng góp cho AutoLabel Studio AI

Cảm ơn bạn quan tâm đến dự án! Mọi đóng góp — báo lỗi, ý tưởng, tài liệu, code — đều được hoan nghênh.

## Bắt đầu

```bash
git clone https://github.com/TruongTanNghia/Auto-Labeling.git
cd Auto-Labeling

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Torch bản CPU là đủ để phát triển (bản CUDA cài riêng nếu cần GPU)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt

python main.py
```

## Chạy kiểm thử

```bash
pytest -v --cov=app
```

Hoặc chạy một file test đơn lẻ:

```bash
pytest tests/test_exporters.py
```

Bộ test chạy **offscreen** (không cần màn hình) và **không cần GPU**. CI sẽ tự động chạy `pytest` và đo coverage trên Ubuntu + Windows với Python 3.10 và 3.12 — hãy đảm bảo các test đều qua trước khi mở PR.

## Quy trình đóng góp

1. Tìm một issue (ưu tiên nhãn `good first issue` / `help wanted`) hoặc mở issue mới để thảo luận trước khi làm tính năng lớn.
2. Fork repo và tạo nhánh từ `main`: `git checkout -b feat/ten-tinh-nang` hoặc `fix/ten-loi`.
3. Code, chạy test, commit với thông điệp rõ ràng (tiếng Việt hoặc tiếng Anh đều được).
4. Mở Pull Request theo mẫu có sẵn, liên kết issue bằng `Closes #<số>`.

## Quy tắc code của dự án

- **Kiến trúc MVC**: nghiệp vụ nằm trong `app/core/`, dữ liệu trong `app/models/`, giao diện trong `app/views/`, điều phối trong `app/controllers/`.
- **Không chạy tác vụ nặng trên luồng giao diện.** Mọi việc tốn thời gian (I/O, inference, export…) phải nằm trong worker (`app/workers/`, kế thừa `BaseWorker`) với progress, log và hỗ trợ hủy.
- Tính năng annotation mới nên hoạt động trên hình học Shapely thật (xem `canvas.py`), không chỉ vẽ đè lên ảnh.
- Plugin mới kế thừa `AnnotatorPlugin` trong `app/plugins/base.py`; khai báo dependency trong `PluginInfo.requires` để ứng dụng báo thiếu thư viện thay vì crash.
- Thêm test vào `tests/test_pipeline.py` cho nghiệp vụ mới (theo mẫu `check("ten", fn)` có sẵn).
- Lint: CI chạy `ruff` — lỗi nghiêm trọng (cú pháp, tên chưa định nghĩa) sẽ làm fail build.

## Báo lỗi

Dùng mẫu **🐛 Báo lỗi** khi mở issue. Log của ứng dụng nằm ở `%LOCALAPPDATA%\AutoLabelStudioAI\logs\` (Windows) — đính kèm log giúp xử lý nhanh hơn rất nhiều.

## Giấy phép & lưu ý

Mô hình YOLO của Ultralytics theo giấy phép **AGPL-3.0** — cân nhắc khi dùng thương mại. Đóng góp của bạn được xem là đồng ý phát hành theo giấy phép của dự án.
