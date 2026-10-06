"""
Configuration manager for Manhwa Translator Overlay.
Saves and loads settings such as mascot coordinates, style, hotkeys, and opacity.
"""

import json
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "pos_x": 100,
    "pos_y": 200,
    "mascot_style": "sticker",  # 'sticker', 'badge', 'character', 'avatar'
    "mascot_size": 95,
    "bubble_opacity": 0.98,
    "mascot_opacity": 1.0,
    "pinned": False,
    "hotkey": "alt+q",
    "auto_paste_clipboard": True,
    "play_sound": False,
    "theme": "comic_light",  # 'comic_light', 'comic_dark'
    "gemini_api_key": "AQ.Ab8RN6JameZCI5KID03P781w8vgYtkJDi-5VMfBCOuI5zq7o6g",
}

class Config:
    def __init__(self, filepath: Path = CONFIG_FILE):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    return cfg
            except Exception as e:
                print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()
