# 🧠 Глобальна Пам'ять Проєкту (Global Project Memory)
## Комплекс: M_Translate & Manhwa Reader (Dark Fantasy Edition)

Ця директорія містить вичерпну архітектурну, технічну, дизайнерську та контекстну документацію проєкту. Вона слугує незмінною базою знань (Single Source of Truth) для розробника та ШІ-асистентів у всіх наступних сесіях.

---

### 🗺️ Структура Пам'яті Проєкту:

1. [**01_PROJECT_OVERVIEW.md**](file:///d:/всі%20проекти/перекладач/.project_memory/01_PROJECT_OVERVIEW.md)
   - Місія та цілі створення комплексу.
   - Хто цільова аудиторія та яку ключову біль вирішує проєкт.
   - Продуктова екосистема: 3 режими випуску (`lm_reader.exe`, `m_translate.exe`, `m_reader_t.exe`).

2. [**02_ARCHITECTURE_AND_TECH_STACK.md**](file:///d:/всі%20проекти/перекладач/.project_memory/02_ARCHITECTURE_AND_TECH_STACK.md)
   - Повний стек технологій (PyQt6, RapidOCR/ONNX, SQLite FTS5, Google Gemini API, AnkiConnect, PyMuPDF, Telethon/aiohttp).
   - Огляд компонентів та модулів ядра перекладача й читалки.
   - Схеми взаємодії між процесами, потоками та базами даних.

3. [**03_DESIGN_SYSTEM_AND_STYLE_GUIDE.md**](file:///d:/всі%20проекти/перекладач/.project_memory/03_DESIGN_SYSTEM_AND_STYLE_GUIDE.md)
   - Фірмовий стиль **Dark Fantasy / Neon Cyber-Comic**.
   - Офіційна палітра кольорів (HEX, градієнти, акценти).
   - Типографіка, геометрія, заокруглення, правила анімацій та тіней.
   - Стилізація комікс-хмаринок, віджетів, кнопок та безшовного скролу.

4. [**04_MODULES_DEEP_DIVE.md**](file:///d:/всі%20проекти/перекладач/.project_memory/04_MODULES_DEEP_DIVE.md)
   - Детальний розбір кожного файлу: `main.py`, `bubble_window.py`, `anki_dialog.py`, `ocr_snipper.py`, `ai_chat_window.py`, `reader.py` тощо.
   - Механіка глобальних гарячих клавіш (Windows hooks), захоплення кадрів 16:10, AnkiConnect integration.
   - Локалізація (TR мультиязичність UK/EN/RU).

5. [**05_ROADMAP_AND_FUTURE_FEATURES.md**](file:///d:/всі%20проекти/перекладач/.project_memory/05_ROADMAP_AND_FUTURE_FEATURES.md)
   - Поточний стан проєкту (Status Quo).
   - Підготовка до впровадження нових фундаментальних функцій та модулів.
   - Технічні вимоги та орієнтири для майбутнього рефакторингу/розширення.

6. [**06_SLOVAK_NOVEL_SYSTEM.md**](file:///d:/всі%20проекти/перекладач/.project_memory/06_SLOVAK_NOVEL_SYSTEM.md)
   - Словацький навчальний напрямок (B1-B2 через читання новел/ранобе).
   - Читалка новел у `manhwa_reader` (Zen/Dark Mode, прогрес з точністю 0.1%, EPUB/DOCX/TXT).
   - Консольна утиліта пакетного перекладу глав (Gemini/DeepL) з авто-архівацією в `archive/`.
   - Окремий полегшений `Slovak Novel Translator` (без OCR, Alt+W для контексту, спрощений Anki, SK->UA).

---

> 💡 **Правило для ШІ:** Перед будь-якими змінами в коді перевіряйте фірмовий стиль у `03_DESIGN_SYSTEM_AND_STYLE_GUIDE.md` та архітектуру в `02_ARCHITECTURE_AND_TECH_STACK.md`.
