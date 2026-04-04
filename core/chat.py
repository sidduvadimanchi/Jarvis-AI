# Backend/Chatbot.py  (v3.0 — Brain-Integrated)
# All original fixes KEPT. Brain layer ADDED on top.
# 100% backward compatible — ChatBot(Query) still works exactly the same.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import re
import time
import datetime
import threading
from json     import load, dump, JSONDecodeError
from pathlib  import Path
from typing   import Callable, Optional
from dotenv   import load_dotenv

load_dotenv()

from groq import Groq

# ── Brain modules (graceful fallback if not ready) ────────────────────────────
try:
    from core.brain.memory      import (save_turn, get_recent,
                                       build_memory_context, save_user_fact,
                                       get_user_fact)
    from core.brain.emotion     import (detect_emotion, detect_emotion_intensity,
                                       get_emotion_system_addition,
                                       get_emotion_prefix, get_farewell)
    from core.brain.personality import build_system_prompt, extract_topics
    _BRAIN = True
except ImportError:
    _BRAIN = False

# ── Config ────────────────────────────────────────────────────────────────────
_GROQ_KEY = (
    os.getenv("GROQ_API_KEY") or
    os.getenv("GroqAPIKey")   or
    os.getenv("GroqKey")
)
if not _GROQ_KEY:
    raise ValueError(
        "\n[Chatbot] Groq API key not found!\n"
        "Add to .env:  GROQ_API_KEY=gsk_...\n"
    )

Username      = os.getenv("Username",      "Siddu")
Assistantname = os.getenv("Assistantname", "Jarvis")

DATA_DIR         = Path("Data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_HISTORY      = 20
MAX_LOG_FILES    = 5
MESSAGES_PER_LOG = 100
MAX_RETRIES      = 3
MODEL            = os.getenv("GroqModel", "llama-3.1-8b-instant")
MAX_TOKENS       = 512
TEMPERATURE      = 0.5
TOP_P            = 0.9

_AI_BOILERPLATE = [
    r"As an AI(?: language model)?[,.]?\s*",
    r"I(?:'m| am) just an AI[,.]?\s*",
    r"I don't have personal opinions[,.]?\s*",
    r"I cannot browse the internet[,.]?\s*",
    r"My knowledge cutoff[^.]*\.\s*",
    r"As of my last (?:training|update)[^.]*\.\s*",
    r"I should (?:note|mention) that[^.]*\.\s*",
    r"Please note that[^.]*\.\s*",
    r"Note:[^.]*\.\s*",
]

_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?",
    r"disregard\s+(?:your\s+)?(?:system|prior|previous)\s+(?:prompt|instructions?)",
    r"you\s+are\s+now\s+(?:a|an)\s+",
    r"pretend\s+(?:you\s+are|to\s+be)\s+",
    r"override\s+(?:your\s+)?(?:system|instructions?)",
    r"act\s+as\s+(?:if\s+you\s+(?:are|were)|a|an)\s+",
    r"forget\s+(?:everything|all)",
    r"jailbreak", r"dan\s+mode", r"developer\s+mode",
]

_client = Groq(api_key=_GROQ_KEY)

# ── Greeting/Farewell patterns ────────────────────────────────────────────────
_GREET_PATTERNS = re.compile(
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening|night|day)|"
    r"what'?s\s+up|howdy|yo|sup|hii+|heyy+)[\s!?.]*$",
    re.IGNORECASE,
)
_FAREWELL_PATTERNS = re.compile(
    r"^(bye|goodbye|good\s*night|see\s+you|cya|later|take\s+care|"
    r"goodnight|night|quit|exit|close|stop)[\s!?.]*$",
    re.IGNORECASE,
)

# ── User fact extraction ──────────────────────────────────────────────────────
_FACT_PATTERNS = [
    (re.compile(r"(?:call me|my name is|i am|i'm)\s+([A-Za-z]+)", re.I), "name"),
    (re.compile(r"i(?:'m| am) (?:a student|studying) (?:at\s+)?(.+)", re.I),    "college"),
    (re.compile(r"my (?:roll\s*(?:number|no)?|enrollment) (?:is\s+)?(\w+)", re.I), "roll_no"),
    (re.compile(r"i(?:'m| am) in (?:semester|sem|year)\s+(\w+)", re.I),          "semester"),
    (re.compile(r"i (?:like|love|enjoy|prefer)\s+(.+)",  re.I),                  "interest"),
]


