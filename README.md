# tool-driver-summary

Công cụ quản lý nội dung học tập từ Google Drive trên máy cá nhân: quét video và tài liệu, đọc phụ đề, trích văn bản, tạo ghi chú có mốc thời gian và xem kết quả qua giao diện web. Dự án cũng có demo offline không cần tài khoản Google.

Xem [đặc tả dữ liệu và tiêu chí kiểm tra](SPECIFICATION.md) cùng [kiến trúc và tiến độ](ARCHITECTURE.md).

## Giao diện web quản lý

Sau khi đã quét Drive, mở giao diện trên máy:

```bash
python3 web_app.py
```

Truy cập **http://127.0.0.1:8765**. Video được duyệt theo khóa học rồi theo chương; chọn bài để mở video gốc và tóm tắt AI đã kiểm tra nguồn. Khi bài mới có bản chép lời mà chưa được AI xử lý, web hiển thị trạng thái chờ tóm tắt; bản chép lời chỉ mở bằng nút riêng để đối chiếu. Tab **Khóa học yêu thích** có bốn khóa mới, bài học vừa mở (lưu trong trình duyệt, hoặc đồng bộ qua MongoDB khi bật đăng nhập) và tìm tên khóa học trên tất cả nguồn đã quét. Tài liệu PDF, Word, PowerPoint, HTML và bảng tính có trang xem riêng `/viewer`: bản gốc Drive ở bên trái, văn bản trích xuất được định dạng ở bên phải; nút **Xem trang riêng** mở tab mới. Tệp gốc chỉ hiện nếu trình duyệt đã đăng nhập Google có quyền xem. Giao diện còn có lịch sử tác vụ và các nút quét Drive, đọc phụ đề, đọc tài liệu, tạo ghi chú AI hoặc gói bài học cho video có phụ đề riêng. Dùng `python3 web_app.py --port 8766` nếu cổng mặc định đang bận.

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

Hai nguồn “Khóa Học Giá Hời 2026” được quét riêng bằng `--curated-exclusions` và `--output-dir drive-reports/new-sources/<ID>`. Dùng `--workers 3` để quét song song với ba kết nối Drive riêng (tối đa 4). Bộ lọc không duyệt sâu các nhánh Dựng phim và Nhiếp ảnh, Thiết kế đồ họa, Tin học văn phòng, “15. Quà tặng: tài nguyên”, và khóa “Khóa Học Suno AI – Biến Ý Tưởng Thành Âm Nhạc”; trong “Khóa học khác” bỏ Âm nhạc, Guitar, Làm nhạc, Piano, Sức khỏe/Làm đẹp. File nhóm Zalo và file quảng bá khóa học giá hời cũng bị loại. Khi tiếp tục từ checkpoint cũ, các mục thuộc nhánh mới bị loại sẽ được gỡ khỏi kết quả. `scan.checkpoint.json` lưu điểm tiếp tục sau mỗi 20 thư mục; chạy lại cùng lệnh nếu Drive trả lỗi tạm thời. Mục **Nguồn Drive mới** trên web cho phép duyệt cây thư mục khi quét và sau khi hoàn tất, tìm kiếm và lọc thư mục/video/tài liệu trong toàn bộ nhánh đang mở, đồng thời đánh dấu video đã có trong thư viện Vibe Coding cũ. Mục “Đọc hướng dẫn trước khi học” được đặt trước các thẻ khóa học/chương. Chọn video để xem trong trình phát nhúng; trình duyệt cần đăng nhập tài khoản có quyền xem file Drive đó.

Nếu đang chạy bản thử trong nền, xem tiến độ bằng `systemctl --user status tool-getsub-source-a-process-suno tool-getsub-source-a-ocr tool-getsub-web` hoặc `journalctl --user -u tool-getsub-source-a-process-suno -f`. Nguồn thứ nhất có hơn 100.000 mục nên lượt quét dùng `--max-files 500000`. Máy dùng HTTP proxy cần cài `PySocks` từ `requirements.txt` để Google API đi qua proxy. `scan.json` là dữ liệu quét chính; `scan.md` là báo cáo có thể tạo lại, có thể xóa để tiết kiệm dung lượng.

