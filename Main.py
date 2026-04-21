# Main.py — Jarvis AI Entry Point
# ─────────────────────────────────────────────────────────────────────────────
# HOW IT WORKS:
#   Thread 1 (main)    → GUI window (tkinter must run on main thread)
#   Thread 2 (daemon)  → Backend loop (mic, voice, chat, automation)
#
# FLOW:
#   Mic ON → SpeechRecognition → FirstLayerDMM → route to:
#     general/realtime → ChatBot → TextToSpeech
#     automation       → Automation(commands)
#   Typed input        → same routing via TypedInput.data file
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import os
import sys
import threading
import time
from pathlib import Path

from dotenv import dotenv_values
from core.state import state_manager, TaskState

# ── Fix working directory ─────────────────────────────────────────────────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

# ── Load env ──────────────────────────────────────────────────────────────────
_env          = dotenv_values(".env")
Username      = _env.get("Username",      "User")
Assistantname = _env.get("Assistantname", "Jarvis")

# ── Temp files dir ────────────────────────────────────────────────────────────
_TEMP = Path("data") / "Files"
_TEMP.mkdir(parents=True, exist_ok=True)

# ── Ensure all temp files exist ───────────────────────────────────────────────
for _fn in ["Mic.data", "Status.data", "Responses.data",
            "Database.data", "TypedInput.data", "Mode.data"]:
    _fp = _TEMP / _fn
    if not _fp.exists():
        _fp.write_text("", encoding="utf-8")

def _validate_env() -> None:
    """Task 2: Strict .env validation at startup."""
    required = {
        "GROQ_API_KEY": ["GroqAPIKey", "GroqKey"],
        "Username": [],
        "Assistantname": []
    }
    missing = []
    for key, aliases in required.items():
        found = _env.get(key)
        if not found:
            for alias in aliases:
                found = _env.get(alias)
                if found: break
        if not found:
            missing.append(key)
    
    if "GROQ_API_KEY" in missing:
        print("\n" + "="*52)
        print("  CRITICAL ERROR: Groq API Key Missing!")
        print("="*52)
        print("  1. Go to: https://console.groq.com/keys")
        print("  2. Create a key and add it to your .env file:")
        print("     GROQ_API_KEY=gsk_your_key_here")
        print("="*52 + "\n")
        sys.exit(1)
    
    if missing:
        print(f"  [WARN] Some non-critical .env keys missing: {', '.join(missing)}")

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS — each wrapped so one missing module won't crash everything
# ─────────────────────────────────────────────────────────────────────────────

# GUI (provides all bridge functions + thinking/streaming primitives)
try:
    from interface.terminal import (
        GraphicalUserInterface,
        SetAssistantStatus,
        GetAssistantStatus,
        ShowTextToScreen,
        SetMicrophoneStatus,
        GetMicrophoneStatus,
        AnswerModifier,
        QueryModifier,
        MicButtonInitialized,
        MicButtonClosed,
        ThinkingPrint,
        StreamingStart,
        StreamingEnd,
        StreamToken,
        SetJarvisBusy,
    )
    _GUI = True
except Exception as e:
    print(f"  [ERROR] GUI import failed: {e}")
    print("  Check: pip install tk")
    _GUI = False
    def GraphicalUserInterface(): input("GUI failed to load. Press Enter to exit.")
    def SetAssistantStatus(s):
        try: (_TEMP/"Status.data").write_text(s, encoding="utf-8")
        except: pass
    def GetAssistantStatus():
        try: return (_TEMP/"Status.data").read_text(encoding="utf-8").strip()
        except: return ""
    def ShowTextToScreen(t):
        try:
            with (_TEMP/"Responses.data").open("a", encoding="utf-8") as f:
                f.write(t+"\n")
        except: pass
    def SetMicrophoneStatus(s):
        try: (_TEMP/"Mic.data").write_text(s, encoding="utf-8")
        except: pass
    def GetMicrophoneStatus():
        try: return (_TEMP/"Mic.data").read_text(encoding="utf-8").strip()
        except: return "False"
    def AnswerModifier(t): return t
    def QueryModifier(q):  return q
    def MicButtonInitialized(): SetMicrophoneStatus("False")
    def MicButtonClosed():      SetMicrophoneStatus("True")
    # Thinking simulation stubs (terminal-only fallbacks)
    def ThinkingPrint(msg): sys.stdout.write(f"\n{msg}\n"); sys.stdout.flush()
    def StreamingStart(prefix=""): sys.stdout.write(f"\n{prefix}"); sys.stdout.flush()
    def StreamingEnd(): sys.stdout.write("\n"); sys.stdout.flush()
    def StreamToken(tok): sys.stdout.write(tok); sys.stdout.flush()
    def SetJarvisBusy(status): pass

