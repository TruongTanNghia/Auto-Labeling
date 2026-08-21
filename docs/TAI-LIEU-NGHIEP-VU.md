# Tài liệu đặc tả nghiệp vụ — AutoLabel Studio AI

> Phiên bản 1.0 · Cập nhật 2026-08 · **Dành cho đội Tester/QA**: mô tả toàn bộ nghiệp vụ xử lý của hệ thống, quy tắc đánh mã `BR-xx` để trace vào test case. Mỗi quy tắc là một điều kiện "phải đúng" — vi phạm là bug.

---

## 0. Khái niệm cốt lõi (đọc trước khi test)

| Khái niệm | Định nghĩa |
| --- | --- |
| **Project** | Một thư mục độc lập chứa toàn bộ dữ liệu: file `project.alsdb` (SQLite) + thư mục `frames/ images/ exports/ runs/ backups/`. Mọi thao tác đều diễn ra trong một project đang mở. |
| **Task** | Loại bài toán của project: `detect` (khung chữ nhật) · `segment` (vùng đa giác) · `obb` (khung xoay) · `pose` (khung + điểm khớp). Chọn khi tạo project. |
| **Class** | Nhãn phân loại đối tượng (vd: person, car). Có tên, màu, thứ tự. |
| **Annotation** | Một đối tượng được đánh dấu trên ảnh: class + hình học (bbox/polygon/keypoints) + confidence + trạng thái + nguồn (`yolo` = máy gán, `manual` = người vẽ). |
| **Confidence** | Độ tự tin của model, 0.0–1.0. Quyết định trạng thái annotation (xem BR-30). |
| **Track ID** | Số định danh một đối tượng xuyên suốt chuỗi frame video (chỉ có khi bật tracking). |

### Vòng đời trạng thái ẢNH

```text
unlabeled (Chưa gán nhãn)
   │  auto label có kết quả, mọi nhãn ≥ ngưỡng review
   ├────────────────────────────▶ auto (Máy gán nhãn)
   │  auto label có ≥1 nhãn dưới ngưỡng review
   ├────────────────────────────▶ review (Cần xem lại)
   │  người dùng bấm duyệt (Enter/duyệt hàng loạt)
   └──── auto/review ───────────▶ approved (Đã duyệt)

re-run auto label không phát hiện gì  ⟶  quay về unlabeled (BR-34)
```

### Vòng đời trạng thái ANNOTATION

`auto` (máy gán, đủ tự tin) → `review` (máy gán, dưới ngưỡng) → `approved` (người xác nhận). Người vẽ tay trong Editor tạo annotation nguồn `manual`.

---

## 1. Quản lý Project (Dashboard)

**Luồng**: mở app → Dashboard → tạo mới / mở project có sẵn / tự mở project gần nhất.

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-01 | Tạo project phải sinh đủ 5 thư mục con `frames/ images/ exports/ runs/ backups/` + file `project.alsdb`. |
| BR-02 | Lần chạy sau, app **tự mở project gần nhất**. Nếu project đã bị xóa/di chuyển → báo lỗi rõ ràng và về Dashboard, không crash. |
| BR-03 | Vào một trang cần project khi chưa mở project → hiển thị 2 nút "Tạo project mới" / "Mở project có sẵn", không hiển thị trang trống hay lỗi. |
| BR-04 | **Autosave** chạy định kỳ (mặc định 5 phút, đổi được trong Settings) kèm backup xoay vòng vào `backups/`, giữ tối đa **10 bản** gần nhất — bản cũ hơn tự xóa. |
| BR-05 | Mọi thao tác lớn (tạo project, cắt frame, auto label, export, train, dọn dẹp) đều ghi vào **lịch sử** và hiển thị ở Dashboard. |
| BR-06 | Dashboard hiển thị đúng thiết bị suy luận: tên GPU + VRAM nếu có CUDA, ngược lại "CPU". |
| BR-07 | Có thể mở project bằng dòng lệnh: `python main.py "đường/dẫn/project.alsdb"`. |

---

## 2. Import (nạp dữ liệu vào project)

