# Backend/Automation/app_control.py
# ─────────────────────────────────────────────────────────────────────────────
# JARVIS AI — App & Web Control  v3.0
#
# FIXES from analysis document:
#   ✅ Removed BeautifulSoup scraping — direct Google search fallback
#   ✅ psutil process detection — no duplicate app launches
#   ✅ All network calls have timeout
#   ✅ Structured logging (file + console)
#   ✅ Alias dict clean and categorised
#   ✅ Multi-app commands  ("open chrome and vscode")
#   ✅ Folder shortcuts  ("open downloads")
#   ✅ No requests/BeautifulSoup import needed
#
# NEW FEATURES:
#   ✅ Study Mode — opens Chrome GFG Gate bookmark folder + study tabs
#   ✅ Focus Mode — blocks distracting sites via Windows hosts file
#   ✅ AI intent resolution — "open my coding environment" → vscode
#   ✅ App installer via winget
#   ✅ Duplicate process detection
#
# VOICE COMMANDS:
#   "open chrome"
#   "open chrome and vscode"
#   "open downloads"
#   "study mode"  /  "open gfg gate"
#   "focus mode on"  /  "focus mode off"
#   "close spotify"
#   "install vscode"
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging, os, re, subprocess, time, webbrowser
from pathlib import Path
from dotenv  import dotenv_values

import psutil
from AppOpener import open as appopen, close as appclose  # type: ignore

# ── env / logging ─────────────────────────────────────────────────────────────
_env       = dotenv_values(".env")
GROQ_KEY   = _env.get("GroqAPIKey") or _env.get("GROQ_API_KEY", "")
GROQ_MODEL = _env.get("GroqModel",  "llama-3.1-8b-instant")

