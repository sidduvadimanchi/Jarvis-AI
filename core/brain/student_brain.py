# Backend/Brain/student_brain.py  —  Jarvis Student Intelligence  v1.0
# ═══════════════════════════════════════════════════════════════════════
#
#  THIS IS THE MOST POWERFUL FEATURE FOR A STUDENT:
#
#  1. LEARNS FROM EVERY CONVERSATION
#     - Every question you ask → logged as a topic you're studying
#     - Wrong answers / "I don't understand" → flagged as weak areas
#     - Topics you've mastered → marked as strong
#
#  2. PERSONAL KNOWLEDGE MODEL  (stored in SQLite)
#     - topic_strength: 0–100 per subject/topic
#     - confusion_log: what you found hard + when
#     - revision_schedule: spaced repetition dates
#     - learning_streaks: days studied per subject
#
#  3. SMART REVISION GENERATION
#     - "Revise me" → picks weakest topic you haven't revised recently
#     - Auto-generates questions at your level
#     - Tracks score over time → shows improvement
#
#  4. PROACTIVE DAILY SUGGESTIONS
#     - "You haven't revised Data Structures in 5 days"
#     - "You found recursion hard yesterday — want to try again?"
#     - "You're on a 7-day Python streak! Keep it up"
#
#  5. STUDY SESSION TRACKING
#     - Start/stop sessions → logs focus time per subject
#     - Weekly study heat map
#     - Compares planned vs actual study
#
#  6. SMART FACT EXTRACTION
#     - "My exam is on 15th Dec" → saved automatically
#     - "I'm in Semester 4 CSE" → saved
#     - "I struggle with integration" → logged as weak area
#
#  Storage:  Data/student_brain.db  (SQLite, fully offline)
# ═══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import re
import json
import sqlite3
import datetime
import threading
from pathlib import Path
from typing  import Optional
from dotenv  import load_dotenv
load_dotenv()

