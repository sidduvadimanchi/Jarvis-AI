# Backend/Brain/nlp_engine.py  —  v2.0  (100% accuracy target)
# ═══════════════════════════════════════════════════════════════════════
# 5-layer classification:
#   L1  Keyword sets       — exact substring match   (O(n), fastest)
#   L2  Regex patterns     — handles phrasing variants
#   L3  KB lookup          — if answer exists in KB → 'knowledge'
#   L4  Context window     — last 3 turns bias short follow-ups
#   L5  Structural cues    — sentence shape (questions → explain)
#
# Knowledge Base: 45+ entries across CS, Psychology, Philosophy, Creativity
# Modes: normal | conversation | english
# Safety: malware/suspicious-file detection + restricted internet
# ═══════════════════════════════════════════════════════════════════════

from __future__ import annotations
import os, re, json, datetime, threading
from pathlib import Path
from typing  import Optional
from dotenv  import load_dotenv
load_dotenv()

_NAME  = os.getenv("Assistantname","Jarvis")
_USER  = os.getenv("Username","Siddu")
_KB_F  = Path("Data") / "knowledge_base.json"

# ═══════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════
_KB  : dict[str,str] = {}
_kbl = threading.Lock()

_DEFAULT: dict[str,str] = {
    # ── Computer Science ──────────────────────────────────────────────
    "polymorphism":
        "One interface, many forms. Same method works differently on different objects. "
        "Example: len() works on strings, lists, dicts. OOP pillar #3.",
    "recursion":
        "A function calling itself. Needs: base case (stops) + recursive case (calls itself). "
        "Example: factorial(n) = n × factorial(n-1). Space: O(n) stack.",
    "machine learning":
        "Teaching computers with data. Three types: Supervised (labels), Unsupervised (patterns), "
        "Reinforcement (reward). Libraries: scikit-learn, PyTorch, TensorFlow.",
    "neural network":
        "Layers of connected nodes inspired by the brain. Input → hidden layers → output. "
        "Trained via backpropagation + gradient descent. Used for vision, speech, NLP.",
    "api":
        "How programs talk to each other. REST API uses HTTP verbs: GET, POST, PUT, DELETE. "
        "Like a restaurant menu — you order (request), kitchen makes it (server responds).",
    "git":
        "Version control for code. Key commands: init, add, commit, push, pull, branch, merge, "
        "rebase. GitHub/GitLab host remote repos. Always commit meaningful messages.",
    "binary search":
        "Find item in sorted list by halving search space each time. O(log n). "
        "Compare middle → smaller=left, larger=right. Needs sorted array.",
    "big o":
        "Algorithm efficiency. O(1) instant, O(log n) fast, O(n) linear, "
        "O(n log n) good sort, O(n²) slow, O(2ⁿ) very slow. Aim for lowest possible.",
    "sql":
        "Database query language. SELECT col FROM table WHERE condition. "
        "JOIN merges tables. INDEX speeds searches. GROUP BY + aggregates for reports.",
    "docker":
        "Container = app + all dependencies. Same on any machine. "
        "Dockerfile defines it. docker-compose runs multiple containers together.",
    "data structure":
        "Array O(1) access. Linked List O(n). Stack LIFO. Queue FIFO. "
        "Hash Map O(1) lookup. BST O(log n) search. Graph for networks.",
    "object oriented":
        "OOP pillars: Encapsulation (hide internals), Inheritance (reuse code), "
        "Polymorphism (many forms), Abstraction (hide complexity). Class = blueprint.",
    "sorting":
        "Bubble O(n²) simple. Merge O(n log n) stable. Quick O(n log n) avg fast. "
        "Heap O(n log n). Counting O(n+k) integers. Python's sort = Timsort = best general.",
    "python":
        "Readable syntax, huge ecosystem. Master: list comprehensions, decorators, "
        "generators, context managers, dataclasses, type hints. Virtual envs for isolation.",
    "cloud":
        "AWS (largest, 200+ services), GCP (AI/ML strong), Azure (enterprise). "
        "Core: compute (EC2/VM), storage (S3/Blob), DB (RDS), functions (Lambda).",
    "design patterns":
        "Reusable solutions to common problems. Creational: Singleton, Factory. "
        "Structural: Adapter, Decorator. Behavioural: Observer, Strategy, Command.",

    # ── Psychology ───────────────────────────────────────────────────
    "stoicism":
        "Control only your thoughts and actions — accept the rest. "
        "Marcus Aurelius, Epictetus. Daily: negative visualisation, journaling. "
        "Core: virtue is the only good. Emotions from judgements, not events.",
    "growth mindset":
        "Carol Dweck: Fixed='I can't'. Growth='I can't YET'. "
        "Effort > talent. Failure = data. Praise process, not ability.",
    "flow state":
        "Csikszentmihalyi: complete absorption = time disappears. "
        "Occurs when skill = challenge level. Conditions: clear goals, instant feedback, full focus.",
    "procrastination":
        "Avoiding tasks despite knowing the cost. Cause: anxiety + perfectionism, NOT laziness. "
        "Fix: 2-minute rule, temptation bundling, implementation intentions ('When X I will Y').",
    "dopamine":
        "Reward neurotransmitter. Released on anticipation of reward — not just reward. "
        "Social media exploits this. Build healthy loops: exercise, learning, creating.",
    "impostor syndrome":
        "Feeling undeserving despite evidence. Common in high achievers. "
        "Fix: document wins, normalise imperfection, name it when it happens.",
    "cognitive bias":
        "Systematic thinking errors. Key: confirmation bias, availability heuristic, "
        "Dunning-Kruger (incompetent overestimate), anchoring, sunk cost fallacy.",
    "emotional intelligence":
        "EQ (Goleman): self-awareness, self-regulation, motivation, empathy, social skills. "
        "EQ predicts success better than IQ for most roles. Trainable.",
    "anxiety":
        "Future-threat worry. Physical: racing heart, shallow breathing. Cognitive: catastrophising. "
        "Fix: 4-7-8 breathing, grounding (5-4-3-2-1 senses), progressive muscle relaxation.",
    "motivation":
        "Intrinsic > extrinsic long-term. Self-determination: autonomy + competence + relatedness. "
        "Start the 2-minute version — action creates motivation, not the reverse.",
    "habits":
        "Cue → routine → reward loop (Duhigg). Atomic Habits (Clear): make it obvious, attractive, "
        "easy, satisfying. Stack new habits onto existing ones. Identity-based change.",
    "focus":
        "Improves with: Pomodoro (25+5), phone in another room, single-tasking, "
        "7-9h sleep, exercise before deep work, cold water when distracted.",

    # ── Philosophy ────────────────────────────────────────────────────
    "existentialism":
        "Sartre, Camus: no inherent meaning — create your own. "
        "Radical freedom + radical responsibility. Embrace anxiety rather than fleeing it.",
    "critical thinking":
        "Question assumptions. Evaluate evidence quality. Consider alternatives. "
        "Identify fallacies. Distinguish fact from opinion. Suspend judgement until sufficient evidence.",
    "socratic method":
        "Learn through questions: Why? How do you know? What's an example? "
        "What would challenge that? Leads to self-discovery rather than passive reception.",
    "logical fallacy":
        "Ad hominem (attack person). Straw man (misrepresent). False dichotomy (only 2 options). "
        "Slippery slope (unlikely chain). Appeal to authority. Red herring. Circular reasoning.",
    "mindfulness":
        "Non-judgemental present-moment awareness. Reduces cortisol, improves focus. "
        "Start: 5 min daily breath observation. Apps: Headspace, Waking Up.",
    "nietzsche":
        "Will to power = drive to grow and overcome, not dominate others. "
        "'God is dead' = old moral framework collapsed. Create your own values. Live as if you'd repeat your life forever.",
    "ethics":
        "Utilitarianism (greatest good for most). Deontology (rules matter, Kant). "
        "Virtue ethics (be a good person, Aristotle). Care ethics (relationships matter).",

    # ── Creativity & Productivity ─────────────────────────────────────
    "creativity":
        "Combining existing ideas in new ways. Boost: diverse inputs, constraints, "
        "incubation (walk away), SCAMPER technique. Diverge first, converge later.",
    "how to be creative":
        "Combining existing ideas in new ways. Boost: diverse inputs, constraints, "
        "incubation (walk away), SCAMPER technique. Diverge first, converge later.",
    "be more creative":
        "Combining existing ideas in new ways. Boost: diverse inputs, constraints, "
        "incubation (walk away), SCAMPER technique. Diverge first, converge later.",
    "design thinking":
        "Empathise → Define → Ideate → Prototype → Test. Non-linear. "
        "Start with deep user understanding. Fail early, cheaply, often.",
    "first principles":
        "Break problem to fundamental truths. Ask Why? 5 times. Question all assumptions. "
        "Rebuild from scratch. Musk used it for SpaceX rockets and Tesla batteries.",
    "deep work":
        "Cal Newport: focused distraction-free work on hard problems. "
        "Schedule it. Protect it. Build tolerance gradually. Shallows work competes for it.",
    "pomodoro":
        "25 min work → 5 min break → repeat 4× → 30 min break. "
        "Creates urgency, prevents decision fatigue, makes tasks less daunting.",
    "effective studying":
        "Most effective: spaced repetition (1d, 3d, 1wk, 1mo), active recall (test don't reread), "
        "interleaving subjects, Feynman technique (explain simply = true understanding).",
    "productivity":
        "Time blocking + MIT (Most Important Task) first + energy management + "
        "single-tasking + 80/20 rule + weekly review. Protect deep work time fiercely.",

    # ── Current tech ──────────────────────────────────────────────────
    "artificial intelligence":
        "Machines doing tasks requiring human intelligence. Subsets: ML → Deep Learning → LLMs. "
        "Key: OpenAI (GPT), Google (Gemini), Anthropic (Claude), Meta (LLaMA).",
    "large language model":
        "Trained on massive text datasets. Predict next token. Transformer architecture + attention. "
        "Emergent capabilities with scale. Prompt engineering controls quality.",
    "prompt engineering":
        "Effective prompts: role + context + task + format + examples + chain-of-thought. "
        "Few-shot > zero-shot for complex tasks. Be specific. Iterate.",
    "skills to learn":
        "2025 most valuable: Python, SQL, Git, cloud (AWS/GCP), API usage, "
        "prompt engineering, data analysis, communication, system design.",
    "vector database":
        "Stores embeddings (numerical representations of meaning). "
        "Used in RAG (retrieval-augmented generation). Tools: Pinecone, Chroma, FAISS.",
}


