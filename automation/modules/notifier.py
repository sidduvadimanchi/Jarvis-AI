# Backend/Automation/notifier.py
# Jarvis AI — Notification & Reminder System
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Desktop notifications (plyer)
#   ✅ Background thread reminders (no external scheduler needed)
#   ✅ Smart time parsing (9pm, 21:00, 9:30 PM all work)
#   ✅ Tomorrow scheduling if time already passed
#   ✅ 8GB RAM safe — pure threading, no heavy libraries
#
# VOICE COMMANDS:
#   "remind me at 9pm to study"
#   "remind me in 30 minutes to take a break"
#   "set reminder at 8am for morning workout"
#   "notify me now"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import datetime
import threading
import time
from typing import Optional


def notify(title: str, message: str, timeout: int = 8) -> None:
    """Show a desktop notification. Silent fail if plyer not installed."""
    try:
        from plyer import notification  # type: ignore
        notification.notify(
            title   = title,
            message = message,
            app_name= "Jarvis AI",
            timeout = timeout,
        )
    except Exception:
        # Fallback — print to terminal
        print(f"\n🔔 [{title}] {message}\n")


def Notify(message: str) -> bool:
    """
    Show an immediate desktop notification.
    Voice: "notify meeting in 5 minutes"
    """
    msg = message.strip() if message.strip() else "Reminder from Jarvis"
    notify("⚡ Jarvis", msg)
    print(f"[green]Notification sent:[/green] {msg}")
    return True


def _parse_time(time_str: str) -> Optional[datetime.datetime]:
    """
    Parse a time string into a datetime object.
    Supports: 9pm, 21:00, 9:30pm, 9:30 PM, in 30 minutes, in 2 hours
    """
    now = datetime.datetime.now()
    ts  = time_str.strip().lower()

    # "in X minutes" / "in X hours"
    if ts.startswith("in "):
        parts = ts.split()
        try:
            val  = int(parts[1])
            unit = parts[2] if len(parts) > 2 else "minutes"
            if "hour" in unit:
                return now + datetime.timedelta(hours=val)
            else:
                return now + datetime.timedelta(minutes=val)
        except Exception:
            pass

    # Standard time formats
    for fmt in ("%I:%M%p", "%I%p", "%H:%M", "%I:%M %p", "%I %p",
                "%I:%M%P", "%I%P", "%I:%M %P"):
        try:
            t = datetime.datetime.strptime(ts.upper(), fmt)
            result = now.replace(
                hour=t.hour, minute=t.minute,
                second=0, microsecond=0
            )
            if result <= now:
                result += datetime.timedelta(days=1)
            return result
        except ValueError:
            continue
    return None


def Reminder(reminder_str: str) -> bool:
    """
    Parse and schedule a reminder in a background thread.
    Model.py sends format: "9:00pm study data structures"
    Also handles: "in 30 minutes take a break"

    Voice examples:
      "remind me at 9pm to study"
      "set reminder at 8am for workout"
      "remind me in 30 minutes to take a break"
    """
    parts   = reminder_str.strip().split()
    if not parts:
        print("[yellow]Reminder: nothing to schedule.[/yellow]")
        return False

    time_str = parts[0]
    message  = " ".join(parts[1:]) if len(parts) > 1 else "Reminder"

    # Handle "in X minutes/hours" format
    if time_str == "in" and len(parts) >= 3:
        time_str = " ".join(parts[:3])
        message  = " ".join(parts[3:]) if len(parts) > 3 else "Reminder"

    remind_at = _parse_time(time_str)

    if remind_at is None:
        # Fallback: 1 minute from now
        remind_at = datetime.datetime.now() + datetime.timedelta(minutes=1)
        print(f"[yellow]Could not parse '{time_str}' — reminding in 1 minute.[/yellow]")

    delay = (remind_at - datetime.datetime.now()).total_seconds()
    if delay < 0:
        delay = 60

    print(f"[green]✅ Reminder set:[/green] '{message}' at {remind_at.strftime('%I:%M %p')} ({int(delay)}s)")
    notify("⏰ Reminder Set", f"'{message}' at {remind_at.strftime('%I:%M %p')}")

    def _fire():
        time.sleep(delay)
        notify("⏰ Jarvis Reminder", message, timeout=15)
        print(f"\n[bold cyan]⏰ REMINDER:[/bold cyan] {message}\n")

    threading.Thread(target=_fire, daemon=True, name=f"reminder_{message[:20]}").start()
    return True