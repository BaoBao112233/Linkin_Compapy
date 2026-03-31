#!/usr/bin/env python3
# ==============================
# Telegram Bot Interface
# File: telegram_bot.py
# Bot nhận lệnh và trả kết quả crawl
# ==============================
"""
Bot Telegram để điều khiển pipeline crawl dữ liệu công ty.

Cách dùng:
  python telegram_bot.py

Các lệnh trong Telegram:
  /start          – Hướng dẫn sử dụng
  /search <kw>    – Tìm công ty (cả LinkedIn + Telegram), mặc định limit=20
  /linkedin <kw>  – Chỉ tìm trên LinkedIn
  /telegram <kw>  – Chỉ tìm trên Telegram
  /crawl <kw> [--limit N] [--format csv|excel|json]
                  – Pipeline đầy đủ, gửi file kết quả
  /channels       – Danh sách kênh Telegram đang theo dõi
  /status         – Trạng thái bot
  /help           – Trợ giúp

Chú ý:
  - Bot xử lý mỗi lệnh trong background thread để không block.
  - Kết quả được gửi lại dưới dạng file CSV/Excel.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import csv
from pathlib import Path
from datetime import datetime

from loguru import logger

import config
from parallel_pipeline import run_parallel

# ── Logging ──────────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add("logs/telegram_bot.log", level="DEBUG", rotation="5 MB")

BOT_TOKEN = config.TELEGRAM_BOT_TOKEN


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════
def _records_to_csv_file(records: list[dict], keyword: str = "") -> str:
    """Ghi records vào file CSV tạm thời, trả về đường dẫn."""
    safe_kw = keyword.replace(" ", "_")[:20] if keyword else "results"
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(config.OUTPUT_DIR) / f"bot_{safe_kw}_{ts}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        out.write_text("No results found.\n")
        return str(out)

    fieldnames = list(records[0].keys())
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return str(out)


def _format_preview(records: list[dict], max_rows: int = 5) -> str:
    """Tạo preview dạng text cho Telegram."""
    if not records:
        return "Không tìm thấy kết quả."

    lines = [f"✅ Tìm thấy *{len(records)}* công ty:\n"]
    for i, r in enumerate(records[:max_rows], 1):
        name    = r.get("name") or r.get("channel_title") or "N/A"
        website = r.get("website") or ""
        source  = r.get("source") or "?"
        icon    = "💼" if "linkedin" in source else "📢"
        lines.append(f"{icon} *{i}. {name}*")
        if website:
            lines.append(f"   🌐 {website}")
    if len(records) > max_rows:
        lines.append(f"\n_...và {len(records) - max_rows} công ty khác. Xem file đính kèm._")
    return "\n".join(lines)


def _parse_crawl_args(text: str) -> tuple[str, int, str]:
    """
    Parse lệnh /crawl <keyword> [--limit N] [--format csv/excel/json]
    Trả về (keyword, limit, format).
    """
    import re
    limit  = 20
    fmt    = "csv"
    # Tách --limit
    m = re.search(r"--limit\s+(\d+)", text)
    if m:
        limit = int(m.group(1))
        text  = text[:m.start()] + text[m.end():]
    # Tách --format
    m = re.search(r"--format\s+(\w+)", text)
    if m:
        fmt  = m.group(1)
        text = text[:m.start()] + text[m.end():]
    keyword = text.strip()
    return keyword, limit, fmt


# ══════════════════════════════════════════════════════════════════════════════
# Bot handlers sử dụng python-telegram-bot v20+
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update, context):
    text = (
        "👋 *Company Crawler Bot*\n\n"
        "Tôi có thể tìm kiếm thông tin công ty từ *LinkedIn* và *Telegram* song song.\n\n"
        "*Các lệnh:*\n"
        "/search `<keyword>` – Tìm cả 2 nguồn (limit mặc định 20)\n"
        "/linkedin `<keyword>` – Chỉ LinkedIn\n"
        "/telegram `<keyword>` – Chỉ Telegram\n"
        "/crawl `<keyword>` `[--limit N]` `[--format csv|excel|json]` – Pipeline đầy đủ\n"
        "/channels – Danh sách kênh Telegram\n"
        "/status – Trạng thái cấu hình\n"
        "/help – Trợ giúp chi tiết\n\n"
        "📌 Ví dụ: `/search fintech `"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update, context):
    text = (
        "📖 *Hướng dẫn chi tiết*\n\n"
        "• Bot tìm kiếm thông tin công ty (tên, website, email, điện thoại…)\n"
        "• Nguồn dữ liệu: LinkedIn companies + Telegram channels/groups\n"
        "• Kết quả trả về: text preview + file CSV\n\n"
        "*Cấu hình nâng cao (Telethon):*\n"
        "Để bot tìm kiếm được toàn bộ channel Telegram, thêm vào `.env`:\n"
        "`TELEGRAM_API_ID=<id>`\n"
        "`TELEGRAM_API_HASH=<hash>`\n"
        "_(Lấy tại https://my.telegram.org/apps)_\n\n"
        "*Ví dụ lệnh:*\n"
        "`/search saas b2b`\n"
        "`/crawl healthcare  --limit 50 --format excel`\n"
        "`/telegram startup hcm`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update, context):
    linkedin_ok = bool(config.LINKEDIN_LI_AT or config.LINKEDIN_EMAIL)
    telethon_ok = bool(config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH)

    text = (
        "⚙️ *Trạng thái cấu hình*\n\n"
        f"• LinkedIn: {'✅ Đã cấu hình' if linkedin_ok else '⚠️ Chưa cấu hình (tùy chọn)'}\n"
        f"• Telegram Bot API: ✅ Token hợp lệ\n"
        f"• Telegram Telethon: {'✅ Đã cấu hình (search đầy đủ)' if telethon_ok else '⚠️ Chưa cấu hình (Bot API mode)'}\n"
        f"• Kênh mặc định: {len(config.TELEGRAM_BUSINESS_CHANNELS)} kênh\n"
        f"• Output dir: `{config.OUTPUT_DIR}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_channels(update, context):
    lines = ["📢 *Kênh Telegram đang theo dõi:*\n"]
    for ch in config.TELEGRAM_BUSINESS_CHANNELS:
        lines.append(f"• @{ch}")
    lines.append(
        "\n_Chỉnh sửa trong `config.py` → `TELEGRAM_BUSINESS_CHANNELS` để thêm/bớt._"
    )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _do_search(update, context, keyword: str, limit: int, source: str):
    """Xử lý tìm kiếm, gửi preview + file."""
    if not keyword:
        await update.message.reply_text("⚠️ Vui lòng nhập từ khóa. Ví dụ: `/search fintech`", parse_mode="Markdown")
        return

    msg = await update.message.reply_text(
        f"🔍 Đang tìm kiếm *{keyword}* trên *{source}*... (giới hạn {limit})",
        parse_mode="Markdown",
    )
    try:
        records = await run_parallel(
            keyword=keyword,
            limit=limit,
            source=source,
            output_format="csv",
        )
        preview  = _format_preview(records, max_rows=5)
        csv_path = _records_to_csv_file(records, keyword)

        await msg.edit_text(preview, parse_mode="Markdown")
        if records:
            with open(csv_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=Path(csv_path).name,
                    caption=f"📎 Kết quả tìm kiếm: *{keyword}* ({len(records)} công ty)",
                    parse_mode="Markdown",
                )
    except Exception as exc:
        logger.error(f"_do_search lỗi: {exc}")
        await msg.edit_text(f"❌ Lỗi khi tìm kiếm: `{exc}`", parse_mode="Markdown")


async def cmd_search(update, context):
    keyword = " ".join(context.args) if context.args else ""
    await _do_search(update, context, keyword, limit=20, source="both")


async def cmd_linkedin(update, context):
    keyword = " ".join(context.args) if context.args else ""
    await _do_search(update, context, keyword, limit=20, source="linkedin")


async def cmd_telegram_search(update, context):
    keyword = " ".join(context.args) if context.args else ""
    await _do_search(update, context, keyword, limit=30, source="telegram")


async def cmd_crawl(update, context):
    raw = " ".join(context.args) if context.args else ""
    keyword, limit, fmt = _parse_crawl_args(raw)

    if not keyword:
        await update.message.reply_text(
            "⚠️ Cú pháp: `/crawl <keyword> [--limit N] [--format csv|excel|json]`",
            parse_mode="Markdown",
        )
        return

    msg = await update.message.reply_text(
        f"🚀 Đang crawl *{keyword}* (limit={limit}, format={fmt})...",
        parse_mode="Markdown",
    )
    try:
        records = await run_parallel(
            keyword=keyword,
            limit=limit,
            source="both",
            output_format=fmt,
        )
        preview  = _format_preview(records, max_rows=8)
        csv_path = _records_to_csv_file(records, keyword)

        await msg.edit_text(preview, parse_mode="Markdown")
        if records:
            with open(csv_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=Path(csv_path).name,
                    caption=f"📎 *{keyword}* – {len(records)} công ty | LinkedIn + Telegram",
                    parse_mode="Markdown",
                )
    except Exception as exc:
        logger.error(f"cmd_crawl lỗi: {exc}")
        await msg.edit_text(f"❌ Lỗi: `{exc}`", parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════
def main():
    try:
        from telegram.ext import ApplicationBuilder, CommandHandler  # type: ignore
    except ImportError:
        logger.error("Chưa cài python-telegram-bot. Chạy: pip install 'python-telegram-bot>=20.0'")
        sys.exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("channels", cmd_channels))
    app.add_handler(CommandHandler("search",   cmd_search))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("telegram", cmd_telegram_search))
    app.add_handler(CommandHandler("crawl",    cmd_crawl))

    logger.success(f"Bot đang chạy... Token: {BOT_TOKEN[:10]}***")
    logger.info("Gửi /start trong Telegram để bắt đầu.")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