DATA_DIR = Path("Data")
LOG_DIR  = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s  [%(levelname)s]  %(message)s",
    handlers = [
        logging.FileHandler(LOG_DIR / "jarvis.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("jarvis.app")

try:
    from .notifier import notify as _notify
except ImportError:
    def _notify(t, m): pass


# ══════════════════════════════════════════════════════════════════════════════
# ALIAS TABLE  — voice phrase → app name or URL
# ══════════════════════════════════════════════════════════════════════════════

APP_ALIASES: dict[str, str] = {
    # ── Editors ──────────────────────────────────────────────────────────
    "vs code":             "vscode",
    "visual studio code":  "vscode",
    "vscode":              "vscode",
    "coding editor":       "vscode",
    "my editor":           "vscode",
    "programming editor":  "vscode",
    "code editor":         "vscode",
    "text editor":         "notepad",
    "notepad":             "notepad",
    "notepad++":           "notepad++",
    "pycharm":             "pycharm",
    "intellij":            "intellij idea",
    "android studio":      "android studio",
    "sublime":             "sublime text",

    # ── Browsers ──────────────────────────────────────────────────────────
    "google":              "chrome",
    "internet":            "chrome",
    "browser":             "chrome",
    "chrome":              "chrome",
    "firefox":             "firefox",
    "edge":                "microsoft edge",
    "brave":               "brave",

    # ── Communication ─────────────────────────────────────────────────────
    "whatsapp":            "whatsapp",
    "telegram":            "telegram",
    "discord":             "discord",
    "slack":               "slack",
    "zoom":                "zoom",
    "teams":               "microsoft teams",
    "ms teams":            "microsoft teams",
    "skype":               "skype",

    # ── Office / Study ────────────────────────────────────────────────────
    "word":                "microsoft word",
    "excel":               "microsoft excel",
    "powerpoint":          "microsoft powerpoint",
    "ms word":             "microsoft word",
    "ms excel":            "microsoft excel",
    "slides":              "microsoft powerpoint",
    "onenote":             "microsoft onenote",

    # ── Media ─────────────────────────────────────────────────────────────
    "spotify":             "spotify",
    "music":               "spotify",
    "vlc":                 "vlc",
    "media player":        "vlc",
    "obs":                 "obs studio",

    # ── System tools ──────────────────────────────────────────────────────
    "task manager":        "taskmgr",
    "file explorer":       "explorer",
    "explorer":            "explorer",
    "calculator":          "calc",
    "calc":                "calc",
    "paint":               "mspaint",
    "cmd":                 "cmd",
    "terminal":            "wt",
    "powershell":          "powershell",

    # ── Websites ──────────────────────────────────────────────────────────
    "youtube":             "https://www.youtube.com",
    "gmail":               "https://mail.google.com",
    "geeksforgeeks":       "https://www.geeksforgeeks.org",
    "gfg":                 "https://www.geeksforgeeks.org",
    "leetcode":            "https://www.leetcode.com",
    "github":              "https://www.github.com",
    "stackoverflow":       "https://www.stackoverflow.com",
    "google classroom":    "https://classroom.google.com",
    "classroom":           "https://classroom.google.com",
    "chatgpt":             "https://chat.openai.com",
    "netflix":             "https://www.netflix.com",
    "instagram":           "https://www.instagram.com",
    "facebook":            "https://www.facebook.com",
    "twitter":             "https://www.twitter.com",
    "x":                   "https://www.x.com",
    "linkedin":            "https://www.linkedin.com",
    "amazon":              "https://www.amazon.in",
    "flipkart":            "https://www.flipkart.com",
    "google drive":        "https://drive.google.com",
    "drive":               "https://drive.google.com",
    "google docs":         "https://docs.google.com",
    "google sheets":       "https://sheets.google.com",
    "google slides":       "https://slides.google.com",
    "maps":                "https://maps.google.com",
    "google maps":         "https://maps.google.com",
    "wikipedia":           "https://www.wikipedia.org",
    "w3schools":           "https://www.w3schools.com",
    "hackerrank":          "https://www.hackerrank.com",
    "codeforces":          "https://codeforces.com",
}

# Folder shortcuts
_FOLDERS: dict[str, str] = {
    "downloads":      str(Path.home() / "Downloads"),
    "documents":      str(Path.home() / "Documents"),
    "desktop":        str(Path.home() / "Desktop"),
    "pictures":       str(Path.home() / "Pictures"),
    "music folder":   str(Path.home() / "Music"),
    "videos":         str(Path.home() / "Videos"),
    "jarvis project": str(Path.cwd()),
    "project folder": str(Path.cwd()),
}

# Sites blocked in focus mode
_BLOCKED: list[str] = [
    "instagram.com", "facebook.com", "twitter.com", "x.com",
    "netflix.com",   "youtube.com",  "reddit.com",  "tiktok.com",
    "snapchat.com",  "discord.com",  "whatsapp.com",
]

# Process name fragments for duplicate detection
_PROCS: dict[str, list[str]] = {
    "chrome":    ["chrome.exe"],
    "firefox":   ["firefox.exe"],
    "vscode":    ["code.exe"],
    "spotify":   ["spotify.exe"],
    "discord":   ["discord.exe"],
    "whatsapp":  ["whatsapp.exe"],
    "telegram":  ["telegram.exe"],
    "notepad":   ["notepad.exe"],
    "vlc":       ["vlc.exe"],
    "zoom":      ["zoom.exe"],
}

# Chrome executable locations (Windows)
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _chrome_exe() -> str | None:
    for p in _CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))

def _resolve(app: str) -> str:
    return APP_ALIASES.get(app.lower().strip(), app)

def _is_running(app: str) -> bool:
    """Return True if app process is already running."""
    app_low  = app.lower()
    procs    = _PROCS.get(app_low, [f"{app_low}.exe"])
    running  = {p.name().lower() for p in psutil.process_iter(["name"])}
    return any(pn.lower() in running for pn in procs)

def _open_in_chrome(url: str) -> None:
    """Open URL in Chrome specifically."""
    exe = _chrome_exe()
    if exe:
        subprocess.Popen([exe, url])
    else:
        webbrowser.open(url)

