# Backend/Model.py  v4.0 — Complete Intent Router
# All original + advanced jobs/GATE/market/PSU intents added
import re
from dotenv import dotenv_values

env_vars     = dotenv_values(".env")
CohereAPIKey = env_vars.get("CohereAPIKey", "")

# Guarded cohere import — works even when cohere is not installed
co = None
try:
    import cohere as _cohere
    if CohereAPIKey:
        # Enforce strict 4-second timeout to fall back instantly if network is blocked
        co = _cohere.Client(api_key=CohereAPIKey, timeout=4.0)
except ImportError:
    pass  # cohere not installed — _fallback_dmm will be used
except Exception:
    co = None

funcs = [
    "exit","general","realtime","open","close","play","generate image","system",
    "content","google search","youtube search","reminder","email","whatsapp",
    "study","focus","assignment","app usage","notify","notes","pbl","lab",
    "timetable","explain","quiz","summarize","weather","alarm","timer",
    "news","jobs","stock","translate","sports","crypto","file","backup","zip",
    "find","calendar","read email","research","workflow","gate","psu","deadlines",
    "market jobs","briefing","bookmark",
]

messages = []

preamble = """
You are a very accurate Decision-Making Model for Jarvis AI.
ONLY classify the query — never answer it.

STANDARD INTENTS:
-> general/realtime/open/close/play/system/content/google search/youtube search
-> reminder/email/whatsapp/study/focus/assignment/notes/pbl/lab/timetable
-> explain/quiz/summarize/generate image/app usage/notify

JOB & CAREER INTENTS:
-> 'jobs upsc' — UPSC notifications with last dates
-> 'jobs ssc' — SSC notifications
-> 'jobs railway' — Railway RRB notifications
-> 'jobs bank' — Bank IBPS/SBI notifications
-> 'jobs defence' — Army/Navy/Air Force
-> 'jobs state' — State PSC
-> 'jobs mp' — Madhya Pradesh government jobs
-> 'jobs government' — all govt jobs
-> 'jobs today' — today's latest govt jobs
-> 'jobs data analyst' — data analyst market jobs
-> 'jobs software engineer' — software developer jobs
-> 'jobs python developer' — Python jobs
-> 'jobs machine learning' — ML/AI jobs
-> 'jobs fresher' — entry level IT jobs
-> 'jobs internship' — internships
-> 'jobs <any keyword>' — any private market job keyword

GATE & PSU INTENTS:
-> 'gate psu' — all PSU recruitment through GATE
-> 'gate psu BHEL' — specific PSU (BHEL/ONGC/DRDO/BARC/NTPC/HPCL...)
-> 'gate syllabus CSE' — GATE CSE syllabus + weightage
-> 'gate changes' — recent GATE format/syllabus changes
-> 'deadlines' — upcoming job application deadlines
-> 'briefing' — complete daily job briefing

LIVE DATA INTENTS:
-> 'weather <city>' — live weather
-> 'news <category>' — latest news
-> 'stock <symbol>' — NSE/BSE stock price
-> 'crypto <symbol>' — cryptocurrency price
-> 'sports <query>' — sports scores
-> 'translate <text> to <lang>' — translation

FILE INTENTS:
-> 'file open <folder>' / 'file find <type>' / 'file zip' / 'file backup'
-> 'alarm <time>' / 'timer <duration>'
-> 'research <topic>' / 'workflow <description>'

EXAMPLES:
"UPSC jobs today" → 'jobs upsc'
"SSC CGL notification" → 'jobs ssc'
"data analyst jobs" → 'jobs data analyst'
"Python developer hiring" → 'jobs python developer'
"PSU recruitment through GATE" → 'gate psu'
"BHEL recruitment 2025" → 'gate psu BHEL'
"GATE CSE syllabus" → 'gate syllabus CSE'
"job deadlines this week" → 'deadlines'
"daily job briefing" → 'briefing'
"weather Bhopal" → 'weather Bhopal'
*** Multiple: 'open chrome and show upsc jobs' → 'open chrome, jobs upsc' ***
*** Goodbye → 'exit' ***
*** Unknown → 'general (query)' ***
"""

