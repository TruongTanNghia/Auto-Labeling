# Tài liệu kiểm thử — AutoLabel Studio AI

> Phiên bản 1.1 · Cập nhật 2026-08 · Kèm biên bản 4 lỗi tìm được và đã vá khi kiểm thử luồng Auto Label + Train với model thật.

## 1. Chiến lược kiểm thử

| Tầng | Công cụ | Khi nào chạy | Cần gì |
| --- | --- | --- | --- |
| Unit + tích hợp (fake engine) | `pytest tests/` | Mỗi commit — CI chạy trên Ubuntu + Windows, Python 3.10/3.12 | Không cần GPU, không cần model |
| E2E model thật | `ALS_E2E=1 pytest tests/test_autolabel_flow.py -k e2e` | Trước khi phát hành; sau khi sửa `inference.py` | Tải yolo11n.pt (~5.6MB); GPU khuyến nghị |
| Smoke test giao diện (thủ công) | Checklist mục 4 | Trước khi phát hành bản đóng gói | Máy Windows có màn hình |

Cách chạy:

```bash
pytest -v                                  # toàn bộ test tự động
pytest --cov=app                           # kèm coverage
ALS_E2E=1 pytest tests/test_autolabel_flow.py -k e2e   # E2E model thật
```

## 2. Danh mục test case luồng Auto Label

Cài đặt tại [tests/test_autolabel_flow.py](../tests/test_autolabel_flow.py). Các module khác (DB, extractor, chất lượng ảnh, canvas, exporter, plugin, theme, UI) xem các file `tests/test_*.py` tương ứng.

### Nhóm A — chạy trong CI (fake engine, không cần model)

| Mã | Mục đích | Các bước chính | Kết quả mong đợi |
| --- | --- | --- | --- |
| TC-AL-01 | Worker ghi annotation + status + thống kê đúng | Chạy worker trên 3 ảnh với detection giả: (0.9 + 0.7), (0.4), (rỗng) | 3 ảnh xử lý, 3 nhãn; ảnh 1 → `auto`; ảnh 2 → `review` (dưới ngưỡng 0.6), annotation mang `review`; 1 ảnh empty; `n_objects` khớp DB |
| TC-AL-02 | Map class model → class project, tạo lazy | Model có class "car" chưa tồn tại trong project | Class "car" được tạo, annotation trỏ đúng `class_id`; không sinh class thừa |
| TC-AL-03 | `overwrite=False` bỏ qua ảnh đã có nhãn | Chạy worker trên các ảnh đã gán nhãn | `n_images == 0`, model **không được gọi** lần nào |
| TC-AL-04 | (BUG-03) Re-run không detect → status nhất quán | Ảnh có nhãn cũ, chạy lại với model trả về rỗng | Nhãn cũ bị xóa, `n_objects=0`, status trả về `unlabeled` |
| TC-AL-05 | (BUG-01) Gỡ tracker khỏi predict thường | Model giả có callback tracker + trạng thái trackers; gọi `_detach_tracker()` | Callback tracker bị gỡ, callback khác giữ nguyên, `predictor.trackers` bị xóa để lần track sau đăng ký lại |
| TC-AL-06 | (BUG-02) Không xóa file model của người dùng | Gọi `purge_corrupt_weight` với file .pt < 1MB ngoài weights_dir và file trong weights_dir | File ngoài: **còn nguyên**, trả về False; file trong weights_dir: xóa, trả về True |
| TC-TR-01 | (BUG-04) final_eval không sinh epoch ảo | Giả lập 2 epoch (có batch) + 1 callback final_eval (không batch, epoch đã tăng) | `history` đúng `[1, 2]`, metric validate cuối cập nhật vào epoch cuối |
| TC-TR-02 | Dừng sớm (patience) vẫn không sinh epoch ảo | 3/10 epoch rồi final_eval | `history == [1, 2, 3]` |
| TC-TR-03 | Đọc đúng metric từ Ultralytics | Callback với loss/mAP/lr giả lập | box/cls loss, mAP50, mAP50-95, lr khớp giá trị |
| TC-TR-04 | Cancel dừng vòng train | `cancel()` rồi bắn callback batch | `trainer.stop`/`stop_training` = True |

