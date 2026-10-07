# tool-driver-summary

Công cụ quản lý nội dung học tập từ Google Drive trên máy cá nhân: quét video và tài liệu, đọc phụ đề, trích văn bản, tạo ghi chú có mốc thời gian và xem kết quả qua giao diện web. Dự án cũng có demo offline không cần tài khoản Google.

## Giao diện web quản lý

Sau khi đã quét Drive, mở giao diện trên máy:

```bash
python3 web_app.py
```

Truy cập **http://127.0.0.1:8765**. Giao diện có tổng quan, tìm kiếm và lọc video/tài liệu theo khóa học, mở phụ đề và văn bản đã trích, xem ghi chú, cùng lịch sử tác vụ. Từ giao diện có thể bấm quét lại Drive, đọc phụ đề, đọc tài liệu hoặc tạo ghi chú AI cho video có phụ đề riêng. Dùng `python3 web_app.py --port 8766` nếu cổng mặc định đang bận.

Web chỉ lắng nghe trên `127.0.0.1`. API chỉ đọc nội dung thuộc manifest; các nút xử lý chỉ chạy tác vụ đã định sẵn. `credentials.json` và `token.json` không được gửi cho trình duyệt. Đóng web bằng `Ctrl+C` trong terminal.

## Demo offline

```bash
python3 getsub_demo.py
python3 getsub_demo.py examples/agent_loop.srt --output demo-result.md
python3 getsub_demo.py examples/agent_loop.srt --ask "Khi công cụ thời tiết lỗi, agent nên làm gì?"
python3 -m unittest discover -s tests -v
```

Có thể thay tệp mẫu bằng phụ đề `.srt` hoặc `.vtt` của một bài giảng khác. Công cụ hiện trích nguyên văn tối đa 5 đoạn đầu vào phần tóm tắt, tạo timeline toàn bài và tìm đoạn nguồn phù hợp với câu hỏi. Nếu câu hỏi có khái niệm không xuất hiện trong transcript, công cụ báo thiếu bằng chứng.

## Quét thư mục Google Drive

`drive_scan.py` quét **đúng thư mục được chỉ định và các thư mục con**, chỉ đọc metadata. Báo cáo liệt kê video, tài liệu, file phụ đề riêng và đánh dấu file phụ đề có tên tương ứng với video. Shortcut được liệt kê nhưng không đi theo, để không ra ngoài phạm vi thư mục đã chọn.

Lần chạy trên tài khoản riêng cần OAuth Desktop credentials của chính bạn:

1. Trong Google Cloud Console, bật **Google Drive API** và tạo **OAuth client ID → Desktop app**.
2. Tải JSON về và đặt tên `credentials.json` trong thư mục dự án. Không gửi file này qua chat hoặc commit vào Git.
3. Cài thư viện và chạy lệnh bên dưới. Trình duyệt sẽ mở để bạn đăng nhập và cho phép quyền **chỉ đọc Drive**. Token lưu cục bộ trong `token.json`.

```bash
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH=.deps python3 drive_scan.py 'LINK_THU_MUC_DRIVE'
```

Kết quả nằm trong `drive-reports/scan.md` và `drive-reports/scan.json`. Cả credentials, token và báo cáo thật đều được `.gitignore` bỏ qua. Dùng `--max-files 2000` nếu thư mục có hơn 500 mục; chương trình sẽ báo lỗi rõ ràng khi chạm giới hạn thay vì xuất báo cáo thiếu.

Nếu trong thư mục có file phụ đề `.srt`/`.vtt` riêng, chạy tiếp:

```bash
PYTHONPATH=.deps python3 drive_process.py
```

Kết quả theo từng file nằm trong `drive-reports/transcripts/`; `manifest.json` ghi số đoạn, thời lượng và lỗi nếu có. Phần đầu mỗi file Markdown chỉ là 5 đoạn phụ đề đầu để kiểm tra, chưa phải bản tóm tắt toàn bài bằng AI.

Đọc văn bản từ các tài liệu PDF, DOCX và TXT trong báo cáo quét:

```bash
PYTHONPATH=.deps python3 drive_documents.py --max-mb 30
```

Kết quả nằm trong `drive-reports/documents/`. `manifest.json` được lưu sau từng file, ghi số ký tự, mã băm nội dung và trạng thái `needs_ocr` nếu PDF không trích được chữ. Lần chạy sau dùng lại những file đã đọc thành công; dùng `--refresh` để tải lại. `--max-mb` đặt giới hạn kích thước từng tài liệu; file lớn được tải theo từng phần.

## Tạo ghi chú AI bằng đăng nhập ChatGPT trong Codex CLI

Nếu máy đã chạy `codex login` và `codex login status` báo đăng nhập bằng ChatGPT, có thể dùng phiên đó qua Codex CLI. Đây không phải khóa API và chương trình Python không đọc token đăng nhập. Lệnh dưới chỉ gửi **nội dung phụ đề của bài được chọn** tới Codex, không gửi `credentials.json` hay `token.json`.

```bash
python3 codex_notes.py --check
python3 codex_notes.py --id ID_FILE_PHU_DE_TU_MANIFEST
# Sau khi kiểm tra bản thử, xử lý toàn bộ 26 bài có phụ đề riêng:
python3 codex_notes.py --all
```

Script tự tìm Codex CLI trong tiện ích VS Code nếu lệnh `codex` không có trong PATH. Nếu cài ở chỗ khác, thêm `--codex /duong/dan/toi/codex`. Ghi chú sinh ra ở `drive-reports/ai-notes/` và được kiểm tra để mốc thời gian khớp phụ đề. Dùng `--refresh` nếu muốn tạo lại. Các báo cáo và ghi chú được tạo từ Drive là dữ liệu riêng của người dùng, được giữ cục bộ trong `drive-reports/` và không đưa lên Git.

**Giới hạn hiện tại:** PDF chứa ảnh cần OCR. Drive API không có phương thức v3 để tải transcript đang hiện trong trình phát video, nên báo cáo không khẳng định video có hay không có transcript nhúng. Ghi chú AI cần kiểm tra lại các tên lệnh, API và thuật ngữ bị nhận dạng sai trong phụ đề.
