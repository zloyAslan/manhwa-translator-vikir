"""
Головна точка входу для Перекладача Словацьких Новел (Slovak Novel Overlay Translator).
"""

import sys
import time
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QGuiApplication, QFont
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu
)
import keyboard
import pyperclip
import win32api
import win32con

def copy_selected_text() -> str:
    """Швидко копіює виділений у системі текст через емуляцію Ctrl+C без сторонніх бібліотек."""
    old_clip = ""
    try:
        old_clip = pyperclip.paste()
    except Exception:
        pass
    
    # Емуляція Ctrl+C через win32api keybd_event
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(ord('C'), 0, 0, 0)
    time.sleep(0.04)
    win32api.keybd_event(ord('C'), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.08)

    try:
        new_clip = pyperclip.paste()
        if new_clip and new_clip != old_clip:
            return new_clip.strip()
    except Exception:
        pass
    return old_clip.strip() if old_clip else ""

from config import config
from dictionary_service import SlovakDictionaryService
from anki_service import SlovakAnkiService
from mascot_badge import SlovakMascotBadge
from bubble_window import SlovakBubbleWindow
from history_window import SlovakHistoryWindow
from anki_dialog import SlovakAnkiDialog
from ai_chat_window import SlovakAIChatWindow

ROOT_DIR = Path(__file__).parent.parent
ICON_PATH = ROOT_DIR / "app_icon.ico"


class SlovakHotkeySignal(QObject):
    translate_triggered = pyqtSignal()
    sentence_capture_triggered = pyqtSignal()
    ai_chat_triggered = pyqtSignal()
    blank_anki_triggered = pyqtSignal()


