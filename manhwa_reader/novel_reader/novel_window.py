"""
Standalone Novel & Light Novel Fullscreen Reader Window (Dark Fantasy Edition).
Features:
- Pure dark comfortable background (#090B10, #121622)
- High contrast readable white typography (#FFFFFF)
- Precise reading progress tracking down to 1 decimal place (e.g., 23.4%)
- Auto bookmarking to config.json
- Direct click / select-to-copy integration with Slovak Novel Translator
- Font size, line spacing and margin adjustments
- Clean Zen Mode (H) and Fullscreen (F11 / Esc)
"""

import sys
import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QPushButton,
    QComboBox, QSlider, QFrame, QScrollArea, QFileDialog
)

try:
    from .parsers.novel_parser import EpubParser, DocxParser
except ImportError:
    try:
        from manhwa_reader.novel_reader.parsers.novel_parser import EpubParser, DocxParser
    except ImportError:
        from novel_reader.parsers.novel_parser import EpubParser, DocxParser


class NovelTextBrowser(QTextBrowser):
    """
    Enhanced reading browser with:
    - Continuous scrolling into next / previous chapter when hitting top/bottom boundaries
    - Hotkeys W (prev chapter) and E (next chapter)
    """
    def __init__(self, owner: 'NovelReaderWindow', parent=None):
        super().__init__(parent)
        self.owner = owner
        self._boundary_cooldown = False

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_W:
            self.owner.prev_chapter()
            event.accept()
            return
        elif key == Qt.Key.Key_E:
            self.owner.next_chapter()
            event.accept()
            return
        elif key == Qt.Key.Key_H:
            self.owner.toggle_zen_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        sb = self.verticalScrollBar()
        delta = event.angleDelta().y()

        # If at the very bottom and scrolling downwards -> seamless advance to next chapter
        if delta < 0 and sb.maximum() > 0 and sb.value() >= sb.maximum():
            if not self._boundary_cooldown:
                self._boundary_cooldown = True
                QTimer.singleShot(400, lambda: setattr(self, '_boundary_cooldown', False))
                self.owner.next_chapter()
                event.accept()
                return

        # If at the very top and scrolling upwards -> seamless return to previous chapter
        elif delta > 0 and sb.value() <= 0:
            if not self._boundary_cooldown and self.owner.current_ch_index > 0:
                self._boundary_cooldown = True
                QTimer.singleShot(400, lambda: setattr(self, '_boundary_cooldown', False))
                self.owner.prev_chapter(scroll_to_bottom=True)
                event.accept()
                return

        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        cursor = self.textCursor()
        selected_text = cursor.selectedText().strip()
        if selected_text:
            import pyperclip
            pyperclip.copy(selected_text)


