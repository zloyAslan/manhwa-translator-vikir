from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush, QFont, 
    QCursor, QGuiApplication, QLinearGradient
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFrame, QScrollArea, QGraphicsDropShadowEffect
)
import pyperclip

BG_MAIN = QColor("#090B10")
CARD_BG = QColor("#121622")
BORDER_SUBTLE = QColor(255, 255, 255, 22)
ACCENT_AMBER = QColor("#F59E0B")
ACCENT_BLUE = QColor("#3B82F6")
ACCENT_MINT = QColor("#10B981")
TEXT_LIGHT = QColor("#F3F4F6")
TEXT_MUTED = QColor("#9CA3AF")


class SlovakBubbleFrame(QWidget):
    """Кастомна хмаринка зі стрілкою-хвостиком, спрямованою на якор."""
    def __init__(self, parent=None, tail_position="left_mid"):
        super().__init__(parent)
        self.tail_position = tail_position
        self.bg_color = BG_MAIN
        self.border_width = 2.0
        self.corner_radius = 16.0
        self.tail_length = 22.0

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(4, 6)
        self.setGraphicsEffect(shadow)

    def set_tail_position(self, pos: str):
        if self.tail_position != pos:
            self.tail_position = pos
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        margin_left = self.tail_length + 4.0 if self.tail_position.startswith("left") else 6.0
        margin_top = 8.0
        margin_right = 10.0
        margin_bottom = 10.0

        rect_x = margin_left
        rect_y = margin_top
        rect_w = max(10.0, w - margin_left - margin_right)
        rect_h = max(10.0, h - margin_top - margin_bottom)

        path = QPainterPath()
        r = self.corner_radius
        path.addRoundedRect(rect_x, rect_y, rect_w, rect_h, r, r)

        tail_path = QPainterPath()
        if self.tail_position == "left_mid":
            base_y1 = rect_y + 38.0
            base_y2 = rect_y + 66.0
            tip_x = max(2.0, rect_x - self.tail_length)
            tip_y = rect_y + 50.0

            tail_path.moveTo(rect_x + 1.0, base_y1)
            tail_path.lineTo(tip_x, tip_y)
            tail_path.lineTo(rect_x + 1.0, base_y2)
            tail_path.closeSubpath()

        final_path = path.united(tail_path)

        # Тіло хмаринки
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawPath(final_path)

        # Тонка темна рамка
        pen = QPen(BORDER_SUBTLE, self.border_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(final_path)

        # Фірмова неонова верхня лінія градієнту (Бурштин -> Синій -> М'ята)
        top_grad = QLinearGradient(rect_x + 15, rect_y, rect_x + rect_w - 15, rect_y)
        top_grad.setColorAt(0.0, ACCENT_AMBER)
        top_grad.setColorAt(0.5, ACCENT_BLUE)
        top_grad.setColorAt(1.0, ACCENT_MINT)
        grad_pen = QPen(QBrush(top_grad), 2.5)
        painter.setPen(grad_pen)
        painter.drawLine(int(rect_x + 20), int(rect_y + 1), int(rect_x + rect_w - 20), int(rect_y + 1))


class SlovakInputHeader(QWidget):
    search_requested = pyqtSignal(str)
    voice_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Введіть або виділіть словацьке слово / фразу...")
        self.line_edit.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        self.line_edit.setFixedHeight(38)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 0 12px;
                color: #FFFFFF;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1.5px solid #F59E0B;
                background-color: #161C2C;
            }
        """)
        self.line_edit.returnPressed.connect(self._on_search)
        layout.addWidget(self.line_edit)

        # Кнопка озвучки 🔊 (як на скріншоті)
        self.voice_btn = QPushButton("🔊")
        self.voice_btn.setFixedSize(38, 38)
        self.voice_btn.setFont(QFont("Segoe UI Emoji", 12))
        self.voice_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.voice_btn.setToolTip("Озвучити текст голосом Lili (Slovak TTS)")
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #F3F4F6;
            }
            QPushButton:hover {
                background-color: #2563EB;
                border-color: #60A5FA;
            }
        """)
        self.voice_btn.clicked.connect(self._on_voice)
        layout.addWidget(self.voice_btn)

        # Кнопка пошуку ➔
        self.search_btn = QPushButton("➔")
        self.search_btn.setFixedSize(38, 38)
        self.search_btn.setFont(QFont("Segoe UI Black", 12))
        self.search_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: #000000;
                border: none;
                border-radius: 8px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)
        self.search_btn.clicked.connect(self._on_search)
        layout.addWidget(self.search_btn)

    def _on_search(self):
        text = self.line_edit.text().strip()
        if text:
            self.search_requested.emit(text)

    def _on_voice(self):
        text = self.line_edit.text().strip()
        if text:
            self.voice_requested.emit(text)

    def set_text(self, text: str):
        self.line_edit.setText(text)
        self.line_edit.selectAll()


