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

import logging
logger = logging.getLogger("manhwa_reader")
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
    QCheckBox, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

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

try:
    from manhwa_reader.sound_system import SoundEngine, AISoundAnalyzer, SoundStudioWindow, TitleClassifier
except ImportError:
    try:
        from sound_system import SoundEngine, AISoundAnalyzer, SoundStudioWindow, TitleClassifier
    except ImportError:
        try:
            from manhwa_reader.sound_system.sound_engine import SoundEngine
            from manhwa_reader.sound_system.ai_sound_analyzer import AISoundAnalyzer
            from manhwa_reader.sound_system.title_classifier import TitleClassifier
            SoundStudioWindow = None
        except ImportError:
            SoundEngine = None
            AISoundAnalyzer = None
            SoundStudioWindow = None
            TitleClassifier = None

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()

CONFIG_FILE = BASE_DIR / "config.json"
# Safe internal credentials loader (Priority: Environment -> SECRETS_VAULT.local.py -> Built-in Internal Fallback)
def _load_internal_credentials():
    api_id = 37560778
    api_hash = "307da2f94fc6450afe139c91bcc59eaa"
    bot_token = "8599785351:AAFNZkDk1GlpbE-tbmoF7CJBlkGHw45hLTA"
    vault_invite = "https://t.me/+O6mlGVWzTSQ5MjVi"
    vault_channel_id = -1004386061072
    vault_channel_title = "Manhwa Vault"

    # 1. Environment variables override
    if os.environ.get("TG_API_ID"):
        try:
            api_id = int(os.environ.get("TG_API_ID"))
        except Exception:
            pass
    if os.environ.get("TG_API_HASH"):
        api_hash = os.environ.get("TG_API_HASH").strip()
    if os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN"):
        bot_token = (os.environ.get("TG_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")).strip()

    # 2. Local secrets vault if available
    try:
        import importlib.util
        vault_path = BASE_DIR.parent / "SECRETS_VAULT.local.py"
        if not vault_path.exists():
            vault_path = BASE_DIR / "SECRETS_VAULT.local.py"
        if vault_path.exists():
            spec = importlib.util.spec_from_file_location("secrets_vault", str(vault_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                api_id = getattr(mod, "TELEGRAM_API_ID", api_id)
                api_hash = getattr(mod, "TELEGRAM_API_HASH", api_hash)
                bot_token = getattr(mod, "TELEGRAM_BOT_TOKEN", bot_token)
                vault_invite = getattr(mod, "TELEGRAM_VAULT_INVITE", vault_invite)
                vault_channel_id = getattr(mod, "TELEGRAM_VAULT_CHANNEL_ID", vault_channel_id)
                vault_channel_title = getattr(mod, "TELEGRAM_VAULT_CHANNEL_TITLE", vault_channel_title)
    except Exception:
        pass

    return api_id, api_hash, bot_token, vault_invite, vault_channel_id, vault_channel_title

INTERNAL_TG_API_ID, INTERNAL_TG_API_HASH, INTERNAL_TG_BOT_TOKEN, INTERNAL_VAULT_INVITE, INTERNAL_VAULT_CHANNEL_ID, INTERNAL_VAULT_CHANNEL_TITLE = _load_internal_credentials()
DEFAULT_BOT_TOKEN = INTERNAL_TG_BOT_TOKEN

# Multilingual Translations (loaded from translations.py)
try:
    from manhwa_reader.translations import TRANSLATIONS
except ImportError:
    try:
        from translations import TRANSLATIONS
    except ImportError:
        from .translations import TRANSLATIONS


def load_config() -> dict:
    default_cfg = {
        "library_path": "library",
        "sounds_path": "sounds",
        "reading_width": 880,
        "bg_color": "#0f1115",
        "zoom": 1.0,
        "fullscreen": False,
        "scroll_speed": 75,
        "preload_mode": "adaptive",
        "manual_preload_threshold": 75,
        "progress_display_mode": "chapter",
        "auto_preload_threshold": 0.67,
        "language": "en",
        "delete_pdf_after_extract": True,
        "bookmarks": {}
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass

    # Ensure in-memory presence of telegram and vault credentials
    default_cfg["tg_api_id"] = default_cfg.get("tg_api_id") or INTERNAL_TG_API_ID
    default_cfg["tg_api_hash"] = default_cfg.get("tg_api_hash") or INTERNAL_TG_API_HASH
    default_cfg["tg_bot_token"] = default_cfg.get("tg_bot_token") or INTERNAL_TG_BOT_TOKEN
    default_cfg["tg_vault_invite"] = default_cfg.get("tg_vault_invite") or INTERNAL_VAULT_INVITE
    default_cfg["tg_vault_channel_id"] = default_cfg.get("tg_vault_channel_id") or INTERNAL_VAULT_CHANNEL_ID
    default_cfg["tg_vault_channel_title"] = default_cfg.get("tg_vault_channel_title") or INTERNAL_VAULT_CHANNEL_TITLE

    return default_cfg


def save_config(cfg: dict):
    """
    Saves user configuration to config.json.
    Excludes sensitive Telegram credentials and private vault channel IDs
    so they remain compiled internally and never leaked into plain text files.
    """
    try:
        clean_cfg = dict(cfg)
        # Strip internal secrets from plain disk file
        for secret_key in [
            "tg_api_id", "tg_api_hash", "tg_bot_token",
            "tg_vault_invite", "tg_vault_channel_id", "tg_vault_channel_title"
        ]:
            clean_cfg.pop(secret_key, None)

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_cfg, f, ensure_ascii=False, indent=2)
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


def detect_title_language(title: str, explicit_lang: Optional[str] = None) -> str:
    """
    Accurately detects language code (UA, RU, EN, RAW) based on explicit tags,
    specific language alphabets (Ukrainian specific letters, Cyrillic) and tags.
    Other languages (including Slovak, Korean, Japanese, Chinese) map to RAW/Other.
    """
    if explicit_lang:
        el = explicit_lang.strip().upper()
        if el in ["UA", "UK", "UKR"]:
            return "UA"
        if el in ["RU", "RUS"]:
            return "RU"
        if el in ["EN", "ENG"]:
            return "EN"
        if el in ["RAW", "KR", "JP", "CN", "SK", "SLO", "SLOVAK"]:
            return "RAW"

    t = title.strip()
    t_up = t.upper()

    # 1. Check explicit bracket tags [UA], [RU], [EN], [RAW]
    m_tag = re.search(r'\[(UA|UK|UKR|RU|RUS|EN|ENG|RAW|KR|JP|CN|SK|SLO)\]', t_up)
    if m_tag:
        code = m_tag.group(1)
        if code in ["UA", "UK", "UKR"]:
            return "UA"
        if code in ["RU", "RUS"]:
            return "RU"
        if code in ["EN", "ENG"]:
            return "EN"
        if code in ["RAW", "KR", "JP", "CN", "SK", "SLO"]:
            return "RAW"

    # 2. Check Slovak specific letters -> maps to RAW / Other
    if re.search(r'[ôďťňľŕĺä]', t, re.I):
        return "RAW"

    # 3. Check Ukrainian specific letters
    if re.search(r'[іїєґ]', t, re.I):
        return "UA"

    # 4. Check Russian specific letters
    if re.search(r'[ыэъё]', t, re.I):
        return "RU"

    # 5. General Cyrillic fallback -> RU if general Cyrillic without unique UA letters
    if re.search(r'[а-я]', t, re.I):
        return "RU"

    # 6. Default Latin -> EN
    return "EN"



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

        header_lbl = QLabel(f"ಠ_ಠ  {title}")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #f87171;")
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

        header_text = f"(ง •̀_•́)ง " + t.get("unpack_confirm_header", "⚡ Розпакування Глави {ch} в JPEG").format(ch=ch_num)
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

        title_lbl = QLabel(f"(•ิ_•ิ) {t.get('dl_already_exists_title', 'Главу вже завантажено')}")
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
        # Check if title already starts with a kaomoji (e.g. (•‿•), (￣▽￣)", ಠ_ಠ, (⊙_⊙;))
        import re
        has_existing_kaomoji = bool(re.match(r"^\s*[\(\[ಠ].*?[\)\]ಠ]\s*", title))

        is_error = any(w in title.lower() or w in message.lower() for w in ["помилка", "error", "не знайдено", "not found", "недоступний"])
        is_success = any(w in title.lower() or w in message.lower() for w in ["успіх", "success", "завершено", "готово", "чудово"])
        if is_error:
            kaomoji = "(⊙_⊙;) "
            badge_color = "#f87171"
            border_color = "rgba(239, 68, 68, 0.55)"
        elif is_success:
            kaomoji = "(￣▽￣)\" "
            badge_color = "#34d399"
            border_color = "rgba(52, 211, 153, 0.55)"
        else:
            kaomoji = "(•‿•) "
            badge_color = "#fbbf24"
            border_color = "rgba(245, 158, 11, 0.55)"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #12151f;
                border: 1.5px solid {border_color};
                border-radius: 16px;
            }}
        """)

        clean_title = title if has_existing_kaomoji else f"{kaomoji}{title}"
        title_lbl = QLabel(clean_title)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {badge_color};")
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
# Change Cover Dialog (Drag-and-Drop, 1:1 Auto Crop, Centered & Draggable)
# ---------------------------------------------------------------------------
class ChangeCoverDialog(QDialog):
    """
    Sleek floating dialog for changing title cover:
    - Movable / draggable by clicking header or background
    - Rounded top drop zone with:
        "( ;) перетягни сюди ⇓"
    - Subtitle explanation:
        "щоб поставити нове прев'ю перетягніть в це поле⇑ фото форматом 1:1 (інший формат обріжеться і відцентрується)"
    - 3 action buttons: [Зберегти] [Скинути] [Скасувати]
    """
    def __init__(self, manhwa_name: str, target_dir: Path, t: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.manhwa_name = manhwa_name
        self.target_dir = Path(target_dir)
        self.t = t or TRANSLATIONS.get("uk", {})
        self.original_cover_path = self.target_dir / "cover.jpg"
        self._new_pixmap: Optional[QPixmap] = None
        self._drag_pos: Optional[QPoint] = None

        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(480, 500)
        self.setAcceptDrops(True)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Card container with dark glassy background and subtle border
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #12151f;
                border: 1.5px solid rgba(45, 212, 191, 0.45);
                border-radius: 18px;
            }
        """)
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(14)

        # Header with title and close button
        hdr_row = QHBoxLayout()
        header_text = self.t.get("cover_dlg_header", "Обкладинка: {name}").format(name=self.manhwa_name)
        title_lbl = QLabel(f"(￣▽￣)\" {header_text}")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #5eead4; border: none; background: transparent;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-weight: 800;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)
        c_layout.addLayout(hdr_row)

        # Drop Zone (Rounded rectangle)
        self.drop_zone = QLabel(self)
        self.drop_zone.setFixedHeight(230)
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_drop_zone_appearance()
        self.drop_zone.mousePressEvent = self._on_drop_zone_clicked
        c_layout.addWidget(self.drop_zone)

        # Descriptive subtitle
        sub_text = self.t.get(
            "cover_dlg_sub",
            "щоб поставити нове прев'ю перетягніть в це поле⇑ фото форматом 1:1\n(інший формат обріжеться і відцентрується)"
        )
        sub_lbl = QLabel(sub_text)
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 500; border: none; background: transparent; line-height: 1.35;")
        c_layout.addWidget(sub_lbl)

        c_layout.addStretch()

        # 3 action buttons: [Зберегти] [Скинути] [Скасувати]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # Reset button (removes custom cover and restores default from first PDF/image)
        reset_btn = QPushButton(self.t.get("cover_dlg_reset", "Скинути"))
        reset_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.16);
                color: #f87171;
                font-weight: 700;
                font-size: 13px;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 9px;
                padding: 9px 16px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.35);
                color: #ffffff;
            }
        """)
        reset_btn.clicked.connect(self._on_reset_cover)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        # Cancel button
        cancel_btn = QPushButton(self.t.get("cover_dlg_cancel", "Скасувати"))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2433;
                color: #cbd5e1;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 9px;
                padding: 9px 18px;
            }
            QPushButton:hover {
                background-color: #2a3347;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        # Save button
        self.save_btn = QPushButton(self.t.get("cover_dlg_save", "Зберегти"))
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d9488, stop:1 #2dd4bf);
                color: #0b1517;
                font-weight: 800;
                font-size: 13px;
                border: none;
                border-radius: 9px;
                padding: 9px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #14b8a6, stop:1 #5eead4);
            }
        """)
        self.save_btn.clicked.connect(self._on_save_cover)
        btn_row.addWidget(self.save_btn)

        c_layout.addLayout(btn_row)
        main_layout.addWidget(self.container)

    def _update_drop_zone_appearance(self):
        if self._new_pixmap and not self._new_pixmap.isNull():
            # Display cropped square preview scaled to fit drop zone
            scaled = self._new_pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.drop_zone.setPixmap(scaled)
            self.drop_zone.setStyleSheet("""
                QLabel {
                    background-color: #0b0e14;
                    border: 2px dashed #2dd4bf;
                    border-radius: 16px;
                }
            """)
        else:
            drop_text = self.t.get("cover_dlg_drop_text", ";) перетягни сюди ⇓\n\nабо натисни для вибору файлу")
            self.drop_zone.setText(drop_text)
            self.drop_zone.setStyleSheet("""
                QLabel {
                    background-color: rgba(22, 28, 42, 0.7);
                    border: 2px dashed rgba(45, 212, 191, 0.6);
                    border-radius: 16px;
                    color: #5eead4;
                    font-size: 15px;
                    font-weight: 700;
                }
                QLabel:hover {
                    background-color: rgba(22, 28, 42, 0.95);
                    border-color: #5eead4;
                    color: #ffffff;
                }
            """)

    def _on_drop_zone_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            from PyQt6.QtWidgets import QFileDialog
            caption = self.t.get("cover_dlg_select_prompt", "Виберіть зображення для {name}").format(name=self.manhwa_name)
            fpath, _ = QFileDialog.getOpenFileName(
                self,
                caption,
                str(self.target_dir),
                "Зображення (*.png *.jpg *.jpeg *.webp)"
            )
            if fpath:
                self._load_and_crop_image(fpath)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_zone.setStyleSheet("""
                QLabel {
                    background-color: rgba(45, 212, 191, 0.15);
                    border: 2px dashed #5eead4;
                    border-radius: 16px;
                    color: #ffffff;
                    font-size: 15px;
                    font-weight: 700;
                }
            """)

    def dragLeaveEvent(self, event):
        self._update_drop_zone_appearance()
        event.accept()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            local_path = urls[0].toLocalFile()
            if local_path and Path(local_path).suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                self._load_and_crop_image(local_path)
                event.acceptProposedAction()
                return
        self._update_drop_zone_appearance()

    def _load_and_crop_image(self, img_path: str):
        """Loads image, center-crops to 1:1 square ratio, and prepares for saving."""
        pm = QPixmap(str(img_path))
        if pm.isNull():
            return
        w = pm.width()
        h = pm.height()
        side = min(w, h)
        x = (w - side) // 2
        y = (h - side) // 2
        square_pm = pm.copy(x, y, side, side)
        self._new_pixmap = square_pm
        self._update_drop_zone_appearance()

    def _on_save_cover(self):
        if self._new_pixmap and not self._new_pixmap.isNull():
            try:
                dest = self.target_dir / "cover.jpg"
                self._new_pixmap.save(str(dest), "JPEG", 92)
                self.accept()
            except Exception as e:
                logger.error(f"Failed to save cover: {e}")
                self.reject()
        else:
            self.accept()

    def _on_reset_cover(self):
        """Removes custom cover.jpg so system generates default from Chapter 1."""
        try:
            if self.original_cover_path.exists():
                self.original_cover_path.unlink()
            self.accept()
        except Exception as e:
            logger.error(f"Failed to reset cover: {e}")
            self.reject()

    # Enable moving/dragging dialog with mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()



# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Collapsible Tree-Based Music Preset Picker (Auto + Folders > / v)
# ---------------------------------------------------------------------------
class CollapsibleMusicPresetPicker(QWidget):
    """
    Displays reading audio preset selection:
    - Top Item: Авто / Auto (clean localized)
    - Folder categories (> collapsed / v expanded):
        * <pack_name> -> list of bg/ tracks
        * my_sounds -> list of tracks
        * meme -> list of tracks
        * core -> list of tracks
    Allows user to expand folders and click any bg track to select it.
    Folder names are crisp white; selected item highlights in mint / teal.
    """
    preset_selected = pyqtSignal(str)  # emits preset data (e.g. "ai_adaptive", "pack:medieval_fantasy:kingdom-sad")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_value = "ai_adaptive"
        self._auto_label_text = "Авто"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        # Selected preset banner display
        self.header_btn = QPushButton("Авто")
        self.header_btn.setFixedHeight(42)
        self.header_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.header_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111e24, stop:1 #0c151c);
                color: #2dd4bf;
                border: 1.5px solid rgba(45, 212, 191, 0.6);
                border-radius: 9px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 700;
                text-align: left;
            }
            QPushButton:hover {
                border-color: #5eead4;
                background: #16272e;
            }
        """)
        self.header_btn.clicked.connect(self._toggle_tree_view)
        self.layout.addWidget(self.header_btn)

        # Tree widget for collapsible categories
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(18)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0b0f19;
                border: 1.5px solid rgba(45, 212, 191, 0.25);
                border-radius: 9px;
                color: #ffffff;
                font-size: 13px;
                padding: 6px;
                min-height: 200px;
                max-height: 270px;
            }
            QTreeWidget::item {
                height: 32px;
                padding-left: 6px;
                border-radius: 6px;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: rgba(45, 212, 191, 0.12);
                color: #ffffff;
            }
            QTreeWidget::item:selected {
                background-color: rgba(45, 212, 191, 0.25);
                color: #2dd4bf;
                font-weight: 700;
                border-left: 3px solid #2dd4bf;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children {
                image: none;
            }
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children {
                image: none;
            }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.layout.addWidget(self.tree)
        # Initially closed by default; opens upon clicking header button
        self.tree.setVisible(False)

    def _toggle_tree_view(self):
        self.tree.setVisible(not self.tree.isVisible())

    def _on_item_expanded(self, item: QTreeWidgetItem):
        raw_title = item.data(0, Qt.ItemDataRole.UserRole + 1) or item.text(0)
        clean_title = raw_title.replace("📁 >  ", "").replace("📁 v  ", "")
        item.setText(0, f"📁 v  {clean_title}")

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        raw_title = item.data(0, Qt.ItemDataRole.UserRole + 1) or item.text(0)
        clean_title = raw_title.replace("📁 >  ", "").replace("📁 v  ", "")
        item.setText(0, f"📁 >  {clean_title}")

    def _on_item_clicked(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            # It's a folder item -> toggle collapse/expand
            item.setExpanded(not item.isExpanded())
            return

        self._current_value = str(data)
        self._update_header_text(item.text(0).strip())
        self.preset_selected.emit(self._current_value)

    def _update_header_text(self, display_text: str):
        if self._current_value == "ai_adaptive":
            self.header_btn.setText(self._auto_label_text)
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #111e24, stop:1 #0c151c);
                    color: #2dd4bf;
                    border: 1.5px solid rgba(45, 212, 191, 0.7);
                    border-radius: 9px;
                    padding: 6px 14px;
                    font-size: 13px;
                    font-weight: 700;
                    text-align: left;
                }
                QPushButton:hover {
                    border-color: #5eead4;
                    background: #16272e;
                }
            """)
        else:
            clean = display_text.replace("🎵", "").strip()
            self.header_btn.setText(f"🎵 {clean}")
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #112327, stop:1 #0c181c);
                    color: #5eead4;
                    border: 1.5px solid #2dd4bf;
                    border-radius: 9px;
                    padding: 6px 14px;
                    font-size: 13px;
                    font-weight: 700;
                    text-align: left;
                }
                QPushButton:hover {
                    border-color: #99f6e4;
                    background: #162d33;
                }
            """)

    def currentData(self) -> str:
        return self._current_value

    def populate(self, sounds_root: Path, auto_title: str = "Авто"):
        self.tree.clear()
        sounds_root = Path(sounds_root)
        # Strip any accidental emojis or brackets from auto_title
        clean_auto = auto_title.replace("⚡", "").strip()
        if "(" in clean_auto:
            clean_auto = clean_auto.split("(")[0].strip()
        if not clean_auto:
            clean_auto = "Авто"
        self._auto_label_text = clean_auto

        # 1. Top Level Auto Item (Clean, no emojis, no brackets)
        auto_item = QTreeWidgetItem(self.tree)
        auto_item.setText(0, clean_auto)
        auto_item.setData(0, Qt.ItemDataRole.UserRole, "ai_adaptive")
        auto_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        auto_item.setForeground(0, QBrush(QColor("#2dd4bf")))

        # Helper to style folder item
        def _add_folder(name: str, count: int) -> QTreeWidgetItem:
            f_item = QTreeWidgetItem(self.tree)
            lbl = f"📁 >  {name} ({count})"
            f_item.setText(0, lbl)
            f_item.setData(0, Qt.ItemDataRole.UserRole + 1, lbl)
            f_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            f_item.setForeground(0, QBrush(QColor("#ffffff")))
            return f_item

        def _add_track(parent_item: QTreeWidgetItem, track_name: str, preset_val: str):
            t_item = QTreeWidgetItem(parent_item)
            clean_name = track_name.replace("-", " ").replace("_", " ")
            t_item.setText(0, f"   🎵 {clean_name}")
            t_item.setData(0, Qt.ItemDataRole.UserRole, preset_val)
            t_item.setForeground(0, QBrush(QColor("#cbd5e1")))

        # 2. Packs Folder categories (sounds/packs/<pack>/bg)
        packs_dir = sounds_root / "packs"
        if packs_dir.exists():
            for pack_folder in sorted([p for p in packs_dir.iterdir() if p.is_dir()]):
                pack_name = pack_folder.name
                bg_dir = pack_folder / "bg"
                bg_files = sorted(list(bg_dir.glob("*.*"))) if bg_dir.exists() else []
                bg_files = [f for f in bg_files if f.suffix.lower() in [".mp3", ".ogg", ".wav"]]

                pack_item = _add_folder(pack_name, len(bg_files))
                for track in bg_files:
                    _add_track(pack_item, track.stem, f"pack:{pack_name}:{track.stem}")

        # 3. My sounds category
        my_sounds_dir = sounds_root / "my_sounds"
        my_files = sorted(list(my_sounds_dir.glob("*.*"))) if my_sounds_dir.exists() else []
        my_files = [f for f in my_files if f.suffix.lower() in [".mp3", ".ogg", ".wav"]]
        my_item = _add_folder("my_sounds", len(my_files))
        for track in my_files:
            _add_track(my_item, track.stem, f"my_sounds:{track.stem}")

        # 4. Meme category
        meme_dir = sounds_root / "meme"
        meme_files = sorted(list(meme_dir.glob("*.*"))) if meme_dir.exists() else []
        meme_files = [f for f in meme_files if f.suffix.lower() in [".mp3", ".ogg", ".wav"]]
        meme_item = _add_folder("meme", len(meme_files))
        for track in meme_files:
            _add_track(meme_item, track.stem, f"meme:{track.stem}")

        # 5. Core soundtrack category (if exists)
        core_bg_dir = sounds_root / "core" / "bg"
        core_files = sorted(list(core_bg_dir.glob("*.*"))) if core_bg_dir.exists() else []
        core_files = [f for f in core_files if f.suffix.lower() in [".mp3", ".ogg", ".wav"] and f.stem != "test_sound"]
        if core_files:
            core_item = _add_folder("core", len(core_files))
            for track in core_files:
                _add_track(core_item, track.stem, f"core:{track.stem}")

        # Sync selection
        self.setCurrentData(self._current_value)

    def setCurrentData(self, target_val: str):
        self._current_value = target_val or "ai_adaptive"
        found = False
        def _check_item(it: QTreeWidgetItem):
            nonlocal found
            data = it.data(0, Qt.ItemDataRole.UserRole)
            if data and data == target_val:
                self.tree.setCurrentItem(it)
                self._update_header_text(it.text(0))
                p = it.parent()
                if p:
                    p.setExpanded(True)
                found = True
                return
            for i in range(it.childCount()):
                _check_item(it.child(i))

        for idx in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(idx)
            _check_item(top)
            if found:
                break

        if not found:
            self._current_value = "ai_adaptive"
            self.header_btn.setText(self._auto_label_text)
            if self.tree.topLevelItemCount() > 0:
                self.tree.setCurrentItem(self.tree.topLevelItem(0))



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
    change_cover_clicked = pyqtSignal(str)         # manhwa_name
    reclassify_clicked = pyqtSignal(str)           # manhwa_name

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
        self.cover_lbl.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cover_lbl.setToolTip(self.lang_dict.get("card_click_to_read", "Натисніть для відкриття тайтлу"))
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
            # Check configured display mode from app config if available
            disp_mode = "chapter"
            p = self.parent()
            while p is not None:
                if hasattr(p, "cfg"):
                    disp_mode = p.cfg.get("progress_display_mode", "chapter")
                    break
                p = p.parent()

            if disp_mode == "overall" and "overall_pct" in self.bookmark_info:
                val = float(self.bookmark_info["overall_pct"])
                bm_text = f"Ch. {ch_num} ({val:.1f}%)"
            else:
                raw_pct = self.bookmark_info.get("percent")
                if raw_pct is None:
                    prog = self.bookmark_info.get("chapter_progress") or self.bookmark_info.get("scroll_ratio", 0.0)
                    raw_pct = float(prog) * 100 if float(prog) <= 1.0 else float(prog)
                bm_text = f"Ch. {ch_num} ({float(raw_pct):.1f}%)"

        info_lbl = QLabel(f"📁 {ch_count}  •  🔖 {bm_text}")
        info_lbl.setStyleSheet("font-size: 11px; color: #9ca3af; font-weight: 500;")
        layout.addWidget(info_lbl)

        # Language badge & Linked Translations Row
        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(5)

        pills_badge = QLabel("🌐")
        pills_badge.setStyleSheet("font-size: 11px; color: #94a3b8;")
        pills_row.addWidget(pills_badge)

        card_lang = detect_title_language(self.manhwa_name)
        my_lang_lbl = QLabel(card_lang)
        my_lang_lbl.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.25);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.6);
            border-radius: 5px;
            padding: 1px 6px;
            font-size: 10px;
            font-weight: 800;
        """)
        pills_row.addWidget(my_lang_lbl)

        # Show other translations if they are actually DIFFERENT languages
        for item in self.linked_translations:
            l_code = item.get("lang", "").upper()
            if l_code == card_lang:
                continue
            l_target = item.get("target") or item.get("title", "")
            pill_btn = QPushButton(l_code)
            pill_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            tip = self.lang_dict.get("switch_trans_tip", "Перейти до {lang} версії: {title}").format(
                lang=l_code, title=item.get("title", l_target)
            )
            pill_btn.setToolTip(tip)
            pill_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(59, 130, 246, 0.15);
                    color: #60a5fa;
                    border: 1px solid rgba(59, 130, 246, 0.4);
                    border-radius: 5px;
                    padding: 1px 6px;
                    font-size: 10px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: rgba(59, 130, 246, 0.35);
                    color: #ffffff;
                    border-color: #3b82f6;
                }
            """)
            pill_btn.clicked.connect(lambda _, it=item: self.switch_translation_clicked.emit(it))
            pills_row.addWidget(pill_btn)

        pills_row.addStretch()
        layout.addLayout(pills_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        read_btn = QPushButton(self.lang_dict["read_btn"])
        read_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        read_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbbf24, stop:1 #d97706);
                color: #121008;
                font-size: 13px;
                font-weight: 800;
                border-radius: 9px;
                padding: 8px 10px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fcd34d, stop:1 #f59e0b);
            }
        """)
        read_btn.clicked.connect(lambda: self.read_clicked.emit(self.manhwa_name))
        btn_row.addWidget(read_btn, stretch=3)

        # 1. Change cover button
        cover_btn = QPushButton("🖼️")
        cover_btn.setToolTip(self.lang_dict.get("card_cover_tip", "Змінити обкладинку тайтлу"))
        cover_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cover_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.16);
                color: #60a5fa;
                font-size: 13px;
                border: 1px solid rgba(59, 130, 246, 0.35);
                border-radius: 9px;
                padding: 6px 7px;
            }
            QPushButton:hover {
                background-color: rgba(59, 130, 246, 0.35);
                color: #ffffff;
            }
        """)
        cover_btn.clicked.connect(lambda: self.change_cover_clicked.emit(self.manhwa_name))
        btn_row.addWidget(cover_btn)

        # 2. Re-analyze / check genre tag button
        reclass_btn = QPushButton("↺")
        reclass_btn.setToolTip(self.lang_dict.get("card_reclass_tip", "Перевірити / оновити жанр та сеттинг через ШІ"))
        reclass_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reclass_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.16);
                color: #2dd4bf;
                font-size: 14px;
                font-weight: 800;
                border: 1px solid rgba(45, 212, 191, 0.35);
                border-radius: 9px;
                padding: 6px 7px;
            }
            QPushButton:hover {
                background-color: rgba(45, 212, 191, 0.35);
                color: #ffffff;
            }
        """)
        reclass_btn.clicked.connect(lambda: self.reclassify_clicked.emit(self.manhwa_name))
        btn_row.addWidget(reclass_btn)

        # 3. Delete button
        del_btn = QPushButton("🗑️")
        del_btn.setToolTip(self.lang_dict["del_tooltip"])
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.16);
                color: #f87171;
                font-size: 13px;
                font-weight: 700;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 9px;
                padding: 6px 7px;
            }
            QPushButton:hover {
                background-color: rgba(220, 38, 38, 0.35);
                color: #ffffff;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.manhwa_name))
        btn_row.addWidget(del_btn)

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

    def mousePressEvent(self, event):
        """Allows opening reader when clicking anywhere on the card/cover, except buttons."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if clicked on a child button (cover_btn, reclass_btn, del_btn, etc.)
            child = self.childAt(event.position().toPoint())
            if not isinstance(child, QPushButton):
                self.read_clicked.emit(self.manhwa_name)
                event.accept()
                return
        super().mousePressEvent(event)


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
            disp_mode = "chapter"
            p = self.parent()
            while p is not None:
                if hasattr(p, "cfg"):
                    disp_mode = p.cfg.get("progress_display_mode", "chapter")
                    break
                p = p.parent()

            if disp_mode == "overall" and "overall_pct" in self.bookmark_info:
                val = float(self.bookmark_info["overall_pct"])
                bm_text = f"Ch. {ch_num} ({val:.1f}%)"
            else:
                raw_pct = self.bookmark_info.get("percent")
                if raw_pct is None:
                    prog = self.bookmark_info.get("chapter_progress") or self.bookmark_info.get("scroll_ratio", 0.0)
                    raw_pct = float(prog) * 100 if float(prog) <= 1.0 else float(prog)
                bm_text = f"Ch. {ch_num} ({float(raw_pct):.1f}%)"

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

        # Language badge & Linked Translations Row
        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(0, 0, 0, 0)
        pills_row.setSpacing(5)

        pills_badge = QLabel("🌐")
        pills_badge.setStyleSheet("font-size: 11px; color: #94a3b8;")
        pills_row.addWidget(pills_badge)

        card_lang = (self.cloud_entry.get("lang") or detect_title_language(self.full_title)).upper()
        my_lang_lbl = QLabel(card_lang)
        my_lang_lbl.setStyleSheet("""
            background-color: rgba(59, 130, 246, 0.25);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.6);
            border-radius: 5px;
            padding: 1px 6px;
            font-size: 10px;
            font-weight: 800;
        """)
        pills_row.addWidget(my_lang_lbl)

        for item in self.linked_translations:
            l_code = item.get("lang", "").upper()
            if l_code == card_lang:
                continue
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


# ---------------------------------------------------------------------------
# Seamless Continuous Webtoon Strip
# ---------------------------------------------------------------------------
class WebtoonScrollCanvas(QScrollArea):
    scroll_progress_signal = pyqtSignal(int, float, float)  # ch_num, chapter_pct, overall_pct
    chapter_changed_signal = pyqtSignal(int)
    mode_changed_signal = pyqtSignal(str)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.reading_width = cfg.get("reading_width", 880)
        self.zoom = cfg.get("zoom", 1.0)
        self.bg_color = cfg.get("bg_color", "transparent")

        self.current_manhwa_name = ""
        self.current_manhwa_path: Optional[Path] = None
        self.loaded_chapters: Set[int] = set()
        self.chapter_modes: Dict[int, str] = {}
        self.active_mode = "jpeg"
        self.page_labels: List[Tuple[int, QLabel, str]] = []
        # Bounded LRU Pixmap cache (max 120 full-size page pixmaps in RAM)
        from collections import OrderedDict
        self.pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        self.max_pixmap_items = 120

        # Preloaded Audio Timelines cache (ch_num -> timeline cues)
        self.preloaded_timelines: Dict[int, list] = {}
        self._preloading_chapters: Set[int] = set()

        self.active_ch_num = 1
        self.is_restoring_scroll = False
        self.is_cloud_mode = False
        self.rolling_cache: Optional[RollingRAMCache] = None
        self.cloud_chapter_map: Dict[int, int] = {}

        self.scale_timer = QTimer(self)
        self.scale_timer.setSingleShot(True)
        self.scale_timer.setInterval(80)
        self.scale_timer.timeout.connect(self._do_rescale)

        # Lightweight Velocity & Ahead-Cue Predictor (zero disk overhead)
        self._last_scroll_time = 0.0
        self._last_scroll_val = 0
        self._scroll_velocity_px_s = 0.0

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.container = QWidget()
        self.main_layout = QHBoxLayout(self.container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.strip_widget = QWidget()
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
        self.set_bg_color(self.bg_color)
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def _cache_pixmap(self, key: str, pm: QPixmap):
        """Puts pixmap into bounded LRU cache, evicting oldest if capacity exceeded."""
        if key in self.pixmap_cache:
            self.pixmap_cache.move_to_end(key)
        self.pixmap_cache[key] = pm
        while len(self.pixmap_cache) > self.max_pixmap_items:
            self.pixmap_cache.popitem(last=False)

    def _get_pixmap(self, key: str) -> Optional[QPixmap]:
        """Gets pixmap from LRU cache, refreshing its recency."""
        if key in self.pixmap_cache:
            self.pixmap_cache.move_to_end(key)
            return self.pixmap_cache[key]
        return None

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

    def paintEvent(self, event):
        if self.bg_color != "transparent":
            painter = QPainter(self.viewport())
            painter.fillRect(self.viewport().rect(), QColor(self.bg_color))
            painter.end()
        super().paintEvent(event)

    def set_bg_color(self, hex_color: str):
        self.bg_color = hex_color
        # Always maintain transparent widget baseline so Qt does not lock alpha channel
        self.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        self.viewport().setStyleSheet("background: transparent;")
        self.container.setStyleSheet("background: transparent;")
        self.strip_widget.setStyleSheet("background: transparent;")
        self.viewport().update()

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

    def _get_parent_app(self):
        p = self.parent()
        while p is not None and not hasattr(p, "sound_engine"):
            p = p.parent()
        return p

    def _find_chapter_folder(self, ch_num: int) -> Optional[Path]:
        if not self.current_manhwa_path or not self.current_manhwa_path.exists():
            return None
        for cand in self.current_manhwa_path.iterdir():
            if cand.is_dir() and not cand.name.startswith("."):
                if extract_chapter_number(cand.name) == ch_num:
                    return cand
        return self.current_manhwa_path / f"chapter_{ch_num:03d}"

    def preload_sound_timeline_for_chapter(self, ch_num: int):
        """Asynchronously preloads or generates sound timeline for next chapter in background."""
        if ch_num in self.preloaded_timelines or ch_num in self._preloading_chapters:
            return
        if not self.current_manhwa_path:
            return
        p = self._get_parent_app()
        if not p or not getattr(p, "sound_engine", None) or not getattr(p.sound_engine, "is_enabled", False):
            return
        preset_mode = p.cfg.get("music_preset", "ai_adaptive")
        if preset_mode != "ai_adaptive" or not getattr(p, "ai_analyzer", None):
            return

        target_ch_dir = self._find_chapter_folder(ch_num)
        if not target_ch_dir or not target_ch_dir.exists():
            return

        self._preloading_chapters.add(ch_num)

        def _worker():
            try:
                tl = p.ai_analyzer.get_or_analyze_chapter(target_ch_dir)
                if tl:
                    self.preloaded_timelines[ch_num] = tl
            except Exception as e:
                logger.debug(f"[WebtoonCanvas] Preload timeline error for ch {ch_num}: {e}")
            finally:
                self._preloading_chapters.discard(ch_num)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _switch_sound_timeline_to_chapter(self, ch_num: int):
        """Seamlessly applies sound timeline for current chapter without freezing."""
        p = self._get_parent_app()
        if not p or not getattr(p, "sound_engine", None) or not getattr(p.sound_engine, "is_enabled", False):
            return
        preset_mode = p.cfg.get("music_preset", "ai_adaptive")
        if preset_mode != "ai_adaptive":
            track_name = preset_mode.split(":", 1)[-1] if ":" in preset_mode else preset_mode
            p.sound_engine.set_timeline([])
            p.sound_engine.play_ambient(track_name)
            p.sound_engine.set_chapter_loading(False)
            return

        # Detect title profile and propagate setting pack to sound_engine
        if getattr(p, "title_classifier", None) and self.current_manhwa_name:
            prof = p.title_classifier.get_title_profile(self.current_manhwa_name)
            if prof:
                p.sound_engine.set_setting_pack(prof.get("setting_pack"))

        # 1. Use in-RAM preloaded timeline if available
        if ch_num in self.preloaded_timelines:
            tl = self.preloaded_timelines[ch_num]
            p.sound_engine.set_timeline(tl)
            p.sound_engine.set_chapter_loading(False)
            return

        target_ch_dir = self._find_chapter_folder(ch_num)
        if not target_ch_dir or not getattr(p, "ai_analyzer", None):
            return

        cache_p = target_ch_dir / "sound_timeline.json"
        if cache_p.exists():
            tl = p.ai_analyzer.get_or_analyze_chapter(target_ch_dir)
            self.preloaded_timelines[ch_num] = tl
            p.sound_engine.set_timeline(tl)
            p.sound_engine.set_chapter_loading(False)
        else:
            p.sound_engine.set_chapter_loading(True)

            def _async_load():
                try:
                    tl = p.ai_analyzer.get_or_analyze_chapter(target_ch_dir)
                    self.preloaded_timelines[ch_num] = tl
                    QTimer.singleShot(0, lambda: p.sound_engine.set_timeline(tl))
                except Exception as ex:
                    logger.error(f"Async timeline error: {ex}")
                finally:
                    QTimer.singleShot(150, lambda: p.sound_engine.set_chapter_loading(False))

            import threading
            threading.Thread(target=_async_load, daemon=True).start()

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

        # Activate current sound timeline and pre-generate next chapter timeline!
        self._switch_sound_timeline_to_chapter(start_ch_num)
        self.preload_sound_timeline_for_chapter(start_ch_num + 1)

    def clear_canvas(self):
        while self.strip_layout.count():
            item = self.strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.page_labels.clear()
        self.loaded_chapters.clear()
        self.chapter_modes.clear()
        self.pixmap_cache.clear()
        self.preloaded_timelines.clear()
        self._preloading_chapters.clear()
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
            self._cache_pixmap(cache_key, pm)
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
            self._cache_pixmap(cache_key, pm)
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
                pm = self._get_pixmap(sp)
                if pm is None:
                    pm = QPixmap(sp)
                    self._cache_pixmap(sp, pm)

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
                    self._cache_pixmap(cache_key, pm)

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
            pm = self._get_pixmap(cache_key)
            if pm is None:
                pm = QPixmap(cache_key)
                self._cache_pixmap(cache_key, pm)
            if not pm.isNull():
                lbl.setPixmap(pm.scaledToWidth(target_w, Qt.TransformationMode.SmoothTransformation))
        self.strip_widget.setUpdatesEnabled(True)

    def on_scroll(self, value: int):
        if self.is_restoring_scroll or not self.page_labels:
            return

        max_scroll = self.verticalScrollBar().maximum()
        if max_scroll <= 0:
            return

        viewport_h = self.viewport().height()

        # -------------------------------------------------------------
        # 1. Real-time Velocity Tracker with Exponential Smoothing
        # -------------------------------------------------------------
        import time
        now = time.time()
        dt = now - self._last_scroll_time if self._last_scroll_time > 0 else 0.1
        dy = abs(value - self._last_scroll_val)
        self._last_scroll_time = now
        self._last_scroll_val = value

        inst_velocity = dy / max(0.01, dt)
        self._scroll_velocity_px_s = 0.7 * self._scroll_velocity_px_s + 0.3 * inst_velocity

        # -------------------------------------------------------------
        # 2. Identify Visible Chapter, Page in Chapter, and Chapter Geometry
        # -------------------------------------------------------------
        # Focus point for reader awareness (roughly 40% into the viewport)
        focus_y = value + int(viewport_h * 0.40)

        visible_ch_num = self.active_ch_num
        page_idx_in_ch = 1
        total_pages_in_ch = 1

        # Track bounds of each chapter in the continuous strip
        ch_bounds: Dict[int, Dict[str, int]] = {}
        ch_pages: Dict[int, list] = {}

        accum_y = 0
        focus_page_found = False

        for idx, item in enumerate(self.page_labels):
            ch = item[0]
            lbl = item[1]
            lh = lbl.height()

            if ch not in ch_bounds:
                ch_bounds[ch] = {"start_y": accum_y, "height": 0}
                ch_pages[ch] = []
            ch_bounds[ch]["height"] += lh
            ch_pages[ch].append((accum_y, lh))

            if not focus_page_found and (accum_y + lh > focus_y):
                visible_ch_num = ch
                page_idx_in_ch = len(ch_pages[ch])
                focus_page_found = True

            accum_y += lh

        if visible_ch_num in ch_pages:
            total_pages_in_ch = max(1, len(ch_pages[visible_ch_num]))

        # -------------------------------------------------------------
        # 3. Handle Chapter Boundary Crossing (Update UI & Sound Timeline)
        # -------------------------------------------------------------
        if visible_ch_num != self.active_ch_num:
            self.active_ch_num = visible_ch_num
            self.chapter_changed_signal.emit(visible_ch_num)
            self._switch_sound_timeline_to_chapter(visible_ch_num)
            # Preload next chapter sound timeline ahead
            self.preload_sound_timeline_for_chapter(visible_ch_num + 1)

        # -------------------------------------------------------------
        # 4. Accurate Chapter Percentage & Overall Title Percentage
        # -------------------------------------------------------------
        ch_geom = ch_bounds.get(visible_ch_num, {"start_y": 0, "height": max_scroll})
        ch_start = ch_geom["start_y"]
        ch_h = max(1, ch_geom["height"])

        ch_eff_scroll = max(0, value - ch_start)
        ch_eff_max = max(1, ch_h - viewport_h)
        chapter_pct = min(1.0, max(0.0, ch_eff_scroll / ch_eff_max))

        # Overall percentage across total known chapters
        p_app = self._get_parent_app()
        total_chs = 1
        if p_app and hasattr(p_app, "chapter_combo") and p_app.chapter_combo.count() > 0:
            total_chs = p_app.chapter_combo.count()

        overall_pct = min(100.0, max(0.0, ((max(0, visible_ch_num - 1) + chapter_pct) / max(1, total_chs)) * 100.0))

        # Emit updated progress signal with BOTH metrics
        self.scroll_progress_signal.emit(visible_ch_num, chapter_pct, overall_pct)

        # -------------------------------------------------------------
        # 5. Configurable / Adaptive Next Chapter Preloading
        # -------------------------------------------------------------
        if self.is_cloud_mode and self.rolling_cache:
            self.rolling_cache.on_scroll_threshold_reached(visible_ch_num, chapter_pct)
        else:
            preload_mode = self.cfg.get("preload_mode", "adaptive")
            if preload_mode != "disabled":
                threshold = 0.80  # Default ~4/5 chapter
                if preload_mode == "manual":
                    threshold = max(0.01, min(1.0, self.cfg.get("manual_preload_threshold", 75) / 100.0))
                elif preload_mode == "adaptive":
                    # If reader scrolls fast, shift preload point earlier so chapter renders in advance!
                    if self._scroll_velocity_px_s > 200:
                        speed_lead = min(0.35, (self._scroll_velocity_px_s - 200) / 1500.0)
                        threshold = max(0.45, 0.80 - speed_lead)

                if chapter_pct >= threshold:
                    next_ch = visible_ch_num + 1
                    if next_ch not in self.loaded_chapters:
                        self.append_chapter(next_ch)
                        self.preload_sound_timeline_for_chapter(next_ch)
                        self.preload_sound_timeline_for_chapter(next_ch + 1)

        # -------------------------------------------------------------
        # 6. Notify Sound Engine with Local Chapter Page & Lookahead
        # -------------------------------------------------------------
        if p_app and getattr(p_app, "sound_engine", None) and getattr(p_app.sound_engine, "is_enabled", False):
            try:
                lookahead_px = min(viewport_h * 2.0, self._scroll_velocity_px_s * 0.8) if self._scroll_velocity_px_s > 150 else 0
                sound_focus_y = value + int(viewport_h * 0.70) + int(lookahead_px)

                sound_page = page_idx_in_ch
                sound_frac = 0
                curr_y = 0

                for item in self.page_labels:
                    if item[0] != visible_ch_num:
                        curr_y += item[1].height()
                        continue
                    lh = item[1].height()
                    if curr_y + lh > sound_focus_y:
                        # Found target page within current chapter
                        offset = max(0, sound_focus_y - curr_y)
                        sound_frac = min(3, max(0, int((offset / max(1, lh)) * 4)))
                        break
                    curr_y += lh

                p_app.sound_engine.on_scroll_position(sound_page, sound_frac)
            except Exception as e:
                logger.debug(f"[WebtoonCanvas] Sound cue error: {e}")

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
        if candidate.is_absolute():
            self.lib_dir = candidate
        else:
            self.lib_dir = (BASE_DIR / candidate).resolve()
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

        # Sounds directory resolution (relative to BASE_DIR or custom absolute path)
        raw_sounds = self.cfg.get("sounds_path", "sounds")
        candidate_sounds = Path(raw_sounds)
        if candidate_sounds.is_absolute():
            self.sounds_dir = candidate_sounds
        else:
            self.sounds_dir = (BASE_DIR / candidate_sounds).resolve()
        self.sounds_dir.mkdir(parents=True, exist_ok=True)

        # Sound Engine & AI Atmosphere Analyzer
        gemini_key = self.cfg.get("gemini_api_key", "")
        self.ai_analyzer = AISoundAnalyzer(api_key=gemini_key, sounds_dir=self.sounds_dir) if AISoundAnalyzer is not None else None
        self.title_classifier = TitleClassifier(api_key=gemini_key) if TitleClassifier is not None else None
        if SoundEngine is not None:
            self.sound_engine = SoundEngine(self, sounds_dir=self.sounds_dir)
            self.sound_engine.set_enabled(self.cfg.get("music_enabled", False))
            self.sound_engine.set_volume(self.cfg.get("music_volume", 40))
        else:
            self.sound_engine = None

        # Dedicated test sound player for volume calibration in Settings
        self._test_audio_out = QAudioOutput(self)
        self._test_audio_player = QMediaPlayer(self)
        self._test_audio_player.setAudioOutput(self._test_audio_out)

        # Kick off background scan for unclassified titles (rate limited <= 1 req/min)
        if self.title_classifier and gemini_key:
            QTimer.singleShot(2500, lambda: self.title_classifier.scan_unclassified_titles(self.lib_dir))

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
        self.filter_lang_combo.addItem(self.t.get("filter_lang_ru", "🇷🇺 RU"), "RU")
        self.filter_lang_combo.addItem(self.t.get("filter_lang_raw", "🌐 RAW / Інші"), "RAW")
        idx = self.filter_lang_combo.findData(self.filter_lang)
        if idx >= 0:
            self.filter_lang_combo.setCurrentIndex(idx)
        else:
            self.filter_lang_combo.setCurrentIndex(0)
            self.filter_lang = "ALL"
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
        detected = detect_title_language(title_name, item_lang)
        if fl == "RAW":
            return detected not in ["UA", "EN", "RU"]
        return fl == detected

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
            card.change_cover_clicked.connect(self.on_change_manhwa_cover)
            card.reclassify_clicked.connect(self.on_reclassify_manhwa)

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

            if not self._matches_lang(n_name, None):
                continue

            bm = bookmarks.get(n_name, {})
            try:
                files = [f for f in n_path.iterdir() if f.is_file() and not f.name.startswith(".")]
                total_chs = len(files) if files else 1
            except Exception:
                total_chs = 1

            if not self._matches_progress(bm, total_chs):
                continue

            card = ManhwaCard(n_name, n_path, bm, self.t)
            card.read_clicked.connect(lambda name, p=n_path: self.open_novel_reader(name, p))
            card.delete_clicked.connect(self.confirm_delete_manhwa)
            card.change_cover_clicked.connect(self.on_change_manhwa_cover)
            card.reclassify_clicked.connect(self.on_reclassify_manhwa)

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
        saved_bm = self.cfg.get("bookmarks", {}).get(novel_name, {})
        self.novel_reader_widget.load_novel(novel_path, novel_name, saved_bookmark=saved_bm)
        # Switch to the novel reader page in stack
        self.stack.setCurrentWidget(self.novel_reader_widget)

    def _on_novel_progress_changed(self, novel_name: str, ch_idx: int, scroll_ratio: float, overall_pct: float):
        if "bookmarks" not in self.cfg:
            self.cfg["bookmarks"] = {}
        sb_val = 0
        if hasattr(self, "novel_reader_widget") and hasattr(self.novel_reader_widget, "text_viewer"):
            sb_val = self.novel_reader_widget.text_viewer.verticalScrollBar().value()
        self.cfg["bookmarks"][novel_name] = {
            "chapter": ch_idx + 1,
            "scroll_ratio": scroll_ratio,
            "chapter_progress": scroll_ratio,
            "scroll_value": sb_val,
            "scroll_y": sb_val,
            "overall_pct": overall_pct,
            "percent": overall_pct
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

    def on_change_manhwa_cover(self, manhwa_name: str):
        """Allows user to set or change cover via drag-and-drop dialog with 1:1 auto-crop."""
        target_dir = self.lib_dir / manhwa_name
        if not target_dir.exists():
            novels_dir = self.lib_dir / "novels_library" / manhwa_name
            if novels_dir.exists():
                target_dir = novels_dir

        dlg = ChangeCoverDialog(manhwa_name, target_dir, t=self.t, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_catalog()

    def on_reclassify_manhwa(self, manhwa_name: str):
        """Re-triggers setting & genre AI classification for the title."""
        target_dir = self.lib_dir / manhwa_name
        if not target_dir.exists():
            novels_dir = self.lib_dir / "novels_library" / manhwa_name
            if novels_dir.exists():
                target_dir = novels_dir

        if not hasattr(self, "title_classifier") or not self.title_classifier:
            err_title = self.t.get("reclass_dlg_not_ready_title", "ШІ Класифікатор не готовий")
            err_msg = self.t.get(
                "reclass_dlg_not_ready_msg",
                "Модуль TitleClassifier не ініціалізовано або відсутній Gemini API ключ у налаштуваннях."
            )
            NoticeDialog(
                f"ಠ_ಠ {err_title}",
                err_msg,
                btn_text=self.t.get("ok_btn", "Зрозуміло"),
                parent=self
            ).exec()
            return

        self.title_classifier.queue_title_analysis(target_dir, priority_first=True, force=True)
        ok_title = self.t.get("reclass_dlg_sent_title", "Запит надіслано!")
        ok_msg = self.t.get(
            "reclass_dlg_sent_msg",
            "ШІ отримав запит на аналіз жанру та сеттингу для:\n«{name}».\n\nЗапит виконується у фоні (ліміт: 1 запит/хв). Коли аналіз завершиться, відповідний пак підтягнеться автоматично!"
        ).format(name=manhwa_name)
        NoticeDialog(
            f"(•‿•) {ok_title}",
            ok_msg,
            btn_text=self.t.get("notice_dl_success_btn", "Гаразд"),
            parent=self
        ).exec()

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
        self.reader_title_lbl.setMinimumWidth(180)
        self.reader_title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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

        zoom_minus = QPushButton("－")
        zoom_minus.setFixedSize(26, 26)
        zoom_minus.setProperty("class", "btnSecondary")
        zoom_minus.clicked.connect(lambda: self.adjust_zoom(-0.1))
        tb_layout.addWidget(zoom_minus)

        self.zoom_lbl = QLabel(f"{int(self.cfg.get('zoom', 1.0) * 100)}%")
        self.zoom_lbl.setStyleSheet("font-weight: 600; color: #9ca3af; min-width: 38px; qproperty-alignment: AlignCenter;")
        tb_layout.addWidget(self.zoom_lbl)

        zoom_plus = QPushButton("＋")
        zoom_plus.setFixedSize(26, 26)
        zoom_plus.setProperty("class", "btnSecondary")
        zoom_plus.clicked.connect(lambda: self.adjust_zoom(0.1))
        tb_layout.addWidget(zoom_plus)

        self.theme_lbl = QLabel(self.t["theme_lbl"])
        tb_layout.addWidget(self.theme_lbl)
        bg_grp = QHBoxLayout()
        bg_grp.setSpacing(5)

        # 3 Backgrounds: Pure Black, Pure White, Transparent (Window Theme)
        bg_options = [
            ("#000000", "border: 2px solid rgba(255, 255, 255, 0.4); background-color: #000000;"),
            ("#ffffff", "border: 2px solid rgba(255, 255, 255, 0.4); background-color: #ffffff;"),
            ("transparent", "border: 2px dashed #38bdf8; background-color: transparent;")
        ]
        for hex_col, btn_style in bg_options:
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    {btn_style}
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
        self.zen_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
            }
        """)
        self.zen_btn.clicked.connect(self.toggle_zen_mode)
        tb_layout.addWidget(self.zen_btn)

        layout.addWidget(self.reader_toolbar)

        self.canvas = WebtoonScrollCanvas(self.cfg)
        self.canvas.scroll_progress_signal.connect(self.on_reader_progress)
        self.canvas.chapter_changed_signal.connect(self.on_reader_chapter_changed)
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
        new_zoom = round(self.canvas.zoom + delta, 2)
        new_zoom = max(0.5, min(2.0, new_zoom))
        self.canvas.set_zoom(new_zoom)
        self.cfg["zoom"] = new_zoom
        self.zoom_lbl.setText(f"{int(round(new_zoom * 100))}%")
        save_config(self.cfg)

    def set_background_color(self, hex_color: str):
        self.cfg["bg_color"] = hex_color
        self.canvas.set_bg_color(hex_color)
        save_config(self.cfg)

    def on_reader_chapter_changed(self, ch_num: int):
        """Seamlessly updates the chapter combo selector when user scrolls into the next chapter."""
        if hasattr(self, "chapter_combo") and self.chapter_combo.count() > 0:
            idx = self.chapter_combo.findData(ch_num)
            if idx >= 0 and self.chapter_combo.currentIndex() != idx:
                self.chapter_combo.blockSignals(True)
                self.chapter_combo.setCurrentIndex(idx)
                self.chapter_combo.blockSignals(False)

    def on_reader_progress(self, ch_num: int, ch_pct: float, overall_pct: Optional[float] = None):
        if not self.current_reading_manhwa:
            return
        scroll_y = self.canvas.verticalScrollBar().value()
        if "bookmarks" not in self.cfg:
            self.cfg["bookmarks"] = {}

        if overall_pct is None:
            # Fallback calculation if called with 2 arguments
            overall_val = round(ch_pct * 100, 1)
            try:
                total_chs = len(self.chapter_combo) if hasattr(self, "chapter_combo") else 1
                if total_chs > 1:
                    overall_val = round(((max(0, ch_num - 1) + ch_pct) / total_chs) * 100, 1)
            except Exception:
                pass
        else:
            overall_val = round(overall_pct, 1)

        self.cfg["bookmarks"][self.current_reading_manhwa] = {
            "chapter": ch_num,
            "scroll_y": scroll_y,
            "chapter_progress": round(ch_pct, 4),
            "percent": round(ch_pct * 100, 1),
            "overall_pct": overall_val
        }
        save_config(self.cfg)

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

            # Automatically queue this title for background setting/genre classification
            if self.title_classifier:
                selected_title = self.dl_title_input.text().strip()
                if selected_title:
                    target_dir = self.lib_dir / selected_title
                    if target_dir.exists():
                        self.title_classifier.queue_title_analysis(target_dir, priority_first=True)
                else:
                    self.title_classifier.scan_unclassified_titles(self.lib_dir)
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

        # Preload Mode Settings (Endless Scroll)
        self.preload_mode_lbl = QLabel(self.t.get("preload_mode_lbl", "Режим підвантаження наступної глави:"))
        grid.addWidget(self.preload_mode_lbl, 1, 0)
        self.preload_mode_combo = QComboBox()
        self.preload_mode_combo.addItem(self.t.get("preload_adaptive", "Адаптивно"), "adaptive")
        self.preload_mode_combo.addItem(self.t.get("preload_manual", "Фіксований відсоток"), "manual")
        self.preload_mode_combo.addItem(self.t.get("preload_disabled", "Вимкнено"), "disabled")
        saved_pl = self.cfg.get("preload_mode", "adaptive")
        pl_idx = self.preload_mode_combo.findData(saved_pl)
        if pl_idx >= 0:
            self.preload_mode_combo.setCurrentIndex(pl_idx)
        apply_combo_style(self.preload_mode_combo)
        self.preload_mode_combo.currentIndexChanged.connect(self._on_preload_mode_changed)
        grid.addWidget(self.preload_mode_combo, 1, 1)

        # Manual Preload Threshold row
        self.preload_thresh_lbl = QLabel(self.t.get("preload_threshold_lbl", "Поріг підвантаження глави (%):"))
        grid.addWidget(self.preload_thresh_lbl, 2, 0)
        thresh_box = QHBoxLayout()
        thresh_box.setSpacing(8)
        self.preload_thresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.preload_thresh_slider.setRange(10, 95)
        saved_thresh = int(self.cfg.get("manual_preload_threshold", 75))
        self.preload_thresh_slider.setValue(saved_thresh)
        self.preload_thresh_val_lbl = QLabel(f"{saved_thresh}%")
        self.preload_thresh_val_lbl.setStyleSheet("font-weight: 700; color: #fbbf24; min-width: 45px;")
        self.preload_thresh_slider.valueChanged.connect(lambda v: self.preload_thresh_val_lbl.setText(f"{v}%"))
        thresh_box.addWidget(self.preload_thresh_slider, stretch=1)
        thresh_box.addWidget(self.preload_thresh_val_lbl)
        grid.addLayout(thresh_box, 2, 1)

        # Apply visual enabled/disabled styling immediately
        self._on_preload_mode_changed(0)

        # Progress Display in Library
        self.progress_display_lbl = QLabel(self.t.get("progress_display_lbl", "Відображення прогресу в бібліотеці:"))
        grid.addWidget(self.progress_display_lbl, 3, 0)
        self.progress_display_combo = QComboBox()
        self.progress_display_combo.addItem(self.t.get("progress_mode_chapter", "Відсоток поточної глави"), "chapter")
        self.progress_display_combo.addItem(self.t.get("progress_mode_overall", "Загальний відсоток від усього тайтлу"), "overall")
        saved_disp = self.cfg.get("progress_display_mode", "chapter")
        disp_idx = self.progress_display_combo.findData(saved_disp)
        if disp_idx >= 0:
            self.progress_display_combo.setCurrentIndex(disp_idx)
        apply_combo_style(self.progress_display_combo)
        grid.addWidget(self.progress_display_combo, 3, 1)

        self.settings_speed_lbl = QLabel(self.t["speed_lbl"])
        grid.addWidget(self.settings_speed_lbl, 4, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(30, 160)
        self.speed_slider.setValue(self.cfg.get("scroll_speed", 75))
        grid.addWidget(self.speed_slider, 4, 1)

        self.settings_lib_lbl = QLabel(self.t["lib_lbl"])
        grid.addWidget(self.settings_lib_lbl, 5, 0)
        
        lib_box = QHBoxLayout()
        lib_box.setSpacing(8)
        self.lib_inp = QLineEdit(str(self.lib_dir))
        self.lib_inp.setReadOnly(False)
        self.lib_inp.setPlaceholderText("Введіть або вставте шлях до папки бібліотеки (наприклад: D:\\my_manga)...")
        self.lib_inp.setStyleSheet("background: #1e2030; color: #f1f5f9; border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; padding: 8px 12px; font-size: 13px;")
        self.lib_inp.editingFinished.connect(self._on_lib_inp_editing_finished)
        lib_box.addWidget(self.lib_inp, stretch=1)
        self.lib_browse_btn = QPushButton(f"📁 {self.t.get('browse_btn', 'Огляд...')}")
        self.lib_browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.lib_browse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #F3F4F6;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.16);
                border-color: #F59E0B;
                color: #FFFFFF;
            }
        """)
        self.lib_browse_btn.clicked.connect(self._browse_library_folder)
        lib_box.addWidget(self.lib_browse_btn)
        grid.addLayout(lib_box, 5, 1)

        # Sounds & Foley Folder row
        self.settings_sounds_lbl = QLabel(self.t.get("sounds_lbl", "Папка аудіо та фолей (звуків):"))
        grid.addWidget(self.settings_sounds_lbl, 6, 0)

        sounds_box = QHBoxLayout()
        sounds_box.setSpacing(8)
        self.sounds_inp = QLineEdit(str(self.sounds_dir))
        self.sounds_inp.setReadOnly(False)
        self.sounds_inp.setPlaceholderText("Введіть або вставте шлях до папки звуків (наприклад: D:\\my_sounds)...")
        self.sounds_inp.setStyleSheet("background: #1e2030; color: #f1f5f9; border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; padding: 8px 12px; font-size: 13px;")
        self.sounds_inp.editingFinished.connect(self._on_sounds_inp_editing_finished)
        sounds_box.addWidget(self.sounds_inp, stretch=1)
        self.sounds_browse_btn = QPushButton(f"📁 {self.t.get('browse_btn', 'Огляд...')}")
        self.sounds_browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.sounds_browse_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #F3F4F6;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.16);
                border-color: #A78BFA;
                color: #FFFFFF;
            }
        """)
        self.sounds_browse_btn.clicked.connect(self._browse_sounds_folder)
        sounds_box.addWidget(self.sounds_browse_btn)
        grid.addLayout(sounds_box, 6, 1)

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

        # Card 3: Background Music & Ambient Atmosphere (Beta)
        music_card = QFrame()
        music_card.setProperty("class", "cardPane")
        mc_layout = QVBoxLayout(music_card)
        mc_layout.setContentsMargins(24, 24, 24, 24)
        mc_layout.setSpacing(14)

        self.music_title = QLabel(self.t.get("music_card_title", "🎵 Фонова музика та атмосфера (Бета 🛠️🚧)"))
        self.music_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #a78bfa;")
        mc_layout.addWidget(self.music_title)

        self.music_sub = QLabel(self.t.get("music_card_sub", "Атмосферний звуковий ембієнт для повного занурення в манхву та новели:"))
        self.music_sub.setStyleSheet("font-size: 13px; color: #9ca3af;")
        mc_layout.addWidget(self.music_sub)

        mc_grid = QGridLayout()
        mc_grid.setSpacing(14)

        # Toggle 1: Background ambient during reading
        self.music_enable_toggle = NeoToggle(
            self.t.get("music_enable_lbl", "Увімкнути фоновий ембієнт при читанні:"),
            "",
            checked=self.cfg.get("music_enabled", False),
            parent=self
        )
        self.music_enable_toggle.toggled.connect(self._on_music_enabled_toggled)
        mc_grid.addWidget(self.music_enable_toggle, 0, 0, 1, 2)

        # Toggle 2: App Lobby & Background Audio Toggle (Preparatory toggle)
        self.music_app_enable_toggle = NeoToggle(
            self.t.get("music_app_enable_lbl", "Увімкнути звуки інтерфейсу:"),
            "",
            checked=self.cfg.get("music_app_enabled", False),
            parent=self
        )
        self.music_app_enable_toggle.toggled.connect(self._on_music_app_enabled_toggled)
        mc_grid.addWidget(self.music_app_enable_toggle, 1, 0, 1, 2)

        self.music_preset_lbl = QLabel(self.t.get("music_preset_lbl", "Режим відтворення / Фоновий трек:"))
        mc_grid.addWidget(self.music_preset_lbl, 2, 0, Qt.AlignmentFlag.AlignTop)

        # Collapsible Tree Picker for Auto + Packs / my_sounds / meme
        self.music_preset_picker = CollapsibleMusicPresetPicker(self)
        self._populate_music_presets()
        self.music_preset_picker.preset_selected.connect(self._on_music_preset_selected)
        mc_grid.addWidget(self.music_preset_picker, 2, 1)

        self.music_vol_lbl = QLabel(self.t.get("music_vol_lbl", "Гучність звуку:"))
        mc_grid.addWidget(self.music_vol_lbl, 3, 0)
        self.music_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.music_vol_slider.setRange(0, 100)
        self.music_vol_slider.setValue(self.cfg.get("music_volume", 40))
        self.music_vol_slider.setStyleSheet("""
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
            QSlider::handle:horizontal:hover {
                background: #fcd34d;
                border-color: #fef08a;
            }
        """)
        self.music_vol_slider.valueChanged.connect(self._on_music_volume_value_changed)
        mc_grid.addWidget(self.music_vol_slider, 3, 1)

        # Row 4: Gemini API Key Input
        self.gemini_key_lbl = QLabel(self.t.get("gemini_key_lbl", "Ключ Google Gemini API:"))
        mc_grid.addWidget(self.gemini_key_lbl, 4, 0)

        key_box = QHBoxLayout()
        key_box.setSpacing(8)
        self.gemini_key_inp = QLineEdit(self.cfg.get("gemini_api_key", ""))
        self.gemini_key_inp.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_inp.setPlaceholderText(self.t.get("gemini_key_ph", "Введіть Gemini API Key..."))
        self.gemini_key_inp.setStyleSheet("background: #1e2030; color: #f1f5f9; border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 6px 12px; font-size: 13px;")
        self.gemini_key_inp.textChanged.connect(lambda: self._update_gemini_status_display())

        # Toggle visibility
        self.gemini_toggle_vis_btn = QPushButton("👁")
        self.gemini_toggle_vis_btn.setFixedSize(36, 32)
        self.gemini_toggle_vis_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.gemini_toggle_vis_btn.setToolTip(self.t.get("show_key_tip", "Показати / приховати ключ"))
        self.gemini_toggle_vis_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.16);
                border-color: #F59E0B;
            }
        """)
        self.gemini_toggle_vis_btn.clicked.connect(self._toggle_gemini_key_visibility)

        # Clear key button
        self.gemini_clear_btn = QPushButton("✕")
        self.gemini_clear_btn.setFixedSize(36, 32)
        self.gemini_clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.gemini_clear_btn.setToolTip(self.t.get("clear_key_tip", "Очистити / видалити ключ"))
        self.gemini_clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 8px;
                color: #f87171;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(239, 68, 68, 0.25);
                border-color: #ef4444;
            }
        """)
        self.gemini_clear_btn.clicked.connect(self._on_gemini_key_cleared)

        key_box.addWidget(self.gemini_key_inp, stretch=1)
        key_box.addWidget(self.gemini_toggle_vis_btn)
        key_box.addWidget(self.gemini_clear_btn)
        mc_grid.addLayout(key_box, 4, 1)

        # Row 5: Status Indicator & Instant Save Button
        status_box = QHBoxLayout()
        self.gemini_status_lbl = QLabel("")
        self._update_gemini_status_display()
        status_box.addWidget(self.gemini_status_lbl, 1)

        self.music_save_btn = QPushButton("💾 Зберегти налаштування звуку")
        self.music_save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.music_save_btn.setStyleSheet("""
            QPushButton {
                background: #0d9488;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: #14b8a6;
            }
        """)
        self.music_save_btn.clicked.connect(self.save_settings)
        status_box.addWidget(self.music_save_btn)
        mc_grid.addLayout(status_box, 5, 0, 1, 2)
        mc_layout.addLayout(mc_grid)

        self.music_notice_lbl = QLabel(self.t.get("music_beta_notice", "Звуковий рушій бере аудіо з папки sounds/ (поруч із library/). Підтримуються як окремі файли, так і підпапки (наприклад sounds/ambient/forest/)."))
        self.music_notice_lbl.setStyleSheet("font-size: 12px; color: #cbd5e1; background-color: rgba(167, 139, 250, 0.12); border: 1px dashed rgba(167, 139, 250, 0.4); border-radius: 8px; padding: 10px;")
        self.music_notice_lbl.setWordWrap(True)
        mc_layout.addWidget(self.music_notice_lbl)

        layout.addWidget(music_card)
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

    def _browse_library_folder(self):
        try:
            start_dir = str(self.lib_dir.resolve()) if self.lib_dir.exists() else ""
            caption = self.t.get("select_lib_folder", "Виберіть папку бібліотеки")
            folder = QFileDialog.getExistingDirectory(
                self,
                caption,
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog
            )
            if folder:
                p = Path(folder).resolve()
                self.lib_inp.setText(str(p))
                self.lib_dir = p
                self.cfg["library_path"] = str(p)
                save_config(self.cfg)
                if hasattr(self, "refresh_catalog"):
                    self.refresh_catalog()
        except Exception as e:
            logger.error(f"Error picking directory: {e}")

    def _on_lib_inp_editing_finished(self):
        txt = self.lib_inp.text().strip()
        if txt:
            try:
                p = Path(txt).resolve()
                if p != self.lib_dir:
                    p.mkdir(parents=True, exist_ok=True)
                    self.lib_dir = p
                    self.cfg["library_path"] = str(p)
                    save_config(self.cfg)
                    if hasattr(self, "refresh_catalog"):
                        self.refresh_catalog()
            except Exception as e:
                logger.error(f"Error updating library path from text: {e}")

    def _browse_sounds_folder(self):
        try:
            start_dir = str(self.sounds_dir.resolve()) if self.sounds_dir.exists() else ""
            caption = self.t.get("select_sounds_folder", "Виберіть папку для аудіо та звукових паків")
            folder = QFileDialog.getExistingDirectory(
                self,
                caption,
                start_dir,
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog
            )
            if folder:
                p = Path(folder).resolve()
                self.sounds_inp.setText(str(p))
                self._apply_new_sounds_dir(p)
        except Exception as e:
            logger.error(f"Error picking sounds directory: {e}")

    def _on_sounds_inp_editing_finished(self):
        txt = self.sounds_inp.text().strip()
        if txt:
            try:
                p = Path(txt).resolve()
                if p != self.sounds_dir:
                    self._apply_new_sounds_dir(p)
            except Exception as e:
                logger.error(f"Error updating sounds path from text: {e}")

    def _apply_new_sounds_dir(self, p: Path):
        p.mkdir(parents=True, exist_ok=True)
        default_sounds = (BASE_DIR / "sounds").resolve()
        if p == default_sounds:
            self.cfg["sounds_path"] = "sounds"
        else:
            self.cfg["sounds_path"] = str(p)
        self.sounds_dir = p
        if hasattr(self, "sound_engine") and self.sound_engine:
            self.sound_engine.set_sounds_dir(p)
        if hasattr(self, "ai_analyzer") and self.ai_analyzer:
            self.ai_analyzer.set_sounds_dir(p)
        if hasattr(self, "_populate_music_presets"):
            self._populate_music_presets()
        save_config(self.cfg)

    def _toggle_gemini_key_visibility(self):
        if not hasattr(self, "gemini_key_inp"):
            return
        if self.gemini_key_inp.echoMode() == QLineEdit.EchoMode.Password:
            self.gemini_key_inp.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.gemini_key_inp.setEchoMode(QLineEdit.EchoMode.Password)

    def _update_gemini_status_display(self):
        if not hasattr(self, "gemini_status_lbl") or not hasattr(self, "gemini_key_inp"):
            return
        val = self.gemini_key_inp.text().strip()
        if val:
            self.gemini_status_lbl.setText(self.t.get("gemini_status_configured", "🟢 Gemini API Key налаштовано"))
            self.gemini_status_lbl.setStyleSheet("font-size: 12px; color: #34d399; font-weight: 700;")
        else:
            self.gemini_status_lbl.setText(self.t.get("gemini_status_none", "⚪ Ключ не вказано (буде використано базові звуки)"))
            self.gemini_status_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 600;")

        # Auto-persist key immediately
        if self.cfg.get("gemini_api_key") != val:
            self.cfg["gemini_api_key"] = val
            save_config(self.cfg)
            if hasattr(self, "ai_analyzer") and self.ai_analyzer:
                self.ai_analyzer.set_api_key(val)

    def _on_gemini_key_cleared(self):
        if hasattr(self, "gemini_key_inp"):
            self.gemini_key_inp.clear()
            self.cfg["gemini_api_key"] = ""
            save_config(self.cfg)
            if hasattr(self, "ai_analyzer") and self.ai_analyzer:
                self.ai_analyzer.set_api_key("")
            self._update_gemini_status_display()

    def _open_sound_studio(self):
        try:
            if SoundStudioWindow is None:
                return
            sounds_dir = getattr(self, "sounds_dir", BASE_DIR / "sounds")
            dlg = SoundStudioWindow(sounds_dir, self)
            dlg.exec()
            if hasattr(self, "sound_engine") and self.sound_engine:
                self.sound_engine.reload_recipes()
        except Exception as e:
            logger.error(f"Failed to open SoundStudio: {e}")

    def _on_preload_mode_changed(self, idx: int):
        mode = self.preload_mode_combo.currentData() if hasattr(self, "preload_mode_combo") else "adaptive"
        is_manual = (mode == "manual")
        if hasattr(self, "preload_thresh_slider"):
            self.preload_thresh_slider.setEnabled(is_manual)
            if is_manual:
                self.preload_thresh_slider.setStyleSheet("""
                    QSlider::groove:horizontal {
                        height: 6px;
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #3b82f6);
                        border-radius: 3px;
                    }
                    QSlider::handle:horizontal {
                        background: #fbbf24;
                        width: 14px;
                        margin: -4px 0;
                        border-radius: 7px;
                    }
                """)
            else:
                self.preload_thresh_slider.setStyleSheet("""
                    QSlider::groove:horizontal {
                        height: 6px;
                        background: rgba(255, 255, 255, 0.08);
                        border-radius: 3px;
                    }
                    QSlider::handle:horizontal {
                        background: #4b5563;
                        width: 14px;
                        margin: -4px 0;
                        border-radius: 7px;
                    }
                """)
        if hasattr(self, "preload_thresh_lbl"):
            self.preload_thresh_lbl.setEnabled(is_manual)
            if is_manual:
                self.preload_thresh_lbl.setStyleSheet("color: #d1d5db;")
            else:
                self.preload_thresh_lbl.setStyleSheet("color: #6b7280;")
        if hasattr(self, "preload_thresh_val_lbl"):
            self.preload_thresh_val_lbl.setEnabled(is_manual)
            if is_manual:
                self.preload_thresh_val_lbl.setStyleSheet("font-weight: 700; color: #fbbf24; min-width: 45px;")
            else:
                self.preload_thresh_val_lbl.setStyleSheet("font-weight: 700; color: #6b7280; min-width: 45px;")

    def _populate_music_presets(self):
        """Fills collapsible tree picker with Auto and all pack / my_sounds / meme folders."""
        curr_preset = self.cfg.get("music_preset", "ai_adaptive")
        sounds_root = getattr(self, "sounds_dir", BASE_DIR / "sounds")
        auto_title = self.t.get("music_preset_ai_adaptive", "Авто")

        if hasattr(self, "music_preset_picker"):
            self.music_preset_picker.populate(sounds_root, auto_title=auto_title)
            self.music_preset_picker.setCurrentData(curr_preset)

    def _on_music_volume_value_changed(self, val: int):
        """Volume adjustment with instant test_sound preview for precise volume feedback."""
        try:
            self.cfg["music_volume"] = int(val)
            if hasattr(self, "sound_engine") and self.sound_engine:
                self.sound_engine.set_volume(val)

            # Preview test_sound so user immediately hears actual volume calibration
            curr_preset = self.cfg.get("music_preset", "ai_adaptive")
            if curr_preset == "ai_adaptive":
                if hasattr(self, "_test_audio_player") and hasattr(self, "_test_audio_out"):
                    self._test_audio_out.setVolume(max(0.0, min(1.0, float(val) / 100.0)))
                    # Find test_sound file (core/bg/test_sound.wav or test_sound.mp3)
                    if self._test_audio_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                        test_file = None
                        if hasattr(self, "sounds_dir"):
                            for cand in [
                                self.sounds_dir / "core" / "bg" / "test_sound.wav",
                                self.sounds_dir / "core" / "bg" / "test_sound.mp3",
                                self.sounds_dir / "core" / "bg" / "test_sound.mp3.bak"
                            ]:
                                if cand.exists():
                                    test_file = cand
                                    break
                        if test_file:
                            self._test_audio_player.setSource(QUrl.fromLocalFile(str(test_file)))
                            self._test_audio_player.play()
        except Exception as e:
            logger.debug(f"Volume change error: {e}")

    def _on_music_preset_selected(self, data: str):
        """Switch audio preset or AI mode cleanly when user selects item in collapsible tree."""
        try:
            if not data or not hasattr(self, "sound_engine") or not self.sound_engine:
                return

            self.cfg["music_preset"] = data
            save_config(self.cfg)

            # Prevent competing audio layers: stop all previous audio before switching!
            self.sound_engine.stop_all(fade=False)

            if data == "ai_adaptive":
                # AI mode active: reader canvas will feed cues dynamically on scroll
                pass
            else:
                self.sound_engine.set_enabled(True)
                if hasattr(self, "music_enable_toggle"):
                    self.music_enable_toggle.setChecked(True)
                vol = self.music_vol_slider.value() if hasattr(self, "music_vol_slider") else 50
                self.sound_engine.set_volume(vol)
                track_name = data.split(":")[-1]
                self.sound_engine.play_ambient(track_name, fade_ms=300)
        except Exception as e:
            logger.debug(f"Preset selection error: {e}")

    def _on_music_enabled_toggled(self, checked: bool):
        """Immediately syncs sound engine enabled state for reading ambient."""
        try:
            self.cfg["music_enabled"] = checked
            save_config(self.cfg)
            if hasattr(self, "sound_engine") and self.sound_engine:
                self.sound_engine.set_enabled(checked)
                if not checked:
                    self.sound_engine.stop_all(fade=True)
                    if hasattr(self, "_test_audio_player") and self._test_audio_player:
                        self._test_audio_player.stop()
        except Exception as e:
            logger.debug(f"Reading music toggle error: {e}")

    def _on_music_app_enabled_toggled(self, checked: bool):
        """Toggle for App Lobby / Interface Ambient Sound (Preparatory toggle)."""
        try:
            self.cfg["music_app_enabled"] = checked
            save_config(self.cfg)
            logger.info(f"App lobby audio toggle set to: {checked}")
        except Exception as e:
            logger.debug(f"App music toggle error: {e}")

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
        if hasattr(self, "preload_mode_combo"):
            self.cfg["preload_mode"] = self.preload_mode_combo.currentData() or "adaptive"
        if hasattr(self, "preload_thresh_slider"):
            self.cfg["manual_preload_threshold"] = self.preload_thresh_slider.value()
        if hasattr(self, "progress_display_combo"):
            self.cfg["progress_display_mode"] = self.progress_display_combo.currentData() or "chapter"
        if hasattr(self, "music_enable_toggle"):
            self.cfg["music_enabled"] = self.music_enable_toggle.isChecked()
        if hasattr(self, "music_app_enable_toggle"):
            self.cfg["music_app_enabled"] = self.music_app_enable_toggle.isChecked()
        if hasattr(self, "music_preset_picker"):
            self.cfg["music_preset"] = self.music_preset_picker.currentData() or "ai_adaptive"
        if hasattr(self, "music_vol_slider"):
            self.cfg["music_volume"] = self.music_vol_slider.value()

        # Update Gemini API Key
        if hasattr(self, "gemini_key_inp"):
            new_key = self.gemini_key_inp.text().strip()
            self.cfg["gemini_api_key"] = new_key
            if hasattr(self, "ai_analyzer") and self.ai_analyzer:
                self.ai_analyzer.set_api_key(new_key)
            self._update_gemini_status_display()

        # Update Sound Engine state
        if hasattr(self, "sound_engine") and self.sound_engine:
            self.sound_engine.set_enabled(self.cfg.get("music_enabled", False))
            self.sound_engine.set_volume(self.cfg.get("music_volume", 40))

        # Update library path if changed
        if hasattr(self, "lib_inp") and self.lib_inp.text().strip():
            new_p = Path(self.lib_inp.text().strip()).resolve()
            if new_p != self.lib_dir:
                try:
                    default_lib = (BASE_DIR / "library").resolve()
                    if new_p == default_lib:
                        self.cfg["library_path"] = "library"
                    else:
                        self.cfg["library_path"] = str(new_p)
                    new_p.mkdir(parents=True, exist_ok=True)
                    self.lib_dir = new_p
                    if hasattr(self, "refresh_catalog"):
                        self.refresh_catalog()
                    if hasattr(self, "populate_unpack_manhwas"):
                        self.populate_unpack_manhwas()
                except Exception as e:
                    logger.error(f"Failed to update library folder: {e}")

        # Update sounds path if changed
        if hasattr(self, "sounds_inp") and self.sounds_inp.text().strip():
            new_sp = Path(self.sounds_inp.text().strip()).resolve()
            if new_sp != self.sounds_dir:
                try:
                    self._apply_new_sounds_dir(new_sp)
                except Exception as e:
                    logger.error(f"Failed to update sounds folder: {e}")

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

        # Retranslate preload controls
        if hasattr(self, "preload_mode_lbl"):
            self.preload_mode_lbl.setText(self.t.get("preload_mode_lbl", "Режим підвантаження наступної глави:"))
        if hasattr(self, "preload_mode_combo"):
            curr_pl = self.preload_mode_combo.currentData()
            self.preload_mode_combo.blockSignals(True)
            self.preload_mode_combo.clear()
            self.preload_mode_combo.addItem(self.t.get("preload_adaptive", "Адаптивно"), "adaptive")
            self.preload_mode_combo.addItem(self.t.get("preload_manual", "Фіксований відсоток"), "manual")
            self.preload_mode_combo.addItem(self.t.get("preload_disabled", "Вимкнено"), "disabled")
            p_idx = self.preload_mode_combo.findData(curr_pl)
            if p_idx >= 0:
                self.preload_mode_combo.setCurrentIndex(p_idx)
            self.preload_mode_combo.blockSignals(False)

        if hasattr(self, "preload_thresh_lbl"):
            self.preload_thresh_lbl.setText(self.t.get("preload_threshold_lbl", "Поріг підвантаження глави (%):"))

        # Retranslate progress display in library
        if hasattr(self, "progress_display_lbl"):
            self.progress_display_lbl.setText(self.t.get("progress_display_lbl", "Відображення прогресу в бібліотеці:"))
        if hasattr(self, "progress_display_combo"):
            curr_dp = self.progress_display_combo.currentData()
            self.progress_display_combo.blockSignals(True)
            self.progress_display_combo.clear()
            self.progress_display_combo.addItem(self.t.get("progress_mode_chapter", "Відсоток поточної глави"), "chapter")
            self.progress_display_combo.addItem(self.t.get("progress_mode_overall", "Загальний відсоток від усього тайтлу"), "overall")
            dp_idx = self.progress_display_combo.findData(curr_dp)
            if dp_idx >= 0:
                self.progress_display_combo.setCurrentIndex(dp_idx)
            self.progress_display_combo.blockSignals(False)

        if hasattr(self, "settings_speed_lbl"):
            self.settings_speed_lbl.setText(self.t["speed_lbl"])
        if hasattr(self, "settings_lib_lbl"):
            self.settings_lib_lbl.setText(self.t["lib_lbl"])
        if hasattr(self, "lib_browse_btn"):
            self.lib_browse_btn.setText(f"📁 {self.t.get('browse_btn', 'Огляд...')}")
        if hasattr(self, "settings_sounds_lbl"):
            self.settings_sounds_lbl.setText(self.t.get("sounds_lbl", "Папка аудіо та фолей (звуків):"))
        if hasattr(self, "sounds_browse_btn"):
            self.sounds_browse_btn.setText(f"📁 {self.t.get('browse_btn', 'Огляд...')}")
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

        # Music settings Card
        if hasattr(self, "music_title"):
            self.music_title.setText(self.t.get("music_card_title", "🎵 Фонова музика та атмосфера (Бета 🛠️🚧)"))
        if hasattr(self, "music_sub"):
            self.music_sub.setText(self.t.get("music_card_sub", "Атмосферний звуковий ембієнт для повного занурення в манхву та новели:"))
        if hasattr(self, "music_enable_toggle"):
            self.music_enable_toggle.set_texts(self.t.get("music_enable_lbl", "Увімкнути фоновий ембієнт при читанні:"), "")
        if hasattr(self, "music_app_enable_toggle"):
            self.music_app_enable_toggle.set_texts(self.t.get("music_app_enable_lbl", "Увімкнути фонові звуки програми (Лоббі):"), "")
        if hasattr(self, "music_preset_lbl"):
            self.music_preset_lbl.setText(self.t.get("music_preset_lbl", "Режим відтворення / Фоновий трек:"))
        if hasattr(self, "music_vol_lbl"):
            self.music_vol_lbl.setText(self.t.get("music_vol_lbl", "Гучність звуку:"))
        if hasattr(self, "music_preset_picker"):
            self._populate_music_presets()
        if hasattr(self, "music_notice_lbl"):
            self.music_notice_lbl.setText(self.t.get("music_beta_notice", "🛠️ Звуковий рушій наразі у режимі бета-тестування. Пресети та ШІ-адаптивний саундтрек проходять калібрування."))
        if hasattr(self, "gemini_key_lbl"):
            self.gemini_key_lbl.setText(self.t.get("gemini_key_lbl", "Ключ Google Gemini API:"))
        if hasattr(self, "gemini_key_inp"):
            self.gemini_key_inp.setPlaceholderText(self.t.get("gemini_key_ph", "Введіть Gemini API Key..."))
        if hasattr(self, "gemini_toggle_vis_btn"):
            self.gemini_toggle_vis_btn.setToolTip(self.t.get("show_key_tip", "Показати / приховати ключ"))
        if hasattr(self, "gemini_clear_btn"):
            self.gemini_clear_btn.setToolTip(self.t.get("clear_key_tip", "Очистити / видалити ключ"))
        self._update_gemini_status_display()

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

        # Stop preview test sound immediately whenever leaving settings tab (index 3)
        if prev_idx == 3 and index != 3:
            if hasattr(self, "sound_engine") and self.sound_engine:
                if self.sound_engine.current_bg == "test_sound":
                    self.sound_engine.stop_all(fade=True)
                    # If user chose a custom preset track, restore it
                    curr_preset = self.cfg.get("music_preset", "ai_adaptive")
                    if curr_preset != "ai_adaptive" and self.cfg.get("music_enabled", False):
                        track_name = curr_preset.split(":")[-1]
                        self.sound_engine.play_ambient(track_name, fade_ms=300)

        # UI Sound feedback and smooth ambient fade when navigating
        if hasattr(self, "_test_audio_player") and self._test_audio_player:
            self._test_audio_player.stop()

        if hasattr(self, "sound_engine") and self.sound_engine:
            self.sound_engine.play_ui_sound("click")
            # If leaving the reader tab (index 1), smoothly fade out and stop all playing audio layers
            if prev_idx == 1 and index != 1:
                self.sound_engine.stop_all(fade=True)

        # We do NOT clear canvas on tab switch so that returning to reader tab preserves the chapter and scroll!

        if index == 0:
            self.refresh_catalog()
        elif index == 1:
            # If returning to reader tab, restore audio on the active scroll position
            if hasattr(self, "sound_engine") and self.sound_engine and self.sound_engine.is_enabled:
                if hasattr(self, "canvas") and self.canvas.page_labels:
                    # Trigger scroll position evaluation to resume bg & amb layers smoothly
                    val = self.canvas.verticalScrollBar().value()
                    self.canvas.on_scroll(val)

            # If returning to reader tab but canvas was somehow empty and manhwa was selected, reload it
            if self.current_reading_manhwa and hasattr(self, "canvas") and not self.canvas.page_labels:
                ch_num = self.chapter_combo.currentData() or 1
                if self.is_cloud_reading:
                    self.load_cloud_chapter(self.current_reading_manhwa, ch_num)
                else:
                    m_path = self.lib_dir / self.current_reading_manhwa
                    if m_path.exists():
                        self.canvas.load_manhwa_chapter(m_path, ch_num, 0)
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
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            try:
                self.worker.terminate()
                self.worker.wait(200)
            except Exception:
                pass
        if hasattr(self, "cloud_dl_worker") and self.cloud_dl_worker and self.cloud_dl_worker.isRunning():
            try:
                self.cloud_dl_worker.cancel()
                self.cloud_dl_worker.terminate()
                self.cloud_dl_worker.wait(200)
            except Exception:
                pass
        if hasattr(self, "canvas"):
            self.canvas.clear_canvas()
        if hasattr(self, "stream_client"):
            try:
                self.stream_client.disconnect()
            except Exception:
                pass
        if hasattr(self, "sound_engine") and self.sound_engine:
            try:
                self.sound_engine.stop_ambient()
                self.sound_engine.stop_sfx()
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
