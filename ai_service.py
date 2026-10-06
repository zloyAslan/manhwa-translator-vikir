"""
Gemini AI Service for Manhwa Translator (Dark Fantasy Edition).
Provides:
- Context-aware manhwa sentence translation & idiom breakdown
- Token-efficient 1-step conversational memory for follow-ups
- Direct in-memory session history tracking
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional
import requests
from config import Config

DEFAULT_GEMINI_KEY = "AQ.Ab8RN6JameZCI5KID03P781w8vgYtkJDi-5VMfBCOuI5zq7o6g"
GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
]


class AIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config().get("gemini_api_key", DEFAULT_GEMINI_KEY)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _call_gemini(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        headers = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 1024
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        last_error = ""
        for model in GEMINI_MODELS:
            url = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
            except Exception as e:
                last_error = str(e)

        raise RuntimeError(f"Gemini API Error: {last_error or 'Не вдалося отримати відповідь'}")

    def analyze_sentence(self, sentence: str) -> Tuple[str, str]:
        """
        Translates a manhwa sentence and breaks down idioms/expressions.
        Returns (translation, explanation).
        """
        clean_sentence = sentence.strip()
        if not clean_sentence:
            return "", ""

        system_instruction = (
            "Ти — елітний художній перекладач манхви та англійської літератури. "
            "Твоє завдання — перекласти речення українською мовою та пояснити ідіоми й сталі вирази. "
            "Відповідь ОБОВ'ЯЗКОВО надай у форматі JSON з двома полями:\n"
            "{\n"
            '  "translation": "влучний, природний український художній переклад речення",\n'
            '  "explanation": "пояснення ідіом/сталих виразів, чому саме так перекладено, буквальне значення проти ідіоматичного, та короткий розбір складових слів чи фраз"\n'
            "}\n"
            "Не додавай жодного зайвого тексту чи коментарів поза межами JSON."
        )

        prompt = (
            f"Речення для перекладу та розбору:\n\"{clean_sentence}\"\n\n"
            "Зроби точний переклад і лаконічний, змістовний розбір."
        )

        raw_response = self._call_gemini(prompt, system_instruction=system_instruction)

        # Parse JSON from response (handling potential markdown fences ```json ... ```)
        cleaned = re.sub(r"^```json\s*", "", raw_response, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()

        translation = ""
        explanation = ""

        try:
            parsed = json.loads(cleaned)
            translation = parsed.get("translation", "").strip()
            explanation = parsed.get("explanation", "").strip()
        except Exception:
            # Fallback if model didn't output pure JSON
            lines = [line.strip() for line in raw_response.split("\n") if line.strip()]
            if lines:
                translation = lines[0].strip("\"'«» ")
                explanation = "\n".join(lines[1:]).strip()

        if not translation:
            translation = raw_response

        return translation, explanation

    def ask_followup(self, sentence: str, previous_ai_response: str, question: str) -> str:
        """
        Follow-up question with strict 1-step context memory to prevent token waste:
        [Sentence] + [Previous AI Answer] + [New Question].
        """
        system_instruction = (
            "Ти — Вікір, помічник для читання манхви. Відповідай українською мовою лаконічно, "
            "прямо по суті запитання, зберігаючи компактність та високу точність без зайвої води."
        )

        prompt = (
            f"Речення для розбору:\n\"{sentence.strip()}\"\n\n"
            f"Попередня відповідь ШІ:\n{previous_ai_response.strip()}\n\n"
            f"Запитання користувача:\n{question.strip()}\n\n"
            "Дай точну і змістовну відповідь."
        )

        return self._call_gemini(prompt, system_instruction=system_instruction)