Năm khóa học bổ sung (Afa Wealth Intelligence, Product Management 101, CAPM, AI For PM 2026 và Project Manager công ty phần mềm) cũng nằm trong mục **Nguồn Drive mới**. Bản tổng quan sơ bộ theo khóa/chương và trạng thái nguồn ở `drive-reports/new-courses-overview.md`. Tóm tắt bài từ bản chép lời giao diện, nếu thu đủ đầu/cuối, nằm trong `drive-reports/new-sources/<ID>/progressive-demo/`; báo cáo phân biệt rõ chúng với tổng quan chỉ dựa trên tài liệu hoặc tên bài. Video không có quyền tải qua Drive API không được đưa vào ASR.

Đợt ưu tiên công nghệ thông tin, kinh doanh và đầu tư trong hai nguồn lớn được chạy bằng `python3 priority_courses.py --limit-per-course 2`. Lệnh kiểm tra trực tiếp hai video đầu của 12 khóa được chọn theo ID thư mục Drive, hoàn thành lượt thu lời của các khóa trước rồi mới chạy prompt tóm tắt AI có dẫn nguồn. Lỗi của một bài được ghi riêng để các khóa còn lại tiếp tục; hết hạn mức Codex CLI thì dừng gọi AI và giữ bản chép lời. Xem danh sách bằng `python3 priority_courses.py --dry-run`, kiểm kê ba nhóm bằng `PYTHONPATH=.deps python3 audit_priority_transcripts.py` và tiến độ ở `drive-reports/priority-courses.json`. Có thể chạy riêng `--phase capture` hoặc `--phase summary`, tăng `--limit-per-course` sau khi đối chiếu đợt đầu. Báo cáo phân biệt video chưa mở trên Drive với video có panel transcript không khả dụng; metadata không chứng minh video có bản chép lời trong giao diện Drive.

Toàn bộ 25.517 video của ba nhóm trong hai nguồn dùng hàng đợi SQLite tại `drive-reports/full-priority-queue.sqlite`. Lệnh `python3 full_priority_queue.py --phase status` cho biết số video đã thu lời và đã tóm tắt. Hai tác vụ nền chạy riêng để bản chép lời hợp lệ được tóm tắt dần, không phải chờ quét hết: `tool-getsub-priority-capture-2.service` chạy `PYTHONPATH=.deps python3 full_priority_queue.py --phase capture --workers 6`, còn `tool-getsub-priority-summary-auto.service` chạy `PYTHONPATH=.deps python3 run_priority_summaries.py --workers 2`. Lịch thu lời luân phiên nhóm IT, kinh doanh và đầu tư, hai nguồn và các khóa học; 336 video ưu tiên vẫn chạy trước. Hàng đợi tóm tắt cân bằng theo nhóm, và 20 video Suno trong bản kiểm kê cũ được đánh dấu `excluded`. Worker AI khóa chống chạy trùng, dừng khi hết hạn mức Codex và được systemd thử lại sau một giờ. Xem log bằng `journalctl --user -u tool-getsub-priority-capture-2.service -n 30 --no-pager` hoặc đổi tên service sang `tool-getsub-priority-summary-auto.service`. Nếu `journalctl -f` báo thiếu watch descriptor, lệnh `-n --no-pager` vẫn đọc được log. Có thể thử một video bằng `--limit 1` và kiểm tra lại video lỗi/panel chưa khả dụng bằng `--phase capture --retry-unavailable`. Chrome thu lời tắt mô hình AI cục bộ để tránh tự tải gói CRX nhiều GB; thư mục tạm của mỗi phiên nằm trong profile tạm và được xóa khi phiên kết thúc. Trạng thái `panel_unavailable` chỉ nói phiên Chrome lúc đó không mở được bản chép lời.

Thu bản chép lời hiển thị trên Drive cho cả năm khóa (không gọi AI, có thể tiếp tục từ manifest sau khi gián đoạn):

```bash
python3 run_new_source_capture.py --workers 2
```

