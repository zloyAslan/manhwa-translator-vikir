"""
Telegram Cloud Relay Specialist — Master Utility
Stream manhwa chapters from open Telegram channels directly into a private vault channel
WITHOUT saving any files to the local hard drive (100% in-memory streaming via io.BytesIO).

Key Capabilities:
- Telethon MTProto Client + HTTP Bot API dual resilience
- In-memory download & direct upload to private vault channel
- Standardized naming: [TITLE_CODE] 001 (Title Name) [LANG].pdf
- Searchable tags & captions (#TITLE_CODE #CH_001 #UA)
- Strict RAM management: immediate buffer closure and garbage collection
- Cloud Index Dictionary (cloud_index.json) & Pinned Telegram Vault Catalog
- Channel auto-discovery & binding helper
- Interactive Ukrainian CLI + Full Programmatic API
"""

import os
import sys

# Configure UTF-8 encoding for Windows terminals
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import re
import gc
import io
import time
import json
import html
import math
import asyncio
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict

# Third-party dependencies
try:
    from telethon import TelegramClient, events
    from telethon.sessions import SQLiteSession, MemorySession
    from telethon.tl.types import (
        MessageMediaDocument,
        DocumentAttributeFilename,
        InputPeerChannel,
        PeerChannel,
        Channel
    )
    from telethon.errors import (
        FloodWaitError,
        BotMethodInvalidError,
        ChannelPrivateError,
        ChatAdminRequiredError
    )
except ImportError:
    TelegramClient = None
    SQLiteSession = None
    MemorySession = None
    MessageMediaDocument = None
    DocumentAttributeFilename = None
    InputPeerChannel = None
    PeerChannel = None
    Channel = None
    FloodWaitError = Exception
    BotMethodInvalidError = Exception
    ChannelPrivateError = Exception
    ChatAdminRequiredError = Exception

try:
    import requests
except ImportError:
    requests = None


# ---------------------------------------------------------------------------
# Default Constants & Configuration Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
PARENT_DIR = BASE_DIR.parent

DEFAULT_CONFIG_PATH = PARENT_DIR / "config.json" if (PARENT_DIR / "config.json").exists() else BASE_DIR / "config.json"
DEFAULT_INDEX_PATH = PARENT_DIR / "cloud_index.json" if (PARENT_DIR / "cloud_index.json").exists() else BASE_DIR / "cloud_index.json"
DEFAULT_SESSION_PATH = PARENT_DIR / "tg_cloud_relay_session"


DEFAULT_API_ID = 37560778
DEFAULT_API_HASH = "307da2f94fc6450afe139c91bcc59eaa"
DEFAULT_BOT_TOKEN = "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA"
DEFAULT_VAULT_INVITE = "https://t.me/+O6mlGVWzTSQ5MjVi"

VALID_EXTENSIONS = {".pdf", ".zip", ".cbz", ".cbr", ".rar"}
STOP_WORDS = {
    "of", "the", "a", "an", "and", "in", "on", "at", "to", "for", "with",
    "з", "та", "і", "й", "в", "у", "на", "під", "про", "до", "від"
}

logger = logging.getLogger("tg_cloud_relay")


