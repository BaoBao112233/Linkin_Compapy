# ==============================
# LinkedIn Company Scraper
# File: company_detail.py
# Lấy thông tin chi tiết công ty
# ==============================

import re
import time
import random
from dataclasses import dataclass, asdict

from loguru import logger
from playwright.sync_api import Page
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from website_email_extractor import WebsiteEmailExtractor

# ── Singleton extractor (tái sử dụng session HTTP) ────────────────────────────
_website_extractor = WebsiteEmailExtractor()

# ── Helper: extract email từ text ────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_email(text: str) -> str:
    """Trả về email đầu tiên tìm thấy trong text (hoặc rỗng)."""
    m = _EMAIL_RE.search(text or "")
    return m.group(0) if m else ""


@dataclass
class CompanyDetail:
    """Thông tin đầy đủ của một công ty LinkedIn."""
    name: str              = ""
    linkedin_url: str      = ""
    website: str           = ""
    industry: str          = ""
    company_size: str      = ""
    headquarters: str      = ""
    founded: str           = ""
    specialties: str       = ""
    description: str       = ""
    email: str             = ""   # email liên hệ (nếu có)
    phone: str             = ""   # số điện thoại (nếu có)
    followers: str         = ""
    # Từ trang search
    location_search: str   = ""
    followers_search: str  = ""
    description_short: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CompanyDetailScraper:
    """
    Truy cập trang LinkedIn Company và lấy thông tin chi tiết.

    Ví dụ:
        scraper = CompanyDetailScraper(page)
        detail = scraper.fetch("https://www.linkedin.com/company/google/")
    """

    def __init__(self, page: Page):
        self.page = page

    # ── Helper lấy text an toàn ────────────────────────────────────────────
    def _safe_text(self, selector: str) -> str:
        try:
            el = self.page.query_selector(selector)
            return el.inner_text().strip() if el else ""
        except Exception:
            return ""

    def _safe_attr(self, selector: str, attr: str) -> str:
        try:
            el = self.page.query_selector(selector)
            return (el.get_attribute(attr) or "").strip() if el else ""
        except Exception:
            return ""

    # ── Lấy thông tin trang About ────────────────────────────────────────
    def _get_about_info(self, base_url: str) -> dict:
        about_url = base_url.rstrip("/") + "/about/"
        logger.debug(f"  Đang tải trang About: {about_url}")
        self.page.goto(about_url, wait_until="domcontentloaded")
        time.sleep(random.uniform(config.REQUEST_DELAY, config.REQUEST_DELAY + 1.0))

        data: dict[str, str] = {}

        # Website
        try:
            website_el = self.page.query_selector("a[data-tracking-control-name='about_website']")
            if not website_el:
                # Fallback: tìm link trong bảng About
                links = self.page.query_selector_all("dt + dd a")
                for link in links:
                    href = link.get_attribute("href") or ""
                    if href.startswith("http") and "linkedin.com" not in href:
                        data["website"] = href
                        break
            else:
                data["website"] = website_el.get_attribute("href") or ""
        except Exception:
            data["website"] = ""

        # Các trường dạng dt/dd trong bảng thông tin
        try:
            dt_els = self.page.query_selector_all(".org-page-details__definition-term")
            dd_els = self.page.query_selector_all(".org-page-details__definition-text")
            for dt_el, dd_el in zip(dt_els, dd_els):
                key   = dt_el.inner_text().strip().lower()
                value = dd_el.inner_text().strip()
                if "website" in key:
                    data["website"] = data.get("website") or value
                elif "industry" in key:
                    data["industry"] = value
                elif "company size" in key or "company_size" in key:
                    data["company_size"] = value
                elif "headquarter" in key:
                    data["headquarters"] = value
                elif "founded" in key:
                    data["founded"] = value
                elif "specialt" in key:
                    data["specialties"] = value
        except Exception as exc:
            logger.debug(f"  Lỗi khi đọc bảng About: {exc}")

        # Fallback selectors cũ
        for field_name, selector_key in [
            ("industry",     "company_industry"),
            ("company_size", "company_size"),
            ("headquarters", "company_headquarters"),
            ("founded",      "company_founded"),
            ("specialties",  "company_specialties"),
        ]:
            if not data.get(field_name):
                data[field_name] = self._safe_text(config.SELECTORS.get(selector_key, ""))

        # Mô tả
        data["description"] = self._safe_text(config.SELECTORS["company_description"])

        # Email: thử tìm trên trang About
        email = ""
        try:
            page_text = self.page.inner_text("body")
            email = extract_email(page_text)
        except Exception:
            pass
        data["email"] = email

        return data

    # ── Fetch thông tin một công ty ──────────────────────────────────────
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def fetch(self, linkedin_url: str) -> CompanyDetail:
        """
        Lấy thông tin chi tiết của một công ty từ URL LinkedIn.

        Args:
            linkedin_url: URL trang công ty (vd: https://www.linkedin.com/company/google/)

        Returns:
            CompanyDetail dataclass với đầy đủ trường.
        """
        if not linkedin_url:
            return CompanyDetail()

        # Chuẩn hóa URL
        if not linkedin_url.startswith("http"):
            linkedin_url = config.LINKEDIN_BASE_URL + linkedin_url
        base_url = linkedin_url.rstrip("/")

        logger.info(f"Đang lấy thông tin: {base_url}")

        # Tải trang chính
        self.page.goto(base_url, wait_until="domcontentloaded")
        time.sleep(random.uniform(1.5, 2.5))

        # Tên công ty
        name = ""
        for name_selector in [
            "h1.org-top-card-summary__title",
            "h1[class*='top-card']",
            "h1",
        ]:
            name = self._safe_text(name_selector)
            if name:
                break

        # Followers từ trang chính
        followers = self._safe_text(config.SELECTORS["company_followers"])

        # Lấy thông tin từ trang About
        about = self._get_about_info(base_url)

        # Nếu LinkedIn không có email → crawl website của công ty
        email = about.get("email", "")
        website = about.get("website", "")
        if not email and website:
            logger.info(f"  LinkedIn không có email – đang crawl website: {website}")
            email = _website_extractor.extract(website)

        return CompanyDetail(
            name=name,
            linkedin_url=base_url,
            website=website,
            industry=about.get("industry", ""),
            company_size=about.get("company_size", ""),
            headquarters=about.get("headquarters", ""),
            founded=about.get("founded", ""),
            specialties=about.get("specialties", ""),
            description=about.get("description", ""),
            email=email,
            followers=followers,
        )
