"""
Localization and Internationalization for M_Translate Manhwa Overlay Translator.
Supports UI localization (uk, en, ru), language direction switching (en, uk, ru, auto),
and M_Translate branding across headers, toasts, tooltips, and system tray.
"""

from typing import Dict, Any, List

SUPPORTED_SOURCE_LANGS: List[str] = ["en", "uk", "ru", "auto"]
SUPPORTED_TARGET_LANGS: List[str] = ["uk", "en", "ru"]
SUPPORTED_UI_LANGS: List[str] = ["uk", "en", "ru"]
SUPPORTED_AI_RESPONSE_LANGS: List[str] = ["uk", "ru", "en"]

LANG_CODE_TO_LABEL: Dict[str, Dict[str, str]] = {
    "uk": {
        "en": "English",
        "uk": "Українська",
        "ru": "Російська",
        "auto": "Авто-визначення",
    },
    "en": {
        "en": "English",
        "uk": "Ukrainian",
        "ru": "Russian",
        "auto": "Auto-detect",
    },
    "ru": {
        "en": "Английский",
        "uk": "Украинский",
        "ru": "Русский",
        "auto": "Авто-определение",
    },
}

POS_TRANSLATIONS_BY_LANG: Dict[str, Dict[str, str]] = {
    "uk": {
        "noun": "ІМЕННИК (Noun)",
        "verb": "ДІЄСЛОВО (Verb)",
        "adjective": "ПРИКМЕТНИК (Adjective)",
        "adverb": "ПРИСЛІВНИК (Adverb)",
        "pronoun": "ЗАЙМЕННИК (Pronoun)",
        "preposition": "ПРИЙМЕННИК (Preposition)",
        "conjunction": "СПОЛУЧНИК (Conjunction)",
        "interjection": "ВИГУК (Interjection)",
        "phrase": "ФРАЗА (Phrase)",
        "idiom": "ІДІОМА (Idiom)",
        "numeral": "ЧИСЛІВНИК (Numeral)",
        "particle": "ЧАСТКА (Particle)",
        "abbreviation": "СКОРОЧЕННЯ (Abbreviation)",
    },
    "ru": {
        "noun": "СУЩЕСТВИТЕЛЬНОЕ (Noun)",
        "verb": "ГЛАГОЛ (Verb)",
        "adjective": "ПРИЛАГАТЕЛЬНОЕ (Adjective)",
        "adverb": "НАРЕЧИЕ (Adverb)",
        "pronoun": "МЕСТОИМЕНИЕ (Pronoun)",
        "preposition": "ПРЕДЛОГ (Preposition)",
        "conjunction": "СОЮЗ (Conjunction)",
        "interjection": "МЕЖДОМЕТИЕ (Interjection)",
        "phrase": "ФРАЗА (Phrase)",
        "idiom": "ИДИОМА (Idiom)",
        "numeral": "ЧИСЛИТЕЛЬНОЕ (Numeral)",
        "particle": "ЧАСТИЦА (Particle)",
        "abbreviation": "СОКРАЩЕНИЕ (Abbreviation)",
    },
    "en": {
        "noun": "NOUN",
        "verb": "VERB",
        "adjective": "ADJECTIVE",
        "adverb": "ADVERB",
        "pronoun": "PRONOUN",
        "preposition": "PREPOSITION",
        "conjunction": "CONJUNCTION",
        "interjection": "INTERJECTION",
        "phrase": "PHRASE",
        "idiom": "IDIOM",
        "numeral": "NUMERAL",
        "particle": "PARTICLE",
        "abbreviation": "ABBREVIATION",
    },
}

