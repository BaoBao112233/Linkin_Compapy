# ==============================
# LinkedIn Company Scraper
# File: config.py
# ==============================

import os
from dotenv import load_dotenv

load_dotenv()

# ── LinkedIn Credentials ──────────────────────────────────────────────────────
LINKEDIN_EMAIL      = os.getenv("LINKEDIN_EMAIL", "your_email@example.com")
LINKEDIN_PASSWORD   = os.getenv("LINKEDIN_PASSWORD", "your_password")
# Cookie-based auth (lấy bằng get_cookie.py – an toàn hơn, tránh CHALLENGE)
LINKEDIN_LI_AT      = os.getenv("LINKEDIN_LI_AT", "")        # session cookie
LINKEDIN_JSESSIONID = os.getenv("LINKEDIN_JSESSIONID", "")   # CSRF token

# ── Groq / LLM Settings ──────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")          # API key từ console.groq.com
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # model Groq dùng

# ── Scraping Settings ─────────────────────────────────────────────────────────
HEADLESS_MODE   = os.getenv("HEADLESS", "true").lower() == "true"   # True = ẩn browser
REQUEST_DELAY   = float(os.getenv("REQUEST_DELAY", "2.5"))          # giây giữa các request
MAX_COMPANIES   = int(os.getenv("MAX_COMPANIES", "500"))            # số công ty tối đa mỗi lần chạy
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", "3"))                # số lần thử lại khi lỗi

# ── Search Defaults ───────────────────────────────────────────────────────────
DEFAULT_KEYWORDS  = ["technology", "fintech", "healthcare"]         # từ khóa tìm kiếm mặc định
DEFAULT_LOCATIONS = ["United States", "United Kingdom", ""]  # quốc gia mặc định
DEFAULT_INDUSTRIES = [                                              # ngành mặc định
    "Computer Software",
    "Internet",
    "Financial Services",
    "Hospital & Health Care",
]

# ── Telegram Settings ────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "8585500195:AAFj68fr3gPmNLeWGKP-2Og1Uxk9oN3lvaI")
# Telethon MTProto (lấy tại https://my.telegram.org/apps)
TELEGRAM_API_ID     = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH   = os.getenv("TELEGRAM_API_HASH", "")
# Các kênh Telegram mặc định để tìm kiếm công ty (thêm/bớt tuỳ ý)
TELEGRAM_BUSINESS_CHANNELS = [
    # === Tin tức kinh doanh / tài chính Việt Nam ===
    "cafef_vn",                # Cafef - tin tức tài chính
    "tinnhanhchungkhoan",      # Tin nhanh chứng khoán
    "vneconomy",               # VnEconomy
    "baodautu_vn",             # Báo đầu tư
    "nhipcaudautu",            # Nhịp cầu đầu tư
    "doanhnhanonline",         # Doanh nhân online
    "thuongtruong",            # Thương trường
    "tapchicongthuong",        # Tạp chí công thương
    "bizlive",                 # BizLive
    # === Startup / Tech ===
    "tech",             # Tech.org
    "tech",             #  Tech
    "fintechvn",               # Fintech VN
    # === Công ty cụ thể (ví dụ) ===
    "momo_vn",                 # MoMo
    "FPT_official",            # FPT Corporation
    "viettel_group",           # Viettel
    "vnpt_official",           # VNPT
    # === Tuyển dụng / job (chứa info công ty) ===
    "topcv_hr",                # TopCV tuyển dụng
    "vieclam24h",              # Việc làm 24h
    "ITviecvn",                # IT Việc
    "careerviet_vn",           # CareerViet
]
TELEGRAM_SESSION_FILE = os.getenv("TELEGRAM_SESSION_FILE", "telegram_session")
TELEGRAM_MAX_MESSAGES = int(os.getenv("TELEGRAM_MAX_MESSAGES", "200"))  # msg/kênh

# ── Output Settings ───────────────────────────────────────────────────────────
OUTPUT_DIR   = os.getenv("OUTPUT_DIR", "output")
OUTPUT_CSV   = os.path.join(OUTPUT_DIR, "companies.csv")
OUTPUT_JSON  = os.path.join(OUTPUT_DIR, "companies.json")
OUTPUT_XLSX  = os.path.join(OUTPUT_DIR, "companies.xlsx")

# ── LinkedIn URLs ─────────────────────────────────────────────────────────────
LINKEDIN_BASE_URL    = "https://www.linkedin.com"
LINKEDIN_LOGIN_URL   = f"{LINKEDIN_BASE_URL}/login"
LINKEDIN_SEARCH_URL  = f"{LINKEDIN_BASE_URL}/search/results/companies/"
LINKEDIN_COMPANY_URL = f"{LINKEDIN_BASE_URL}/company/"

# ── Selectors (CSS / XPath) ───────────────────────────────────────────────────
SELECTORS = {
    "login_email":          "#username",
    "login_password":       "#password",
    "login_button":         "button[type='submit']",
    "search_result_card":   "li.reusable-search__result-container",
    "company_name":         ".entity-result__title-text a span[aria-hidden='true']",
    "company_url":          ".entity-result__title-text a",
    "next_page_button":     "button[aria-label='Next']",
    # Company detail page
    "company_website":      "a[data-tracking-control-name='about_website']",
    "company_industry":     ".overflow-hidden ~ .t-14.t-black.t-normal",
    "company_size":         ".org-about-company-module__company-size-definition-text",
    "company_founded":      ".org-about-company-module__founded",
    "company_headquarters": ".org-about-company-module__headquarters",
    "company_description":  ".org-about-us-organization-description__text",
    "company_followers":    ".org-top-card-summary__follower-count",
    "company_specialties":  ".org-about-company-module__specialties",
}
