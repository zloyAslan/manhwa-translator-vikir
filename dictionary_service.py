"""
Dictionary and Translation Service for Manhwa Overlay Translator.
Provides rich English-to-Ukrainian translations with parts of speech, synonyms, definitions, and IPA.
"""

import sys
import json
import sqlite3
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

DB_PATH = Path(__file__).parent / "cache.db"

POS_TRANSLATIONS = {
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
}

# Common fantasy / manhwa collocation hints for richer context cards
MANHWA_COLLOCATIONS = {
    "sword": ["iron sword (залізний меч)", "holy sword (священний меч)", "sword intent (намір меча)", "sword master (майстер меча)"],
    "hound": ["bloodhound (гончак/шукач)", "iron hound (залізний хорт)", "hellhound (пекельний пес)", "hunting hound (мисливський пес)"],
    "blood": ["iron-blooded (залізнокровний)", "bloodline (родовід)", "bloodlust (жага крові)", "dragon blood (кров дракона)"],
    "revenge": ["take revenge (помститися)", "blood revenge (кривава помста)", "avenger (месник)", "sweet revenge (солодка помста)"],
    "iron": ["iron-blooded (залізнокровний)", "iron will (залізна воля)", "iron wall (залізна стіна)", "iron ore (залізна руда)"],
    "clan": ["swordsman clan (клан мечників)", "family clan (родинний клан)", "clan head (голова клану)", "elder (старійшина)"],
    "blade": ["shadow blade (тіньове лезо)", "broken blade (зламане лезо)", "sharp blade (гостре лезо)"],
    "strike": ["fatal strike (смертельний удар)", "counter-strike (контрудар)", "lightning strike (удар блискавки)"],
    "shadow": ["shadow monarch (монарх тіней)", "shadow step (тіньовий крок)", "in the shadows (у тіні)"],
    "hunter": ["monster hunter (мисливець на монстрів)", "rank hunter (ранговий мисливець)", "guild (гільдія)"],
}

