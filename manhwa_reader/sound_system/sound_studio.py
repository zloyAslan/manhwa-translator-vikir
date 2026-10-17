"""
Sound Studio & Atmosphere Mixer for Manhwa & Novel Reader (Dark Fantasy Edition).
Allows users to:
1. Audition and balance multiple sound layers with percentage volume sliders.
2. Combine ambient beds + Foley SFX (e.g. City 50% + Horse Hooves 30% + Distant Crowd 10%).
3. Bake multi-layer recipes into pure 16-bit PCM WAV audio files offline (Zero dependencies: uses standard library `wave`).
4. Manage and inspect Sound Packs (Lite vs Standard vs Epic).
5. Save and load recipes into `sound_recipes.json`.
"""

import sys
import os
import json
import wave
import struct
import math
from pathlib import Path
from typing import Dict, Any, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QScrollArea, QWidget, QProgressBar, QTabWidget,
    QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


# ---------------------------------------------------------------------------
# Offline Pure-Python Wave Mixer Engine
# ---------------------------------------------------------------------------
def mix_wav_files(
    input_tracks: List[tuple[Path, float]], # [(path, volume_0_to_1), ...]
    output_path: Path,
    target_duration_sec: float = 45.0,
    seamless_loop_fade_sec: float = 2.0
) -> bool:
    """
    Reads 16-bit PCM WAV files, resamples/pads them to target_duration,
    scales volume, mixes down into a single master WAV, and applies a crossfade
    between head and tail for 100% seamless looping.
    Requires ZERO external libraries.
    """
    if not input_tracks:
        return False

    sample_rate = 44100
    num_channels = 2
    total_frames = int(target_duration_sec * sample_rate)
    master_buffer = [0.0] * (total_frames * num_channels)

    for file_path, volume in input_tracks:
        if not file_path.exists() or volume <= 0.001:
            continue
        try:
            with wave.open(str(file_path), 'rb') as wf:
                in_channels = wf.getnchannels()
                in_sampwidth = wf.getsampwidth()
                in_framerate = wf.getframerate()
                in_frames = wf.getnframes()

                if in_sampwidth != 2:
                    # Skip non-16-bit PCM in raw reader
                    continue

                raw_bytes = wf.readframes(in_frames)
                total_samples = len(raw_bytes) // 2
                fmt = f"<{total_samples}h"
                samples = struct.unpack(fmt, raw_bytes)

                # Loop and overlay samples into master buffer
                idx = 0
                step = in_framerate / float(sample_rate)
                in_sample_idx = 0.0

                for f in range(total_frames):
                    curr_in_frame = int(in_sample_idx) % in_frames
                    if in_channels == 1:
                        val = samples[curr_in_frame] * volume
                        master_buffer[f * 2] += val
                        master_buffer[f * 2 + 1] += val
                    else:
                        left_idx = (curr_in_frame * 2) % len(samples)
                        right_idx = (left_idx + 1) % len(samples)
                        master_buffer[f * 2] += samples[left_idx] * volume
                        master_buffer[f * 2 + 1] += samples[right_idx] * volume

                    in_sample_idx += step
        except Exception as e:
            print(f"Error mixing {file_path}: {e}")
            continue

    # Apply seamless loop crossfade (head <-> tail)
    fade_frames = int(seamless_loop_fade_sec * sample_rate)
    if fade_frames > 0 and fade_frames < total_frames // 2:
        for i in range(fade_frames):
            factor = i / float(fade_frames)
            # fade in tail into head
            tail_idx = (total_frames - fade_frames + i) * 2
            head_idx = i * 2

            master_buffer[head_idx] = master_buffer[head_idx] * factor + master_buffer[tail_idx] * (1.0 - factor)
            master_buffer[head_idx + 1] = master_buffer[head_idx + 1] * factor + master_buffer[tail_idx + 1] * (1.0 - factor)

    # Hard-limit and clip to 16-bit integer range (-32767 to 32767)
    out_samples = []
    for val in master_buffer:
        clamped = max(-32767.0, min(32767.0, val))
        out_samples.append(int(clamped))

    # Write destination file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), 'wb') as out_wf:
        out_wf.setnchannels(num_channels)
        out_wf.setsampwidth(2)
        out_wf.setframerate(sample_rate)
        out_bytes = struct.pack(f"<{len(out_samples)}h", *out_samples)
        out_wf.writeframes(out_bytes)

    return True


