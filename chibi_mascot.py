"""
Floating M_Translate Mascot Widget for Manhwa Overlay.
Provides:
- Vector Neon Logo Badge default mode (interlocking 文 and A with amber aura)
- Hover and breathing animations
- Backward compatibility for ChibiMascot class alias
- Modernized context menu
"""

from pathlib import Path
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QPixmap, QCursor, QColor, QAction, QFont, QPainter
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QMenu, QGraphicsDropShadowEffect, QApplication
)
import win32con
import win32gui

from config import Config
from localization import tr
from mascot_badge import VectorMascotBadge, paint_mtranslate_logo

ASSETS_DIR = Path(__file__).parent


class ChibiMascot(VectorMascotBadge):
    """
    Main Floating Mascot Widget.
    Inherits from VectorMascotBadge to directly present the new M_Translate Vector Neon Logo,
    while maintaining all signal contracts and backwards compatibility.
    """
    def __init__(self, config: Config, parent=None):
        super().__init__(config, parent)