class DictionaryService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache (
                        word TEXT PRIMARY KEY,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        word TEXT,
                        main_trans TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"DB Init Error: {e}")

    def get_cached(self, word: str) -> Optional[Dict[str, Any]]:
        clean = word.strip().lower()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM cache WHERE word = ?", (clean,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            print(f"Cache get error: {e}")
        return None

    def save_cached(self, word: str, data: Dict[str, Any]):
        clean = word.strip().lower()
        main_trans = data.get("main", "").strip()
        # NEVER cache failed translations where translation is empty or matches raw English text
        if not main_trans or (main_trans.lower() == clean and any(c.isascii() and c.isalpha() for c in clean)):
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (word, data) VALUES (?, ?)",
                    (clean, json.dumps(data, ensure_ascii=False))
                )
                conn.execute(
                    "INSERT INTO history (word, main_trans) VALUES (?, ?)",
                    (clean, main_trans)
                )
                conn.commit()
        except Exception as e:
            print(f"Cache save error: {e}")

    def get_history(self, limit: int = 50) -> List[Dict[str, str]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT word, main_trans, created_at FROM history ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                return [{"word": r[0], "main": r[1], "time": r[2]} for r in cursor.fetchall()]
        except Exception as e:
            print(f"History get error: {e}")
            return []

    def clear_history(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
        except Exception as e:
            print(f"Clear history error: {e}")

    def _fetch_fallback_translate(self, text: str) -> str:
        """Fallback translation via MyMemory API when primary Google request has issues."""
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {"q": text, "langpair": "en|uk"}
            resp = requests.get(url, params=params, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                t = data.get("responseData", {}).get("translatedText", "").strip()
                if t and t.lower() != text.lower() and not t.startswith("MYMEMORY WARNING"):
                    return t
        except Exception as e:
            print(f"Fallback translate error: {e}")
        return ""

    def lookup(self, text: str) -> Dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return {"error": "Порожній запит"}

        # Check cache first (ignore bad cached entries where translation is identical to query)
        cached = self.get_cached(clean_text)
        if cached:
            c_main = cached.get("main", "").strip()
            if c_main and (c_main.lower() != clean_text.lower() or not any(c.isascii() and c.isalpha() for c in clean_text)):
                return cached

        # Fetch Google Translate Single API
        gt_data = self._fetch_google_dict(clean_text)

        # Quick attempt to fetch Free Dictionary API only for single words
        dict_data = None
        if " " not in clean_text and len(clean_text) < 30:
            dict_data = self._fetch_free_dictionary(clean_text)

        result = self._format_result(clean_text, gt_data, dict_data)
        self.save_cached(clean_text, result)
        return result

    def _fetch_google_dict(self, text: str) -> Dict[str, Any]:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "uk",
            "dt": ["t", "bd", "rm", "ss", "ex", "md"],
            "dj": "1",
            "q": text,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=4)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Google fetch error: {e}")
        return {}

    def _fetch_free_dictionary(self, word: str) -> Optional[Dict[str, Any]]:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        try:
            resp = requests.get(url, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
        except Exception:
            pass
        return None

    def _format_result(self, original_text: str, gt_data: Dict[str, Any], dict_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        main_trans = ""
        translit = ""

        if "sentences" in gt_data and isinstance(gt_data["sentences"], list):
            for s in gt_data["sentences"]:
                if isinstance(s, dict):
                    if "trans" in s and s["trans"]:
                        main_trans += s["trans"]
                    if "src_translit" in s and s["src_translit"] and not translit:
                        translit = s["src_translit"]

        # If primary translation failed or returned the exact same English text:
        if not main_trans or (main_trans.strip().lower() == original_text.strip().lower() and any(c.isascii() and c.isalpha() for c in original_text)):
            fallback_trans = self._fetch_fallback_translate(original_text)
            if fallback_trans:
                main_trans = fallback_trans

        if not main_trans:
            main_trans = original_text

        phonetic = translit
        audio_url = ""
        if dict_data:
            if dict_data.get("phonetic"):
                phonetic = dict_data["phonetic"]
            for ph in dict_data.get("phonetics", []):
                if not phonetic and ph.get("text"):
                    phonetic = ph["text"]
                if ph.get("audio"):
                    audio_url = ph["audio"]

        pos_list = []
        all_synonyms_set = set()
        if "dict" in gt_data and isinstance(gt_data["dict"], list):
            for d in gt_data["dict"]:
                pos_raw = d.get("pos", "").lower()
                pos_title = POS_TRANSLATIONS.get(pos_raw, pos_raw.upper())
                terms = d.get("terms", [])
                entries = []
                for entry in d.get("entry", []):
                    w = entry.get("word", "")
                    rev = entry.get("reverse_translation", [])
                    entries.append({"word": w, "reverse": rev[:4]})
                    for r in rev:
                        if r.lower() != original_text.lower():
                            all_synonyms_set.add(r)
                pos_list.append({
                    "pos": pos_raw,
                    "title": pos_title,
                    "terms": terms[:8],
                    "entries": entries[:6]
                })

        clouds = []

        # ==========================================
        # ХМАРИНКА 1: ГОЛОВНИЙ ПЕРЕКЛАД ТА ВИМОВА
        # ==========================================
        cloud_1 = {
            "type": "main",
            "badge": "★ ГОЛОВНИЙ ПЕРЕКЛАД",
            "title": main_trans,
            "phonetic": f"/{phonetic}/" if phonetic else "",
            "quick_copy": main_trans,
            "alt_terms": []
        }
        # Add quick top alternatives if present
        if pos_list and pos_list[0]["terms"]:
            alts = [t for t in pos_list[0]["terms"] if t.lower() != main_trans.lower()][:3]
            cloud_1["alt_terms"] = alts
        clouds.append(cloud_1)

        # ==========================================
        # ХМАРИНКА 2: ПЕРША ЧАСТИНА МОВИ ТА ВАРІАНТИ
        # ==========================================
        if len(pos_list) > 0:
            first_pos = pos_list[0]
            cloud_2 = {
                "type": "pos",
                "badge": f"💬 {first_pos['title']}",
                "terms": first_pos["terms"][:5],
                "details": []
            }
            for e in first_pos["entries"][:3]:
                if e["reverse"]:
                    cloud_2["details"].append(f"{e['word']} ({', '.join(e['reverse'][:3])})")
            clouds.append(cloud_2)

        # ==========================================
        # ХМАРИНКА 3: ДРУГА ЧАСТИНА МОВИ АБО СИНОНІМИ
        # ==========================================
        if len(pos_list) > 1:
            sec_pos = pos_list[1]
            cloud_3 = {
                "type": "pos",
                "badge": f"⚡ {sec_pos['title']}",
                "terms": sec_pos["terms"][:5],
                "details": []
            }
            for e in sec_pos["entries"][:3]:
                if e["reverse"]:
                    cloud_3["details"].append(f"{e['word']} ({', '.join(e['reverse'][:3])})")
            clouds.append(cloud_3)
        elif all_synonyms_set:
            # Synonyms cloud in English
            cloud_3 = {
                "type": "synonyms",
                "badge": "🔄 АНГЛІЙСЬКІ СИНОНІМИ",
                "terms": list(all_synonyms_set)[:6],
                "details": []
            }
            clouds.append(cloud_3)
        elif dict_data and dict_data.get("meanings"):
            m = dict_data["meanings"][0]
            defs = [d["definition"] for d in m.get("definitions", [])[:2] if "definition" in d]
            cloud_3 = {
                "type": "definition",
                "badge": "📖 ЗНАЧЕННЯ АНГЛІЙСЬКОЮ",
                "terms": defs[:2],
                "details": []
            }
            clouds.append(cloud_3)

        # ==========================================
        # ХМАРИНКА 4: КОНТЕКСТ / МАНХВА ЗВОРОТИ / ПРИКЛАДИ
        # ==========================================
        lower_word = original_text.lower().strip()
        custom_hints = MANHWA_COLLOCATIONS.get(lower_word)

        if custom_hints:
            clouds.append({
                "type": "manhwa",
                "badge": "🗡️ У МАНХВІ ТА КОМІКСАХ",
                "terms": custom_hints[:4],
                "details": []
            })
        elif len(pos_list) > 2:
            third_pos = pos_list[2]
            clouds.append({
                "type": "pos",
                "badge": f"✨ {third_pos['title']}",
                "terms": third_pos["terms"][:4],
                "details": []
            })
        elif dict_data and dict_data.get("meanings"):
            # Check for examples
            examples = []
            for m in dict_data["meanings"]:
                for d in m.get("definitions", []):
                    if d.get("example"):
                        examples.append(d["example"])
            if examples:
                clouds.append({
                    "type": "example",
                    "badge": "💡 ПРИКЛАД ВЖИВАННЯ",
                    "terms": examples[:2],
                    "details": []
                })

        # If we still have fewer than 3 clouds, and there's phrase or synonym data:
        if len(clouds) < 3 and all_synonyms_set:
            clouds.append({
                "type": "synonyms",
                "badge": "🔄 СИНОНІМИ (EN)",
                "terms": list(all_synonyms_set)[:5],
                "details": []
            })

        # If phrase breakdown is useful:
        if len(clouds) < 4 and " " in original_text:
            words = [w.strip() for w in original_text.split() if len(w.strip()) > 1][:4]
            breakdown = []
            for w in words:
                sub_cached = self.get_cached(w)
                if sub_cached:
                    breakdown.append(f"{w} = {sub_cached.get('main', '')}")
                else:
                    breakdown.append(w)
            if breakdown:
                clouds.append({
                    "type": "breakdown",
                    "badge": "🧩 СЛОВА У ВИРАЗІ",
                    "terms": breakdown,
                    "details": []
                })

        # If still only 2 clouds, add a quick help/tip cloud
        if len(clouds) < 3:
            clouds.append({
                "type": "tip",
                "badge": "💡 ПОРАДА",
                "terms": ["Натисніть на будь-яку хмаринку, щоб скопіювати переклад!", "Enter або клік для швидкого перекладу"],
                "details": []
            })

        return {
            "query": original_text,
            "main": main_trans,
            "phonetic": phonetic,
            "audio": audio_url,
            "clouds": clouds[:4]
        }

    def get_word_article(self, text: str) -> Dict[str, Any]:
        """
        Builds a rich learner's dictionary article (Oxford/Cambridge style)
        with headword, phonetic, parts of speech, definitions, examples, 
        and derived/inflected forms (-s, -ed, -ing, noun/adj variants).
        """
        clean_text = text.strip()
        if not clean_text:
            return {"query": text, "cards": []}

        gt_data = self._fetch_google_dict(clean_text)
        dict_data = None

        phonetic = ""
        if "sentences" in gt_data and isinstance(gt_data["sentences"], list):
            for s in gt_data["sentences"]:
                if isinstance(s, dict) and s.get("src_translit"):
                    phonetic = s["src_translit"]
                    break

        # Collect Google POS translations
        pos_ukr_map = {}
        if "dict" in gt_data and isinstance(gt_data["dict"], list):
            for d in gt_data["dict"]:
                p = d.get("pos", "").lower()
                terms = d.get("terms", [])
                if terms:
                    pos_ukr_map[p] = terms[:4]

        # Parse Google Oxford definitions
        defs_by_pos = {}
        if "definitions" in gt_data and isinstance(gt_data["definitions"], list):
            for g_def in gt_data["definitions"]:
                pos = g_def.get("pos", "").lower()
                entries = g_def.get("entry", [])
                pos_entries = []
                for e in entries:
                    gloss = e.get("gloss", "")
                    ex = e.get("example", "")
                    if gloss:
                        item = f"• {gloss}"
                        if ex:
                            item += f"<br>&nbsp;&nbsp;↳ <i>Приклад: \"{ex}\"</i>"
                        pos_entries.append(item)
                if pos_entries:
                    defs_by_pos[pos] = pos_entries

        # Fallback to Free Dictionary definitions if Google didn't have definitions
        if not defs_by_pos and dict_data and dict_data.get("meanings"):
            for m in dict_data["meanings"]:
                pos = m.get("partOfSpeech", "").lower()
                top_defs = []
                for d in m.get("definitions", [])[:2]:
                    d_text = d.get("definition", "")
                    ex = d.get("example", "")
                    if d_text:
                        item = f"• {d_text}"
                        if ex:
                            item += f"<br>&nbsp;&nbsp;↳ <i>Приклад: \"{ex}\"</i>"
                        top_defs.append(item)
                if top_defs:
                    defs_by_pos[pos] = top_defs

        # Phonetic transcription
        phonetic = ""
        if "sentences" in gt_data:
            for s in gt_data["sentences"]:
                if s.get("src_translit"):
                    phonetic = s["src_translit"]
                    break
        if not phonetic and dict_data:
            phonetic = dict_data.get("phonetic", "")

        cards = []
        # Build cards for each POS present in Google dict or definitions
        all_pos_keys = list(dict.fromkeys(list(pos_ukr_map.keys()) + list(defs_by_pos.keys())))
        for pos in all_pos_keys:
            pos_ukr = POS_TRANSLATIONS.get(pos, pos.upper())
            ukr_terms = pos_ukr_map.get(pos, [])
            top_defs = defs_by_pos.get(pos, [])
            if not top_defs and ukr_terms:
                top_defs = [f"• Значення: {', '.join(ukr_terms[:4])}"]

            forms = []
            if pos == "verb":
                base = clean_text.rstrip("e") if clean_text.endswith("e") and not clean_text.endswith("ee") else clean_text
                ed_form = clean_text + "d" if clean_text.endswith("e") else clean_text + "ed"
                ing_form = base + "ing"
                s_form = clean_text + "es" if clean_text.endswith(("s", "sh", "ch", "x", "z")) else clean_text + "s"
                forms = [f"3rd: {s_form}", f"-ed: {ed_form}", f"-ing: {ing_form}"]
            elif pos == "noun":
                pl = clean_text + "es" if clean_text.endswith(("s", "sh", "ch", "x", "z")) else clean_text + "s"
                forms = [f"plural: {pl}"]
            elif pos in ("adjective", "adj"):
                forms = [f"adv: {clean_text}ly", f"-er: {clean_text}er", f"-est: {clean_text}est"]

            card_data = {
                "badge": f"📖 {pos.upper()} • {pos_ukr}",
                "title": f"{clean_text} {f'/{phonetic}/' if phonetic else ''}",
                "translation": ", ".join(ukr_terms) if ukr_terms else "",
                "definitions": top_defs[:3],
                "forms": forms,
                "synonyms": [],
                "word": clean_text,
                "pos": pos
            }
            cards.append(card_data)

        if not cards:
            main_res = self.lookup(clean_text)
            main_t = main_res.get("main", "")
            cards.append({
                "badge": "📖 СЛОВНИКОВА СТАТТЯ",
                "title": f"{clean_text} {f'/{phonetic}/' if phonetic else ''}",
                "translation": main_t,
                "definitions": [f"• Переклад: {main_t}"],
                "forms": [f"-ed: {clean_text}ed", f"-ing: {clean_text}ing", f"-s: {clean_text}s"],
                "synonyms": [],
                "word": clean_text,
                "pos": "word"
            })

        return {
            "query": clean_text,
            "phonetic": phonetic,
            "cards": cards
        }