**Luồng**: Import → thêm video / thư mục ảnh / dataset có nhãn — hoặc kéo-thả thẳng vào cửa sổ app.

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-10 | Kéo-thả file/thư mục vào **bất kỳ trang nào** → app tự chuyển sang trang Import và nhận dữ liệu. |
| BR-11 | Video (mp4, avi, mov, mkv, webm…) **không nạp thẳng vào project được** — phải cắt frame trước. Trang Import phải hiển thị rõ bước kế tiếp là "Cắt frame từ video". |
| BR-12 | Chọn video → xem trước phải hiện: frame mẫu, độ phân giải, FPS, thời lượng, codec, dung lượng. |
| BR-13 | Nạp thư mục ảnh: tùy chọn "Sao chép ảnh vào thư mục project" — bật thì copy vào `images/`, tắt thì tham chiếu đường dẫn gốc (ảnh gốc bị xóa ngoài app → ảnh trong app thành "mất file"). |
| BR-14 | Tùy chọn "Phát hiện ảnh trùng khi nạp" (pHash + SSIM): ảnh trùng bị **đánh dấu** `duplicate` chứ không bị từ chối nạp. |
| BR-15 | Nạp cùng một ảnh (cùng đường dẫn) 2 lần → không tạo bản ghi trùng trong DB (số ảnh không tăng). |
| BR-16 | Đường dẫn/tên file **có dấu tiếng Việt, ký tự Unicode** phải hoạt động bình thường ở mọi bước (nạp, hiển thị, gán nhãn, export). |

### 2b. Nhập dataset có nhãn sẵn (YOLO / COCO)

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-17 | Hỗ trợ nhập dataset **YOLO** (thư mục có `data.yaml`/`classes.txt` + `labels/`) và **COCO JSON**. Định dạng chọn ở combobox. |
| BR-18 | Phải có bước **Xem trước** hiển thị số ảnh / số annotation / số class **trước khi** nhập thật. |
| BR-19 | Xung đột class: class trùng tên (không phân biệt hoa thường) với class có sẵn → **gộp vào class cũ**; class chưa có → **tự tạo mới**. Không hỏi lại từng class. |
| BR-20 | Round-trip phải bảo toàn: export YOLO/COCO từ project A → import vào project B → số annotation, class, tọa độ (sai số < 1px) phải khớp. |

---

## 3. Frame Extractor (cắt frame từ video)

**Luồng**: chọn video → chọn chế độ + bộ lọc → xem ước lượng → Bắt đầu → ảnh rơi vào `frames/` và được nạp vào project với `frame_index` + `timestamp`.

### 3.1. Năm chế độ cắt

| Chế độ | Quy tắc xử lý |
| --- | --- |
| Every Frame | Lấy mọi frame trong khoảng đã chọn. |
| Every N Frames | Cứ N frame lấy 1 (N=4, video 40 frame → 10 ảnh). |
| Every N Seconds | Quy đổi theo FPS của video: bước nhảy = N × FPS frame. |
| Adaptive Motion | Chỉ lấy khi khác biệt frame (frame-diff) vượt `motion_threshold` (mặc định 0.045). Video tĩnh hoàn toàn → rất ít/không có ảnh. |
| Scene Detection | Chỉ lấy khi histogram HSV đổi vượt `scene_threshold` (mặc định 0.35) — tức đổi cảnh. |

