"""
Standalone Multi-Layer Atmospheric Sound Engine for Manhwa & Novel Reader (Dark Fantasy Edition).
Architecture:
- Layer 1: Background Music (BG) - long narrative arcs (5-15 pages), subtle volume (e.g. 20-40%), seamless loop & crossfade.
- Layer 2: Scene Environment (AMB) - location ambiance (fireplace, forest wind, tavern crowd, rain, dungeon drip), balanced volume (40-60%).
- Layer 3: Dynamic SFX & Action - point strikes (sword clash, roar) OR temporary action loops (horse galloping, footsteps run),
           which automatically stop or crossfade smoothly as soon as a new action/scene arrives.
- Anti-desync, fast-scroll protection, and backward compatibility with old single-cue timelines.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import QObject, QUrl, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

logger = logging.getLogger("sound_engine")


class SoundEngine(QObject):
    cue_triggered = pyqtSignal(str, str, int, int)  # mood/bg, sfx, page, fraction

    def __init__(self, parent=None, sounds_dir: Optional[Path] = None):
        super().__init__(parent)

        base_dir = Path(__file__).parent.parent.resolve()  # manhwa_reader folder
        self.sounds_dir = sounds_dir or (base_dir / "sounds")
        self.ambient_dir = self.sounds_dir / "ambient"
        self.sfx_dir = self.sounds_dir / "sfx"
        self.ui_dir = self.sounds_dir / "ui"
        self.my_sounds_dir = self.sounds_dir / "my_sounds"

        # Ensure modular sound structure exists without recreating deleted legacy folders
        (self.sounds_dir / "my_sounds").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "core").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "packs").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "meme").mkdir(parents=True, exist_ok=True)

        self.is_enabled = False
        self.master_volume = 0.5  # 0.0 to 1.0
        self.is_loading_chapter = False

        # State tracking
        self.current_bg: str = ""
        self.current_amb: str = ""
        self.current_sfx_loop: str = ""
        self.active_timeline: List[Dict[str, Any]] = []
        self.last_triggered_key: str = ""
        self.last_scroll_page: int = 1
        self.last_scroll_fraction: int = 0
        self.last_sfx_page: int = -99
        self.last_sfx_name: str = ""

        # Smart Audio Buffer Cache (Sliding Window lookahead preloading)
        self.cached_audio_urls: Dict[str, QUrl] = {}
        self.cached_file_paths: Dict[str, Path] = {}

        # Relative volumes for layers (0.0 to 1.0)
        self.bg_target_vol: float = 0.35
        self.amb_target_vol: float = 0.55
        self.sfx_target_vol: float = 0.85

        # -------------------------------------------------------------
        # LAYER 1: Background Music (BG) - Dual Player A & B for crossfade
        # -------------------------------------------------------------
        self.bg_out_a = QAudioOutput()
        self.bg_player_a = QMediaPlayer()
        self.bg_player_a.setAudioOutput(self.bg_out_a)
        self.bg_player_a.setLoops(QMediaPlayer.Loops.Infinite)

        self.bg_out_b = QAudioOutput()
        self.bg_player_b = QMediaPlayer()
        self.bg_player_b.setAudioOutput(self.bg_out_b)
        self.bg_player_b.setLoops(QMediaPlayer.Loops.Infinite)

        self.bg_active_player = "A"

        self.bg_crossfade_timer = QTimer(self)
        self.bg_crossfade_timer.setInterval(40)
        self.bg_crossfade_timer.timeout.connect(self._step_bg_crossfade)
        self.bg_fade_steps_remaining = 0
        self.bg_fade_total_steps = 25
        self.bg_fade_in_player = "A"

        # -------------------------------------------------------------
        # LAYER 2: Scene Environment (AMB) - Dual Player A & B for crossfade
        # -------------------------------------------------------------
        self.amb_out_a = QAudioOutput()
        self.amb_player_a = QMediaPlayer()
        self.amb_player_a.setAudioOutput(self.amb_out_a)
        self.amb_player_a.setLoops(QMediaPlayer.Loops.Infinite)

        self.amb_out_b = QAudioOutput()
        self.amb_player_b = QMediaPlayer()
        self.amb_player_b.setAudioOutput(self.amb_out_b)
        self.amb_player_b.setLoops(QMediaPlayer.Loops.Infinite)

        self.amb_active_player = "A"

        self.amb_crossfade_timer = QTimer(self)
        self.amb_crossfade_timer.setInterval(40)
        self.amb_crossfade_timer.timeout.connect(self._step_amb_crossfade)
        self.amb_fade_steps_remaining = 0
        self.amb_fade_total_steps = 25
        self.amb_fade_in_player = "A"

        # -------------------------------------------------------------
        # LAYER 3: Dynamic Multi-SFX & Action Channel
        # -------------------------------------------------------------
        # One-shot multi-voice pool for simultaneous multi-SFX layering
        self.sfx_pool_size = 6
        self.sfx_players: List[QMediaPlayer] = []
        self.sfx_outputs: List[QAudioOutput] = []
        for _ in range(self.sfx_pool_size):
            out = QAudioOutput()
            player = QMediaPlayer()
            player.setAudioOutput(out)
            self.sfx_outputs.append(out)
            self.sfx_players.append(player)
        self.sfx_player_idx = 0

        # Primary references for backward compatibility
        self.sfx_out = self.sfx_outputs[0]
        self.sfx_player = self.sfx_players[0]

        # Action loop player (sustained galloping, running, battle noise until next action)
        self.sfx_loop_out = QAudioOutput()
        self.sfx_loop_player = QMediaPlayer()
        self.sfx_loop_player.setAudioOutput(self.sfx_loop_out)
        self.sfx_loop_player.setLoops(QMediaPlayer.Loops.Infinite)

        self.sfx_fade_timer = QTimer(self)
        self.sfx_fade_timer.setInterval(30)
        self.sfx_fade_timer.timeout.connect(self._step_sfx_fadeout)
        self.sfx_fade_steps_remaining = 0

        self.recipes_file = self.sounds_dir / "sound_recipes.json"
        self.recipes: Dict[str, Any] = self._load_recipes()

        self.set_volume(50)

    @property
    def current_mood(self) -> str:
        """Backward compatibility for legacy UI status display."""
        parts = []
        if self.current_bg:
            parts.append(self.current_bg)
        if self.current_amb and self.current_amb != self.current_bg:
            parts.append(self.current_amb)
        return " + ".join(parts) if parts else ""

    @current_mood.setter
    def current_mood(self, value: str):
        if not value:
            self.current_bg = ""
            self.current_amb = ""

    def _load_recipes(self) -> Dict[str, Any]:
        if self.recipes_file.exists():
            try:
                import json
                with open(self.recipes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"Failed to load sound_recipes.json: {e}")
        return {}

    def set_sounds_dir(self, new_dir: Path):
        """Dynamically reconfigures the sound directory root and updates subdirectories."""
        self.sounds_dir = Path(new_dir)
        self.ambient_dir = self.sounds_dir / "ambient"
        self.sfx_dir = self.sounds_dir / "sfx"
        self.ui_dir = self.sounds_dir / "ui"
        self.my_sounds_dir = self.sounds_dir / "my_sounds"
        (self.sounds_dir / "my_sounds").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "core").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "packs").mkdir(parents=True, exist_ok=True)
        (self.sounds_dir / "meme").mkdir(parents=True, exist_ok=True)
        self.recipes_file = self.sounds_dir / "sound_recipes.json"
        self.reload_recipes()

    def reload_recipes(self):
        self.recipes = self._load_recipes()

    def set_enabled(self, enabled: bool):
        self.is_enabled = bool(enabled)
        if not self.is_enabled:
            self.stop_all(fade=True)

    def set_volume(self, volume_percent: int):
        self.master_volume = max(0.0, min(1.0, float(volume_percent) / 100.0))
        self._reapply_volumes()

    def _reapply_volumes(self):
        # Layer 1: BG
        eff_bg_vol = self.master_volume * self.bg_target_vol
        if self.bg_active_player == "A":
            self.bg_out_a.setVolume(eff_bg_vol)
        else:
            self.bg_out_b.setVolume(eff_bg_vol)

        # Layer 2: AMB
        eff_amb_vol = self.master_volume * self.amb_target_vol
        if self.amb_active_player == "A":
            self.amb_out_a.setVolume(eff_amb_vol)
        else:
            self.amb_out_b.setVolume(eff_amb_vol)

        # Layer 3: SFX Pool
        eff_sfx_vol = self.master_volume * self.sfx_target_vol
        for out in self.sfx_outputs:
            out.setVolume(eff_sfx_vol)
        self.sfx_loop_out.setVolume(eff_sfx_vol)

    def set_chapter_loading(self, loading: bool):
        """Stops/resumes effects during chapter loads to prevent delayed audio."""
        self.is_loading_chapter = loading
        if loading:
            for p in self.sfx_players:
                p.stop()
            self.sfx_loop_player.stop()

    def update_audio_precache(self, current_page: int, lookahead_pages: int = 4):
        """
        Sliding-window lookahead sound cache:
        1. Preloads audio tracks (SFX, ambient, BG) required for current_page .. current_page + lookahead_pages.
        2. Evicts sounds that have already passed, UNLESS they reappear in future pages of the chapter.
        """
        if not self.active_timeline:
            self.cached_audio_urls.clear()
            self.cached_file_paths.clear()
            return

        needed_tokens: set[str] = set()
        future_tokens: set[str] = set()

        for cue in self.active_timeline:
            cp = cue.get("p", 1)
            # Gather tokens for this cue
            tokens = []
            if cue.get("bg"):
                tokens.append(cue.get("bg"))
            if cue.get("amb"):
                tokens.append(cue.get("amb"))
            sfx = cue.get("sfx") or cue.get("s", "")
            if sfx and sfx not in ["none", "silence"]:
                tokens.extend([t.strip() for t in str(sfx).split(",") if t.strip() and t.strip().lower() not in ["none", "silence"]])

            # If within active lookahead window
            if current_page <= cp <= (current_page + lookahead_pages):
                needed_tokens.update(tokens)
            # If anywhere in the future of the chapter
            if cp >= current_page:
                future_tokens.update(tokens)

        # 1. Preload needed sounds into cache
        for token in needed_tokens:
            if token not in self.cached_audio_urls and token not in ["none", "silence"]:
                audio_path = self._resolve_any_sound_file(token)
                if audio_path and audio_path.exists():
                    self.cached_file_paths[token] = audio_path
                    self.cached_audio_urls[token] = QUrl.fromLocalFile(str(audio_path))

        # 2. Smart eviction: only delete if NOT used anywhere in future pages
        evict_keys = [k for k in self.cached_audio_urls if k not in future_tokens and k != self.current_bg and k != self.current_amb]
        for k in evict_keys:
            self.cached_audio_urls.pop(k, None)
            self.cached_file_paths.pop(k, None)

    def set_setting_pack(self, pack_name: Optional[str]):
        """Sets the active setting pack for preferred audio resolution."""
        self.active_setting_pack = pack_name

    def _resolve_any_sound_file(self, token: str, category_hint: Optional[str] = None) -> Optional[Path]:
        """
        Resolves audio file searching modular sound architecture:
        1. Specific setting pack (sounds/packs/<active_setting_pack>/...) if set.
        2. All packs (sounds/packs/*)
        3. Core universal sounds (sounds/core/...)
        4. Meme / neutral effects (sounds/meme/...)
        5. User custom sounds (sounds/my_sounds/...)
        6. Legacy flat folders (ambient, sfx, ui) if present.
        """
        if not token or token in ["none", "silence"]:
            return None

        # A. Priority 1: Check active setting pack first
        packs_dir = self.sounds_dir / "packs"
        if getattr(self, "active_setting_pack", None) and packs_dir.exists():
            pack_dir = packs_dir / self.active_setting_pack
            if pack_dir.exists():
                f = self._find_audio_file(pack_dir, token)
                if f:
                    return f

        # B. Priority 2: Check all packs
        if packs_dir.exists():
            f = self._find_audio_file(packs_dir, token)
            if f:
                return f

        # C. Priority 3: Check CORE universal library
        core_dir = self.sounds_dir / "core"
        if core_dir.exists():
            f = self._find_audio_file(core_dir, token)
            if f:
                return f

        # D. Priority 4: Check MEME folder
        meme_dir = self.sounds_dir / "meme"
        if meme_dir.exists():
            f = self._find_audio_file(meme_dir, token)
            if f:
                return f

        # E. Priority 5: User & Legacy directories
        for directory in [self.my_sounds_dir, self.sfx_dir, self.ambient_dir, self.ui_dir]:
            if directory.exists():
                f = self._find_audio_file(directory, token)
                if f:
                    return f

        return None

    def set_timeline(self, timeline: List[Dict[str, Any]]):
        """Loads timeline cues for the currently active chapter and starts layers."""
        self.active_timeline = sorted(timeline, key=lambda x: (x.get("p", 1), x.get("f", 0)))
        self.last_triggered_key = ""
        self.update_audio_precache(self.last_scroll_page)
        if self.active_timeline and self.is_enabled and not self.is_loading_chapter:
            self.on_scroll_position(self.last_scroll_page, self.last_scroll_fraction)

    def on_scroll_position(self, page: int, fraction: int):
        """
        Main audio orchestrator called when reader scrolls.
        Maintains Layer 1 (Music), Layer 2 (Ambiance), and triggers Layer 3 (SFX / Action loops).
        """
        if not self.is_enabled or self.is_loading_chapter or not self.active_timeline:
            return

        page_delta = abs(page - self.last_scroll_page)
        # Update audio buffer cache when page changes
        if page != self.last_scroll_page:
            self.update_audio_precache(page)
        self.last_scroll_page = page
        self.last_scroll_fraction = fraction

        target_bg = None
        target_bg_vol = 0.35
        target_amb = None
        target_amb_vol = 0.55
        target_sfx_loop = None

        exact_cue = None

        for cue in self.active_timeline:
            cp = cue.get("p", 1)
            cf = cue.get("f", 0)
            if (cp < page) or (cp == page and cf <= fraction):
                # 1. Background Music
                bg = cue.get("bg")
                if not bg:
                    # Backward compatibility with old "m"
                    m = cue.get("m", "")
                    if m and m not in ["crowd", "rain", "storm", "tavern", "cave", "dungeon"]:
                        bg = m
                if bg and bg != "none":
                    target_bg = bg
                    target_bg_vol = float(cue.get("bg_vol", 0.35))

                # 2. Scene Environment
                amb = cue.get("amb")
                if not amb:
                    # Backward compatibility with old "m" if it was environment
                    m = cue.get("m", "")
                    if m in ["crowd", "rain", "storm", "tavern", "cave", "dungeon"]:
                        amb = m
                if amb is not None:
                    if amb in ["none", "silence"]:
                        target_amb = "silence"
                        target_amb_vol = 0.0
                    else:
                        target_amb = amb
                        target_amb_vol = float(cue.get("amb_vol", 0.55))

                # 3. Action loop cue active currently
                sfx_mode = cue.get("sfx_mode", "one_shot")
                s = cue.get("sfx") or cue.get("s")
                if sfx_mode == "loop_until_next" and s and s not in ["none", "silence"]:
                    target_sfx_loop = s
                elif sfx_mode != "loop_until_next":
                    target_sfx_loop = None

            if cp == page and cf == fraction:
                exact_cue = cue

        # -------------------------------------------------------------
        # Transition Layer 1: Background Music
        # -------------------------------------------------------------
        if target_bg and target_bg != self.current_bg:
            self.bg_target_vol = target_bg_vol
            if target_bg == "silence":
                self._stop_bg(fade=True)
            else:
                self.play_bg_music(target_bg, fade_ms=1400)

        # -------------------------------------------------------------
        # Transition Layer 2: Scene Environment
        # -------------------------------------------------------------
        if target_amb and target_amb != self.current_amb:
            self.amb_target_vol = target_amb_vol
            if target_amb == "silence":
                self._stop_amb(fade=True)
            else:
                self.play_ambience(target_amb, fade_ms=1000)

        # -------------------------------------------------------------
        # Transition Layer 3: Action Loop management
        # -------------------------------------------------------------
        if target_sfx_loop != self.current_sfx_loop:
            if target_sfx_loop:
                self.play_sfx_loop(target_sfx_loop)
            else:
                self.stop_sfx_loop(fade=True)

        # -------------------------------------------------------------
        # Layer 3: Instant One-Shot SFX on exact fractional boundary
        # -------------------------------------------------------------
        if not exact_cue:
            return

        cue_key = f"{page}:{fraction}:{exact_cue.get('bg')}:{exact_cue.get('amb')}:{exact_cue.get('sfx') or exact_cue.get('s')}"
        if cue_key == self.last_triggered_key:
            return

        self.last_triggered_key = cue_key
        sfx = exact_cue.get("sfx") or exact_cue.get("s", "")
        sfx_mode = exact_cue.get("sfx_mode", "one_shot")

        if sfx and sfx != "none" and page_delta <= 2:
            if sfx_mode == "one_shot":
                # Quick smooth interrupt of existing action loop if hero suddenly hits / clashes
                if self.current_sfx_loop:
                    self.stop_sfx_loop(fade=True)
                sfx_vol = float(exact_cue.get("sfx_vol", 0.85))
                self.play_sfx(sfx, volume_scale=sfx_vol)

        self.cue_triggered.emit(self.current_bg or self.current_amb, sfx or "", page, fraction)

    # -------------------------------------------------------------
    # Layer 1: Music Playback Methods
    # -------------------------------------------------------------
    def play_bg_music(self, track_name: str, fade_ms: int = 1400):
        if not self.is_enabled or not track_name:
            return
        if track_name == self.current_bg:
            return

        audio_file = self._resolve_any_sound_file(track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.ui_dir, track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.my_sounds_dir, track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.ambient_dir, track_name)

        self.current_bg = track_name
        if not audio_file:
            logger.debug(f"[SoundEngine] BG music '{track_name}' not found on disk")
            return

        target_url = QUrl.fromLocalFile(str(audio_file))

        if self.bg_active_player == "A":
            self.bg_fade_in_player = "B"
            self.bg_player_b.setSource(target_url)
            self.bg_out_b.setVolume(0.0)
            self.bg_player_b.play()
        else:
            self.bg_fade_in_player = "A"
            self.bg_player_a.setSource(target_url)
            self.bg_out_a.setVolume(0.0)
            self.bg_player_a.play()

        self.bg_fade_total_steps = max(10, fade_ms // 40)
        self.bg_fade_steps_remaining = self.bg_fade_total_steps
        self.bg_crossfade_timer.start()

    def _step_bg_crossfade(self):
        target_eff_vol = self.master_volume * self.bg_target_vol
        if self.bg_fade_steps_remaining <= 0:
            self.bg_crossfade_timer.stop()
            if self.bg_fade_in_player == "NONE":
                self.bg_player_a.stop()
                self.bg_player_b.stop()
                self.bg_out_a.setVolume(0.0)
                self.bg_out_b.setVolume(0.0)
            elif self.bg_fade_in_player == "B":
                self.bg_player_a.stop()
                self.bg_out_a.setVolume(0.0)
                self.bg_out_b.setVolume(target_eff_vol)
                self.bg_active_player = "B"
            else:
                self.bg_player_b.stop()
                self.bg_out_b.setVolume(0.0)
                self.bg_out_a.setVolume(target_eff_vol)
                self.bg_active_player = "A"
            return

        self.bg_fade_steps_remaining -= 1
        progress = 1.0 - (self.bg_fade_steps_remaining / float(self.bg_fade_total_steps))
        
        if self.bg_fade_in_player == "NONE":
            cur_a = self.bg_out_a.volume() * 0.75
            cur_b = self.bg_out_b.volume() * 0.75
            self.bg_out_a.setVolume(cur_a)
            self.bg_out_b.setVolume(cur_b)
        else:
            in_vol = target_eff_vol * progress
            out_vol = target_eff_vol * (1.0 - progress)
            if self.bg_fade_in_player == "B":
                self.bg_out_b.setVolume(in_vol)
                self.bg_out_a.setVolume(out_vol)
            else:
                self.bg_out_a.setVolume(in_vol)
                self.bg_out_b.setVolume(out_vol)

    def _stop_bg(self, fade: bool = True):
        self.current_bg = ""
        if fade:
            self.bg_fade_in_player = "NONE"
            self.bg_fade_total_steps = 15
            self.bg_fade_steps_remaining = 15
            self.bg_crossfade_timer.start()
        else:
            self.bg_crossfade_timer.stop()
            self.bg_player_a.stop()
            self.bg_player_b.stop()
            self.bg_out_a.setVolume(0.0)
            self.bg_out_b.setVolume(0.0)

    # -------------------------------------------------------------
    # Layer 2: Environment Ambiance Playback Methods
    # -------------------------------------------------------------
    def play_ambience(self, track_name: str, fade_ms: int = 1000):
        if not self.is_enabled or not track_name:
            return
        if track_name == self.current_amb:
            return

        audio_file = self._resolve_any_sound_file(track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.ambient_dir, track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.my_sounds_dir, track_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.ui_dir, track_name)

        self.current_amb = track_name
        if not audio_file:
            logger.debug(f"[SoundEngine] Ambiance '{track_name}' not found on disk")
            return

        target_url = QUrl.fromLocalFile(str(audio_file))

        if self.amb_active_player == "A":
            self.amb_fade_in_player = "B"
            self.amb_player_b.setSource(target_url)
            self.amb_out_b.setVolume(0.0)
            self.amb_player_b.play()
        else:
            self.amb_fade_in_player = "A"
            self.amb_player_a.setSource(target_url)
            self.amb_out_a.setVolume(0.0)
            self.amb_player_a.play()

        self.amb_fade_total_steps = max(10, fade_ms // 40)
        self.amb_fade_steps_remaining = self.amb_fade_total_steps
        self.amb_crossfade_timer.start()

    def _step_amb_crossfade(self):
        target_eff_vol = self.master_volume * self.amb_target_vol
        if self.amb_fade_steps_remaining <= 0:
            self.amb_crossfade_timer.stop()
            if self.amb_fade_in_player == "NONE":
                self.amb_player_a.stop()
                self.amb_player_b.stop()
                self.amb_out_a.setVolume(0.0)
                self.amb_out_b.setVolume(0.0)
            elif self.amb_fade_in_player == "B":
                self.amb_player_a.stop()
                self.amb_out_a.setVolume(0.0)
                self.amb_out_b.setVolume(target_eff_vol)
                self.amb_active_player = "B"
            else:
                self.amb_player_b.stop()
                self.amb_out_b.setVolume(0.0)
                self.amb_out_a.setVolume(target_eff_vol)
                self.amb_active_player = "A"
            return

        self.amb_fade_steps_remaining -= 1
        progress = 1.0 - (self.amb_fade_steps_remaining / float(self.amb_fade_total_steps))
        
        if self.amb_fade_in_player == "NONE":
            cur_a = self.amb_out_a.volume() * 0.75
            cur_b = self.amb_out_b.volume() * 0.75
            self.amb_out_a.setVolume(cur_a)
            self.amb_out_b.setVolume(cur_b)
        else:
            in_vol = target_eff_vol * progress
            out_vol = target_eff_vol * (1.0 - progress)
            if self.amb_fade_in_player == "B":
                self.amb_out_b.setVolume(in_vol)
                self.amb_out_a.setVolume(out_vol)
            else:
                self.amb_out_a.setVolume(in_vol)
                self.amb_out_b.setVolume(out_vol)

    def _stop_amb(self, fade: bool = True):
        self.current_amb = ""
        if fade:
            self.amb_fade_in_player = "NONE"
            self.amb_fade_total_steps = 15
            self.amb_fade_steps_remaining = 15
            self.amb_crossfade_timer.start()
        else:
            self.amb_crossfade_timer.stop()
            self.amb_player_a.stop()
            self.amb_player_b.stop()
            self.amb_out_a.setVolume(0.0)
            self.amb_out_b.setVolume(0.0)

    # -------------------------------------------------------------
    # Layer 3: Dynamic SFX & Action Loops
    # -------------------------------------------------------------
    def play_sfx(self, sfx_name: str, volume_scale: float = 0.85):
        if not self.is_enabled or self.is_loading_chapter or not sfx_name:
            return

        # Support multi-SFX combinations: e.g. "horse_whinny,sword_clash" or "monster_roar,heavy_strike"
        tokens = [t.strip() for t in str(sfx_name).split(",") if t.strip() and t.strip().lower() not in ["none", "silence"]]
        if not tokens:
            return

        for token in tokens:
            # 1. Use preloaded cached URL if present (instant 0ms RAM access)
            audio_url = self.cached_audio_urls.get(token)
            if not audio_url:
                audio_file = self._resolve_any_sound_file(token)
                if audio_file:
                    audio_url = QUrl.fromLocalFile(str(audio_file))

            if not audio_url:
                logger.debug(f"[SoundEngine] SFX '{token}' requested (not found)")
                continue

            # Round-robin allocation across player voice pool so effects layer cleanly without clipping
            player = self.sfx_players[self.sfx_player_idx]
            out = self.sfx_outputs[self.sfx_player_idx]
            self.sfx_player_idx = (self.sfx_player_idx + 1) % len(self.sfx_players)

            out.setVolume(self.master_volume * volume_scale)
            player.setSource(audio_url)
            player.play()

    def play_sfx_loop(self, sfx_name: str, volume_scale: float = 0.75):
        if not self.is_enabled or self.is_loading_chapter or not sfx_name:
            return
        if sfx_name == self.current_sfx_loop:
            return

        audio_file = self._resolve_any_sound_file(sfx_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.sfx_dir, sfx_name)
        if not audio_file:
            audio_file = self._find_audio_file(self.ambient_dir, sfx_name)
        if not audio_file:
            return

        self.current_sfx_loop = sfx_name
        self.sfx_loop_out.setVolume(self.master_volume * volume_scale)
        self.sfx_loop_player.setSource(QUrl.fromLocalFile(str(audio_file)))
        self.sfx_loop_player.play()

    def stop_sfx_loop(self, fade: bool = True):
        self.current_sfx_loop = ""
        if fade and self.sfx_loop_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.sfx_fade_steps_remaining = 10
            self.sfx_fade_timer.start()
        else:
            self.sfx_fade_timer.stop()
            self.sfx_loop_player.stop()

    def _step_sfx_fadeout(self):
        if self.sfx_fade_steps_remaining <= 0:
            self.sfx_fade_timer.stop()
            self.sfx_loop_player.stop()
            return
        self.sfx_fade_steps_remaining -= 1
        vol = self.sfx_loop_out.volume() * 0.75
        self.sfx_loop_out.setVolume(vol)

    # -------------------------------------------------------------
    # Legacy / UI Helper Methods
    # -------------------------------------------------------------
    def play_ambient(self, mood_name: str, fade_ms: int = 1200):
        """Backward compatible helper: stops competing layers and routes to play_bg_music or play_ambience."""
        if not mood_name:
            self.stop_all(fade=True)
            return

        clean_name = mood_name.split(":", 1)[-1] if ":" in mood_name else mood_name

        # Check if the file is located in ui_dir or my_sounds_dir
        is_bg = (
            mood_name.startswith("ui:") or
            mood_name.startswith("my_sounds:") or
            bool(self._find_audio_file(self.ui_dir, clean_name)) or
            bool(self._find_audio_file(self.my_sounds_dir, clean_name)) or
            clean_name in [
                "legendary-kingdom-music-rising-empire", "fantasy-ambient", "magic_fantasy",
                "palace", "mansion", "ancient_celtic_music", "test_sound",
                "by-the-rafters-glow-full-version-medieval-tavern-music-rpg-game"
            ]
        )

        if is_bg:
            self._stop_amb(fade=False)
            self.play_bg_music(clean_name, fade_ms)
        else:
            self._stop_bg(fade=False)
            self.play_ambience(clean_name, fade_ms)

    def play_ui_sound(self, sound_name: str):
        if not self.is_enabled:
            return
        audio_file = self._find_audio_file(self.ui_dir, sound_name)
        if audio_file:
            self.sfx_player.setSource(QUrl.fromLocalFile(str(audio_file)))
            self.sfx_player.play()

    def stop_all(self, fade: bool = True):
        self.bg_crossfade_timer.stop()
        self.amb_crossfade_timer.stop()
        self.sfx_fade_timer.stop()
        self._stop_bg(fade=fade)
        self._stop_amb(fade=fade)
        self.stop_sfx_loop(fade=fade)
        for p in self.sfx_players:
            p.stop()
        self.last_triggered_key = ""

    def _find_audio_file(self, directory: Path, name: str) -> Optional[Path]:
        """
        Supports exact matches first, subfolders, variations (name_1.mp3), and semantic aliases.
        """
        import random
        if not directory.exists() or not name:
            return None

        # Clean off any prefix like 'ui:' or 'my_sounds:'
        raw_name = name.split(":", 1)[-1] if ":" in name else name

        # 1. Exact file match first (highest priority)
        for ext in [".mp3", ".ogg", ".wav"]:
            cand = directory / f"{raw_name}{ext}"
            if cand.exists():
                return cand

        ALIAS_MAP = {
            "palace": ["legendary-kingdom-music-rising-empire", "crowd", "fantasy-ambient"],
            "mansion": ["fantasy-ambient", "magic_fantasy", "ancient_celtic_music"],
            "study": ["fantasy-ambient", "magic_fantasy"],
            "fireplace": ["fantasy-ambient", "magic_fantasy"],
            "magic": ["magic_fantasy", "magical-forest-instrumental-flute-strings-melody"],
            "ballroom": ["legendary-kingdom-music-rising-empire", "crowd"],
            "nature": ["forest_1", "magical-forest-instrumental-flute-strings-melody", "movements_in_forest"],
            "battle": ["guns_battle", "war_drums", "sword_clash"],
            "cave": ["cave_1", "cave_2", "dungeon"],
            "dungeon": ["dungeon", "cave_1", "nto-the-darkness-cello-version-long"],
            "monster": ["monster_roar"],
            "dragon": ["monster_roar"],
            "fear": ["heartbeat"],
            "horse": ["gallop", "neighing"],
            "romantic": ["desert_in_bloom", "magical-forest-instrumental-flute-strings-melody", "ancient_celtic_music"],
            "peaceful_portrait": ["desert_in_bloom", "magical-forest-instrumental-flute-strings-melody", "ancient_celtic_music"]
        }

        candidates_to_try = [raw_name]
        if raw_name in ALIAS_MAP:
            candidates_to_try.extend(ALIAS_MAP[raw_name])

        for cand_name in candidates_to_try:
            # A. Check subfolder: e.g. sounds/ambient/forest/
            subfolder = directory / cand_name
            if subfolder.is_dir():
                folder_tracks = []
                for ext in [".mp3", ".ogg", ".wav"]:
                    folder_tracks.extend(list(subfolder.glob(f"*{ext}")))
                if folder_tracks:
                    return random.choice(folder_tracks)

            # B. Check flat variations: e.g. forest_1.mp3, forest_2.wav
            variations = []
            for ext in [".mp3", ".ogg", ".wav"]:
                variations.extend(list(directory.glob(f"{cand_name}_*{ext}")))
            if variations:
                return random.choice(variations)

            # C. Check exact file match for alias
            for ext in [".mp3", ".ogg", ".wav"]:
                cand = directory / f"{cand_name}{ext}"
                if cand.exists():
                    return cand

            # D. Dynamic recursive search (exact stem match or contained substring)
            clean_cand = cand_name.lower().replace("_", "").replace("-", "")
            for f in directory.rglob("*"):
                if f.is_file() and f.suffix.lower() in [".mp3", ".ogg", ".wav"]:
                    clean_stem = f.stem.lower().replace("_", "").replace("-", "")
                    if clean_cand == clean_stem or (len(clean_cand) >= 4 and clean_cand in clean_stem):
                        return f

        return None
