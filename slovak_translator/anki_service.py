import requests
from typing import Dict, Any, List, Optional
from config import config

class SlovakAnkiService:
    def __init__(self):
        self.ports = [8766, 8765]

    @property
    def deck_name(self) -> str:
        return config.get("anki_deck", "словацька новели")

    def _invoke(self, action: str, **params) -> Dict[str, Any]:
        preferred_port = config.get("anki_port", 8766)
        active_ports = [preferred_port] + [p for p in self.ports if p != preferred_port]

        last_error = None
        for port in active_ports:
            try:
                response = requests.post(
                    f"http://localhost:{port}",
                    json={"action": action, "version": 6, "params": params},
                    timeout=2.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if len(data) == 2 and "error" in data and "result" in data:
                        if data["error"]:
                            raise Exception(data["error"])
                        config.set("anki_port", port)
                        return data["result"]
            except Exception as e:
                last_error = e

        raise ConnectionError(f"Не вдалося підключитися до AnkiConnect: {last_error}")

    def is_connected(self) -> bool:
        try:
            self._invoke("version")
            return True
        except Exception:
            return False

    def get_deck_names(self) -> List[str]:
        try:
            return self._invoke("deckNames") or []
        except Exception:
            return []

    def create_deck(self, deck_name: str) -> bool:
        try:
            self._invoke("createDeck", deck=deck_name)
            return True
        except Exception:
            return False

    def add_card(self, word: str, translation: str, sentence: str = "") -> bool:
        deck = self.deck_name
        decks = self.get_deck_names()
        if deck not in decks:
            self.create_deck(deck)

        # Фонетична транскрипція
        ipa_str = ""
        try:
            from tts_service import get_slovak_ipa
            ipa_str = get_slovak_ipa(word)
        except Exception:
            pass

        # Формуємо красиву картку
        # Front: Слово + IPA транскрипція + Контекстне речення з виділенням слова
        front_html = f"<div style='font-size: 22px; font-weight: bold; color: #2DD4BF; margin-bottom: 4px;'>{word}</div>"
        if ipa_str:
            front_html += f"<div style='font-size: 13px; font-style: italic; color: #94A3B8; margin-bottom: 8px;'>{ipa_str}</div>"
        if sentence:
            highlighted = sentence
            front_html += f"<div style='font-size: 15px; font-style: italic; color: #E2E8F0; border-left: 3px solid #F59E0B; padding-left: 8px; margin-top: 6px;'>{highlighted}</div>"

        back_html = f"<div style='font-size: 18px; color: #F8FAFC;'>{translation}</div>"

        note = {
            "deckName": deck,
            "modelName": "Basic",
            "fields": {
                "Front": front_html,
                "Back": back_html
            },
            "tags": ["slovak_novels"]
        }

        try:
            res = self._invoke("addNote", note=note)
            return bool(res)
        except Exception as e:
            # Спробуємо зберегти якщо модель інша або дефолтна
            try:
                models = self._invoke("modelNames") or []
                if models:
                    note["modelName"] = models[0]
                    model_fields = self._invoke("modelFieldNames", modelName=models[0]) or []
                    if len(model_fields) >= 2:
                        note["fields"] = {
                            model_fields[0]: front_html,
                            model_fields[1]: back_html
                        }
                        res = self._invoke("addNote", note=note)
                        return bool(res)
            except Exception:
                pass
            raise e
