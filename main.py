"""
Main Application Entry Point for M_Translate Manhwa Overlay Translator (Dark Fantasy Edition).
Coordinates:
- Floating M_Translate Vector Neon Mascot Badge
- Streamlined Comic Bubble Window
- Anki Card Creator Modal (AnkiConnect ports 8766/8765, deck 'англ манхва')
- RapidOCR Word Capture (Alt+E / F12)
- RapidOCR Sentence Capture for Anki (Alt+W)
- Panel Art Aspect-Preserving Cropper (Alt+D)
"""

import sys
import re
from pathlib import Path
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QGuiApplication, QFont
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu
)
import keyboard
import pyperclip

from config import config, Config
from dictionary_service import DictionaryService
from anki_service import AnkiService
from chibi_mascot import ChibiMascot
from bubble_window import BubbleWindow
from history_window import HistoryWindow
from ocr_snipper import SnippingOverlay
from anki_dialog import AnkiCardDialog
from panel_cropper import PanelCropper
from ai_chat_window import AIChatWindow
from localization import tr

ASSETS_DIR = Path(__file__).parent


class HotkeySignal(QObject):
    translate_triggered = pyqtSignal()
    word_ocr_triggered = pyqtSignal()
    sentence_ocr_triggered = pyqtSignal()
    panel_crop_triggered = pyqtSignal()
    ai_chat_triggered = pyqtSignal()
    blank_anki_triggered = pyqtSignal()


