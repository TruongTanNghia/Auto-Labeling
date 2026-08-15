# Kế hoạch phát triển và kiểm thử tiếp theo (Context Document)

## 1. Tóm tắt trạng thái hiện tại

### Đã hoàn thành (Issue #2 & Issue #3):
- **Cấu hình tham số động plugin (Issue #2)**: Đã hoàn thiện khai báo schema cấu hình động cho cả 5 plugin và tích hợp vào giao diện Cài đặt.
- **Kiểm chứng Grounding DINO với trọng số thật**: Đã nạp thành công `IDEA-Research/grounding-dino-tiny` từ Hugging Face Hub và chạy suy luận end-to-end trên CPU (Thời gian nạp: 16.98s, Suy luận: 8.73s, phát hiện chính xác đối tượng).
- **Kiểm chứng Florence-2 với trọng số thật**: Đã vá các điểm chưa tương thích giữa mô hình `microsoft/Florence-2-base` và phiên bản thư viện hiện tại. Đã chạy suy luận thành công 100% trên CPU (Thời gian nạp: 10.05s, Suy luận: 86.31s).
- **SAM Refiner & FastSAM**: Đã được kiểm thử chạy ổn định với trọng số thật trước đó.

---

## 2. Các công việc cần làm trong đoạn chat tiếp theo

### Công việc 1: Kiểm thử SAM 3 Concept trên Google Colab (Khuyên dùng)
- **Lý do**: Tệp trọng số `sam3.pt` nặng ~3GB, việc tải và chạy suy luận trên GPU miễn phí của Google Colab (NVIDIA T4) chỉ mất vài giây đến vài chục giây, tránh quá tải cho CPU máy cục bộ.
- **Các bước thực hiện**:
  1. Sử dụng môi trường Colab GPU để tải tệp `sam3.pt` tốc độ cao.
  2. Nạp plugin `sam3_concept` hoặc mã nguồn kiểm thử và thực thi suy luận trên bộ ảnh mẫu.
  3. Ghi lại kết quả kiểm chứng (thời gian nạp, thời gian suy luận GPU, mức sử dụng VRAM) để phục vụ cho mô tả Pull Request.

### Công việc 2: Hoàn thiện mô tả Pull Request cho Issue #3
- **Mục tiêu**: Báo cáo đầy đủ kết quả thực nghiệm của cả 5 plugin đi kèm dự án.
- **Các bước thực hiện**:
  1. Tổng hợp bảng số liệu thực tế về thời gian nạp và thời gian suy luận của 5 plugin (`SAM Refiner`, `FastSAM`, `Grounding DINO`, `Florence-2`, `SAM 3 Concept`).
  2. Soạn nội dung Mô tả Pull Request chi tiết kèm hình ảnh/log kết quả để đóng Issue #3.

### Công việc 3: Lưu trữ cấu hình tham số động và cải thiện trải nghiệm
- **Mục tiêu**: Đảm bảo các tùy chỉnh tham số plugin từ giao diện Cài đặt được lưu lại bền vững giữa các phiên làm việc.
- **Các bước thực hiện**:
  1. Ghi nhận và đồng bộ các thay đổi tham số từ giao diện Settings vào tệp cấu hình ứng dụng.
  2. Bổ sung thông báo trạng thái hoặc thanh tiến trình rõ ràng khi ứng dụng đang thực hiện nạp mô hình nặng lần đầu.