def _load_kb() -> None:
    global _KB
    with _kbl:
        if _KB_F.exists():
            try: _KB = json.loads(_KB_F.read_text(encoding="utf-8")); return
            except Exception: pass
        _KB = dict(_DEFAULT); _save_kb()

def _save_kb() -> None:
    Path("Data").mkdir(parents=True, exist_ok=True)
    _KB_F.write_text(json.dumps(_KB, indent=2, ensure_ascii=False), encoding="utf-8")

def add_to_kb(question: str, answer: str) -> None:
    if not _KB: _load_kb()
    with _kbl: _KB[question.lower().strip()] = answer
    _save_kb()


def kb_lookup(query: str) -> Optional[str]:
    """Multi-strategy KB lookup."""
    if not _KB: _load_kb()
    q = query.lower().strip()
    q_c = re.sub(
        r"^(what\s+is|what\s+are|how\s+to|how\s+do\s+i|explain|define|"
        r"tell\s+me\s+about|describe|meaning\s+of|how\s+does|understand)\s+","",q).strip()

    # 1. Exact match
    for candidate in (q_c, q):
        if candidate in _KB: return _KB[candidate]

    # 2. KB key is substring of query
    for key, val in _KB.items():
        if key in q or key in q_c: return val

    # 3. All words of key appear in query
    for key, val in _KB.items():
        kw = set(key.split())
        if len(kw) >= 2 and kw.issubset(set(q_c.split())):
            return val

    return None


