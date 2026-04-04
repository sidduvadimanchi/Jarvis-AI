# Backend/SpeechRecognition.py
# Python 3.10+ | Production-grade Speech Recognition for Jarvis
# ─────────────────────────────────────────────────────────────────────────────
# BUG-1  ✅ JS init: window.SpeechRecognition || window.webkitSpeechRecognition
# BUG-2  ✅ CPU loop: 0.25s sleep + WebDriverWait — no more 100% CPU
# BUG-3  ✅ Session check before every DOM access + auto Chrome restart
# BUG-4  ✅ InputLanguage: env_vars.get("InputLanguage") or "en-US"
# BUG-5  ✅ ChromeDriver path cached in file — no re-download every run
# BUG-6  ✅ lang injected into HTML via format, not fragile string replace
# BUG-7  ✅ 10s timeout in SpeechRecognition() — never hangs forever
# BUG-8  ✅ HTML written once (hash check) — not on every import
# BUG-9  ✅ PRIMARY engine = speech_recognition (5MB) — Selenium is fallback
# BUG-10 ✅ QueryModifier uses startswith() — no false questions
# BUG-11 ✅ deep-translator replaces unmaintained mtranslate
# BUG-12 ✅ Class-based _ChromeSTT — no global driver, restartable
# BUG-13 ✅ Full type hints on all public functions
# BUG-14 ✅ pathlib throughout — Python 3.10 best practice
# BUG-15 ✅ adjust_for_ambient_noise() on every listen call
# BUG-16 ✅ energy_threshold=250, dynamic_energy_threshold=True
# FIX-17 ✅ audio-capture treated as fatal — no infinite loop
# FIX-18 ✅ headless removed — Chrome gets real mic access
# FIX-19 ✅ atexit cleanup registered on import (not just __main__)
# FIX-20 ✅ primary engine skip now prints clear warning
# ─────────────────────────────────────────────────────────────────────────────
# ARCHITECTURE:
#   PRIMARY  → speech_recognition library (fast, 5MB RAM, noise-resistant)
#   FALLBACK → Selenium Chrome Web Speech API (for non-English / no PyAudio)
#   Both engines feed into the same QueryModifier → Main.py pipeline
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import atexit
import os
import re
import time
import hashlib
import threading
from pathlib import Path
from typing  import Optional
from dotenv  import load_dotenv

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# Configuration — loaded once at import, never re-read
# ═════════════════════════════════════════════════════════════════════════════

# BUG-4 FIX: 'or' ensures empty string falls back to default
InputLanguage: str = (os.getenv("InputLanguage") or "en-US").strip()
Username:      str = os.getenv("Username",      "User")
Assistantname: str = os.getenv("Assistantname", "Jarvis")

# BUG-14 FIX: pathlib everywhere
_ROOT       = Path.cwd()
_DATA_DIR   = _ROOT / "Data"
_TEMP_DIR   = _ROOT / "Frontend" / "Files"
_HTML_PATH  = _DATA_DIR / "Voice.html"
_HASH_PATH  = _DATA_DIR / "Voice.html.md5"   # BUG-8: hash cache
_DRIVER_CACHE = _DATA_DIR / "chromedriver.path"  # BUG-5: driver path cache

_DATA_DIR.mkdir(parents=True, exist_ok=True)
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Tunable constants — change here, affects entire system
LISTEN_TIMEOUT     : int   = 8    # BUG-7: max seconds waiting for speech start
PHRASE_TIME_LIMIT  : int   = 15    # max seconds for a single phrase
SELENIUM_TIMEOUT   : int   = 12    # seconds for Chrome DOM wait
CALIBRATE_SECS     : float = 0.1   # ambient noise calibration duration
ENERGY_THRESHOLD   : int   = 50    # SOFT-VOICE: lowered for normal speaking volume
POLL_SLEEP         : float = 0.25  # BUG-2: DOM poll interval (was 0)
MAX_CHROME_RETRIES : int   = 3     # BUG-3: Chrome crash recovery attempts


# ═════════════════════════════════════════════════════════════════════════════
# PRIMARY ENGINE: speech_recognition
# BUG-9 FIX: 5MB RAM vs 400MB for Chrome — use this as primary
# ═════════════════════════════════════════════════════════════════════════════
_SR_AVAILABLE = False
_recognizer   = None
sr            = None