def _open_multiple_in_chrome(urls: list[str]) -> None:
    """Open multiple URLs as tabs in one Chrome window."""
    exe = _chrome_exe()
    if exe:
        subprocess.Popen([exe] + urls)
    else:
        for url in urls:
            webbrowser.open_new_tab(url)


# ══════════════════════════════════════════════════════════════════════════════
# AI INTENT RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

def _ai_resolve(natural: str) -> str:
    """
    Use Groq to map a natural language phrase to an app name.
    Example: "open my coding environment" → "vscode"
    Returns original if resolution fails.
    """
    if not GROQ_KEY:
        return natural
    known = ", ".join(sorted({v for v in APP_ALIASES.values() if not _is_url(v)})[:45])
    prompt = (
        f"User said: '{natural}'\n"
        f"Map to one of: {known}\n"
        f"Return ONLY the app name. No explanation."
    )
    try:
        from groq import Groq
        resp = Groq(api_key=GROQ_KEY).chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=15, temperature=0.1,
        )
        result = resp.choices[0].message.content.strip().lower()
        log.info("AI resolved '%s' → '%s'", natural, result)
        return result
    except Exception as e:
        log.warning("AI resolution failed: %s", e)
        return natural


# ══════════════════════════════════════════════════════════════════════════════
# STUDY MODE
# ══════════════════════════════════════════════════════════════════════════════

# URLs opened in study mode
_STUDY_URLS = [
    "https://www.geeksforgeeks.org/gate-cs-notes-gq/",    # GFG GATE notes
    "https://practice.geeksforgeeks.org/explore",          # GFG practice
    "https://www.geeksforgeeks.org/lmns-gq/",              # GFG GATE PYQs
    "https://www.leetcode.com/problemset/",                # LeetCode
]

def OpenStudyMode() -> bool:
    """
    Activate study mode:
      1. Open Chrome with all GFG GATE study tabs
      2. Try to open Chrome Bookmarks (GFG Gate folder is visible there)

    Voice: "study mode", "open gfg gate", "start studying"

    NOTE: Chrome does not allow opening a specific named bookmark folder
    via command line — there is no such URL. The closest we can do is
    open chrome://bookmarks/ so the user can click 'GFG Gate' folder,
    AND simultaneously open the actual study pages as tabs.
    """
    log.info("Study mode activated")

    exe = _chrome_exe()
    if not exe:
        log.warning("Chrome not found — using default browser")
        for url in _STUDY_URLS:
            webbrowser.open_new_tab(url)
        _notify("Study Mode 📚", "Opened study tabs")
        return True

    # Step 1: Open all study content tabs in a new Chrome window
    subprocess.Popen([exe, "--new-window"] + _STUDY_URLS)
    log.info("Opened %d study tabs", len(_STUDY_URLS))

    # Step 2: After brief delay, open bookmarks manager so user can
    # click the 'GFG Gate' folder manually if needed
    time.sleep(1.5)
    subprocess.Popen([exe, "chrome://bookmarks/"])

    print("\n  📚  Study Mode activated!")
    print(f"  Opened {len(_STUDY_URLS)} tabs: GFG GATE Notes, Practice, PYQs, LeetCode")
    print("  Also opened Chrome Bookmarks — click 'GFG Gate' folder to see your saved pages.\n")
    _notify("Study Mode 📚", f"{len(_STUDY_URLS)} study tabs opened")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# FOCUS MODE  — hosts-file site blocking
# ══════════════════════════════════════════════════════════════════════════════

_HOSTS  = r"C:\Windows\System32\drivers\etc\hosts"
_MARK   = "# JARVIS_FOCUS_MODE_START"
_ENDMRK = "# JARVIS_FOCUS_MODE_END"