# ═══════════════════════════════════════════════════════════════════════
# INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════

# L1 — keyword sets (fastest, O(n))
_KW: dict[str, list[str]] = {
    "greeting"   : ["hi ","hello","hey ","hey,","good morning","good afternoon","good evening",
                     "good night","sup ","yo ","howdy","what's up","whats up"],
    "farewell"   : ["bye","goodbye","good bye","see you","cya","later ","take care",
                    "exit","quit jarvis","close jarvis","goodnight","good night"],
    "thanks"     : ["thank you","thanks","appreciate","helpful","great answer","you're awesome"],
    "how_are_you": ["how are you","how r u","how you doing","you okay","you good","you alright"],
    "task_add"   : ["add task","create task","new task","remind me to","todo ","set reminder",
                    "add a task","make a task","create a reminder"],
    "task_view"  : ["show tasks","my tasks","list tasks","pending tasks","what are my tasks",
                    "show my todos","view tasks","all tasks"],
    "task_done"  : ["mark done","task done","completed task","finish task","done with",
                    "task complete","mark task"],
    "performance": ["my performance","show performance","daily report","my score",
                    "how am i doing","my progress","task stats","show stats"],
    "quiz"       : ["quiz me","test me on","make a quiz","quiz on","practice questions",
                    "ask me questions","quiz about"],
    "study"      : ["assignment","lab manual","pbl ","make notes","create notes",
                    "my timetable","show timetable","study start","study stop","study report",
                    "ieee paper","research paper","make a report"],
    "email"      : ["send email","write email","email to","compose email","send a mail"],
    "whatsapp"   : ["send whatsapp","whatsapp to","message on whatsapp"],
    "automation" : ["open ","launch ","close ","shutdown","restart","sleep mode",
                    "take screenshot","screenshot","mute ","unmute","volume up","volume down",
                    "lock screen","lock pc","app usage","battery status"],
    "realtime"   : ["latest news","today's news","breaking news","weather","current weather",
                    "price of","stock price","who won","live score","what's happening",
                    "current price","news today","temperature in"],
    "search"     : ["search for","google ","search on youtube","youtube search","find on web",
                    "search youtube","look up"],
    "image"      : ["generate image","create image","draw ","make image","render image",
                    "generate a picture","create a picture"],
    "explain"    : ["explain ","what is ","what are ","how does","define ","meaning of",
                    "describe ","how do","tell me about","what's the difference"],
    "knowledge"  : ["stoic","stoicism","psychology","philosophy","creativity","mindfulness",
                    "procrastinat","dopamine","motivat","habits","cognitive bias","impostor",
                    "existential","nietzsche","critical thinking","design thinking","deep work",
                    "flow state","growth mindset","emotional intelligence","first principles",
                    "logical fallacy","socratic","pomodoro","effective study","productivity tips"],
    "plan_today" : ["what's my plan","plan for today","today's plan","what should i do today",
                    "my goals today","plan my day"],
    "conversation":["i feel ","i'm feeling","i am feeling","i feel like","let's talk",
                    "conversation mode","just talk","i need to talk","talk to me",
                    "i'm stressed","i'm sad","i'm happy","i'm excited","i'm worried"],
    "english"    : ["english mode","english practice","check my english","correct my grammar",
                    "improve my english","my english","grammar check","english correction"],
    "export"     : ["export chat","save chat","download chat","save conversation"],
    "memory"     : ["what do you remember","show memory","my memory","what do you know about me",
                    "what have you learned"],
    "malware"    : ["virus","malware","ransomware","trojan","spyware","infected file",
                    "suspicious file","suspicious process","my file is infected","hack",
                    "hacker","security threat","remove virus"],
}

