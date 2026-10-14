"""
Forwarder to manhwa_reader/master_downloader/tg_cloud_relay.py
"""
import sys
from pathlib import Path

module_dir = Path(__file__).parent / "master_downloader"
if str(module_dir) not in sys.path:
    sys.path.insert(0, str(module_dir))

from tg_cloud_relay import *
from tg_cloud_relay import main

if __name__ == "__main__":
    main()
