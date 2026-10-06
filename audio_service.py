"""
Audio speech service for Manhwa Translator.
Provides robust offline English pronunciation on Windows using native SAPI / System.Speech.
"""
import threading
import re
import subprocess
import pythoncom
import win32com.client

CREATE_NO_WINDOW = 0x08000000

def speak_english(text: str):
    """
    Speaks English text asynchronously on default audio device.
    Uses native SAPI.SpVoice with fallback to PowerShell System.Speech.
    """
    if not text:
        return
    clean_text = re.sub(r"[^A-Za-z0-9\s\.\,\!\?']", " ", text).strip()
    if not clean_text:
        return

    def _worker():
        # 1. Try native SAPI COM directly
        try:
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            # 0 = Synchronous inside thread, 1 = Asynchronous
            voice.Speak(clean_text, 0)
            return
        except Exception:
            pass
        finally:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

        # 2. Fallback to PowerShell System.Speech
        try:
            safe_text = clean_text.replace("'", "''")
            ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe_text}')"
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
