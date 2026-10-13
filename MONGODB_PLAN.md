# MongoDB và truy cập nhiều thiết bị

## Trạng thái

- Đã có lệnh `mongo_migrate.py` đồng bộ danh mục bảy nguồn Drive, thư viện cũ và **nội dung đã kiểm tra** sang MongoDB. Lệnh dùng upsert theo ID; chạy lại không nhân đôi dữ liệu.
- API web đọc danh mục, nội dung, tìm khóa học và lịch sử học từ MongoDB khi có kết nối. Khi DB lỗi, danh mục/nội dung vẫn đọc bản local; lịch sử học giữ trong trình duyệt.
- Đã có đăng nhập một tài khoản bằng mật khẩu băm `scrypt`. Để xem trên thiết bị khác, cần đặt web sau một đường HTTPS riêng (ví dụ Tailscale Serve hoặc reverse proxy có TLS). Web vẫn chỉ lắng nghe `127.0.0.1`.
- **Chưa kết nối Atlas thật**: máy chưa có `MONGODB_URI` mới. Mật khẩu Atlas từng xuất hiện trong chat phải được đổi trước khi cấu hình. Chưa có dữ liệu nào được xóa.

## Cấu hình trên máy chạy web

1. Đổi mật khẩu người dùng Atlas; cho phép IP của máy chạy web trong Atlas Network Access. Không đưa URI hoặc mật khẩu vào Git, chat, lệnh shell được lưu lịch sử hay URL của trình duyệt.
2. Cài `requirements.txt` vào `.deps` và đặt `MONGODB_URI` mới trong môi trường của **tiến trình chạy lệnh đồng bộ và web**. Có thể đặt tên DB bằng `MONGODB_DATABASE`; mặc định là `tool_driver_summary`.
3. Chạy `PYTHONPATH=.deps python3 mongo_migrate.py`. Có thể thử một nguồn bằng `--source-id ID`, hoặc chỉ nạp danh mục bằng `--metadata-only`. Chạy lại sau mỗi lượt thu transcript/tạo tóm tắt để đưa nội dung mới lên DB.
4. Tạo hash đăng nhập bằng `python3 web_auth.py hash` (nhập mật khẩu tại prompt, không qua dòng lệnh), rồi đặt kết quả vào `WEB_PASSWORD_HASH`; đặt `WEB_USERNAME` nếu muốn đổi tên tài khoản mặc định `admin`.
5. Cấu hình HTTPS từ thiết bị khác tới `127.0.0.1:8765`. Đặt tên miền HTTPS được dùng vào `WEB_ALLOWED_HOSTS` (danh sách ngăn bằng dấu phẩy). Chỉ bật Basic Auth qua HTTPS. Máy chủ web không tự tạo chứng chỉ hoặc URL công khai.

Các biến môi trường phải được đặt trong cùng phiên/đơn vị dịch vụ chạy web; đặt ở terminal khác sẽ không ảnh hưởng tiến trình web đang chạy. Khởi động lại web sau khi đổi cấu hình.

## Cách kiểm tra và giới hạn

- Sau khi chạy đồng bộ, so sánh số mục từng nguồn in từ `mongo_migrate.py` với `scan.json`/`scan.checkpoint.json`. Mở một bài đã có tóm tắt trên hai thiết bị và kiểm tra lịch sử gần đây. Kiểm tra thêm tìm kiếm khóa học và trang xem tài liệu.
- Bản gốc video/PDF trên Drive vẫn cần đăng nhập Google có quyền xem **trong trình duyệt của từng thiết bị**. MongoDB chỉ chứa nội dung trích xuất/ghi chú và metadata đã kiểm tra; nó không cấp quyền xem file gốc.
- Dữ liệu mới tạo trên máy **không tự đẩy lên MongoDB** cho đến khi chạy lại `mongo_migrate.py`. Danh mục cũ trong DB có thể tiếp tục hiện trong lúc đang đồng bộ nguồn; API chuyển sang thế hệ mới khi ghi xong metadata.
- Tài khoản đăng nhập web hiện là **một tài khoản chung**, chưa có nhiều người dùng/đăng ký hoặc phân quyền riêng. Lịch sử được chia sẻ giữa các thiết bị dùng cùng tài khoản.
- Chưa xóa `drive-reports/`: đó là nguồn để phục hồi/đồng bộ lại. Trước khi dọn dữ liệu, cần sao lưu và đối chiếu bản DB thật; lệnh đồng bộ không xóa dữ liệu gốc.
