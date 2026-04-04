# Backend/Automation/app_monitor.py
# Jarvis AI — App Usage Monitor
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Real-time RAM/CPU usage per app
#   ✅ Track which apps used today
#   ✅ Productivity apps vs distracting apps detection
#   ✅ System health report (RAM, CPU, disk)
#   ✅ Kill any process by name
#   ✅ 8GB RAM safe — psutil is very lightweight
#
# VOICE COMMANDS:
#   "show app usage"
#   "app usage report"
#   "system health"
#   "how much ram is free"
#   "what apps are running"
#   "kill chrome"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from .notifier import notify

_env     = dotenv_values(".env")
DATA_DIR = Path(_env.get("DataDir", "Data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Apps classified as productive vs distracting
_PRODUCTIVE = {
    "code", "vscode", "pycharm", "idea", "eclipse", "notepad", "notepad++",
    "word", "excel", "powerpoint", "python", "node", "chrome", "firefox",
    "postman", "git", "terminal", "cmd", "powershell", "teams", "zoom",
}
_DISTRACTING = {
    "youtube", "instagram", "facebook", "tiktok", "netflix", "spotify",
    "steam", "games", "discord", "whatsapp",
}


def AppUsageReport() -> bool:
    """
    Show top 15 apps by RAM usage + system health.
    Voice: "show app usage", "app usage report"
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        print("[red]psutil not installed.[/red] Run: pip install psutil")
        return False

    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "status"]):
            try:
                if p.info["status"] == psutil.STATUS_ZOMBIE:
                    continue
                mem_mb = p.info["memory_info"].rss / (1024 * 1024)
                if mem_mb < 1:
                    continue
                procs.append({
                    "name":    p.info["name"] or "Unknown",
                    "pid":     p.info["pid"],
                    "mem_mb":  mem_mb,
                    "cpu":     p.info["cpu_percent"] or 0,
                })
            except Exception:
                continue

        # Sort by RAM usage
        procs.sort(key=lambda x: x["mem_mb"], reverse=True)
        top15 = procs[:15]

        # System stats
        ram    = psutil.virtual_memory()
        cpu    = psutil.cpu_percent(interval=1)
        disk   = psutil.disk_usage("C:\\")

        print(f"\n[bold cyan]📊 App Usage Report — {datetime.datetime.now().strftime('%I:%M %p')}[/bold cyan]")
        print(f"{'App':<28} {'RAM (MB)':>10} {'CPU%':>7}")
        print("─" * 48)

        productive_count   = 0
        distracting_count  = 0

        for p in top15:
            name_low = p["name"].lower().replace(".exe", "")
            tag = ""
            if any(k in name_low for k in _PRODUCTIVE):
                tag = " ✅"
                productive_count += 1
            elif any(k in name_low for k in _DISTRACTING):
                tag = " ⚠️"
                distracting_count += 1

            print(
                f"  {(p['name'][:25] + tag):<30} "
                f"{p['mem_mb']:>8.1f}  "
                f"{p['cpu']:>6.1f}%"
            )

        print("─" * 48)
        print(f"\n[bold]System Health:[/bold]")
        print(f"  🖥  RAM:  {ram.used / (1024**3):.1f} GB used / {ram.total / (1024**3):.1f} GB total ({ram.percent}%)")
        print(f"  ⚡ CPU:  {cpu}%")
        print(f"  💾 Disk: {disk.used / (1024**3):.1f} GB used / {disk.total / (1024**3):.1f} GB ({disk.percent}%)")
        print(f"  ✅ Productive apps: {productive_count}")
        print(f"  ⚠️  Distracting apps: {distracting_count}")
        print()

        # Warn if RAM > 80%
        if ram.percent > 80:
            notify(
                "⚠ Jarvis — High RAM Usage",
                f"RAM at {ram.percent}% — consider closing some apps!"
            )

        notify(
            "Jarvis — App Report 📊",
            f"RAM: {ram.percent}% | CPU: {cpu}% | Top: {top15[0]['name'] if top15 else 'N/A'}"
        )
        return True

    except Exception as e:
        print(f"[red]AppUsageReport failed:[/red] {e}")
        return False


def SystemHealth() -> bool:
    """
    Quick system health check.
    Voice: "system health", "how much ram is free", "check cpu usage"
    """
    try:
        import psutil  # type: ignore
        ram  = psutil.virtual_memory()
        cpu  = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage("C:\\")
        batt = psutil.sensors_battery()

        free_gb  = (ram.total - ram.used) / (1024**3)
        status   = []

        if ram.percent > 85:
            status.append(f"⚠ HIGH RAM: {ram.percent}%")
        if cpu > 80:
            status.append(f"⚠ HIGH CPU: {cpu}%")
        if disk.percent > 90:
            status.append(f"⚠ LOW DISK: {disk.percent}% used")

        print(f"\n[bold cyan]🖥 System Health[/bold cyan]")
        print(f"  RAM  : {ram.used/(1024**3):.1f}/{ram.total/(1024**3):.1f} GB ({ram.percent}%)")
        print(f"  Free : {free_gb:.1f} GB")
        print(f"  CPU  : {cpu}%")
        print(f"  Disk : {disk.percent}% used")
        if batt:
            print(f"  Batt : {int(batt.percent)}% {'🔌 Charging' if batt.power_plugged else '🔋 On battery'}")
        print()

        msg = f"RAM:{ram.percent}% CPU:{cpu}% Disk:{disk.percent}%"
        if status:
            msg = " | ".join(status)
            notify("⚠ Jarvis — System Warning", msg)
        else:
            notify("Jarvis — System Health ✅", msg)
        return True

    except ImportError:
        print("[red]psutil not installed.[/red] Run: pip install psutil")
        return False
    except Exception as e:
        print(f"[red]SystemHealth failed:[/red] {e}")
        return False


def KillProcess(name: str) -> bool:
    """
    Kill a process by name.
    Voice: "kill chrome", "close notepad process"
    """
    try:
        import psutil  # type: ignore
        killed = 0
        for p in psutil.process_iter(["name", "pid"]):
            try:
                if name.lower().replace(".exe", "") in p.info["name"].lower():
                    p.kill()
                    print(f"[green]Killed:[/green] {p.info['name']} (PID {p.info['pid']})")
                    killed += 1
            except Exception:
                continue

        if killed == 0:
            print(f"[yellow]No process found matching: {name}[/yellow]")
        else:
            notify("Jarvis", f"Killed {killed} process(es): {name}")
        return killed > 0

    except Exception as e:
        print(f"[red]KillProcess failed:[/red] {e}")
        return False