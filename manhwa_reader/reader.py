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

from pathlib import Path
_THIS_DIR = str(Path(__file__).parent.resolve())
_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import re
import json
import asyncio
import shutil
import subprocess
from typing import List, Dict, Optional, Tuple, Set

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect, QRectF, QUrl
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QFont, QIcon, QKeySequence,
    QLinearGradient, QRadialGradient, QBrush, QCursor, QPalette, QDesktopServices
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

try:
    from downloader import (
        TelegramManhwaDownloader, extract_chapter_number, clean_channel_link,
        extract_pdf_to_images, extract_chapter_pdf
    )
    from cloud_stream import (
        TelegramStreamClient, RollingRAMCache, StreamDownloadThread,
        load_cloud_index, save_cloud_index
    )
except ImportError:
    from manhwa_reader.downloader import (
        TelegramManhwaDownloader, extract_chapter_number, clean_channel_link,
        extract_pdf_to_images, extract_chapter_pdf
    )
    from manhwa_reader.cloud_stream import (
        TelegramStreamClient, RollingRAMCache, StreamDownloadThread,
        load_cloud_index, save_cloud_index
    )

try:
    from manhwa_reader.novel_reader.novel_window import NovelReaderWindow
except ImportError:
    try:
        from novel_reader.novel_window import NovelReaderWindow
    except ImportError:
        try:
            from .novel_reader.novel_window import NovelReaderWindow
        except Exception:
            NovelReaderWindow = None

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()

CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_LIB_DIR = BASE_DIR / "library"
DEFAULT_BOT_TOKEN = "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA"


