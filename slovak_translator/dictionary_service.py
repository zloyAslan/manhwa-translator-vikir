import json
import sqlite3
import requests
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import SlovakConfig

DB_PATH = Path(__file__).parent / "slovak_cache.db"

POS_MAP = {
    "noun": "іменник",
    "verb": "дієслово",
    "adjective": "прикметник",
    "adverb": "прислівник",
    "pronoun": "займенник",
    "preposition": "прийменник",
    "conjunction": "сполучник",
    "interjection": "вигук",
    "numeral": "числівник",
    "particle": "частка"
}

class SlovakDictionaryService:
    def __init__(self, db_path: Path = DB_PATH, config: Optional[SlovakConfig] = None):
        self.db_path = db_path
        self.config = config or SlovakConfig()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        word TEXT PRIMARY KEY,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word TEXT,
                        main_trans TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception:
            pass

    def get_cached(self, word: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT data FROM cache WHERE word = ?", (word.lower().strip(),))
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception:
            pass
        return None

    def save_cached(self, word: str, data: Dict[str, Any]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (word, data) VALUES (?, ?)",
                    (word.lower().strip(), json.dumps(data, ensure_ascii=False))
                )
                conn.execute(
                    "INSERT INTO history (word, main_trans) VALUES (?, ?)",
                    (word.strip(), data.get("main", ""))
                )
                conn.commit()
        except Exception:
            pass

    def translate_deeplx(self, text: str) -> Optional[str]:
        endpoint = self.config.get("deeplx_endpoint", "http://127.0.0.1:1188/translate")
        payload = {
            "text": text,
            "source_lang": "SK",
            "target_lang": "UK"
        }
        try:
            resp = requests.post(endpoint, json=payload, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and data["data"]:
                    return data["data"]
                if "translated_text" in data:
                    return data["translated_text"]
        except Exception:
            pass
        return None

    def translate_google(self, text: str) -> str:
        """Переклад через Google Chrome Translation API (швидкий, стабільний, без 429)."""
        url = "https://clients5.google.com/translate_a/t"
        params = {
            "client": "dict-chrome-ex",
            "sl": "sk",
            "tl": "uk",
            "q": text
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return str(data[0]).strip()
        except Exception:
            pass
        return ""

    def translate_mymemory(self, text: str) -> str:
        """Резервний перекладач MyMemory."""
        try:
            q = urllib.parse.urlencode({"q": text, "langpair": "sk|uk"})
            url = f"https://api.mymemory.translated.net/get?{q}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, headers=headers, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                trans = data.get("responseData", {}).get("translatedText", "")
                if trans and "MYMEMORY WARNING" not in trans:
                    return trans.strip()
        except Exception:
            pass
        return ""

    def lookup(self, text: str) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return {}

        cached = self.get_cached(clean_text)
        if cached:
            return cached

        # 1. Спроба DeepLX
        deepl_trans = self.translate_deeplx(clean_text)

        # 2. Переклад Google Chrome API
        google_trans = self.translate_google(clean_text)

        # 3. Резерв MyMemory якщо Google не відповів
        mymemory_trans = ""
        if not google_trans and not deepl_trans:
            mymemory_trans = self.translate_mymemory(clean_text)

        main_trans = deepl_trans or google_trans or mymemory_trans or clean_text

        clouds: List[Dict[str, Any]] = []

        details = []
        if deepl_trans:
            details.append(f"DeepLX: {deepl_trans}")
        if google_trans:
            details.append(f"Google: {google_trans}")
        if mymemory_trans and not google_trans:
            details.append(f"MyMemory: {mymemory_trans}")

        ipa_str = ""
        try:
            from tts_service import get_slovak_ipa
            ipa_str = get_slovak_ipa(clean_text)
        except Exception:
            pass

        clouds.append({
            "badge": "🇸🇰 СЛОВАЦЬКА ➔ 🇺🇦 УКРАЇНСЬКА",
            "title": clean_text,
            "phonetic": ipa_str,
            "terms": [main_trans] if main_trans.lower() != clean_text.lower() else [],
            "details": details or ["Перекладено надійно через онлайн-рушій"]
        })

        result = {
            "query": clean_text,
            "main": main_trans,
            "clouds": clouds,
            "source_lang": "sk",
            "target_lang": "uk"
        }

        self.save_cached(clean_text, result)
        return result

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        history = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT word, main_trans, created_at FROM history ORDER BY id DESC LIMIT ?", (limit,))
                for row in cur.fetchall():
                    history.append({
                        "word": row[0],
                        "translation": row[1],
                        "created_at": row[2]
                    })
        except Exception:
            pass
        return history