class NovelReaderWindow(QWidget):
    """
    Dedicated Light Novel / Web Novel Reading Window.
    Can be used standalone or embedded as a tab/page.
    """
    back_to_library_requested = pyqtSignal()
    progress_changed = pyqtSignal(str, int, float)  # novel_id, chapter_idx, percent

    def __init__(self, parent=None, t: dict = None):
        super().__init__(parent)
        self.t = t or {}
        self.novel_title = ""
        self.novel_path: Optional[Path] = None
        self.chapters: List[Dict[str, Any]] = []
        self.current_ch_index = 0
        self.font_size = 17
        self.is_zen_mode = False

        self.init_ui()

    def set_translations(self, t: dict):
        self.t = t or {}
        if hasattr(self, "back_btn"):
            self.back_btn.setText(self.t.get("to_catalog", "← Library"))
        if hasattr(self, "title_lbl") and not self.novel_title:
            self.title_lbl.setText(f"📖 {self.t.get('select_manhwa', 'Select a novel')}")
        if hasattr(self, "prev_btn"):
            self.prev_btn.setToolTip(self.t.get("prev_ch", "Previous"))
        if hasattr(self, "next_btn"):
            self.next_btn.setToolTip(self.t.get("next_ch", "Next"))
        if hasattr(self, "zen_btn"):
            self.zen_btn.setText(self.t.get("show_menu", "Показати меню (H)") if self.is_zen_mode else self.t.get("hide_menu", "Сховати меню (H)"))

    def init_ui(self):
        self.setObjectName("NovelReaderRoot")
        self.setStyleSheet("""
            QWidget#NovelReaderRoot {
                background-color: #090B10;
                color: #FFFFFF;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 16, 24, 16)
        self.main_layout.setSpacing(12)

        # 1. Top Header Toolbar
        self.toolbar = QFrame()
        self.toolbar.setStyleSheet("""
            QFrame {
                background-color: #121622;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 4px 12px;
            }
        """)
        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)
        tb_layout.setSpacing(12)

        self.back_btn = QPushButton(self.t.get("to_catalog", "← Library"))
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #F3F4F6;
                font-weight: 700;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
                border-color: #F59E0B;
                color: #FFFFFF;
            }
        """)
        self.back_btn.clicked.connect(self.back_to_library_requested.emit)
        tb_layout.addWidget(self.back_btn)

        self.title_lbl = QLabel(f"📖 {self.t.get('select_manhwa', 'Select a novel')}")
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #F59E0B;")
        tb_layout.addWidget(self.title_lbl, stretch=1)

        # Chapter selector
        self.ch_combo = QComboBox()
        self.ch_combo.setStyleSheet("""
            QComboBox {
                background-color: #0D101A;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                color: #FFFFFF;
                padding: 5px 12px;
                font-weight: 600;
                min-width: 180px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #121622;
                color: #FFFFFF;
                selection-background-color: #F59E0B;
                selection-color: #000000;
            }
        """)
        self.ch_combo.currentIndexChanged.connect(self.on_chapter_selected)
        tb_layout.addWidget(self.ch_combo)

        # Prev / Next
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip(self.t.get("prev_ch", "Previous"))
        self.prev_btn.setStyleSheet(self._btn_nav_style())
        self.prev_btn.clicked.connect(self.prev_chapter)
        tb_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip(self.t.get("next_ch", "Next"))
        self.next_btn.setStyleSheet(self._btn_nav_style())
        self.next_btn.clicked.connect(self.next_chapter)
        tb_layout.addWidget(self.next_btn)

        # Font zoom buttons
        font_dec_btn = QPushButton("A-")
        font_dec_btn.setStyleSheet(self._btn_nav_style())
        font_dec_btn.clicked.connect(self.decrease_font)
        tb_layout.addWidget(font_dec_btn)

        font_inc_btn = QPushButton("A+")
        font_inc_btn.setStyleSheet(self._btn_nav_style())
        font_inc_btn.clicked.connect(self.increase_font)
        tb_layout.addWidget(font_inc_btn)

        # Progress Pill
        self.progress_pill = QLabel("0.0%")
        self.progress_pill.setStyleSheet("""
            background-color: rgba(45, 212, 191, 0.15);
            border: 1px solid rgba(45, 212, 191, 0.4);
            color: #2DD4BF;
            font-weight: 800;
            font-size: 13px;
            padding: 4px 10px;
            border-radius: 8px;
        """)
        tb_layout.addWidget(self.progress_pill)

        # Hide Menu (Zen Mode) Button — Exactly like in manhwa reader
        self.zen_btn = QPushButton(self.t.get("hide_menu", "Сховати меню (H)"))
        self.zen_btn.setProperty("class", "btnSecondary")
        self.zen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.zen_btn.setStyleSheet("""
            QPushButton {
                background-color: #121824;
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #CBD5E1;
                font-weight: 700;
                font-size: 11px;
                border-radius: 8px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #1E293B;
                color: #FFFFFF;
                border-color: #F59E0B;
            }
        """)
        self.zen_btn.clicked.connect(self.toggle_zen_mode)
        tb_layout.addWidget(self.zen_btn)

        self.main_layout.addWidget(self.toolbar)

        # 2. Reading Text Area
        self.text_viewer = NovelTextBrowser(self)
        self.text_viewer.setOpenExternalLinks(False)
        self.text_viewer.setStyleSheet("""
            QTextBrowser {
                background-color: #090B10;
                border: none;
                padding: 10px 40px;
                selection-background-color: #F59E0B;
                selection-color: #000000;
            }
            QScrollBar:vertical {
                background: #090B10;
                width: 8px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #F59E0B;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none; background: none;
            }
        """)
        self.text_viewer.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.main_layout.addWidget(self.text_viewer, stretch=1)

    def _btn_nav_style(self) -> str:
        return """
            QPushButton {
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
                font-weight: 800;
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: #F59E0B;
            }
        """

    def load_novel(self, file_or_dir: Path, title: Optional[str] = None):
        self.novel_path = file_or_dir
        self.novel_title = title or file_or_dir.stem
        self.title_lbl.setText(f"📖 {self.novel_title}")
        self.chapters.clear()

        if file_or_dir.is_file():
            suf = file_or_dir.suffix.lower()
            if suf == ".epub":
                self.chapters = EpubParser.extract_chapters(file_or_dir)
            elif suf in [".docx", ".txt"]:
                text = DocxParser.extract_text(file_or_dir)
                # Check if this text file has embedded chapter markers === Title ===
                marker_parts = re.split(r'===\s*(.*?)\s*===\n*', text)
                if len(marker_parts) > 2:
                    self.chapters = []
                    # If there's preamble text before the first marker
                    if marker_parts[0].strip():
                        self.chapters.append({
                            "chapter": 1,
                            "title": "Prologue",
                            "content": marker_parts[0].strip()
                        })
                    for i in range(1, len(marker_parts), 2):
                        ch_title = marker_parts[i].strip()
                        ch_content = marker_parts[i+1].strip() if i+1 < len(marker_parts) else ""
                        self.chapters.append({
                            "chapter": len(self.chapters) + 1,
                            "title": ch_title,
                            "content": ch_content
                        })
                else:
                    self.chapters = [{
                        "chapter": 1,
                        "title": file_or_dir.stem,
                        "content": text
                    }]
        elif file_or_dir.is_dir():
            # Directory of chapter files (.docx, .txt, .epub) — scan recursively
            files = [
                f for f in file_or_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in [".docx", ".txt", ".epub"]
                and not any(part.startswith(".") for part in f.parts)
            ]
            files.sort(key=lambda p: p.name)
            ch_num = 1
            for f in files:
                if f.suffix.lower() == ".epub":
                    sub_chs = EpubParser.extract_chapters(f)
                    self.chapters.extend(sub_chs)
                else:
                    text = DocxParser.extract_text(f)
                    marker_parts = re.split(r'===\s*(.*?)\s*===\n*', text)
                    if len(marker_parts) > 2:
                        if marker_parts[0].strip():
                            self.chapters.append({
                                "chapter": ch_num,
                                "title": "Prologue",
                                "content": marker_parts[0].strip()
                            })
                            ch_num += 1
                        for i in range(1, len(marker_parts), 2):
                            ch_title = marker_parts[i].strip()
                            ch_content = marker_parts[i+1].strip() if i+1 < len(marker_parts) else ""
                            self.chapters.append({
                                "chapter": ch_num,
                                "title": ch_title,
                                "content": ch_content
                            })
                            ch_num += 1
                    else:
                        self.chapters.append({
                            "chapter": ch_num,
                            "title": f.stem,
                            "content": text
                        })
                        ch_num += 1

        self.ch_combo.blockSignals(True)
        self.ch_combo.clear()
        ch_prefix = self.t.get("chapter_prefix", "Chapter")
        for idx, ch in enumerate(self.chapters):
            raw_title = str(ch.get('title') or '').strip()
            # If title is empty, fallback to Chapter X
            if not raw_title:
                display_title = f"{ch_prefix} {idx+1}"
            # If title already starts with digits (e.g. '1. The Light...', '1 - ...') or special tags like 'Prologue'
            elif re.match(r'^\d+[\.\:\-\s]', raw_title) or raw_title.lower().startswith(('prologue', 'пролог', 'epilogue', 'епілог')):
                display_title = raw_title
            else:
                display_title = f"{idx+1}. {raw_title}"
            self.ch_combo.addItem(display_title, idx)
        self.ch_combo.blockSignals(False)

        if self.chapters:
            self.display_chapter(0)

    def display_chapter(self, index: int):
        if not (0 <= index < len(self.chapters)):
            return
        self.current_ch_index = index
        self.ch_combo.blockSignals(True)
        self.ch_combo.setCurrentIndex(index)
        self.ch_combo.blockSignals(False)

        ch_data = self.chapters[index]
        ch_prefix = self.t.get("chapter_prefix", "Chapter")
        title = ch_data.get("title", f"{ch_prefix} {index+1}")
        content = ch_data.get("content", "")

        # Format beautiful Dark Fantasy HTML
        html_paragraphs = "".join(f"<p style='margin-bottom: 1.2em;'>{p.strip()}</p>" for p in content.splitlines() if p.strip())
        
        full_html = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Plus Jakarta Sans', -apple-system, system-ui, sans-serif;
                font-size: {self.font_size}px;
                line-height: 1.75;
                color: #FFFFFF;
                background-color: #090B10;
                max-width: 820px;
                margin: 0 auto;
            }}
            h1 {{
                font-size: {self.font_size + 8}px;
                font-weight: 800;
                color: #F59E0B;
                margin-top: 20px;
                margin-bottom: 24px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                padding-bottom: 12px;
            }}
            p {{
                color: #FFFFFF;
                letter-spacing: 0.01em;
            }}
        </style>
        </head>
        <body>
            <h1>{title}</h1>
            {html_paragraphs}
        </body>
        </html>
        """
        self.text_viewer.setHtml(full_html)
        self.text_viewer.verticalScrollBar().setValue(0)
        self.update_progress()

    def on_chapter_selected(self, idx: int):
        if idx >= 0 and idx != self.current_ch_index:
            self.display_chapter(idx)

    def prev_chapter(self, scroll_to_bottom: bool = False):
        if self.current_ch_index > 0:
            self.display_chapter(self.current_ch_index - 1)
            if scroll_to_bottom:
                sb = self.text_viewer.verticalScrollBar()
                sb.setValue(sb.maximum())

    def next_chapter(self):
        if self.current_ch_index + 1 < len(self.chapters):
            self.display_chapter(self.current_ch_index + 1)

    def increase_font(self):
        if self.font_size < 32:
            self.font_size += 2
            self.display_chapter(self.current_ch_index)

    def decrease_font(self):
        if self.font_size > 12:
            self.font_size -= 2
            self.display_chapter(self.current_ch_index)

    def on_scroll(self):
        self.update_progress()

    def keyPressEvent(self, event):
        """Global reader hotkeys: W = Prev Chapter, E = Next Chapter."""
        key = event.key()
        if key == Qt.Key.Key_W:
            self.prev_chapter()
            event.accept()
            return
        elif key == Qt.Key.Key_E:
            self.next_chapter()
            event.accept()
            return
        elif key == Qt.Key.Key_H:
            self.toggle_zen_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def toggle_zen_mode(self):
        self.is_zen_mode = not self.is_zen_mode
        self.zen_btn.setText(self.t.get("show_menu", "Показати меню (H)") if self.is_zen_mode else self.t.get("hide_menu", "Сховати меню (H)"))
        
        # Hide parent header and navigation tabs if embedded inside ManhwaApp
        p = self.parent()
        while p is not None:
            if hasattr(p, "header_frame") and hasattr(p, "nav_frame"):
                if self.is_zen_mode:
                    p.header_frame.hide()
                    p.nav_frame.hide()
                    p.root_layout.setContentsMargins(0, 0, 0, 0)
                else:
                    p.header_frame.show()
                    p.nav_frame.show()
                    p.root_layout.setContentsMargins(24, 16, 24, 20)
                break
            p = p.parent()

    def update_progress(self):
        sb = self.text_viewer.verticalScrollBar()
        total_ch = len(self.chapters) if self.chapters else 1
        
        scroll_pct = (sb.value() / sb.maximum()) if sb.maximum() > 0 else 0.0
        # Overall progress with 1 decimal place precision
        overall_pct = ((self.current_ch_index + scroll_pct) / total_ch) * 100.0
        overall_pct = min(100.0, max(0.0, overall_pct))
        
        self.progress_pill.setText(f"{overall_pct:.1f}%")
        self.progress_changed.emit(self.novel_title, self.current_ch_index, overall_pct)