# ---------------------------------------------------------------------------
# Configuration Helpers
# ---------------------------------------------------------------------------
def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Loads configuration from config.json, providing sensible defaults."""
    cfg = {
        "tg_api_id": DEFAULT_API_ID,
        "tg_api_hash": DEFAULT_API_HASH,
        "tg_bot_token": DEFAULT_BOT_TOKEN,
        "tg_vault_invite": DEFAULT_VAULT_INVITE,
        "tg_vault_channel_id": None,
        "tg_vault_channel_title": "",
        "pinned_catalog_msg_id": None,
        "library_path": "library"
    }
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception as e:
            logger.warning(f"Помилка читання конфігурації: {e}")
    return cfg


def save_config(cfg: Dict[str, Any], config_path: Path = DEFAULT_CONFIG_PATH) -> bool:
    """Safely updates config.json while preserving other application settings."""
    try:
        current = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                current = json.load(f)
        current.update(cfg)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Не вдалося зберегти конфігурацію: {e}")
        return False


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class ChapterItem:
    """Represents a manhwa chapter found in an open Telegram channel."""
    message_id: int
    raw_filename: str
    ext: str
    size_bytes: int
    size_mb: float
    chapter_num: int
    caption: str = ""
    message_obj: Any = None

    def display_title(self) -> str:
        ch_str = f"Розділ {self.chapter_num:03d}" if self.chapter_num > 0 else "Спецвипуск"
        return f"{ch_str} | {self.raw_filename} ({self.size_mb:.1f} MB)"


@dataclass
class RelayedChapter:
    """Metadata for a chapter relayed to the vault channel."""
    chapter_num: int
    filename: str
    size_mb: float
    vault_msg_id: int
    vault_msg_link: str
    source_msg_id: int
    source_channel: str
    tags: List[str]
    relayed_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ---------------------------------------------------------------------------
# Utility & Parsing Helpers
# ---------------------------------------------------------------------------
def clean_channel_link(link: str) -> str:
    """Cleans a channel link or @username to a bare username or numeric string."""
    link = link.strip()
    link = re.sub(r"^https?://t\.me/", "", link)
    link = re.sub(r"^t\.me/", "", link)
    link = re.sub(r"^s/", "", link)
    link = link.lstrip("@")
    return link.split("/")[0].split("?")[0]


def parse_channel_id(val: Union[int, str]) -> Optional[int]:
    """
    Parses channel ID from integer, string, or Telegram message URL
    e.g. -1002345678901, 2345678901, or https://t.me/c/2345678901/15
    """
    if val is None:
        return None
        
    val_str = str(val).strip()
    
    # Reject invite links like https://t.me/+... or /joinchat/ (they have no chat ID in text)
    if "t.me/+" in val_str or "joinchat" in val_str:
        return None

    # Message link format: https://t.me/c/2345678901/15 or https://t.me/c/2345678901
    m = re.search(r't\.me/c/(\d+)', val_str)
    if m:
        raw_id = m.group(1)
        if len(raw_id) >= 7:
            return int(f"-100{raw_id}")
        return None

    # Already formatted -100... channel ID
    if val_str.startswith("-100"):
        digits = re.sub(r'[^\d]', '', val_str[4:])
        if len(digits) >= 7:
            return int(f"-100{digits}")
        return None

    # Pure numeric format without -100 prefix (must be at least 8 digits)
    clean = re.sub(r'[^\d]', '', val_str)
    if len(clean) >= 8:
        return int(f"-100{clean}")

    return None


def extract_chapter_number(text: str) -> Optional[int]:
    """
    Extracts chapter number from filename or message caption.
    Handles [001], ch. 1, Глава 15, Розділ 4, #001, title_05.pdf, etc.
    """
    text_clean = text.replace('_', ' ')
    
    # Pattern 1: [006] or [6]
    m = re.search(r'\[(\d{1,4})\]', text_clean)
    if m:
        return int(m.group(1))
    
    # Pattern 2: ch 6, chapter 6, глава 6, розділ 6, ep 6
    m = re.search(r'(?:ch(?:apter)?|глава|розділ|ep(?:isode)?)[\s._-]*(\d{1,4})', text_clean, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Pattern 3: #006 or #6
    m = re.search(r'#(\d{1,4})\b', text_clean)
    if m:
        return int(m.group(1))

    # Pattern 4: Standalone number before extension or surrounded by space/dashes
    m = re.search(r'(?:^|[\s\-])(\d{1,4})(?:\.(?:pdf|zip|cbz|cbr|rar)|\s|$)', text_clean, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def parse_chapter_range(range_str: str) -> Optional[Callable[[int], bool]]:
    """
    Parses chapter range string into a filter predicate (ch: int) -> bool.
    Supports '1-30', '5', '1 2 5', '5-', '-20'.
    """
    if not range_str or not range_str.strip():
        return None
    s = range_str.strip()
    
    if '-' in s:
        parts = s.split('-', 1)
        start = int(parts[0].strip()) if parts[0].strip() else 1
        end = int(parts[1].strip()) if parts[1].strip() else 999999
        return lambda ch: start <= ch <= end
    
    nums = [int(p) for p in s.replace(',', ' ').split() if p.isdigit()]
    if nums:
        target_set = set(nums)
        return lambda ch: ch in target_set
        
    return None


def generate_title_code(title: str) -> str:
    """Generates a clean 2-6 letter uppercase title code/acronym from title name."""
    if not title:
        return "MANHWA"
    cleaned = re.sub(r'[^\w\s]', '', title).strip()
    words = [w for w in cleaned.split() if w.lower() not in STOP_WORDS]
    if not words:
        words = cleaned.split()
    if len(words) >= 2:
        code = ''.join(w[0] for w in words).upper()
        return code[:5] if len(code) > 6 else code
    elif len(words) == 1:
        return words[0][:5].upper()
    return "MANHWA"


def normalize_lang(raw: str) -> str:
    """
    Normalizes language codes and common aliases to uppercase standard tags:
    - 'ан.', 'англ', 'eng', 'english', 'eu' -> 'EN' (or preserves 'EU')
    - 'укр', 'ukr', 'ук', 'ua', 'uk' -> 'UA'
    - 'рус', 'рос', 'ru', 'rus' -> 'RU'
    """
    if not raw or not raw.strip():
        return "EN"
    s = raw.strip().lower().rstrip(".")
    if s in ("ан", "англ", "eng", "english", "en", "us"):
        return "EN"
    elif s == "eu":
        return "EU"
    elif s in ("укр", "ukr", "ук", "ua"):
        return "UA"
    elif s == "uk":
        return "UK"
    elif s in ("рус", "рос", "ru", "rus"):
        return "RU"
    return raw.strip().upper()



def format_chapter_filename(
    title_code: str,
    chapter_num: int,
    title_name: str,
    lang: str = "UA",
    ext: str = "pdf"
) -> str:
    """
    Standardized filename: [TITLE_CODE] 001 (Title Name) [LANG].pdf
    Example: [ПЗ-КХ] 001 (Помста залізно-кровного хорта) [UA].pdf
    """
    code_clean = re.sub(r'[\\/*?:"<>|\[\]]', '', title_code).strip()
    title_clean = re.sub(r'[\\/*?:"<>|\(\)]', '', title_name).strip()
    lang_clean = re.sub(r'[\\/*?:"<>|\[\]]', '', lang).strip()
    ext_clean = ext.lstrip(".").lower()
    ch_str = f"{chapter_num:03d}" if chapter_num < 1000 else f"{chapter_num:04d}"
    return f"[{code_clean}] {ch_str} ({title_clean}) [{lang_clean}].{ext_clean}"


def format_chapter_caption(
    title_code: str,
    chapter_num: int,
    title_name: str,
    lang: str = "UA",
    size_mb: float = 0.0,
    ext: str = "PDF",
    source_channel: str = ""
) -> str:
    """Standardized Telegram caption with searchable tags."""
    code_tag = re.sub(r'[^\w]', '_', title_code).strip('_')
    lang_tag = re.sub(r'[^\w]', '', lang).strip()
    ch_str = f"{chapter_num:03d}" if chapter_num < 1000 else f"{chapter_num:04d}"
    
    tags = [
        f"#TITLE_{code_tag}",
        f"#CH_{ch_str}",
        f"#{lang_tag}" if lang_tag else "",
        f"#{code_tag}"
    ]
    tags = [t for t in tags if t and t != "#"]
    tags_line = " ".join(tags)
    
    safe_code = html.escape(title_code)
    safe_name = html.escape(title_name)
    
    caption_lines = [
        f"📖 <b>[{safe_code}] Розділ {ch_str}</b> — {safe_name}",
        f"📦 Формат: <code>{ext.upper()}</code> | 💾 Розмір: <b>{size_mb:.1f} МБ</b>",
        f"🏷️ {tags_line}",
        "⚡ <i>Telegram Cloud Vault Relay</i>"
    ]
    return "\n".join(caption_lines)


def render_progress_bar(current: int, total: int, width: int = 24) -> str:
    """Renders a sleek terminal progress bar."""
    if total <= 0:
        return f"[{'=' * width}]"
    pct = min(1.0, max(0.0, current / total))
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:5.1f}%"


# ---------------------------------------------------------------------------
# Cloud Index Manager
# ---------------------------------------------------------------------------
class CloudIndexManager:
    """
    Manages persistent index of all manhwa chapters relayed into the private vault.
    Saves to cloud_index.json and formats pinned catalog posts.
    """
    def __init__(self, index_path: Path = DEFAULT_INDEX_PATH):
        self.index_path = index_path
        self.data: Dict[str, Any] = {
            "vault_channel_id": None,
            "vault_channel_title": "",
            "pinned_catalog_msg_id": None,
            "last_updated": None,
            "titles": {}
        }
        self.load()

    def load(self):
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self.data.update(saved)
            except Exception as e:
                logger.warning(f"Помилка завантаження cloud_index.json: {e}")

    def save(self):
        try:
            self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Помилка збереження cloud_index.json: {e}")

    def add_chapter(self, title_code: str, title_name: str, lang: str, chapter: RelayedChapter):
        code = title_code.upper()
        if "titles" not in self.data:
            self.data["titles"] = {}
            
        if code not in self.data["titles"]:
            self.data["titles"][code] = {
                "title_code": code,
                "title_name": title_name,
                "lang": lang.upper(),
                "total_chapters": 0,
                "chapters": {}
            }
            
        title_entry = self.data["titles"][code]
        title_entry["title_name"] = title_name
        title_entry["lang"] = lang.upper()
        
        ch_key = str(chapter.chapter_num)
        title_entry["chapters"][ch_key] = asdict(chapter)
        title_entry["total_chapters"] = len(title_entry["chapters"])
        self.save()

    def has_chapter(self, title_code: str, chapter_num: int) -> bool:
        code = title_code.upper()
        if code in self.data.get("titles", {}):
            return str(chapter_num) in self.data["titles"][code].get("chapters", {})
        return False

    def get_summary(self) -> str:
        titles = self.data.get("titles", {})
        total_ch = sum(t.get("total_chapters", 0) for t in titles.values())
        return f"{len(titles)} тайтлів, {total_ch} розділів у хмарі"

    def format_catalog_markdown(self) -> str:
        """Builds a beautiful Markdown message for pinning in the vault channel."""
        titles = self.data.get("titles", {})
        channel_title = self.data.get("vault_channel_title") or "Manhwa Cloud Vault"
        vault_id = self.data.get("vault_channel_id")
        vault_clean_id = str(abs(vault_id))[3:] if vault_id and str(vault_id).startswith("-100") else ""
        
        lines = [
            f"📚 <b>КАТАЛОГ СХОВИЩА: {channel_title}</b>",
            f"<i>Останнє оновлення: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
            "─────────────────────────────"
        ]
        
        if not titles:
            lines.append("<i>Сховище наразі порожнє. Розділи ще не ретрансльовано.</i>")
        else:
            for code_key, info in titles.items():
                code = info.get("title_code") or info.get("code") or code_key
                name = info.get("title_name") or info.get("title") or code_key
                lang = info.get("lang", "UA")
                chapters = info.get("chapters", {})
                ch_nums = sorted([int(k) for k in chapters.keys()])
                
                if ch_nums:
                    min_ch, max_ch = ch_nums[0], ch_nums[-1]
                    range_txt = f"{min_ch:03d} – {max_ch:03d}" if len(ch_nums) > 1 else f"{min_ch:03d}"
                else:
                    range_txt = "0"
                    
                lines.append(f"\n📖 <b>{name}</b> <code>[{code}]</code> [{lang}]")
                lines.append(f"• Доступно розділів: <b>{len(chapters)}</b> (№ {range_txt})")
                
                # Render direct links if vault ID is available
                links = []
                for ch_num in ch_nums[:8]:  # Show first 8 direct links
                    ch_data = chapters[str(ch_num)]
                    msg_id = ch_data.get("vault_msg_id") or ch_data.get("message_id")
                    if msg_id and vault_clean_id:
                        link_url = f"https://t.me/c/{vault_clean_id}/{msg_id}"
                        links.append(f"<a href=\"{link_url}\">№{ch_num:03d}</a>")
                    else:
                        links.append(f"№{ch_num:03d}")
                        
                if len(ch_nums) > 8:
                    last_ch = ch_nums[-1]
                    last_msg_id = chapters[str(last_ch)].get("vault_msg_id") or chapters[str(last_ch)].get("message_id")
                    if last_msg_id and vault_clean_id:
                        links.append(f"... <a href=\"https://t.me/c/{vault_clean_id}/{last_msg_id}\">№{last_ch:03d}</a>")
                    else:
                        links.append(f"... №{last_ch:03d}")
                        
                if links:
                    lines.append(f"• Швидкі посилання: {' • '.join(links)}")
                lines.append(f"• Теги: <code>#TITLE_{code}</code> <code>#{code}</code>")

        lines.extend([
            "\n─────────────────────────────",
            "🏷️ <code>#CATALOG</code> <code>#INDEX</code> <code>#VAULT</code>",
            "⚡ <i>Автоматично згенеровано Manhwa Cloud Relay</i>"
        ])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP Bot API Fallback Client
# ---------------------------------------------------------------------------
class TelegramBotApiClient:
    """Direct HTTP Telegram Bot API client for instant updates & <=50MB streaming."""
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def get_me(self) -> Dict[str, Any]:
        url = f"{self.base_url}/getMe"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def get_chat(self, chat_id: Union[int, str]) -> Dict[str, Any]:
        url = f"{self.base_url}/getChat?chat_id={chat_id}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def send_message(self, chat_id: Union[int, str], text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def edit_message_text(self, chat_id: Union[int, str], message_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/editMessageText", data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def pin_chat_message(self, chat_id: Union[int, str], message_id: int) -> Dict[str, Any]:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "message_id": message_id
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/pinChatMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def get_updates(self, offset: Optional[int] = None, timeout: int = 1) -> List[Dict[str, Any]]:
        params = {
            "timeout": timeout,
            "allowed_updates": json.dumps(["message", "channel_post", "my_chat_member", "chat_member"])
        }
        if offset is not None:
            params["offset"] = offset
        url = f"{self.base_url}/getUpdates?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=timeout + 5) as resp:
            res = json.loads(resp.read().decode())
            return res.get("result", [])

    def upload_document(
        self,
        chat_id: Union[int, str],
        file_buffer: io.BytesIO,
        filename: str,
        caption: str = "",
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Uploads in-memory buffer via multipart HTTP (supports files up to 50MB)."""
        if not requests:
            raise RuntimeError("Пакунок 'requests' необхідний для резервного HTTP завантаження.")
        
        file_buffer.seek(0)
        files = {
            "document": (filename, file_buffer, "application/octet-stream")
        }
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": parse_mode
        }
        resp = requests.post(f"{self.base_url}/sendDocument", data=data, files=files, timeout=120)
        return resp.json()


