# ==============================
# Telegram Company Scraper
# File: telegram_scraper.py
# Tìm kiếm thông tin công ty từ Telegram
# ==============================
"""
Hai chế độ hoạt động:

  1. Bot-only mode (chỉ cần BOT_TOKEN):
     - Dùng Bot API để lấy thông tin kênh, forward tin nhắn
     - Hạn chế: không thể search tất cả channel công khai

  2. Telethon mode (cần API_ID + API_HASH + BOT_TOKEN hoặc user session):
     - Tìm kiếm toàn bộ channel/group công khai trên Telegram
     - Phân tích tin nhắn để trích xuất thông tin công ty
     - Mạnh hơn và đầy đủ hơn

Thiết lập Telethon:
  1. Truy cập https://my.telegram.org/apps
  2. Đăng nhập, tạo ứng dụng → lấy api_id và api_hash
  3. Thêm vào .env: TELEGRAM_API_ID=... và TELEGRAM_API_HASH=...
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, asdict, field
from typing import AsyncGenerator

import httpx
from bs4 import BeautifulSoup
from loguru import logger

import config


# ── Regex helpers ──────────────────────────────────────────────────────────
_EMAIL_RE   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE   = re.compile(r"(?:\+84|0)[0-9]{8,10}")
_URL_RE     = re.compile(r"https?://[^\s\)\]>\"']+")
_MENTION_RE = re.compile(r"@([A-Za-z0-9_]{5,})")


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text or "")
    return m.group(0) if m else ""


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text or "")
    return m.group(0) if m else ""


def _extract_website(text: str) -> str:
    for url in _URL_RE.findall(text or ""):
        # Loại trừ link Telegram, ảnh, v.v.
        if not any(x in url for x in ["t.me", "telegram", ".jpg", ".png", ".gif"]):
            return url.rstrip(".,;)")
    return ""


# ── Data model ──────────────────────────────────────────────────────────────
@dataclass
class TelegramCompany:
    """Thông tin công ty trích xuất từ Telegram."""
    name: str         = ""
    description: str  = ""
    website: str      = ""
    email: str        = ""
    phone: str        = ""
    channel: str      = ""          # @username kênh nguồn
    channel_title: str = ""
    channel_members: int = 0
    message_date: str = ""
    source: str       = "telegram"
    linkedin_url: str = ""          # để ghép với LinkedIn data
    industry: str     = ""
    location: str     = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def is_valid(self) -> bool:
        """Kiểm tra có đủ thông tin để lưu không."""
        return bool(self.name.strip())


# ══════════════════════════════════════════════════════════════════════════════
# Web scraper – crawl t.me/s/<channel> (không cần đăng nhập)
# ══════════════════════════════════════════════════════════════════════════════
class TelegramWebScraper:
    """
    Scrape kênh Telegram công khai qua trang web t.me/s/<username>.
    Không cần API key, không cần đăng nhập.
    Hoạt động với mọi kênh/supergroup đã bật Preview.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }

    def __init__(self):
        self._client = httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=20,
            follow_redirects=True,
        )

    async def close(self):
        await self._client.aclose()

    # ── Lấy HTML của trang kênh ───────────────────────────────────────────
    async def _fetch_channel_page(self, username: str) -> tuple[str, bool]:
        """
        Trả về (html, has_preview).
        Ưu tiên t.me/s/ (có bài đăng), fallback sang t.me/ (chỉ metadata).
        """
        uname = username.lstrip('@')
        # Thử preview URL trước
        url_s = f"https://t.me/s/{uname}"
        try:
            resp = await self._client.get(url_s, follow_redirects=False)
            if resp.status_code == 200 and 'tgme_widget_message' in resp.text:
                return resp.text, True
        except Exception:
            pass

        # Fallback: trang thường (chứa OG meta + channel info)
        url = f"https://t.me/{uname}"
        try:
            resp = await self._client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text, False
        except Exception as exc:
            logger.debug(f"fetch {url} lỗi: {exc}")
        return "", False

    # ── Parse thông tin kênh từ HTML ─────────────────────────────────────
    @staticmethod
    def _parse_channel_info(html: str, username: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        title = ""
        description = ""
        members = 0

        # Tiêu đề kênh (preview mode)
        h1 = soup.select_one(".tgme_channel_info_header_title")
        if h1:
            title = h1.get_text(strip=True)

        # Preview mode: page title
        if not title:
            pt = soup.select_one(".tgme_page_title")
            if pt:
                title = pt.get_text(strip=True)

        # OG metadata (hoạt động trên mọi trang t.me/)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                raw = og_title.get("content", "")
                # Loại bỏ prefix "Telegram: " nếu có
                title = raw.replace("Telegram: ", "").replace("Contact @", "").strip()

        # Description (preview mode)
        desc_el = soup.select_one(".tgme_channel_info_description")
        if desc_el:
            description = desc_el.get_text(strip=True)

        # Page description (t.me/ fallback)
        if not description:
            pg_desc = soup.select_one(".tgme_page_description")
            if pg_desc:
                description = pg_desc.get_text(strip=True)

        # OG description (cuối cùng)
        if not description:
            og_desc = soup.select_one('meta[property="og:description"]')
            if og_desc:
                description = og_desc.get("content", "").strip()

        # Số thành viên
        counter_els = soup.select(".tgme_channel_info_counter")
        for el in counter_els:
            val_el  = el.select_one(".counter_value")
            type_el = el.select_one(".counter_type")
            if val_el and type_el:
                c_type = type_el.get_text(strip=True).lower()
                c_val  = val_el.get_text(strip=True).replace(" ", "").replace(",", "")
                if "member" in c_type or "subscriber" in c_type:
                    try:
                        members = int(c_val.replace("K", "000").replace("M", "000000"))
                    except ValueError:
                        pass

        # Extra: member count từ tgme_page_extra
        if members == 0:
            extra = soup.select_one(".tgme_page_extra")
            if extra:
                text = extra.get_text(strip=True)
                m = re.search(r"([\d\s,]+)\s*(members?|subscribers?)", text, re.I)
                if m:
                    try:
                        members = int(m.group(1).replace(" ", "").replace(",", ""))
                    except ValueError:
                        pass

        return {"title": title, "description": description, "members": members}

    # ── Parse tin nhắn trong kênh ────────────────────────────────────────
    @staticmethod
    def _parse_messages(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        messages = []
        for msg_el in soup.select(".tgme_widget_message"):
            text_el = msg_el.select_one(".tgme_widget_message_text")
            if not text_el:
                continue
            text = text_el.get_text(separator="\n", strip=True)
            date_el = msg_el.select_one("time")
            date_str = date_el.get("datetime", "")[:10] if date_el else ""
            if text:
                messages.append({"text": text, "date": date_str})
        return messages

    # ── Scrape 1 kênh, trả về danh sách TelegramCompany ──────────────────
    async def scrape_channel(
        self,
        username: str,
        keyword: str = "",
    ) -> list[TelegramCompany]:
        html, has_preview = await self._fetch_channel_page(username)
        if not html:
            return []

        info     = self._parse_channel_info(html, username)
        messages = self._parse_messages(html) if has_preview else []

        title    = info["title"] or username
        ch_clean = f"@{username.lstrip('@')}"

        companies:  list[TelegramCompany] = []
        seen_names: set[str] = set()
        kw_words = [w.lower() for w in keyword.split() if len(w) > 2] if keyword else []

        # 1. Kênh bản thân: dù không có website/email vẫn thu thập nếu là kênh doanh nghiệp
        desc = info["description"]
        web  = _extract_website(desc)
        email = _extract_email(desc)
        phone = _extract_phone(desc)

        combined = f"{title} {desc} {username}".lower()
        keyword_match = not kw_words or any(w in combined for w in kw_words)

        if keyword_match and title:
            c = TelegramCompany(
                name=title,
                description=desc[:400] if desc else "",
                website=web,
                email=email,
                phone=phone,
                channel=ch_clean,
                channel_title=title,
                channel_members=info["members"],
                source="telegram_web",
            )
            if c.is_valid() and c.name not in seen_names:
                seen_names.add(c.name)
                companies.append(c)

        # 2. Trích xuất công ty từ từng message (nếu có preview)
        for msg in messages:
            text = msg["text"]
            if kw_words and not any(w in text.lower() for w in kw_words):
                continue
            company = TelegramTelethonScraper._parse_company_from_message(text, title)
            if company and company.name not in seen_names:
                company.channel       = ch_clean
                company.channel_title = title
                company.message_date  = msg["date"]
                company.source        = "telegram_web"
                seen_names.add(company.name)
                companies.append(company)

        if companies:
            logger.info(
                f"  [TG Web] @{username} ({title}) | members={info['members']:,} "
                f"| {'preview' if has_preview else 'metadata'} | {len(companies)} entry"
            )
        else:
            logger.debug(f"  [TG Web] @{username} → 0 kết quả (keyword filter)")

        return companies

    # ── Scrape nhiều kênh ─────────────────────────────────────────────────
    async def scrape_channels(
        self,
        channels: list[str],
        keyword: str = "",
    ) -> list[TelegramCompany]:
        all_companies: list[TelegramCompany] = []
        for username in channels:
            try:
                result = await self.scrape_channel(username, keyword)
                all_companies.extend(result)
            except Exception as exc:
                logger.debug(f"scrape_channel @{username} lỗi: {exc}")
            await asyncio.sleep(0.5)  # polite delay
        return all_companies


# ══════════════════════════════════════════════════════════════════════════════
# Bot-only scraper (chỉ dùng Bot API – không cần api_id/api_hash)
# ══════════════════════════════════════════════════════════════════════════════
class TelegramBotAPIScraper:
    """
    Scraper dùng Telegram Bot API (chỉ cần BOT_TOKEN).
    Có thể:
      - Lấy thông tin channel/supergroup nếu biết @username
      - Đọc tin nhắn từ channel bot đã tham gia hoặc được thêm vào
    Không thể search channel công khai tùy ý (cần Telethon).
    """

    BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, token: str = config.TELEGRAM_BOT_TOKEN):
        self.token = token
        self._base = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=30)

    async def close(self):
        await self._client.aclose()

    # ── Low-level request ────────────────────────────────────────────────
    async def _call(self, method: str, **params) -> dict:
        url = f"{self._base}/{method}"
        resp = await self._client.post(url, json=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data.get('description')}")
        return data["result"]

    # ── Lấy thông tin 1 channel ──────────────────────────────────────────
    async def get_chat_info(self, username: str) -> dict:
        """Lấy thông tin chat (channel/group). username có thể có hoặc không có @."""
        handle = username if username.startswith("@") else f"@{username}"
        try:
            return await self._call("getChat", chat_id=handle)
        except Exception as exc:
            logger.debug(f"getChat({handle}) lỗi: {exc}")
            return {}

    async def get_chat_member_count(self, username: str) -> int:
        handle = username if username.startswith("@") else f"@{username}"
        try:
            result = await self._call("getChatMemberCount", chat_id=handle)
            return int(result)
        except Exception:
            return 0

    # ── Đọc tin nhắn từ channel (forward updates) ────────────────────────
    async def get_updates(self, offset: int = 0, limit: int = 100) -> list[dict]:
        try:
            return await self._call("getUpdates", offset=offset, limit=limit, timeout=5)
        except Exception:
            return []

    # ── Scrape danh sách kênh đã biết ───────────────────────────────────
    async def scrape_channels(
        self,
        channels: list[str],
        keyword: str = "",
    ) -> list[TelegramCompany]:
        """
        Lấy thông tin từ danh sách kênh Telegram.
        Nếu keyword được cung cấp, lọc theo từng từ riêng (AND logic).
        """
        results: list[TelegramCompany] = []
        # Tách keyword thành các từ, loại bỏ stop words ngắn
        kw_words = [w.lower() for w in keyword.split() if len(w) > 2] if keyword else []

        for username in channels:
            info = await self.get_chat_info(username)
            if not info:
                continue

            title       = info.get("title", "")
            description = info.get("description", "") or info.get("bio", "")
            invite_link = info.get("invite_link", "")

            # Lọc theo keyword: mỗi từ phải xuất hiện trong title hoặc description
            if kw_words:
                combined_text = f"{title} {description} {username}".lower()
                # Chỉ cần ít nhất 1 từ khớp (OR logic để rộng hơn)
                if not any(w in combined_text for w in kw_words):
                    continue

            member_count = await self.get_chat_member_count(username)

            company = TelegramCompany(
                name=title,
                description=description[:500] if description else "",
                website=_extract_website(description),
                email=_extract_email(description),
                phone=_extract_phone(description),
                channel=f"@{username.lstrip('@')}",
                channel_title=title,
                channel_members=member_count,
                source="telegram_bot_api",
            )
            if company.is_valid():
                results.append(company)
                logger.info(f"  [TG] {title} | @{username} | {member_count:,} members")

            await asyncio.sleep(0.3)  # rate limit

        return results


