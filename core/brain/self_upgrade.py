# Backend/Brain/self_upgrade.py
# Jarvis AI — Safe Self-Upgrade System
# Checks improvements on startup, asks permission, applies only what you approve
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import sys
import json
import datetime
import subprocess
import importlib
from pathlib import Path
from typing  import Optional

_LOG_FILE = Path("Data") / "upgrade_log.txt"

# ══════════════════════════════════════════════════════════
# UPGRADE REGISTRY
# Each entry: {id, title, description, type, action}
# type: 'package' | 'knowledge' | 'config' | 'tip'
# ══════════════════════════════════════════════════════════

_UPGRADES = [
    {
        "id"         : "pkg_matplotlib",
        "title"      : "Diagram support in assignments",
        "description": "Adds process flow diagrams to Word documents",
        "type"       : "package",
        "package"    : "matplotlib",
        "check_import": "matplotlib",
    },
    {
        "id"         : "pkg_rich",
        "title"      : "Prettier terminal output",
        "description": "Coloured, formatted terminal for Jarvis responses",
        "type"       : "package",
        "package"    : "rich",
        "check_import": "rich",
    },
    {
        "id"         : "pkg_docx2pdf",
        "title"      : "PDF export from assignments",
        "description": "Convert Word documents to PDF automatically",
        "type"       : "package",
        "package"    : "docx2pdf",
        "check_import": "docx2pdf",
    },
    {
        "id"         : "pkg_psutil",
        "title"      : "System health monitoring",
        "description": "CPU, RAM, battery, disk usage reports",
        "type"       : "package",
        "package"    : "psutil",
        "check_import": "psutil",
    },
    {
        "id"         : "pkg_plyer",
        "title"      : "Desktop notifications",
        "description": "Pop-up notifications for reminders and task completions",
        "type"       : "package",
        "package"    : "plyer",
        "check_import": "plyer",
    },
    {
        "id"         : "model_pbl",
        "title"      : "PBL/Lab format in Model.py",
        "description": "Adds 'pbl', 'lab', 'notes', 'timetable' to intent router",
        "type"       : "model_patch",
        "file"       : "Backend/Model.py",
    },
    {
        "id"         : "env_display_name",
        "title"      : "Email display name in .env",
        "description": "Add GmailDisplayName for professional email sender name",
        "type"       : "env_tip",
        "key"        : "GmailDisplayName",
        "suggestion" : "GmailDisplayName=Your Full Name",
    },
    {
        "id"         : "env_roll_number",
        "title"      : "Roll number on assignment cover pages",
        "description": "Add RollNumber and Semester to .env for cover pages",
        "type"       : "env_tip",
        "key"        : "RollNumber",
        "suggestion" : "RollNumber=21CS001\nSemester=5th Semester",
    },
]


def _is_package_installed(pkg: str) -> bool:
    try:
        importlib.import_module(pkg)
        return True
    except ImportError:
        return False


def _env_key_exists(key: str) -> bool:
    from dotenv import dotenv_values
    return bool(dotenv_values(".env").get(key))


def _check_upgrades() -> list[dict]:
    """
    Check which upgrades are actually needed (not already done).

    Returns
    -------
    list[dict] — upgrades that should be offered
    """
    needed = []

    for upg in _UPGRADES:
        utype = upg["type"]

        if utype == "package":
            if not _is_package_installed(upg["check_import"]):
                needed.append(upg)

        elif utype == "env_tip":
            if not _env_key_exists(upg["key"]):
                needed.append(upg)

        elif utype == "model_patch":
            # Check if Model.py has the new keywords
            fpath = Path(upg["file"])
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                if '"pbl"' not in content and "'pbl'" not in content:
                    needed.append(upg)

    return needed


