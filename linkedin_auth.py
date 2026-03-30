# ==============================
# LinkedIn Company Scraper
# File: linkedin_auth.py
# Xử lý đăng nhập LinkedIn
# ==============================

import time
from loguru import logger
from playwright.sync_api import Page, Browser, Playwright, sync_playwright
import config


class LinkedInAuth:
    """Quản lý phiên đăng nhập LinkedIn bằng Playwright."""

    def __init__(self, headless: bool = config.HEADLESS_MODE):
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None

    # ── Khởi động browser ─────────────────────────────────────────────────────
    def start(self) -> Page:
        logger.info("Khởi động trình duyệt...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        self.page = context.new_page()
        # Ẩn dấu hiệu automation
        self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self.page

    # ── Đăng nhập ────────────────────────────────────────────────────────────
    def login(self, email: str = config.LINKEDIN_EMAIL, password: str = config.LINKEDIN_PASSWORD) -> bool:
        if self.page is None:
            self.start()

        logger.info(f"Đăng nhập với tài khoản: {email}")
        self.page.goto(config.LINKEDIN_LOGIN_URL, wait_until="networkidle")
        time.sleep(1)

        # Điền email
        self.page.fill(config.SELECTORS["login_email"], email)
        time.sleep(0.5)

        # Điền password
        self.page.fill(config.SELECTORS["login_password"], password)
        time.sleep(0.5)

        # Click đăng nhập
        self.page.click(config.SELECTORS["login_button"])
        self.page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Kiểm tra đăng nhập thành công
        if "feed" in self.page.url or "checkpoint" in self.page.url:
            logger.success("Đăng nhập thành công!")
            return True
        else:
            # Kiểm tra CAPTCHA / xác minh 2 bước
            if "challenge" in self.page.url or "checkpoint" in self.page.url:
                logger.warning(
                    "LinkedIn yêu cầu xác minh bổ sung (CAPTCHA / 2FA). "
                    "Hãy hoàn tất xác minh thủ công trong cửa sổ trình duyệt."
                )
                input("Nhấn Enter sau khi hoàn tất xác minh...")
                return True
            logger.error("Đăng nhập thất bại. Kiểm tra lại email / mật khẩu.")
            return False

    # ── Dừng browser ─────────────────────────────────────────────────────────
    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Đã đóng trình duyệt.")
