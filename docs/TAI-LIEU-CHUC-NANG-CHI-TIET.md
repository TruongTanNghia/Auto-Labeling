# Đặc tả chức năng chi tiết — AutoLabel Studio AI

> Phiên bản 1.0 · Cập nhật 2026-08 · **Dành cho đội Tester/QA**: liệt kê **từng control** trên từng màn hình — mọi nút bấm, thanh trượt, ô tham số — kèm giá trị mặc định, phạm vi cho phép và hành vi, **trích trực tiếp từ mã nguồn giao diện**.
>
> Cách dùng: mỗi bảng là một nhóm control đúng thứ tự xuất hiện trên màn hình. Cột "Mặc định/Phạm vi" là giá trị phải thấy khi mở app lần đầu — lệch là bug. Cột "Hành vi" là điều phải xảy ra khi thao tác. Quy tắc nghiệp vụ tổng quát (mã BR-xx) xem tại [TAI-LIEU-NGHIEP-VU.md](TAI-LIEU-NGHIEP-VU.md).

## Mục lục

1. [Trang Import](#1-trang-import)
2. [Trang Frame Extractor (Cắt frame)](#2-trang-frame-extractor-cắt-frame)
3. [Trang Auto Label](#3-trang-auto-label)
4. [Trang Train Model](#4-trang-train-model)
5. [Trang Annotation Editor](#5-trang-annotation-editor)
6. [Trang Dataset Manager](#6-trang-dataset-manager)
7. [Trang Statistics & Export](#7-trang-statistics--export)
8. [Trang Settings](#8-trang-settings)
9. [Trang Dashboard](#9-trang-dashboard)

---

# 1. Trang Import

## 1.1. Header (thanh tiêu đề trang)

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Thêm thư mục ảnh | Nút (ghost, icon thư mục) | — | Mở hộp thoại chọn thư mục ("Chọn thư mục chứa ảnh"), quét ảnh; thư mục rỗng → toast "Thư mục này không chứa ảnh nào." |
| Thêm video | Nút (primary, icon video) | — | Mở hộp thoại chọn nhiều file video (mp4/avi/mov/mkv/webm…), thêm vào danh sách nguồn |

## 1.2. Khung "Nguồn dữ liệu" (cột trái)

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| "Kéo thả video, ảnh hoặc cả thư mục vào đây" | Khu kéo-thả (viền nét đứt) | Hiện khi danh sách rỗng | Thả file/thư mục → tự phân loại video/ảnh; **tự ẩn** khi đã có dữ liệu |
| Danh sách nguồn | Danh sách (chọn nhiều, item cao 52px, tooltip = đường dẫn đầy đủ) | Rỗng | Chọn item → xem trước bên phải (video: frame ở 1/3 phim + bảng thông số; thư mục: ảnh đầu tiên); cũng nhận kéo-thả |
| Bỏ mục đang chọn | Nút (ghost, icon trừ) | — | Xóa các item đang chọn; chưa chọn gì → toast "Hãy chọn mục muốn bỏ ở danh sách bên trái." |
| Xoá hết | Nút (danger, icon thùng rác) | — | Xóa toàn bộ danh sách, reset khung xem trước |
| Nhãn đếm | Nhãn động | "Chưa có gì" | Hiển thị "{n} video · {n} ảnh" theo nội dung danh sách |

## 1.3. Khung "Xem trước" (cột phải)

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Ảnh xem trước | Nhãn ảnh (min 200px, giữ tỉ lệ) + nhận kéo-thả | "Chọn một mục ở bên trái để xem trước" | Hiện frame video/ảnh đầu thư mục; lỗi → "Không mở được video này" / "Không đọc được ảnh" |
| Bảng thông tin video | Lưới key-value | Rỗng | Tên file · Độ phân giải · FPS · Thời lượng · Tổng số frame · Codec · Dung lượng |
| Bảng thông tin thư mục ảnh | Lưới key-value | Rỗng | Thư mục · Số ảnh · Kích thước ảnh đầu · Dung lượng (ước tính từ 400 ảnh mẫu) |

## 1.4. Khung "Bước tiếp theo"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nhãn hướng dẫn | Nhãn HTML động | "Chưa chọn gì. Dùng nút **Thêm video** / **Thêm thư mục ảnh**…" | Đổi theo 4 trạng thái: rỗng / chỉ video / chỉ ảnh / lẫn lộn; chưa mở project → nối thêm cảnh báo màu vàng "Chưa mở project — bấm nút bên dưới sẽ hỏi tạo project trước." |
| Nạp ảnh vào project | Nút (primary, icon import) | **Chỉ hiện khi có ảnh**; disable khi đang chạy | Chạy worker quét-nạp ảnh (khử trùng theo toggle bên dưới, phát hiện mờ bật, thiếu sáng tắt); chưa có project → hỏi tạo trước |
| Cắt frame từ video | Nút (primary, icon phim) | **Chỉ hiện khi có video** | Chuyển sang trang Cắt frame kèm danh sách video, toast "Đã chuyển video sang trang cắt frame." |
| Sao chép ảnh vào thư mục project *(hint: Giữ nguyên vị trí gốc nếu tắt)* | Toggle | **Tắt** | Bật → copy ảnh vào `images/` của project; tắt → chỉ tham chiếu đường dẫn gốc |
| Phát hiện ảnh trùng khi nạp *(hint: So sánh bằng perceptual hash + SSIM)* | Toggle | **Bật** | Bật/tắt khử trùng lặp khi nạp ảnh |

## 1.5. Khung "Nhập dataset có nhãn" (YOLO/COCO từ Roboflow, CVAT, labelImg…)

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Ô đường dẫn dataset | Ô text **chỉ đọc** | Placeholder "Chưa chọn thư mục dataset" | Hiển thị thư mục đã chọn, không gõ tay được |
| Chọn thư mục | Nút (ghost) | — | Mở hộp thoại "Chọn thư mục dataset"; chọn xong ẩn khung kết quả xem trước cũ |
| Định dạng | Combobox | **YOLO Segmentation**; lựa chọn: YOLO Segmentation / YOLO Detection / COCO JSON | Chọn parser tương ứng |
| Nhãn kết quả xem trước | Nhãn động | **Ẩn** ban đầu | Sau "Xem trước": Số ảnh phát hiện · Số vùng nhãn · Class mới sẽ thêm / Gộp vào class cũ; lỗi → chữ đỏ |
| Xem trước | Nút (ghost, icon mắt) | — | Đọc thử dataset và hiện thống kê; chưa chọn thư mục → toast "Hãy chọn thư mục dataset trước." |
| Nhập vào project | Nút (primary) | Disable khi đang chạy | Chạy worker nhập (copy ảnh vào project); xong thông báo số ảnh/nhãn/class đã nhập |

## 1.6. Thanh tiến trình (cuối trang)

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nhãn giai đoạn | Nhãn đậm | Ẩn tới khi chạy | Vd "Đang nạp {n} ảnh vào project ..." |
| Phần trăm | Nhãn màu accent | 0% | Cập nhật theo tiến độ |
| Hủy | Nút (ghost, icon ×) | — | Hủy worker đang chạy |
| Thanh tiến trình | Progress bar | 0–100 | Theo tiến độ worker |

## 1.7. Kéo-thả toàn trang

Thả file/thư mục vào **bất kỳ đâu** trên trang (kể cả danh sách, khung xem trước) → tự phân loại video/ảnh (quét đệ quy trong thư mục); không tìm thấy gì → toast "Không tìm thấy video hoặc ảnh nào trong thứ vừa thả."

---

# 2. Trang Frame Extractor (Cắt frame)

## 2.1. Header

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Chọn video | Nút (ghost, icon video) | — | Chọn nhiều video, thay danh sách hiện tại, refresh thông tin + ước lượng |
| Bắt đầu cắt frame | Nút (primary, icon play) | **Disable khi đang chạy** | Lưu cấu hình rồi chạy worker cắt; chưa chọn video → toast "Chưa chọn video nào."; chưa có project → hỏi tạo |

## 2.2. Khung "Chế độ cắt frame" — 5 chip chọn một

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Mọi frame | Chip chọn (tooltip: "Lấy toàn bộ frame của video") | — | Chọn chế độ `every_frame`, ẩn hết tham số riêng |
| Mỗi N frame | Chip chọn (tooltip: "Lấy 1 frame sau mỗi N frame") | — | Hiện ô "Lấy 1 frame mỗi … frame" |
| Mỗi N giây | Chip chọn (tooltip: "Lấy 1 frame sau mỗi N giây") | **Được chọn mặc định** | Hiện ô "Lấy 1 frame mỗi … giây" |
| Theo chuyển động | Chip chọn (tooltip: "Chỉ lấy frame khi có chuyển động đáng kể") | — | Hiện thanh "Ngưỡng chuyển động" |
| Đổi cảnh | Chip chọn (tooltip: "Lấy frame mỗi khi khung hình đổi cảnh") | — | Hiện thanh "Ngưỡng đổi cảnh" |

**Tham số theo chế độ** (chỉ hiện đúng ô của chế độ đang chọn):

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Lấy 1 frame mỗi (frame) | Ô số nguyên, hậu tố " frame" | **5**; min 1 – max 10000, bước 1 | Đổi → cập nhật ngay ô ước lượng số ảnh |
| Lấy 1 frame mỗi (giây) | Ô số thập phân, hậu tố " giây" | **1.00**; min 0.02 – max 600, bước 0.1 | Đổi → cập nhật ước lượng |
| Ngưỡng chuyển động *(Càng thấp càng lấy nhiều frame)* | Thanh trượt + ô số đồng bộ | **0.045**; min 0.005 – max 0.4, bước 0.005 | Ghi ngưỡng frame-diff |
| Ngưỡng đổi cảnh *(Càng thấp càng nhạy)* | Thanh trượt + ô số | **0.35**; min 0.05 – max 0.95, bước 0.01 | Ghi ngưỡng histogram HSV |
| Giới hạn số ảnh | Ô số nguyên, hậu tố " ảnh" | **0 = "Không giới hạn"**; max 1.000.000 | Chặn số ảnh tối đa; đổi → cập nhật ước lượng |
| Khoảng thời gian: bắt đầu | Ô số thập phân, hậu tố " s" | **0.0**; max 100000, bước 1 | Cắt từ giây này |
| Khoảng thời gian: kết thúc | Ô số thập phân, hậu tố " s" | **0.0 = "Hết video"** | Cắt đến giây này |

## 2.3. Khung "Lọc chất lượng"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Loại ảnh trùng lặp *(pHash + SSIM)* | Toggle | **Bật** | Bật/tắt khử trùng khi cắt |
| Phương pháp | Combobox | **"pHash + SSIM — khuyên dùng"**; lựa chọn: pHash — nhanh / SSIM — chính xác / pHash + SSIM — khuyên dùng | Chọn thuật toán so trùng |
| Khoảng cách pHash *(Càng nhỏ càng chặt, 0 = giống hệt)* | Ô số nguyên | **6**; min 0 – max 32 | Ngưỡng Hamming distance |
| Ngưỡng SSIM | Thanh trượt + ô số | **0.965**; min 0.7 – max 0.999, bước 0.001 | Ngưỡng xác nhận trùng |
| Phát hiện ảnh mờ *(variance of Laplacian)* | Toggle | **Bật** | Bật/tắt lọc mờ |
| Ngưỡng độ nét | Ô số thập phân | **60.0**; min 0 – max 5000, bước 5 | Dưới ngưỡng = mờ |
| Lọc ảnh thiếu sáng *(độ sáng trung bình 0–255)* | Toggle | **Tắt** | Bật/tắt lọc tối |
| Ngưỡng độ sáng | Ô số thập phân | **45.0**; min 0 – max 255, bước 5 | Dưới ngưỡng = thiếu sáng |

## 2.4. Khung "Đầu ra"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Định dạng | Combobox | **JPG**; lựa chọn JPG / PNG | Định dạng ảnh lưu |
| Chất lượng JPG | Thanh trượt | **92**; min 50 – max 100 | Chất lượng nén JPEG |
| Thu nhỏ cạnh dài | Ô số nguyên, hậu tố " px" | **0 = "Giữ nguyên"**; max 8192 | Resize cạnh dài về giá trị này |
| Thư mục lưu | Ô text (gõ tay được) | Placeholder "Mặc định: thư mục frames của project" | Trống → lưu vào `frames/` của project |
| Nút chọn thư mục | Nút icon thư mục, tooltip "Chọn thư mục…" | — | Mở hộp thoại chọn thư mục lưu |

## 2.5. Cột phải: thông tin & kết quả

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Khung "Video đang xử lý" | Lưới key-value | "Trạng thái: Chưa chọn video" | 1 video: Tên · Độ phân giải · FPS · Thời lượng · Tổng frame. Nhiều video: Số video · Tổng frame · Tổng thời lượng. Lỗi → "Không đọc được video này" |
| Khung "Ước lượng kết quả" — con số lớn | Nhãn số lớn giữa khung | **"0"** | Tính lại tức thì khi đổi N frame/N giây/giới hạn/khoảng thời gian/danh sách video; chú thích "ảnh sẽ được sinh ra (trước khi lọc)" |
| Khung "Bước tiếp theo" | Cả khung | **Ẩn mặc định** | Chỉ hiện sau khi cắt xong có ≥1 ảnh: "Đã có **{n} ảnh** trong project…" + nút **Gán nhãn tự động cho ảnh vừa cắt** → chuyển sang trang Auto Label kèm đúng loạt ảnh vừa cắt |
| Khung "Xem trước frame" | Nhãn ảnh | "Chưa có frame nào" | Hiện frame vừa cắt theo thời gian thực |
| Khung "Nhật ký" | Ô log chỉ đọc | Rỗng | Log từng bước, tự cuộn cuối; xóa mỗi lần bấm Bắt đầu; kết thúc ghi "KẾT QUẢ: lưu {n} ảnh / đọc {n} frame" |
| Thanh tiến trình + Hủy | Như trang Import | 0% | "Đang cắt frame …"; Hủy dừng worker, ảnh đã cắt giữ nguyên |

---

# 3. Trang Auto Label

## 3.1. Header

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nạp model | Nút (ghost, icon tải xuống) | Disable khi đang nạp | Lưu cấu hình model rồi nạp trọng số ở luồng nền |
| Bắt đầu gán nhãn | Nút (primary, icon play) | Disable khi đang chạy | Chạy gán nhãn trên ảnh đang chọn (hoặc toàn bộ); **model chưa nạp → tự nạp trước rồi chạy tiếp**. Chặn kèm toast khi: chưa mở project ("Hãy mở hoặc tạo project trước.") / đang chạy ("Đang gán nhãn, vui lòng đợi.") / không có ảnh ("Không có ảnh nào để gán nhãn.") |

## 3.2. Khung "Ảnh trong project"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Bộ lọc ảnh | Combobox | **"Tất cả ảnh"**; lựa chọn: Tất cả ảnh / Chưa gán nhãn / Cần xem lại / Đã duyệt / Bỏ qua ảnh trùng | Đổi → nạp lại danh sách theo bộ lọc |
| Nhãn "Đang chọn sẵn **N ảnh vừa cắt**…" | Nhãn động | **Ẩn** mặc định | Chỉ hiện khi được chuyển sang từ trang Cắt frame; đồng thời tự đặt lọc "Chưa gán nhãn" và chọn sẵn đúng loạt ảnh vừa cắt |
| Danh sách ảnh | Danh sách thumbnail, chọn nhiều; tooltip = đường dẫn, kích thước, số đối tượng, trạng thái | — | Chọn ảnh → xem trước kết quả suy luận đã có ở khung bên phải |
| Chọn tất cả | Nút (ghost) | — | Chọn toàn bộ danh sách |
| Nhãn đếm | Nhãn | "0 ảnh" | Cập nhật "{n} ảnh" sau mỗi lần refresh |

## 3.3. Khung "Cấu hình model"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nhiệm vụ | Combobox | **Segmentation**; lựa chọn: Detection / Segmentation / OBB — hộp xoay / Pose — điểm khớp | Đổi → nạp lại danh sách trọng số theo nhiệm vụ |
| Trọng số | Combobox | Điền động theo nhiệm vụ (vd segment: yolov8n-seg → yolo12m-seg; detect: yolov8n → yolo12x) | Chọn model chuẩn (bị bỏ qua nếu có Model riêng) |
| Model riêng | Nhãn "Không dùng" + nút **Chọn file** + nút **Xoá** | "Không dùng" | Chọn file `.pt/.onnx/.engine/.torchscript` → ưu tiên dùng thay model chuẩn; Xoá → về "Không dùng" |
| Thiết bị | Combobox | **Auto (ưu tiên GPU)**; lựa chọn: Auto / CPU / CUDA:i - tên GPU | Thiết bị nạp model |
| Cỡ ảnh vào model | Ô số nguyên | **640**; min 128 – max 4096, bước 32 | Kích thước ảnh đưa vào model |
| Nhãn trạng thái model | Nhãn màu | **"Chưa nạp model"** (vàng) | → "Đang nạp model …" (xanh dương) → mô tả model (xanh lá) → "Nạp model thất bại" (đỏ) |

## 3.4. Khung "Tham số suy luận"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Độ tin cậy | Thanh trượt + ô số | **0.45**; min 0.01 – max 0.99, bước 0.01 | Ngưỡng confidence tối thiểu của detection |
| IOU (khử trùng) | Thanh trượt + ô số | **0.5**; min 0.05 – max 0.95 | Ngưỡng NMS |
| Ngưỡng xem lại *(Dự đoán thấp hơn ngưỡng này sẽ bị đánh dấu Cần xem lại)* | Thanh trượt + ô số | **0.6**; min 0.05 – max 0.99 | Ảnh có nhãn dưới ngưỡng → trạng thái "Cần xem lại" |
| Số đối tượng tối đa | Ô số nguyên | **1000**; min 1 – max 30000, bước 50 | Giới hạn detection mỗi ảnh |
| Giản lược polygon | Thanh trượt + ô số | **0.0025**; min 0 – max 0.02, bước 0.0005 | Mức đơn giản hóa Douglas–Peucker |
| Diện tích tối thiểu | Ô số nguyên, hậu tố " px" | **24**; min 0 – max 100000, bước 4 | Loại detection nhỏ hơn |
| Ghi đè nhãn đã có | Toggle | **Bật** | Tắt → bỏ qua ảnh đã có nhãn (không gọi model) |
| Theo dõi đối tượng qua frame | Toggle | **Tắt** | Bật → mở combobox tracker + cập nhật cảnh báo |
| Thuật toán tracker | Combobox | **BoT-SORT**; lựa chọn: BoT-SORT / ByteTrack | **Chỉ enable khi tracking bật** |
| Nhãn cảnh báo tracking | Nhãn động màu vàng | Rỗng | "Chỉ bật theo dõi khi ảnh có thứ tự frame (từ Frame Extractor)." — toggle bị **disable + tự tắt** khi không ảnh nào có frame_index; cảnh báo thêm khi khoảng cách frame trung bình > 3 ("khá thưa…") |

## 3.5. Khung "Suy luận cắt lát (ảnh lớn)" — SAHI

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Bật suy luận cắt lát | Toggle | **Tắt** | Bật → mở 2 control dưới + hiện dòng cảnh báo hiệu năng |
| Cỡ ô *(Khuyến nghị: bằng cỡ ảnh vào model)* | Ô số nguyên, hậu tố " px" | **640**; min 64 – max 2048, bước 64 | Kích thước mỗi ô cắt; **disable khi SAHI tắt** |
| Tỉ lệ chồng lấn *(Tăng để bắt đối tượng sát biên ô)* | Thanh trượt + ô số | **0.2**; min 0 – max 0.5, bước 0.05 | Chồng lấn giữa các ô; **disable khi SAHI tắt** |
| Dòng cảnh báo hiệu năng | Nhãn mờ | Chỉ hiện khi bật | "Ảnh 4K với ô 640px tạo ~35 ô — chậm hơn ~10–30 lần so với suy luận thường." |

## 3.6. Khung "Plugin tinh chỉnh"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Chọn plugin | Combobox | **"Không dùng plugin"**; các mục: Chọn thông minh (SAM 2/SAM 1) / FastSAM / Florence-2 / SAM 3 Concept (prompt văn bản) / Grounding DINO | Đổi → hiện mô tả plugin + trạng thái cài đặt (xanh/vàng); plugin SAM → hiện thêm combobox trọng số SAM |
| Mô tả plugin | Nhãn động | "Chỉ dùng YOLO, không qua plugin." | Mô tả plugin đang chọn |
| Trọng số SAM | Combobox (**ẩn**, chỉ hiện khi chọn plugin SAM) | **SAM 2 Large (300 MB)**; lựa chọn: SAM 2 Large / SAM 2 Base (148 MB) / SAM 1 Base (366 MB) / SAM 1 Large (1.2 GB) / FastSAM Small (25 MB) / FastSAM XL (140 MB) | Đổi → lưu ngay vào cấu hình `sam.weights` (đã vá BUG-05) |
| Ô prompt | Ô text, placeholder "Mô tả bằng chữ, ví dụ: crack, rust, bolt" | **Chỉ hiện khi plugin nhận prompt** (FastSAM, Florence-2, G-DINO, SAM 3); ẩn khi không chọn plugin (đã vá BUG-06) | Truyền prompt văn bản cho plugin |
| Nhãn trạng thái plugin | Nhãn màu | Rỗng | Trạng thái cài đặt: đủ điều kiện (xanh) / thiếu gì (vàng, kèm lý do) |

## 3.7. Cột phải

| Vùng | Nội dung / Hành vi |
|---|---|
| Khung "Xem trước kết quả" | Vẽ ảnh + box/polygon màu theo class, nhãn "class conf"; trống → "Kết quả suy luận sẽ hiện ở đây"; cập nhật realtime khi đang chạy |
| Khung "Kết quả" | 5 chỉ số đều khởi đầu "0": Ảnh đã xử lý · Đối tượng sinh ra · Ảnh cần xem lại (vàng) · Dự đoán độ tin cậy thấp (đỏ) · Ảnh không có đối tượng (xám) |
| Nút "Mở trình sửa nhãn để xem lại" | Chuyển sang trang Editor |
| Khung "Nhật ký" | Log chỉ đọc, tự cuộn, xóa mỗi lần bắt đầu |
| Thanh tiến trình | "Đang gán nhãn {n} ảnh …" + % + nút Hủy; kết thúc "Gán nhãn hoàn tất" |

---

# 4. Trang Train Model

## 4.1. Header

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Mở thư mục huấn luyện | Nút (ghost, icon thư mục) | — | Mở thư mục `runs/` của project trong Explorer |
| Dừng | Nút (danger, icon stop) | **Disable mặc định**, chỉ enable khi đang train | Hủy train, trạng thái "Đang dừng …" |
| Bắt đầu huấn luyện | Nút (primary, icon play) | Disable khi đang train | Lưu cấu hình, xóa log + 2 biểu đồ, chạy train. Chặn khi: chưa mở project / đang chạy / **dưới 2 ảnh đã gán nhãn** ("Cần tối thiểu 2 ảnh đã gán nhãn để huấn luyện.") |

## 4.2. Khung "Model & dữ liệu"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nhiệm vụ | Combobox | **Segmentation**; Segmentation / Detection / OBB / Pose | Đổi → nạp lại danh sách model |
| Model | Combobox | Theo nhiệm vụ (MODEL_ZOO) | Model nền để train |
| Model riêng | Ô text, placeholder "Đường dẫn file .pt / .onnx" + nút duyệt (lọc PyTorch *.pt) | Rỗng | Có nội dung → **ghi đè** lựa chọn Model; sau khi train xong ô này tự điền đường dẫn `best.pt` vừa tạo |
| File data.yaml | Ô text, placeholder "Mặc định: tự sinh dataset.yaml" + nút duyệt (lọc *.yaml/*.yml) | Rỗng | Chọn file yaml → **tự tắt** toggle "Tự sinh dataset" |
| Tự sinh dataset từ project | Toggle | **Bật** | App tự export dataset YOLO từ project trước khi train |
| Chỉ huấn luyện trên ảnh đã duyệt | Toggle | **Tắt** | Lọc chỉ ảnh `approved` khi dựng dataset |

## 4.3. Khung "Siêu tham số"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Số epoch | Ô số nguyên | **100**; min 1 – max 5000, bước 10 | Số epoch train |
| Cỡ batch | Ô số nguyên | **16**; min 1 – max 512 | Batch size |
| Cỡ ảnh vào model | Ô số nguyên | **640**; min 128 – max 2048, bước 32 | imgsz |
| Patience | Ô số nguyên | **50**; min 0 – max 1000, bước 5 | Dừng sớm khi metric không cải thiện |
| Số worker | Ô số nguyên | **4**; min 0 – max 32 | Worker nạp dữ liệu |
| Learning rate (lr0) | Ô số thập phân (5 chữ số) | **0.01**; min 0.00001 – max 1.0, bước 0.001 | Tốc độ học ban đầu |
| Optimizer | Combobox | **Auto**; Auto / SGD / Adam / AdamW / NAdam / RMSProp | Bộ tối ưu |
| Thiết bị | Combobox | **Auto (ưu tiên GPU)** / CPU / CUDA:i | Thiết bị train |
| Tỷ lệ tập kiểm định | Thanh trượt + ô số | **0.2**; min 0.05 – max 0.5 | Tỉ lệ val khi tự dựng dataset |
| Bật tăng cường dữ liệu (Augmentation) | Toggle | **Bật** | Bật/tắt augmentation |
| Cache ảnh vào RAM | Toggle | **Tắt** | Cache dataset để train nhanh hơn |

## 4.4. Khung "Lịch sử huấn luyện"

Danh sách **chỉ đọc** 15 lần chạy gần nhất: `ngày • tên model • N epochs • mAP x.xxx • trạng thái` (icon màu: xong = xanh lá, đang chạy = xanh dương, lỗi = đỏ); tooltip = thư mục kết quả.

## 4.5. Cột phải — giám sát realtime (chỉ hiển thị)

| Vùng | Nội dung |
|---|---|
| Vòng tiến độ | % hoàn thành theo epoch |
| Bảng thông tin | Epoch `0 / 0` · Thời gian đã chạy `00:00:00` (đồng hồ cập nhật mỗi giây) · Ước tính còn lại `--:--:--` · Thiết bị · Trạng thái ("Sẵn sàng" → "Đang chuẩn bị ..." → tên giai đoạn → "Train hoàn tất." / "Đã dừng" / "Thất bại") |
| Biểu đồ "Chỉ số đánh giá" | 4 đường theo epoch: mAP50, mAP50-95, Precision, Recall |
| Biểu đồ "Hàm mất mát (Loss)" | box_loss, seg_loss, cls_loss theo epoch (chỉ vẽ khi ≠ 0) |
| Nhật ký huấn luyện | Log chỉ đọc; kết thúc ghi "Best weights: …"; lỗi ghi "LỖI: {msg}" |

---

# 5. Trang Annotation Editor

## 5.1. Header

| Control | Loại | Phím tắt | Hành vi |
|---|---|---|---|
| Gán nhãn ảnh này | Nút (ghost, icon đũa phép) | — | Suy luận YOLO riêng ảnh đang mở, thêm kết quả vào canvas; model chưa nạp → toast "Hãy nạp model ở trang Auto Label trước."; disable khi đang suy luận |
| Lưu | Nút (ghost, icon lưu) | Ctrl+S | Ghi toàn bộ annotation của ảnh vào DB + toast số đối tượng |
| Duyệt && sang ảnh sau | Nút (primary, icon check) | Enter | Lưu → duyệt ảnh (approved) → sang ảnh kế |

## 5.2. Cột trái — khung "Ảnh"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Bộ lọc | Combobox | **Tất cả**; Tất cả / Cần xem lại / Chưa gán nhãn / Đã duyệt | Nạp lại danh sách ảnh theo bộ lọc |
| Nút xóa ảnh (icon thùng rác) | Nút icon, phím **Shift+Del** | — | Hộp thoại xóa ảnh hiện tại (xem 5.2b) |
| Danh sách ảnh | Danh sách (chọn một) | — | Chọn → nạp ảnh + nhãn lên canvas |
| Chuột phải lên ảnh | Menu ngữ cảnh | — | "Xoá ảnh này khỏi project" / "Đánh dấu ảnh cần xem lại" / "Đánh dấu ảnh đã duyệt" |

**5.2b. Hộp thoại xóa ảnh** — "Xoá ảnh '{tên}' khỏi project?": 3 nút **Chỉ gỡ khỏi project** (giữ file) / **Xoá luôn file trên đĩa** / **Huỷ** (mặc định). Sau xóa tự chuyển sang ảnh kế.

## 5.3. Cột trái — khung "Lớp đối tượng"

| Control | Loại | Phím tắt | Hành vi |
|---|---|---|---|
| Danh sách lớp (icon màu) | Danh sách | Phím **1..9** chọn lớp thứ n **và gán ngay cho đối tượng đang chọn** | Chọn → đặt lớp vẽ hiện hành; **nháy đúp** → gán lớp cho các đối tượng đang chọn |
| Thêm lớp | Nút (ghost, icon +) | — | Hộp nhập "Tên lớp:" |
| Chuột phải lên lớp | Menu ngữ cảnh | — | Đổi tên / Đổi màu (color picker) / Ẩn-hiện / **Xoá lớp** (hỏi "Xoá lớp này và toàn bộ nhãn thuộc nó?") |

## 5.4. Thanh công cụ (8 nút chọn-một + nút lệnh)

| Công cụ | Phím | Hành vi |
|---|---|---|
| **Chọn** (mặc định) | V | Chọn/kéo đối tượng, kéo đỉnh chỉnh hình, nháy đúp cạnh thêm đỉnh |
| Chọn thông minh | Q | Nhấp điểm hoặc kéo khung để SAM tự khoanh vùng; hiện thanh chọn model SAM |
| Polygon | W | Bấm từng đỉnh; chuột phải/Enter đóng hình, Backspace bỏ đỉnh, Esc hủy |
| Hộp bao | — | Kéo tạo bbox |
| Cọ vẽ | B | Tô thêm vùng (Alt+cuộn đổi cỡ cọ); hiện thanh cỡ cọ |
| Tẩy | E | Xóa bớt vùng; tẩy giữa tạo **lỗ** trong mask |
| Cắt đôi | S | Kẻ đường cắt tách vùng làm hai |
| Di chuyển | giữ Space / chuột giữa | Pan ảnh |

| Nút lệnh | Phím | Hành vi |
|---|---|---|
| Gộp vùng | M | Gộp các vùng đang chọn thành một |
| Giản lược | — | Giảm số đỉnh polygon đang chọn (epsilon cố định 1.8) |
| Xoá đối tượng | Delete | Xóa đối tượng đang chọn |
| Hoàn tác / Làm lại | Ctrl+Z / Ctrl+Y (và Ctrl+Shift+Z) | Undo/Redo — nút tự mờ khi hết bước |
| Phóng to / Thu nhỏ / Vừa khung | Ctrl+= / Ctrl+- / Ctrl+0 | Zoom ×1.2, ×1/1.2, fit |
| (không nút) Chọn tất cả | Ctrl+A | Chọn mọi đối tượng trên ảnh |

## 5.5. Thanh tùy chọn công cụ (ẩn mặc định)

| Control | Loại | Mặc định/Phạm vi | Điều kiện hiện |
|---|---|---|---|
| Cỡ cọ / tẩy | Thanh trượt + ô số | **20**; min 2 – max 200 | Chỉ hiện khi dùng Cọ vẽ / Tẩy; giá trị được nhớ vào cấu hình |
| Mô hình SAM | Combobox | **SAM 2 Large (300 MB)**; 6 lựa chọn như mục 3.6 | Chỉ hiện khi dùng Chọn thông minh; lưu ngay vào cấu hình |
| Banner tiến độ SAM | Nhãn + progress 0–100 | Ẩn | Hiện khi đang tải model SAM / đang phân tích ảnh |

## 5.6. Thanh điều hướng dưới canvas

| Control | Phím | Hành vi |
|---|---|---|
| Ảnh trước / Ảnh sau | A / D | Chuyển ảnh trong danh sách đã lọc (kẹp ở 2 đầu) |
| Nhãn vị trí "0 / 0" | — | "{thứ tự} / {tổng}" |
| Nhãn zoom "100%" | — | Cập nhật theo mức zoom |

## 5.7. Cột phải

| Khung | Control | Hành vi |
|---|---|---|
| **Navigator** | Minimap cao 150px có khung viewport | Bấm điểm bất kỳ → canvas cuộn tới đó |
| **Đối tượng trên ảnh** | Danh sách chọn nhiều: `#n tên-lớp [T#track] · conf` (conf="manual" nếu vẽ tay; màu vàng nếu cần xem lại) | Chọn đồng bộ 2 chiều với canvas. Chuột phải → menu **kéo-thả được**: Xoá / Gộp vùng / Giản lược / Chuyển thành polygon / "Áp dụng sửa đổi cho track" (chỉ hiện khi đối tượng có track_id) |
| **Thuộc tính** | Lớp (combobox) | Đổi lớp cho đối tượng đang chọn; không chọn gì → đặt lớp vẽ hiện hành |
| | Độ tin cậy (ô số) | **1.0**; 0.0–1.0 bước 0.01; **disable khi không chọn đối tượng** |
| | Nhãn thông tin | 1 đối tượng: mã/track/số đỉnh/kích thước/diện tích; nhiều: số lượng + tổng diện tích |
| | Nút "Áp dụng sửa đổi cho track" | **Ẩn**; chỉ hiện khi chọn đúng 1 đối tượng có track_id → hỏi xác nhận rồi đổi lớp toàn track trong project |
| | Nút "Cần xem lại" / "Đã duyệt" | Đặt trạng thái cho các đối tượng đang chọn |
| **Hiển thị** | Hiện độ tin cậy (toggle, **Bật**) · Hiện tên lớp (toggle, **Bật**) · Độ đậm (thanh trượt, **0.35**; 0–0.9) | Tùy chỉnh cách vẽ trên canvas, lưu vào cấu hình |

Bố cục: 3 cột kéo giãn được bằng splitter (khởi tạo 240 / 850 / 310 px, không cột nào thu về 0).

---

# 6. Trang Dataset Manager

## 6.1. Header

| Control | Loại | Hành vi |
|---|---|---|
| Dọn dẹp | Nút (ghost, icon lấp lánh) | Mở menu dọn dẹp 6 mục (xem 6.5) |
| Mở trình sửa nhãn | Nút (primary) | Chuyển sang trang Editor |

## 6.2. Hàng 6 thẻ thống kê

| Thẻ | Màu | Bấm được? |
|---|---|---|
| Tổng số ảnh | tím | Không |
| Đã gán nhãn | xanh lá | **Có** → lọc "Đã gán nhãn" |
| Chưa gán nhãn | vàng | **Có** → lọc "Chưa gán nhãn" |
| Tổng đối tượng | xanh dương | Không |
| Số lớp | tím sáng | Không |
| Ảnh trùng | đỏ | **Có** → lọc "Trùng" |

## 6.3. Thanh lọc + tìm kiếm

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| 7 chip lọc | Chip chọn-một | **"Tất cả"** được chọn | Tất cả / Đã gán nhãn / Chưa gán nhãn / Cần xem lại / Đã duyệt / Trùng / Mờ |
| Ô tìm kiếm | Ô text có icon kính lúp + nút xóa, rộng 210px | Placeholder "Tìm theo tên file …" | Lọc realtime theo tên file (không phân biệt hoa thường), áp **sau** chip lọc |
| Cỡ thumbnail | Combobox 88px | **"Vừa" (150px)**; Nhỏ (118) / Vừa (150) / Lớn (198) | Đổi cỡ ô lưới ảnh |

## 6.4. Lưới ảnh + thao tác hàng loạt

| Control | Loại | Hành vi |
|---|---|---|
| Lưới thumbnail | Chọn nhiều (Ctrl/Shift), nạp lazy nền | **Nháy đúp** một ảnh → mở thẳng trong Editor |
| Nhãn chọn | "Chưa chọn ảnh nào" → "Đang chọn {n} ảnh" | — |
| Duyệt | Nút (ghost) | Duyệt hàng loạt ảnh chọn; chưa chọn → toast "Hãy chọn ảnh trước." |
| Đánh dấu xem lại | Nút (ghost) | Đặt "Cần xem lại" hàng loạt |
| Xoá | Nút (danger) | Hộp thoại: **Yes** = chỉ gỡ khỏi project / **Yes to All** = xóa cả file trên đĩa / **Cancel** (mặc định) |

## 6.5. Menu "Dọn dẹp" (6 mục)

| Mục | Xác nhận? | Hành vi |
|---|---|---|
| Xoá tất cả ảnh trùng | Có ("Xoá {n} ảnh trùng?") | Không có ảnh trùng → toast "Không có ảnh trùng nào." |
| Xoá ảnh mờ dưới ngưỡng | Có | Ngưỡng lấy từ cấu hình cắt frame (mặc định 60.0) |
| Xoá ảnh chưa gán nhãn | Có | Xóa khỏi project (không xóa file) |
| Gỡ ảnh không còn tồn tại trên ổ đĩa | **Không hỏi** — chạy ngay | Toast số ảnh đã gỡ |
| Tính lại số đối tượng | Không hỏi | Đếm lại `n_objects` toàn bộ ảnh |
| Sao lưu project | Không hỏi | Tạo backup ngay |

## 6.6. Cột phải — thống kê lớp (chỉ hiển thị)

| Khung | Nội dung |
|---|---|
| Đối tượng theo lớp | Biểu đồ cột ngang (chỉ lớp có đối tượng) |
| Tỷ lệ ảnh theo lớp | Biểu đồ donut, tâm hiện tổng số ảnh |
| Chi tiết từng lớp | Bảng chỉ đọc 6 cột: Lớp (tô màu) · Ảnh · Đối tượng · Mask · Diện tích TB (px²) · Độ phủ (%) |

---

# 7. Trang Statistics & Export

## 7.1. Header + cột chọn mục

| Control | Loại | Hành vi |
|---|---|---|
| Làm mới | Nút (ghost, icon refresh) | Tính lại toàn bộ số liệu/biểu đồ |
| Xuất dataset | Nút (primary) | Nhảy thẳng sang mục "Xuất dataset" |
| Cột "Mục" (6 tab con, chọn một) | **"Tổng quan"** chọn mặc định | Tổng quan / Phân bố lớp / Kích thước đối tượng / Bản đồ nhiệt / Chất lượng ảnh / Xuất dataset |

## 7.2. Mục "Tổng quan" (chỉ hiển thị)

4 thẻ: Tổng số ảnh · Tổng đối tượng · Tổng số mask · Đối tượng/ảnh (2 chữ số). Biểu đồ donut phân bố lớp; histogram diện tích (28 cột, đơn vị px²); thanh tiến độ gán nhãn nhiều màu + 4 chú giải (Đã duyệt/Cần xem lại/Máy gán nhãn/Chưa gán nhãn); bảng "Thông tin project" 9 dòng (tên, thư mục, loại bài toán, ngày tạo/cập nhật, số lớp, tổng diện tích mask, số track, độ dài track trung bình).

## 7.3. Mục "Phân bố lớp" / "Kích thước đối tượng" / "Chất lượng ảnh" (chỉ hiển thị)

- **Phân bố lớp**: cột dọc "Số đối tượng theo lớp"; cột ngang "Số ảnh chứa mỗi lớp"; cột ngang "Độ cân bằng dữ liệu" (% ảnh chứa lớp); histogram "Phân bố độ tin cậy" (20 cột, trục 0.0→1.0).
- **Kích thước**: histogram diện tích mask/box; histogram "Số đối tượng trên mỗi ảnh"; bảng thống kê 5 dòng (diện tích min/max, đối tượng/ảnh TB, nhiều nhất, tổng mask).
- **Chất lượng ảnh**: 4 thẻ Ảnh đạt chuẩn / Ảnh trùng lặp / Ảnh mờ / Ảnh thiếu sáng (ngưỡng lấy từ cấu hình cắt frame); histogram độ nét + histogram độ sáng (26 cột).

## 7.4. Mục "Bản đồ nhiệt"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Bản đồ nhiệt vị trí đối tượng | Heatmap | — | Mật độ tâm đối tượng trên khung chuẩn hóa |
| Độ phân giải lưới | Ô số nguyên | **24**; min 6 – max 64, bước 2 | Đổi → vẽ lại heatmap ngay |
| Bảng màu | Combobox | **Tím**; Tím / Nóng | Đổi màu heatmap ngay |

## 7.5. Mục "Xuất dataset"

**Chọn định dạng** — 7 chip chọn-một (mặc định theo Settings, gốc là **YOLO Segmentation**), mỗi chip có dòng mô tả khi chọn:

| Chip | Mô tả hiện ra |
|---|---|
| YOLO Segmentation | "Polygon chuẩn hoá — dùng cho model *-seg.pt" |
| YOLO Detection | "Bounding box chuẩn hoá: cx cy w h" |
| YOLO OBB | "Hộp xoay 4 đỉnh chuẩn hoá — dùng cho model *-obb.pt" |
| YOLO Pose | "Box kèm keypoint — dùng cho model *-pose.pt" |
| COCO JSON | "File instances.json chuẩn COCO, có cả keypoints" |
| Pascal VOC XML | "Một file .xml cho mỗi ảnh" |
| PNG Mask | "Ảnh mask 8-bit theo chỉ số lớp, kèm bản mask màu" |

**Khung "Cấu hình"**:

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Tên dataset | Ô text | **"dataset"** (rỗng → tự về "dataset") | Tên thư mục xuất |
| Thư mục xuất + nút duyệt | Ô text | Placeholder "Mặc định: thư mục exports của project" | Nơi ghi kết quả |
| Tỷ lệ tập kiểm định | Thanh trượt + ô số | **0.20**; min 0 – max 0.5 | val split (train = 1 − val − test) |
| Tỷ lệ tập kiểm tra | Thanh trượt + ô số | **0.00**; min 0 – max 0.3 | test split |
| Seed ngẫu nhiên | Ô số nguyên | **42**; min 0 – max 99999 | Cùng seed → cùng cách chia |
| Độ tin cậy tối thiểu | Thanh trượt + ô số | **0.00**; min 0 – max 0.99 | Bỏ nhãn dưới ngưỡng |
| Chỉ ảnh đã duyệt *(Bỏ qua ảnh máy gán/cần xem lại)* | Toggle | **Tắt** | Lọc `approved` |
| Loại ảnh trùng lặp | Toggle | **Bật** | Loại ảnh duplicate |
| Loại ảnh mờ | Toggle | **Tắt** | Loại ảnh dưới ngưỡng nét |
| Sao chép file ảnh *(Tắt để chỉ sinh file nhãn)* | Toggle | **Bật** | Copy ảnh vào dataset |
| Không chia train/val *(Xuất tất cả vào thư mục "all")* | Toggle | **Tắt** | Bố cục phẳng |

**Khung "Thực hiện"**: nút **Bắt đầu xuất** (disable khi đang xuất; đang chạy → toast "Đang xuất, vui lòng đợi."); nút **Mở thư mục kết quả** (**disable cho đến khi xuất xong**); ô nhật ký; thanh tiến trình + Hủy.

---

# 8. Trang Settings

*(Luôn dùng được kể cả chưa mở project)*

## 8.1. Header

| Control | Hành vi |
|---|---|
| Khôi phục mặc định | Hỏi "Đưa toàn bộ cài đặt về giá trị mặc định?" → reset + toast nhắc khởi động lại |
| Lưu cài đặt | Lưu toàn bộ form (kể cả form plugin đang mở), áp dụng ngôn ngữ/theme ngay, toast xác nhận |

## 8.2. Tab "Chung"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Ngôn ngữ | Combobox | **Tiếng Việt** / English | Đổi ngôn ngữ khi Lưu |
| Chủ đề | Combobox | **Tối** / Sáng / Theo hệ thống | Đổi theme khi Lưu |
| Màu nhấn | 8 ô màu 26×26 (ô đang chọn viền trắng) + nút "Màu khác…" (color picker) | Màu tím mặc định | Áp dụng sau khi khởi động lại (có ghi chú) |
| Thư mục project + nút duyệt | Ô text | Rỗng | Thư mục mặc định chứa project |
| Tự động lưu mỗi | Ô số nguyên, hậu tố " phút" | **5**; min 0 – max 120; **0 hiện chữ "Tắt"** | Chu kỳ autosave |
| Định dạng xuất mặc định | Combobox 7 định dạng | **YOLO Segmentation** | Quyết định chip chọn sẵn ở trang Export |
| Hỏi trước khi thoát | Toggle | **Bật** | Xác nhận khi đóng app |
| Mở lại project gần nhất khi khởi động | Toggle | **Bật** | Tắt → luôn mở màn hình trống |
| Đường dẫn hệ thống | Bảng chỉ đọc + 3 nút "Mở thư mục dữ liệu/nhật ký/trọng số" | — | Mở Explorer đúng thư mục |

## 8.3. Tab "Model"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Nhiệm vụ | Combobox | **Segment**; Detect/Segment/Obb/Pose | Nhiệm vụ mặc định |
| Chọn mô hình YOLO sẵn có | Combobox 7 preset | **YOLO11 Medium (50 MB)**; Nano 6MB → X-Large 120MB + 2 bản v8 | Chọn → tự điền ô "Tên tệp trọng số" |
| Tên tệp trọng số | Ô text | **yolo11m-seg.pt** | Gõ tay được tên khác |
| Model riêng + nút duyệt | Ô text, placeholder ".pt / .onnx / .engine" | Rỗng | Trọng số tùy chỉnh |
| Thiết bị | Combobox | **Auto (ưu tiên GPU)** / CPU / CUDA:i | Thiết bị mặc định |
| Cỡ ảnh vào model | Ô số nguyên | **640**; 128–4096, bước 32 | imgsz mặc định |
| Dùng FP16 *(Nhanh hơn trên GPU có tensor core)* | Toggle | **Tắt** | Half precision |
| Thiết bị hiện tại | Bảng chỉ đọc | — | CUDA khả dụng / Tên thiết bị / Số GPU / VRAM / Phiên bản torch / Phiên bản CUDA |

## 8.4. Tab "Suy luận"

| Control | Mặc định/Phạm vi |
|---|---|
| Độ tin cậy | **0.45**; 0.01–0.99 |
| IOU (khử trùng) | **0.5**; 0.05–0.95 |
| Ngưỡng cần xem lại | **0.6**; 0.05–0.99 |
| Ngưỡng tin cậy thấp | **0.35**; 0.01–0.9 |
| Số đối tượng tối đa | **1000**; 1–30000, bước 50 |
| Giản lược polygon | **0.0025**; 0–0.02, bước 0.0005 |
| Diện tích tối thiểu | **24 px**; 0–100000, bước 4 |
| Mask độ phân giải cao *(sắc nét hơn, chậm hơn chút)* | Toggle **Bật** |
| Khử trùng không phân biệt lớp | Toggle **Tắt** |
| Ghi đè nhãn đã có khi gán nhãn tự động | Toggle **Bật** |

## 8.5. Tab "Gán nhãn"

| Control | Mặc định/Phạm vi |
|---|---|
| Hiện độ tin cậy / Tô màu theo lớp / Hiện tên lớp / Tự chọn đối tượng vừa tạo | 4 toggle, đều **Bật** |
| Cỡ cọ vẽ | **20 px**; 2–300, bước 2 |
| Độ đậm vùng tô | **0.35**; 0–0.9 |
| Độ dày đường viền | **2**; 0.5–8, bước 0.5 |
| Cỡ điểm đỉnh | **6**; 2–16, bước 1 |

## 8.6. Tab "Plugin"

| Control | Loại | Hành vi |
|---|---|---|
| Bảng plugin 4 cột (Plugin/Loại/Trạng thái/Yêu cầu) | Bảng chỉ đọc, chọn hàng | Chọn → hiện chi tiết + form tham số; trạng thái tô xanh (sẵn sàng) / vàng (thiếu, kèm lệnh `pip install …`) |
| Quét lại plugin | Nút | Khám phá lại plugin (nhận plugin mới thả vào thư mục) |
| Mở thư mục plugin | Nút | Mở Explorer thư mục plugins |
| Form "Cấu hình tham số plugin" | **Form động theo từng plugin**: số nguyên/số thực (bước và số thập phân tự chỉnh theo độ lớn) / toggle / combobox / ô text, kèm dòng mô tả từng tham số | Lưu khi bấm "Lưu cài đặt" hoặc khi chuyển plugin khác |
| Khôi phục mặc định plugin | Nút (ẩn nếu plugin không có tham số) | Hỏi xác nhận → trả tham số plugin về mặc định |
| Khung "Tự viết plugin" | Nhãn hướng dẫn | Chỉ đọc |

## 8.7. Tab "Phím tắt" & "Giới thiệu"

- **Phím tắt**: bảng **chỉ đọc** 3 cột (Nhóm/Phím/Chức năng) — chưa gán lại phím trong UI được.
- **Giới thiệu**: logo, phiên bản, mô tả, bảng công nghệ, ghi chú giấy phép AGPL-3.0 — không có gì bấm được.

---

# 9. Trang Dashboard

## 9.1. Header

| Control | Hành vi |
|---|---|
| Mở project | Hộp thoại mở file `.alsdb` (bắt đầu tại thư mục project mặc định) |
| Tạo project mới | Mở hộp thoại tạo project (xem 9.5) |

## 9.2. Thẻ chào mừng

- Tiêu đề động: "Chào mừng đến với {app}" (chưa có project) / "Project: {tên}" + dòng phụ "… · Cập nhật: {giờ}".
- **5 chip hành động nhanh** (luôn bấm được, kể cả chưa mở project — trang đích tự xử lý): Nạp video → Import · Cắt frame → Extract · Gán nhãn tự động → Auto Label · Sửa nhãn → Editor · Xuất / Huấn luyện → Train.
- Vòng "Tiến độ gán nhãn": % = ảnh đã gán nhãn / tổng ảnh.

## 9.3. Bốn thẻ thống kê (đều bấm được)

| Thẻ | Bấm → đi đến |
|---|---|
| Tổng số ảnh | Dataset Manager |
| Đã gán nhãn | Editor |
| Đối tượng | Statistics |
| Số lớp | Statistics |

## 9.4. Hàng giữa & dưới

| Khung | Control | Hành vi |
|---|---|---|
| Project gần đây | Danh sách (tên + ngày giờ + dung lượng) | **Nháy đúp** → mở project. Chuột phải → Mở / Mở thư mục chứa project / **Bỏ khỏi danh sách** (không xóa file). Rỗng → dòng "Chưa có project nào…" (không bấm được) |
| Trạng thái dataset | Donut + thanh nhiều màu + 4 chú giải | Chỉ hiển thị |
| Hệ thống | Tên GPU (xanh lá nếu CUDA, vàng nếu CPU) + chi tiết + dòng "Model: chưa nạp / {tên model}" + nút **Kiểm tra lại thiết bị** | Nút → dò lại GPU và cập nhật |
| Hoạt động gần đây | Danh sách 30 dòng lịch sử (icon theo loại thao tác) | Chỉ đọc |

## 9.5. Hộp thoại "Tạo project mới"

| Control | Loại | Mặc định/Phạm vi | Hành vi |
|---|---|---|---|
| Tên project | Ô text, placeholder "Ví dụ: Railway Crack Detection" | Rỗng | Gõ → cập nhật dòng "Sẽ tạo tại: {đường dẫn}"; **để trống rồi bấm Tạo → toast "Tên project không được để trống"** |
| Thư mục lưu + nút Duyệt... | Ô text | Thư mục project mặc định | Nơi tạo thư mục project |
| Loại bài toán | Combobox | **Segmentation — mask polygon**; + Detection / OBB / Pose | Task của project (không đổi được sau khi tạo từ UI) |
| Mô tả | Ô text nhiều dòng, cao 72px | Rỗng (không bắt buộc) | Mô tả hiện ở Dashboard |
| Tạo project / Hủy | 2 nút | — | Tạo (kiểm tra tên sau khi đóng hộp thoại) / bỏ |

---

## Phụ lục A. Điều hướng & khung sườn chung

- Sidebar 9 mục = 9 trang, phím `Ctrl+1` … `Ctrl+9` theo đúng thứ tự; `F11` toàn màn hình; `Ctrl+Q` thoát (có hỏi nếu bật "Hỏi trước khi thoát").
- Mọi trang cần project mà chưa mở project → hiện màn hình 2 nút "Tạo project mới" / "Mở project có sẵn" (trừ Dashboard và Settings luôn dùng được).
- Kéo-thả file vào bất kỳ trang nào → tự chuyển sang Import.

