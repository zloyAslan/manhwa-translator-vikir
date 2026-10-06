"""
AI Chat Window for Manhwa Translator (Dark Fantasy Edition).
Features:
- ChatGPT / Claude style multi-session management (each conversation isolated)
- Session switcher with full message history restoration
- Text insertion without auto-sending (waits for user's Enter or button click)
- Messenger layout (User on right, Vikir AI on left)
- Movable anywhere on screen by dragging header/frame
- 2-message split for sentence analysis: Translation + Idiom breakdown
- Strict 1-step token-efficient context for follow-up questions
- Selectable text and instant '⭐ В Anki' card creation
"""

import time
from typing import List, Optional, Dict, Any
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QTextEdit, QPushButton, QGraphicsDropShadowEffect,
    QApplication, QMenu
)
import pyperclip

from ai_service import AIService

AI_BG_MAIN = "#090B10"
AI_BG_CARD = "#121622"
USER_BUBBLE_BG = "#1E293B"
AI_BUBBLE_BG = "#141A28"


class ChatSession:
    """Represents an isolated conversation session in memory."""
    def __init__(self, session_id: str, title: str, sentence: str):
        self.session_id = session_id
        self.title = title
        self.sentence = sentence
        self.previous_ai_response = ""
        self.messages: List[Dict[str, Any]] = []

    def add_message(self, role: str, text: str, badge: str = "", sentence_context: str = ""):
        self.messages.append({
            "role": role,  # 'user' or 'ai'
            "text": text,
            "badge": badge,
            "sentence_context": sentence_context
        })


class AIWorker(QThread):
    analysis_ready = pyqtSignal(str, str)  # translation, explanation
    followup_ready = pyqtSignal(str)       # answer
    error_occurred = pyqtSignal(str)

    def __init__(self, ai_service: AIService, task_type: str, sentence: str, prev_resp: str = "", question: str = ""):
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
                ans = self.ai_service.ask_followup(self.sentence, self.prev_resp, self.question)
                self.followup_ready.emit(ans)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ChatMessageBubble(QFrame):
    """Single chat bubble widget with messenger style."""
    anki_requested = pyqtSignal(str, str, str)  # word, translation, sentence
    toast_signal = pyqtSignal(str)

    def __init__(self, text: str, is_user: bool = False, badge: str = "", sentence_context: str = "", parent=None):
        super().__init__(parent)
        self.raw_text = text
        self.is_user = is_user
        self.badge = badge
        self.sentence_context = sentence_context

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Optional top badge
        if self.badge:
            badge_lbl = QLabel(self.badge)
            badge_lbl.setFont(QFont("Segoe UI Black", 8))
            badge_lbl.setStyleSheet("color: #F59E0B; background: transparent;")
            layout.addWidget(badge_lbl)

        # Message text label (selectable by mouse)
        self.text_lbl = QLabel(self.raw_text)
        self.text_lbl.setFont(QFont("Segoe UI", 10))
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_lbl.setStyleSheet("color: #F3F4F6; background: transparent; line-height: 1.4;")
        layout.addWidget(self.text_lbl)

        # AI Action row
        if not self.is_user:
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.setSpacing(8)

            copy_btn = QPushButton("📋 Копіювати")
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

        # Styling
        if self.is_user:
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
        first_line = self.raw_text.split("\n")[0].strip()
        word = self.sentence_context or first_line
        trans = self.raw_text
        self.anki_requested.emit(word, trans, self.sentence_context)


