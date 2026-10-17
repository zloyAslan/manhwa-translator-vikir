from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSizeGrip
)
from anki_service import SlovakAnkiService
from config import config

class SlovakAnkiCheckWorker(QThread):
    status_ready = pyqtSignal(bool, int, str)

    def __init__(self, anki_service: SlovakAnkiService):
        super().__init__()
        self.anki_service = anki_service

    def run(self):
        connected = self.anki_service.is_connected()
        port = config.get("anki_port", 8766)
        deck = self.anki_service.deck_name
        self.status_ready.emit(connected, port, deck)


class SlovakAnkiSaveWorker(QThread):
    finished_signal = pyqtSignal(bool, str, str)  # success, word, message

    def __init__(self, anki_service: SlovakAnkiService, word: str, trans: str, sentence: str):
        super().__init__()
        self.anki_service = anki_service
        self.word = word
        self.trans = trans
        self.sentence = sentence

    def run(self):
        try:
            self.anki_service.add_card(self.word, self.trans, self.sentence)
            self.finished_signal.emit(True, self.word, "✓ Успішно збережено в Anki!")
        except Exception as e:
            self.finished_signal.emit(False, self.word, f"Помилка: {e}")


class SlovakAnkiDialog(QWidget):
    card_saved_signal = pyqtSignal(str)

    def __init__(self, anki_service: SlovakAnkiService, parent=None):
        super().__init__(parent)
        self.anki_service = anki_service
        self.drag_start_pos = None
        self._check_worker = None
        self._save_worker = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460, 520)
        self.setMinimumSize(400, 440)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Зовнішня рамка Dark Fantasy
        self.frame = QFrame(self)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #090B10;
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(4, 6)
        self.frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(10)

        # Верхня панель (Заголовок + закриття)
        top_bar = QHBoxLayout()
        self.title_lbl = QLabel(f"⭐ Anki Картка ({self.anki_service.deck_name})")
        self.title_lbl.setFont(QFont("Segoe UI Black", 11))
        self.title_lbl.setStyleSheet("color: #F59E0B; border: none;")
        top_bar.addWidget(self.title_lbl)

        top_bar.addStretch()

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

        # Статус підключення
        self.conn_banner = QPushButton()
        self.conn_banner.setFont(QFont("Segoe UI Black", 8))
        self.conn_banner.setFixedHeight(26)
        self.conn_banner.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.conn_banner.clicked.connect(self.update_connection_status)
        layout.addWidget(self.conn_banner)

        # 1. Поле "Словацьке слово" + кнопка прослуховування 🔊
        lbl_word = QLabel("Словацьке слово / вираз:")
        lbl_word.setFont(QFont("Segoe UI Black", 8))
        lbl_word.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(lbl_word)

        word_row = QHBoxLayout()
        word_row.setSpacing(6)

        self.word_edit = QLineEdit()
        self.word_edit.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.word_edit.setStyleSheet("""
            QLineEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 7px 10px;
                color: #2DD4BF;
            }
            QLineEdit:focus {
                border-color: #2DD4BF;
            }
        """)
        word_row.addWidget(self.word_edit, stretch=1)

        self.voice_btn = QPushButton("🔊")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setFont(QFont("Segoe UI Emoji", 11))
        self.voice_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.voice_btn.setToolTip("Прослухати словацьку вимову (Lili TTS)")
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: #F8FAFC;
            }
            QPushButton:hover {
                background-color: #3B82F6;
                border-color: #60A5FA;
            }
        """)
        self.voice_btn.clicked.connect(self._on_voice)
        word_row.addWidget(self.voice_btn)

        layout.addLayout(word_row)

        # 2. Поле "Контекстне речення з новели" (Alt+W)
        sent_header = QHBoxLayout()
        lbl_sent = QLabel("Контекстне речення з новели (Alt+W для виділення):")
        lbl_sent.setFont(QFont("Segoe UI Black", 8))
        lbl_sent.setStyleSheet("color: #94A3B8; border: none;")
        sent_header.addWidget(lbl_sent)

        layout.addLayout(sent_header)

        self.sent_edit = QTextEdit()
        self.sent_edit.setFont(QFont("Segoe UI", 10))
        self.sent_edit.setFixedHeight(75)
        self.sent_edit.setPlaceholderText("Виділіть речення в тексті новели та натисніть Alt+W...")
        self.sent_edit.setStyleSheet("""
            QTextEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 8px;
                color: #F1F5F9;
                font-size: 13px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border-color: #2DD4BF;
            }
        """)
        layout.addWidget(self.sent_edit)

        # 3. Поле "Український переклад"
        lbl_trans = QLabel("Український переклад:")
        lbl_trans.setFont(QFont("Segoe UI Black", 8))
        lbl_trans.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(lbl_trans)

        self.trans_edit = QTextEdit()
        self.trans_edit.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.trans_edit.setFixedHeight(85)
        self.trans_edit.setStyleSheet("""
            QTextEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px;
                color: #FFFFFF;
            }
            QTextEdit:focus {
                border-color: #2DD4BF;
            }
        """)
        layout.addWidget(self.trans_edit)

        # Статус збереження
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI Black", 9))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #10B981; border: none; padding: 4px;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        layout.addStretch()

        # Кнопка збереження картки
        deck = self.anki_service.deck_name
        self.btn_save = QPushButton(f"💾 Додати картку в Anki ({deck})")
        self.btn_save.setFont(QFont("Segoe UI Black", 10))
        self.btn_save.setFixedHeight(38)
        self.btn_save.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 9px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        self.btn_save.clicked.connect(self.save_card)
        layout.addWidget(self.btn_save)

        # Нижній рядок з QSizeGrip
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        tip_text = QLabel("ESC / ✕ щоб закрити")
        tip_text.setFont(QFont("Segoe UI", 8))
        tip_text.setStyleSheet("color: #64748B; background: transparent;")
        bottom_bar.addWidget(tip_text)
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
        layout.addLayout(bottom_bar)

        main_layout.addWidget(self.frame)
        self.update_connection_status()

    def update_connection_status(self):
        self.conn_banner.setText("⏳ Перевірка підключення до Anki...")
        self.conn_banner.setStyleSheet("""
            QPushButton {
                background-color: rgba(148, 163, 184, 0.12);
                color: #94A3B8;
                border: 1px solid rgba(148, 163, 184, 0.25);
                border-radius: 6px;
            }
        """)
        self._check_worker = SlovakAnkiCheckWorker(self.anki_service)
        self._check_worker.status_ready.connect(self._on_connection_status_ready)
        self._check_worker.start()

    def _on_connection_status_ready(self, connected: bool, port: int, deck: str):
        if connected:
            self.conn_banner.setText(f"✓ AnkiConnect підключено (порт {port}) • Колода '{deck}'")
            self.conn_banner.setStyleSheet("""
                QPushButton {
                    background-color: rgba(16, 185, 129, 0.12);
                    color: #34D399;
                    border: 1px solid rgba(16, 185, 129, 0.35);
                    border-radius: 6px;
                }
            """)
        else:
            self.conn_banner.setText("⚠ Anki недоступний. Запустіть Anki з AnkiConnect (порти 8766/8765)")
            self.conn_banner.setStyleSheet("""
                QPushButton {
                    background-color: rgba(239, 68, 68, 0.15);
                    color: #F87171;
                    border: 1px solid rgba(239, 68, 68, 0.35);
                    border-radius: 6px;
                }
            """)

    def _on_voice(self):
        word = self.word_edit.text().strip()
        if word:
            from tts_service import SlovakTTSService
            SlovakTTSService.get_instance().speak(word)

    def set_sentence(self, sentence: str):
        self.sent_edit.setPlainText(sentence)
        self.status_lbl.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_for_word(self, word: str, translation: str = "", sentence: str = ""):
        self.word_edit.setText(word)
        self.trans_edit.setPlainText(translation)
        if sentence:
            self.sent_edit.setPlainText(sentence)
        self.status_lbl.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_empty(self):
        self.word_edit.clear()
        self.trans_edit.clear()
        self.sent_edit.clear()
        self.status_lbl.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def save_card(self):
        word = self.word_edit.text().strip()
        trans = self.trans_edit.toPlainText().strip()
        sentence = self.sent_edit.toPlainText().strip()

        if not word:
            self.status_lbl.setText("Вкажіть слово!")
            self.status_lbl.setStyleSheet("color: #EF4444; border: none;")
            self.status_lbl.show()
            return

        self.btn_save.setEnabled(False)
        self.btn_save.setText("⏳ Збереження в Anki...")
        self.status_lbl.setText("Зберігаємо картку...")
        self.status_lbl.setStyleSheet("color: #F59E0B; border: none;")
        self.status_lbl.show()

        self._save_worker = SlovakAnkiSaveWorker(self.anki_service, word, trans, sentence)
        self._save_worker.finished_signal.connect(self._on_card_saved_result)
        self._save_worker.start()

    def _on_card_saved_result(self, success: bool, word: str, message: str):
        deck = self.anki_service.deck_name
        self.btn_save.setEnabled(True)
        self.btn_save.setText(f"💾 Додати картку в Anki ({deck})")

        if success:
            self.status_lbl.setText(message)
            self.status_lbl.setStyleSheet("color: #10B981; border: none;")
            self.status_lbl.show()
            self.card_saved_signal.emit(word)
            # Очищуємо поля щоб при наступному виклику не залишались старі контексти
            self.sent_edit.clear()
            self.word_edit.clear()
            self.trans_edit.clear()
            QTimer.singleShot(1200, self.hide)
        else:
            self.status_lbl.setText(message)
            self.status_lbl.setStyleSheet("color: #EF4444; border: none;")
            self.status_lbl.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