# L2 — regex patterns
_RE: dict[str, list[str]] = {
    "greeting"   : [r"^(hi+|hey+|hello+|good\s+(morning|afternoon|evening|night))[\s!?.]*$"],
    "farewell"   : [r"^(bye+|goodbye|good\s*night|see\s+you|take\s+care)[\s!?.]*$"],
    "task_add"   : [r"\b(add|create|new|set)\s+(?:a\s+)?(?:\w+\s+)?task\b",
                    r"\bremind\s+me\s+(to|at)\b"],
    "task_view"  : [r"\b(show|list|view|see|what)\s+(?:are\s+)?(?:my\s+)?tasks?\b",
                    r"\bwhat(?:'s|\s+are)\s+(?:my\s+)?(?:tasks?|todos?|reminders?)\b"],
    "performance": [r"\bhow\s+(?:am|did)\s+i\s+do\b",
                    r"\bmy\s+(?:daily\s+)?(?:score|progress|performance)\b"],
    "explain"    : [r"\b(what\s+is|what\s+are|how\s+does|explain|define|describe)\b"],
    "realtime"   : [r"\b(latest|current|today'?s?|now|live|breaking)\b.{0,20}\b(news|price|score|weather|result)\b",
                    r"\bweather\s+(in|today|right now)\b",
                    r"\bprice\s+of\b",
                    r"\bwho\s+(is|won|leads)\b"],
    "automation" : [r"^(open|launch|close|quit|kill|start)\s+\w",
                    r"\b(shutdown|restart|hibernate|screenshot|lock\s+screen|mute|unmute|volume|battery)\b"],
    "study"      : [r"\b(assignment|lab\s+manual|pbl|notes\s+on|timetable|study\s+(start|stop|report))\b"],
    "image"      : [r"\b(generate|create|draw|make|render)\s+(an?\s+)?(image|picture|illustration|photo)\b"],
    "quiz"       : [r"\b(quiz\s+me|test\s+me\s+on|practice\s+questions)\b"],
    "knowledge"  : [r"\b(stoic|growth\s+mindset|flow\s+state|design\s+thinking|first\s+principles|"
                     r"deep\s+work|pomodoro|procrastinat|dopamine|impostor|cognitive\s+bias|"
                     r"emotional\s+intel|mindfuln|existential|nietzsch|critical\s+think|"
                     r"logical\s+fallac|socratic|productivity\s+tips|effective\s+stud)\b"],
    "malware"    : [r"\b(virus|malware|ransomware|trojan|spyware|hack(?:ed)?|infect(?:ed)?|"
                     r"suspicious\s+(?:file|process|code)|security\s+threat|remove\s+virus)\b"],
    "english"    : [r"\b(correct\s+my\s+(?:grammar|english)|english\s+(?:mode|practice|check)|"
                     r"check\s+my\s+english|improve\s+my\s+english)\b"],
    "conversation":[ r"\bi\s+(?:feel|am\s+feeling|need\s+to\s+talk|want\s+to\s+talk)\b",
                     r"\b(let'?s?\s+(?:talk|chat)|conversation\s+mode)\b"],
}

