from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFrame, QGraphicsDropShadowEffect, QTabWidget,
    QWidget, QComboBox
)
from config import config
from anki_service import SlovakAnkiService

class SlovakSettingsDialog(QDialog):
    """
    Повноцінне діалогове вікно налаштувань у фірмовому стилі Dark Fantasy з вкладками:
    - [🇸🇰 Мови]: Фіксований напрямок Словацька -> Українська, DeepLX Endpoint
    - [🤖 ШІ Gemini]: API Ключ (з кнопкою приховати/показати 👁), вибір моделі Gemini
    - [⭐ Anki]: Назва колоди (за замовчуванням 'словацька новели'), перевірка зв'язку
    - [📖 Довідка]: Підказка по гарячих клавішах (Alt+Q, Alt+W, Alt+A, Alt+S)
    """
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.anki_service = SlovakAnkiService()
        self.drag_start_pos = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 500)
        self.init_ui()
        self.test_anki_connection(initial=True)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Контейнер Dark Fantasy
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

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # 1. Верхній бар
        header = QHBoxLayout()
        title_lbl = QLabel("⚙ Налаштування Словацького Перекладача")
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
        layout.addLayout(header)

        # 2. Вкладки QTabWidget
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

        input_style = """
            QLineEdit {
                background-color: #121622;
                color: #F3F4F6;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 6px 10px;
                font-weight: 600;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #F59E0B;
            }
        """
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
        lbl_style = "color: #CBD5E1; font-size: 11px; font-weight: 700; background: transparent; border: none;"

        # --- TAB 1: Мови та Рушії ---
        tab_lang = QWidget()
        tl_layout = QVBoxLayout(tab_lang)
        tl_layout.setContentsMargins(6, 6, 6, 6)
        tl_layout.setSpacing(8)

        lbl_dir = QLabel("Напрямок перекладу:")
        lbl_dir.setStyleSheet(lbl_style)
        tl_layout.addWidget(lbl_dir)

        dir_badge = QLabel("🇸🇰 Словацька (SK) ➔ 🇺🇦 Українська (UK)")
        dir_badge.setFont(QFont("Segoe UI Black", 9))
        dir_badge.setStyleSheet("""
            background-color: #121622;
            color: #2DD4BF;
            border: 1px solid rgba(45, 212, 191, 0.35);
            border-radius: 6px;
            padding: 7px 10px;
        """)
        tl_layout.addWidget(dir_badge)

        lbl_deepl = QLabel("DeepLX Endpoint (URL локального сервера):")
        lbl_deepl.setStyleSheet(lbl_style)
        tl_layout.addWidget(lbl_deepl)

        self.deepl_edit = QLineEdit(config.get("deeplx_endpoint", "http://127.0.0.1:1188/translate"))
        self.deepl_edit.setStyleSheet(input_style)
        tl_layout.addWidget(self.deepl_edit)

        # Налаштування озвучки (TTS)
        lbl_tts = QLabel("Рушій озвучки (Словацька вимова):")
        lbl_tts.setStyleSheet(lbl_style)
        tl_layout.addWidget(lbl_tts)

        self.tts_engine_combo = QComboBox()
        self.tts_engine_combo.setStyleSheet(combo_style)
        self.tts_engine_combo.addItem("✨ Microsoft Azure Neural (Viktoria - чітка студійна вимова)", "edge")
        self.tts_engine_combo.addItem("🌐 Google Translate TTS (Резервний онлайн-голос)", "google")
        current_engine = config.get("tts_engine", "edge")
        idx = self.tts_engine_combo.findData(current_engine)
        if idx >= 0:
            self.tts_engine_combo.setCurrentIndex(idx)
        tl_layout.addWidget(self.tts_engine_combo)

        lbl_speed = QLabel("Швидкість озвучки:")
        lbl_speed.setStyleSheet(lbl_style)
        tl_layout.addWidget(lbl_speed)

        self.tts_speed_combo = QComboBox()
        self.tts_speed_combo.setStyleSheet(combo_style)
        self.tts_speed_combo.addItem("🐢 Повільніше (-25% для ретельного вивчення звуків)", "-25%")
        self.tts_speed_combo.addItem("👌 Комфортно (-15% чіткий помірний темп)", "-15%")
        self.tts_speed_combo.addItem("⚡ Звичайна (100% природна розмовна)", "+0%")
        current_speed = config.get("tts_speed", "-15%")
        s_idx = self.tts_speed_combo.findData(current_speed)
        if s_idx >= 0:
            self.tts_speed_combo.setCurrentIndex(s_idx)
        tl_layout.addWidget(self.tts_speed_combo)

        tl_layout.addStretch()
        self.tab_widget.addTab(tab_lang, "🇸🇰 Мови та Озвучка")

        # --- TAB 2: ШІ Gemini ---
        tab_ai = QWidget()
        tai_layout = QVBoxLayout(tab_ai)
        tai_layout.setContentsMargins(6, 6, 6, 6)
        tai_layout.setSpacing(8)

        lbl_key = QLabel("Google Gemini API Ключ:")
        lbl_key.setStyleSheet(lbl_style)
        tai_layout.addWidget(lbl_key)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self.key_edit = QLineEdit(config.get("gemini_api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setStyleSheet(input_style)
        key_row.addWidget(self.key_edit, stretch=1)

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
                border-color: #F59E0B;
            }
        """)
        self.toggle_key_btn.clicked.connect(self.toggle_key_visibility)
        key_row.addWidget(self.toggle_key_btn)
        tai_layout.addLayout(key_row)

        lbl_model = QLabel("Модель Gemini:")
        lbl_model.setStyleSheet(lbl_style)
        tai_layout.addWidget(lbl_model)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.setStyleSheet(combo_style)
        self.ai_model_combo.addItem("gemini-flash-lite-latest (швидка, економна)", "gemini-flash-lite-latest")
        self.ai_model_combo.addItem("gemini-flash-latest (стандартна)", "gemini-flash-latest")
        self.ai_model_combo.addItem("gemini-3.1-flash-lite (нове покоління 3.1)", "gemini-3.1-flash-lite")
        cur_m = config.get("gemini_model", "gemini-flash-lite-latest")
        m_idx = self.ai_model_combo.findData(cur_m)
        if m_idx >= 0:
            self.ai_model_combo.setCurrentIndex(m_idx)
        tai_layout.addWidget(self.ai_model_combo)

        tai_layout.addStretch()
        self.tab_widget.addTab(tab_ai, "🤖 ШІ Gemini")

        # --- TAB 3: Anki Connect ---
        tab_anki = QWidget()
        tanki_layout = QVBoxLayout(tab_anki)
        tanki_layout.setContentsMargins(6, 6, 6, 6)
        tanki_layout.setSpacing(8)

        lbl_deck = QLabel("Назва колоди Anki:")
        lbl_deck.setStyleSheet(lbl_style)
        tanki_layout.addWidget(lbl_deck)

        self.deck_edit = QLineEdit(config.get("anki_deck", "словацька новели"))
        self.deck_edit.setStyleSheet(input_style)
        tanki_layout.addWidget(self.deck_edit)

        lbl_status = QLabel("Статус зв'язку з AnkiConnect:")
        lbl_status.setStyleSheet(lbl_style)
        tanki_layout.addWidget(lbl_status)

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

        test_btn = QPushButton("🔄 Перевірити з'єднання (порти 8766/8765)")
        test_btn.setFont(QFont("Segoe UI Black", 8))
        test_btn.setFixedHeight(28)
        test_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        test_btn.setStyleSheet("""
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
        test_btn.clicked.connect(lambda: self.test_anki_connection(initial=False))
        tanki_layout.addWidget(test_btn)

        tanki_layout.addStretch()
        self.tab_widget.addTab(tab_anki, "⭐ Anki")

        # --- TAB 4: Довідка ---
        tab_help = QWidget()
        thelp_layout = QVBoxLayout(tab_help)
        thelp_layout.setContentsMargins(6, 6, 6, 6)
        thelp_layout.setSpacing(10)

        help_text = QLabel(
            "<b>Slovak Novel Translator — Гарячі клавіші:</b><br><br>"
            "• <b>Alt+Q</b> — відкрити / сховати хмаринку або перекласти виділене слово.<br>"
            "• <b>Alt+W</b> — виділіть речення в читалці й натисніть Alt+W, щоб додати його як контекст в Anki.<br>"
            "• <b>Alt+A</b> — запитати у ШІ Gemini аналіз виділеного речення чи сленгу.<br>"
            "• <b>Alt+S</b> — відкрити чисте вікно створення Anki картки.<br>"
            "• <b>Подвійний клік</b> — виділити слово для швидкого перегляду."
        )
        help_text.setFont(QFont("Segoe UI", 9))
        help_text.setStyleSheet("color: #94A3B8; background: transparent; line-height: 1.5;")
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_text.setWordWrap(True)
        thelp_layout.addWidget(help_text)
        thelp_layout.addStretch()
        self.tab_widget.addTab(tab_help, "📖 Довідка")

        layout.addWidget(self.tab_widget)

        # 3. Нижні кнопки Зберегти / Скасувати
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        cancel_btn = QPushButton("Скасувати")
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

        save_btn = QPushButton("Зберегти налаштування")
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
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        main_layout.addWidget(frame)

    def toggle_key_visibility(self):
        if self.key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("🔒")
        else:
            self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("👁")

    def test_anki_connection(self, initial: bool = False):
        connected = self.anki_service.is_connected()
        port = config.get("anki_port", 8766)
        if connected:
            self.anki_status_badge.setText(f"✓ Підключено (порт {port}) • Anki доступний")
            self.anki_status_badge.setStyleSheet("""
                background-color: rgba(16, 185, 129, 0.15);
                color: #34D399;
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
            """)
        else:
            self.anki_status_badge.setText("❌ Anki не знайдено (перевірте AnkiConnect)")
            self.anki_status_badge.setStyleSheet("""
                background-color: rgba(239, 68, 68, 0.15);
                color: #F87171;
                border: 1px solid rgba(239, 68, 68, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
            """)

    def save_settings(self):
        config.set("anki_deck", self.deck_edit.text().strip() or "словацька новели")
        config.set("gemini_api_key", self.key_edit.text().strip())
        config.set("gemini_model", self.ai_model_combo.currentData())
        config.set("deeplx_endpoint", self.deepl_edit.text().strip())
        config.set("tts_engine", self.tts_engine_combo.currentData())
        config.set("tts_speed", self.tts_speed_combo.currentData())
        self.settings_saved.emit()
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