> TC-TR-* nằm tại [tests/test_trainer.py](../tests/test_trainer.py).

### Nhóm B — E2E model thật (`ALS_E2E=1`)

| Mã | Mục đích | Các bước chính | Kết quả mong đợi |
| --- | --- | --- | --- |
| TC-E2E-01 | Detect thật + hồi quy tracker leak | Nạp yolo11n.pt, predict bus.jpg; track 2 lần; predict lại | ≥4 detection gồm bus + person; predict sau tracking **không** có `track_id`, số detection không giảm |
| TC-E2E-02 | SAHI trên ảnh lớn | Ghép bus.jpg 2×2 (2160×1620); so `predict` với `slice_predict` | SAHI ≥ inference thường, mọi bbox nằm trong ảnh gốc |

### Nhóm C — kịch bản E2E đầy đủ (đã chạy thủ công 2026-08, tham khảo để tái lập)

Luồng: tạo project → nạp 3 ảnh → dựng video 40 frame → cắt frame (every_n_frames=4, khử trùng lặp) → auto label GPU → kiểm DB → overwrite=False → tracking → segmentation → SAHI → export YOLO.

Kết quả ghi nhận trên RTX 3050 Laptop (4GB):

- 13 ảnh → **73 đối tượng** (bus 15, person 56, tie 1, skateboard 1), ~4 ảnh/s.
- Tracking 10 frame: track_id `{1..5}` nhất quán xuyên suốt, đối tượng ra khỏi khung mất track đúng lúc.
- Segmentation: 6/6 detection có polygon.
- SAHI trên mosaic: 46 detection so với 18 khi inference thường.
- Export YOLO detection: 73 dòng nhãn = 73 đối tượng, tọa độ chuẩn hóa [0,1], có `data.yaml`.

**Luồng Train (E2E thật, RTX 3050, 2026-08):** project 12 ảnh → auto-label 48 đối tượng → `TrainWorker` tự dựng dataset YOLO (`runs/dataset/data.yaml`) → train yolo11n 2 epoch/imgsz 320 (~20s GPU) → metric bắn về từng epoch → `best.pt` được ghi, nạp lại và suy luận được. Phát hiện + vá BUG-04 trong lần chạy này.

## 3. Biên bản lỗi (đã vá 2026-08)

### BUG-01 — Tracker "bám" vào mọi predict sau một phiên tracking · Nghiêm trọng: **CAO**

- **Hiện tượng**: sau khi auto-label chế độ tracking, các lệnh suy luận thường sau đó (auto-label thường, SAHI, "Auto label ảnh này" trong Editor) bị BoT-SORT chạy ngầm: log tràn cảnh báo `GMC failed`, kết quả bị **nuốt detection** (ảnh mosaic: 2 thay vì 18) và dính `track_id` giả vào DB.
- **Nguyên nhân gốc**: `model.track()` của Ultralytics đăng ký callback tracking **một lần trên model** và callback không kiểm tra mode — mọi `predict()` sau đó vẫn kích hoạt tracker.
- **Cách vá**: thêm `YoloEngine._detach_tracker()` gỡ callback thuộc `ultralytics.trackers` + xóa `predictor.trackers`; gọi ở đầu `predict()`/`predict_batch()`; `reset_tracker()` dùng chung cơ chế (xóa hẳn attr thay vì gán `None` — gán None làm `track()` lần sau không đăng ký lại được).
- **Hồi quy**: TC-AL-05, TC-E2E-01.

### BUG-02 — `purge_corrupt_weight` có thể xóa model của người dùng · Nghiêm trọng: **TRUNG BÌNH**

