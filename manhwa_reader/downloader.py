"""
Downloader module for Telegram Manhwa Reader.
Uses Telethon to search and download manhwa chapters (PDF, ZIP, CBZ, images)
from open Telegram channels, extracting them into seamless page folders.
"""

import os
import re
import sys
import json
import asyncio
import zipfile
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any

try:
    from telethon import TelegramClient
    from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename
except ImportError:
    TelegramClient = None

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if DEFAULT_CONFIG_PATH.exists():
        try:
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "tg_api_id": 37560778,
        "tg_api_hash": "307da2f94fc6450afe139c91bcc59eaa",
        "tg_bot_token": "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA",
        "library_path": "library"
    }


def clean_channel_link(link: str) -> str:
    link = link.strip()
    link = re.sub(r"^https?://t\.me/", "", link)
    link = re.sub(r"^t\.me/", "", link)
    link = re.sub(r"^s/", "", link)
    link = link.lstrip("@")
    return link.split("/")[0].split("?")[0]


def extract_chapter_number(text: str) -> Optional[int]:
    """Extract chapter number from filename or message caption."""
    # Pattern 1: [006] or [6]
    m = re.search(r'\[(\d{1,4})\]', text)
    if m:
        return int(m.group(1))
    
    # Pattern 2: ch 6, chapter 6, глава 6, розділ 6
    m = re.search(r'(?:ch(?:apter)?|глава|розділ|ep|episode)[\s._-]*(\d{1,4})', text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    # Pattern 3: #006 or #6
    m = re.search(r'#(\d{1,4})', text)
    if m:
        return int(m.group(1))

    # Pattern 4: any standalone number in brackets or preceded by space/dash
    m = re.search(r'(?:^|[\s_\-])(\d{1,4})(?:\.pdf|\.zip|\.cbz|\s|$)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def extract_pdf_to_images(pdf_path: Path, output_dir: Path, progress_cb: Optional[Callable[[str], None]] = None) -> int:
    """Extracts all pages from PDF to high quality JPEG images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not fitz:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Run 'pip install pymupdf'.")
    
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    
    if progress_cb:
        progress_cb(f"Конвертація PDF: 0/{total_pages} сторінок...")

    saved_count = 0
    for idx, page in enumerate(doc):
        # 150 DPI provides sharp readable text without excessive file size
        pix = page.get_pixmap(dpi=150)
        img_filename = output_dir / f"{idx + 1:03d}.jpg"
        pix.save(str(img_filename))
        saved_count += 1
        if progress_cb and (idx + 1) % 5 == 0:
            progress_cb(f"Конвертація PDF: {idx + 1}/{total_pages} сторінок...")

    doc.close()
    if progress_cb:
        progress_cb(f"Конвертовано всі {total_pages} сторінок.")
    return saved_count


def extract_archive_to_images(archive_path: Path, output_dir: Path) -> int:
    """Extracts image files from ZIP or CBZ archive."""
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    
    with zipfile.ZipFile(archive_path, 'r') as zf:
        members = [m for m in zf.infolist() if not m.is_dir() and Path(m.filename).suffix.lower() in valid_exts]
        # Sort naturally
        members.sort(key=lambda m: m.filename)
        for idx, m in enumerate(members):
            data = zf.read(m)
            out_file = output_dir / f"{idx + 1:03d}{Path(m.filename).suffix.lower()}"
            with open(out_file, "wb") as out_f:
                out_f.write(data)
            count += 1
    return count


class TelegramManhwaDownloader:
    def __init__(self, api_id: int, api_hash: str, session_path: Optional[str] = None, bot_token: Optional[str] = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path or str(Path(__file__).parent / "tg_session")
        self.bot_token = bot_token
        self.client: Optional[TelegramClient] = None

    async def connect(self, code_callback: Optional[Callable[[], str]] = None):
        if self.client and self.client.is_connected():
            return
        
        cfg = load_config()
        b_tok = self.bot_token or cfg.get("tg_bot_token")

        if b_tok:
            bot_sess = str(Path(__file__).parent / "tg_bot_session")
            self.client = TelegramClient(bot_sess, self.api_id, self.api_hash)
            await self.client.start(bot_token=b_tok)
            return

        self.client = TelegramClient(self.session_path, self.api_id, self.api_hash)
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            if sys.stdin is None or not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
                raise RuntimeError("Потрібна авторизація в Telegram! Натисніть кнопку '🔑 Авторизація Telegram' угорі вкладки.")
            phone = input("Введіть номер телефону для Telegram (з +380...): ") if not code_callback else None
            if not phone:
                raise RuntimeError("Telegram authorization needed.")
            await self.client.send_code_request(phone)
            code = input("Введіть код із Telegram: ")
            await self.client.sign_in(phone, code)

    async def search_channel_chapters(
        self,
        channel_name_or_link: str,
        filter_keyword: str = "",
        limit: int = 400,
        status_cb: Optional[Callable[[str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Scans channel for PDF/archive/image manhwa chapters."""
        channel_name = clean_channel_link(channel_name_or_link)
        if status_cb:
            status_cb(f"Пошук у каналі @{channel_name}...")

        await self.connect()
        try:
            entity = await self.client.get_entity(channel_name)
        except Exception as e:
            raise RuntimeError(f"Не вдалося знайти канал '{channel_name}': {e}")

        found_items = []
        kw = filter_keyword.strip().lower()

        # Bot token uses get_messages in batches to bypass BotMethodInvalidError
        is_bot = await self.client.is_bot()
        if is_bot:
            batch_size = 100
            for start_id in range(1, limit + 1, batch_size):
                ids = list(range(start_id, min(start_id + batch_size, limit + 1)))
                msgs = await self.client.get_messages(entity, ids=ids)
                for message in msgs:
                    if not message or not message.media:
                        continue
                    doc_name = ""
                    is_valid_doc = False
                    if isinstance(message.media, MessageMediaDocument) and message.media.document:
                        for attr in message.media.document.attributes:
                            if isinstance(attr, DocumentAttributeFilename):
                                doc_name = attr.file_name
                                break
                        ext = Path(doc_name).suffix.lower()
                        if ext in [".pdf", ".zip", ".cbz", ".cbr", ".rar"]:
                            is_valid_doc = True

                    caption = message.text or ""
                    search_haystack = f"{doc_name} {caption}".lower()
                    if kw and kw not in search_haystack:
                        continue

                    if is_valid_doc:
                        ch_num = extract_chapter_number(doc_name) or extract_chapter_number(caption)
                        found_items.append({
                            "id": message.id,
                            "message": message,
                            "filename": doc_name,
                            "caption": caption[:100],
                            "size_mb": round((message.media.document.size or 0) / (1024 * 1024), 2),
                            "chapter": ch_num if ch_num is not None else -1,
                            "type": "doc"
                        })
        else:
            async for message in self.client.iter_messages(entity, limit=limit):
                if not message.media:
                    continue
                doc_name = ""
                is_valid_doc = False
                if isinstance(message.media, MessageMediaDocument) and message.media.document:
                    for attr in message.media.document.attributes:
                        if isinstance(attr, DocumentAttributeFilename):
                            doc_name = attr.file_name
                            break
                    ext = Path(doc_name).suffix.lower()
                    if ext in [".pdf", ".zip", ".cbz", ".cbr", ".rar"]:
                        is_valid_doc = True

                caption = message.text or ""
                search_haystack = f"{doc_name} {caption}".lower()
                if kw and kw not in search_haystack:
                    continue

                if is_valid_doc:
                    ch_num = extract_chapter_number(doc_name) or extract_chapter_number(caption)
                    found_items.append({
                        "id": message.id,
                        "message": message,
                        "filename": doc_name,
                        "caption": caption[:100],
                        "size_mb": round((message.media.document.size or 0) / (1024 * 1024), 2),
                        "chapter": ch_num if ch_num is not None else -1,
                        "type": "doc"
                    })

        # Sort by chapter number
        found_items.sort(key=lambda x: (x["chapter"] if x["chapter"] != -1 else 999999, x["id"]))
        if status_cb:
            status_cb(f"Знайдено розділів/файлів: {len(found_items)}")
        return found_items

    async def download_chapter(
        self,
        item: Dict[str, Any],
        manhwa_dir: Path,
        keep_raw: bool = False,
        status_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[float], None]] = None
    ) -> Path:
        """Downloads chapter and extracts pages into manhwa_dir/chapter_XXX/."""
        ch_num = item.get("chapter", 1)
        ch_folder_name = f"chapter_{ch_num:03d}" if ch_num > 0 else f"chapter_msg_{item['id']}"
        chapter_dir = manhwa_dir / ch_folder_name
        chapter_dir.mkdir(parents=True, exist_ok=True)

        # Check if already extracted
        existing_imgs = list(chapter_dir.glob("*.jpg")) + list(chapter_dir.glob("*.png"))
        if len(existing_imgs) > 2:
            if status_cb:
                status_cb(f"Глава {ch_num} вже існує ({len(existing_imgs)} сторінок). Пропуск.")
            return chapter_dir

        raw_dir = manhwa_dir / ".temp_downloads"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file_path = raw_dir / item["filename"]

        def telethon_progress(current, total):
            pct = current / total if total > 0 else 0
            if progress_cb:
                progress_cb(pct)

        if status_cb:
            status_cb(f"Завантаження {item['filename']} ({item['size_mb']} MB)...")

        await self.client.download_media(
            item["message"],
            file=str(raw_file_path),
            progress_callback=telethon_progress
        )

        ext = raw_file_path.suffix.lower()
        if status_cb:
            status_cb(f"Розпакування сторінок для Глави {ch_num}...")

        if ext == ".pdf":
            extract_pdf_to_images(raw_file_path, chapter_dir, progress_cb=status_cb)
        elif ext in [".zip", ".cbz"]:
            extract_archive_to_images(raw_file_path, chapter_dir)
        else:
            # Single file or unhandled
            pass

        # Check / set cover image
        cover_path = manhwa_dir / "cover.jpg"
        if not cover_path.exists():
            first_pages = sorted(chapter_dir.glob("*.jpg"))
            if first_pages:
                import shutil
                shutil.copy(first_pages[0], cover_path)

        if not keep_raw and raw_file_path.exists():
            try:
                raw_file_path.unlink()
            except Exception:
                pass

        return chapter_dir

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()