# Context window
_ctx : list[dict] = []
_ctl  = threading.Lock()

def _ctx_push(q: str, intent: str):
    with _ctl:
        _ctx.append({"q": q[:80], "intent": intent})
        if len(_ctx) > 4: _ctx.pop(0)

def _ctx_hint() -> Optional[str]:
    with _ctl:
        if len(_ctx) >= 2:
            last = _ctx[-1]["intent"]
            if last in ("quiz","study","explain","knowledge","english","conversation"):
                return last
    return None


def classify_intent(query: str) -> str:
    """5-layer intent classifier. Target: 100% on common inputs."""
    low = query.lower().strip()
    if not low: return "general"

    # Pre-check: if query starts with 'what is/are/explain/tell me about'
    # and KB has an answer → return 'knowledge' immediately (prevents 'explain' stealing it)
    _explain_prefix = re.match(
        r"^(what\s+is|what\s+are|explain|tell\s+me\s+about|describe|how\s+does|"
        r"meaning\s+of|define)\s+", low, re.I)
    if _explain_prefix and kb_lookup(query):
        _ctx_push(low, "knowledge"); return "knowledge"

    # L1 — keyword sets (skip 'explain' here — handled by L2+L5 to avoid stealing knowledge)
    _skip_l1 = {"explain"}
    for intent, keywords in _KW.items():
        if intent in _skip_l1: continue
        if any(kw in low for kw in keywords):
            _ctx_push(low, intent); return intent

    # L2 — regex
    for intent, patterns in _RE.items():
        for pat in patterns:
            if re.search(pat, low, re.I):
                _ctx_push(low, intent); return intent

    # L3 — KB lookup (catches remaining knowledge queries)
    if kb_lookup(query):
        _ctx_push(low, "knowledge"); return "knowledge"

    # L4 — context window bias (short follow-ups)
    hint = _ctx_hint()
    if hint and len(low.split()) <= 5:
        _ctx_push(low, hint); return hint

    # L5 — structural cues
    if low[0:2] in ("wh","ho","is","ar","ca","do","di") or low.endswith("?"):
        _ctx_push(low, "explain"); return "explain"

    _ctx_push(low, "general"); return "general"