class SlovakCloudCard(QFrame):
    copied_signal = pyqtSignal(str)

    def __init__(self, card_data: dict, parent=None):
        super().__init__(parent)
        self.card_data = card_data
        self.setObjectName("SlovakCloudCard")

        self.setStyleSheet("""
            QFrame#SlovakCloudCard {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QFrame#SlovakCloudCard:hover {
                border: 1px solid rgba(245, 158, 11, 0.35);
                background-color: #161C2C;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Верхня панелька картки
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        badge_text = card_data.get("badge", "СЛОВАЦЬКА ➔ УКРАЇНСЬКА")
        badge = QLabel(badge_text)
        badge.setFont(QFont("Segoe UI Black", 8))
        badge.setStyleSheet("""
            QLabel {
                background-color: rgba(245, 158, 11, 0.15);
                color: #F59E0B;
                padding: 3px 8px;
                border-radius: 6px;
                border: 1px solid rgba(245, 158, 11, 0.3);
            }
        """)
        header_layout.addWidget(badge)

        header_layout.addStretch()

        copy_hint = QLabel("клікніть щоб скопіювати")
        copy_hint.setFont(QFont("Segoe UI", 8))
        copy_hint.setStyleSheet("color: #64748B; background: transparent;")
        header_layout.addWidget(copy_hint)

        layout.addLayout(header_layout)

        # Заголовок картки (Словацьке слово + IPA транскрипція + кнопка 🔊)
        title_text = card_data.get("title", "")
        ipa_text = card_data.get("phonetic", "")
        if title_text:
            word_row = QHBoxLayout()
            word_row.setContentsMargins(0, 0, 0, 0)
            word_row.setSpacing(8)

            title_lbl = QLabel(title_text)
            title_lbl.setFont(QFont("Segoe UI Black", 16))
            title_lbl.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
            title_lbl.setWordWrap(True)
            word_row.addWidget(title_lbl)

            if ipa_text:
                ipa_lbl = QLabel(ipa_text)
                ipa_lbl.setFont(QFont("Segoe UI", 10, italic=True))
                ipa_lbl.setStyleSheet("color: #94A3B8; background: transparent; padding-top: 4px;")
                word_row.addWidget(ipa_lbl)

            # Маленька кнопка озвучки слова
            self.speaker_btn = QPushButton("🔊")
            self.speaker_btn.setFixedSize(26, 26)
            self.speaker_btn.setFont(QFont("Segoe UI Emoji", 10))
            self.speaker_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.speaker_btn.setToolTip("Прослухати вимову слова (Lili TTS)")
            self.speaker_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1E293B;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 6px;
                    color: #F8FAFC;
                }
                QPushButton:hover {
                    background-color: #3B82F6;
                    border-color: #60A5FA;
                }
            """)
            self.speaker_btn.clicked.connect(self._on_speak_word)
            word_row.addWidget(self.speaker_btn)

            word_row.addStretch()
            layout.addLayout(word_row)

        # Основний переклад (Українська)
        terms = card_data.get("terms", [])
        if terms:
            terms_lbl = QLabel(", ".join(terms))
            terms_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
            terms_lbl.setStyleSheet("color: #2DD4BF; border: none; background: transparent;")
            terms_lbl.setWordWrap(True)
            layout.addWidget(terms_lbl)

        # Додаткові деталі (наприклад DeepLX / Google)
        details = card_data.get("details", [])
        for det in details:
            det_lbl = QLabel(f"• {det}")
            det_lbl.setFont(QFont("Segoe UI", 9))
            det_lbl.setStyleSheet("color: #94A3B8; border: none; background: transparent;")
            det_lbl.setWordWrap(True)
            layout.addWidget(det_lbl)

    def _on_speak_word(self):
        text = self.card_data.get("title", "")
        if text:
            from tts_service import SlovakTTSService
            SlovakTTSService.get_instance().speak(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            title = self.card_data.get("title", "")
            terms = ", ".join(self.card_data.get("terms", []))
            to_copy = terms if terms else title
            if to_copy:
                pyperclip.copy(to_copy)
                self.copied_signal.emit(to_copy)