# Quick CLI Interface
if __name__ == "__main__":
    print("=" * 60)
    print("  MANHWA TELEGRAM DOWNLOADER (Standalone)")
    print("=" * 60)

    cfg = load_config()
    api_id = cfg.get("tg_api_id", 37560778)
    api_hash = cfg.get("tg_api_hash", "307da2f94fc6450afe139c91bcc59eaa")
    lib_dir = Path(__file__).parent / cfg.get("library_path", "library")
    lib_dir.mkdir(parents=True, exist_ok=True)

    channel_input = input("Введіть посилання або юзернейм каналу (напр. @Manhwa_Weebs): ").strip()
    if not channel_input:
        channel_input = "Manhwa_Weebs"

    search_kw = input("Ключове слово для пошуку (напр. Baskerville / Revenge або Enter для всіх): ").strip()
    title_name = input("Як назвати папку з манхвою у бібліотеці: ").strip()
    if not title_name:
        title_name = search_kw or "Manhwa_Download"

    target_manhwa_dir = lib_dir / title_name

    downloader = TelegramManhwaDownloader(api_id, api_hash)

    async def run():
        def log(msg):
            print(f"[TG] {msg}")

        await downloader.connect()
        items = await downloader.search_channel_chapters(channel_input, filter_keyword=search_kw, status_cb=log)
        
        if not items:
            print("Нічого не знайдено.")
            return

        print(f"\nЗнайдено {len(items)} розділів.")
        start_ans = input(f"Завантажити всі {len(items)} розділів? (Y/n): ").strip().lower()
        if start_ans in ["n", "no"]:
            return

        for idx, itm in enumerate(items):
            print(f"\n--- [{idx + 1}/{len(items)}] Глава {itm['chapter']} ({itm['filename']}) ---")
            await downloader.download_chapter(
                itm,
                target_manhwa_dir,
                keep_raw=False,
                status_cb=log,
                progress_cb=lambda p: print(f"\rПрогрес: {int(p * 100)}%", end="", flush=True)
            )

        print(f"\nУспішно завантажено в: {target_manhwa_dir}")
        await downloader.disconnect()

    asyncio.run(run())