# ---------------------------------------------------------------------------
# Multilingual Translations
# ---------------------------------------------------------------------------
TRANSLATIONS = {
    "en": {
        "app_title": "Manhwa Reader AI Drafter",
        "tab_catalog": "📚 Library",
        "tab_reader": "📖 Reader",
        "tab_downloader": "⚡ TG Downloader",
        "tab_settings": "⚙️ Settings",
        "badge_engine": "🚀 STANDALONE WEBTOON ENGINE",
        "subtitle": "Standalone webtoon player, auto-bookmarks & high-speed Telegram downloader",
        "fs_on": "⛶ Fullscreen (F11)",
        "fs_off": "🗗 Windowed (F11)",
        "hide_menu": "👁 Hide Toolbar (H)",
        "show_menu": "👁 Show Toolbar (H)",
        "to_catalog": "← Library",
        "lib_title": "Your Library",
        "refresh": "🔄 Refresh",
        "add_tg": "+ Download from TG",
        "empty_lib": "📂 Your library is currently empty.\nHead over to '⚡ TG Downloader' tab to get started!",
        "read_btn": "▶ Read",
        "del_tooltip": "Delete manhwa",
        "del_confirm_title": "Delete Manhwa",
        "del_confirm_msg": "Are you sure you want to delete:\n«{title}» ?",
        "del_confirm_sub": "All downloaded chapters, files, and bookmarks will be permanently removed from disk.",
        "cancel": "Cancel",
        "del_btn_action": "🗑️ Yes, Delete",
        "select_manhwa": "Select a manhwa",
        "prev_ch": "◀ Previous",
        "next_ch": "Next ▶",
        "chapter_prefix": "Chapter",
        "width_lbl": "Width:",
        "zoom_lbl": "Zoom:",
        "theme_lbl": "Theme:",
        "dl_title": "⚡ Telegram PDF Chapter Downloader",
        "dl_info_title": "📌 How Downloader Works:",
        "dl_info_desc": "Provide an open channel link (e.g., https://t.me/channel_name) or username (@channel_name). The app will search for PDF files and save them to your library.",
        "dl_channel": "Channel (URL or @tag):",
        "dl_channel_ph": "https://t.me/channel_name or @channel_name",
        "dl_search": "Search Keyword (Filter):",
        "dl_search_ph": "e.g.: Title (or leave empty for all PDFs)",
        "dl_range": "Chapter Number or Range:",
        "dl_range_ph": "e.g.: 2 or 1-30 or 1 2 (empty = all)",
        "dl_name": "Title Name in Library:",
        "dl_name_ph": "Folder name for manhwa in library",
        "dl_lang": "Translation Language:",
        "dl_lang_auto": "Auto-detect",
        "dl_start": "🚀 Start Download",
        "settings_title": "⚙️ Application Settings",
        "lang_lbl": "Interface Language:",
        "speed_lbl": "Keyboard Scroll Speed:",
        "lib_lbl": "Library Folder:",
        "save_btn": "💾 Save Settings",
        "saved_msg": "Settings saved successfully!",
        "auth_btn": "🤖 Bot Token",
        "auth_ok": "🟢 Telegram Bot Connected",
        "auth_needed": "🟡 Telegram Bot Token Required",
        "toggle_extract_jpeg_title": "Extract to JPEG upon Download",
        "toggle_extract_jpeg_sub": "Converts PDF files into image galleries during download",
        "toggle_novel_mode_title": "Novel / Light Novel (EPUB / DOCX / TXT)",
        "toggle_novel_mode_sub": "Save as text novel chapters into dedicated Novel Library",
        "cat_tab_novels": "📖 Novels / Light Novels",
        "toggle_del_pdf_title": "Delete Original PDF After Extraction",
        "toggle_del_pdf_sub": "Saves disk space after creating JPEG galleries",
        "read_in_jpeg": "🖼️ Read in JPEG",
        "read_in_pdf": "📑 Read in PDF",
        "manual_unpack_title": "📦 Manual Chapter Unpack (PDF → JPEG)",
        "manual_unpack_sub": "Select manhwa and chapter from existing PDFs to convert into JPEG:",
        "manual_unpack_m_lbl": "Manhwa:",
        "manual_unpack_ch_lbl": "Chapter to Unpack:",
        "manual_unpack_btn": "⚡ Unpack Selected Chapter to JPEG",
        "status_only_pdf": "Only PDF",
        "status_has_jpeg": "Already JPEG",
        "status_no_pdf": "No PDF Chapters Available",
        "status_empty_m": "No manhwa in library",
        "unpack_confirm_title": "Unpack JPEG",
        "unpack_confirm_header": "⚡ Unpack Chapter {ch} to JPEG",
        "unpack_confirm_msg": "JPEG pages for this chapter are not unpacked yet.\nWould you like to unpack them from the existing PDF now?",
        "unpack_confirm_btn": "⚡ Unpack to JPEG",
        "pdf_missing_title": "PDF Unavailable",
        "pdf_missing_msg": "Original PDF file for chapter {ch} was deleted after extraction or is missing.",
        "token_dlg_title": "Telegram Bot Setup",
        "token_dlg_header": "🤖 Telegram Bot Token for Downloads",
        "token_dlg_info": "The bot allows downloading chapters without phone numbers, SMS, or 2FA passwords.\nPaste your bot token from @BotFather here. It will be saved in config.json.",
        "token_dlg_lbl": "API Bot Token:",
        "token_dlg_ph": "e.g.: 8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA",
        "token_save_btn": "💾 Save Token",
        "token_saved_msg": "Token saved successfully in config.json!",
        "token_ready_log": "🟢 Telegram Bot connected! Ready to download chapters.",
        "ok_btn": "Got it",
        "unpacking_progress": "Unpacking chapter {num}...",
        "unpacking_success": "✓ Chapter {num} unpacked successfully ({count} pages)!",
        "unpacking_error": "Unpack error: {err}",
        "select_pdf_first": "Please select a chapter with an existing PDF!",
        "dl_err_no_channel": "Error: please enter a channel link!",
        "dl_start_log": "Search and download for: «{title}» (Chapters: {range})...",
        "dl_all": "all",
        "log_success_tag": "[SUCCESS]",
        "log_error_tag": "[ERROR]",
        "dl_log_connecting": "Connecting to Telegram service via Bot...",
        "dl_log_searching": "Searching for PDF chapters in @{channel}...",
        "dl_log_found_count": "Found chapters/documents: {count}",
        "dl_log_total_to_download": "Will download chapters: {count}. Starting...",
        "dl_log_chapter_header": "[{idx}/{total}] Chapter {ch}: {filename}",
        "dl_log_downloading": "Downloading {filename} ({size} MB)...",
        "dl_log_downloaded": "Chapter {ch} downloaded! Parallel JPEG extraction started...",
        "dl_log_extracting": "Extracting pages for Chapter {ch}...",
        "dl_log_extract_done": "✓ Chapter {ch}: JPEG extraction complete.",
        "dl_log_saved_pdf": "Saved as PDF: Chapter {ch}",
        "dl_log_waiting_extract": "Waiting for background extraction tasks to complete...",
        "dl_log_done": "Download of «{title}» finished successfully!",
        "dl_already_exists_title": "Chapter Already Downloaded",
        "dl_already_exists_msg": "The following chapter(s) are already downloaded:\n{chapters}\n\nDo you want to re-download them?",
        "dl_already_exists_redownload": "⚡ Download Again",
        "dl_already_exists_skip": "Skip Existing",
        "dl_already_exists_cancel": "Cancel",
        "dl_log_skipped_exists": "Chapter {ch} already exists. Skipping.",
        "cat_tab_local": "📚 Local Library",
        "cat_tab_cloud": "☁️ Cloud Vault",
        "cloud_vault_title": "Cloud Vault",
        "cloud_stream_read": "⚡ Read Online",
        "cloud_empty": "☁️ No titles found in your cloud vault.",
        "cloud_sync_btn": "🔄 Refresh",
        "cloud_badge": "CLOUD",
        "cloud_status_streaming": "⚡ Streaming in RAM (0 bytes on disk)",
        "cloud_card_dl_btn": "📥 Download",
        "cloud_card_dl_tooltip": "Download PDF to local library",
        "cloud_card_chs_word": "chapters",
        "cloud_card_new": "New",
        "cloud_dl_dlg_title": "Download PDF",
        "cloud_dl_dlg_header": "📥 Download Chapter (PDF)",
        "cloud_dl_total_range": "Total chapters available in vault: {min_ch}–{max_ch} (total {total})",
        "cloud_dl_total_count": "Total chapters available in vault: {total}",
        "cloud_dl_folder_lbl": "Save destination (folder name in Library):",
        "cloud_dl_range_lbl": "Chapter number or range:",
        "cloud_dl_range_ph": "e.g.: 1 or 1-10 or 1 2 3",
        "cloud_dl_btn": "📥 Download PDF",
        "reader_cloud_dl_btn": "📥 Download PDF",
        "notice_dl_success_title": "Download Complete",
        "notice_dl_success_btn": "Great",
        "notice_dl_error_title": "Download Error",
        "notice_dl_error_btn": "Got it",
        "cloud_dl_no_chapters": "No chapters found matching filter '{range}'.",
        "cloud_dl_start_status": "📥 Started downloading {total} chapters to library «{folder}»...",
        "cloud_dl_chapter_status": "[{idx}/{total}] Downloading Chapter {ch}...",
        "cloud_dl_saved_pdf": "✓ Chapter {ch} saved as PDF.",
        "cloud_dl_finish_success": "Successfully downloaded {total} chapters of manhwa «{folder}»!",
        "search_ph": "🔍 Search titles...",
        "filter_lang_all": "All Languages",
        "filter_lang_ua": "🇺🇦 UA",
        "filter_lang_en": "🇬🇧 EN",
        "filter_lang_raw": "🌐 RAW",
        "filter_prog_all": "All Progress",
        "filter_prog_reading": "📖 Reading",
        "filter_prog_completed": "✅ Read",
        "filter_prog_unread": "⏳ Unread",
        "search_count_lbl": "Showing: {count}",
        "btn_translate_nav": "⚔️ Translate",
        "translate_not_found_title": "M_Translate Module Not Found!",
        "translate_not_found_msg": "You do not have the Translate module installed. Visit our official Telegram channel to download the full version of the application.",
        "telegram_open_btn": "✈️ Open Telegram Channel",
        "other_translations_avail": "🌐 Available translations:",
        "switch_trans_tip": "Switch to {lang} version: {title}"
    },
    "uk": {
        "app_title": "Manhwa Reader AI Drafter",
        "tab_catalog": "📚 Бібліотека",
        "tab_reader": "📖 Читалка",
        "tab_downloader": "⚡ TG Завантажувач",
        "tab_settings": "⚙️ Налаштування",
        "badge_engine": "🚀 STANDALONE WEBTOON ENGINE",
        "subtitle": "Автономний вебтун-плеєр, автозакладки та швидкий завантажувач із Telegram",
        "fs_on": "⛶ На весь екран (F11)",
        "fs_off": "🗗 Згорнути (F11)",
        "hide_menu": "👁 Приховати меню (H)",
        "show_menu": "👁 Показати меню (H)",
        "to_catalog": "← Бібліотека",
        "lib_title": "Твоя бібліотека",
        "refresh": "🔄 Оновити",
        "add_tg": "+ Завантажити з TG",
        "empty_lib": "📂 У бібліотеці поки порожньо.\nПерейдіть у вкладку '⚡ TG Завантажувач', щоб додати манхву!",
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
        "chapter_prefix": "Глава",
        "width_lbl": "Ширина:",
        "zoom_lbl": "Зум:",
        "theme_lbl": "Фон:",
        "dl_title": "⚡ Завантажувач PDF-глав із Telegram",
        "dl_info_title": "📌 Як працює завантажувач:",
        "dl_info_desc": "Вкажіть посилання на відкритий канал (наприклад, https://t.me/channel_name) або юзернейм (@channel_name). Програма знайде PDF-документи та збереже їх у бібліотеку манхви.",
        "dl_channel": "Канал (URL або @тег):",
        "dl_channel_ph": "https://t.me/channel_name або @channel_name",
        "dl_search": "Пошукове слово (фільтр):",
        "dl_search_ph": "Наприклад: Назва (або порожньо для всіх PDF)",
        "dl_range": "Номер або діапазон (напр. 2 або 1-30):",
        "dl_range_ph": "Наприклад: 2 або 1-30 або 1 2 (порожньо = всі)",
        "dl_name": "Назва тайтлу в бібліотеці:",
        "dl_name_ph": "Назва папки манхви у бібліотеці",
        "dl_lang": "Мова перекладу тайтлу:",
        "dl_lang_auto": "Авто-визначення",
        "dl_start": "🚀 Почати завантаження",
        "settings_title": "⚙️ Налаштування програми",
        "lang_lbl": "Мова інтерфейсу:",
        "speed_lbl": "Швидкість скролу клавішами:",
        "lib_lbl": "Папка бібліотеки:",
        "save_btn": "💾 Зберегти налаштування",
        "saved_msg": "Налаштування успішно збережено!",
        "auth_btn": "🤖 Токен Бота",
        "auth_ok": "🟢 Telegram Бот підключено",
        "auth_needed": "🟡 Потрібен токен бота Telegram",
        "toggle_extract_jpeg_title": "Розпаковувати в JPEG при завантаженні",
        "toggle_extract_jpeg_sub": "Конвертує PDF-файли у галерею зображень під час скачування",
        "toggle_novel_mode_title": "Новела / Ранобе (EPUB / DOCX / TXT)",
        "toggle_novel_mode_sub": "Зберігати глави тексту в окрему Бібліотеку Новел для читання",
        "cat_tab_novels": "📖 Новели / Ранобе",
        "toggle_del_pdf_title": "Видаляти оригінальний PDF після розпаковки",
        "toggle_del_pdf_sub": "Економить місце на диску після створення JPEG-галереї",
        "read_in_jpeg": "🖼️ Читати в JPEG",
        "read_in_pdf": "📑 Читати в PDF",
        "manual_unpack_title": "📦 Ручне розпакування глав (PDF → JPEG)",
        "manual_unpack_sub": "Оберіть манхву та главу з наявних PDF для конвертації в JPEG:",
        "manual_unpack_m_lbl": "Манхва:",
        "manual_unpack_ch_lbl": "Глава для розпаковки:",
        "manual_unpack_btn": "⚡ Розпакувати вибрану главу в JPEG",
        "status_only_pdf": "Тільки PDF",
        "status_has_jpeg": "Вже є JPEG",
        "status_no_pdf": "Немає розділів із PDF",
        "status_empty_m": "У бібліотеці немає манхви",
        "unpack_confirm_title": "Розпакування JPEG",
        "unpack_confirm_header": "⚡ Розпакування Глави {ch} в JPEG",
        "unpack_confirm_msg": "Сторінки JPEG для цієї глави ще не розпаковані.\nРозпакувати зараз із наявного PDF-файлу за нашою технологією?",
        "unpack_confirm_btn": "⚡ Розпакувати в JPEG",
        "pdf_missing_title": "PDF недоступний",
        "pdf_missing_msg": "Оригінальний PDF-файл для глави {ch} було видалено після розпаковки або він відсутній.",
        "token_dlg_title": "Налаштування Telegram Бота",
        "token_dlg_header": "🤖 Токен Telegram Бота для завантаження",
        "token_dlg_info": "Бот дозволяє завантажувати глави без телефонів, SMS та паролів 2FA.\nВставте сюди токен вашого бота з @BotFather. Він збережеться в config.json.",
        "token_dlg_lbl": "API Токен Бота:",
        "token_dlg_ph": "Наприклад: 8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA",
        "token_save_btn": "💾 Зберегти токен",
        "token_saved_msg": "Токен успішно збережено в config.json!",
        "token_ready_log": "🟢 Telegram Бот підключено! Можна завантажувати глави.",
        "ok_btn": "Зрозуміло",
        "unpacking_progress": "Розпакування глави {num}...",
        "unpacking_success": "✓ Главу {num} успішно розпаковано ({count} сторінок)!",
        "unpacking_error": "Помилка розпакування: {err}",
        "select_pdf_first": "Оберіть главу з наявним PDF!",
        "dl_err_no_channel": "Помилка: введіть посилання на канал!",
        "dl_start_log": "Пошук та завантаження для: «{title}» (Глави: {range})...",
        "dl_all": "всі",
        "log_success_tag": "[УСПІХ]",
        "log_error_tag": "[ПОМИЛКА]",
        "dl_log_connecting": "Підключення до сервісу Telegram через Бота...",
        "dl_log_searching": "Пошук PDF-глав у каналі @{channel}...",
        "dl_log_found_count": "Знайдено розділів/файлів: {count}",
        "dl_log_total_to_download": "Буде завантажено глав: {count}. Розпочинаємо...",
        "dl_log_chapter_header": "[{idx}/{total}] Глава {ch}: {filename}",
        "dl_log_downloading": "Завантаження {filename} ({size} MB)...",
        "dl_log_downloaded": "Глава {ch} завантажена! Паралельна розпаковка в JPEG розпочата...",
        "dl_log_extracting": "Розпакування сторінок для Глави {ch}...",
        "dl_log_extract_done": "✓ Глава {ch}: розпаковку в JPEG завершено.",
        "dl_log_saved_pdf": "Збережено як PDF: Глава {ch}",
        "dl_log_waiting_extract": "Очікування завершення фонових задач розпаковки...",
        "dl_log_done": "Завантаження манхви «{title}» успішно завершено!",
        "dl_already_exists_title": "Главу вже завантажено",
        "dl_already_exists_msg": "Наступні глави вже існують у бібліотеці:\n{chapters}\n\nБажаєте завантажити їх повторно?",
        "dl_already_exists_redownload": "⚡ Завантажити повторно",
        "dl_already_exists_skip": "Пропустити існуючі",
        "dl_already_exists_cancel": "Скасувати",
        "dl_log_skipped_exists": "Глава {ch} вже існує. Пропуск.",
        "cat_tab_local": "📚 Локальна бібліотека",
        "cat_tab_cloud": "☁️ Хмарне сховище",
        "cloud_vault_title": "Хмарне сховище",
        "cloud_stream_read": "⚡ Читати онлайн",
        "cloud_empty": "☁️ У вашому хмарному сховищі поки немає збережених глав.",
        "cloud_sync_btn": "🔄 Оновити",
        "cloud_badge": "ХМАРА",
        "cloud_status_streaming": "⚡ Стрімінг у RAM (0 байт на диску)",
        "cloud_card_dl_btn": "📥 Завантажити",
        "cloud_card_dl_tooltip": "Завантажити PDF у локальну бібліотеку",
        "cloud_card_chs_word": "глав",
        "cloud_card_new": "Нова",
        "cloud_dl_dlg_title": "Завантажити PDF",
        "cloud_dl_dlg_header": "📥 Завантажити главу (PDF)",
        "cloud_dl_total_range": "Всього доступно глав у сховищі: {min_ch}–{max_ch} (всього {total})",
        "cloud_dl_total_count": "Всього доступно глав у сховищі: {total}",
        "cloud_dl_folder_lbl": "Куди зберегти (назва папки у Library):",
        "cloud_dl_range_lbl": "Номер або діапазон глав:",
        "cloud_dl_range_ph": "Наприклад: 1 або 1-10 або 1 2 3",
        "cloud_dl_btn": "📥 Завантажити PDF",
        "reader_cloud_dl_btn": "📥 Завантажити PDF",
        "notice_dl_success_title": "Завантаження завершено",
        "notice_dl_success_btn": "Чудово",
        "notice_dl_error_title": "Помилка завантаження",
        "notice_dl_error_btn": "Зрозуміло",
        "cloud_dl_no_chapters": "Не знайдено глав за фільтром '{range}'.",
        "cloud_dl_start_status": "📥 Розпочато завантаження {total} глав у бібліотеку «{folder}»...",
        "cloud_dl_chapter_status": "[{idx}/{total}] Завантаження Глави {ch}...",
        "cloud_dl_saved_pdf": "✓ Глава {ch} збережена як PDF.",
        "cloud_dl_finish_success": "Успішно завантажено {total} глав манхви «{folder}»!",
        "search_ph": "🔍 Пошук тайтлів...",
        "filter_lang_all": "Всі мови",
        "filter_lang_ua": "🇺🇦 UA",
        "filter_lang_en": "🇬🇧 EN",
        "filter_lang_raw": "🌐 RAW",
        "filter_prog_all": "Весь прогрес",
        "filter_prog_reading": "📖 Читаю",
        "filter_prog_completed": "✅ Прочитано",
        "filter_prog_unread": "⏳ Непочаті",
        "search_count_lbl": "Знайдено: {count}",
        "btn_translate_nav": "⚔️ Translate",
        "translate_not_found_title": "Модуль M_Translate не знайдено!",
        "translate_not_found_msg": "У вас немає встановленого модуля Translate. Перейдіть до нашого офіційного Telegram-каналу, щоб завантажити повноцінну версію додатку.",
        "telegram_open_btn": "✈️ Відкрити Telegram-канал",
        "other_translations_avail": "🌐 Доступні інші переклади:",
        "switch_trans_tip": "Перейти до {lang} версії: {title}"
    },
    "ru": {
        "app_title": "Manhwa Reader AI Drafter",
        "tab_catalog": "📚 Библиотека",
        "tab_reader": "📖 Читалка",
        "tab_downloader": "⚡ TG Загрузчик",
        "tab_settings": "⚙️ Настройки",
        "badge_engine": "🚀 STANDALONE WEBTOON ENGINE",
        "subtitle": "Автономный вебтун-плеер, автозакладки и быстрый загрузчик из Telegram",
        "fs_on": "⛶ На весь экран (F11)",
        "fs_off": "🗗 Свернуть (F11)",
        "hide_menu": "👁 Скрыть меню (H)",
        "show_menu": "👁 Показать меню (H)",
        "to_catalog": "← Библиотека",
        "lib_title": "Твоя библиотека",
        "refresh": "🔄 Обновить",
        "add_tg": "+ Загрузить из TG",
        "empty_lib": "📂 В библиотеке пока пусто.\nПерейдите во вкладку '⚡ TG Загрузчик', чтобы добавить манхву!",
        "read_btn": "▶ Читать",
        "del_tooltip": "Удалить манхву",
        "del_confirm_title": "Удалить манхву",
        "del_confirm_msg": "Вы действительно хотите удалить манхву:\n«{title}» ?",
        "del_confirm_sub": "Все скачанные главы, файлы и закладка будут полностью удалены с диска.",
        "cancel": "Отмена",
        "del_btn_action": "🗑️ Да, удалить",
        "select_manhwa": "Выберите манхву",
        "prev_ch": "◀ Предыдущая",
        "next_ch": "Следующая ▶",
        "chapter_prefix": "Глава",
        "width_lbl": "Ширина:",
        "zoom_lbl": "Зум:",
        "theme_lbl": "Фон:",
        "dl_title": "⚡ Загрузчик PDF-глав из Telegram",
        "dl_info_title": "📌 Как работает загрузчик:",
        "dl_info_desc": "Укажите ссылку на открытый канал (например, https://t.me/channel_name) или юзернейм (@channel_name). Программа найдет PDF-документы и сохранит их в библиотеку манхвы.",
        "dl_channel": "Канал (URL или @тег):",
        "dl_channel_ph": "https://t.me/channel_name или @channel_name",
        "dl_search": "Поисковое слово (фильтр):",
        "dl_search_ph": "Например: Название (или оставьте пустым для всех PDF)",
        "dl_range": "Номер или диапазон (напр. 2 или 1-30):",
        "dl_range_ph": "Например: 2 или 1-30 или 1 2 (пусто = все)",
        "dl_name": "Название тайтла в библиотеке:",
        "dl_name_ph": "Название папки манхвы в библиотеке",
        "dl_lang": "Язык перевода тайтла:",
        "dl_lang_auto": "Авто-определение",
        "dl_start": "🚀 Начать загрузку",
        "settings_title": "⚙️ Настройки программы",
        "lang_lbl": "Язык интерфейса:",
        "speed_lbl": "Скорость скролла клавишами:",
        "lib_lbl": "Папка библиотеки:",
        "save_btn": "💾 Сохранить настройки",
        "saved_msg": "Настройки успешно сохранены!",
        "auth_btn": "🤖 Токен Бота",
        "auth_ok": "🟢 Telegram Бот подключен",
        "auth_needed": "🟡 Требуется токен бота Telegram",
        "toggle_extract_jpeg_title": "Распаковывать в JPEG при загрузке",
        "toggle_extract_jpeg_sub": "Конвертирует PDF-файлы в галерею изображений во время скачивания",
        "toggle_novel_mode_title": "Новелла / Ранобэ (EPUB / DOCX / TXT)",
        "toggle_novel_mode_sub": "Сохранять текстовые главы в отдельную Библиотеку Новелл для чтения",
        "cat_tab_novels": "📖 Новеллы / Ранобэ",
        "toggle_del_pdf_title": "Удалять исходный PDF после распаковки",
        "toggle_del_pdf_sub": "Экономит место на диске после создания галереи JPEG",
        "read_in_jpeg": "🖼️ Читать в JPEG",
        "read_in_pdf": "📑 Читать в PDF",
        "manual_unpack_title": "📦 Ручная распаковка глав (PDF → JPEG)",
        "manual_unpack_sub": "Выберите манхву и главу из доступных PDF для конвертации в JPEG:",
        "manual_unpack_m_lbl": "Манхва:",
        "manual_unpack_ch_lbl": "Глава для распаковки:",
        "manual_unpack_btn": "⚡ Распаковать выбранную главу в JPEG",
        "status_only_pdf": "Только PDF",
        "status_has_jpeg": "Уже есть JPEG",
        "status_no_pdf": "Нет глав с PDF",
        "status_empty_m": "В библиотеке нет манхвы",
        "unpack_confirm_title": "Распаковка JPEG",
        "unpack_confirm_header": "⚡ Распаковка Главы {ch} в JPEG",
        "unpack_confirm_msg": "Страницы JPEG для этой главы ещё не распакованы.\nРаспаковать сейчас из имеющегося PDF-файла по нашей технологии?",
        "unpack_confirm_btn": "⚡ Распаковать в JPEG",
        "pdf_missing_title": "PDF недоступен",
        "pdf_missing_msg": "Исходный PDF-файл для главы {ch} был удален после распаковки или отсутствует.",
        "token_dlg_title": "Настройка Telegram Бота",
        "token_dlg_header": "🤖 Токен Telegram Бота для загрузки",
        "token_dlg_info": "Бот позволяет загружать главы без телефонов, SMS и паролей 2FA.\nВставьте сюда токен вашего бота из @BotFather. Он сохранится в config.json.",
        "token_dlg_lbl": "API Токен Бота:",
        "token_dlg_ph": "Например: 8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA",
        "token_save_btn": "💾 Сохранить токен",
        "token_saved_msg": "Токен успешно сохранен в config.json!",
        "token_ready_log": "🟢 Telegram Бот подключен! Можно загружать главы.",
        "ok_btn": "Понятно",
        "unpacking_progress": "Распаковка главы {num}...",
        "unpacking_success": "✓ Глава {num} успешно распакована ({count} страниц)!",
        "unpacking_error": "Ошибка распаковки: {err}",
        "select_pdf_first": "Выберите главу с имеющимся PDF!",
        "dl_err_no_channel": "Ошибка: введите ссылку на канал!",
        "dl_start_log": "Поиск и загрузка для: «{title}» (Главы: {range})...",
        "dl_all": "все",
        "log_success_tag": "[УСПЕХ]",
        "log_error_tag": "[ОШИБКА]",
        "dl_log_connecting": "Подключение к сервису Telegram через Бота...",
        "dl_log_searching": "Поиск PDF-глав в канале @{channel}...",
        "dl_log_found_count": "Найдено глав/файлов: {count}",
        "dl_log_total_to_download": "Будет загружено глав: {count}. Начинаем...",
        "dl_log_chapter_header": "[{idx}/{total}] Глава {ch}: {filename}",
        "dl_log_downloading": "Загрузка {filename} ({size} MB)...",
        "dl_log_downloaded": "Глава {ch} скачана! Параллельная распаковка в JPEG начата...",
        "dl_log_extracting": "Распаковка страниц для Главы {ch}...",
        "dl_log_extract_done": "✓ Глава {ch}: распаковка в JPEG завершена.",
        "dl_log_saved_pdf": "Сохранено как PDF: Глава {ch}",
        "dl_log_waiting_extract": "Ожидание завершения фоновых задач распаковки...",
        "dl_log_done": "Загрузка манхвы «{title}» успешно завершена!",
        "dl_already_exists_title": "Глава уже скачана",
        "dl_already_exists_msg": "Следующие главы уже существуют в библиотеке:\n{chapters}\n\nЖелаете скачать их повторно?",
        "dl_already_exists_redownload": "⚡ Скачать повторно",
        "dl_already_exists_skip": "Пропустить существующие",
        "dl_already_exists_cancel": "Отмена",
        "dl_log_skipped_exists": "Глава {ch} уже существует. Пропуск.",
        "cat_tab_local": "📚 Локальная библиотека",
        "cat_tab_cloud": "☁️ Облачное хранилище",
        "cloud_vault_title": "Облачное хранилище",
        "cloud_stream_read": "⚡ Читать онлайн",
        "cloud_empty": "☁️ В вашем облачном хранилище пока нет сохраненных глав.",
        "cloud_sync_btn": "🔄 Обновить",
        "cloud_badge": "ОБЛАКО",
        "cloud_status_streaming": "⚡ Стриминг в RAM (0 байт на диске)",
        "cloud_card_dl_btn": "📥 Скачать",
        "cloud_card_dl_tooltip": "Скачать PDF в локальную библиотеку",
        "cloud_card_chs_word": "глав",
        "cloud_card_new": "Новая",
        "cloud_dl_dlg_title": "Скачать PDF",
        "cloud_dl_dlg_header": "📥 Скачать главу (PDF)",
        "cloud_dl_total_range": "Всего доступно глав в хранилище: {min_ch}–{max_ch} (всего {total})",
        "cloud_dl_total_count": "Всего доступно глав в хранилище: {total}",
        "cloud_dl_folder_lbl": "Куда сохранить (название папки в Library):",
        "cloud_dl_range_lbl": "Номер или диапазон глав:",
        "cloud_dl_range_ph": "Например: 1 или 1-10 или 1 2 3",
        "cloud_dl_btn": "📥 Скачать PDF",
        "reader_cloud_dl_btn": "📥 Скачать PDF",
        "notice_dl_success_title": "Загрузка завершена",
        "notice_dl_success_btn": "Отлично",
        "notice_dl_error_title": "Ошибка загрузки",
        "notice_dl_error_btn": "Понятно",
        "cloud_dl_no_chapters": "Не найдено глав по фильтру '{range}'.",
        "cloud_dl_start_status": "📥 Начат процесс загрузки {total} глав в библиотеку «{folder}»...",
        "cloud_dl_chapter_status": "[{idx}/{total}] Загрузка Главы {ch}...",
        "cloud_dl_saved_pdf": "✓ Глава {ch} сохранена как PDF.",
        "cloud_dl_finish_success": "Успешно загружено {total} глав манхвы «{folder}»!",
        "search_ph": "🔍 Поиск тайтлов...",
        "filter_lang_all": "Все языки",
        "filter_lang_ua": "🇺🇦 UA",
        "filter_lang_en": "🇬🇧 EN",
        "filter_lang_raw": "🌐 RAW",
        "filter_prog_all": "Весь прогресс",
        "filter_prog_reading": "📖 Читаю",
        "filter_prog_completed": "✅ Прочитано",
        "filter_prog_unread": "⏳ Не начато",
        "search_count_lbl": "Найдено: {count}",
        "btn_translate_nav": "⚔️ Translate",
        "translate_not_found_title": "Модуль M_Translate не найден!",
        "translate_not_found_msg": "У вас не установлен модуль Translate. Перейдите в наш официальный Telegram-канал, чтобы скачать полную версию приложения.",
        "telegram_open_btn": "✈️ Открыть Telegram-канал",
        "other_translations_avail": "🌐 Доступны другие переводы:",
        "switch_trans_tip": "Перейти к {lang} версии: {title}"
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
        "language": "en",
        "delete_pdf_after_extract": True,
        "tg_api_id": 37560778,
        "tg_api_hash": "307da2f94fc6450afe139c91bcc59eaa",
        "tg_bot_token": DEFAULT_BOT_TOKEN,
        "bookmarks": {}
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    if not default_cfg.get("tg_bot_token"):
        default_cfg["tg_bot_token"] = DEFAULT_BOT_TOKEN
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


def normalize_search_text(text: str) -> str:
    """Lowercases, removes extra punctuation and symbols for fuzzy/partial matching."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r'[\'\"`_—–\-\(\)\[\]\{\}\.,:;!\\?]', ' ', t)
    return " ".join(t.split())


def matches_search_query(query: str, title: str, aliases: Optional[List[str]] = None, extra_tags: Optional[List[str]] = None) -> bool:
    """
    Checks if query matches title, any aliases, or extra tags in Ukrainian, English, Russian or romanized forms.
    Returns True if every token of query appears in at least one of the candidate names.
    """
    q_norm = normalize_search_text(query)
    if not q_norm:
        return True
    
    candidates = [title]
    if aliases:
        candidates.extend(aliases)
    if extra_tags:
        candidates.extend(extra_tags)
    
    cand_strings = [normalize_search_text(c) for c in candidates if c]
    joined_candidates = " ".join(cand_strings)
    
    # Check if whole normalized query is in joined candidates
    if q_norm in joined_candidates:
        return True
    
    # Or every token in query matches somewhere in candidates
    q_tokens = q_norm.split()
    return all(token in joined_candidates for token in q_tokens)



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
    background-color: #161922;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 9px;
    padding: 7px 12px;
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
    selection-background-color: #d97706;
}
QComboBox:hover {
    border: 1px solid #fbbf24;
}
QComboBox:on {
    border-color: #fbbf24;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #fbbf24;
    margin-right: 8px;
    margin-top: 2px;
}
QComboBox QAbstractItemView {
    background-color: #161922;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 8px;
    color: #ffffff;
    selection-background-color: #d97706;
    selection-color: #110d04;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
    color: #ffffff;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #d97706;
    color: #110d04;
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


COMBO_BOX_STYLESHEET = """
QComboBox {
    background-color: #121622;
    color: #F3F4F6;
    border: 1px solid rgba(255, 255, 255, 0.20);
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 700;
    font-size: 13px;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #F59E0B;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border-left: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #F59E0B;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #121622;
    color: #F3F4F6;
    border: 1.5px solid #F59E0B;
    border-radius: 8px;
    selection-background-color: #F59E0B;
    selection-color: #000000;
    outline: none;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    color: #F3F4F6;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #F59E0B;
    color: #000000;
    font-weight: bold;
}
"""


def apply_combo_style(combo: QComboBox):
    from PyQt6.QtWidgets import QListView
    combo.setView(QListView())
    combo.setStyleSheet(COMBO_BOX_STYLESHEET)


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
# Neon Toggle (Brawl Stars AI Drafter Mint/Red Style)
# ---------------------------------------------------------------------------
class NeoToggle(QFrame):
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, subtitle: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.title_text = title
        self.subtitle_text = subtitle
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.init_ui()
        self.update_appearance()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        self.indicator = QLabel(self)
        self.indicator.setFixedSize(26, 26)
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.indicator)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_lbl = QLabel(self.title_text, self)
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700;")
        text_layout.addWidget(self.title_lbl)

        if self.subtitle_text:
            self.sub_lbl = QLabel(self.subtitle_text, self)
            self.sub_lbl.setStyleSheet("font-size: 11px;")
            text_layout.addWidget(self.sub_lbl)
        else:
            self.sub_lbl = None

        layout.addLayout(text_layout)
        layout.addStretch()

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update_appearance()
            self.toggled.emit(self._checked)
        super().mousePressEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.EnabledChange:
            self.update_appearance()
            if not self.isEnabled():
                self.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        super().changeEvent(event)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, val: bool):
        if self._checked != val:
            self._checked = val
            self.update_appearance()
            self.toggled.emit(self._checked)

    def update_appearance(self):
        if not self.isEnabled():
            self.setStyleSheet("""
                NeoToggle {
                    background-color: rgba(20, 23, 30, 0.45);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                }
            """)
            self.indicator.setText("✕")
            self.indicator.setStyleSheet("""
                QLabel {
                    background-color: rgba(28, 32, 42, 0.5);
                    border: 1.5px solid #4b5563;
                    border-radius: 6px;
                    color: #6b7280;
                    font-size: 13px;
                    font-weight: 900;
                }
            """)
            self.title_lbl.setStyleSheet("color: #6b7280; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            if self.sub_lbl:
                self.sub_lbl.setStyleSheet("color: #4b5563; font-size: 11px; border: none; background: transparent;")
            return

        if self._checked:
            self.setStyleSheet("""
                NeoToggle {
                    background-color: rgba(10, 26, 24, 0.75);
                    border: 1px solid rgba(45, 212, 191, 0.45);
                    border-radius: 10px;
                }
                NeoToggle:hover {
                    border: 1px solid rgba(45, 212, 191, 0.75);
                    background-color: rgba(10, 26, 24, 0.90);
                }
            """)
            self.indicator.setText("✓")
            self.indicator.setStyleSheet("""
                QLabel {
                    background-color: rgba(10, 26, 24, 0.95);
                    border: 1.5px solid #2dd4bf;
                    border-radius: 6px;
                    color: #2dd4bf;
                    font-size: 15px;
                    font-weight: 900;
                }
            """)
            self.title_lbl.setStyleSheet("color: #5eead4; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            if self.sub_lbl:
                self.sub_lbl.setStyleSheet("color: #99f6e4; font-size: 11px; border: none; background: transparent;")
        else:
            self.setStyleSheet("""
                NeoToggle {
                    background-color: rgba(35, 12, 14, 0.75);
                    border: 1px solid rgba(239, 68, 68, 0.45);
                    border-radius: 10px;
                }
                NeoToggle:hover {
                    border: 1px solid rgba(239, 68, 68, 0.75);
                    background-color: rgba(35, 12, 14, 0.90);
                }
            """)
            self.indicator.setText("✕")
            self.indicator.setStyleSheet("""
                QLabel {
                    background-color: rgba(35, 12, 14, 0.95);
                    border: 1.5px solid #f87171;
                    border-radius: 6px;
                    color: #f87171;
                    font-size: 13px;
                    font-weight: 900;
                }
            """)
            self.title_lbl.setStyleSheet("color: #fca5a5; font-size: 13px; font-weight: 700; border: none; background: transparent;")
            if self.sub_lbl:
                self.sub_lbl.setStyleSheet("color: #fecaca; font-size: 11px; border: none; background: transparent;")

    def set_texts(self, title: str, subtitle: str = ""):
        self.title_text = title
        self.subtitle_text = subtitle
        self.title_lbl.setText(title)
        if self.sub_lbl:
            self.sub_lbl.setText(subtitle)



# ---------------------------------------------------------------------------
# Unpack Confirmation Dialog
# ---------------------------------------------------------------------------
class UnpackConfirmDialog(QDialog):
    def __init__(self, ch_num: int, t: dict = None, parent=None):
        super().__init__(parent)
        if t is None:
            t = TRANSLATIONS.get("uk")
        self.t = t
        self.setWindowTitle(t.get("unpack_confirm_title", "Розпакування JPEG"))
        self.setFixedSize(440, 220)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #141722;
                border: 1px solid rgba(251, 191, 36, 0.35);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        header_text = t.get("unpack_confirm_header", "⚡ Розпакування Глави {ch} в JPEG").format(ch=ch_num)
        title_lbl = QLabel(header_text)
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #fbbf24;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(t.get("unpack_confirm_msg", "Сторінки JPEG для цієї глави ще не розпаковані.\nРозпакувати зараз із наявного PDF-файлу за нашою технологією?"))
        msg_lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #f3f4f6; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        cancel_btn = QPushButton(t.get("cancel", "Скасувати"))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            background-color: #212636;
            color: #e5e7eb;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 9px;
            padding: 9px 16px;
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        unpack_btn = QPushButton(t.get("unpack_confirm_btn", "⚡ Розпакувати в JPEG"))
        unpack_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        unpack_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
            color: #110d04;
            font-weight: 700;
            font-size: 13px;
            border: none;
            border-radius: 9px;
            padding: 9px 16px;
        """)
        unpack_btn.clicked.connect(self.accept)
        btn_layout.addWidget(unpack_btn)

        layout.addLayout(btn_layout)


# ---------------------------------------------------------------------------
# Chapter Already Exists Dialog
# ---------------------------------------------------------------------------
class ChapterAlreadyExistsDialog(QDialog):
    """Small popup shown when requested chapters already exist locally."""
    def __init__(self, ch_list: list, t: dict = None, parent=None):
        super().__init__(parent)
        if t is None:
            t = TRANSLATIONS.get("uk")
        self.t = t
        self.result_choice = "cancel"  # "redownload", "skip", "cancel"

        self.setWindowTitle(t.get("dl_already_exists_title", "Главу вже завантажено"))
        self.setFixedSize(460, 240)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #141722;
                border: 1px solid rgba(251, 191, 36, 0.45);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title_lbl = QLabel(f"⚠️ {t.get('dl_already_exists_title', 'Главу вже завантажено')}")
        title_lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #fbbf24;")
        layout.addWidget(title_lbl)

        ch_str = ", ".join(str(c) for c in ch_list[:12])
        if len(ch_list) > 12:
            ch_str += f"... (+{len(ch_list) - 12})"

        msg_text = t.get(
            "dl_already_exists_msg",
            "Наступні глави вже існують у бібліотеці:\n{chapters}\n\nБажаєте завантажити їх повторно?"
        ).format(chapters=ch_str)

        msg_lbl = QLabel(msg_text)
        msg_lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #f3f4f6; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton(t.get("dl_already_exists_cancel", "Скасувати"))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            background-color: #212636;
            color: #9ca3af;
            font-weight: 600;
            font-size: 12px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 8px 14px;
        """)
        cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(cancel_btn)

        skip_btn = QPushButton(t.get("dl_already_exists_skip", "Пропустити існуючі"))
        skip_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        skip_btn.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            font-weight: 600;
            font-size: 12px;
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 8px;
            padding: 8px 14px;
        """)
        skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(skip_btn)

        redownload_btn = QPushButton(t.get("dl_already_exists_redownload", "⚡ Завантажити повторно"))
        redownload_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        redownload_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
            color: #110d04;
            font-weight: 700;
            font-size: 12px;
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
        """)
        redownload_btn.clicked.connect(self._on_redownload)
        btn_layout.addWidget(redownload_btn)

        layout.addLayout(btn_layout)

    def _on_cancel(self):
        self.result_choice = "cancel"
        self.reject()

    def _on_skip(self):
        self.result_choice = "skip"
        self.accept()

    def _on_redownload(self):
        self.result_choice = "redownload"
        self.accept()



# ---------------------------------------------------------------------------
# Notice Dialog (Dark card info popup)
# ---------------------------------------------------------------------------
class NoticeDialog(QDialog):
    def __init__(self, title: str, message: str, btn_text: str = "Зрозуміло", action_btn_text: Optional[str] = None, on_action_click=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(480, 240)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #12151f;
                border: 1.5px solid rgba(245, 158, 11, 0.55);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)

        hdr_row = QHBoxLayout()
        title_lbl = QLabel(f"⚠️ {title}")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #fbbf24;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-weight: 700;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #e5e7eb; line-height: 1.45;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        ok_btn = QPushButton(btn_text)
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2433;
                color: #cbd5e1;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 9px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #2a3347;
                color: #ffffff;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        if action_btn_text and on_action_click:
            act_btn = QPushButton(action_btn_text)
            act_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            act_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f59e0b, stop:1 #d97706);
                    color: #110d04;
                    font-weight: 800;
                    font-size: 13px;
                    border: none;
                    border-radius: 9px;
                    padding: 8px 20px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #b45309);
                }
            """)
            act_btn.clicked.connect(lambda: (on_action_click(), self.accept()))
            btn_layout.addWidget(act_btn)

        layout.addLayout(btn_layout)



