"""
Batch Translator CLI for Light Novels into Slovak Language (B1-B2 preparation).
Translates EPUB, DOCX, and TXT files using Google Gemini API (with strict Slovak grammar prompts)
or Free Google Translate as a fallback.

Moves original source files into archive/ and outputs translated files into novel_library/.
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from typing import List, Optional

# Project root path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config import config
except ImportError:
    config = None

try:
    from manhwa_reader.novel_reader.parsers.novel_parser import EpubParser, DocxParser
except ImportError:
    try:
        from novel_reader.parsers.novel_parser import EpubParser, DocxParser
    except ImportError:
        EpubParser = None
        DocxParser = None


def chunk_text(text: str, max_words: int = 600) -> List[str]:
    """Splits chapter text into logical semantic chunks.
    Ensures chunks don't exceed max_words even if there are giant monolithic paragraphs."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_count = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        words = p.split()
        p_len = len(words)

        # If a single paragraph is larger than max_words, subdivide it by sentences or word blocks
        if p_len > max_words:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_count = 0
            # Split giant paragraph into pieces of max_words
            for i in range(0, p_len, max_words):
                sub_part = " ".join(words[i:i + max_words])
                chunks.append(sub_part)
            continue

        if current_count + p_len > max_words and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p]
            current_count = p_len
        else:
            current_chunk.append(p)
            current_count += p_len

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks


def translate_with_gemini(text_chunk: str, api_key: str, model_name: str = "gemini-flash-lite-latest") -> str:
    """Translates chunk to academic literary Slovak using Gemini API via direct REST."""
    import requests

    system_instruction = (
        "Si profesionálny prekladateľ kníh a fantasy noviel do slovenského jazyka. "
        "Prelož nasledujúci text do čistej, gramaticky správnej a prirodzenej slovenčiny (úroveň B2-C1). "
        "Prísne dbaj na správne pády (genitív, datív, akuzatív, lokál, inštrumentál), "
        "zhodu rodu a čísla podstatných a prídavných mien, a prirodzený slovosled. "
        "Zachovaj odseky a formátovanie. Vráť VÝHRADNE hotový slovenský preklad bez akýchkoľvek vlastných komentárov či úvodov."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text_chunk}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {"temperature": 0.25}
    }
    headers = {"Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code == 200:
        cands = resp.json().get("candidates", [])
        if cands:
            return cands[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    elif resp.status_code == 429:
        raise RuntimeError("Gemini Rate Limit (429 Too Many Requests)")
    raise RuntimeError(f"Gemini API Error [{resp.status_code}]: {resp.text[:200]}")


def translate_with_deeplx(text_chunk: str, target_lang: str = "SK", source_lang: str = "EN") -> str:
    """Translates text chunk using local DeepLX service on port 1188.
    Automatically handles DeepLX 1500-char limit by subdividing into safe slices."""
    import requests

    ensure_deeplx_running()
    url = "http://127.0.0.1:1188/translate"

    # DeepLX free web endpoint has a 1500 characters limit per single request
    if len(text_chunk) > 1200:
        parts = []
        words = text_chunk.split()
        sub = []
        c_len = 0
        for w in words:
            if c_len + len(w) > 1000:
                parts.append(" ".join(sub))
                sub = [w]
                c_len = len(w)
            else:
                sub.append(w)
                c_len += len(w) + 1
        if sub:
            parts.append(" ".join(sub))

        res_list = []
        for p in parts:
            res_list.append(translate_with_deeplx(p, target_lang=target_lang, source_lang=source_lang))
            time.sleep(0.2)
        return " ".join(res_list)

    resp = requests.post(url, json={
        "text": text_chunk,
        "source_lang": source_lang,
        "target_lang": target_lang
    }, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data"):
            return str(data["data"]).strip()
    raise RuntimeError(f"DeepLX Error [{resp.status_code}]: {resp.text[:200]}")


def translate_with_google_free(text_chunk: str, target_lang: str = "sk") -> str:
    """Fallback translation using free google translation endpoint with safe chunk slicing."""
    import urllib.request
    import urllib.parse
    import json

    # Google GET single query has URL length limits; slice into ~1500 chars if needed
    if len(text_chunk) > 2000:
        parts = []
        words = text_chunk.split()
        sub = []
        c_len = 0
        for w in words:
            if c_len + len(w) > 1500:
                parts.append(" ".join(sub))
                sub = [w]
                c_len = len(w)
            else:
                sub.append(w)
                c_len += len(w) + 1
        if sub:
            parts.append(" ".join(sub))
        
        res_list = []
        for p in parts:
            res_list.append(translate_with_google_free(p, target_lang=target_lang))
            time.sleep(0.3)
        return " ".join(res_list)

    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q=" + urllib.parse.quote(text_chunk)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode('utf-8'))
        translated = "".join(part[0] for part in data[0] if part[0])
        return translated


def process_novel_file(
    file_path: Path,
    output_dir: Path,
    archive_dir: Path,
    engine: str = "deeplx",
    api_key: Optional[str] = None
):
    print(f"\n==================================================")
    print(f"📖 Обробка файлу: {file_path.name}")
    print(f"⚙️ Рушій перекладу: {engine.upper()}")
    print(f"==================================================")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    suffix = file_path.suffix.lower()
    content = ""
    
    if suffix in [".docx", ".txt"]:
        content = DocxParser.extract_text(file_path) if DocxParser else file_path.read_text(encoding="utf-8", errors="ignore")
    elif suffix == ".epub":
        if EpubParser:
            chapters = EpubParser.extract_chapters(file_path)
            content = "\n\n".join([f"=== {ch['title']} ===\n\n{ch['content']}" for ch in chapters])
        else:
            print("⚠️ Помилка: EpubParser недоступний.")
            return

    if not content.strip():
        print("⚠️ Помилка: Не вдалося витягти текст із файлу.")
        return

    # Max words: 500 words per chunk for high reliability & zero token truncation
    chunks = chunk_text(content, max_words=500)
    print(f"📦 Текст розбито на {len(chunks)} фрагментів (середній розмір ~300-500 слів).")

    # Use multi-threading for DeepLX (4 concurrent workers = 4-5x speedup)
    # Gemini stays sequential with 4.5s delay due to strict 15 RPM free tier limit
    translated_parts = [None] * len(chunks)

    if engine == "deeplx":
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print("⚡ Режим паралельного перекладу: 4 потоки одночасно!")
        completed_count = 0

        def translate_single(index, text):
            try:
                res = translate_with_deeplx(text, target_lang="SK")
                return index, res, None
            except Exception as e:
                try:
                    res = translate_with_google_free(text, target_lang="sk")
                    return index, res, "Google fallback"
                except Exception as e2:
                    return index, text, f"Error: {e2}"

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(translate_single, i, ch) for i, ch in enumerate(chunks)]
            for fut in as_completed(futures):
                idx, res, note = fut.result()
                translated_parts[idx] = res
                completed_count += 1
                status = f" [{note}]" if note else ""
                print(f"⏳ [{completed_count}/{len(chunks)}] Готово фрагмент #{idx+1}{status}")

    else:
        for idx, ch in enumerate(chunks):
            word_count = len(ch.split())
            print(f"⏳ [{idx+1}/{len(chunks)}] Переклад ({word_count} слів)... ", end="", flush=True)
            try:
                if engine == "gemini" and api_key:
                    tr_part = translate_with_gemini(ch, api_key)
                    # Google Gemini Free Tier limit: strict 15 RPM => 4.5 seconds sleep between calls
                    time.sleep(4.5)
                else:
                    tr_part = translate_with_google_free(ch, target_lang="sk")
                    time.sleep(0.5)
                translated_parts[idx] = tr_part
                print("[ГОТОВО]")
            except Exception as e:
                print(f"[ПОМИЛКА: {e}]. Спроба резервного Google...")
                try:
                    tr_part = translate_with_google_free(ch, target_lang="sk")
                    translated_parts[idx] = tr_part
                    print("[РЕЗЕРВ УСПІШНО]")
                    time.sleep(0.5)
                except Exception as e2:
                    print(f"[ФАТАЛЬНА ПОМИЛКА: {e2}]. Збережено оригінал фрагмента.")
                    translated_parts[idx] = ch

    full_translated = "\n\n".join(translated_parts)
    
    # Clean title name: e.g. "The Beginning After the End_ Book 1..." -> "The Beginning After the End [SK]"
    raw_name = file_path.stem
    # If the file was inside a folder (e.g. library/novels_library/Title/...), use parent folder name
    if file_path.parent.name not in ["archive", "Novels_Slovak", "library"]:
        base_title = file_path.parent.name
        # Remove any existing [OTHER] / [EN] tag
        clean_base = re.sub(r'\[(OTHER|EN|RAW|UA|SK)\]', '', base_title).strip()
        title_folder_name = f"{clean_base} [SK]"
    else:
        # Generate base from filename
        clean_stem = re.sub(r'[_]+', ' ', raw_name)
        clean_stem = re.sub(r'\[(OTHER|EN|RAW|UA|SK)\]', '', clean_stem).strip()
        title_folder_name = f"{clean_stem} [SK]"

    target_title_dir = output_dir / title_folder_name
    target_title_dir.mkdir(parents=True, exist_ok=True)

    out_file = target_title_dir / f"{raw_name}_SK.txt"
    out_file.write_text(full_translated, encoding="utf-8")
    print(f"\n✅ Переклад успішно збережено у Бібліотеку Новел:")
    print(f"   📁 {target_title_dir}")
    print(f"   📄 {out_file.name}")

    # Optional archiving with user confirmation
    print("\n📦 Бажаєте перемістити оригінал в архів?")
    ans = input("   Перемістити вихідний файл/папку в archive/? [y/N]: ").strip().lower()
    if ans in ['y', 'yes', 'так', 'т']:
        if file_path.parent.name not in ["archive", "Novels_Slovak", "library"]:
            # Move the entire original title folder
            target_archive_dir = archive_dir / file_path.parent.name
            try:
                shutil.move(str(file_path.parent), str(target_archive_dir))
                print(f"📦 Папку тайтлу переміщено в архів: {target_archive_dir}")
            except Exception as e:
                print(f"⚠️ Не вдалося перемістити папку в архів: {e}")
        else:
            target_archive = archive_dir / file_path.name
            try:
                shutil.move(str(file_path), str(target_archive))
                print(f"📦 Вихідний файл переміщено в архів: {target_archive}")
            except Exception as e:
                print(f"⚠️ Не вдалося перемістити файл в архів: {e}")
    else:
        print("ℹ️ Оригінал залишено на місці без змін.")


_deeplx_process = None

def ensure_deeplx_running():
    """Ensure local DeepLX service is running on 127.0.0.1:1188."""
    global _deeplx_process
    try:
        r = requests.get("http://127.0.0.1:1188", timeout=1)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    deeplx_bin = PROJECT_ROOT / "bin" / "deeplx.exe"
    if deeplx_bin.exists():
        try:
            import subprocess
            _deeplx_process = subprocess.Popen(
                [str(deeplx_bin), "-p", "1188"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1.5)
            return True
        except Exception as e:
            print(f"Не вдалося запустити DeepLX: {e}")
    return False


def main():
    print("=" * 60)
    print("  🇸🇰 SLOVAK NOVEL BATCH TRANSLATOR (Dark Fantasy Edition)")
    print("=" * 60)

    key = config.get("gemini_api_key", "") if config else ""
    if not key:
        key = os.environ.get("GEMINI_API_KEY", "")

    # Ensure DeepLX is online
    ensure_deeplx_running()

    parser = argparse.ArgumentParser(description="Batch Translate Novels into Slovak")
    parser.add_argument("--input", "-i", type=str, help="Шлях до файлу або папки для перекладу")
    parser.add_argument("--engine", "-e", choices=["deeplx", "gemini", "google"], default=None, help="Рушій перекладу (deeplx / gemini / google)")
    args = parser.parse_args()

    input_path_str = args.input
    if not input_path_str:
        input_path_str = input("\nВведіть шлях до файлу/папки новели (EPUB/DOCX/TXT): ").strip().strip('"')

    if not input_path_str:
        print("Файл не вказано. Вихід.")
        return

    p = Path(input_path_str)
    if not p.exists():
        print(f"Шлях не існує: {p}")
        return

    # Engine selection prompt if not explicitly provided via flags
    engine = args.engine
    if not engine:
        print("\nОберіть рушій для перекладу:")
        print(" [1] DeepLX (Локальний DeepL, безлімітний, швидкий)")
        print(" [2] Gemini AI (3.1 Flash-Lite, ліміт 15 запитів/хв, літературний стиль)")
        print(" [3] Google Translate (Безкоштовний резервний)")
        choice = input("Ваш вибір [1/2/3] (за замовчуванням 1): ").strip()
        if choice == "2":
            engine = "gemini"
        elif choice == "3":
            engine = "google"
        else:
            engine = "deeplx"

    if engine == "gemini" and not key:
        print("⚠️ УВАГА: Gemini API Key не знайдено у config.json! Перемикаємо на DeepLX.")
        engine = "deeplx"

    # Destinations: save directly into novels_library
    out_dir = PROJECT_ROOT / "manhwa_reader" / "library" / "novels_library"
    archive_dir = PROJECT_ROOT / "archive"

    files_to_process = []
    if p.is_file():
        files_to_process.append(p)
    elif p.is_dir():
        files_to_process.extend([f for f in p.iterdir() if f.suffix.lower() in [".epub", ".docx", ".txt"]])

    print(f"\nЗнайдено файлів для обробки: {len(files_to_process)}")
    for f in files_to_process:
        process_novel_file(f, out_dir, archive_dir, engine=engine, api_key=key)

    print("\n🎉 Всі файли успішно перекладено та заархівовано!")


if __name__ == "__main__":
    main()
