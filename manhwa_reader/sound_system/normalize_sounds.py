"""
Audio Normalization Utility for Manhwa Reader Soundpacks.
Scans manhwa_reader/sounds and normalizes all tracks into manhwa_reader/sounds_normalized (or sounds2).
- BG / Ambient tracks: Target RMS 0.13 (~ -16 to -18 dBFS) with hard peak limiting at 0.92 to prevent clipping.
- SFX tracks: Peak normalization to 0.89 (-1 dBFS) for crisp punchy sound effects without distortion.
"""

import os
import sys
import shutil
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import numpy as np
import soundfile as sf


def normalize_audio(data: np.ndarray, is_bg_or_ambient: bool = False) -> np.ndarray:
    if data.size == 0:
        return data

    max_peak = np.max(np.abs(data))
    if max_peak < 1e-6:
        return data

    if is_bg_or_ambient:
        # RMS target normalization
        rms = np.sqrt(np.mean(data**2))
        target_rms = 0.13
        if rms > 1e-5:
            gain = target_rms / rms
            # Limit gain to reasonable bounds [0.2, 5.0]
            gain = np.clip(gain, 0.25, 4.0)
            norm_data = data * gain
            # Safety peak clip/compression if loud section exceeds 0.92
            peak = np.max(np.abs(norm_data))
            if peak > 0.92:
                norm_data = norm_data * (0.92 / peak)
            return norm_data.astype(np.float32)
        else:
            return (data * (0.85 / max_peak)).astype(np.float32)
    else:
        # SFX: Peak normalize to 0.89 (-1 dBFS)
        target_peak = 0.89
        norm_data = data * (target_peak / max_peak)
        return norm_data.astype(np.float32)


def process_soundpacks(src_root: Path, dst_root: Path):
    print(f"🎵 Початок нормалізації аудіо...")
    print(f"📂 Джерело: {src_root}")
    print(f"📁 Призначення: {dst_root}\n")

    dst_root.mkdir(parents=True, exist_ok=True)
    count_ok = 0
    count_err = 0

    for root, dirs, files in os.walk(src_root):
        rel_path = Path(root).relative_to(src_root)
        target_dir = dst_root / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            src_file = Path(root) / f
            dst_file = target_dir / f

            # Copy non-audio files directly (like recipes.json)
            ext = src_file.suffix.lower()
            if ext not in [".wav", ".mp3", ".ogg", ".flac"]:
                shutil.copy2(src_file, dst_file)
                continue

            try:
                data, sr = sf.read(str(src_file), always_2d=False)
                # Determine track role from directory name or filename
                path_str = str(src_file).lower()
                is_bg = ("bg" in path_str) or ("ambient" in path_str) or ("music" in path_str)

                norm_data = normalize_audio(data, is_bg_or_ambient=is_bg)

                # Write out file preserving format
                fmt = "WAV" if ext == ".wav" else ("MP3" if ext == ".mp3" else None)
                if fmt:
                    sf.write(str(dst_file), norm_data, sr, format=fmt)
                else:
                    sf.write(str(dst_file), norm_data, sr)

                count_ok += 1
                role_str = "BG/Ambient" if is_bg else "SFX/UI"
                print(f"✓ [{role_str:10}] {rel_path / f}")
            except Exception as e:
                count_err += 1
                print(f"❌ Помилка з {f}: {e}")
                shutil.copy2(src_file, dst_file)

    print(f"\n==========================================")
    print(f"✨ Готово! Успішно нормалізовано: {count_ok} аудіофайлів (помилок: {count_err})")
    print(f"📁 Нова папка зі збалансованим звуком: {dst_root}")
    print(f"==========================================\n")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    sounds_src = base_dir / "manhwa_reader" / "sounds"
    sounds_dst = base_dir / "manhwa_reader" / "sounds_normalized"

    if not sounds_src.exists():
        print(f"❌ Не знайдено папку звуків: {sounds_src}")
    else:
        process_soundpacks(sounds_src, sounds_dst)
