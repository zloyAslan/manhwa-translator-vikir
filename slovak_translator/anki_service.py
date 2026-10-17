import requests
from typing import Dict, Any, List, Optional
from config import config

class SlovakAnkiService:
    def __init__(self):
        self.ports = [8766, 8765]
        self._cached_decks: Optional[List[str]] = None
        self._last_deck_cache_time = 0.0

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
                    f"http://127.0.0.1:{port}",
                    json={"action": action, "version": 6, "params": params},
                    timeout=1.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and "error" in data and "result" in data:
                        if data["error"]:
                            # Це відповідь від живого Anki! Піднімаємо реальну помилку Anki
                            # і в жодному разі не йдемо на закритий порт!
                            if port != preferred_port:
                                config.set("anki_port", port)
                            err_msg = data["error"]
                            if "cannot create note because it is a duplicate" in str(err_msg).lower():
                                raise ValueError("Ця картка вже існує в Anki (дублікат)!")
                            raise RuntimeError(err_msg)
                        if port != preferred_port:
                            config.set("anki_port", port)
                        return data["result"]
            except (ValueError, RuntimeError) as e:
                # Логічні помилки самого Anki піднімаємо відразу
                raise e
            except Exception as e:
                # Мережева помилка (порт закритий / недоступний)
                last_error = e

        raise ConnectionError(f"Не вдалося підключитися до Anki: перевірте, чи запущений Anki (порт {preferred_port})")

    def is_connected(self) -> bool:
        try:
            self._invoke("version")
            return True
        except Exception:
            return False

    def get_deck_names(self, force_refresh: bool = False) -> List[str]:
        import time
        now = time.time()
        if not force_refresh and self._cached_decks is not None and (now - self._last_deck_cache_time < 30.0):
            return self._cached_decks
        try:
            decks = self._invoke("deckNames") or []
            self._cached_decks = decks
            self._last_deck_cache_time = now
            return decks
        except Exception:
            return self._cached_decks or []

    def create_deck(self, deck_name: str) -> bool:
        try:
            self._invoke("createDeck", deck=deck_name)
            self._cached_decks = None
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
        front_html = f"<div style='font-size: 22px; font-weight: bold; color: #2DD4BF; margin-bottom: 4px;'>{word}</div>"
        if ipa_str:
            front_html += f"<div style='font-size: 13px; font-style: italic; color: #94A3B8; margin-bottom: 8px;'>{ipa_str}</div>"
        if sentence:
            highlighted = sentence
            front_html += f"<div style='font-size: 15px; font-style: italic; color: #E2E8F0; border-left: 3px solid #F59E0B; padding-left: 8px; margin-top: 6px;'>{highlighted}</div>"

        back_html = f"<div style='font-size: 18px; color: #F8FAFC;'>{translation}</div>"

        # Отримуємо доступні моделі в Anki
        models = self._invoke("modelNames") or []
        chosen_model = None
        chosen_fields = []

        # Пріоритет: "Манхва Словник", "Базовий", "Basic", або перша з двома чи більше полями
        preferred_models = ["Манхва Словник", "Базовий", "Basic"]
        for pref in preferred_models:
            if pref in models:
                flds = self._invoke("modelFieldNames", modelName=pref) or []
                if flds:
                    chosen_model = pref
                    chosen_fields = flds
                    break

        if not chosen_model and models:
            for m in models:
                flds = self._invoke("modelFieldNames", modelName=m) or []
                if len(flds) >= 2:
                    chosen_model = m
                    chosen_fields = flds
                    break

        if not chosen_model:
            chosen_model = "Basic"
            chosen_fields = ["Front", "Back"]

        # Формуємо поля залежно від моделі
        fields_dict = {}
        if chosen_model == "Манхва Словник" and len(chosen_fields) >= 3:
            fields_dict = {
                chosen_fields[0]: f"{word} {ipa_str}".strip(),
                chosen_fields[1]: sentence,
                chosen_fields[2]: back_html
            }
        elif len(chosen_fields) >= 2:
            fields_dict = {
                chosen_fields[0]: front_html,
                chosen_fields[1]: back_html
            }
        else:
            fields_dict = {
                chosen_fields[0]: f"{front_html}<hr>{back_html}"
            }

        note = {
            "deckName": deck,
            "modelName": chosen_model,
            "fields": fields_dict,
            "options": {
                "allowDuplicate": True,
                "duplicateScope": "deck"
            },
            "tags": ["slovak_novels"]
        }

        res = self._invoke("addNote", note=note)
        return bool(res)
