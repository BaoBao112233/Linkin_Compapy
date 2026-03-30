# ==============================
# LinkedIn Company Scraper
# File: linkedin_api_client.py
# Sử dụng linkedin-api (unofficial)
# Nhanh hơn Playwright, không cần browser
# ==============================

from __future__ import annotations

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from company_detail import CompanyDetail, extract_email
from website_email_extractor import WebsiteEmailExtractor

# Singleton – tái sử dụng HTTP session cho toàn bộ pipeline
_web_extractor = WebsiteEmailExtractor()


class LinkedInAPIClient:
    """
    Wrapper quanh thư viện linkedin-api (unofficial).

    Ưu điểm:  Không cần browser, nhanh hơn.
    Nhược điểm: LinkedIn có thể chặn nếu dùng quá nhiều.

    Tài liệu: https://github.com/tomquirk/linkedin-api
    """

    def __init__(
        self,
        email: str = config.LINKEDIN_EMAIL,
        password: str = config.LINKEDIN_PASSWORD,
    ):
        self._email = email
        self._password = password
        self._api = None

    # ── Kết nối ──────────────────────────────────────────────────────────
    def connect(self):
        try:
            from linkedin_api import Linkedin  # type: ignore
        except ImportError:
            logger.error("Chưa cài linkedin-api. Chạy: pip install linkedin-api")
            raise

        li_at      = config.LINKEDIN_LI_AT
        jsessionid = config.LINKEDIN_JSESSIONID

        try:
            if li_at:
                # ── Ưu tiên dùng cookie (tránh CHALLENGE) ─────────────────
                logger.info("linkedin-api: Đăng nhập bằng cookie li_at...")
                from requests.cookies import RequestsCookieJar
                jar = RequestsCookieJar()
                jar.set("li_at", li_at, domain=".linkedin.com", path="/")
                # JSESSIONID phải có dấu ngoặc kép – đây là csrf token
                jid = jsessionid if jsessionid.startswith('"') else f'"{jsessionid}"'
                if jid and jid != '""':
                    jar.set("JSESSIONID", jid, domain=".linkedin.com", path="/")
                # authenticate=True + cookies=CookieJar → gọi _set_session_cookies đúng cách
                self._api = Linkedin(
                    self._email or "",
                    self._password or "",
                    cookies=jar,
                    authenticate=True,
                )
            else:
                # ── Fallback: dùng email/password ─────────────────────────
                logger.info("linkedin-api: Đăng nhập bằng email/password...")
                logger.warning(
                    "Nếu gặp lỗi CHALLENGE, hãy chạy 'python get_cookie.py' trước."
                )
                self._api = Linkedin(self._email, self._password)

            logger.success("linkedin-api: Đăng nhập thành công!")
        except Exception as exc:
            logger.error(f"Đăng nhập thất bại: {exc}")
            if "CHALLENGE" in str(exc):
                logger.error(
                    "LinkedIn yêu cầu xác minh. Chạy lệnh sau để lấy cookie:\n"
                    "  python get_cookie.py"
                )
            raise

    # ── Tìm kiếm công ty ────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(config.MAX_RETRIES), wait=wait_exponential(min=2, max=8))
    def search_companies(
        self,
        keyword: str,
        limit: int = 50,
        location: str = "",
    ) -> list[dict]:
        """
        Tìm kiếm công ty qua LinkedIn API không chính thức.

        Returns:
            Danh sách dict thô từ API.
        """
        if self._api is None:
            self.connect()

        logger.info(f"API: Tìm kiếm '{keyword}' (limit={limit})")
        params: dict = {"keywords": keyword, "limit": limit}
        results = self._api.search_companies(**params)  # type: ignore
        logger.info(f"API: Tìm thấy {len(results)} công ty")
        return results

    # ── Lấy chi tiết một công ty ─────────────────────────────────────────
    @retry(stop=stop_after_attempt(config.MAX_RETRIES), wait=wait_exponential(min=2, max=8))
    def get_company(self, public_id: str) -> CompanyDetail:
        """
        Lấy thông tin chi tiết công ty qua public_id (slug).

        Args:
            public_id: Phần cuối URL LinkedIn (vd: 'google' trong /company/google/)

        Returns:
            CompanyDetail
        """
        if self._api is None:
            self.connect()

        logger.debug(f"API: Fetch company '{public_id}'")
        raw = self._api.get_company(public_id)  # type: ignore

        # ── Mapping fields ────────────────────────────────────────────────
        name = raw.get("name", "")
        linkedin_url = f"{config.LINKEDIN_COMPANY_URL}{public_id}/"

        # Website
        website = raw.get("companyPageUrl") or raw.get("websiteUrl") or ""
        if not website:
            urls = raw.get("websites", [])
            if urls:
                website = urls[0].get("url", "")

        # Ngành
        industries = raw.get("industries", [])
        industry = industries[0].get("localizedName", "") if industries else ""
        if not industry:
            industry = raw.get("companyIndustries", [{}])
            if isinstance(industry, list) and industry:
                industry = industry[0].get("localizedName", "")
            else:
                industry = ""

        # Số nhân viên
        staff_range = raw.get("staffCountRange", {})
        company_size = ""
        if staff_range:
            lo = staff_range.get("start", "")
            hi = staff_range.get("end", "")
            company_size = f"{lo}-{hi}" if hi else f"{lo}+"

        # Trụ sở
        hq = raw.get("headquarter", {})
        headquarters = ", ".join(
            filter(None, [hq.get("city", ""), hq.get("country", "")])
        )

        # Thành lập
        founded = str(raw.get("foundedOn", {}).get("year", "") or "")

        # Chuyên ngành
        specialties = ", ".join(raw.get("specialities") or [])

        # Mô tả
        description = raw.get("description", "")

        # Followers
        followers = str(raw.get("followingInfo", {}).get("followerCount", "") or "")

        # Phone
        phone_info = raw.get("phone", {}) or {}
        phone = str(phone_info.get("number", "") or "").strip()

        # Email – LinkedIn không expose trực tiếp; thử các field ẩn + regex trên description
        email = (
            raw.get("emailAddress", "")
            or raw.get("email", "")
            or raw.get("contactEmail", "")
            or ""
        )
        if not email:
            # Thử tìm trong description / specialties
            email = extract_email(description) or extract_email(specialties)

        # Nếu vẫn không có email → crawl website công ty + Groq LLM extract
        if not email and website:
            logger.info(f"  LinkedIn không có email cho '{name}' – crawl website: {website}")
            email = _web_extractor.extract(website)

        return CompanyDetail(
            name=name,
            linkedin_url=linkedin_url,
            website=website,
            industry=industry,
            company_size=company_size,
            headquarters=headquarters,
            founded=founded,
            specialties=specialties,
            description=description,
            email=email,
            phone=phone,
            followers=followers,
        )

    # ── Tìm + lấy chi tiết hàng loạt ─────────────────────────────────────
    def fetch_companies_bulk(
        self,
        keyword: str,
        limit: int = 100,
    ) -> list[CompanyDetail]:
        """
        Tìm kiếm và lấy chi tiết hàng loạt công ty.

        Returns:
            Danh sách CompanyDetail đã có đầy đủ thông tin (bao gồm website).
        """
        search_results = self.search_companies(keyword, limit=limit)
        details: list[CompanyDetail] = []

        for result in search_results:
            try:
                # Lấy public_id từ kết quả tìm kiếm
                public_id = (
                    result.get("publicIdentifier")
                    or result.get("company", {}).get("publicIdentifier")
                    or result.get("urn_id", "").split(":")[-1]
                )
                if not public_id:
                    # Thử lấy từ URL
                    url = result.get("profileUrl", "")
                    if "/company/" in url:
                        public_id = url.split("/company/")[1].strip("/")

                if not public_id:
                    logger.debug(f"Bỏ qua: không tìm được public_id cho {result}")
                    continue

                detail = self.get_company(public_id)

                # ── Bổ sung thêm thông tin từ kết quả search ──────────────
                # headline → description_short
                headline = result.get("headline") or ""
                if isinstance(headline, dict):
                    headline = headline.get("text", "")
                detail.description_short = str(headline)

                # subline → location_search
                subline = result.get("subline") or result.get("headquarter") or ""
                if isinstance(subline, dict):
                    subline = subline.get("text", "")
                detail.location_search = str(subline)

                # followersCount → followers_search
                fc = result.get("followersCount") or result.get("followers") or ""
                detail.followers_search = str(fc) if fc else ""

                details.append(detail)
                logger.info(
                    f"  ✓ {detail.name:<40} | {detail.website or '(no website)'} | email={detail.email or '-'}"
                )
            except Exception as exc:
                logger.warning(f"Lỗi khi lấy công ty: {exc}")

        return details
