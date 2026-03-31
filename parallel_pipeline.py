#!/usr/bin/env python3
# ==============================
# Parallel Pipeline
# File: parallel_pipeline.py
# Chạy song song LinkedIn + Telegram
# ==============================
"""
Crawl thông tin công ty từ LinkedIn và Telegram đồng thời.

Cách dùng:

  # Tìm kiếm theo keyword (cả LinkedIn + Telegram):
  python parallel_pipeline.py --keyword "fintech " --limit 50

  # Chỉ Telegram:
  python parallel_pipeline.py --keyword "startup" --limit 30 --source telegram

  # Chỉ LinkedIn:
  python parallel_pipeline.py --keyword "technology" --limit 100 --source linkedin

  # Xuất Excel:
  python parallel_pipeline.py --keyword "healthcare" --limit 50 --format excel

  # Chỉ tìm trên các kênh Telegram cụ thể:
  python parallel_pipeline.py --keyword "saas" --channels startups,tech
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger
from tqdm import tqdm

import config
import exporter
from company_detail import CompanyDetail
from telegram_scraper import TelegramScraper, TelegramCompany

# ── Suppress noisy httpx / urllib3 logs ─────────────────────────────────────
import logging as _logging
_logging.getLogger("httpx").setLevel(_logging.WARNING)
_logging.getLogger("httpcore").setLevel(_logging.WARNING)

# ── Logging ──────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)
logger.add("logs/parallel_pipeline.log", level="DEBUG", rotation="10 MB")


# ══════════════════════════════════════════════════════════════════════════════
# LinkedIn runner (chạy trong thread vì linkedin_api_client là synchronous)
# ══════════════════════════════════════════════════════════════════════════════
def _run_linkedin(keyword: str, limit: int) -> list[dict]:
    """Chạy LinkedIn scraper trong thread pool (synchronous)."""
    try:
        from linkedin_api_client import LinkedInAPIClient
        client = LinkedInAPIClient()
        client.connect()
        results: list[dict] = []
        seen: set[str] = set()

        logger.info(f"[LinkedIn] Bắt đầu tìm: '{keyword}' (limit={limit})")
        for detail in client.fetch_companies_bulk(keyword, limit=limit):
            if detail.linkedin_url not in seen:
                seen.add(detail.linkedin_url)
                d = detail.to_dict()
                d["source"] = "linkedin"
                results.append(d)
                logger.debug(f"  [LinkedIn] {detail.name}")

        logger.success(f"[LinkedIn] Lấy được {len(results)} công ty")
        return results
    except ImportError:
        logger.warning("[LinkedIn] Chưa cài linkedin-api – bỏ qua LinkedIn.")
        return []
    except Exception as exc:
        logger.error(f"[LinkedIn] Lỗi: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Telegram runner (async)
# ══════════════════════════════════════════════════════════════════════════════
async def _run_telegram(
    keyword: str,
    limit: int,
    channels: list[str] | None = None,
) -> list[dict]:
    """Chạy Telegram scraper (async)."""
    try:
        async with TelegramScraper() as tg:
            logger.info(f"[Telegram] Bắt đầu tìm: '{keyword}' (limit={limit})")
            companies = await tg.search_companies(keyword, limit=limit, channels=channels)
            results = [c.to_dict() for c in companies]
            logger.success(f"[Telegram] Lấy được {len(results)} công ty")
            return results
    except Exception as exc:
        logger.error(f"[Telegram] Lỗi: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Merge & deduplicate
# ══════════════════════════════════════════════════════════════════════════════
def _merge_results(linkedin: list[dict], telegram: list[dict]) -> list[dict]:
    """
    Gộp kết quả từ 2 nguồn, loại bỏ trùng lặp theo tên công ty.
    Ưu tiên giữ bản đầy đủ hơn (nhiều field không rỗng hơn).
    """
    merged: dict[str, dict] = {}

    def _score(r: dict) -> int:
        return sum(1 for v in r.values() if v)

    for record in linkedin + telegram:
        key = (record.get("name") or "").strip().lower()
        if not key:
            continue
        if key not in merged or _score(record) > _score(merged[key]):
            merged[key] = record

    results = list(merged.values())
    # Sắp xếp: LinkedIn trước, Telegram sau
    results.sort(key=lambda r: (r.get("source", "z"), r.get("name", "")))
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Export
# ══════════════════════════════════════════════════════════════════════════════
def _export(records: list[dict], fmt: str, keyword: str = ""):
    """Lưu kết quả theo format yêu cầu."""
    safe_kw = keyword.replace(" ", "_").replace(",", "-")[:30] if keyword else "combined"
    suffix  = f"_{safe_kw}" if safe_kw else ""

    if fmt in ("csv", "all"):
        path = f"{config.OUTPUT_DIR}/companies_parallel{suffix}.csv"
        exporter.save_csv(records, path)
    if fmt in ("json", "all"):
        path = f"{config.OUTPUT_DIR}/companies_parallel{suffix}.json"
        exporter.save_json(records, path)
    if fmt in ("excel", "all"):
        path = f"{config.OUTPUT_DIR}/companies_parallel{suffix}.xlsx"
        exporter.save_excel(records, path)
    if fmt == "all":
        pass  # đã lưu 3 định dạng ở trên


# ══════════════════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════════════════
async def run_parallel(
    keyword: str,
    limit: int            = 50,
    source: str           = "both",   # "linkedin" | "telegram" | "both"
    output_format: str    = "csv",
    channels: list[str] | None = None,
) -> list[dict]:
    """
    Chạy pipeline song song LinkedIn + Telegram và trả về danh sách merged.
    """
    start = time.time()
    linkedin_results:  list[dict] = []
    telegram_results: list[dict] = []

    loop = asyncio.get_event_loop()

    # ── Chạy song song bằng asyncio.gather ──────────────────────────────
    async def _linkedin_async():
        if source in ("linkedin", "both"):
            executor = ThreadPoolExecutor(max_workers=1)
            return await loop.run_in_executor(executor, _run_linkedin, keyword, limit)
        return []

    async def _telegram_async():
        if source in ("telegram", "both"):
            return await _run_telegram(keyword, limit, channels)
        return []

    logger.info(f"Bắt đầu parallel pipeline | keyword='{keyword}' | source={source} | limit={limit}")

    li_task, tg_task = await asyncio.gather(
        _linkedin_async(),
        _telegram_async(),
        return_exceptions=True,
    )

    if isinstance(li_task, list):
        linkedin_results = li_task
    else:
        logger.warning(f"LinkedIn task lỗi: {li_task}")

    if isinstance(tg_task, list):
        telegram_results = tg_task
    else:
        logger.warning(f"Telegram task lỗi: {tg_task}")

    # ── Merge ────────────────────────────────────────────────────────────
    merged = _merge_results(linkedin_results, telegram_results)

    elapsed = time.time() - start
    logger.success(
        f"Hoàn thành! LinkedIn={len(linkedin_results)}, "
        f"Telegram={len(telegram_results)}, "
        f"Merged={len(merged)}, "
        f"Thời gian={elapsed:.1f}s"
    )

    # ── Export ───────────────────────────────────────────────────────────
    if merged:
        _export(merged, output_format, keyword)

    return merged


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Crawl thông tin công ty từ LinkedIn + Telegram song song"
    )
    parser.add_argument("--keyword",  "-k", default="technology ",
                        help="Từ khóa tìm kiếm (mặc định: 'technology ')")
    parser.add_argument("--limit",    "-n", type=int, default=50,
                        help="Số công ty tối đa mỗi nguồn (mặc định: 50)")
    parser.add_argument("--source",   "-s", default="both",
                        choices=["both", "linkedin", "telegram"],
                        help="Nguồn dữ liệu (mặc định: both)")
    parser.add_argument("--format",   "-f", default="csv",
                        choices=["csv", "json", "excel", "all"],
                        help="Định dạng xuất file (mặc định: csv)")
    parser.add_argument("--channels", "-c", default="",
                        help="Kênh Telegram cụ thể, cách nhau bằng dấu phẩy")
    args = parser.parse_args()

    channels = [c.strip() for c in args.channels.split(",") if c.strip()] or None

    asyncio.run(
        run_parallel(
            keyword=args.keyword,
            limit=args.limit,
            source=args.source,
            output_format=args.format,
            channels=channels,
        )
    )


if __name__ == "__main__":
    main()