### 3.2. Quy tắc chung

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-21 | **Khử trùng lặp** (bật mặc định): so pHash 64-bit (khoảng cách ≤ 6) rồi xác nhận lại bằng SSIM (≥ 0.965) mới tính là trùng. Ảnh trùng bị loại (hoặc giữ + đánh dấu nếu bật "keep_rejected"). |
| BR-22 | **Lọc ảnh mờ** (bật mặc định): variance of Laplacian < `blur_threshold` (mặc định 60) → loại/đánh dấu mờ. |
| BR-23 | **Lọc thiếu sáng** (tắt mặc định): độ sáng trung bình < ngưỡng (mặc định 45) → loại/đánh dấu. |
| BR-24 | Các giới hạn phải được tôn trọng đồng thời: `max_frames` (0 = không giới hạn), khoảng thời gian `start_time`–`end_time`, thu nhỏ cạnh dài `resize_long_side`, định dạng JPG/PNG + chất lượng JPEG. |
| BR-25 | **Ước lượng số ảnh đầu ra hiển thị trước khi chạy** và phải sát thực tế với chế độ Every Frame / N Frames / N Seconds (chế độ adaptive/scene chỉ ước lượng tương đối). |
| BR-26 | Kết quả trả về phải đếm đúng: `n_read` (đọc), `n_saved` (lưu), `n_duplicate`, `n_blurry`, `n_dark`. Tổng hợp lý: saved + loại bỏ ≤ read. |
| BR-27 | Mỗi ảnh cắt ra lưu kèm `frame_index` (thứ tự frame gốc) và `timestamp` (giây) — bắt buộc để tracking hoạt động đúng (BR-37). |
| BR-28 | Đang cắt có thể **Hủy**: dừng sớm, ảnh đã cắt vẫn giữ, không treo UI, không crash. Video hỏng/không mở được → báo lỗi rõ, không crash. |

---

## 4. Auto Label (gán nhãn tự động) — nghiệp vụ trung tâm

**Luồng**: chọn nhiệm vụ (detect/segment/obb/pose) + trọng số → **Nạp model** → cấu hình ngưỡng → chọn phạm vi ảnh → **Bắt đầu gán nhãn** → theo dõi tiến độ/preview → kết quả ghi vào DB.

### 4.1. Nạp model

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-29a | Hỗ trợ trọng số: `.pt`, `.onnx`, `.engine`, `.torchscript`. Tên model chuẩn (vd `yolo11n.pt`) chưa có trên máy → **tự tải** về thư mục weights của app, có hiển thị % tiến độ tải. |
| BR-29b | Thiết bị: `auto` → dùng GPU nếu có CUDA, ngược lại CPU. Chuyển GPU thất bại → **fallback CPU + ghi log**, không crash. |
| BR-29c | File trọng số chuẩn tải dở (hỏng) → app tự xóa **chỉ khi file nằm trong thư mục weights của app** và tải lại một lần. File `.pt` của người dùng ở nơi khác **tuyệt đối không bị xóa** dù nạp lỗi (đã vá BUG-02). |
| BR-29d | Nạp lại cùng weights + task + device → không nạp lại từ đầu (trả về ngay). |

### 4.2. Quy tắc gán nhãn

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-30 | **Ngưỡng 3 tầng** với mỗi detection có confidence `c`: `c ≥ review_threshold` (mặc định 0.6) → annotation `auto`; `c < review_threshold` → annotation `review` và **ảnh** chuyển "Cần xem lại"; `c < low_conf_threshold` (mặc định 0.35) → đếm thêm vào "Low Confidence". Detection dưới `confidence` suy luận (mặc định 0.45) không xuất hiện. |
| BR-31 | **Class lazy**: chỉ tạo class trong project khi có ít nhất 1 dự đoán thuộc class đó. Nạp model COCO 80 class rồi gán nhãn ảnh chỉ có người + xe → project chỉ có class person, car (không sinh 80 class rỗng). Class trùng tên có sẵn (không phân biệt hoa thường) → dùng lại, không tạo mới. |
| BR-32 | Detection diện tích < `min_area_px` (mặc định 24 px²) bị loại. Polygon được đơn giản hóa Douglas–Peucker theo `polygon_simplify` (0.0025 × chu vi; 0 = giữ nguyên). |
| BR-33 | **Ghi đè**: bật (mặc định) → nhãn cũ của ảnh bị thay hoàn toàn bằng nhãn mới. Tắt → ảnh đã có nhãn bị **bỏ qua hoàn toàn, không gọi model** (tiết kiệm GPU — kiểm bằng thời gian chạy). |
| BR-34 | Re-run trên ảnh từng có nhãn mà lần này **không phát hiện gì** → nhãn cũ bị xóa và status ảnh trả về `unlabeled` — không được để ảnh 0 đối tượng mang nhãn "Máy gán nhãn" (đã vá BUG-03). |
| BR-35 | Ảnh mất file (đường dẫn không tồn tại) → **bỏ qua + ghi log**, các ảnh sau vẫn chạy tiếp. Lỗi suy luận 1 ảnh không được làm dừng cả batch. |
| BR-36 | Kết quả tổng kết phải khớp DB: số ảnh xử lý, tổng đối tượng, số ảnh cần review, số ảnh rỗng, thống kê theo class, tốc độ ảnh/s. `n_objects` trên từng ảnh = số annotation thực trong DB. |

