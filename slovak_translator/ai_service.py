import os
import json
import requests
from typing import Tuple, List, Dict, Any
from config import config

class SlovakAIService:
    def __init__(self):
        pass

    def get_api_key(self) -> str:
        return config.get("gemini_api_key", "").strip()

    def get_model(self) -> str:
        return config.get("gemini_model", "gemini-flash-lite-latest")

    def _call_gemini_api(self, prompt: str) -> str:
        api_key = self.get_api_key()
        if not api_key:
            return "Помилка: API ключ Gemini не встановлено в налаштуваннях."

        model = self.get_model()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1000
            }
        }
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12.0)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            return f"Помилка Gemini API: {resp.status_code} - {resp.text[:150]}"
        except Exception as e:
            return f"Помилка з'єднання з Gemini: {e}"

    def analyze_sentence(self, sentence: str) -> Tuple[str, str]:
        prompt = f"""Ти — професійний перекладач художніх новел і репетитор словацької мови (рівень B1-B2).
Твоє завдання — перекласти словацьке речення українською мовою та коротко розібрати його особливості (граматика, специфічний сленг, відмінки, фразеологізми, нюанси).

Словацьке речення з новели:
"{sentence}"

Формат відповіді (чітко за тегами):
<TRANSLATION>
[Художній літературний переклад українською мовою]
</TRANSLATION>
<BREAKDOWN>
[Короткий, структурований розбір:
1. Ключові слова/ідіоми та їх значення
2. Граматичні чи відмінкові нюанси (якщо є)
3. Контекстне значення]
</BREAKDOWN>"""

        raw = self._call_gemini_api(prompt)

        trans = ""
        expl = ""

        if "<TRANSLATION>" in raw and "</TRANSLATION>" in raw:
            parts = raw.split("<TRANSLATION>")[1].split("</TRANSLATION>")
            trans = parts[0].strip()
            if "<BREAKDOWN>" in parts[1]:
                expl = parts[1].split("<BREAKDOWN>")[1].replace("</BREAKDOWN>", "").strip()
            else:
                expl = parts[1].strip()
        else:
            trans = raw
            expl = "Детальний аналіз відсутній."

        return trans, expl

    def ask_followup(self, context_sentence: str, prev_answer: str, user_question: str) -> str:
        prompt = f"""Контекст словацького речення з новели:
"{context_sentence}"

Попередній розбір:
{prev_answer}

Питання читача:
"{user_question}"

Дай чітку, зрозумілу та лаконічну відповідь українською мовою."""
        return self._call_gemini_api(prompt)
