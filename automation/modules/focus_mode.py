# Backend/Automation/focus_mode.py
# Jarvis AI — Focus Mode / Distraction Blocker
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Block social media + distracting sites via Windows hosts file
#   ✅ Enable/disable with voice
#   ✅ Custom site blocking
#   ✅ Auto DNS flush after changes
#   ✅ Backup original hosts file
#   ⚠  Requires: Run VSCode/terminal as Administrator
#
# VOICE COMMANDS:
#   "enable study mode"
#   "enable focus mode"
#   "disable focus mode"
#   "focus on"  /  "focus off"
#   "block instagram"
#   "unblock all sites"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from .notifier import notify

_env     = dotenv_values(".env")
DATA_DIR = Path(_env.get("DataDir", "Data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_HOSTS_FILE   = Path(r"C:\Windows\System32\drivers\etc\hosts")
_HOSTS_BACKUP = DATA_DIR / "hosts_backup.txt"
_REDIRECT_IP  = "127.0.0.1"
_MARKER_START = "# === JARVIS FOCUS MODE START ==="
_MARKER_END   = "# === JARVIS FOCUS MODE END ==="

# Default blocked sites — add/remove as needed
_DEFAULT_BLOCKED = [
    # Social media
    "www.instagram.com",    "instagram.com",
    "www.facebook.com",     "facebook.com",
    "www.twitter.com",      "twitter.com",
    "www.tiktok.com",       "tiktok.com",
    "www.reddit.com",       "reddit.com",
    "www.pinterest.com",    "pinterest.com",
    "www.snapchat.com",     "snapchat.com",
    "www.linkedin.com",     # optional — remove if you need linkedin for study

    # Video (optional — comment out if you need YouTube for study)
    # "www.youtube.com",    "youtube.com",

    # Gaming
    "www.miniclip.com",
    "www.y8.com",
]


def _is_admin() -> bool:
    """Check if running as administrator."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def FocusMode(command: str) -> bool:
    """
    Enable or disable focus mode.

    Commands: enable / on / start / disable / off / stop / status
    Voice: "enable focus mode", "disable focus mode", "focus on"
    """
    cmd = command.lower().strip()

    # ── Enable ────────────────────────────────────────────────────────────────
    if cmd in ("enable", "on", "start", "study mode", "focus on",
               "enable study mode", "enable focus"):
        if not _is_admin():
            print("[red]❌ Admin rights required to enable focus mode.[/red]")
            print("[yellow]→ Right-click VSCode → 'Run as administrator'[/yellow]")
            notify("Jarvis — Focus Mode ❌", "Need admin rights. Restart VSCode as Admin.")
            return False

        try:
            # Backup original
            if not _HOSTS_BACKUP.exists():
                _HOSTS_BACKUP.write_bytes(_HOSTS_FILE.read_bytes())
                print("[cyan]Hosts file backed up.[/cyan]")

            content = _HOSTS_FILE.read_text(encoding="utf-8", errors="ignore")
            if _MARKER_START in content:
                print("[yellow]Focus mode is already enabled.[/yellow]")
                notify("Jarvis", "Focus mode is already active.")
                return True

            # Build block entries
            block_lines = [f"\n{_MARKER_START}"]
            for site in _DEFAULT_BLOCKED:
                block_lines.append(f"{_REDIRECT_IP}  {site}")
            block_lines.append(f"{_MARKER_END}\n")

            with _HOSTS_FILE.open("a", encoding="utf-8") as f:
                f.write("\n".join(block_lines))

            os.system("ipconfig /flushdns >nul 2>&1")
            print("[bold green]✅ Focus mode ENABLED![/bold green]")
            print(f"[green]   {len(_DEFAULT_BLOCKED)} distracting sites blocked.[/green]")
            notify(
                "Jarvis — Focus Mode ✅",
                f"{len(_DEFAULT_BLOCKED)} sites blocked. Stay focused! 💪"
            )
            return True

        except PermissionError:
            print("[red]Permission denied. Run as Administrator.[/red]")
            return False
        except Exception as e:
            print(f"[red]FocusMode enable failed:[/red] {e}")
            return False

    # ── Disable ───────────────────────────────────────────────────────────────
    elif cmd in ("disable", "off", "stop", "focus off", "disable focus",
                 "disable study mode", "unblock all"):
        if not _is_admin():
            print("[red]❌ Admin rights required to disable focus mode.[/red]")
            print("[yellow]→ Right-click VSCode → 'Run as administrator'[/yellow]")
            return False

        try:
            content = _HOSTS_FILE.read_text(encoding="utf-8", errors="ignore")
            if _MARKER_START not in content:
                print("[yellow]Focus mode is not active.[/yellow]")
                return True

            # Remove everything between markers
            lines   = content.split("\n")
            cleaned = []
            skip    = False
            for line in lines:
                if _MARKER_START in line:
                    skip = True
                    continue
                if _MARKER_END in line:
                    skip = False
                    continue
                if not skip:
                    cleaned.append(line)

            _HOSTS_FILE.write_text("\n".join(cleaned), encoding="utf-8")
            os.system("ipconfig /flushdns >nul 2>&1")
            print("[bold green]✅ Focus mode DISABLED![/bold green]")
            print("[green]   All sites unblocked.[/green]")
            notify("Jarvis — Focus Mode Off", "All websites are now accessible.")
            return True

        except PermissionError:
            print("[red]Permission denied. Run as Administrator.[/red]")
            return False
        except Exception as e:
            print(f"[red]FocusMode disable failed:[/red] {e}")
            return False

    # ── Status ────────────────────────────────────────────────────────────────
    elif cmd in ("status", "check", "is focus on"):
        try:
            content = _HOSTS_FILE.read_text(encoding="utf-8", errors="ignore")
            active  = _MARKER_START in content
            status  = "ENABLED ✅" if active else "DISABLED ❌"
            print(f"[cyan]Focus mode: {status}[/cyan]")
            notify("Jarvis — Focus Mode", f"Status: {status}")
            return True
        except Exception as e:
            print(f"[red]Status check failed:[/red] {e}")
            return False

    print(f"[yellow]FocusMode: unknown command '{command}'[/yellow]")
    print("[yellow]Try: enable, disable, status[/yellow]")
    return False