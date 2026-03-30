# LinkedIn Company Scraper

Công cụ Python để **lấy thông tin và website của các công ty trên LinkedIn** trên toàn thế giới.

---

## Thông tin lấy được

| Trường           | Mô tả                              |
|------------------|------------------------------------|
| `name`           | Tên công ty                        |
| `linkedin_url`   | Link trang LinkedIn                |
| `website`        | **Website chính thức**             |
| `industry`       | Ngành nghề                         |
| `company_size`   | Quy mô nhân sự (vd: 1001-5000)     |
| `headquarters`   | Trụ sở chính                       |
| `founded`        | Năm thành lập                      |
| `specialties`    | Lĩnh vực chuyên môn                |
| `description`    | Mô tả công ty                      |
| `followers`      | Số người theo dõi trên LinkedIn    |

---

## Cài đặt

```bash
# 1. Clone và vào thư mục
cd Linkin_Compapy

# 2. Tạo môi trường ảo (khuyến nghị)
python -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Cài Playwright browsers (chỉ cần nếu dùng --mode browser)
playwright install chromium

# 5. Tạo file cấu hình
cp .env.example .env
# Mở .env và điền email + password LinkedIn của bạn
```

---

## Cấu hình

Chỉnh sửa file `.env`:

```env
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

HEADLESS=true          # true = ẩn browser, false = hiện browser
REQUEST_DELAY=2.5      # giây chờ giữa mỗi request
MAX_COMPANIES=500      # giới hạn số công ty mỗi lần chạy
```

---

## Cách dùng

### Chế độ 1: Unofficial API (Nhanh nhất ✅)

```bash
# Tìm 200 công ty fintech
python main.py --mode api --keyword "fintech" --limit 200

# Nhiều từ khóa
python main.py --mode api --keyword "fintech,saas,healthtech" --limit 500

# Xuất ra Excel
python main.py --mode api --keyword "technology" --limit 100 --format excel
```

### Chế độ 2: Playwright Browser (Ổn định nhất 🌐)

```bash
# Tìm công ty healthcare tại Mỹ
python main.py --mode browser --keyword "healthcare" --location "United States" --pages 5

# Nhiều quốc gia
python main.py --mode browser --keyword "fintech" \
  --location "United States,United Kingdom,Singapore" --pages 3

# Chỉ lấy dữ liệu cơ bản (không lấy website, nhanh hơn)
python main.py --mode browser --keyword "saas" --no-detailed
```

### Tham số đầy đủ

```
--mode       api | browser          Chế độ chạy (mặc định: api)
--keyword    "từ khóa"              Từ khóa, phân cách bằng dấu phẩy
--location   "quốc gia"             Chỉ dùng với browser mode
--pages      5                      Số trang tìm kiếm (browser mode)
--limit      100                    Số công ty tối đa (api mode)
--detailed                          Lấy chi tiết đầy đủ (mặc định: bật)
--no-detailed                       Chỉ lấy dữ liệu cơ bản (nhanh hơn)
--format     csv|json|excel|all     Định dạng xuất (mặc định: all)
```

---

## Ví dụ kết quả

File `output/companies.xlsx`:

| name | website | industry | company_size | headquarters | founded |
|------|---------|----------|--------------|--------------|---------|
| Stripe | https://stripe.com | Financial Services | 1001-5000 | San Francisco, US | 2010 |
| Figma | https://figma.com | Computer Software | 501-1000 | San Francisco, US | 2012 |
| Grab | https://grab.com | Internet | 5001-10000 | Singapore | 2012 |

---

## Kiến trúc dự án

```
Linkin_Compapy/
├── main.py                  # Điểm khởi chạy CLI
├── config.py                # Cấu hình chung
├── linkedin_auth.py         # Đăng nhập Playwright
├── company_scraper.py       # Tìm kiếm danh sách công ty
├── company_detail.py        # Lấy chi tiết từng công ty
├── linkedin_api_client.py   # Unofficial API client
├── exporter.py              # Xuất CSV / JSON / Excel
├── requirements.txt
├── .env.example
└── output/                  # Kết quả (tự tạo)
    ├── companies.csv
    ├── companies.json
    └── companies.xlsx
```

---

## Lưu ý quan trọng

> **⚠️ Sử dụng có trách nhiệm**
>
> - Công cụ này chỉ dành cho mục đích nghiên cứu, học tập.
> - LinkedIn có [Điều khoản Dịch vụ](https://www.linkedin.com/legal/user-agreement) nghiêm cấm scraping.
> - Không nên dùng tài khoản chính — hãy dùng tài khoản phụ.
> - Đặt `REQUEST_DELAY` đủ lớn (≥ 2 giây) để tránh bị chặn.
> - LinkedIn có thể yêu cầu xác minh CAPTCHA / 2FA lần đầu đăng nhập.

---

## Xử lý lỗi phổ biến

| Lỗi | Giải pháp |
|-----|-----------|
| `Login failed` | Kiểm tra `.env`, thử đặt `HEADLESS=false` để tự xử lý CAPTCHA |
| `No companies found` | LinkedIn thay đổi selector — mở issue hoặc cập nhật `config.py` |
| `Rate limited` | Tăng `REQUEST_DELAY` lên 5-10 giây |
| `playwright install` | Chạy `playwright install chromium` |
