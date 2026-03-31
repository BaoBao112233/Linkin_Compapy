# Company Scraper – LinkedIn & Telegram

Công cụ Python thu thập thông tin công ty từ **LinkedIn** và **Telegram** trên thị trường **toàn cầu** (Vietnam · SEA · India · USA · EU · MEA · LATAM · East Asia).

---

## Tính năng

- **3 chế độ chạy** phù hợp với từng mục đích: nhanh, song song, hoặc quy mô lớn
- **315 LinkedIn keywords** phủ 20+ thị trường và 15+ ngành
- **147 Telegram channels** toàn cầu — không cần xác thực
- **Checkpoint / Resume** — crawl 10k+ công ty không sợ mất dữ liệu khi ngắt giữa chừng
- **Dedup tự động** theo `linkedin_url` / channel username
- **Xuất đa định dạng**: CSV · JSON · Excel

---

## Dữ liệu thu thập

### LinkedIn

| Trường | Mô tả |
|---|---|
| `name` | Tên công ty |
| `linkedin_url` | URL trang LinkedIn |
| `website` | Website chính thức |
| `industry` | Ngành nghề |
| `company_size` | Quy mô nhân sự (vd: `1001-5000`) |
| `headquarters` | Trụ sở chính |
| `founded` | Năm thành lập |
| `specialties` | Lĩnh vực chuyên môn |
| `description` | Mô tả công ty |
| `email` | Email liên hệ (crawl từ website) |
| `phone` | Số điện thoại (nếu có) |
| `followers` | Số người theo dõi trên LinkedIn |

### Telegram

| Trường | Mô tả |
|---|---|
| `name` | Tên kênh / công ty |
| `channel` | Username Telegram (`@channel`) |
| `description` | Bio / mô tả kênh |
| `members` | Số thành viên |
| `website` | Website (từ bio) |
| `email` | Email (từ bio) |
| `source` | Nguồn (`telegram`) |

---

## Cài đặt

```bash
# 1. Clone và vào thư mục
git clone <repo-url>
cd Linkin_Compapy

# 2. Tạo môi trường ảo
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Cài linkedin-api (unofficial)
pip install git+https://github.com/tomquirk/linkedin-api.git

# 5. Cài Playwright browsers (chỉ cần nếu dùng --mode browser)
playwright install chromium

# 6. Cấu hình .env
cp .env.example .env
```

---

## Cấu hình `.env`

```env
# LinkedIn – bắt buộc
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

# Cookie auth (ổn định hơn username/password)
LINKEDIN_LI_AT=AQEDAUr...
LINKEDIN_JSESSIONID=ajax:620818...

# Telegram Bot (tuỳ chọn – chỉ cần cho telegram_bot.py)
TELEGRAM_BOT_TOKEN=8585500195:AAFj...

# Telegram MTProto API (tuỳ chọn – cho Telethon)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef...

# Tuỳ chỉnh hành vi
HEADLESS=true
REQUEST_DELAY=2.5
MAX_COMPANIES=500
```

> **Lấy LinkedIn cookie (`li_at`, `JSESSIONID`)**: Đăng nhập LinkedIn trên trình duyệt → DevTools → Application → Cookies → `linkedin.com`.

---

## Kiến trúc dự án

```
Linkin_Compapy/
├── main.py                  # Chế độ 1: Scrape đơn theo keyword (API hoặc Browser)
├── parallel_pipeline.py     # Chế độ 2: LinkedIn + Telegram song song theo keyword
├── large_crawl_10k.py       # Chế độ 3: Crawl 10k+ công ty quy mô lớn toàn cầu
│
├── linkedin_api_client.py   # Wrapper LinkedIn unofficial API
├── linkedin_auth.py         # Xác thực Playwright
├── company_scraper.py       # Tìm kiếm danh sách công ty (Playwright)
├── company_detail.py        # Lấy chi tiết từng công ty
├── telegram_scraper.py      # Scraper Telegram (Web + Bot API + Telethon)
├── telegram_bot.py          # Telegram bot giao tiếp người dùng
│
├── website_email_extractor.py  # Crawl website để lấy email liên hệ
├── keyword_generator.py     # Sinh keyword tự động (AI-assisted)
├── exporter.py              # Xuất CSV / JSON / Excel
├── config.py                # Cấu hình toàn cục
│
├── requirements.txt
├── .env.example
├── logs/                    # Log file (tự tạo)
└── output/                  # Kết quả xuất (tự tạo)
    ├── companies_10k.csv
    ├── companies_10k.json
    └── companies_10k.xlsx
```

---

## Cách dùng

### Chế độ 1 — `main.py` (Scrape đơn giản)

Phù hợp khi cần tìm kiếm nhanh theo một vài keyword.

```bash
# Unofficial API – nhanh nhất
python main.py --mode api --keyword "fintech" --limit 200

# Nhiều keyword cùng lúc
python main.py --mode api --keyword "fintech,saas,healthtech" --limit 500

# Playwright Browser – ổn định hơn, hỗ trợ lọc vị trí
python main.py --mode browser --keyword "healthcare" --location "United States" --pages 5

# Xuất Excel
python main.py --mode api --keyword "technology Vietnam" --limit 100 --format excel
```

| Tham số | Giá trị | Mô tả |
|---|---|---|
| `--mode` | `api` \| `browser` | Chế độ chạy (mặc định: `api`) |
| `--keyword` | `"từ khóa"` | Từ khóa, phân cách bằng dấu phẩy |
| `--limit` | `200` | Số công ty tối đa (api mode) |
| `--location` | `"United States"` | Lọc theo quốc gia (browser mode) |
| `--pages` | `5` | Số trang tìm kiếm (browser mode) |
| `--format` | `csv\|json\|excel\|all` | Định dạng xuất (mặc định: `all`) |
| `--no-detailed` | — | Bỏ qua crawl chi tiết (nhanh hơn) |

