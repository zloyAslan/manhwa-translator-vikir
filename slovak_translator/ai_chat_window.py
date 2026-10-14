from pathlib import Path
from typing import List, Optional, Dict, Any
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QTextEdit, QPushButton, QGraphicsDropShadowEffect,
    QApplication, QMenu
)
import pyperclip
from ai_service import SlovakAIService
from config import config

AI_BG_MAIN = "#090B10"
AI_BG_CARD = "#121622"
USER_BUBBLE_BG = "#1E293B"
AI_BUBBLE_BG = "#141A28"


class SlovakAIWorker(QThread):
    analysis_ready = pyqtSignal(str, str)
    followup_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ai_service: SlovakAIService, task_type: str, sentence: str, prev_resp: str = "", question: str = ""):
        super().__init__()
        self.ai_service = ai_service
        self.task_type = task_type
        self.sentence = sentence
        self.prev_resp = prev_resp
        self.question = question

    def run(self):
        try:
            if self.task_type == "analyze":
                trans, expl = self.ai_service.analyze_sentence(self.sentence)
                self.analysis_ready.emit(trans, expl)
            elif self.task_type == "followup":
                answer = self.ai_service.ask_followup(self.sentence, self.prev_resp, self.question)
                self.followup_ready.emit(answer)
        except Exception as e:
            self.error_occurred.emit(str(e))