Kết quả nằm tại `drive-reports/new-sources/<ID>/ui-transcripts/`; tiến độ từng khóa ở `batch-manifest.json` cùng thư mục và trên trang **Nguồn Drive**. Chạy `python3 batch_ui_lessons.py --source-id <ID> --workers 1 --ai` để dùng prompt trong `progressive_demo.py` tạo tóm tắt, các ý chính và câu hỏi ôn tập có dẫn nguồn. File kết quả nằm ở `drive-reports/new-sources/<ID>/progressive-demo/` và là nội dung mặc định trên web khi đã qua kiểm tra. Trạng thái `ai_waiting` nghĩa là **đã có bản chép lời**, chỉ đang chờ hạn mức Codex CLI; `failed` cần xem lỗi trong manifest. Cửa sổ Chrome chạy ngầm và dùng bản sao profile đã đăng nhập.

Phụ đề và tài liệu trích xuất của từng nguồn nằm trong `drive-reports/new-sources/<ID>/transcripts/` và `documents/`. Web cho mở các file có trạng thái `ok` ngay trong trang đọc và lọc riêng file phụ đề. File `.txt` không có mốc thời gian được lưu và hiển thị như văn bản đi kèm (`untimed_text`), không tính là bản chép lời video; file phụ đề 0 byte được đánh dấu `empty`. Phụ đề được ghép vào video khi tên bài chuẩn hóa trùng duy nhất trong cùng thư mục chương, kể cả kiểu `1. Bài.srt` và `Bài 01 Bài.mp4`; các bản `_en` và `_vi` cùng bài đều được nối với video, và web ưu tiên bản tiếng Việt. Trường hợp tên video không duy nhất vẫn để phụ đề riêng. Bộ đọc nhận SRT có dòng trống sau số thứ tự; với đoạn có mốc bắt đầu bằng mốc kết thúc, bộ đọc thêm 1 ms để giữ nội dung đoạn. Manifest phụ đề được lưu mỗi 20 file và manifest tài liệu mỗi 50 file để tiếp tục sau gián đoạn. Tác vụ nền `tool-getsub-source-a-process-suno` đợi nguồn thứ nhất quét xong rồi đọc phụ đề và tài liệu. Xem tiến độ bằng `systemctl --user status <tên-tác-vụ>` hoặc mở mục **Nguồn Drive mới** trên web.

Nếu trong thư mục có file phụ đề `.srt`/`.vtt` riêng, chạy tiếp:

```bash
PYTHONPATH=.deps python3 drive_process.py
```

Kết quả theo từng file nằm trong `drive-reports/transcripts/<tên khóa học>/<tên chương>/<tên video>.md`; `manifest.json` ghi số đoạn, thời lượng và lỗi nếu có. Phần đầu mỗi file Markdown chỉ là 5 đoạn phụ đề đầu để kiểm tra, chưa phải bản tóm tắt toàn bài bằng AI.

## Bản thử đọc transcript giao diện và phân tích theo đoạn

Nếu chủ sở hữu cho phép trích xuất bản chép lời đang hiển thị trong Drive, xem [hướng dẫn thử một video](browser-demo/README.md). Có thể thu bằng tab Chrome đang mở hoặc chạy `browser-demo/background_capture.py` trong một phiên Chrome headless riêng để tiếp tục dùng máy. Bộ nhập kiểm tra JSON và chuyển thành SRT trong `drive-reports/ui-transcripts/`. Hãy kiểm tra đầu và cuối bản thu với video trước khi dùng cho AI; công cụ không tự khẳng định đã lấy đủ mọi câu chỉ từ việc chạm đáy panel.

Với phụ đề riêng đã xử lý, hoặc SRT giao diện đã kiểm tra, thử cách phân tích từng đoạn và tạo ghi chú có trích dẫn:

```bash
python3 progressive_demo.py --id ID_FILE_PHU_DE_TU_MANIFEST
python3 progressive_demo.py --ui-video-id ID_VIDEO_TRONG_SCAN
```

Kết quả nằm trong `drive-reports/progressive-demo/` theo khóa học/chương/bài. JSON lưu các điểm kiến thức và câu trích nguồn; Markdown tổng hợp sau khi toàn bộ đoạn đã được đọc.