# ---------------------------------------------------------------------------
# Floating Single Chapter PDF Download Dialog (Compact & Clean)
# ---------------------------------------------------------------------------
class SingleChapterDownloadDialog(QDialog):
    """
    Floating dialog to download chapter PDF(s) from cloud into local library.
    Allows specifying target folder name (manhwa title on PC) and chapter range.
    """
    download_requested = pyqtSignal(str, str, str)  # title_code, pc_folder_name, chapter_filter

    def __init__(self, title_code: str, title_info: dict, current_ch: int, lib_dir: Path, t: dict = None, parent=None):
        super().__init__(parent)
        self.title_code = title_code
        self.title_info = title_info
        self.current_ch = current_ch
        self.lib_dir = lib_dir
        self.t = t or TRANSLATIONS.get("uk")

        self.setWindowTitle(self.t.get("cloud_dl_dlg_title", "Завантажити PDF"))
        self.setFixedSize(460, 340)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #121622;
                border: 1px solid rgba(59, 130, 246, 0.45);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        # Header
        hdr_row = QHBoxLayout()
        full_name = title_info.get("title_name") or title_code
        hdr_lbl = QLabel(self.t.get("cloud_dl_dlg_header", "📥 Завантажити главу (PDF)"))
        hdr_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #60A5FA;")
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                font-weight: 700;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        layout.addLayout(hdr_row)

        # Total chapters info
        chapters_dict = title_info.get("chapters", {})
        sorted_chs = sorted([int(k) for k in chapters_dict.keys() if str(k).isdigit()])
        if sorted_chs:
            total_chs_text = self.t.get(
                "cloud_dl_total_range",
                "Всього доступно глав у сховищі: {min_ch}–{max_ch} (всього {total})"
            ).format(min_ch=min(sorted_chs), max_ch=max(sorted_chs), total=len(sorted_chs))
        else:
            total_chs_text = self.t.get(
                "cloud_dl_total_count",
                "Всього доступно глав у сховищі: {total}"
            ).format(total=len(chapters_dict))

        sub_info = QLabel(f"«{full_name}»\n{total_chs_text}")
        sub_info.setStyleSheet("font-size: 12px; color: #94A3B8; font-weight: 500; line-height: 1.3;")
        sub_info.setWordWrap(True)
        layout.addWidget(sub_info)

        # Input 1: Folder name on PC in library
        lbl_folder = QLabel(self.t.get("cloud_dl_folder_lbl", "Куди зберегти (назва папки у Library):"))
        lbl_folder.setStyleSheet("font-size: 13px; font-weight: 600; color: #E2E8F0;")
        layout.addWidget(lbl_folder)

        # Default folder name is title_name or sanitized code
        default_folder = title_info.get("title_name") or title_code
        self.folder_inp = QLineEdit(default_folder)
        self.folder_inp.setStyleSheet("""
            QLineEdit {
                background-color: #0B0E17;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border-color: #60A5FA;
            }
        """)
        layout.addWidget(self.folder_inp)

        # Input 2: Chapter number / range
        lbl_range = QLabel(self.t.get("cloud_dl_range_lbl", "Номер або діапазон глав:"))
        lbl_range.setStyleSheet("font-size: 13px; font-weight: 600; color: #E2E8F0;")
        layout.addWidget(lbl_range)

        self.ch_inp = QLineEdit(str(current_ch))
        self.ch_inp.setPlaceholderText(self.t.get("cloud_dl_range_ph", "Наприклад: 1 або 1-10 або 1 2 3"))
        self.ch_inp.setStyleSheet("""
            QLineEdit {
                background-color: #0B0E17;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border-color: #60A5FA;
            }
        """)
        layout.addWidget(self.ch_inp)

        layout.addStretch()

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = QPushButton(self.t.get("cancel", "Скасувати"))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F2433;
                color: #94A3B8;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 9px;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background-color: #2D3748;
                color: #FFFFFF;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        dl_btn = QPushButton(self.t.get("cloud_dl_btn", "📥 Завантажити PDF"))
        dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        dl_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1D4ED8);
                color: #FFFFFF;
                font-weight: 800;
                font-size: 13px;
                border: none;
                border-radius: 9px;
                padding: 9px 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #60A5FA, stop:1 #2563EB);
            }
        """)
        dl_btn.clicked.connect(self._on_start_download)
        btn_row.addWidget(dl_btn)

        layout.addLayout(btn_row)

    def _on_start_download(self):
        folder_name = self.folder_inp.text().strip() or self.title_code
        ch_filter = self.ch_inp.text().strip() or str(self.current_ch)
        self.download_requested.emit(self.title_code, folder_name, ch_filter)
        self.accept()


# ---------------------------------------------------------------------------
# Telegram Bot Token Dialog (No phone numbers, SMS or 2FA needed!)
# ---------------------------------------------------------------------------
class TelegramBotTokenDialog(QDialog):
    def __init__(self, cfg: dict, t: dict = None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        if t is None:
            t = TRANSLATIONS.get("uk")
        self.t = t
        self.setWindowTitle(t.get("token_dlg_title", "Налаштування Telegram Бота"))
        self.setFixedSize(530, 320)
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

        title = QLabel(t.get("token_dlg_header", "🤖 Токен Telegram Бота для завантаження"))
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #fbbf24;")
        layout.addWidget(title)

        info = QLabel(
            t.get("token_dlg_info",
                  "Бот дозволяє завантажувати глави без телефонів, SMS та паролів 2FA.\nВставте сюди токен вашого бота з @BotFather. Він збережеться в config.json.")
        )
        info.setStyleSheet("color: #9ca3af; font-size: 12px; line-height: 1.4;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel(t.get("token_dlg_lbl", "API Токен Бота:")))
        self.token_inp = QLineEdit(self.cfg.get("tg_bot_token", ""))
        self.token_inp.setPlaceholderText(t.get("token_dlg_ph", "Наприклад: 8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA"))
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
        cancel_btn = QPushButton(t.get("cancel", "Скасувати"))
        cancel_btn.setProperty("class", "btnSecondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(t.get("token_save_btn", "💾 Зберегти токен"))
        save_btn.setProperty("class", "btnAccent")
        save_btn.clicked.connect(self.save_token)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def save_token(self):
        tok = self.token_inp.text().strip()
        self.cfg["tg_bot_token"] = tok
        save_config(self.cfg)
        self.status_lbl.setText(self.t.get("token_saved_msg", "Токен успішно збережено в config.json!"))
        QTimer.singleShot(600, self.accept)

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

    def __init__(self, api_id: int, api_hash: str, channel: str, search_kw: str, range_str: str, title: str, lib_dir: Path, extract_to_jpeg: bool, del_pdf: bool, t: dict = None, force_redownload: bool = False, is_novel: bool = False, duplicate_mode: str = "newest"):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.channel = clean_channel_link(channel)
        self.search_kw = search_kw
        self.range_str = range_str.strip()
        self.title = title
        self.lib_dir = lib_dir
        self.extract_to_jpeg = extract_to_jpeg
        self.del_pdf = del_pdf
        self.t = t or TRANSLATIONS.get("uk")
        self.force_redownload = force_redownload
        self.is_novel = is_novel
        self.duplicate_mode = duplicate_mode  # "newest", "oldest", "all"

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._download_coro())
            msg_done = self.t.get("dl_log_done", "Завантаження манхви «{title}» успішно завершено!").format(title=self.title)
            self.finished_signal.emit(True, msg_done)
        except Exception as e:
            self.finished_signal.emit(False, str(e))
        finally:
            loop.close()

    async def _download_coro(self):
        cfg = load_config()
        bot_tok = cfg.get("tg_bot_token")
        downloader = TelegramManhwaDownloader(self.api_id, self.api_hash, bot_token=bot_tok)
        self.status_signal.emit(self.t.get("dl_log_connecting", "Підключення до сервісу Telegram через Бота..."))

        try:
            await downloader.connect()

            self.status_signal.emit(self.t.get("dl_log_searching", "Пошук PDF-глав у каналі @{channel}...").format(channel=self.channel))
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

            # Розумна фільтрація дублікатів (коли в каналі є стара і нова манхва або перезапуск)
            if self.duplicate_mode in ["newest", "oldest"] and filtered:
                ch_map = {}
                for it in filtered:
                    c = it.get("chapter", -1)
                    if c not in ch_map:
                        ch_map[c] = []
                    ch_map[c].append(it)

                deduped = []
                for c, group in ch_map.items():
                    if len(group) == 1 or c == -1:
                        deduped.extend(group)
                    else:
                        # Сортуємо групу за message.id
                        group.sort(key=lambda x: x["id"])
                        if self.duplicate_mode == "newest":
                            chosen = group[-1]  # Найновіший реліз
                            skipped = group[:-1]
                            deduped.append(chosen)
                            self.status_signal.emit(f"⚡ Глава {c}: обрано новіший файл «{chosen['filename']}» (пропущено старіші: {', '.join(s['filename'] for s in skipped)})")
                        elif self.duplicate_mode == "oldest":
                            chosen = group[0]   # Перший оригінальний
                            skipped = group[1:]
                            deduped.append(chosen)
                            self.status_signal.emit(f"📦 Глава {c}: обрано старіший файл «{chosen['filename']}» (пропущено новіші: {', '.join(s['filename'] for s in skipped)})")
                
                filtered = deduped
                filtered.sort(key=lambda x: (x["chapter"] if x["chapter"] != -1 else 999999, x["id"]))

            if not filtered:
                raise RuntimeError(f"Жодна глава не відповідає фільтру '{self.range_str}'. Знайдені глави: {[x.get('chapter') for x in items[:10]]}")

            if self.is_novel:
                novels_dir = self.lib_dir / "novels_library"
                novels_dir.mkdir(parents=True, exist_ok=True)
                target_dir = novels_dir / self.title
            else:
                target_dir = self.lib_dir / self.title
            target_dir.mkdir(parents=True, exist_ok=True)
            total = len(filtered)
            self.status_signal.emit(self.t.get("dl_log_total_to_download", "Буде завантажено глав: {count}. Розпочинаємо...").format(count=total))

            from concurrent.futures import ThreadPoolExecutor
            extractor_pool = ThreadPoolExecutor(max_workers=2) if self.extract_to_jpeg else None
            extraction_futures = []

            for idx, item in enumerate(filtered):
                ch_num = item.get("chapter", idx + 1)
                hdr = self.t.get("dl_log_chapter_header", "[{idx}/{total}] Глава {ch}: {filename}").format(
                    idx=idx + 1, total=total, ch=ch_num, filename=item['filename']
                )
                self.status_signal.emit(hdr)

                def sub_prog(p):
                    overall = (idx + p) / total
                    self.progress_signal.emit(overall)

                if self.extract_to_jpeg and extractor_pool:
                    ch_folder_name = f"chapter_{ch_num:03d}" if ch_num > 0 else f"chapter_msg_{item['id']}"
                    ch_dir = target_dir / ch_folder_name
                    ch_dir.mkdir(parents=True, exist_ok=True)
                    target_pdf = ch_dir / f"chapter_pdf_{ch_num:03d}.pdf"

                    existing_imgs = list(ch_dir.glob("*.jpg")) + list(ch_dir.glob("*.png"))
                    if not self.force_redownload and len(existing_imgs) > 2:
                        skip_msg = self.t.get("dl_log_skipped_exists", "Глава {ch} вже існує. Пропуск.").format(ch=ch_num)
                        self.status_signal.emit(f"{skip_msg} ({len(existing_imgs)} стор.)")
                        self.progress_signal.emit((idx + 1) / total)
                        continue

                    raw_dir = target_dir / ".temp_downloads"
                    raw_dir.mkdir(parents=True, exist_ok=True)
                    raw_file = raw_dir / item["filename"]

                    await downloader.client.download_media(
                        item["message"],
                        file=str(raw_file),
                        progress_callback=lambda cur, tot: sub_prog(cur / tot if tot > 0 else 0)
                    )

                    if raw_file.suffix.lower() == ".pdf":
                        import shutil
                        shutil.move(str(raw_file), str(target_pdf))

                        cover_p = target_dir / "cover.jpg"
                        if not cover_p.exists() and fitz:
                            try:
                                doc = fitz.open(str(target_pdf))
                                if len(doc) > 0:
                                    doc[0].get_pixmap(dpi=150).save(str(cover_p))
                                doc.close()
                            except Exception:
                                pass

                        self.status_signal.emit(self.t.get("dl_log_downloaded", "Глава {ch} завантажена! Паралельна розпаковка в JPEG розпочата...").format(ch=ch_num))

                        def run_extract(p_pdf, p_dir, c_num, d_pdf):
                            extract_chapter_pdf(
                                p_pdf,
                                p_dir,
                                delete_pdf=d_pdf,
                                progress_cb=lambda s: self.status_signal.emit(f"[{c_num}] {s}")
                            )
                            done_msg = self.t.get("dl_log_extract_done", "✓ Глава {ch}: розпаковку в JPEG завершено.").format(ch=c_num)
                            self.status_signal.emit(done_msg)

                        fut = extractor_pool.submit(run_extract, target_pdf, ch_dir, ch_num, self.del_pdf)
                        extraction_futures.append(fut)
                    else:
                        await downloader.download_chapter(
                            item, target_dir, extract_to_jpeg=True, delete_pdf=self.del_pdf,
                            status_cb=lambda s: self.status_signal.emit(s), progress_cb=sub_prog,
                            force_redownload=self.force_redownload
                        )
                else:
                    await downloader.download_chapter(
                        item,
                        target_dir,
                        extract_to_jpeg=False,
                        delete_pdf=False,
                        status_cb=lambda s: self.status_signal.emit(s),
                        progress_cb=sub_prog,
                        force_redownload=self.force_redownload
                    )

                self.progress_signal.emit((idx + 1) / total)

            if extractor_pool and extraction_futures:
                self.status_signal.emit(self.t.get("dl_log_waiting_extract", "Очікування завершення фонових задач розпаковки..."))
                for fut in extraction_futures:
                    fut.result()
                extractor_pool.shutdown()

        finally:
            await downloader.disconnect()


# ---------------------------------------------------------------------------
# Background Worker to Download Chapters from Cloud Vault to Local Library
# ---------------------------------------------------------------------------
class CloudDownloadWorker(QThread):
    progress_signal = pyqtSignal(float)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, stream_client: TelegramStreamClient, vault_target: Any, title_code: str, title_info: dict, pc_folder_name: str, range_str: str, lib_dir: Path, t: dict = None):
        super().__init__()
        self.stream_client = stream_client
        self.vault_target = vault_target
        self.title_code = title_code
        self.title_info = title_info
        self.pc_folder_name = pc_folder_name
        self.range_str = range_str
        self.lib_dir = lib_dir
        self.t = t or TRANSLATIONS.get("uk")
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            target_m_dir = self.lib_dir / self.pc_folder_name
            target_m_dir.mkdir(parents=True, exist_ok=True)

            chapters_dict = self.title_info.get("chapters", {})
            allowed_chapters = parse_chapter_filter(self.range_str)

            matching_chapters = []
            for ch_k, ch_val in chapters_dict.items():
                try:
                    c_num = int(ch_k)
                    msg_id = ch_val.get("vault_msg_id") or ch_val.get("message_id")
                    if not msg_id:
                        continue
                    if allowed_chapters is None or c_num in allowed_chapters:
                        matching_chapters.append((c_num, msg_id, ch_val))
                except Exception:
                    pass

            matching_chapters.sort(key=lambda x: x[0])

            if not matching_chapters:
                raise RuntimeError(self.t.get("cloud_dl_no_chapters", "Не знайдено глав за фільтром '{range}'.").format(range=self.range_str))

            total = len(matching_chapters)
            self.status_signal.emit(self.t.get("cloud_dl_start_status", "📥 Розпочато завантаження {total} глав у бібліотеку «{folder}»...").format(total=total, folder=self.pc_folder_name))

            for idx, (c_num, msg_id, c_meta) in enumerate(matching_chapters):
                if self._is_cancelled:
                    break

                self.status_signal.emit(self.t.get("cloud_dl_chapter_status", "[{idx}/{total}] Завантаження Глави {ch}...").format(idx=idx + 1, total=total, ch=c_num))

                def sub_prog(pct, cur, tot):
                    overall = (idx + pct) / total
                    self.progress_signal.emit(overall)

                data = self.stream_client.fetch_message_stream_sync(self.vault_target, msg_id, sub_prog)

                # Save directly as PDF into chapter folder
                ch_dir = target_m_dir / f"chapter_{c_num:03d}"
                ch_dir.mkdir(parents=True, exist_ok=True)
                pdf_target = ch_dir / f"chapter_pdf_{c_num:03d}.pdf"
                with open(pdf_target, "wb") as f:
                    f.write(data)

                # Generate cover.jpg if not present yet
                cover_p = target_m_dir / "cover.jpg"
                if not cover_p.exists() and fitz:
                    try:
                        doc = fitz.open(stream=data, filetype="pdf")
                        if len(doc) > 0:
                            doc[0].get_pixmap(dpi=150).save(str(cover_p))
                        doc.close()
                    except Exception:
                        pass

                self.progress_signal.emit((idx + 1) / total)
                self.status_signal.emit(self.t.get("cloud_dl_saved_pdf", "✓ Глава {ch} збережена як PDF.").format(ch=c_num))

            msg = self.t.get("cloud_dl_finish_success", "Успішно завантажено {total} глав манхви «{folder}»!").format(total=total, folder=self.pc_folder_name)
            self.finished_signal.emit(True, msg)
        except Exception as e:
            self.finished_signal.emit(False, str(e))


# ---------------------------------------------------------------------------
# Manhwa Card in Catalog
# ---------------------------------------------------------------------------
class ManhwaCard(QFrame):
    read_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    switch_translation_clicked = pyqtSignal(dict)  # item info dict with "type", "target", etc.

    def __init__(self, manhwa_name: str, manhwa_path: Path, bookmark_info: dict, lang_dict: dict, linked_translations: Optional[List[dict]] = None, parent=None):
        super().__init__(parent)
        self.manhwa_name = manhwa_name
        self.manhwa_path = manhwa_path
        self.bookmark_info = bookmark_info
        self.lang_dict = lang_dict
        self.linked_translations = linked_translations or []

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
        self.setFixedSize(260, 420)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.cover_lbl = QLabel()
        self.cover_lbl.setFixedHeight(210)
        self.cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_lbl.setStyleSheet("""
            background-color: #0c0e14;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        """)
        self.load_cover()
        layout.addWidget(self.cover_lbl)

        title_lbl = QLabel(self.manhwa_name)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #f3f4f6;")
        title_lbl.setWordWrap(True)
        title_lbl.setFixedHeight(38)
        layout.addWidget(title_lbl)

        ch_count = self.get_chapter_count()
        bm_text = "New" if self.lang_dict.get("cancel") == "Cancel" else "Нова"
        if self.bookmark_info:
            ch_num = self.bookmark_info.get("chapter", 1)
            pct = int(self.bookmark_info.get("chapter_progress", 0) * 100)
            bm_text = f"Ch. {ch_num} ({pct}%)"

        info_lbl = QLabel(f"📁 {ch_count}  •  🔖 {bm_text}")
        info_lbl.setStyleSheet("font-size: 11px; color: #9ca3af; font-weight: 500;")
        layout.addWidget(info_lbl)

        # Linked Translations Pills (if available)
        if self.linked_translations:
            pills_row = QHBoxLayout()
            pills_row.setContentsMargins(0, 0, 0, 0)
            pills_row.setSpacing(5)

            pills_badge = QLabel("🌐")
            pills_badge.setStyleSheet("font-size: 11px; color: #94a3b8;")
            pills_row.addWidget(pills_badge)

            for item in self.linked_translations:
                l_code = item.get("lang", "").upper()
                l_target = item.get("target") or item.get("title", "")
                pill_btn = QPushButton(l_code)
                pill_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                tip = self.lang_dict.get("switch_trans_tip", "Перейти до {lang} версії: {title}").format(
                    lang=l_code, title=item.get("title", l_target)
                )
                pill_btn.setToolTip(tip)
                pill_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(245, 158, 11, 0.15);
                        color: #fbbf24;
                        border: 1px solid rgba(245, 158, 11, 0.4);
                        border-radius: 5px;
                        padding: 1px 6px;
                        font-size: 10px;
                        font-weight: 800;
                    }
                    QPushButton:hover {
                        background-color: rgba(245, 158, 11, 0.35);
                        color: #ffffff;
                        border-color: #f59e0b;
                    }
                """)
                pill_btn.clicked.connect(lambda _, it=item: self.switch_translation_clicked.emit(it))
                pills_row.addWidget(pill_btn)

            pills_row.addStretch()
            layout.addLayout(pills_row)
        else:
            layout.addSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        read_btn = QPushButton(self.lang_dict["read_btn"])
        read_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        read_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
                color: #121008;
                font-size: 13px;
                font-weight: 800;
                border-radius: 9px;
                padding: 8px 12px;
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
                font-size: 14px;
                font-weight: 700;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 9px;
                padding: 7px 9px;
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
        chapter_nums = set()
        for p in self.manhwa_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                num = extract_chapter_number(p.name)
                if num is not None:
                    chapter_nums.add(num)
        for pdf_p in self.manhwa_path.glob("*.pdf"):
            num = extract_chapter_number(pdf_p.stem)
            if num is not None:
                chapter_nums.add(num)
        return len(chapter_nums)

    def load_cover(self):
        cover_path = self.manhwa_path / "cover.jpg"
        if not cover_path.exists():
            for img in self.manhwa_path.glob("**/*.jpg"):
                cover_path = img
                break

        if not cover_path or not cover_path.exists():
            for pdf_f in self.manhwa_path.glob("**/*.pdf"):
                if fitz:
                    try:
                        doc = fitz.open(str(pdf_f))
                        if len(doc) > 0:
                            cover_path = self.manhwa_path / "cover.jpg"
                            doc[0].get_pixmap(dpi=150).save(str(cover_path))
                        doc.close()
                        break
                    except Exception:
                        pass

        if cover_path and cover_path.exists():
            pm = QPixmap(str(cover_path))
            if not pm.isNull():
                scaled = pm.scaled(232, 210, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                rect = QRect((scaled.width() - 232) // 2, (scaled.height() - 210) // 2, 232, 210)
                self.cover_lbl.setPixmap(scaled.copy(rect))
                return

        self.cover_lbl.setText("📖\nCover")


# ---------------------------------------------------------------------------
# Cloud Manhwa Card (Streamable from Telegram Vault)
# ---------------------------------------------------------------------------
class CloudManhwaCard(QFrame):
    read_cloud_clicked = pyqtSignal(str)
    download_cloud_clicked = pyqtSignal(str)
    switch_translation_clicked = pyqtSignal(dict)  # item info dict with "type", "target", etc.

    def __init__(self, title: str, cloud_entry: dict, bookmark_info: dict, lang_dict: dict, linked_translations: Optional[List[dict]] = None, parent=None):
        super().__init__(parent)
        self.title = title
        self.cloud_entry = cloud_entry
        self.bookmark_info = bookmark_info
        self.lang_dict = lang_dict
        self.linked_translations = linked_translations or cloud_entry.get("linked_translations", [])

        self.setObjectName("cloudManhwaCard")
        self.setStyleSheet("""
            #cloudManhwaCard {
                background-color: rgba(18, 24, 38, 0.94);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 16px;
            }
            #cloudManhwaCard:hover {
                border: 1px solid rgba(59, 130, 246, 0.70);
                background-color: rgba(22, 30, 48, 0.98);
            }
        """)
        self.setFixedSize(270, 435)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # Top Badge: Cloud Stream
        badge_row = QHBoxLayout()
        badge_lbl = QLabel(f" ☁️ {self.lang_dict.get('cloud_badge', 'CLOUD')} ")
        badge_lbl.setFont(QFont("Segoe UI Black", 8))
        badge_lbl.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.20);
            color: #60A5FA;
            border: 1px solid rgba(59, 130, 246, 0.45);
            border-radius: 6px;
            padding: 2px 6px;
            font-weight: 800;
        """)
        badge_row.addWidget(badge_lbl)

        code = self.cloud_entry.get("code") or self.cloud_entry.get("title_code", "")
        lang = self.cloud_entry.get("lang", "")
        badge_text = f"[{code}]" if code else ""
        if lang:
            badge_text = f"{badge_text} [{lang}]" if badge_text else f"[{lang}]"
        if badge_text:
            code_lbl = QLabel(badge_text)
            code_lbl.setFont(QFont("Segoe UI Black", 8))
            code_lbl.setStyleSheet("color: #94A3B8; font-weight: 700;")
            badge_row.addWidget(code_lbl)

        badge_row.addStretch()
        layout.addLayout(badge_row)

        # Cover (Stylized cloud cover preview)
        self.cover_lbl = QLabel()
        self.cover_lbl.setFixedHeight(155)
        self.cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_lbl.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111827, stop:1 #1E293B);
            border-radius: 10px;
            border: 1px solid rgba(59, 130, 246, 0.2);
            color: #93C5FD;
            font-weight: 700;
            font-size: 13px;
        """)
        display_code = code or self.title
        self.cover_lbl.setText(f"☁️\n{display_code}\nONLINE")
        layout.addWidget(self.cover_lbl)

        self.full_title = self.cloud_entry.get("title_name") or self.title
        title_lbl = QLabel(self.full_title)
        title_lbl.setToolTip(self.full_title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F3F4F6;")
        title_lbl.setWordWrap(True)
        title_lbl.setFixedHeight(34)
        layout.addWidget(title_lbl)

        chapters = self.cloud_entry.get("chapters", {})
        ch_count = len(chapters)
        bm_text = self.lang_dict.get("cloud_card_new", "Нова")
        if self.bookmark_info:
            ch_num = self.bookmark_info.get("chapter", 1)
            pct = int(self.bookmark_info.get("chapter_progress", 0) * 100)
            bm_text = f"Ch. {ch_num} ({pct}%)"

        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        chs_word = self.lang_dict.get("cloud_card_chs_word", "глав")
        info_lbl = QLabel(f"☁️ {ch_count} {chs_word} • 🔖 {bm_text}")
        info_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 600;")
        info_row.addWidget(info_lbl)
        info_row.addStretch()
        layout.addLayout(info_row)

        # Action Buttons Row: Download PDF + Stream Read
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 2, 0, 0)
        actions_row.setSpacing(8)

        card_dl_btn = QPushButton(self.lang_dict.get("cloud_card_dl_btn", "📥 Завантажити"))
        card_dl_btn.setToolTip(self.lang_dict.get("cloud_card_dl_tooltip", "Завантажити PDF у локальну бібліотеку"))
        card_dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        card_dl_btn.setFixedHeight(32)
        card_dl_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.14);
                color: #60A5FA;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid rgba(59, 130, 246, 0.40);
                border-radius: 8px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.28);
                color: #93C5FD;
                border-color: #60A5FA;
            }
        """)
        card_dl_btn.clicked.connect(lambda: self.download_cloud_clicked.emit(self.title))
        actions_row.addWidget(card_dl_btn)

        read_btn = QPushButton(self.lang_dict.get("cloud_stream_read", "⚡ Читати онлайн"))
        read_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        read_btn.setFixedHeight(32)
        read_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1D4ED8);
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 800;
                border-radius: 8px;
                padding: 4px 12px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #60A5FA, stop:1 #2563EB);
            }
        """)
        read_btn.clicked.connect(lambda: self.read_cloud_clicked.emit(self.title))
        actions_row.addWidget(read_btn, stretch=1)
        layout.addLayout(actions_row)

        # Linked Translations Pills (if available)
        if self.linked_translations:
            pills_row = QHBoxLayout()
            pills_row.setContentsMargins(0, 0, 0, 0)
            pills_row.setSpacing(5)

            pills_badge = QLabel("🌐")
            pills_badge.setStyleSheet("font-size: 11px; color: #94a3b8;")
            pills_row.addWidget(pills_badge)

            for item in self.linked_translations:
                l_code = item.get("lang", "").upper()
                l_target = item.get("target") or item.get("title", "")
                pill_btn = QPushButton(l_code)
                pill_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                tip = self.lang_dict.get("switch_trans_tip", "Перейти до {lang} версії: {title}").format(
                    lang=l_code, title=item.get("title", l_target)
                )
                pill_btn.setToolTip(tip)
                pill_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(59, 130, 246, 0.18);
                        color: #60a5fa;
                        border: 1px solid rgba(59, 130, 246, 0.45);
                        border-radius: 5px;
                        padding: 1px 6px;
                        font-size: 10px;
                        font-weight: 800;
                    }
                    QPushButton:hover {
                        background-color: rgba(59, 130, 246, 0.35);
                        color: #ffffff;
                        border-color: #93c5fd;
                    }
                """)
                pill_btn.clicked.connect(lambda _, it=item: self.switch_translation_clicked.emit(it))
                pills_row.addWidget(pill_btn)

            pills_row.addStretch()
            layout.addLayout(pills_row)
        else:
            layout.addSpacing(2)


