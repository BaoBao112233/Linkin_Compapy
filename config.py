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

# ── Scraping Settings ─────────────────────────────────────────────────────────
HEADLESS_MODE   = os.getenv("HEADLESS", "true").lower() == "true"   # True = ẩn browser
REQUEST_DELAY   = float(os.getenv("REQUEST_DELAY", "2.5"))          # giây giữa các request
MAX_COMPANIES   = int(os.getenv("MAX_COMPANIES", "500"))            # số công ty tối đa mỗi lần chạy
MAX_RETRIES     = int(os.getenv("MAX_RETRIES", "3"))                # số lần thử lại khi lỗi

# ── Search Defaults ───────────────────────────────────────────────────────────
DEFAULT_KEYWORDS  = ["technology", "fintech", "healthcare"]         # từ khóa tìm kiếm mặc định
DEFAULT_LOCATIONS = ["United States", "United Kingdom", "Vietnam"]  # quốc gia mặc định
DEFAULT_INDUSTRIES = [                                              # ngành mặc định
    "Computer Software",
    "Internet",
    "Financial Services",
    "Hospital & Health Care",
]

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