def EnableFocusMode() -> bool:
    """Block distracting sites by editing Windows hosts file. Needs admin."""
    try:
        content = Path(_HOSTS).read_text(encoding="utf-8")
        if _MARK in content:
            print("  ℹ  Focus mode already enabled.")
            return True
        block = f"\n{_MARK}\n"
        for site in _BLOCKED:
            block += f"127.0.0.1  {site}\n127.0.0.1  www.{site}\n"
        block += f"{_ENDMRK}\n"
        with open(_HOSTS, "a", encoding="utf-8") as f:
            f.write(block)
        log.info("Focus mode ON — %d sites blocked", len(_BLOCKED))
        _notify("Focus Mode ON 🎯", f"{len(_BLOCKED)} sites blocked")
        print(f"\n  🎯  Focus mode enabled — {len(_BLOCKED)} distracting sites blocked.\n")
        return True
    except PermissionError:
        print("\n  ⚠  Focus mode needs Administrator rights.")
        print("  Right-click your terminal → Run as Administrator.\n")
        return False
    except Exception as e:
        log.error("Focus mode error: %s", e)
        return False

def DisableFocusMode() -> bool:
    """Remove focus mode block from hosts file."""
    try:
        lines     = Path(_HOSTS).read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        skip      = False
        for line in lines:
            if _MARK in line:
                skip = True
            if not skip:
                new_lines.append(line)
            if _ENDMRK in line:
                skip = False
        Path(_HOSTS).write_text("".join(new_lines), encoding="utf-8")
        log.info("Focus mode OFF")
        _notify("Focus Mode OFF", "Sites unblocked")
        print("\n  ✅  Focus mode disabled. All sites unblocked.\n")
        return True
    except PermissionError:
        print("\n  ⚠  Needs Administrator rights to disable.\n")
        return False
    except Exception as e:
        log.error("Disable focus error: %s", e)
        return False


# ══════════════════════════════════════════════════════════════════════════════
# APP INSTALLER  (winget)
# ══════════════════════════════════════════════════════════════════════════════