Để xử lý tiếp các video chưa có file phụ đề trong bản quét hiện tại, chạy `python3 batch_ui_lessons.py --workers 2 --ai`. Lệnh dùng Chrome chạy ngầm, tự bỏ qua bản thu và ghi chú đã hợp lệ, rồi ghi tiến độ vào `drive-reports/ui-transcripts/batch-manifest.json`. Có thể thử một khóa học trước bằng `--course 'Tên khóa học' --limit 1`; mở web để xem tiến độ và bài học đã hoàn tất. Bản thu không đủ mốc đầu/cuối và ghi chú thiếu dẫn nguồn sẽ được ghi lỗi để chạy lại, không được coi là bài học hoàn tất.

Nếu Codex CLI báo hết hạn mức, bản chép lời đã thu vẫn hiện trong web theo khóa học/chương với trạng thái `ai_waiting`. Lệnh dừng gọi AI cho các bài còn lại trong lượt đó; chạy lại `python3 batch_ui_lessons.py --workers 2 --ai` khi hạn mức phục hồi. Dùng `python3 batch_ui_lessons.py --missing-only --workers 2` để thử thu lại các video chưa có bản chép lời mà không gọi AI, hoặc `python3 batch_ui_lessons.py --reconcile-only` để chỉ cập nhật trạng thái từ kết quả đã lưu.

Đọc văn bản từ các tài liệu PDF, DOC/DOCX, PPT/PPTX, HTML, XLSX/XLSM/XLS, TXT, Markdown, Google Docs và Google Sheets trong báo cáo quét. Máy cần `catdoc` cho Word cũ, LibreOffice cho PowerPoint cũ và Excel `.xls`; `.xlsx`/`.xlsm` dùng `openpyxl`. Google Sheets xuất CSV của trang tính đầu:

```bash
PYTHONPATH=.deps python3 drive_documents.py --max-mb 30
PYTHONPATH=.deps python3 drive_documents.py --max-mb 30 --ocr
```

