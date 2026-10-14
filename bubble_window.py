"""
Floating Comic Bubble Window for Manhwa Translator (Dark Fantasy Edition).
Features:
- Streamlined compact reading layout (sentence moved to dedicated Anki modal)
- White italic phonetic transcription next to Anki button
- Zero white strips (transparent scroll viewport)
- Resizable geometry with persistent memory
- Language direction switching (Source -> Target) & quick swap (⇄)
- Full UI localization (uk, en, ru)
- Sleek Dark Fantasy Settings dialog (⚙)
- Direct exit button (⏻ Вийти)
"""

from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QColor, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QGraphicsDropShadowEffect, QApplication, QPushButton, QSizeGrip,
    QComboBox, QDialog, QFrame
)
from bubble_widgets import ComicBubbleFrame, ComicCloudCard, ComicInputHeader, ComicArticleCard
from dictionary_service import DictionaryService
from localization import tr, get_lang_label, SUPPORTED_SOURCE_LANGS, SUPPORTED_TARGET_LANGS, SUPPORTED_UI_LANGS
import win32con
import win32gui


class LanguageSettingsDialog(QDialog):
    """
    Settings dialog with Dark Fantasy aesthetic:
    - [Languages / Мови]: Source, Target, UI Language + Swap button
    - [AI / ШІ Gemini]: Gemini API Key (masked/unmasked toggle), Model dropdown, AI Response Language selector
    - [Anki Connect]: Deck Name input, Connection test status badge, Ports checking (8766/8765)
    - [Інструкція / Help]: Button to open local HTML user guide in default browser
    """
    settings_saved = pyqtSignal(str, str, str)  # src, tgt, ui

    def __init__(self, current_src: str, current_tgt: str, current_ui: str, parent=None):
        super().__init__(parent)
        self.current_src = current_src
        self.current_tgt = current_tgt
        self.current_ui = current_ui
        self.drag_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 480)

        self.init_ui()
        self.test_anki_connection(initial=True)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Dialog container frame
        frame = QFrame(self)
        frame.setStyleSheet("""
            QFrame#SettingsFrame {
                background-color: #090B10;
                border: 1.5px solid #F59E0B;
                border-radius: 14px;
            }
        """)
        frame.setObjectName("SettingsFrame")
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 230))
        shadow.setOffset(0, 4)
        frame.setGraphicsEffect(shadow)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(18, 14, 18, 14)
        frame_layout.setSpacing(10)

        # Header bar
        header = QHBoxLayout()
        title_lbl = QLabel(tr("settings_dialog_title", self.current_ui))
        title_lbl.setFont(QFont("Segoe UI Black", 11))
        title_lbl.setStyleSheet("color: #F59E0B; background: transparent; border: none;")
        header.addWidget(title_lbl)

        header.addStretch()

        close_btn = QLabel("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setFont(QFont("Segoe UI Black", 9))
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QLabel {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QLabel:hover {
                background-color: #EF4444;
                color: #FFFFFF;
            }
        """)
        close_btn.mousePressEvent = lambda e: self.reject()
        header.addWidget(close_btn)
        frame_layout.addLayout(header)

        # Tab widget styling
        from PyQt6.QtWidgets import QTabWidget, QLineEdit
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.1);
                background-color: #0E121A;
                border-radius: 8px;
                padding: 10px;
            }
            QTabBar::tab {
                background-color: #121622;
                color: #94A3B8;
                padding: 6px 12px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #0E121A;
                color: #F59E0B;
                border-color: #F59E0B;
                font-weight: 900;
            }
            QTabBar::tab:hover:!selected {
                color: #F3F4F6;
                background-color: #161D2D;
            }
        """)

        # Common styles
        combo_style = """
            QComboBox {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 5px 8px;
                font-weight: 700;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #F59E0B;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid #F59E0B;
                selection-background-color: #F59E0B;
                selection-color: #000000;
                outline: none;
            }
        """
        input_style = """
            QLineEdit {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 5px 8px;
                font-weight: 600;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #F59E0B;
            }
        """
        lbl_style = "color: #CBD5E1; font-size: 11px; font-weight: 700; background: transparent; border: none;"

        # TAB 1: Languages
        tab_lang = QWidget()
        tl_layout = QVBoxLayout(tab_lang)
        tl_layout.setContentsMargins(6, 6, 6, 6)
        tl_layout.setSpacing(8)

        src_lbl = QLabel(tr("source_lang_label", self.current_ui))
        src_lbl.setStyleSheet(lbl_style)
        tl_layout.addWidget(src_lbl)

        self.src_combo = QComboBox()
        self.src_combo.setStyleSheet(combo_style)
        for code in SUPPORTED_SOURCE_LANGS:
            label = f"{get_lang_label(code, self.current_ui)} ({code.upper()})"
            self.src_combo.addItem(label, code)
        src_idx = self.src_combo.findData(self.current_src)
        if src_idx >= 0:
            self.src_combo.setCurrentIndex(src_idx)
        tl_layout.addWidget(self.src_combo)

        tgt_lbl = QLabel(tr("target_lang_label", self.current_ui))
        tgt_lbl.setStyleSheet(lbl_style)
        tl_layout.addWidget(tgt_lbl)

        self.tgt_combo = QComboBox()
        self.tgt_combo.setStyleSheet(combo_style)
        for code in SUPPORTED_TARGET_LANGS:
            label = f"{get_lang_label(code, self.current_ui)} ({code.upper()})"
            self.tgt_combo.addItem(label, code)
        tgt_idx = self.tgt_combo.findData(self.current_tgt)
        if tgt_idx >= 0:
            self.tgt_combo.setCurrentIndex(tgt_idx)
        tl_layout.addWidget(self.tgt_combo)

        ui_lbl = QLabel(tr("ui_lang_label", self.current_ui))
        ui_lbl.setStyleSheet(lbl_style)
        tl_layout.addWidget(ui_lbl)

        self.ui_combo = QComboBox()
        self.ui_combo.setStyleSheet(combo_style)
        for code in SUPPORTED_UI_LANGS:
            label = f"{get_lang_label(code, self.current_ui)} ({code.upper()})"
            self.ui_combo.addItem(label, code)
        ui_idx = self.ui_combo.findData(self.current_ui)
        if ui_idx >= 0:
            self.ui_combo.setCurrentIndex(ui_idx)
        tl_layout.addWidget(self.ui_combo)

        swap_btn = QPushButton(tr("lang_swap_btn", self.current_ui))
        swap_btn.setFont(QFont("Segoe UI Black", 8))
        swap_btn.setFixedHeight(26)
        swap_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        swap_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #FBBF24;
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 6px;
                padding: 0 8px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #F59E0B;
                color: #000000;
            }
        """)
        swap_btn.clicked.connect(self.on_swap)
        tl_layout.addWidget(swap_btn)
        tl_layout.addStretch()
        self.tab_widget.addTab(tab_lang, tr("tab_languages", self.current_ui))

        # TAB 2: AI Gemini
        tab_ai = QWidget()
        tai_layout = QVBoxLayout(tab_ai)
        tai_layout.setContentsMargins(6, 6, 6, 6)
        tai_layout.setSpacing(8)

        ai_key_lbl = QLabel(tr("gemini_api_key_label", self.current_ui))
        ai_key_lbl.setStyleSheet(lbl_style)
        tai_layout.addWidget(ai_key_lbl)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        from config import config
        self.key_input = QLineEdit()
        self.key_input.setStyleSheet(input_style)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setText(config.get("gemini_api_key", ""))
        key_row.addWidget(self.key_input, stretch=1)

        self.toggle_key_btn = QPushButton("👁")
        self.toggle_key_btn.setFixedSize(28, 28)
        self.toggle_key_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_key_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #F59E0B;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1E293B;
            }
        """)
        self.toggle_key_btn.clicked.connect(self.toggle_key_visibility)
        key_row.addWidget(self.toggle_key_btn)
        tai_layout.addLayout(key_row)

        ai_model_lbl = QLabel(tr("gemini_model_label", self.current_ui))
        ai_model_lbl.setStyleSheet(lbl_style)
        tai_layout.addWidget(ai_model_lbl)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setStyleSheet(combo_style)
        self.ai_model_combo.addItem("gemini-flash-latest (стабільний, авто-вибір)", "gemini-flash-latest")
        self.ai_model_combo.addItem("gemini-3.1-flash-lite (надшвидкий 3.1)", "gemini-3.1-flash-lite")
        self.ai_model_combo.addItem("gemini-3.5-flash (потужний 3.5)", "gemini-3.5-flash")
        cur_model = config.get("gemini_model", "gemini-flash-latest")
        m_idx = self.ai_model_combo.findData(cur_model)
        if m_idx >= 0:
            self.ai_model_combo.setCurrentIndex(m_idx)
        tai_layout.addWidget(self.ai_model_combo)

        ai_resp_lbl = QLabel(tr("ai_resp_lang_label", self.current_ui))
        ai_resp_lbl.setStyleSheet(lbl_style)
        tai_layout.addWidget(ai_resp_lbl)

        self.ai_resp_combo = QComboBox()
        self.ai_resp_combo.setStyleSheet(combo_style)
        self.ai_resp_combo.addItem("Українська (UK)", "uk")
        self.ai_resp_combo.addItem("English (EN)", "en")
        self.ai_resp_combo.addItem("Русский (RU)", "ru")
        cur_resp_lang = config.get("ai_response_lang", "uk")
        r_idx = self.ai_resp_combo.findData(cur_resp_lang)
        if r_idx >= 0:
            self.ai_resp_combo.setCurrentIndex(r_idx)
        tai_layout.addWidget(self.ai_resp_combo)
        tai_layout.addStretch()
        self.tab_widget.addTab(tab_ai, tr("tab_ai", self.current_ui))

        # TAB 3: Anki Connect
        tab_anki = QWidget()
        tanki_layout = QVBoxLayout(tab_anki)
        tanki_layout.setContentsMargins(6, 6, 6, 6)
        tanki_layout.setSpacing(8)

        deck_lbl = QLabel(tr("anki_deck_label", self.current_ui))
        deck_lbl.setStyleSheet(lbl_style)
        tanki_layout.addWidget(deck_lbl)

        self.deck_input = QLineEdit()
        self.deck_input.setStyleSheet(input_style)
        self.deck_input.setText(config.get("anki_deck", "англ манхва"))
        tanki_layout.addWidget(self.deck_input)

        status_header = QLabel(tr("anki_status_label", self.current_ui))
        status_header.setStyleSheet(lbl_style)
        tanki_layout.addWidget(status_header)

        self.anki_status_badge = QLabel("🔍 Перевірка...")
        self.anki_status_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.anki_status_badge.setStyleSheet("""
            QLabel {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        tanki_layout.addWidget(self.anki_status_badge)

        test_anki_btn = QPushButton(tr("anki_test_btn", self.current_ui))
        test_anki_btn.setFont(QFont("Segoe UI Black", 8))
        test_anki_btn.setFixedHeight(28)
        test_anki_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        test_anki_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 212, 191, 0.15);
                color: #2DD4BF;
                border: 1px solid rgba(45, 212, 191, 0.4);
                border-radius: 6px;
                padding: 0 10px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #0D9488;
                color: #FFFFFF;
            }
        """)
        test_anki_btn.clicked.connect(lambda: self.test_anki_connection(initial=False))
        tanki_layout.addWidget(test_anki_btn)
        tanki_layout.addStretch()
        self.tab_widget.addTab(tab_anki, tr("tab_anki", self.current_ui))

        # TAB 4: User Guide / Help
        tab_help = QWidget()
        thelp_layout = QVBoxLayout(tab_help)
        thelp_layout.setContentsMargins(6, 6, 6, 6)
        thelp_layout.setSpacing(12)

        help_desc = QLabel(
            "M_Translate створено для комфортного читання манхви та вивчення мови.\n"
            "• Alt+Q = виклик пошуку перекладача\n"
            "• Alt+E / F12 = захоплення слова з екрана\n"
            "• Alt+W = захоплення речення для Anki\n"
            "• Alt+D = рамка кадрування арту манхви (16:10)\n"
            "• Alt+A = чат розбору ідіом та контексту з ШІ"
        )
        help_desc.setFont(QFont("Segoe UI", 9))
        help_desc.setStyleSheet("color: #94A3B8; background: transparent; line-height: 1.5;")
        thelp_layout.addWidget(help_desc)

        guide_btn = QPushButton(tr("help_guide_btn", self.current_ui))
        guide_btn.setFont(QFont("Segoe UI Black", 9))
        guide_btn.setFixedHeight(34)
        guide_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        guide_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 8px;
                padding: 0 14px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        guide_btn.clicked.connect(self.open_user_guide)
        thelp_layout.addWidget(guide_btn)
        thelp_layout.addStretch()
        self.tab_widget.addTab(tab_help, tr("tab_help", self.current_ui))

        frame_layout.addWidget(self.tab_widget)

        # Bottom Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton(tr("cancel_btn", self.current_ui))
        cancel_btn.setFont(QFont("Segoe UI Black", 8))
        cancel_btn.setFixedHeight(28)
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 0 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                color: #FFFFFF;
                border-color: #CBD5E1;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(tr("save_btn", self.current_ui))
        save_btn.setFont(QFont("Segoe UI Black", 9))
        save_btn.setFixedHeight(28)
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)
        save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(save_btn)

        frame_layout.addLayout(btn_layout)
        main_layout.addWidget(frame)

    def toggle_key_visibility(self):
        from PyQt6.QtWidgets import QLineEdit
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("🔒")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("👁")

    def test_anki_connection(self, initial: bool = False):
        import requests
        ports = [8766, 8765]
        found_port = None
        for p in ports:
            try:
                resp = requests.post(f"http://127.0.0.1:{p}", json={"action": "version", "version": 6}, timeout=0.35)
                if resp.status_code == 200 and resp.json().get("result"):
                    found_port = p
                    break
            except Exception:
                continue

        if found_port:
            msg = tr("anki_connected", self.current_ui, port=found_port)
            self.anki_status_badge.setText(msg)
            self.anki_status_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34D399;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
            """)
        else:
            msg = tr("anki_not_found", self.current_ui)
            self.anki_status_badge.setText(msg)
            self.anki_status_badge.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.15);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
            """)

    def open_user_guide(self):
        import webbrowser
        from pathlib import Path
        guide_file = Path(__file__).parent / "user_guide.html"
        if guide_file.exists():
            webbrowser.open(guide_file.as_uri())
        else:
            webbrowser.open("https://github.com")

    def on_swap(self):
        cur_src = self.src_combo.currentData()
        cur_tgt = self.tgt_combo.currentData()

        if cur_src == "auto":
            new_src = cur_tgt
            new_tgt = "uk" if new_src != "uk" else "en"
        else:
            new_src = cur_tgt
            new_tgt = cur_src if cur_src in SUPPORTED_TARGET_LANGS else "uk"

        src_idx = self.src_combo.findData(new_src)
        if src_idx >= 0:
            self.src_combo.setCurrentIndex(src_idx)

        tgt_idx = self.tgt_combo.findData(new_tgt)
        if tgt_idx >= 0:
            self.tgt_combo.setCurrentIndex(tgt_idx)

    def on_save(self):
        from config import config
        new_src = self.src_combo.currentData()
        new_tgt = self.tgt_combo.currentData()
        new_ui = self.ui_combo.currentData()

        # Save AI settings
        config.set("gemini_api_key", self.key_input.text().strip())
        config.set("gemini_model", self.ai_model_combo.currentData())
        config.set("ai_response_lang", self.ai_resp_combo.currentData())

        # Save Anki settings
        deck_text = self.deck_input.text().strip() or "англ манхва"
        config.set("anki_deck", deck_text)

        self.settings_saved.emit(new_src, new_tgt, new_ui)
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None


