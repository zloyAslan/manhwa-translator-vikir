"""
Title Classifier and Setting Profiler for Manhwa Reader.
Analyzes the first chapter of downloaded manhwas in background using Gemini Flash-Lite.
Extracts: genre, setting_pack, historical/tech era, audio mood tags, and forbidden elements.

Rate-limited to <= 1 request per minute to protect API quotas.
Saves metadata to title_profiles.json in library/config directory.
"""

import os
import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger("title_classifier")

DEFAULT_PACKS = [
    "medieval_fantasy",
    "system_murim",
    "magic_academy",
    "modern_school_romance",
    "cyberpunk_scifi",
    "dark_fantasy_horror",
    "industrial_dieselpunk",
    "historical_oriental"
]


class TitleClassifier:
    """
    Background worker that profiles manhwa titles based on Chapter 1 inspection.
    """
    def __init__(self, api_key: str = "", profiles_path: Optional[Path] = None):
        self.api_key = api_key.strip()
        self.model_name = "gemini-3.1-flash-lite"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.upload_url = "https://generativelanguage.googleapis.com/upload/v1beta/files"

        base_dir = Path(__file__).parent.parent.resolve()
        self.profiles_path = profiles_path or (base_dir / "title_profiles.json")
        self.profiles: Dict[str, Dict[str, Any]] = self._load_profiles()

        # Rate limiting and queue
        self._lock = threading.Lock()
        self._queue: List[Path] = []
        self._is_running = False
        self._last_request_time: float = 0.0
        self._cooldown_seconds: float = 62.0  # Safe >= 1 minute limit

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        if self.profiles_path.exists():
            try:
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"Could not load profiles from {self.profiles_path}: {e}")
        return {}

    def _save_profiles(self):
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save title profiles: {e}")

    def get_title_profile(self, title_name: str) -> Optional[Dict[str, Any]]:
        """Returns existing profile if verified."""
        with self._lock:
            return self.profiles.get(title_name)

    def queue_title_analysis(self, manhwa_dir: Path, priority_first: bool = False, force: bool = False):
        """Adds a title directory to background classification queue."""
        manhwa_dir = Path(manhwa_dir)
        title_name = manhwa_dir.name
        with self._lock:
            if force and title_name in self.profiles:
                del self.profiles[title_name]
                self._save_profiles()
            elif not force and title_name in self.profiles and self.profiles[title_name].get("verified"):
                return
            # Prevent duplicate queue entries
            if any(p.name == title_name for p in self._queue):
                return
            if priority_first:
                self._queue.insert(0, manhwa_dir)
            else:
                self._queue.append(manhwa_dir)

        self._ensure_worker_running()

    def scan_unclassified_titles(self, library_dir: Path):
        """Scans library directory for titles that have not yet been classified."""
        library_dir = Path(library_dir)
        if not library_dir.exists():
            return

        for folder in library_dir.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                with self._lock:
                    is_done = folder.name in self.profiles and self.profiles[folder.name].get("verified")
                if not is_done:
                    self.queue_title_analysis(folder)

    def _ensure_worker_running(self):
        with self._lock:
            if not self._is_running:
                self._is_running = True
                t = threading.Thread(target=self._worker_loop, daemon=True, name="TitleClassifierWorker")
                t.start()

    def _worker_loop(self):
        logger.info("TitleClassifier background worker started.")
        while True:
            target_dir = None
            with self._lock:
                if not self._queue:
                    self._is_running = False
                    logger.info("TitleClassifier worker idle (queue empty).")
                    break
                target_dir = self._queue.pop(0)

            # Wait cooldown before next request (not more than 1 per minute)
            elapsed = time.time() - self._last_request_time
            if elapsed < self._cooldown_seconds:
                sleep_needed = self._cooldown_seconds - elapsed
                time.sleep(sleep_needed)

            if not self.api_key:
                logger.debug("Gemini API key is not configured. Postponing title analysis.")
                time.sleep(5)
                continue

            try:
                self._analyze_title(target_dir)
            except Exception as e:
                logger.error(f"Error classifying {target_dir.name}: {e}")
            finally:
                self._last_request_time = time.time()

    def _find_first_chapter_pdf(self, manhwa_dir: Path) -> Optional[Path]:
        """Finds chapter 1 or the earliest available chapter PDF."""
        # 1. Search inside chapter subdirectories
        sub_pdfs = list(manhwa_dir.rglob("*.pdf"))
        if not sub_pdfs:
            return None

        # Sort by chapter number heuristics
        def _sort_key(p: Path):
            import re
            m = re.search(r'(\d+)', p.stem)
            return int(m.group(1)) if m else 9999

        sub_pdfs.sort(key=_sort_key)
        return sub_pdfs[0]

    def _analyze_title(self, manhwa_dir: Path):
        title_name = manhwa_dir.name
        pdf_path = self._find_first_chapter_pdf(manhwa_dir)
        if not pdf_path or not pdf_path.exists():
            logger.info(f"No PDF found for title '{title_name}'. Skipping.")
            return

        file_size = pdf_path.stat().st_size
        logger.info(f"Classifying title '{title_name}' using sample chapter {pdf_path.name} ({file_size / (1024*1024):.1f} MB)...")

        # Upload first chapter via Files API
        upload_target = f"{self.upload_url}?key={self.api_key}"
        upload_headers = {
            "X-Goog-Upload-Command": "start, upload, finalize",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": "application/pdf",
            "Content-Type": "application/pdf"
        }

        with open(pdf_path, "rb") as f:
            data = f.read()

        up_resp = requests.post(upload_target, headers=upload_headers, data=data, timeout=90)
        if up_resp.status_code != 200:
            logger.warning(f"Classification upload failed ({up_resp.status_code}): {up_resp.text[:200]}")
            return

        file_info = up_resp.json().get("file", {})
        file_uri = file_info.get("uri")
        if not file_uri:
            return

        prompt = f"""
You are a webtoon/manga literary scholar, worldbuilding analyst, and sound director.
Analyze this manhwa chapter sample to classify the world, genre, and setting rules for acoustic design.

Select the BEST matching 'setting_pack' from this list:
{json.dumps(DEFAULT_PACKS)}

Extract:
1. "setting_pack": Exactly one matching string from the list above.
2. "primary_genre": Main genre (e.g. "Dark Medieval Fantasy", "Murim Cultivation", "Modern Romance", "Cyberpunk").
3. "era": Time period or world type (e.g. "Medieval European", "Ancient China", "Modern 21st Century", "Far Future").
4. "forbidden_elements": List of 4-8 things that MUST NEVER appear in this world's sound design (e.g. ["cars", "smartphones", "lasers", "modern_guns"]).
5. "recommended_instruments": 3-5 typical instruments (e.g. ["lute", "orchestral strings", "celtic flute"]).
6. "summary": A brief 1-sentence description of the story setting.

Output STRICT JSON only:
{{
  "setting_pack": "medieval_fantasy",
  "primary_genre": "Dark Medieval Fantasy",
  "era": "Medieval European",
  "forbidden_elements": ["cars", "cellphones", "modern_sirens", "electronic_beeps", "automatic_rifles"],
  "recommended_instruments": ["lute", "cello", "orchestral_drums", "flute"],
  "summary": "A grim medieval fantasy tale of swordsmen, beasts, and dungeons."
}}
"""
        req_url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"file_data": {"mime_type": "application/pdf", "file_uri": file_uri}},
                    {"text": prompt}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        resp = requests.post(req_url, json=payload, timeout=60)
        if resp.status_code != 200:
            logger.warning(f"Gemini classification response error ({resp.status_code}): {resp.text[:200]}")
            return

        result_text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if result_text:
            try:
                profile_data = json.loads(result_text)
                profile_data["verified"] = True
                profile_data["classified_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

                with self._lock:
                    self.profiles[title_name] = profile_data
                    self._save_profiles()

                logger.info(f"Successfully classified '{title_name}' -> Setting: {profile_data.get('setting_pack')} ({profile_data.get('primary_genre')})")
            except Exception as e:
                logger.error(f"Failed to parse classification JSON: {e}")
