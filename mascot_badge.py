"""
Vector Neon Logo Badge and Interactive Widget for M_Translate.
Faithfully renders the user's sketch (media_1791610601203_55ac5d8a.png):
- Deep black background (#090B10) circular badge with subtle radial glow
- Amber / Gold neon accents (#F59E0B / #FBBF24 / #FEF08A)
- Outer circle perimeter with two opposing curved hooked bracket arcs that curve inward
- Classic intertwined translation mark: Asian character 文 interlocking with Latin 'A'
  * Character 文: top vertical stroke, horizontal bar, left-curving stroke, and intersecting right stroke.
  * Latin 'A': two angled legs with horizontal crossbar overlapping 文.
- Breathing neon pulse animation, hover brightness, and drag-and-drop window handling.
"""

from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPainterPath, QFont,
    QRadialGradient, QImage, QCursor, QAction
)
from PyQt6.QtWidgets import (
    QWidget, QMenu, QApplication
)
import win32con
import win32gui
from config import Config
from localization import tr

ASSETS_DIR = Path(__file__).parent


def paint_mtranslate_logo(painter: QPainter, size: int, hover: bool = False, glow_phase: float = 1.0):
    """
    Paints the vector M_Translate badge into the given QPainter context.
    Renders a static, sharp, clean black-gold badge without flashing/jumping animations:
    - Deep black background (#090B10)
    - Gold / Amber clean neon borders and accents
    - Central interlocking Chinese '文' and Latin 'A' translation emblem
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    center = size / 2.0
    outer_r = size * 0.44

    # 1. Subtle Outer Amber Aura
    aura_grad = QRadialGradient(center, center, size * 0.48)
    aura_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    aura_grad.setColorAt(0.75, QColor(245, 158, 11, 45))
    aura_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(aura_grad))
    painter.drawEllipse(QRectF(0, 0, size, size))

    # 2. Main Badge Disc (Deep Matte Black #090B10)
    disc_grad = QRadialGradient(center, center * 0.85, outer_r)
    disc_grad.setColorAt(0.0, QColor("#121622"))
    disc_grad.setColorAt(0.72, QColor("#090B10"))
    disc_grad.setColorAt(1.0, QColor("#05060A"))
    painter.setBrush(QBrush(disc_grad))

    # Outer circle border (Solid clean gold border)
    border_pen = QPen(QColor(245, 158, 11, 210), max(2.0, size * 0.026))
    painter.setPen(border_pen)
    painter.drawEllipse(QRectF(center - outer_r, center - outer_r, outer_r * 2, outer_r * 2))

    # 3. Central Translation Symbol: Interlocking '文' and 'A'
    # Stroke properties - static and elegant without hover distortion
    sym_color = QColor(251, 191, 36)
    sym_pen = QPen(sym_color, max(2.6, size * 0.038))
    sym_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    sym_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(sym_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(sym_pen)

    # --- Character '文' ---
    # Top vertical dot/tick (dian)
    wen_tick = QPainterPath()
    tick_x = center - (size * 0.06)
    wen_tick.moveTo(tick_x, center - (size * 0.25))
    wen_tick.lineTo(tick_x, center - (size * 0.17))
    painter.drawPath(wen_tick)

    # Horizontal bar (heng)
    wen_h = QPainterPath()
    h_y = center - (size * 0.17)
    wen_h.moveTo(center - (size * 0.24), h_y)
    wen_h.lineTo(center + (size * 0.14), h_y)
    painter.drawPath(wen_h)

    # Left-sweeping stroke (pie)
    wen_pie = QPainterPath()
    wen_pie.moveTo(tick_x + (size * 0.01), h_y)
    wen_pie.cubicTo(
        center - (size * 0.04), center - (size * 0.04),
        center - (size * 0.14), center + (size * 0.08),
        center - (size * 0.20), center + (size * 0.19)
    )
    painter.drawPath(wen_pie)

    # Right-sweeping stroke (na) crossing pie
    wen_na = QPainterPath()
    wen_na.moveTo(center - (size * 0.11), center - (size * 0.09))
    wen_na.cubicTo(
        center - (size * 0.02), center + (size * 0.02),
        center + (size * 0.06), center + (size * 0.11),
        center + (size * 0.17), center + (size * 0.19)
    )
    painter.drawPath(wen_na)

    # --- Latin 'A' (Interlocking lower-right) ---
    a_color = QColor(255, 255, 255) if hover else QColor(252, 211, 77)
    a_pen = QPen(a_color, max(2.4, size * 0.036))
    a_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    a_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(a_pen)

    # Legs of 'A'
    a_legs = QPainterPath()
    apex_x = center + (size * 0.09)
    apex_y = center - (size * 0.06)

    leg_l_x = center - (size * 0.04)
    leg_l_y = center + (size * 0.25)

    leg_r_x = center + (size * 0.22)
    leg_r_y = center + (size * 0.25)

    a_legs.moveTo(leg_l_x, leg_l_y)
    a_legs.lineTo(apex_x, apex_y)
    a_legs.lineTo(leg_r_x, leg_r_y)
    painter.drawPath(a_legs)

    # Crossbar of 'A'
    a_bar = QPainterPath()
    bar_y = center + (size * 0.11)
    bar_l_x = center + (size * 0.005)
    bar_r_x = center + (size * 0.175)
    a_bar.moveTo(bar_l_x, bar_y)
    a_bar.lineTo(bar_r_x, bar_y)
    painter.drawPath(a_bar)


def generate_mtranslate_icon_png(target_path: Path, size: int = 256):
    """Renders and saves high-resolution 256x256 PNG icon."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    paint_mtranslate_logo(painter, size, hover=False, glow_phase=1.0)
    painter.end()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(target_path), "PNG")
    return target_path