def InstallApp(app: str) -> bool:
    """Install an app via winget. Voice: 'install vscode'"""
    log.info("Installing: %s", app)
    print(f"\n  📦  Installing '{app}' via winget...")
    try:
        result = subprocess.run(
            ["winget", "install", app,
             "--silent", "--accept-package-agreements",
             "--accept-source-agreements"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            print(f"  ✅  '{app}' installed.")
            _notify("Installed ✅", app)
            return True
        print(f"  ⚠  winget returned code {result.returncode}.")
        print(f"  Output: {result.stdout[-300:] if result.stdout else ''}")
        return False
    except FileNotFoundError:
        print("  ❌  winget not found. Get it from the Microsoft Store.")
        return False
    except subprocess.TimeoutExpired:
        print("  ⚠  Installation running in background (took too long).")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# OPEN APP
# ══════════════════════════════════════════════════════════════════════════════

def OpenApp(app: str) -> bool:
    """
    Open a single app or website.

    Strategy
    ────────
    1. Folder shortcut check
    2. Alias resolution
    3. Direct URL → Chrome
    4. Duplicate process check → focus window
    5. AppOpener (installed apps database)
    6. System executable (calc, notepad, etc.)
    7. AI intent resolution
    8. Google search fallback (never fails)
    """
    clean = app.lower().strip()
    log.info("Open: '%s'", clean)

    # 1. Folder
    for key, path in _FOLDERS.items():
        if key in clean:
            os.startfile(path)
            log.info("Opened folder: %s", path)
            return True

    # 2. Alias
    resolved = _resolve(clean)

    # 3. URL
    if _is_url(resolved):
        _open_in_chrome(resolved)
        log.info("Opened URL: %s", resolved)
        return True

    # 4. Already running → bring to front via AppOpener
    if _is_running(resolved):
        log.info("'%s' already running — focusing", resolved)
        print(f"  ℹ  '{resolved}' is already running.")
        try:
            appopen(resolved, match_closest=True, output=False)
        except Exception:
            pass
        return True

    # 5. AppOpener
    for name in ([resolved] if resolved == clean else [resolved, clean]):
        try:
            appopen(name, match_closest=True, output=True, throw_error=True)
            log.info("AppOpener opened: %s", name)
            return True
        except Exception:
            pass

    # 6. System executables
    _sys = {"calc":"calc","notepad":"notepad","taskmgr":"taskmgr",
            "explorer":"explorer","mspaint":"mspaint","cmd":"cmd",
            "powershell":"powershell","wt":"wt"}
    if resolved in _sys:
        try:
            os.startfile(_sys[resolved])
            return True
        except Exception:
            pass

    # 7. AI intent resolution
    ai = _ai_resolve(app)
    if ai and ai.lower() != clean:
        log.info("AI resolved: '%s' → '%s'", app, ai)
        return OpenApp(ai)

    # 8. Google search fallback  (FIX: no BeautifulSoup, no scraping)
    search = f"https://www.google.com/search?q={app.replace(' ', '+')}"
    log.info("Fallback: Google search for '%s'", app)
    _open_in_chrome(search)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# CLOSE APP
# ══════════════════════════════════════════════════════════════════════════════

def CloseApp(app: str) -> bool:
    """
    Close an app gracefully. Falls back to psutil terminate.
    Voice: "close chrome", "close spotify"
    """
    clean    = app.lower().strip()
    resolved = _resolve(clean)
    log.info("Close: '%s'", resolved)

    # AppOpener close
    for name in ([resolved] if resolved == clean else [resolved, clean]):
        try:
            appclose(name, match_closest=True, output=True, throw_error=True)
            log.info("Closed: %s", name)
            return True
        except Exception:
            pass

    # psutil terminate fallback
    procs  = _PROCS.get(resolved, [f"{resolved}.exe"])
    killed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        if proc.info.get("name","").lower() in [p.lower() for p in procs]:
            try:
                proc.terminate()
                killed += 1
            except Exception:
                pass
    if killed:
        log.info("psutil killed %d process(es) for '%s'", killed, resolved)
        return True

    print(f"  ⚠  '{app}' may not be running.")
    return False


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-APP  ("open chrome and vscode")
# ══════════════════════════════════════════════════════════════════════════════

def OpenMultiple(command: str) -> bool:
    """Parse 'open X and Y and Z' and open each."""
    stripped = re.sub(r"^(open|launch|start|load)\s+", "", command.lower()).strip()
    apps     = re.split(r"\s+and\s+|\s*,\s*", stripped)
    ok       = 0
    for a in apps:
        a = a.strip()
        if a:
            if OpenApp(a):
                ok += 1
    return ok > 0


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND ROUTER  — called by AutomationEngine
# ══════════════════════════════════════════════════════════════════════════════

def handle_app_command(command: str) -> bool:
    """
    Main entry point. Routes voice command to correct handler.
    Called by AutomationEngine for any open/close/install/study/focus command.
    """
    cmd = command.lower().strip()

    # Study mode
    if any(w in cmd for w in ("study mode", "start study", "open gfg gate",
                               "gfg gate", "study session")):
        return OpenStudyMode()

    # Focus mode
    if any(w in cmd for w in ("focus enable","focus on","focus mode on",
                               "enable focus","block sites","study focus")):
        return EnableFocusMode()
    if any(w in cmd for w in ("focus disable","focus off","focus mode off",
                               "disable focus","unblock sites")):
        return DisableFocusMode()

    # Install
    if cmd.startswith("install "):
        return InstallApp(cmd[8:].strip())

    # Close
    if cmd.startswith(("close ","quit ","exit ")):
        app = re.sub(r"^(close|quit|exit)\s+","", cmd).strip()
        return CloseApp(app)

    # Multi-app open
    if " and " in cmd:
        return OpenMultiple(cmd)

    # Single open
    for prefix in ("open ","launch ","start ","load ","boot "):
        if cmd.startswith(prefix):
            return OpenApp(cmd[len(prefix):].strip())

    # Bare name
    return OpenApp(cmd)