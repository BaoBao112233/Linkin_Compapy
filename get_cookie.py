#!/usr/bin/env python3
"""
get_cookie.py – Đăng nhập LinkedIn qua browser thật,
lưu cookie li_at vào file .env để dùng cho API mode.

Chạy một lần:
    python get_cookie.py
"""
import sys, os, re, time
sys.path.insert(0, os.path.dirname(__file__))

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv, set_key

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_FILE)

EMAIL    = os.getenv("LINKEDIN_EMAIL", "")
PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")


def get_li_at_cookie() -> str:
    print("\n" + "="*60)
    print("  Lấy cookie li_at từ LinkedIn")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)   # Hiện browser để xử lý CAPTCHA
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        print(f"\n  → Mở LinkedIn Login...")
        page.goto("https://www.linkedin.com/login", wait_until="networkidle")
        time.sleep(1)

        # Điền thông tin nếu có
        if EMAIL and EMAIL != "your_email@example.com":
            page.fill("#username", EMAIL)
            time.sleep(0.4)
        if PASSWORD and PASSWORD != "your_password":
            page.fill("#password", PASSWORD)
            time.sleep(0.4)
            page.click("button[type='submit']")
            print("  → Đã tự động điền thông tin đăng nhập.")
        else:
            print("  → Vui lòng điền email và mật khẩu trong cửa sổ browser.")

        print("\n  ⏳ Đang chờ bạn đăng nhập thành công...")
        print("     (Nếu có CAPTCHA / xác minh email, hãy hoàn tất rồi nhấn Enter ở đây)")

        # Chờ đến khi vào được feed hoặc user nhấn Enter
        def check_logged_in() -> bool:
            try:
                return "feed" in page.url or "mynetwork" in page.url or "jobs" in page.url
            except Exception:
                return False

        max_wait = 120  # tối đa 2 phút
        waited = 0
        while not check_logged_in() and waited < max_wait:
            time.sleep(1)
            waited += 1

        if not check_logged_in():
            print("\n  ⚠️  Chưa phát hiện đăng nhập thành công.")
            input("     Nhấn Enter sau khi đăng nhập xong trong browser...")

        # Lấy cookie li_at
        cookies = ctx.cookies("https://www.linkedin.com")
        li_at = next((c["value"] for c in cookies if c["name"] == "li_at"), None)
        jsessionid = next((c["value"] for c in cookies if c["name"] == "JSESSIONID"), "")

        browser.close()

    if not li_at:
        print("\n  ✗ Không lấy được cookie li_at. Thử lại sau.")
        sys.exit(1)

    # Ghi vào .env
    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()
    set_key(ENV_FILE, "LINKEDIN_LI_AT", li_at)
    if jsessionid:
        set_key(ENV_FILE, "LINKEDIN_JSESSIONID", jsessionid.strip('"'))

    print(f"\n  ✅ Đã lưu cookie vào .env")
    print(f"     li_at = {li_at[:30]}...")
    print("\n  Bây giờ chạy scraper:")
    print("     python main.py --mode api --keyword 'technology' --limit 100\n")
    return li_at


if __name__ == "__main__":
    get_li_at_cookie()