---

### Chế độ 2 — `parallel_pipeline.py` (LinkedIn + Telegram song song)

Phù hợp khi muốn kết hợp dữ liệu từ cả hai nguồn theo cùng một keyword.

```bash
# Tìm kiếm cả LinkedIn lẫn Telegram
python parallel_pipeline.py --keyword "fintech" --limit 50

# Chỉ Telegram
python parallel_pipeline.py --keyword "startup" --source telegram --limit 30

# Chỉ LinkedIn
python parallel_pipeline.py --keyword "technology" --source linkedin --limit 100

# Xuất Excel
python parallel_pipeline.py --keyword "healthcare" --limit 50 --format excel
```

---

### Chế độ 3 — `large_crawl_10k.py` (Crawl 10k+ toàn cầu) ⭐

Phù hợp khi cần thu thập dữ liệu quy mô lớn với **checkpoint/resume**.

```bash
# Chạy đầy đủ (LinkedIn + Telegram, đích 10.000 công ty)
python large_crawl_10k.py

# Tuỳ chỉnh đích
python large_crawl_10k.py --target 5000

# Chỉ LinkedIn
python large_crawl_10k.py --source linkedin

# Chỉ Telegram
python large_crawl_10k.py --source telegram

# Tiếp tục từ checkpoint (bị ngắt giữa chừng)
python large_crawl_10k.py --resume

# Chế độ Enrich – gọi get_company() từng công ty (chậm nhưng đủ thông tin)
python large_crawl_10k.py --enrich

# Tất cả tuỳ chọn
python large_crawl_10k.py --source both --target 10000 --per-keyword 200 --resume
```

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `--source` | `both` | `linkedin` \| `telegram` \| `both` |
| `--target` | `10000` | Tổng số công ty mục tiêu |
| `--per-keyword` | `200` | Số công ty tối đa mỗi keyword LinkedIn |
| `--resume` | — | Tiếp tục từ checkpoint đã lưu |
| `--enrich` | — | Crawl chi tiết đầy đủ (chậm ~12 cty/phút) |

**Phủ sóng thị trường (315 keywords, 147 Telegram channels):**

| Thị trường | Keywords | Ví dụ |
|---|---|---|
| Vietnam | 23 | `fintech Vietnam`, `công ty công nghệ` |
| SE Asia | 28 | `startup Singapore`, `fintech Indonesia` |
| India | 14 | `SaaS India`, `startup Bangalore` |
| USA | 45+ | `AI startup USA`, `startup Silicon Valley` |
| Europe | 25+ | `fintech London`, `startup Berlin`, `EU SaaS` |
| Middle East / Africa | 14 | `startup Dubai`, `fintech Nigeria` |
| LATAM | 8 | `fintech Brazil`, `startup São Paulo` |
| East Asia | 9 | `startup Tokyo`, `tech company Korea` |
| Global verticals | 60+ | `generative AI`, `climate tech`, `Web3` |

**Output** (tự động lưu checkpoint mỗi keyword):

```
output/
├── companies_10k.csv
├── companies_10k.json
├── companies_10k.xlsx
├── checkpoint_linkedin_10k.json   # Resume data
└── checkpoint_telegram_10k.json   # Resume data
```

**Ước tính hiệu suất (Fast mode):**

| Chỉ số | Giá trị |
|---|---|
| Tốc độ | ~100-200 công ty/phút |
| 315 keywords × ~100 avg | ~31.500 công ty thô |
| Sau dedup | ~10.000-15.000 unique |
| Thời gian ước tính | 2-4 giờ (LinkedIn) + 1 giờ (Telegram) |

---

## Ví dụ kết quả

`output/companies_10k.csv`:

| name | website | industry | company_size | headquarters | founded | email |
|---|---|---|---|---|---|---|
| Stripe | stripe.com | Financial Services | 1001-5000 | San Francisco | 2010 | — |
| Figma | figma.com | Computer Software | 501-1000 | San Francisco | 2012 | — |
| Grab | grab.com | Internet | 5001-10000 | Singapore | 2012 | — |
| MoMo | momo.vn | Financial Services | 1001-5000 | Ho Chi Minh City | 2010 | support@momo.vn |

---

## Xử lý lỗi phổ biến

| Lỗi | Giải pháp |
|---|---|
| `Login failed` | Kiểm tra `.env`; thử cookie auth thay vì email/password |
| `Rate limited` | Tăng `REQUEST_DELAY` lên 5-10 giây; để crawl chạy từ từ |
| `CAPTCHA / verification` | Đặt `HEADLESS=false`, tự xử lý thủ công lần đầu |
| `No companies found` | LinkedIn thay đổi selector — cập nhật `config.py` |
| `Telegram 400 Bad Request` | Bot chưa join kênh; scraper tự động fallback sang Web scraper |
| Mất dữ liệu khi ngắt | Chạy `python large_crawl_10k.py --resume` để tiếp tục |

---

## Lưu ý quan trọng

> **⚠️ Sử dụng có trách nhiệm**
>
> - Công cụ này chỉ dành cho mục đích **nghiên cứu và học tập**.
> - LinkedIn có [Điều khoản Dịch vụ](https://www.linkedin.com/legal/user-agreement) nghiêm cấm scraping tự động.
> - **Không dùng tài khoản chính** — hãy dùng tài khoản phụ.
> - Đặt `REQUEST_DELAY` ≥ 2 giây để tránh bị khoá tài khoản.
> - Cookie `li_at` hết hạn sau vài tuần — cần lấy lại nếu gặp lỗi auth.
