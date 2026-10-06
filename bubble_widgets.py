"""
Comic Speech Bubble and Response Cloud Widgets for Manhwa Translator.
Features:
- Dark Fantasy Theme (Screenshot 2: #090B10, #121622, amber/blue/mint gradient)
- Horizontally aligned speech tail pointing directly into Vikir's face
- Zero white backgrounds / strips
- Integration with robust audio service
"""

from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush, QFont, 
    QCursor, QGuiApplication, QLinearGradient
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFrame, QScrollArea, QGraphicsDropShadowEffect
)
from audio_service import speak_english

# Dark Fantasy Palette matching user's reference
BG_MAIN = QColor("#090B10")
CARD_BG = QColor("#121622")
BORDER_SUBTLE = QColor(255, 255, 255, 22)
ACCENT_AMBER = QColor("#F59E0B")
ACCENT_BLUE = QColor("#3B82F6")
ACCENT_MINT = QColor("#10B981")
TEXT_LIGHT = QColor("#F3F4F6")
TEXT_MUTED = QColor("#9CA3AF")


class ComicBubbleFrame(QWidget):
    """
    A widget that paints a dark fantasy dialogue balloon with rounded corners,
    a glowing gradient top border, and an authentic comic speech tail pointing at Vikir.
    """
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
            # Point tail straight horizontally at Vikir's cheek/shoulder (y around 45..75)
            base_y1 = rect_y + 38.0
            base_y2 = rect_y + 66.0
            kink_x = rect_x - 12.0
            kink_y = rect_y + 54.0
            tip_x = max(2.0, rect_x - self.tail_length)
            tip_y = rect_y + 50.0

            tail_path.moveTo(rect_x + 1.0, base_y1)
            tail_path.lineTo(kink_x, kink_y)
            tail_path.lineTo(tip_x, tip_y)
            tail_path.lineTo(kink_x - 4.0, kink_y + 10.0)
            tail_path.lineTo(rect_x + 1.0, base_y2)
            tail_path.closeSubpath()

        combined_path = path.united(tail_path).simplified()

        # Dark Matte Fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawPath(combined_path)

        # Subtle dark border
        pen = QPen(BORDER_SUBTLE, self.border_width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(combined_path)

        # Glowing Top Gradient Line (Amber -> Blue -> Mint, matching reference screenshot 2)
        top_grad = QLinearGradient(rect_x + 15, rect_y, rect_x + rect_w - 15, rect_y)
        top_grad.setColorAt(0.0, ACCENT_AMBER)
        top_grad.setColorAt(0.5, ACCENT_BLUE)
        top_grad.setColorAt(1.0, ACCENT_MINT)
        grad_pen = QPen(QBrush(top_grad), 2.5)
        painter.setPen(grad_pen)
        painter.drawLine(int(rect_x + 20), int(rect_y + 1), int(rect_x + rect_w - 20), int(rect_y + 1))


class ComicCloudCard(QFrame):
    """
    Response cloud card with Dark Fantasy styling (#121622),
    amber badges, and no white artifacts.
    """
    copied_signal = pyqtSignal(str)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("ComicCloudCard")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        badge_text = self.data.get("badge", "ВАРІАНТ")
        badge_lbl = QLabel(f" {badge_text} ")
        badge_lbl.setFont(QFont("Segoe UI Black", 9))
        badge_lbl.setStyleSheet("""
            QLabel {
                background-color: rgba(245, 158, 11, 0.15);
                color: #FBBF24;
                border: 1px solid rgba(245, 158, 11, 0.35);
                border-radius: 9999px;
                padding: 3px 10px;
                font-weight: 800;
            }
        """)
        header_layout.addWidget(badge_lbl)

        phonetic = self.data.get("phonetic", "")
        if phonetic:
            phonetic_lbl = QLabel(phonetic)
            phonetic_lbl.setFont(QFont("Segoe UI", 9, italic=True))
            phonetic_lbl.setStyleSheet("color: #F3F4F6; font-style: italic;")
            header_layout.addWidget(phonetic_lbl)

        header_layout.addStretch()

        copy_hint = QLabel("📋 Клік щоб скопіювати")
        copy_hint.setFont(QFont("Segoe UI", 8))
        copy_hint.setStyleSheet("color: #64748B;")
        header_layout.addWidget(copy_hint)

        layout.addLayout(header_layout)

        # Main Title (Primary translation)
        main_title = self.data.get("title", "")
        if main_title:
            title_lbl = QLabel(main_title)
            title_lbl.setFont(QFont("Segoe UI Black", 16))
            title_lbl.setStyleSheet("color: #F3F4F6; font-weight: 900; background: transparent;")
            title_lbl.setWordWrap(True)
            layout.addWidget(title_lbl)

        # Terms chips
        terms = self.data.get("terms", [])
        if terms:
            terms_container = QWidget()
            terms_container.setStyleSheet("background: transparent;")
            terms_layout = QHBoxLayout(terms_container)
            terms_layout.setContentsMargins(0, 2, 0, 2)
            terms_layout.setSpacing(6)

            for term in terms[:5]:
                chip = QLabel(f"  {term}  ")
                chip.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                chip.setStyleSheet("""
                    QLabel {
                        background-color: rgba(255, 255, 255, 0.05);
                        color: #E2E8F0;
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 6px;
                        padding: 3px 8px;
                    }
                    QLabel:hover {
                        background-color: #2563EB;
                        color: #FFFFFF;
                        border-color: #60A5FA;
                    }
                """)
                terms_layout.addWidget(chip)
            terms_layout.addStretch()
            layout.addWidget(terms_container)

        # Details list
        details = self.data.get("details", [])
        for det in details[:2]:
            det_lbl = QLabel(f"• {det}")
            det_lbl.setFont(QFont("Segoe UI", 9))
            det_lbl.setStyleSheet("color: #94A3B8; background: transparent;")
            det_lbl.setWordWrap(True)
            layout.addWidget(det_lbl)

        self.setStyleSheet("""
            QFrame#ComicCloudCard {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QFrame#ComicCloudCard:hover {
                background-color: #161C2C;
                border: 1px solid rgba(245, 158, 11, 0.5);
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            text_to_copy = self.data.get("title")
            if not text_to_copy:
                terms = self.data.get("terms", [])
                text_to_copy = terms[0] if terms else ""
            if text_to_copy:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(text_to_copy)
                self.copied_signal.emit(text_to_copy)


class ComicArticleCard(QFrame):
    """
    Card displaying learner dictionary article style (Oxford/Cambridge format)
    showing part of speech, definitions with examples, and grammatical inflections/forms.
    """
    copied_signal = pyqtSignal(str)
    anki_requested = pyqtSignal(str, str)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.setObjectName("ComicArticleCard")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Top row: Badge + Anki button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        badge_lbl = QLabel(f" {self.data.get('badge', '📖 СТАТТЯ')} ")
        badge_lbl.setFont(QFont("Segoe UI Black", 8))
        badge_lbl.setStyleSheet("""
            QLabel {
                background-color: rgba(59, 130, 246, 0.18);
                color: #60A5FA;
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        top_row.addWidget(badge_lbl)

        top_row.addStretch()

        anki_mini_btn = QPushButton("⭐ В Anki")
        anki_mini_btn.setFont(QFont("Segoe UI Black", 8))
        anki_mini_btn.setFixedHeight(22)
        anki_mini_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        anki_mini_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #FBBF24;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 4px;
                padding: 0 6px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #F59E0B;
                color: #000000;
            }
        """)
        w = self.data.get("word", "")
        trans = self.data.get("translation", "") or f"[{self.data.get('pos', '')}]"
        anki_mini_btn.clicked.connect(lambda: self.anki_requested.emit(w, trans))
        top_row.addWidget(anki_mini_btn)

        layout.addLayout(top_row)

        # Word title + translation
        title_str = self.data.get("title", "")
        ukr_str = self.data.get("translation", "")
        title_lbl = QLabel(title_str)
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #2DD4BF; background: transparent;")
        layout.addWidget(title_lbl)

        if ukr_str:
            trans_lbl = QLabel(f"➜ {ukr_str}")
            trans_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            trans_lbl.setStyleSheet("color: #F3F4F6; background: transparent;")
            layout.addWidget(trans_lbl)

        # Definitions
        defs = self.data.get("definitions", [])
        for d in defs:
            d_lbl = QLabel(d)
            d_lbl.setFont(QFont("Segoe UI", 9))
            d_lbl.setStyleSheet("color: #CBD5E1; background: transparent;")
            d_lbl.setWordWrap(True)
            layout.addWidget(d_lbl)

        # Grammatical forms / inflections
        forms = self.data.get("forms", [])
        if forms:
            forms_row = QHBoxLayout()
            forms_row.setSpacing(6)
            for f in forms:
                f_chip = QLabel(f)
                f_chip.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
                f_chip.setStyleSheet("""
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #A7F3D0;
                    border: 1px solid rgba(45, 212, 191, 0.3);
                    border-radius: 5px;
                    padding: 2px 6px;
                """)
                forms_row.addWidget(f_chip)
            forms_row.addStretch()
            layout.addLayout(forms_row)

        self.setStyleSheet("""
            QFrame#ComicArticleCard {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QFrame#ComicArticleCard:hover {
                background-color: #161C2C;
                border: 1px solid rgba(59, 130, 246, 0.5);
            }
        """)



class ComicInputHeader(QWidget):
    """
    Search & Action Header with voice button, Alt+E lens button, and input field.
    """
    search_requested = pyqtSignal(str)
    ocr_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Text input
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("Введіть слово англійською (Enter для перекладу)...")
        self.line_edit.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 7px 12px;
                color: #F3F4F6;
                selection-background-color: #F59E0B;
                selection-color: #000000;
            }
            QLineEdit:focus {
                border: 1.5px solid #F59E0B;
                background-color: #171D2D;
            }
        """)
        self.line_edit.returnPressed.connect(self.on_submit)
        layout.addWidget(self.line_edit, stretch=1)

        # Voice pronunciation button 🔊
        self.voice_btn = QPushButton("🔊")
        self.voice_btn.setToolTip("Озвучити англійською (Вимова)")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setFont(QFont("Segoe UI Emoji", 12))
        self.voice_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2563EB;
                border-color: #60A5FA;
            }
        """)
        self.voice_btn.clicked.connect(self.pronounce_current)
        layout.addWidget(self.voice_btn)

        # OCR Screen Lens button 📷 Alt+E
        self.ocr_btn = QPushButton("📷 Alt+E")
        self.ocr_btn.setToolTip("Захопити слово з екрана манхви [Alt+E]")
        self.ocr_btn.setFixedHeight(36)
        self.ocr_btn.setFont(QFont("Segoe UI Black", 9))
        self.ocr_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ocr_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.15);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 8px;
                padding: 0 10px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #0D9488;
                color: #FFFFFF;
            }
        """)
        self.ocr_btn.clicked.connect(self.ocr_requested.emit)
        layout.addWidget(self.ocr_btn)

        # Translate button ➜
        self.submit_btn = QPushButton("➜")
        self.submit_btn.setToolTip("Перекласти (Enter)")
        self.submit_btn.setFont(QFont("Segoe UI Black", 12))
        self.submit_btn.setFixedSize(36, 36)
        self.submit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 8px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        self.submit_btn.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_btn)

    def on_submit(self):
        text = self.line_edit.text().strip()
        if text:
            # If all caps, lowercase single words
            if text.isupper() and " " not in text:
                text = text.lower()
                self.line_edit.setText(text)
            self.search_requested.emit(text)

    def pronounce_current(self):
        text = self.line_edit.text().strip()
        if text:
            speak_english(text)

    def set_text(self, text: str):
        self.line_edit.setText(text)
        self.line_edit.selectAll()
        self.line_edit.setFocus()
