"""
tts_engine.py — Jarvis AI Text-to-Speech Engine
================================================
Fully upgraded, bug-fixed, production-grade TTS module.
"""

import asyncio
import hashlib
import os
import random
import threading
import glob
import time

import edge_tts
import pygame
from dotenv import dotenv_values

# ──────────────────────────────────────────────
# 1. CONFIG  (loaded once at import)
# ──────────────────────────────────────────────
_env = dotenv_values(".env")

ASSISTANT_VOICE: str   = _env.get("AssistantVoice", "en-US-AriaNeural")  # FIX: default fallback
VOICE_RATE:      str   = _env.get("VoiceRate",      "+13%")               # NEW: configurable
VOICE_PITCH:     str   = _env.get("VoicePitch",     "+5Hz")               # NEW: configurable
VOICE_VOLUME:    float = float(_env.get("VoiceVolume", "1.0"))            # NEW: configurable

DATA_DIR:  str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")  # FIX: cross-platform
CACHE_DIR: str = os.path.join(DATA_DIR, "cache")

MAX_TTS_CHARS:   int = 1000   # NEW: hard cap
LONG_WORD_COUNT: int = 60     # NEW: smarter long-answer detection

# ──────────────────────────────────────────────
# 2. ONE-TIME SETUP  (FIX: mixer init once, not per call)
# ──────────────────────────────────────────────
os.makedirs(DATA_DIR,  exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

def clean_cache(max_age_days=7):
    """Purge old audio files to save disk space."""
    now = time.time()
    for f in glob.glob(os.path.join(CACHE_DIR, "*.mp3")):
        if os.stat(f).st_mtime < now - max_age_days * 86400:
            try: os.remove(f)
            except: pass

clean_cache()

try:
    pygame.mixer.init()
    pygame.mixer.music.set_volume(VOICE_VOLUME)
    _MIXER_READY = True
except Exception as exc:
    print(f"[TTS] Mixer init error: {exc}")
    _MIXER_READY = False

_stop_event = threading.Event()   # NEW: thread-safe interrupt


def stop_speaking() -> None:
    """Interrupt current playback from any thread (e.g. voice command)."""
    _stop_event.set()


# ──────────────────────────────────────────────
# 3. ASYNC TTS GENERATION
# ──────────────────────────────────────────────
async def _generate_audio(text: str, path: str) -> None:
    communicate = edge_tts.Communicate(
        text, ASSISTANT_VOICE, pitch=VOICE_PITCH, rate=VOICE_RATE
    )
    await communicate.save(path)


def _run_async(coro) -> None:
    """FIX: Safely run async coroutine even inside a running event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result(timeout=30)       # NEW: timeout protection
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


# ──────────────────────────────────────────────
# 4. AUDIO CACHE  (NEW)
# ──────────────────────────────────────────────
def _cache_path(text: str) -> str:
    key = hashlib.md5(
        f"{text}|{ASSISTANT_VOICE}|{VOICE_RATE}|{VOICE_PITCH}".encode()
    ).hexdigest()
    return os.path.join(CACHE_DIR, f"{key}.mp3")


def _get_or_generate(text: str) -> str:
    """Return cached MP3 path; generate if not cached yet."""
    path = _cache_path(text)
    if not os.path.exists(path):
        _run_async(_generate_audio(text, path))
    return path


# ──────────────────────────────────────────────
# 5. PLAYBACK
# ──────────────────────────────────────────────
def _play_audio(file_path: str, func=lambda r=None: True) -> bool:
    if not _MIXER_READY:
        print("[TTS] Playback unavailable: pygame mixer not initialized.")
        return False
    _stop_event.clear()
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()

        clock = pygame.time.Clock()
        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():            # NEW: interrupt check
                pygame.mixer.music.stop()
                return False
            try:
                if func() is False:             # legacy callback
                    pygame.mixer.music.stop()
                    return False
            except TypeError:
                pass
            clock.tick(20)
        return True

    except Exception as exc:
        print(f"[TTS] Playback error: {exc}")
        return False

    finally:
        try:
            func(False)
        except TypeError:
            try:
                func()
            except Exception:
                pass
        except Exception:
            pass
        try:
            pygame.mixer.music.stop()           # FIX: always stop before releasing
        except Exception:
            pass


# ──────────────────────────────────────────────
# 6. PUBLIC API
# ──────────────────────────────────────────────
def tts(text: str, func=lambda r=None: True) -> bool:
    """
    Speak *text* aloud.
    - Empty text silently skipped.          (NEW)
    - Text > MAX_TTS_CHARS auto-truncated.  (NEW)
    - Returns True on clean finish.
    """
    if not text or not text.strip():        # NEW: empty guard
        print("[TTS] Skipped: empty text.")
        return False

    if len(text) > MAX_TTS_CHARS:           # NEW: size guard
        print(f"[TTS] Truncated {len(text)} → {MAX_TTS_CHARS} chars.")
        text = text[:MAX_TTS_CHARS]

    try:
        return _play_audio(_get_or_generate(text), func)
    except asyncio.TimeoutError:
        print("[TTS] Edge TTS timed out.")
        return False
    except Exception as exc:
        print(f"[TTS] Error: {exc}")
        return False


_LONG_RESPONSES = [                         # FIX: trimmed to 5
    "The rest of the result is on the chat screen, sir.",
    "Please check the chat screen for the full answer, sir.",
    "The complete response is on the chat screen, sir.",
    "Kindly review the chat screen for more details, sir.",
    "The remainder of the answer is on the chat screen, sir.",
]


def text_to_speech(text: str, func=lambda r=None: True) -> bool:
    """
    Smart TTS: summary + redirect for long text, full speech for short.
    FIX: uses word count instead of raw char length for better detection.
    """
    if not text or not text.strip():
        return False

    sentences  = [s.strip() for s in text.split(".") if s.strip()]
    word_count = len(text.split())

    if len(sentences) > 4 or word_count > LONG_WORD_COUNT:
        summary = ". ".join(sentences[:2]) + ". "
        spoken  = summary + random.choice(_LONG_RESPONSES)
    else:
        spoken = text

    return tts(spoken, func)


# Backwards-compatible PascalCase aliases (drop-in replacement)
TTS          = tts
TextToSpeech = text_to_speech


# ──────────────────────────────────────────────
# 7. INTERACTIVE TEST HARNESS
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 46)
    print("   Jarvis TTS Engine — Interactive Test")
    print("=" * 46)
    print(f"  Voice   : {ASSISTANT_VOICE}")
    print(f"  Rate    : {VOICE_RATE}  Pitch: {VOICE_PITCH}  Vol: {VOICE_VOLUME}")
    print(f"  Data    : {DATA_DIR}")
    print("  Commands: quit | stop | cache | <any text>")
    print("=" * 46)

    try:
        while True:
            user_input = input("\nEnter text: ").strip()
            if not user_input:
                print("  [!] Empty — skipped.")
                continue
            if user_input.lower() == "quit":
                print("Goodbye."); break
            elif user_input.lower() == "stop":
                stop_speaking()
                print("  [!] Stop signal sent.")
            elif user_input.lower() == "cache":
                n = len(os.listdir(CACHE_DIR))
                print(f"  Cache: {n} file(s) in {CACHE_DIR}")
            else:
                wc = len(user_input.split())
                print(f"  Speaking ({len(user_input)} chars, {wc} words)…")
                ok = text_to_speech(user_input)
                print(f"  Completed: {ok}")

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
    finally:
        pygame.mixer.quit()