ChatHistory = [
    {"role":"User","message":"how are you?"},
    {"role":"Chatbot","message":"general how are you?"},
    {"role":"User","message":"open chrome"},
    {"role":"Chatbot","message":"open chrome"},
    {"role":"User","message":"UPSC jobs today"},
    {"role":"Chatbot","message":"jobs upsc"},
    {"role":"User","message":"SSC CGL notification 2025"},
    {"role":"Chatbot","message":"jobs ssc"},
    {"role":"User","message":"data analyst jobs"},
    {"role":"Chatbot","message":"jobs data analyst"},
    {"role":"User","message":"Python developer hiring"},
    {"role":"Chatbot","message":"jobs python developer"},
    {"role":"User","message":"ML engineer jobs India"},
    {"role":"Chatbot","message":"jobs machine learning"},
    {"role":"User","message":"PSU recruitment through GATE"},
    {"role":"Chatbot","message":"gate psu"},
    {"role":"User","message":"BHEL recruitment 2025"},
    {"role":"Chatbot","message":"gate psu BHEL"},
    {"role":"User","message":"DRDO CEPTAM notification"},
    {"role":"Chatbot","message":"gate psu DRDO"},
    {"role":"User","message":"BARC recruitment"},
    {"role":"Chatbot","message":"gate psu BARC"},
    {"role":"User","message":"GATE CSE syllabus changes"},
    {"role":"Chatbot","message":"gate syllabus CSE"},
    {"role":"User","message":"upcoming job deadlines"},
    {"role":"Chatbot","message":"deadlines"},
    {"role":"User","message":"give me daily job briefing"},
    {"role":"Chatbot","message":"briefing"},
    {"role":"User","message":"weather in Bhopal"},
    {"role":"Chatbot","message":"weather Bhopal"},
    {"role":"User","message":"TCS stock price"},
    {"role":"Chatbot","message":"stock TCS"},
    {"role":"User","message":"Bitcoin price"},
    {"role":"Chatbot","message":"crypto BTC"},
    {"role":"User","message":"bye jarvis"},
    {"role":"Chatbot","message":"exit"},
]


def FirstLayerDMM(prompt:str="test") -> list[str]:
    if not co: return _fallback_dmm(prompt)
    messages.append({"role":"user","content":prompt})
    try:
        stream   = co.chat_stream(model="command-r-08-2024",message=prompt,
                                  temperature=0.7,chat_history=ChatHistory,
                                  prompt_truncation="OFF",connectors=[],preamble=preamble)
        response = ""
        for ev in stream:
            if ev.event_type=="text-generation": response += ev.text
        response = response.replace("\n","")
        parts    = [i.strip() for i in response.split(",")]
        result   = [t for t in parts if any(t.startswith(f) for f in funcs)]
        return result if result else _fallback_dmm(prompt)
    except Exception as e:
        print(f"[Model] Cohere error: {e}")
        return _fallback_dmm(prompt)


