import json
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "pos_x": 100,
    "pos_y": 100,
    "window_width": 480,
    "window_height": 560,
    "source_lang": "sk",
    "target_lang": "uk",
    "ui_lang": "uk",
    "auto_paste_clipboard": True,
    "anki_deck": "словацька новели",
    "anki_port": 8766,
    "gemini_api_key": "",
    "gemini_model": "gemini-flash-lite-latest",
    "deeplx_endpoint": "http://127.0.0.1:1188/translate",
    "tts_engine": "edge",
    "tts_speed": "-15%"
}

class SlovakConfig:
    def __init__(self):
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                    self.data.update(disk_data)
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()

config = SlovakConfig()
