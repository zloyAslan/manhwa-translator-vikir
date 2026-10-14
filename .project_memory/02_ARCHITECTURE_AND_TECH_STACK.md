# 🏗️ 02. Архітектура та технологічний стек (Architecture & Tech Stack)

## 1. Стек технологій

| Рівень | Технологія / Бібліотека | Призначення |
|---|---|---|
| **GUI Framework** | `PyQt6` (Core, Gui, Widgets) | Потужний графічний фреймворк, frameless вікна, прозорість, кастомний QSS, QGraphicsDropShadow |
| **OCR Engine** | `RapidOCR` + `ONNX Runtime` | Нейромережеве розпізнавання тексту з високою точністю для коміксних шрифтів (виправлення плутанини `D` / `P`) |
| **Штучний інтелект** | `google-genai` / Google Gemini API | Семантичний розбір тексту, ідіом, сленгу, контекстний діалог у ролі асистента Вікіра |
| **Інтеграція Anki** | `AnkiConnect` (HTTP REST API, порти 8766/8765) + `genanki` | Миттєве додавання нотаток у запущену десктопну програму Anki або прямий експорт `.apkg` |
| **Кешування словника** | `SQLite3` (`cache.db`, з підтримкою FTS5/швидкого пошуку) | Локальне збереження історії перекладів, визначень та прикладів |
| **Читалка (Engine)** | `PyMuPDF` (`fitz`), `Pillow` (PIL) | Рендеринг довгих вертикальних PDF-файлів вебтунів, розбивка на тайли, обробка зображень |
| **Хмара та Завантажувач** | `aiohttp`, `telethon` (Telegram MTProto client) | Завантаження розділів манхви з каналів Telegram та стрімінг із хмарного індексу |
| **Системні перехоплювачі** | `keyboard`, `pyperclip`, `pywin32` | Глобальні системні гарячі клавіші (Windows LL hooks), робота з буфером обміну, системні атрибути вікон |
| **Аудіо (Вимова)** | `edge-tts` (Microsoft Azure Neural) + `winmm` MCI API / `winsound` | Студійний нейронний синтез мовлення (SK ViktoriaNeural) з регулюванням швидкості та фоновим програванням без підвисання UI |

---

## 2. Загальна схема архітектури компонентів

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 ГОЛОВНІ ВХІДНІ ТОЧКИ                                   │
│  main.py (M_Translate)  │  reader.py (Reader)  │  suite_main.py (Комбайн Suite)        │
│  slovak_translator/main.py (Slovak Novel)      │  novel_batch_translator/novel_batch...│
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
           ┌────────────────────────────────┼────────────────────────────────┐
           ▼                                ▼                                ▼
┌───────────────────────────────┐ ┌─────────────────────────────────┐ ┌────────────────────────────────┐
│ МОДУЛЬ ОВЕРЛЕЮ (M_Translate)  │ │      МОДУЛЬ ЧИТАЛКИ (MANHWA)    │ │ СЛОВАЦЬКИЙ ПЕРЕКЛАДАЧ (SK-UK)  │
├───────────────────────────────┤ ├─────────────────────────────────┤ ├────────────────────────────────┤
│ • MascotBadge / ChibiMascot   │ │ • Reader Window (PyQt6 Scroll)  │ │ • Frameless Cloud Window (QSS) │
│ • BubbleWindow (Comic Frame)  │ │ • Webtoon Strip Layout          │ │ • Alt+W Live Text Capture      │
│ • SnippingOverlay (RapidOCR)  │ │ • PDF / Image Tile Renderer     │ │ • Edge Neural TTS (Viktoria)   │
│ • PanelCropper (Кадрування)   │ │ • Novel Reader (`novel_reader`) │ │ • IPA Phonetic Transcription   │
│ • AnkiCardDialog (Арт 16:10)  │ │ • Cloud Stream Client           │ │ • Text-only Anki Cards         │
│ • AIChatWindow (Gemini)       │ │ • Telegram Downloader + Dedup   │ │ • Gemini Fast Assistant        │
│ • HistoryWindow (Словник)     │ │ • Zen Mode / Fullscreen (F11/H) │ │ • Isolated SQLite Cache        │
└───────────────────────────────┘ └─────────────────────────────────┘ └────────────────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          СЕРВІСНИЙ ШАР (CORE)                         │
├───────────────────────────────────────────────────────────────────────┤
│ • DictionaryService: офлайн-кеш SQLite, парсинг слів, переклад        │
│ • AIService: підключення до Gemini 1.5/2.0 Flash/Pro, prompt templates │
│ • AnkiService: AnkiConnect API client (порт 8766), генерація apkg     │
│ • AudioService: завантаження та програвання нативного аудіо вимови    │
│ • Localization (tr): локалізація інтерфейсу uk/en/ru                  │
│ • Config (config.py / config.json): стан вікон, ключі, налаштування   │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3. Модель збереження стану та даних

1. **`config.json`**:
   - `gemini_api_key`, `gemini_model` (наприклад, `gemini-2.0-flash`), `ai_response_language`
   - `source_language` (`auto`, `en`, `ko`), `target_language` (`uk`, `ru`, `en`)
   - `ui_language` (`uk`, `en`, `ru`)
   - `anki_port` (8766 / 8765), `anki_deck` ("англ манхва")
   - Геометрія вікон: позиція бейджа, розміри бабла, стан закріплення (pin).

2. **`cache.db` (SQLite)**:
   - Зберігає кешовані картки перекладів, щоб не робити повторні мережеві запити.
   - Історія пошуків із таймстемпами для перегляду у `HistoryWindow`.

3. **`manhwa_reader/library`**:
   - Локальні папки манхви: назви творів -> томи -> глави (зображення або PDF).

4. **`manhwa_reader/cloud_index.json`**:
   - Метадані хмарного каталогу (назви манхв, обкладинки, списки доступних глав, посилання на стрім).
