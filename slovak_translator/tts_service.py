"""
Офлайн та онлайн модуль синтезу словацького мовлення (TTS) для Slovak Novel Translator.
Рушії:
1. Microsoft Azure Neural (ViktoriaNeural / LukasNeural) через edge-tts:
   - Максимально чітка дикція, ідеальні наголоси, плавний темп (за замовчуванням -15% для комфортного вивчення).
2. Локальний нейро-рушій Piper (голос Lili) з налаштуванням швидкості length_scale=1.35.
3. Резерв: Google Translate TTS API.
"""

import os
import re
import sys
import wave
import shutil
import pathlib
import hashlib
import asyncio
import threading
import winsound
import urllib.request
import urllib.parse
from typing import Optional
from config import config

MODULES_DIR = pathlib.Path(__file__).parent / "models"
LOCAL_APP_DATA = pathlib.Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "slovak_translator_tts"
LOCAL_APP_DATA.mkdir(parents=True, exist_ok=True)

# Правила транскрипції для словацької мови (IPA)
SLOVAK_PHONETIC_RULES = [
    ("dž", "d͡ʒ"), ("dz", "d͡z"), ("ch", "x"),
    ("ia", "i̯a"), ("ie", "i̯e"), ("iu", "i̯u"),
    ("ô", "u̯o"), ("ä", "ɛ"),
    ("ď", "ɟ"), ("ť", "c"), ("ň", "ɲ"), ("ľ", "ʎ"),
    ("š", "ʃ"), ("č", "t͡ʃ"), ("ž", "ʒ"),
    ("c", "t͡s"), ("h", "ɦ"), ("x", "ks"),
    ("á", "aː"), ("é", "eː"), ("í", "iː"), ("ý", "iː"),
    ("ó", "oː"), ("ú", "uː"), ("ŕ", "r̩ː"), ("ĺ", "l̩ː"),
    ("y", "i")
]

def get_slovak_ipa(text: str) -> str:
    """Генерує фонетичну IPA транскрипцію для словацького слова."""
    clean = text.strip()
    if not clean or len(clean.split()) > 4:
        return ""
    w = clean.lower()
    for src, dst in SLOVAK_PHONETIC_RULES:
        w = w.replace(src, dst)
    return f"[{w}]"


class SlovakTTSService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.audio_cache_dir = LOCAL_APP_DATA / "audio_cache"
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def synthesize_to_file(self, text: str) -> Optional[pathlib.Path]:
        """Синтезує аудіо словацької вимови у файл."""
        clean_text = text.strip()
        if not clean_text:
            return None

        engine = config.get("tts_engine", "edge")
        rate = config.get("tts_speed", "-15%")

        text_hash = hashlib.md5(f"{clean_text.lower()}_{engine}_{rate}".encode("utf-8")).hexdigest()
        out_audio = self.audio_cache_dir / f"sk_{text_hash}.mp3"
        out_wav = self.audio_cache_dir / f"sk_{text_hash}.wav"

        if out_audio.exists() and out_audio.stat().st_size > 500:
            return out_audio
        if out_wav.exists() and out_wav.stat().st_size > 500:
            return out_wav

        # 1. Пріоритет: Microsoft Azure Neural (sk-SK-ViktoriaNeural) — ідеальна дикція
        if engine == "edge" or engine != "google":
            try:
                import edge_tts
                async def _gen():
                    comm = edge_tts.Communicate(clean_text, voice="sk-SK-ViktoriaNeural", rate=rate)
                    await comm.save(str(out_audio))
                asyncio.run(_gen())
                if out_audio.exists() and out_audio.stat().st_size > 500:
                    return out_audio
            except Exception:
                pass

        # 3. Резервний синтез Google Translate TTS
        try:
            encoded_q = urllib.parse.quote(clean_text)
            url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_q}&tl=sk&client=tw-ob"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = resp.read()
                if len(data) > 500:
                    with open(out_audio, "wb") as f:
                        f.write(data)
                    return out_audio
        except Exception:
            pass

        return None

    def speak(self, text: str):
        """Програє вимову у фоновому потоці без підвисання інтерфейсу."""
        def _worker():
            audio_path = self.synthesize_to_file(text)
            if audio_path and audio_path.exists():
                try:
                    if audio_path.suffix.lower() == ".wav":
                        winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
                    else:
                        # Програвання mp3 через Windows Multimedia API
                        import ctypes
                        winmm = ctypes.windll.winmm
                        alias = f"sk_tts_{threading.get_ident()}"
                        safe_path = str(audio_path).replace("\\", "/")
                        winmm.mciSendStringW(f'open "{safe_path}" type mpegvideo alias {alias}', None, 0, 0)
                        winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
                        winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                except Exception:
                    pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