class ManhwaTranslatorApp:
    def __init__(self, show_mascot: bool = True, in_suite: bool = False):
        self.in_suite = in_suite
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        icon_path = ASSETS_DIR / "app_icon.ico"
        if icon_path.exists():
            self.app_icon = QIcon(str(icon_path))
            self.app.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()

        self.config = config
        self.dict_service = DictionaryService()
        self.anki_service = AnkiService()

        # Windows & Overlays
        self.mascot = ChibiMascot(self.config)
        self.bubble_window = BubbleWindow(self.dict_service, self.config)
        self.history_window = HistoryWindow(self.dict_service)
        self.anki_dialog = AnkiCardDialog(self.anki_service)
        self.ai_window = AIChatWindow()
        self.snipper = SnippingOverlay()
        self.cropper = PanelCropper()

        # Connect mascot signals
        self.mascot.clicked_signal.connect(self.toggle_bubble)
        self.mascot.open_history_signal.connect(self.open_history)
        self.mascot.ocr_word_signal.connect(lambda: self.start_ocr("word"))
        self.mascot.ocr_sentence_signal.connect(lambda: self.start_ocr("sentence"))

        # Connect bubble window signals
        self.bubble_window.quit_requested.connect(self.quit_app)
        self.bubble_window.ocr_word_requested.connect(lambda: self.start_ocr("word"))
        self.bubble_window.open_anki_dialog_signal.connect(self.open_anki_dialog)
        self.bubble_window.open_ai_chat_signal.connect(self.on_open_ai_chat)
        self.bubble_window.ui_language_changed.connect(self.on_ui_language_changed)
        self.history_window.word_selected.connect(self.translate_from_history)

        # Connect AI dialog signals
        self.ai_window.open_anki_dialog_signal.connect(self.open_anki_dialog)

        # Connect Anki dialog signals
        self.anki_dialog.request_sentence_ocr.connect(lambda: self.start_ocr("sentence"))
        self.anki_dialog.request_panel_crop.connect(self.start_panel_cropper)

        # Connect OCR & Cropper signals
        self.snipper.text_captured.connect(self.on_ocr_captured)
        self.cropper.image_captured.connect(self.on_panel_captured)

        # Setup system tray
        self.setup_tray()

        # Setup global hotkeys
        self.hotkey_emitter = HotkeySignal()
        self.hotkey_emitter.translate_triggered.connect(self.on_translate_hotkey)
        self.hotkey_emitter.word_ocr_triggered.connect(lambda: self.start_ocr("word"))
        self.hotkey_emitter.sentence_ocr_triggered.connect(lambda: self.start_ocr("sentence"))
        self.hotkey_emitter.panel_crop_triggered.connect(self.start_panel_cropper)
        self.hotkey_emitter.ai_chat_triggered.connect(self.on_ai_hotkey)
        self.hotkey_emitter.blank_anki_triggered.connect(self.on_open_blank_anki)
        self.setup_hotkeys()

        if show_mascot:
            self.mascot.show()

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.app_icon, self.app)
        self.setup_tray_menu()
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def setup_tray_menu(self):
        ul = self.config.get("ui_lang", "uk")
        self.tray.setToolTip(tr("tray_tooltip", ul))

        tray_menu = QMenu()
        tray_menu.setFont(QFont("Segoe UI", 9))
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #F3F4F6;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
            }
            QMenu::item:selected {
                background-color: #F59E0B;
                color: #000000;
                font-weight: bold;
            }
        """)

        act_word_ocr = tray_menu.addAction(tr("tray_word_ocr", ul))
        act_word_ocr.triggered.connect(lambda: self.start_ocr("word"))

        act_sent_ocr = tray_menu.addAction(tr("tray_sent_ocr", ul))
        act_sent_ocr.triggered.connect(lambda: self.start_ocr("sentence"))

        act_panel_crop = tray_menu.addAction(tr("tray_panel_crop", ul))
        act_panel_crop.triggered.connect(self.start_panel_cropper)

        act_blank_anki = tray_menu.addAction(tr("tray_blank_anki", ul))
        act_blank_anki.triggered.connect(self.on_open_blank_anki)

        act_ai = tray_menu.addAction(tr("tray_ai", ul))
        act_ai.triggered.connect(self.on_ai_hotkey)

        act_show = tray_menu.addAction(tr("tray_show", ul))
        act_show.triggered.connect(self.toggle_bubble)

        act_hist = tray_menu.addAction(tr("tray_dict", ul))
        act_hist.triggered.connect(self.open_history)

        act_reset = tray_menu.addAction(tr("tray_center", ul))
        act_reset.triggered.connect(self.center_mascot)

        tray_menu.addSeparator()

        act_exit = tray_menu.addAction(tr("tray_exit", ul))
        act_exit.triggered.connect(self.quit_app)

        self.tray.setContextMenu(tray_menu)

    def on_ui_language_changed(self, lang: str):
        self.setup_tray_menu()
        if hasattr(self, "bubble_window"):
            self.bubble_window.retranslate_ui()
        if hasattr(self, "ai_window"):
            self.ai_window.retranslate_ui()
        if hasattr(self, "anki_dialog"):
            self.anki_dialog.retranslate_ui()
        if hasattr(self, "history_window"):
            self.history_window.retranslate_ui()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_bubble()

    def center_mascot(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.mascot.width() // 2)
        cy = screen.center().y() - (self.mascot.height() // 2)
        self.mascot.move(cx, cy)
        self.config.set("pos_x", cx)
        self.config.set("pos_y", cy)
        self.mascot.enforce_topmost()

    def setup_hotkeys(self):
        # 1. Translate hotkey (Alt+Q)
        try:
            keyboard.add_hotkey("alt+q", lambda: self.hotkey_emitter.translate_triggered.emit())
        except Exception:
            pass

        # 2. Word OCR hotkey (Alt+E and F12)
        try:
            keyboard.add_hotkey("alt+e", lambda: self.hotkey_emitter.word_ocr_triggered.emit())
            keyboard.add_hotkey("f12", lambda: self.hotkey_emitter.word_ocr_triggered.emit())
        except Exception:
            pass

        # 3. Sentence OCR hotkey (Alt+W)
        try:
            keyboard.add_hotkey("alt+w", lambda: self.hotkey_emitter.sentence_ocr_triggered.emit())
        except Exception:
            pass

        # 4. Panel Art Cropper hotkey (Alt+D)
        try:
            keyboard.add_hotkey("alt+d", lambda: self.hotkey_emitter.panel_crop_triggered.emit())
        except Exception:
            pass

        # 5. AI Sentence Breakdown hotkey (Alt+A)
        try:
            keyboard.add_hotkey("alt+a", lambda: self.hotkey_emitter.ai_chat_triggered.emit())
        except Exception:
            pass

        # 6. Blank Anki Card Creator hotkey (Alt+S)
        try:
            keyboard.add_hotkey("alt+s", lambda: self.hotkey_emitter.blank_anki_triggered.emit())
        except Exception:
            pass

    def start_ocr(self, mode: str = "word"):
        self.bubble_window.hide_bubble()
        self.anki_dialog.hide()
        self.snipper.start_selection(mode=mode)

    def start_panel_cropper(self):
        self.bubble_window.hide_bubble()
        self.anki_dialog.hide()
        self.cropper.start_cropper()

    def on_ocr_captured(self, text: str, mode: str):
        clean_text = text.strip()
        if not clean_text:
            return

        if mode == "sentence":
            # Sentence mode: populate Anki dialog sentence field and show modal
            self.anki_dialog.set_sentence(clean_text)
        else:
            # Word mode: copy to clipboard, translate and display clouds
            pyperclip.copy(clean_text)
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(clean_text)

    def on_panel_captured(self, img_bytes: bytes):
        self.anki_dialog.set_image(img_bytes)

    def on_open_blank_anki(self):
        if not self.anki_dialog.isVisible():
            screen = QGuiApplication.primaryScreen().availableGeometry()
            cx = screen.center().x() - (self.anki_dialog.width() // 2)
            cy = screen.center().y() - (self.anki_dialog.height() // 2)
            self.anki_dialog.move(cx, cy)
        self.anki_dialog.open_empty()

    def open_anki_dialog(self, word: str = "", translation: str = "", sentence: str = ""):
        if not self.anki_dialog.isVisible():
            screen = QGuiApplication.primaryScreen().availableGeometry()
            cx = screen.center().x() - (self.anki_dialog.width() // 2)
            cy = screen.center().y() - (self.anki_dialog.height() // 2)
            self.anki_dialog.move(cx, cy)
        if word or translation or sentence:
            self.anki_dialog.open_for_word(word, translation, sentence)
        else:
            self.anki_dialog.open_empty()

    def on_translate_hotkey(self):
        auto_paste = self.config.get("auto_paste_clipboard", True)
        clip_word = ""

        if auto_paste:
            try:
                raw_clip = pyperclip.paste().strip()
                if raw_clip and len(raw_clip) < 80 and re.match(r"^[A-Za-z0-9\s\-\'\,\.\!\?]+$", raw_clip):
                    clip_word = raw_clip
            except Exception:
                pass

        if self.bubble_window.isVisible() and not clip_word:
            self.bubble_window.hide_bubble()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(clip_word)

    def toggle_bubble(self):
        if self.bubble_window.isVisible():
            self.bubble_window.hide_bubble()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus()

    def open_history(self):
        self.history_window.load_history()
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def translate_from_history(self, word: str):
        self.bubble_window.position_relative_to(self.mascot.geometry())
        self.bubble_window.show_and_focus(word)

    def on_open_ai_chat(self, text: str = ""):
        self.bubble_window.hide_bubble()
        # Position near screen center if not visible
        if not self.ai_window.isVisible():
            screen = QGuiApplication.primaryScreen().availableGeometry()
            cx = screen.center().x() - (self.ai_window.width() // 2)
            cy = screen.center().y() - (self.ai_window.height() // 2)
            self.ai_window.move(cx, cy)

        self.ai_window.show()
        self.ai_window.raise_()
        self.ai_window.activateWindow()

        self.ai_window.prepare_input(text)

    def on_ai_hotkey(self):
        text = ""
        # 1. Check if bubble window input has text
        if self.bubble_window.isVisible():
            text = self.bubble_window.input_header.line_edit.text().strip()

        # 2. If no text in bubble, check clipboard
        if not text:
            try:
                clip = pyperclip.paste().strip()
                if clip and len(clip.split()) > 3:
                    text = clip
            except Exception:
                pass

        if len(text.split()) > 3:
            self.on_open_ai_chat(text)
        else:
            self.on_open_ai_chat("")

    def quit_app(self):
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        if getattr(self, "in_suite", False):
            # If running inside suite, closing translator should NOT close the reader!
            self.mascot.hide()
            self.bubble_window.hide()
            self.history_window.hide()
            self.anki_dialog.hide()
            self.ai_window.hide()
            self.tray.hide()
        else:
            self.app.quit()

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    app = ManhwaTranslatorApp()
    sys.exit(app.run())