# ---------------------------------------------------------------------------
# Seamless Continuous Webtoon Strip
# ---------------------------------------------------------------------------
class WebtoonScrollCanvas(QScrollArea):
    scroll_progress_signal = pyqtSignal(int, float)
    mode_changed_signal = pyqtSignal(str)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.reading_width = cfg.get("reading_width", 880)
        self.zoom = cfg.get("zoom", 1.0)
        self.bg_color = cfg.get("bg_color", "#0f1115")

        self.current_manhwa_name = ""
        self.current_manhwa_path: Optional[Path] = None
        self.loaded_chapters: Set[int] = set()
        self.chapter_modes: Dict[int, str] = {}
        self.active_mode = "jpeg"
        self.page_labels: List[Tuple[int, QLabel, str]] = []
        self.pixmap_cache: Dict[str, QPixmap] = {}

        self.active_ch_num = 1
        self.is_restoring_scroll = False
        self.is_cloud_mode = False
        self.rolling_cache: Optional[RollingRAMCache] = None
        self.cloud_chapter_map: Dict[int, int] = {}

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

        # Cloud In-Memory Streaming Progress Box
        self.cloud_loading_frame = QFrame()
        self.cloud_loading_frame.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 12px;
                padding: 24px;
                margin: 40px;
            }
        """)
        cl_layout = QVBoxLayout(self.cloud_loading_frame)
        cl_layout.setSpacing(12)
        cl_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cloud_status_lbl = QLabel("☁️ Завантаження глави у пам'ять (RAM)...")
        self.cloud_status_lbl.setStyleSheet("color: #93C5FD; font-size: 15px; font-weight: 700;")
        self.cloud_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl_layout.addWidget(self.cloud_status_lbl)

        self.cloud_prog_bar = QProgressBar()
        self.cloud_prog_bar.setRange(0, 100)
        self.cloud_prog_bar.setValue(0)
        self.cloud_prog_bar.setTextVisible(True)
        self.cloud_prog_bar.setFixedWidth(360)
        self.cloud_prog_bar.setFixedHeight(18)
        self.cloud_prog_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1F2937;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 9px;
                text-align: center;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #60A5FA);
                border-radius: 8px;
            }
        """)
        cl_layout.addWidget(self.cloud_prog_bar, 0, Qt.AlignmentFlag.AlignCenter)

        self.cloud_bytes_lbl = QLabel("0.0 MB / 0.0 MB (0%)")
        self.cloud_bytes_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px;")
        self.cloud_bytes_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl_layout.addWidget(self.cloud_bytes_lbl)

        self.cloud_loading_frame.hide()

        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.strip_widget)
        self.main_layout.addWidget(self.cloud_loading_frame)
        self.main_layout.addStretch(1)

        self.setWidget(self.container)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def show_cloud_progress(self, ch_num: int, pct: float, cur_bytes: int, total_bytes: int):
        self.strip_widget.hide()
        self.cloud_loading_frame.show()
        c_mb = cur_bytes / (1024 * 1024)
        t_mb = total_bytes / (1024 * 1024) if total_bytes > 0 else 0
        self.cloud_status_lbl.setText(f"☁️ Стрімінг глави {ch_num} безпосередньо у RAM...")
        self.cloud_prog_bar.setValue(int(pct))
        if total_bytes > 0:
            self.cloud_bytes_lbl.setText(f"{c_mb:.1f} MB / {t_mb:.1f} MB ({int(pct)}%)")
        else:
            self.cloud_bytes_lbl.setText(f"{c_mb:.1f} MB завантажено...")

    def show_cloud_error(self, ch_num: int, err_msg: str):
        self.strip_widget.hide()
        self.cloud_loading_frame.show()
        self.cloud_status_lbl.setText(f"⚠️ Помилка завантаження глави {ch_num}")
        self.cloud_bytes_lbl.setText(str(err_msg))

    def hide_cloud_progress(self):
        self.cloud_loading_frame.hide()
        self.strip_widget.show()

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

    def get_chapter_resources(self, ch_num: int) -> Tuple[List[Path], Optional[Path]]:
        if not self.current_manhwa_path:
            return [], None

        target_dir = None
        for p in self.current_manhwa_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                if extract_chapter_number(p.name) == ch_num:
                    target_dir = p
                    break

        if not target_dir:
            target_dir = self.current_manhwa_path / f"chapter_{ch_num:03d}"

        imgs = []
        if target_dir.exists():
            imgs = sorted(
                list(target_dir.glob("*.jpg")) + list(target_dir.glob("*.png")) + list(target_dir.glob("*.webp")),
                key=lambda p: p.name
            )

        pdf_path = None
        if target_dir.exists():
            pdfs = list(target_dir.glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]

        if not pdf_path:
            for p in self.current_manhwa_path.glob("*.pdf"):
                if extract_chapter_number(p.stem) == ch_num:
                    pdf_path = p
                    break

        return imgs, pdf_path

    def load_manhwa_chapter(self, manhwa_path: Path, start_ch_num: int, restore_scroll_y: int = 0, preferred_mode: Optional[str] = None):
        self.current_manhwa_path = manhwa_path
        self.current_manhwa_name = manhwa_path.name
        self.active_ch_num = start_ch_num
        self.is_restoring_scroll = True
        if preferred_mode:
            self.active_mode = preferred_mode

        self.clear_canvas()
        self.append_chapter(start_ch_num)

        actual_mode = self.chapter_modes.get(start_ch_num, self.active_mode)
        self.active_mode = actual_mode
        self.mode_changed_signal.emit(actual_mode)

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
        self.chapter_modes.clear()
        self.pixmap_cache.clear()
        if self.rolling_cache:
            self.rolling_cache.clear_all()

    def load_cloud_stream_chapter(self, title: str, start_ch_num: int, pdf_bytes: bytes, chapter_map: dict, stream_client: TelegramStreamClient):
        self.is_cloud_mode = True
        self.current_manhwa_name = title
        self.current_manhwa_path = None
        self.active_ch_num = start_ch_num
        self.active_mode = "pdf"
        self.cloud_chapter_map = chapter_map

        if not self.rolling_cache:
            self.rolling_cache = RollingRAMCache(stream_client, None)
            self.rolling_cache.preload_finished_signal.connect(self._on_cloud_preload_finished)
        self.rolling_cache.set_chapter_map(chapter_map)

        self.clear_canvas()
        self.hide_cloud_progress()
        self.loaded_chapters.add(start_ch_num)
        self.chapter_modes[start_ch_num] = "pdf"

        target_w = int(self.reading_width * self.zoom)
        self.strip_widget.setFixedWidth(target_w)

        rendered_pages = self.rolling_cache.render_pdf_stream(start_ch_num, pdf_bytes, target_w=target_w)
        for idx, (pm, cache_key) in enumerate(rendered_pages):
            self.pixmap_cache[cache_key] = pm
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setContentsMargins(0, 0, 0, 0)
            lbl.setStyleSheet("border: none; padding: 0px; margin: 0px;")
            lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))
            self.strip_layout.addWidget(lbl)
            self.page_labels.append((start_ch_num, lbl, cache_key))

        self.verticalScrollBar().setValue(0)
        self.is_restoring_scroll = False
        self.mode_changed_signal.emit("pdf")

    def _on_cloud_preload_finished(self, next_ch: int):
        if next_ch in self.loaded_chapters or not self.rolling_cache:
            return
        self.loaded_chapters.add(next_ch)
        self.chapter_modes[next_ch] = "pdf"
        target_w = int(self.reading_width * self.zoom)

        divider = QLabel(f"━━━   CHAPTER {next_ch} [CLOUD STREAM]   ━━━")
        divider.setAlignment(Qt.AlignmentFlag.AlignCenter)
        divider.setStyleSheet("""
            color: #60a5fa;
            font-size: 14px;
            font-weight: 700;
            padding: 30px 0px 20px 0px;
            background: transparent;
        """)
        self.strip_layout.addWidget(divider)

        pages = self.rolling_cache.rendered_pages.get(next_ch, [])
        for idx, (pm, cache_key) in enumerate(pages):
            self.pixmap_cache[cache_key] = pm
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setContentsMargins(0, 0, 0, 0)
            lbl.setStyleSheet("border: none; padding: 0px; margin: 0px;")
            lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))
            self.strip_layout.addWidget(lbl)
            self.page_labels.append((next_ch, lbl, cache_key))

    def append_chapter(self, ch_num: int):
        if ch_num in self.loaded_chapters:
            return

        imgs, pdf_path = self.get_chapter_resources(ch_num)

        # Decide mode
        use_mode = "none"
        if self.active_mode == "pdf" and pdf_path:
            use_mode = "pdf"
        elif self.active_mode == "jpeg" and len(imgs) > 0:
            use_mode = "jpeg"
        elif len(imgs) > 0:
            use_mode = "jpeg"
        elif pdf_path:
            use_mode = "pdf"
        else:
            return

        self.loaded_chapters.add(ch_num)
        self.chapter_modes[ch_num] = use_mode

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

        if use_mode == "jpeg":
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

        elif use_mode == "pdf" and pdf_path:
            if not fitz:
                err_lbl = QLabel("PyMuPDF (fitz) не встановлено для читання PDF!")
                err_lbl.setStyleSheet("color: #f87171; padding: 20px; font-weight: 700;")
                self.strip_layout.addWidget(err_lbl)
                return

            try:
                doc = fitz.open(str(pdf_path))
                for idx, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=150)
                    fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
                    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
                    pm = QPixmap.fromImage(qimg.copy())

                    cache_key = f"pdf_{pdf_path.name}_{ch_num}_{idx}"
                    self.pixmap_cache[cache_key] = pm

                    lbl = QLabel()
                    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    lbl.setContentsMargins(0, 0, 0, 0)
                    lbl.setStyleSheet("border: none; padding: 0px; margin: 0px;")
                    lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))

                    self.strip_layout.addWidget(lbl)
                    self.page_labels.append((ch_num, lbl, cache_key))
                doc.close()
            except Exception as e:
                err_lbl = QLabel(f"Помилка відкриття PDF: {e}")
                err_lbl.setStyleSheet("color: #f87171; padding: 20px; font-weight: 700;")
                self.strip_layout.addWidget(err_lbl)

    def apply_saved_scroll(self, scroll_y: int):
        self.verticalScrollBar().setValue(scroll_y)
        self.is_restoring_scroll = False

    def _do_rescale(self):
        target_w = int(self.reading_width * self.zoom)
        self.strip_widget.setFixedWidth(target_w)

        self.strip_widget.setUpdatesEnabled(False)
        for ch_num, lbl, cache_key in self.page_labels:
            if cache_key not in self.pixmap_cache:
                self.pixmap_cache[cache_key] = QPixmap(cache_key)
            pm = self.pixmap_cache[cache_key]
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

        if self.is_cloud_mode and self.rolling_cache:
            self.rolling_cache.on_scroll_threshold_reached(self.active_ch_num, ratio)
        elif ratio >= self.cfg.get("auto_preload_threshold", 0.67):
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

        raw_lib = self.cfg.get("library_path", "library")
        candidate = Path(raw_lib)
        if candidate.is_absolute() and candidate.exists():
            self.lib_dir = candidate
        else:
            self.lib_dir = (BASE_DIR / candidate.name if candidate.name else BASE_DIR / "library").resolve()
        self.lib_dir.mkdir(parents=True, exist_ok=True)

        self.current_reading_manhwa = ""
        self.current_reading_chapter = 1
        self.is_zen_mode = False
        self.catalog_view_mode = "local"
        self.is_cloud_reading = False
        self.search_query = ""
        self.filter_lang = "ALL"
        self.filter_progress = "ALL"
        self.stream_client = TelegramStreamClient()
        self.current_cloud_worker: Optional[StreamDownloadThread] = None

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

        self.badge_lbl = QLabel(self.t["badge_engine"])
        self.badge_lbl.setStyleSheet("""
            color: #fbbf24;
            background-color: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.30);
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        title_box.addWidget(self.badge_lbl)

        title_lbl = QLabel("Manhwa Reader <span style='color: #fbbf24;'>AI Drafter</span>")
        title_lbl.setStyleSheet("font-size: 26px; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;")
        title_box.addWidget(title_lbl)

        self.sub_lbl = QLabel(self.t["subtitle"])
        self.sub_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        title_box.addWidget(self.sub_lbl)

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

        self.tab_translate_btn = QPushButton(self.t.get("btn_translate_nav", "⚔️ Translate"))
        self.tab_translate_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.tab_translate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #6d28d9);
                color: #ffffff;
                font-weight: 800;
                font-size: 13px;
                border: 1px solid rgba(167, 139, 250, 0.5);
                border-radius: 9px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a78bfa, stop:1 #7c3aed);
                border-color: #c4b5fd;
            }
        """)
        self.tab_translate_btn.clicked.connect(self.launch_overlay_translator)

        nav_layout.addWidget(self.tab_catalog_btn)
        nav_layout.addWidget(self.tab_reader_btn)
        nav_layout.addWidget(self.tab_downloader_btn)
        nav_layout.addWidget(self.tab_settings_btn)
        nav_layout.addWidget(self.tab_translate_btn)
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
    # -----------------------------------------------------------------------
    # TAB 0: CATALOG
    # -----------------------------------------------------------------------
    def create_catalog_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Top Bar: Title + Refresh + Add TG
        top_bar = QHBoxLayout()
        self.cat_title = QLabel(self.t["lib_title"])
        self.cat_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f3f4f6;")
        top_bar.addWidget(self.cat_title)
        top_bar.addStretch()

        self.refresh_btn = QPushButton(self.t["refresh"])
        self.refresh_btn.setProperty("class", "btnSecondary")
        self.refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_btn.clicked.connect(self.refresh_catalog)
        top_bar.addWidget(self.refresh_btn)

        self.add_btn = QPushButton(self.t["add_tg"])
        self.add_btn.setProperty("class", "btnAccent")
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.clicked.connect(lambda: self.switch_tab(2))
        top_bar.addWidget(self.add_btn)

        layout.addLayout(top_bar)

        # Segmented Controls Bar: Switcher (Local/Cloud) + Elegant Dark Fantasy Search Bar + Filter Dropdowns
        sub_bar = QHBoxLayout()
        sub_bar.setSpacing(10)

        self.btn_mode_local = QPushButton(self.t.get("cat_tab_local", "📚 Локальна бібліотека"))
        self.btn_mode_local.setCheckable(True)
        self.btn_mode_local.setChecked(True)
        self.btn_mode_local.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mode_local.setStyleSheet("""
            QPushButton {
                background-color: #121824;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border-color: #F59E0B;
                font-weight: 800;
            }
        """)
        self.btn_mode_local.clicked.connect(lambda: self.set_catalog_mode("local"))
        sub_bar.addWidget(self.btn_mode_local)

        self.btn_mode_cloud = QPushButton(self.t.get("cat_tab_cloud", "☁️ Моя Хмара Telegram"))
        self.btn_mode_cloud.setCheckable(True)
        self.btn_mode_cloud.setChecked(False)
        self.btn_mode_cloud.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mode_cloud.setStyleSheet("""
            QPushButton {
                background-color: #121824;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1D4ED8);
                color: #FFFFFF;
                border-color: #60A5FA;
                font-weight: 800;
            }
        """)
        self.btn_mode_cloud.clicked.connect(lambda: self.set_catalog_mode("cloud"))
        sub_bar.addWidget(self.btn_mode_cloud)

        self.btn_mode_novels = QPushButton(self.t.get("cat_tab_novels", "📖 Новели / Ранобе"))
        self.btn_mode_novels.setCheckable(True)
        self.btn_mode_novels.setChecked(False)
        self.btn_mode_novels.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_mode_novels.setStyleSheet("""
            QPushButton {
                background-color: #121824;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #047857);
                color: #FFFFFF;
                border-color: #34D399;
                font-weight: 800;
            }
        """)
        self.btn_mode_novels.clicked.connect(lambda: self.set_catalog_mode("novels"))
        self.btn_mode_novels.hide()  # Hidden by default until a novel is present
        sub_bar.addWidget(self.btn_mode_novels)

        # Elegant Dark Fantasy Real-Time Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.t.get("search_ph", "🔍 Пошук тайтлів..."))
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(15, 18, 26, 0.85);
                color: #ffffff;
                border: 1.5px solid rgba(245, 158, 11, 0.45);
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
                min-width: 220px;
            }
            QLineEdit:hover {
                border-color: rgba(245, 158, 11, 0.80);
                background-color: rgba(20, 24, 34, 0.95);
            }
            QLineEdit:focus {
                border: 1.5px solid #fbbf24;
                background-color: #141824;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        sub_bar.addWidget(self.search_input, 1)

        # Language Filter Dropdown
        self.filter_lang_combo = QComboBox()
        self._populate_lang_filter()
        apply_combo_style(self.filter_lang_combo)
        self.filter_lang_combo.currentIndexChanged.connect(self._on_filter_changed)
        sub_bar.addWidget(self.filter_lang_combo)

        # Reading Progress Filter Dropdown
        self.filter_prog_combo = QComboBox()
        self._populate_prog_filter()
        apply_combo_style(self.filter_prog_combo)
        self.filter_prog_combo.currentIndexChanged.connect(self._on_filter_changed)
        sub_bar.addWidget(self.filter_prog_combo)

        layout.addLayout(sub_bar)

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

    def _populate_lang_filter(self):
        self.filter_lang_combo.blockSignals(True)
        self.filter_lang_combo.clear()
        self.filter_lang_combo.addItem(self.t.get("filter_lang_all", "Всі мови"), "ALL")
        self.filter_lang_combo.addItem(self.t.get("filter_lang_ua", "🇺🇦 UA"), "UA")
        self.filter_lang_combo.addItem(self.t.get("filter_lang_en", "🇬🇧 EN"), "EN")
        self.filter_lang_combo.addItem(self.t.get("filter_lang_raw", "🌐 RAW"), "RAW")
        idx = self.filter_lang_combo.findData(self.filter_lang)
        if idx >= 0:
            self.filter_lang_combo.setCurrentIndex(idx)
        self.filter_lang_combo.blockSignals(False)

    def _populate_prog_filter(self):
        self.filter_prog_combo.blockSignals(True)
        self.filter_prog_combo.clear()
        self.filter_prog_combo.addItem(self.t.get("filter_prog_all", "Весь прогрес"), "ALL")
        self.filter_prog_combo.addItem(self.t.get("filter_prog_reading", "📖 Читаю"), "READING")
        self.filter_prog_combo.addItem(self.t.get("filter_prog_completed", "✅ Прочитано"), "COMPLETED")
        self.filter_prog_combo.addItem(self.t.get("filter_prog_unread", "⏳ Непочаті"), "UNREAD")
        idx = self.filter_prog_combo.findData(self.filter_progress)
        if idx >= 0:
            self.filter_prog_combo.setCurrentIndex(idx)
        self.filter_prog_combo.blockSignals(False)

    def _on_search_text_changed(self, text: str):
        self.search_query = text.strip()
        self.refresh_catalog()

    def _on_filter_changed(self):
        self.filter_lang = self.filter_lang_combo.currentData() or "ALL"
        self.filter_progress = self.filter_prog_combo.currentData() or "ALL"
        self.refresh_catalog()

    def set_catalog_mode(self, mode: str):
        self.catalog_view_mode = mode
        if mode == "local":
            self.btn_mode_local.setChecked(True)
            self.btn_mode_cloud.setChecked(False)
            if hasattr(self, "btn_mode_novels"):
                self.btn_mode_novels.setChecked(False)
            self.cat_title.setText(self.t["lib_title"])
        elif mode == "cloud":
            self.btn_mode_local.setChecked(False)
            self.btn_mode_cloud.setChecked(True)
            if hasattr(self, "btn_mode_novels"):
                self.btn_mode_novels.setChecked(False)
            self.cat_title.setText(self.t.get("cloud_vault_title", "Хмарне сховище"))
        elif mode == "novels":
            self.btn_mode_local.setChecked(False)
            self.btn_mode_cloud.setChecked(False)
            if hasattr(self, "btn_mode_novels"):
                self.btn_mode_novels.setChecked(True)
            self.cat_title.setText(self.t.get("cat_tab_novels", "📖 Новели / Ранобе"))
        self.refresh_catalog()

    def _get_cloud_index_data(self) -> dict:
        """Cached / safe access to cloud_index.json."""
        return load_cloud_index()

    def _resolve_linked_translations(self, title_key: str, cloud_titles: dict) -> List[dict]:
        """Resolves cross-language translations from cloud index and local library."""
        norm_key = normalize_search_text(title_key)
        for code, info in cloud_titles.items():
            candidates = [code, info.get("title_name", "")]
            candidates.extend(info.get("aliases", []))
            for cand in candidates:
                if normalize_search_text(cand) == norm_key or norm_key in normalize_search_text(cand) or normalize_search_text(cand) in norm_key:
                    return info.get("linked_translations", [])
        return []

    def _resolve_aliases(self, title_key: str, cloud_titles: dict) -> List[str]:
        """Returns aliases list for a given manhwa title from cloud index if present."""
        norm_key = normalize_search_text(title_key)
        for code, info in cloud_titles.items():
            candidates = [code, info.get("title_name", "")]
            candidates.extend(info.get("aliases", []))
            for cand in candidates:
                if normalize_search_text(cand) == norm_key or norm_key in normalize_search_text(cand) or normalize_search_text(cand) in norm_key:
                    return info.get("aliases", [])
        return []

    def _matches_progress(self, bm: dict, total_chapters: int) -> bool:
        if self.filter_progress == "ALL":
            return True
        if total_chapters <= 0:
            return self.filter_progress == "UNREAD"
        if not bm:
            return self.filter_progress == "UNREAD"

        ch_num = bm.get("chapter", 0)
        prog = bm.get("chapter_progress", 0.0)

        if self.filter_progress == "UNREAD":
            return ch_num <= 1 and prog < 0.05
        elif self.filter_progress == "COMPLETED":
            return ch_num >= total_chapters and prog >= 0.85
        elif self.filter_progress == "READING":
            is_unread = (ch_num <= 1 and prog < 0.05)
            is_completed = (ch_num >= total_chapters and prog >= 0.85)
            return not is_unread and not is_completed
        return True

    def _matches_lang(self, title_name: str, item_lang: Optional[str] = None) -> bool:
        if self.filter_lang == "ALL":
            return True
        fl = self.filter_lang.upper()

        if item_lang:
            norm_item = item_lang.strip().upper()
            if fl in norm_item:
                return True

        t_upper = title_name.upper()
        if fl == "UA" and ("[UA]" in t_upper or "(UA)" in t_upper or re.search(r'[а-яіїєґ]', title_name, re.I)):
            return True
        if fl == "EN" and ("[EN]" in t_upper or "(EN)" in t_upper or not re.search(r'[а-яіїєґ]', title_name, re.I)):
            return True
        if fl == "RAW" and ("[RAW]" in t_upper or "(RAW)" in t_upper or "RAW" in t_upper):
            return True
        return False

    def on_switch_translation(self, trans_item: dict):
        """Switches view to the target translation."""
        t_type = trans_item.get("type", "local")
        target = trans_item.get("target") or trans_item.get("title", "")
        if t_type == "cloud":
            if self.catalog_view_mode != "cloud":
                self.set_catalog_mode("cloud")
            self.search_input.setText(target)
        else:
            if self.catalog_view_mode != "local":
                self.set_catalog_mode("local")
            self.search_input.setText(target)

    def refresh_catalog(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Check if any novels exist in novels_library or library/Novels*
        has_novels = self._has_any_novels()
        if hasattr(self, "btn_mode_novels"):
            self.btn_mode_novels.setVisible(has_novels)

        if getattr(self, "catalog_view_mode", "local") == "cloud":
            self.refresh_cloud_catalog()
            return
        elif getattr(self, "catalog_view_mode", "local") == "novels":
            self.refresh_novels_catalog()
            return

        manhwas = [
            p for p in self.lib_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
            and p.name != "novels_library"
            and not p.name.lower().startswith("novel")
        ]

        if not manhwas:
            empty_lbl = QLabel(self.t["empty_lib"])
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #9ca3af; font-size: 15px; padding: 60px;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)
            return

        cols = max(1, self.width() // 280)
        bookmarks = self.cfg.get("bookmarks", {})
        cloud_data = self._get_cloud_index_data()
        cloud_titles = cloud_data.get("titles", {})

        displayed_count = 0
        for m_path in manhwas:
            m_name = m_path.name
            aliases = self._resolve_aliases(m_name, cloud_titles)

            # Search query matching
            if self.search_query:
                if not matches_search_query(self.search_query, m_name, aliases):
                    continue

            # Calculate chapter count for progress filter
            temp_card = ManhwaCard(m_name, m_path, {}, self.t)
            total_chs = temp_card.get_chapter_count()
            temp_card.deleteLater()

            bm = bookmarks.get(m_name, {})
            if not self._matches_progress(bm, total_chs):
                continue

            if not self._matches_lang(m_name, None):
                continue

            linked_trans = self._resolve_linked_translations(m_name, cloud_titles)
            card = ManhwaCard(m_name, m_path, bm, self.t, linked_translations=linked_trans)
            card.read_clicked.connect(self.open_manhwa_reader)
            card.delete_clicked.connect(self.confirm_delete_manhwa)
            card.switch_translation_clicked.connect(self.on_switch_translation)

            row = displayed_count // cols
            col = displayed_count % cols
            self.cards_grid.addWidget(card, row, col)
            displayed_count += 1

        if displayed_count == 0 and manhwas:
            empty_lbl = QLabel(f"🔍 {self.t.get('cloud_empty', 'Не знайдено тайтлів за запитом.')}")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #fbbf24; font-size: 15px; padding: 60px; font-weight: 600;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)

    def refresh_cloud_catalog(self):
        cloud_data = self._get_cloud_index_data()
        titles = cloud_data.get("titles", {})

        if not titles:
            empty_lbl = QLabel(self.t.get("cloud_empty", "☁️ У вашому хмарному сховищі поки немає збережених глав."))
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #93C5FD; font-size: 15px; padding: 60px;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)
            return

        cols = max(1, self.width() // 280)
        bookmarks = self.cfg.get("bookmarks", {})

        displayed_count = 0
        for title, info in titles.items():
            full_title = info.get("title_name") or title
            aliases = info.get("aliases", [])

            # Search query matching
            if self.search_query:
                if not matches_search_query(self.search_query, full_title, aliases + [title]):
                    continue

            chapters = info.get("chapters", {})
            total_chs = len(chapters)
            bm = bookmarks.get(title, {})

            if not self._matches_progress(bm, total_chs):
                continue

            item_lang = info.get("lang")
            if not self._matches_lang(full_title, item_lang):
                continue

            linked_trans = info.get("linked_translations", [])
            card = CloudManhwaCard(title, info, bm, self.t, linked_translations=linked_trans)
            card.read_cloud_clicked.connect(self.open_cloud_manhwa_reader)
            card.download_cloud_clicked.connect(self.open_cloud_download_dialog)
            card.switch_translation_clicked.connect(self.on_switch_translation)

            row = displayed_count // cols
            col = displayed_count % cols
            self.cards_grid.addWidget(card, row, col)
    def _has_any_novels(self) -> bool:
        """Checks if there are any novels downloaded locally."""
        novels_dir = self.lib_dir / "novels_library"
        if novels_dir.exists() and any(novels_dir.iterdir()):
            return True
        for p in self.lib_dir.iterdir():
            if p.is_dir() and "novel" in p.name.lower():
                return True
        return False

    def refresh_novels_catalog(self):
        """Renders novel/light novel cards in catalog."""
        novels_dir = self.lib_dir / "novels_library"
        candidate_dirs = []
        if novels_dir.exists():
            candidate_dirs.extend([p for p in novels_dir.iterdir() if not p.name.startswith(".")])
        for p in self.lib_dir.iterdir():
            if p.is_dir() and "novel" in p.name.lower() and p != novels_dir:
                candidate_dirs.append(p)

        if not candidate_dirs:
            empty_lbl = QLabel("📖 У Бібліотеці Новел поки що немає тайтлів.\nЗавантажте розділи через '⚡ TG Downloader' з галочкою 'Новела / Ранобе'.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #34D399; font-size: 15px; padding: 60px; font-weight: 600;")
            self.cards_grid.addWidget(empty_lbl, 0, 0)
            return

        cols = max(1, self.width() // 280)
        bookmarks = self.cfg.get("bookmarks", {})

        displayed_count = 0
        for n_path in candidate_dirs:
            n_name = n_path.name
            if self.search_query and self.search_query.lower() not in n_name.lower():
                continue

            bm = bookmarks.get(n_name, {})
            card = ManhwaCard(n_name, n_path, bm, self.t)
            card.read_clicked.connect(lambda name, p=n_path: self.open_novel_reader(name, p))
            card.delete_clicked.connect(self.confirm_delete_manhwa)

            row = displayed_count // cols
            col = displayed_count % cols
            self.cards_grid.addWidget(card, row, col)
            displayed_count += 1

    def open_novel_reader(self, novel_name: str, novel_path: Path):
        """Opens dedicated embedded Novel Reader inside the same window."""
        if not hasattr(self, "novel_reader_widget") or self.novel_reader_widget is None:
            if NovelReaderWindow is not None:
                self.novel_reader_widget = NovelReaderWindow(self, t=self.t)
                self.novel_reader_widget.back_to_library_requested.connect(lambda: self.switch_tab(0))
                self.novel_reader_widget.progress_changed.connect(self._on_novel_progress_changed)
                self.stack.addWidget(self.novel_reader_widget)
            else:
                err_title = self.t.get("log_error_tag", "Error").strip("[]")
                NoticeDialog(
                    err_title,
                    self.t.get("novel_load_err", "Failed to load novel reader module."),
                    btn_text=self.t.get("ok_btn", "OK"),
                    parent=self
                ).exec()
                return

        if hasattr(self.novel_reader_widget, "set_translations"):
            self.novel_reader_widget.set_translations(self.t)
        self.novel_reader_widget.load_novel(novel_path, novel_name)
        # Switch to the novel reader page in stack
        self.stack.setCurrentWidget(self.novel_reader_widget)

    def _on_novel_progress_changed(self, novel_name: str, ch_idx: int, percent: float):
        if "bookmarks" not in self.cfg:
            self.cfg["bookmarks"] = {}
        self.cfg["bookmarks"][novel_name] = {
            "chapter": ch_idx + 1,
            "chapter_progress": percent / 100.0,
            "scroll_y": 0
        }
        save_config(self.cfg)

    def open_cloud_download_dialog(self, title_code: Optional[str] = None):
        code = title_code or self.current_reading_manhwa
        if not code:
            return

        cloud_data = load_cloud_index()
        title_info = cloud_data.get("titles", {}).get(code, {})
        current_ch = self.canvas.active_ch_num if self.is_cloud_reading else 1

        dlg = SingleChapterDownloadDialog(code, title_info, current_ch, self.lib_dir, t=self.t, parent=self)
        dlg.download_requested.connect(self.run_cloud_download)
        dlg.exec()

    def run_cloud_download(self, title_code: str, pc_folder_name: str, ch_filter: str):
        cloud_data = load_cloud_index()
        title_info = cloud_data.get("titles", {}).get(title_code, {})
        vault_target = cloud_data.get("vault_channel_id") or cloud_data.get("vault_channel", -1004386061072)

        self.cloud_dl_worker = CloudDownloadWorker(
            self.stream_client, vault_target, title_code, title_info, pc_folder_name, ch_filter, self.lib_dir, t=self.t
        )

        def _on_status(msg):
            if hasattr(self, "dl_log"):
                self.dl_log.append(f"• {msg}")
            if self.is_cloud_reading:
                self.reader_title_lbl.setText(f"📥 {msg[:35]}")

        def _on_finished(ok, msg):
            if hasattr(self, "dl_log"):
                tag = self.t.get("log_success_tag", "[УСПІХ]") if ok else self.t.get("log_error_tag", "[ПОМИЛКА]")
                self.dl_log.append(f"\n{tag} {msg}")
            if ok:
                self.refresh_catalog()
                NoticeDialog(
                    self.t.get("notice_dl_success_title", "Завантаження завершено"),
                    msg,
                    btn_text=self.t.get("notice_dl_success_btn", "Чудово"),
                    parent=self
                ).exec()
            else:
                NoticeDialog(
                    self.t.get("notice_dl_error_title", "Помилка завантаження"),
                    msg,
                    btn_text=self.t.get("notice_dl_error_btn", "Зрозуміло"),
                    parent=self
                ).exec()

        self.cloud_dl_worker.status_signal.connect(_on_status)
        self.cloud_dl_worker.finished_signal.connect(_on_finished)
        self.cloud_dl_worker.start()

    def open_cloud_manhwa_reader(self, title: str, force_ch: Optional[int] = None):
        self.current_reading_manhwa = title
        self.is_cloud_reading = True
        self.mode_toggle_btn.setText(self.t.get("reader_cloud_dl_btn", "📥 Завантажити PDF"))
        self.mode_toggle_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #1D4ED8);
                border: 1px solid #60A5FA;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 5px 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #2563EB);
                border-color: #93C5FD;
            }
        """)

        cloud_data = load_cloud_index()
        title_info = cloud_data.get("titles", {}).get(title, {})
        chapters_dict = title_info.get("chapters", {})

        ch_map = {}
        for ch_k, ch_val in chapters_dict.items():
            try:
                ch_num = int(ch_k)
                msg_id = ch_val.get("vault_msg_id") or ch_val.get("message_id")
                ch_map[ch_num] = msg_id
            except Exception:
                pass

        sorted_chapters = sorted(list(ch_map.keys()))
        if not sorted_chapters:
            sorted_chapters = [1]

        ch_word = "Ch." if self.lang == "en" else "Глава"
        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()
        for c_num in sorted_chapters:
            self.chapter_combo.addItem(f"{ch_word} {c_num} [☁️]", c_num)
        self.chapter_combo.blockSignals(False)

        bm = self.cfg.get("bookmarks", {}).get(title, {})
        start_ch = force_ch or bm.get("chapter", sorted_chapters[0])

        idx = self.chapter_combo.findData(start_ch)
        if idx >= 0:
            self.chapter_combo.blockSignals(True)
            self.chapter_combo.setCurrentIndex(idx)
            self.chapter_combo.blockSignals(False)

        full_name = title_info.get("title_name") or title
        self.reader_title_lbl.setText(f"☁️ {full_name}")
        self.switch_tab(1)

        self.load_cloud_chapter(title, start_ch)

    def load_cloud_chapter(self, title: str, ch_num: int):
        cloud_data = load_cloud_index()
        title_info = cloud_data.get("titles", {}).get(title, {})
        chapters_dict = title_info.get("chapters", {})

        ch_map = {}
        for ch_k, ch_val in chapters_dict.items():
            try:
                c_n = int(ch_k)
                ch_map[c_n] = ch_val.get("vault_msg_id") or ch_val.get("message_id")
            except Exception:
                pass

        target_msg_id = ch_map.get(ch_num)
        target_vault = cloud_data.get("vault_channel_id") or cloud_data.get("vault_channel", "https://t.me/+O6mlGVWzTSQ5MjVi")
        full_name = title_info.get("title_name") or title

        # Cancel any previous active cloud download worker to avoid crashes
        if self.current_cloud_worker and self.current_cloud_worker.isRunning():
            try:
                self.current_cloud_worker.cancel()
                self.current_cloud_worker.quit()
                self.current_cloud_worker.wait(300)
            except Exception:
                pass

        if not target_msg_id:
            self.canvas.show_cloud_error(ch_num, f"Главу {ch_num} не знайдено в хмарному сховищі.")
            return

        self.canvas.show_cloud_progress(ch_num, 0.0, 0, 0)
        self.reader_title_lbl.setText(f"☁️ {full_name} — Глава {ch_num} (RAM стрімінг)")

        worker = StreamDownloadThread(self.stream_client, target_vault, ch_num, target_msg_id)
        self.current_cloud_worker = worker

        def _on_progress(c_n, pct, cur, tot):
            if c_n == ch_num:
                self.canvas.show_cloud_progress(c_n, pct, cur, tot)

        def _on_loaded(c_n, data):
            if c_n == ch_num:
                self.reader_title_lbl.setText(f"☁️ {full_name} — Ch. {ch_num}")
                self.canvas.load_cloud_stream_chapter(title, c_n, data, ch_map, self.stream_client)

        def _on_error(c_n, err):
            if c_n == ch_num:
                self.reader_title_lbl.setText(f"⚠️ Помилка: {err[:30]}")
                self.canvas.show_cloud_error(c_n, err)

        worker.progress_signal.connect(_on_progress)
        worker.finished_signal.connect(_on_loaded)
        worker.error_signal.connect(_on_error)
        worker.start()

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
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(6)

        self.back_btn = QPushButton(self.t["to_catalog"])
        self.back_btn.setProperty("class", "btnSecondary")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.clicked.connect(lambda: self.switch_tab(0))
        tb_layout.addWidget(self.back_btn)

        self.reader_title_lbl = QLabel(self.t["select_manhwa"])
        self.reader_title_lbl.setStyleSheet("font-weight: 700; font-size: 14px; color: #fbbf24;")
        self.reader_title_lbl.setMaximumWidth(220)
        tb_layout.addWidget(self.reader_title_lbl)

        tb_layout.addStretch()

        self.prev_ch_btn = QPushButton("◀")
        self.prev_ch_btn.setToolTip(self.t["prev_ch"])
        self.prev_ch_btn.setFixedSize(28, 28)
        self.prev_ch_btn.setProperty("class", "btnSecondary")
        self.prev_ch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prev_ch_btn.clicked.connect(self.prev_chapter)
        tb_layout.addWidget(self.prev_ch_btn)

        self.chapter_combo = QComboBox()
        self.chapter_combo.setFixedWidth(110)
        apply_combo_style(self.chapter_combo)
        self.chapter_combo.currentIndexChanged.connect(self.on_chapter_combo_change)
        tb_layout.addWidget(self.chapter_combo)

        self.next_ch_btn = QPushButton("▶")
        self.next_ch_btn.setToolTip(self.t["next_ch"])
        self.next_ch_btn.setFixedSize(28, 28)
        self.next_ch_btn.setProperty("class", "btnSecondary")
        self.next_ch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_ch_btn.clicked.connect(self.next_chapter)
        tb_layout.addWidget(self.next_ch_btn)

        # Mode toggle button (PDF <-> JPEG)
        self.mode_toggle_btn = QPushButton(self.t["read_in_jpeg"])
        self.mode_toggle_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.mode_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a202e;
                border: 1px solid rgba(251, 191, 36, 0.45);
                color: #fbbf24;
                font-weight: 700;
                font-size: 12px;
                padding: 5px 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(251, 191, 36, 0.18);
                border-color: #fbbf24;
            }
        """)
        self.mode_toggle_btn.clicked.connect(self.toggle_reader_mode)
        tb_layout.addWidget(self.mode_toggle_btn)

        self.width_lbl = QLabel(self.t["width_lbl"])
        tb_layout.addWidget(self.width_lbl)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(600, 1400)
        self.width_slider.setValue(self.cfg.get("reading_width", 880))
        self.width_slider.setFixedWidth(75)
        self.width_slider.valueChanged.connect(self.on_width_slider_change)
        tb_layout.addWidget(self.width_slider)

        zoom_minus = QPushButton("－")
        zoom_minus.setFixedSize(26, 26)
        zoom_minus.setProperty("class", "btnSecondary")
        zoom_minus.clicked.connect(lambda: self.adjust_zoom(-0.1))
        tb_layout.addWidget(zoom_minus)

        self.zoom_lbl = QLabel(f"{int(self.cfg.get('zoom', 1.0) * 100)}%")
        self.zoom_lbl.setStyleSheet("font-weight: 600; color: #9ca3af; min-width: 36px;")
        tb_layout.addWidget(self.zoom_lbl)

        zoom_plus = QPushButton("＋")
        zoom_plus.setFixedSize(26, 26)
        zoom_plus.setProperty("class", "btnSecondary")
        zoom_plus.clicked.connect(lambda: self.adjust_zoom(0.1))
        tb_layout.addWidget(zoom_plus)

        self.theme_lbl = QLabel(self.t["theme_lbl"])
        tb_layout.addWidget(self.theme_lbl)
        bg_grp = QHBoxLayout()
        bg_grp.setSpacing(4)
        for hex_col in ["#0f1115", "#000000", "#181b23"]:
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_col};
                    border: 2px solid rgba(255, 255, 255, 0.25);
                    border-radius: 9px;
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
        self.canvas.mode_changed_signal.connect(self.on_reader_mode_changed)
        layout.addWidget(self.canvas, 1)

        return widget

    def on_reader_mode_changed(self, mode: str):
        if self.is_cloud_reading:
            self.mode_toggle_btn.setText(self.t.get("reader_cloud_dl_btn", "📥 Завантажити PDF"))
            return
        if mode == "pdf":
            self.mode_toggle_btn.setText(self.t["read_in_jpeg"])
        else:
            self.mode_toggle_btn.setText(self.t["read_in_pdf"])

    def toggle_reader_mode(self):
        if not self.current_reading_manhwa:
            return
        if self.is_cloud_reading:
            self.open_cloud_download_dialog(self.current_reading_manhwa)
            return

        ch_num = self.canvas.active_ch_num
        m_path = self.lib_dir / self.current_reading_manhwa
        current_mode = self.canvas.active_mode

        imgs, pdf_path = self.canvas.get_chapter_resources(ch_num)

        if current_mode == "pdf":
            # User wants to read in JPEG!
            if len(imgs) > 0:
                curr_scroll = self.canvas.verticalScrollBar().value()
                self.canvas.load_manhwa_chapter(m_path, ch_num, curr_scroll, preferred_mode="jpeg")
            else:
                # Prompt to unpack
                if pdf_path and pdf_path.exists():
                    dlg = UnpackConfirmDialog(ch_num, t=self.t, parent=self)
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        ch_dir = pdf_path.parent if pdf_path.parent != m_path else m_path / f"chapter_{ch_num:03d}"
                        ch_dir.mkdir(parents=True, exist_ok=True)
                        del_pdf = self.cfg.get("delete_pdf_after_extract", False)
                        extract_chapter_pdf(pdf_path, ch_dir, delete_pdf=del_pdf)
                        curr_scroll = self.canvas.verticalScrollBar().value()
                        self.canvas.load_manhwa_chapter(m_path, ch_num, curr_scroll, preferred_mode="jpeg")
                else:
                    dlg = NoticeDialog(
                        self.t.get("pdf_missing_title", "PDF недоступний"),
                        self.t.get("pdf_not_found", "PDF-файл не знайдено на диску."),
                        btn_text=self.t.get("ok_btn", "Зрозуміло"),
                        parent=self
                    )
                    dlg.exec()
        else:
            # User wants to read in PDF!
            if pdf_path and pdf_path.exists():
                curr_scroll = self.canvas.verticalScrollBar().value()
                self.canvas.load_manhwa_chapter(m_path, ch_num, curr_scroll, preferred_mode="pdf")
            else:
                msg_txt = self.t.get("pdf_missing_msg", "Оригінальний PDF-файл для глави {ch} було видалено після розпаковки або він відсутній.").format(ch=ch_num)
                dlg = NoticeDialog(
                    self.t.get("pdf_missing_title", "PDF недоступний"),
                    msg_txt,
                    btn_text=self.t.get("ok_btn", "Зрозуміло"),
                    parent=self
                )
                dlg.exec()

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
        self.is_cloud_reading = False
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
        self.mode_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a202e;
                border: 1px solid rgba(251, 191, 36, 0.45);
                color: #fbbf24;
                font-weight: 700;
                font-size: 12px;
                padding: 5px 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(251, 191, 36, 0.18);
                border-color: #fbbf24;
            }
        """)
        self.switch_tab(1)
        self.canvas.load_manhwa_chapter(m_path, start_ch, saved_scroll_y)

    def on_chapter_combo_change(self, idx: int):
        ch_num = self.chapter_combo.currentData()
        if ch_num and self.current_reading_manhwa:
            if self.is_cloud_reading:
                self.load_cloud_chapter(self.current_reading_manhwa, ch_num)
            else:
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
        self.dl_card_title = QLabel(self.t["dl_title"])
        self.dl_card_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        top_auth_row.addWidget(self.dl_card_title)
        top_auth_row.addStretch()

        self.auth_status_lbl = QLabel(self.t.get("auth_ok", "🟢 Telegram Бот підключено"))
        self.auth_status_lbl.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
        top_auth_row.addWidget(self.auth_status_lbl)

        # Bot token is built-in and protected from accidental modification
        self.auth_btn = QPushButton(self.t["auth_btn"])
        self.auth_btn.hide()

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
        
        self.dl_info_title_lbl = QLabel(self.t["dl_info_title"])
        self.dl_info_title_lbl.setStyleSheet("font-weight: 700; font-size: 14px; color: #fbbf24;")
        ib_layout.addWidget(self.dl_info_title_lbl)

        self.dl_info_desc_lbl = QLabel(self.t["dl_info_desc"])
        self.dl_info_desc_lbl.setStyleSheet("color: #d1d5db; font-size: 13px; font-weight: 400;")
        self.dl_info_desc_lbl.setWordWrap(True)
        ib_layout.addWidget(self.dl_info_desc_lbl)

        card_layout.addWidget(info_banner)

        # High-Contrast Form Grid
        form_grid = QGridLayout()
        form_grid.setSpacing(12)

        self.lbl_channel = QLabel(self.t["dl_channel"])
        form_grid.addWidget(self.lbl_channel, 0, 0)
        self.dl_channel_inp = QLineEdit("")
        self.dl_channel_inp.setPlaceholderText(self.t["dl_channel_ph"])
        form_grid.addWidget(self.dl_channel_inp, 0, 1)

        self.lbl_search = QLabel(self.t["dl_search"])
        form_grid.addWidget(self.lbl_search, 1, 0)
        self.dl_kw_inp = QLineEdit("")
        self.dl_kw_inp.setPlaceholderText(self.t["dl_search_ph"])
        form_grid.addWidget(self.dl_kw_inp, 1, 1)

        self.lbl_range = QLabel(self.t["dl_range"])
        form_grid.addWidget(self.lbl_range, 2, 0)
        self.dl_range_inp = QLineEdit("1")
        self.dl_range_inp.setPlaceholderText(self.t["dl_range_ph"])
        form_grid.addWidget(self.dl_range_inp, 2, 1)

        self.lbl_name = QLabel(self.t["dl_name"])
        form_grid.addWidget(self.lbl_name, 3, 0)
        self.dl_title_inp = QLineEdit("")
        self.dl_title_inp.setPlaceholderText(self.t["dl_name_ph"])
        form_grid.addWidget(self.dl_title_inp, 3, 1)

        self.lbl_dl_lang = QLabel(self.t.get("dl_lang", "Мова перекладу тайтлу:"))
        form_grid.addWidget(self.lbl_dl_lang, 4, 0)
        self.dl_lang_combo = QComboBox()
        self.dl_lang_combo.addItem(self.t.get("dl_lang_auto", "Авто-визначення"), "AUTO")
        self.dl_lang_combo.addItem("🇺🇦 UK (Українська)", "UA")
        self.dl_lang_combo.addItem("🇬🇧 EN (English)", "EN")
        self.dl_lang_combo.addItem("🇷🇺 RU (Русский)", "RU")
        self.dl_lang_combo.addItem("🌐 OTHER (Інша / RAW)", "OTHER")
        apply_combo_style(self.dl_lang_combo)
        form_grid.addWidget(self.dl_lang_combo, 4, 1)

        self.lbl_dl_version = QLabel("При дублікатах глав:")
        form_grid.addWidget(self.lbl_dl_version, 5, 0)
        self.dl_version_combo = QComboBox()
        self.dl_version_combo.addItem("⚡ Завантажувати новіші (найсвіжіший реліз / перезапуск)", "newest")
        self.dl_version_combo.addItem("📦 Завантажувати старіші (перші оригінальні випуски)", "oldest")
        self.dl_version_combo.addItem("📁 Завантажувати всі версії без пропуску", "all")
        apply_combo_style(self.dl_version_combo)
        form_grid.addWidget(self.dl_version_combo, 5, 1)

        card_layout.addLayout(form_grid)

        # Neon Toggles (Brawl Stars Drafter style)
        toggles_box = QVBoxLayout()
        toggles_box.setSpacing(10)

        # Novel / Light Novel Toggle (Placed higher with small subtitle hint)
        self.novel_mode_toggle = NeoToggle(
            self.t.get("toggle_novel_mode_title", "Новела / Ранобе (EPUB / DOCX / TXT)"),
            self.t.get("toggle_novel_mode_sub", "Зберігати глави тексту в окрему Бібліотеку Новел для читання"),
            checked=self.cfg.get("download_as_novel", False)
        )
        self.novel_mode_toggle.toggled.connect(self._on_novel_mode_toggled)
        toggles_box.addWidget(self.novel_mode_toggle)

        self.extract_jpeg_toggle = NeoToggle(
            self.t["toggle_extract_jpeg_title"],
            self.t["toggle_extract_jpeg_sub"],
            checked=self.cfg.get("extract_to_jpeg", False)
        )
        self.extract_jpeg_toggle.toggled.connect(self._on_extract_jpeg_toggled)
        toggles_box.addWidget(self.extract_jpeg_toggle)

        self.del_pdf_toggle = NeoToggle(
            self.t["toggle_del_pdf_title"],
            self.t["toggle_del_pdf_sub"],
            checked=self.cfg.get("delete_pdf_after_extract", False)
        )
        self.del_pdf_toggle.setEnabled(self.extract_jpeg_toggle.isChecked())
        self.del_pdf_toggle.toggled.connect(self._on_del_pdf_toggled)
        toggles_box.addWidget(self.del_pdf_toggle)

        card_layout.addLayout(toggles_box)

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

    def _on_novel_mode_toggled(self, val: bool):
        self.cfg["download_as_novel"] = val
        save_config(self.cfg)

    def _on_extract_jpeg_toggled(self, val: bool):
        self.cfg["extract_to_jpeg"] = val
        save_config(self.cfg)
        if hasattr(self, "del_pdf_toggle"):
            self.del_pdf_toggle.setEnabled(val)

    def _on_del_pdf_toggled(self, val: bool):
        self.cfg["delete_pdf_after_extract"] = val
        save_config(self.cfg)

    def check_auth_status(self):
        """Checks if Telegram session file or Bot Token is active."""
        if self.cfg.get("tg_bot_token"):
            self.auth_status_lbl.setText(self.t.get("auth_ok", "🟢 Telegram Бот підключено"))
            self.auth_status_lbl.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
            return
        session_file = BASE_DIR / "tg_session.session"
        if session_file.exists() and session_file.stat().st_size > 4000:
            self.auth_status_lbl.setText(self.t.get("auth_ok", "🟢 Telegram Бот підключено"))
            self.auth_status_lbl.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 700;")
        else:
            self.auth_status_lbl.setText(self.t.get("auth_needed", "🟡 Потрібен токен бота Telegram"))
            self.auth_status_lbl.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 600;")

    def open_telegram_auth(self):
        dlg = TelegramBotTokenDialog(self.cfg, t=self.t, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.check_auth_status()
            self.dl_log.append(self.t.get("token_ready_log", "🟢 Telegram Бот підключено! Можна завантажувати глави."))

    def start_download(self):
        channel = self.dl_channel_inp.text().strip()
        kw = self.dl_kw_inp.text().strip()
        range_s = self.dl_range_inp.text().strip()
        title = self.dl_title_inp.text().strip()

        if not channel:
            self.dl_log.append(self.t.get("dl_err_no_channel", "Помилка: введіть посилання на канал!"))
            return

        if not title:
            title = kw or "Downloaded_Manhwa"

        selected_lang = self.dl_lang_combo.currentData() if hasattr(self, "dl_lang_combo") else "AUTO"
        if selected_lang and selected_lang != "AUTO":
            tag = f"[{selected_lang}]"
            if tag not in title and f"({selected_lang})" not in title:
                title = f"{title} {tag}"

        self.dl_start_btn.setEnabled(False)
        self.dl_prog.setValue(0)
        self.dl_log.clear()
        start_msg = self.t.get("dl_start_log", "Пошук та завантаження для: «{title}» (Глави: {range})...").format(
            title=title, range=range_s or self.t.get("dl_all", "всі")
        )
        self.dl_log.append(start_msg)

        api_id = self.cfg.get("tg_api_id", 37560778)
        api_hash = self.cfg.get("tg_api_hash", "307da2f94fc6450afe139c91bcc59eaa")
        extract_to_jpeg = self.extract_jpeg_toggle.isChecked()
        del_pdf = self.del_pdf_toggle.isChecked()

        # Check if requested chapters already exist locally
        force_redownload = False
        allowed_chapters = parse_chapter_filter(range_s)
        target_m_dir = self.lib_dir / title
        existing_ch_nums = []

        if target_m_dir.exists() and target_m_dir.is_dir():
            for p in sorted(target_m_dir.iterdir()):
                if p.is_dir() and p.name.startswith("chapter_"):
                    c_num = extract_chapter_number(p.name)
                    if c_num is not None:
                        has_imgs = len(list(p.glob("*.jpg")) + list(p.glob("*.png"))) > 2
                        has_pdf = len(list(p.glob("*.pdf"))) > 0
                        if has_imgs or has_pdf:
                            if allowed_chapters is None or c_num in allowed_chapters:
                                existing_ch_nums.append(c_num)

        if existing_ch_nums:
            dlg = ChapterAlreadyExistsDialog(existing_ch_nums, t=self.t, parent=self)
            dlg.exec()
            choice = getattr(dlg, "result_choice", "cancel")
            if choice == "cancel":
                self.dl_start_btn.setEnabled(True)
                self.dl_log.append(f"• {self.t.get('dl_already_exists_cancel', 'Скасувати')}")
                return
            elif choice == "redownload":
                force_redownload = True
            elif choice == "skip":
                force_redownload = False

        is_novel = self.novel_mode_toggle.isChecked() if hasattr(self, "novel_mode_toggle") else False
        dup_mode = self.dl_version_combo.currentData() if hasattr(self, "dl_version_combo") else "newest"
        self.worker = DownloadWorker(
            api_id, api_hash, channel, kw, range_s, title, self.lib_dir,
            extract_to_jpeg, del_pdf, t=self.t, force_redownload=force_redownload,
            is_novel=is_novel, duplicate_mode=dup_mode
        )
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
            tag = self.t.get("log_success_tag", "[УСПІХ]")
            self.dl_log.append(f"\n{tag} {msg}")
            self.refresh_catalog()
        else:
            tag = self.t.get("log_error_tag", "[ПОМИЛКА]")
            self.dl_log.append(f"\n{tag} {msg}")

    # -----------------------------------------------------------------------
    # TAB 3: SETTINGS
    # -----------------------------------------------------------------------
    def create_settings_page(self) -> QWidget:
        scroll_wrapper = QScrollArea()
        scroll_wrapper.setWidgetResizable(True)
        scroll_wrapper.setStyleSheet("background: transparent; border: none;")

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        # Card 1: Main Settings
        card = QFrame()
        card.setProperty("class", "cardPane")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        self.settings_card_title = QLabel(self.t["settings_title"])
        self.settings_card_title.setStyleSheet("font-size: 19px; font-weight: 700; color: #ffffff;")
        card_layout.addWidget(self.settings_card_title)

        grid = QGridLayout()
        grid.setSpacing(14)

        self.settings_lang_lbl = QLabel(self.t["lang_lbl"])
        grid.addWidget(self.settings_lang_lbl, 0, 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English (EN)", "en")
        self.lang_combo.addItem("Українська (UA)", "uk")
        self.lang_combo.addItem("Русский (RU)", "ru")
        curr_lang = self.cfg.get("language", "en")
        idx = self.lang_combo.findData(curr_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        else:
            self.lang_combo.setCurrentIndex(0)
        apply_combo_style(self.lang_combo)
        self.lang_combo.currentIndexChanged.connect(self.on_language_combo_change)
        grid.addWidget(self.lang_combo, 0, 1)

        self.settings_speed_lbl = QLabel(self.t["speed_lbl"])
        grid.addWidget(self.settings_speed_lbl, 1, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(30, 160)
        self.speed_slider.setValue(self.cfg.get("scroll_speed", 75))
        grid.addWidget(self.speed_slider, 1, 1)

        self.settings_lib_lbl = QLabel(self.t["lib_lbl"])
        grid.addWidget(self.settings_lib_lbl, 2, 0)
        lib_inp = QLineEdit(str(self.lib_dir))
        lib_inp.setReadOnly(True)
        grid.addWidget(lib_inp, 2, 1)

        card_layout.addLayout(grid)

        self.save_btn = QPushButton(self.t["save_btn"])
        self.save_btn.setFixedHeight(48)
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
                color: #121008;
                font-size: 15px;
                font-weight: 800;
                border-radius: 10px;
                padding: 10px 20px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fcd34d, stop:1 #f59e0b);
            }
        """)
        self.save_btn.clicked.connect(self.save_settings)
        card_layout.addWidget(self.save_btn)

        self.settings_saved_status = QLabel("")
        self.settings_saved_status.setStyleSheet("font-size: 13px; color: #34d399; font-weight: 700;")
        card_layout.addWidget(self.settings_saved_status)

        layout.addWidget(card)

        # Card 2: Manual Unpack Tool (PDF -> JPEG)
        unpack_card = QFrame()
        unpack_card.setProperty("class", "cardPane")
        uc_layout = QVBoxLayout(unpack_card)
        uc_layout.setContentsMargins(24, 24, 24, 24)
        uc_layout.setSpacing(14)

        self.uc_title = QLabel(self.t["manual_unpack_title"])
        self.uc_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #fbbf24;")
        uc_layout.addWidget(self.uc_title)

        self.uc_sub = QLabel(self.t["manual_unpack_sub"])
        self.uc_sub.setStyleSheet("font-size: 13px; color: #9ca3af;")
        uc_layout.addWidget(self.uc_sub)

        uc_grid = QGridLayout()
        uc_grid.setSpacing(12)

        self.uc_manhwa_lbl = QLabel(self.t["manual_unpack_m_lbl"])
        uc_grid.addWidget(self.uc_manhwa_lbl, 0, 0)
        self.settings_m_combo = QComboBox()
        apply_combo_style(self.settings_m_combo)
        self.settings_m_combo.currentIndexChanged.connect(self._on_settings_manhwa_selected)
        uc_grid.addWidget(self.settings_m_combo, 0, 1)

        self.uc_ch_lbl = QLabel(self.t["manual_unpack_ch_lbl"])
        uc_grid.addWidget(self.uc_ch_lbl, 1, 0)
        self.settings_ch_combo = QComboBox()
        apply_combo_style(self.settings_ch_combo)
        uc_grid.addWidget(self.settings_ch_combo, 1, 1)

        uc_layout.addLayout(uc_grid)

        self.unpack_action_btn = QPushButton(self.t["manual_unpack_btn"])
        self.unpack_action_btn.setProperty("class", "btnSecondary")
        self.unpack_action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.unpack_action_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0d9488, stop:1 #059669);
                color: #ffffff;
                font-weight: 700;
                font-size: 13px;
                border: none;
                border-radius: 9px;
                padding: 10px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14b8a6, stop:1 #0d9488);
            }
        """)
        self.unpack_action_btn.clicked.connect(self._do_manual_chapter_unpack)
        uc_layout.addWidget(self.unpack_action_btn)

        self.settings_unpack_status = QLabel("")
        self.settings_unpack_status.setStyleSheet("font-size: 12px; color: #5eead4; font-weight: 600;")
        uc_layout.addWidget(self.settings_unpack_status)

        layout.addWidget(unpack_card)
        layout.addStretch()

        self._populate_settings_manhwa_list()

        scroll_wrapper.setWidget(inner_widget)
        return scroll_wrapper

    def _populate_settings_manhwa_list(self):
        if not hasattr(self, "settings_m_combo"):
            return
        self.settings_m_combo.blockSignals(True)
        prev_data = self.settings_m_combo.currentData()
        self.settings_m_combo.clear()
        manhwas = [p for p in self.lib_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
        if not manhwas:
            self.settings_m_combo.addItem(self.t.get("status_empty_m", "У бібліотеці немає манхви"), None)
            self.settings_m_combo.blockSignals(False)
            if hasattr(self, "settings_ch_combo"):
                self.settings_ch_combo.clear()
                self.settings_ch_combo.addItem(self.t.get("status_no_pdf", "Немає розділів із PDF"), None)
            return

        selected_idx = 0
        for idx, m in enumerate(manhwas):
            self.settings_m_combo.addItem(m.name, str(m.resolve()))
            if prev_data and str(m.resolve()) == prev_data:
                selected_idx = idx

        self.settings_m_combo.setCurrentIndex(selected_idx)
        self.settings_m_combo.blockSignals(False)
        self._on_settings_manhwa_selected(self.settings_m_combo.currentIndex())

    def _on_settings_manhwa_selected(self, idx: int):
        if not hasattr(self, "settings_ch_combo"):
            return
        self.settings_ch_combo.clear()
        m_str = self.settings_m_combo.currentData()
        if not m_str:
            self.settings_ch_combo.addItem(self.t.get("status_no_pdf", "Немає розділів із PDF"), None)
            return

        m_path = Path(m_str)
        if not m_path.exists():
            self.settings_ch_combo.addItem(self.t.get("status_no_pdf", "Немає розділів із PDF"), None)
            return

        chapters_with_pdf = []
        for p in m_path.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                num = extract_chapter_number(p.name)
                pdfs = list(p.glob("*.pdf"))
                imgs = list(p.glob("*.jpg")) + list(p.glob("*.png"))
                if pdfs and num is not None:
                    chapters_with_pdf.append((num, pdfs[0], p, len(imgs) > 0))

        for loose_pdf in m_path.glob("*.pdf"):
            num = extract_chapter_number(loose_pdf.stem)
            if num is not None and not any(c[0] == num for c in chapters_with_pdf):
                ch_dir = m_path / f"chapter_{num:03d}"
                chapters_with_pdf.append((num, loose_pdf, ch_dir, False))

        chapters_with_pdf.sort(key=lambda x: x[0])
        status_has_jpeg = self.t.get("status_has_jpeg", "Вже є JPEG")
        status_only_pdf = self.t.get("status_only_pdf", "Тільки PDF")
        prefix = self.t.get("chapter_prefix", "Глава")

        for num, pdf_path, ch_dir, has_imgs in chapters_with_pdf:
            status = status_has_jpeg if has_imgs else status_only_pdf
            self.settings_ch_combo.addItem(f"{prefix} {num} ({status})", (num, str(pdf_path.resolve()), str(ch_dir.resolve())))

        if self.settings_ch_combo.count() == 0:
            self.settings_ch_combo.addItem(self.t.get("status_no_pdf", "Немає розділів із PDF"), None)

    def _do_manual_chapter_unpack(self):
        data = self.settings_ch_combo.currentData()
        if not data:
            self.settings_unpack_status.setText(self.t.get("select_pdf_first", "Оберіть главу з наявним PDF!"))
            self.settings_unpack_status.setStyleSheet("color: #f87171; font-weight: 600;")
            return

        num, pdf_str, ch_dir_str = data
        pdf_path = Path(pdf_str)
        ch_dir = Path(ch_dir_str)
        if not pdf_path.exists():
            self.settings_unpack_status.setText(self.t.get("pdf_not_found", "PDF-файл не знайдено на диску."))
            self.settings_unpack_status.setStyleSheet("color: #f87171; font-weight: 600;")
            return

        ch_dir.mkdir(parents=True, exist_ok=True)
        del_pdf = self.cfg.get("delete_pdf_after_extract", False)
        prog_tmpl = self.t.get("unpacking_progress", "Розпакування глави {num}...")
        self.settings_unpack_status.setText(prog_tmpl.format(num=num))
        self.settings_unpack_status.setStyleSheet("color: #fbbf24; font-weight: 600;")
        QApplication.processEvents()

        try:
            count = extract_chapter_pdf(pdf_path, ch_dir, delete_pdf=del_pdf)
            succ_tmpl = self.t.get("unpacking_success", "✓ Главу {num} успішно розпаковано ({count} сторінок)!")
            self.settings_unpack_status.setText(succ_tmpl.format(num=num, count=count))
            self.settings_unpack_status.setStyleSheet("color: #34d399; font-weight: 700;")
            self._on_settings_manhwa_selected(self.settings_m_combo.currentIndex())
        except Exception as e:
            err_tmpl = self.t.get("unpacking_error", "Помилка розпакування: {err}")
            self.settings_unpack_status.setText(err_tmpl.format(err=e))
            self.settings_unpack_status.setStyleSheet("color: #f87171; font-weight: 600;")

    def on_language_combo_change(self, idx: int):
        new_lang = self.lang_combo.currentData()
        if not new_lang or new_lang == self.lang:
            return
        self.lang = new_lang
        self.cfg["language"] = self.lang
        save_config(self.cfg)
        self.t = TRANSLATIONS.get(self.lang, TRANSLATIONS["uk"])
        self.retranslate_ui()

    def save_settings(self):
        new_lang = self.lang_combo.currentData()
        self.cfg["language"] = new_lang
        self.cfg["scroll_speed"] = self.speed_slider.value()
        save_config(self.cfg)

        if new_lang != self.lang:
            self.lang = new_lang
            self.t = TRANSLATIONS.get(self.lang, TRANSLATIONS["uk"])
            self.retranslate_ui()

        self.settings_saved_status.setText(self.t["saved_msg"])
        QTimer.singleShot(3500, lambda: self.settings_saved_status.setText(""))

    def retranslate_ui(self):
        # Window & Header
        self.setWindowTitle(self.t["app_title"])
        if hasattr(self, "badge_lbl"):
            self.badge_lbl.setText(self.t["badge_engine"])
        if hasattr(self, "sub_lbl"):
            self.sub_lbl.setText(self.t["subtitle"])
        if hasattr(self, "fs_btn"):
            self.fs_btn.setText(self.t["fs_off"] if self.isFullScreen() else self.t["fs_on"])

        # Navigation Tabs
        if hasattr(self, "tab_catalog_btn"):
            self.tab_catalog_btn.setText(self.t["tab_catalog"])
        if hasattr(self, "tab_reader_btn"):
            self.tab_reader_btn.setText(self.t["tab_reader"])
        if hasattr(self, "tab_downloader_btn"):
            self.tab_downloader_btn.setText(self.t["tab_downloader"])
        if hasattr(self, "tab_settings_btn"):
            self.tab_settings_btn.setText(self.t["tab_settings"])
        if hasattr(self, "tab_translate_btn"):
            self.tab_translate_btn.setText(self.t.get("btn_translate_nav", "⚔️ Translate"))

        # Tab 0: Catalog
        if getattr(self, "catalog_view_mode", "local") == "cloud":
            if hasattr(self, "cat_title"):
                self.cat_title.setText(self.t.get("cloud_vault_title", "Cloud Vault"))
        elif getattr(self, "catalog_view_mode", "local") == "novels":
            if hasattr(self, "cat_title"):
                self.cat_title.setText(self.t.get("cat_tab_novels", "📖 Novels / Light Novels"))
        else:
            if hasattr(self, "cat_title"):
                self.cat_title.setText(self.t["lib_title"])
        if hasattr(self, "btn_mode_local"):
            self.btn_mode_local.setText(self.t.get("cat_tab_local", "📚 Local Library"))
        if hasattr(self, "btn_mode_cloud"):
            self.btn_mode_cloud.setText(self.t.get("cat_tab_cloud", "☁️ Cloud Vault"))
        if hasattr(self, "btn_mode_novels"):
            self.btn_mode_novels.setText(self.t.get("cat_tab_novels", "📖 Novels / Light Novels"))
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setText(self.t["refresh"])
        if hasattr(self, "add_btn"):
            self.add_btn.setText(self.t["add_tg"])
        if hasattr(self, "search_input"):
            self.search_input.setPlaceholderText(self.t.get("search_ph", "🔍 Search titles..."))
        if hasattr(self, "_populate_lang_filter"):
            self._populate_lang_filter()
        if hasattr(self, "_populate_prog_filter"):
            self._populate_prog_filter()
        self.refresh_catalog()

        # Tab 1: Reader
        if hasattr(self, "back_btn"):
            self.back_btn.setText(self.t["to_catalog"])
        if hasattr(self, "reader_title_lbl") and not self.current_reading_manhwa:
            self.reader_title_lbl.setText(self.t["select_manhwa"])
        if hasattr(self, "prev_ch_btn"):
            self.prev_ch_btn.setToolTip(self.t["prev_ch"])
        if hasattr(self, "next_ch_btn"):
            self.next_ch_btn.setToolTip(self.t["next_ch"])
        if hasattr(self, "mode_toggle_btn"):
            if self.is_cloud_reading:
                self.mode_toggle_btn.setText(self.t.get("reader_cloud_dl_btn", "📥 Download PDF"))
            elif self.canvas.active_mode == "pdf":
                self.mode_toggle_btn.setText(self.t["read_in_jpeg"])
            else:
                self.mode_toggle_btn.setText(self.t["read_in_pdf"])
        if hasattr(self, "width_lbl"):
            self.width_lbl.setText(self.t["width_lbl"])
        if hasattr(self, "theme_lbl"):
            self.theme_lbl.setText(self.t["theme_lbl"])
        if hasattr(self, "zen_btn"):
            self.zen_btn.setText(self.t["show_menu"] if self.is_zen_mode else self.t["hide_menu"])
        if hasattr(self, "chapter_combo") and self.chapter_combo.count() > 0:
            self.chapter_combo.blockSignals(True)
            for i in range(self.chapter_combo.count()):
                num = self.chapter_combo.itemData(i)
                if num is not None:
                    self.chapter_combo.setItemText(i, f"{self.t['chapter_prefix']} {num}")
            self.chapter_combo.blockSignals(False)

        # Tab 2: Downloader
        if hasattr(self, "dl_card_title"):
            self.dl_card_title.setText(self.t["dl_title"])
        if hasattr(self, "auth_btn"):
            self.auth_btn.setText(self.t["auth_btn"])
        if hasattr(self, "check_auth_status"):
            self.check_auth_status()
        if hasattr(self, "dl_info_title_lbl"):
            self.dl_info_title_lbl.setText(self.t["dl_info_title"])
        if hasattr(self, "dl_info_desc_lbl"):
            self.dl_info_desc_lbl.setText(self.t["dl_info_desc"])
        if hasattr(self, "lbl_channel"):
            self.lbl_channel.setText(self.t["dl_channel"])
        if hasattr(self, "lbl_search"):
            self.lbl_search.setText(self.t["dl_search"])
        if hasattr(self, "lbl_range"):
            self.lbl_range.setText(self.t["dl_range"])
        if hasattr(self, "lbl_name"):
            self.lbl_name.setText(self.t["dl_name"])
        if hasattr(self, "lbl_dl_lang"):
            self.lbl_dl_lang.setText(self.t.get("dl_lang", "Translation Language:"))
        if hasattr(self, "dl_channel_inp"):
            self.dl_channel_inp.setPlaceholderText(self.t["dl_channel_ph"])
        if hasattr(self, "dl_kw_inp"):
            self.dl_kw_inp.setPlaceholderText(self.t["dl_search_ph"])
        if hasattr(self, "dl_range_inp"):
            self.dl_range_inp.setPlaceholderText(self.t["dl_range_ph"])
        if hasattr(self, "dl_title_inp"):
            self.dl_title_inp.setPlaceholderText(self.t["dl_name_ph"])
        if hasattr(self, "novel_mode_toggle"):
            self.novel_mode_toggle.set_texts(self.t["toggle_novel_mode_title"], self.t["toggle_novel_mode_sub"])
        if hasattr(self, "extract_jpeg_toggle"):
            self.extract_jpeg_toggle.set_texts(self.t["toggle_extract_jpeg_title"], self.t["toggle_extract_jpeg_sub"])
        if hasattr(self, "del_pdf_toggle"):
            self.del_pdf_toggle.set_texts(self.t["toggle_del_pdf_title"], self.t["toggle_del_pdf_sub"])
        if hasattr(self, "dl_start_btn"):
            self.dl_start_btn.setText(self.t["dl_start"])

        # Tab 3: Settings
        if hasattr(self, "settings_card_title"):
            self.settings_card_title.setText(self.t["settings_title"])
        if hasattr(self, "settings_lang_lbl"):
            self.settings_lang_lbl.setText(self.t["lang_lbl"])
        if hasattr(self, "settings_speed_lbl"):
            self.settings_speed_lbl.setText(self.t["speed_lbl"])
        if hasattr(self, "settings_lib_lbl"):
            self.settings_lib_lbl.setText(self.t["lib_lbl"])
        if hasattr(self, "save_btn"):
            self.save_btn.setText(self.t["save_btn"])
        if hasattr(self, "uc_title"):
            self.uc_title.setText(self.t["manual_unpack_title"])
        if hasattr(self, "uc_sub"):
            self.uc_sub.setText(self.t["manual_unpack_sub"])
        if hasattr(self, "uc_manhwa_lbl"):
            self.uc_manhwa_lbl.setText(self.t["manual_unpack_m_lbl"])
        if hasattr(self, "uc_ch_lbl"):
            self.uc_ch_lbl.setText(self.t["manual_unpack_ch_lbl"])
        if hasattr(self, "unpack_action_btn"):
            self.unpack_action_btn.setText(self.t["manual_unpack_btn"])
        self._populate_settings_manhwa_list()

        # Embedded Novel Reader tab if active
        if hasattr(self, "novel_reader_widget") and self.novel_reader_widget is not None:
            if hasattr(self.novel_reader_widget, "set_translations"):
                self.novel_reader_widget.set_translations(self.t)

    def launch_overlay_translator(self):
        """
        Launches the overlay translator module (main.py or m_translate.exe) in root directory
        as an independent detached background process.
        If running inside m_reader_t suite, activates the embedded translator.
        If not found, displays a stylish Dark Fantasy NoticeDialog.
        """
        # 1. If embedded suite translator exists, show its mascot and bubble!
        if hasattr(self, "suite_translator") and self.suite_translator is not None:
            try:
                self.suite_translator.mascot.show()
                self.suite_translator.toggle_bubble()
                return
            except Exception:
                pass

        if getattr(sys, "frozen", False):
            # In compiled distribution: look for m_translate.exe in the same folder as this exe
            project_root = BASE_DIR
            exe_path = BASE_DIR / "m_translate.exe"
            if exe_path.exists():
                found_target = exe_path
                target_args = [str(exe_path)]
            else:
                found_target = None
        else:
            # Development mode: check project root
            project_root = BASE_DIR.parent.resolve()
            exe_path = project_root / "m_translate.exe"
            main_py = project_root / "main.py"
            run_bat = project_root / "run.bat"
            venv_py = project_root / ".venv" / "Scripts" / "pythonw.exe"
            if not venv_py.exists():
                venv_py = project_root / ".venv" / "Scripts" / "python.exe"

            if exe_path.exists():
                found_target = exe_path
                target_args = [str(exe_path)]
            elif main_py.exists():
                found_target = main_py
                py_bin = str(venv_py) if venv_py.exists() else sys.executable
                target_args = [py_bin, str(main_py)]
            elif run_bat.exists():
                found_target = run_bat
                target_args = [str(run_bat)]
            else:
                found_target = None

        if found_target:
            try:
                # Windows flags for completely detached background process
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                creation_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(
                    target_args,
                    cwd=str(project_root),
                    creationflags=creation_flags,
                    close_fds=True
                )
            except Exception as e:
                # Fallback popen
                try:
                    subprocess.Popen(target_args, cwd=str(project_root))
                except Exception as ex:
                    NoticeDialog(
                        self.t.get("log_error_tag", "Error").strip("[]"),
                        f"Failed to launch M_Translate: {ex}",
                        btn_text=self.t.get("ok_btn", "OK"),
                        parent=self
                    ).exec()
        else:
            # Show stylish Dark Fantasy Notice Dialog
            tg_channel_url = "https://t.me/lm_reader"
            cloud_index = self._get_cloud_index_data()
            if cloud_index.get("vault_channel"):
                tg_channel_url = cloud_index.get("vault_channel")

            dlg = NoticeDialog(
                title=self.t.get("translate_not_found_title", "M_Translate Module Not Found!"),
                message=self.t.get(
                    "translate_not_found_msg",
                    "You do not have the Translate module installed. Visit our official Telegram channel to download the full version of the application."
                ),
                btn_text=self.t.get("ok_btn", "OK"),
                action_btn_text=self.t.get("telegram_open_btn", "✈️ Open Telegram Channel"),
                on_action_click=lambda: QDesktopServices.openUrl(QUrl("https://t.me/lm_reader")),
                parent=self
            )
            dlg.exec()

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

        prev_idx = self.stack.currentIndex()
        self.stack.setCurrentIndex(index)
        if prev_idx == 1 and index != 1:
            if hasattr(self, "canvas"):
                self.canvas.clear_canvas()
            if self.current_cloud_worker and self.current_cloud_worker.isRunning():
                try:
                    self.current_cloud_worker.cancel()
                    self.current_cloud_worker.quit()
                except Exception:
                    pass

        if index == 0:
            self.refresh_catalog()
        elif index == 2:
            self.check_auth_status()
        elif index == 3:
            self._populate_settings_manhwa_list()

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
            if self.stack.currentIndex() == 1 or (hasattr(self, "novel_reader_widget") and self.stack.currentWidget() == self.novel_reader_widget):
                self.toggle_zen_mode()
        elif event.key() == Qt.Key.Key_Escape:
            if self.is_zen_mode:
                self.toggle_zen_mode()
            elif self.isFullScreen():
                self.toggle_fullscreen()
            elif self.stack.currentIndex() == 1 or (hasattr(self, "novel_reader_widget") and self.stack.currentWidget() == self.novel_reader_widget):
                self.switch_tab(0)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        save_config(self.cfg)
        if hasattr(self, "canvas"):
            self.canvas.clear_canvas()
        if hasattr(self, "stream_client"):
            try:
                self.stream_client.disconnect()
            except Exception:
                pass
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