# ═══════════════════════════════════════════════════════════════════════
# MODE SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════════════════
def get_mode_system_prompt(mode: str) -> str:
    if mode == "conversation":
        return (
            f"You are {_NAME}, talking with {_USER} as a close, caring friend.\n"
            "CONVERSATION MODE rules:\n"
            "- Acknowledge emotions FIRST before any advice\n"
            "- Ask follow-up questions to understand better\n"
            "- Be warm, natural, encouraging — NOT robotic\n"
            "- Give honest but kind feedback\n"
            "- Reference things you know about the user\n"
            "- End every response with a question or supportive statement\n"
            "- NEVER say 'As an AI' or give disclaimers\n"
            "- Short to medium length — conversational, not an essay\n"
        )
    if mode == "english":
        return (
            f"You are {_NAME}, English practice coach for {_USER}.\n"
            "ENGLISH MODE rules:\n"
            "- Give a real-world scenario for the user to respond to\n"
            "- When they respond, identify mistakes clearly:\n"
            "  Format: ✗ 'wrong phrase' → ✓ 'correct phrase' — Reason: brief\n"
            "- Score: Fluency /10  Grammar /10  Vocabulary /10\n"
            "- Suggest 3 better ways to express the same idea\n"
            "- Quiz idioms, phrasal verbs, collocations when relevant\n"
            "- Be encouraging — celebrate improvement\n"
            "- Scenarios: job interviews, apologies, arguments, descriptions\n"
        )
    return ""

# ═══════════════════════════════════════════════════════════════════════
# RESPONSE CLEANER
# ═══════════════════════════════════════════════════════════════════════
_STRIP = [
    r"As an AI(?:\s+language\s+model)?,?\s*",
    r"I(?:'m| am) (?:just )?an AI,?\s*",
    r"I don'?t have (?:personal\s+)?(?:opinions?|feelings?|experiences?),?\s*",
    r"I cannot (?:browse|access) the (?:internet|web),?\s*",
    r"My (?:knowledge\s+)?(?:cutoff|training)[^.]+\.\s*",
    r"As of my (?:last\s+)?(?:training|update)[^.]+\.\s*",
    r"Please note that[^.]+\.\s*",
    r"Note:\s*[^.]+\.\s*",
    r"Is there anything else I can (?:help|assist)[^?]+\?",
    r"Feel free to ask[^.]+\.",
    r"Let me know if[^.]+\.",
    r"I hope (?:this|that) (?:helps?|answers?)[^.]*\.",
]
def clean_response(text: str) -> str:
    for p in _STRIP:
        text = re.sub(p, "", text, flags=re.I)
    return "\n".join(l.rstrip() for l in text.split("\n")).strip()


