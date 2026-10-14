"""
Master Downloader & Telegram Cloud Relay Entrypoint.
Streams manhwa chapters directly between Telegram channels in RAM.
"""

import sys
from pathlib import Path

# Ensure master_downloader folder is on sys.path
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tg_cloud_relay import main

if __name__ == "__main__":
    main()