- **Hiện tượng**: file `.pt` < 1MB nằm **ngoài** thư mục weights (model custom nhỏ của người dùng) bị xóa vĩnh viễn nếu nạp lỗi — kể cả khi lỗi chỉ do lệch phiên bản ultralytics.
- **Cách vá**: chỉ cho phép xóa file nằm **trong** `weights_dir()` (nơi chứa trọng số chuẩn có thể tải lại).
- **Hồi quy**: TC-AL-06.

### BUG-03 — Re-run auto label rỗng để lại status sai · Nghiêm trọng: **THẤP**

- **Hiện tượng**: ảnh đã có nhãn, chạy lại auto label (overwrite) mà model không phát hiện gì → nhãn cũ bị xóa nhưng ảnh vẫn hiển thị "Máy gán nhãn"/"Cần xem lại" với 0 đối tượng; bộ lọc và thống kê sai.
- **Cách vá**: khi không có detection và ảnh trước đó có nhãn → đặt status về `unlabeled`.
- **Hồi quy**: TC-AL-04.

### BUG-04 — Train hiển thị "epoch ảo" vượt tổng (3/2) · Nghiêm trọng: **THẤP**

- **Hiện tượng**: train N epoch nhưng UI/log hiện epoch `N+1/N`, `epochs_done = N+1`, biểu đồ metric có thêm một điểm thừa.
- **Nguyên nhân gốc**: sau vòng train, Ultralytics tăng `trainer.epoch` thêm 1 **rồi mới** chạy `final_eval`, và final_eval vẫn bắn `on_fit_epoch_end`; guard cũ so sánh bằng epoch nên trượt.
- **Cách vá**: đếm số batch train kể từ epoch-end gần nhất — epoch thật luôn có ≥1 batch, lần gọi trong final_eval thì không → cập nhật metric validate cuối vào epoch cuối thay vì thêm epoch mới. Cách này đúng cả khi dừng sớm do patience.
- **Hồi quy**: TC-TR-01, TC-TR-02.

## 4. Checklist smoke test giao diện (thủ công, trước phát hành)

1. ☐ Mở app → Dashboard hiện GPU đúng (hoặc CPU), không lỗi console.
2. ☐ Tạo project mới → thư mục sinh đủ `frames/ images/ exports/ runs/ backups/`.
3. ☐ Kéo-thả 1 video vào cửa sổ → app chuyển trang Import, xem trước hiện thông số.
4. ☐ Cắt frame chế độ Every N Frames, bật khử trùng lặp → số ảnh khớp ước lượng, có progress + hủy được.
5. ☐ Auto Label: nạp yolo11n.pt → gán nhãn → ảnh có box + confidence, ảnh dưới ngưỡng vào bộ lọc "Cần xem lại".
6. ☐ Editor: sửa 1 polygon bằng Brush, Undo/Redo, `Enter` duyệt và sang ảnh kế.
7. ☐ Statistics: biểu đồ class + heatmap hiển thị; Export YOLO det → mở `data.yaml` kiểm tra.
8. ☐ Train 1 epoch với dataset nhỏ → biểu đồ metric chạy, `best.pt` được ghi.
9. ☐ Đóng mở lại app → project gần nhất tự mở, lịch sử ghi ở Dashboard.
10. ☐ Settings: đổi ngôn ngữ / theme (nếu bật) và khởi động lại — không vỡ giao diện.

## 5. Quy ước viết test mới

- Mỗi bug được vá **phải** kèm test hồi quy đặt tên `TC-…` và ghi vào bảng mục 2.
- Test cần DB/ảnh dùng fixture `repo` / `sample_data` trong `tests/conftest.py` — không tự tạo project thủ công.
- Test cần model thật phải nằm sau marker `requires_real_model` (`ALS_E2E=1`) để CI không phụ thuộc mạng.
- Fake engine chuẩn: xem `FakeEngine` trong `tests/test_autolabel_flow.py`.
