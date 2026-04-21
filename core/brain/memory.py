# Backend/Brain/memory.py
# Jarvis AI — Persistent Memory (SQLite)
# Remembers conversations, emotions, topics across ALL sessions
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import sqlite3
import datetime
import threading
from pathlib import Path
from typing  import Optional

_DB_PATH = Path("Data") / "jarvis_memory.db"
_lock    = threading.Lock()

# ── Schema ────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,   -- 'user' or 'assistant'
    content     TEXT    NOT NULL,
    emotion     TEXT,               -- detected emotion at this turn
    topic       TEXT,               -- detected topic keyword
    timestamp   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_summary (
    date        TEXT PRIMARY KEY,
    summary     TEXT,
    emotions    TEXT,               -- comma-separated emotions of the day
    topics      TEXT,               -- comma-separated topics
    msg_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_facts (
    key         TEXT PRIMARY KEY,   -- e.g. 'name', 'college', 'roll_no'
    value       TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    source      TEXT,               -- 'search', 'user', 'interaction'
    updated_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_time    ON conversations(timestamp);
"""


# ── Persistent connection (BUG #5 FIX) ─────────────────────────────────────
# Previously opened a new SQLite connection on EVERY call—causing handle
# leaks and significant latency under load. Now we keep one persistent
# connection with WAL mode so concurrent reads never block each other.
_db_connection: "sqlite3.Connection | None" = None

def _conn() -> sqlite3.Connection:
    """Return the single, reusable database connection (thread-safe via _lock)."""
    global _db_connection
    if _db_connection is None:
        Path("Data").mkdir(parents=True, exist_ok=True)
        _db_connection = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _db_connection.row_factory = sqlite3.Row
        # WAL mode: readers don’t block writers, writers don’t block readers
        _db_connection.execute("PRAGMA journal_mode=WAL")
        _db_connection.execute("PRAGMA synchronous=NORMAL")  # Fast + safe
        _db_connection.executescript(_SCHEMA)
    return _db_connection


# ── Session ID (one per run) ──────────────────────────────────
import os, time as _time
_SESSION_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def save_turn(
    role    : str,
    content : str,
    emotion : Optional[str] = None,
    topic   : Optional[str] = None,
) -> None:
    """Save one conversation turn to persistent memory."""
    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO conversations (session_id,role,content,emotion,topic,timestamp)"
            " VALUES (?,?,?,?,?,?)",
            (_SESSION_ID, role, content[:2000], emotion, topic,
             datetime.datetime.now().isoformat()),
        )
        c.commit()
        c.close()


def get_recent(n: int = 20) -> list[dict]:
    """
    Get the last n conversation turns across ALL sessions.
    Returns list of dicts with keys: role, content, emotion, topic, timestamp.
    """
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT role,content,emotion,topic,timestamp FROM conversations"
            " ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
    return [dict(r) for r in reversed(rows)]


def get_yesterday_summary() -> Optional[str]:
    """Return yesterday's stored summary if available."""
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT summary FROM daily_summary WHERE date=?", (yesterday,)
        ).fetchone()
        c.close()
    return row["summary"] if row else None


def get_today_stats() -> dict:
    """Return today's message count, emotions, topics."""
    today = datetime.date.today().isoformat()
    with _lock:
        c   = _conn()
        cnt = c.execute(
            "SELECT COUNT(*) as n FROM conversations WHERE timestamp LIKE ?",
            (f"{today}%",)
        ).fetchone()["n"]
        emos = c.execute(
            "SELECT emotion, COUNT(*) as n FROM conversations"
            " WHERE timestamp LIKE ? AND emotion IS NOT NULL GROUP BY emotion",
            (f"{today}%",)
        ).fetchall()
        c.close()
    return {
        "count"   : cnt,
        "emotions": {r["emotion"]: r["n"] for r in emos},
    }


def save_user_fact(key: str, value: str) -> None:
    """Remember a fact about the user (name, college, etc.)."""
    with _lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO user_facts(key,value,updated_at) VALUES(?,?,?)",
            (key.lower(), value, datetime.datetime.now().isoformat()),
        )
        c.commit()
        c.close()


def get_user_fact(key: str) -> Optional[str]:
    """Retrieve a remembered user fact."""
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT value FROM user_facts WHERE key=?", (key.lower(),)
        ).fetchone()
        c.close()
    return row["value"] if row else None


def get_all_user_facts() -> dict:
    """Return all remembered user facts."""
    with _lock:
        c    = _conn()
        rows = c.execute("SELECT key,value FROM user_facts").fetchall()
        c.close()
    return {r["key"]: r["value"] for r in rows}


def save_daily_summary(summary: str, emotions: list[str], topics: list[str]) -> None:
    """Save a daily summary (called at end of day or on shutdown)."""
    today = datetime.date.today().isoformat()
    stats = get_today_stats()
    with _lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO daily_summary(date,summary,emotions,topics,msg_count)"
            " VALUES(?,?,?,?,?)",
            (today, summary, ",".join(emotions), ",".join(topics), stats["count"]),
        )
        c.commit()
        c.close()


def save_knowledge(topic: str, content: str, source: str = "interaction") -> None:
    """Store learned facts from search results or user interaction."""
    with _lock:
        c = _conn()
        # Keep only unique topics, but update them with new content
        c.execute(
            "INSERT OR REPLACE INTO knowledge (topic, content, source, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (topic.lower(), content[:3000], source, datetime.datetime.now().isoformat())
        )
        c.commit()
        c.close()


def get_relevant_knowledge(query: str, limit: int = 3) -> list[dict]:
    """Retrieve knowledge entries relevant to the query (simple keyword match)."""
    with _lock:
        c = _conn()
        # Simple keyword matching for now
        words = [w.strip() for w in query.lower().split() if len(w) > 3]
        if not words:
            # If no good keywords, just return recent knowledge
            rows = c.execute(
                "SELECT topic, content, source FROM knowledge ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        else:
            # Build query with LIKE for each word
            q_parts = [f"(topic LIKE ? OR content LIKE ?)" for _ in words]
            params  = []
            for w in words:
                params.extend([f"%{w}%", f"%{w}%"])
            sql = f"SELECT topic, content, source FROM knowledge WHERE {' OR '.join(q_parts)} ORDER BY updated_at DESC LIMIT ?"
            rows = c.execute(sql, params + [limit]).fetchall()
        c.close()
    return [dict(r) for r in rows]


def build_memory_context() -> str:
    """
    Build a compact memory context string to inject into system prompt.
    Used by Chatbot.py to give Jarvis persistent awareness.
    """
    lines = []

    # User facts
    facts = get_all_user_facts()
    if facts:
        fact_str = ", ".join(f"{k}={v}" for k, v in facts.items())
        lines.append(f"Known about user: {fact_str}.")

    # Yesterday's summary
    yday = get_yesterday_summary()
    if yday:
        lines.append(f"Yesterday's session: {yday}")

    # Today's stats
    stats = get_today_stats()
    if stats["count"] > 0:
        lines.append(f"Today so far: {stats['count']} messages exchanged.")
        if stats["emotions"]:
            dominant = max(stats["emotions"], key=stats["emotions"].get)
            lines.append(f"User's dominant mood today: {dominant}.")

    # Recently Learned Knowledge
    knowledge = get_relevant_knowledge("", limit=2)
    if knowledge:
        k_str = " | ".join(f"{k['topic']}: {k['content'][:150]}..." for k in knowledge)
        lines.append(f"Learned context: {k_str}")

    return " ".join(lines) if lines else ""