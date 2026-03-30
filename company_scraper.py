# ==============================
# LinkedIn Company Scraper
# File: company_scraper.py
# Tìm kiếm danh sách công ty
# ==============================

import time
import random
import urllib.parse
from typing import Generator
from dataclasses import dataclass, asdict, field

from loguru import logger
from playwright.sync_api import Page
from tenacity import retry, stop_after_attempt, wait_exponential

import config


@dataclass
class CompanyBasic:
    """Thông tin cơ bản từ trang tìm kiếm."""
    name: str = ""
    linkedin_url: str = ""
    industry: str = ""
    location: str = ""
    followers: str = ""
    description_short: str = ""


class CompanySearchScraper:
    """
    Tìm kiếm danh sách công ty trên LinkedIn Search.

    Ví dụ:
        scraper = CompanySearchScraper(page)
        for company in scraper.search("fintech", location="United States"):
            print(company)
    """

    def __init__(self, page: Page):
        self.page = page

    # ── Xây dựng URL tìm kiếm ─────────────────────────────────────────────
    def _build_search_url(
        self,
        keyword: str,
        location: str = "",
        industry: str = "",
        page_num: int = 1,
    ) -> str:
        params: dict[str, str] = {
            "keywords": keyword,
            "origin": "SWITCH_SEARCH_VERTICAL",
        }
        if location:
            params["geoUrn"] = self._encode_location(location)
        if industry:
            params["industry"] = industry

        base = f"{config.LINKEDIN_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        if page_num > 1:
            base += f"&page={page_num}"
        return base

    def _encode_location(self, location: str) -> str:
        """Mapping tên quốc gia → LinkedIn geoUrn (các giá trị phổ biến)."""
        GEO_MAP = {
            "United States":  "103644278",
            "United Kingdom": "101165590",
            "Vietnam":        "104195383",
            "Singapore":      "102454443",
            "Germany":        "101282230",
            "France":         "105015875",
            "India":          "102713980",
            "Canada":         "101174742",
            "Australia":      "101452733",
            "Japan":          "101355337",
            "China":          "102890883",
            "Brazil":         "106057199",
            "Netherlands":    "102890719",
            "Sweden":         "105117694",
            "South Korea":    "105149562",
        }
        return GEO_MAP.get(location, "")

    # ── Lấy danh sách thẻ công ty trên 1 trang ───────────────────────────
    def _extract_cards(self) -> list[CompanyBasic]:
        companies: list[CompanyBasic] = []
        try:
            self.page.wait_for_selector(
                config.SELECTORS["search_result_card"], timeout=10_000
            )
        except Exception:
            logger.warning("Không tìm thấy kết quả trên trang này.")
            return companies

        cards = self.page.query_selector_all(config.SELECTORS["search_result_card"])
        logger.info(f"  → Tìm thấy {len(cards)} thẻ công ty trên trang hiện tại.")

        for card in cards:
            try:
                # Tên công ty
                name_el = card.query_selector(".entity-result__title-text a span[aria-hidden='true']")
                name = name_el.inner_text().strip() if name_el else ""

                # LinkedIn URL
                url_el = card.query_selector(".entity-result__title-text a")
                url = url_el.get_attribute("href") if url_el else ""
                if url and "?" in url:
                    url = url.split("?")[0].rstrip("/")

                # Ngành & Vị trí (dòng phụ)
                subtitles = card.query_selector_all(".entity-result__primary-subtitle")
                industry = subtitles[0].inner_text().strip() if len(subtitles) > 0 else ""
                location = subtitles[1].inner_text().strip() if len(subtitles) > 1 else ""

                # Followers
                followers_el = card.query_selector(".entity-result__secondary-subtitle")
                followers = followers_el.inner_text().strip() if followers_el else ""

                # Mô tả ngắn
                desc_el = card.query_selector(".entity-result__summary")
                description_short = desc_el.inner_text().strip() if desc_el else ""

                if name:
                    companies.append(CompanyBasic(
                        name=name,
                        linkedin_url=url,
                        industry=industry,
                        location=location,
                        followers=followers,
                        description_short=description_short,
                    ))
            except Exception as exc:
                logger.debug(f"Bỏ qua một thẻ do lỗi: {exc}")

        return companies

    # ── Generator tìm kiếm qua nhiều trang ──────────────────────────────
    def search(
        self,
        keyword: str,
        location: str = "",
        industry: str = "",
        max_pages: int = 10,
    ) -> Generator[CompanyBasic, None, None]:
        """
        Duyệt qua nhiều trang kết quả tìm kiếm và yield từng CompanyBasic.

        Args:
            keyword:   Từ khóa tìm kiếm (tên công ty, lĩnh vực, ...)
            location:  Tên quốc gia (xem _encode_location)
            industry:  Mã ngành LinkedIn
            max_pages: Số trang tối đa cần lấy
        """
        logger.info(
            f"Tìm kiếm: keyword='{keyword}', location='{location}', "
            f"max_pages={max_pages}"
        )
        total = 0

        for page_num in range(1, max_pages + 1):
            url = self._build_search_url(keyword, location, industry, page_num)
            logger.info(f"Đang tải trang {page_num}: {url}")
            self.page.goto(url, wait_until="domcontentloaded")
            time.sleep(random.uniform(config.REQUEST_DELAY, config.REQUEST_DELAY + 1.5))

            companies = self._extract_cards()
            if not companies:
                logger.info("Không còn kết quả, dừng tìm kiếm.")
                break

            for c in companies:
                total += 1
                if total > config.MAX_COMPANIES:
                    logger.info(f"Đã đạt giới hạn {config.MAX_COMPANIES} công ty.")
                    return
                yield c

            # Kiểm tra nút trang tiếp theo
            next_btn = self.page.query_selector(config.SELECTORS["next_page_button"])
            if not next_btn or next_btn.is_disabled():
                logger.info("Đã hết trang kết quả.")
                break

            time.sleep(random.uniform(1.0, 2.0))
