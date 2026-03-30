#!/usr/bin/env python3
"""
test_email_extractor.py
Chạy thử WebsiteEmailExtractor và lưu kết quả vào output/email_test.csv

Cách chạy:
    python test_email_extractor.py
"""
import sys
sys.path.insert(0, "/home/baobao/Projects/Linkin_Compapy")

import os
import csv
from pathlib import Path
from loguru import logger
from website_email_extractor import WebsiteEmailExtractor
import config

# ── Cấu hình log đẹp ─────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)

# ── Danh sách website thử nghiệm ─────────────────────────────────────────────
TEST_WEBSITES = [
    ("Anthropic",         "https://www.anthropic.com"),
    ("Groq",              "https://groq.com"),
    ("Hugging Face",      "https://huggingface.co"),
    ("Notion",            "https://www.notion.so"),
    ("Linear",            "https://linear.app"),
]

OUTPUT_CSV = os.path.join(config.OUTPUT_DIR, "email_test.csv")

def main():
    # Đảm bảo thư mục output tồn tại
    Path(config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    extractor = WebsiteEmailExtractor()

    print("\n" + "═" * 65)
    print("  WebsiteEmailExtractor – Kết quả")
    print("═" * 65)
    print(f"{'Công ty':<20} {'Website':<35} {'Email tìm được'}")
    print("─" * 65)

    rows = []
    for company, url in TEST_WEBSITES:
        try:
            emails = extractor.extract_all(url)
            email_str = ", ".join(emails) if emails else ""
            status = "✓" if emails else "✗"
            print(f"{status} {company:<18} {url:<35} {email_str or '(không tìm thấy)'}")
        except Exception as exc:
            logger.error(f"Lỗi xử lý {url}: {exc}")
            email_str = ""
            print(f"✗ {company:<18} {url:<35} LỖI: {exc}")

        rows.append({
            "company":  company,
            "website":  url,
            "email":    email_str,
            "source":   "LLM+Regex" if config.GROQ_API_KEY else "Regex",
        })

    # ── Lưu CSV ────────────────────────────────────────────────────────────
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["company", "website", "email", "source"])
        writer.writeheader()
        writer.writerows(rows)

    print("═" * 65)
    found = sum(1 for r in rows if r["email"])
    print(f"\nTổng kết : {found}/{len(TEST_WEBSITES)} website có email.")
    print(f"Đã lưu   : {OUTPUT_CSV}\n")


if __name__ == "__main__":
    main()