def _fallback_dmm(prompt:str) -> list[str]:
    low = prompt.lower().strip()

    if re.search(r"\b(bye|goodbye|exit|quit|close jarvis)\b",low): return ["exit"]

    # System
    sys_map = {
        r"\b(shutdown|shut down|power off)\b":"system shutdown",
        r"\b(restart|reboot)\b":"system restart",
        r"\b(screenshot|screen shot)\b":"system screenshot",
        r"\b(mute|silence)\b":"system mute",
        r"\b(unmute|sound on)\b":"system unmute",
        r"\bvolume up\b":"system volume up",
        r"\bvolume down\b":"system volume down",
        r"\block (screen|computer|laptop)\b":"system lock",
        r"\b(battery|battery status)\b":"system battery",
        r"\bcpu (usage|load)\b|\bram usage\b":"system health",
    }
    for pat,cmd in sys_map.items():
        if re.search(pat,low): return [cmd]

    # Alarm / Timer
    am = re.search(r"(?:set\s+)?(?:alarm|wake\s+me)(?:\s+(?:at|for))?\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",low)
    if am: return [f"alarm {am.group(1).strip()}"]
    tm = re.search(r"(?:set\s+)?(?:timer|countdown)\s+(\d+\s*(?:hour|hr|minute|min|second|sec)s?)",low)
    if tm: return [f"timer {tm.group(1).strip()}"]

    # Weather
    if "weather" in low:
        wm = re.search(r"weather(?:\s+(?:in|for|at))?\s*([a-zA-Z\s]+)?",low)
        city = wm.group(1).strip() if wm and wm.group(1) else "Bhopal"
        return [f"weather {city.strip() or 'Bhopal'}"]

    # GATE PSU
    if "gate" in low or "psu" in low:
        if any(w in low for w in ("syllabus","topic","subject","change","format")):
            return ["gate syllabus CSE"]
        for psu in ["bhel","ongc","hpcl","iocl","ntpc","pgcil","bsnl","drdo","hal","bel","barc","gail","sail"]:
            if psu in low: return [f"gate psu {psu.upper()}"]
        return ["gate psu"]

    # Deadlines / Briefing / Bookmark
    if any(w in low for w in ("deadline","upcoming deadline","last date")): return ["deadlines"]
    if any(w in low for w in ("briefing","daily briefing","job summary")): return ["briefing"]
    if "bookmark" in low or "save job" in low: return ["bookmark"]
    if "saved job" in low or "my jobs" in low: return ["bookmark view"]

    # Jobs — specific categories
    job_map = [
        (r"\b(upsc|ias|ips|nda|cds|capf)\b","jobs upsc"),
        (r"\b(ssc|cgl|chsl|mts|gd constable)\b","jobs ssc"),
        (r"\b(railway|rrb|ntpc|group.d|alp)\b","jobs railway"),
        (r"\b(bank|ibps|sbi|rbi|po|clerk)\b","jobs bank"),
        (r"\b(army|navy|airforce|defence|afcat|nda)\b","jobs defence"),
        (r"\b(psc|bpsc|mpsc|uppsc|tnpsc|kpsc)\b","jobs psc"),
        (r"\b(mppsc|mp police|mp patwari)\b","jobs mp"),
        (r"\b(data analyst|data analysis)\b","jobs data analyst"),
        (r"\b(data scien|ml engineer|machine learning)\b","jobs machine learning"),
        (r"\b(python developer|python job)\b","jobs python developer"),
        (r"\b(software engineer|developer|programmer)\b","jobs software engineer"),
        (r"\b(web developer|frontend|backend|fullstack)\b","jobs web developer"),
        (r"\b(cloud|aws|azure|devops)\b","jobs cloud"),
        (r"\b(cyber|security|ethical hack)\b","jobs cyber security"),
        (r"\b(fresher|entry.level|campus)\b","jobs fresher"),
        (r"\b(intern|internship)\b","jobs internship"),
        (r"\b(remote|work.from.home)\b","jobs remote"),
    ]
    for pat,intent in job_map:
        if re.search(pat,low): return [intent]

    # Generic job/vacancy/recruitment
    if re.search(r"\b(job|vacancy|vacancies|recruitment|hiring|placement|naukri)\b",low):
        # Extract keyword
        kw = re.sub(r".*(find|search|show|get|latest)\s+","",low)
        kw = re.sub(r"\s*(job|jobs|vacancy|recruitment|hiring|notification).*","",kw).strip()
        if kw and len(kw) > 2: return [f"jobs {kw}"]
        return ["jobs government"]

    # Open/Close
    opens  = re.findall(r"(?:open|launch|start)\s+([^,]+?)(?:\s+and\s+|$)",low)
    closes = re.findall(r"(?:close|quit|kill)\s+([^,]+?)(?:\s+and\s+|$)",low)
    result = []
    for o in opens:  result.append(f"open {o.strip()}")
    for c in closes: result.append(f"close {c.strip()}")
    if result: return result

    # Play
    pm = re.search(r"(?:play|stream)\s+(.+)",low)
    if pm: return [f"play {pm.group(1).strip()}"]

    # News
    if re.search(r"\b(news|headlines|current events)\b",low):
        cats = {"tech":"technology","sport":"sports","business":"business",
                "health":"health","science":"science","entertain":"entertainment"}
        cat  = next((v for k,v in cats.items() if k in low),"general")
        return [f"news {cat}"]

    # Stock / Crypto
    sm = re.search(r"(?:stock|share|price)\s+(?:of\s+)?([A-Za-z]+)",low)
    if sm or re.search(r"\b(tcs|infosys|reliance|wipro|hdfc|icici|sbi)\b",low):
        sym_m = re.search(r"\b(TCS|INFY|RELIANCE|WIPRO|HDFC|ICICI|SBI|ONGC|tcs|infosys|reliance|wipro|hdfc|icici|sbi|ongc)\b",prompt)
        sym   = sym_m.group(1).upper() if sym_m else (sm.group(1).upper() if sm else "TCS")
        return [f"stock {sym}"]
    if re.search(r"\b(bitcoin|ethereum|btc|eth|dogecoin|doge|crypto|bnb)\b",low):
        cmap = {"bitcoin":"BTC","ethereum":"ETH","dogecoin":"DOGE","bnb":"BNB","btc":"BTC","eth":"ETH"}
        sym  = next((v for k,v in cmap.items() if k in low),"BTC")
        return [f"crypto {sym}"]

    # Sports
    if re.search(r"\b(ipl|cricket|football|f1|nba|score|match)\b",low):
        return [f"sports {low}"]

    # Translate
    tm2 = re.search(r"translate\s+(.+?)\s+(?:to|into)\s+([a-zA-Z]+)",low)
    if tm2: return [f"translate {tm2.group(1)} to {tm2.group(2)}"]

    # File
    if re.search(r"\b(zip|compress)\b",low):
        target = re.sub(r".*(zip|compress)\s+", "", low).strip()
        return [f"file zip {target}"]
    if re.search(r"\b(backup|back up)\b",low):
        target = re.sub(r".*(backup|back up)\s+", "", low).strip()
        return [f"file backup {target}"]
    if re.search(r"\bfind\s+.*(pdf|doc|txt|mp3|mp4|jpg|png)\b",low):
        target = re.sub(r"^.*find\s+", "", low).strip()
        return [f"file find {target}"]
    if re.search(r"\bopen\s+.*(folder|directory)\b",low):
        fm = re.search(r"open\s+(?:the\s+)?(?:my\s+)?(.+?)\s+folder",low)
        return [f"file open {fm.group(1) if fm else 'documents'}"]

    # Email / WhatsApp
    if re.search(r"\bread\s+(my\s+)?email|check\s+(my\s+)?inbox\b",low): return ["read email"]
    em = re.search(r"(?:send\s+)?email\s+(?:to\s+)?(\w+)\s+(?:about\s+)?(.+)",low)
    if em: return [f"email to {em.group(1)} about {em.group(2)}"]
    wm2 = re.search(r"whatsapp\s+(?:to\s+)?(\w+)\s+(?:saying|message|about)?\s*(.+)",low)
    if wm2: return [f"whatsapp to {wm2.group(1)} message {wm2.group(2)}"]

    # Study
    if re.search(r"start\s+stud",low):
        sub = re.search(r"study(?:ing)?\s+(.+)",low)
        return [f"study start {sub.group(1)}" if sub else "study start"]
    if re.search(r"stop\s+stud",low): return ["study stop"]
    if re.search(r"study\s+report",low): return ["study report"]
    if re.search(r"focus\s+(on|enable)",low): return ["focus enable"]
    if re.search(r"focus\s+(off|disable)",low): return ["focus disable"]

    # Assignment / Notes
    if re.search(r"\b(assignment|homework)\b",low):
        t = re.sub(r".*(assignment|homework)\s+(on\s+)?","",low).strip()
        return [f"assignment {t}" if t else "assignment"]
    if re.search(r"\bnotes?\b",low):
        t = re.sub(r".*notes?\s+(on\s+)?","",low).strip()
        return [f"notes {t}" if t else "notes"]

    # Timetable
    if "timetable" in low:
        if re.search(r"\b(add|set)\b",low):
            target = re.sub(r".*timetable\s+(add\s+)?", "", low).strip()
            return [f"timetable add {target}"]
        return ["timetable show"]

    # Explain / Quiz / Summarize
    if re.search(r"\b(explain|what is|define)\b",low):
        target = re.sub(r"^(explain|what is|define)\s+", "", low).strip()
        return [f"explain {target}"]
    if re.search(r"\b(quiz|test me)\b",low):
        target = re.sub(r"^(quiz|quiz me on|test me on)\s+", "", low).strip()
        return [f"quiz {target}"]
    if re.search(r"\b(summarize|summarise)\b",low):
        target = re.sub(r"^(summarize|summarise|summary of)\s+", "", low).strip()
        return [f"summarize {target}"]

    # Research
    if re.search(r"\b(research|deep dive|investigate)\b",low):
        t = re.sub(r"^(research|deep dive into|investigate)\s+","",low).strip()
        return [f"research {t}"]

    # Realtime
    if any(kw in low for kw in ["latest","current","today","live","breaking","who won"]):
        return [f"realtime {prompt}"]

    # YouTube / Google
    if "youtube" in low:
        target = re.sub(r".*youtube\s+(?:search\s+)?", "", low).strip()
        return [f"youtube search {target}"]
    if re.search(r"\b(google|search for)\b",low):
        target = re.sub(r".*(google|search for)\s+", "", low).strip()
        return [f"google search {target}"]

    return [f"general {prompt}"]