### 4.3. Tracking (theo dõi đối tượng qua frame)

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-37 | Bật tracking → ảnh được **sắp lại theo `frame_index`** trước khi chạy (ảnh không có frame_index xếp cuối). Tracker reset khi bắt đầu phiên mới — track_id đếm lại từ 1. |
| BR-38 | Cùng một đối tượng di chuyển qua các frame liên tiếp phải giữ **nguyên một track_id**. Đối tượng ra khỏi khung → track_id đó biến mất, không gán nhầm cho đối tượng khác. |
| BR-39 | **Sau phiên tracking, mọi suy luận thường (auto label không tracking, SAHI, "Auto label ảnh này" trong Editor) phải sạch**: không dính track_id, không giảm số detection, không cảnh báo GMC tràn log (đã vá BUG-01 — lỗi nghiêm trọng nhất từng phát hiện, đội tester chú ý regression điểm này). |

### 4.4. SAHI (suy luận cắt lát cho ảnh lớn)

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-40 | Ảnh ≤ kích thước ô (mặc định 640px) → tự động dùng suy luận thường (không cắt lát vô ích). |
| BR-41 | Ảnh lớn: cắt ô chồng lấn (mặc định 20%), suy luận từng ô, **dịch tọa độ về ảnh gốc** — mọi bbox/polygon kết quả phải nằm trong phạm vi ảnh gốc. |
| BR-42 | Box/polygon trùng nhau ở vùng chồng lấn phải được khử (NMS xuyên ô theo class); với segmentation, mảnh polygon cùng class sát ranh giới ô được **gộp thành một vùng liền** (Shapely). Không được thấy "2 box chồng khít nhau" tại ranh giới ô. |
| BR-43 | SAHI phải tìm được **≥** số đối tượng so với suy luận thường trên cùng ảnh lớn chứa đối tượng nhỏ (đây là lý do tồn tại của tính năng). Tiến độ hiển thị theo từng ô. |

### 4.5. Plugin tinh chỉnh

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-44 | Plugin được chọn nhưng thiếu thư viện/trọng số → ghi log lý do và **chạy tiếp không plugin** — không crash, không dừng batch. |
| BR-45 | Plugin lỗi giữa chừng trên 1 ảnh → giữ detection gốc của YOLO cho ảnh đó, ghi log, chạy tiếp. |
| BR-46 | Plugin refine (SAM/FastSAM) nhận box thô → trả mask polygon bám sát đối tượng; số đối tượng không đổi trừ khi plugin chủ động lọc. |

---

## 5. Annotation Editor (sửa nhãn)

