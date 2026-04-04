# Backend/Brain/task_manager.py
# Jarvis AI — Task Manager v2.0
# Persistent SQLite tasks, priorities, deadlines, daily performance, voice parsing
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sqlite3
import datetime
import re
import threading
from pathlib import Path
from typing  import Optional

_DB   = Path("Data") / "tasks.db"
_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    description  TEXT    DEFAULT '',
    priority     TEXT    DEFAULT 'medium',
    status       TEXT    DEFAULT 'pending',
    category     TEXT    DEFAULT 'general',
    due_date     TEXT,
    due_time     TEXT,
    created_at   TEXT    NOT NULL,
    completed_at TEXT,
    reminder_sent INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS daily_log (
    date        TEXT PRIMARY KEY,
    tasks_done  INTEGER DEFAULT 0,
    tasks_total INTEGER DEFAULT 0,
    score       INTEGER DEFAULT 0,
    note        TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_due      ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority);
"""

_PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
_CATEGORY_ICONS = {
    "study": "📚", "work": "💼", "personal": "👤",
    "health": "💪", "general": "📌",
}


def _conn() -> sqlite3.Connection:
    Path("Data").mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


# ── CRUD ──────────────────────────────────────────────────────

def add_task(title: str, description: str = "", priority: str = "medium",
             category: str = "general", due_date: Optional[str] = None,
             due_time: Optional[str] = None) -> int:
    with _lock:
        c   = _conn()
        cur = c.execute(
            "INSERT INTO tasks(title,description,priority,category,due_date,due_time,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (title, description, priority.lower(), category.lower(),
             due_date, due_time, datetime.datetime.now().isoformat()),
        )
        c.commit(); tid = cur.lastrowid; c.close()
    return tid


def get_tasks(status: Optional[str] = None, category: Optional[str] = None,
              today_only: bool = False) -> list[dict]:
    with _lock:
        c     = _conn()
        query = "SELECT * FROM tasks WHERE 1=1"
        args  = []
        if status:   query += " AND status=?";   args.append(status)
        if category: query += " AND category=?"; args.append(category)
        if today_only:
            today = datetime.date.today().isoformat()
            query += " AND (due_date=? OR due_date IS NULL)"; args.append(today)
        query += (" ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1"
                  " WHEN 'medium' THEN 2 ELSE 3 END, due_date ASC NULLS LAST")
        rows = c.execute(query, args).fetchall(); c.close()
    return [dict(r) for r in rows]


def get_task_by_id(tid: int) -> Optional[dict]:
    with _lock:
        c = _conn()
        r = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        c.close()
    return dict(r) if r else None


def update_task_status(tid: int, status: str) -> bool:
    with _lock:
        c   = _conn()
        done = datetime.datetime.now().isoformat() if status == "done" else None
        c.execute("UPDATE tasks SET status=?, completed_at=? WHERE id=?", (status, done, tid))
        c.commit(); c.close()
    _update_daily_log()
    return True


def delete_task(tid: int) -> bool:
    with _lock:
        c = _conn()
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        c.commit(); c.close()
    return True


def edit_task(tid: int, **kwargs) -> bool:
    allowed = {"title", "description", "priority", "category", "due_date", "due_time", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates: return False
    with _lock:
        c = _conn()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE tasks SET {set_clause} WHERE id=?",
                  list(updates.values()) + [tid])
        c.commit(); c.close()
    return True


# ── PERFORMANCE ───────────────────────────────────────────────

def _update_daily_log() -> None:
    today = datetime.date.today().isoformat()
    with _lock:
        c     = _conn()
        total = c.execute("SELECT COUNT(*) FROM tasks WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0]
        done  = c.execute("SELECT COUNT(*) FROM tasks WHERE status='done' AND completed_at LIKE ?", (f"{today}%",)).fetchone()[0]
        score = int(done / total * 100) if total > 0 else 0
        c.execute("INSERT OR REPLACE INTO daily_log(date,tasks_done,tasks_total,score) VALUES(?,?,?,?)",
                  (today, done, total, score))
        c.commit(); c.close()


def get_today_performance() -> dict:
    today = datetime.date.today().isoformat()
    with _lock:
        c        = _conn()
        pending  = c.execute("SELECT COUNT(*) FROM tasks WHERE status='pending' AND (due_date<=? OR due_date IS NULL)", (today,)).fetchone()[0]
        in_prog  = c.execute("SELECT COUNT(*) FROM tasks WHERE status='in_progress'").fetchone()[0]
        done_t   = c.execute("SELECT COUNT(*) FROM tasks WHERE status='done' AND completed_at LIKE ?", (f"{today}%",)).fetchone()[0]
        overdue  = c.execute("SELECT COUNT(*) FROM tasks WHERE status NOT IN ('done','cancelled') AND due_date<? AND due_date IS NOT NULL", (today,)).fetchone()[0]
        urgent   = c.execute("SELECT * FROM tasks WHERE priority='urgent' AND status='pending'").fetchall()
        c.close()
    total = pending + in_prog + done_t
    return {
        "pending": pending, "in_progress": in_prog, "done_today": done_t,
        "overdue": overdue, "score": int(done_t/total*100) if total else 0,
        "urgent_tasks": [dict(r) for r in urgent], "total": total,
    }


def get_weekly_performance() -> list[dict]:
    result = []
    for i in range(6, -1, -1):
        d = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        with _lock:
            c   = _conn()
            row = c.execute("SELECT * FROM daily_log WHERE date=?", (d,)).fetchone()
            c.close()
        result.append(dict(row) if row else {"date": d, "tasks_done": 0, "tasks_total": 0, "score": 0})
    return result


def get_due_soon(minutes: int = 5) -> list[dict]:
    now      = datetime.datetime.now()
    deadline = (now + datetime.timedelta(minutes=minutes)).strftime("%H:%M")
    today    = now.date().isoformat()
    with _lock:
        c    = _conn()
        rows = c.execute(
            "SELECT * FROM tasks WHERE status='pending' AND due_date=? AND due_time<=? AND reminder_sent=0",
            (today, deadline),
        ).fetchall(); c.close()
    return [dict(r) for r in rows]


def mark_reminder_sent(tid: int) -> None:
    with _lock:
        c = _conn()
        c.execute("UPDATE tasks SET reminder_sent=1 WHERE id=?", (tid,))
        c.commit(); c.close()


# ── VOICE PARSER ──────────────────────────────────────────────

def parse_task_from_voice(cmd: str) -> Optional[dict]:
    """Parse natural language task command into structured dict."""
    low = cmd.lower()

    # Extract title
    for pat in [
        r"(?:add|create|new|set)(?:\s+\w+)?\s+task\s+(?:to\s+)?(.+?)(?:\s+(?:at|by|before|high|low|urgent|today|tomorrow)|$)",
        r"remind\s+me\s+to\s+(.+?)(?:\s+(?:at|by|today|tomorrow)|$)",
        r"todo[:\s]+(.+?)(?:\s+at|\s+by|$)",
    ]:
        m = re.search(pat, low)
        if m:
            title = m.group(1).strip()
            break
    else:
        title = re.sub(r"^(?:add|create|new|set|remind me to|todo)\s*", "", low).strip()

    if not title or len(title) < 3:
        return None

    priority = "medium"
    if any(w in low for w in ["urgent","asap","critical","immediately"]): priority = "urgent"
    elif any(w in low for w in ["high","important","must","need to"]):    priority = "high"
    elif any(w in low for w in ["low","whenever","optional","later"]):    priority = "low"

    category = "general"
    if any(w in low for w in ["study","learn","assignment","homework","exam","class","notes"]): category = "study"
    elif any(w in low for w in ["work","job","meeting","client","submit","project","office"]):  category = "work"
    elif any(w in low for w in ["gym","exercise","health","doctor","medicine","water"]):        category = "health"
    elif any(w in low for w in ["family","friend","personal","birthday","call"]):               category = "personal"

    due_time = None
    tm = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
    if tm:
        h = int(tm.group(1)); m2 = int(tm.group(2) or 0); ap = tm.group(3)
        if ap == "pm" and h < 12: h += 12
        elif ap == "am" and h == 12: h = 0
        due_time = f"{h:02d}:{m2:02d}"

    due_date = None
    if "today"    in low: due_date = datetime.date.today().isoformat()
    elif "tomorrow" in low: due_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    return {"title": title.title(), "priority": priority,
            "category": category, "due_date": due_date, "due_time": due_time}


def format_task_speech(task: dict) -> str:
    icon  = _CATEGORY_ICONS.get(task.get("category", "general"), "📌")
    title = task.get("title", "Task")
    due   = task.get("due_time", "")
    prio  = task.get("priority", "medium")
    return f"{icon} {title}" + (f" at {due}" if due else "") + \
           (f" — {prio} priority" if prio in ("urgent","high") else "")


def start_reminder_thread(speak_fn=None) -> None:
    """Background thread: checks due tasks every 60s, calls speak_fn when due."""
    import time
    def _loop():
        while True:
            try:
                for task in get_due_soon(minutes=5):
                    mark_reminder_sent(task["id"])
                    msg = f"Reminder: {task['title']} is due at {task.get('due_time','soon')}!"
                    if speak_fn:
                        try: speak_fn(msg)
                        except Exception: pass
                    else:
                        print(f"\n🔔 {msg}")
            except Exception: pass
            time.sleep(60)
    threading.Thread(target=_loop, daemon=True).start()


# ── TESTS ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, tempfile
    _DB = Path(tempfile.mkdtemp()) / "test_tasks.db"

    tests = [
        ("add task study python at 3pm today high priority",
         {"title_contains":"Study Python","priority":"high","due_time":"15:00"}),
        ("remind me to submit assignment by tomorrow urgent",
         {"title_contains":"Submit Assignment","priority":"urgent"}),
        ("create work task client meeting at 2pm tomorrow",
         {"category":"work","due_time":"14:00"}),
        ("todo drink water at 8am today",
         {"due_time":"08:00","due_date": datetime.date.today().isoformat()}),
        ("add task gym workout health category low priority",
         {"category":"health","priority":"low"}),
    ]

    print("\n=== TASK VOICE PARSER — TEST SUITE ===\n")
    passed = 0
    for cmd, expected in tests:
        result = parse_task_from_voice(cmd)
        ok = True
        if result is None:
            ok = False
        else:
            for k, v in expected.items():
                if k == "title_contains":
                    if v.lower() not in result.get("title","").lower(): ok = False
                elif result.get(k) != v:
                    ok = False
        status = "✅" if ok else "❌"
        if ok: passed += 1
        print(f"  {status}  '{cmd[:55]}'")
        print(f"       Got: {result}\n")

    # CRUD test
    print("=== CRUD OPERATIONS TEST ===\n")
    tid = add_task("Test Task", priority="high", category="study",
                   due_date=datetime.date.today().isoformat(), due_time="14:00")
    assert get_task_by_id(tid)["title"] == "Test Task", "Add failed"
    update_task_status(tid, "done")
    assert get_task_by_id(tid)["status"] == "done", "Update failed"
    perf = get_today_performance()
    assert perf["done_today"] >= 1, "Performance tracking failed"
    delete_task(tid)
    assert get_task_by_id(tid) is None, "Delete failed"
    print("  ✅  add_task → PASS")
    print("  ✅  update_task_status → PASS")
    print("  ✅  get_today_performance → PASS")
    print("  ✅  delete_task → PASS")
    print(f"\nVoice Parser Score: {passed}/{len(tests)} = {100*passed//len(tests)}%")