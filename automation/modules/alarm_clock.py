# Backend/Automation/alarm_clock.py
# ─────────────────────────────────────────────────────────────────────────────
# JARVIS AI — Alarm & Clock System
#
# VOICE COMMANDS:
#   "set alarm for 7:30 am"
#   "set clock for 5 minutes"
#   "set timer for 10 minutes"
#   "set alarm for 30 seconds"
#   "stop alarm"
#   "stop clock"
#   "stop timer"
#   "cancel alarm"
#   "list alarms"
#
# FEATURES:
#   - Multiple simultaneous alarms/timers
#   - Instant stop (responds in < 100ms)
#   - Rings with system beep + pygame (if available)
#   - Countdown display in terminal
#   - Warns 1 minute before alarm fires
#   - Persists alarms to Data/alarms.json (survives restart)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
import re
import threading
import time
import datetime
import os
import sys
from pathlib import Path
from typing import Optional

# ── paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path("Data")
ALARM_FILE = DATA_DIR / "alarms.json"
LOG_DIR    = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("jarvis.alarm")

# ── optional notifier ─────────────────────────────────────────────────────────
try:
    from .notifier import notify as _notify
except ImportError:
    def _notify(t, m): pass

# ── optional TTS ─────────────────────────────────────────────────────────────
try:
    from Backend.TextToSpeech import TextToSpeech as _tts
    _HAS_TTS = True
except ImportError:
    _HAS_TTS = False

# ── optional pygame for alarm sound ──────────────────────────────────────────
try:
    import pygame
    pygame.mixer.init()
    _HAS_PYGAME = True
except Exception:
    _HAS_PYGAME = False


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE  (all access protected by _lock)
# ══════════════════════════════════════════════════════════════════════════════

_lock           = threading.Lock()
_alarms: dict[str, dict] = {}   # id -> alarm dict
_stop_events: dict[str, threading.Event] = {}
_alarm_counter  = 0              # used to generate unique IDs


def _new_id() -> str:
    global _alarm_counter
    with _lock:
        _alarm_counter += 1
        return f"alarm_{_alarm_counter}"


# ══════════════════════════════════════════════════════════════════════════════
# SOUND
# ══════════════════════════════════════════════════════════════════════════════

def _ring(label: str, stop_event: threading.Event) -> None:
    """
    Ring alarm: beep 3 times, then speak via TTS.
    Stops immediately if stop_event is set.
    """
    # Terminal bell
    for _ in range(3):
        if stop_event.is_set():
            return
        sys.stdout.write("\a")
        sys.stdout.flush()
        time.sleep(0.6)

    # Pygame beep tone
    if _HAS_PYGAME and not stop_event.is_set():
        try:
            import numpy as np
            sample_rate = 44100
            duration    = 0.5
            freq        = 880
            t           = np.linspace(0, duration, int(sample_rate * duration), False)
            wave        = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
            stereo      = np.column_stack([wave, wave])
            sound       = pygame.sndarray.make_sound(stereo)
            for _ in range(3):
                if stop_event.is_set():
                    break
                sound.play()
                time.sleep(0.7)
        except Exception:
            pass

    # TTS announcement
    if _HAS_TTS and not stop_event.is_set():
        try:
            _tts(f"Alarm! {label}. Your time is up!")
        except Exception:
            pass

    # Notification
    if not stop_event.is_set():
        _notify(f"⏰ Alarm: {label}", "Time is up!")
        print(f"\n\n  ⏰  ALARM: {label}  — Time is up!\n")


# ══════════════════════════════════════════════════════════════════════════════
# ALARM WORKER THREAD
# ══════════════════════════════════════════════════════════════════════════════

def _alarm_worker(alarm_id: str, label: str, fire_time: float,
                  stop_event: threading.Event) -> None:
    """
    Sleeps until fire_time, then rings.
    Checks stop_event every 100ms for instant cancellation.
    Warns 60 seconds before firing.
    """
    warned = False

    while True:
        if stop_event.is_set():
            log.info("Alarm '%s' cancelled.", label)
            print(f"\n  ✅  Alarm '{label}' stopped.")
            break

        remaining = fire_time - time.time()

        if remaining <= 0:
            # Time to ring
            _ring(label, stop_event)
            break

        # Warn 1 minute before
        if not warned and 55 <= remaining <= 65:
            warned = True
            _notify(f"Alarm in 1 min: {label}", "")
            if _HAS_TTS:
                try:
                    _tts(f"Heads up. {label} alarm in 1 minute.")
                except Exception:
                    pass
            print(f"\n  ⏰  1 minute warning: {label}")

        # Sleep in short intervals for fast stop response
        time.sleep(min(0.1, remaining))

    # Clean up
    with _lock:
        _alarms.pop(alarm_id, None)
        _stop_events.pop(alarm_id, None)

    _save_alarms()


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

