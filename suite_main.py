"""
Integrated launcher for Manhwa Suite (Reader + M_Translate).
Runs both the Reader and M_Translate overlay in a unified process.
"""

import sys
import os
import multiprocessing
from pathlib import Path

# Add project root and manhwa_reader directory to sys.path
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "manhwa_reader"))

from PyQt6.QtWidgets import QApplication
from manhwa_reader.reader import ManhwaApp
from main import ManhwaTranslatorApp


def run_suite():
    # Setup Windows multiprocessing support if frozen
    multiprocessing.freeze_support()

    # Initialize Qt Application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 1. Initialize M_Translate overlay translator components
    # We instantiate the translator logic sharing the same event loop
    translator = ManhwaTranslatorApp()

    # 2. Initialize and display Manhwa Reader main window
    reader_win = ManhwaApp()
    reader_win.show()

    # Run the unified event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    run_suite()
