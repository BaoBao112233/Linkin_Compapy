#!/usr/bin/env python3
"""
run_pipeline.py – Pipeline đầy đủ:
  [LLM Keyword Expand] → LinkedIn Search → Website Crawl → Groq LLM Email Extract → CSV

Cách dùng:

  # Tìm + tự động sinh từ khóa liên quan bằng LLM (mặc định):
  python run_pipeline.py --industry "fintech " --limit 5

  # Chỉ định từ khóa thủ công (bỏ qua LLM expand):
  python run_pipeline.py --keyword "neobank,digital payments" --limit 10

  # Kiểm soát số lượng từ khóa LLM sinh ra:
  python run_pipeline.py --industry "healthcare AI" --num-keywords 30 --limit 5

  # Từ file CSV sẵn có (cột: name, website):
  python run_pipeline.py --from-csv my_companies.csv

  # Demo nhanh không cần LinkedIn (dùng dữ liệu mẫu):
  python run_pipeline.py --demo
"""

import argparse
import csv
import os
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from tqdm import tqdm

import config
import exporter
from company_detail import CompanyDetail
from website_email_extractor import WebsiteEmailExtractor
from keyword_generator import KeywordGenerator

# ── Logging ──────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)
os.makedirs("logs", exist_ok=True)
logger.add("logs/pipeline.log", level="DEBUG", rotation="10 MB", retention="7 days")


# ── Dữ liệu demo (không cần LinkedIn) ───────────────────────────────────────
DEMO_COMPANIES = [
    CompanyDetail(name="Groq",          website="https://groq.com",         linkedin_url="https://www.linkedin.com/company/groq-inc/",      industry="Artificial Intelligence"),
    CompanyDetail(name="Linear",        website="https://linear.app",       linkedin_url="https://www.linkedin.com/company/linear-app/",    industry="Computer Software"),
    CompanyDetail(name="Mistral AI",    website="https://mistral.ai",       linkedin_url="https://www.linkedin.com/company/mistralai/",     industry="Artificial Intelligence"),
    CompanyDetail(name="Vercel",        website="https://vercel.com",       linkedin_url="https://www.linkedin.com/company/vercel/",        industry="Internet"),
    CompanyDetail(name="Resend",        website="https://resend.com",       linkedin_url="https://www.linkedin.com/company/resend/",        industry="Computer Software"),
]


# ── Bước 0: LLM generate keywords ───────────────────────────────────────────
def expand_keywords(topic: str, n: int = 20) -> list[str]:
    """Gọi Groq LLM để mở rộng 1 chủ đề → nhiều từ khóa LinkedIn."""
    gen = KeywordGenerator()
    return gen.generate(topic, n=n)


# ── Bước 1: Tìm công ty từ LinkedIn API ─────────────────────────────────────
def search_linkedin(keywords: list[str], limit: int) -> list[CompanyDetail]:
    """Tìm kiếm công ty trên LinkedIn với danh sách từ khóa, trả về danh sách CompanyDetail."""
    from linkedin_api_client import LinkedInAPIClient

    client = LinkedInAPIClient()
    client.connect()

    all_companies: list[CompanyDetail] = []
    seen: set[str] = set()

    for i, kw in enumerate(keywords, 1):
        logger.info(f"[{i}/{len(keywords)}] Tìm kiếm LinkedIn: '{kw}' (tối đa {limit}/keyword)")
        try:
            companies = client.fetch_companies_bulk(kw, limit=limit)
            added = 0
            for c in companies:
                if c.linkedin_url not in seen:
                    seen.add(c.linkedin_url)
                    all_companies.append(c)
                    added += 1
            logger.info(f"  → Thêm mới {added} công ty (tổng: {len(all_companies)})")
        except Exception as exc:
            logger.error(f"Lỗi tìm kiếm '{kw}': {exc}")

    logger.success(f"LinkedIn search xong: {len(all_companies)} công ty duy nhất.")
    return all_companies


# ── Bước 2: Crawl website + LLM extract email ────────────────────────────────
def enrich_emails(
    companies: list[CompanyDetail],
    extractor: WebsiteEmailExtractor,
    force_recrawl: bool = False,
) -> list[CompanyDetail]:
    """
    Với mỗi công ty có website nhưng chưa có email,
    crawl website và dùng Groq LLM để extract email.
    """
    need_crawl = [c for c in companies if c.website and (not c.email or force_recrawl)]
    already    = len(companies) - len(need_crawl)

    logger.info(f"Email enrichment: {already} đã có email, {len(need_crawl)} cần crawl.")

    for i, company in enumerate(tqdm(need_crawl, desc="Crawl website", unit="site"), 1):
        try:
            email = extractor.extract(company.website)
            if email:
                company.email = email
                logger.success(f"  [{i}/{len(need_crawl)}] {company.name:<35} → {email}")
            else:
                logger.debug(f"  [{i}/{len(need_crawl)}] {company.name:<35} → (không tìm thấy)")
        except Exception as exc:
            logger.warning(f"  [{i}/{len(need_crawl)}] Lỗi: {company.name}: {exc}")

        # Delay nhẹ tránh rate-limit
        time.sleep(random.uniform(0.5, 1.2))

    return companies


