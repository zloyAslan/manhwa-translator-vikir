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
import genanki

DECKS_DIR = Path(__file__).parent / "anki_decks"
DECKS_DIR.mkdir(exist_ok=True)
APKG_FILE = DECKS_DIR / "angl_manhwa.apkg"
CSV_FILE = DECKS_DIR / "anki_cards.csv"
DB_PATH = Path(__file__).parent / "cache.db"

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
.panel-img {
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
    ],
    templates=[
        {
            'name': 'Манхва Картка',
            'qfmt': '''
                <div class="word">{{Слово}}</div>
                <hr id="divider" style="border: 1px solid #334155; margin: 12px 0;">
                {{#Речення}}<div class="sentence">{{Речення}}</div>{{/Речення}}
            ''',
            'afmt': '''
                {{FrontSide}}
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
            return False, "Помилка: Слово або переклад порожні"

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

        # 2. Direct AnkiConnect
        anki_url = self.find_ankiconnect_url()
        ankiconnect_success = False

        if anki_url:
            ankiconnect_success = self._send_to_ankiconnect(anki_url, word, sentence, translation, image_bytes, image_filename)

        if ankiconnect_success:
            return True, f"✓ Додано прямо в Anki в колоду '{self.deck_name}'!"
        else:
            return False, "⚠️ Anki не відкрито! Запустіть Anki (з AnkiConnect)."

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

    def sync_model_template(self, url: str):
        try:
            payload = {
                "action": "updateModelTemplates",
                "version": 6,
                "params": {
                    "model": {
                        "name": "Манхва Словник",
                        "templates": {
                            "Card 1": {
                                "Front": '<div style="font-size: 32px; font-weight: bold; color: #2dd4bf; text-align: center;">{{Слово}}</div><hr id=divider style="border: 1px solid #334155; margin: 14px 0;">{{#Речення}}<div style="font-size: 17px; color: #94a3b8; font-style: italic; text-align: center;">{{Речення}}</div>{{/Речення}}',
                                "Back": '{{FrontSide}}<hr id=answer style="border: 1px dashed #475569; margin: 16px 0;"><div style="font-size: 26px; font-weight: bold; color: #ffffff; text-align: center;">{{Переклад}}</div>'
                            }
                        }
                    }
                }
            }
            requests.post(url, json=payload, timeout=1.0)
            requests.post(url, json={
                "action": "updateModelStyling",
                "version": 6,
                "params": {
                    "model": {
                        "name": "Манхва Словник",
                        "css": ANKI_CARD_CSS
                    }
                }
            }, timeout=1.0)
        except Exception:
            pass

    def _send_to_ankiconnect(self, url: str, word: str, sentence: str, translation: str, image_bytes: Optional[bytes], image_filename: str) -> bool:
        try:
            self.sync_model_template(url)
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

            # Build fields
            final_translation = translation
            if image_filename:
                final_translation += f'<br><div style="text-align: center;"><img class="panel-img" src="{image_filename}"></div>'

            payload = {
                "action": "addNote",
                "version": 6,
                "params": {
                    "note": {
                        "deckName": self.deck_name,
                        "modelName": "Манхва Словник",
                        "fields": {
                            "Слово": word,
                            "Речення": sentence,
                            "Переклад": final_translation
                        },
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
                if img_path and os.path.exists(img_path):
                    fname = os.path.basename(img_path)
                    media_files.append(img_path)
                    final_trans += f'<br><div style="text-align: center;"><img class="panel-img" src="{fname}"></div>'

                note = genanki.Note(
                    model=MANHWA_MODEL,
                    fields=[word_clean, sent_clean, final_trans]
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
