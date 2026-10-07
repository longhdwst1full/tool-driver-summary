# Kiến trúc và tiến độ

## Luồng xử lý

1. `drive_scan.py` dùng quyền Drive chỉ đọc để quét đúng thư mục gốc và các thư mục con. Kết quả là `scan.json` cùng `scan.md`; shortcut được liệt kê nhưng không truy theo.
2. `output_layout.py` tạo đường dẫn kết quả từ cấu trúc thư mục, tên bài và tên video. Mọi phần đường dẫn được chuẩn hóa và kiểm tra trước khi ghi file. ID Drive vẫn dùng trong manifest để liên kết ổn định khi tên hiển thị thay đổi.
3. `drive_process.py` tải 26 file phụ đề riêng đã phát hiện, phân tích mốc thời gian và lưu Markdown. `drive_documents.py` trích văn bản PDF, DOCX, TXT; bỏ qua tài liệu quảng cáo Khóa học giá hời và đánh dấu PDF ảnh là `needs_ocr`.
4. `codex_notes.py` tạo ghi chú AI từ phụ đề khi người dùng chạy lệnh hoặc chọn trên web. `study_pack.py` xây dựng chỉ mục mọi khóa học từ manifest và di chuyển các ghi chú mẫu cũ sang đường dẫn dễ đọc.
5. `web_app.py` cung cấp API cục bộ và giao diện `web/` để duyệt dữ liệu, đọc kết quả và chạy các tác vụ cố định. Web chỉ mở file được liệt kê trong manifest; OAuth credentials và báo cáo thật đều nằm ngoài Git.

## Các giai đoạn

| Giai đoạn | Trạng thái |
|---|---|
| Demo phụ đề offline và kiểm kê Drive | Hoàn thành |
| Trích phụ đề và tài liệu có văn bản | Hoàn thành |
| Giao diện quản lý cục bộ | Hoàn thành |
| Tên kết quả theo khóa học/chương/bài, lọc tài liệu quảng cáo, chỉ mục toàn bộ thư mục | Hoàn thành |
| OCR cho PDF chứa ảnh | Chưa triển khai |
| Transcript nhúng trong trình phát Drive và video không có file phụ đề riêng | Chưa được Drive API v3 cung cấp trực tiếp |

## Dữ liệu và giới hạn

`drive-reports/`, `.deps/`, `credentials.json` và `token.json` được `.gitignore` loại trừ. Không ghi vào Drive. Việc tạo ghi chú AI chỉ thực hiện cho bài có file phụ đề riêng; thông tin trong ghi chú cần đối chiếu lại với video khi dùng làm tài liệu chính thức.