**Luồng**: chọn ảnh (thường lọc "Cần xem lại") → sửa bằng công cụ → `Enter` duyệt và sang ảnh kế.

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-50 | 7 công cụ: Select (V) · Polygon (W) · BBox · Brush (B) · Eraser (E) · Split (S) · Pan (giữ Space). Phím tắt phải đúng như bảng trong README. |
| BR-51 | **Brush/Eraser thao tác trên hình học thật** (Shapely): tô thêm = hợp vùng; tẩy = cắt vùng. Tẩy xuyên giữa vùng → tạo **lỗ**, và lỗ vẫn export được ra YOLO (kỹ thuật keyhole — kiểm bằng export sau khi tẩy lỗ). |
| BR-52 | Split: kẻ một đường cắt → 1 vùng tách thành nhiều vùng (mỗi vùng một annotation). Merge (M): các vùng đang chọn gộp thành một. Simplify: giảm số đỉnh nhưng hình dạng không biến dạng rõ rệt. |
| BR-53 | Kéo đỉnh chỉnh hình; **nháy đúp lên cạnh** thêm đỉnh mới; Delete xóa đối tượng chọn; Esc hủy thao tác vẽ dở. |
| BR-54 | **Undo/Redo tối thiểu 60 bước**, hoạt động đúng với mọi công cụ kể cả brush/eraser/split/merge. |
| BR-55 | `A`/`D` chuyển ảnh trước/sau; `Enter` = duyệt ảnh hiện tại (status → `approved`) và sang ảnh kế; phím `1..9` gán class cho đối tượng đang chọn. |
| BR-56 | Đổi class/confidence được cho **nhiều đối tượng cùng lúc**; thao tác trên ảnh phải cập nhật ngay số liệu (n_objects, trạng thái) ở các trang khác. |
| BR-57 | Zoom (Ctrl +/-/0), Pan, Navigator (minimap có khung viewport) hoạt động; Alt + cuộn đổi cỡ cọ khi dùng Brush/Eraser. |
| BR-58 | Vẽ tay annotation mới → nguồn ghi `manual`, confidence = 1.0. |

---

## 6. Dataset Manager (quản lý & dọn dẹp)

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-60 | Thumbnail nạp **lazy ở luồng nền** — cuộn danh sách vài nghìn ảnh không giật/đứng UI. |
| BR-61 | Bộ lọc: Tất cả · Đã gán nhãn · Chưa gán nhãn · Cần review · Đã duyệt · Trùng · Mờ — số lượng mỗi bộ lọc phải khớp thống kê nhanh phía trên. |
| BR-62 | Thao tác hàng loạt: duyệt, đánh dấu review, xóa. Xóa có tùy chọn "xóa cả file trên đĩa" — không tick thì chỉ gỡ khỏi project, file còn nguyên. |
| BR-63 | **Dọn dẹp**: xóa ảnh trùng / ảnh mờ / ảnh chưa gán nhãn, gỡ ảnh mất file, tính lại số đối tượng, sao lưu trước khi dọn. Mỗi hành động phải báo trước số lượng ảnh hưởng và cho xác nhận. |
| BR-64 | Xóa ảnh → annotation của ảnh đó bị xóa theo; xóa class → hỏi xác nhận và xử lý annotation thuộc class đó theo lựa chọn. |

---

## 7. Statistics & Export

### 7.1. Thống kê

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-70 | 6 mục: Tổng quan · Phân bố class · Kích thước object · Bản đồ nhiệt · Chất lượng ảnh · Xuất dataset. Số liệu phải khớp DB (đối chiếu với Dataset Manager). |
| BR-71 | Heatmap thể hiện mật độ **vị trí** đối tượng trên khung ảnh chuẩn hóa; phân bố confidence/độ nét/độ sáng/số đối tượng mỗi ảnh vẽ đúng dữ liệu. |

### 7.2. Export — 7 định dạng

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-72 | 7 định dạng: YOLO Seg · YOLO Det · YOLO OBB · YOLO Pose · COCO JSON (kèm keypoints) · Pascal VOC XML · PNG Mask (kèm mask màu). |
| BR-73 | **YOLO Det**: mỗi dòng đúng 5 cột `class cx cy w h`, tọa độ chuẩn hóa 0–1. **YOLO Seg**: `class x1 y1 x2 y2 ...`. **OBB**: 8 tọa độ + polygon tự quy về hộp xoay nhỏ nhất. **Pose**: ghi kèm `kpt_shape` vào `data.yaml`. Tổng số dòng nhãn = tổng đối tượng đã export. |
| BR-74 | Chia **train/val/test** theo tỉ lệ + seed: cùng seed → cùng cách chia (tái lập được); mỗi ảnh chỉ thuộc một split; tự sinh `data.yaml` + `classes.txt`. |
| BR-75 | Bộ lọc export phải có hiệu lực: chỉ ảnh đã duyệt (`only_approved`) · loại ảnh trùng · loại ảnh mờ · confidence tối thiểu · chọn class. Không còn ảnh nào thỏa → báo lỗi rõ ràng, không xuất thư mục rỗng. |
| BR-76 | Export đè lên thư mục dataset cùng tên cũ (xóa sạch trước khi ghi) — không trộn lẫn kết quả cũ mới. |