Kết quả nằm trong `drive-reports/documents/<tên khóa học>/<tên chương>/<tên tài liệu>.txt`. `manifest.json` được lưu mỗi 50 file và lúc kết thúc, ghi số ký tự, mã băm nội dung và trạng thái `needs_ocr` nếu PDF không trích được chữ. Thêm `--ocr` để xử lý PDF ảnh bằng Tesseract cùng gói ngôn ngữ `vie` và `eng` (cài `tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng` trên Linux). File `.doc` thực tế là HTML được đọc như văn bản; Google Docs được xuất bằng Drive API. Tài liệu quảng cáo “Các khóa học thuộc về Khóa học giá hời” và file khóa tạm Office được đánh dấu `excluded`, không tải lại và không xuất hiện trong thư viện học tập. Lần chạy sau dùng lại những file đã đọc thành công; dùng `--refresh` để tải lại. `--max-mb` đặt giới hạn kích thước từng tài liệu; file lớn được tải theo từng phần.

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
python3 batch_lessons.py
python3 lesson_artifacts.py
python3 cross_source.py
```

Kết quả Markdown và JSON nằm trong `drive-reports/lesson-packs/` theo tên khóa/chương/bài. `lesson_artifacts.py` tách các bài QA `ok` thành `transcript.md`, `summary.md`, `deep_notes.md`, `concepts.json`, `timeline.json`, `quiz.json`, `metadata.json` trong `drive-reports/lesson-artifacts/`. Chạy lại cùng nguồn sẽ dùng bản đã có; `--refresh` tạo lại và `--rerender` chỉ dựng lại Markdown từ JSON đã lưu. Chức năng này dùng phiên đăng nhập Codex CLI hiện tại và chỉ áp dụng cho bài có file phụ đề riêng.

`cross_source.py` đối chiếu phụ đề với tài liệu đi kèm của cùng bài, phân loại nội dung trùng, bổ sung và có thể mâu thuẫn. Mỗi cặp phải có quote nguyên văn từ cả hai phía; báo cáo ở `drive-reports/cross-source/`, được kiểm kê riêng trong `qa-report.json` và trang review mở được từ mục Ghi chú trên web. Cờ mâu thuẫn là điểm cần người học kiểm tra, chưa phải kết luận hai nguồn chắc chắn sai nhau.

## Tổng hợp khóa học, tìm kiếm và NotebookLM

Sau khi batch tạo bài hoàn tất, chạy một lệnh để kiểm toán và tạo lại toàn bộ đầu ra:

```bash
python3 finalize_pipeline.py
```

Có thể chạy từng bước khi cần:

```bash
python3 course_synthesis.py
python3 qa_report.py
python3 knowledge_search.py build
python3 knowledge_search.py search 'từ khóa cần tìm' --limit 5
python3 knowledge_search.py ask 'Câu hỏi về khóa học?'
python3 notebook_export.py
```

`course_synthesis.py` tạo `course_summary.md`, `course_map.json`, `concept_graph.json`, `learning_path.md`, `master_notes.md` và `course_quiz.json` trong `drive-reports/courses/<tên khóa>/`. Công cụ chỉ tổng hợp bài đã qua QA, giữ ID đoạn nguồn trong JSON và đánh dấu các định nghĩa khác nhau để người dùng đối chiếu. Bản tổng hợp xuất hiện trong mục **Ghi chú** trên web.

`knowledge_search.py` tạo chỉ mục từ đoạn nguồn của các bài đã qua QA. Khi có `MONGODB_URI`, công cụ dùng MongoDB Atlas; khi chưa cấu hình, bản demo vẫn dùng SQLite FTS5 cục bộ. Lệnh `ask` dùng Codex CLI để trả lời và từ chối ID trích dẫn không có trong các đoạn truy xuất. Chỉ mục cần xây lại sau khi có thêm bài. `notebook_export.py` tạo thư mục Markdown theo khóa ở `drive-reports/notebooklm-export/`; `manifest.json` còn liệt kê link tài liệu gốc đi kèm. Nhập các nguồn này bằng giao diện NotebookLM bằng tài khoản của bạn. Dự án chưa tự tải nội dung lên NotebookLM.

Để dùng Atlas, **đổi mật khẩu đã chia sẻ trong chat**, bảo đảm IP máy được phép trong Atlas Network Access, rồi đặt URI mới qua biến môi trường `MONGODB_URI` trong terminal riêng hoặc file `.env` cục bộ (file này đã bị `.gitignore` loại trừ). Cài lại `requirements.txt`, sau đó chạy `python3 knowledge_search.py build --backend mongo`. Tên database mặc định là `tool_driver_summary`; có thể đổi bằng `MONGODB_DATABASE`. Không ghi URI vào source, README, log hoặc Git. Nếu chưa cấu hình URI, dùng `--backend sqlite` để thử cục bộ.

Đồng bộ danh mục và nội dung đã kiểm tra sang MongoDB bằng `PYTHONPATH=.deps python3 mongo_migrate.py`; chạy lại sau mỗi đợt có bản chép lời hoặc bài AI mới. Web tự đọc DB khi `MONGODB_URI` có trong môi trường của tiến trình web và tự đọc local nếu DB tạm lỗi. Lịch sử bài gần đây được đồng bộ giữa các thiết bị dùng cùng tài khoản khi bật `WEB_PASSWORD_HASH` và DB sẵn sàng. Cấu hình đăng nhập và HTTPS ở [MONGODB_PLAN.md](MONGODB_PLAN.md). Chưa có kết nối Atlas thật trên máy này vì `MONGODB_URI` mới chưa được đặt.

Lệnh `batch_lessons.py` có thể chạy lại sau khi gián đoạn; bài có nguồn và prompt không đổi sẽ được dùng lại. Dùng `--course 'Tên khóa'` hoặc `--limit 3` để thử một phần trước khi xử lý toàn bộ.

**Giới hạn hiện tại:** Video chủ sở hữu tắt quyền tải không thể đưa qua ASR. Drive API không có phương thức v3 để tải transcript đang hiện trong trình phát video, nên báo cáo không khẳng định video có hay không có transcript nhúng. OCR có thể nhận dạng sai ký tự, cần đối chiếu lại với PDF gốc. QA tự động xác minh trích dẫn và độ phủ phụ đề; độ chính xác ngữ nghĩa và tính dễ đọc vẫn cần người học xem lại. Ghi chú AI cần kiểm tra lại tên lệnh, API và thuật ngữ bị nhận dạng sai trong phụ đề.