# ══════════════════════════════════════════════════════════════════════════════
# Telethon scraper (dùng MTProto – mạnh hơn, cần api_id + api_hash)
# ══════════════════════════════════════════════════════════════════════════════
class TelegramTelethonScraper:
    """
    Scraper dùng Telethon (MTProto API).
    Có thể:
      - Tìm kiếm toàn bộ channel/group công khai
      - Đọc tin nhắn, lọc theo keyword
      - Trích xuất thông tin công ty từ posts
    Cần:
      TELEGRAM_API_ID và TELEGRAM_API_HASH trong .env
      (lấy tại https://my.telegram.org/apps)
    """

    def __init__(
        self,
        api_id: int        = config.TELEGRAM_API_ID,
        api_hash: str      = config.TELEGRAM_API_HASH,
        bot_token: str     = config.TELEGRAM_BOT_TOKEN,
        session_file: str  = config.TELEGRAM_SESSION_FILE,
    ):
        self.api_id      = api_id
        self.api_hash    = api_hash
        self.bot_token   = bot_token
        self.session_file = session_file
        self._client     = None

    async def connect(self):
        """Kết nối TTelegramClient bằng bot token."""
        try:
            from telethon import TelegramClient  # type: ignore
            from telethon.errors import AuthKeyError  # type: ignore
        except ImportError:
            logger.error("Chưa cài telethon. Chạy: pip install telethon")
            raise

        if self.api_id == 0 or not self.api_hash:
            raise ValueError(
                "Chưa cấu hình TELEGRAM_API_ID / TELEGRAM_API_HASH.\n"
                "Truy cập https://my.telegram.org/apps để lấy.\n"
                "Thêm vào .env: TELEGRAM_API_ID=... TELEGRAM_API_HASH=..."
            )

        self._client = TelegramClient(
            self.session_file,
            self.api_id,
            self.api_hash,
        )
        await self._client.start(bot_token=self.bot_token)
        me = await self._client.get_me()
        logger.success(f"Telethon kết nối thành công: @{me.username}")

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    # ── Tìm kiếm kênh theo keyword ────────────────────────────────────────
    async def search_channels(self, keyword: str, limit: int = 20) -> list[dict]:
        """Tìm kiếm kênh/group công khai theo keyword."""
        from telethon.tl.functions.contacts import SearchRequest  # type: ignore

        try:
            result = await self._client(SearchRequest(q=keyword, limit=limit))
            channels = []
            for chat in result.chats:
                channels.append({
                    "id":         chat.id,
                    "username":   getattr(chat, "username", "") or "",
                    "title":      getattr(chat, "title", "") or "",
                    "members":    getattr(chat, "participants_count", 0) or 0,
                })
            logger.info(f"  [Telethon] Tìm thấy {len(channels)} kênh cho '{keyword}'")
            return channels
        except Exception as exc:
            logger.warning(f"search_channels lỗi: {exc}")
            return []

    # ── Đọc tin nhắn từ 1 kênh ────────────────────────────────────────────
    async def iter_channel_messages(
        self,
        channel_id,
        keyword: str = "",
        limit: int = config.TELEGRAM_MAX_MESSAGES,
    ) -> AsyncGenerator[dict, None]:
        """Yield từng message từ channel, lọc theo keyword nếu có."""
        try:
            async for msg in self._client.iter_messages(channel_id, limit=limit):
                text = msg.text or msg.message or ""
                if not text:
                    continue
                if keyword and keyword.lower() not in text.lower():
                    continue
                yield {
                    "text":   text,
                    "date":   str(msg.date.date()) if msg.date else "",
                    "msg_id": msg.id,
                }
        except Exception as exc:
            logger.debug(f"iter_channel_messages lỗi: {exc}")

    # ── Trích xuất thông tin công ty từ text ─────────────────────────────
    @staticmethod
    def _parse_company_from_message(text: str, channel_title: str = "") -> TelegramCompany | None:
        """
        Phân tích text của 1 message để trích xuất thông tin công ty.
        Trả về None nếu không đủ thông tin.
        """
        # Tiêu chí: phải có website hoặc email hoặc phone
        website = _extract_website(text)
        email   = _extract_email(text)
        phone   = _extract_phone(text)

        if not (website or email or phone):
            return None

        # Lấy tên công ty: thường là dòng đầu tiên hoặc in đậm (markdown)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        name = ""
        for line in lines[:5]:
            # Loại bỏ dòng chỉ là URL hoặc hashtag
            if not line.startswith("http") and not line.startswith("#"):
                name = line[:100]
                break

        if not name:
            name = channel_title or "Unknown"

        return TelegramCompany(
            name=name,
            description=text[:400].replace("\n", " "),
            website=website,
            email=email,
            phone=phone,
            channel_title=channel_title,
            source="telegram_telethon",
        )

    # ── Pipeline chính: search + scrape ──────────────────────────────────
    async def scrape_by_keyword(
        self,
        keyword: str,
        channel_limit: int = 10,
        msg_limit: int = config.TELEGRAM_MAX_MESSAGES,
    ) -> list[TelegramCompany]:
        """
        Tìm kiếm kênh theo keyword, sau đó đọc tin nhắn để trích xuất
        thông tin công ty.
        """
        channels = await self.search_channels(keyword, limit=channel_limit)
        results:  list[TelegramCompany] = []
        seen_names: set[str] = set()

        for ch in channels:
            username = ch.get("username", "")
            title    = ch.get("title", "")
            ch_id    = ch.get("id")

            logger.info(f"  [Telethon] Quét kênh: {title} (@{username})")
            async for msg in self.iter_channel_messages(ch_id, keyword=keyword, limit=msg_limit):
                company = self._parse_company_from_message(msg["text"], title)
                if company and company.name not in seen_names:
                    company.channel    = f"@{username}" if username else ""
                    company.message_date = msg["date"]
                    seen_names.add(company.name)
                    results.append(company)

        logger.success(f"  [Telethon] Tổng cộng: {len(results)} công ty từ Telegram")
        return results

    # ── Scrape từ danh sách kênh cụ thể ─────────────────────────────────
    async def scrape_channels_list(
        self,
        channels: list[str],
        keyword: str = "",
        msg_limit: int = config.TELEGRAM_MAX_MESSAGES,
    ) -> list[TelegramCompany]:
        """Scrape tin nhắn từ danh sách kênh đã biết."""
        results:    list[TelegramCompany] = []
        seen_names: set[str] = set()

        for username in channels:
            try:
                entity = await self._client.get_entity(
                    username if username.startswith("@") else f"@{username}"
                )
                title  = getattr(entity, "title", username)
                ch_id  = entity.id
                logger.info(f"  [Telethon] Quét: {title} (@{username})")

                async for msg in self.iter_channel_messages(ch_id, keyword=keyword, limit=msg_limit):
                    company = self._parse_company_from_message(msg["text"], title)
                    if company and company.name not in seen_names:
                        company.channel      = f"@{username.lstrip('@')}"
                        company.message_date = msg["date"]
                        seen_names.add(company.name)
                        results.append(company)
            except Exception as exc:
                logger.warning(f"  Bỏ qua @{username}: {exc}")

        return results


