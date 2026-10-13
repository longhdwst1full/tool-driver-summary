# Kiến trúc và tiến độ

## Luồng xử lý

1. `drive_scan.py` dùng quyền Drive chỉ đọc để quét đúng thư mục gốc và các thư mục con. Kết quả là `scan.json` cùng `scan.md`; shortcut được liệt kê nhưng không truy theo.
2. `output_layout.py` tạo đường dẫn kết quả từ cấu trúc thư mục, tên bài và tên video. Mọi phần đường dẫn được chuẩn hóa và kiểm tra trước khi ghi file. ID Drive vẫn dùng trong manifest để liên kết ổn định khi tên hiển thị thay đổi.
3. `drive_process.py` đọc file phụ đề riêng, phân tích mốc thời gian và lưu Markdown. `drive_documents.py` trích văn bản PDF, DOC/DOCX, PPT/PPTX, TXT, Markdown và Google Docs; bỏ qua tài liệu quảng cáo và file khóa tạm Office, đánh dấu PDF ảnh là `needs_ocr`.
4. `codex_notes.py` tạo ghi chú AI từ phụ đề khi người dùng chạy lệnh hoặc chọn trên web. `study_pack.py` xây dựng chỉ mục mọi khóa học từ manifest và di chuyển các ghi chú mẫu cũ sang đường dẫn dễ đọc.
5. `chunking.py` chia phụ đề theo cửa sổ 5–8 phút và tài liệu theo đoạn văn, mỗi đoạn có `chunk_id` cố định để trích dẫn. `llm_client.py` gom lời gọi Codex CLI (`CodexCLIClient`) và prompt có version (`Prompt`); `codex_notes.py` dùng lại lớp này.
6. `lesson_pack.py` tạo gói bài học (tóm tắt, khái niệm, timeline, ghi chú chi tiết, cần nhớ, quiz) từ một phụ đề. Mỗi ý có `quote` nguyên văn; kiểm tra tự động đối chiếu quote với chunk, đo coverage, cho Codex sửa tối đa 2 lần rồi đánh dấu `needs_review`. Tài liệu đọc được trong cùng thư mục với video được thêm làm nguồn phụ (tối đa 12.000 ký tự); coverage chỉ tính trên phụ đề. Kết quả ở `drive-reports/lesson-packs/` dạng `.md` và `.json`, xem được trên web (tab Ghi chú hoặc chi tiết video).
7. `web_app.py` cung cấp API cục bộ và giao diện `web/` để duyệt dữ liệu, đọc kết quả và chạy các tác vụ cố định. Web chỉ mở file được liệt kê trong manifest; OAuth credentials và báo cáo thật đều nằm ngoài Git.
8. `batch_lessons.py` chạy lần lượt các bài có phụ đề, dùng cache của `lesson_pack.py` để tiếp tục sau gián đoạn. `lesson_artifacts.py` xuất từng phần của bài QA `ok` thành bảy tệp theo đặc tả MVP. `cross_source.py` đối chiếu phụ đề và tài liệu với quote hai phía, phân loại trùng/bổ sung/có thể mâu thuẫn. `course_synthesis.py` tổng hợp các bài QA `ok` thành sáu tệp cấp khóa, giữ ID nguồn và gắn cờ định nghĩa có thể mâu thuẫn.
9. `qa_report.py` kiểm toán lại trích dẫn và độ phủ của mọi gói bài học. `knowledge_search.py` lập chỉ mục MongoDB khi có `MONGODB_URI`, hoặc SQLite FTS5 trong demo cục bộ, từ chunk của bài QA `ok`; tìm kiếm hoặc gửi nguồn truy xuất cho Codex CLI trả lời có trích dẫn. `notebook_export.py` chuẩn bị gói Markdown để người dùng nhập vào NotebookLM. `finalize_pipeline.py` chạy các bước tạo đầu ra cuối theo thứ tự.

## Các giai đoạn

| Giai đoạn | Trạng thái |
|---|---|
| Demo phụ đề offline và kiểm kê Drive | Hoàn thành |
| Trích phụ đề và tài liệu có văn bản | Phụ đề hai nguồn mới đã xử lý; tài liệu nguồn thứ nhất còn chạy nền |
| Giao diện quản lý cục bộ | Hoàn thành |
| Tên kết quả theo khóa học/chương/bài, lọc tài liệu quảng cáo, chỉ mục toàn bộ thư mục | Hoàn thành |
| Trạng thái nguồn của video (`caption_file` / `asr_ready` / `no_source`), chia đoạn, lớp LLM | Hoàn thành |
| Gói bài học có dẫn nguồn và kiểm tra tự động | Hoàn thành 26/26 bài của nguồn demo ban đầu; các video ở hai nguồn mới chưa được chạy AI hàng loạt |
| Web duyệt theo khóa học/chương và xem Markdown | Hoàn thành |
| Đối chiếu nhiều nguồn trong một bài | Đã có báo cáo có quote hai phía cho 4 bài có tài liệu đi kèm; các cờ mâu thuẫn cần người xem lại |
| Tổng hợp nhiều bài thành kiến thức cấp khóa | Hoàn thành trên 26 bài QA `ok` của nguồn demo ban đầu; cần chạy lại sau khi có thêm bài QA `ok` |
| Trích văn bản PPTX | Đã triển khai; thư mục quét hiện không có PPTX để thử trực tiếp |
| OCR cho PDF chứa ảnh | Đã triển khai; nguồn thứ hai đã chạy OCR, nguồn thứ nhất chờ lượt đọc tài liệu hoàn tất |
| Gói xuất NotebookLM | Đã xuất 29 tệp Markdown và link 2 tài liệu gốc; nhập lên NotebookLM do người dùng thực hiện |
| Tìm kiếm và hỏi đáp có dẫn nguồn | Đã lập chỉ mục SQLite FTS5 với 79 đoạn nguồn và thử hỏi đáp có trích dẫn hợp lệ; backend MongoDB đã có code, chờ URI mới sau khi đổi mật khẩu |
| ASR cho video tải được | Chưa triển khai; cần kiểm tra quyền tải theo từng video trước khi chạy |
| Transcript trong trình phát Drive | Đã thử thu qua trình duyệt trên nguồn demo; chưa thu hàng loạt hai nguồn mới, Drive API v3 không xuất trực tiếp bản chép lời giao diện |

## Dữ liệu và giới hạn

`drive-reports/`, `.deps/`, `credentials.json` và `token.json` được `.gitignore` loại trừ. Không ghi vào Drive. Hai nguồn mới đã quét xong: nguồn thứ nhất có 67.562 video và 2.142 file phụ đề riêng (2.022 đọc được, 12 văn bản không mốc, 108 file trống); nguồn thứ hai có 24.200 video và 56 file phụ đề riêng (54 đọc được, 2 văn bản không mốc). File phụ đề không tự chứng minh video tương ứng đã có bài học AI; chỉ các bài có ghi chú và QA hợp lệ mới được tổng hợp. OCR cho PDF ảnh chạy cục bộ, có thể sai chữ. QA tự động kiểm tra quote và độ phủ, còn tính đúng ngữ nghĩa cần xem lại với nguồn.