class VectorMascotBadge(QWidget):
    """
    Interactive floating widget rendering the vector neon M_Translate badge.
    Supports hover glow animation, drag-and-drop, and right-click context menu.
    """
    clicked_signal = pyqtSignal()
    open_history_signal = pyqtSignal()
    ocr_word_signal = pyqtSignal()
    ocr_sentence_signal = pyqtSignal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.click_tolerance = 5
        self.mouse_pressed_pos = QPoint()
        self.is_hovered = False
        self._glow_phase = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        badge_size = self.config.get("mascot_size", 95)
        self.setFixedSize(badge_size, badge_size)

        saved_x = self.config.get("pos_x", 120)
        saved_y = self.config.get("pos_y", 220)
        self.move(saved_x, saved_y)

        # Topmost enforcement
        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self.enforce_topmost)
        self.topmost_timer.start(1500)

    def paintEvent(self, event):
        painter = QPainter(self)
        size = min(self.width(), self.height())
        paint_mtranslate_logo(painter, size, hover=False, glow_phase=1.0)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed_pos = event.globalPosition().toPoint()
            self.drag_start_pos = event.globalPosition().toPoint() - self.pos()
            self.dragging = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if not self.config.get("pinned", False):
                delta = (event.globalPosition().toPoint() - self.mouse_pressed_pos).manhattanLength()
                if delta > self.click_tolerance:
                    self.dragging = True
                    new_pos = event.globalPosition().toPoint() - self.drag_start_pos
                    self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.dragging:
                self.clicked_signal.emit()
            else:
                self.config.set("pos_x", self.pos().x())
                self.config.set("pos_y", self.pos().y())
            self.dragging = False

    def show_context_menu(self, pos):
        ul = self.config.get("ui_lang", "uk")
        menu = QMenu(self)
        menu.setFont(QFont("Segoe UI", 9))
        menu.setStyleSheet("""
            QMenu {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 4px;
                color: #F3F4F6;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F59E0B;
                color: #000000;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.08);
                margin: 4px 6px;
            }
        """)

        # OCR Word Action
        act_ocr_w = QAction(tr("tray_word_ocr", ul), self)
        act_ocr_w.triggered.connect(self.ocr_word_signal.emit)
        menu.addAction(act_ocr_w)

        # OCR Sentence Action
        act_ocr_s = QAction(tr("tray_sent_ocr", ul), self)
        act_ocr_s.triggered.connect(self.ocr_sentence_signal.emit)
        menu.addAction(act_ocr_s)

        # Translate Action
        act_trans = QAction(tr("tray_show", ul), self)
        act_trans.triggered.connect(self.clicked_signal.emit)
        menu.addAction(act_trans)

        # History Action
        act_history = QAction(tr("tray_dict", ul), self)
        act_history.triggered.connect(self.open_history_signal.emit)
        menu.addAction(act_history)

        menu.addSeparator()

        # Pin position
        pinned = self.config.get("pinned", False)
        pin_text = "🔓 Відкріпити (дозволити рух)" if pinned else "📌 Закріпити на екрані"
        act_pin = QAction(pin_text, self)
        act_pin.triggered.connect(self.toggle_pin)
        menu.addAction(act_pin)

        menu.addSeparator()

        # Full Exit Action
        act_exit = QAction(tr("tray_exit", ul), self)
        act_exit.triggered.connect(QApplication.quit)
        menu.addAction(act_exit)

        menu.exec(pos)

    def toggle_pin(self):
        curr = self.config.get("pinned", False)
        self.config.set("pinned", not curr)
