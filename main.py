#!/usr/bin/env python3
# ==============================
# LinkedIn Company Scraper
# File: main.py
# Điểm khởi chạy chính
# ==============================
"""
Cách dùng:

  # Dùng unofficial API (nhanh hơn, không cần browser):
  python main.py --mode api --keyword "fintech" --limit 200

  # Dùng Playwright browser (ổn định hơn):
  python main.py --mode browser --keyword "healthcare" --location "United States" --pages 5

  # Nhiều từ khóa + nhiều quốc gia:
  python main.py --mode api --keyword "technology,fintech" --limit 500

  # Xuất ra file Excel:
  python main.py --mode api --keyword "saas" --limit 100 --format excel
"""

import argparse
import sys
import time
import random

from loguru import logger
from tqdm import tqdm

import config
import exporter
from company_detail import CompanyDetail


# ── Logging setup ──────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add("logs/scraper.log", level="DEBUG", rotation="10 MB", retention="7 days")


# ── Mode 1: Unofficial API ─────────────────────────────────────────────────
def run_api_mode(keyword: str, limit: int, output_format: str):
    import signal
    from linkedin_api_client import LinkedInAPIClient

    client = LinkedInAPIClient()
    client.connect()

    keywords = [k.strip() for k in keyword.split(",")]
    all_details: list[CompanyDetail] = []
    seen_urls: set[str] = set()

    # ── Auto-save khi bấm Ctrl+C ────────────────────────────────────────
    def _save_and_exit(sig, frame):
        logger.warning("\nĐã nhận Ctrl+C – đang lưu dữ liệu đã thu thập...")
        if all_details:
            _export([d.to_dict() for d in all_details], output_format)
        else:
            logger.warning("Chưa có dữ liệu để lưu.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _save_and_exit)

    try:
        for kw in keywords:
            logger.info(f"━━ Từ khóa: '{kw}' (limit={limit}) ━━")
            for detail in client.fetch_companies_bulk(kw, limit=limit):
                if detail.linkedin_url not in seen_urls:
                    seen_urls.add(detail.linkedin_url)
                    all_details.append(detail)
            # Lưu checkpoint sau mỗi keyword
            if all_details:
                _export([d.to_dict() for d in all_details], output_format)
                logger.info(f"  → Checkpoint: đã lưu {len(all_details)} công ty.")
    except KeyboardInterrupt:
        logger.warning("\nĐã nhận Ctrl+C – đang lưu dữ liệu đã thu thập...")
        if all_details:
            _export([d.to_dict() for d in all_details], output_format)
        else:
            logger.warning("Chưa có dữ liệu để lưu.")
        sys.exit(0)


# ── Mode 2: Playwright Browser ─────────────────────────────────────────────
def run_browser_mode(
    keyword: str,
    location: str,
    pages: int,
    detailed: bool,
    output_format: str,
):
    from linkedin_auth import LinkedInAuth
    from company_scraper import CompanySearchScraper
    from company_detail import CompanyDetailScraper

    auth = LinkedInAuth(headless=config.HEADLESS_MODE)
    try:
        page = auth.start()
        if not auth.login():
            logger.error("Không thể tiếp tục do đăng nhập thất bại.")
            return

        keywords = [k.strip() for k in keyword.split(",")]
        locations = [l.strip() for l in location.split(",")] if location else [""]
        all_records: list[dict] = []
        seen_urls: set[str] = set()

        search_scraper = CompanySearchScraper(page)
        detail_scraper = CompanyDetailScraper(page)

        for kw in keywords:
            for loc in locations:
                logger.info(f"━━ Từ khóa: '{kw}' | Quốc gia: '{loc or 'Toàn cầu'}' ━━")
                basics = list(
                    tqdm(
                        search_scraper.search(kw, location=loc, max_pages=pages),
                        desc=f"  Tìm kiếm '{kw}'",
                        unit=" công ty",
                    )
                )
                logger.info(f"  Tìm thấy {len(basics)} công ty từ tìm kiếm.")

                if detailed:
                    # Lấy chi tiết từng công ty (có website)
                    logger.info("  Đang lấy thông tin chi tiết (bao gồm website)...")
                    for basic in tqdm(basics, desc="  Chi tiết", unit=" công ty"):
                        if basic.linkedin_url in seen_urls:
                            continue
                        seen_urls.add(basic.linkedin_url)
                        try:
                            detail = detail_scraper.fetch(basic.linkedin_url)
                            # Bổ sung dữ liệu search
                            detail.location_search   = basic.location
                            detail.followers_search  = basic.followers
                            detail.description_short = basic.description_short
                            if not detail.name:
                                detail.name = basic.name
                            all_records.append(detail.to_dict())
                            time.sleep(random.uniform(1.0, 2.0))
                        except Exception as exc:
                            logger.warning(f"  Lỗi khi lấy chi tiết '{basic.name}': {exc}")
                            # Vẫn lưu dữ liệu cơ bản
                            from dataclasses import asdict
                            all_records.append(asdict(basic))
                else:
                    # Chỉ lưu dữ liệu tìm kiếm (nhanh hơn, không có website)
                    from dataclasses import asdict
                    for basic in basics:
                        if basic.linkedin_url not in seen_urls:
                            seen_urls.add(basic.linkedin_url)
                            all_records.append(asdict(basic))

        _export(all_records, output_format)

    finally:
        auth.close()


# ── Xuất dữ liệu ────────────────────────────────────────────────────────────
def _export(records: list[dict], output_format: str):
    if not records:
        logger.warning("Không có dữ liệu để xuất.")
        return
    logger.info(f"Tổng cộng: {len(records)} công ty.")
    if output_format == "all":
        exporter.save_all(records)
    elif output_format == "csv":
        exporter.save_csv(records)
    elif output_format == "json":
        exporter.save_json(records)
    elif output_format == "excel":
        exporter.save_excel(records)


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Company Scraper – Lấy thông tin công ty toàn cầu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", choices=["api", "browser"], default="api",
        help="api = unofficial API (nhanh), browser = Playwright (ổn định). Mặc định: api"
    )
    parser.add_argument(
        "--keyword", default="technology",
        help="Từ khóa tìm kiếm. Nhiều từ khóa cách nhau bằng dấu phẩy. Mặc định: technology"
    )
    parser.add_argument(
        "--location", default="",
        help="Quốc gia (chỉ dùng với --mode browser). Vd: 'United States,'"
    )
    parser.add_argument(
        "--pages", type=int, default=5,
        help="Số trang tìm kiếm (chỉ dùng với --mode browser). Mặc định: 5"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Số công ty tối đa (dùng với --mode api). Mặc định: 100"
    )
    parser.add_argument(
        "--detailed", action="store_true", default=True,
        help="Lấy chi tiết (website, quy mô, ...) cho mỗi công ty. Mặc định: True"
    )
    parser.add_argument(
        "--no-detailed", dest="detailed", action="store_false",
        help="Chỉ lấy dữ liệu cơ bản từ tìm kiếm (nhanh hơn)"
    )
    parser.add_argument(
        "--format", dest="output_format",
        choices=["csv", "json", "excel", "all"], default="all",
        help="Định dạng xuất file. Mặc định: all (CSV + JSON + Excel)"
    )

    args = parser.parse_args()

    import os
    os.makedirs("logs", exist_ok=True)

    logger.info("=" * 60)
    logger.info("  LinkedIn Company Scraper  –  github.com/BaorBaor")
    logger.info("=" * 60)
    logger.info(f"  Chế độ:   {args.mode}")
    logger.info(f"  Từ khóa:  {args.keyword}")
    logger.info(f"  Định dạng: {args.output_format}")
    logger.info("=" * 60)

    if args.mode == "api":
        run_api_mode(args.keyword, args.limit, args.output_format)
    else:
        run_browser_mode(
            keyword=args.keyword,
            location=args.location,
            pages=args.pages,
            detailed=args.detailed,
            output_format=args.output_format,
        )


if __name__ == "__main__":
    main()
