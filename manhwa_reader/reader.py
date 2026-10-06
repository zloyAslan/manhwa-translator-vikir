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
    QLinearGradient, QRadialGradient, QBrush, QCursor, QPalette
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

from downloader import (
    TelegramManhwaDownloader, extract_chapter_number, clean_channel_link,
    extract_pdf_to_images, extract_chapter_pdf
)

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_LIB_DIR = BASE_DIR / "library"


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
        "dl_log_skipped_exists": "Chapter {ch} already exists. Skipping."
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
        "dl_log_skipped_exists": "Глава {ch} вже існує. Пропуск."
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
        "dl_log_skipped_exists": "Глава {ch} уже существует. Пропуск."
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
        "tg_bot_token": "",
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
    background-color: #161922;
    border: 1px solid rgba(255, 255, 255, 0.24);
    border-radius: 9px;
    padding: 7px 12px;
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    min-height: 28px;
    outline: none;
    selection-background-color: transparent;
    selection-color: #ffffff;
}
QComboBox:hover {
    border: 1px solid #fbbf24;
    background-color: #1a1e29;
}
QComboBox:focus {
    border: 1.5px solid #fbbf24;
    background-color: #161922;
    outline: none;
}
QComboBox:on {
    border: 1.5px solid #fbbf24;
    background-color: #161922;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #fbbf24;
    margin-right: 10px;
    margin-top: 2px;
}
QComboBox QAbstractItemView {
    background-color: #161922;
    border: 1.5px solid #fbbf24;
    border-radius: 8px;
    color: #ffffff;
    selection-background-color: #2b3145;
    selection-color: #fbbf24;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 12px;
    border-radius: 6px;
    color: #ffffff;
    background-color: transparent;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #232838;
    color: #fbbf24;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #2b3145;
    color: #fbbf24;
    font-weight: 700;
}
"""


def apply_combo_style(combo: QComboBox):
    combo.setStyleSheet(COMBO_BOX_STYLESHEET)
    pal = combo.palette()
    pal.setColor(QPalette.ColorRole.Base, QColor("#161922"))
    pal.setColor(QPalette.ColorRole.Window, QColor("#161922"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#161922"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#161922"))
    combo.setPalette(pal)
    view = combo.view()
    if view:
        v_pal = view.palette()
        v_pal.setColor(QPalette.ColorRole.Base, QColor("#161922"))
        v_pal.setColor(QPalette.ColorRole.Window, QColor("#161922"))
        v_pal.setColor(QPalette.ColorRole.Highlight, QColor("#2b3145"))
        v_pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#fbbf24"))
        v_pal.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        view.setPalette(v_pal)
        view.setStyleSheet("""
            QAbstractItemView {
                background-color: #161922;
                border: 1.5px solid #fbbf24;
                border-radius: 8px;
                color: #ffffff;
                outline: none;
                padding: 4px;
                selection-background-color: #2b3145;
                selection-color: #fbbf24;
            }
            QAbstractItemView::item {
                min-height: 28px;
                padding: 6px 12px;
                border-radius: 6px;
                color: #ffffff;
                background-color: transparent;
            }
            QAbstractItemView::item:hover {
                background-color: #232838;
                color: #fbbf24;
            }
            QAbstractItemView::item:selected {
                background-color: #2b3145;
                color: #fbbf24;
                font-weight: 700;
            }
        """)


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
    def __init__(self, title: str, message: str, btn_text: str = "Зрозуміло", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(430, 210)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #141722;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title_lbl = QLabel(f"⚠️ {title}")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f87171;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #e5e7eb; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(btn_text)
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet("""
            background-color: #212636;
            color: #f3f4f6;
            font-weight: 600;
            font-size: 13px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 9px;
            padding: 8px 18px;
        """)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)


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

    def __init__(self, api_id: int, api_hash: str, channel: str, search_kw: str, range_str: str, title: str, lib_dir: Path, extract_to_jpeg: bool, del_pdf: bool, t: dict = None, force_redownload: bool = False):
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

            if not filtered:
                raise RuntimeError(f"Жодна глава не відповідає фільтру '{self.range_str}'. Знайдені глави: {[x.get('chapter') for x in items[:10]]}")

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
        if mode == "pdf":
            self.mode_toggle_btn.setText(self.t["read_in_jpeg"])
        else:
            self.mode_toggle_btn.setText(self.t["read_in_pdf"])

    def toggle_reader_mode(self):
        if not self.current_reading_manhwa:
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
        self.dl_card_title = QLabel(self.t["dl_title"])
        self.dl_card_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        top_auth_row.addWidget(self.dl_card_title)
        top_auth_row.addStretch()

        self.auth_status_lbl = QLabel(self.t["auth_needed"])
        self.auth_status_lbl.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: 600;")
        top_auth_row.addWidget(self.auth_status_lbl)

        self.auth_btn = QPushButton(self.t["auth_btn"])
        self.auth_btn.setProperty("class", "btnSecondary")
        self.auth_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.auth_btn.clicked.connect(self.open_telegram_auth)
        top_auth_row.addWidget(self.auth_btn)

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

        card_layout.addLayout(form_grid)

        # Neon Toggles (Brawl Stars Drafter style)
        toggles_box = QVBoxLayout()
        toggles_box.setSpacing(10)

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

        self.worker = DownloadWorker(
            api_id, api_hash, channel, kw, range_s, title, self.lib_dir,
            extract_to_jpeg, del_pdf, t=self.t, force_redownload=force_redownload
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

        # Tab 0: Catalog
        if hasattr(self, "cat_title"):
            self.cat_title.setText(self.t["lib_title"])
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setText(self.t["refresh"])
        if hasattr(self, "add_btn"):
            self.add_btn.setText(self.t["add_tg"])
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
            if self.canvas.active_mode == "pdf":
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
        if hasattr(self, "dl_channel_inp"):
            self.dl_channel_inp.setPlaceholderText(self.t["dl_channel_ph"])
        if hasattr(self, "dl_kw_inp"):
            self.dl_kw_inp.setPlaceholderText(self.t["dl_search_ph"])
        if hasattr(self, "dl_range_inp"):
            self.dl_range_inp.setPlaceholderText(self.t["dl_range_ph"])
        if hasattr(self, "dl_title_inp"):
            self.dl_title_inp.setPlaceholderText(self.t["dl_name_ph"])
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
