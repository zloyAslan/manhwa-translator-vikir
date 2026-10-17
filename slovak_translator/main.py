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

import ctypes
from ctypes import wintypes
import threading

def copy_selected_text(restore_clipboard: bool = False) -> str:
    """
    Копіює виділений у системі текст через емуляцію Ctrl+C.
    Якщо restore_clipboard=True, після прочитання повертає в буфер обміну попередній вміст!
    """
    old_clip = ""
    try:
        old_clip = pyperclip.paste()
    except Exception:
        pass
    
    # Емуляція Ctrl+C через win32api keybd_event
    try:
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(ord('C'), 0, 0, 0)
        time.sleep(0.02)
        win32api.keybd_event(ord('C'), 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.04)

        new_clip = pyperclip.paste()
        captured = new_clip.strip() if new_clip else ""

        if restore_clipboard:
            try:
                pyperclip.copy(old_clip)
            except Exception:
                pass

        if captured and captured != old_clip:
            return captured
        return captured if captured else (old_clip.strip() if old_clip else "")
    except Exception:
        return ""


class SlovakMouseWatcher(QObject):
    """
    Відстежує подвійний клік мишкою або виділення тексту протягуванням (drag & drop selection),
    і автоматично надсилає виділене слово чи фразу в перекладач без необхідності натискати Ctrl+C!
    """
    text_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._hook = None
        self._thread = None
        self._down_pos = None
        self._last_up_time = 0.0
        self._last_up_pos = None

    def start(self):
        self._thread = threading.Thread(target=self._run_hook, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hook:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None

    def _run_hook(self):
        WH_MOUSE_LL = 14
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_ulong)
            ]

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def _hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                msg = wParam
                struct = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                x, y = struct.pt.x, struct.pt.y
                now = time.time()

                if msg == WM_LBUTTONDOWN:
                    self._down_pos = (x, y)
                elif msg == WM_LBUTTONUP:
                    should_check = False
                    if self._down_pos:
                        dx = abs(x - self._down_pos[0])
                        dy = abs(y - self._down_pos[1])
                        # Протягування мишкою (виділення речення або слова)
                        if dx > 15 or dy > 8:
                            should_check = True

                    # Подвійний клік (виділення слова)
                    if not should_check and self._last_up_pos:
                        dist = abs(x - self._last_up_pos[0]) + abs(y - self._last_up_pos[1])
                        if dist < 8 and (now - self._last_up_time) < 0.4:
                            should_check = True

                    self._last_up_time = now
                    self._last_up_pos = (x, y)
                    self._down_pos = None

                    if should_check:
                        # Запускаємо зчитування виділеного тексту через 80мс, давши вікну оновити виділення
                        threading.Thread(target=self._capture_worker, daemon=True).start()

            return ctypes.windll.user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        proc = HOOKPROC(_hook_callback)
        self._hook = ctypes.windll.user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            proc,
            ctypes.windll.kernel32.GetModuleHandleW(None),
            0
        )

        msg = wintypes.MSG()
        while self._running:
            res = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if res <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def _capture_worker(self):
        time.sleep(0.08)
        # Копіюємо виділення і повертаємо попередній вміст буфера обміну, щоб буфер користувача не псувався!
        captured = copy_selected_text(restore_clipboard=True)
        if captured:
            words = captured.split()
            # Якщо це слово або коротка фраза (до 15 слів)
            if 0 < len(words) <= 15:
                self.text_selected.emit(captured)


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
        # Відстеження буфера обміну (миттєве підхоплення слів)
        self.last_auto_clip = ""
        self._ignore_clipboard = False
        self.clipboard = self.app.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

        self.setup_hotkeys()
        self.mascot.show()

        # Відстеження виділення тексту мишкою (подвійний клік або drag selection)
        self.mouse_watcher = SlovakMouseWatcher()
        self.mouse_watcher.text_selected.connect(self.on_mouse_text_selected)
        self.mouse_watcher.start()

    def on_mouse_text_selected(self, text: str):
        """Спрацьовує одразу, коли користувач виділив слово або речення мишкою без Ctrl+C."""
        text = text.strip()
        if not text:
            return

        # Не перебиваємо відкритий діалог Anki якщо користувач там редагує
        if self.anki_dialog.isVisible() and self.anki_dialog.isActiveWindow():
            return

        if self.bubble_window.isVisible():
            self.bubble_window.input_header.set_text(text)
            self.bubble_window.start_lookup(text)
            self.bubble_window.enforce_topmost()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(text)

    def on_clipboard_changed(self):
        """
        Коли користувач виділяє слово або копіює його,
        воно автоматично потрапляє в рядок перекладу.
        """
        if self._ignore_clipboard:
            return

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
        # Автоматично беремо виділений текст без затирання буфера
        clip_word = copy_selected_text(restore_clipboard=False)

        if self.bubble_window.isVisible() and not clip_word:
            self.bubble_window.hide_bubble()
        else:
            self.bubble_window.position_relative_to(self.mascot.geometry())
            self.bubble_window.show_and_focus(clip_word)

    def on_capture_sentence_hotkey(self):
        """
        Захоплює виділене в читалці/браузері речення натисканням Alt+W.
        Якщо вікно перекладача перекриває текст — ховаємо його на момент копіювання,
        потім відкриваємо картку Anki з вставленим реченням!
        """
        was_bubble_visible = self.bubble_window.isVisible()
        if was_bubble_visible:
            self.bubble_window.hide()

        # Тимчасово блокуємо автопереклад із буфера, щоб не спамити запитами
        self._ignore_clipboard = True
        try:
            captured_sentence = copy_selected_text(restore_clipboard=False)
        finally:
            self._ignore_clipboard = False

        # Відкриваємо діалог Anki з реченням
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

        try:
            if hasattr(self, "mouse_watcher") and self.mouse_watcher:
                self.mouse_watcher.stop()
        except Exception:
            pass

        # Припиняємо будь-які фонові потоки
        try:
            if hasattr(self.bubble_window, "active_lookup_thread") and self.bubble_window.active_lookup_thread:
                self.bubble_window.active_lookup_thread.terminate()
        except Exception:
            pass

        try:
            if hasattr(self.anki_dialog, "_save_worker") and self.anki_dialog._save_worker:
                self.anki_dialog._save_worker.terminate()
            if hasattr(self.anki_dialog, "_check_worker") and self.anki_dialog._check_worker:
                self.anki_dialog._check_worker.terminate()
        except Exception:
            pass

        try:
            self.bubble_window.close()
            self.anki_dialog.close()
            self.history_window.close()
            self.ai_window.close()
            self.mascot.close()
            self.tray.hide()
        except Exception:
            pass

        self.app.quit()
        # Повне завершення процесу, щоб ніякі приховані фонові потоки не залишались у системі
        import os
        os._exit(0)

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    app = SlovakTranslatorApp()
    sys.exit(app.run())