class AIChatWindow(QWidget):
    open_anki_dialog_signal = pyqtSignal(str, str, str)  # word, translation, sentence

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_service = AIService()
        self.sessions: List[ChatSession] = []
        self.current_session: Optional[ChatSession] = None
        self.active_worker = None

        self.dragging = False
        self.drag_start_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(480, 560)

        self.init_ui()
        self.start_new_chat(show_welcome=True)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

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

        # 1. Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.title_lbl = QLabel("⚔️ ВІКІР AI")
        self.title_lbl.setFont(QFont("Segoe UI Black", 10))
        self.title_lbl.setStyleSheet("color: #F59E0B; background: transparent;")
        top_bar.addWidget(self.title_lbl)

        top_bar.addStretch()

        # "+ Новий" Chat Button
        self.new_chat_btn = QPushButton("＋ Новий")
        self.new_chat_btn.setToolTip("Почати новий окремий розбір (новий чат)")
        self.new_chat_btn.setFont(QFont("Segoe UI Black", 8))
        self.new_chat_btn.setFixedHeight(24)
        self.new_chat_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.15);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.35);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #0D9488;
                color: #FFFFFF;
            }
        """)
        self.new_chat_btn.clicked.connect(lambda: self.start_new_chat(show_welcome=True))
        top_bar.addWidget(self.new_chat_btn)

        # "💬 Сесії" Dropdown Button
        self.sessions_btn = QPushButton("💬 Сесії (0)")
        self.sessions_btn.setToolTip("Список збережених діалогів цієї сесії")
        self.sessions_btn.setFont(QFont("Segoe UI Black", 8))
        self.sessions_btn.setFixedHeight(24)
        self.sessions_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.sessions_btn.setStyleSheet("""
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
        self.sessions_btn.clicked.connect(self.show_sessions_menu)
        top_bar.addWidget(self.sessions_btn)

        # Close button '✕'
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

        # Toast notification
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

        # 2. Scroll Area for Chat Messages
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

        # 3. Typing indicator label
        self.typing_lbl = QLabel("АІ Вікір пише...")
        self.typing_lbl.setFont(QFont("Segoe UI", 9, italic=True))
        self.typing_lbl.setStyleSheet("color: #94A3B8; font-style: italic; background: transparent; padding-left: 6px;")
        self.typing_lbl.hide()
        layout.addWidget(self.typing_lbl)

        # 4. Input Row
        input_box = QHBoxLayout()
        input_box.setSpacing(8)

        self.chat_input = QTextEdit()
        self.chat_input.setFixedHeight(50)
        self.chat_input.setFont(QFont("Segoe UI", 10))
        self.chat_input.setPlaceholderText("Введіть або відредагуйте текст (Enter для надсилання)...")
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
        self.chat_input.installEventFilter(self)
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

    def show_toast(self, msg: str):
        self.toast_lbl.setText(msg)
        self.toast_lbl.show()
        QTimer.singleShot(2000, self.toast_lbl.hide)

    def clear_messages_ui(self):
        """Removes all rendered message bubbles from the layout."""
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def update_sessions_button_text(self):
        count = len(self.sessions)
        self.sessions_btn.setText(f"💬 Сесії ({count})")

    def start_new_chat(self, show_welcome: bool = True):
        """Starts a clean, new chat session."""
        self.current_session = None
        self.clear_messages_ui()
        self.title_lbl.setText("⚔️ ВІКІР AI • НОВИЙ РОЗБІР")
        self.update_sessions_button_text()

        if show_welcome:
            self.render_ai_bubble(
                "Привіт! Я Вікір. Введіть речення або питання знизу та натисніть Enter (або ➤).\n"
                "Я надам точний український художній переклад та розберу приховані ідіоми.",
                badge="🗡️ ВІКІР"
            )

    def render_user_bubble(self, text: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()

        bubble = ChatMessageBubble(text, is_user=True)
        bubble.toast_signal.connect(self.show_toast)
        bubble.setMaximumWidth(int(self.width() * 0.82))
        row.addWidget(bubble)

        self.messages_layout.insertLayout(self.messages_layout.count() - 1, row)
        self.scroll_to_bottom()

    def render_ai_bubble(self, text: str, badge: str = "⚔️ ВІКІР", sentence_ctx: str = ""):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        bubble = ChatMessageBubble(text, is_user=False, badge=badge, sentence_context=sentence_ctx)
        bubble.toast_signal.connect(self.show_toast)
        bubble.anki_requested.connect(self.open_anki_dialog_signal.emit)
        bubble.setMaximumWidth(int(self.width() * 0.88))
        row.addWidget(bubble)
        row.addStretch()

        self.messages_layout.insertLayout(self.messages_layout.count() - 1, row)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        QTimer.singleShot(60, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def prepare_input(self, text: str):
        """
        Pre-fills the chat input with the given text WITHOUT auto-sending.
        Allows the user to review/edit before pressing Enter.
        """
        self.show()
        self.raise_()
        self.activateWindow()
        if text:
            self.chat_input.setText(text)
            self.chat_input.selectAll()
            self.chat_input.setFocus()

    def on_send_clicked(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return

        self.chat_input.clear()

        # If there is no active session, create a new one for this sentence
        if self.current_session is None:
            clean_title = text.replace("\n", " ").strip()
            title = clean_title[:38] + "..." if len(clean_title) > 38 else clean_title
            session_id = f"sess_{int(time.time()*1000)}"
            new_session = ChatSession(session_id, title, text)
            self.sessions.append(new_session)
            self.current_session = new_session
            self.update_sessions_button_text()
            self.title_lbl.setText(f"⚔️ {title}")

            # Clear welcome message
            self.clear_messages_ui()

            # Record and render user message
            self.current_session.add_message("user", text)
            self.render_user_bubble(text)

            # Start sentence analysis
            self.typing_lbl.show()
            self.send_btn.setEnabled(False)

            self.active_worker = AIWorker(self.ai_service, "analyze", text)
            self.active_worker.analysis_ready.connect(self.on_analysis_received)
            self.active_worker.error_occurred.connect(self.on_ai_error)
            self.active_worker.start()
        else:
            # Active session exists: this is a follow-up in this session
            self.current_session.add_message("user", text)
            self.render_user_bubble(text)

            self.typing_lbl.show()
            self.send_btn.setEnabled(False)

            self.active_worker = AIWorker(
                self.ai_service, "followup",
                self.current_session.sentence,
                self.current_session.previous_ai_response,
                text
            )
            self.active_worker.followup_ready.connect(self.on_followup_received)
            self.active_worker.error_occurred.connect(self.on_ai_error)
            self.active_worker.start()

    def on_analysis_received(self, translation: str, explanation: str):
        self.typing_lbl.hide()
        self.send_btn.setEnabled(True)

        if not self.current_session:
            return

        self.current_session.previous_ai_response = f"{translation}\n{explanation}".strip()

        if translation:
            self.current_session.add_message("ai", f"«{translation}»", badge="📖 ХУДОЖНІЙ ПЕРЕКЛАД", sentence_context=self.current_session.sentence)
            self.render_ai_bubble(f"«{translation}»", badge="📖 ХУДОЖНІЙ ПЕРЕКЛАД", sentence_ctx=self.current_session.sentence)

        if explanation:
            self.current_session.add_message("ai", explanation, badge="🔍 РОЗБІР ІДІОМ ТА СТРУКТУРИ", sentence_context=self.current_session.sentence)
            self.render_ai_bubble(explanation, badge="🔍 РОЗБІР ІДІОМ ТА СТРУКТУРИ", sentence_ctx=self.current_session.sentence)

    def on_followup_received(self, answer: str):
        self.typing_lbl.hide()
        self.send_btn.setEnabled(True)

        if not self.current_session:
            return

        self.current_session.previous_ai_response = answer
        self.current_session.add_message("ai", answer, badge="💬 ВІКІР", sentence_context=self.current_session.sentence)
        self.render_ai_bubble(answer, badge="💬 ВІКІР", sentence_ctx=self.current_session.sentence)

    def on_ai_error(self, err: str):
        self.typing_lbl.hide()
        self.send_btn.setEnabled(True)
        err_msg = f"⚠️ Помилка Gemini: {err}"
        if self.current_session:
            self.current_session.add_message("ai", err_msg, badge="⚠️ ПОМИЛКА")
        self.render_ai_bubble(err_msg, badge="⚠️ ПОМИЛКА")

    def switch_to_session(self, session: ChatSession):
        """Switches completely to the selected past conversation (restoring history)."""
        self.current_session = session
        self.clear_messages_ui()
        self.title_lbl.setText(f"⚔️ {session.title}")

        # Render all stored messages in sequence
        for m in session.messages:
            if m.get("role") == "user":
                self.render_user_bubble(m.get("text", ""))
            else:
                self.render_ai_bubble(
                    m.get("text", ""),
                    badge=m.get("badge", "⚔️ ВІКІР"),
                    sentence_ctx=m.get("sentence_context", "")
                )

        self.scroll_to_bottom()
        self.chat_input.clear()
        self.chat_input.setFocus()
        self.show_toast(f"Відкрито сесію: {session.title[:25]}...")

    def clear_all_sessions(self):
        self.sessions.clear()
        self.start_new_chat(show_welcome=True)
        self.show_toast("Всі сесії очищено!")

    def show_sessions_menu(self):
        """Displays distinct previous sessions to switch between, like ChatGPT."""
        menu = QMenu(self)
        menu.setFont(QFont("Segoe UI", 9))
        menu.setStyleSheet("""
            QMenu {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #F3F4F6;
                padding: 4px;
            }
            QMenu::item {
                padding: 7px 16px;
            }
            QMenu::item:selected {
                background-color: #2DD4BF;
                color: #000000;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.1);
                margin: 4px 8px;
            }
        """)

        # Option: New Chat
        act_new = menu.addAction("➕ Почати новий розбір")
        act_new.triggered.connect(lambda: self.start_new_chat(show_welcome=True))
        menu.addSeparator()

        if not self.sessions:
            act_empty = menu.addAction("(Немає збережених сесій)")
            act_empty.setEnabled(False)
        else:
            for s in reversed(self.sessions):
                msg_count = len(s.messages)
                is_active = (self.current_session and self.current_session.session_id == s.session_id)
                prefix = "▶ " if is_active else "💬 "
                title_preview = f"{prefix}{s.title} ({msg_count} пов.)"

                act = menu.addAction(title_preview)
                act.triggered.connect(lambda checked, target=s: self.switch_to_session(target))

            menu.addSeparator()
            act_clear = menu.addAction("🗑️ Очистити всі сесії")
            act_clear.triggered.connect(self.clear_all_sessions)

        menu.exec(QCursor.pos())

    # Movable window implementation
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def eventFilter(self, obj, event):
        if obj == self.chat_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.on_send_clicked()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
