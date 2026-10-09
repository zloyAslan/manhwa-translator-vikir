"""
Dedicated Anki Card Creator Modal for Manhwa Translator.
Allows reviewing and fine-tuning:
- Слово (Word)
- Речення (Sentence with Alt+W snip & text selection)
- Переклад (Ukrainian translation)
- Манхва-арт (Panel art with Alt+D aspect-locked cropper)
Directly saves to Anki via AnkiConnect (ports 8766/8765) and .apkg.
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QCursor, QPixmap, QImage
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QFrame, QFileDialog, QGraphicsDropShadowEffect
)
from anki_service import AnkiService


class AnkiCardDialog(QWidget):
    request_sentence_ocr = pyqtSignal()
    request_panel_crop = pyqtSignal()
    card_saved_signal = pyqtSignal(str)

    def __init__(self, anki_service: AnkiService, parent=None):
        super().__init__(parent)
        self.anki_service = anki_service
        self.image_bytes = None
        self.dragging = False
        self.drag_start_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460, 560)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Outer Dark Fantasy Frame
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
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        # Top Bar
        top_bar = QHBoxLayout()
        title_lbl = QLabel("🎴 Створення картки • англ манхва")
        title_lbl.setFont(QFont("Segoe UI Black", 11))
        title_lbl.setStyleSheet("color: #F59E0B; border: none;")
        top_bar.addWidget(title_lbl)

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

        # 1. Поле "Слово"
        lbl_word = QLabel("СЛОВО (Word):")
        lbl_word.setFont(QFont("Segoe UI Black", 8))
        lbl_word.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(lbl_word)

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
        layout.addWidget(self.word_edit)

        # 2. Поле "Речення"
        sent_header = QHBoxLayout()
        lbl_sent = QLabel("РЕЧЕННЯ (Sentence):")
        lbl_sent.setFont(QFont("Segoe UI Black", 8))
        lbl_sent.setStyleSheet("color: #94A3B8; border: none;")
        sent_header.addWidget(lbl_sent)

        sent_header.addStretch()

        self.btn_ocr_sent = QPushButton("📝 Захопити з манхви (Alt+W)")
        self.btn_ocr_sent.setFont(QFont("Segoe UI Black", 8))
        self.btn_ocr_sent.setFixedHeight(26)
        self.btn_ocr_sent.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_ocr_sent.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.15);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #0D9488;
                color: #FFFFFF;
            }
        """)
        self.btn_ocr_sent.clicked.connect(self.request_sentence_ocr.emit)
        sent_header.addWidget(self.btn_ocr_sent)

        layout.addLayout(sent_header)

        self.sent_edit = QTextEdit()
        self.sent_edit.setFont(QFont("Segoe UI", 9, italic=True))
        self.sent_edit.setFixedHeight(65)
        self.sent_edit.setPlaceholderText("Речення з манхви (виділіть через Alt+W або вставте текст)...")
        self.sent_edit.setStyleSheet("""
            QTextEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px;
                color: #CBD5E1;
            }
            QTextEdit:focus {
                border-color: #2DD4BF;
            }
        """)
        layout.addWidget(self.sent_edit)

        # 3. Поле "Переклад"
        lbl_trans = QLabel("ПЕРЕКЛАД (Translation):")
        lbl_trans.setFont(QFont("Segoe UI Black", 8))
        lbl_trans.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(lbl_trans)

        self.trans_edit = QTextEdit()
        self.trans_edit.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        self.trans_edit.setFixedHeight(75)
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

        # 4. Зображення / Манхва-арт
        img_header = QHBoxLayout()
        lbl_img = QLabel("МАНХВА-АРТ ДЛЯ КАРТКИ (Опціонально):")
        lbl_img.setFont(QFont("Segoe UI Black", 8))
        lbl_img.setStyleSheet("color: #94A3B8; border: none;")
        img_header.addWidget(lbl_img)

        img_header.addStretch()

        self.btn_capture_art = QPushButton("🖼️ Захопити панель (Alt+D)")
        self.btn_capture_art.setFont(QFont("Segoe UI Black", 8))
        self.btn_capture_art.setFixedHeight(26)
        self.btn_capture_art.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_capture_art.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.15);
                color: #60A5FA;
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)
        self.btn_capture_art.clicked.connect(self.request_panel_crop.emit)
        img_header.addWidget(self.btn_capture_art)

        self.btn_clear_img = QPushButton("🗑️")
        self.btn_clear_img.setToolTip("Видалити зображення")
        self.btn_clear_img.setFixedSize(26, 26)
        self.btn_clear_img.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_clear_img.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #94A3B8;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        self.btn_clear_img.clicked.connect(self.clear_image)
        self.btn_clear_img.hide()
        img_header.addWidget(self.btn_clear_img)

        layout.addLayout(img_header)

        # Image preview box
        self.img_preview = QLabel("Немає зображення (натисніть Alt+D для рамки арту)")
        self.img_preview.setFixedHeight(90)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setFont(QFont("Segoe UI", 8))
        self.img_preview.setStyleSheet("""
            QLabel {
                background-color: #121622;
                border: 1px dashed rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #64748B;
            }
        """)
        layout.addWidget(self.img_preview)

        # Status / Feedback label
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI Black", 9))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #10B981; border: none;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        # 5. Bottom Save Button
        self.save_btn = QPushButton("✅ Додати в Anki (англ манхва)")
        self.save_btn.setFont(QFont("Segoe UI Black", 10))
        self.save_btn.setFixedHeight(38)
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setStyleSheet("""
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
        self.save_btn.clicked.connect(self.save_card)
        layout.addWidget(self.save_btn)

        main_layout.addWidget(self.frame)

    def open_empty(self):
        """Opens completely blank dialog without carrying over any text or expressions."""
        self.word_edit.clear()
        self.trans_edit.clear()
        self.sent_edit.clear()
        self.clear_image()
        self.status_lbl.hide()
        self.save_btn.setEnabled(True)
        self.save_btn.setText("✅ Додати в Anki (англ манхва)")
        self.show()
        self.raise_()
        self.activateWindow()
        self.word_edit.setFocus()

    def open_for_word(self, word: str, translation: str, sentence: str = ""):
        self.word_edit.setText(word)
        self.trans_edit.setPlainText(translation)
        self.sent_edit.setPlainText(sentence)
        self.clear_image()
        self.status_lbl.hide()
        self.save_btn.setEnabled(True)
        self.save_btn.setText("✅ Додати в Anki (англ манхва)")
        self.show()
        self.raise_()
        self.activateWindow()

    def set_sentence(self, sentence: str):
        self.sent_edit.setPlainText(sentence)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_image(self, img_bytes: bytes):
        self.image_bytes = img_bytes
        pixmap = QPixmap()
        pixmap.loadFromData(img_bytes)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.img_preview.width() - 10, self.img_preview.height() - 10,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.img_preview.setPixmap(scaled)
            self.img_preview.setStyleSheet("""
                QLabel {
                    background-color: #121622;
                    border: 1.5px solid #2DD4BF;
                    border-radius: 8px;
                }
            """)
            self.btn_clear_img.show()
        self.show()
        self.raise_()
        self.activateWindow()

    def clear_image(self):
        self.image_bytes = None
        self.img_preview.clear()
        self.img_preview.setText("Немає зображення (натисніть Alt+D для рамки арту)")
        self.img_preview.setStyleSheet("""
            QLabel {
                background-color: #121622;
                border: 1px dashed rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #64748B;
            }
        """)
        self.btn_clear_img.hide()

    def save_card(self):
        word = self.word_edit.text().strip()
        trans = self.trans_edit.toPlainText().strip()
        sentence = self.sent_edit.toPlainText().strip()

        if not word or not trans:
            self.status_lbl.setText("⚠️ Заповніть слово та переклад!")
            self.status_lbl.setStyleSheet("color: #EF4444; border: none;")
            self.status_lbl.show()
            return

        ok, msg = self.anki_service.add_card(word, trans, sentence, self.image_bytes)
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet("color: #10B981; border: none;" if ok else "color: #EF4444; border: none;")
        self.status_lbl.show()

        if ok:
            self.save_btn.setText("✓ Успішно додано!")
            self.save_btn.setEnabled(False)
            self.card_saved_signal.emit(word)
            QTimer.singleShot(1400, self.hide)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.save_card()
        else:
            super().keyPressEvent(event)
