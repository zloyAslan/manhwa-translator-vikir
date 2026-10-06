"""
MANHWA READER — AI DRAFTER STYLE
Modern Webtoon Player & Telegram Downloader:
- Seamless vertical scroll (Webtoon strip, zero gaps/lines)
- Zen Reading Mode: Hide/Show top headers with 'H' hotkey or button
- Smooth lag-free zoom (debounced + pixmap memory cache)
- Multilingual support: Ukrainian (UA) and English (EN)
- Scrollable high-contrast Downloader with Telegram Auth Dialog
- Smart Chapter Range Filter (e.g. '2', '1 2', '1-30')
"""

import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import re
import json
import asyncio
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect, QRectF
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QIcon, QKeySequence,
    QLinearGradient, QRadialGradient, QBrush, QCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QComboBox, QLineEdit,
    QProgressBar, QTextEdit, QDialog, QFrame, QSizePolicy, QStackedWidget,
    QCheckBox
)

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from downloader import TelegramManhwaDownloader, extract_chapter_number, clean_channel_link

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_LIB_DIR = BASE_DIR / "library"


# ---------------------------------------------------------------------------
# Multilingual Translations
# ---------------------------------------------------------------------------
TRANSLATIONS = {
    "uk": {
        "app_title": "Manhwa Reader AI Drafter",
        "tab_catalog": "📚 Каталог",
        "tab_reader": "📖 Читати",
        "tab_downloader": "⚡ Завантажувач TG",
        "tab_settings": "⚙️ Налаштування",
        "badge_engine": "🚀 STANDALONE WEBTOON ENGINE",
        "subtitle": "Автономний вебтун-плеєр, автозакладки та швидкий завантажувач із Telegram",
        "fs_on": "⛶ На весь екран (F11)",
        "fs_off": "🗗 Згорнути (F11)",
        "hide_menu": "👁 Приховати меню (H)",
        "show_menu": "👁 Показати меню (H)",
        "to_catalog": "← До каталогу",
        "lib_title": "Твоя бібліотека",
        "refresh": "🔄 Оновити",
        "add_tg": "+ Завантажити нову з TG",
        "empty_lib": "📂 У бібліотеці поки порожньо.\nПерейдіть у вкладку '⚡ Завантажувач TG', щоб додати манхву!",
        "read_btn": "▶ Читати",
        "del_tooltip": "Видалити манхву",
        "del_confirm_title": "Видалити манхву",
        "del_confirm_msg": "Ви дійсно хочете видалити манхву:\n«{title}» ?",
        "del_confirm_sub": "Усі викачані глави, файли та закладка будуть повністю видалені з диска.",
        "cancel": "Скасувати",
        "del_btn_action": "🗑️ Так, видалити",
        "select_manhwa": "Оберіть манхву",
        "prev_ch": "◀ Попередня",
        "next_ch": "Наступна ▶",
        "width_lbl": "Ширина:",
        "zoom_lbl": "Зум:",
        "theme_lbl": "Фон:",
        "dl_title": "⚡ Завантажувач PDF-глав із Telegram",
        "dl_info_title": "📌 Як працює завантажувач:",
        "dl_info_desc": "Вкажіть посилання на відкритий канал (наприклад, https://t.me/channel_name) або юзернейм (@channel_name). Програма знайде PDF-документи та збереже їх у галерею манхви.",
        "dl_channel": "Канал (URL або @тег):",
        "dl_search": "Пошукове слово (фільтр):",
        "dl_range": "Номер або діапазон (напр. 2 або 1-30):",
        "dl_name": "Назва тайтлу в бібліотеці:",
        "dl_start": "🚀 Почати завантаження",
        "settings_title": "⚙️ Налаштування програми",
        "lang_lbl": "Мова інтерфейсу:",
        "del_pdf_lbl": "Автоматично видаляти вихідний PDF після конвертації (економія пам'яті):",
        "speed_lbl": "Швидкість скролу клавішами:",
        "save_btn": "💾 Зберегти налаштування",
        "saved_msg": "Налаштування успішно збережено!",
        "auth_btn": "🤖 Налаштувати Токен Бота",
        "auth_ok": "🟢 Telegram Бот підключено",
        "auth_needed": "🟡 Потрібен токен бота Telegram"
    },
    "en": {
        "app_title": "Manhwa Reader AI Drafter",
        "tab_catalog": "📚 Library",
        "tab_reader": "📖 Reader",
        "tab_downloader": "⚡ TG Downloader",
        "tab_settings": "⚙️ Settings",
        "badge_engine": "🚀 STANDALONE WEBTOON ENGINE",
        "subtitle": "Standalone webtoon player, auto-bookmarks & Telegram fast downloader",
        "fs_on": "⛶ Fullscreen (F11)",
        "fs_off": "🗗 Windowed (F11)",
        "hide_menu": "👁 Hide Menu (H)",
        "show_menu": "👁 Show Menu (H)",
        "to_catalog": "← Back to Library",
        "lib_title": "Your Library",
        "refresh": "🔄 Refresh",
        "add_tg": "+ Download from TG",
        "empty_lib": "📂 Your library is currently empty.\nGo to '⚡ TG Downloader' to fetch manhwa!",
        "read_btn": "▶ Read",
        "del_tooltip": "Delete manhwa",
        "del_confirm_title": "Delete Manhwa",
        "del_confirm_msg": "Are you sure you want to delete:\n«{title}» ?",
        "del_confirm_sub": "All downloaded chapters, files and bookmarks will be wiped from disk.",
        "cancel": "Cancel",
        "del_btn_action": "🗑️ Yes, Delete",
        "select_manhwa": "Select a manhwa",
        "prev_ch": "◀ Prev",
        "next_ch": "Next ▶",
        "width_lbl": "Width:",
        "zoom_lbl": "Zoom:",
        "theme_lbl": "Theme:",
        "dl_title": "⚡ Telegram PDF Chapter Downloader",
        "dl_info_title": "📌 How the downloader works:",
        "dl_info_desc": "Provide channel URL (e.g. https://t.me/channel_name) or tag (@channel_name). The engine discovers PDF chapters and turns them into seamless strips.",
        "dl_channel": "Channel (URL or @tag):",
        "dl_search": "Filter title / keyword:",
        "dl_range": "Chapter or range (e.g. 2 or 1-30):",
        "dl_name": "Target title folder name:",
        "dl_start": "🚀 Start Download",
        "settings_title": "⚙️ Application Settings",
        "lang_lbl": "UI Language:",
        "del_pdf_lbl": "Auto-delete original PDF after extracting pages (saves disk space):",
        "speed_lbl": "Keyboard scroll speed:",
        "save_btn": "💾 Save Settings",
        "saved_msg": "Settings saved successfully!",
        "auth_btn": "🔑 Telegram Login",
        "auth_ok": "🟢 Telegram Authorized",
        "auth_needed": "🟡 One-time Telegram login needed"
    }
}