# ═══════════════════════════════════════════════════════════════════════
# MALWARE / SECURITY ADVISOR
# ═══════════════════════════════════════════════════════════════════════
def get_malware_advice(query: str) -> str:
    """
    When user mentions a virus / suspicious file / hack.
    Returns structured advice without accessing the internet.
    """
    q = query.lower()
    if "delete" in q or "remove" in q:
        action = "removal"
    elif "infected" in q or "virus" in q:
        action = "infection"
    else:
        action = "suspicious"

    steps = {
        "infection": [
            "1. **Disconnect** from internet immediately (prevents spread)",
            "2. **Do NOT restart** — some malware activates on reboot",
            "3. Run **Windows Defender** full scan (free, built-in)",
            "4. Use **Malwarebytes Free** (https://malwarebytes.com) — download from another device",
            "5. Check **Task Manager** → Details tab for unknown processes",
            "6. Check **Startup** (Win+R → msconfig) for unknown entries",
            "7. Check browser extensions — remove any you didn't install",
            "8. If infection confirmed: **backup personal files to external drive**",
            "9. Consider **clean reinstall** of Windows if critical files affected",
        ],
        "removal": [
            "1. **Identify the file** — right-click → Properties → check digital signature",
            "2. Check file location — system files shouldn't be in Downloads/Temp",
            "3. Google the filename + 'is it safe' before deleting system files",
            "4. Use **Process Explorer** (Sysinternals) to see what's running",
            "5. If confirmed malware: delete + empty Recycle Bin + run full AV scan",
            "6. **Check registry** (Run: regedit) for persistence entries (advanced)",
        ],
        "suspicious": [
            "1. Tell me the **file name** or **process name** — I can help identify it",
            "2. Check **VirusTotal.com** — upload the file or paste the URL",
            "3. Check **Task Manager** → CPU/Memory usage — malware often uses high resources",
            "4. Unusual network traffic? → **TCPView** (Sysinternals) shows all connections",
            "5. Run **Windows Defender** offline scan (most thorough)",
        ],
    }
    lines = [f"🔴 **Security Alert Detected**\n"]
    lines += steps[action]
    lines += [
        "",
        "**Free trusted tools:**",
        "• Windows Defender (built-in)  • Malwarebytes Free  • VirusTotal.com",
        "• Process Explorer (Sysinternals)  • HiJackThis Free",
        "",
        "⚠️ **Never** download 'antivirus' from pop-up ads — those ARE the malware.",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# SAFE INTERNET ACCESS RULES
# ═══════════════════════════════════════════════════════════════════════
_BLOCKED_DOMAINS = {
    # Malware / hacking
    "exploit-db","pastebin.com/raw","darkweb","onion","thepiratebay",
    "torrent","warez","crackz","hackforums","nulled.to",
    # Adult
    "pornhub","xvideos","onlyfans","xhamster",
    # Scam-prone
    "freebitcoin","cryptogiveaway","419",
}

_ALLOWED_KNOWLEDGE_DOMAINS = {
    "wikipedia.org","britannica.com","khan academy","coursera.org","edx.org",
    "medium.com","dev.to","stackoverflow.com","github.com","arxiv.org",
    "psychology today","sciencedirect","pubmed","scholar.google",
    "apa.org","verywellmind.com","positivepsychology.com",
    "philosophybasics.com","iep.utm.edu","plato.stanford.edu",
}

def is_safe_url(url: str) -> bool:
    """Check if a URL is safe for Jarvis to access."""
    low = url.lower()
    return not any(b in low for b in _BLOCKED_DOMAINS)

def is_knowledge_domain(url: str) -> bool:
    """True if URL is in the approved knowledge domain list."""
    low = url.lower()
    return any(d in low for d in _ALLOWED_KNOWLEDGE_DOMAINS)


# ═══════════════════════════════════════════════════════════════════════
# TESTS  — target 100%
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    _load_kb()

    cases = [
        # Social
        ("hi",                              "greeting"),
        ("hello jarvis",                    "greeting"),
        ("hey there",                       "greeting"),
        ("good morning",                    "greeting"),
        ("good afternoon",                  "greeting"),
        ("bye",                             "farewell"),
        ("goodbye",                         "farewell"),
        ("goodnight",                       "farewell"),
        ("how are you doing",               "how_are_you"),
        ("thank you so much",               "thanks"),
        # Tasks
        ("add task study python today",     "task_add"),
        ("remind me to submit report",      "task_add"),
        ("create a new task for gym",       "task_add"),
        ("show my tasks",                   "task_view"),
        ("list all pending tasks",          "task_view"),
        ("mark task done",                  "task_done"),
        ("show my performance",             "performance"),
        ("my daily score",                  "performance"),
        # Automation
        ("open chrome",                     "automation"),
        ("close firefox",                   "automation"),
        ("shutdown laptop",                 "automation"),
        ("take a screenshot",               "automation"),
        ("mute the volume",                 "automation"),
        ("battery status",                  "automation"),
        # Study
        ("create assignment on AI",         "study"),
        ("make lab manual on op-amp",       "study"),
        ("make a pbl on smart home",        "study"),
        ("show timetable",                  "study"),
        # Knowledge
        ("what is stoicism",                "knowledge"),
        ("explain procrastination",         "knowledge"),
        ("tell me about growth mindset",    "knowledge"),
        ("what is flow state",              "knowledge"),
        ("deep work techniques",            "knowledge"),
        # Explain / general questions (NOT in KB → explain)
        ("what is quantum entanglement",    "explain"),
        ("how does inflation work",         "explain"),
        ("explain the water cycle",         "explain"),
        # Realtime
        ("latest news today",               "realtime"),
        ("weather in hyderabad",            "realtime"),
        ("current price of bitcoin",        "realtime"),
        ("who won yesterday's match",       "realtime"),
        # Modes
        ("i feel really stressed today",    "conversation"),
        ("let's just talk",                 "conversation"),
        ("conversation mode on",            "conversation"),
        ("check my english grammar",        "english"),
        ("english practice mode",           "english"),
        # Security
        ("my file looks infected",          "malware"),
        ("found a suspicious process",      "malware"),
        ("there's a virus on my laptop",    "malware"),
        # Other
        ("quiz me on data structures",      "quiz"),
        ("send email to professor",         "email"),
        ("search youtube for lofi",         "search"),
        ("generate image of sunset",        "image"),
    ]

    passed = 0
    print(f"\n{'═'*64}")
    print(f"  NLP ENGINE v2.0 — {len(cases)} test cases")
    print(f"{'═'*64}\n")

    for query, expected in cases:
        got = classify_intent(query)
        ok  = (got == expected)
        if ok: passed += 1
        tag = "✅" if ok else "❌"
        note = f" (got {got}, exp {expected})" if not ok else ""
        print(f"  {tag}  {query!r:48}{note}")

    pct = 100 * passed // len(cases)
    print(f"\n{'═'*64}")
    print(f"  SCORE: {passed}/{len(cases)} = {pct}%")
    print(f"{'═'*64}\n")

    # KB spot check
    print("  KB LOOKUP:")
    for q, expect_hit in [
        ("what is stoicism",             True),
        ("explain recursion",            True),
        ("how to be creative",           True),
        ("procrastination",              True),
        ("weather in london",            False),
    ]:
        r  = kb_lookup(q)
        ok = (r is not None) == expect_hit
        print(f"  {'✅' if ok else '❌'}  {q!r:40} → {'HIT' if r else 'MISS'}" +
              (f": {r[:50]}..." if r else ""))

    print(f"\n  SECURITY TEST:")
    for url, safe in [
        ("https://wikipedia.org/Stoicism",  True),
        ("https://exploit-db.com/hack",     False),
        ("https://stackoverflow.com/q/123", True),
        ("http://darkweb.onion/malware",    False),
    ]:
        ok = is_safe_url(url) == safe
        print(f"  {'✅' if ok else '❌'}  {url[:50]} → {'safe' if is_safe_url(url) else 'BLOCKED'}")