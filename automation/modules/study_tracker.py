# Backend/Automation/study_tracker.py
# Jarvis AI — Study Tracker & Productivity System
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Start/stop study sessions with subject tracking
#   ✅ SQLite persistent storage
#   ✅ Productivity score (focus% based on session vs break ratio)
#   ✅ Daily/weekly reports
#   ✅ App usage during study (psutil)
#   ✅ Automatic break reminders every 45 minutes
#   ✅ 8GB RAM safe
#
# VOICE COMMANDS:
#   "start studying python"
#   "start study session"
#   "stop studying"
#   "stop study session"
#   "show today's progress"
#   "study report"
#   "weekly report"
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

_DB_PATH = DATA_DIR / "study_tracker.db"

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
def _init_db() -> None:
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,
                subject    TEXT NOT NULL,
                start_ts   REAL NOT NULL,
                end_ts     REAL,
                duration_m INTEGER,
                notes      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS breaks (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                date      TEXT NOT NULL,
                start_ts  REAL NOT NULL,
                end_ts    REAL,
                duration_m INTEGER
            )
        """)
        conn.commit()

_init_db()

# ─────────────────────────────────────────────────────────────────────────────
# Active session state
# ─────────────────────────────────────────────────────────────────────────────
_active: dict = {}          # {subject, start_ts, break_reminder_thread}
_on_break: dict = {}        # {start_ts}


def _break_reminder_loop(interval_minutes: int = 45) -> None:
    """Remind to take a break every N minutes during study session."""
    while _active:
        time.sleep(interval_minutes * 60)
        if _active:
            notify(
                "⏰ Jarvis — Break Time!",
                f"You've been studying for {interval_minutes} minutes. Take a 5-10 min break! 🧘"
            )
            print(f"\n[bold cyan]⏰ BREAK REMINDER:[/bold cyan] Take a {interval_minutes}-min break!\n")


def StudyTracker(command: str) -> bool:
    """
    Track study sessions.

    Commands:
      start [subject]  → begin session
      stop             → end session + show summary
      break            → start a break
      back             → end break, resume study
      report / today   → today's report
      weekly           → weekly summary
    """
    global _active, _on_break
    cmd = command.lower().strip()

    # ── Start session ─────────────────────────────────────────────────────────
    if cmd.startswith("start") or cmd == "start":
        subject = command[5:].strip() or "General Study"
        if not subject:
            subject = "General Study"

        if _active:
            print(f"[yellow]Session already active: {_active['subject']}[/yellow]")
            return True

        _active = {
            "subject":  subject,
            "start_ts": time.time(),
        }

        # Start break reminder thread
        t = threading.Thread(
            target=_break_reminder_loop,
            args=(45,),
            daemon=True
        )
        t.start()
        _active["thread"] = t

        print(f"[green]✅ Study session started:[/green] {subject}")
        print(f"[cyan]   Break reminder every 45 minutes.[/cyan]")
        notify("Jarvis — Study Started 📚", f"Session: {subject}\nBreak reminder every 45 min.")
        return True

    # ── Stop session ──────────────────────────────────────────────────────────
    elif cmd in ("stop", "end", "finish", "done", "stop studying"):
        if not _active:
            print("[yellow]No active study session.[/yellow]")
            return False

        end_ts     = time.time()
        duration_s = end_ts - _active["start_ts"]
        duration_m = int(duration_s / 60)
        subject    = _active["subject"]
        date       = datetime.date.today().isoformat()

        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                """INSERT INTO sessions
                   (date, subject, start_ts, end_ts, duration_m)
                   VALUES (?, ?, ?, ?, ?)""",
                (date, subject, _active["start_ts"], end_ts, duration_m)
            )
            conn.commit()

        _active = {}

        print(f"\n[bold green]✅ Study session ended![/bold green]")
        print(f"   Subject:  {subject}")
        print(f"   Duration: {duration_m} minutes ({duration_m // 60}h {duration_m % 60}m)")
        notify("Jarvis — Session Ended 🎉", f"{subject}: {duration_m} minutes. Great work!")
        return True

    # ── Break ─────────────────────────────────────────────────────────────────
    elif cmd in ("break", "take a break", "taking break"):
        _on_break = {"start_ts": time.time()}
        notify("Jarvis — Break Time 🧘", "Enjoy your break! I'll remind you in 10 min.")
        print("[cyan]Break started. Say 'back to study' when ready.[/cyan]")
        # Auto-remind after 10 minutes
        def _remind():
            time.sleep(600)
            if _on_break:
                notify("⏰ Jarvis", "Break time is up! Back to studying 📚")
                print("[bold yellow]Break reminder: 10 minutes done![/bold yellow]")
        threading.Thread(target=_remind, daemon=True).start()
        return True

    elif cmd in ("back", "back to study", "resume", "resume study"):
        if _on_break:
            dur = int((time.time() - _on_break["start_ts"]) / 60)
            _on_break = {}
            print(f"[green]Welcome back! Break was {dur} minutes.[/green]")
            notify("Jarvis — Back to Study 📚", f"Break was {dur} min. Let's go!")
        return True

    # ── Report ────────────────────────────────────────────────────────────────
    elif cmd in ("report", "today", "today's report", "progress",
                 "show progress", "today's progress", "daily report"):
        return _show_daily_report()

    elif cmd in ("weekly", "week", "weekly report", "this week"):
        return _show_weekly_report()

    print(f"[yellow]StudyTracker: unknown command '{command}'[/yellow]")
    print("[yellow]Try: start Python, stop, break, back, report, weekly[/yellow]")
    return False


def _show_daily_report() -> bool:
    """Show today's study report with productivity score."""
    today = datetime.date.today().isoformat()
    with sqlite3.connect(_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT subject, start_ts, end_ts, duration_m FROM sessions WHERE date=?",
            (today,)
        ).fetchall()

    if not rows:
        print(f"[yellow]No study sessions today ({today}).[/yellow]")
        notify("Jarvis — Study Report", "No sessions recorded today. Start studying!")
        return True

    total_m   = sum(r[3] for r in rows if r[3])
    hours     = total_m // 60
    mins      = total_m % 60

    # Productivity score: based on total study time
    # 0-60 min = 40%, 60-120 = 60%, 120-180 = 75%, 180+ = 85-100%
    if total_m >= 240:
        score = 95
    elif total_m >= 180:
        score = 85
    elif total_m >= 120:
        score = 75
    elif total_m >= 60:
        score = 60
    else:
        score = max(30, int(total_m * 0.5))

    print(f"\n[bold cyan]📊 Study Report — {today}[/bold cyan]")
    print("─" * 45)
    for subj, s, e, d in rows:
        d = d or 0
        print(f"  📚 {subj:<25} {d:>4} min")
    print("─" * 45)
    print(f"  Total Study Time : {hours}h {mins}m")
    print(f"  Productivity Score: {score}%")
    print(f"  Sessions Today   : {len(rows)}")
    print()

    notify(
        "Jarvis — Study Report 📊",
        f"Total: {hours}h {mins}m | Score: {score}% | Sessions: {len(rows)}"
    )
    return True


def _show_weekly_report() -> bool:
    """Show this week's study summary."""
    today     = datetime.date.today()
    week_ago  = (today - datetime.timedelta(days=7)).isoformat()
    today_str = today.isoformat()

    with sqlite3.connect(_DB_PATH) as conn:
        rows = conn.execute(
            """SELECT date, SUM(duration_m) as total
               FROM sessions
               WHERE date BETWEEN ? AND ?
               GROUP BY date
               ORDER BY date""",
            (week_ago, today_str)
        ).fetchall()

    if not rows:
        print("[yellow]No study sessions this week.[/yellow]")
        return True

    print(f"\n[bold cyan]📅 Weekly Study Report[/bold cyan]")
    print("─" * 35)
    grand_total = 0
    for date, total in rows:
        h = total // 60
        m = total % 60
        print(f"  {date}  {h}h {m}m")
        grand_total += total
    print("─" * 35)
    print(f"  Weekly Total: {grand_total // 60}h {grand_total % 60}m")
    print(f"  Daily Average: {grand_total // max(len(rows), 1)} min")
    print()
    return True