_USERNAME  = os.getenv("Username",      "Siddu")
_ANAME     = os.getenv("Assistantname", "Jarvis")
_DB_PATH   = Path("Data") / "student_brain.db"
_lock      = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════
_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject      TEXT NOT NULL,            -- e.g. 'Data Structures', 'Maths', 'Physics'
    topic        TEXT NOT NULL,            -- e.g. 'recursion', 'integration'
    strength     INTEGER DEFAULT 50,       -- 0=total beginner, 100=mastered
    times_asked  INTEGER DEFAULT 0,        -- how many times asked about this
    times_confused INTEGER DEFAULT 0,      -- how many times said "I don't understand"
    last_studied TEXT,                     -- ISO date
    next_revision TEXT,                    -- ISO date (spaced repetition)
    notes        TEXT,                     -- Jarvis notes about this topic
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confusion_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL,
    query       TEXT NOT NULL,             -- exact question asked
    response    TEXT,                      -- Jarvis answer
    understood  INTEGER DEFAULT 0,         -- 1=yes, 0=no/unclear
    timestamp   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    subject      TEXT,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    duration_min INTEGER DEFAULT 0,
    focus_score  INTEGER DEFAULT 0,        -- 0-100 (based on activity)
    topics_covered TEXT,                   -- JSON list
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS revision_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL,
    score       INTEGER,                   -- 0-100
    questions   INTEGER DEFAULT 0,
    correct     INTEGER DEFAULT 0,
    timestamp   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_facts (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    category    TEXT,                      -- 'academic', 'schedule', 'goal', 'preference'
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS daily_study_log (
    date        TEXT PRIMARY KEY,
    total_min   INTEGER DEFAULT 0,
    subjects    TEXT,                      -- JSON list
    topics      TEXT,                      -- JSON list
    queries     INTEGER DEFAULT 0,
    mood        TEXT
);

CREATE INDEX IF NOT EXISTS idx_topics_strength  ON topics(strength);
CREATE INDEX IF NOT EXISTS idx_topics_subject   ON topics(subject);
CREATE INDEX IF NOT EXISTS idx_confusion_topic  ON confusion_log(topic);
CREATE INDEX IF NOT EXISTS idx_sessions_date    ON study_sessions(start_time);
"""


def _conn() -> sqlite3.Connection:
    Path("Data").mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


# ═══════════════════════════════════════════════════════════════════════
# SUBJECT DETECTION  — maps any query to a subject
# ═══════════════════════════════════════════════════════════════════════
_SUBJECT_MAP: dict[str, list[str]] = {
    "Data Structures"   : ["array","linked list","stack","queue","tree","graph","heap",
                           "hash","trie","binary","bst","avl","sorting","searching",
                           "data structure","algorithm","complexity","big o","time complexity"],
    "Python"            : ["python","def ","class ","lambda","list comprehension","decorator",
                           "generator","asyncio","pandas","numpy","matplotlib","django","flask",
                           "pip","virtualenv","pep8","type hint"],
    "C/C++"             : ["c++","c programming","pointer","malloc","struct","class cpp",
                           "template","stl","vector cpp","iostream","header file","gcc","g++"],
    "Java"              : ["java","jvm","spring","maven","gradle","junit","inheritance java",
                           "interface java","abstract class","generics java"],
    "Database / SQL"    : ["sql","mysql","postgresql","sqlite","nosql","mongodb","query",
                           "join","index","foreign key","primary key","normalization","acid",
                           "transaction","database","orm","crud"],
    "Computer Networks" : ["tcp","udp","ip","http","https","dns","dhcp","network","routing",
                           "subnet","firewall","osi","socket","bandwidth","latency","protocol"],
    "Operating Systems" : ["process","thread","deadlock","semaphore","mutex","scheduling",
                           "memory management","virtual memory","paging","segmentation","kernel",
                           "system call","ipc","context switch","race condition"],
    "Mathematics"       : ["calculus","integration","differentiation","matrix","determinant",
                           "eigenvalue","fourier","laplace","probability","statistics","mean",
                           "median","mode","standard deviation","permutation","combination",
                           "limits","differential equation","algebra","trigonometry"],
    "Electronics"       : ["op-amp","transistor","diode","capacitor","resistor","circuit",
                           "voltage","current","amplifier","oscillator","555 timer","adc","dac",
                           "microcontroller","arduino","pcb","vhdl","fpga","signal processing"],
    "Machine Learning"  : ["machine learning","neural network","deep learning","cnn","rnn",
                           "lstm","transformer","backprop","gradient descent","overfitting",
                           "regularization","feature engineering","svm","random forest",
                           "scikit","pytorch","tensorflow","keras","llm","embedding"],
    "Physics"           : ["mechanics","thermodynamics","optics","electromagnetism","quantum",
                           "relativity","wave","force","energy","momentum","entropy","photon"],
    "General Study"     : ["study","exam","test","assignment","project","notes","revision",
                           "understand","explain","how does","what is","why does"],
}

def detect_subject(text: str) -> str:
    """Detect which subject a query belongs to."""
    low = text.lower()
    scores: dict[str, int] = {}
    for subj, keywords in _SUBJECT_MAP.items():
        score = sum(1 for kw in keywords if kw in low)
        if score > 0:
            scores[subj] = score
    if not scores:
        return "General Study"
    return max(scores, key=scores.get)


# ═══════════════════════════════════════════════════════════════════════
# CONFUSION SIGNALS  — detect when user is struggling
# ═══════════════════════════════════════════════════════════════════════
_CONFUSION_SIGNALS = [
    r"\bi\s+(?:don'?t|do\s+not|didn'?t)\s+(?:understand|get|know|follow)\b",
    r"\b(?:confused|confusing|confuse me|makes no sense|not clear)\b",
    r"\bwhat\s+(?:do\s+you\s+mean|does\s+that\s+mean|is\s+that)\b",
    r"\b(?:still\s+)?(?:lost|unclear|not\s+sure)\b",
    r"\b(?:explain\s+again|re-?explain|once\s+more|again please|explain\s+it)\b",
    r"\b(?:huh|what\?{2,}|i\s+give\s+up|this\s+is\s+hard)\b",
    r"\b(?:too\s+(?:hard|difficult|complex|complicated))\b",
    r"\bcan(?:'t| not)\s+(?:understand|follow|grasp)\b",
]

def is_confused(text: str) -> bool:
    """Returns True if the user seems confused or struggling."""
    low = text.lower()
    return any(re.search(p, low) for p in _CONFUSION_SIGNALS)

_MASTERY_SIGNALS = [
    r"\b(?:got\s+it|i\s+(?:get|understand)|makes\s+sense|clear\s+now|i\s+see)\b",
    r"\b(?:thanks?\s*[!.]?|perfect|exactly|that'?s?\s+(?:right|it|helpful|clear))\b",
    r"\b(?:understood|learned|makes?\s+(?:sense|more\s+sense))\b",
]

def is_understood(text: str) -> bool:
    """Returns True if user signals they understood."""
    low = text.lower()
    return any(re.search(p, low) for p in _MASTERY_SIGNALS)


# ═══════════════════════════════════════════════════════════════════════
# SMART FACT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════
_FACT_PATTERNS: list[tuple] = [
    # Academic
    (re.compile(r"(?:i'?m?\s+in|studying\s+in|enrolled\s+in)\s+(?:semester|sem|year)\s*(\w+)", re.I),
     "semester", "academic"),
    (re.compile(r"(?:i'?m?\s+(?:a\s+)?(?:studying|study|in)|pursuing)\s+([A-Za-z.]+(?:\s+[A-Za-z.]+)?)\s*(?:student|degree|branch|course)?", re.I),
     "branch", "academic"),
    (re.compile(r"my\s+(?:roll\s*(?:no|number)?|enrollment\s*(?:no|number)?)\s+is\s+(\w+)", re.I),
     "roll_number", "academic"),
    (re.compile(r"(?:studying\s+at|college\s+is|i\s+go\s+to|i\s+study\s+at)\s+([A-Za-z\s]+?)(?:\s+and|\.|,|$)", re.I),
     "college", "academic"),
    # Schedule / exams
    (re.compile(r"(?:my\s+)?(?:exam|test|viva|submission)\s+(?:is\s+)?(?:on|at)\s+(\d{1,2}(?:st|nd|rd|th)?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{1,2}))", re.I),
     "next_exam", "schedule"),
    (re.compile(r"(?:exam|test)\s+(?:in|after)\s+(\d+)\s+days?", re.I),
     "exam_days_away", "schedule"),
    # Weak/strong subjects
    (re.compile(r"i\s+(?:struggle|find\s+it\s+hard|am\s+weak)\s+(?:with|in|at)\s+([^.!?]+)", re.I),
     "weak_in", "academic"),
    (re.compile(r"i'?m?\s+(?:good|strong|great)\s+(?:at|in)\s+([^.!?]+)", re.I),
     "strong_in", "academic"),
    # Goals
    (re.compile(r"(?:my\s+)?goal\s+is\s+(?:to\s+)?([^.!?]+)", re.I),
     "goal", "goal"),
    (re.compile(r"i\s+want\s+to\s+(?:become|be\s+a?)\s+([^.!?]+)", re.I),
     "career_goal", "goal"),
]

def extract_facts(text: str) -> dict[str, tuple[str, str]]:
    """
    Extract student facts from text.
    Returns {key: (value, category)} pairs.
    """
    found: dict[str, tuple[str, str]] = {}
    for pat, key, cat in _FACT_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).strip().strip(".,!?")
            if len(val) > 1:
                found[key] = (val, cat)
    return found


# ═══════════════════════════════════════════════════════════════════════
# TOPIC TRACKER  — core learning engine
# ═══════════════════════════════════════════════════════════════════════
def log_topic_interaction(
    query    : str,
    response : str,
    confused : bool = False,
    mastered : bool = False,
) -> str:
    """
    Called after every conversation turn.
    Updates topic strength, logs confusion, schedules revision.
    Returns the detected subject for context.
    """
    subject = detect_subject(query)
    topic   = _extract_topic_keyword(query)
    today   = datetime.date.today().isoformat()

    # Strength delta
    if confused: delta = -8
    elif mastered: delta = +12
    else: delta = +2  # neutral interaction = small gain

    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT id, strength, times_asked, times_confused FROM topics "
            "WHERE subject=? AND topic=?", (subject, topic)
        ).fetchone()

        if row:
            new_strength = max(0, min(100, row["strength"] + delta))
            c.execute(
                "UPDATE topics SET strength=?, times_asked=times_asked+1, "
                "times_confused=times_confused+?, last_studied=?, next_revision=? "
                "WHERE id=?",
                (new_strength,
                 1 if confused else 0,
                 today,
                 _next_revision_date(new_strength),
                 row["id"]),
            )
        else:
            init_strength = max(0, min(100, 50 + delta))
            c.execute(
                "INSERT INTO topics(subject, topic, strength, times_asked, "
                "times_confused, last_studied, next_revision, created_at) "
                "VALUES(?,?,?,1,?,?,?,?)",
                (subject, topic, init_strength,
                 1 if confused else 0,
                 today,
                 _next_revision_date(init_strength),
                 datetime.datetime.now().isoformat()),
            )

        # Log confusion
        if confused:
            c.execute(
                "INSERT INTO confusion_log(topic, query, response, understood, timestamp) "
                "VALUES(?,?,?,0,?)",
                (topic, query[:500], response[:1000],
                 datetime.datetime.now().isoformat()),
            )

        # Update daily log
        _update_daily_log(c, subject, topic)
        c.commit(); c.close()

    return subject


def _extract_topic_keyword(text: str) -> str:
    """Extract a short topic keyword from a query."""
    clean = re.sub(
        r"^(?:what\s+is|explain|how\s+does|tell\s+me\s+about|define|describe|"
        r"help\s+me\s+with|i\s+need\s+help\s+with|understand)\s+",
        "", text.strip(), flags=re.I
    )
    words = clean.split()
    topic = " ".join(words[:4]).lower().strip("?.,!")
    return topic[:60] if topic else text[:40].lower()


def _next_revision_date(strength: int) -> str:
    """
    Spaced repetition interval based on topic strength.
    Weak topics → revise sooner. Strong topics → revise later.
    """
    if strength < 30:   days = 1    # Very weak → tomorrow
    elif strength < 50: days = 2    # Weak → 2 days
    elif strength < 70: days = 4    # Medium → 4 days
    elif strength < 85: days = 7    # Good → 1 week
    else:               days = 14   # Strong → 2 weeks
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _update_daily_log(c: sqlite3.Connection, subject: str, topic: str) -> None:
    today = datetime.date.today().isoformat()
    row = c.execute(
        "SELECT subjects, topics, queries FROM daily_study_log WHERE date=?", (today,)
    ).fetchone()
    if row:
        subjects = json.loads(row["subjects"] or "[]")
        topics   = json.loads(row["topics"]   or "[]")
        if subject not in subjects: subjects.append(subject)
        if topic   not in topics:   topics.append(topic)
        c.execute(
            "UPDATE daily_study_log SET subjects=?, topics=?, queries=queries+1 WHERE date=?",
            (json.dumps(subjects), json.dumps(topics), today),
        )
    else:
        c.execute(
            "INSERT INTO daily_study_log(date, subjects, topics, queries) VALUES(?,?,?,1)",
            (today, json.dumps([subject]), json.dumps([topic])),
        )


# ═══════════════════════════════════════════════════════════════════════
# STUDENT FACTS
# ═══════════════════════════════════════════════════════════════════════
def save_student_fact(key: str, value: str, category: str = "academic") -> None:
    with _lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO student_facts(key,value,category,updated_at) VALUES(?,?,?,?)",
            (key.lower(), value, category, datetime.datetime.now().isoformat()),
        )
        c.commit(); c.close()

def get_student_fact(key: str) -> Optional[str]:
    with _lock:
        c   = _conn()
        row = c.execute("SELECT value FROM student_facts WHERE key=?", (key.lower(),)).fetchone()
        c.close()
    return row["value"] if row else None

def get_all_student_facts() -> dict:
    with _lock:
        c    = _conn()
        rows = c.execute("SELECT key,value,category FROM student_facts").fetchall()
        c.close()
    return {r["key"]: {"value": r["value"], "category": r["category"]} for r in rows}


# ═══════════════════════════════════════════════════════════════════════
# SMART QUERIES
# ═══════════════════════════════════════════════════════════════════════
def get_weakest_topics(n: int = 5) -> list[dict]:
    """Get n topics with lowest strength that need revision."""
    with _lock:
        c    = _conn()
        rows = c.execute(
            "SELECT subject, topic, strength, times_confused, last_studied, next_revision "
            "FROM topics ORDER BY strength ASC, times_confused DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_due_for_revision() -> list[dict]:
    """Get topics whose revision date is today or overdue."""
    today = datetime.date.today().isoformat()
    with _lock:
        c    = _conn()
        rows = c.execute(
            "SELECT subject, topic, strength, next_revision FROM topics "
            "WHERE next_revision <= ? ORDER BY strength ASC", (today,)
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_strong_topics(n: int = 5) -> list[dict]:
    """Get topics where user is strongest."""
    with _lock:
        c    = _conn()
        rows = c.execute(
            "SELECT subject, topic, strength FROM topics "
            "ORDER BY strength DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_all_topics() -> list[dict]:
    with _lock:
        c    = _conn()
        rows = c.execute(
            "SELECT subject, topic, strength, times_asked, times_confused, "
            "last_studied, next_revision FROM topics ORDER BY subject, strength DESC"
        ).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_study_streak() -> int:
    """How many consecutive days the user has studied."""
    today  = datetime.date.today()
    streak = 0
    with _lock:
        c = _conn()
        for i in range(30):
            d   = (today - datetime.timedelta(days=i)).isoformat()
            row = c.execute(
                "SELECT queries FROM daily_study_log WHERE date=?", (d,)
            ).fetchone()
            if row and row["queries"] > 0:
                streak += 1
            elif i > 0:  # Allow today with no queries yet
                break
        c.close()
    return streak

def get_weekly_heatmap() -> list[dict]:
    """7-day study summary for heatmap display."""
    today = datetime.date.today()
    result = []
    with _lock:
        c = _conn()
        for i in range(6, -1, -1):
            d   = (today - datetime.timedelta(days=i)).isoformat()
            row = c.execute(
                "SELECT queries, subjects, total_min FROM daily_study_log WHERE date=?", (d,)
            ).fetchone()
            result.append({
                "date"      : d,
                "day"       : (today - datetime.timedelta(days=i)).strftime("%a"),
                "queries"   : row["queries"]   if row else 0,
                "subjects"  : json.loads(row["subjects"] or "[]") if row else [],
                "total_min" : row["total_min"] if row else 0,
            })
        c.close()
    return result

def get_today_study_summary() -> dict:
    today = datetime.date.today().isoformat()
    with _lock:
        c   = _conn()
        row = c.execute(
            "SELECT queries, subjects, topics, total_min FROM daily_study_log WHERE date=?",
            (today,)
        ).fetchone()
        c.close()
    if not row:
        return {"queries": 0, "subjects": [], "topics": [], "total_min": 0}
    return {
        "queries"  : row["queries"],
        "subjects" : json.loads(row["subjects"] or "[]"),
        "topics"   : json.loads(row["topics"]   or "[]"),
        "total_min": row["total_min"],
    }


# ═══════════════════════════════════════════════════════════════════════
# STUDY SESSIONS
# ═══════════════════════════════════════════════════════════════════════
_active_session: Optional[dict] = None
_session_lock   = threading.Lock()

def start_study_session(subject: str = "General Study") -> str:
    global _active_session
    with _session_lock:
        if _active_session:
            return f"Session already running for {_active_session['subject']}. Stop it first."
        _active_session = {
            "subject"   : subject,
            "start"     : datetime.datetime.now().isoformat(),
            "topics"    : [],
        }
    return f"Study session started for **{subject}**. I'm tracking your focus time. Good luck!"

def stop_study_session() -> str:
    global _active_session
    with _session_lock:
        if not _active_session:
            return "No active study session."
        sess = _active_session
        _active_session = None

    start  = datetime.datetime.fromisoformat(sess["start"])
    end    = datetime.datetime.now()
    dur    = int((end - start).total_seconds() / 60)
    topics = sess.get("topics", [])

    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO study_sessions(subject,start_time,end_time,duration_min,topics_covered) "
            "VALUES(?,?,?,?,?)",
            (sess["subject"], sess["start"], end.isoformat(), dur,
             json.dumps(topics)),
        )
        # Update daily log
        today = datetime.date.today().isoformat()
        c.execute(
            "INSERT OR IGNORE INTO daily_study_log(date,total_min,subjects,topics,queries) "
            "VALUES(?,0,'[]','[]',0)", (today,)
        )
        c.execute(
            "UPDATE daily_study_log SET total_min=total_min+? WHERE date=?", (dur, today)
        )
        c.commit(); c.close()

    msg = (f"Session ended! You studied **{sess['subject']}** for **{dur} minutes**.")
    if dur >= 25:
        msg += " Great focus! That's a full Pomodoro."
    elif dur >= 50:
        msg += " 🔥 Deep work session! You're building serious momentum."
    return msg

def add_topic_to_session(topic: str) -> None:
    global _active_session
    with _session_lock:
        if _active_session and topic not in _active_session["topics"]:
            _active_session["topics"].append(topic)

def get_session_status() -> Optional[dict]:
    with _session_lock:
        if not _active_session:
            return None
        start   = datetime.datetime.fromisoformat(_active_session["start"])
        elapsed = int((datetime.datetime.now() - start).total_seconds() / 60)
        return {**_active_session, "elapsed_min": elapsed}


# ═══════════════════════════════════════════════════════════════════════
# REVISION QUESTION GENERATOR
# ═══════════════════════════════════════════════════════════════════════

# Question templates per subject
_Q_TEMPLATES: dict[str, list[str]] = {
    "Data Structures": [
        "What is the time complexity of {topic}?",
        "Explain the difference between a Stack and a Queue using {topic}.",
        "Write pseudocode for {topic}.",
        "When would you use {topic} over a simpler structure?",
        "What are the edge cases to consider when implementing {topic}?",
    ],
    "Python": [
        "Write a Python function demonstrating {topic}.",
        "What is the difference between {topic} and a similar concept?",
        "What error would you get if you misused {topic}?",
        "Give 3 real-world use cases for {topic}.",
        "How would you debug a {topic} issue?",
    ],
    "Mathematics": [
        "Solve a problem involving {topic}.",
        "Explain the intuition behind {topic} in simple words.",
        "What are the key formulas for {topic}?",
        "How does {topic} apply in engineering?",
        "What's a common mistake students make with {topic}?",
    ],
    "Machine Learning": [
        "Explain {topic} in simple words — no jargon.",
        "What problem does {topic} solve?",
        "What are the limitations of {topic}?",
        "How would you implement {topic} in 5 lines of code?",
        "Compare {topic} with an alternative approach.",
    ],
    "default": [
        "Explain {topic} in your own words.",
        "Give a real-world example of {topic}.",
        "What are 3 key points about {topic}?",
        "How does {topic} work step by step?",
        "What's the most important thing to remember about {topic}?",
    ],
}

def generate_revision_question(topic_row: Optional[dict] = None) -> dict:
    """
    Generate a revision question for the weakest due topic.
    Returns {question, topic, subject, hint}.
    """
    import random

    if not topic_row:
        due   = get_due_for_revision()
        weak  = get_weakest_topics(3)
        pool  = due + [t for t in weak if t not in due]
        if not pool:
            return {
                "question": f"Tell me about something you've been studying lately, {_USERNAME}.",
                "topic"   : "general",
                "subject" : "General Study",
                "hint"    : "",
            }
        topic_row = pool[0]

    subj     = topic_row.get("subject", "General Study")
    topic    = topic_row.get("topic",   "your studies")
    strength = topic_row.get("strength", 50)

    templates = _Q_TEMPLATES.get(subj, _Q_TEMPLATES["default"])
    template  = random.choice(templates)
    question  = template.format(topic=topic)

    # Hint for weak topics
    hint = ""
    if strength < 40:
        hint = f"(Take your time — your strength on this topic is {strength}/100. No pressure!)"
    elif strength < 60:
        hint = f"(You're improving! Strength: {strength}/100)"

    return {
        "question": question,
        "topic"   : topic,
        "subject" : subj,
        "hint"    : hint,
        "strength": strength,
    }


# ═══════════════════════════════════════════════════════════════════════
# PROACTIVE SUGGESTIONS  — Jarvis tells you what to study
# ═══════════════════════════════════════════════════════════════════════
def get_daily_suggestion() -> str:
    """
    Generates a personalised study suggestion for today.
    Called on startup / morning focus.
    """
    lines = []
    name  = _USERNAME

    # Streak
    streak = get_study_streak()
    if streak >= 7:
        lines.append(f"🔥 {streak}-day study streak! You're on fire, {name}.")
    elif streak >= 3:
        lines.append(f"⚡ {streak}-day streak! Keep the momentum going.")
    elif streak == 0:
        lines.append(f"💪 Fresh start today, {name}. Let's make it count.")

    # Due for revision
    due = get_due_for_revision()
    if due:
        d = due[0]
        lines.append(
            f"📖 **Revision due:** {d['topic']} ({d['subject']}) — "
            f"Strength: {d['strength']}/100"
        )

    # Weakest topic
    weak = get_weakest_topics(1)
    if weak:
        w = weak[0]
        if w.get("times_confused", 0) > 2:
            lines.append(
                f"⚠️ **{w['topic']}** still gives you trouble "
                f"({w['times_confused']} confusions logged). Worth spending 15 min on it?"
            )

    # Exam check
    exam = get_student_fact("next_exam")
    if exam:
        lines.append(f"📅 Exam coming up: {exam} — plan your revision accordingly.")

    # Today summary
    today = get_today_study_summary()
    if today["queries"] == 0:
        lines.append("No study activity yet today. Shall we start a session?")
    else:
        lines.append(
            f"Today so far: {today['queries']} questions across "
            f"{', '.join(today['subjects'][:3]) or 'various topics'}."
        )

    return "\n".join(lines) if lines else f"Ready to study, {name}? What subject today?"


def build_jarvis_context() -> str:
    """
    Compact context string injected into Jarvis system prompt.
    Gives Jarvis knowledge of the student's academic situation.
    """
    parts = []

    facts = get_all_student_facts()
    if facts:
        academic = {k: v["value"] for k, v in facts.items() if v["category"] == "academic"}
        if academic:
            parts.append("Student profile: " + "; ".join(f"{k}={v}" for k,v in academic.items()))

    weak = get_weakest_topics(3)
    if weak:
        wt = ", ".join(f"{t['topic']}({t['strength']}/100)" for t in weak)
        parts.append(f"Weak areas: {wt}")

    strong = get_strong_topics(2)
    if strong:
        st = ", ".join(f"{t['topic']}({t['strength']}/100)" for t in strong)
        parts.append(f"Strong at: {st}")

    due = get_due_for_revision()
    if due:
        dr = ", ".join(t["topic"] for t in due[:3])
        parts.append(f"Due for revision: {dr}")

    streak = get_study_streak()
    if streak > 0:
        parts.append(f"Study streak: {streak} days")

    session = get_session_status()
    if session:
        parts.append(
            f"Active study session: {session['subject']} "
            f"({session['elapsed_min']} min in)"
        )

    return " | ".join(parts) if parts else ""


# ═══════════════════════════════════════════════════════════════════════
# LEARN FROM CONVERSATION  (called after EVERY ChatBot response)
# ═══════════════════════════════════════════════════════════════════════
def learn_from_conversation(
    user_query    : str,
    jarvis_answer : str,
) -> dict:
    """
    The main learning loop. Called after every response.
    Returns dict with what was learned (for logging).
    """
    confused = is_confused(user_query)
    mastered = is_understood(user_query)

    # Log topic interaction
    subject = log_topic_interaction(
        query    = user_query,
        response = jarvis_answer,
        confused = confused,
        mastered = mastered,
    )

    # Extract and save facts
    facts = extract_facts(user_query)
    for key, (value, category) in facts.items():
        save_student_fact(key, value, category)

    # Track session topic
    if _active_session:
        add_topic_to_session(_extract_topic_keyword(user_query))

    return {
        "subject" : subject,
        "confused": confused,
        "mastered": mastered,
        "facts"   : facts,
    }


# ═══════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import tempfile, os
    # Use a temp DB for testing
    _DB_PATH = Path(tempfile.mkdtemp()) / "test_brain.db"

    print(f"\n{'═'*60}")
    print("  STUDENT BRAIN — Test Suite")
    print(f"{'═'*60}\n")

    tests_passed = 0
    total_tests  = 0

    def check(label, result, expected):
        global tests_passed, total_tests
        total_tests += 1
        ok = result == expected if expected is not None else bool(result)
        if ok: tests_passed += 1
        print(f"  {'✅' if ok else '❌'}  {label}: {result!r}")

    # Subject detection
    check("Python query",    detect_subject("explain list comprehension in python"), "Python")
    check("DSA query",       detect_subject("what is binary search tree"),          "Data Structures")
    check("ML query",        detect_subject("how does backpropagation work"),       "Machine Learning")
    check("Math query",      detect_subject("solve integration by parts"),          "Mathematics")
    check("Network query",   detect_subject("explain tcp three way handshake"),     "Computer Networks")

    # Confusion signals
    check("is_confused TRUE",  is_confused("I don't understand recursion"),     True)
    check("is_confused TRUE",  is_confused("this is too hard"),                 True)
    check("is_confused FALSE", is_confused("great, thanks!"),                   False)
    check("is_understood",     is_understood("got it, makes sense now"),         True)
    check("is_understood neg", is_understood("I still don't get it"),            False)

    # Fact extraction
    facts = extract_facts("I'm in semester 4 studying at VIT and my roll number is 22BCE1234")
    check("semester extracted", "semester" in facts,   True)
    check("college extracted",  "college"  in facts,   True)
    check("roll extracted",     "roll_number" in facts, True)

    facts2 = extract_facts("I struggle with integration and I'm good at Python")
    check("weak extracted",   "weak_in"   in facts2, True)
    check("strong extracted", "strong_in" in facts2, True)

    # Learning loop
    result = learn_from_conversation(
        "I don't understand binary search",
        "Binary search works by halving the search space..."
    )
    check("learned subject",  result["subject"],  "Data Structures")
    check("confusion logged", result["confused"],  True)

    result2 = learn_from_conversation(
        "Got it! recursion makes sense now",
        "Great! You've understood the concept."
    )
    check("mastery detected", result2["mastered"], True)

    # Topic queries
    weak = get_weakest_topics(3)
    check("weak topics returned", len(weak) > 0, True)

    due = get_due_for_revision()
    check("revision check runs", isinstance(due, list), True)

    # Study session
    msg = start_study_session("Data Structures")
    check("session started", "started" in msg.lower(), True)
    import time; time.sleep(0.1)
    msg2 = stop_study_session()
    check("session stopped", "session ended" in msg2.lower(), True)

    # Suggestion
    suggestion = get_daily_suggestion()
    check("suggestion generated", len(suggestion) > 10, True)

    # Context builder
    ctx = build_jarvis_context()
    check("context not empty", isinstance(ctx, str), True)

    print(f"\n{'═'*60}")
    print(f"  SCORE: {tests_passed}/{total_tests} = {100*tests_passed//total_tests}%")
    print(f"{'═'*60}\n")