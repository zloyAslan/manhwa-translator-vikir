"""
AI Sound Analyzer for Manhwa & Novel Reader (Dark Fantasy Edition).
Analyzes complete chapter PDFs using Google Gemini Vision API to generate
precise atmospheric and sound effect cues broken down by page and vertical fractions (0.0, 0.25, 0.5, 0.75).

Features:
- 100% Chapter-level caching: saves sound_timeline.json right inside the chapter folder.
- Native full PDF upload (no manual page slicing needed).
- Compact JSON payload to ensure lightning-fast responses (~2-4 seconds) and minimal token usage.
- Extensive, structured vocabulary pool for Ambients (m), Sound Effects (s), and Character Tones (c).
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger("ai_sound_analyzer")

MOOD_POOL_DEFAULT = [
    "cave", "dungeon", "forest", "rain", "storm", "city", "tavern",
    "ruins", "library", "battlefield", "snow_mountain", "ocean_beach",
    "palace", "airplane_flight", "mystic_sanctuary", "silence"
]

SFX_POOL_DEFAULT = [
    "horse_whinny", "sword_clash", "heavy_strike", "magic_cast", "footsteps",
    "door_creak", "monster_roar", "body_fall", "gasp_shock", "laughter",
    "heartbeat", "rain_splash", "wind_gust", "page_turn", "explosion", "none"
]

TONE_POOL = [
    "epic", "grim", "tense", "peaceful", "humorous", "romantic", "melancholy"
]

TIMELINE_FILENAME = "sound_timeline.json"


def scan_layered_sound_pools(sounds_dir: Path, setting_pack: Optional[str] = None) -> tuple[list[str], list[str], list[str]]:
    """
    Categorizes available audio tracks into 3 distinct layers for AI sound design:
    1. bg_pool: Background score/music (orchestral, synths, emotional tracks)
    2. amb_pool: Environmental atmosphere (wind, tavern, cave, school noise, rain)
    3. sfx_pool: Immediate sound effects and action loops (swords, hits, run, laughs, meme sounds)

    Supports both legacy flat layout (ambient/, sfx/, ui/) AND new modular layout:
    - sounds/core/ (universal bg, amb, sfx)
    - sounds/packs/<setting_pack>/ (genre-specific bg, amb, sfx)
    - sounds/meme/ (neutral & meme sounds)
    - sounds/my_sounds/ (user custom tracks)
    """
    import re
    bg_candidates = set(["silence"])
    amb_candidates = set(["silence"])
    sfx_candidates = set(["none"])

    def _add_file(f: Path, target_layer: Optional[str] = None):
        if not f.is_file() or f.suffix.lower() not in [".mp3", ".ogg", ".wav"]:
            return
        base = re.sub(r'_\d+$', '', f.stem).strip().lower()
        if not base or base.startswith("test_sound"):
            return

        layer = target_layer
        if not layer:
            # Detect layer from directory path name
            parts = [p.lower() for p in f.parts]
            if "bg" in parts or "ui" in parts:
                layer = "bg"
            elif "amb" in parts or "ambient" in parts:
                layer = "amb"
            elif "sfx" in parts or "meme" in parts:
                layer = "sfx"
            else:
                # Heuristic guess based on name
                if any(k in base for k in ["music", "theme", "melody", "piano", "orchestra", "sad", "epic", "acoustic", "fun"]):
                    layer = "bg"
                else:
                    layer = "amb"

        if layer == "bg":
            bg_candidates.add(base)
        elif layer == "amb":
            amb_candidates.add(base)
        elif layer == "sfx":
            sfx_candidates.add(base)

    # 1. Scan CORE (Universal pool for all settings)
    core_dir = sounds_dir / "core"
    if core_dir.exists():
        for item in core_dir.rglob("*"):
            _add_file(item)

    # 2. Scan SPECIFIC PACK (or all active packs if no setting specified)
    packs_dir = sounds_dir / "packs"
    if packs_dir.exists():
        if setting_pack and (packs_dir / setting_pack).exists():
            for item in (packs_dir / setting_pack).rglob("*"):
                _add_file(item)
        else:
            # If no setting pack specified or not found, scan all packs
            for item in packs_dir.rglob("*"):
                _add_file(item)

    # 3. Scan MEME folder
    meme_dir = sounds_dir / "meme"
    if meme_dir.exists():
        for item in meme_dir.rglob("*"):
            _add_file(item, target_layer="sfx")

    # 4. Scan MY_SOUNDS & legacy folders for backward compatibility
    for legacy_name in ["ambient", "sfx", "ui", "my_sounds"]:
        legacy_dir = sounds_dir / legacy_name
        if legacy_dir.exists():
            for item in legacy_dir.rglob("*"):
                _add_file(item)

    return sorted(list(bg_candidates)), sorted(list(amb_candidates)), sorted(list(sfx_candidates))


def scan_available_sound_pools(sounds_dir: Path) -> tuple[list[str], list[str]]:
    """Legacy compatibility helper."""
    bg, amb, sfx = scan_layered_sound_pools(sounds_dir)
    return sorted(list(set(bg + amb))), sfx


class AISoundAnalyzer:
    """
    Coordinates PDF analysis and timeline generation via Gemini API.
    """
    def __init__(self, api_key: str = "", model_name: str = "gemini-3.5-flash-lite", sounds_dir: Optional[Path] = None):
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        base_dir = Path(__file__).parent.parent.resolve()  # manhwa_reader folder
        self.sounds_dir = sounds_dir or (base_dir / "sounds")

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def set_sounds_dir(self, new_dir: Path):
        """Updates root sound directory for AI mood/sfx pool detection."""
        self.sounds_dir = Path(new_dir)

    def get_or_analyze_chapter(
        self,
        chapter_dir: Path,
        pdf_path: Optional[Path] = None,
        force_reanalyze: bool = False,
        title_profile: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves cached timeline from chapter folder if available.
        Otherwise, reads chapter PDF, analyzes with Gemini, and saves to cache.
        Strictly targets chapter_dir (e.g. library/Title/chapter_001/).
        """
        chapter_dir = Path(chapter_dir)
        cache_file = chapter_dir / TIMELINE_FILENAME

        # 1. Fast Cache Hit
        if not force_reanalyze and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(f"Loaded cached sound timeline from {cache_file.name} ({len(data)} cues)")
                        return data
            except Exception as e:
                logger.warning(f"Failed to read cache file {cache_file}: {e}")

        # 2. Locate PDF inside chapter_dir or alongside
        target_pdf = pdf_path
        if not target_pdf or not target_pdf.exists():
            pdfs = list(chapter_dir.glob("*.pdf"))
            if pdfs:
                target_pdf = pdfs[0]

        # Check if parent has matching chapter PDF
        if not target_pdf or not target_pdf.exists():
            from manhwa_reader.downloader import extract_chapter_number
            target_ch_num = extract_chapter_number(chapter_dir.name)
            for p in chapter_dir.parent.glob("*.pdf"):
                if extract_chapter_number(p.stem) == target_ch_num:
                    target_pdf = p
                    break

        if not target_pdf or not target_pdf.exists():
            logger.info(f"No PDF found for {chapter_dir}. Generating default ambient timeline.")
            default_timeline = self._generate_default_timeline()
            self._save_cache(cache_file, default_timeline)
            return default_timeline

        # 3. Check API Key
        if not self.api_key:
            logger.warning("Gemini API Key is not set. Generating default ambient timeline.")
            default_timeline = self._generate_default_timeline()
            self._save_cache(cache_file, default_timeline)
            return default_timeline

        # Auto-detect title profile if not provided
        if not title_profile:
            try:
                from .title_classifier import TitleClassifier
                classifier = TitleClassifier(self.api_key)
                title_profile = classifier.get_title_profile(chapter_dir.parent.name)
            except Exception:
                pass

        # 4. Perform AI Analysis
        try:
            timeline = self._analyze_pdf_with_gemini(target_pdf, title_profile=title_profile)
            if timeline:
                self._save_cache(cache_file, timeline)
                return timeline
        except Exception as e:
            logger.error(f"AI Sound Analysis failed: {e}")

        default_timeline = self._generate_default_timeline()
        self._save_cache(cache_file, default_timeline)
        return default_timeline

    def _analyze_pdf_with_gemini(self, pdf_path: Path, title_profile: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Uploads chapter PDF using Google Files API (reliable, fast, no base64 size limits)
        and sends structured prompt to gemini-3.1-flash-lite.
        Takes setting rules and forbidden audio elements into account.
        """
        file_size = pdf_path.stat().st_size
        logger.info(f"Uploading PDF {pdf_path.name} ({file_size / (1024*1024):.1f} MB) via Google Files API...")

        upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={self.api_key}"
        upload_headers = {
            "X-Goog-Upload-Command": "start, upload, finalize",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": "application/pdf",
            "Content-Type": "application/pdf"
        }

        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        up_resp = requests.post(upload_url, headers=upload_headers, data=pdf_data, timeout=90)
        if up_resp.status_code != 200:
            raise RuntimeError(f"Files API upload failed ({up_resp.status_code}): {up_resp.text[:300]}")

        file_info = up_resp.json().get("file", {})
        file_uri = file_info.get("uri")
        if not file_uri:
            raise RuntimeError("Files API returned no file URI.")

        # Build setting instructions if profile is available
        setting_context = ""
        setting_pack = None
        if title_profile:
            setting_pack = title_profile.get("setting_pack", "medieval_fantasy")
            primary_genre = title_profile.get("primary_genre", "Fantasy")
            era = title_profile.get("era", "Unknown")
            forbidden = title_profile.get("forbidden_elements", [])
            setting_context = f"""
STRICT WORLD SETTING RULES:
- Genre / Universe: {primary_genre} ({era})
- Setting Pack: {setting_pack}
- FORBIDDEN AUDIO ELEMENTS: {json.dumps(forbidden)}
  NEVER trigger any sound that belongs to modern or anachronistic times! Respect the world's era strictly.
"""

        # Scan distinct 3-layer pools filtered by setting_pack + core + meme
        bg_pool, amb_pool, sfx_pool = scan_layered_sound_pools(self.sounds_dir, setting_pack=setting_pack)

        prompt = f"""
You are an award-winning anime and webtoon sound director, Foley master, and musical composer.
Analyze this entire manhwa chapter PDF and compose a rich, multi-layered cinematic soundscape.
{setting_context}
CRITICAL ARCHITECTURE: 3 SIMULTANEOUS SOUND LAYERS
A great soundtrack is a blend of 3 distinct elements playing together in harmony:

1. LAYER 1: "bg" (Background Score / Music):
   - Sets the macro emotional theme and spans several pages without stopping.
   - Kept subtle so reading is comfortable: "bg_vol" usually 0.20 to 0.40.
   - Available tracks: {json.dumps(bg_pool)}
   - USAGE GUIDELINES:
     * Grand royal banquet / noble ballroom / aristocratic assembly -> "legendary-kingdom-music-rising-empire" (vol: 0.35-0.45).
     * Noble estate interior, study room, magic training, or mystery -> "magic_fantasy" or "fantasy-ambient" (vol: 0.25-0.35).
     * Beautiful princess portraits, blooming gardens, flowers, gentle romantic or poignant dialogues -> "desert_in_bloom", "magical-forest-instrumental-flute-strings-melody", or "ancient_celtic_music" (vol: 0.25-0.35).
     * Underground dungeon, grim dungeon descent, or lethal monster encounter -> "nto-the-darkness-cello-version-long" (vol: 0.30-0.40).
     * Lively medieval tavern / celebration -> "by-the-rafters-glow-full-version-medieval-tavern-music-rpg-game" (vol: 0.35-0.45).
     * High suspense or eerie silence -> "silence".

2. LAYER 2: "amb" (Scene Environmental Acoustic):
   - Physical acoustic space where the characters are physically located, layered right on top of the music.
   - Kept balanced: "amb_vol" usually 0.35 to 0.60.
   - Available ambients: {json.dumps(amb_pool)}
   - USAGE GUIDELINES:
     * CAVE / UNDERGROUND / MONSTER LAIR: When characters enter a cave or face monsters underground -> use "cave" or "dungeon" (vol: 0.50-0.65).
     * Study room or resting by a hearth -> "fireplace" (vol: 0.50).
     * Ballroom or lively assembly -> "crowd" (vol: 0.40-0.50).
     * Nature / woods / forest -> "forest" or "movements_in_forest" (vol: 0.40-0.55).
     * Outdoor trees or serene garden -> "birds_voices" (vol: 0.40).
     * Military mobilization / army camp -> "military_camp" or "barrack" (vol: 0.45).
     * Ominous atmosphere / ruins / crows circling -> "crows" (vol: 0.45).
     * Heavy rain / thunder -> "rain" or "storm" (vol: 0.50-0.65).
     * If entering a soundproof room or when ambiance should stop -> "none" or "silence".

3. LAYER 3: "sfx" (Dynamic Action, Monster Events, Multi-SFX Foley & Accents):
   - Immediate actions and visual beats that occur on specific panels or quarter-pages.
   - MULTI-SFX & FOLEY LAYERING:
     * "sfx" CAN CONTAIN MULTIPLE SIMULTANEOUS SOUNDS SEPARATED BY COMMAS!
     * For example: "neighing,sword_clash" (horse neighing while sword strikes), "monster_roar,heavy_strike", "war_drums,gallop", or "scream,sword_clash".
     * When multiple sounds occur simultaneously in a dramatic clash, combine them via commas: e.g. "sfx": "neighing,sword_clash".
   - "sfx_vol": 0.40 to 0.85 (subtle smirks/whispers at 0.40-0.50, heavy strikes/explosions at 0.85).
   - "sfx_mode":
     * "one_shot": impacts or momentary cues that trigger once (even if comma-separated like "neighing,sword_clash").
     * "loop_until_next": sustained continuous actions (e.g. "gallop", "run", "war_drums").
   - HOW TO SUSTAIN, COMBINE, OR CANCEL CONTINUOUS ACTION:
     * While horse gallops: "sfx": "gallop", "sfx_mode": "loop_until_next".
     * At moment of impact during the gallop: emit "sfx": "neighing,sword_clash" ("one_shot"). The engine layers the clash and neigh on top, or seamlessly shifts into battle drums.
     * When action ceases: set "sfx": "none" or "sfx_mode": "one_shot". The loop will cleanly fade out.

SPECIFIC VISUAL & SCENE RULES:
- MONSTERS & DRAGONS: When monsters, gargoyles, or dragons appear (e.g. red flying monsters, dark beasts in caves) -> use "amb": "cave", "bg": "nto-the-darkness-cello-version-long", and trigger "sfx": "monster_roar" or "monster_roar,heartbeat"!
- BATTLEFIELD CLASHES: When mounted knights or warriors charge into battle -> use "sfx": "gallop,war_drums" or "sword_clash,neighing".
- DREAD & SHOCK: When a character is frozen in fear, terrified, or sensing sudden danger -> trigger "sfx": "heartbeat" (vol: 0.60-0.75).
- CHARACTER EXPRESSIONS & VILLAIN SMIRKS: When a character has a cunning smirk, dark smile, or smug grin -> trigger "sfx": "male_laugh" (vol: 0.50).
- NO MODERN SOUNDS: NEVER use "city" or car traffic in a medieval fantasy manhwa!

OUTPUT FORMAT:
Output ONLY a valid JSON array of objects without Markdown formatting or markdown backticks:
[
  {{
    "p": 1,
    "f": 0,
    "bg": "nto-the-darkness-cello-version-long",
    "bg_vol": 0.35,
    "amb": "cave",
    "amb_vol": 0.55,
    "sfx": "none",
    "sfx_vol": 0.0,
    "sfx_mode": "one_shot",
    "d": "entering dark glowing cave with monsters"
  }},
  {{
    "p": 2,
    "f": 2,
    "bg": "nto-the-darkness-cello-version-long",
    "bg_vol": 0.35,
    "amb": "cave",
    "amb_vol": 0.55,
    "sfx": "monster_roar,heavy_strike",
    "sfx_vol": 0.85,
    "sfx_mode": "one_shot",
    "d": "dragon monster roaring and striking the ground"
  }},
  {{
    "p": 4,
    "f": 1,
    "bg": "legendary-kingdom-music-rising-empire",
    "bg_vol": 0.35,
    "amb": "military_camp",
    "amb_vol": 0.50,
    "sfx": "gallop,neighing",
    "sfx_vol": 0.80,
    "sfx_mode": "one_shot",
    "d": "cavalry charge arrives at the front gate"
  }},
  {{
    "p": 5,
    "f": 1,
    "bg": "magical-forest-instrumental-flute-strings-melody",
    "bg_vol": 0.30,
    "amb": "birds_voices",
    "amb_vol": 0.40,
    "sfx": "none",
    "sfx_vol": 0.0,
    "sfx_mode": "one_shot",
    "d": "princess portrait in blooming garden"
  }},
  {{
    "p": 12,
    "f": 0,
    "bg": "fantasy-ambient",
    "bg_vol": 0.30,
    "amb": "fireplace",
    "amb_vol": 0.50,
    "sfx": "none",
    "sfx_vol": 0.0,
    "sfx_mode": "one_shot",
    "d": "warm study conversation"
  }},
  {{
    "p": 16,
    "f": 2,
    "bg": "legendary-kingdom-music-rising-empire",
    "bg_vol": 0.40,
    "amb": "crowd",
    "amb_vol": 0.45,
    "sfx": "none",
    "sfx_vol": 0.0,
    "sfx_mode": "one_shot",
    "d": "grand ballroom reception"
  }}
]
"""
        url = f"{self.base_url}/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "fileData": {
                                "mimeType": "application/pdf",
                                "fileUri": file_uri
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini returned empty parts.")

        text_content = parts[0].get("text", "").strip()

        # Parse JSON with fallback repair if truncated
        try:
            parsed = json.loads(text_content)
        except Exception:
            # If slightly truncated, trim to last complete object
            last_bracket = text_content.rfind("}")
            if last_bracket != -1:
                repaired = text_content[:last_bracket + 1] + "]"
                parsed = json.loads(repaired)
            else:
                raise

        if isinstance(parsed, list):
            parsed.sort(key=lambda x: (x.get("p", 1), x.get("f", 0)))
            return parsed
        return []

    def _generate_default_timeline(self) -> List[Dict[str, Any]]:
        """Fallback timeline when API key or PDF is unavailable."""
        return [
            {"p": 1, "f": 0, "m": "dungeon", "s": "none", "c": "peaceful", "d": "initial ambient"}
        ]

    def _save_cache(self, cache_file: Path, timeline: List[Dict[str, Any]]):
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(timeline, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(timeline)} sound cues to {cache_file.name}")
        except Exception as e:
            logger.error(f"Failed to write sound cache {cache_file}: {e}")