---

## 8. Train Model

**Luồng**: cấu hình → Bắt đầu → app **tự dựng dataset YOLO từ project** (không cần export tay) → train → theo dõi realtime → `best.pt` lưu lại dùng ngay.

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-80 | Dataset tự dựng vào `runs/dataset/` theo đúng task của project (detect→yolo_det, segment→yolo_seg…), chia val theo tỉ lệ đã chọn, có `data.yaml`. |
| BR-81 | Cấu hình đầy đủ: epochs, batch, imgsz, optimizer, lr, patience, workers, device, augmentation, cache. Device auto → GPU nếu có. |
| BR-82 | Theo dõi **thời gian thực**: vòng tiến độ, biểu đồ mAP50/mAP50-95/P/R, biểu đồ loss, log, thời gian chạy + ước tính còn lại. Metric cập nhật **mỗi epoch**. |
| BR-83 | Epoch hiển thị **không bao giờ vượt tổng** (không có "3/2"); `epochs_done` = số epoch thực chạy — kể cả khi dừng sớm do patience (đã vá BUG-04). |
| BR-84 | **Hủy** giữa chừng: train dừng ở batch/epoch kế tiếp, app không treo, kết quả dở được ghi nhận là đã hủy. |
| BR-85 | Kết thúc: `best.pt` + `last.pt` nằm trong `runs/<tên run>/weights/`; lịch sử các lần train lưu lại; `best.pt` nạp được ngay ở trang Auto Label để suy luận. |
| BR-86 | Chạy train nhiều lần → mỗi lần một thư mục run mới (train1, train2…), không đè kết quả cũ. |

---

## 9. Settings

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-90 | 7 mục: Chung · Model · Suy luận · Annotation · Plugin · Phím tắt · Giới thiệu. Mọi thay đổi lưu vào `settings.json` và **giữ nguyên sau khi khởi động lại**. |
| BR-91 | Đổi ngôn ngữ (Việt/Anh): toàn bộ giao diện đổi theo, không sót chuỗi, không vỡ layout. |
| BR-92 | Tham số plugin chỉnh được qua form trong Settings → Plugin (không cần sửa code); "Khôi phục mặc định" trả về giá trị gốc; "Quét lại plugin" nhận plugin mới thả vào thư mục plugins. |
| BR-93 | Plugin thiếu điều kiện (vd SAM 3 thiếu `sam3.pt`) → Settings hiển thị **đúng lý do + lệnh cần chạy**, các plugin khác vẫn hoạt động. |

---

## 10. Quy tắc xuyên suốt (mọi màn hình)

| Mã | Quy tắc nghiệp vụ |
| --- | --- |
| BR-100 | **UI không bao giờ đứng**: mọi tác vụ nặng (cắt frame, suy luận, export, train, quét thư mục) chạy nền, có thanh tiến độ + log + nút **Hủy** hoạt động. Trong lúc chạy vẫn cuộn/di chuyển UI được. |
| BR-101 | Hủy bất kỳ tác vụ nào: dừng trong vài giây, dữ liệu đã xử lý xong vẫn hợp lệ, không để DB ở trạng thái dở dang. |
| BR-102 | Lỗi đơn lẻ (1 ảnh hỏng, 1 file mất) → ghi log + bỏ qua + chạy tiếp; lỗi hệ thống (hết VRAM, mất model) → thông báo rõ nguyên nhân bằng ngôn ngữ người dùng, không hiện traceback thô. |
| BR-103 | Số liệu phải **nhất quán giữa các trang**: n_objects, số class, trạng thái ảnh trên Dashboard = Dataset Manager = Statistics = Editor. |
| BR-104 | App đóng đột ngột (kill) giữa chừng → mở lại project vẫn đọc được (SQLite WAL), mất tối đa dữ liệu từ lần autosave gần nhất. |
| BR-105 | Phím tắt toàn cục: `Ctrl+1..9` chuyển trang, `Ctrl+N/O/S` project, `F5` bắt đầu auto label, `F11` toàn màn hình. |