def _save_alarms() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        data = {k: v for k, v in _alarms.items()}
    try:
        ALARM_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_alarms() -> None:
    """Restore alarms from file on startup, skip any already past."""
    if not ALARM_FILE.exists():
        return
    try:
        data = json.loads(ALARM_FILE.read_text(encoding="utf-8"))
        now  = time.time()
        for alarm_id, alarm in data.items():
            fire_time = alarm.get("fire_time", 0)
            if fire_time > now + 5:          # only restore future alarms
                SetAlarm(
                    label     = alarm.get("label", "Alarm"),
                    fire_time = fire_time,
                    _alarm_id = alarm_id,
                )
    except Exception as e:
        log.warning("Could not restore alarms: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def SetAlarm(label: str, fire_time: float,
             _alarm_id: Optional[str] = None) -> str:
    """
    Schedule an alarm at a specific Unix timestamp.

    Parameters
    ----------
    label     : str    — human-readable name e.g. "5 minute timer"
    fire_time : float  — Unix timestamp when alarm fires
    _alarm_id : str    — internal override (used for restore from file)

    Returns
    -------
    str  — alarm_id
    """
    alarm_id   = _alarm_id or _new_id()
    stop_event = threading.Event()

    with _lock:
        _alarms[alarm_id]      = {"label": label, "fire_time": fire_time}
        _stop_events[alarm_id] = stop_event

    t = threading.Thread(
        target   = _alarm_worker,
        args     = (alarm_id, label, fire_time, stop_event),
        daemon   = True,
        name     = f"alarm-{alarm_id}",
    )
    t.start()
    _save_alarms()

    remaining = fire_time - time.time()
    mins, secs = divmod(int(remaining), 60)
    hrs,  mins = divmod(mins, 60)

    parts = []
    if hrs:  parts.append(f"{hrs}h")
    if mins: parts.append(f"{mins}m")
    if secs: parts.append(f"{secs}s")
    time_str = " ".join(parts) or "now"

    print(f"\n  ⏰  Alarm set: '{label}'  — fires in {time_str}")
    log.info("Alarm set: %s  fires in %s", label, time_str)
    _notify(f"Alarm Set: {label}", f"Fires in {time_str}")

    if _HAS_TTS:
        try:
            _tts(f"Alarm set for {time_str}.")
        except Exception:
            pass

    return alarm_id


def StopAlarm(identifier: str = "") -> bool:
    """
    Stop alarm(s) instantly.

    Parameters
    ----------
    identifier : str
        Alarm ID, label substring, or "" to stop ALL alarms.

    Returns
    -------
    bool  — True if at least one alarm was stopped
    """
    stopped = 0
    with _lock:
        ids_to_stop = list(_stop_events.keys())

    if identifier:
        # Filter by label or id
        ident_low = identifier.lower()
        with _lock:
            ids_to_stop = [
                aid for aid, alarm in _alarms.items()
                if ident_low in alarm.get("label", "").lower()
                or ident_low in aid.lower()
            ]

    for aid in ids_to_stop:
        with _lock:
            ev = _stop_events.get(aid)
        if ev:
            ev.set()          # instant stop — thread checks this every 100ms
            stopped += 1

    if stopped:
        log.info("Stopped %d alarm(s)", stopped)
        _notify("Alarm Stopped", f"{stopped} alarm(s) cancelled")
    else:
        print("\n  ℹ  No active alarms to stop.")

    return stopped > 0