# ---------------------------------------------------------------------------
# Master Telegram Cloud Relay Engine
# ---------------------------------------------------------------------------
class TelegramCloudRelay:
    """
    Main Relay Specialist engine.
    Streams manhwa chapters from open channels into private vault channels
    without any local disk I/O.
    """
    def __init__(
        self,
        api_id: int = DEFAULT_API_ID,
        api_hash: str = DEFAULT_API_HASH,
        bot_token: str = DEFAULT_BOT_TOKEN,
        vault_id: Optional[int] = None,
        session_path: Optional[Union[str, Path]] = DEFAULT_SESSION_PATH,
        use_memory_session: bool = False,
        config_path: Path = DEFAULT_CONFIG_PATH,
        index_path: Path = DEFAULT_INDEX_PATH
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.config_path = config_path
        self.session_path = str(session_path) if session_path else str(DEFAULT_SESSION_PATH)
        self.use_memory_session = use_memory_session
        
        # Load configs
        cfg = load_config(self.config_path)
        self.vault_id = vault_id or cfg.get("tg_vault_channel_id")
        self.vault_title = cfg.get("tg_vault_channel_title", "")
        self.vault_invite = cfg.get("tg_vault_invite", DEFAULT_VAULT_INVITE)
        
        self.index_manager = CloudIndexManager(index_path)
        if self.vault_id:
            self.index_manager.data["vault_channel_id"] = self.vault_id
        if self.vault_title:
            self.index_manager.data["vault_channel_title"] = self.vault_title
            
        self.client: Optional[TelegramClient] = None
        self.http_bot = TelegramBotApiClient(self.bot_token)
        self._vault_entity: Any = None

    async def connect(self):
        """Connects Telethon client with persistent SQLite session or MemorySession."""
        if self.client and self.client.is_connected():
            return
            
        if TelegramClient is None:
            raise RuntimeError("Telethon не встановлено в середовищі. Запустіть 'pip install telethon'.")

        session = MemorySession() if self.use_memory_session else self.session_path
        self.client = TelegramClient(session, self.api_id, self.api_hash)
        
        try:
            await self.client.start(bot_token=self.bot_token)
            me = await self.client.get_me()
            logger.info(f"🟢 Підключено до Telegram як @{me.username} (ID: {me.id})")
        except FloodWaitError as e:
            wait_min = math.ceil(e.seconds / 60)
            msg = (
                f"\n⚠️ Telegram встановив FloodWait на {e.seconds} сек (~{wait_min} хв) "
                f"для авторизації бота.\n"
                f"Після завершення таймера сесія збережеться у базі назавжди й очікування більше не повториться."
            )
            print(msg)
            
            # Interactive phone fallback option
            print("💡 Ви можете увійти зі свого особистого Telegram-акаунта (за номером телефону),")
            print("   щоб почати качати розділи прямо зараз, не чекаючи 20 хвилин!")
            choice = input("\nАвторизувати особистий Telegram (y/N)? ").strip().lower()
            if choice in ("y", "yes", "так"):
                phone = input("Введіть ваш номер телефону для Telegram (+380...): ").strip()
                if phone:
                    await self.client.send_code_request(phone)
                    code = input("Введіть код підтвердження з Telegram: ").strip()
                    try:
                        await self.client.sign_in(phone, code)
                        me = await self.client.get_me()
                        print(f"🟢 Успішно підключено як {me.first_name} (@{getattr(me, 'username', '') or 'user'})!")
                        return
                    except Exception as pe:
                        print(f"❌ Помилка входу за телефоном: {pe}")
            raise RuntimeError(f"Очікування завершення FloodWait ({wait_min} хв)...")

    async def disconnect(self):
        """Safely disconnects client."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    # -----------------------------------------------------------------------
    # Vault Channel Discovery & Binding
    # -----------------------------------------------------------------------
    async def bind_vault(
        self,
        target: Optional[Union[int, str]] = None,
        timeout: int = 60,
        status_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[int, str]:
        """
        Discovers and binds the target private vault channel.
        Supports:
        - Direct numeric ID (e.g. -1002345678901)
        - Telegram message link (e.g. https://t.me/c/2345678901/15)
        - Automated update listening: guides user to send any message / command to channel.
        """
        def log(msg: str):
            if status_cb:
                status_cb(msg)
            else:
                print(msg)

        # 1. Target provided directly
        if target:
            parsed_id = parse_channel_id(target)
            if not parsed_id:
                raise ValueError(
                    "Некоректний формат! Посилання-запрошення (https://t.me/+...) не містить ID каналу.\n"
                    "Будь ласка, скопіюйте посилання на БУДЬ-ЯКЕ повідомлення всередині каналу (вигляд: https://t.me/c/XXXXXXXXXX/1) "
                    "або введіть числовий ID (-100...)."
                )
            log(f"🔎 Перевірка доступу до каналу з ID: {parsed_id}...")
            try:
                chat_info = self.http_bot.get_chat(parsed_id)
                if chat_info.get("ok"):
                    title = chat_info["result"].get("title", f"Vault {parsed_id}")
                    self._save_vault_info(parsed_id, title)
                    log(f"✅ Канал успішно перевірено та прив'язано: «{title}» (ID: {parsed_id})")
                    return parsed_id, title
                else:
                    raise RuntimeError(f"Telegram повернув помилку: {chat_info.get('description')}")
            except Exception as e:
                log(f"❌ Бот не має доступу до каналу {parsed_id}: {e}\n"
                    f"Переконайтеся, що бот доданий у канал як АДМІНІСТРАТОР (із правом публікації повідомлень).")
                raise e

        # 2. Check if already bound in config
        if self.vault_id:
            try:
                chat_info = self.http_bot.get_chat(self.vault_id)
                if chat_info.get("ok"):
                    title = chat_info["result"].get("title", f"Vault {self.vault_id}")
                    self.vault_title = title
                    log(f"ℹ️ Використовується збережений канал-сховище: «{title}» (ID: {self.vault_id})")
                    return self.vault_id, title
            except Exception:
                pass

        # 3. Interactive / Auto-Discovery Listener via Telegram Updates
        log("\n" + "=" * 65)
        log("🔗 РЕЖИМ АВТОВИЯВЛЕННЯ КАНАЛУ-СХОВИЩА")
        log("=" * 65)
        log(f"1. Додайте бота в приватний канал як АДМІНІСТРАТОРА (право публікації).")
        log(f"   (Ваше посилання-запрошення: {self.vault_invite})")
        log(f"2. Надішліть у цей канал БУДЬ-ЯКЕ повідомлення (наприклад: /bind або привіт).")
        log(f"3. Очікування оновлення від Telegram (таймаут {timeout} сек)...")

        start_time = time.time()
        last_offset = None
        
        while time.time() - start_time < timeout:
            try:
                updates = self.http_bot.get_updates(offset=last_offset, timeout=2)
                for u in updates:
                    last_offset = u["update_id"] + 1
                    chat = None
                    if "channel_post" in u:
                        chat = u["channel_post"].get("chat")
                    elif "my_chat_member" in u:
                        chat = u["my_chat_member"].get("chat")
                    elif "message" in u:
                        chat = u["message"].get("chat")

                    if chat and chat.get("type") in ("channel", "supergroup"):
                        cid = chat.get("id")
                        title = chat.get("title", "Приватне Сховище")
                        log(f"\n🎉 Виявлено канал: «{title}» (ID: {cid})!")
                        
                        # Send confirmation test post
                        try:
                            self.http_bot.send_message(
                                cid,
                                "⚡ <b>Канал-сховище успішно прив'язано до Manhwa Cloud Relay!</b>\n"
                                "Готовий до стрімінгу розділів без збереження на диск."
                            )
                        except Exception:
                            pass
                            
                        self._save_vault_info(cid, title)
                        return cid, title
            except Exception as e:
                pass
            await asyncio.sleep(1.5)

        raise TimeoutError(
            "Не вдалося автоматично виявити канал-сховище за вказаний час. "
            "Переконайтеся, що бот є адміністратором каналу, або вкажіть ID вручну (--vault -100...)."
        )

    def _save_vault_info(self, vault_id: int, title: str):
        self.vault_id = vault_id
        self.vault_title = title
        self.index_manager.data["vault_channel_id"] = vault_id
        self.index_manager.data["vault_channel_title"] = title
        self.index_manager.save()
        save_config({
            "tg_vault_channel_id": vault_id,
            "tg_vault_channel_title": title
        }, self.config_path)

    async def get_vault_entity(self) -> Any:
        """Resolves Telethon entity for vault channel or returns vault_id."""
        if not self.vault_id:
            await self.bind_vault()
            
        if self._vault_entity:
            return self._vault_entity

        if self.client and self.client.is_connected():
            try:
                self._vault_entity = await self.client.get_entity(self.vault_id)
                return self._vault_entity
            except Exception as e:
                logger.info(f"MTProto get_entity requires cache: {e}. Using raw ID {self.vault_id}.")
        return self.vault_id

    # -----------------------------------------------------------------------
    # Source Channel Chapter Discovery
    # -----------------------------------------------------------------------
    async def find_channel_latest_id(self, entity: Any) -> int:
        """Finds latest message ID in an open channel using fast exponential search."""
        low = 1
        cur = 200
        step = 400
        while True:
            try:
                m = await self.client.get_messages(entity, ids=cur)
                if m is not None:
                    low = cur
                    cur += step
                    step *= 2
                else:
                    high = cur
                    break
            except Exception:
                high = cur
                break
                
        while low + 1 < high:
            mid = (low + high) // 2
            try:
                m = await self.client.get_messages(entity, ids=mid)
                if m is not None:
                    low = mid
                else:
                    high = mid
            except Exception:
                high = mid
        return low

    async def search_source_channel(
        self,
        source_channel: str,
        keyword: str = "",
        chapter_range: Optional[str] = None,
        limit: int = 500,
        status_cb: Optional[Callable[[str], None]] = None
    ) -> List[ChapterItem]:
        """
        Scans an open Telegram channel for manhwa chapters (PDF, ZIP, CBZ, CBR).
        Applies keyword filter and chapter range filter.
        """
        def log(msg: str):
            if status_cb:
                status_cb(msg)
            else:
                print(msg)

        await self.connect()
        ch_clean = clean_channel_link(source_channel)
        log(f"🔍 Підключення до відкритого каналу: @{ch_clean}...")
        
        try:
            entity = await self.client.get_entity(ch_clean)
        except Exception as e:
            raise RuntimeError(f"Не вдалося знайти або відкрити канал '@{ch_clean}': {e}")

        kw = keyword.strip().lower()
        range_filter = parse_chapter_range(chapter_range) if chapter_range else None

        # Determine message scan boundaries
        latest_id = await self.find_channel_latest_id(entity)
        start_id = max(1, latest_id - limit + 1)
        total_to_scan = latest_id - start_id + 1
        log(f"📊 Останнє повідомлення каналу: #{latest_id}. Сканування діапазону #{start_id}..#{latest_id} ({total_to_scan} повідомлень)...")

        found_chapters: List[ChapterItem] = []
        batch_size = 100

        for b_start in range(start_id, latest_id + 1, batch_size):
            b_ids = list(range(b_start, min(b_start + batch_size, latest_id + 1)))
            try:
                msgs = await self.client.get_messages(entity, ids=b_ids)
            except Exception as e:
                logger.warning(f"Помилка завантаження пачки повідомлень: {e}")
                continue

            for m in msgs:
                if not m or not m.media:
                    continue
                
                doc_name = ""
                doc_size = 0
                
                if isinstance(m.media, MessageMediaDocument) and m.media.document:
                    doc_size = m.media.document.size or 0
                    for attr in m.media.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            doc_name = attr.file_name
                            break

                ext = Path(doc_name).suffix.lower()
                if ext not in VALID_EXTENSIONS:
                    continue

                caption = m.text or ""
                search_haystack = f"{doc_name} {caption}".lower()
                
                if kw and kw not in search_haystack:
                    continue

                ch_num = extract_chapter_number(doc_name) or extract_chapter_number(caption) or -1
                
                if range_filter and ch_num != -1:
                    if not range_filter(ch_num):
                        continue

                size_mb = round(doc_size / (1024 * 1024), 2)
                found_chapters.append(ChapterItem(
                    message_id=m.id,
                    raw_filename=doc_name,
                    ext=ext.lstrip("."),
                    size_bytes=doc_size,
                    size_mb=size_mb,
                    chapter_num=ch_num,
                    caption=caption,
                    message_obj=m
                ))

        # Sort naturally by chapter number, then by message id
        found_chapters.sort(key=lambda x: (x.chapter_num if x.chapter_num != -1 else 999999, x.message_id))
        log(f"✅ Знайдено валідних розділів манхви: {len(found_chapters)}")
        return found_chapters

    # -----------------------------------------------------------------------
    # In-Memory Stream Relay (Zero Disk I/O)
    # -----------------------------------------------------------------------
    async def stream_relay_chapter(
        self,
        chapter_item: ChapterItem,
        title_code: str,
        title_name: str,
        lang: str = "UA",
        vault_target: Any = None,
        progress_cb: Optional[Callable[[str, float, int, int], None]] = None
    ) -> RelayedChapter:
        """
        Streams a single chapter from the open channel into the vault channel.
        Uses in-memory buffer (io.BytesIO) with immediate garbage collection.
        Zero files written to the local hard drive!
        """
        await self.connect()
        target = vault_target or await self.get_vault_entity()
        
        new_filename = format_chapter_filename(
            title_code=title_code,
            chapter_num=chapter_item.chapter_num,
            title_name=title_name,
            lang=lang,
            ext=chapter_item.ext
        )
        
        caption = format_chapter_caption(
            title_code=title_code,
            chapter_num=chapter_item.chapter_num,
            title_name=title_name,
            lang=lang,
            size_mb=chapter_item.size_mb,
            ext=chapter_item.ext.upper()
        )

        in_memory_buffer = io.BytesIO()
        in_memory_buffer.name = new_filename

        try:
            # 1. DOWNLOAD PHASE (Directly into RAM buffer)
            def dl_callback(current, total):
                pct = (current / total) * 100 if total > 0 else 0
                if progress_cb:
                    progress_cb("download", pct, current, total)

            await self.client.download_media(
                chapter_item.message_obj,
                file=in_memory_buffer,
                progress_callback=dl_callback
            )
            in_memory_buffer.seek(0)
            buffer_size = in_memory_buffer.getbuffer().nbytes

            # 2. UPLOAD PHASE (Stream directly from RAM into Vault Channel)
            def up_callback(current, total):
                pct = (current / total) * 100 if total > 0 else 0
                if progress_cb:
                    progress_cb("upload", pct, current, total)

            sent_msg_id = None
            
            # Primary engine: Telethon MTProto
            try:
                sent_msg = await self.client.send_file(
                    target,
                    file=in_memory_buffer,
                    attributes=[DocumentAttributeFilename(file_name=new_filename)],
                    caption=caption,
                    parse_mode="html",
                    progress_callback=up_callback
                )
                sent_msg_id = sent_msg.id
            except Exception as mtproto_err:
                logger.warning(f"MTProto send_file error: {mtproto_err}. Спроба через HTTP Bot API...")
                # HTTP Bot API fallback for files <= 50MB
                if buffer_size <= 50 * 1024 * 1024 and self.vault_id:
                    in_memory_buffer.seek(0)
                    resp = self.http_bot.upload_document(
                        chat_id=self.vault_id,
                        file_buffer=in_memory_buffer,
                        filename=new_filename,
                        caption=caption
                    )
                    if resp.get("ok"):
                        sent_msg_id = resp["result"]["message_id"]
                    else:
                        raise RuntimeError(f"HTTP upload failed: {resp.get('description')}")
                else:
                    raise mtproto_err

            # 3. Create Record & Index
            vault_clean_id = str(abs(self.vault_id))[3:] if self.vault_id and str(self.vault_id).startswith("-100") else ""
            vault_link = f"https://t.me/c/{vault_clean_id}/{sent_msg_id}" if vault_clean_id and sent_msg_id else ""
            
            relayed = RelayedChapter(
                chapter_num=chapter_item.chapter_num,
                filename=new_filename,
                size_mb=chapter_item.size_mb,
                vault_msg_id=sent_msg_id or 0,
                vault_msg_link=vault_link,
                source_msg_id=chapter_item.message_id,
                source_channel=str(getattr(chapter_item.message_obj.chat, 'username', '')),
                tags=[f"#TITLE_{title_code}", f"#CH_{chapter_item.chapter_num:03d}", f"#{lang.upper()}"]
            )
            
            self.index_manager.add_chapter(title_code, title_name, lang, relayed)
            return relayed

        finally:
            # 4. MEMORY PURGE (Mandatory cleanup)
            in_memory_buffer.close()
            del in_memory_buffer
            gc.collect()

    async def relay_batch(
        self,
        chapters: List[ChapterItem],
        title_code: str,
        title_name: str,
        lang: str = "UA",
        skip_existing: bool = True,
        status_cb: Optional[Callable[[str], None]] = None,
        item_done_cb: Optional[Callable[[RelayedChapter, int, int], None]] = None
    ) -> List[RelayedChapter]:
        """Relays a sequence of chapters with progress reporting and existing check."""
        def log(msg: str):
            if status_cb:
                status_cb(msg)
            else:
                print(msg)

        results: List[RelayedChapter] = []
        total = len(chapters)
        log(f"🚀 Початок стрімінгу {total} розділів для «{title_name}» [{title_code}]...")

        for idx, item in enumerate(chapters, 1):
            ch_num = item.chapter_num
            if skip_existing and self.index_manager.has_chapter(title_code, ch_num):
                log(f"⏩ [{idx}/{total}] Розділ {ch_num:03d} вже є у хмарному індексі. Пропуск.")
                continue

            log(f"\n📦 [{idx}/{total}] Стрімінг: Розділ {ch_num:03d} ({item.size_mb:.1f} MB)...")
            
            def on_progress(phase: str, pct: float, cur: int, tot: int):
                cur_mb = cur / (1024 * 1024)
                tot_mb = tot / (1024 * 1024)
                bar = render_progress_bar(cur, tot, width=20)
                phase_ua = "Завантаження в RAM" if phase == "download" else "Стрімінг у сховище"
                sys.stdout.write(f"\r   {phase_ua}: {bar} {cur_mb:.1f}/{tot_mb:.1f} МБ")
                sys.stdout.flush()

            try:
                relayed = await self.stream_relay_chapter(
                    chapter_item=item,
                    title_code=title_code,
                    title_name=title_name,
                    lang=lang,
                    progress_cb=on_progress
                )
                print(f" -> ✅ УСПІШНО!")
                results.append(relayed)
                if item_done_cb:
                    item_done_cb(relayed, idx, total)
            except Exception as e:
                print(f" -> ❌ ПОМИЛКА: {e}")
                logger.error(f"Помилка стрімінгу розділу {ch_num}: {e}")

        log(f"\n🎉 Завершено! Успішно ретрансльовано: {len(results)}/{total} розділів.")
        return results

    # -----------------------------------------------------------------------
    # Pinned Vault Catalog Management
    # -----------------------------------------------------------------------
    async def sync_catalog_post(self, vault_target: Any = None) -> Optional[int]:
        """Generates or updates the pinned catalog post in the private vault channel."""
        target_id = self.vault_id
        if not target_id:
            return None
            
        catalog_text = self.index_manager.format_catalog_markdown()
        pinned_msg_id = self.index_manager.data.get("pinned_catalog_msg_id")

        # 1. Try editing existing pinned post
        if pinned_msg_id:
            try:
                res = self.http_bot.edit_message_text(target_id, pinned_msg_id, catalog_text)
                if res.get("ok"):
                    print(f"📌 Закріплений каталог успішно оновлено (Повідомлення #{pinned_msg_id}).")
                    return pinned_msg_id
            except Exception as e:
                logger.info(f"Не вдалося відредагувати повідомлення #{pinned_msg_id}: {e}. Створюємо новий пост...")

        # 2. Send new post and pin it
        try:
            res = self.http_bot.send_message(target_id, catalog_text)
            if res.get("ok"):
                new_msg_id = res["result"]["message_id"]
                try:
                    self.http_bot.pin_chat_message(target_id, new_msg_id)
                except Exception:
                    pass
                self.index_manager.data["pinned_catalog_msg_id"] = new_msg_id
                self.index_manager.save()
                save_config({"pinned_catalog_msg_id": new_msg_id}, self.config_path)
                print(f"📌 Створено та закріплено новий каталог (Повідомлення #{new_msg_id})!")
                return new_msg_id
        except Exception as e:
            print(f"⚠️ Помилка створення каталогу у каналі: {e}")
            return None


# ---------------------------------------------------------------------------
# Interactive Ukrainian CLI Interface
# ---------------------------------------------------------------------------
def print_banner(relay: TelegramCloudRelay):
    print("\n" + "=" * 70)
    print("   ⚡ MANHWA TELEGRAM CLOUD RELAY — ГОЛОВНА УТИЛІТА СТРІМІНГУ ⚡   ")
    print("   Пряма передача розділів манхви з відкритих каналів у сховище    ")
    print("           (100% В ОПЕРАТИВНІЙ ПАМ'ЯТІ • БЕЗ ДИСКУ)                ")
    print("=" * 70)
    v_id = relay.vault_id or "НЕ ПРИВ'ЯЗАНО"
    v_title = relay.vault_title or "—"
    summary = relay.index_manager.get_summary()
    print(f"🏛️  Канал-сховище: {v_title} [ID: {v_id}]")
    print(f"📊 Хмарний індекс: {summary}")
    print("=" * 70)


async def run_interactive_mode(relay: TelegramCloudRelay):
    """Rich interactive console menu in Ukrainian."""
    while True:
        print_banner(relay)
        print("\nОберіть дію:")
        print(" [1] 🚀 Пошук та стрімінг розділів (Відкритий канал ➔ Сховище)")
        print(" [2] 🔗 Прив'язати / перевірити приватний канал-сховище")
        print(" [3] 📋 Переглянути хмарний індекс (Cloud Index)")
        print(" [4] 📌 Оновити закріплений каталог у каналі-сховищі")
        print(" [5] ⚙️ Налаштування та статус підключення")
        print(" [0] 🚪 Вихід")
        
        choice = input("\nВаш вибір [0-5]: ").strip()
        
        if choice == "0":
            print("\nДо зустрічі! Завершення роботи...")
            await relay.disconnect()
            break

        elif choice == "1":
            print("\n" + "=" * 65)
            print("🚀 ПОШУК ТА СТРІМІНГ РОЗДІЛІВ (RAM ➔ ПРИВАТНЕ СХОВИЩЕ)")
            print("=" * 65)
            
            # 1. Канал-джерело
            source = input("1. З якого каналу викачуємо? (посилання або @username): ").strip()
            if not source:
                print("❌ Канал-джерело не вказано.")
                continue

            # 2. Повна назва тайтлу
            title_name = input("2. Повна назва тайтлу (буде у дужках '( )', напр. Помста залізно-кровного хорта): ").strip()
            if not title_name:
                title_name = "Manhwa"

            # 3. Скорочена назва / код
            auto_code = generate_title_code(title_name)
            title_code = input(f"3. Скорочена назва / код (буде у '[ ]', напр. ПЗ-КХ, Enter = '{auto_code}'): ").strip() or auto_code

            # 4. Локалізація
            raw_lang = input("4. Яка локалізація? (напр. EN / UA / RU, Enter = 'EN'): ").strip()
            lang = normalize_lang(raw_lang)

            # 5. Номер або діапазон глав
            ch_range = input("5. Яка глава або діапазон? (напр. 1-30, 5, або Enter для всіх знайдених): ").strip()

            # 6. Пошуковий фільтр
            keyword = input(f"6. Пошуковий фільтр у каналі (Enter для пошуку '{title_name}' або всіх PDF): ").strip()

            try:
                items = await relay.search_source_channel(
                    source_channel=source,
                    keyword=keyword,
                    chapter_range=ch_range
                )
            except Exception as e:
                print(f"❌ Помилка пошуку: {e}")
                continue

            if not items:
                print("⚠️ Розділів за вказаними фільтрами не знайдено.")
                continue

            print(f"\n✅ Знайдено {len(items)} розділів! Приклад назв у сховищі:")
            for it in items[:5]:
                sample_name = format_chapter_filename(
                    title_code=title_code,
                    chapter_num=it.chapter_num or 1,
                    title_name=title_name,
                    lang=lang,
                    ext=it.ext
                )
                print(f"  📄 {sample_name} ({it.size_mb:.1f} MB)")
            if len(items) > 5:
                print(f"  ... та ще {len(items) - 5} розділів.")

            confirm = input(f"\nРозпочати стрімінг {len(items)} розділів у сховище через RAM (0 байт на диску)? [Y/n]: ").strip().lower()
            if confirm in ("", "y", "yes", "так"):
                # Validate Vault Channel
                if not relay.vault_id:
                    print("\n" + "=" * 65)
                    print("⚠️ ПРИВАТНИЙ КАНАЛ-СХОВИЩЕ ЩЕ НЕ ПРИВ'ЯЗАНО!")
                    print("=" * 65)
                    print("Щоб бот знав, куди вивантажувати розділи:")
                    print("1. Відкрийте ваш приватний канал у Telegram (де бот є адміном).")
                    print("2. Надішліть будь-яке повідомлення (напр. привіт).")
                    print("3. Клікніть правою кнопкою на це повідомлення -> 'Скопіювати посилання'")
                    print("   (вигляд: https://t.me/c/XXXXXXXXXX/1).")
                    raw_val = input("\nВставте посилання на повідомлення з каналу (або ID -100...): ").strip()
                    try:
                        await relay.bind_vault(target=raw_val)
                    except Exception as ve:
                        print(f"❌ {ve}")
                        continue

                await relay.relay_batch(items, title_code=title_code, title_name=title_name, lang=lang)

                
                pin_q = input("\nОновити закріплений каталог у каналі-сховищі? [Y/n]: ").strip().lower()
                if pin_q in ("", "y", "yes", "так"):
                    await relay.sync_catalog_post()

        elif choice == "2":
            print("\n--- 🔗 ПРИВ'ЯЗКА ПРИВАТНОГО КАНАЛУ-СХОВИЩА ---")
            print("1. Ввести ID вручну (наприклад: -1002345678901 або посилання https://t.me/c/...)")
            print("2. Автовиявлення (надіслати повідомлення або /bind у канал)")
            sub_c = input("Виберіть варіант [1/2]: ").strip()
            
            if sub_c == "1":
                raw_val = input("Введіть ID або посилання: ").strip()
                try:
                    await relay.bind_vault(target=raw_val)
                except Exception as e:
                    print(f"❌ Помилка: {e}")
            else:
                try:
                    await relay.bind_vault(timeout=60)
                except Exception as e:
                    print(f"❌ Помилка автовиявлення: {e}")

        elif choice == "3":
            print("\n--- 📋 ХМАРНИЙ ІНДЕКС (CLOUD INDEX) ---")
            titles = relay.index_manager.data.get("titles", {})
            if not titles:
                print("Хмарний індекс порожній.")
            else:
                for code, data in titles.items():
                    print(f"\n📖 [{code}] {data.get('title_name')} [{data.get('lang')}]")
                    print(f"   Всього розділів: {data.get('total_chapters')}")
                    chapters = data.get("chapters", {})
                    sorted_ch = sorted([int(k) for k in chapters.keys()])
                    sample = [f"№{c:03d}" for c in sorted_ch[:10]]
                    print(f"   Розділи: {', '.join(sample)}{'...' if len(sorted_ch) > 10 else ''}")
            input("\nНатисніть Enter для повернення...")

        elif choice == "4":
            print("\n--- 📌 ОНОВЛЕННЯ ЗАКРІПЛЕНОГО КАТАЛОГУ ---")
            await relay.sync_catalog_post()
            input("\nНатисніть Enter для повернення...")

        elif choice == "5":
            print("\n--- ⚙️ НАЛАШТУВАННЯ ТА СТАТУС ---")
            print(f"Telegram Bot Token: {relay.bot_token[:10]}...{relay.bot_token[-5:]}")
            print(f"API ID: {relay.api_id}")
            print(f"Vault Channel ID: {relay.vault_id or 'Не встановлено'}")
            print(f"Vault Invite Link: {relay.vault_invite}")
            try:
                me = relay.http_bot.get_me()
                print(f"🟢 Статус Bot API: OK (@{me['result']['username']})")
            except Exception as e:
                print(f"🔴 Статус Bot API: Помилка ({e})")
            input("\nНатисніть Enter для повернення...")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="⚡ Manhwa Telegram Cloud Relay — Master Streaming Utility",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-s", "--source", help="Відкритий канал-джерело (username або посилання)")
    parser.add_argument("-v", "--vault", help="ID або посилання на приватний канал-сховище (-100...)")
    parser.add_argument("-f", "--filter", default="", help="Ключове слово для пошуку")
    parser.add_argument("-r", "--range", default="", help="Діапазон розділів (наприклад: 1-30, 5, 1 2 5)")
    parser.add_argument("-c", "--title-code", help="Код тайтлу (наприклад: PZKH, SWORD_HOUND)")
    parser.add_argument("-n", "--title-name", help="Повна назва манхви")
    parser.add_argument("-l", "--lang", default="UA", help="Мовний тег (за замовчуванням: UA)")
    parser.add_argument("--limit", type=int, default=500, help="Кількість останніх повідомлень для сканування")
    parser.add_argument("--bind", action="store_true", help="Запустити майстер прив'язки каналу-сховища")
    parser.add_argument("--pin-catalog", action="store_true", help="Оновити закріплений каталог у сховищі")
    parser.add_argument("--show-index", action="store_true", help="Показати хмарний індекс")
    parser.add_argument("-i", "--interactive", action="store_true", help="Інтерактивний консольний режим")

    args = parser.parse_args()

    relay = TelegramCloudRelay(vault_id=parse_channel_id(args.vault) if args.vault else None)

    async def cli_runner():
        if args.bind:
            await relay.bind_vault(target=args.vault)
            return

        if args.pin_catalog:
            await relay.sync_catalog_post()
            return

        if args.show_index:
            print(json.dumps(relay.index_manager.data, ensure_ascii=False, indent=2))
            return

        if args.source:
            t_name = args.title_name or args.filter or "Manhwa"
            t_code = args.title_code or generate_title_code(t_name)
            
            items = await relay.search_source_channel(
                source_channel=args.source,
                keyword=args.filter,
                chapter_range=args.range,
                limit=args.limit
            )
            if not items:
                print("Розділів не знайдено.")
                return

            await relay.relay_batch(items, title_code=t_code, title_name=t_name, lang=args.lang)
            return

        # Default to interactive mode
        await run_interactive_mode(relay)

    try:
        asyncio.run(cli_runner())
    except KeyboardInterrupt:
        print("\nРоботу перервано користувачем.")
    except Exception as e:
        print(f"\n❌ Критична помилка: {e}")


if __name__ == "__main__":
    main()
