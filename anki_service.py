"""
Anki Service for Manhwa Translator.
Features:
- Direct sync to desktop Anki via AnkiConnect (ports 8766 and 8765)
- Deck: "англ манхва", Model: "Манхва Словник"
- Fields: "Слово", "Речення", "Переклад"
- Support for image panel attachments (Alt+D) with visual memory
- Automatic generation of .apkg deck files for phone/PC
"""

import os
import base64
import time
import sqlite3
import requests
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import sys
import genanki
from config import config
from localization import tr

if getattr(sys, "frozen", False):
    _APP_BASE = Path(sys.executable).parent.resolve()
else:
    _APP_BASE = Path(__file__).parent.resolve()

DECKS_DIR = _APP_BASE / "anki_decks"
APKG_FILE = DECKS_DIR / "angl_manhwa.apkg"
CSV_FILE = DECKS_DIR / "anki_cards.csv"
DB_PATH = _APP_BASE / "cache.db"

ANKI_PORTS = [8766, 8765]

MODEL_ID = 1684920194
DECK_ID = 2085930281

ANKI_CARD_CSS = """
.card {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 20px;
    text-align: center;
    color: #f3f4f6;
    background-color: #0b0e14;
    padding: 24px;
}
.word {
    font-size: 32px;
    font-weight: 800;
    color: #2dd4bf;
    margin-bottom: 8px;
}
.sentence {
    font-size: 16px;
    font-style: italic;
    color: #94a3b8;
    margin-top: 10px;
    margin-bottom: 14px;
}
.translation {
    font-size: 24px;
    font-weight: 800;
    color: #ffffff;
    margin-top: 14px;
}
.panel-img, .art img {
    max-height: 280px;
    border-radius: 8px;
    border: 1px solid #334155;
    margin-top: 14px;
}
"""

MANHWA_MODEL = genanki.Model(
    MODEL_ID,
    'Манхва Словник',
    fields=[
        {'name': 'Слово'},
        {'name': 'Речення'},
        {'name': 'Переклад'},
        {'name': 'Арт'},
    ],
    templates=[
        {
            'name': 'Манхва Картка',
            'qfmt': '''
                <div class="word">{{Слово}}</div>
                <hr id="divider" style="border: 1px solid #334155; margin: 12px 0;">
                {{#Речення}}<div class="sentence">{{Речення}}</div>{{/Речення}}
                {{#Арт}}<div class="art" style="margin-top: 12px; text-align: center;">{{Арт}}</div>{{/Арт}}
            ''',
            'afmt': '''
                {{FrontSide}}
                <hr id="answer" style="border: 1px dashed #475569; margin: 16px 0;">
                <div class="translation">{{Переклад}}</div>
            ''',
        },
    ],
    css=ANKI_CARD_CSS
)


