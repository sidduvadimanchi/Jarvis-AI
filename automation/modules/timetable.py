# Backend/Automation/timetable.py
# Jarvis AI — Smart Timetable System
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ SQLite timetable storage (persists forever)
#   ✅ Auto class reminders (5 min before each class)
#   ✅ Show today's / any day's schedule
#   ✅ Add / delete entries by voice
#   ✅ Default timetable pre-loaded
#   ✅ 8GB RAM safe — pure threading
#
# VOICE COMMANDS:
#   "show my timetable"
#   "show timetable for Monday"
#   "timetable add Monday 9:00 AM Physics"
#   "timetable delete Physics"
#   "what is my schedule today"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import datetime
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from .notifier import notify

_env     = dotenv_values(".env")
DATA_DIR = Path(_env.get("DataDir", "Data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = DATA_DIR / "timetable.db"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _init_db() -> None:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                day     TEXT NOT NULL,
                time    TEXT NOT NULL,
                subject TEXT NOT NULL,
                notes   TEXT DEFAULT ''
            )
        """)
        # Load default if empty
        if conn.execute("SELECT COUNT(*) FROM timetable").fetchone()[0] == 0:
            defaults = [
                ("Monday",    "08:00 AM", "Mathematics",           ""),
                ("Monday",    "10:00 AM", "Break",                 ""),
                ("Monday",    "10:30 AM", "Programming Practice",  ""),
                ("Monday",    "02:00 PM", "Data Structures",       ""),
                ("Tuesday",   "08:00 AM", "Physics",               ""),
                ("Tuesday",   "10:00 AM", "Break",                 ""),
                ("Tuesday",   "10:30 AM", "Machine Learning",      ""),
                ("Tuesday",   "02:00 PM", "Project Work",          ""),
                ("Wednesday", "08:00 AM", "Web Development",       ""),
                ("Wednesday", "10:00 AM", "Break",                 ""),
                ("Wednesday", "10:30 AM", "Database Systems",      ""),
                ("Wednesday", "02:00 PM", "Revision",              ""),
                ("Thursday",  "08:00 AM", "Computer Networks",     ""),
                ("Thursday",  "10:00 AM", "Break",                 ""),
                ("Thursday",  "10:30 AM", "Operating Systems",     ""),
                ("Thursday",  "02:00 PM", "Assignment Work",       ""),
                ("Friday",    "08:00 AM", "Algorithms",            ""),
                ("Friday",    "10:00 AM", "Break",                 ""),
                ("Friday",    "10:30 AM", "Practice Problems",     ""),
                ("Friday",    "02:00 PM", "Weekly Review",         ""),
                ("Saturday",  "09:00 AM", "Self Study",            ""),
                ("Saturday",  "11:00 AM", "Project",               ""),
                ("Sunday",    "10:00 AM", "Revision & Rest",       ""),
            ]
            conn.executemany(
                "INSERT INTO timetable (day, time, subject, notes) VALUES (?,?,?,?)",
                defaults
            )
        conn.commit()

_init_db()

# Track which reminders are already set today (avoid duplicates)
_reminders_set: set = set()


def _schedule_reminders_for_day(day: str, rows: list) -> int:
    """Schedule desktop notifications 5 min before each class today."""
    global _reminders_set
    now     = datetime.datetime.now()
    count   = 0

    for time_str, subject, notes in rows:
        if subject.lower() == "break":
            continue
        key = f"{day}_{time_str}_{subject}"
        if key in _reminders_set:
            continue

        try:
            t = datetime.datetime.strptime(time_str.strip(), "%I:%M %p")
            class_time  = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            remind_time = class_time - datetime.timedelta(minutes=5)

            if remind_time > now:
                delay = (remind_time - now).total_seconds()
                _reminders_set.add(key)

                def _fire(s=subject, d=delay, ct=class_time):
                    time.sleep(d)
                    notify(
                        "⏰ Jarvis — Class Starting!",
                        f"{s} starts in 5 minutes at {ct.strftime('%I:%M %p')} 📚"
                    )
                    print(f"\n[bold cyan]⏰ CLASS IN 5 MIN:[/bold cyan] {s} at {ct.strftime('%I:%M %p')}\n")

                threading.Thread(target=_fire, daemon=True).start()
                count += 1
        except Exception:
            continue

    return count


def ShowTimetable(day: str = "") -> bool:
    """
    Show timetable for a specific day or today.
    Voice: "show my timetable", "show timetable for Monday"
    """
    # Resolve day
    target_day = ""
    if day.strip():
        for d in DAYS:
            if d.lower().startswith(day.lower().strip()[:3]):
                target_day = d
                break
        if not target_day:
            target_day = day.strip().capitalize()
    else:
        target_day = datetime.datetime.now().strftime("%A")

    with sqlite3.connect(_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT time, subject, notes FROM timetable WHERE day=? ORDER BY time",
            (target_day,)
        ).fetchall()

    if not rows:
        print(f"[yellow]No timetable entries for {target_day}.[/yellow]")
        notify("Jarvis — Timetable", f"No schedule for {target_day}.")
        return True

    today = datetime.datetime.now().strftime("%A")
    print(f"\n[bold cyan]📅 Timetable — {target_day}[/bold cyan]")
    print(f"{'Time':<14} {'Subject':<28} Notes")
    print("─" * 55)

    for time_str, subject, notes in rows:
        icon = "☕" if subject.lower() == "break" else "📚"
        print(f"  {icon} {time_str:<12} {subject:<28} {notes or ''}")

    print()

    # Auto-set reminders if showing today
    if target_day == today:
        count = _schedule_reminders_for_day(target_day, rows)
        if count > 0:
            print(f"[green]✅ {count} class reminder(s) set for today![/green]")
            notify("Jarvis — Timetable", f"Showing {target_day} | {count} reminders set 🔔")
        else:
            notify("Jarvis — Timetable", f"Showing {target_day} schedule.")

    return True


def AddTimetableEntry(entry_str: str) -> bool:
    """
    Add an entry to the timetable.
    Format: "Monday 9:00 AM Physics notes here"
    Voice: "timetable add Monday 9:00 AM Physics"
    """
    try:
        parts = entry_str.strip().split()
        if len(parts) < 3:
            print("[yellow]Format: timetable add <Day> <Time> <AM/PM> <Subject>[/yellow]")
            print("[yellow]Example: timetable add Monday 9:00 AM Physics[/yellow]")
            return False

        # Parse day
        day = parts[0].capitalize()
        if day not in DAYS:
            print(f"[yellow]Invalid day: {day}. Use: {', '.join(DAYS)}[/yellow]")
            return False

        # Parse time (handle "9:00 AM" or "9AM" or "9:00AM")
        if len(parts) >= 3 and parts[2].upper() in ("AM", "PM"):
            time_str = f"{parts[1]} {parts[2].upper()}"
            subject  = " ".join(parts[3:]) if len(parts) > 3 else "Study"
        else:
            time_str = parts[1]
            subject  = " ".join(parts[2:]) if len(parts) > 2 else "Study"

        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO timetable (day, time, subject) VALUES (?,?,?)",
                (day, time_str, subject)
            )
            conn.commit()

        print(f"[green]✅ Added:[/green] {day} {time_str} — {subject}")
        notify("Jarvis — Timetable Updated", f"Added: {day} {time_str} {subject}")
        return True

    except Exception as e:
        print(f"[red]AddTimetableEntry failed:[/red] {e}")
        return False


def DeleteTimetableEntry(subject: str) -> bool:
    """
    Delete timetable entries matching subject name.
    Voice: "timetable delete Physics"
    """
    try:
        subject = subject.strip()
        with sqlite3.connect(_DB_PATH) as conn:
            deleted = conn.execute(
                "DELETE FROM timetable WHERE LOWER(subject) LIKE ?",
                (f"%{subject.lower()}%",)
            ).rowcount
            conn.commit()

        if deleted > 0:
            print(f"[green]✅ Deleted {deleted} entry/entries matching: '{subject}'[/green]")
            notify("Jarvis — Timetable", f"Deleted entries matching: {subject}")
        else:
            print(f"[yellow]No entries found matching: '{subject}'[/yellow]")
        return True

    except Exception as e:
        print(f"[red]DeleteTimetableEntry failed:[/red] {e}")
        return False


def ShowWeeklyTimetable() -> bool:
    """Show the full weekly timetable at once."""
    print("\n[bold cyan]📅 Weekly Timetable[/bold cyan]")
    print("═" * 60)
    for day in DAYS:
        with sqlite3.connect(_DB_PATH) as conn:
            rows = conn.execute(
                "SELECT time, subject FROM timetable WHERE day=? ORDER BY time",
                (day,)
            ).fetchall()
        if rows:
            print(f"\n  [bold]{day}[/bold]")
            for t, s in rows:
                icon = "☕" if s.lower() == "break" else "📚"
                print(f"    {icon} {t:<12} {s}")
    print()
    return True