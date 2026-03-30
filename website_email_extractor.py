# ==============================
# LinkedIn Company Scraper
# File: website_email_extractor.py
# Crawl website + dùng Groq LLM (Langchain) để extract email
# ==============================
"""
Cách dùng độc lập:

    from website_email_extractor import WebsiteEmailExtractor
    extractor = WebsiteEmailExtractor()
    email = extractor.extract("https://stripe.com")
    print(email)   # contact@stripe.com
"""

import re
import time
import random
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel, Field

import config

# ── Pydantic schema cho output LLM ───────────────────────────────────────────
class EmailResult(BaseModel):
    emails: list[str] = Field(
        default_factory=list,
        description="Danh sách các email liên hệ chính thức tìm được (không bao gồm email mẫu/dummy).",
    )
    source: str = Field(
        default="",
        description="Nơi tìm thấy email: ví dụ 'contact page', 'footer', 'about page'.",
    )


# ── Regex nhanh để lọc sơ bộ ──────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_DUMMY_WORDS = {"example", "test", "your", "name", "user", "email", "domain",
                "company", "username", "youremail", "sentry", "sample"}


def _is_real_email(email: str) -> bool:
    """Lọc bỏ email dummy/placeholder."""
    lower = email.lower()
    return not any(w in lower for w in _DUMMY_WORDS)


class WebsiteEmailExtractor:
    """
    Crawl 1 website (trang chính + /contact + /about) và dùng Groq LLM
    để extract email liên hệ chính thức.

    Pipeline:
        1. requests + BeautifulSoup crawl text từ trang chính + trang contact
        2. Gửi text → Groq (qua Langchain) để extract email chính xác
        3. Fallback: regex đơn giản nếu không có API key hoặc LLM lỗi
    """

    # Các đường dẫn thường chứa thông tin liên hệ
    _CONTACT_PATHS = [
        "/contact", "/contact-us", "/contacts",
        "/about", "/about-us",
        "/reach-us", "/get-in-touch",
        "/support", "/help",
        "/team", "/company",
    ]
    _REQUEST_TIMEOUT = 12
    _MAX_TEXT_CHARS  = 5000   # ký tự tối đa gửi LLM

    def __init__(self):
        self._chain = None   # lazy init Langchain chain
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

    # ── Lazy-init Langchain ───────────────────────────────────────────────
    def _get_chain(self):
        """Khởi tạo Langchain chain với Groq (lazy, chỉ tạo 1 lần)."""
        if self._chain is not None:
            return self._chain

        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        llm = ChatGroq(
            model=config.GROQ_MODEL,
            temperature=0,
            api_key=config.GROQ_API_KEY,
        )

        parser = JsonOutputParser(pydantic_object=EmailResult)

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert at identifying official business contact email addresses in website text.

Rules:
- Extract ONLY real, operational email addresses intended for business contact.
- SKIP placeholder/example emails (e.g. example@, your@, test@, user@, name@, email@domain).
- SKIP transactional/system emails unless they are also listed as contact emails.
- PREFER emails like: contact@, info@, hello@, support@, sales@, press@, team@.
- If multiple emails exist, list all of them.
- Return JSON strictly matching this schema:
{format_instructions}""",
            ),
            (
                "user",
                """Website URL: {website_url}

Scraped text (main page + contact/about page):
---
{text}
---

Extract all official contact email addresses from the text above. Return JSON only.""",
            ),
        ]).partial(format_instructions=parser.get_format_instructions())

        self._chain = prompt | llm | parser
        return self._chain

    # ── Crawling helpers ──────────────────────────────────────────────────
    def _fetch_text(self, url: str) -> str:
        """Lấy text thuần túy từ 1 URL (bỏ script/style/svg)."""
        try:
            resp = self._session.get(
                url,
                timeout=self._REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code not in (200, 203):
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            # Xoá các thẻ không chứa nội dung
            for tag in soup(["script", "style", "meta", "link", "noscript", "svg", "img"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)
        except Exception as exc:
            logger.debug(f"  fetch_text({url}) lỗi: {exc}")
            return ""

    def _collect_text(self, website_url: str) -> str:
        """
        Crawl trang chính + 1 trang contact/about (nếu tìm thấy).
        Trả về chuỗi text gộp, tối đa _MAX_TEXT_CHARS ký tự.
        """
        base = website_url.rstrip("/")
        parts: list[str] = []

        # 1. Trang chính
        logger.debug(f"  Crawling main page: {base}")
        main_text = self._fetch_text(base)
        if main_text:
            parts.append(main_text[:2500])

        # 2. Thử từng contact/about path – lấy trang đầu tiên trả về text dài
        for path in self._CONTACT_PATHS:
            url = base + path
            t = self._fetch_text(url)
            if t and len(t) > 200:
                logger.debug(f"  Crawled contact page: {url} ({len(t)} chars)")
                parts.append(t[:2500])
                time.sleep(random.uniform(0.3, 0.8))
                break   # 1 trang là đủ

        combined = " ".join(parts)
        return combined[: self._MAX_TEXT_CHARS]

    # ── Public API ────────────────────────────────────────────────────────
    def extract(self, website_url: str) -> str:
        """
        Crawl website và dùng LLM extract email chính thức.
        Trả về email đầu tiên tìm được, hoặc chuỗi rỗng nếu không tìm thấy.

        Args:
            website_url: URL website công ty (vd: "https://stripe.com")
        Returns:
            Email string hoặc ""
        """
        emails = self.extract_all(website_url)
        return emails[0] if emails else ""

    def extract_all(self, website_url: str) -> list[str]:
        """
        Trả về danh sách TẤT CẢ email tìm được từ website.

        Args:
            website_url: URL website công ty
        Returns:
            List[str] các email (có thể rỗng)
        """
        if not website_url or not website_url.startswith("http"):
            return []

        logger.info(f"[EmailExtractor] Đang xử lý: {website_url}")

        # ── Bước 1: Crawl text ────────────────────────────────────────────
        text = self._collect_text(website_url)
        if not text.strip():
            logger.warning(f"  Không lấy được text từ: {website_url}")
            return []

        # ── Bước 2: Thử LLM (Groq) ───────────────────────────────────────
        if config.GROQ_API_KEY:
            try:
                chain = self._get_chain()
                result = chain.invoke({"website_url": website_url, "text": text})
                llm_emails: list[str] = []
                if isinstance(result, dict):
                    llm_emails = result.get("emails", [])
                elif hasattr(result, "emails"):
                    llm_emails = result.emails

                # Lọc dummy
                llm_emails = [e for e in llm_emails if _is_real_email(e)]

                if llm_emails:
                    logger.success(f"  [LLM] Tìm được: {llm_emails}")
                    return llm_emails
                else:
                    logger.debug("  [LLM] Không tìm thấy email – fallback regex")
            except Exception as exc:
                logger.warning(f"  [LLM] Lỗi: {exc} – chuyển sang regex")
        else:
            logger.debug("  GROQ_API_KEY chưa được cấu hình – dùng regex")

        # ── Bước 3: Fallback regex ────────────────────────────────────────
        found = _EMAIL_RE.findall(text)
        real = [e for e in found if _is_real_email(e)]
        # Loại trùng, giữ thứ tự
        seen: set[str] = set()
        dedup = []
        for e in real:
            if e.lower() not in seen:
                seen.add(e.lower())
                dedup.append(e)

        if dedup:
            logger.info(f"  [Regex] Tìm được: {dedup}")
        return dedup