---

## 11. Ca biên & dữ liệu test gợi ý cho đội QA

| # | Ca biên | Kỳ vọng |
| --- | --- | --- |
| E-01 | Video 0 frame / file rỗng / đuôi sai | Báo lỗi rõ, không crash |
| E-02 | Ảnh 1×1 px, ảnh xám, PNG có kênh alpha | Nạp + gán nhãn không lỗi (có thể 0 detection) |
| E-03 | Ảnh cực lớn (≥ 8000px) + SAHI | Chạy được, chậm nhưng không hết RAM đột tử |
| E-04 | Project trên đường dẫn có dấu + khoảng trắng | Mọi luồng hoạt động (BR-16) |
| E-05 | Chạy auto label khi GPU đang bận ứng dụng khác | Chậm hoặc fallback, không crash |
| E-06 | Tắt mạng khi đang tải trọng số | Báo lỗi tải; nạp lại khi có mạng thành công (file dở bị dọn — BR-29c) |
| E-07 | Xóa file ảnh ngoài app rồi auto label / export | Bỏ qua + log (BR-35); export không chứa ảnh mất file |
| E-08 | Hủy ở mọi tác vụ, tại nhiều thời điểm khác nhau | BR-101 |
| E-09 | Train với dataset chỉ 2–3 ảnh / chỉ 1 class / 0 ảnh val | Chạy được hoặc báo thiếu dữ liệu rõ ràng, không crash |
| E-10 | Hai lần export cùng tên dataset liên tiếp | Kết quả lần 2 sạch, không lẫn file cũ (BR-76) |
| E-11 | Auto label 2 lần liên tiếp: lần 1 tracking, lần 2 thường | Lần 2 sạch track_id, đủ detection (BR-39 — regression BUG-01) |
| E-12 | Re-run auto label với confidence 0.99 | Ảnh về `unlabeled`, không kẹt status cũ (BR-34 — regression BUG-03) |

**Dữ liệu test có sẵn**: 2 ảnh mẫu của Ultralytics (`bus.jpg`, `zidane.jpg` — nằm trong package, chứa người/xe buýt thật), model nhẹ `yolo11n.pt` (~5.6MB, tự tải). Kịch bản E2E mẫu và kết quả chuẩn tham khảo tại [TAI-LIEU-KIEM-THU.md](TAI-LIEU-KIEM-THU.md) (nhóm C).

---

## 12. Lỗi đã biết & đã vá (regression bắt buộc mỗi release)

| Bug | Tóm tắt | Quy tắc liên quan | Test tự động |
| --- | --- | --- | --- |
| BUG-01 (cao) | Tracker bám vào predict thường sau phiên tracking — nuốt detection, track_id giả | BR-39 | TC-AL-05, TC-E2E-01 |
| BUG-02 (TB) | Xóa nhầm file model người dùng ngoài weights_dir | BR-29c | TC-AL-06 |
| BUG-03 (thấp) | Re-run rỗng để lại status "auto" | BR-34 | TC-AL-04 |
| BUG-04 (thấp) | Epoch ảo "3/2" từ final_eval của Ultralytics | BR-83 | TC-TR-01, TC-TR-02 |
| BUG-05 (thấp) | Combobox "Trọng số SAM" trang Auto Label không được connect | BR-44 | TC-UI-05 |
| BUG-06 (cao) | Ô prompt plugin bị ẩn vĩnh viễn → plugin prompt không dùng được từ UI | BR-44 | TC-UI-05 |

> Chi tiết nguyên nhân gốc và cách vá: [TAI-LIEU-KIEM-THU.md](TAI-LIEU-KIEM-THU.md) mục 3.
