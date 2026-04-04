# Backend/Automation/__init__.py
# Jarvis AI — Safe imports, isolates each module error

try:
    from .app_control import OpenApp, CloseApp
except Exception as e:
    print(f"[Automation] app_control error: {e}")
    def OpenApp(app, sess=None): pass
    def CloseApp(app): pass

try:
    from .system_control import System
except Exception as e:
    print(f"[Automation] system_control error: {e}")
    def System(cmd): pass

try:
    from .media_control import PlayYoutube, GoogleSearch, YouTubeSearch, MediaControl
except Exception as e:
    print(f"[Automation] media_control error: {e}")
    def PlayYoutube(q): pass
    def GoogleSearch(q): pass
    def YouTubeSearch(q): pass
    def MediaControl(q): pass

try:
    from .email_system import SendEmail
except Exception as e:
    print(f"[Automation] email_system error: {e}")
    def SendEmail(p): pass

try:
    from .whatsapp_system import SendWhatsApp
except Exception as e:
    print(f"[Automation] whatsapp_system error: {e}")
    def SendWhatsApp(p): pass

try:
    from .study_tracker import StudyTracker
except Exception as e:
    print(f"[Automation] study_tracker error: {e}")
    def StudyTracker(cmd): pass

try:
    from .focus_mode import FocusMode
except Exception as e:
    print(f"[Automation] focus_mode error: {e}")
    def FocusMode(cmd): pass

try:
    from .assignment_creator import CreateAssignment, CreateNotes
except Exception as e:
    print(f"[Automation] assignment_creator error: {e}")
    def CreateAssignment(t): pass
    def CreateNotes(t): pass

try:
    from .timetable import ShowTimetable, AddTimetableEntry, DeleteTimetableEntry, ShowWeeklyTimetable
except Exception as e:
    print(f"[Automation] timetable error: {e}")
    def ShowTimetable(d=""): pass
    def AddTimetableEntry(s): pass
    def DeleteTimetableEntry(s): pass
    def ShowWeeklyTimetable(): pass

try:
    from .content_writer import Content, ExplainTopic, GenerateQuiz, SummarizeTopic
except Exception as e:
    print(f"[Automation] content_writer error: {e}")
    def Content(t): pass
    def ExplainTopic(t): pass
    def GenerateQuiz(t): pass
    def SummarizeTopic(t): pass

try:
    from .app_monitor import AppUsageReport, SystemHealth, KillProcess
except Exception as e:
    print(f"[Automation] app_monitor error: {e}")
    def AppUsageReport(): pass
    def SystemHealth(): pass
    def KillProcess(n): pass

try:
    from .notifier import Notify, Reminder, notify
except Exception as e:
    print(f"[Automation] notifier error: {e}")
    def Notify(m): pass
    def Reminder(m): pass
    def notify(t, m): pass