# Đặc tả dữ liệu và tiêu chí hoàn tất

## Đầu vào

- Một thư mục Google Drive, quét đệ quy bằng quyền chỉ đọc; ID file là khóa liên kết ổn định.
- Video có file phụ đề `.srt`/`.vtt` riêng được ghép với phụ đề theo manifest quét.
- Tài liệu PDF, DOCX, PPTX, TXT; file quảng cáo Khóa học giá hời bị loại.
- PDF ảnh được OCR cục bộ khi dùng `drive_documents.py --ocr`. Chữ OCR cần đối chiếu bản gốc.

## Đầu ra và tên file

`output_layout.py` tạo tên theo khóa học/chương/bài và kiểm tra đường dẫn trước khi ghi. File gốc trên Drive không bị đổi tên. Toàn bộ đầu ra riêng nằm trong `drive-reports/` và không đưa lên Git.

| Giai đoạn | Đường dẫn | Nội dung |
|---|---|
| Quét | `scan.json`, `scan.md` | Cây thư mục, metadata, cặp video/phụ đề |
| Trích nguồn | `transcripts/`, `documents/` | Văn bản và manifest trạng thái |
| Bài học | `lesson-packs/` | Markdown + JSON theo schema `lesson_pack.SCHEMA` |
| Bài học tách file | `lesson-artifacts/` | Transcript, summary, deep notes, concepts, timeline, quiz, metadata |
| Khóa học | `courses/` | Tóm tắt, bản đồ bài, đồ thị khái niệm, lộ trình, master notes, quiz |
| QA | `qa-report.json` | Kiểm tra lại quote, ID nguồn, coverage |
| Tìm kiếm | `knowledge.sqlite` | Bảng ảo SQLite FTS5 `chunks` |
| NotebookLM | `notebooklm-export/` | Markdown và manifest để nhập thủ công |

`lesson_pack.SCHEMA` yêu cầu `summary`, `objectives`, `concepts`, `steps`, `timeline`, `sections`, `must_remember`, `quiz`, `caveats`. Mọi khái niệm, bước, mục ghi chú, điều cần nhớ và câu hỏi có `source_refs` gồm `chunk_id` và quote nguyên văn. JSON bài học còn giữ `chunks`, `qa`, `meta` để kiểm tra lại và tái tạo đầu ra. Phiên bản prompt nằm trong `meta.prompt_id`; nguồn và prompt không đổi thì không gọi lại mô hình.

## Kiểm tra và trạng thái lỗi

- Tài liệu lưu manifest sau từng file. Các trạng thái gồm `ok`, `excluded`, `needs_ocr`, `too_large`, `unsupported`, `no_access`, `error`.
- Bài học được kiểm tra ID nguồn, quote, độ phủ phụ đề tối thiểu 85% và cấu trúc quiz. Lỗi được sửa tối đa hai lần; còn lỗi thì `needs_review`, không đưa vào tổng hợp khóa.
- `qa_report.py` kiểm toán lại đầu ra sau batch. Kiểm tra tự động không khẳng định độ chính xác ngữ nghĩa hoặc tính dễ đọc.
- Tìm kiếm chỉ lập chỉ mục chunk của bài đã qua QA. Câu trả lời AI bị từ chối nếu dẫn ID chunk không nằm trong nguồn truy xuất.
- Video không có file phụ đề riêng và không được chủ sở hữu cho tải được đánh dấu `no_source`; không suy đoán nội dung.

## Mốc kiểm thử

`python3 -m unittest discover -s tests -q` kiểm tra xử lý tên file, quét, phụ đề, tài liệu, gói bài, tổng hợp, tìm kiếm và API web. Dữ liệu mẫu `examples/agent_loop.srt` dùng cho demo offline. Thư mục Drive thực tế được dùng để kiểm tra luồng live, nhưng nội dung riêng không đưa vào repository.
