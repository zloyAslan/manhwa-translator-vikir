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

class HistoryWindow(QWidget):
    word_selected = pyqtSignal(str)

    def __init__(self, dict_service: DictionaryService, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.anki_service = AnkiService()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setWindowTitle("📖 Словник Манхви - Історія Перекладів")
        self.resize(440, 530)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("🗡️ Словник слів з манхви")
        header.setFont(QFont("Segoe UI Black", 12))
        header.setStyleSheet("color: #0F172A;")
        header_layout.addWidget(header)

        header_layout.addStretch()

        self.anki_badge = QLabel(f"⭐ Anki: {self.anki_service.get_cards_count()}")
        self.anki_badge.setFont(QFont("Segoe UI Black", 9))
        self.anki_badge.setStyleSheet("""
            background-color: #FEF08A;
            color: #713F12;
            border: 1.5px solid #854D0E;
            border-radius: 6px;
            padding: 3px 8px;
        """)
        header_layout.addWidget(self.anki_badge)

        layout.addLayout(header_layout)

        # Search filter
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍 Пошук по історії слів...")
        self.filter_input.setFont(QFont("Segoe UI", 10))
        self.filter_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #CBD5E1;
                border-radius: 8px;
                padding: 6px 10px;
                background: #F8FAFC;
            }
            QLineEdit:focus {
                border-color: #2563EB;
            }
        """)
        self.filter_input.textChanged.connect(self.apply_filter)
        layout.addWidget(self.filter_input)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Segoe UI", 10))
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 2.5px solid #0F172A;
                border-radius: 10px;
                background: #FFFFFF;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #E2E8F0;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background: #EFF6FF;
            }
            QListWidget::item:selected {
                background: #2563EB;
                color: #FFFFFF;
            }
        """)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # Bottom buttons row 1
        btn_layout_1 = QHBoxLayout()
        btn_layout_1.setSpacing(8)

        self.copy_btn = QPushButton("📋 Скопіювати")
        self.copy_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.copy_btn.clicked.connect(self.copy_selected)
        btn_layout_1.addWidget(self.copy_btn)

        self.anki_btn = QPushButton("⭐ Додати в Anki")
        self.anki_btn.setFont(QFont("Segoe UI Black", 9))
        self.anki_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEF08A;
                color: #713F12;
                border: 2px solid #713F12;
            }
            QPushButton:hover {
                background-color: #FDE047;
            }
        """)
        self.anki_btn.clicked.connect(self.add_selected_to_anki)
        btn_layout_1.addWidget(self.anki_btn)

        self.clear_btn = QPushButton("🗑️ Очистити")
        self.clear_btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.clear_btn.clicked.connect(self.clear_history)
        btn_layout_1.addWidget(self.clear_btn)

        layout.addLayout(btn_layout_1)

        # Bottom buttons row 2: Open Anki folder
        self.open_anki_folder_btn = QPushButton("📦 Відкрити папку з колодою Anki (.apkg)")
        self.open_anki_folder_btn.setFont(QFont("Segoe UI Black", 9))
        self.open_anki_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #FFFFFF;
                border: 2px solid #0F172A;
                padding: 7px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.open_anki_folder_btn.clicked.connect(self.open_anki_folder)
        layout.addWidget(self.open_anki_folder_btn)

        self.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                border: 2px solid #0F172A;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
            }
        """)

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