UI_STRINGS: Dict[str, Dict[str, str]] = {
    "uk": {
        # Top bar
        "app_title": "⚡ M_TRANSLATE",
        "app_title_full": "⚡ M_TRANSLATE ПЕРЕКЛАДАЧ",
        "exit_btn": "⏻ Вийти",
        "exit_tooltip": "Повністю закрити програму",
        "close_tooltip": "Сховати віконце (Esc)",
        "settings_btn": "⚙",
        "settings_tooltip": "Налаштування мов, ШІ Gemini та Anki",
        "swap_tooltip": "Поміняти напрямок мов (⇄)",
        
        # Search & input
        "input_placeholder": "Введіть слово або фразу (Enter для перекладу)...",
        "voice_tooltip": "Озвучити вимову",
        "ocr_btn": "📷 Alt+E",
        "ocr_tooltip": "Захопити слово з екрана манхви [Alt+E]",
        "submit_tooltip": "Перекласти (Enter)",

        # Action bar
        "anki_btn": "⭐ Створити картку в Anki",
        "article_btn": "🌱 Словотвір",
        "article_btn_active": "★ Переклад",
        "article_tooltip": "Показати всі граматичні форми та статтю словника",
        "article_tooltip_active": "Повернутися до звичайного перекладу",
        "ai_btn": "🤖 AI",
        "ai_tooltip": "ШІ-розбір речень та ідіом (Alt+A)",

        # Clouds / results
        "copy_hint": "📋 Клік щоб скопіювати",
        "copied_toast": "✓ Скопійовано: {text}",
        "translating_status": "🔍 M_Translate перекладає '{query}'...",
        "not_found_badge": "⚠️ НЕ ЗНАЙДЕНО",
        "not_found_details": "Перевір правильність написання вихідного тексту.",
        "article_not_found_badge": "⚠️ НЕ ЗНАЙДЕНО СТАТТІ",
        "article_not_found_details": "Не вдалося сформувати окремі граматичні статті для цього слова.",
        
        # Cloud badges
        "cloud_main_badge": "★ ГОЛОВНИЙ ПЕРЕКЛАД",
        "cloud_synonyms_badge": "🔄 СИНОНІМИ",
        "cloud_definitions_badge": "📖 ЗНАЧЕННЯ",
        "cloud_manhwa_badge": "🗡️ У МАНХВІ ТА КОМІКСАХ",
        "cloud_example_badge": "💡 ПРИКЛАД ВЖИВАННЯ",
        "cloud_breakdown_badge": "🧩 СЛОВА У ВИРАЗІ",
        "cloud_tip_badge": "💡 ПОРАДА",
        "cloud_tip_term_1": "Натисніть на будь-яку хмаринку, щоб скопіювати переклад!",
        "cloud_tip_term_2": "Enter або клік для швидкого перекладу",
        "cloud_article_badge": "📖 СЛОВНИКОВА СТАТТЯ",
        "cloud_article_meaning": "• Значення: ",
        "cloud_article_example": "Приклад: ",
        "cloud_article_trans": "• Переклад: ",

        # Welcome card
        "welcome_badge": "⚡ M_TRANSLATE ГОТОВИЙ ДО РОБОТИ",
        "welcome_title": "Виділіть репліку через Alt+E або введіть слово",
        "welcome_phonetic": "[m_translate • manhwa learning companion]",
        "welcome_detail_1": "📷 Alt+E: миттєво виділити слово чи фразу в манхві",
        "welcome_detail_2": "⭐ Кнопка 'Створити картку в Anki' відкриває вікно додавання",
        "welcome_detail_3": "🖼️ Alt+D: рамка для захоплення малюнка панелі в картку!",

        # Bottom tip
        "bottom_tip": "📷 Alt+E = слово • Alt+W = речення • ↘ тягнути кутик",

        # Settings dialog
        "settings_dialog_title": "⚙ Налаштування • M_Translate",
        "tab_languages": "🌐 Мови",
        "tab_ai": "🤖 ШІ Gemini",
        "tab_anki": "🎴 Anki Connect",
        "tab_help": "📖 Інструкція",
        "source_lang_label": "Вихідна мова (Source):",
        "target_lang_label": "Мова перекладу (Target):",
        "ui_lang_label": "Мова інтерфейсу (UI):",
        "lang_swap_btn": "⇄ Поміняти місцями",
        "gemini_api_key_label": "Gemini API Key:",
        "gemini_model_label": "Модель Gemini:",
        "ai_resp_lang_label": "Мова пояснень та відповідей ШІ:",
        "anki_deck_label": "Назва колоди Anki (Deck):",
        "anki_status_label": "Статус AnkiConnect:",
        "anki_connected": "🟢 Підключено (порт {port})",
        "anki_not_found": "🔴 Anki не знайдено (перевірте AnkiConnect на 8766/8765)",
        "anki_test_btn": "🔄 Перевірити зв'язок",
        "help_guide_btn": "📖 Відкрити інструкцію (User Guide)",
        "save_btn": "Зберегти",
        "cancel_btn": "Закрити",

        # Tray Menu
        "tray_tooltip": "⚡ M_Translate Оверлей",
        "tray_word_ocr": "📷 Захопити слово (Alt+E)",
        "tray_sent_ocr": "📝 Захопити речення для Anki (Alt+W)",
        "tray_panel_crop": "🖼️ Захопити арт у картку (Alt+D)",
        "tray_blank_anki": "🎴 Створити порожню картку (Alt+S)",
        "tray_ai": "🤖 ШІ-розбір речень та ідіом (Alt+A)",
        "tray_show": "💬 Відкрити перекладач (Alt+Q)",
        "tray_dict": "📖 Словник та картки Anki",
        "tray_center": "🎯 Центрувати віджет M_Translate на екрані",
        "tray_exit": "❌ Вийти з програми (Повне закриття)",

        # AI Chat Window
        "ai_window_title_base": "⚡ M_TRANSLATE AI",
        "ai_window_title_new": "⚡ M_TRANSLATE AI • НОВИЙ РОЗБІР",
        "ai_new_chat_btn": "＋ Новий",
        "ai_new_chat_tooltip": "Почати новий окремий розбір (новий чат)",
        "ai_sessions_btn": "💬 Сесії ({count})",
        "ai_sessions_tooltip": "Список збережених діалогів цієї сесії",
        "ai_close_tooltip": "Сховати вікно AI",
        "ai_typing": "M_Translate AI пише...",
        "ai_input_placeholder": "Введіть або відредагуйте текст (Enter для надсилання)...",
        "ai_welcome_text": "Привіт! Я M_Translate AI. Введіть речення або питання знизу та натисніть Enter (або ➤).\nЯ надам точний художній переклад та детально розберу граматику, ідіоми та приховані нюанси.",
        "ai_bubble_copy_btn": "📋 Копіювати",
        "ai_bubble_anki_btn": "⭐ В Anki",
        "ai_copied_toast": "Текст скопійовано!",
        "ai_session_deleted": "Сесію видалено",
        "ai_delete_session": "🗑️ Видалити цю сесію",
        "ai_sessions_empty": "(Немає збережених сесій)",
        "ai_sessions_new_action": "➕ Почати новий розбір",
        "ai_sessions_clear_all": "🗑️ Очистити всі сесії",
        "ai_sessions_cleared_toast": "Всі сесії очищено!",
        "ai_session_opened_toast": "Відкрито сесію: {title}...",
        "ai_msg_count": "{count} пов.",
        "ai_badge_art_trans": "📖 ХУДОЖНІЙ ПЕРЕКЛАД",
        "ai_badge_idiom_expl": "🔍 РОЗБІР ІДІОМ ТА СТРУКТУРИ",
        "ai_badge_error": "⚠️ ПОМИЛКА",
        "ai_error_gemini": "⚠️ Помилка Gemini: {error}",

        # Anki Card Creator Modal
        "anki_dialog_title": "🎴 Створення картки • {deck}",
        "anki_word_label": "СЛОВО (Word):",
        "anki_sent_label": "РЕЧЕННЯ (Sentence):",
        "anki_btn_ocr_sent": "📝 Захопити з манхви (Alt+W)",
        "anki_sent_placeholder": "Речення з манхви (виділіть через Alt+W або вставте текст)...",
        "anki_trans_label": "ПЕРЕКЛАД (Translation):",
        "anki_art_label": "МАНХВА-АРТ ДЛЯ КАРТКИ (Опціонально):",
        "anki_btn_capture_art": "🖼️ Захопити панель (Alt+D)",
        "anki_no_image": "Немає зображення (натисніть Alt+D для рамки арту)",
        "anki_save_btn": "✅ Додати в Anki ({deck})",
        "anki_validation_error": "⚠️ Заповніть слово та переклад!",
        "anki_delete_art_tooltip": "Видалити зображення",
        "anki_deck_not_found_prompt": "Колоду '{deck}' не знайдено в Anki.\nСтворити нову з нашою картковою архітектурою (Лице: Слово, Речення, Арт; Зворот: Переклад)?",
        "anki_sync_template_prompt": "Тип нотатки для колоди '{deck}' відрізняється від нашого 'Манхва Словник'.\nОновити та синхронізувати шаблон на Dark Fantasy макет (Лице: Слово, Речення, Арт; Зворот: Переклад)?",
        "anki_unreachable_title": "⚡ AnkiConnect не знайдено",
        "anki_unreachable_banner": "⚡ Anki не відкрито • Картки зберігаються локально (SQLite/APKG)",
        "anki_connected_banner": "🟢 AnkiConnect підключено ({deck})",
        "anki_unreachable_dialog_text": "⚠️ Anki не запущено або плагін AnkiConnect не знайдено на портах 8765/8766.\n\nЩоб картки додавалися прямо в Anki:\n1. Відкрийте програму Anki на комп'ютері.\n2. Встановіть плагін AnkiConnect (Код: 2055492159).\n\n💾 До запуску Anki ваші картки надійно зберігаються локально в базу даних SQLite, CSV та пакет angl_manhwa.apkg.",
        "anki_deck_created_success": "✓ Колоду '{deck}' та макет Dark Fantasy успішно створено!",
        "anki_template_synced_success": "✓ Шаблон '{deck}' успішно синхронізовано з Dark Fantasy макетом!",
        "anki_btn_create_deck": "⚔️ Створити колоду",
        "anki_btn_sync_template": "⚔️ Оновити шаблон",
        "anki_btn_confirm_ok": "Зрозуміло (OK)",
        "anki_btn_cancel": "Скасувати",
        "anki_saved_local_msg": "💾 Збережено локально (SQLite/APKG)! Запустіть Anki для прямої синхронізації.",
        "saved": "Збережено",

        # History Window
        "hist_window_title": "📖 Словник Манхви - Історія Перекладів",
        "hist_header": "⚡ Словник слів з манхви",
        "hist_search_ph": "🔍 Пошук по історії слів...",
        "hist_copy_btn": "📋 Скопіювати",
        "hist_anki_btn": "⭐ Додати в Anki",
        "hist_clear_btn": "🗑️ Очистити",
        "hist_open_folder_btn": "📦 Відкрити папку з колодою Anki (.apkg)",
        "hist_empty": "Історія порожня.",
        "hist_no_results": "Слів не знайдено за фільтром.",
        "hist_copied_toast": "✓ Скопійовано: {word}",
        "hist_clear_confirm_title": "Очистити історію",
        "hist_clear_confirm_msg": "Ви впевнені, що хочете видалити всі слова з історії?",
    },
    "en": {
        # Top bar
        "app_title": "⚡ M_TRANSLATE",
        "app_title_full": "⚡ M_TRANSLATE OVERLAY",
        "exit_btn": "⏻ Exit",
        "exit_tooltip": "Completely exit the application",
        "close_tooltip": "Hide bubble window (Esc)",
        "settings_btn": "⚙",
        "settings_tooltip": "Language, Gemini AI, and Anki settings",
        "swap_tooltip": "Swap translation languages (⇄)",

        # Search & input
        "input_placeholder": "Enter word or phrase (Enter to translate)...",
        "voice_tooltip": "Pronounce audio",
        "ocr_btn": "📷 Alt+E",
        "ocr_tooltip": "Capture word from manhwa screen [Alt+E]",
        "submit_tooltip": "Translate (Enter)",

        # Action bar
        "anki_btn": "⭐ Create Anki Card",
        "article_btn": "🌱 Word Forms",
        "article_btn_active": "★ Translation",
        "article_tooltip": "Show all grammatical forms and dictionary article",
        "article_tooltip_active": "Return to standard translation",
        "ai_btn": "🤖 AI",
        "ai_tooltip": "AI sentence & idiom analysis (Alt+A)",

        # Clouds / results
        "copy_hint": "📋 Click to copy",
        "copied_toast": "✓ Copied: {text}",
        "translating_status": "🔍 M_Translate is translating '{query}'...",
        "not_found_badge": "⚠️ NOT FOUND",
        "not_found_details": "Please check the spelling of your input text.",
        "article_not_found_badge": "⚠️ ARTICLE NOT FOUND",
        "article_not_found_details": "Could not generate grammatical entry for this word.",

        # Cloud badges
        "cloud_main_badge": "★ MAIN TRANSLATION",
        "cloud_synonyms_badge": "🔄 SYNONYMS",
        "cloud_definitions_badge": "📖 DEFINITIONS",
        "cloud_manhwa_badge": "🗡️ IN MANHWA & COMICS",
        "cloud_example_badge": "💡 USAGE EXAMPLE",
        "cloud_breakdown_badge": "🧩 WORDS IN PHRASE",
        "cloud_tip_badge": "💡 TIP",
        "cloud_tip_term_1": "Click on any bubble card to copy translation!",
        "cloud_tip_term_2": "Press Enter or click arrow to translate",
        "cloud_article_badge": "📖 DICTIONARY ENTRY",
        "cloud_article_meaning": "• Meaning: ",
        "cloud_article_example": "Example: ",
        "cloud_article_trans": "• Translation: ",

        # Welcome card
        "welcome_badge": "⚡ M_TRANSLATE READY",
        "welcome_title": "Select manhwa text with Alt+E or type a word",
        "welcome_phonetic": "[m_translate • manhwa learning companion]",
        "welcome_detail_1": "📷 Alt+E: instantly capture word or phrase in manhwa",
        "welcome_detail_2": "⭐ 'Create Anki Card' button opens the card creator",
        "welcome_detail_3": "🖼️ Alt+D: capture panel art directly into your card!",

        # Bottom tip
        "bottom_tip": "📷 Alt+E = word • Alt+W = sentence • ↘ drag corner",

        # Settings dialog
        "settings_dialog_title": "⚙ Settings • M_Translate",
        "tab_languages": "🌐 Languages",
        "tab_ai": "🤖 Gemini AI",
        "tab_anki": "🎴 Anki Connect",
        "tab_help": "📖 User Guide",
        "source_lang_label": "Source Language:",
        "target_lang_label": "Target Language:",
        "ui_lang_label": "Interface Language:",
        "lang_swap_btn": "⇄ Swap Languages",
        "gemini_api_key_label": "Gemini API Key:",
        "gemini_model_label": "Gemini Model:",
        "ai_resp_lang_label": "AI Explanations & Responses Language:",
        "anki_deck_label": "Anki Deck Name:",
        "anki_status_label": "AnkiConnect Status:",
        "anki_connected": "🟢 Connected (port {port})",
        "anki_not_found": "🔴 Anki not found (check AnkiConnect on 8766/8765)",
        "anki_test_btn": "🔄 Test Connection",
        "help_guide_btn": "📖 Open User Guide",
        "save_btn": "Save",
        "cancel_btn": "Close",

        # Tray Menu
        "tray_tooltip": "⚡ M_Translate Overlay",
        "tray_word_ocr": "📷 Capture word (Alt+E)",
        "tray_sent_ocr": "📝 Capture sentence for Anki (Alt+W)",
        "tray_panel_crop": "🖼️ Capture art for card (Alt+D)",
        "tray_blank_anki": "🎴 Create blank card (Alt+S)",
        "tray_ai": "🤖 AI Sentence & Idiom Breakdown (Alt+A)",
        "tray_show": "💬 Open Translator (Alt+Q)",
        "tray_dict": "📖 Dictionary & Anki cards",
        "tray_center": "🎯 Center M_Translate widget on screen",
        "tray_exit": "❌ Exit Application",

        # AI Chat Window
        "ai_window_title_base": "⚡ M_TRANSLATE AI",
        "ai_window_title_new": "⚡ M_TRANSLATE AI • NEW ANALYSIS",
        "ai_new_chat_btn": "＋ New",
        "ai_new_chat_tooltip": "Start a new isolated analysis (new chat)",
        "ai_sessions_btn": "💬 Sessions ({count})",
        "ai_sessions_tooltip": "Saved conversations in this session",
        "ai_close_tooltip": "Hide AI window",
        "ai_typing": "M_Translate AI is typing...",
        "ai_input_placeholder": "Enter or edit text (Enter to send)...",
        "ai_welcome_text": "Greetings! I am M_Translate AI. Type a sentence or question below and press Enter (or ➤).\nI will provide a refined literary translation and analyze idioms, nuance, and grammar.",
        "ai_bubble_copy_btn": "📋 Copy",
        "ai_bubble_anki_btn": "⭐ To Anki",
        "ai_copied_toast": "Text copied!",
        "ai_session_deleted": "Session deleted",
        "ai_delete_session": "🗑️ Delete this session",
        "ai_sessions_empty": "(No saved sessions)",
        "ai_sessions_new_action": "➕ Start new analysis",
        "ai_sessions_clear_all": "🗑️ Clear all sessions",
        "ai_sessions_cleared_toast": "All sessions cleared!",
        "ai_session_opened_toast": "Opened session: {title}...",
        "ai_msg_count": "{count} msgs",
        "ai_badge_art_trans": "📖 LITERARY TRANSLATION",
        "ai_badge_idiom_expl": "🔍 IDIOM & STRUCTURE BREAKDOWN",
        "ai_badge_error": "⚠️ ERROR",
        "ai_error_gemini": "⚠️ Gemini error: {error}",

        # Anki Card Creator Modal
        "anki_dialog_title": "🎴 Card Creator • {deck}",
        "anki_word_label": "WORD:",
        "anki_sent_label": "SENTENCE:",
        "anki_btn_ocr_sent": "📝 Snip from manhwa (Alt+W)",
        "anki_sent_placeholder": "Sentence from manhwa (snip with Alt+W or paste text)...",
        "anki_trans_label": "TRANSLATION:",
        "anki_art_label": "MANHWA ART FOR CARD (Optional):",
        "anki_btn_capture_art": "🖼️ Capture panel art (Alt+D)",
        "anki_no_image": "No image (press Alt+D for panel crop box)",
        "anki_save_btn": "✅ Add to Anki ({deck})",
        "anki_validation_error": "⚠️ Please fill word and translation!",
        "anki_delete_art_tooltip": "Remove image",
        "anki_deck_not_found_prompt": "Deck '{deck}' was not found in Anki.\nCreate a new one with our card architecture (Front: Word, Sentence, Art; Back: Translation)?",
        "anki_sync_template_prompt": "Note type for deck '{deck}' is not our custom 'Манхва Словник'.\nUpdate and synchronize template to our Dark Fantasy layout (Front: Word, Sentence, Art; Back: Translation)?",
        "anki_unreachable_title": "⚡ AnkiConnect Unreachable",
        "anki_unreachable_banner": "⚡ Anki not running • Cards saved locally (SQLite/APKG)",
        "anki_connected_banner": "🟢 AnkiConnect connected ({deck})",
        "anki_unreachable_dialog_text": "⚠️ Anki is not running or AnkiConnect was not detected on ports 8765/8766.\n\nTo add cards directly into Anki:\n1. Open Anki on your computer.\n2. Install the AnkiConnect add-on (Code: 2055492159).\n\n💾 Meanwhile, your cards are safely saved locally to SQLite, CSV, and the angl_manhwa.apkg package.",
        "anki_deck_created_success": "✓ Deck '{deck}' and Dark Fantasy layout created successfully!",
        "anki_template_synced_success": "✓ Template for '{deck}' successfully synchronized to Dark Fantasy layout!",
        "anki_btn_create_deck": "⚔️ Create Deck",
        "anki_btn_sync_template": "⚔️ Update Template",
        "anki_btn_confirm_ok": "Understood (OK)",
        "anki_btn_cancel": "Cancel",
        "anki_saved_local_msg": "💾 Saved locally (SQLite/APKG)! Launch Anki for direct sync.",
        "saved": "Saved",

        # History Window
        "hist_window_title": "📖 Manhwa Vocabulary - Translation History",
        "hist_header": "⚡ Manhwa Vocabulary List",
        "hist_search_ph": "🔍 Search translation history...",
        "hist_copy_btn": "📋 Copy",
        "hist_anki_btn": "⭐ Add to Anki",
        "hist_clear_btn": "🗑️ Clear",
        "hist_open_folder_btn": "📦 Open Anki Deck Folder (.apkg)",
        "hist_empty": "History is empty.",
        "hist_no_results": "No words found matching filter.",
        "hist_copied_toast": "✓ Copied: {word}",
        "hist_clear_confirm_title": "Clear History",
        "hist_clear_confirm_msg": "Are you sure you want to delete all words from history?",
    },
    "ru": {
        # Top bar
        "app_title": "⚡ M_TRANSLATE",
        "app_title_full": "⚡ M_TRANSLATE ПЕРЕВОДЧИК",
        "exit_btn": "⏻ Выйти",
        "exit_tooltip": "Полностью закрыть приложение",
        "close_tooltip": "Скрыть окно (Esc)",
        "settings_btn": "⚙",
        "settings_tooltip": "Настройки языков, ИИ Gemini и Anki",
        "swap_tooltip": "Поменять языки местами (⇄)",

        # Search & input
        "input_placeholder": "Введите слово или фразу (Enter для перевода)...",
        "voice_tooltip": "Озвучить произношение",
        "ocr_btn": "📷 Alt+E",
        "ocr_tooltip": "Захватить слово с экрана манхвы [Alt+E]",
        "submit_tooltip": "Перевести (Enter)",

        # Action bar
        "anki_btn": "⭐ Создать карточку в Anki",
        "article_btn": "🌱 Словообразование",
        "article_btn_active": "★ Перевод",
        "article_tooltip": "Показать все грамматические формы и словарную статью",
        "article_tooltip_active": "Вернуться к обычному переводу",
        "ai_btn": "🤖 AI",
        "ai_tooltip": "ИИ-разбор предложений и идиом (Alt+A)",

        # Clouds / results
        "copy_hint": "📋 Клик для копирования",
        "copied_toast": "✓ Скопировано: {text}",
        "translating_status": "🔍 M_Translate переводит '{query}'...",
        "not_found_badge": "⚠️ НЕ НАЙДЕНО",
        "not_found_details": "Проверьте правильность написания текста.",
        "article_not_found_badge": "⚠️ СТАТЬЯ НЕ НАЙДЕНА",
        "article_not_found_details": "Не удалось составить грамматические статьи для этого слова.",

        # Cloud badges
        "cloud_main_badge": "★ ГЛАВНЫЙ ПЕРЕВОД",
        "cloud_synonyms_badge": "🔄 СИНОНИМЫ",
        "cloud_definitions_badge": "📖 ЗНАЧЕНИЕ",
        "cloud_manhwa_badge": "🗡️ В МАНХВЕ И КОМИКСАХ",
        "cloud_example_badge": "💡 ПРИМЕР ИСПОЛЬЗОВАНИЯ",
        "cloud_breakdown_badge": "🧩 СЛОВА В ВЫРАЖЕНИИ",
        "cloud_tip_badge": "💡 СОВЕТ",
        "cloud_tip_term_1": "Нажмите на любое облачко, чтобы скопировать перевод!",
        "cloud_tip_term_2": "Enter или клик для быстрого перевода",
        "cloud_article_badge": "📖 СЛОВАРНАЯ СТАТЬЯ",
        "cloud_article_meaning": "• Значение: ",
        "cloud_article_example": "Пример: ",
        "cloud_article_trans": "• Перевод: ",

        # Welcome card
        "welcome_badge": "⚡ M_TRANSLATE ГОТОВ К РАБОТЕ",
        "welcome_title": "Выделите реплику через Alt+E или введите слово",
        "welcome_phonetic": "[m_translate • manhwa learning companion]",
        "welcome_detail_1": "📷 Alt+E: мгновенно выделить слово или фразу в манхве",
        "welcome_detail_2": "⭐ Кнопка 'Создать карточку в Anki' открывает окно добавления",
        "welcome_detail_3": "🖼️ Alt+D: рамка для захвата арта панели в карточку!",

        # Bottom tip
        "bottom_tip": "📷 Alt+E = слово • Alt+W = предложение • ↘ тянуть угол",

        # Settings dialog
        "settings_dialog_title": "⚙ Настройки • M_Translate",
        "tab_languages": "🌐 Языки",
        "tab_ai": "🤖 ИИ Gemini",
        "tab_anki": "🎴 Anki Connect",
        "tab_help": "📖 Инструкция",
        "source_lang_label": "Исходный язык (Source):",
        "target_lang_label": "Язык перевода (Target):",
        "ui_lang_label": "Язык интерфейса (UI):",
        "lang_swap_btn": "⇄ Поменять местами",
        "gemini_api_key_label": "Gemini API Key:",
        "gemini_model_label": "Модель Gemini:",
        "ai_resp_lang_label": "Язык пояснений и ответов ИИ:",
        "anki_deck_label": "Имя колоды Anki (Deck):",
        "anki_status_label": "Статус AnkiConnect:",
        "anki_connected": "🟢 Подключено (порт {port})",
        "anki_not_found": "🔴 Anki не найден (проверьте AnkiConnect на 8766/8765)",
        "anki_test_btn": "🔄 Проверить связь",
        "help_guide_btn": "📖 Открыть инструкцию (User Guide)",
        "save_btn": "Сохранить",
        "cancel_btn": "Закрыть",

        # Tray Menu
        "tray_tooltip": "⚡ M_Translate Оверлей",
        "tray_word_ocr": "📷 Захватить слово (Alt+E)",
        "tray_sent_ocr": "📝 Захватить предложение для Anki (Alt+W)",
        "tray_panel_crop": "🖼️ Захватить арт в карточку (Alt+D)",
        "tray_blank_anki": "🎴 Создать пустую карточку (Alt+S)",
        "tray_ai": "🤖 ИИ-разбор предложений и идиом (Alt+A)",
        "tray_show": "💬 Открыть переводчик (Alt+Q)",
        "tray_dict": "📖 Словарь и карточки Anki",
        "tray_center": "🎯 Центрировать виджет M_Translate на экране",
        "tray_exit": "❌ Выйти из программы (Полное закрытие)",

        # AI Chat Window
        "ai_window_title_base": "⚡ M_TRANSLATE AI",
        "ai_window_title_new": "⚡ M_TRANSLATE AI • НОВЫЙ РАЗБОР",
        "ai_new_chat_btn": "＋ Новый",
        "ai_new_chat_tooltip": "Начать новый отдельный разбор (новый чат)",
        "ai_sessions_btn": "💬 Сессии ({count})",
        "ai_sessions_tooltip": "Список сохранённых диалогов этой сессии",
        "ai_close_tooltip": "Скрыть окно AI",
        "ai_typing": "M_Translate AI пишет...",
        "ai_input_placeholder": "Введите или отредактируйте текст (Enter для отправки)...",
        "ai_welcome_text": "Привет! Я M_Translate AI. Введите предложение или вопрос снизу и нажмите Enter (или ➤).\nЯ предоставлю точный художественный перевод и подробно разберу скрытые идиомы, грамматику и нюансы.",
        "ai_bubble_copy_btn": "📋 Копировать",
        "ai_bubble_anki_btn": "⭐ В Anki",
        "ai_copied_toast": "Текст скопирован!",
        "ai_session_deleted": "Сессия удалена",
        "ai_delete_session": "🗑️ Удалить эту сессию",
        "ai_sessions_empty": "(Нет сохранённых сессий)",
        "ai_sessions_new_action": "➕ Начать новый разбор",
        "ai_sessions_clear_all": "🗑️ Очистить все сессии",
        "ai_sessions_cleared_toast": "Все сессии очищены!",
        "ai_session_opened_toast": "Открыта сессия: {title}...",
        "ai_msg_count": "{count} сообщ.",
        "ai_badge_art_trans": "📖 ХУДОЖЕСТВЕННЫЙ ПЕРЕВОД",
        "ai_badge_idiom_expl": "🔍 РАЗБОР ИДИОМ И СТРУКТУРЫ",
        "ai_badge_error": "⚠️ ОШИБКА",
        "ai_error_gemini": "⚠️ Ошибка Gemini: {error}",

        # Anki Card Creator Modal
        "anki_dialog_title": "🎴 Создание карточки • {deck}",
        "anki_word_label": "СЛОВО (Word):",
        "anki_sent_label": "ПРЕДЛОЖЕНИЕ (Sentence):",
        "anki_btn_ocr_sent": "📝 Захватить из манхвы (Alt+W)",
        "anki_sent_placeholder": "Предложение из манхвы (выделите через Alt+W или вставьте текст)...",
        "anki_trans_label": "ПЕРЕВОД (Translation):",
        "anki_art_label": "МАНХВА-АРТ ДЛЯ КАРТОЧКИ (Опционально):",
        "anki_btn_capture_art": "🖼️ Захватить панель (Alt+D)",
        "anki_no_image": "Нет изображения (нажмите Alt+D для рамки арта)",
        "anki_save_btn": "✅ Добавить в Anki ({deck})",
        "anki_validation_error": "⚠️ Заполните слово и перевод!",
        "anki_delete_art_tooltip": "Удалить изображение",
        "anki_deck_not_found_prompt": "Колода '{deck}' не найдена в Anki.\nСоздать новую с нашей карточной архитектурой (Лицо: Слово, Предложение, Арт; Оборот: Перевод)?",
        "anki_sync_template_prompt": "Тип записи для колоды '{deck}' отличается от нашего 'Манхва Словник'.\nОбновить и синхронизировать шаблон на Dark Fantasy макет (Лицо: Слово, Предложение, Арт; Оборот: Перевод)?",
        "anki_unreachable_title": "⚡ AnkiConnect не найден",
        "anki_unreachable_banner": "⚡ Anki не запущен • Карточки сохраняются локально (SQLite/APKG)",
        "anki_connected_banner": "🟢 AnkiConnect подключен ({deck})",
        "anki_unreachable_dialog_text": "⚠️ Anki не запущен или плагин AnkiConnect не найден на портах 8765/8766.\n\nЧтобы карточки добавлялись напрямую в Anki:\n1. Откройте программу Anki на компьютере.\n2. Установите плагин AnkiConnect (Код: 2055492159).\n\n💾 До запуска Anki ваши карточки надежно сохраняются локально в базу SQLite, CSV и автономный пакет angl_manhwa.apkg.",
        "anki_deck_created_success": "✓ Колода '{deck}' и макет Dark Fantasy успешно созданы!",
        "anki_template_synced_success": "✓ Шаблон '{deck}' успешно синхронизирован с макетом Dark Fantasy!",
        "anki_btn_create_deck": "⚔️ Создать колоду",
        "anki_btn_sync_template": "⚔️ Обновить шаблон",
        "anki_btn_confirm_ok": "Понятно (OK)",
        "anki_btn_cancel": "Отмена",
        "anki_saved_local_msg": "💾 Сохранено локально (SQLite/APKG)! Запустите Anki для прямой синхронизации.",
        "saved": "Сохранено",

        # History Window
        "hist_window_title": "📖 Словарь Манхвы - История Переводов",
        "hist_header": "⚡ Словарь слов из манхвы",
        "hist_search_ph": "🔍 Поиск по истории слов...",
        "hist_copy_btn": "📋 Скопировать",
        "hist_anki_btn": "⭐ Добавить в Anki",
        "hist_clear_btn": "🗑️ Очистить",
        "hist_open_folder_btn": "📦 Открыть папку с колодой Anki (.apkg)",
        "hist_empty": "История пуста.",
        "hist_no_results": "Слов по фильтру не найдено.",
        "hist_copied_toast": "✓ Скопировано: {word}",
        "hist_clear_confirm_title": "Очистить историю",
        "hist_clear_confirm_msg": "Вы уверены, что хотите удалить все слова из истории?",
    },
}


def tr(key: str, lang: str = "uk", **kwargs) -> str:
    """Fetches localized string with fallback to Ukrainian and string formatting."""
    lang_dict = UI_STRINGS.get(lang, UI_STRINGS["uk"])
    text = lang_dict.get(key, UI_STRINGS["uk"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def get_pos_translation(pos: str, target_lang: str = "uk") -> str:
    """Returns localized part of speech title based on selected target language."""
    pos_clean = pos.strip().lower()
    mapping = POS_TRANSLATIONS_BY_LANG.get(target_lang, POS_TRANSLATIONS_BY_LANG["uk"])
    return mapping.get(pos_clean, pos.upper())


def get_lang_label(code: str, ui_lang: str = "uk") -> str:
    """Returns human-readable name of language in currently active UI language."""
    labels = LANG_CODE_TO_LABEL.get(ui_lang, LANG_CODE_TO_LABEL["uk"])
    return labels.get(code, code.upper())
