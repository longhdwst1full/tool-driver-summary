# Thử đọc bản chép lời hiển thị trên Drive

## Dùng tab Chrome hiện tại

Đây là cách phù hợp khi Google từ chối đăng nhập trong Chrome do Playwright mở. Trên tab video Drive đang đăng nhập, mở **Bản chép lời**, nhấn **F12 → Console**, dán toàn bộ nội dung [console-transcript.js](console-transcript.js), rồi Enter. Nếu Chrome chặn dán, gõ `allow pasting` và dán lại. Script cuộn panel, tải một tệp `getsub-transcript-<video-id>.json` về thư mục Downloads mặc định; không gửi dữ liệu đến dịch vụ khác.

Nhập kết quả và tạo ghi chú:

```bash
python3 import_ui_transcript.py ~/Downloads/getsub-transcript-VIDEO_ID.json
python3 progressive_demo.py --ui-video-id VIDEO_ID
```

Bộ nhập chỉ nhận video có trong `drive-reports/scan.json`, bản thu có cả mốc đầu và đã đi đến cuối panel. Sau khi nhập, hãy đối chiếu vài đoạn ở đầu, giữa, cuối video trước khi tin rằng nội dung đầy đủ. Profile Chrome và file tải về là dữ liệu riêng của bạn.

## Chạy ngầm khi vẫn dùng máy

Nếu Chrome đang đăng nhập tài khoản xem được video, chạy một phiên Chrome tạm trong chế độ headless. Phiên này dùng bản sao riêng của cookie/profile, tắt tiếng, không chiếm chuột hoặc bàn phím và tự xóa profile tạm khi xong:

```bash
python3 -m pip install --target .deps -r requirements.txt
PYTHONPATH=.deps python3 browser-demo/background_capture.py --video-id VIDEO_ID --ai
```

Để terminal cũng được giải phóng, chạy lệnh trên với `nohup`:

```bash
nohup env PYTHONPATH=.deps python3 browser-demo/background_capture.py --video-id VIDEO_ID --ai > drive-reports/background-capture.log 2>&1 < /dev/null &
```

Không cần `--ai` nếu chỉ muốn thu bản chép lời. Nếu tài khoản nằm ở profile khác, thêm `--profile-name 'Profile 1'`. Kết quả nằm trong `drive-reports/ui-transcripts/` và `drive-reports/progressive-demo/`. Nếu Chrome chạy ngầm không thấy quyền xem, hãy kiểm tra profile Chrome đã chọn; phiên này không thể tự đăng nhập thay bạn.