# Intent classifier
try:
    from core.intent import FirstLayerDMM
    _MODEL = True
except Exception as e:
    print(f"  [WARN] Model not loaded: {e}")
    _MODEL = False
    def FirstLayerDMM(q): return ["general"]

# Chatbot
try:
    from core.chat import ChatBot
    _CHATBOT = True
except Exception as e:
    print(f"  [WARN] Chatbot not loaded: {e}")
    _CHATBOT = False
    def ChatBot(q, stream_callback=None): return f"I heard you say: {q}. (Chatbot not loaded)"

# Speech recognition
try:
    from interface.stt import SpeechRecognition
    _STT = True
except Exception as e:
    print(f"  [WARN] SpeechToText not loaded: {e}")
    _STT = False
    def SpeechRecognition(): return ""

# Text to speech
try:
    from interface.tts import TextToSpeech
    _TTS = True
except Exception as e:
    print(f"  [WARN] TextToSpeech not loaded: {e}")
    _TTS = False
    def TextToSpeech(t): print(f"  [TTS] {t}")

# Automation engine
try:
    from automation.engine import Automation
    _AUTO = True
except Exception as e:
    print(f"  [WARN] AutomationEngine not loaded: {e}")
    _AUTO = False
    async def Automation(cmds): print(f"  [AUTO] {cmds}")

# Realtime search (optional)
try:
    from utils.search import RealtimeSearchEngine
    _SEARCH = True
except Exception:
    _SEARCH = False
    def RealtimeSearchEngine(q): return ChatBot(q)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — read/write temp file safely
# ─────────────────────────────────────────────────────────────────────────────

def _read(filename: str, default: str = "") -> str:
    try:
        return (_TEMP / filename).read_text(encoding="utf-8").strip()
    except Exception:
        return default

def _write(filename: str, value: str) -> None:
    try:
        (_TEMP / filename).write_text(value, encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# THINKING SIMULATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_THINKING_STAGES = [
    "{name}: thinking... understanding your request... 🌏",
    "{name}: thinking... classifying intent... 🧠",
    "{name}: thinking... generating response... ✍️",
]


def _thinking_stage(stage: int) -> None:
    """Print one thinking stage line immediately."""
    if stage >= len(_THINKING_STAGES):
        return
    ThinkingPrint(_THINKING_STAGES[stage].format(name=Assistantname))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE COMMAND — decides what to do with a query
# ─────────────────────────────────────────────────────────────────────────────

_AUTOMATION_KEYWORDS = [
    "open", "close", "play", "system", "email", "whatsapp",
    "reminder", "study", "focus", "assignment", "timetable",
    "content", "explain", "quiz", "summarize", "notes",
    "kill", "app usage", "health", "screenshot", "volume",
    "battery", "wifi", "lock", "mute", "unmute",
]

def _is_automation(prediction: list) -> bool:
    """Check if any predicted label is an explicit automation command."""
    for item in prediction:
        lc = str(item).lower().strip()
        # Ensure the label either starts with the keyword + space or is an exact match
        # This prevents "how is the system" from being caught by "system shutdown"
        for kw in _AUTOMATION_KEYWORDS:
            if lc == kw or lc.startswith(kw + " "):
                return True
    return False