# ---------------------------------------------------------------------------
# Layer Mixer Slot Widget
# ---------------------------------------------------------------------------
class MixerSlotWidget(QFrame):
    def __init__(self, slot_num: int, sounds_dir: Path, parent=None):
        super().__init__(parent)
        self.slot_num = slot_num
        self.sounds_dir = sounds_dir

        self.audio_out = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)

        self.setStyleSheet("""
            QFrame {
                background: #14171c;
                border: 1px solid #282f3a;
                border-radius: 8px;
                padding: 6px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.lbl_slot = QLabel(f"Шар #{slot_num}")
        self.lbl_slot.setStyleSheet("color: #d4a373; font-weight: bold; min-width: 55px;")
        layout.addWidget(self.lbl_slot)

        # File Dropdown
        self.combo_file = QComboBox()
        self.combo_file.setMinimumWidth(180)
        self.combo_file.setStyleSheet("""
            QComboBox {
                background: #0f1115;
                color: #e0e6ed;
                border: 1px solid #333d4d;
                border-radius: 5px;
                padding: 4px 8px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #181c24;
                color: #e0e6ed;
                selection-background-color: #2b3648;
            }
        """)
        self.populate_files()
        self.combo_file.currentIndexChanged.connect(self._on_file_changed)
        layout.addWidget(self.combo_file, 1)

        # Volume Slider
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(50)
        self.slider_vol.setFixedWidth(120)
        self.slider_vol.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: #252b36;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #d4a373;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #fdf0d5;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
        """)
        self.slider_vol.valueChanged.connect(self._on_vol_changed)
        layout.addWidget(self.slider_vol)

        self.lbl_vol = QLabel("50%")
        self.lbl_vol.setStyleSheet("color: #9aa4b2; min-width: 38px;")
        layout.addWidget(self.lbl_vol)

        # Browse custom file button
        self.btn_browse = QPushButton("📁")
        self.btn_browse.setToolTip("Обрати інший аудіофайл...")
        self.btn_browse.setFixedSize(28, 28)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background: #212631;
                border: 1px solid #364153;
                border-radius: 5px;
                color: #e0e6ed;
            }
            QPushButton:hover { background: #2f3645; }
        """)
        self.btn_browse.clicked.connect(self._browse_custom_file)
        layout.addWidget(self.btn_browse)

    def populate_files(self):
        self.combo_file.clear()
        self.combo_file.addItem("--- Вимкнено ---", "")

        for category in ["ambient", "sfx", "ui"]:
            cat_dir = self.sounds_dir / category
            if cat_dir.exists():
                for f in sorted(list(cat_dir.iterdir())):
                    if f.is_file() and f.suffix.lower() in [".mp3", ".ogg", ".wav"]:
                        self.combo_file.addItem(f"[{category}] {f.name}", str(f.resolve()))

    def _browse_custom_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Обрати аудіотрек",
            str(self.sounds_dir),
            "Аудіо (*.mp3 *.ogg *.wav);;Усі файли (*.*)"
        )
        if file_path:
            p = Path(file_path)
            self.combo_file.addItem(f"[Зовнішній] {p.name}", str(p.resolve()))
            self.combo_file.setCurrentIndex(self.combo_file.count() - 1)

    def _on_file_changed(self):
        file_path = self.combo_file.currentData()
        if file_path and Path(file_path).exists():
            self.player.setSource(QUrl.fromLocalFile(file_path))
            self._on_vol_changed(self.slider_vol.value())
        else:
            self.player.stop()

    def _on_vol_changed(self, val: int):
        self.lbl_vol.setText(f"{val}%")
        self.audio_out.setVolume(val / 100.0)

    def get_track_data(self) -> Optional[tuple[Path, float]]:
        file_path = self.combo_file.currentData()
        if not file_path:
            return None
        p = Path(file_path)
        if not p.exists():
            return None
        return (p, self.slider_vol.value() / 100.0)

    def play(self):
        if self.combo_file.currentData():
            self.player.play()

    def stop(self):
        self.player.stop()


# ---------------------------------------------------------------------------
# Main Sound Studio Window
# ---------------------------------------------------------------------------
class SoundStudioWindow(QDialog):
    def __init__(self, sounds_dir: Path, parent=None):
        super().__init__(parent)
        self.sounds_dir = sounds_dir
        self.recipes_file = self.sounds_dir / "sound_recipes.json"

        self.setWindowTitle("Майстерня Звуку та Атмосфери (Sound Studio)")
        self.resize(750, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d11;
                color: #e0e6ed;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QLabel { color: #e0e6ed; font-size: 13px; }
            QGroupBox {
                border: 1px solid #232936;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
                font-weight: bold;
                color: #d4a373;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 5px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header
        header = QLabel("🎚️ Редактор Атмосферних Рецептів та Звукових Пакетів")
        header.setStyleSheet("font-size: 17px; font-weight: bold; color: #fdf0d5;")
        main_layout.addWidget(header)

        sub = QLabel("Комбінуйте фони та шуми (місто + коні + люди), створюйте пресети або запікайте у готовий безшовний трек.")
        sub.setStyleSheet("color: #8c97a8; font-size: 12px;")
        main_layout.addWidget(sub)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #232936; background: #0f1115; border-radius: 6px; }
            QTabBar::tab {
                background: #141820;
                color: #8c97a8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #232936; color: #fdf0d5; font-weight: bold; }
        """)

        # Tab 1: Layer Mixer
        self.tab_mixer = QWidget()
        self._build_mixer_tab()
        self.tabs.addTab(self.tab_mixer, "🎛️ Мікшер Шарів (Layer Mixer)")

        # Tab 2: Sound Packs Inspector
        self.tab_packs = QWidget()
        self._build_packs_tab()
        self.tabs.addTab(self.tab_packs, "📦 Інспектор Пакетів (Sound Packs)")

        main_layout.addWidget(self.tabs, 1)

    def _build_mixer_tab(self):
        layout = QVBoxLayout(self.tab_mixer)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Recipe Name Bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Назва рецепту:"))
        self.edit_recipe_name = QLineEdit()
        self.edit_recipe_name.setPlaceholderText("наприклад: horse_city_arrival або epic_battle")
        self.edit_recipe_name.setStyleSheet("""
            QLineEdit {
                background: #14171c;
                border: 1px solid #2c3545;
                color: #fdf0d5;
                border-radius: 5px;
                padding: 5px 10px;
            }
        """)
        top_bar.addWidget(self.edit_recipe_name, 1)
        layout.addLayout(top_bar)

        # Slots container (4 slots)
        self.slots: List[MixerSlotWidget] = []
        for i in range(1, 5):
            slot = MixerSlotWidget(i, self.sounds_dir, self)
            self.slots.append(slot)
            layout.addWidget(slot)

        # Playback Controls Bar
        play_bar = QHBoxLayout()
        self.btn_preview = QPushButton("▶ Прослухати мікс (Audition)")
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background: #234d38;
                border: 1px solid #347052;
                border-radius: 6px;
                color: #d1fae5;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2b6146; }
        """)
        self.btn_preview.clicked.connect(self._toggle_audition)
        play_bar.addWidget(self.btn_preview)

        self.btn_stop = QPushButton("⏹ Зупинити")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background: #3a1a1a;
                border: 1px solid #5a2a2a;
                border-radius: 6px;
                color: #fca5a5;
                padding: 8px 14px;
            }
            QPushButton:hover { background: #4a2222; }
        """)
        self.btn_stop.clicked.connect(self._stop_audition)
        play_bar.addWidget(self.btn_stop)

        play_bar.addStretch()

        # Save Recipe
        self.btn_save_recipe = QPushButton("💾 Зберегти рецепт")
        self.btn_save_recipe.setStyleSheet("""
            QPushButton {
                background: #252e3d;
                border: 1px solid #3b4961;
                border-radius: 6px;
                color: #93c5fd;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #323d50; }
        """)
        self.btn_save_recipe.clicked.connect(self._save_recipe)
        play_bar.addWidget(self.btn_save_recipe)

        # Bake WAV Button
        self.btn_bake_wav = QPushButton("⚡ Запекти в єдиний WAV")
        self.btn_bake_wav.setToolTip("Змішує всі обрані WAV-шари в один 45-секундний безшовний файл (100% без лагів)")
        self.btn_bake_wav.setStyleSheet("""
            QPushButton {
                background: #5b3e1b;
                border: 1px solid #855b27;
                border-radius: 6px;
                color: #fef08a;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #714d22; }
        """)
        self.btn_bake_wav.clicked.connect(self._bake_wav)
        play_bar.addWidget(self.btn_bake_wav)

        layout.addLayout(play_bar)

    def _build_packs_tab(self):
        layout = QVBoxLayout(self.tab_packs)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = QLabel(
            "<b>Рівні пакетів звуків:</b><br>"
            "• <b>Lite (Мінімум):</b> 3-4 базові амбієнти (ліс, місто, печера) — покривають 80% сцен.<br>"
            "• <b>Standard:</b> 12 амбієнтів + 10 SFX.<br>"
            "• <b>Epic:</b> повний пул зі змінними варіаціями (forest_1.mp3, forest_2.mp3)."
        )
        info.setStyleSheet("color: #a3b1c2; line-height: 1.4;")
        layout.addWidget(info)

        self.list_installed = QListWidget()
        self.list_installed.setStyleSheet("""
            QListWidget {
                background: #14171c;
                border: 1px solid #232936;
                border-radius: 6px;
                color: #e0e6ed;
                padding: 6px;
            }
        """)
        self._refresh_pack_list()
        layout.addWidget(self.list_installed, 1)

        btn_refresh = QPushButton("🔄 Оновити список файлів")
        btn_refresh.clicked.connect(self._refresh_pack_list)
        layout.addWidget(btn_refresh)

    def _refresh_pack_list(self):
        self.list_installed.clear()
        total_files = 0
        for category in ["ambient", "sfx", "ui"]:
            cat_dir = self.sounds_dir / category
            count = 0
            if cat_dir.exists():
                files = list(cat_dir.glob("*.*"))
                count = len(files)
                total_files += count
                for f in files:
                    size_kb = f.stat().st_size / 1024
                    item = QListWidgetItem(f"[{category.upper()}] {f.name} ({size_kb:.1f} KB)")
                    self.list_installed.addItem(item)

        if total_files == 0:
            item = QListWidgetItem("⚠️ Не знайдено жодного аудіофайлу в папці sounds/! Додайте .mp3 або .wav файли.")
            item.setForeground(Qt.GlobalColor.yellow)
            self.list_installed.addItem(item)

    def _toggle_audition(self):
        for slot in self.slots:
            slot.play()

    def _stop_audition(self):
        for slot in self.slots:
            slot.stop()

    def _save_recipe(self):
        name = self.edit_recipe_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Помилка", "Введіть назву для цього рецепту!")
            return

        tracks = []
        for slot in self.slots:
            data = slot.get_track_data()
            if data:
                p, vol = data
                tracks.append({
                    "file": str(p.name),
                    "volume": round(vol, 2)
                })

        if not tracks:
            QMessageBox.warning(self, "Помилка", "Оберіть хоча б один аудіотрек у мікшері!")
            return

        recipes = {}
        if self.recipes_file.exists():
            try:
                with open(self.recipes_file, "r", encoding="utf-8") as f:
                    recipes = json.load(f)
            except Exception:
                recipes = {}

        recipes[name] = tracks
        try:
            with open(self.recipes_file, "w", encoding="utf-8") as f:
                json.dump(recipes, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Успіх", f"Рецепт '{name}' збережено у sound_recipes.json!")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти рецепт: {e}")

    def _bake_wav(self):
        tracks = []
        for slot in self.slots:
            data = slot.get_track_data()
            if data:
                tracks.append(data)

        if not tracks:
            QMessageBox.warning(self, "Помилка", "Оберіть хоча б один WAV-трек для запікання!")
            return

        out_name = self.edit_recipe_name.text().strip() or "baked_ambient"
        dest_path = self.sounds_dir / "ambient" / f"{out_name}.wav"

        success = mix_wav_files(tracks, dest_path, target_duration_sec=45.0, seamless_loop_fade_sec=2.0)
        if success:
            QMessageBox.information(
                self,
                "Запікання завершено",
                f"Файл успішно запечено в:\n{dest_path.name}\n(45 сек, безшовне зациклення)"
            )
            self._refresh_pack_list()
        else:
            QMessageBox.warning(
                self,
                "Помилка",
                "Не вдалося запекти файли. Переконайтесь, що вихідні треки у форматі 16-bit WAV."
            )

    def closeEvent(self, event):
        self._stop_audition()
        super().closeEvent(event)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    sounds_folder = Path(__file__).parent.parent / "sounds"
    win = SoundStudioWindow(sounds_folder)
    win.show()
    sys.exit(app.exec())