def _install_package(pkg: str) -> bool:
    """Safely install a Python package."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ❌  Install failed: {e}")
        return False


def _log_upgrade(upg_id: str, success: bool, note: str = "") -> None:
    """Write upgrade action to log file."""
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("a", encoding="utf-8") as f:
        status = "SUCCESS" if success else "FAILED"
        f.write(
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{status} | {upg_id} | {note}\n"
        )


def _apply_upgrade(upg: dict) -> bool:
    """Apply a single upgrade. Returns True on success."""
    utype = upg["type"]

    if utype == "package":
        print(f"\n  📦  Installing {upg['package']}...")
        ok = _install_package(upg["package"])
        if ok:
            print(f"  ✅  {upg['package']} installed successfully")
        else:
            print(f"  ❌  Failed to install {upg['package']}")
        _log_upgrade(upg["id"], ok, upg["package"])
        return ok

    elif utype == "env_tip":
        print(f"\n  📝  Add to your .env file:\n")
        print(f"      {upg['suggestion']}\n")
        _log_upgrade(upg["id"], True, "tip shown")
        return True

    elif utype == "model_patch":
        # Add missing keywords to Model.py preamble
        fpath = Path(upg["file"])
        if not fpath.exists():
            return False
        content = fpath.read_text(encoding="utf-8")
        addition = (
            "\n-> Respond with 'notes (topic)' if asking to create notes on a topic.\n"
            "-> Respond with 'pbl (topic)' if asking to create a PBL or project report.\n"
            "-> Respond with 'lab (topic)' if asking to create a lab manual.\n"
            "-> Respond with 'timetable show' if asking to see the timetable.\n"
            "-> Respond with 'timetable add (details)' if asking to add to timetable.\n"
        )
        # Insert before the last "***" line
        old  = '*** If the user is saying goodbye'
        new  = addition + old
        content = content.replace(old, new, 1)
        fpath.write_text(content, encoding="utf-8")
        _log_upgrade(upg["id"], True, "Model.py patched")
        print(f"  ✅  Model.py updated with new intent keywords")
        return True

    return False


# ══════════════════════════════════════════════════════════
# MAIN STARTUP CHECK — called from Main.py
# ══════════════════════════════════════════════════════════

def run_startup_upgrade_check() -> None:
    """
    Run on every Jarvis startup.
    Checks what can be improved, shows list, asks permission.
    Runs in ~2 seconds if nothing to upgrade.
    """
    W  = 62
    LINE  = "─" * W
    DLINE = "═" * W

    print(f"\n  {DLINE}")
    print(f"  🧠  JARVIS BRAIN — Startup Check")
    print(f"  {DLINE}")

    needed = _check_upgrades()

    if not needed:
        print(f"  ✅  Everything is up to date. No upgrades needed.")
        print(f"  {DLINE}\n")
        return

    print(f"\n  Found {len(needed)} possible improvement(s):\n")
    for i, upg in enumerate(needed, 1):
        icon = "📦" if upg["type"] == "package" else ("📝" if upg["type"] == "env_tip" else "🔧")
        print(f"  [{i}] {icon}  {upg['title']}")
        print(f"       {upg['description']}\n")

    print(f"  {LINE}")
    print("  Options:")
    print("    yes     → apply all upgrades")
    print("    no      → skip all, continue normally")
    print("    1,2,3   → apply only selected numbers")
    print(f"  {LINE}\n")

    try:
        answer = input("  Your choice: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Skipping upgrades.\n")
        return

    if answer in ("no", "n", "skip", ""):
        print("\n  ⏭  Upgrades skipped. Starting Jarvis...\n")
        return

    # Determine which to apply
    to_apply: list[dict] = []
    if answer in ("yes", "y", "all"):
        to_apply = needed
    else:
        try:
            indices = [int(x.strip()) - 1 for x in answer.split(",")]
            to_apply = [needed[i] for i in indices if 0 <= i < len(needed)]
        except (ValueError, IndexError):
            print("  ❌  Invalid choice. Skipping upgrades.\n")
            return

    if not to_apply:
        print("  No valid selections. Skipping.\n")
        return

    print(f"\n  Applying {len(to_apply)} upgrade(s)...\n")
    success_count = 0
    for upg in to_apply:
        ok = _apply_upgrade(upg)
        if ok:
            success_count += 1

    print(f"\n  {DLINE}")
    print(f"  ✅  {success_count}/{len(to_apply)} upgrade(s) applied.")
    print(f"  📄  Log saved to: Data/upgrade_log.txt")
    print(f"  {DLINE}\n")