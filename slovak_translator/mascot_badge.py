from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QFont,
    QRadialGradient, QCursor
)
from PyQt6.QtWidgets import (
    QWidget, QMenu, QApplication
)
import win32con
import win32gui
from config import config

def paint_slovak_badge(painter: QPainter, size: int, hover: bool = False):
    """
    Малює кругле неонове Dark Fantasy лого з символами SK та 文/A в золотих тонах.
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    center = size / 2.0
    outer_r = size * 0.44

    # 1. Зовнішня золотиста аура
    aura_grad = QRadialGradient(center, center, size * 0.48)
    aura_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    aura_grad.setColorAt(0.75, QColor(245, 158, 11, 45 if not hover else 80))
    aura_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(aura_grad))
    painter.drawEllipse(QRectF(0, 0, size, size))

    # 2. Основний диск маскота (#090B10)
    disc_grad = QRadialGradient(center, center * 0.85, outer_r)
    disc_grad.setColorAt(0.0, QColor("#121622"))
    disc_grad.setColorAt(0.72, QColor("#090B10"))
    disc_grad.setColorAt(1.0, QColor("#05060A"))
    painter.setBrush(QBrush(disc_grad))

    # Золота обводка
    border_pen = QPen(QColor(245, 158, 11, 230), max(2.0, size * 0.026))
    painter.setPen(border_pen)
    painter.drawEllipse(QRectF(center - outer_r, center - outer_r, outer_r * 2, outer_r * 2))

    # 3. Символіка всередині: "SK" у верхній дузі або центральний неоновий логотип
    # Малюємо стилізовану монограму 'SK' золотом та м'ятою
    painter.setFont(QFont("Segoe UI Black", int(size * 0.22), QFont.Weight.Black))
    painter.setPen(QPen(QColor("#2DD4BF" if hover else "#F59E0B")))
    painter.drawText(QRectF(0, size * 0.18, size, size * 0.35), Qt.AlignmentFlag.AlignCenter, "SK")

    # Підпис "NOVEL" знизу
    painter.setFont(QFont("Segoe UI Black", int(size * 0.11), QFont.Weight.Bold))
    painter.setPen(QPen(QColor("#94A3B8")))
    painter.drawText(QRectF(0, size * 0.55, size, size * 0.25), Qt.AlignmentFlag.AlignCenter, "NOVEL")


class SlovakMascotBadge(QWidget):
    clicked_signal = pyqtSignal()
    open_history_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.badge_size = 64
        self.setFixedSize(self.badge_size, self.badge_size)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.drag_position = QPoint()
        self.is_dragging = False
        self.is_hovered = False

        # Відновлюємо позицію
        saved_x = config.get("pos_x", 100)
        saved_y = config.get("pos_y", 100)
        self.move(saved_x, saved_y)

        # Таймер утримання TopMost
        self.topmost_timer = QTimer(self)
        self.topmost_timer.setInterval(2000)
        self.topmost_timer.timeout.connect(self.enforce_topmost)
        self.topmost_timer.start()

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

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_slovak_badge(painter, self.badge_size, hover=self.is_hovered)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.is_dragging = False
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if not self.drag_position.isNull():
                delta = event.globalPosition().toPoint() - self.frameGeometry().topLeft() - self.drag_position
                if delta.manhattanLength() > 3:
                    self.is_dragging = True
                    new_pos = event.globalPosition().toPoint() - self.drag_position
                    self.move(new_pos)
                    config.set("pos_x", new_pos.x())
                    config.set("pos_y", new_pos.y())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_dragging:
                self.clicked_signal.emit()
            self.is_dragging = False
            event.accept()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setFont(QFont("Segoe UI", 9))
        menu.setStyleSheet("""
            QMenu {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #F3F4F6;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
            }
            QMenu::item:selected {
                background-color: #F59E0B;
                color: #000000;
                font-weight: bold;
            }
        """)

        act_show = menu.addAction("📖 Показати перекладач (Alt+Q)")
        act_show.triggered.connect(self.clicked_signal.emit)

        act_hist = menu.addAction("📜 Історія перекладів")
        act_hist.triggered.connect(self.open_history_signal.emit)

        act_center = menu.addAction("🎯 Центрувати якор")
        act_center.triggered.connect(self.center_on_screen)

        menu.addSeparator()

        act_exit = menu.addAction("⏻ Вийти")
        act_exit.triggered.connect(QApplication.quit)

        menu.exec(pos)

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        cx = screen.center().x() - (self.width() // 2)
        cy = screen.center().y() - (self.height() // 2)
        self.move(cx, cy)
        config.set("pos_x", cx)
        config.set("pos_y", cy)
        self.enforce_topmost()
