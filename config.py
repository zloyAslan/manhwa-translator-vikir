"""
Configuration manager for M_Translate Overlay Translator.
Saves and loads settings such as mascot coordinates, style, hotkeys, AI parameters, and languages.
"""

import sys
import json
from pathlib import Path
from typing import Any, Dict

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

CONFIG_FILE = APP_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "pos_x": 100,
    "pos_y": 200,
    "mascot_style": "vector_badge",  # 'vector_badge', 'sticker', 'badge', 'art'
    "mascot_size": 95,
    "bubble_opacity": 0.98,
    "mascot_opacity": 1.0,
    "pinned": False,
    "hotkey": "alt+q",
    "auto_paste_clipboard": True,
    "play_sound": False,
    "theme": "comic_light",  # 'comic_light', 'comic_dark'
    "gemini_api_key": "",
    "gemini_model": "gemini-flash-latest",
    "ai_response_lang": "uk",  # 'uk', 'ru', 'en'
    "source_lang": "en",  # 'en', 'uk', 'ru', 'auto'
    "target_lang": "uk",  # 'uk', 'en', 'ru'
    "ui_lang": "uk",      # 'uk', 'en', 'ru'
    "anki_deck": "англ манхва",
    "anki_port": 8766,
}

SUPPORTED_SOURCE_LANGS = ["en", "uk", "ru", "auto"]
SUPPORTED_TARGET_LANGS = ["uk", "en", "ru"]
SUPPORTED_UI_LANGS = ["uk", "en", "ru"]
SUPPORTED_AI_RESPONSE_LANGS = ["uk", "ru", "en"]
SUPPORTED_GEMINI_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]


class Config:
    _instance = None

    def __new__(cls, filepath: Path = CONFIG_FILE):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, filepath: Path = CONFIG_FILE):
        if getattr(self, "_initialized", False):
            return
        self.filepath = filepath
        self.data = self._load()
        self._initialized = True

    def reload(self):
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

    @property
    def ui_lang(self) -> str:
        return self.get("ui_lang", "uk")

    @property
    def source_lang(self) -> str:
        return self.get("source_lang", "en")

    @property
    def target_lang(self) -> str:
        return self.get("target_lang", "uk")

    @property
    def ai_response_lang(self) -> str:
        return self.get("ai_response_lang", "uk")

    @property
    def gemini_model(self) -> str:
        return self.get("gemini_model", "gemini-2.5-flash-lite")

    @property
    def anki_deck(self) -> str:
        return self.get("anki_deck", "англ манхва")


# Singleton instance
config = Config()