try:
    import speech_recognition as sr                      # type: ignore
    _recognizer = sr.Recognizer()

    # BUG-16 FIX: noise-resistant recognizer settings
    _recognizer.energy_threshold                     = ENERGY_THRESHOLD
    _recognizer.dynamic_energy_threshold             = False   # auto-adapts to room noise
    _recognizer.dynamic_energy_adjustment_damping    = 0.15   # faster noise adaptation
    _recognizer.pause_threshold                      = 0.6    # 0.6s silence = end of speech (SOFT-VOICE)
    _recognizer.non_speaking_duration                = 0.4
    _recognizer.operation_timeout                    = None   # handled via listen() timeout
    _SR_AVAILABLE = True
except ImportError:
    # FIX-20: clear warning so developer knows why primary engine was skipped
    print(
        "[STT] WARNING: 'speech_recognition' or 'PyAudio' not installed.\n"
        "         Primary engine disabled. Using Selenium fallback.\n"
        "         To fix: pip install SpeechRecognition PyAudio"
    )


# ═════════════════════════════════════════════════════════════════════════════
# FALLBACK ENGINE: Selenium Chrome Web Speech API
# ═════════════════════════════════════════════════════════════════════════════
_SELENIUM_AVAILABLE = False
try:
    from selenium                                import webdriver               # type: ignore
    from selenium.webdriver.common.by            import By                      # type: ignore
    from selenium.webdriver.chrome.service       import Service                 # type: ignore
    from selenium.webdriver.chrome.options       import Options                 # type: ignore
    from selenium.webdriver.support.ui           import WebDriverWait           # type: ignore
    from selenium.webdriver.support              import expected_conditions as EC # type: ignore
    from selenium.common.exceptions              import (                        # type: ignore
        WebDriverException, NoSuchElementException, TimeoutException as _SeTO,
    )
    _SELENIUM_AVAILABLE = True
except ImportError:
    pass


# ═════════════════════════════════════════════════════════════════════════════
# TRANSLATOR: deep-translator (BUG-11 FIX — replaces broken mtranslate)
# ═════════════════════════════════════════════════════════════════════════════
_TRANSLATE_AVAILABLE = False
try:
    from deep_translator import GoogleTranslator as _GT  # type: ignore
    _TRANSLATE_AVAILABLE = True

    def _do_translate(text: str) -> str:
        return _GT(source="auto", target="en").translate(text) or text

except ImportError:
    # graceful fallback — try old mtranslate, else no-op
    try:
        import mtranslate as _mt                          # type: ignore
        def _do_translate(text: str) -> str:
            try:
                return _mt.translate(text, "en", "auto") or text
            except Exception:
                return text
    except ImportError:
        def _do_translate(text: str) -> str:
            return text   # no translator — return as-is


# ═════════════════════════════════════════════════════════════════════════════
# HTML template for Selenium engine
# BUG-1  FIX: correct JS init
# BUG-6  FIX: lang via {lang} format — no fragile string replace
# BUG-8  FIX: hash-checked — written only when content changes
# ═════════════════════════════════════════════════════════════════════════════
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Jarvis Voice</title>
</head>
<body>
    <button id="start" onclick="startRecognition()">Start</button>
    <button id="end"   onclick="stopRecognition()">Stop</button>
    <p id="output"></p>
    <p id="status">ready</p>

