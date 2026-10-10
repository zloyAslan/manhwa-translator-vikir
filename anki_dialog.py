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
    QTextEdit, QPushButton, QFrame, QFileDialog, QGraphicsDropShadowEffect,
    QDialog
)
from anki_service import AnkiService
from config import config
from localization import tr


class DarkFantasyConfirmDialog(QDialog):
    """
    Sleek Dark Fantasy confirmation/alert modal.
    Used for deck creation prompts, template synchronization, and AnkiConnect help.
    """
    def __init__(self, title: str, message: str, confirm_text: str = "", cancel_text: str = "", parent=None, is_info_only: bool = False):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(430, 270 if not is_info_only else 330)
        self.drag_start_pos = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        frame = QFrame(self)
        frame.setStyleSheet("""
            QFrame {
                background-color: #090B10;
                border: 1.5px solid #F59E0B;
                border-radius: 14px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 230))
        shadow.setOffset(0, 5)
        frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header with title & close button
        header = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI Black", 10))
        title_lbl.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        header.addWidget(title_lbl)

        header.addStretch()

        close_btn = QLabel("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setFont(QFont("Segoe UI Black", 9))
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QLabel {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QLabel:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        close_btn.mousePressEvent = lambda e: self.reject()
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Body Message
        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 9))
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #F3F4F6; background: transparent; border: none; line-height: 1.4;")
        layout.addWidget(msg_lbl, stretch=1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        if not is_info_only and cancel_text:
            cancel_btn = QPushButton(cancel_text)
            cancel_btn.setFont(QFont("Segoe UI Black", 8))
            cancel_btn.setFixedHeight(30)
            cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    color: #94A3B8;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 6px;
                    padding: 0 14px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #334155;
                    color: #F8FAFC;
                }
            """)
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text or "OK")
        confirm_btn.setFont(QFont("Segoe UI Black", 9))
        confirm_btn.setFixedHeight(30)
        confirm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)
        main_layout.addWidget(frame)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None


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
        self._prompted_deck_create = False
        self._prompted_template_sync = False

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
        deck = getattr(self.anki_service, "deck_name", "англ манхва")
        top_bar = QHBoxLayout()
        self.title_lbl = QLabel(tr("anki_dialog_title", config.ui_lang, deck=deck))
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

        # Connection status banner
        self.conn_banner = QPushButton()
        self.conn_banner.setFont(QFont("Segoe UI Black", 8))
        self.conn_banner.setFixedHeight(26)
        self.conn_banner.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.conn_banner.clicked.connect(self.on_banner_clicked)
        layout.addWidget(self.conn_banner)

        # 1. Поле "Слово"
        self.lbl_word = QLabel(tr("anki_word_label", config.ui_lang))
        self.lbl_word.setFont(QFont("Segoe UI Black", 8))
        self.lbl_word.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(self.lbl_word)

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
        self.lbl_sent = QLabel(tr("anki_sent_label", config.ui_lang))
        self.lbl_sent.setFont(QFont("Segoe UI Black", 8))
        self.lbl_sent.setStyleSheet("color: #94A3B8; border: none;")
        sent_header.addWidget(self.lbl_sent)

        sent_header.addStretch()

        self.btn_ocr_sent = QPushButton(tr("anki_btn_ocr_sent", config.ui_lang))
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
        self.sent_edit.setPlaceholderText(tr("anki_sent_placeholder", config.ui_lang))
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
        self.lbl_trans = QLabel(tr("anki_trans_label", config.ui_lang))
        self.lbl_trans.setFont(QFont("Segoe UI Black", 8))
        self.lbl_trans.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(self.lbl_trans)

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
        self.lbl_img = QLabel(tr("anki_art_label", config.ui_lang))
        self.lbl_img.setFont(QFont("Segoe UI Black", 8))
        self.lbl_img.setStyleSheet("color: #94A3B8; border: none;")
        img_header.addWidget(self.lbl_img)

        img_header.addStretch()

        self.btn_capture_art = QPushButton(tr("anki_btn_capture_art", config.ui_lang))
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
        self.btn_clear_img.setToolTip(tr("anki_delete_art_tooltip", config.ui_lang))
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
        self.img_preview = QLabel(tr("anki_no_image", config.ui_lang))
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
        self.save_btn = QPushButton(tr("anki_save_btn", config.ui_lang, deck=deck))
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

    def showEvent(self, event):
        super().showEvent(event)
        self.retranslate_ui()
        self.check_deck_and_model(prompt_user=True)

    def update_connection_banner(self, connected: bool):
        ul = config.ui_lang
        deck = getattr(self.anki_service, "deck_name", "англ манхва")
        if connected:
            self.conn_banner.setText(tr("anki_connected_banner", ul, deck=deck))
            self.conn_banner.setStyleSheet("""
                QPushButton {
                    background-color: rgba(16, 185, 129, 0.12);
                    color: #34D399;
                    border: 1px solid rgba(16, 185, 129, 0.35);
                    border-radius: 6px;
                    padding: 0 8px;
                    text-align: center;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: rgba(16, 185, 129, 0.22);
                }
            """)
        else:
            self.conn_banner.setText(tr("anki_unreachable_banner", ul))
            self.conn_banner.setStyleSheet("""
                QPushButton {
                    background-color: rgba(245, 158, 11, 0.12);
                    color: #FBBF24;
                    border: 1px solid rgba(245, 158, 11, 0.35);
                    border-radius: 6px;
                    padding: 0 8px;
                    text-align: center;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: rgba(245, 158, 11, 0.22);
                }
            """)

    def on_banner_clicked(self):
        ul = config.ui_lang
        info = self.anki_service.inspect_deck_configuration()
        if not info["connected"]:
            dlg = DarkFantasyConfirmDialog(
                title=tr("anki_unreachable_title", ul),
                message=tr("anki_unreachable_dialog_text", ul),
                confirm_text=tr("anki_btn_confirm_ok", ul),
                parent=self,
                is_info_only=True
            )
            dlg.exec()
        else:
            self.check_deck_and_model(prompt_user=True)

    def check_deck_and_model(self, prompt_user: bool = True):
        info = self.anki_service.inspect_deck_configuration()
        self.update_connection_banner(info["connected"])

        if not info["connected"]:
            return

        ul = config.ui_lang
        deck = getattr(self.anki_service, "deck_name", "англ манхва")

        if not info["deck_exists"] and prompt_user and not self._prompted_deck_create:
            self._prompted_deck_create = True
            dlg = DarkFantasyConfirmDialog(
                title=f"⚔️ {tr('app_title', ul).replace('⚔️ ', '').replace('⚡ ', '')} • ANKI",
                message=tr("anki_deck_not_found_prompt", ul, deck=deck),
                confirm_text=tr("anki_btn_create_deck", ul),
                cancel_text=tr("anki_btn_cancel", ul),
                parent=self
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.anki_service.create_deck(info["url"], deck)
                self.status_lbl.setText(tr("anki_deck_created_success", ul, deck=deck))
                self.status_lbl.setStyleSheet("color: #10B981; border: none;")
                self.status_lbl.show()
                self.update_connection_banner(True)
        elif info["deck_exists"] and not info["model_matches"] and prompt_user and not self._prompted_template_sync:
            self._prompted_template_sync = True
            dlg = DarkFantasyConfirmDialog(
                title=f"⚔️ {tr('app_title', ul).replace('⚔️ ', '').replace('⚡ ', '')} • ANKI",
                message=tr("anki_sync_template_prompt", ul, deck=deck),
                confirm_text=tr("anki_btn_sync_template", ul),
                cancel_text=tr("anki_btn_cancel", ul),
                parent=self
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.anki_service.ensure_or_create_model(info["url"])
                self.status_lbl.setText(tr("anki_template_synced_success", ul, deck=deck))
                self.status_lbl.setStyleSheet("color: #10B981; border: none;")
                self.status_lbl.show()

    def retranslate_ui(self):
        """Refreshes all labels and button texts when UI language changes."""
        ul = config.ui_lang
        deck = getattr(self.anki_service, "deck_name", "англ манхва")
        self.title_lbl.setText(tr("anki_dialog_title", ul, deck=deck))
        self.lbl_word.setText(tr("anki_word_label", ul))
        self.lbl_sent.setText(tr("anki_sent_label", ul))
        self.btn_ocr_sent.setText(tr("anki_btn_ocr_sent", ul))
        self.sent_edit.setPlaceholderText(tr("anki_sent_placeholder", ul))
        self.lbl_trans.setText(tr("anki_trans_label", ul))
        self.lbl_img.setText(tr("anki_art_label", ul))
        self.btn_capture_art.setText(tr("anki_btn_capture_art", ul))
        self.btn_clear_img.setToolTip(tr("anki_delete_art_tooltip", ul))
        if self.image_bytes is None:
            self.img_preview.setText(tr("anki_no_image", ul))
        self.save_btn.setText(tr("anki_save_btn", ul, deck=deck))

        info = self.anki_service.inspect_deck_configuration()
        self.update_connection_banner(info["connected"])

    def open_empty(self):
        """Opens completely blank dialog without carrying over any text or expressions."""
        self.retranslate_ui()
        self.word_edit.clear()
        self.trans_edit.clear()
        self.sent_edit.clear()
        self.clear_image()
        self.status_lbl.hide()
        self.save_btn.setEnabled(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.word_edit.setFocus()
        self.check_deck_and_model(prompt_user=True)

    def open_for_word(self, word: str, translation: str, sentence: str = ""):
        self.retranslate_ui()
        self.word_edit.setText(word)
        self.trans_edit.setPlainText(translation)
        self.sent_edit.setPlainText(sentence)
        self.clear_image()
        self.status_lbl.hide()
        self.save_btn.setEnabled(True)
        self.show()
        self.raise_()
        self.activateWindow()
        self.check_deck_and_model(prompt_user=True)

    def set_sentence(self, sentence: str):
        self.retranslate_ui()
        self.sent_edit.setPlainText(sentence)
        self.show()
        self.raise_()
        self.activateWindow()

    def set_image(self, img_bytes: bytes):
        self.retranslate_ui()
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
        self.img_preview.setText(tr("anki_no_image", config.ui_lang))
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
            self.status_lbl.setText(tr("anki_validation_error", config.ui_lang))
            self.status_lbl.setStyleSheet("color: #EF4444; border: none;")
            self.status_lbl.show()
            return

        ok, msg = self.anki_service.add_card(word, trans, sentence, self.image_bytes)
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet("color: #10B981; border: none;" if ok else "color: #EF4444; border: none;")
        self.status_lbl.show()

        if ok:
            self.save_btn.setText("✓ " + (tr("saved", config.ui_lang) if tr("saved", config.ui_lang) != "saved" else "OK"))
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