def load_config() -> dict:
    default_cfg = {
        "library_path": "library",
        "reading_width": 880,
        "bg_color": "#0f1115",
        "zoom": 1.0,
        "fullscreen": False,
        "scroll_speed": 75,
        "auto_preload_threshold": 0.67,
        "language": "uk",
        "delete_pdf_after_extract": True,
        "tg_api_id": 37560778,
        "tg_api_hash": "307da2f94fc6450afe139c91bcc59eaa",
        "tg_bot_token": "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA",
        "bookmarks": {}
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


def parse_chapter_filter(range_str: str) -> Optional[Set[int]]:
    """Intelligently parses user input like '2', '1-2', '1 2', '1, 2', '1-30'."""
    s = range_str.strip()
    if not s:
        return None

    # Check range with dash or 'to'
    m = re.match(r'^(\d+)\s*[-:.to]+\s*(\d+)$', s, re.IGNORECASE)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        if low > high:
            low, high = high, low
        return set(range(low, high + 1))

    # Check standalone or whitespace/comma separated numbers
    nums = re.findall(r'\d+', s)
    if nums:
        return set(int(n) for n in nums)

    return None


# ---------------------------------------------------------------------------
# High-Contrast Stylesheet
# ---------------------------------------------------------------------------
STYLESHEET = """
QWidget {
    color: #f3f4f6;
    font-family: 'Segoe UI', 'Plus Jakarta Sans', sans-serif;
    outline: none;
}

QMainWindow, #mainCentralWidget {
    background-color: #0f1115;
}

.cardPane {
    background-color: rgba(22, 26, 36, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}

#navBar {
    background-color: rgba(13, 16, 26, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 6px;
}

QPushButton.navTab {
    background-color: transparent;
    color: #9ca3af;
    border: none;
    border-radius: 9px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton.navTab:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.08);
}
QPushButton.navTab:checked, QPushButton.navTab.activeTab {
    color: #121008;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
    font-weight: 700;
}

QPushButton.btnAccent {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
    color: #110d04;
    font-weight: 700;
    font-size: 14px;
    border-radius: 10px;
    padding: 10px 18px;
    border: none;
}
QPushButton.btnAccent:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fcd34d, stop:1 #f59e0b);
}

QPushButton.btnSecondary {
    background-color: #1f2433;
    color: #f3f4f6;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    padding: 8px 14px;
}
QPushButton.btnSecondary:hover {
    background-color: #2c3348;
    color: #ffffff;
}

/* Explicit High-Contrast Form Inputs */
QLineEdit {
    background-color: #151924;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 9px;
    padding: 9px 14px;
    color: #ffffff;
    font-size: 14px;
    font-weight: 500;
}
QLineEdit:focus {
    border: 1px solid #fbbf24;
    background-color: #1a202e;
}

QLabel {
    color: #e5e7eb;
    font-size: 13px;
    font-weight: 600;
}

QComboBox {
    background-color: #181c28;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 9px;
    padding: 6px 12px;
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
}
QComboBox:hover {
    border-color: rgba(251, 191, 36, 0.5);
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #181c28;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 8px;
    color: #f3f4f6;
    selection-background-color: #d97706;
    selection-color: #121008;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #d97706;
    color: #121008;
    font-weight: 700;
}

QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #3b82f6);
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #fbbf24;
    border: 2px solid #ffffff;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

QScrollBar:vertical {
    border: none;
    background: #0f1115;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.22);
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #d97706;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# ---------------------------------------------------------------------------
# Ambient Radial Glow Background Widget
# ---------------------------------------------------------------------------
class AmbientBackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f1115"))

        w = float(self.width())
        h = float(self.height())

        top_glow = QRadialGradient(w * 0.12, h * 0.15, w * 0.45)
        top_glow.setColorAt(0.0, QColor(245, 158, 11, 20))
        top_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), QBrush(top_glow))

        bottom_glow = QRadialGradient(w * 0.88, h * 0.75, w * 0.50)
        bottom_glow.setColorAt(0.0, QColor(37, 99, 235, 20))
        bottom_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), QBrush(bottom_glow))

        stripe = QLinearGradient(0.0, 0.0, w, 0.0)
        stripe.setColorAt(0.0, QColor("#d97706"))
        stripe.setColorAt(0.5, QColor("#2563eb"))
        stripe.setColorAt(1.0, QColor("#0d9488"))
        painter.fillRect(QRectF(0.0, 0.0, w, 3.0), QBrush(stripe))
        painter.end()


# ---------------------------------------------------------------------------
# Custom Dark Confirmation Dialog
# ---------------------------------------------------------------------------
class ConfirmDeleteDialog(QDialog):
    def __init__(self, title: str, manhwa_name: str, lang_dict: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(lang_dict["del_confirm_title"])
        self.setFixedSize(440, 240)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #141722;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)

        header_lbl = QLabel(f"🗑️  {title}")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #f87171;")
        layout.addWidget(header_lbl)

        msg_lbl = QLabel(lang_dict["del_confirm_msg"].format(title=manhwa_name))
        msg_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #f3f4f6;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        sub_lbl = QLabel(lang_dict["del_confirm_sub"])
        sub_lbl.setStyleSheet("font-size: 12px; color: #9ca3af;")
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton(lang_dict["cancel"])
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            background-color: #212636;
            color: #e5e7eb;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 10px;
            padding: 10px 18px;
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        del_btn = QPushButton(lang_dict["del_btn_action"])
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setStyleSheet("""
            background-color: #dc2626;
            color: #ffffff;
            font-weight: 700;
            font-size: 13px;
            border: none;
            border-radius: 10px;
            padding: 10px 18px;
        """)
        del_btn.clicked.connect(self.accept)
        btn_layout.addWidget(del_btn)

        layout.addLayout(btn_layout)


# ---------------------------------------------------------------------------
# Telegram Bot Token Dialog (No phone numbers, SMS or 2FA needed!)
# ---------------------------------------------------------------------------
class TelegramBotTokenDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Налаштування Telegram Бота")
        self.setFixedSize(520, 310)
        self.setStyleSheet("""
            QDialog {
                background-color: #141722;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("🤖 Токен Telegram Бота для завантаження")
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #fbbf24;")
        layout.addWidget(title)

        info = QLabel(
            "Бот дозволяє завантажувати глави без телефонів, SMS та паролів 2FA.\n"
            "Вставте сюди токен вашого бота з @BotFather. Він збережеться в config.json."
        )
        info.setStyleSheet("color: #9ca3af; font-size: 12px; line-height: 1.4;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("API Токен Бота:"))
        self.token_inp = QLineEdit(self.cfg.get("tg_bot_token", ""))
        self.token_inp.setPlaceholderText("Наприклад: 8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA")
        self.token_inp.setStyleSheet("""
            QLineEdit {
                background-color: #0b0d13;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #fbbf24;
            }
        """)
        layout.addWidget(self.token_inp)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #34d399;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.setProperty("class", "btnSecondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Зберегти токен")
        save_btn.setProperty("class", "btnAccent")
        save_btn.clicked.connect(self.save_token)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def save_token(self):
        tok = self.token_inp.text().strip()
        self.cfg["tg_bot_token"] = tok
        save_config(self.cfg)
        self.status_lbl.setText("Токен успішно збережено в config.json!")
        QTimer.singleShot(600, self.accept)


# ---------------------------------------------------------------------------
# Telegram Downloader Worker Thread
# ---------------------------------------------------------------------------
class DownloadWorker(QThread):
    progress_signal = pyqtSignal(float)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    need_auth_signal = pyqtSignal()

    def __init__(self, api_id: int, api_hash: str, channel: str, search_kw: str, range_str: str, title: str, lib_dir: Path, del_pdf: bool):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.channel = clean_channel_link(channel)
        self.search_kw = search_kw
        self.range_str = range_str.strip()
        self.title = title
        self.lib_dir = lib_dir
        self.del_pdf = del_pdf

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._download_coro())
            self.finished_signal.emit(True, f"Завантаження манхви «{self.title}» успішно завершено!")
        except Exception as e:
            self.finished_signal.emit(False, str(e))
        finally:
            loop.close()

    async def _download_coro(self):
        cfg = load_config()
        bot_tok = cfg.get("tg_bot_token")
        downloader = TelegramManhwaDownloader(self.api_id, self.api_hash, bot_token=bot_tok)
        self.status_signal.emit("Підключення до сервісу Telegram через Бота...")

        await downloader.connect()

        self.status_signal.emit(f"Пошук PDF-глав у каналі @{self.channel}...")
        items = await downloader.search_channel_chapters(
            self.channel,
            filter_keyword=self.search_kw,
            status_cb=lambda s: self.status_signal.emit(s)
        )

        if not items:
            raise RuntimeError("У каналі не знайдено PDF-файлів або документів.")

        # Smart filter by user input
        allowed_chapters = parse_chapter_filter(self.range_str)
        filtered = []
        for it in items:
            ch_num = it.get("chapter", -1)
            if allowed_chapters is None:
                filtered.append(it)
            elif ch_num in allowed_chapters:
                filtered.append(it)

        if not filtered:
            raise RuntimeError(f"Жодна глава не відповідає фільтру '{self.range_str}'. Знайдені глави: {[x.get('chapter') for x in items[:10]]}")

        target_dir = self.lib_dir / self.title
        total = len(filtered)
        self.status_signal.emit(f"Буде завантажено глав: {total}. Розпочинаємо...")

        for idx, item in enumerate(filtered):
            ch_num = item.get("chapter", idx + 1)
            self.status_signal.emit(f"[{idx + 1}/{total}] Глава {ch_num}: {item['filename']}")

            def sub_prog(p):
                overall = (idx + p) / total
                self.progress_signal.emit(overall)

            await downloader.download_chapter(
                item,
                target_dir,
                keep_raw=not self.del_pdf,
                status_cb=lambda s: self.status_signal.emit(s),
                progress_cb=sub_prog
            )
            self.progress_signal.emit((idx + 1) / total)

        await downloader.disconnect()


# ---------------------------------------------------------------------------
# Manhwa Card in Catalog
# ---------------------------------------------------------------------------
class ManhwaCard(QFrame):
    read_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)

    def __init__(self, manhwa_name: str, manhwa_path: Path, bookmark_info: dict, lang_dict: dict, parent=None):
        super().__init__(parent)
        self.manhwa_name = manhwa_name
        self.manhwa_path = manhwa_path
        self.bookmark_info = bookmark_info
        self.lang_dict = lang_dict

        self.setObjectName("manhwaCard")
        self.setStyleSheet("""
            #manhwaCard {
                background-color: rgba(22, 26, 36, 0.94);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 16px;
            }
            #manhwaCard:hover {
                border: 1px solid rgba(217, 119, 6, 0.60);
                background-color: rgba(28, 33, 46, 0.98);
            }
        """)
        self.setFixedSize(260, 400)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.cover_lbl = QLabel()
        self.cover_lbl.setFixedHeight(230)
        self.cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_lbl.setStyleSheet("""
            background-color: #0c0e14;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        """)
        self.load_cover()
        layout.addWidget(self.cover_lbl)

        title_lbl = QLabel(self.manhwa_name)
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f3f4f6;")
        title_lbl.setWordWrap(True)
        title_lbl.setFixedHeight(42)
        layout.addWidget(title_lbl)

        ch_count = self.get_chapter_count()
        bm_text = "New" if self.lang_dict.get("cancel") == "Cancel" else "Нова"
        if self.bookmark_info:
            ch_num = self.bookmark_info.get("chapter", 1)
            pct = int(self.bookmark_info.get("chapter_progress", 0) * 100)
            bm_text = f"Ch. {ch_num} ({pct}%)"

        info_lbl = QLabel(f"📁 {ch_count}  •  🔖 {bm_text}")
        info_lbl.setStyleSheet("font-size: 12px; color: #9ca3af; font-weight: 500;")
        layout.addWidget(info_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        read_btn = QPushButton(self.lang_dict["read_btn"])
        read_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        read_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
                color: #121008;
                font-size: 14px;
                font-weight: 800;
                border-radius: 10px;
                padding: 10px 14px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fcd34d, stop:1 #f59e0b);
            }
        """)
        read_btn.clicked.connect(lambda: self.read_clicked.emit(self.manhwa_name))
        btn_row.addWidget(read_btn, 4)

        del_btn = QPushButton("🗑️")
        del_btn.setToolTip(self.lang_dict["del_tooltip"])
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.16);
                color: #f87171;
                font-size: 15px;
                font-weight: 700;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 10px;
                padding: 8px 10px;
            }
            QPushButton:hover {
                background-color: rgba(220, 38, 38, 0.35);
                color: #ffffff;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.manhwa_name))
        btn_row.addWidget(del_btn, 1)

        layout.addLayout(btn_row)

    def get_chapter_count(self) -> int:
        if not self.manhwa_path.exists():
            return 0
        dirs = [p for p in self.manhwa_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
        pdfs = [p for p in self.manhwa_path.glob("*.pdf")]
        return max(len(dirs), len(pdfs))

    def load_cover(self):
        cover_path = self.manhwa_path / "cover.jpg"
        if not cover_path.exists():
            for img in self.manhwa_path.glob("**/*.jpg"):
                cover_path = img
                break

        if cover_path and cover_path.exists():
            pm = QPixmap(str(cover_path))
            if not pm.isNull():
                scaled = pm.scaled(232, 230, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                rect = QRect((scaled.width() - 232) // 2, (scaled.height() - 230) // 2, 232, 230)
                self.cover_lbl.setPixmap(scaled.copy(rect))
                return

        self.cover_lbl.setText("📖\nCover")


# ---------------------------------------------------------------------------
# Seamless Continuous Webtoon Strip
# ---------------------------------------------------------------------------
class WebtoonScrollCanvas(QScrollArea):
    scroll_progress_signal = pyqtSignal(int, float)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.reading_width = cfg.get("reading_width", 880)
        self.zoom = cfg.get("zoom", 1.0)
        self.bg_color = cfg.get("bg_color", "#0f1115")

        self.current_manhwa_name = ""
        self.current_manhwa_path: Optional[Path] = None
        self.loaded_chapters: Dict[int, List[Path]] = {}
        self.page_labels: List[Tuple[int, QLabel, str]] = []
        self.pixmap_cache: Dict[str, QPixmap] = {}

        self.active_ch_num = 1
        self.is_restoring_scroll = False

        self.scale_timer = QTimer(self)
        self.scale_timer.setSingleShot(True)
        self.scale_timer.setInterval(80)
        self.scale_timer.timeout.connect(self._do_rescale)

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(f"QScrollArea {{ background-color: {self.bg_color}; border: none; }}")

        self.container = QWidget()
        self.container.setStyleSheet(f"background-color: {self.bg_color};")
        self.main_layout = QHBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.strip_widget = QWidget()
        self.strip_widget.setStyleSheet(f"background-color: {self.bg_color};")
        self.strip_layout = QVBoxLayout(self.strip_widget)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(0)

        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.strip_widget)
        self.main_layout.addStretch(1)

        self.setWidget(self.container)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def set_reading_width(self, width: int):
        self.reading_width = width
        self.scale_timer.start()

    def set_zoom(self, zoom: float):
        self.zoom = max(0.5, min(2.5, zoom))
        self.scale_timer.start()

    def set_bg_color(self, hex_color: str):
        self.bg_color = hex_color
        self.setStyleSheet(f"QScrollArea {{ background-color: {self.bg_color}; border: none; }}")
        self.container.setStyleSheet(f"background-color: {self.bg_color};")
        self.strip_widget.setStyleSheet(f"background-color: {self.bg_color};")

    def ensure_chapter_images(self, ch_num: int) -> List[Path]:
        if not self.current_manhwa_path:
            return []

        target_dir = None
        for p in self.current_manhwa_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                if extract_chapter_number(p.name) == ch_num:
                    target_dir = p
                    break

        if not target_dir:
            for pdf_p in self.current_manhwa_path.glob("*.pdf"):
                if extract_chapter_number(pdf_p.stem) == ch_num:
                    target_dir = self.current_manhwa_path / f"chapter_{ch_num:03d}"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    self._extract_pdf(pdf_p, target_dir)
                    if self.cfg.get("delete_pdf_after_extract", True):
                        pdf_p.unlink(missing_ok=True)
                    break

        if not target_dir or not target_dir.exists():
            return []

        imgs = sorted(
            list(target_dir.glob("*.jpg")) + list(target_dir.glob("*.png")) + list(target_dir.glob("*.webp")),
            key=lambda p: p.name
        )

        if len(imgs) == 0:
            for pdf_f in target_dir.glob("*.pdf"):
                self._extract_pdf(pdf_f, target_dir)
                if self.cfg.get("delete_pdf_after_extract", True):
                    pdf_f.unlink(missing_ok=True)
                imgs = sorted(
                    list(target_dir.glob("*.jpg")) + list(target_dir.glob("*.png")),
                    key=lambda p: p.name
                )
                break

        return imgs

    def _extract_pdf(self, pdf_file: Path, out_dir: Path):
        if not fitz:
            return
        try:
            doc = fitz.open(str(pdf_file))
            for idx, page in enumerate(doc):
                pix = page.get_pixmap(dpi=150)
                pix.save(str(out_dir / f"page_{idx+1:03d}.jpg"))
            doc.close()
        except Exception as e:
            print(f"Error extracting PDF: {e}")

    def load_manhwa_chapter(self, manhwa_path: Path, start_ch_num: int, restore_scroll_y: int = 0):
        self.current_manhwa_path = manhwa_path
        self.current_manhwa_name = manhwa_path.name
        self.active_ch_num = start_ch_num
        self.is_restoring_scroll = True

        self.clear_canvas()
        self.append_chapter(start_ch_num)

        if restore_scroll_y > 0:
            QTimer.singleShot(120, lambda: self.apply_saved_scroll(restore_scroll_y))
        else:
            self.verticalScrollBar().setValue(0)
            self.is_restoring_scroll = False

    def clear_canvas(self):
        while self.strip_layout.count():
            item = self.strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.page_labels.clear()
        self.loaded_chapters.clear()
        self.pixmap_cache.clear()

    def append_chapter(self, ch_num: int):
        if ch_num in self.loaded_chapters:
            return

        imgs = self.ensure_chapter_images(ch_num)
        if not imgs:
            return

        self.loaded_chapters[ch_num] = imgs

        divider = QLabel(f"━━━   CHAPTER {ch_num}   ━━━")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter)
        divider.setStyleSheet("""
            color: #fbbf24;
            font-size: 15px;
            font-weight: 700;
            padding: 18px 0px;
            background-color: rgba(24, 27, 35, 0.75);
            border-top: 2px dashed rgba(217, 119, 6, 0.45);
            border-bottom: 2px dashed rgba(217, 119, 6, 0.45);
        """)
        self.strip_layout.addWidget(divider)

        target_w = int(self.reading_width * self.zoom)

        for img_p in imgs:
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setContentsMargins(0, 0, 0, 0)
            lbl.setStyleSheet("border: none; padding: 0px; margin: 0px;")

            sp = str(img_p)
            if sp not in self.pixmap_cache:
                self.pixmap_cache[sp] = QPixmap(sp)

            pm = self.pixmap_cache[sp]
            if not pm.isNull():
                lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))

            self.strip_layout.addWidget(lbl)
            self.page_labels.append((ch_num, lbl, sp))

    def apply_saved_scroll(self, scroll_y: int):
        self.verticalScrollBar().setValue(scroll_y)
        self.is_restoring_scroll = False

    def _do_rescale(self):
        target_w = int(self.reading_width * self.zoom)
        self.strip_widget.setFixedWidth(target_w)

        self.strip_widget.setUpdatesEnabled(False)
        for ch_num, lbl, img_path in self.page_labels:
            if img_path not in self.pixmap_cache:
                self.pixmap_cache[img_path] = QPixmap(img_path)
            pm = self.pixmap_cache[img_path]
            if not pm.isNull():
                lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))
        self.strip_widget.setUpdatesEnabled(True)

    def on_scroll(self, value: int):
        if self.is_restoring_scroll or not self.page_labels:
            return

        max_scroll = self.verticalScrollBar().maximum()
        if max_scroll <= 0:
            return

        ratio = value / max_scroll

        if ratio >= self.cfg.get("auto_preload_threshold", 0.67):
            next_ch = self.active_ch_num + 1
            if next_ch not in self.loaded_chapters:
                self.append_chapter(next_ch)

        self.scroll_progress_signal.emit(self.active_ch_num, ratio)

    def keyPressEvent(self, event):
        key = event.key()
        scroll_step = self.cfg.get("scroll_speed", 75)

        if key in [Qt.Key.Key_Down, Qt.Key.Key_S]:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + scroll_step)
        elif key in [Qt.Key.Key_Up, Qt.Key.Key_W]:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - scroll_step)
        elif key == Qt.Key.Key_Space:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + int(self.height() * 0.85))
        elif key == Qt.Key.Key_PageDown:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + self.height())
        elif key == Qt.Key.Key_PageUp:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - self.height())
        else:
            super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Main Application Window
# ---------------------------------------------------------------------------
class ManhwaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.lang = self.cfg.get("language", "uk")
        self.t = TRANSLATIONS.get(self.lang, TRANSLATIONS["uk"])

        self.lib_dir = BASE_DIR / self.cfg.get("library_path", "library")
        self.lib_dir.mkdir(parents=True, exist_ok=True)

        self.current_reading_manhwa = ""
        self.current_reading_chapter = 1
        self.is_zen_mode = False

        self.init_window_properties()
        self.init_ui()
        self.refresh_catalog()

    def init_window_properties(self):
        self.setWindowTitle(self.t["app_title"])
        self.resize(1280, 840)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(STYLESHEET)

        icon_path = BASE_DIR / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def init_ui(self):
        self.central_ambient = AmbientBackgroundWidget(self)
        self.setCentralWidget(self.central_ambient)

        self.root_layout = QVBoxLayout(self.central_ambient)
        self.root_layout.setContentsMargins(24, 16, 24, 20)
        self.root_layout.setSpacing(14)

        # 1. Header
        self.header_frame = QFrame()
        self.header_frame.setProperty("class", "cardPane")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(22, 14, 22, 14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        badge_lbl = QLabel(self.t["badge_engine"])
        badge_lbl.setStyleSheet("""
            color: #fbbf24;
            background-color: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.30);
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        title_box.addWidget(badge_lbl)

        title_lbl = QLabel("Manhwa Reader <span style='color: #fbbf24;'>AI Drafter</span>")
        title_lbl.setStyleSheet("font-size: 26px; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel(self.t["subtitle"])
        sub_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        title_box.addWidget(sub_lbl)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.fs_btn = QPushButton(self.t["fs_on"])
        self.fs_btn.setProperty("class", "btnSecondary")
        self.fs_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        header_layout.addWidget(self.fs_btn)

        self.root_layout.addWidget(self.header_frame)

        # 2. Navigation Tabs
        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("navBar")
        nav_layout = QHBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(8)

        self.tab_catalog_btn = QPushButton(self.t["tab_catalog"])
        self.tab_catalog_btn.setProperty("class", "navTab activeTab")
        self.tab_catalog_btn.setCheckable(True)
        self.tab_catalog_btn.setChecked(True)
        self.tab_catalog_btn.clicked.connect(lambda: self.switch_tab(0))

        self.tab_reader_btn = QPushButton(self.t["tab_reader"])
        self.tab_reader_btn.setProperty("class", "navTab")
        self.tab_reader_btn.setCheckable(True)
        self.tab_reader_btn.clicked.connect(lambda: self.switch_tab(1))

        self.tab_downloader_btn = QPushButton(self.t["tab_downloader"])
        self.tab_downloader_btn.setProperty("class", "navTab")
        self.tab_downloader_btn.setCheckable(True)
        self.tab_downloader_btn.clicked.connect(lambda: self.switch_tab(2))

        self.tab_settings_btn = QPushButton(self.t["tab_settings"])
        self.tab_settings_btn.setProperty("class", "navTab")
        self.tab_settings_btn.setCheckable(True)
        self.tab_settings_btn.clicked.connect(lambda: self.switch_tab(3))

        nav_layout.addWidget(self.tab_catalog_btn)
        nav_layout.addWidget(self.tab_reader_btn)
        nav_layout.addWidget(self.tab_downloader_btn)
        nav_layout.addWidget(self.tab_settings_btn)
        nav_layout.addStretch()

        self.root_layout.addWidget(self.nav_frame)

        # 3. Stacked Pages
        self.stack = QStackedWidget()
        self.root_layout.addWidget(self.stack, 1)

        self.page_catalog = self.create_catalog_page()
        self.stack.addWidget(self.page_catalog)

        self.page_reader = self.create_reader_page()
        self.stack.addWidget(self.page_reader)

        self.page_downloader = self.create_downloader_page()
        self.stack.addWidget(self.page_downloader)

        self.page_settings = self.create_settings_page()
        self.stack.addWidget(self.page_settings)

    # -----------------------------------------------------------------------
    # TAB 0: CATALOG
    # -----------------------------------------------------------------------
    def create_catalog_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        cat_title = QLabel(self.t["lib_title"])
        cat_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f3f4f6;")
        top_bar.addWidget(cat_title)
        top_bar.addStretch()

        refresh_btn = QPushButton(self.t["refresh"])
        refresh_btn.setProperty("class", "btnSecondary")
        refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_btn.clicked.connect(self.refresh_catalog)
        top_bar.addWidget(refresh_btn)

        add_btn = QPushButton(self.t["add_tg"])
        add_btn.setProperty("class", "btnAccent")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.clicked.connect(lambda: self.switch_tab(2))
        top_bar.addWidget(add_btn)

        layout.addLayout(top_bar)

        self.catalog_scroll = QScrollArea()
        self.catalog_scroll.setWidgetResizable(True)
        self.catalog_scroll.setStyleSheet("background: transparent; border: none;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(16)
        self.cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.catalog_scroll.setWidget(self.cards_container)
        layout.addWidget(self.catalog_scroll, 1)

        return widget

    def refresh_catalog(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        manhwas = [p for p in self.lib_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

        if not manhwas:
            empty_lbl = QLabel(self.t["empty_lib"])
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #9ca3af; font-size: 15px; padding: 60px;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)
            return

        cols = max(1, self.width() // 280)
        bookmarks = self.cfg.get("bookmarks", {})

        for idx, m_path in enumerate(manhwas):
            bm = bookmarks.get(m_path.name, {})
            card = ManhwaCard(m_path.name, m_path, bm, self.t)
            card.read_clicked.connect(self.open_manhwa_reader)
            card.delete_clicked.connect(self.confirm_delete_manhwa)

            row = idx // cols
            col = idx % cols
            self.cards_grid.addWidget(card, row, col)

    def confirm_delete_manhwa(self, manhwa_name: str):
        dlg = ConfirmDeleteDialog(self.t["del_confirm_title"], manhwa_name, self.t, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            target_path = self.lib_dir / manhwa_name
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)

            if "bookmarks" in self.cfg and manhwa_name in self.cfg["bookmarks"]:
                del self.cfg["bookmarks"][manhwa_name]
                save_config(self.cfg)

            self.refresh_catalog()

    # -----------------------------------------------------------------------
    # TAB 1: WEBTOON READER (Zen Mode)
    # -----------------------------------------------------------------------
    def create_reader_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.reader_toolbar = QFrame()
        self.reader_toolbar.setProperty("class", "cardPane")
        tb_layout = QHBoxLayout(self.reader_toolbar)
        tb_layout.setContentsMargins(14, 8, 14, 8)
        tb_layout.setSpacing(8)

        back_btn = QPushButton(self.t["to_catalog"])
        back_btn.setProperty("class", "btnSecondary")
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.clicked.connect(lambda: self.switch_tab(0))
        tb_layout.addWidget(back_btn)

        self.reader_title_lbl = QLabel(self.t["select_manhwa"])
        self.reader_title_lbl.setStyleSheet("font-weight: 700; font-size: 15px; color: #fbbf24;")
        tb_layout.addWidget(self.reader_title_lbl)

        tb_layout.addStretch()

        prev_ch_btn = QPushButton("◀")
        prev_ch_btn.setToolTip(self.t["prev_ch"])
        prev_ch_btn.setFixedWidth(32)
        prev_ch_btn.setProperty("class", "btnSecondary")
        prev_ch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        prev_ch_btn.clicked.connect(self.prev_chapter)
        tb_layout.addWidget(prev_ch_btn)

        self.chapter_combo = QComboBox()
        self.chapter_combo.setFixedWidth(130)
        self.chapter_combo.currentIndexChanged.connect(self.on_chapter_combo_change)
        tb_layout.addWidget(self.chapter_combo)

        next_ch_btn = QPushButton("▶")
        next_ch_btn.setToolTip(self.t["next_ch"])
        next_ch_btn.setFixedWidth(32)
        next_ch_btn.setProperty("class", "btnSecondary")
        next_ch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        next_ch_btn.clicked.connect(self.next_chapter)
        tb_layout.addWidget(next_ch_btn)

        tb_layout.addWidget(QLabel(self.t["width_lbl"]))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(600, 1400)
        self.width_slider.setValue(self.cfg.get("reading_width", 880))
        self.width_slider.setFixedWidth(90)
        self.width_slider.valueChanged.connect(self.on_width_slider_change)
        tb_layout.addWidget(self.width_slider)

        zoom_minus = QPushButton("－")
        zoom_minus.setFixedWidth(28)
        zoom_minus.setProperty("class", "btnSecondary")
        zoom_minus.clicked.connect(lambda: self.adjust_zoom(-0.1))
        tb_layout.addWidget(zoom_minus)

        self.zoom_lbl = QLabel(f"{int(self.cfg.get('zoom', 1.0) * 100)}%")
        self.zoom_lbl.setStyleSheet("font-weight: 600; color: #9ca3af; min-width: 40px;")
        tb_layout.addWidget(self.zoom_lbl)

        zoom_plus = QPushButton("＋")
        zoom_plus.setFixedWidth(28)
        zoom_plus.setProperty("class", "btnSecondary")
        zoom_plus.clicked.connect(lambda: self.adjust_zoom(0.1))
        tb_layout.addWidget(zoom_plus)

        tb_layout.addWidget(QLabel(self.t["theme_lbl"]))
        bg_grp = QHBoxLayout()
        bg_grp.setSpacing(4)
        for hex_col in ["#0f1115", "#000000", "#181b23"]:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 2px solid rgba(255, 255, 255, 0.25);
                    border-radius: 10px;
                }}
                QPushButton:hover {{
                    border-color: #fbbf24;
                }}
            """)
            btn.clicked.connect(lambda _, c=hex_col: self.set_background_color(c))
            bg_grp.addWidget(btn)
        tb_layout.addLayout(bg_grp)

        self.zen_btn = QPushButton(self.t["hide_menu"])
        self.zen_btn.setProperty("class", "btnSecondary")
        self.zen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.zen_btn.clicked.connect(self.toggle_zen_mode)
        tb_layout.addWidget(self.zen_btn)

        layout.addWidget(self.reader_toolbar)

        self.canvas = WebtoonScrollCanvas(self.cfg)
        self.canvas.scroll_progress_signal.connect(self.on_reader_progress)
        layout.addWidget(self.canvas, 1)

        return widget

    def toggle_zen_mode(self):
        self.is_zen_mode = not self.is_zen_mode
        if self.is_zen_mode:
            self.header_frame.hide()
            self.nav_frame.hide()
            self.zen_btn.setText(self.t["show_menu"])
            self.root_layout.setContentsMargins(0, 0, 0, 0)
        else:
            self.header_frame.show()
            self.nav_frame.show()
            self.zen_btn.setText(self.t["hide_menu"])
            self.root_layout.setContentsMargins(24, 16, 24, 20)

    def open_manhwa_reader(self, manhwa_name: str, force_ch: Optional[int] = None):
        self.current_reading_manhwa = manhwa_name
        m_path = self.lib_dir / manhwa_name
        if not m_path.exists():
            return

        chapter_nums = set()
        for p in m_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                num = extract_chapter_number(p.name)
                if num is not None:
                    chapter_nums.add(num)
        for pdf_p in m_path.glob("*.pdf"):
            num = extract_chapter_number(pdf_p.stem)
            if num is not None:
                chapter_nums.add(num)

        sorted_chapters = sorted(list(chapter_nums))
        if not sorted_chapters:
            sorted_chapters = [1]

        ch_word = "Ch." if self.lang == "en" else "Глава"
        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()
        for c_num in sorted_chapters:
            self.chapter_combo.addItem(f"{ch_word} {c_num}", c_num)
        self.chapter_combo.blockSignals(False)

        bm = self.cfg.get("bookmarks", {}).get(manhwa_name, {})
        start_ch = force_ch or bm.get("chapter", sorted_chapters[0])
        saved_scroll_y = bm.get("scroll_y", 0) if not force_ch else 0

        idx = self.chapter_combo.findData(start_ch)
        if idx >= 0:
            self.chapter_combo.blockSignals(True)
            self.chapter_combo.setCurrentIndex(idx)
            self.chapter_combo.blockSignals(False)

        self.reader_title_lbl.setText(f"📖 {manhwa_name}")
        self.switch_tab(1)
        self.canvas.load_manhwa_chapter(m_path, start_ch, saved_scroll_y)

    def on_chapter_combo_change(self, idx: int):
        ch_num = self.chapter_combo.currentData()
        if ch_num and self.current_reading_manhwa:
            m_path = self.lib_dir / self.current_reading_manhwa
            self.canvas.load_manhwa_chapter(m_path, ch_num, 0)

    def prev_chapter(self):
        curr_idx = self.chapter_combo.currentIndex()
        if curr_idx > 0:
            self.chapter_combo.setCurrentIndex(curr_idx - 1)

    def next_chapter(self):
        curr_idx = self.chapter_combo.currentIndex()
        if curr_idx < self.chapter_combo.count() - 1:
            self.chapter_combo.setCurrentIndex(curr_idx + 1)

    def on_width_slider_change(self, val: int):
        self.cfg["reading_width"] = val
        self.canvas.set_reading_width(val)
        save_config(self.cfg)

    def adjust_zoom(self, delta: float):
        new_zoom = round(self.canvas.zoom + delta, 1)
        new_zoom = max(0.5, min(2.5, new_zoom))
        self.canvas.set_zoom(new_zoom)
        self.cfg["zoom"] = new_zoom
        self.zoom_lbl.setText(f"{int(new_zoom * 100)}%")
        save_config(self.cfg)

    def set_background_color(self, hex_color: str):
        self.cfg["bg_color"] = hex_color
        self.canvas.set_bg_color(hex_color)
        save_config(self.cfg)

    def on_reader_progress(self, ch_num: int, pct: float):
        if not self.current_reading_manhwa:
            return
        scroll_y = self.canvas.verticalScrollBar().value()
        if "bookmarks" not in self.cfg:
            self.cfg["bookmarks"] = {}

        self.cfg["bookmarks"][self.current_reading_manhwa] = {
            "chapter": ch_num,
            "scroll_y": scroll_y,
            "chapter_progress": round(pct, 2)
        }

    # -----------------------------------------------------------------------
    # TAB 2: TELEGRAM DOWNLOADER (Scrollable, High Contrast, Auth Support)
    # -----------------------------------------------------------------------
    def create_downloader_page(self) -> QWidget:
        # Wrap everything in QScrollArea so user can scroll without any squishing!
        scroll_wrapper = QScrollArea()
        scroll_wrapper.setWidgetResizable(True)
        scroll_wrapper.setStyleSheet("background: transparent; border: none;")

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("class", "cardPane")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(26, 26, 26, 26)
        card_layout.setSpacing(16)

        # Header with Auth Status
        top_auth_row = QHBoxLayout()
        c_title = QLabel(self.t["dl_title"])
        c_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        top_auth_row.addWidget(c_title)
        top_auth_row.addStretch()

        self.auth_status_lbl = QLabel(self.t["auth_needed"])
        self.auth_status_lbl.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 600;")
        top_auth_row.addWidget(self.auth_status_lbl)

        auth_btn = QPushButton(self.t["auth_btn"])
        auth_btn.setProperty("class", "btnSecondary")
        auth_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        auth_btn.clicked.connect(self.open_telegram_auth)
        top_auth_row.addWidget(auth_btn)

        card_layout.addLayout(top_auth_row)
        self.check_auth_status()

        # Clean Amber Banner (No ugly flat lines!)
        info_banner = QFrame()
        info_banner.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.08);
            border-left: 4px solid #f59e0b;
            border-radius: 8px;
            padding: 12px 16px;
        """)
        ib_layout = QVBoxLayout(info_banner)
        ib_layout.setSpacing(4)
        
        ib_title = QLabel(self.t["dl_info_title"])
        ib_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #fbbf24;")
        ib_layout.addWidget(ib_title)

        ib_text = QLabel(self.t["dl_info_desc"])
        ib_text.setStyleSheet("color: #d1d5db; font-size: 13px; font-weight: 400;")
        ib_text.setWordWrap(True)
        ib_layout.addWidget(ib_text)

        card_layout.addWidget(info_banner)

        # High-Contrast Form Grid
        form_grid = QGridLayout()
        form_grid.setSpacing(12)

        lbl_ch = QLabel(self.t["dl_channel"])
        form_grid.addWidget(lbl_ch, 0, 0)
        self.dl_channel_inp = QLineEdit("")
        self.dl_channel_inp.setPlaceholderText("https://t.me/channel_name або @channel_name")
        form_grid.addWidget(self.dl_channel_inp, 0, 1)

        lbl_kw = QLabel(self.t["dl_search"])
        form_grid.addWidget(lbl_kw, 1, 0)
        self.dl_kw_inp = QLineEdit("")
        self.dl_kw_inp.setPlaceholderText("Наприклад: Назва (або порожньо для всіх PDF)")
        form_grid.addWidget(self.dl_kw_inp, 1, 1)

        lbl_rg = QLabel(self.t["dl_range"])
        form_grid.addWidget(lbl_rg, 2, 0)
        self.dl_range_inp = QLineEdit("1")
        self.dl_range_inp.setPlaceholderText("Наприклад: 2 або 1-30 або 1 2 (порожньо = всі)")
        form_grid.addWidget(self.dl_range_inp, 2, 1)

        lbl_nm = QLabel(self.t["dl_name"])
        form_grid.addWidget(lbl_nm, 3, 0)
        self.dl_title_inp = QLineEdit("")
        self.dl_title_inp.setPlaceholderText("Назва папки манхви у бібліотеці")
        form_grid.addWidget(self.dl_title_inp, 3, 1)

        card_layout.addLayout(form_grid)

        # Progress bar
        self.dl_prog = QProgressBar()
        self.dl_prog.setValue(0)
        self.dl_prog.setTextVisible(True)
        self.dl_prog.setStyleSheet("""
            QProgressBar {
                background-color: #12151e;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                text-align: center;
                color: #ffffff;
                font-weight: 700;
                height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #3b82f6);
                border-radius: 7px;
            }
        """)
        card_layout.addWidget(self.dl_prog)

        # Log Console
        self.dl_log = QTextEdit()
        self.dl_log.setReadOnly(True)
        self.dl_log.setFixedHeight(180)
        self.dl_log.setStyleSheet("""
            background-color: #0b0d13;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            color: #a7f3d0;
            padding: 8px;
        """)
        card_layout.addWidget(self.dl_log)

        # Action Button (Always vibrant, prominent and visible)
        self.dl_start_btn = QPushButton(self.t["dl_start"])
        self.dl_start_btn.setFixedHeight(50)
        self.dl_start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.dl_start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
                color: #121008;
                font-size: 15px;
                font-weight: 800;
                border-radius: 12px;
                padding: 12px 24px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fcd34d, stop:1 #f59e0b);
            }
            QPushButton:disabled {
                background-color: #2b3145;
                color: #6b7280;
            }
        """)
        self.dl_start_btn.clicked.connect(self.start_download)
        card_layout.addWidget(self.dl_start_btn)

        layout.addWidget(card)
        layout.addStretch()

        scroll_wrapper.setWidget(inner_widget)
        return scroll_wrapper

    def check_auth_status(self):
        """Checks if Telegram session file or Bot Token is active."""
        if self.cfg.get("tg_bot_token"):
            self.auth_status_lbl.setText("🟢 Telegram Бот підключено")
            self.auth_status_lbl.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
            return
        session_file = BASE_DIR / "tg_session.session"
        if session_file.exists() and session_file.stat().st_size > 4000:
            self.auth_status_lbl.setText(self.t["auth_ok"])
            self.auth_status_lbl.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
        else:
            self.auth_status_lbl.setText(self.t["auth_needed"])
            self.auth_status_lbl.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 600;")

    def open_telegram_auth(self):
        dlg = TelegramBotTokenDialog(self.cfg, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.check_auth_status()
            self.dl_log.append("Токен Telegram Бота оновлено! Можна завантажувати глави.")

    def start_download(self):
        channel = self.dl_channel_inp.text().strip()
        kw = self.dl_kw_inp.text().strip()
        range_s = self.dl_range_inp.text().strip()
        title = self.dl_title_inp.text().strip()

        if not channel:
            self.dl_log.append("Помилка: введіть посилання на канал!")
            return

        if not title:
            title = kw or "Downloaded_Manhwa"

        self.dl_start_btn.setEnabled(False)
        self.dl_prog.setValue(0)
        self.dl_log.clear()
        self.dl_log.append(f"Пошук та завантаження для: «{title}» (Глави: {range_s or 'всі'})...")

        api_id = self.cfg.get("tg_api_id", 37560778)
        api_hash = self.cfg.get("tg_api_hash", "307da2f94fc6450afe139c91bcc59eaa")
        del_pdf = self.cfg.get("delete_pdf_after_extract", True)

        self.worker = DownloadWorker(api_id, api_hash, channel, kw, range_s, title, self.lib_dir, del_pdf)
        self.worker.status_signal.connect(lambda s: self.dl_log.append(f"• {s}"))
        self.worker.progress_signal.connect(lambda p: self.dl_prog.setValue(int(p * 100)))
        self.worker.need_auth_signal.connect(self.on_worker_need_auth)
        self.worker.finished_signal.connect(self.on_download_finished)
        self.worker.start()

    def on_worker_need_auth(self):
        self.dl_start_btn.setEnabled(True)
        self.open_telegram_auth()

    def on_download_finished(self, success: bool, msg: str):
        self.dl_start_btn.setEnabled(True)
        if success:
            self.dl_prog.setValue(100)
            self.dl_log.append(f"\n[УСПІХ] {msg}")
            self.refresh_catalog()
        else:
            self.dl_log.append(f"\n[ПОМИЛКА] {msg}")

    # -----------------------------------------------------------------------
    # TAB 3: SETTINGS
    # -----------------------------------------------------------------------
    def create_settings_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setProperty("class", "cardPane")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        title = QLabel(self.t["settings_title"])
        title.setStyleSheet("font-size: 19px; font-weight: 700;")
        card_layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(14)

        grid.addWidget(QLabel(self.t["lang_lbl"]), 0, 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Українська (UA)", "uk")
        self.lang_combo.addItem("English (EN)", "en")
        curr_lang = self.cfg.get("language", "uk")
        self.lang_combo.setCurrentIndex(0 if curr_lang == "uk" else 1)
        grid.addWidget(self.lang_combo, 0, 1)

        grid.addWidget(QLabel(self.t["del_pdf_lbl"]), 1, 0)
        self.del_pdf_check = QCheckBox()
        self.del_pdf_check.setChecked(self.cfg.get("delete_pdf_after_extract", True))
        grid.addWidget(self.del_pdf_check, 1, 1)

        grid.addWidget(QLabel(self.t["speed_lbl"]), 2, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(30, 160)
        self.speed_slider.setValue(self.cfg.get("scroll_speed", 75))
        grid.addWidget(self.speed_slider, 2, 1)

        grid.addWidget(QLabel("Library Folder:"), 3, 0)
        lib_inp = QLineEdit(str(self.lib_dir))
        lib_inp.setReadOnly(True)
        grid.addWidget(lib_inp, 3, 1)

        card_layout.addLayout(grid)

        save_btn = QPushButton(self.t["save_btn"])
        save_btn.setProperty("class", "btnAccent")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self.save_settings)
        card_layout.addWidget(save_btn)

        card_layout.addStretch()
        layout.addWidget(card)
        layout.addStretch()
        return widget

    def save_settings(self):
        new_lang = self.lang_combo.currentData()
        self.cfg["language"] = new_lang
        self.cfg["delete_pdf_after_extract"] = self.del_pdf_check.isChecked()
        self.cfg["scroll_speed"] = self.speed_slider.value()
        save_config(self.cfg)

        self.lang = new_lang
        self.t = TRANSLATIONS.get(self.lang, TRANSLATIONS["uk"])
        self.refresh_catalog()

    # -----------------------------------------------------------------------
    # NAVIGATION & FULLSCREEN
    # -----------------------------------------------------------------------
    def switch_tab(self, index: int):
        buttons = [self.tab_catalog_btn, self.tab_reader_btn, self.tab_downloader_btn, self.tab_settings_btn]
        for idx, btn in enumerate(buttons):
            if idx == index:
                btn.setProperty("class", "navTab activeTab")
                btn.setChecked(True)
            else:
                btn.setProperty("class", "navTab")
                btn.setChecked(False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.stack.setCurrentIndex(index)
        if index == 0:
            self.refresh_catalog()
        elif index == 2:
            self.check_auth_status()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.header_frame.show()
            self.fs_btn.setText(self.t["fs_on"])
        else:
            self.showFullScreen()
            self.fs_btn.setText(self.t["fs_off"])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_H:
            if self.stack.currentIndex() == 1:
                self.toggle_zen_mode()
        elif event.key() == Qt.Key.Key_Escape:
            if self.is_zen_mode:
                self.toggle_zen_mode()
            elif self.isFullScreen():
                self.toggle_fullscreen()
            elif self.stack.currentIndex() == 1:
                self.switch_tab(0)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        save_config(self.cfg)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# App Main
# ---------------------------------------------------------------------------
def main():
    import ctypes
    try:
        myappid = 'manhwa.aidrafter.reader.v1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = BASE_DIR / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = ManhwaApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
