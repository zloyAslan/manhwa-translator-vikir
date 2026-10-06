"""
Panel Art Cropper Tool for Manhwa Translator (Alt + D).
Provides a ready-made floating frame with a fixed aspect ratio (16:10)
that can be moved around the screen, scaled proportionally by dragging corners,
and captured directly into Anki cards.
"""

from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QCursor, QFont, QGuiApplication, QImage
)
from PyQt6.QtWidgets import QWidget
import io


class PanelCropper(QWidget):
    image_captured = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.aspect_ratio = 16.0 / 10.0  # Clean card aspect ratio

        self.frame_rect = QRect(200, 200, 480, 300)
        self.is_dragging_frame = False
        self.is_resizing = False
        self.active_corner = None  # 'br', 'bl', 'tr', 'tl'
        self.drag_offset = QPoint()
        self.resize_start_pos = QPoint()
        self.initial_rect = QRect()

        self.handle_size = 14

    def start_cropper(self):
        screens = QGuiApplication.screens()
        virtual_rect = QRect()
        for s in screens:
            virtual_rect = virtual_rect.united(s.geometry())

        self.setGeometry(virtual_rect)

        # Center frame on screen
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = 520
        h = int(w / self.aspect_ratio)
        cx = screen.center().x() - (w // 2)
        cy = screen.center().y() - (h // 2)
        self.frame_rect = QRect(cx, cy, w, h)

        self.show()
        self.raise_()
        self.activateWindow()

    def get_corner_rect(self, corner: str) -> QRect:
        hs = self.handle_size
        r = self.frame_rect
        if corner == 'tl':
            return QRect(r.left() - hs // 2, r.top() - hs // 2, hs, hs)
        elif corner == 'tr':
            return QRect(r.right() - hs // 2, r.top() - hs // 2, hs, hs)
        elif corner == 'bl':
            return QRect(r.left() - hs // 2, r.bottom() - hs // 2, hs, hs)
        elif corner == 'br':
            return QRect(r.right() - hs // 2, r.bottom() - hs // 2, hs, hs)
        return QRect()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark overlay
        painter.fillRect(self.rect(), QColor(9, 11, 16, 60))

        # Clear inside frame
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.frame_rect, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Amber & Mint Border
        pen = QPen(QColor(245, 158, 11), 3)  # Amber gold
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.frame_rect)

        # Draw Corner Resize Handles
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(45, 212, 191))  # Mint
        for c in ['tl', 'tr', 'bl', 'br']:
            painter.drawRoundedRect(self.get_corner_rect(c), 4, 4)

        # Floating bar above frame
        r = self.frame_rect
        bar_w = 340
        bar_h = 30
        bar_x = r.left() + (r.width() - bar_w) // 2
        bar_y = max(10, r.top() - bar_h - 8)
        bar_rect = QRect(bar_x, bar_y, bar_w, bar_h)

        painter.setBrush(QColor(18, 22, 34, 240))
        painter.drawRoundedRect(bar_rect, 7, 7)

        painter.setPen(QColor(243, 244, 246))
        painter.setFont(QFont("Segoe UI Black", 9))
        painter.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, "🖼️ Рухайте рамку • Кутик = масштаб • Enter = ✓")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            # Check corners first
            for c in ['br', 'bl', 'tr', 'tl']:
                if self.get_corner_rect(c).contains(pos):
                    self.is_resizing = True
                    self.active_corner = c
                    self.resize_start_pos = pos
                    self.initial_rect = QRect(self.frame_rect)
                    return

            # Check inside frame for dragging
            if self.frame_rect.contains(pos):
                self.is_dragging_frame = True
                self.drag_offset = pos - self.frame_rect.topLeft()
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancel()

    def mouseMoveEvent(self, event):
        pos = event.pos()

        if self.is_dragging_frame:
            new_top_left = pos - self.drag_offset
            self.frame_rect.moveTo(new_top_left)
            self.update()
            return

        if self.is_resizing and self.active_corner:
            # Scale proportionally preserving aspect ratio
            delta_x = pos.x() - self.resize_start_pos.x()
            init_w = self.initial_rect.width()

            if self.active_corner in ['br', 'tr']:
                new_w = max(180, init_w + delta_x)
            else:
                new_w = max(180, init_w - delta_x)

            new_h = int(new_w / self.aspect_ratio)

            if self.active_corner == 'br':
                self.frame_rect = QRect(self.initial_rect.left(), self.initial_rect.top(), new_w, new_h)
            elif self.active_corner == 'bl':
                self.frame_rect = QRect(self.initial_rect.right() - new_w, self.initial_rect.top(), new_w, new_h)
            elif self.active_corner == 'tr':
                self.frame_rect = QRect(self.initial_rect.left(), self.initial_rect.bottom() - new_h, new_w, new_h)
            elif self.active_corner == 'tl':
                self.frame_rect = QRect(self.initial_rect.right() - new_w, self.initial_rect.bottom() - new_h, new_w, new_h)

            self.update()
            return

        # Cursor updates
        for c in ['tl', 'br']:
            if self.get_corner_rect(c).contains(pos):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
                return
        for c in ['tr', 'bl']:
            if self.get_corner_rect(c).contains(pos):
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
                return

        if self.frame_rect.contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_frame = False
            self.is_resizing = False
            self.active_corner = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def capture_panel(self):
        self.hide()
        r = self.frame_rect
        if r.width() > 10 and r.height() > 10:
            screen = QGuiApplication.primaryScreen()
            pixmap = screen.grabWindow(0, r.x(), r.y(), r.width(), r.height())
            byte_array = io.BytesIO()
            qimg = pixmap.toImage()
            # Convert to JPEG bytes
            from PIL import Image
            buffer = qimg.bits().asstring(qimg.sizeInBytes())
            pil_img = Image.frombuffer('RGBA', (qimg.width(), qimg.height()), buffer, 'raw', 'BGRA', 0, 1)
            rgb_img = pil_img.convert('RGB')
            rgb_img.save(byte_array, format='JPEG', quality=92)
            self.image_captured.emit(byte_array.getvalue())

    def cancel(self):
        self.is_dragging_frame = False
        self.is_resizing = False
        self.hide()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.capture_panel()
        elif event.key() == Qt.Key.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)
