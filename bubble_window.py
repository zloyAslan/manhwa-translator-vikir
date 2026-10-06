"""
Floating Comic Bubble Window for Manhwa Translator (Dark Fantasy Edition).
Features:
- Streamlined compact reading layout (sentence moved to dedicated Anki modal)
- White italic phonetic transcription next to Anki button
- Zero white strips (transparent scroll viewport)
- Resizable geometry with persistent memory
- Direct exit button (⏻ Вийти)
"""

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QGraphicsDropShadowEffect, QApplication, QPushButton, QSizeGrip
)
from bubble_widgets import ComicBubbleFrame, ComicCloudCard, ComicInputHeader, ComicArticleCard
from dictionary_service import DictionaryService
import win32con
import win32gui


class LookupThread(QThread):
    result_ready = pyqtSignal(dict)

    def __init__(self, service: DictionaryService, query: str):
        super().__init__()
        self.service = service
        self.query = query

    def run(self):
        result = self.service.lookup(self.query)
        self.result_ready.emit(result)


class BubbleWindow(QWidget):
    closed_signal = pyqtSignal()
    ocr_word_requested = pyqtSignal()
    open_anki_dialog_signal = pyqtSignal(str, str, str)
    open_ai_chat_signal = pyqtSignal(str)

    def __init__(self, dict_service: DictionaryService, config, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.config = config
        self.current_result = None
        self.active_lookup_thread = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        saved_w = self.config.get("window_width", 500)
        saved_h = self.config.get("window_height", 580)
        self.resize(max(380, saved_w), max(350, saved_h))

        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Outer comic balloon frame
        self.bubble_frame = ComicBubbleFrame(self, tail_position="left_mid")
        frame_layout = QVBoxLayout(self.bubble_frame)
        frame_layout.setContentsMargins(34, 14, 14, 14)
        frame_layout.setSpacing(8)

        # 1. Top Bar: Title & Action Buttons
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_lbl = QLabel("⚔️ ВІКІР ПЕРЕКЛАДАЧ")
        title_lbl.setFont(QFont("Segoe UI Black", 10))
        title_lbl.setStyleSheet("color: #F59E0B; letter-spacing: 0.5px; background: transparent;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        # Full Exit button
        self.exit_btn = QPushButton("⏻ Вийти")
        self.exit_btn.setToolTip("Повністю закрити програму")
        self.exit_btn.setFont(QFont("Segoe UI Black", 8))
        self.exit_btn.setFixedHeight(24)
        self.exit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #DC2626;
                color: #FFFFFF;
            }
        """)
        self.exit_btn.clicked.connect(QApplication.quit)
        top_bar.addWidget(self.exit_btn)

        # Close / Minimize '✕' button
        close_btn = QLabel("✕")
        close_btn.setToolTip("Сховати віконце (Esc)")
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
        close_btn.mousePressEvent = lambda e: self.hide_bubble()
        top_bar.addWidget(close_btn)

        frame_layout.addLayout(top_bar)

        # 2. Search / Input Header
        self.input_header = ComicInputHeader()
        self.input_header.search_requested.connect(self.start_lookup)
        self.input_header.ocr_requested.connect(self.ocr_word_requested.emit)
        frame_layout.addWidget(self.input_header)

        # 3. Action Row: Anki Creator Button + White Italic Phonetics
        self.action_bar = QHBoxLayout()
        self.action_bar.setContentsMargins(2, 0, 2, 0)
        self.action_bar.setSpacing(10)

        self.anki_btn = QPushButton("⭐ Створити картку в Anki")
        self.anki_btn.setFont(QFont("Segoe UI Black", 9))
        self.anki_btn.setFixedHeight(28)
        self.anki_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.anki_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        self.anki_btn.clicked.connect(self.on_open_anki_modal)
        self.anki_btn.hide()
        self.action_bar.addWidget(self.anki_btn)

        # Word forms / article button (Oxford style)
        self.article_btn = QPushButton("🌱 Словотвір")
        self.article_btn.setFont(QFont("Segoe UI Black", 9))
        self.article_btn.setFixedHeight(28)
        self.article_btn.setToolTip("Показати всі граматичні форми та статтю словника")
        self.article_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.article_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.18);
                color: #60A5FA;
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 6px;
                padding: 0 10px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)
        self.article_btn.clicked.connect(self.on_show_word_article)
        self.article_btn.hide()
        self.action_bar.addWidget(self.article_btn)

        # Gemini AI Assistant button (Alt+A)
        self.ai_btn = QPushButton("🤖 AI")
        self.ai_btn.setFont(QFont("Segoe UI Black", 9))
        self.ai_btn.setFixedHeight(28)
        self.ai_btn.setToolTip("ШІ-розбір речень та ідіом (Alt+A)")
        self.ai_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.18);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 6px;
                padding: 0 10px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #0D9488;
                color: #FFFFFF;
            }
        """)
        self.ai_btn.clicked.connect(self.on_ai_btn_clicked)
        self.action_bar.addWidget(self.ai_btn)

        # White Italic Phonetics Label next to buttons
        self.phonetic_top_lbl = QLabel("")
        self.phonetic_top_lbl.setFont(QFont("Segoe UI", 10, italic=True))
        self.phonetic_top_lbl.setStyleSheet("color: #FFFFFF; font-style: italic; background: transparent;")
        self.action_bar.addWidget(self.phonetic_top_lbl)

        self.action_bar.addStretch()
        frame_layout.addLayout(self.action_bar)

        # Status indicator
        self.status_lbl = QLabel("")
        self.status_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.status_lbl.setStyleSheet("color: #2DD4BF; padding: 2px 4px; background: transparent;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.hide()
        frame_layout.addWidget(self.status_lbl)

        # Notification banner (Toast)
        self.toast_banner = QLabel("")
        self.toast_banner.setFont(QFont("Segoe UI Black", 9))
        self.toast_banner.setStyleSheet("""
            background-color: #065F46;
            color: #A7F3D0;
            border: 1px solid #10B981;
            border-radius: 6px;
            padding: 4px 10px;
        """)
        self.toast_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_banner.hide()
        frame_layout.addWidget(self.toast_banner)

        # 4. Scroll area with ZERO white background
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: #090B10;
                width: 7px;
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
        self.scroll_area.viewport().setStyleSheet("background: transparent; border: none;")

        self.clouds_widget = QWidget()
        self.clouds_widget.setStyleSheet("background: transparent; border: none;")
        self.clouds_layout = QVBoxLayout(self.clouds_widget)
        self.clouds_layout.setContentsMargins(0, 4, 0, 4)
        self.clouds_layout.setSpacing(8)

        self.scroll_area.setWidget(self.clouds_widget)
        frame_layout.addWidget(self.scroll_area, stretch=1)

        # 5. Bottom resize grip bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 0, 0)
        tip_text = QLabel("📷 Alt+E = слово • Alt+W = речення • ↘ тягнути кутик")
        tip_text.setFont(QFont("Segoe UI", 8))
        tip_text.setStyleSheet("color: #64748B; background: transparent;")
        bottom_bar.addWidget(tip_text)
        bottom_bar.addStretch()

        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("QSizeGrip { width: 14px; height: 14px; background: transparent; }")
        bottom_bar.addWidget(self.size_grip)
        frame_layout.addLayout(bottom_bar)

        self.main_layout.addWidget(self.bubble_frame)

        self.show_welcome_cloud()

    def show_welcome_cloud(self):
        self.clear_clouds()
        welcome_card = ComicCloudCard({
            "badge": "🗡️ ВІКІР ГОТОВИЙ ДО БОЮ",
            "title": "Виділіть репліку через Alt+E або введіть слово",
            "phonetic": "[revenge of the iron-blooded sword hound]",
            "terms": ["devoted", "faithful", "hound", "strike", "clan"],
            "details": [
                "📷 Alt+E: миттєво виділити слово чи фразу в манхві",
                "⭐ Кнопка 'Створити картку в Anki' відкриває вікно додавання",
                "🖼️ Alt+D: рамка для захоплення малюнка панелі в картку!"
            ]
        })
        welcome_card.copied_signal.connect(self.on_copied)
        self.clouds_layout.addWidget(welcome_card)

    def clear_clouds(self):
        while self.clouds_layout.count():
            item = self.clouds_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def start_lookup(self, query: str):
        query = query.strip()
        if not query:
            return

        self.status_lbl.setText(f"🔍 Вікір перекладає '{query}'...")
        self.status_lbl.show()

        self.active_lookup_thread = LookupThread(self.dict_service, query)
        self.active_lookup_thread.result_ready.connect(self.display_results)
        self.active_lookup_thread.start()

    def display_results(self, result: dict):
        self.status_lbl.hide()
        self.clear_clouds()
        self.current_result = result

        phonetic = result.get("phonetic", "")
        if phonetic:
            clean_ph = phonetic.strip("[]/ ")
            self.phonetic_top_lbl.setText(f"/{clean_ph}/")
        else:
            self.phonetic_top_lbl.setText("")

        clouds = result.get("clouds", [])
        query = result.get("query", "")
        words = query.split()
        if len(words) in (1, 2) and clouds:
            self.article_btn.show()
        else:
            self.article_btn.hide()

        if not clouds:
            self.anki_btn.hide()
            self.article_btn.hide()
            no_res_card = ComicCloudCard({
                "badge": "⚠️ НЕ ЗНАЙДЕНО",
                "title": result.get("query", ""),
                "details": ["Перевір правильність написання англійського тексту."]
            })
            self.clouds_layout.addWidget(no_res_card)
        else:
            self.anki_btn.show()
            for cloud_data in clouds:
                card = ComicCloudCard(cloud_data)
                card.copied_signal.connect(self.on_copied)
                self.clouds_layout.addWidget(card)

        self.enforce_topmost()

    def on_show_word_article(self):
        if not self.current_result:
            return
        query = self.current_result.get("query", "")
        self.status_lbl.setText(f"📖 Завантаження статті для '{query}'...")
        self.status_lbl.show()
        article = self.dict_service.get_word_article(query)
        self.status_lbl.hide()
        self.clear_clouds()
        cards = article.get("cards", [])
        if not cards:
            no_card = ComicCloudCard({
                "badge": "⚠️ НЕ ЗНАЙДЕНО СТАТТІ",
                "title": query,
                "details": ["Не вдалося сформувати окремі граматичні статті для цього слова."]
            })
            self.clouds_layout.addWidget(no_card)
        else:
            for card_data in cards:
                art_card = ComicArticleCard(card_data)
                art_card.copied_signal.connect(self.on_copied)
                art_card.anki_requested.connect(lambda w, t: self.open_anki_dialog_signal.emit(w, t, ""))
                self.clouds_layout.addWidget(art_card)
        self.enforce_topmost()

    def on_ai_btn_clicked(self):
        text = self.input_header.line_edit.text().strip()
        words = text.split()
        if len(words) > 3:
            self.open_ai_chat_signal.emit(text)
        else:
            self.open_ai_chat_signal.emit("")

    def on_open_anki_modal(self):
        if not self.current_result:
            return
        word = self.current_result.get("query", "")
        main_trans = self.current_result.get("main", "")

        trans_lines = [main_trans]
        for c in self.current_result.get("clouds", [])[1:]:
            badge = c.get("badge", "")
            terms = c.get("terms", [])
            if terms:
                trans_lines.append(f"{badge}: {', '.join(terms[:4])}")

        full_trans = ", ".join(main_trans.split(", ")[:3])
        self.open_anki_dialog_signal.emit(word, full_trans, "")

    def on_copied(self, text: str):
        self.toast_banner.setText(f"✓ Скопійовано: {text}")
        self.toast_banner.show()
        QTimer.singleShot(2200, self.toast_banner.hide)

    def position_relative_to(self, mascot_geo):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        mx = mascot_geo.x()
        my = mascot_geo.y()
        mw = mascot_geo.width()
        mh = mascot_geo.height()

        target_x = mx + mw + 6
        target_y = my + (mh // 2) - 58

        if target_x + self.width() > screen.right() - 10:
            target_x = mx - self.width() - 6
            self.bubble_frame.set_tail_position("none")
        else:
            self.bubble_frame.set_tail_position("left_mid")

        if target_y + self.height() > screen.bottom() - 10:
            target_y = max(screen.top() + 10, screen.bottom() - self.height() - 10)

        if target_y < screen.top() + 10:
            target_y = screen.top() + 10

        self.move(target_x, target_y)
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

    def show_and_focus(self, initial_text: str = ""):
        self.show()
        self.raise_()
        self.activateWindow()
        self.enforce_topmost()
        if initial_text:
            self.input_header.set_text(initial_text)
            self.start_lookup(initial_text)
        else:
            self.input_header.line_edit.setFocus()

    def hide_bubble(self):
        self.hide()
        self.closed_signal.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bubble()
        else:
            super().keyPressEvent(event)
