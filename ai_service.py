"""
Gemini AI Service for M_Translate Manhwa Translator (Dark Fantasy Edition).
Provides:
- Context-aware manhwa sentence translation & idiom breakdown tailored for language learners
- Support for target_lang and custom ai_response_lang (uk, ru, en)
- Grammar explanations, nuance analysis, idioms, and natural translations
- Model selection (gemini-2.5-flash-lite, gemini-2.5-flash)
- Token-efficient 1-step conversational memory for follow-up inquiries
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional
import requests
from config import Config

DEFAULT_GEMINI_KEY = ""
DEFAULT_MODELS_FALLBACK = [
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite"
]


class AIService:
    def __init__(self, api_key: Optional[str] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.api_key = api_key or self.config.get("gemini_api_key", "")
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

        chosen_model = self.config.get("gemini_model", "gemini-flash-latest")
        models_to_try = [chosen_model] + [m for m in DEFAULT_MODELS_FALLBACK if m != chosen_model]

        active_key = self.config.get("gemini_api_key", self.api_key)
        if not active_key:
            raise RuntimeError("Введіть ваш Gemini API Key у Налаштуваннях (Вкладка AI Gemini) для використання ШІ.")

        last_error = ""
        for model in models_to_try:
            url = f"{self.base_url}/{model}:generateContent?key={active_key}"
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                elif resp.status_code == 429:
                    err_json = {}
                    try:
                        err_json = resp.json().get("error", {})
                        err_msg = err_json.get("message", "Перевищено ліміт запитів (Rate Limit).")
                    except Exception:
                        err_msg = "Перевищено ліміт запитів (Rate Limit)."
                    last_error = f"{model}: Ліміт запитів вичерпано (HTTP 429). Спробуйте через кілька секунд."
                    continue
                else:
                    # If 503 (high demand) or 404 (deprecated), continue immediately to next model in loop
                    err_json = {}
                    try:
                        err_json = resp.json().get("error", {})
                        err_msg = err_json.get("message", resp.text[:120])
                    except Exception:
                        err_msg = resp.text[:120]
                    last_error = f"{model} (HTTP {resp.status_code}): {err_msg}"
                    continue
            except Exception as e:
                last_error = f"{model}: {str(e)}"
                continue

        raise RuntimeError(f"Gemini API: {last_error or 'Всі моделі перевантажені або недоступні'}")

    def analyze_sentence(
        self,
        sentence: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        ui_lang: Optional[str] = None,
        ai_response_lang: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Translates a manhwa sentence and breaks down idioms/expressions tailored for language learners.
        Uses ai_response_lang for explanations, idioms breakdown, and grammar commentary.
        Returns (translation, explanation).
        """
        clean_sentence = sentence.strip()
        if not clean_sentence:
            return "", ""

        sl = source_lang or self.config.get("source_lang", "en")
        tl = target_lang or self.config.get("target_lang", "uk")
        # Explanations and prompts language priority: explicit ai_response_lang -> config -> ui_lang -> uk
        resp_lang = ai_response_lang or self.config.get("ai_response_lang") or ui_lang or self.config.get("ui_lang", "uk")

        target_desc_uk = {
            "uk": "українською мовою",
            "en": "англійською мовою",
            "ru": "російською мовою",
        }.get(tl, "українською мовою")

        target_desc_ru = {
            "uk": "на украинский язык",
            "en": "на английский язык",
            "ru": "на русский язык",
        }.get(tl, "на русский язык")

        target_desc_en = {
            "uk": "into Ukrainian",
            "en": "into English",
            "ru": "into Russian",
        }.get(tl, "into Ukrainian")

        if resp_lang == "ru":
            system_instruction = (
                "Ты — экспертный ИИ-наставник по изучению иностранных языков и художественный переводчик манхвы/комиксов M_Translate. "
                f"Твоя задача — точно перевести предложенную реплику {target_desc_ru} и дать структурированный обучающий разбор на русском языке. "
                "Особое внимание удели:\n"
                "1. Смыслу идиом, сленга и метафор (буквальное значение vs идиоматическое).\n"
                "2. Грамматической конструкции или необычным фразовым глаголам.\n"
                "3. Нюансам тона и контекста персонажа манхвы.\n"
                "Ответ ОБЯЗАТЕЛЬНО предоставь в формате чистого JSON без дополнительной разметки вне него:\n"
                "{\n"
                f'  "translation": "живой, естественный и точный художественный перевод {target_desc_ru}",\n'
                '  "explanation": "краткий и емкий обучающий разбор: грамматика, ключевые слова, идиомы и контекст на русском языке"\n'
                "}"
            )
            prompt = (
                f"Реплика/предложение для перевода и языкового разбора:\n\"{clean_sentence}\"\n\n"
                "Сделай перевод и обучающий разбор для читателя манхвы."
            )
        elif resp_lang == "en":
            system_instruction = (
                "You are an expert language-learning AI tutor and manhwa literary translator for M_Translate. "
                f"Your task is to accurately translate the sentence {target_desc_en} and provide an insightful learning breakdown in English. "
                "Focus on:\n"
                "1. Idiomatic expressions, manhwa slang, and figurative vs literal meanings.\n"
                "2. Grammatical structure and key vocabulary insights.\n"
                "3. Emotional tone and nuanced reading context.\n"
                "The response MUST be in pure JSON format:\n"
                "{\n"
                f'  "translation": "natural, evocative literary translation {target_desc_en}",\n'
                '  "explanation": "concise educational breakdown: grammar nuance, vocabulary breakdown, and idioms in English"\n'
                "}"
            )
            prompt = (
                f"Sentence for translation and linguistic breakdown:\n\"{clean_sentence}\"\n\n"
                "Provide the translation and educational breakdown for a manhwa reader."
            )
        else:  # default uk
            system_instruction = (
                "Ти — експертний ШІ-наставник з вивчення іноземних мов та художній перекладач манхви M_Translate. "
                f"Твоє завдання — влучно перекласти репліку {target_desc_uk} та надати структурований навчальний розбір українською мовою. "
                "Зверни особливу увагу на:\n"
                "1. Значення ідіом, сленгу та метафор (буквальне значення проти ідіоматичного контексту).\n"
                "2. Граматичну структуру та ключові фразові дієслова.\n"
                "3. Емоційні нюанси тону та контекст персонажа манхви.\n"
                "Відповідь ОБОВ'ЯЗКОВО надай у форматі чистого JSON:\n"
                "{\n"
                f'  "translation": "живий, точний та природний художній переклад {target_desc_uk}",\n'
                '  "explanation": "лаконічний і змістовний навчальний розбір: граматика, ключові слова, ідіоми та контекстні нюанси українською мовою"\n'
                "}"
            )
            prompt = (
                f"Репліка/речення для перекладу та навчального розбору:\n\"{clean_sentence}\"\n\n"
                "Зроби переклад та детальний навчальний розбір для читача манхви."
            )

        raw_response = self._call_gemini(prompt, system_instruction=system_instruction)

        # Parse JSON from response
        cleaned = re.sub(r"^```json\s*", "", raw_response, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()

        translation = ""
        explanation = ""

        try:
            parsed = json.loads(cleaned)
            translation = parsed.get("translation", "").strip()
            explanation = parsed.get("explanation", "").strip()
        except Exception:
            lines = [line.strip() for line in raw_response.split("\n") if line.strip()]
            if lines:
                translation = lines[0].strip("\"'«» ")
                explanation = "\n".join(lines[1:]).strip()

        if not translation:
            translation = raw_response

        return translation, explanation

    def ask_followup(
        self,
        sentence: str,
        previous_ai_response: str,
        question: str,
        ui_lang: Optional[str] = None,
        ai_response_lang: Optional[str] = None
    ) -> str:
        """
        Follow-up question with strict token-efficient 1-step context memory:
        [First sentence of session] + [Previous AI Answer] + [New Question].
        Answers in ai_response_lang.
        """
        resp_lang = ai_response_lang or self.config.get("ai_response_lang") or ui_lang or self.config.get("ui_lang", "uk")

        if resp_lang == "ru":
            system_instruction = (
                "Ты — M_Translate AI, наставник по языкам и чтению манхвы. "
                "Отвечай на русском языке лаконично, точно и доступно, объясняя грамматику, идиомы и значение фраз."
            )
            prompt_parts = []
            if sentence.strip():
                prompt_parts.append(f"Исходная фраза манхвы:\n\"{sentence.strip()}\"")
            if previous_ai_response.strip():
                prompt_parts.append(f"Предыдущий разбор:\n{previous_ai_response.strip()}")
            prompt_parts.append(f"Вопрос пользователя:\n{question.strip()}\n\nДай содержательный ответ на русском языке.")
        elif resp_lang == "en":
            system_instruction = (
                "You are M_Translate AI, a manhwa and language-learning companion. "
                "Answer in English concisely and accurately, explaining grammar, idioms, and reading nuances."
            )
            prompt_parts = []
            if sentence.strip():
                prompt_parts.append(f"Original manhwa sentence:\n\"{sentence.strip()}\"")
            if previous_ai_response.strip():
                prompt_parts.append(f"Previous analysis:\n{previous_ai_response.strip()}")
            prompt_parts.append(f"User question:\n{question.strip()}\n\nProvide an accurate and helpful answer in English.")
        else:  # default uk
            system_instruction = (
                "Ти — M_Translate AI, наставник з вивчення мов та читання манхви. "
                "Відповідай українською мовою лаконічно, точно та доступно, розбираючи граматику, ідіоми та значення реплік."
            )
            prompt_parts = []
            if sentence.strip():
                prompt_parts.append(f"Початкова репліка з манхви:\n\"{sentence.strip()}\"")
            if previous_ai_response.strip():
                prompt_parts.append(f"Попередній розбір:\n{previous_ai_response.strip()}")
            prompt_parts.append(f"Запитання користувача:\n{question.strip()}\n\nДай змістовну відповідь українською мовою.")

        prompt = "\n\n".join(prompt_parts)
        return self._call_gemini(prompt, system_instruction=system_instruction)
