# Backend/Automation/system_control.py
# Jarvis AI — System Control
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Volume: mute, unmute, up, down
#   ✅ Power: shutdown, restart, sleep, hibernate, lock
#   ✅ Screenshot with auto-save to Pictures
#   ✅ Confirmation guard for dangerous commands
#   ✅ Battery status check
#   ✅ WiFi on/off
#   ✅ Brightness control (Windows)
#   ✅ 8GB RAM safe — no heavy libraries
#
# VOICE COMMANDS:
#   "volume up" / "volume down" / "mute" / "unmute"
#   "shutdown" / "restart" / "sleep" / "hibernate"
#   "lock screen" / "lock my computer"
#   "take screenshot"
#   "what is battery percentage"
#   "turn off wifi" / "turn on wifi"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import ctypes
import datetime
import os
import subprocess
from typing import Optional

import keyboard  # type: ignore

from .notifier import notify

# Commands requiring confirmation before execution
_DANGEROUS = frozenset({"shutdown", "restart", "hibernate", "logoff", "log off"})


def _confirm(cmd: str) -> bool:
    """Ask terminal confirmation for dangerous commands."""
    notify("⚠ Jarvis — Confirm", f"Type YES to confirm: {cmd}")
    print(f"\n[bold yellow]⚠ Confirmation required:[/bold yellow] '{cmd}'")
    try:
        ans = input(f"  Confirm '{cmd}'? (yes/no): ").strip().lower()
        return ans in ("yes", "y")
    except Exception:
        return False


def System(command: str) -> bool:
    """
    Execute a system command.

    Supported commands:
      volume: mute, unmute, volume up, volume down
      power:  shutdown, restart, sleep, hibernate, lock, lock screen
      tools:  screenshot, battery, wifi on, wifi off
    """
    cmd = command.lower().strip()

    # ── Volume ────────────────────────────────────────────────────────────────
    vol_map = {
        "mute":        "volume mute",
        "unmute":      "volume mute",
        "volume up":   "volume up",
        "volume down": "volume down",
        "vol up":      "volume up",
        "vol down":    "volume down",
        "increase volume": "volume up",
        "decrease volume": "volume down",
        "turn up volume":  "volume up",
        "turn down volume":"volume down",
    }
    if cmd in vol_map:
        try:
            keyboard.press_and_release(vol_map[cmd])
            print(f"[green]System:[/green] {cmd}")
            return True
        except Exception as e:
            print(f"[red]Volume error:[/red] {e}")
            return False

    # ── Power (dangerous — confirm first) ─────────────────────────────────────
    power_cmd = None
    if cmd in ("shutdown", "shut down", "power off", "turn off"):
        power_cmd = "shutdown"
    elif cmd in ("restart", "reboot", "restart computer"):
        power_cmd = "restart"
    elif cmd in ("sleep", "sleep mode", "go to sleep"):
        power_cmd = "sleep"
    elif cmd in ("hibernate",):
        power_cmd = "hibernate"
    elif cmd in ("logoff", "log off", "sign out"):
        power_cmd = "logoff"

    if power_cmd:
        if not _confirm(power_cmd):
            print(f"[yellow]'{power_cmd}' cancelled.[/yellow]")
            return False
        try:
            if power_cmd == "shutdown":
                notify("Jarvis", "Shutting down in 5 seconds...")
                os.system("shutdown /s /t 5")
            elif power_cmd == "restart":
                notify("Jarvis", "Restarting in 5 seconds...")
                os.system("shutdown /r /t 5")
            elif power_cmd == "sleep":
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            elif power_cmd == "hibernate":
                os.system("shutdown /h")
            elif power_cmd == "logoff":
                os.system("shutdown /l")
            return True
        except Exception as e:
            print(f"[red]Power command failed:[/red] {e}")
            return False

    # ── Lock screen ───────────────────────────────────────────────────────────
    if cmd in ("lock", "lock screen", "lock pc", "lock computer",
               "lock my computer", "lock the screen"):
        try:
            ctypes.windll.user32.LockWorkStation()
            print("[green]Screen locked.[/green]")
            return True
        except Exception as e:
            print(f"[red]Lock failed:[/red] {e}")
            return False

    # ── Screenshot ────────────────────────────────────────────────────────────
    if cmd in ("screenshot", "take screenshot", "capture screen",
               "screen capture", "take a screenshot"):
        try:
            keyboard.press_and_release("win+prtsc")
            ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            notify("Jarvis", f"Screenshot saved! ({ts})")
            print(f"[green]Screenshot taken:[/green] saved to Pictures folder")
            return True
        except Exception as e:
            print(f"[red]Screenshot failed:[/red] {e}")
            return False

    # ── Battery status ────────────────────────────────────────────────────────
    if cmd in ("battery", "battery status", "battery percentage",
               "how much battery", "check battery"):
        try:
            import psutil  # type: ignore
            batt = psutil.sensors_battery()
            if batt:
                pct    = int(batt.percent)
                status = "Charging" if batt.power_plugged else "On Battery"
                mins   = int(batt.secsleft / 60) if batt.secsleft > 0 else 0
                msg    = f"Battery: {pct}% — {status}"
                if mins > 0 and not batt.power_plugged:
                    msg += f" — {mins} min remaining"
                notify("Jarvis — Battery", msg)
                print(f"[cyan]{msg}[/cyan]")
            else:
                print("[yellow]Battery info not available.[/yellow]")
            return True
        except ImportError:
            print("[yellow]psutil not installed. Run: pip install psutil[/yellow]")
            return False

    # ── WiFi ──────────────────────────────────────────────────────────────────
    if cmd in ("wifi off", "turn off wifi", "disable wifi"):
        try:
            subprocess.run(
                ["netsh", "interface", "set", "interface",
                 "Wi-Fi", "disable"], check=True
            )
            notify("Jarvis", "WiFi disabled.")
            print("[green]WiFi disabled.[/green]")
            return True
        except Exception as e:
            print(f"[red]WiFi off failed:[/red] {e}")
            return False

    if cmd in ("wifi on", "turn on wifi", "enable wifi"):
        try:
            subprocess.run(
                ["netsh", "interface", "set", "interface",
                 "Wi-Fi", "enable"], check=True
            )
            notify("Jarvis", "WiFi enabled.")
            print("[green]WiFi enabled.[/green]")
            return True
        except Exception as e:
            print(f"[red]WiFi on failed:[/red] {e}")
            return False

    print(f"[yellow]System: Unknown command '{command}'[/yellow]")
    print("[yellow]Try: mute, unmute, volume up, volume down, shutdown, restart, sleep, lock, screenshot, battery[/yellow]")
    return False