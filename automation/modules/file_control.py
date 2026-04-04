# Backend/Automation/file_control.py
# Jarvis AI — Tier 4 File & System Automation
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations
import os, sys, shutil, zipfile, subprocess, datetime, glob
from pathlib import Path
from dotenv  import dotenv_values

_env     = dotenv_values(".env")
USERNAME = _env.get("Username", "User")

try:
    from .notifier import notify
except ImportError:
    def notify(t, m): print(f"[{t}] {m}")

# Common folder shortcuts
_FOLDERS = {
    "downloads"  : str(Path.home() / "Downloads"),
    "desktop"    : str(Path.home() / "Desktop"),
    "documents"  : str(Path.home() / "Documents"),
    "pictures"   : str(Path.home() / "Pictures"),
    "music"      : str(Path.home() / "Music"),
    "videos"     : str(Path.home() / "Videos"),
    "temp"       : str(Path.home() / "AppData" / "Local" / "Temp"),
    "project"    : str(Path.cwd()),
    "data"       : str(Path.cwd() / "Data"),
    "jarvis"     : str(Path.cwd()),
}

_EXT_MAP = {
    "pdf": "*.pdf", "doc": "*.doc*", "image": "*.jpg *.png *.jpeg *.gif",
    "mp3": "*.mp3", "mp4": "*.mp4 *.avi *.mkv", "zip": "*.zip *.rar",
    "py" : "*.py",  "txt": "*.txt", "excel": "*.xlsx *.xls",
    "word":"*.docx *.doc",
}


def OpenFolder(folder_name: str) -> bool:
    """Open a folder in Windows Explorer."""
    name = folder_name.lower().strip()
    path = _FOLDERS.get(name, name)
    if not Path(path).exists():
        # Try user home subfolders
        home_path = Path.home() / folder_name
        if home_path.exists():
            path = str(home_path)
        else:
            print(f"  Folder not found: {folder_name}")
            return False
    os.startfile(path)
    notify("Jarvis — Folder", f"Opened: {path}")
    return True


def FindFiles(file_type: str, location: str = "Desktop") -> str:
    """Find all files of a type in a location."""
    loc  = _FOLDERS.get(location.lower().strip(), location)
    exts = _EXT_MAP.get(file_type.lower(), f"*.{file_type.lower()}")

    found = []
    for ext in exts.split():
        found.extend(glob.glob(os.path.join(loc, "**", ext), recursive=True))

    if not found:
        return f"No {file_type} files found in {location}."

    lines = [f"Found {len(found)} {file_type} file(s) in {location}:"]
    for f in found[:10]:
        size = Path(f).stat().st_size // 1024
        lines.append(f"  • {Path(f).name} ({size} KB)")
    if len(found) > 10:
        lines.append(f"  ... and {len(found)-10} more")
    return "\n".join(lines)


def ZipFolder(folder_path: str) -> bool:
    """Zip a folder."""
    path = Path(_FOLDERS.get(folder_path.lower(), folder_path))
    if not path.exists():
        path = Path.cwd() / folder_path
    if not path.exists():
        print(f"  Folder not found: {folder_path}")
        return False

    zip_path = path.parent / f"{path.name}_{datetime.datetime.now():%Y%m%d_%H%M}.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in path.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(path.parent))
        size = zip_path.stat().st_size // (1024*1024)
        print(f"  Zipped: {zip_path.name} ({size} MB)")
        notify("Jarvis — Zip", f"Created: {zip_path.name}")
        return True
    except Exception as e:
        print(f"  Zip failed: {e}")
        return False


def BackupFolder(folder_path: str) -> bool:
    """Backup a folder to Desktop/Backups."""
    src = Path(_FOLDERS.get(folder_path.lower(), folder_path))
    if not src.exists():
        src = Path.cwd() / folder_path
    if not src.exists():
        print(f"  Source not found: {folder_path}")
        return False

    backup_dir = Path.home() / "Desktop" / "Jarvis_Backups"
    backup_dir.mkdir(exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    dest = backup_dir / f"{src.name}_{ts}"

    try:
        shutil.copytree(str(src), str(dest))
        print(f"  Backed up to: {dest}")
        notify("Jarvis — Backup", f"Backup complete: {dest.name}")
        return True
    except Exception as e:
        print(f"  Backup failed: {e}")
        return False


def CreateFile(filename: str, file_type: str = "text") -> bool:
    """Create a new file and open it."""
    desktop = Path.home() / "Desktop"
    # Add extension if missing
    if "." not in filename:
        ext_map = {
            "python": ".py", "py": ".py",
            "html"  : ".html", "css": ".css",
            "js"    : ".js", "java": ".java",
            "text"  : ".txt", "txt": ".txt",
            "word"  : ".docx",
        }
        ext      = ext_map.get(file_type.lower(), ".txt")
        filename = filename + ext

    path = desktop / filename
    try:
        path.write_text("", encoding="utf-8")
        os.startfile(str(path))
        print(f"  Created: {path}")
        notify("Jarvis — File", f"Created: {filename}")
        return True
    except Exception as e:
        print(f"  Create failed: {e}")
        return False


def EmptyRecycleBin() -> bool:
    """Empty Windows recycle bin."""
    try:
        import winshell
        winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
        print("  Recycle bin emptied.")
        notify("Jarvis", "Recycle bin emptied")
        return True
    except ImportError:
        # Fallback via shell command
        try:
            subprocess.run(
                ["powershell", "-Command", "Clear-RecycleBin -Force"],
                capture_output=True, timeout=15
            )
            print("  Recycle bin emptied.")
            return True
        except Exception as e:
            print(f"  Could not empty bin: {e}")
            return False


def handle_file_command(command: str) -> bool:
    """Route file commands from AutomationEngine."""
    cmd = command.strip()
    lc  = cmd.lower()

    if lc.startswith("file open "):
        folder = cmd[10:].strip()
        return OpenFolder(folder)

    if lc.startswith("file find "):
        parts = cmd[10:].strip().split()
        ftype = parts[0] if parts else "pdf"
        loc   = " ".join(parts[1:]) if len(parts) > 1 else "Desktop"
        result = FindFiles(ftype, loc)
        print(result)
        return True

    if lc.startswith("file zip "):
        folder = cmd[9:].strip()
        return ZipFolder(folder)

    if lc.startswith("file backup "):
        folder = cmd[12:].strip()
        return BackupFolder(folder)

    if lc.startswith("file create "):
        parts  = cmd[12:].strip().split()
        fname  = parts[0] if parts else "newfile.txt"
        ftype  = parts[1] if len(parts) > 1 else "text"
        return CreateFile(fname, ftype)

    return False


if __name__ == "__main__":
    script = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.join(script, "..", ".."))

    print("\n=== FILE CONTROL TEST ===\n")
    print("  [1] Open downloads folder")
    print("  [2] Find PDFs on Desktop")
    print("  [3] Create test.py on Desktop")
    print("  [0] Exit")
    while True:
        c = input("\n  Choice: ").strip()
        if c == "1": OpenFolder("downloads")
        elif c == "2": print(FindFiles("pdf", "Desktop"))
        elif c == "3": CreateFile("test", "python")
        elif c == "0": break