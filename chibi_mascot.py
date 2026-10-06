"""
Floating Vikir Mascot Widget for Manhwa Translator.
Features draggable chibi avatar (Revenge of the Iron-Blooded Sword Hound),
always-on-top in fullscreen mode, and context menu with Alt+E and Alt+W actions.
"""

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPixmap, QCursor, QColor, QAction, QFont
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QMenu, QGraphicsDropShadowEffect, QApplication
)
from pathlib import Path
import win32con
import win32gui

ASSETS_DIR = Path(__file__).parent


class ChibiMascot(QWidget):
    clicked_signal = pyqtSignal()
    open_history_signal = pyqtSignal()
    ocr_word_signal = pyqtSignal()
    ocr_sentence_signal = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.click_tolerance = 5
        self.mouse_pressed_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.init_ui()
        self.load_mascot_image()

        saved_x = self.config.get("pos_x", 120)
        saved_y = self.config.get("pos_y", 220)
        self.move(saved_x, saved_y)

        self.topmost_timer = QTimer(self)
        self.topmost_timer.timeout.connect(self.enforce_topmost)
        self.topmost_timer.start(1500)

    def init_ui(self):
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(2, 4)
        self.image_label.setGraphicsEffect(shadow)

    def load_mascot_image(self):
        style = self.config.get("mascot_style", "sticker")
        size = self.config.get("mascot_size", 100)

        img_path = ASSETS_DIR / "vikir_sticker.png"
        if style == "badge":
            img_path = ASSETS_DIR / "vikir_badge.png"
        elif style == "art":
            img_path = ASSETS_DIR / "vikir_art_badge.png"

        if not img_path.exists():
            img_path = ASSETS_DIR / "vikir_sticker.png"

        pixmap = QPixmap(str(img_path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self.setFixedSize(scaled.width() + 10, scaled.height() + 10)
            self.image_label.setGeometry(5, 5, scaled.width(), scaled.height())
        else:
            self.setFixedSize(size, size)

        self.enforce_topmost()

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
        act_ocr_w = QAction("📷 Захопити слово з екрана (Alt+E)", self)
        act_ocr_w.triggered.connect(self.ocr_word_signal.emit)
        menu.addAction(act_ocr_w)

        # OCR Sentence Action
        act_ocr_s = QAction("📝 Захопити речення для Anki (Alt+W)", self)
        act_ocr_s.triggered.connect(self.ocr_sentence_signal.emit)
        menu.addAction(act_ocr_s)

        # Translate Action
        act_trans = QAction("💬 Відкрити перекладач (Alt+Q)", self)
        act_trans.triggered.connect(self.clicked_signal.emit)
        menu.addAction(act_trans)

        # History Action
        act_history = QAction("📖 Словник / Історія слів", self)
        act_history.triggered.connect(self.open_history_signal.emit)
        menu.addAction(act_history)

        menu.addSeparator()

        # Mascot Style submenu
        style_menu = menu.addMenu("🎨 Вигляд Вікіра")
        
        act_sticker = QAction("✨ Чібі Вікір із мечами (Стікер)", self)
        act_sticker.setCheckable(True)
        act_sticker.setChecked(self.config.get("mascot_style") == "sticker")
        act_sticker.triggered.connect(lambda: self.change_style("sticker"))
        style_menu.addAction(act_sticker)

        act_badge = QAction("🔘 Круглий жетон Вікіра", self)
        act_badge.setCheckable(True)
        act_badge.setChecked(self.config.get("mascot_style") == "badge")
        act_badge.triggered.connect(lambda: self.change_style("badge"))
        style_menu.addAction(act_badge)

        act_art = QAction("🗡️ Серйозний арт Вікіра з манхви", self)
        act_art.setCheckable(True)
        act_art.setChecked(self.config.get("mascot_style") == "art")
        act_art.triggered.connect(lambda: self.change_style("art"))
        style_menu.addAction(act_art)

        # Pin position
        pinned = self.config.get("pinned", False)
        pin_text = "🔓 Відкріпити (дозволити рух)" if pinned else "📌 Закріпити на екрані"
        act_pin = QAction(pin_text, self)
        act_pin.triggered.connect(self.toggle_pin)
        menu.addAction(act_pin)

        menu.addSeparator()

        # Full Exit Action
        act_exit = QAction("❌ Вийти з програми (Повне закриття)", self)
        act_exit.triggered.connect(QApplication.quit)
        menu.addAction(act_exit)

        menu.exec(pos)

    def change_style(self, style_name: str):
        self.config.set("mascot_style", style_name)
        self.load_mascot_image()

    def toggle_pin(self):
        curr = self.config.get("pinned", False)
        self.config.set("pinned", not curr)
