# Hệ Thống Quản Lý Cơ Sở Dữ Liệu Trường Học

Hệ thống quản lý cơ sở dữ liệu trường học dựa trên Python với kiểm soát truy cập theo vai trò và chuyển đổi ngôn ngữ tự nhiên thành SQL bằng LLM.

## 🌟 Tính Năng

- **Kiểm Soát Truy Cập Theo Vai Trò (RBAC)**: Phân quyền riêng biệt cho sinh viên và giảng viên
- **Xử Lý Ngôn Ngữ Tự Nhiên**: Chuyển đổi câu hỏi tiếng Việt thành truy vấn SQL bằng Google Gemini AI
- **Phân Tích SQL Nâng Cao**: Sử dụng LLM để phân tích truy vấn SQL chính xác hơn
- **Bảo Mật Cơ Sở Dữ Liệu**: Tự động xác thực quyền hạn trước khi thực thi truy vấn
- **Giao Diện Tương Tác**: Giao diện dòng lệnh cho truy vấn thời gian thực
- **Hỗ Trợ Đa Vai Trò**: Vai trò sinh viên và giảng viên với các mức truy cập khác nhau

## 🏗️ Kiến Trúc Hệ Thống

### Các Thành Phần Chính

1. **DatabaseManager**: Quản lý kết nối MySQL và thực thi truy vấn
2. **PermissionManager**: Quản lý quyền hạn theo vai trò với phân tích SQL bằng LLM
3. **SQLParserLLM**: Sử dụng LLM để phân tích và xác thực truy vấn SQL chính xác
4. **QueryProcessor**: Bộ xử lý chính cho việc xử lý câu hỏi ngôn ngữ tự nhiên
5. **SQLTemplateManager**: Tạo template SQL theo vai trò cụ thể

### Sơ Đồ Cơ Sở Dữ Liệu

Hệ thống làm việc với cơ sở dữ liệu trường học bao gồm:
- **Students**: Thông tin và hồ sơ sinh viên
- **Teachers**: Thông tin và hồ sơ giảng viên
- **Courses**: Danh mục môn học
- **Classes**: Các lớp học cụ thể với phân công giảng viên
- **Enrollments**: Quan hệ sinh viên-lớp học
- **Schedules**: Thông tin lịch học
- **Users**: Dữ liệu xác thực (truy cập hạn chế)

## 🔧 Cài Đặt

### Yêu Cầu Hệ Thống

- Python 3.8+
- MySQL Server
- Google AI API key

### Thư Viện Phụ Thuộc

```bash
pip install pandas
pip install langchain-core
pip install langchain-google-genai
pip install langchain-community
pip install sqlalchemy
pip install pymysql
```

### Thiết Lập

1. **Clone repository**
```bash
git clone <repository-url>
cd school-database-system
```

2. **Cấu hình kết nối cơ sở dữ liệu**
Chỉnh sửa class `DatabaseConfig` trong file chính:
```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = "mat_khau_cua_ban"
    database: str = "SchoolDB"
```

3. **Thiết lập Google AI API key**
```python
API_KEY = "google_ai_api_key_cua_ban"
```

4. **Chuẩn bị file cấu hình quyền hạn**
Đảm bảo file `permissions2.json` có trong thư mục dự án

## 🚀 Sử Dụng

### Khởi Chạy Hệ Thống

```bash
python main.py
```

### Ví Dụ Câu Hỏi

**Dành cho Sinh Viên:**
- "Thông tin của tôi"
- "Các lớp học tôi đã đăng ký"
- "Lịch học của tôi"
- "Điểm số của tôi"
- "Danh sách môn học đã học"

**Dành cho Giảng Viên:**
- "Thông tin của tôi"
- "Các lớp tôi đang dạy"
- "Danh sách sinh viên trong lớp"
- "Lịch dạy của tôi"
- "Môn học tôi phụ trách"

