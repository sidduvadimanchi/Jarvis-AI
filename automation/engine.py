# Backend/AutomationEngine.py  v4.0
# Jarvis AI — Master Command Dispatcher
from __future__ import annotations
import asyncio, os, re, sys, threading
from typing import List

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path: sys.path.insert(0, _root)
os.chdir(_root)

def _imp(module, names, flags):
    try:
        mod = __import__(module, fromlist=names)
        for n in names: flags[n] = getattr(mod, n, lambda *a, **k: None)
        return True
    except ImportError as e:
        print(f"  [WARN] {module}: {e}")
        for n in names: flags[n] = lambda *a, **k: print(f"  [{n}] not available")
        return False

F = {}
_imp("automation.modules.app_control",       ["OpenApp","CloseApp"],                   F)
_imp("automation.modules.system_control",    ["System"],                               F)
_imp("automation.modules.media_control",     ["PlayYoutube","GoogleSearch","YouTubeSearch","MediaControl"], F)
_imp("automation.modules.email_system",      ["SendEmail"],                            F)
_imp("automation.modules.timetable",         ["ShowTimetable","AddTimetableEntry","DeleteTimetableEntry","ShowWeeklyTimetable"], F)
_imp("automation.modules.study_tracker",     ["StudyTracker"],                         F)
_imp("automation.modules.focus_mode",        ["FocusMode"],                            F)
_imp("automation.modules.assignment_creator",["CreateAssignment","CreateNotes"],       F)
_imp("automation.modules.content_writer",    ["Content","ExplainTopic","GenerateQuiz","SummarizeTopic"], F)
_imp("automation.modules.app_monitor",       ["AppUsageReport","SystemHealth","KillProcess"], F)
_imp("automation.modules.notifier",          ["Notify","Reminder"],                    F)
_imp("automation.modules.alarm_clock",       ["handle_alarm_command","StopAlarm"],     F)
_imp("automation.modules.realtime_data",     ["handle_realtime_command","GetWeather","GetNews","GetStock","GetCrypto","GetSports","TranslateText","GetJobs"], F)
_imp("automation.modules.file_control",      ["handle_file_command","OpenFolder","FindFiles","ZipFolder","BackupFolder","CreateFile"], F)
_imp("automation.modules.advanced_jobs",     ["handle_advanced_jobs","GetGovtJob","GetGATEPSU","GetGATESyllabus","GetMarketJobs","GetDeadlines","DailyJobBriefing","BookmarkJob","GetBookmarks"], F)

try:
    from automation.modules.whatsapp_system import SendWhatsApp
    F["SendWhatsApp"] = SendWhatsApp
except ImportError:
    F["SendWhatsApp"] = lambda x: print(f"  [WhatsApp] not available")

try:
    from interface.terminal import ShowTextToScreen
except ImportError:
    from pathlib import Path
    def ShowTextToScreen(t):
        try:
            with (Path("data")/"Files"/"Responses.data").open("a",encoding="utf-8") as f:
                f.write(t+"\n")
        except: pass


def _show(result: str):
    """Show result in GUI + print."""
    ShowTextToScreen(f"Jarvis : {result}")