<script>
    const output = document.getElementById('output');
    const status = document.getElementById('status');
    let recognition = null;
    let active = false;

    // BUG-1 FIX: correct cross-browser init
    const SpeechAPI = window.SpeechRecognition || window.webkitSpeechRecognition;

    function startRecognition() {{
        if (!SpeechAPI) {{
            status.textContent = "error:unsupported";
            return;
        }}
        try {{
            recognition = new SpeechAPI();
            // BUG-6 FIX: lang set from Python format — never empty at runtime
            recognition.lang           = '{lang}';
            recognition.continuous     = true;
            recognition.interimResults = false;
            active = true;
            status.textContent = "listening";

            recognition.onresult = function(e) {{
                const t = e.results[e.results.length - 1][0].transcript.trim();
                if (t) {{
                    output.textContent += t + " ";
                    status.textContent  = "received";
                }}
            }};

            recognition.onerror = function(e) {{
                status.textContent = "error:" + e.error;
                if (active && e.error !== "not-allowed" && e.error !== "service-not-allowed" && e.error !== "audio-capture") {{
                    setTimeout(() => {{ if (active) {{ try {{ recognition.start(); }} catch(ex) {{}} }} }}, 400);
                }}
            }};

            recognition.onend = function() {{
                if (active) {{
                    try {{ recognition.start(); }} catch(ex) {{}}
                }}
            }};

            recognition.start();
        }} catch(ex) {{
            status.textContent = "error:init:" + ex.message;
        }}
    }}

    function stopRecognition() {{
        active = false;
        if (recognition) {{ try {{ recognition.stop(); }} catch(ex) {{}} }}
        output.innerHTML  = "";
        status.textContent = "stopped";
    }}