def _handle_query(query: str, is_typed: bool = False) -> None:
    """
    Core routing logic — same for voice and typed input.

    Thinking simulation flow:
      Stage 0 → immediately on entry        ("thinking... understanding...")
      Stage 1 → after DMM classification    ("thinking... classifying intent...")
      Stage 2 → just before API call        ("thinking... generating response...")
      Stream  → tokens appear word-by-word as Groq streams them back
    """
    if not query.strip():
        return

    if not is_typed:
        ShowTextToScreen(f"{Username} : {query}")

    # ── CONTEXT GUARD: If locked, automation is already handling input ────────
    if state_manager.is_locked():
        state_manager.set_state(TaskState.PROCESSING)
        return

    # ── STAGE 0: fire immediately, zero delay ─────────────────────────────────
    state_manager.set_state(TaskState.PROCESSING)
    _thinking_stage(0)
    SetAssistantStatus("Thinking...")

    try:
        # ── Intent classification ─────────────────────────────────────────────
        if _MODEL:
            prediction = FirstLayerDMM(query)
        else:
            prediction = ["general"]

        # ── STAGE 0: Permission Intercept ─────────────────────────────────────
        if state_manager.get_context() == "system_permission":
            ans = query.lower().strip()
            if any(w in ans for w in ("yes", "ok", "do it", "sure", "yep", "fine", "proceed")):
                from automation.modules.app_monitor import KillProcess
                pending_file = Path("Data")/"Files"/"PendingAction.data"
                if pending_file.exists():
                    action_data = pending_file.read_text(encoding="utf-8").split("|")
                    if action_data[0] == "kill":
                        KillProcess(action_data[1])
                        ShowTextToScreen(f"Jarvis : Optimizing system... {action_data[1]} closed.")
                        if _TTS: TextToSpeech("Optimizing system, sir.")
                pending_file.unlink(missing_ok=True)
                state_manager.set_context(None)
                state_manager.set_state(TaskState.IDLE)
                return
            else:
                # Cancel pending action
                (Path("Data")/"Files"/"PendingAction.data").unlink(missing_ok=True)
                state_manager.set_context(None)
                state_manager.set_state(TaskState.IDLE)
                # Continue to normal chat if it wasn't a clear 'no'
                if any(w in ans for w in ("no", "don't", "stop", "cancel")):
                    ShowTextToScreen("Jarvis : Understood. No changes made.")
                    return

        # ── STAGE 1: after DMM returned ───────────────────────────────────────
        _thinking_stage(1)

        # ── Automation commands ───────────────────────────────────────────────
        if _is_automation(prediction):
            _thinking_stage(2)
            SetAssistantStatus("Processing...")
            
            # Task 3: Safe Async Runner to prevent RuntimeError across threads
            def _run_automation():
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(Automation(prediction))
                except Exception as e:
                    print(f"  [ERROR] Automation Loop: {e}")
                finally:
                    loop.close()
                    # BUG #4 FIX: Always reset state so Jarvis never freezes permanently
                    state_manager.set_state(TaskState.IDLE)
                    SetAssistantStatus("Available...")
                    SetJarvisBusy(False)
            
            threading.Thread(target=_run_automation, daemon=True).start()
            return

        # ── Realtime search ───────────────────────────────────────────────────
        if "realtime" in str(prediction).lower():
            _thinking_stage(2)
            SetAssistantStatus("Searching...")
            if _SEARCH:
                answer = RealtimeSearchEngine(QueryModifier(query))
            else:
                answer = ChatBot(QueryModifier(query))
            answer = AnswerModifier(answer)
            # Realtime results arrive as a single block — print normally
            ShowTextToScreen(f"{Assistantname} : {answer}")
            if _TTS:
                TextToSpeech(answer)
            return

        # ── General chat — STREAMED token by token ────────────────────────────
        _thinking_stage(2)
        SetAssistantStatus("Answering...")

        # Buffer the full answer for TTS (which needs the complete text)
        _full_answer: list[str] = []

        def _stream_callback(token: str) -> None:
            _full_answer.append(token)
            StreamToken(token)

        # Determine role based on prefix content
        tone = state_manager.get_tone()
        StreamingStart(f"Jarvis ({tone}): ")

        # This blocks until Groq finishes, but _stream_callback fires per token
        answer = ChatBot(QueryModifier(query), tone=tone, stream_callback=_stream_callback)

        # Put the cursor on a new line after the last token
        StreamingEnd()

        # Fallback: if stream_callback never fired (error/empty), print normally
        if not _full_answer and answer:
            ShowTextToScreen(f"{Assistantname} : {answer}")

        # TTS uses the complete assembled answer
        final_answer = AnswerModifier(answer)
        if _TTS:
            TextToSpeech(final_answer)

    except Exception as e:
        print(f"  [ERROR] _handle_query: {e}")
    finally:
        SetAssistantStatus("Available...")
        StreamingEnd()
        SetJarvisBusy(False) # Always release the prompt lock