if __name__ == "__main__":
    tests = [
        ("how are you","general"),
        ("open chrome","open"),
        ("UPSC jobs","jobs upsc"),
        ("SSC CGL notification","jobs ssc"),
        ("Railway RRB recruitment","jobs railway"),
        ("data analyst jobs today","jobs data analyst"),
        ("Python developer jobs India","jobs python developer"),
        ("ML engineer hiring","jobs machine learning"),
        ("fresher IT jobs","jobs fresher"),
        ("PSU recruitment through GATE","gate psu"),
        ("BHEL recruitment 2025","gate psu BHEL"),
        ("DRDO CEPTAM notification","gate psu DRDO"),
        ("GATE CSE syllabus","gate syllabus CSE"),
        ("upcoming job deadlines","deadlines"),
        ("daily job briefing","briefing"),
        ("weather Bhopal","weather"),
        ("TCS stock price","stock"),
        ("Bitcoin price","crypto"),
        ("translate hello to hindi","translate"),
        ("create assignment on AI","assignment"),
        ("explain recursion","explain"),
        ("start studying python","study"),
        ("bye jarvis","exit"),
    ]
    print("\n=== MODEL v4.0 TEST SUITE ===\n")
    passed = 0
    for query,expected in tests:
        result = _fallback_dmm(query)
        got    = result[0] if result else ""
        ok     = got.startswith(expected)
        if ok: passed += 1
        s = "OK  " if ok else "FAIL"
        print(f"[{s}] '{query}'")
        if not ok: print(f"       Expected: '{expected}' | Got: '{got}'")
    print(f"\nScore: {passed}/{len(tests)} = {100*passed//len(tests)}%")


