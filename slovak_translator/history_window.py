from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QListWidget, QListWidgetItem, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QApplication
)
import pyperclip
from dictionary_service import SlovakDictionaryService
from anki_service import SlovakAnkiService

class SlovakHistoryWindow(QWidget):
    word_selected = pyqtSignal(str)

    def __init__(self, dict_service: SlovakDictionaryService, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.anki_service = SlovakAnkiService()
        self.drag_start_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(460, 540)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Контейнер Dark Fantasy
        self.frame = QFrame(self)
        self.frame.setStyleSheet("""
            QFrame#HistoryFrame {
                background-color: #090B10;
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
        """)
        self.frame.setObjectName("HistoryFrame")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 220))
        shadow.setOffset(4, 6)
        self.frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Верхній бар
        header_layout = QHBoxLayout()
        header_lbl = QLabel("📜 Історія перекладів словацької")
        header_lbl.setFont(QFont("Segoe UI Black", 11))
        header_lbl.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        header_layout.addWidget(header_lbl)

        header_layout.addStretch()

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
        header_layout.addWidget(close_btn)

        layout.addLayout(header_layout)

        # 2. Рядок швидкого фільтра
        self.filter_input = QLineEdit()
        self.filter_input.setFont(QFont("Segoe UI", 10))
        self.filter_input.setPlaceholderText("Швидкий пошук у списку...")
        self.filter_input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 10px;
                background: #121622;
                color: #F3F4F6;
            }
            QLineEdit:focus {
                border-color: #F59E0B;
            }
        """)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        # 3. Список слів QListWidget (з повним Dark Fantasy оформленням без артефактів)
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Segoe UI", 10))
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                background: #090B10;
                color: #F3F4F6;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background: rgba(245, 158, 11, 0.12);
                color: #FBBF24;
            }
            QListWidget::item:selected {
                background: #F59E0B;
                color: #000000;
                font-weight: bold;
            }
            QScrollBar:vertical {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: #090B10;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #252F45;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #F59E0B;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # 4. Нижня панель дій
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        copy_btn = QPushButton("📋 Скопіювати")
        copy_btn.setFont(QFont("Segoe UI Black", 8))
        copy_btn.setFixedHeight(30)
        copy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #E2E8F0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #F59E0B;
            }
        """)
        copy_btn.clicked.connect(self.copy_selected)
        btn_layout.addWidget(copy_btn)

        open_bubble_btn = QPushButton("📖 Перекласти в хмаринці")
        open_bubble_btn.setFont(QFont("Segoe UI Black", 8))
        open_bubble_btn.setFixedHeight(30)
        open_bubble_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_bubble_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 14px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        open_bubble_btn.clicked.connect(self.open_selected_in_bubble)
        btn_layout.addWidget(open_bubble_btn)

        layout.addLayout(btn_layout)
        main_layout.addWidget(self.frame)

    def load_history(self):
        self.list_widget.clear()
        self.filter_input.clear()
        items = self.dict_service.get_history(limit=60)
        for it in items:
            w = it["word"]
            t = it["translation"]
            item_text = f"{w}  ➔  {t}" if t else w
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, w)
            self.list_widget.addItem(list_item)

    def apply_filter(self, text: str):
        query = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(query not in item.text().lower())

    def on_item_double_clicked(self, item: QListWidgetItem):
        word = item.data(Qt.ItemDataRole.UserRole)
        if word:
            self.word_selected.emit(word)
            self.hide()

    def open_selected_in_bubble(self):
        item = self.list_widget.currentItem()
        if item:
            self.on_item_double_clicked(item)

    def copy_selected(self):
        item = self.list_widget.currentItem()
        if item:
            word = item.data(Qt.ItemDataRole.UserRole)
            if word:
                pyperclip.copy(word)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