async def TranslateAndExecute(commands: List[str]):
    tasks = []

    for command in commands:
        cmd = command.strip()
        if not cmd: continue
        lc  = cmd.lower()

        # ── STOP ALARM ────────────────────────────────────────────────────────
        if any(w in lc for w in ("stop alarm","stop timer","cancel alarm","silence alarm")):
            tasks.append(asyncio.to_thread(F["StopAlarm"]))

        # ── ALARM / TIMER ─────────────────────────────────────────────────────
        elif any(lc.startswith(p) for p in ("alarm","timer")):
            tasks.append(asyncio.to_thread(F["handle_alarm_command"], cmd))

        # ── WEATHER ───────────────────────────────────────────────────────────
        elif lc.startswith("weather"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))

        # ── NEWS ──────────────────────────────────────────────────────────────
        elif lc.startswith("news"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))

        # ── STOCK / CRYPTO ────────────────────────────────────────────────────
        elif lc.startswith("stock"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))
        elif lc.startswith("crypto"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))

        # ── SPORTS ────────────────────────────────────────────────────────────
        elif lc.startswith("sports"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))

        # ── TRANSLATE ─────────────────────────────────────────────────────────
        elif lc.startswith("translate"):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_realtime_command"](c))))

        # ── GATE PSU ──────────────────────────────────────────────────────────
        elif lc.startswith("gate"):
            if "syllabus" in lc:
                branch = "CSE"
                for b in ["EE","ME","CE","EC","CS","CSE"]:
                    if b.lower() in lc: branch = b; break
                tasks.append(asyncio.to_thread(lambda br=branch: _show(F["GetGATESyllabus"](br))))
            else:
                psu_m = None
                for psu in ["BHEL","ONGC","HPCL","NTPC","DRDO","BARC","BEL","HAL","GAIL","PGCIL","BSNL","SAIL"]:
                    if psu.lower() in lc: psu_m = psu; break
                tasks.append(asyncio.to_thread(lambda p=psu_m: _show(F["GetGATEPSU"](p or "all"))))

        # ── JOB DEADLINES ─────────────────────────────────────────────────────
        elif lc.startswith("deadlines") or "deadline" in lc:
            dm = re.search(r"(\d+)\s*day", lc)
            days = int(dm.group(1)) if dm else 10
            tasks.append(asyncio.to_thread(lambda d=days: _show(F["GetDeadlines"](d))))

        # ── DAILY BRIEFING ────────────────────────────────────────────────────
        elif "briefing" in lc:
            tasks.append(asyncio.to_thread(lambda: _show(F["DailyJobBriefing"]())))

        # ── BOOKMARK ──────────────────────────────────────────────────────────
        elif "bookmark" in lc or "save job" in lc:
            if "view" in lc or "show" in lc or "list" in lc:
                tasks.append(asyncio.to_thread(lambda: _show(F["GetBookmarks"]())))
            else:
                nm = re.search(r"(\d+)", lc)
                n  = int(nm.group(1)) if nm else 1
                tasks.append(asyncio.to_thread(lambda i=n: _show(F["BookmarkJob"](i))))

        # ── ALL JOBS (routes to advanced_jobs) ────────────────────────────────
        elif lc.startswith("jobs") or any(w in lc for w in (
            "upsc","ssc","railway","bank jobs","defence jobs","gate psu",
            "data analyst","software jobs","python jobs","ml jobs","fresher jobs"
        )):
            tasks.append(asyncio.to_thread(lambda c=cmd: _show(F["handle_advanced_jobs"](c))))

        # ── FILE OPERATIONS ───────────────────────────────────────────────────
        elif lc.startswith("file "):
            tasks.append(asyncio.to_thread(F["handle_file_command"], cmd))

        # ── RESEARCH ──────────────────────────────────────────────────────────
        elif lc.startswith("research "):
            topic = cmd[9:].strip()
            def _research(t=topic):
                result = F["handle_realtime_command"](f"news {t}")
                _show(f"Research on {t}:\n{result}")
                F["CreateNotes"](f"{t}\n\n{result}")
            tasks.append(asyncio.to_thread(_research))


        # ── ADVANCED JOBS (GATE PSU / Market / Saved) ────────────────────────
        elif lc.startswith("jobs gate_psu") or lc.startswith("jobs market") or              re.search(r"\b(gate|psu|bhel|ongc|ntpc|hpcl|iocl|drdo|barc|isro)\b", lc) or              re.search(r"\b(data analyst|python developer|ml engineer|"
                        r"machine learning|software engineer)\b", lc):
            tasks.append(asyncio.to_thread(
                lambda c=cmd: ShowTextToScreen(
                    f"Jarvis : {F['handle_advanced_jobs'](c)}")))

        elif "daily job briefing" in lc or "job alerts today" in lc:
            tasks.append(asyncio.to_thread(
                lambda: ShowTextToScreen(
                    f"Jarvis : {F['DailyJobBriefing']()}")))

        elif "saved jobs" in lc or "bookmark job" in lc:
            tasks.append(asyncio.to_thread(
                lambda: ShowTextToScreen(
                    f"Jarvis : {F['GetBookmarks']()}")))

        # ── OPEN / CLOSE ──────────────────────────────────────────────────────
        elif lc.startswith("open "):
            tasks.append(asyncio.to_thread(F["OpenApp"], cmd[5:].strip()))
        elif lc.startswith("close "):
            tasks.append(asyncio.to_thread(F["CloseApp"], cmd[6:].strip()))

        # ── PLAY / MEDIA ──────────────────────────────────────────────────────
        elif lc.startswith("play "):
            tasks.append(asyncio.to_thread(F["PlayYoutube"], cmd[5:].strip()))
        elif lc.startswith("google search "):
            tasks.append(asyncio.to_thread(F["GoogleSearch"], cmd[14:].strip()))
        elif lc.startswith("youtube search "):
            tasks.append(asyncio.to_thread(F["YouTubeSearch"], cmd[15:].strip()))
        elif lc in ("pause","resume","next song","previous song"):
            tasks.append(asyncio.to_thread(F["MediaControl"], lc))

        # ── SYSTEM ────────────────────────────────────────────────────────────
        elif lc.startswith("system "):
            t = cmd[7:].strip()
            if any(w in t for w in ("health","ram","cpu","disk")):
                tasks.append(asyncio.to_thread(F["SystemHealth"]))
            else:
                tasks.append(asyncio.to_thread(F["System"], t))
        elif lc in ("health","system health","check system"):
            tasks.append(asyncio.to_thread(F["SystemHealth"]))

        # ── EMAIL / WHATSAPP ──────────────────────────────────────────────────
        elif lc.startswith("email") or "send email" in lc:
            tasks.append(asyncio.to_thread(F["SendEmail"], cmd))
        elif lc.startswith("whatsapp"):
            tasks.append(asyncio.to_thread(F["SendWhatsApp"], cmd[9:].strip()))
        elif lc.startswith("read email"):
            tasks.append(asyncio.to_thread(F["SendEmail"], "read"))

        # ── REMINDER / NOTIFY ─────────────────────────────────────────────────
        elif lc.startswith("reminder "):
            tasks.append(asyncio.to_thread(F["Reminder"], cmd[9:].strip()))
        elif lc.startswith("notify"):
            tasks.append(asyncio.to_thread(F["Notify"], cmd[6:].strip() or "Reminder"))

        # ── STUDY / FOCUS ─────────────────────────────────────────────────────
        elif lc.startswith("study "):
            tasks.append(asyncio.to_thread(F["StudyTracker"], cmd[6:].strip()))
        elif lc.startswith("focus "):
            tasks.append(asyncio.to_thread(F["FocusMode"], cmd[6:].strip()))

        # ── ASSIGNMENT / NOTES / PBL / LAB ───────────────────────────────────
        elif lc.startswith("assignment "):
            tasks.append(asyncio.to_thread(F["CreateAssignment"], cmd[11:].strip()))
        elif lc.startswith("notes "):
            tasks.append(asyncio.to_thread(F["CreateNotes"], cmd[6:].strip()))
        elif lc.startswith("pbl "):
            tasks.append(asyncio.to_thread(F["CreateAssignment"], f"PBL {cmd[4:].strip()}"))
        elif lc.startswith("lab "):
            tasks.append(asyncio.to_thread(F["CreateAssignment"], f"Lab {cmd[4:].strip()}"))

        # ── TIMETABLE ─────────────────────────────────────────────────────────
        elif lc in ("timetable","timetable show","timetable today"):
            tasks.append(asyncio.to_thread(F["ShowTimetable"]))
        elif lc == "timetable weekly":
            tasks.append(asyncio.to_thread(F["ShowWeeklyTimetable"]))
        elif lc.startswith("timetable for "):
            tasks.append(asyncio.to_thread(F["ShowTimetable"], cmd[14:].strip()))
        elif lc.startswith("timetable add "):
            tasks.append(asyncio.to_thread(F["AddTimetableEntry"], cmd[14:].strip()))
        elif lc.startswith(("timetable delete ","timetable remove ")):
            tasks.append(asyncio.to_thread(F["DeleteTimetableEntry"], cmd[17:].strip()))

        # ── CONTENT / EXPLAIN / QUIZ / SUMMARIZE ──────────────────────────────
        elif lc.startswith("content "):
            tasks.append(asyncio.to_thread(F["Content"], cmd[8:].strip()))
        elif lc.startswith("explain "):
            tasks.append(asyncio.to_thread(F["ExplainTopic"], cmd[8:].strip()))
        elif lc.startswith("quiz "):
            tasks.append(asyncio.to_thread(F["GenerateQuiz"], cmd[5:].strip()))
        elif lc.startswith(("summarize ","summary ")):
            tasks.append(asyncio.to_thread(F["SummarizeTopic"], cmd.split(" ",1)[1].strip()))

        # ── APP MONITOR ───────────────────────────────────────────────────────
        elif lc in ("app usage","running apps","show apps"):
            tasks.append(asyncio.to_thread(F["AppUsageReport"]))
        elif lc.startswith("kill "):
            tasks.append(asyncio.to_thread(F["KillProcess"], cmd[5:].strip()))

        # ── REALTIME CATCH-ALL ────────────────────────────────────────────────
        elif lc.startswith("realtime "):
            q = cmd[9:].strip()
            tasks.append(asyncio.to_thread(lambda c=q: _show(F["handle_realtime_command"](c))))

        else:
            print(f"  [Engine] No handler: '{cmd}'")

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception): print(f"  [Engine Error] {r}")
            yield r


async def Automation(commands: List[str]) -> bool:
    async for _ in TranslateAndExecute(commands):
        pass
    return True


if __name__ == "__main__":
    print("\n" + "═"*58)
    print("  JARVIS AUTOMATION ENGINE v4.0")
    print("═"*58)
    while True:
        print("""
  [1]  Run any command
  [2]  All govt jobs
  [3]  GATE PSU alerts
  [4]  Data analyst jobs
  [5]  Job deadlines
  [6]  Daily briefing
  [7]  GATE CSE syllabus
  [0]  Exit""")
        c = input("\n  Choice: ").strip()
        if   c=="0": break
        elif c=="1":
            cmd = input("  Command: ").strip()
            if cmd: asyncio.run(Automation([cmd]))
        elif c=="2": asyncio.run(Automation(["jobs government"]))
        elif c=="3": asyncio.run(Automation(["gate psu"]))
        elif c=="4": asyncio.run(Automation(["jobs data analyst"]))
        elif c=="5": asyncio.run(Automation(["deadlines"]))
        elif c=="6": asyncio.run(Automation(["briefing"]))
        elif c=="7": asyncio.run(Automation(["gate syllabus CSE"]))