# ══════════════════════════════════════════════════════════════════════════════
# Unified scraper – tự động chọn chế độ phù hợp
# ══════════════════════════════════════════════════════════════════════════════
class TelegramScraper:
    """
    Unified scraper: tự động dùng Telethon nếu có api_id/api_hash,
    ngược lại fallback sang Bot API.
    """

    def __init__(self):
        self._telethon_available = (
            config.TELEGRAM_API_ID != 0 and bool(config.TELEGRAM_API_HASH)
        )
        self._telethon:    TelegramTelethonScraper | None = None
        self._bot_api:     TelegramBotAPIScraper    | None = None
        self._web_scraper: TelegramWebScraper       | None = None

    async def connect(self):
        if self._telethon_available:
            logger.info("Telegram: sử dụng Telethon (MTProto mode)")
            self._telethon = TelegramTelethonScraper()
            await self._telethon.connect()
        else:
            logger.info("Telegram: sử dụng Web Scraper mode (t.me/s/) + Bot API")
            self._bot_api = TelegramBotAPIScraper()
            self._web_scraper = TelegramWebScraper()

    async def disconnect(self):
        if self._telethon:
            await self._telethon.disconnect()
        if self._bot_api:
            await self._bot_api.close()
        if self._web_scraper:
            await self._web_scraper.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    async def search_companies(
        self,
        keyword: str,
        limit: int = 50,
        channels: list[str] | None = None,
    ) -> list[TelegramCompany]:
        """
        Tìm kiếm thông tin công ty từ Telegram.

        Args:
            keyword:  Từ khoá tìm kiếm
            limit:    Giới hạn số công ty trả về
            channels: Danh sách kênh cụ thể (nếu None → dùng config mặc định)
        """
        ch_list = channels or config.TELEGRAM_BUSINESS_CHANNELS

        if self._telethon:
            # Chế độ mạnh: tìm + quét kênh theo keyword
            results = await self._telethon.scrape_by_keyword(keyword, channel_limit=10)
            # Bổ sung kênh đã biết nếu vẫn còn chỗ
            if len(results) < limit:
                extra = await self._telethon.scrape_channels_list(ch_list, keyword=keyword)
                existing_names = {r.name for r in results}
                for c in extra:
                    if c.name not in existing_names:
                        results.append(c)
        elif self._web_scraper:
            # Web scraper mode: crawl t.me/s/ – không cần credentials
            logger.info(f"[TG] Crawl {len(ch_list)} kênh qua t.me/s/ ...")
            results = await self._web_scraper.scrape_channels(ch_list, keyword=keyword)
            # Bot API bổ sung metadata
            if self._bot_api:
                bot_results = await self._bot_api.scrape_channels(ch_list, keyword=keyword)
                existing_names = {r.name for r in results}
                for c in bot_results:
                    if c.name not in existing_names:
                        results.append(c)
        else:
            results = []

        return results[:limit]
