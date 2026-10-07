# tool-driver-summary

Công cụ quản lý nội dung học tập từ Google Drive trên máy cá nhân: quét video và tài liệu, đọc phụ đề, trích văn bản, tạo ghi chú có mốc thời gian và xem kết quả qua giao diện web. Dự án cũng có demo offline không cần tài khoản Google.

## Giao diện web quản lý

Sau khi đã quét Drive, mở giao diện trên máy:

```bash
python3 web_app.py
```

Truy cập **http://127.0.0.1:8765**. Video được duyệt theo khóa học rồi theo chương; chọn bài để mở video gốc, phụ đề và ghi chú. Các file Markdown được xem dưới dạng trang đọc có tiêu đề, danh sách và bảng. Giao diện còn có tài liệu, ghi chú, lịch sử tác vụ và các nút quét Drive, đọc phụ đề, đọc tài liệu, tạo ghi chú AI hoặc gói bài học cho video có phụ đề riêng. Dùng `python3 web_app.py --port 8766` nếu cổng mặc định đang bận.

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

Kết quả theo từng file nằm trong `drive-reports/transcripts/<tên khóa học>/<tên chương>/<tên video>.md`; `manifest.json` ghi số đoạn, thời lượng và lỗi nếu có. Phần đầu mỗi file Markdown chỉ là 5 đoạn phụ đề đầu để kiểm tra, chưa phải bản tóm tắt toàn bài bằng AI.

Đọc văn bản từ các tài liệu PDF, DOCX và TXT trong báo cáo quét:

```bash
PYTHONPATH=.deps python3 drive_documents.py --max-mb 30
```

Kết quả nằm trong `drive-reports/documents/<tên khóa học>/<tên chương>/<tên tài liệu>.txt`. `manifest.json` được lưu sau từng file, ghi số ký tự, mã băm nội dung và trạng thái `needs_ocr` nếu PDF không trích được chữ. Các tài liệu quảng cáo “Các khóa học thuộc về Khóa học giá hời” được đánh dấu `excluded`, không tải lại và không xuất hiện trong thư viện học tập. Lần chạy sau dùng lại những file đã đọc thành công; dùng `--refresh` để tải lại. `--max-mb` đặt giới hạn kích thước từng tài liệu; file lớn được tải theo từng phần.

Tạo lại chỉ mục liên kết video, phụ đề, tài liệu và ghi chú của mọi khóa học:

```bash
python3 study_pack.py
```

Chỉ mục nằm tại `drive-reports/study-notes/index.md`. Tên file kết quả theo tên khóa học, chương, bài hoặc video trên Drive; nếu trùng tên, chương trình thêm một phần ngắn của ID để tránh ghi đè. File gốc trên Drive không bị đổi tên. Khi xử lý từ giao diện web, chỉ mục được cập nhật sau tác vụ thành công.

## Tạo ghi chú AI bằng đăng nhập ChatGPT trong Codex CLI

Nếu máy đã chạy `codex login` và `codex login status` báo đăng nhập bằng ChatGPT, có thể dùng phiên đó qua Codex CLI. Đây không phải khóa API và chương trình Python không đọc token đăng nhập. Lệnh dưới chỉ gửi **nội dung phụ đề của bài được chọn** tới Codex, không gửi `credentials.json` hay `token.json`.

```bash
python3 codex_notes.py --check
python3 codex_notes.py --id ID_FILE_PHU_DE_TU_MANIFEST
# Sau khi kiểm tra bản thử, xử lý toàn bộ 26 bài có phụ đề riêng:
python3 codex_notes.py --all
```

Script tự tìm Codex CLI trong tiện ích VS Code nếu lệnh `codex` không có trong PATH. Nếu cài ở chỗ khác, thêm `--codex /duong/dan/toi/codex`. Ghi chú sinh ra ở `drive-reports/ai-notes/` và được kiểm tra để mốc thời gian khớp phụ đề. Dùng `--refresh` nếu muốn tạo lại. Các báo cáo và ghi chú được tạo từ Drive là dữ liệu riêng của người dùng, được giữ cục bộ trong `drive-reports/` và không đưa lên Git.

## Gói bài học có dẫn nguồn

`lesson_pack.py` chia phụ đề thành các đoạn có ID, đưa tài liệu đọc được cùng thư mục vào làm nguồn phụ, rồi tạo tóm tắt, mục tiêu, khái niệm, các bước thực hành, timeline và câu hỏi ôn tập. Các trích dẫn được đối chiếu với nguồn; kết quả cần xem lại được đánh dấu `needs_review`.

```bash
python3 lesson_pack.py --id ID_FILE_PHU_DE_TU_MANIFEST
```

Kết quả Markdown và JSON nằm trong `drive-reports/lesson-packs/` theo tên khóa/chương/bài. Chạy lại cùng nguồn sẽ dùng bản đã có; `--refresh` tạo lại và `--rerender` chỉ dựng lại Markdown từ JSON đã lưu. Chức năng này dùng phiên đăng nhập Codex CLI hiện tại và chỉ áp dụng cho bài có file phụ đề riêng.

**Giới hạn hiện tại:** PDF chứa ảnh cần OCR. Drive API không có phương thức v3 để tải transcript đang hiện trong trình phát video, nên báo cáo không khẳng định video có hay không có transcript nhúng. Ghi chú AI cần kiểm tra lại các tên lệnh, API và thuật ngữ bị nhận dạng sai trong phụ đề.