class SlovakAIMessageCard(QFrame):
    anki_requested = pyqtSignal(str, str, str)
    toast_signal = pyqtSignal(str)

    def __init__(self, role: str, text: str, can_anki: bool = False, raw_trans: str = "", sentence_context: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self.raw_text = text
        self.raw_trans = raw_trans
        self.sentence_context = sentence_context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Текст повідомлення
        self.text_lbl = QLabel()
        self.text_lbl.setFont(QFont("Segoe UI", 10))
        self.text_lbl.setStyleSheet("color: #F3F4F6; background: transparent; border: none; line-height: 1.4;")
        self.text_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.text_lbl.setText(text.replace("\n", "<br>"))
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.text_lbl)

        # Панель кнопок для AI
        if self.role == "ai":
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.setSpacing(8)

            copy_btn = QPushButton("📋 Скопіювати")
            copy_btn.setFont(QFont("Segoe UI", 8))
            copy_btn.setFixedHeight(22)
            copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #94A3B8;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    padding: 0 6px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                    background-color: rgba(255, 255, 255, 0.12);
                }
            """)
            copy_btn.clicked.connect(self.copy_content)
            btn_row.addWidget(copy_btn)

            if can_anki:
                anki_btn = QPushButton("⭐ В Anki")
                anki_btn.setFont(QFont("Segoe UI Black", 8))
                anki_btn.setFixedHeight(22)
                anki_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                anki_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(245, 158, 11, 0.15);
                        color: #FBBF24;
                        border: 1px solid rgba(245, 158, 11, 0.35);
                        border-radius: 4px;
                        padding: 0 8px;
                        font-weight: 800;
                    }
                    QPushButton:hover {
                        background-color: #F59E0B;
                        color: #000000;
                    }
                """)
                anki_btn.clicked.connect(self.send_to_anki)
                btn_row.addWidget(anki_btn)

            btn_row.addStretch()
            layout.addLayout(btn_row)

        # Стилізація
        if self.role == "user":
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {USER_BUBBLE_BG};
                    border: 1px solid rgba(59, 130, 246, 0.3);
                    border-radius: 12px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {AI_BUBBLE_BG};
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                }}
            """)

    def copy_content(self):
        pyperclip.copy(self.raw_text)
        self.toast_signal.emit("Текст скопійовано!")

    def send_to_anki(self):
        word = self.sentence_context[:30] if self.sentence_context else "Вираз"
        trans = self.raw_trans or self.raw_text
        self.anki_requested.emit(word, trans, self.sentence_context)


class SlovakAIChatWindow(QWidget):
    open_anki_dialog_signal = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_service = SlovakAIService()
        self.current_sentence = ""
        self.previous_ai_response = ""
        self.drag_start_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(500, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Контейнер Dark Fantasy
        self.frame = QFrame(self)
        self.frame.setStyleSheet(f"""
            QFrame#MainFrame {{
                background-color: {AI_BG_MAIN};
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }}
        """)
        self.frame.setObjectName("MainFrame")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(4, 6)
        self.frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Верхній бар
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        title_lbl = QLabel("🤖 ШІ-Консультант (Gemini B1-B2)")
        title_lbl.setFont(QFont("Segoe UI Black", 10))
        title_lbl.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        # Кнопка Очистити чат
        clear_chat_btn = QPushButton("🗑️ Очистити")
        clear_chat_btn.setFont(QFont("Segoe UI Black", 8))
        clear_chat_btn.setFixedHeight(24)
        clear_chat_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #CBD5E1;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.16);
                color: #FFFFFF;
            }
        """)
        clear_chat_btn.clicked.connect(self.clear_chat)
        top_bar.addWidget(clear_chat_btn)

        # Кнопка Закрити (✕)
        close_btn = QLabel("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setFont(QFont("Segoe UI Black", 10))
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
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
        close_btn.mousePressEvent = lambda e: self.hide()
        top_bar.addWidget(close_btn)

        layout.addLayout(top_bar)

        # Тост повідомлення
        self.toast_lbl = QLabel("")
        self.toast_lbl.setFont(QFont("Segoe UI Black", 8))
        self.toast_lbl.setStyleSheet("""
            background-color: #065F46;
            color: #A7F3D0;
            border: 1px solid #10B981;
            border-radius: 5px;
            padding: 3px 8px;
        """)
        self.toast_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_lbl.hide()
        layout.addWidget(self.toast_lbl)

        # 2. Область повідомлень (Скрол)
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

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background: transparent; border: none;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Індикатор друку
        self.typing_lbl = QLabel("⏳ ШІ аналізує словацький текст...")
        self.typing_lbl.setFont(QFont("Segoe UI", 9, italic=True))
        self.typing_lbl.setStyleSheet("color: #94A3B8; font-style: italic; background: transparent; padding-left: 6px;")
        self.typing_lbl.hide()
        layout.addWidget(self.typing_lbl)

        # 3. Нижня панель введення
        input_box = QHBoxLayout()
        input_box.setSpacing(8)

        self.chat_input = QTextEdit()
        self.chat_input.setFixedHeight(50)
        self.chat_input.setFont(QFont("Segoe UI", 10))
        self.chat_input.setPlaceholderText("Введіть питання по реченню або словацький фрагмент...")
        self.chat_input.setStyleSheet("""
            QTextEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 6px 10px;
                color: #F3F4F6;
            }
            QTextEdit:focus {
                border-color: #2DD4BF;
            }
        """)
        input_box.addWidget(self.chat_input, stretch=1)

        self.send_btn = QPushButton("➤")
        self.send_btn.setFont(QFont("Segoe UI Black", 12))
        self.send_btn.setFixedSize(46, 50)
        self.send_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2DD4BF, stop:1 #0D9488);
                color: #000000;
                border: 1px solid #2DD4BF;
                border-radius: 10px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #5EEAD4;
            }
        """)
        self.send_btn.clicked.connect(self.on_send_clicked)
        input_box.addWidget(self.send_btn)

        layout.addLayout(input_box)
        main_layout.addWidget(self.frame)

        self.show_welcome_message()

    def show_welcome_message(self):
        welcome_text = (
            "👋 Вітаю! Я ваш особистий репетитор словацької мови під час читання новел.<br><br>"
            "• Виділіть речення в тексті та відкрийте це вікно (<b>Alt+A</b>).<br>"
            "• Я розберу відмінки, фразеологізми, сленг та дам літературний переклад."
        )
        card = SlovakAIMessageCard("ai", welcome_text)
        card.toast_signal.connect(self.show_toast)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, card)

    def show_toast(self, msg: str):
        self.toast_lbl.setText(msg)
        self.toast_lbl.show()
        QTimer.singleShot(2000, self.toast_lbl.hide)

    def clear_chat(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.current_sentence = ""
        self.previous_ai_response = ""
        self.show_welcome_message()

    def prepare_input(self, sentence: str):
        if sentence:
            self.chat_input.setPlainText(sentence)
            self.current_sentence = sentence
            self.analyze_sentence(sentence)

    def analyze_sentence(self, sentence: str):
        self.add_message("user", sentence)
        self.typing_lbl.show()

        self.worker = SlovakAIWorker(self.ai_service, "analyze", sentence)
        self.worker.analysis_ready.connect(self.on_analysis_ready)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_analysis_ready(self, trans: str, expl: str):
        self.typing_lbl.hide()
        full_text = f"📖 <b>Переклад:</b><br>{trans}<br><br>🔍 <b>Розбір граматики та нюансів:</b><br>{expl}"
        self.previous_ai_response = f"{trans}\n\n{expl}"
        self.add_message("ai", full_text, can_anki=True, raw_trans=trans, sentence_context=self.current_sentence)

    def on_send_clicked(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return

        self.chat_input.clear()

        if not self.current_sentence:
            self.current_sentence = text
            self.analyze_sentence(text)
        else:
            self.add_message("user", text)
            self.typing_lbl.show()
            self.worker = SlovakAIWorker(
                self.ai_service, "followup", self.current_sentence, self.previous_ai_response, text
            )
            self.worker.followup_ready.connect(self.on_followup_ready)
            self.worker.error_occurred.connect(self.on_error)
            self.worker.start()

    def on_followup_ready(self, answer: str):
        self.typing_lbl.hide()
        self.previous_ai_response += f"\n\nВідповідь: {answer}"
        self.add_message("ai", answer)

    def on_error(self, err: str):
        self.typing_lbl.hide()
        self.add_message("ai", f"❌ Помилка: {err}")

    def add_message(self, role: str, text: str, can_anki: bool = False, raw_trans: str = "", sentence_context: str = ""):
        card = SlovakAIMessageCard(role, text, can_anki, raw_trans, sentence_context)
        card.toast_signal.connect(self.show_toast)
        card.anki_requested.connect(self.open_anki_dialog_signal.emit)

        idx = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertWidget(idx, card)
        QTimer.singleShot(60, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