def ListAlarms() -> list[dict]:
    """Return list of all active alarms with remaining time."""
    now = time.time()
    result = []
    with _lock:
        for aid, alarm in _alarms.items():
            remaining = max(0, alarm["fire_time"] - now)
            mins, secs = divmod(int(remaining), 60)
            hrs, mins  = divmod(mins, 60)
            parts = []
            if hrs:  parts.append(f"{hrs}h")
            if mins: parts.append(f"{mins}m")
            if secs: parts.append(f"{secs}s")
            result.append({
                "id":        aid,
                "label":     alarm["label"],
                "remaining": " ".join(parts) or "ringing",
            })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# VOICE COMMAND PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_duration(text: str) -> Optional[int]:
    """
    Extract total seconds from a duration string.

    Examples
    --------
    "5 minutes"       → 300
    "1 hour 30 min"   → 5400
    "45 seconds"      → 45
    "2 hours"         → 7200
    """
    text  = text.lower()
    total = 0

    patterns = [
        (r"(\d+)\s*hour",   3600),
        (r"(\d+)\s*hr",     3600),
        (r"(\d+)\s*min",    60),
        (r"(\d+)\s*sec",    1),
        (r"(\d+)\s*s\b",    1),
    ]
    for pattern, multiplier in patterns:
        m = re.search(pattern, text)
        if m:
            total += int(m.group(1)) * multiplier

    return total if total > 0 else None


def _parse_clock_time(text: str) -> Optional[float]:
    """
    Parse a specific time like "7:30 am", "14:00", "9 pm".

    Returns
    -------
    float | None  — Unix timestamp for that time today (or tomorrow if past)
    """
    text = text.lower().strip()
    # HH:MM am/pm
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = m.group(3)
        if ampm == "pm" and hour < 12: hour += 12
        if ampm == "am" and hour == 12: hour = 0
    else:
        # H am/pm
        m = re.search(r"(\d{1,2})\s*(am|pm)", text)
        if not m:
            return None
        hour   = int(m.group(1))
        minute = 0
        ampm   = m.group(2)
        if ampm == "pm" and hour < 12: hour += 12
        if ampm == "am" and hour == 12: hour = 0

    now   = datetime.datetime.now()
    alarm = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if alarm <= now:
        alarm += datetime.timedelta(days=1)   # schedule for tomorrow

    return alarm.timestamp()


def handle_alarm_command(command: str) -> str:
    """
    Parse a voice command and set/stop alarms.

    Parameters
    ----------
    command : str

    Returns
    -------
    str  — response message for Jarvis to speak
    """
    cmd = command.lower().strip()

    # ── STOP commands — checked FIRST for speed ───────────────────────────
    if any(w in cmd for w in ("stop", "cancel", "dismiss", "silence", "snooze off")):
        ok = StopAlarm()
        return "All alarms stopped." if ok else "No active alarms."

    # ── LIST ──────────────────────────────────────────────────────────────
    if "list" in cmd or "show" in cmd:
        alarms = ListAlarms()
        if not alarms:
            return "No active alarms."
        lines = "\n".join(f"  {a['label']}: {a['remaining']} remaining" for a in alarms)
        print(f"\n  Active alarms:\n{lines}\n")
        return f"You have {len(alarms)} active alarm{'s' if len(alarms)>1 else ''}."

    # ── DURATION-based (timer / clock) ────────────────────────────────────
    duration_secs = _parse_duration(cmd)
    if duration_secs:
        mins, secs = divmod(duration_secs, 60)
        hrs,  mins = divmod(mins, 60)
        parts = []
        if hrs:  parts.append(f"{hrs} hour{'s' if hrs>1 else ''}")
        if mins: parts.append(f"{mins} minute{'s' if mins>1 else ''}")
        if secs: parts.append(f"{secs} second{'s' if secs>1 else ''}")
        label     = " ".join(parts) + " timer"
        fire_time = time.time() + duration_secs
        SetAlarm(label, fire_time)
        return f"Timer set for {' '.join(parts)}."

    # ── Specific time (7:30 am etc.) ─────────────────────────────────────
    fire_time = _parse_clock_time(cmd)
    if fire_time:
        t_str = datetime.datetime.fromtimestamp(fire_time).strftime("%I:%M %p")
        label = f"Alarm at {t_str}"
        SetAlarm(label, fire_time)
        return f"Alarm set for {t_str}."

    return "I couldn't understand that alarm time. Try: 'set timer for 5 minutes' or 'set alarm for 7:30 am'."


# ── Restore on import ─────────────────────────────────────────────────────────
_load_alarms()