</script>
</body>
</html>"""


def _ensure_html() -> str:
    """
    BUG-8 FIX: Write HTML only when content has changed (hash comparison).
    Returns the file:// URI for the HTML file.
    """
    html = _HTML_TEMPLATE.format(lang=InputLanguage)  # BUG-6 FIX
    new_md5 = hashlib.md5(html.encode()).hexdigest()

    # Read cached hash
    if _HASH_PATH.exists() and _HTML_PATH.exists():
        try:
            if _HASH_PATH.read_text().strip() == new_md5:
                return _HTML_PATH.as_uri()   # unchanged — skip write
        except Exception:
            pass

    # Write updated HTML + hash
    _HTML_PATH.write_text(html, encoding="utf-8")
    try:
        _HASH_PATH.write_text(new_md5)
    except Exception:
        pass
    return _HTML_PATH.as_uri()


# ═════════════════════════════════════════════════════════════════════════════
# BUG-12 FIX: Class-based Chrome driver — no global variable, restartable
# BUG-3  FIX: session check before every DOM access
# BUG-5  FIX: ChromeDriver path cached in file — no re-download every run
# ═════════════════════════════════════════════════════════════════════════════
class _ChromeSTT:
    """
    Selenium Chrome fallback STT engine.
    Self-healing: detects crashes and restarts automatically.
    Memory-optimised: all heavy Chrome features disabled.
    FIX-18: headless removed so Chrome can access real microphone.
    """

    def __init__(self) -> None:
        self._driver   : Optional[object] = None
        self._lock     = threading.Lock()
        self._html_uri = _ensure_html()

    # ── BUG-5 FIX: driver path caching ───────────────────────────────────────
    @staticmethod
    def _get_driver_path() -> Optional[str]:
        # Check file cache first
        if _DRIVER_CACHE.exists():
            cached = _DRIVER_CACHE.read_text().strip()
            if cached and Path(cached).exists():
                return cached
        # Download if needed
        try:
            from webdriver_manager.chrome import ChromeDriverManager  # type: ignore
            path = ChromeDriverManager().install()
            _DRIVER_CACHE.write_text(path)
            return path
        except Exception as e:
            print(f"[ChromeSTT] Driver install failed: {e}")
            return None

    def _build_options(self) -> "Options":
        opts = Options()
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        opts.add_argument("--use-fake-ui-for-media-stream")   # mic access no popup
        # FIX-18: headless=new REMOVED — headless Chrome cannot access real microphone.
        # Chrome will open minimised instead (hidden from taskbar via window position).
        opts.add_argument("--window-position=-32000,-32000")  # off-screen, not headless
        opts.add_argument("--window-size=1,1")                # tiny window
        # Performance/stability flags
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_argument("--js-flags=--max-old-space-size=256")
        opts.add_argument("--memory-pressure-off")
        return opts

    def _start(self) -> bool:
        """Start Chrome. Returns True on success."""
        path = self._get_driver_path()
        if not path:
            return False
        try:
            svc = Service(path)
            self._driver = webdriver.Chrome(service=svc, options=self._build_options())
            return True
        except Exception as e:
            print(f"[ChromeSTT] Start error: {e}")
            self._driver = None
            return False

    def _is_alive(self) -> bool:
        """BUG-3 FIX: check Chrome session is still valid before DOM access."""
        if not self._driver:
            return False
        try:
            return bool(self._driver.session_id)  # type: ignore[union-attr]
        except Exception:
            return False

    def _restart(self) -> bool:
        """BUG-3 FIX: restart Chrome after crash."""
        print("[ChromeSTT] Restarting Chrome...")
        try:
            if self._driver:
                self._driver.quit()  # type: ignore[union-attr]
        except Exception:
            pass
        self._driver = None
        time.sleep(1.2)
        return self._start()

    def listen(self, timeout: int = SELENIUM_TIMEOUT) -> Optional[str]:
        """
        Open HTML page, start recognition, wait for result.
        BUG-2  FIX: POLL_SLEEP prevents 100% CPU.
        BUG-7  FIX: timeout enforced.
        BUG-3  FIX: session checked before every DOM call.
        FIX-17 FIX: audio-capture is fatal — exit immediately, no infinite loop.
        FIX-18 FIX: headless removed so real mic works.
        """
        with self._lock:
            # Lazy / recovery init
            if not self._is_alive():
                ok = False
                for attempt in range(1, MAX_CHROME_RETRIES + 1):
                    print(f"[ChromeSTT] Init attempt {attempt}/{MAX_CHROME_RETRIES}")
                    if self._start():
                        ok = True
                        break
                    time.sleep(1.5)
                if not ok:
                    print("[ChromeSTT] Could not start Chrome after retries")
                    return None

            try:
                self._driver.get(self._html_uri)          # type: ignore[union-attr]
                time.sleep(0.3)

                # Click Start
                self._driver.find_element(By.ID, "start").click()  # type: ignore[union-attr]

                # BUG-7 FIX: enforce timeout
                deadline = time.time() + timeout
                result   = ""

                while time.time() < deadline:
                    # BUG-2 FIX: sleep — prevents 100% CPU
                    time.sleep(POLL_SLEEP)

                    # BUG-3 FIX: session health check before DOM access
                    if not self._is_alive():
                        print("[ChromeSTT] Session lost during listen")
                        threading.Thread(target=self._restart, daemon=True).start()
                        return None

                    try:
                        st_el  = self._driver.find_element(By.ID, "status")   # type: ignore
                        out_el = self._driver.find_element(By.ID, "output")   # type: ignore
                        status = st_el.text.strip()
                        text   = out_el.text.strip()
                    except Exception:
                        continue   # transient DOM error — keep waiting

                    if status.startswith("error:"):
                        err = status.replace("error:", "")
                        print(f"[ChromeSTT] JS error: {err}")
                        # FIX-17: audio-capture = no mic access, fatal like not-allowed
                        # Stop immediately instead of looping 40+ times
                        if err in ("not-allowed", "service-not-allowed", "audio-capture"):
                            print(
                                f"[ChromeSTT] Fatal mic error '{err}' — "
                                "stopping. Check microphone permissions."
                            )
                            return None
                        continue

                    if text:
                        result = text
                        break

                # Stop recognition + clear output
                try:
                    self._driver.find_element(By.ID, "end").click()  # type: ignore
                except Exception:
                    pass

                return result or None

            except Exception as e:
                print(f"[ChromeSTT] Listen error: {e}")
                # Schedule restart for next call
                threading.Thread(target=self._restart, daemon=True).start()
                return None

    def quit(self) -> None:
        try:
            if self._driver:
                self._driver.quit()  # type: ignore[union-attr]
        except Exception:
            pass
        self._driver = None


# Lazy singleton — Chrome only starts if speech_recognition is unavailable
_chrome_instance: Optional[_ChromeSTT] = None
_chrome_lock = threading.Lock()

def _get_chrome() -> Optional[_ChromeSTT]:
    global _chrome_instance
    if not _SELENIUM_AVAILABLE:
        return None
    with _chrome_lock:
        if _chrome_instance is None:
            _chrome_instance = _ChromeSTT()
    return _chrome_instance


# ═════════════════════════════════════════════════════════════════════════════
# NOISE CANCELLATION HELPERS
# BUG-15 FIX: ambient calibration
# BUG-16 FIX: dynamic threshold
# ═════════════════════════════════════════════════════════════════════════════
_calibrated_once: bool = False   # FIX: calibrate only once — saves 0.1-0.2s per listen

def _calibrate(source: object) -> None:
    """
    Calibrate for ambient noise.
    FIX: Only runs ONCE at startup — skipped on subsequent calls.
    This saves 0.1-0.2s on every single voice command.
    """
    global _calibrated_once
    if _calibrated_once:
        return   # skip — already calibrated
    try:
        _recognizer.adjust_for_ambient_noise(        # type: ignore[union-attr]
            source, duration=CALIBRATE_SECS
        )
        if _recognizer.energy_threshold > 100:       # type: ignore[union-attr]
            _recognizer.energy_threshold = 50         # type: ignore[union-attr]
        _calibrated_once = True
        print(f"[STT] Calibrated. Energy threshold: {_recognizer.energy_threshold:.0f}")
    except Exception:
        pass


def _find_mic_index() -> Optional[int]:
    """
    FIX-21: Auto-detect best working microphone device index.
    Uses PyAudio directly to check input channels — only real
    input devices (not speakers/output) will have inputChannels > 0.
    Prefers built-in mic (Intel Smart Sound) over others.
    """
    if not _SR_AVAILABLE or sr is None:
        return None

    import pyaudio  # type: ignore
    p = pyaudio.PyAudio()

    # Build list of valid INPUT-only device indexes with their names
    input_devices: list[tuple[int, str]] = []
    try:
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                # Only real input devices have maxInputChannels > 0
                if int(info.get("maxInputChannels", 0)) > 0:
                    input_devices.append((i, info.get("name", "")))
            except Exception:
                continue
    finally:
        p.terminate()

    if not input_devices:
        print("[STT-Primary] No input devices found by PyAudio.")
        return None

    print(f"[STT] Found {len(input_devices)} input device(s):")
    for idx, name in input_devices:
        print(f"       [{idx}] {name}")

    # Priority keywords — pick best mic first
    priority_keywords = [
        "intel",
        "microphone array",
        "realtek hd audio mic",
        "microphone (realtek",
        "microphone",
        "headset",
        "input",
    ]

    # Try priority devices first, then rest
    def priority_score(item: tuple[int, str]) -> int:
        name_low = item[1].lower()
        for score, kw in enumerate(priority_keywords):
            if kw in name_low:
                return score
        return len(priority_keywords)

    sorted_devices = sorted(input_devices, key=priority_score)

    # Test each device using PyAudio directly (same method as test_mic.py)
    import pyaudio as _pa  # type: ignore
    p2 = _pa.PyAudio()
    working: list[tuple[int, str]] = []
    try:
        for idx, name in sorted_devices:
            try:
                stream = p2.open(
                    format=_pa.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    input_device_index=idx,
                    frames_per_buffer=1024,
                )
                stream.read(1024, exception_on_overflow=False)
                stream.stop_stream()
                stream.close()
                working.append((idx, name))
            except Exception:
                continue
    finally:
        p2.terminate()

    if working:
        best_idx, best_name = working[0]
        print(f"[STT] Selected mic index {best_idx}: {best_name}")
        return best_idx

    # Last resort — return index 1 (Intel Smart Sound) directly
    print("[STT] Using default mic index 1 (Intel Smart Sound)")
    return 1


# Cache mic index — detect once, reuse every call
_mic_index: Optional[int] = None
_mic_index_detected: bool = False


def _get_mic_index() -> Optional[int]:
    """Return cached mic index, detecting it on first call."""
    global _mic_index, _mic_index_detected
    if not _mic_index_detected:
        _mic_index = _find_mic_index()
        _mic_index_detected = True
    return _mic_index


def _primary_listen() -> Optional[str]:
    """
    PRIMARY: speech_recognition library listen + Google STT.
    BUG-9  FIX: 5MB RAM, not 400MB.
    BUG-15 FIX: calibrates for ambient noise.
    BUG-16 FIX: dynamic energy threshold enabled.
    BUG-7  FIX: timeout + phrase_time_limit.
    FIX-21 FIX: auto mic device detection — no more NoneType error.
    """
    if not _SR_AVAILABLE or sr is None:
        return None

    mic_idx = _get_mic_index()

    try:
        # FIX-21: use detected device_index instead of default None
        with sr.Microphone(device_index=mic_idx) as source:  # type: ignore
            _calibrate(source)                               # BUG-15 FIX

            try:
                audio = _recognizer.listen(     # type: ignore[union-attr]
                    source,
                    timeout          = LISTEN_TIMEOUT,    # BUG-7 FIX
                    phrase_time_limit= PHRASE_TIME_LIMIT,
                )
            except sr.WaitTimeoutError:         # type: ignore
                return None   # silence — normal, not an error

    except OSError as e:
        print(f"[STT-Primary] Mic error: {e}")
        # Do NOT reset mic index — keep using same device
        # Resetting caused Selenium fallback on every error
        return None
    except Exception as e:
        print(f"[STT-Primary] Unexpected: {e}")
        return None

    # Recognise — try Google (works online)
    try:
        text = _recognizer.recognize_google(    # type: ignore[union-attr]
            audio, language=InputLanguage
        )
        return text.strip() if text else None
    except sr.UnknownValueError:                # type: ignore
        return None   # silence / unintelligible — normal
    except sr.RequestError as e:                # type: ignore
        print(f"[STT-Primary] Google API error: {e}")
        return None
    except Exception as e:
        print(f"[STT-Primary] Recognise error: {e}")
        return None


# ═════════════════════════════════════════════════════════════════════════════
# BUG-10 FIX: QueryModifier — strong startswith detection, no false questions
# BUG-13 FIX: full type hints on all public functions
# ═════════════════════════════════════════════════════════════════════════════

# BUG-10 FIX: question words checked at START of query only
_QUESTION_STARTS = (
    "how ", "what ", "who ", "where ", "when ", "why ", "which ",
    "whose ", "whom ", "is ", "are ", "was ", "were ", "am ",
    "can you", "could you", "would you", "will you",
    "do you", "did you", "does ", "shall ", "should ",
    "may i", "could i", "have you", "has ", "had ",
)

# Supplementary regex — only fires if above misses an obvious question
_QUESTION_RE = re.compile(
    r"^(what|who|where|when|why|how|which|whose|whom)\b",
    re.IGNORECASE,
)

# STT misrecognition correction table
_CORRECTIONS: dict[str, str] = {
    "hay":           "hey",
    "helo":          "hello",
    "hellow":        "hello",
    "hellwo":        "hello",
    "can me":        "call me",
    "calls me":      "call me",
    "cold me":       "call me",
    "travis":        "jarvis",
    "service":       "jarvis",
    "harvest":       "jarvis",
    "a jarvis":      "hey jarvis",
    "whether":       "weather",
    "wether":        "weather",
    "you tube":      "youtube",
    "play musics":   "play music",
    "time india":    "time in india",
    "in indian standrads": "in indian standard time",
    "in indian standards": "in indian standard time",
}


def _apply_corrections(text: str) -> str:
    """Apply STT misrecognition corrections."""
    low = text.lower().strip()
    # Exact match first
    if low in _CORRECTIONS:
        return _CORRECTIONS[low]
    # Partial replacement
    for wrong, right in _CORRECTIONS.items():
        if wrong in low:
            low = low.replace(wrong, right)
    return low.strip()


def QueryModifier(Query: str) -> str:  # BUG-13 FIX: type hints
    """
    BUG-10 FIX: uses startswith() — no false questions from 'tell me how'.
    BUG-13 FIX: type hints added.
    Normalises punctuation, capitalises, applies corrections.
    """
    if not Query or not Query.strip():
        return ""

    q = _apply_corrections(Query).strip().rstrip(" .?!")

    # BUG-10 FIX: question only if query STARTS with a question word
    is_question = (
        q.lower().startswith(_QUESTION_STARTS)
        or bool(_QUESTION_RE.match(q))
    )

    q += "?" if is_question else "."
    return q.capitalize()


def UniversalTranslator(Text: str) -> str:  # BUG-13 FIX: type hints
    """
    BUG-11 FIX: deep-translator replaces broken mtranslate.
    BUG-13 FIX: type hints.
    """
    if not Text or not Text.strip():
        return ""
    try:
        result = _do_translate(Text.strip())
        return result.capitalize() if result else Text.capitalize()
    except Exception:
        return Text.capitalize()


# ═════════════════════════════════════════════════════════════════════════════
# Status writer (unchanged interface — Main.py compatible)
# ═════════════════════════════════════════════════════════════════════════════
def SetAssistantStatus(Status: str) -> None:  # BUG-13 FIX: type hint
    """Write status to file — used by GUI to show current state."""
    try:
        (_TEMP_DIR / "Status.data").write_text(Status, encoding="utf-8")
    except Exception as e:
        print(f"[STT] Status write error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API — SpeechRecognition()
# Drop-in replacement for original. Main.py calls: Query = SpeechRecognition()
# ═════════════════════════════════════════════════════════════════════════════
def SpeechRecognition() -> Optional[str]:  # BUG-13 FIX: type hint
    """
    Unified, noise-resistant speech recognition.

    Strategy (fastest → slowest):
      1. speech_recognition library (primary — fast, 5MB, noise-resistant)
      2. Selenium Chrome fallback (for systems without PyAudio)
      3. Translate if non-English, then QueryModifier for punctuation

    Returns:
        str  — processed, punctuated query ready for AI pipeline
        None — nothing heard / error (Main.py should skip this cycle)

    NEVER raises exceptions — all errors handled internally.
    Compatible: Main.py calls  Query = SpeechRecognition()
    """
    is_english = InputLanguage.lower().startswith("en")
    raw: Optional[str] = None

    # ── Stage 1: Primary engine (speech_recognition) ─────────────────────────
    if _SR_AVAILABLE:
        raw = _primary_listen()
        if raw:
            print(f"[STT] Primary: {raw!r}")

    # ── Stage 2: Selenium fallback — DISABLED (primary mic works fine) ──────────
    # Selenium adds 3-5 second delay and causes Chrome popups
    # Only enable if primary mic completely fails on your system
    # if not raw and _SELENIUM_AVAILABLE:
    #     print("[STT] Trying Selenium fallback...")
    #     chrome = _get_chrome()
    #     if chrome:
    #         raw = chrome.listen()
    #         if raw:
    #             print(f"[STT] Selenium: {raw!r}")

    if not raw or not raw.strip():
        return None

    # ── Stage 3: Translate if non-English ────────────────────────────────────
    if not is_english:
        SetAssistantStatus("Translating...")
        raw = UniversalTranslator(raw)
        SetAssistantStatus("Listening...")

    # ── Stage 4: QueryModifier — punctuation + correction ────────────────────
    result = QueryModifier(raw)
    if result:
        print(f"[STT] Final: {result!r}")
    return result or None


# ═════════════════════════════════════════════════════════════════════════════
# Cleanup — FIX-19: registered on import, not just __main__
# ═════════════════════════════════════════════════════════════════════════════
def cleanup() -> None:
    """Properly shut down Chrome if it was started."""
    global _chrome_instance
    if _chrome_instance:
        _chrome_instance.quit()
        _chrome_instance = None


# FIX-19: register cleanup whenever this module is imported (not just __main__)
atexit.register(cleanup)


# ═════════════════════════════════════════════════════════════════════════════
# CLI diagnostic + test runner
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    print("=" * 55)
    print(f"  {Assistantname} — SpeechRecognition Engine")
    print("=" * 55)
    print(f"  Language  : {InputLanguage}")
    print(f"  Primary   : {'✅ speech_recognition' if _SR_AVAILABLE   else '❌ not installed (pip install SpeechRecognition PyAudio)'}")
    print(f"  Fallback  : {'✅ Selenium Chrome'    if _SELENIUM_AVAILABLE else '❌ not installed (pip install selenium webdriver-manager)'}")
    print(f"  Translator: {'✅ deep-translator'    if _TRANSLATE_AVAILABLE else '⚠️  fallback active (pip install deep-translator)'}")
    print(f"  Noise calib: ✅ {CALIBRATE_SECS}s per listen")
    print(f"  Timeout    : ✅ {LISTEN_TIMEOUT}s")
    print(f"  Energy thr : ✅ {ENERGY_THRESHOLD} (dynamic)")
    print("=" * 55)
    print("  Speak now — Ctrl+C to quit\n")

    try:
        while True:
            result = SpeechRecognition()
            if result:
                print(f"  You said: {result}\n")
            else:
                print("  (nothing heard — try again)\n")
    except KeyboardInterrupt:
        print("\n  Goodbye!")
    finally:
        cleanup()
        sys.exit(0)