class LookupThread(QThread):
    result_ready = pyqtSignal(dict)

    def __init__(self, service: DictionaryService, query: str, source_lang: str = "en", target_lang: str = "uk", ui_lang: str = "uk"):
        super().__init__()
        self.service = service
        self.query = query
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.ui_lang = ui_lang

    def run(self):
        result = self.service.lookup(
            self.query,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            ui_lang=self.ui_lang
        )
        self.result_ready.emit(result)


class BubbleWindow(QWidget):
    closed_signal = pyqtSignal()
    quit_requested = pyqtSignal()
    ocr_word_requested = pyqtSignal()
    open_anki_dialog_signal = pyqtSignal(str, str, str)
    open_ai_chat_signal = pyqtSignal(str)
    ui_language_changed = pyqtSignal(str)

    def __init__(self, dict_service: DictionaryService, config, parent=None):
        super().__init__(parent)
        self.dict_service = dict_service
        self.config = config
        self.current_result = None
        self.active_lookup_thread = None
        self.is_article_view = False
        self._updating_combos = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        saved_w = self.config.get("window_width", 500)
        saved_h = self.config.get("window_height", 580)
        self.setMinimumSize(420, 380)
        self.resize(max(440, saved_w), max(400, saved_h))

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

        # 1. Top Bar: Title, Language Direction Controls, Settings & Action Buttons
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.title_lbl = QLabel(tr("app_title", self.get_ui_lang()))
        self.title_lbl.setFont(QFont("Segoe UI Black", 10))
        self.title_lbl.setStyleSheet("color: #F59E0B; letter-spacing: 0.5px; background: transparent;")
        top_bar.addWidget(self.title_lbl)

        # Language Direction Bar
        lang_ctrl_layout = QHBoxLayout()
        lang_ctrl_layout.setSpacing(4)

        combo_style = """
            QComboBox {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 1px 4px 1px 6px;
                font-weight: 800;
                font-size: 11px;
            }
            QComboBox:hover {
                border: 1px solid #F59E0B;
                background-color: #161C2C;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 14px;
                border-left: none;
            }
            QComboBox QAbstractItemView {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid #F59E0B;
                selection-background-color: #F59E0B;
                selection-color: #000000;
                outline: none;
            }
        """

        # Source language combo
        self.src_combo = QComboBox()
        self.src_combo.setFixedSize(64, 24)
        self.src_combo.setFont(QFont("Segoe UI Black", 8))
        self.src_combo.setStyleSheet(combo_style)
        self.src_combo.addItem("AUTO", "auto")
        self.src_combo.addItem("EN", "en")
        self.src_combo.addItem("UK", "uk")
        self.src_combo.addItem("RU", "ru")
        self.src_combo.currentIndexChanged.connect(self.on_source_combo_changed)
        lang_ctrl_layout.addWidget(self.src_combo)

        # Swap button ⇄
        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setFixedSize(26, 24)
        self.swap_btn.setFont(QFont("Segoe UI Black", 10))
        self.swap_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.swap_btn.setToolTip(tr("swap_tooltip", self.get_ui_lang()))
        self.swap_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.12);
                color: #F59E0B;
                border: 1px solid rgba(245, 158, 11, 0.35);
                border-radius: 6px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #F59E0B;
                color: #000000;
            }
        """)
        self.swap_btn.clicked.connect(self.on_swap_langs_clicked)
        lang_ctrl_layout.addWidget(self.swap_btn)

        # Target language combo
        self.tgt_combo = QComboBox()
        self.tgt_combo.setFixedSize(54, 24)
        self.tgt_combo.setFont(QFont("Segoe UI Black", 8))
        self.tgt_combo.setStyleSheet(combo_style)
        self.tgt_combo.addItem("UK", "uk")
        self.tgt_combo.addItem("EN", "en")
        self.tgt_combo.addItem("RU", "ru")
        self.tgt_combo.currentIndexChanged.connect(self.on_target_combo_changed)
        lang_ctrl_layout.addWidget(self.tgt_combo)

        # Settings dialog button ⚙
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(26, 24)
        self.settings_btn.setFont(QFont("Segoe UI Emoji", 9))
        self.settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_btn.setToolTip(tr("settings_tooltip", self.get_ui_lang()))
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #121622;
                color: #94A3B8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: #252F45;
                color: #F59E0B;
                border-color: #F59E0B;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings_dialog)
        lang_ctrl_layout.addWidget(self.settings_btn)

        top_bar.addLayout(lang_ctrl_layout)
        top_bar.addStretch()

        # Full Exit button
        self.exit_btn = QPushButton(tr("exit_btn", self.get_ui_lang()))
        self.exit_btn.setToolTip(tr("exit_tooltip", self.get_ui_lang()))
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
        self.exit_btn.clicked.connect(self.quit_requested.emit)
        top_bar.addWidget(self.exit_btn)

        # Close / Minimize '✕' button
        self.close_btn = QLabel("✕")
        self.close_btn.setToolTip(tr("close_tooltip", self.get_ui_lang()))
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.close_btn.setFont(QFont("Segoe UI Black", 10))
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.setStyleSheet("""
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
        self.close_btn.mousePressEvent = lambda e: self.hide_bubble()
        top_bar.addWidget(self.close_btn)

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

        self.anki_btn = QPushButton(tr("anki_btn", self.get_ui_lang()))
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
        self.article_btn = QPushButton(tr("article_btn", self.get_ui_lang()))
        self.article_btn.setFont(QFont("Segoe UI Black", 9))
        self.article_btn.setFixedHeight(28)
        self.article_btn.setToolTip(tr("article_tooltip", self.get_ui_lang()))
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
        self.ai_btn = QPushButton(tr("ai_btn", self.get_ui_lang()))
        self.ai_btn.setFont(QFont("Segoe UI Black", 9))
        self.ai_btn.setFixedHeight(28)
        self.ai_btn.setToolTip(tr("ai_tooltip", self.get_ui_lang()))
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
        self.tip_text = QLabel(tr("bottom_tip", self.get_ui_lang()))
        self.tip_text.setFont(QFont("Segoe UI", 8))
        self.tip_text.setStyleSheet("color: #64748B; background: transparent;")
        bottom_bar.addWidget(self.tip_text)
        bottom_bar.addStretch()

        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("QSizeGrip { width: 14px; height: 14px; background: transparent; }")
        bottom_bar.addWidget(self.size_grip)
        frame_layout.addLayout(bottom_bar)

        self.main_layout.addWidget(self.bubble_frame)

        # Sync combo states with configuration & initialize UI localization
        self.sync_combos_from_config()
        self.retranslate_ui()
        self.show_welcome_cloud()

    def get_ui_lang(self) -> str:
        return self.config.get("ui_lang", "uk")

    def sync_combos_from_config(self):
        """Syncs top-bar language combo boxes to active configuration without firing recursive events."""
        self._updating_combos = True
        cur_src = self.config.get("source_lang", "en")
        cur_tgt = self.config.get("target_lang", "uk")

        src_idx = self.src_combo.findData(cur_src)
        if src_idx >= 0:
            self.src_combo.setCurrentIndex(src_idx)

        tgt_idx = self.tgt_combo.findData(cur_tgt)
        if tgt_idx >= 0:
            self.tgt_combo.setCurrentIndex(tgt_idx)

        self._updating_combos = False

    def retranslate_ui(self):
        """Updates all visible UI strings and tooltips based on current UI language."""
        ul = self.get_ui_lang()

        self.title_lbl.setText(tr("app_title", ul))
        self.exit_btn.setText(tr("exit_btn", ul))
        self.exit_btn.setToolTip(tr("exit_tooltip", ul))
        self.close_btn.setToolTip(tr("close_tooltip", ul))
        self.swap_btn.setToolTip(tr("swap_tooltip", ul))
        self.settings_btn.setToolTip(tr("settings_tooltip", ul))

        self.input_header.line_edit.setPlaceholderText(tr("input_placeholder", ul))
        self.input_header.voice_btn.setToolTip(tr("voice_tooltip", ul))
        self.input_header.ocr_btn.setToolTip(tr("ocr_tooltip", ul))
        self.input_header.submit_btn.setToolTip(tr("submit_tooltip", ul))

        self.anki_btn.setText(tr("anki_btn", ul))
        if self.is_article_view:
            self.article_btn.setText(tr("article_btn_active", ul))
            self.article_btn.setToolTip(tr("article_tooltip_active", ul))
        else:
            self.article_btn.setText(tr("article_btn", ul))
            self.article_btn.setToolTip(tr("article_tooltip", ul))

        self.ai_btn.setText(tr("ai_btn", ul))
        self.ai_btn.setToolTip(tr("ai_tooltip", ul))

        self.tip_text.setText(tr("bottom_tip", ul))

    def on_source_combo_changed(self, index: int):
        if self._updating_combos:
            return
        code = self.src_combo.currentData()
        if code and code != self.config.get("source_lang"):
            self.config.set("source_lang", code)
            query = self.input_header.line_edit.text().strip()
            if query:
                self.start_lookup(query)

    def on_target_combo_changed(self, index: int):
        if self._updating_combos:
            return
        code = self.tgt_combo.currentData()
        if code and code != self.config.get("target_lang"):
            self.config.set("target_lang", code)
            query = self.input_header.line_edit.text().strip()
            if query:
                self.start_lookup(query)

    def on_swap_langs_clicked(self):
        cur_src = self.config.get("source_lang", "en")
        cur_tgt = self.config.get("target_lang", "uk")

        if cur_src == "auto":
            new_src = cur_tgt
            new_tgt = "uk" if new_src != "uk" else "en"
        else:
            new_src = cur_tgt
            new_tgt = cur_src if cur_src in SUPPORTED_TARGET_LANGS else "uk"

        self.config.set("source_lang", new_src)
        self.config.set("target_lang", new_tgt)

        self.sync_combos_from_config()

        query = self.input_header.line_edit.text().strip()
        if query:
            self.start_lookup(query)

    def open_settings_dialog(self):
        cur_src = self.config.get("source_lang", "en")
        cur_tgt = self.config.get("target_lang", "uk")
        cur_ui = self.config.get("ui_lang", "uk")

        dialog = LanguageSettingsDialog(cur_src, cur_tgt, cur_ui, self)
        dialog.settings_saved.connect(self.apply_settings)
        # Position centered over bubble window
        dialog.move(
            self.x() + (self.width() - dialog.width()) // 2,
            self.y() + (self.height() - dialog.height()) // 2
        )
        dialog.exec()

    def apply_settings(self, source_lang: str, target_lang: str, ui_lang: str):
        old_src = self.config.get("source_lang", "en")
        old_tgt = self.config.get("target_lang", "uk")

        self.config.set("source_lang", source_lang)
        self.config.set("target_lang", target_lang)
        self.config.set("ui_lang", ui_lang)

        self.sync_combos_from_config()
        self.retranslate_ui()
        self.ui_language_changed.emit(ui_lang)

        # If welcome screen is active, refresh it in the new UI language
        if not self.current_result:
            self.show_welcome_cloud()

        # If query is active and translation direction changed, re-translate
        query = self.input_header.line_edit.text().strip()
        if query and (old_src != source_lang or old_tgt != target_lang):
            self.start_lookup(query)

    def show_welcome_cloud(self):
        self.clear_clouds()
        ul = self.get_ui_lang()
        welcome_card = ComicCloudCard({
            "badge": tr("welcome_badge", ul),
            "title": tr("welcome_title", ul),
            "phonetic": tr("welcome_phonetic", ul),
            "terms": ["devoted", "faithful", "hound", "strike", "clan"],
            "details": [
                tr("welcome_detail_1", ul),
                tr("welcome_detail_2", ul),
                tr("welcome_detail_3", ul)
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

        ul = self.get_ui_lang()
        sl = self.config.get("source_lang", "en")
        tl = self.config.get("target_lang", "uk")

        self.status_lbl.setText(tr("translating_status", ul, query=query))
        self.status_lbl.show()

        self.active_lookup_thread = LookupThread(
            self.dict_service,
            query,
            source_lang=sl,
            target_lang=tl,
            ui_lang=ul
        )
        self.active_lookup_thread.result_ready.connect(self.display_results)
        self.active_lookup_thread.start()

    def display_results(self, result: dict):
        self.status_lbl.hide()
        self.clear_clouds()
        self.current_result = result
        ul = self.get_ui_lang()

        phonetic = result.get("phonetic", "")
        if phonetic:
            clean_ph = phonetic.strip("[]/ ")
            self.phonetic_top_lbl.setText(f"/{clean_ph}/")
        else:
            self.phonetic_top_lbl.setText("")

        clouds = result.get("clouds", [])
        query = result.get("query", "")
        words = query.split()

        self.is_article_view = False
        self.article_btn.setText(tr("article_btn", ul))
        self.article_btn.setToolTip(tr("article_tooltip", ul))
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

        if len(words) in (1, 2) and clouds:
            self.article_btn.show()
        else:
            self.article_btn.hide()

        if not clouds:
            self.anki_btn.hide()
            self.article_btn.hide()
            no_res_card = ComicCloudCard({
                "badge": tr("not_found_badge", ul),
                "title": result.get("query", ""),
                "details": [tr("not_found_details", ul)]
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

        ul = self.get_ui_lang()
        if self.is_article_view:
            # Toggle back to normal translation view
            self.display_results(self.current_result)
            return

        # Switch to article view
        query = self.current_result.get("query", "")
        self.is_article_view = True
        self.article_btn.setText(tr("article_btn_active", ul))
        self.article_btn.setToolTip(tr("article_tooltip_active", ul))
        self.article_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #000000;
                border: 1px solid #F59E0B;
                border-radius: 6px;
                padding: 0 10px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #FBBF24;
            }
        """)

        sl = self.config.get("source_lang", "en")
        tl = self.config.get("target_lang", "uk")
        article = self.dict_service.get_word_article(query, source_lang=sl, target_lang=tl, ui_lang=ul)
        self.clear_clouds()
        cards = article.get("cards", [])
        if not cards:
            no_card = ComicCloudCard({
                "badge": tr("article_not_found_badge", ul),
                "title": query,
                "details": [tr("article_not_found_details", ul)]
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
        ul = self.get_ui_lang()
        self.toast_banner.setText(tr("copied_toast", ul, text=text))
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
        saved_w = self.config.get("window_width", 500)
        saved_h = self.config.get("window_height", 580)
        self.resize(max(440, saved_w), max(400, saved_h))
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

    def showEvent(self, event):
        super().showEvent(event)
        self.retranslate_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() >= 420 and self.height() >= 380:
            self.config.set("window_width", self.width())
            self.config.set("window_height", self.height())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bubble()
        else:
            super().keyPressEvent(event)