class JarvisChatbot:
    """
    Brain-integrated Jarvis chatbot.
    Remembers across sessions, detects emotions, adapts personality.
    """

    def __init__(self) -> None:
        self._lock           = threading.Lock()
        self._cache: list[dict] = []
        self._cache_dirty    = False
        self._last_save      = time.time()
        self._SAVE_INTERVAL  = 30.0
        self._session_topics : list[str] = []
        self._current_emotion: Optional[str] = None
        self._emotion_count  = 0

        self._cache = self._load_history()

    # ── Tool Manifest (Self-Awareness) ──────────────────────────────────────────
    _TOOL_MANIFEST = """
    YOUR ACTUAL CAPABILITIES (STRICT):
    1. System/App: Open/Close any app (Chrome, VS Code), System Health (RAM, CPU, Battery).
    2. Real-time: Weather ☀️, News 📰, Stocks/Crypto 📈, Google/YouTube Search.
    3. Study/Jobs: GATE Prep Strategy, PSU Alerts, CSE Syllabus, Job Deadlines, Daily Briefing.
    4. Productivity: Timetables, Focus Mode, Assignment Notes, Summarization.
    5. Comms: Send/Read Emails 📧, WhatsApp 💬, Alarms/Timers ⏰.
    """

    def _get_system_prompt(self, query: str = "", tone: str = "professional") -> str:
        if not _BRAIN:
            # Fallback to basic prompt
            return (
                f"Your name is {Assistantname}. You are a helpful assistant "
                f"talking with {Username}.\n{self._TOOL_MANIFEST}\nBe concise. Never say 'As an AI'."
            )

        hour     = datetime.datetime.now().hour
        emotion  = self._current_emotion
        intensity = detect_emotion_intensity(query, emotion) if emotion else 0

        # Inject Tool Manifest into the base personality prompt
        base_prompt = build_system_prompt(
            emotion          = emotion,
            emotion_intensity= intensity,
            memory_context   = build_memory_context(),
            recent_topics    = self._session_topics[-10:],
            is_late_night    = hour >= 22,
        )

        # Tone Guard Instructions
        tone_map = {
            "professional": "TONE: Professional, concise, business-ready. No slang, no 'yaar', no casual fillers.",
            "friendly"    : "TONE: Warm, helpful, friendly but safe. Use first names.",
            "formal"      : "TONE: Strictly formal, academic, official. No contractions. Dear/Sincerely style."
        }
        tone_instr = tone_map.get(tone.lower(), tone_map["professional"])

        return f"{base_prompt}\n{self._TOOL_MANIFEST}\nSTRICT RULES:\n1. {tone_instr}\n2. Never mention being an AI.\n3. Do not repeat the user's name excessively."

    # ── Storage helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _log_path(index: int = 0) -> Path:
        return DATA_DIR / "ChatLog.json" if index == 0 \
               else DATA_DIR / f"ChatLog_{index}.json"

    def _load_history(self) -> list[dict]:
        path = self._log_path(0)
        if not path.exists():
            self._write_json(path, [])
            return []
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return []
            with path.open("r", encoding="utf-8") as fh:
                data = load(fh)
            return data[-MAX_HISTORY:] if isinstance(data, list) else []
        except (JSONDecodeError, OSError, ValueError):
            backup = path.with_suffix(".bak.json")
            try:
                path.rename(backup)
            except Exception:
                pass
            self._write_json(path, [])
            return []

    @staticmethod
    def _write_json(path: Path, data: list) -> None:
        tmp = path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                dump(data, fh, indent=2, ensure_ascii=False)
            tmp.replace(path)
        except Exception as e:
            print(f"[Chatbot] Write error: {e}")
            try: tmp.unlink(missing_ok=True)
            except Exception: pass

    def _flush(self, force: bool = False) -> None:
        if not self._cache_dirty:
            return
        now = time.time()
        if force or (now - self._last_save) >= self._SAVE_INTERVAL:
            self._write_json(self._log_path(0), self._cache[-MAX_HISTORY:])
            self._last_save   = now
            self._cache_dirty = False

    def _rotate_if_needed(self) -> None:
        if len(self._cache) < MESSAGES_PER_LOG:
            return
        for i in range(MAX_LOG_FILES - 1, 0, -1):
            src = self._log_path(i)
            if src.exists():
                try: src.rename(self._log_path(i + 1))
                except Exception: pass
        try: self._log_path(0).rename(self._log_path(1))
        except Exception: pass
        self._cache = []
        self._write_json(self._log_path(0), [])

    # ── Input processing ───────────────────────────────────────────────────────
    @staticmethod
    def _sanitise(text: str) -> str:
        text = text.strip()[:500]
        return re.sub(r"[\x00-\x08\x0b\x0e-\x1f\x7f]", "", text)

    @staticmethod
    def _is_injection(text: str) -> bool:
        low = text.lower()
        return any(re.search(pat, low) for pat in _INJECTION_PATTERNS)

    def _extract_user_facts(self, text: str) -> None:
        """Silently extract and remember facts about the user."""
        if not _BRAIN:
            return
        for pattern, key in _FACT_PATTERNS:
            m = pattern.search(text)
            if m:
                value = m.group(1).strip()
                if 2 <= len(value) <= 50:
                    save_user_fact(key, value)

    # ── Greeting/Farewell handlers ────────────────────────────────────────────
    def _handle_greeting(self) -> str:
        hour = datetime.datetime.now().hour
        if _BRAIN:
            from Backend.Brain.emotion import get_time_greeting
            base = get_time_greeting()
        else:
            if   5 <= hour < 12: base = f"Good morning {Username}!"
            elif 12<= hour < 17: base = f"Good afternoon {Username}!"
            elif 17<= hour < 22: base = f"Good evening {Username}!"
            else:                base = f"Hey {Username}!"

        # Add memory-based follow-up
        if _BRAIN:
            yesterday = None
            try:
                from Backend.Brain.memory import get_yesterday_summary
                yesterday = get_yesterday_summary()
            except Exception:
                pass
            if yesterday:
                return f"{base} Yesterday we talked about: {yesterday[:80]}... Want to continue?"
        return f"{base} What can I do for you today?"

    def _handle_farewell(self) -> str:
        if _BRAIN:
            return get_farewell(self._current_emotion)
        return f"Goodbye {Username}! Talk soon."

    # ── Memory compression ─────────────────────────────────────────────────────
    def _maybe_compress(self) -> None:
        if len(self._cache) < MAX_HISTORY:
            return
        half      = len(self._cache) // 2
        old_turns = self._cache[:half]
        self._cache = self._cache[half:]
        lines = [
            f"{'User' if m['role']=='user' else Assistantname}: {m['content'][:120]}"
            for m in old_turns
        ]

        def _bg():
            try:
                resp = _client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role":"system","content":"Summarise this conversation in 3-4 sentences."},
                        {"role":"user","content":"\n".join(lines)},
                    ],
                    max_tokens=150, temperature=0.3, stream=False,
                )
                summary = resp.choices[0].message.content.strip()
                with self._lock:
                    self._cache.insert(0, {
                        "role":"system",
                        "content": f"[Earlier conversation summary]: {summary}",
                    })
                # Save to persistent memory
                if _BRAIN:
                    from Backend.Brain.memory import save_daily_summary
                    save_daily_summary(summary, [], [])
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    # ── Response filtering ─────────────────────────────────────────────────────
    @staticmethod
    def _filter_response(text: str) -> str:
        """Production cleaner: removes AI boilerplate and redundant titles."""
        for pat in _AI_BOILERPLATE:
            text = re.sub(pat, "", text, flags=re.IGNORECASE)
        
        # Collapse 3+ newlines to 2 (one empty line)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Context-Aware Emojis ──────────────────────────────────────────────────
    _EMOJI_MAP = {
        "time": "🕒", "date": "📅", "day": "⏳", 
        "weather": "☀️", "temp": "🌡️", "rain": "🌧️",
        "search": "🔍", "find": "🔎", "news": "📰",
        "open": "🚀", "close": "🚪", "app": "💻",
        "system": "⚙️", "health": "🏥", "battery": "🔋",
        "email": "📧", "mail": "📨", "whatsapp": "💬",
        "music": "🎵", "play": "🎶", "video": "📺",
        "joke": "😄", "funny": "🤣", "laugh": "😆",
        "calculate": "🔢", "math": "📐", "study": "📚",
        "reminder": "⏰", "alarm": "🔔", "timer": "⏳",
    }

    @classmethod
    def _get_context_emoji(cls, text: str) -> str:
        """Production intelligence: returns the perfect emoji for the situation."""
        text_lc = text.lower()
        for kw, emoji in cls._EMOJI_MAP.items():
            if kw in text_lc:
                return emoji
        return "🧠" # Default for intelligent chat

    @staticmethod
    def answer_modifier(answer: str) -> str:
        """
        Smart Spacing + Context Emojis:
        Fixes the 'wall of text' while adding situational flair.
        """
        lines = [ln.rstrip() for ln in answer.split("\n")]
        final_lines = []
        
        for i, line in enumerate(lines):
            if line.strip():
                final_lines.append(line)
            elif i > 0 and i < len(lines)-1 and lines[i-1].strip() and lines[i+1].strip():
                if not (final_lines and final_lines[-1] == ""):
                    final_lines.append("")
                    
        # Append situational emoji if not already containing one
        emoji = JarvisChatbot._get_context_emoji(answer)
        if final_lines and not any(e in final_lines[-1] for e in "🕒📅⏳☀️🌡️🌧️🔍🔎📰🚀🚪💻⚙️🏥🔋📧📨💬🎵🎶📺😄🤣😆🔢📐📚⏰🔔"):
            final_lines[-1] = f"{final_lines[-1]} {emoji}"
            
        return "\n".join(final_lines)

    # ── Realtime context ───────────────────────────────────────────────────────
    _TIME_KEYWORDS = frozenset([
        "time","date","day","today","yesterday","tomorrow","week",
        "month","year","when","schedule","now","current",
    ])

    def _needs_realtime(self, query: str) -> bool:
        return any(kw in query.lower() for kw in self._TIME_KEYWORDS)

    @staticmethod
    def _realtime_info() -> str:
        now = datetime.datetime.now()
        return (
            f"Real-time: Day={now.strftime('%A')}, "
            f"Date={now.strftime('%d %B %Y')}, "
            f"Time={now.strftime('%H:%M')}"
        )

    # ── Groq call ──────────────────────────────────────────────────────────────
    def _call_groq(
        self,
        payload   : list[dict],
        callback  : Optional[Callable[[str], None]] = None,
    ) -> str:
        last_err: Exception = RuntimeError("No attempts")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                completion = _client.chat.completions.create(
                    model=MODEL, messages=payload,
                    max_tokens=MAX_TOKENS, temperature=TEMPERATURE,
                    top_p=TOP_P, stream=True,
                )
                answer = ""
                for chunk in completion:
                    content = None
                    try:
                        content = getattr(chunk.choices[0].delta, "content", None)
                    except Exception:
                        pass
                    if content:
                        answer += content
                        if callback:
                            try: callback(content)
                            except Exception: pass
                return answer.replace("</s>","").strip()
            except Exception as exc:
                last_err = exc
                if attempt < MAX_RETRIES:
                    time.sleep(attempt * 1.5)
        raise last_err

    # ── PUBLIC CHAT ────────────────────────────────────────────────────────────
    def chat(
        self,
        query   : str,
        tone    : str = "professional",
        callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        with self._lock:
            # 1. Clean
            query = self._sanitise(query)
            if not query:
                return "Please say something and I'll help."

            # 2. Injection guard
            if self._is_injection(query):
                return "I can't follow instructions that override my settings. How can I help normally?"

            # 3. Context Triage
            sys_prompt = self._get_system_prompt(query, tone)
            payload = [{"role": "system", "content": sys_prompt}]
            
            # Add context if brain available
            if _BRAIN:
                context = build_memory_context()
                if context:
                    payload.append({"role": "system", "content": f"Memory Context: {context}"})
            
            payload.append({"role": "user", "content": query})

            # 3. Extract user facts silently
            self._extract_user_facts(query)

            # 4. Detect emotion — update running state
            if _BRAIN:
                emo = detect_emotion(query)
                if emo:
                    self._current_emotion = emo
                    self._emotion_count   = self._emotion_count + 1
                elif self._emotion_count > 0:
                    self._emotion_count -= 1
                    if self._emotion_count == 0:
                        self._current_emotion = None

            # 6. Groq call with consolidated payload
            try:
                # Add realtime info if needed
                if self._needs_realtime(query):
                    payload.append({"role": "system", "content": self._realtime_info()})

                # Add emotion prefix from Brain if strong emotion and tone is friendly
                emotion_pfx = ""
                if _BRAIN and tone == "friendly":
                    emotion_pfx = get_emotion_prefix(self._current_emotion)
                    if emotion_pfx:
                        payload.append({"role": "system", "content": f"Emotional context: {emotion_pfx}"})

                answer = self._call_groq(payload, callback)
                
                if _BRAIN: save_turn("user", query, self._current_emotion)
                if _BRAIN: save_turn("assistant", answer)
                
                # Cache for session continuity
                self._cache.append({"role":"user","content":query})
                self._cache.append({"role":"assistant","content":answer})
                self._cache_dirty = True
                
                return answer
            except Exception as e:
                return f"Sorry, my brain encountered an error: {e}"
            if _BRAIN and self._current_emotion:
                intensity = detect_emotion_intensity(query, self._current_emotion)
                if intensity >= 5:
                    emotion_pfx = get_emotion_prefix(self._current_emotion)

            self._cache.append({"role":"user","content":query})
            payload = sys_msgs + self._cache[-MAX_HISTORY:]

            # 9. Call Groq
            try:
                raw = self._call_groq(payload, callback)
            except Exception as exc:
                self._cache.pop()
                return f"Connection trouble. Please try again. ({type(exc).__name__})"

            if not raw:
                self._cache.pop()
                return "I didn't get a response. Could you rephrase?"

            # 10. Post-process
            answer = self._filter_response(raw)
            answer = self.answer_modifier(answer)
            if emotion_pfx:
                answer = emotion_pfx + answer

            # 11. Save to cache + persistent memory
            self._cache.append({"role":"assistant","content":answer})
            self._cache_dirty = True
            self._rotate_if_needed()
            self._flush(force=False)

            if _BRAIN:
                save_turn("user",      query,  self._current_emotion,
                          self._session_topics[-1] if self._session_topics else None)
                save_turn("assistant", answer)

            return answer

    def flush(self) -> None:
        with self._lock:
            self._flush(force=True)

    def clear_history(self) -> None:
        with self._lock:
            self._cache       = []
            self._cache_dirty = False
            self._write_json(self._log_path(0), [])


# ── Singleton + public API (100% backward compatible) ─────────────────────────
_bot = JarvisChatbot()

def ChatBot(Query: str, stream_callback: Optional[Callable[[str], None]] = None) -> str:
    return _bot.chat(Query, stream_callback)

def flush_chatbot()          -> None: _bot.flush()
def clear_chatbot_history()  -> None: _bot.clear_history()
def AnswerModifier(Answer: str) -> str: return JarvisChatbot.answer_modifier(Answer)
def RealtimeInformation()    -> str:   return JarvisChatbot._realtime_info()

if __name__ == "__main__":
    import atexit, sys as _sys
    atexit.register(flush_chatbot)
    print(f"\n{Assistantname} Chatbot v3.0 — Brain Active: {_BRAIN}")
    print("─"*50)
    try:
        while True:
            try:   ui = input("You: ").strip()
            except EOFError: break
            if not ui: continue
            if ui.lower() in ("quit","exit","bye"):
                print(f"{Assistantname}: {ChatBot(ui)}"); break
            print(f"\n{Assistantname}: {ChatBot(ui)}\n")
    except KeyboardInterrupt:
        print(f"\n{Assistantname}: Goodbye!")
    finally:
        flush_chatbot()
        _sys.exit(0)