"""
Cloud Stream & In-Memory Reading Engine for Manhwa Reader.
Enables streaming manhwa chapters directly from Telegram channels into RAM
using PyMuPDF (fitz.open stream) without saving gigabytes of files to disk.
Implements Rolling RAM Cache (prefetching ch+1 at 80% scroll, evicting ch-1).
"""

import io
import gc
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

try:
    from telethon import TelegramClient
    from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename
    from telethon.sessions import MemorySession
except ImportError:
    TelegramClient = None

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

import sys

if getattr(sys, "frozen", False):
    _APP_ROOT = Path(sys.executable).parent.resolve()
else:
    _APP_ROOT = Path(__file__).parent.resolve()

CONFIG_FILE = _APP_ROOT / "config.json"
CLOUD_INDEX_FILE = _APP_ROOT / "cloud_index.json"

# Embedded baseline catalog fallback so the app always displays titles even on fresh machine
DEFAULT_EMBEDDED_INDEX: dict = {
  "vault_channel_id": -1004386061072,
  "vault_channel_title": "Manhwa Vault",
  "pinned_catalog_msg_id": 6,
  "titles": {
    "RI-BH": {
      "title_code": "RI-BH",
      "title_name": "Revenge of the Iron-Blooded Hound",
      "lang": "EN",
      "total_chapters": 3,
      "aliases": [
        "Помста залізно-кровного хорта",
        "Revenge of the Iron-Blooded Sword Hound",
        "Iron-Blooded Hound",
        "Месть железнокровного пса"
      ],
      "linked_translations": [
        {
          "lang": "UA",
          "title": "Помста залізно-кровного хорта",
          "type": "local",
          "target": "Revenge of the Iron-Blooded Sword Hound"
        },
        {
          "lang": "EN",
          "title": "Revenge of the Iron-Blooded Hound",
          "type": "cloud",
          "target": "RI-BH"
        }
      ],
      "chapters": {
        "1": {
          "chapter_num": 1,
          "filename": "[RI-BH] 001 (Revenge of the Iron-Blooded Hound) [EN].pdf",
          "size_mb": 9.0,
          "vault_msg_id": 3
        },
        "2": {
          "chapter_num": 2,
          "filename": "[RI-BH] 002 (Revenge of the Iron-Blooded Hound) [EN].pdf",
          "size_mb": 8.98,
          "vault_msg_id": 4
        },
        "3": {
          "chapter_num": 3,
          "filename": "[RI-BH] 003 (Revenge of the Iron-Blooded Hound) [EN].pdf",
          "size_mb": 9.1,
          "vault_msg_id": 5
        }
      }
    }
  }
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_cloud_index() -> dict:
    # 1. Try local file next to exe / script
    if CLOUD_INDEX_FILE.exists():
        try:
            with open(CLOUD_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "titles" in data:
                    return data
        except Exception:
            pass

    # 2. Try MEIPASS if PyInstaller bundled it
    if hasattr(sys, "_MEIPASS"):
        bundled_index = Path(sys._MEIPASS) / "cloud_index.json"
        if bundled_index.exists():
            try:
                with open(bundled_index, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and "titles" in data:
                        return data
            except Exception:
                pass

    # 3. Try directory of this module
    mod_index = Path(__file__).parent / "cloud_index.json"
    if mod_index.exists():
        try:
            with open(mod_index, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "titles" in data:
                    return data
        except Exception:
            pass

    # 4. Fallback to embedded baseline catalog
    return DEFAULT_EMBEDDED_INDEX.copy()


def save_cloud_index(data: dict):
    try:
        with open(CLOUD_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CloudStream] Failed to save cloud index: {e}")


class CloudChapterInfo:
    def __init__(self, title: str, chapter_num: int, message_id: int, filename: str, size_mb: float):
        self.title = title
        self.chapter_num = chapter_num
        self.message_id = message_id
        self.filename = filename
        self.size_mb = size_mb

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "chapter_num": self.chapter_num,
            "message_id": self.message_id,
            "filename": self.filename,
            "size_mb": self.size_mb
        }


SESSION_PATH = Path(__file__).parent / "tg_cloud_relay_session"


import threading

class TelegramStreamClient:
    """Manages bot connection to Telegram for in-memory streaming on a single persistent background loop."""

    def __init__(self, api_id: int = 37560778, api_hash: str = "307da2f94fc6450afe139c91bcc59eaa", bot_token: str = ""):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token or load_config().get("tg_bot_token", "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA")
        self.client: Optional[TelegramClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def _start_loop_thread(self):
        if self._thread and self._thread.is_alive():
            return
        ready_evt = threading.Event()

        def _loop_worker():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            ready_evt.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_loop_worker, daemon=True, name="TgStreamLoopThread")
        self._thread.start()
        ready_evt.wait(2.0)

    def run_coro(self, coro):
        """Runs a coroutine on the dedicated stream client event loop."""
        if not self._loop or not self._loop.is_running():
            self._start_loop_thread()
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()

    async def _ensure_connected_coro(self):
        if self.client and self.client.is_connected():
            return
        if not TelegramClient:
            raise RuntimeError("Telethon не встановлено в системі.")

        self.client = TelegramClient(MemorySession(), self.api_id, self.api_hash)
        await self.client.start(bot_token=self.bot_token)

    async def _fetch_stream_coro(self, channel_entity: Any, message_id: int, progress_cb: Optional[Callable[[float, int, int], None]] = None) -> bytes:
        await self._ensure_connected_coro()

        # Handle string channel ID format e.g. "-1004386061072"
        if isinstance(channel_entity, str):
            try:
                channel_entity = int(channel_entity)
            except Exception:
                pass

        entity = await self.client.get_entity(channel_entity)
        msg = await self.client.get_messages(entity, ids=message_id)
        if not msg or not msg.media:
            raise RuntimeError(f"Повідомлення #{message_id} не містить файлу.")

        ram_buffer = io.BytesIO()

        def _prog(cur, tot):
            if progress_cb:
                pct = cur / tot if tot > 0 else 0
                progress_cb(pct, cur, tot)

        await self.client.download_media(msg, file=ram_buffer, progress_callback=_prog)
        data = ram_buffer.getvalue()
        ram_buffer.close()
        return data

    def fetch_message_stream_sync(self, channel_entity: Any, message_id: int, progress_cb: Optional[Callable[[float, int, int], None]] = None) -> bytes:
        """Downloads document bytes directly into RAM without touching the disk, on the persistent loop."""
        return self.run_coro(self._fetch_stream_coro(channel_entity, message_id, progress_cb))

    def disconnect(self):
        if self.client and self._loop and self._loop.is_running():
            try:
                self.run_coro(self.client.disconnect())
            except Exception:
                pass
            self.client = None


class StreamDownloadThread(QThread):
    """Background worker to download chapter bytes into RAM."""
    finished_signal = pyqtSignal(int, bytes)              # chapter_num, bytes
    progress_signal = pyqtSignal(int, float, int, int)    # chapter_num, pct (0.0 to 1.0), cur, tot
    error_signal = pyqtSignal(int, str)                   # chapter_num, error_msg

    def __init__(self, stream_client: TelegramStreamClient, channel_target: Any, chapter_num: int, message_id: int):
        super().__init__()
        self.stream_client = stream_client
        self.channel_target = channel_target
        self.chapter_num = chapter_num
        self.message_id = message_id
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def on_progress(p: float, cur: int, tot: int):
                if not self._is_cancelled:
                    self.progress_signal.emit(self.chapter_num, p, cur, tot)

            data = self.stream_client.fetch_message_stream_sync(
                self.channel_target, self.message_id, on_progress
            )
            if not self._is_cancelled:
                self.finished_signal.emit(self.chapter_num, data)
        except Exception as e:
            if not self._is_cancelled:
                self.error_signal.emit(self.chapter_num, str(e))



class RollingRAMCache(QObject):
    """
    Manages in-memory rendered pages with automatic sliding window eviction.
    Maintains [current_chapter] and preloads [next_chapter], discarding old ones.
    """
    chapter_rendered_signal = pyqtSignal(int, list)  # chapter_num, list of (pixmap, cache_key)
    preload_finished_signal = pyqtSignal(int)
    preload_failed_signal = pyqtSignal(int, str)

    def __init__(self, stream_client: TelegramStreamClient, channel_target: Any, max_cached_chapters: int = 3):
        super().__init__()
        self.stream_client = stream_client
        self.channel_target = channel_target
        self.max_cached_chapters = max(2, max_cached_chapters)

        # Map: chapter_num -> list of QPixmap
        self.rendered_pages: Dict[int, List[Tuple[QPixmap, str]]] = {}
        # Map: chapter_num -> raw bytes (cached temporarily)
        self.raw_stream_cache: Dict[int, bytes] = {}

        self.current_chapter: int = 1
        self.chapter_msg_map: Dict[int, int] = {}  # chapter_num -> message_id

        self.active_workers: Dict[int, StreamDownloadThread] = {}

    def _enforce_cache_limits(self):
        """Enforces max_cached_chapters to prevent unbounded RAM usage."""
        if len(self.rendered_pages) > self.max_cached_chapters:
            # Keep current_chapter, current_chapter + 1, current_chapter - 1 prioritized
            preferred = {self.current_chapter, self.current_chapter + 1, self.current_chapter - 1}
            candidates = [c for c in self.rendered_pages.keys() if c not in preferred]
            # If all are in preferred (e.g. max_cached_chapters == 2), evict the farthest from current
            if not candidates:
                candidates = sorted(self.rendered_pages.keys(), key=lambda c: abs(c - self.current_chapter), reverse=True)
            for c in candidates:
                if len(self.rendered_pages) <= self.max_cached_chapters:
                    break
                self.evict_chapter(c)


    def set_chapter_map(self, ch_map: Dict[int, int]):
        self.chapter_msg_map = dict(ch_map)

    def render_pdf_stream(self, ch_num: int, pdf_bytes: bytes, target_w: int = 800, dpi: int = 150) -> List[Tuple[QPixmap, str]]:
        """Converts raw PDF bytes into a list of QPixmap objects directly in RAM."""
        if not fitz:
            raise RuntimeError("PyMuPDF is required for streaming PDF rendering.")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_list = []

        for idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            pm = QPixmap.fromImage(qimg.copy())

            cache_key = f"cloud_stream_ch{ch_num:03d}_p{idx:03d}"
            page_list.append((pm, cache_key))

        doc.close()
        self.rendered_pages[ch_num] = page_list
        self._enforce_cache_limits()
        return page_list

    def request_preload(self, ch_num: int):
        """Asynchronously preloads chapter into RAM if not already cached."""
        if ch_num in self.rendered_pages or ch_num in self.active_workers:
            return
        msg_id = self.chapter_msg_map.get(ch_num)
        if not msg_id:
            return

        worker = StreamDownloadThread(self.stream_client, self.channel_target, ch_num, msg_id)
        worker.finished_signal.connect(self._on_preload_downloaded)
        worker.error_signal.connect(self._on_preload_error)
        self.active_workers[ch_num] = worker
        worker.start()

    def _on_preload_downloaded(self, ch_num: int, data: bytes):
        if ch_num in self.active_workers:
            del self.active_workers[ch_num]
        self.raw_stream_cache[ch_num] = data
        try:
            self.render_pdf_stream(ch_num, data)
            self.preload_finished_signal.emit(ch_num)
        except Exception as e:
            self.preload_failed_signal.emit(ch_num, str(e))

    def _on_preload_error(self, ch_num: int, err: str):
        if ch_num in self.active_workers:
            del self.active_workers[ch_num]
        self.preload_failed_signal.emit(ch_num, err)

    def on_scroll_threshold_reached(self, current_ch: int, progress: float):
        """
        When scroll reaches 80% (4/5), trigger preloading for next chapter.
        When moving past 20% (1/5) in new chapter, evict older chapters.
        """
        self.current_chapter = current_ch

        # 1. Preload Next Chapter at 80%
        if progress >= 0.80:
            next_ch = current_ch + 1
            if next_ch in self.chapter_msg_map and next_ch not in self.rendered_pages:
                self.request_preload(next_ch)

        # 2. Evict Old Chapters (keep only current_ch, current_ch + 1)
        if progress >= 0.20:
            keep_chapters = {current_ch, current_ch + 1, current_ch - 1}
            to_remove = [c for c in self.rendered_pages if c not in keep_chapters]
            for c in to_remove:
                self.evict_chapter(c)

    def evict_chapter(self, ch_num: int):
        """Releases all pixmaps and raw byte buffers of chapter from RAM."""
        if ch_num in self.rendered_pages:
            self.rendered_pages[ch_num].clear()
            del self.rendered_pages[ch_num]
        if ch_num in self.raw_stream_cache:
            del self.raw_stream_cache[ch_num]
        gc.collect()

    def clear_all(self):
        """Evicts everything from RAM cache."""
        for worker in self.active_workers.values():
            try:
                worker.terminate()
            except Exception:
                pass
        self.active_workers.clear()
        self.rendered_pages.clear()
        self.raw_stream_cache.clear()
        gc.collect()