# ── v3.1 patch: add GATE PSU and market job intents ───────────────────────────
_GATE_PSU_PATTERNS = [
    r"\bgate\s+psu\b", r"\bpsu\s+gate\b", r"\bpsu\s+through\s+gate\b",
    r"\bgate\s+cse\b", r"\bgate\s+2026\b", r"\bgate\s+syllabus\b",
    r"\b(bhel|ongc|ntpc|hpcl|iocl|bsnl|drdo|hal|bel|barc|isro|gail)\b",
]
_MARKET_JOB_PATTERNS = [
    r"\b(data\s+analyst|data\s+scientist|machine\s+learning|ml\s+engineer)\b",
    r"\b(python\s+developer|software\s+engineer|web\s+developer)\b",
    r"\b(full\s+stack|backend|frontend|devops|cloud\s+engineer)\b",
]

def _patch_fallback(prompt: str) -> list[str]:
    """Extend _fallback_dmm with GATE/PSU/market job detection."""
    low = prompt.lower().strip()
    # GATE PSU
    for p in _GATE_PSU_PATTERNS:
        if re.search(p, low):
            return [f"jobs gate_psu {prompt}"]
    # Market jobs
    for p in _MARKET_JOB_PATTERNS:
        m = re.search(p, low)
        if m:
            return [f"jobs market {m.group(1)}"]
    # Specific job keyword
    job_m = re.search(r"(.+?)\s+jobs?\s*(today|now|2025|in\s+india)?$", low)
    if job_m and len(job_m.group(1)) > 3:
        kw = job_m.group(1).strip()
        # avoid matching generic words
        skip = {"govt","government","latest","any","all","new"}
        if kw not in skip:
            return [f"jobs market {kw}"]
    return _fallback_dmm(prompt)

# Override FirstLayerDMM to use patched version
_orig_first = FirstLayerDMM
def FirstLayerDMM(prompt: str = "test") -> list[str]:
    result = _orig_first(prompt)
    if result and result[0].startswith("general"):
        patched = _patch_fallback(prompt)
        if not patched[0].startswith("general"):
            return patched
    return result if result else _patch_fallback(prompt)