class AnkiService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.deck_name = "англ манхва"
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS anki_cards (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word TEXT UNIQUE,
                        sentence TEXT,
                        translation TEXT,
                        image_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(anki_cards)")
                existing_cols = [row[1] for row in cursor.fetchall()]
                if "sentence" not in existing_cols:
                    conn.execute("ALTER TABLE anki_cards ADD COLUMN sentence TEXT")
                if "image_path" not in existing_cols:
                    conn.execute("ALTER TABLE anki_cards ADD COLUMN image_path TEXT")
                conn.commit()
        except Exception as e:
            print(f"Anki DB Init Error: {e}")

    def find_ankiconnect_url(self) -> Optional[str]:
        """Detects whether AnkiConnect is listening on port 8766 or 8765."""
        for port in ANKI_PORTS:
            url = f"http://127.0.0.1:{port}"
            try:
                resp = requests.post(url, json={"action": "version", "version": 6}, timeout=0.4)
                if resp.status_code == 200 and resp.json().get("result"):
                    return url
            except Exception:
                continue
        return None

    def add_card(self, word: str, translation: str, sentence: str = "", image_bytes: Optional[bytes] = None) -> Tuple[bool, str]:
        word = word.strip()
        translation = translation.strip()
        sentence = sentence.strip()
        if not word or not translation:
            return False, tr("anki_validation_error", config.ui_lang)

        image_filename = ""
        saved_img_path = ""
        if image_bytes:
            ts = int(time.time())
            image_filename = f"manhwa_{word.lower()[:10]}_{ts}.jpg"
            saved_img_path = str(DECKS_DIR / image_filename)
            try:
                with open(saved_img_path, "wb") as f:
                    f.write(image_bytes)
            except Exception as e:
                print(f"Error saving image: {e}")

        # 1. Save to SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO anki_cards (word, sentence, translation, image_path)
                    VALUES (?, ?, ?, ?)
                """, (word, sentence, translation, saved_img_path))
                conn.commit()
        except Exception as e:
            print(f"Error saving to db: {e}")

        # 2. Append to CSV
        self._append_to_csv(word, sentence, translation)

        # 3. Always update .apkg file
        self.export_apkg()

        # 4. Direct AnkiConnect sync if available
        anki_url = self.find_ankiconnect_url()
        ankiconnect_success = False

        if anki_url:
            ankiconnect_success = self._send_to_ankiconnect(anki_url, word, sentence, translation, image_bytes, image_filename)

        if ankiconnect_success:
            return True, f"✓ Додано прямо в Anki в колоду '{self.deck_name}'!"
        else:
            return True, tr("anki_saved_local_msg", config.ui_lang)

    def _append_to_csv(self, word: str, sentence: str, translation: str):
        try:
            write_header = not CSV_FILE.exists()
            with open(CSV_FILE, "a", encoding="utf-8") as f:
                if write_header:
                    f.write("Слово;Речення;Переклад\n")
                clean_s = sentence.replace("\n", " ").replace(";", ",")
                clean_t = translation.replace("\n", " ").replace(";", ",")
                f.write(f"{word};{clean_s};{clean_t}\n")
        except Exception as e:
            print(f"CSV error: {e}")

    def get_deck_names(self, url: str) -> List[str]:
        try:
            resp = requests.post(url, json={"action": "deckNames", "version": 6}, timeout=1.5)
            if resp.status_code == 200:
                return resp.json().get("result", []) or []
        except Exception as e:
            print(f"Error fetching deck names: {e}")
        return []

    def create_deck(self, url: str, deck_name: str) -> bool:
        try:
            resp = requests.post(url, json={
                "action": "createDeck",
                "version": 6,
                "params": {"deck": deck_name}
            }, timeout=2.0)
            if resp.status_code == 200 and resp.json().get("error") is None:
                self.ensure_or_create_model(url)
                return True
        except Exception as e:
            print(f"Error creating deck {deck_name}: {e}")
        return False

    def get_model_names(self, url: str) -> List[str]:
        try:
            resp = requests.post(url, json={"action": "modelNames", "version": 6}, timeout=1.5)
            if resp.status_code == 200:
                return resp.json().get("result", []) or []
        except Exception as e:
            print(f"Error fetching model names: {e}")
        return []

    def get_deck_models(self, url: str, deck_name: str) -> List[str]:
        try:
            resp = requests.post(url, json={
                "action": "findNotes",
                "version": 6,
                "params": {"query": f'deck:"{deck_name}"'}
            }, timeout=2.0)
            if resp.status_code == 200:
                note_ids = resp.json().get("result", []) or []
                if note_ids:
                    info_resp = requests.post(url, json={
                        "action": "notesInfo",
                        "version": 6,
                        "params": {"notes": note_ids[:5]}
                    }, timeout=2.0)
                    if info_resp.status_code == 200:
                        info_data = info_resp.json().get("result", []) or []
                        return list({n.get("modelName") for n in info_data if n.get("modelName")})
        except Exception as e:
            print(f"Error checking deck models: {e}")
        return []

    def ensure_or_create_model(self, url: str, model_name: str = "Манхва Словник") -> bool:
        """
        Ensures the custom Dark Fantasy layout exists:
        Front: Слово, Речення, Арт
        Back: Переклад
        """
        front_tpl = (
            '<div class="word">{{Слово}}</div>'
            '<hr id="divider" style="border: 1px solid #334155; margin: 12px 0;">'
            '{{#Речення}}<div class="sentence">{{Речення}}</div>{{/Речення}}'
            '{{#Арт}}<div class="art" style="margin-top: 12px; text-align: center;">{{Арт}}</div>{{/Арт}}'
        )
        back_tpl = (
            '{{FrontSide}}'
            '<hr id="answer" style="border: 1px dashed #475569; margin: 16px 0;">'
            '<div class="translation">{{Переклад}}</div>'
        )

        models = self.get_model_names(url)
        if model_name not in models:
            try:
                resp = requests.post(url, json={
                    "action": "createModel",
                    "version": 6,
                    "params": {
                        "modelName": model_name,
                        "inOrderFields": ["Слово", "Речення", "Переклад", "Арт"],
                        "css": ANKI_CARD_CSS,
                        "cardTemplates": [
                            {
                                "Name": "Манхва Картка",
                                "Front": front_tpl,
                                "Back": back_tpl
                            }
                        ]
                    }
                }, timeout=2.0)
                if resp.status_code == 200 and resp.json().get("error") is None:
                    return True
            except Exception as e:
                print(f"Error creating model {model_name}: {e}")

        # Model exists: ensure fields, templates and styling
        try:
            f_resp = requests.post(url, json={
                "action": "modelFieldNames",
                "version": 6,
                "params": {"modelName": model_name}
            }, timeout=1.5)
            if f_resp.status_code == 200:
                fields = f_resp.json().get("result", []) or []
                if "Арт" not in fields:
                    requests.post(url, json={
                        "action": "modelAddField",
                        "version": 6,
                        "params": {
                            "model": {
                                "name": model_name,
                                "fieldName": "Арт"
                            }
                        }
                    }, timeout=1.5)

            requests.post(url, json={
                "action": "updateModelTemplates",
                "version": 6,
                "params": {
                    "model": {
                        "name": model_name,
                        "templates": {
                            "Манхва Картка": {
                                "Front": front_tpl,
                                "Back": back_tpl
                            },
                            "Card 1": {
                                "Front": front_tpl,
                                "Back": back_tpl
                            }
                        }
                    }
                }
            }, timeout=1.5)

            requests.post(url, json={
                "action": "updateModelStyling",
                "version": 6,
                "params": {
                    "model": {
                        "name": model_name,
                        "css": ANKI_CARD_CSS
                    }
                }
            }, timeout=1.5)
            return True
        except Exception as e:
            print(f"Error syncing model {model_name}: {e}")
            return False

    def inspect_deck_configuration(self) -> Dict[str, Any]:
        """
        Inspects AnkiConnect reachability, deck existence, and model configuration.
        """
        url = self.find_ankiconnect_url()
        if not url:
            return {
                "connected": False,
                "url": None,
                "deck_exists": False,
                "model_matches": False,
                "deck_name": self.deck_name
            }

        decks = self.get_deck_names(url)
        deck_exists = self.deck_name in decks
        if not deck_exists:
            return {
                "connected": True,
                "url": url,
                "deck_exists": False,
                "model_matches": False,
                "deck_name": self.deck_name
            }

        deck_models = self.get_deck_models(url, self.deck_name)
        models = self.get_model_names(url)

        if deck_models:
            model_matches = ("Манхва Словник" in deck_models)
        else:
            model_matches = ("Манхва Словник" in models)

        return {
            "connected": True,
            "url": url,
            "deck_exists": True,
            "model_matches": model_matches,
            "deck_name": self.deck_name
        }

    def _send_to_ankiconnect(self, url: str, word: str, sentence: str, translation: str, image_bytes: Optional[bytes], image_filename: str) -> bool:
        try:
            self.ensure_or_create_model(url)
            if image_bytes and image_filename:
                b64_data = base64.b64encode(image_bytes).decode('ascii')
                requests.post(url, json={
                    "action": "storeMediaFile",
                    "version": 6,
                    "params": {
                        "filename": image_filename,
                        "data": b64_data
                    }
                }, timeout=2.0)

            # Check if model has 'Арт' field
            has_art_field = False
            try:
                f_resp = requests.post(url, json={
                    "action": "modelFieldNames",
                    "version": 6,
                    "params": {"modelName": "Манхва Словник"}
                }, timeout=1.0)
                if f_resp.status_code == 200:
                    fields = f_resp.json().get("result", []) or []
                    has_art_field = ("Арт" in fields)
            except Exception:
                pass

            art_tag = f'<img class="panel-img" src="{image_filename}">' if image_filename else ""
            if has_art_field:
                note_fields = {
                    "Слово": word,
                    "Речення": sentence,
                    "Переклад": translation,
                    "Арт": art_tag
                }
            else:
                final_trans = translation + (f'<br><div style="text-align: center;">{art_tag}</div>' if art_tag else "")
                note_fields = {
                    "Слово": word,
                    "Речення": sentence,
                    "Переклад": final_trans
                }

            payload = {
                "action": "addNote",
                "version": 6,
                "params": {
                    "note": {
                        "deckName": self.deck_name,
                        "modelName": "Манхва Словник",
                        "fields": note_fields,
                        "options": {
                            "allowDuplicate": True,
                            "duplicateScope": "deck"
                        },
                        "tags": ["манхва", "англійська"]
                    }
                }
            }
            resp = requests.post(url, json=payload, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("error") is None:
                    return True
                else:
                    print(f"AnkiConnect addNote error: {data.get('error')}")
        except Exception as e:
            print(f"AnkiConnect request error: {e}")
        return False

    def export_apkg(self, output_path: Path = APKG_FILE) -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT word, sentence, translation, image_path FROM anki_cards ORDER BY id DESC")
                rows = cursor.fetchall()

            deck = genanki.Deck(DECK_ID, self.deck_name)
            media_files = []

            for word, sentence, translation, img_path in rows:
                word_clean = word or ""
                sent_clean = sentence or ""
                final_trans = translation or ""
                art_tag = ""
                if img_path and os.path.exists(img_path):
                    fname = os.path.basename(img_path)
                    media_files.append(img_path)
                    art_tag = f'<img class="panel-img" src="{fname}">'

                note = genanki.Note(
                    model=MANHWA_MODEL,
                    fields=[word_clean, sent_clean, final_trans, art_tag]
                )
                deck.add_note(note)

            pkg = genanki.Package(deck)
            if media_files:
                pkg.media_files = media_files
            pkg.write_to_file(str(output_path))
            return str(output_path)
        except Exception as e:
            print(f"Error exporting apkg: {e}")
            return ""

    def get_cards_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM anki_cards")
                return cursor.fetchone()[0]
        except Exception:
            return 0