# ─────────────────────────────────────────────────────────────────────────────
# BACKEND LOOP — runs in daemon thread
# ─────────────────────────────────────────────────────────────────────────────

_last_typed = ""

def MainExecution() -> None:
    """
    Main backend loop.
    Polls every 100ms for:
      1. Mic active → voice input
      2. TypedInput.data → text input from GUI
    """
    global _last_typed

    print(f"  [{Assistantname}] Backend started.")
    SetAssistantStatus("Available...")

    # BUG #9 FIX: Adaptive sleep — fast when active, slow when idle
    _ACTIVE_SLEEP = 0.05   # 50ms  when mic is live or input arrived
    _IDLE_SLEEP   = 0.20   # 200ms when nothing is happening
    _sleep_time   = _IDLE_SLEEP

    while True:
        try:
            # ── 1. VOICE INPUT ────────────────────────────────────────────
            mic = _read("Mic.data", "False")

            if mic == "True":
                _sleep_time = _ACTIVE_SLEEP
                SetAssistantStatus("Listening...")
                query = SpeechRecognition() if _STT else ""

                if query and query.strip():
                    _handle_query(query.strip(), is_typed=False)
                else:
                    SetAssistantStatus("Available...")
            else:
                _sleep_time = _IDLE_SLEEP

            # ── 2. TYPED INPUT from GUI ───────────────────────────────────
            typed_file = _TEMP / "TypedInput.data"
            if typed_file.exists():
                typed = typed_file.read_text(encoding="utf-8").strip()
                if typed and typed != _last_typed:
                    _last_typed = typed
                    _sleep_time = _ACTIVE_SLEEP
                    SetJarvisBusy(True) # Lock prompt instantly
                    # Clear immediately to signal GUI that we've picked it up
                    typed_file.write_text("", encoding="utf-8")
                    _handle_query(typed, is_typed=True)

        except KeyboardInterrupt:
            print(f"\n  [{Assistantname}] Shutting down...")
            break
        except Exception as e:
            print(f"  [ERROR] MainExecution loop: {e}")
            SetAssistantStatus("Available...")

        time.sleep(_sleep_time)   # Adaptive: 50ms active / 200ms idle

# ─────────────────────────────────────────────────────────────────────────────
# STARTUP CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def _startup_check() -> None:
    """Print module status on startup."""
    print("\n" + "=" * 52)
    print(f"  {Assistantname} AI - Starting up")
    print("=" * 52)

    checks = [
        ("GUI          ", _GUI),
        ("Model/Intent ", _MODEL),
        ("Chatbot      ", _CHATBOT), 
        ("SpeechToText ", _STT),
        ("TextToSpeech ", _TTS),
        ("Automation   ", _AUTO),
        ("RealtimeSearch", _SEARCH),
    ]
    for name, loaded in checks:
        status = "OK    " if loaded else "MISSING"
        mark   = "" if loaded else "  ***"
        print(f"  {status}  {name}{mark}")

    print("=" * 52)

    # Warn about missing .env keys
    missing = []
    for key in ["GroqAPIKey", "Username", "Assistantname"]:
        if not _env.get(key):
            missing.append(key)
    if missing:
        print(f"\n  [WARN] Missing .env keys: {', '.join(missing)}")
        print("  Add them to your .env file.\n")

    print(f"\n  User      : {Username}")
    print(f"  Assistant : {Assistantname}")
    print(f"  Temp dir  : {_TEMP.resolve()}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _validate_env()
    _startup_check()

    # Start backend in daemon thread
    backend_thread = threading.Thread(
        target=MainExecution,
        daemon=True,
        name="JarvisBackend"
    )
    backend_thread.start()

    # Start GUI on main thread
    # (tkinter MUST run on the main thread — never in a thread)
    try:
        GraphicalUserInterface()
    except KeyboardInterrupt:
        print(f"\n  [{Assistantname}] Goodbye!\n")
    finally:
        SetMicrophoneStatus("False")
        sys.exit(0)
