from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QGraphicsDropShadowEffect, QApplication, QPushButton, QFrame,
    QSizeGrip
)
import win32con
import win32gui
from bubble_widgets import SlovakBubbleFrame, SlovakCloudCard, SlovakInputHeader
from dictionary_service import SlovakDictionaryService
from settings_dialog import SlovakSettingsDialog
from config import config

class SlovakLookupThread(QThread):
    result_ready = pyqtSignal(dict)

    def __init__(self, dict_service: SlovakDictionaryService, query: str):
        super().__init__()
        self.dict_service = dict_service
        self.query = query

    def run(self):
        result = self.dict_service.lookup(self.query)
        self.result_ready.emit(result)


class SlovakBubbleWindow(QWidget):
    closed_signal = pyqtSignal()
    open_anki_dialog_signal = pyqtSignal(str, str, str)
    open_ai_chat_signal = pyqtSignal(str)

    def __init__(self, dict_service: SlovakDictionaryService, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.current_result = None
        self.active_lookup_thread = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        saved_w = config.get("window_width", 480)
        saved_h = config.get("window_height", 560)
        self.setMinimumSize(420, 380)
        self.resize(max(440, saved_w), max(400, saved_h))

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Зовнішній комікс-фрейм з хвостиком
        self.bubble_frame = SlovakBubbleFrame(self, tail_position="left_mid")
        frame_layout = QVBoxLayout(self.bubble_frame)
        frame_layout.setContentsMargins(34, 14, 14, 14)
        frame_layout.setSpacing(8)

        # 1. Верхній бар
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.title_lbl = QLabel("🇸🇰 СЛОВАЦЬКИЙ ПЕРЕКЛАДАЧ")
        self.title_lbl.setFont(QFont("Segoe UI Black", 10))
        self.title_lbl.setStyleSheet("color: #F59E0B; letter-spacing: 0.5px; background: transparent;")
        top_bar.addWidget(self.title_lbl)

        # Напрямок перекладу (фіксований SK ➔ UK)
        lang_badge = QLabel("SK ➔ UK")
        lang_badge.setFont(QFont("Segoe UI Black", 8))
        lang_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(45, 212, 191, 0.15);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        top_bar.addWidget(lang_badge)

        top_bar.addStretch()

        # Кнопка ШІ 🤖
        self.ai_btn = QPushButton("🤖 ШІ")
        self.ai_btn.setFixedSize(48, 24)
        self.ai_btn.setFont(QFont("Segoe UI Black", 8))
        self.ai_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ai_btn.setToolTip("Відкрити консультацію ШІ Gemini для розбору речення")
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(139, 92, 246, 0.15);
                color: #A78BFA;
                border: 1px solid rgba(139, 92, 246, 0.4);
                border-radius: 6px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #7C3AED;
                color: #FFFFFF;
            }
        """)
        self.ai_btn.clicked.connect(self.on_ai_btn_clicked)
        top_bar.addWidget(self.ai_btn)

        # Кнопка Налаштування ⚙
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(26, 24)
        self.settings_btn.setFont(QFont("Segoe UI Emoji", 9))
        self.settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_btn.setToolTip("Налаштування")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #252F45;
                color: #F59E0B;
                border-color: #F59E0B;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        top_bar.addWidget(self.settings_btn)

        # Кнопка Повний вихід (⏻)
        self.exit_btn = QPushButton("⏻ Вийти")
        self.exit_btn.setFont(QFont("Segoe UI Black", 8))
        self.exit_btn.setFixedHeight(24)
        self.exit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.exit_btn.clicked.connect(QApplication.quit)
        top_bar.addWidget(self.exit_btn)

        # Кнопка Закрити (✕)
        self.close_btn = QLabel("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_btn.setFont(QFont("Segoe UI Black", 10))
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.setStyleSheet("""
            QLabel {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QLabel:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        self.close_btn.mousePressEvent = lambda e: self.hide_bubble()
        top_bar.addWidget(self.close_btn)

        frame_layout.addLayout(top_bar)

        # 2. Рядок пошуку / введення
        self.input_header = SlovakInputHeader()
        self.input_header.search_requested.connect(self.start_lookup)
        self.input_header.voice_requested.connect(self.pronounce_input)
        frame_layout.addWidget(self.input_header)

        # 3. Action Bar: Кнопка "⭐ В Anki" (як в оригінальному M_Translate)
        self.action_bar = QHBoxLayout()
        self.action_bar.setContentsMargins(2, 0, 2, 0)
        self.action_bar.setSpacing(10)

        self.anki_top_btn = QPushButton("⭐ В Anki")
        self.anki_top_btn.setFont(QFont("Segoe UI Black", 9))
        self.anki_top_btn.setFixedHeight(28)
        self.anki_top_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.anki_top_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        self.anki_top_btn.clicked.connect(self.on_open_anki_modal)
        self.anki_top_btn.hide()
        self.action_bar.addWidget(self.anki_top_btn)

        self.action_bar.addStretch()
        frame_layout.addLayout(self.action_bar)

        # Статус
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI", 9, italic=True))
        self.status_lbl.setStyleSheet("color: #F59E0B; background: transparent; padding-left: 2px;")
        self.status_lbl.hide()
        frame_layout.addWidget(self.status_lbl)

        # 4. Область карток / хмаринок результату
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: #090B10;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #252F45;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #F59E0B;
            }
        """)
        self.scroll_area.viewport().setStyleSheet("background: transparent; border: none;")

        self.clouds_container = QWidget()
        self.clouds_container.setStyleSheet("background: transparent; border: none;")
        self.clouds_layout = QVBoxLayout(self.clouds_container)
        self.clouds_layout.setContentsMargins(0, 0, 0, 0)
        self.clouds_layout.setSpacing(10)
        self.scroll_area.setWidget(self.clouds_container)
        frame_layout.addWidget(self.scroll_area, stretch=1)

        # Повідомлення про копіювання
        self.toast_banner = QLabel("")
        self.toast_banner.setFont(QFont("Segoe UI Black", 9))
        self.toast_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_banner.setStyleSheet("""
            background-color: #10B981;
            color: #000000;
            border-radius: 6px;
            padding: 4px;
        """)
        self.toast_banner.hide()
        frame_layout.addWidget(self.toast_banner)

        # 5. Нижній рядок з QSizeGrip для зміни розміру за кутик
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        self.tip_text = QLabel("ESC / ✕ щоб закрити")
        self.tip_text.setFont(QFont("Segoe UI", 8))
        self.tip_text.setStyleSheet("color: #64748B; background: transparent;")
        bottom_bar.addWidget(self.tip_text)
        bottom_bar.addStretch()

        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)
        self.size_grip.setStyleSheet("""
            QSizeGrip {
                width: 16px;
                height: 16px;
                background: transparent;
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><circle cx="13" cy="13" r="1.5" fill="%2394A3B8"/><circle cx="8" cy="13" r="1.5" fill="%2394A3B8"/><circle cx="13" cy="8" r="1.5" fill="%2394A3B8"/><circle cx="3" cy="13" r="1.5" fill="%2364748B"/><circle cx="8" cy="8" r="1.5" fill="%2364748B"/><circle cx="13" cy="3" r="1.5" fill="%2364748B"/></svg>');
            }
            QSizeGrip:hover {
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><circle cx="13" cy="13" r="1.5" fill="%23F59E0B"/><circle cx="8" cy="13" r="1.5" fill="%23F59E0B"/><circle cx="13" cy="8" r="1.5" fill="%23F59E0B"/><circle cx="3" cy="13" r="1.5" fill="%23F59E0B"/><circle cx="8" cy="8" r="1.5" fill="%23F59E0B"/><circle cx="13" cy="3" r="1.5" fill="%23F59E0B"/></svg>');
            }
        """)
        bottom_bar.addWidget(self.size_grip)
        frame_layout.addLayout(bottom_bar)

        main_layout.addWidget(self.bubble_frame)
        self.show_welcome_cloud()

    def show_welcome_cloud(self):
        self.clear_clouds()
        self.anki_top_btn.hide()
        welcome_card = SlovakCloudCard({
            "badge": "🇸🇰 СЛОВАЦЬКІ НОВЕЛИ",
            "title": "Вітаємо у Slovak Novel Translator!",
            "terms": ["kniha", "kapitola", "svetlo", "meč", "sila"],
            "details": [
                "• Alt+Q — Показати / сховати перекладач або перекласти виділений текст",
                "• Alt+W — Виділіть речення в читалці та натисніть хоткей, щоб вставити контекст для Anki",
                "• Виділіть або двічі клікніть будь-яке слово в читалці для миттєвого перекладу"
            ]
        })
        welcome_card.copied_signal.connect(self.on_copied)
        self.clouds_layout.addWidget(welcome_card)

    def clear_clouds(self):
        while self.clouds_layout.count():
            item = self.clouds_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def start_lookup(self, query: str):
        query = query.strip()
        if not query:
            return

        self.status_lbl.setText(f"Перекладаю '{query}'...")
        self.status_lbl.show()

        if self.active_lookup_thread and self.active_lookup_thread.isRunning():
            try:
                self.active_lookup_thread.disconnect()
            except Exception:
                pass

        self.active_lookup_thread = SlovakLookupThread(self.dict_service, query)
        self.active_lookup_thread.result_ready.connect(self.display_results)
        self.active_lookup_thread.start()

    def display_results(self, result: dict):
        self.status_lbl.hide()
        self.clear_clouds()
        self.current_result = result

        clouds = result.get("clouds", [])
        if clouds:
            self.anki_top_btn.show()
            for c in clouds:
                card = SlovakCloudCard(c)
                card.copied_signal.connect(self.on_copied)
                self.clouds_layout.addWidget(card)
        else:
            self.anki_top_btn.hide()

        self.enforce_topmost()

    def on_open_anki_modal(self):
        if not self.current_result:
            return
        word = self.current_result.get("query", "")
        trans = self.current_result.get("main", "")
        self.open_anki_dialog_signal.emit(word, trans, "")

    def pronounce_input(self, text: str = ""):
        to_speak = text.strip() if text else self.input_header.line_edit.text().strip()
        if to_speak:
            from tts_service import SlovakTTSService
            SlovakTTSService.get_instance().speak(to_speak)

    def on_ai_btn_clicked(self):
        text = self.input_header.line_edit.text().strip()
        self.open_ai_chat_signal.emit(text)

    def open_settings_dialog(self):
        dialog = SlovakSettingsDialog(self)
        dialog.exec()

    def on_copied(self, text: str):
        self.toast_banner.setText(f"Скопійовано: {text[:35]}...")
        self.toast_banner.show()
        QTimer.singleShot(2000, self.toast_banner.hide)

    def position_relative_to(self, mascot_geo):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        mx = mascot_geo.x()
        my = mascot_geo.y()
        mw = mascot_geo.width()
        mh = mascot_geo.height()

        target_x = mx + mw + 6
        target_y = my + (mh // 2) - 58

        if target_x + self.width() > screen.right() - 10:
            target_x = mx - self.width() - 6
            self.bubble_frame.set_tail_position("none")
        else:
            self.bubble_frame.set_tail_position("left_mid")

        if target_y + self.height() > screen.bottom() - 10:
            target_y = max(screen.top() + 10, screen.bottom() - self.height() - 10)

        if target_y < screen.top() + 10:
            target_y = screen.top() + 10

        self.move(target_x, target_y)
        self.enforce_topmost()

    def enforce_topmost(self):
        try:
            hwnd = int(self.winId())
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
            )
        except Exception:
            pass

    def show_and_focus(self, initial_text: str = ""):
        saved_w = config.get("window_width", 480)
        saved_h = config.get("window_height", 560)
        self.resize(max(440, saved_w), max(400, saved_h))
        self.show()
        self.raise_()
        self.activateWindow()
        self.enforce_topmost()
        if initial_text:
            self.input_header.set_text(initial_text)
            self.start_lookup(initial_text)
        else:
            self.input_header.line_edit.setFocus()

    def hide_bubble(self):
        self.hide()
        self.closed_signal.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() >= 420 and self.height() >= 380:
            config.set("window_width", self.width())
            config.set("window_height", self.height())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bubble()
        else:
            super().keyPressEvent(event)
