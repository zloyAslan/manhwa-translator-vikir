"""
History and Vocabulary Review Window for Manhwa Translator.
Allows reviewing words looked up during reading sessions and exporting to Anki.
"""

import os
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QListWidget, QListWidgetItem, QPushButton, QMessageBox
)
from dictionary_service import DictionaryService
from anki_service import AnkiService, DECKS_DIR
from config import config
from localization import tr

class HistoryWindow(QWidget):
    word_selected = pyqtSignal(str)

    def __init__(self, dict_service: DictionaryService, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.anki_service = AnkiService()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.resize(460, 540)
        self.init_ui()
        self.retranslate_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self.retranslate_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        self.header_lbl = QLabel()
        self.header_lbl.setFont(QFont("Segoe UI Black", 12))
        self.header_lbl.setStyleSheet("color: #F59E0B;")
        header_layout.addWidget(self.header_lbl)

        header_layout.addStretch()

        self.anki_badge = QLabel(f"⭐ Anki: {self.anki_service.get_cards_count()}")
        self.anki_badge.setFont(QFont("Segoe UI Black", 9))
        self.anki_badge.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.15);
            color: #FBBF24;
            border: 1.5px solid rgba(245, 158, 11, 0.4);
            border-radius: 6px;
            padding: 3px 8px;
        """)
        header_layout.addWidget(self.anki_badge)

        layout.addLayout(header_layout)

        # Search filter
        self.filter_input = QLineEdit()
        self.filter_input.setFont(QFont("Segoe UI", 10))
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

        # List Widget
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
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # Bottom buttons row 1
        btn_layout_1 = QHBoxLayout()
        btn_layout_1.setSpacing(8)

        self.copy_btn = QPushButton()
        self.copy_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #E2E8F0;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                border-color: #F59E0B;
            }
        """)
        self.copy_btn.clicked.connect(self.copy_selected)
        btn_layout_1.addWidget(self.copy_btn)

        self.anki_btn = QPushButton()
        self.anki_btn.setFont(QFont("Segoe UI Black", 9))
        self.anki_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.18);
                color: #FBBF24;
                border: 1px solid rgba(245, 158, 11, 0.45);
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #F59E0B;
                color: #000000;
            }
        """)
        self.anki_btn.clicked.connect(self.add_selected_to_anki)
        btn_layout_1.addWidget(self.anki_btn)

        self.clear_btn = QPushButton()
        self.clear_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #EF4444;
                border: 1px solid rgba(239, 68, 68, 0.35);
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.2);
            }
        """)
        self.clear_btn.clicked.connect(self.clear_history)
        btn_layout_1.addWidget(self.clear_btn)

        layout.addLayout(btn_layout_1)

        # Bottom buttons row 2: Open Anki folder
        self.open_anki_folder_btn = QPushButton()
        self.open_anki_folder_btn.setFont(QFont("Segoe UI Black", 9))
        self.open_anki_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                padding: 7px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                color: #FFFFFF;
                border-color: #F59E0B;
            }
        """)
        self.open_anki_folder_btn.clicked.connect(self.open_anki_folder)
        layout.addWidget(self.open_anki_folder_btn)

        self.setStyleSheet("background-color: #0B0E14;")

    def retranslate_ui(self):
        ul = config.ui_lang
        self.setWindowTitle(tr("hist_window_title", ul))
        self.header_lbl.setText(tr("hist_header", ul))
        self.filter_input.setPlaceholderText(tr("hist_search_ph", ul))
        self.copy_btn.setText(tr("hist_copy_btn", ul))
        self.anki_btn.setText(tr("hist_anki_btn", ul))
        self.clear_btn.setText(tr("hist_clear_btn", ul))
        self.open_anki_folder_btn.setText(tr("hist_open_folder_btn", ul))

    def load_history(self):
        self.list_widget.clear()
        records = self.dict_service.get_history(limit=120)
        for r in records:
            item = QListWidgetItem(f"⚔️ {r['word']}  ➜  {r['main']}")
            item.setData(Qt.ItemDataRole.UserRole, (r['word'], r['main']))
            self.list_widget.addItem(item)
        self.update_anki_badge()

    def update_anki_badge(self):
        self.anki_badge.setText(f"⭐ Anki: {self.anki_service.get_cards_count()}")

    def apply_filter(self, text: str):
        query = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(query not in item.text().lower())

    def on_item_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            word, _ = data
            self.word_selected.emit(word)
            self.close()

    def copy_selected(self):
        item = self.list_widget.currentItem()
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                word, main = data
                QGuiApplication.clipboard().setText(f"{word} — {main}")

    def add_selected_to_anki(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            word, main = data
            cached = self.dict_service.get_cached(word)
            phonetic = cached.get("phonetic", "") if cached else ""
            details = ""
            if cached and cached.get("clouds"):
                dets = []
                for c in cached["clouds"][1:]:
                    if c.get("terms"):
                        dets.append(f"{c.get('badge')}: {', '.join(c['terms'][:3])}")
                details = "<br>".join(dets)

            ok, msg = self.anki_service.add_card(word, main, phonetic, details)
            self.update_anki_badge()
            QMessageBox.information(self, "Anki", msg)

    def open_anki_folder(self):
        try:
            os.startfile(str(DECKS_DIR))
        except Exception as e:
            QMessageBox.warning(self, "Помилка", f"Не вдалося відкрити папку: {e}")

    def clear_history(self):
        self.dict_service.clear_history()
        self.list_widget.clear()
