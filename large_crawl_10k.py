#!/usr/bin/env python3
# ==============================
# Large Scale Crawl – 10K+ Companies (GLOBAL)
# File: large_crawl_10k.py
# Thu thập ~10.000+ công ty từ LinkedIn + Telegram – thị trường TOÀN CẦU
# Markets:  · SEA · India · USA · EU · MEA · LATAM · East Asia
# ==============================
"""
Thiết kế:
  LinkedIn : 300+ keywords × 200 results → ~10.000-20.000 công ty (dedup)
  Telegram : 130+ kênh global (VN + SEA + India + USA + EU + Africa + LATAM)
  Tổng mục tiêu: ~10.000+ công ty duy nhất TOÀN CẦU

Tính năng:
  - Checkpoint mỗi 200 công ty (tiếp tục khi bị ngắt)
  - Dedup theo linkedin_url / channel username
  - Progress bar tqdm
  - Stats report cuối

Cách chạy:
  python large_crawl_10k.py                    # chạy đầy đủ (cả 2 nguồn)
  python large_crawl_10k.py --source linkedin  # chỉ LinkedIn
  python large_crawl_10k.py --source telegram  # chỉ Telegram
  python large_crawl_10k.py --resume           # tiếp tục từ checkpoint
  python large_crawl_10k.py --target 10000     # tuỳ chỉnh đích
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
from tqdm import tqdm

import config
import exporter

# ── Logging ──────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
)
logger.add("logs/large_crawl_10k.log", level="DEBUG", rotation="50 MB", retention="14 days")

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR   = Path(config.OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_LI  = OUTPUT_DIR / "checkpoint_linkedin_10k.json"
CHECKPOINT_TG  = OUTPUT_DIR / "checkpoint_telegram_10k.json"
FINAL_CSV      = OUTPUT_DIR / "companies_10k.csv"
FINAL_JSON     = OUTPUT_DIR / "companies_10k.json"
FINAL_EXCEL    = OUTPUT_DIR / "companies_10k.xlsx"


# ══════════════════════════════════════════════════════════════════════════════
# Keyword library – GLOBAL markets (USA / EU / SEA / India / LATAM / Global)
# ══════════════════════════════════════════════════════════════════════════════
LINKEDIN_KEYWORD_BATCHES = [

    # ════════════════════════════════════════════════════════════════
    #  (home market – keep a solid base)
    # ════════════════════════════════════════════════════════════════
    ["fintech ", "digital payments ", "mobile banking ",
     "software company ", "IT outsourcing ", "tech startup ",
     "SaaS ", "AI ", "e-commerce ", "logistics ",
     "healthtech ", "edtech ", "proptech ",
     "digital marketing ", "manufacturing ",
     "clean energy ", "consulting ", "BPO ",
     "venture capital ", "startup Ho Chi Minh City",
     "công ty công nghệ", "phần mềm Việt Nam", "chuyển đổi số"],

    # ════════════════════════════════════════════════════════════════
    # SOUTHEAST ASIA – regional
    # ════════════════════════════════════════════════════════════════
    # Singapore
    ["fintech Singapore", "tech startup Singapore", "SaaS Singapore",
     "AI company Singapore", "e-commerce Singapore", "logistics Singapore",
     "healthtech Singapore", "edtech Singapore", "proptech Singapore",
     "digital bank Singapore", "cybersecurity Singapore",
     "venture capital Singapore", "Series A Singapore"],

    # Indonesia
    ["fintech Indonesia", "tech startup Indonesia", "e-commerce Indonesia",
     "gojek ecosystem", "tokopedia", "SaaS Indonesia", "AI Indonesia",
     "logistics Indonesia", "healthtech Indonesia", "edtech Indonesia",
     "startup Jakarta", "digital payment Indonesia"],

    # Thailand / Philippines / Malaysia / Myanmar
    ["tech startup Thailand", "fintech Thailand", "startup Bangkok",
     "fintech Philippines", "tech company Philippines", "startup Manila",
     "tech startup Malaysia", "fintech Malaysia", "startup Kuala Lumpur",
     "startup Myanmar", "tech company Cambodia", "startup Southeast Asia"],

    # SEA – broad
    ["Southeast Asia startup", "SEA tech company", "ASEAN fintech",
     "ASEAN e-commerce", "Southeast Asia SaaS", "Southeast Asia unicorn",
     "Southeast Asia venture capital", "Grab", "Sea Limited",
     "Gojek", "Shopee Southeast Asia"],

    # ════════════════════════════════════════════════════════════════
    # INDIA
    # ════════════════════════════════════════════════════════════════
    ["fintech India", "SaaS India", "tech startup India", "IT services India",
     "AI company India", "e-commerce India", "healthtech India",
     "edtech India", "startup Bangalore", "startup Mumbai", "startup Delhi",
     "startup Hyderabad", "startup Pune", "unicorn India",
     "software outsourcing India", "BPO India", "digital payments India",
     "Flipkart", "Razorpay", "CRED India", "Zepto India"],

    # ════════════════════════════════════════════════════════════════
    # UNITED STATES
    # ════════════════════════════════════════════════════════════════
    # Silicon Valley / SF Bay Area
    ["startup Silicon Valley", "tech company San Francisco",
     "AI company San Francisco", "SaaS San Francisco",
     "fintech San Francisco", "startup Bay Area",
     "biotech San Francisco", "deep tech Silicon Valley"],

    # New York
    ["fintech New York", "startup New York", "tech company New York",
     "SaaS New York", "adtech New York", "media company New York",
     "Wall Street fintech", "proptech New York"],

    # Austin / Seattle / Boston / Miami / LA
    ["startup Austin", "tech company Seattle", "startup Boston",
     "biotech Boston", "startup Miami", "tech company Los Angeles",
     "startup Denver", "startup Chicago"],

    # USA – broad verticals
    ["AI startup USA", "generative AI company", "LLM startup",
     "B2B SaaS company", "enterprise software company",
     "cloud computing company", "cybersecurity company USA",
     "data analytics company", "developer tools company",
     "API company", "infrastructure software", "devops company",
     "observability startup", "no-code platform"],

    # US – sector
    ["healthtech USA", "digital health company", "medical AI",
     "telemedicine company", "biotech company", "pharma tech",
     "insurtech USA", "legaltech USA", "regtech company",
     "proptech USA", "construction tech", "climate tech USA",
     "clean energy company", "EV startup USA", "agritech USA"],

    # US – consumer & media
    ["consumer startup USA", "social media startup",
     "creator economy company", "subscription company",
     "marketplace startup USA", "gaming company USA",
     "streaming company", "D2C brand USA"],

    # US – VC / funding
    ["Y Combinator portfolio", "a16z portfolio", "Sequoia portfolio",
     "Tiger Global portfolio", "Series B startup", "Series C startup",
     "growth equity USA", "SPAC technology"],

    # ════════════════════════════════════════════════════════════════
    # EUROPE
    # ════════════════════════════════════════════════════════════════
    # UK / London
    ["fintech London", "startup London", "tech company London",
     "SaaS London", "AI company UK", "healthtech UK",
     "insurtech London", "proptech London", "legaltech UK"],

    # Germany / DACH
    ["tech startup Germany", "startup Berlin", "SaaS Germany",
     "fintech Germany", "industry 4.0 Germany", "manufacturing tech Germany",
     "startup Munich", "startup Hamburg", "B2B software Germany"],

    # France
    ["startup Paris", "tech company France", "AI company France",
     "SaaS France", "fintech France", "deeptech France"],

    # Netherlands / Nordics
    ["startup Amsterdam", "tech company Netherlands",
     "startup Stockholm", "fintech Stockholm", "startup Helsinki",
     "startup Copenhagen", "Nordic startup", "startup Oslo"],

    # EU – broad
    ["European startup", "EU tech company", "Berlin startup ecosystem",
     "European unicorn", "EU SaaS", "EU fintech",
     "European deep tech", "EU cybersecurity"],

    # ════════════════════════════════════════════════════════════════
    # MIDDLE EAST & AFRICA
    # ════════════════════════════════════════════════════════════════
    ["fintech Dubai", "startup Dubai", "tech company UAE",
     "startup Abu Dhabi", "DIFC fintech", "startup Israel",
     "Israeli tech", "cybersecurity Israel", "startup Tel Aviv",
     "fintech Africa", "startup Lagos", "fintech Nigeria",
     "fintech Kenya", "startup Nairobi", "African tech"],

    # ════════════════════════════════════════════════════════════════
    # LATAM
    # ════════════════════════════════════════════════════════════════
    ["fintech Brazil", "startup São Paulo", "tech company Brazil",
     "fintech Mexico", "startup Mexico City", "e-commerce LATAM",
     "startup Colombia", "startup Buenos Aires",
     "nubank", "Mercado Libre", "LATAM unicorn"],

    # ════════════════════════════════════════════════════════════════
    # CHINA / EAST ASIA
    # ════════════════════════════════════════════════════════════════
    ["tech company China", "AI company China", "startup Shanghai",
     "startup Beijing", "fintech China", "SaaS China",
     "tech company Japan", "startup Tokyo", "fintech Japan",
     "tech company Korea", "startup Seoul", "fintech Korea",
     "K-startup", "Japanese SaaS"],

    # ════════════════════════════════════════════════════════════════
    # GLOBAL – industry verticals (no region)
    # ════════════════════════════════════════════════════════════════
    # AI / ML
    ["artificial intelligence company", "machine learning startup",
     "generative AI", "LLM company", "AI platform",
     "computer vision company", "NLP company", "AI infrastructure",
     "MLOps startup", "AI agent company"],

    # Cloud & Infra
    ["cloud company", "cloud native startup", "SaaS company",
     "PaaS company", "IaaS provider", "serverless company",
     "data warehouse company", "database startup",
     "cloud security company", "zero trust security"],

    # Fintech global
    ["global fintech", "neobank", "digital bank",
     "open banking", "embedded finance", "BNPL company",
     "crypto exchange", "DeFi protocol", "Web3 company",
     "payment processing company", "remittance company"],

    # Health & Bio
    ["digital health company", "biotech company", "genomics company",
     "precision medicine", "health AI", "drug discovery AI",
     "clinical trial tech", "medtech company"],

    # Climate & Energy
    ["climate tech company", "cleantech startup", "renewable energy company",
     "carbon capture company", "green hydrogen", "EV company",
     "smart grid company", "energy storage startup"],

    # Future of Work
    ["future of work startup", "remote work platform",
     "HR tech company", "talent marketplace",
     "workforce management", "collaboration tool company",
     "productivity startup"],

    # Mobility & Logistics
    ["mobility startup", "autonomous vehicle company",
     "drone delivery startup", "supply chain tech",
     "freight tech", "last-mile logistics startup",
     "fleet management company"],

    # Space & Deep Tech
    ["space tech startup", "satellite company",
     "quantum computing company", "robotics startup",
     "nanotechnology company", "semiconductor startup",
     "photonics company"],

    # ════════════════════════════════════════════════════════════════
    # INVESTMENT / VC / ACCELERATORS (global)
    # ════════════════════════════════════════════════════════════════
    ["venture capital firm", "early stage investor",
     "corporate venture capital", "startup accelerator",
     "tech incubator", "family office tech",
     "sovereign wealth fund tech", "growth equity firm"],
]

# Flat list (dedup)
_seen_kw: set[str] = set()
ALL_LINKEDIN_KEYWORDS: list[str] = []
for _batch in LINKEDIN_KEYWORD_BATCHES:
    for _kw in _batch:
        _kw_lower = _kw.lower()
        if _kw_lower not in _seen_kw:
            _seen_kw.add(_kw_lower)
            ALL_LINKEDIN_KEYWORDS.append(_kw)


# ══════════════════════════════════════════════════════════════════════════════
# Telegram channel library – 120+ kênh business VN
# ══════════════════════════════════════════════════════════════════════════════
TELEGRAM_CHANNELS_LARGE: list[str] = [
    # ═══════════════════════════════════════════════════════════
    #  – Business / Finance news
    # ═══════════════════════════════════════════════════════════
    "cafef_vn", "tinnhanhchungkhoan", "vneconomy", "baodautu_vn",
    "nhipcaudautu", "doanhnhanonline", "thuongtruong", "bizlive",
    "doanhtri_vn", "nhipsongkinhdoanh", "markettimes_vn", "stockbiz_vn",
    "vnexpress_kinh_doanh", "tuoitre_kinhte", "zingnews_kd",

    # VN – Startup / VC / IT
    "tech", "tech", "fintechvn", "startupviet",
    "vnstartup", "vietfuture_vc", "mekong_capital", "do_ventures",
    "ITviecvn", "topdev_vn", "codetudau", "devvn", "codehub_vn",
    "python", "javascriptvn",

    # VN – Big tech / corps
    "FPT_official", "momo_vn", "viettel_group", "vnpt_official",
    "vng_corporation", "tiki_official", "vnpay_vn", "zalopay_vn",
    "grab_", "shopee_",

    # ═══════════════════════════════════════════════════════════
    # SOUTHEAST ASIA – Regional
    # ═══════════════════════════════════════════════════════════
    "techinasia", "dealstreetasia", "krasia_news", "e27_official",
    "techcrunch_sea", "sea_startup", "asean_startup",
    "singapore_tech", "sgtech_news", "startupsg",
    "indonesia_startup", "startup_indonesia", "id_tech",
    "techindonesia", "dailysocial_id",
    "startup_thailand", "tech_thailand",
    "startupph", "tech_philippines",
    "malaysia_startup", "malay_tech",

    # ═══════════════════════════════════════════════════════════
    # INDIA
    # ═══════════════════════════════════════════════════════════
    "inc42media", "yourStory_in", "Indian_startup",
    "startup_india_official", "techcrunch_india",
    "vc_india", "blume_vc", "sequoia_india",
    "bangalore_tech", "mumbai_startup",

    # ═══════════════════════════════════════════════════════════
    # USA / Global English – Tech & VC
    # ═══════════════════════════════════════════════════════════
    "ycombinator", "techcrunch", "venturebeat",
    "producthunt", "hackernews_feed", "the_information_tech",
    "bloomberg_technology", "wired_mag",
    "a16z_news", "sequoia_capital", "benchmark_vc",
    "first_round_capital", "greylock_vc",
    "sifted_vc", "axios_pro_tech",

    # USA – Sector specific
    "ai_news_daily", "openai_news", "google_ai_news",
    "fintech_times", "finovate_news", "payments_dive",
    "healthcaretechtoday", "mobihealthnews",
    "edtechhub", "edutechreview",
    "proptech_insider", "climatetech_vc",
    "cleanenergy_news", "ev_news_daily",

    # ═══════════════════════════════════════════════════════════
    # EUROPE
    # ═══════════════════════════════════════════════════════════
    "sifted_eu", "eu_startups", "uktech_news",
    "techround_uk", "startups_co_uk",
    "berlin_startup", "germany_startup",
    "french_tech", "station_f",
    "nordics_startup", "north_tech_eu",

    # ═══════════════════════════════════════════════════════════
    # MIDDLE EAST / AFRICA
    # ═══════════════════════════════════════════════════════════
    "menvets", "magnitt_news", "wamda_news",
    "difc_fintech", "dubai_startup",
    "techcabal", "disrupt_africa",
    "startupblink_africa", "partech_africa",

    # ═══════════════════════════════════════════════════════════
    # LATAM
    # ═══════════════════════════════════════════════════════════
    "latamlist", "contxto_latam", "startupblink_latam",
    "sao_paulo_tech", "mexico_startup",

    # ═══════════════════════════════════════════════════════════
    # CHINA / EAST ASIA
    # ═══════════════════════════════════════════════════════════
    "china_tech_news", "36kr_global",
    "japan_startup_news", "tokyo_startup",
    "korea_startup", "kstartup_news",

    # ═══════════════════════════════════════════════════════════
    # GLOBAL – Cross-sector / Aggregators
    # ═══════════════════════════════════════════════════════════
    "crunchbase_news", "pitchbook_news",
    "startup_digest_global", "startup_weekly",
    "the_vc_corner", "founders_news",
    "saas_weekly", "b2b_saas_channel",
    "ai_magazine", "futuretools_ai",
    "crypto_briefing", "web3_daily",
    "climatebase_news", "sustainability_tech",
    "bigtech_news", "faang_updates",
]


# ══════════════════════════════════════════════════════════════════════════════
# Checkpoint helpers
# ══════════════════════════════════════════════════════════════════════════════
def _load_checkpoint(path: Path) -> dict:
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {"done_keywords": [], "done_channels": [], "records": []}


def _save_checkpoint(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)  # atomic write


# ══════════════════════════════════════════════════════════════════════════════
# LinkedIn crawler – chạy trong ThreadPoolExecutor (sync)
# ══════════════════════════════════════════════════════════════════════════════
def crawl_linkedin(
    keywords: list[str],
    per_keyword_limit: int = 200,
    target: int = 10_000,
    resume: bool = False,
    enrich: bool = False,     # True → gọi get_company() từng cái (chậm nhưng đủ thông tin)
) -> list[dict]:
    """
    Crawl LinkedIn: nhiều keywords, checkpoint mỗi 200 công ty.

    Fast mode (mặc định):  1 API call/keyword → ~100 companies/phút
    Enrich mode (--enrich): từng company gọi get_company() → ~12 companies/phút
    """
    from linkedin_api_client import LinkedInAPIClient

    ckpt = _load_checkpoint(CHECKPOINT_LI) if resume else {"done_keywords": [], "done_channels": [], "records": []}
    done_kws: set[str] = set(ckpt.get("done_keywords", []))
    all_records: list[dict] = ckpt.get("records", [])
    seen_urls: set[str] = {r["linkedin_url"] for r in all_records if r.get("linkedin_url")}

    mode_label = "ENRICH (với website/email)" if enrich else "FAST (search-only, không website crawl)"
    logger.info(f"[LinkedIn] {mode_label} | {len(keywords)} keywords | đích={target:,}")
    if resume and all_records:
        logger.info(f"[LinkedIn] Resume từ checkpoint: {len(all_records):,} công ty đã có")

    # Kết nối LinkedIn
    try:
        client = LinkedInAPIClient()
        client.connect()
    except Exception as exc:
        logger.error(f"[LinkedIn] Không thể kết nối: {exc}")
        return all_records

    pending_keywords = [kw for kw in keywords if kw not in done_kws]

    with tqdm(total=target, initial=len(all_records), desc="LinkedIn", unit="cty", ncols=80) as pbar:
        for kw in pending_keywords:
            if len(all_records) >= target:
                logger.info(f"[LinkedIn] Đã đạt mục tiêu {target:,} – dừng.")
                break

            logger.info(f"[LinkedIn] '{kw}' ({len(all_records):,}/{target:,})")
            try:
                if enrich:
                    batch = client.fetch_companies_bulk(
                        kw, limit=per_keyword_limit, skip_email_crawl=False
                    )
                else:
                    batch = client.fetch_companies_fast_bulk(kw, limit=per_keyword_limit)

                new_count = 0
                for detail in batch:
                    url = detail.linkedin_url
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        rec = detail.to_dict()
                        rec["source"]         = "linkedin"
                        rec["crawl_keyword"]  = kw
                        all_records.append(rec)
                        new_count += 1
                        pbar.update(1)

                logger.info(f"  → +{new_count} mới | tổng={len(all_records):,}")
                done_kws.add(kw)

                # Checkpoint
                _save_checkpoint(CHECKPOINT_LI, {
                    "done_keywords": list(done_kws),
                    "done_channels": [],
                    "records": all_records,
                })

                # Lưu bản trung gian CSV mỗi 1000 công ty
                milestone = (len(all_records) // 1000) * 1000
                prev_milestone = ((len(all_records) - new_count) // 1000) * 1000
                if milestone > prev_milestone or len(all_records) >= target:
                    _save_interim(all_records, "linkedin")
                    logger.info(f"  ✅ Interim save: {len(all_records):,} công ty")

            except KeyboardInterrupt:
                logger.warning("[LinkedIn] Ctrl+C – lưu checkpoint và dừng.")
                break
            except Exception as exc:
                logger.warning(f"[LinkedIn] Lỗi với '{kw}': {exc}")
                time.sleep(3)

    logger.success(f"[LinkedIn] Hoàn thành: {len(all_records):,} công ty")
    return all_records


# ══════════════════════════════════════════════════════════════════════════════
# Telegram crawler – async
# ══════════════════════════════════════════════════════════════════════════════
async def crawl_telegram(
    channels: list[str],
    resume: bool = False,
) -> list[dict]:
    """
    Crawl Telegram: scrape metadata + messages từ danh sách kênh lớn.
    Không lọc keyword để maximize số lượng.
    """
    from telegram_scraper import TelegramWebScraper, TelegramBotAPIScraper

    ckpt = _load_checkpoint(CHECKPOINT_TG) if resume else {"done_keywords": [], "done_channels": [], "records": []}
    done_channels: set[str] = set(ckpt.get("done_channels", []))
    all_records: list[dict] = ckpt.get("records", [])
    seen_names: set[str] = {r.get("name", "").lower() for r in all_records}

    logger.info(f"[Telegram] Bắt đầu | {len(channels)} kênh")
    if resume and all_records:
        logger.info(f"[Telegram] Resume từ checkpoint: {len(all_records):,} entries đã có")

    pending = [ch for ch in channels if ch not in done_channels]

    web_scraper = TelegramWebScraper()
    bot_api     = TelegramBotAPIScraper()

    try:
        with tqdm(total=len(channels), initial=len(done_channels), desc="Telegram", unit="kênh") as pbar:
            for username in pending:
                try:
                    # Web scrape (t.me/s/ + t.me/ fallback)
                    companies = await web_scraper.scrape_channel(username, keyword="")
                    new_count = 0
                    for c in companies:
                        name_key = c.name.lower().strip()
                        if name_key and name_key not in seen_names:
                            seen_names.add(name_key)
                            rec = c.to_dict()
                            rec["crawl_channel"] = username
                            all_records.append(rec)
                            new_count += 1

                    done_channels.add(username)
                    pbar.update(1)
                    pbar.set_postfix({"collected": len(all_records)})

                    # Checkpoint mỗi 10 kênh
                    if len(done_channels) % 10 == 0:
                        _save_checkpoint(CHECKPOINT_TG, {
                            "done_keywords": [],
                            "done_channels": list(done_channels),
                            "records": all_records,
                        })

                    await asyncio.sleep(0.4)

                except KeyboardInterrupt:
                    logger.warning("[Telegram] Ctrl+C – lưu checkpoint.")
                    break
                except Exception as exc:
                    logger.debug(f"[Telegram] @{username} lỗi: {exc}")
                    done_channels.add(username)
                    pbar.update(1)

    finally:
        await web_scraper.close()
        await bot_api.close()
        _save_checkpoint(CHECKPOINT_TG, {
            "done_keywords": [],
            "done_channels": list(done_channels),
            "records": all_records,
        })

    logger.success(f"[Telegram] Hoàn thành: {len(all_records):,} entries")
    return all_records


# ══════════════════════════════════════════════════════════════════════════════
# Interim save
# ══════════════════════════════════════════════════════════════════════════════
def _save_interim(records: list[dict], source: str):
    path = OUTPUT_DIR / f"interim_{source}.csv"
    try:
        if records:
            import pandas as pd
            pd.DataFrame(records).to_csv(path, index=False, encoding="utf-8-sig")
            logger.debug(f"Interim save: {len(records):,} → {path}")
    except Exception as exc:
        logger.debug(f"Interim save lỗi: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# Merge & deduplicate
# ══════════════════════════════════════════════════════════════════════════════
def merge_and_export(li_records: list[dict], tg_records: list[dict]) -> list[dict]:
    """Gộp, dedup, xuất 3 định dạng."""
    merged: dict[str, dict] = {}

    def _score(r: dict) -> int:
        return sum(1 for v in r.values() if v and str(v).strip() not in ("", "nan", "None"))

    for rec in li_records + tg_records:
        key = (rec.get("linkedin_url") or rec.get("channel") or rec.get("name") or "").strip().lower()
        if not key:
            continue
        if key not in merged or _score(rec) > _score(merged[key]):
            merged[key] = rec

    final = list(merged.values())
    # Sắp xếp: LinkedIn trước
    final.sort(key=lambda r: (r.get("source", "z") != "linkedin", r.get("name", "")))

    logger.success(f"Merge: LinkedIn={len(li_records):,} + Telegram={len(tg_records):,} → Unique={len(final):,}")

    if not final:
        logger.warning("Không có dữ liệu để xuất!")
        return final

    # Export
    exporter.save_csv(final, str(FINAL_CSV))
    exporter.save_json(final, str(FINAL_JSON))
    try:
        exporter.save_excel(final, str(FINAL_EXCEL))
    except Exception as exc:
        logger.warning(f"Excel export lỗi (bỏ qua): {exc}")

    # Stats report
    _print_stats(final)
    return final


def _print_stats(records: list[dict]):
    import pandas as pd
    df = pd.DataFrame(records)
    total = len(df)

    li_count = len(df[df.get("source", pd.Series()) == "linkedin"]) if "source" in df else 0
    tg_count = total - li_count

    has_website = df["website"].notna().sum() if "website" in df else 0
    has_email   = df["email"].notna().sum()   if "email" in df else 0

    # Top industries
    if "industry" in df:
        top_industries = (
            df["industry"].dropna()
            .value_counts().head(10)
            .to_dict()
        )
    else:
        top_industries = {}

    # Top locations
    if "headquarters" in df:
        top_hq = (
            df["headquarters"].dropna()
            .value_counts().head(5)
            .to_dict()
        )
    else:
        top_hq = {}

    print("\n" + "═" * 60)
    print(f"  📊 CRAWL REPORT – {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("═" * 60)
    print(f"  Tổng công ty unique   : {total:>8,}")
    print(f"  ├─ Từ LinkedIn        : {li_count:>8,}")
    print(f"  └─ Từ Telegram        : {tg_count:>8,}")
    print(f"  Có website            : {has_website:>8,} ({has_website/total*100:.1f}%)")
    print(f"  Có email              : {has_email:>8,} ({has_email/total*100:.1f}%)")
    if top_industries:
        print("\n  Top industries:")
        for ind, cnt in list(top_industries.items())[:5]:
            print(f"    {ind:<35} {cnt:>5,}")
    if top_hq:
        print("\n  Top headquarters:")
        for hq, cnt in list(top_hq.items())[:5]:
            print(f"    {hq:<35} {cnt:>5,}")
    print("\n  Output files:")
    print(f"    CSV   : {FINAL_CSV}")
    print(f"    JSON  : {FINAL_JSON}")
    print(f"    Excel : {FINAL_EXCEL}")
    print("═" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Large-scale crawl: ~10.000 công ty từ LinkedIn + Telegram"
    )
    parser.add_argument("--source", default="both",
                        choices=["both", "linkedin", "telegram"],
                        help="Nguồn dữ liệu (mặc định: both)")
    parser.add_argument("--target", type=int, default=10_000,
                        help="Mục tiêu số công ty LinkedIn (mặc định: 10000)")
    parser.add_argument("--per-keyword", type=int, default=200,
                        help="Số công ty tối đa mỗi keyword LinkedIn (mặc định: 200)")
    parser.add_argument("--resume", action="store_true",
                        help="Tiếp tục từ checkpoint (không crawl lại đã xong)")
    parser.add_argument("--enrich", action="store_true",
                        help="Gọi get_company() cho từng công ty (đầy đủ nhưng ~100x chậm hơn)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Bỏ qua Telegram (chỉ LinkedIn)")
    args = parser.parse_args()

    start_time = time.time()
    li_records: list[dict] = []
    tg_records: list[dict] = []

    source = "linkedin" if args.no_telegram else args.source

    # ── LinkedIn ──────────────────────────────────────────────────────────
    if source in ("both", "linkedin"):
        logger.info(f"━━ PHASE 1: LinkedIn ({len(ALL_LINKEDIN_KEYWORDS)} keywords, đích={args.target:,}) ━━")
        li_records = crawl_linkedin(
            keywords=ALL_LINKEDIN_KEYWORDS,
            per_keyword_limit=args.per_keyword,
            target=args.target,
            resume=args.resume,
            enrich=args.enrich,
        )

    # ── Telegram ──────────────────────────────────────────────────────────
    if source in ("both", "telegram"):
        logger.info(f"━━ PHASE 2: Telegram ({len(TELEGRAM_CHANNELS_LARGE)} kênh) ━━")
        tg_records = asyncio.run(
            crawl_telegram(
                channels=TELEGRAM_CHANNELS_LARGE,
                resume=args.resume,
            )
        )

    # ── Merge & Export ────────────────────────────────────────────────────
    if li_records or tg_records:
        logger.info("━━ PHASE 3: Merge & Export ━━")
        merge_and_export(li_records, tg_records)
    else:
        logger.warning("Không có dữ liệu từ cả hai nguồn!")

    elapsed = time.time() - start_time
    h, m = divmod(int(elapsed), 3600)
    m, s = divmod(m, 60)
    logger.success(f"Hoàn thành toàn bộ trong {h}h {m}m {s}s")


if __name__ == "__main__":
    main()
