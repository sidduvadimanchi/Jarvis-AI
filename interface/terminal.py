import logging
from pathlib import Path
from core.state import state_manager, TaskState

# Suppress annoying third-party HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("cohere").setLevel(logging.WARNING)
logging.getLogger("groq").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Paths
_TEMP = Path("data") / "Files"
_TEMP.mkdir(parents=True, exist_ok=True)

# ── Production State Control ──────────────────────────────────────────────────
_print_lock = threading.Lock()
_jarvis_busy = False
_stream_buffer = ""
_last_headers = set()

class ResponseSanitizer:
    """
    Prevents duplicate content (signatures, greetings, headers)
    within a short scrolling window of responses.
    """
    def __init__(self, window_size=5):
        self.history = []
        self.window_size = window_size
        self.signatures = ["best regards", "sincerely", "thanks", "regards"]

    def is_duplicate(self, text: str) -> bool:
        low = text.lower().strip()
        if not low: return False
        
        # Check signature guard
        if any(sig in low for sig in self.signatures):
            if any(any(sig in h for sig in self.signatures) for h in self.history):
                return True

        if low in self.history:
            return True
            
        self.history.append(low)
        if len(self.history) > self.window_size:
            self.history.pop(0)
        return False

_sanitizer = ResponseSanitizer()

def SetJarvisBusy(status: bool) -> None:
    """Explicitly control the terminal prompt lock & global state."""
    global _jarvis_busy
    _jarvis_busy = status
    if status:
        state_manager.set_state(TaskState.PROCESSING)
    else:
        state_manager.set_state(TaskState.IDLE)


def ThinkingPrint(message: str) -> None:
    """Print status line with [SYSTEM] prefix and cache it."""
    global _last_headers
    if message in _last_headers:
        return
    _last_headers.add(message)
    with _print_lock:
        sys.stdout.write(f"\n[SYSTEM] {message}...\n")
        sys.stdout.flush()

def StreamingStart(prefix: str = "Assistant") -> None:
    """Start token stream with [JARVIS] or [AI] prefix."""
    global _jarvis_busy, _last_headers
    _jarvis_busy = True
    state_manager.set_state(TaskState.PROCESSING)
    _last_headers.clear()

    # Determine role based on prefix content
    role = "[AI]" if "body" in prefix.lower() or "generate" in prefix.lower() else "[JARVIS]"
    with _print_lock:
        sys.stdout.write(f"\n{role} ")
        sys.stdout.flush()


def StreamingEnd() -> None:
    """Finalize stream; flushes any leftover buffer and releases prompt."""
    global _jarvis_busy, _stream_buffer
    with _print_lock:
        if _stream_buffer:
            sys.stdout.write(_stream_buffer)
        sys.stdout.write("\n")
        sys.stdout.flush()
    _stream_buffer = ""
    _jarvis_busy = False


def StreamToken(token: str) -> None:
    """
    Production-grade buffered writer. 
    Collects tokens until a threshold (20 chars) or a word boundary is hit.
    This prevents 'stutter' and fixes broken multi-byte characters.
    """
    global _stream_buffer
    _stream_buffer += token

    # Flush conditions: word boundary OR buffer pressure
    if " " in token or len(_stream_buffer) > 20:
        with _print_lock:
            sys.stdout.write(_stream_buffer)
            sys.stdout.flush()
        _stream_buffer = ""

# Main Loop Execution
def GraphicalUserInterface():
    print("=" * 52)
    print("  [JARVIS TERMINAL MODE ACTIVE]")
    print("  Enter your commands below.")
    print("  Type '/mic' to toggle Voice Listening on or off.")
    print("  Press Ctrl+C to quit.")
    print("=" * 52)
    print()
    
    global _last_typed_echo
    _last_typed_echo = ""

    while True:
        try:
            # Sync terminal prompt with global state
            while state_manager.get_state() != TaskState.IDLE and not state_manager.get_context():
                time.sleep(0.05)
            
            # Additional safety sleep to let stdout clear
            time.sleep(0.1)
            
            prompt = "You (type '/mic' to toggle) > "
            if state_manager.get_state() == TaskState.COLLECTING:
                prompt = "Collecting Input > "
                
            req = input(prompt).strip()
            
            if not req:
                continue

            _last_typed_echo = req

            # Intercept /mic command
            if req.lower() == "/mic":
                current_status = GetMicrophoneStatus()
                new_status = "False" if current_status == "True" else "True"
                SetMicrophoneStatus(new_status)
                state_str = "ON" if new_status == "True" else "OFF"
                print(f"[SYSTEM] Microphone listening mode is now {state_str}")
                continue
            
            # Send text input to backend thread via shared file
            try:
                (_TEMP / "TypedInput.data").write_text(req, encoding="utf-8")
            except Exception as e:
                print(f"[Error writing input] {e}")

            # Wait until backend signals it has picked up the input.
            # We poll a tiny flag file instead of a fixed 0.5s sleep —
            # the backend will clear TypedInput.data once it reads it,
            # so we wait for that to happen (max 2s) instead of guessing.
            _deadline = time.time() + 2.0
            while time.time() < _deadline:
                try:
                    remaining = (_TEMP / "TypedInput.data").read_text(encoding="utf-8").strip()
                    if not remaining:   # backend cleared it → it's processing
                        break
                except Exception:
                    pass
                time.sleep(0.05)  # 50ms poll — 10× faster than the old 0.5s sleep

            # Now wait for Jarvis to finish entirely before showing next prompt
            _stream_deadline = time.time() + 60.0
            while _jarvis_busy and time.time() < _stream_deadline:
                time.sleep(0.01) # Faster poll for better responsiveness

        except (KeyboardInterrupt, EOFError):
            break

# Screen Output
def ShowTextToScreen(t):
    global _last_typed_echo
    # 1. Reject exact typed echo
    if _last_typed_echo and t.endswith(f": {_last_typed_echo}"):
        _last_typed_echo = "" # consume the echo
        return
    
    # 2. Reject internal duplicates
    if _sanitizer.is_duplicate(t):
        return

    # 3. Determine role prefix
    prefix = "[JARVIS]"
    if t.startswith("[SYSTEM]") or t.startswith("[AI]"):
        prefix = "" # already prefixed
    
    with _print_lock:
        print(f"\n{prefix} {t}\n")

# State Access Functions
def SetAssistantStatus(s):
    try: (_TEMP/"Status.data").write_text(s, encoding="utf-8")
    except: pass

def GetAssistantStatus():
    try: return (_TEMP/"Status.data").read_text(encoding="utf-8").strip()
    except: return ""

def SetMicrophoneStatus(s):
    try: (_TEMP/"Mic.data").write_text(s, encoding="utf-8")
    except: pass

def GetMicrophoneStatus():
    try: return (_TEMP/"Mic.data").read_text(encoding="utf-8").strip()
    except: return "False"

# Data Modifier Dummies
def AnswerModifier(t): 
    return t

def QueryModifier(q):  
    return q

def MicButtonInitialized(): 
    SetMicrophoneStatus("False")

def MicButtonClosed():      
    SetMicrophoneStatus("True")

# Request input from GUI (kept for legacy support)
def RequestGUIInput(msg): 
    return input(f"{msg}: ")

def GetCurrentMode(): 
    return "conv"