## 🔒 Hệ Thống Phân Quyền

### Quyền Hạn Sinh Viên

- **Bảng Students**: SELECT, UPDATE (chỉ thông tin của mình)
- **Bảng Enrollments**: SELECT (chỉ đăng ký của mình)
- **Bảng Classes**: SELECT (chỉ lớp đã đăng ký)
- **Bảng Courses**: SELECT (chỉ môn học đã đăng ký)
- **Bảng Schedules**: SELECT (chỉ lịch học của mình)
- **Bảng Teachers**: SELECT FullName (chỉ giảng viên dạy mình)

### Quyền Hạn Giảng Viên

- **Bảng Teachers**: SELECT, UPDATE (chỉ thông tin của mình)
- **Bảng Classes**: SELECT (chỉ lớp mình dạy)
- **Bảng Students**: SELECT (chỉ sinh viên trong lớp mình dạy)
- **Bảng Enrollments**: SELECT (chỉ đăng ký của lớp mình dạy)
- **Bảng Courses**: SELECT (chỉ môn học mình dạy)
- **Bảng Schedules**: SELECT (chỉ lịch dạy của mình)

## 🔍 Tính Năng Nâng Cao

### Phân Tích SQL Bằng LLM

Hệ thống sử dụng Google Gemini AI để:
- Phân tích chính xác cấu trúc truy vấn SQL
- Xác định bảng, cột và thao tác được sử dụng
- Cải thiện độ chính xác của việc kiểm tra quyền hạn
- Tự động fallback về regex parsing nếu LLM thất bại

### Bảo Mật Đa Lớp

1. **Xác thực vai trò**: Tự động xác định vai trò từ UserID
2. **Kiểm tra quyền truy cập**: Xác thực quyền trước khi thực thi
3. **Bảo vệ dữ liệu nhạy cảm**: Chặn truy cập bảng Users
4. **Giới hạn theo vai trò**: Mỗi vai trò chỉ thấy dữ liệu liên quan

## 📁 Cấu Trúc Dự Án

```
school-database-system/
├── main.py                 # File chính chứa tất cả các class
├── permissions2.json       # Cấu hình quyền hạn
└── README.md              # Tài liệu hướng dẫn
```

## 🛠️ Cấu Hình

### File permissions2.json

File này định nghĩa quyền hạn chi tiết cho từng vai trò:
- `allowed_operations`: Các thao tác được phép (SELECT, INSERT, UPDATE, DELETE)
- `allowed_columns`: Các cột được phép truy cập
- `conditions`: Điều kiện bắt buộc khi truy vấn

### Tùy Chỉnh Template SQL

Có thể tùy chỉnh template trong `SQLTemplateManager` để:
- Thêm quy tắc mới cho vai trò
- Định nghĩa ví dụ truy vấn cụ thể
- Tùy chỉnh ngôn ngữ hướng dẫn

## 🚨 Lưu Ý Bảo Mật

- Không bao giờ để lộ API key trong mã nguồn
- Thường xuyên cập nhật mật khẩu cơ sở dữ liệu
- Kiểm tra log để phát hiện truy cập bất thường
- Giới hạn quyền truy cập MySQL theo nguyên tắc tối thiểu

## 🤝 Đóng Góp

1. Fork dự án
2. Tạo branch tính năng (`git checkout -b feature/AmazingFeature`)
3. Commit thay đổi (`git commit -m 'Add some AmazingFeature'`)
4. Push lên branch (`git push origin feature/AmazingFeature`)
5. Mở Pull Request

## 📝 License

Dự án này được phân phối dưới giấy phép MIT. Xem file `LICENSE` để biết thêm chi tiết.

## 📞 Liên Hệ Hỗ Trợ

- Email: support@schooldb.com
- GitHub Issues: [Tạo issue mới](https://github.com/your-repo/issues)
- Documentation: [Wiki](https://github.com/your-repo/wiki)