class SlovakTranslatorApp:
    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        if ICON_PATH.exists():
            self.app_icon = QIcon(str(ICON_PATH))
            self.app.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()

        self.dict_service = SlovakDictionaryService()
        self.anki_service = SlovakAnkiService()

        # Вікна та віджети
        self.mascot = SlovakMascotBadge()
        self.bubble_window = SlovakBubbleWindow(self.dict_service)
        self.history_window = SlovakHistoryWindow(self.dict_service)
        self.anki_dialog = SlovakAnkiDialog(self.anki_service)
        self.ai_window = SlovakAIChatWindow()

        # Зв'язуємо сигнали якоря (маскота)
        self.mascot.clicked_signal.connect(self.toggle_bubble)
        self.mascot.open_history_signal.connect(self.open_history)

        # Зв'язуємо сигнали хмаринки
        self.bubble_window.open_anki_dialog_signal.connect(self.open_anki_dialog)
        self.bubble_window.open_ai_chat_signal.connect(self.open_ai_chat)
        self.history_window.word_selected.connect(self.translate_from_history)

        # Зв'язуємо сигнали ШІ
        self.ai_window.open_anki_dialog_signal.connect(self.open_anki_dialog)

        # Системний трей
        self.setup_tray()

        # Гарячі клавіші
        self.hotkey_emitter = SlovakHotkeySignal()
        self.hotkey_emitter.translate_triggered.connect(self.on_translate_hotkey)
        self.hotkey_emitter.sentence_capture_triggered.connect(self.on_capture_sentence_hotkey)
        self.hotkey_emitter.ai_chat_triggered.connect(self.on_ai_hotkey)
        self.hotkey_emitter.blank_anki_triggered.connect(self.open_blank_anki)
        # Відстеження буфера обміну (миттєве підхоплення слів при подвійному кліку / копіюванні)
        self.last_auto_clip = ""
        self.clipboard = self.app.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

        self.setup_hotkeys()
        self.mascot.show()

    def on_clipboard_changed(self):
        """
        Коли користувач виділяє слово подвійним кліком мишки або копіює його,
        воно автоматично потрапляє в рядок перекладу.
        """
        if not config.get("auto_paste_clipboard", True):
            return

        try:
            text = self.clipboard.text().strip()
        except Exception:
            return

        if not text or text == self.last_auto_clip:
            return

        # Ігноруємо занадто довгі уривки (більше 25 слів) або порожні рядки
        words = text.split()
        if len(words) > 25:
            return

        self.last_auto_clip = text

        # Якщо вікно перекладача відкрите або активне, миттєво оновлюємо рядок і перекладаємо
        if self.bubble_window.isVisible():
            self.bubble_window.input_header.set_text(text)
            self.bubble_window.start_lookup(text)
            self.bubble_window.enforce_topmost()
        else:
            # Якщо вікно згорнуто, розгортаємо біля маскота та перекладаємо
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(text)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.app_icon, self.app)
        self.tray.setToolTip("Slovak Novel Translator (SK ➔ UK)")

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

        act_show = tray_menu.addAction("📖 Показати перекладач (Alt+Q)")
        act_show.triggered.connect(self.toggle_bubble)

        act_sent = tray_menu.addAction("📝 Захопити виділене речення в Anki (Alt+W)")
        act_sent.triggered.connect(self.on_capture_sentence_hotkey)

        act_anki = tray_menu.addAction("⭐ Створити порожню картку Anki (Alt+S)")
        act_anki.triggered.connect(self.open_blank_anki)

        act_ai = tray_menu.addAction("🤖 ШІ-Консультант Gemini (Alt+A)")
        act_ai.triggered.connect(self.on_ai_hotkey)

        act_hist = tray_menu.addAction("📜 Історія перекладів")
        act_hist.triggered.connect(self.open_history)

        act_reset = tray_menu.addAction("🎯 Центрувати якор")
        act_reset.triggered.connect(self.mascot.center_on_screen)

        tray_menu.addSeparator()

        act_exit = tray_menu.addAction("⏻ Вийти")
        act_exit.triggered.connect(self.quit_app)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_bubble()

    def setup_hotkeys(self):
        # 1. Alt+Q - Переклад або показати/сховати
        try:
            keyboard.add_hotkey("alt+q", lambda: self.hotkey_emitter.translate_triggered.emit())
        except Exception:
            pass

        # 2. Alt+W - Захопити виділене речення мишкою без OCR
        try:
            keyboard.add_hotkey("alt+w", lambda: self.hotkey_emitter.sentence_capture_triggered.emit())
        except Exception:
            pass

        # 3. Alt+A - ШІ аналіз
        try:
            keyboard.add_hotkey("alt+a", lambda: self.hotkey_emitter.ai_chat_triggered.emit())
        except Exception:
            pass

        # 4. Alt+S - Порожня картка Anki
        try:
            keyboard.add_hotkey("alt+s", lambda: self.hotkey_emitter.blank_anki_triggered.emit())
        except Exception:
            pass

    def on_translate_hotkey(self):
        # Автоматично беремо виділений текст (імітуємо Ctrl+C якщо є виділення)
        clip_word = ""
        old_clip = ""
        try:
            old_clip = pyperclip.paste()
        except Exception:
            pass

        clip_word = copy_selected_text()
        if clip_word and len(clip_word.split()) > 10:
            # Якщо виділено ціле довге речення/абзац, не звужуємо до слова
            pass

        if self.bubble_window.isVisible() and not clip_word:
            self.bubble_window.hide_bubble()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(clip_word)

    def on_capture_sentence_hotkey(self):
        """
        Захоплює виділене в читалці/браузері речення натисканням Alt+W
        і автоматично вставляє його в поле Anki!
        """
        captured_sentence = copy_selected_text()

        # Відкриваємо вікно Anki
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.anki_dialog.width() // 2)
        cy = screen.center().y() - (self.anki_dialog.height() // 2)
        self.anki_dialog.move(cx, cy)
        self.anki_dialog.set_sentence(captured_sentence)

    def toggle_bubble(self):
        if self.bubble_window.isVisible():
            self.bubble_window.hide_bubble()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus()

    def open_history(self):
        self.history_window.load_history()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.history_window.width() // 2)
        cy = screen.center().y() - (self.history_window.height() // 2)
        self.history_window.move(cx, cy)
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    def translate_from_history(self, word: str):
        self.bubble_window.position_relative_to(self.mascot.geometry())
        self.bubble_window.show_and_focus(word)

    def open_anki_dialog(self, word: str = "", translation: str = "", sentence: str = ""):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.anki_dialog.width() // 2)
        cy = screen.center().y() - (self.anki_dialog.height() // 2)
        self.anki_dialog.move(cx, cy)
        self.anki_dialog.open_for_word(word, translation, sentence)

    def open_blank_anki(self):
        self.open_anki_dialog("", "", "")

    def open_ai_chat(self, text: str = ""):
        self.bubble_window.hide_bubble()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.ai_window.width() // 2)
        cy = screen.center().y() - (self.ai_window.height() // 2)
        self.ai_window.move(cx, cy)
        self.ai_window.show()
        self.ai_window.raise_()
        self.ai_window.activateWindow()
        self.ai_window.prepare_input(text)

    def on_ai_hotkey(self):
        # Якщо в полі хмаринки є текст
        text = ""
        if self.bubble_window.isVisible():
            text = self.bubble_window.input_header.line_edit.text().strip()

        if not text:
            clip = copy_selected_text()
            if clip and len(clip.split()) >= 2:
                text = clip

        self.open_ai_chat(text)

    def quit_app(self):
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self.app.quit()

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    app = SlovakTranslatorApp()
    sys.exit(app.run())