# ── Bước 3: Lưu CSV ──────────────────────────────────────────────────────────
def save_results(companies: list[CompanyDetail], csv_path: str = config.OUTPUT_CSV):
    records = [c.to_dict() for c in companies]
    exporter.save_csv(records, csv_path)

    # In bảng tóm tắt đẹp
    with_email    = sum(1 for c in companies if c.email)
    without_email = len(companies) - with_email
    print("\n" + "═" * 80)
    print(f"{'Tên công ty':<30} {'Website':<35} {'Email'}")
    print("─" * 80)
    for c in companies:
        print(f"  {c.name:<28} {(c.website or '-'):<35} {c.email or '(không có)'}")
    print("═" * 80)
    print(f"\n  Tổng: {len(companies)} công ty  |  Có email: {with_email}  |  Không có: {without_email}")
    print(f"  Đã lưu CSV: {csv_path}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="[LLM Keyword Expand] → LinkedIn Search → Website Crawl → Groq LLM Email Extract → CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Nguồn từ khóa
    kw_group = parser.add_mutually_exclusive_group()
    kw_group.add_argument(
        "--industry", "-i", default="",
        metavar="TOPIC",
        help="Lĩnh vực / chủ đề. LLM sẽ tự sinh từ khóa liên quan. Vd: 'fintech '",
    )
    kw_group.add_argument(
        "--keyword", "-k", default="",
        help="Chỉ định từ khóa thủ công (bỏ qua LLM expand). Nhiều từ khóa cách nhau dấu phẩy.",
    )
    kw_group.add_argument(
        "--from-csv", metavar="FILE",
        help="Đọc danh sách công ty từ CSV (cột: name, website). Bỏ qua LinkedIn search.",
    )
    kw_group.add_argument(
        "--demo", action="store_true",
        help="Chạy demo với dữ liệu mẫu, không cần LinkedIn credentials.",
    )
    # Kiểm soát số lượng
    parser.add_argument("--num-keywords", "-n", type=int, default=20,
                        help="Số từ khóa LLM sinh ra (chỉ dùng với --industry, mặc định: 20)")
    parser.add_argument("--limit", "-l", type=int, default=5,
                        help="Số công ty tối đa mỗi từ khóa LinkedIn (mặc định: 5)")
    parser.add_argument("--output", "-o", default=config.OUTPUT_CSV,
                        help=f"File CSV đầu ra (mặc định: {config.OUTPUT_CSV})")
    parser.add_argument("--force-recrawl", action="store_true",
                        help="Crawl lại website dù công ty đã có email từ LinkedIn.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chỉ sinh & hiển thị từ khóa, không chạy LinkedIn search.")

    args = parser.parse_args()

    extractor = WebsiteEmailExtractor()
    companies: list[CompanyDetail] = []

    # ── Chọn nguồn dữ liệu ──────────────────────────────────────────────────
    if args.demo:
        logger.info("Chế độ DEMO – dùng dữ liệu mẫu (không cần LinkedIn credentials).")
        companies = DEMO_COMPANIES[:]

    elif args.from_csv:
        logger.info(f"Đọc công ty từ file: {args.from_csv}")
        with open(args.from_csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name    = row.get("name") or row.get("company") or ""
                website = row.get("website") or row.get("url") or ""
                email   = row.get("email") or ""
                if website:
                    companies.append(CompanyDetail(name=name, website=website, email=email))
        logger.info(f"Đọc được {len(companies)} công ty từ CSV.")

    elif args.industry:
        # ── LLM expand keywords rồi search LinkedIn ──────────────────────
        logger.info("═" * 60)
        logger.info(f"  Chủ đề: '{args.industry}'")
        logger.info(f"  Đang sinh ~{args.num_keywords} từ khóa bằng Groq LLM...")
        logger.info("═" * 60)

        keywords = expand_keywords(args.industry, n=args.num_keywords)

        # Hiển thị bảng từ khóa
        print("\n" + "─" * 60)
        print(f"  LLM sinh được {len(keywords)} từ khóa cho '{args.industry}':")
        print("─" * 60)
        for idx, kw in enumerate(keywords, 1):
            print(f"  {idx:>3}. {kw}")
        print("─" * 60)
        print(f"  → Sẽ search LinkedIn với mỗi từ khóa, tối đa {args.limit} công ty/keyword")
        print(f"  → Tổng tối đa: ~{len(keywords) * args.limit} công ty (sau dedup sẽ ít hơn)")
        print("─" * 60 + "\n")

        if args.dry_run:
            logger.info("--dry-run: dừng tại đây, không chạy LinkedIn search.")
            sys.exit(0)

        companies = search_linkedin(keywords, args.limit)

    elif args.keyword:
        # Từ khóa thủ công
        keywords = [k.strip() for k in args.keyword.split(",") if k.strip()]
        logger.info(f"Từ khóa thủ công ({len(keywords)}): {keywords}")
        companies = search_linkedin(keywords, args.limit)

    else:
        parser.print_help()
        sys.exit(0)

    if not companies:
        logger.warning("Không có công ty nào để xử lý.")
        sys.exit(0)

    # ── Crawl website + extract email ────────────────────────────────────────
    logger.info(f"\n{'─'*60}")
    logger.info(f"Crawl website + extract email ({len(companies)} công ty)...")
    logger.info(f"LLM backend: {'Groq (' + config.GROQ_MODEL + ')' if config.GROQ_API_KEY else 'Regex fallback (thiếu GROQ_API_KEY)'}")
    logger.info(f"{'─'*60}\n")

    companies = enrich_emails(companies, extractor, force_recrawl=args.force_recrawl)

    # ── Lưu kết quả ─────────────────────────────────────────────────────────
    save_results(companies, args.output)


if __name__ == "__main__":
    main()
