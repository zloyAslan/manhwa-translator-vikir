"""
OCR Snipping / Screen Lens Tool for Manhwa Translator.
Uses RapidOCR (ONNX) for flawless recognition of manhwa/comic fonts without D/P confusion.
Supports:
- Word capture mode (Alt + E)
- Sentence capture mode for Anki (Alt + W)
- Automatic ALL-CAPS normalization for manhwa fonts
"""

import re
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QThread
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QCursor, QFont, QGuiApplication, QImage
)
from PyQt6.QtWidgets import QWidget
from PIL import Image, ImageOps
import numpy as np
from rapidocr_onnxruntime import RapidOCR

# Initialize OCR engine once globally
_ocr_engine = RapidOCR()


def normalize_manhwa_caps(text: str) -> str:
    """Converts ALL-CAPS manhwa text into clean lowercase or sentence case."""
    text = text.strip()
    if not text:
        return ""
    letters = [c for c in text if c.isalpha()]
    if letters and (sum(1 for c in letters if c.isupper()) / len(letters)) > 0.65:
        if " " not in text:
            return text.lower()
        # Sentence case
        parts = re.split(r'([.!?]\s+)', text.lower())
        res = []
        for p in parts:
            if p and p[0].isalpha():
                p = p[0].upper() + p[1:]
            p = re.sub(r'\bi\b', 'I', p)
            res.append(p)
        return "".join(res)
    return text


class OcrWorker(QThread):
    finished_signal = pyqtSignal(str, str)

    def __init__(self, pil_image: Image.Image, mode: str):
        super().__init__()
        self.pil_image = pil_image
        self.mode = mode

    def run(self):
        try:
            # 1. Add white margin padding so text touching the border is not cut off
            padded_img = ImageOps.expand(self.pil_image, border=25, fill='white')
            np_img = np.array(padded_img)
            result, elapse = _ocr_engine(np_img)
            
            if result:
                # 2. Sort detected boxes strictly from top to bottom, left to right
                def get_y(item):
                    box = item[0]
                    return (box[0][1] + box[2][1]) / 2.0
                def get_x(item):
                    box = item[0]
                    return box[0][0]

                # Group into horizontal bands (16px threshold) then sort left to right
                sorted_res = sorted(result, key=lambda item: (round(get_y(item) / 16.0), get_x(item)))
                lines = [line[1] for line in sorted_res]
                raw_text = " ".join(lines)
            else:
                raw_text = ""

            # 3. Clean up noise artifacts like ^, ~, |, stray question marks on words
            raw_text = re.sub(r'[\^~\|_\\@]', ' ', raw_text)
            raw_text = re.sub(r'(?<=\s)\?(\w+)', r'\1', raw_text)
            raw_text = re.sub(r'^\?(\w+)', r'\1', raw_text)
            clean_text = raw_text.replace("\r", " ").replace("\n", " ")
            clean_text = re.sub(r"\s+", " ", clean_text)
            clean_text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", clean_text).strip()

            normalized = normalize_manhwa_caps(clean_text)
            self.finished_signal.emit(normalized, self.mode)
        except Exception as e:
            print(f"RapidOCR Error: {e}")
            self.finished_signal.emit("", self.mode)


class SnippingOverlay(QWidget):
    # Emits (captured_text, mode) where mode is "word" or "sentence"
    text_captured = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self.start_pos = QPoint()
        self.current_pos = QPoint()
        self.is_selecting = False
        self.mode = "word"  # 'word' or 'sentence'
        self.worker = None

    def start_selection(self, mode: str = "word"):
        self.mode = mode
        screens = QGuiApplication.screens()
        virtual_rect = QRect()
        for s in screens:
            virtual_rect = virtual_rect.united(s.geometry())

        self.setGeometry(virtual_rect)
        self.is_selecting = False
        self.start_pos = QPoint()
        self.current_pos = QPoint()
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(9, 11, 16, 60))

        is_sentence = (self.mode == "sentence")
        accent_color = QColor(45, 212, 191) if is_sentence else QColor(245, 158, 11)

        if self.is_selecting and self.start_pos != self.current_pos:
            select_rect = QRect(self.start_pos, self.current_pos).normalized()

            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(select_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            pen = QPen(accent_color, 2.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(select_rect)

            corner_pen = QPen(QColor(59, 130, 246) if is_sentence else QColor(45, 212, 191), 3.5)
            painter.setPen(corner_pen)
            cl = 12
            painter.drawLine(select_rect.left(), select_rect.top(), select_rect.left() + cl, select_rect.top())
            painter.drawLine(select_rect.left(), select_rect.top(), select_rect.left(), select_rect.top() + cl)
            painter.drawLine(select_rect.right(), select_rect.top(), select_rect.right() - cl, select_rect.top())
            painter.drawLine(select_rect.right(), select_rect.top(), select_rect.right(), select_rect.top() + cl)
            painter.drawLine(select_rect.left(), select_rect.bottom(), select_rect.left() + cl, select_rect.bottom())
            painter.drawLine(select_rect.left(), select_rect.bottom(), select_rect.left(), select_rect.bottom() - cl)
            painter.drawLine(select_rect.right(), select_rect.bottom(), select_rect.right() - cl, select_rect.bottom())
            painter.drawLine(select_rect.right(), select_rect.bottom(), select_rect.right() - cl, select_rect.bottom() - cl)

            tip_text = "📝 Відпустіть для речення (Anki)" if is_sentence else "📷 Відпустіть для слова (Alt+E)"
            tip_rect = QRect(select_rect.left(), max(10, select_rect.top() - 28), 280, 24)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(18, 22, 34, 235))
            painter.drawRoundedRect(tip_rect, 6, 6)

            painter.setPen(accent_color)
            painter.setFont(QFont("Segoe UI Black", 9))
            painter.drawText(tip_rect, Qt.AlignmentFlag.AlignCenter, f"{tip_text} • Esc")
        else:
            tip_w, tip_h = 430, 34
            hint_rect = QRect((self.width() - tip_w) // 2, 40, tip_w, tip_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(18, 22, 34, 240))
            painter.drawRoundedRect(hint_rect, 8, 8)

            painter.setPen(accent_color)
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            if is_sentence:
                painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, "📝 Виділіть речення з манхви (Alt+W • Esc - скасувати)")
            else:
                painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, "🔍 Виділіть репліку для перекладу (Alt+E • Esc - скасувати)")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancel_snipping()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = QRect(self.start_pos, self.current_pos).normalized()
            self.hide()

            if rect.width() > 10 and rect.height() > 10:
                screen = QGuiApplication.primaryScreen()
                pixmap = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
                qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                buffer = qimg.bits().asstring(qimg.sizeInBytes())
                pil_img = Image.frombuffer('RGBA', (qimg.width(), qimg.height()), buffer, 'raw', 'RGBA', 0, 1).convert('RGB')

                self.worker = OcrWorker(pil_img, self.mode)
                self.worker.finished_signal.connect(self.on_ocr_finished)
                self.worker.start()

    def on_ocr_finished(self, text: str, mode: str):
        if text:
            self.text_captured.emit(text, mode)

    def cancel_snipping(self):
        self.is_selecting = False
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_snipping()
        else:
            super().keyPressEvent(event)
