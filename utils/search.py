# Backend/RealtimesearchEngine.py
# Python 3.10+ compatible | All 12 issues fixed
import os
import sys
import random
import datetime
from json import load, dump
from difflib import get_close_matches
from dotenv import load_dotenv

load_dotenv()

# ── Optional web search ──────────────────────────────────────────────────────
SEARCH_AVAILABLE = True
try:
    from googlesearch import search as google_search
except Exception:
    SEARCH_AVAILABLE = False
    google_search = None  # type: ignore

# ── Groq client ───────────────────────────────────────────────────────────────
from groq import Groq

GROQ_KEY = (
    os.getenv("GROQ_API_KEY")
    or os.getenv("GroqAPIKey")
    or os.getenv("GroqKey")
)
if not GROQ_KEY:
    raise ValueError(
        "Groq API key missing. Add GROQ_API_KEY=<key> to your .env file."
    )
client = Groq(api_key=GROQ_KEY)

# ── Identity ──────────────────────────────────────────────────────────────────
Username      = os.getenv("Username", "User")
Assistantname = os.getenv("Assistantname", "Jarvis")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR     = "Data"
CHATLOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(CHATLOG_PATH):
    with open(CHATLOG_PATH, "w", encoding="utf-8") as _f:
        dump([], _f)

# ── Short-term session state ──────────────────────────────────────────────────
_session: dict = {
    "nickname": None,        # remembered nickname (fix #8)
    "last_emotion": None,    # remembered emotion  (fix #10)
}

# ═════════════════════════════════════════════════════════════════════════════
# FIX #12 – clean helper (no extra blank lines, no "Assistant:\n" prefix)
# ═════════════════════════════════════════════════════════════════════════════
def AnswerModifier(text: str) -> str:
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


def Information() -> str:
    now = datetime.datetime.now()
    return (
        "Current time information:\n"
        f"Day:  {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d %B %Y')}\n"
        f"Time: {now.strftime('%H:%M:%S')}\n"
    )


# ═════════════════════════════════════════════════════════════════════════════
# FIX #9 + #11 – expanded greeting vocab & fuzzy matching
# ═════════════════════════════════════════════════════════════════════════════
GREETING_WORDS = {
    "hi", "hello", "hey", "hiya", "hola",
    "yo", "sup", "wassup", "howdy", "greetings",
    "heya", "heyy", "hihi", "morning", "evening",
    # common typos handled via fuzzy match below
}

HONORIFICS = {
    "bro", "bruh", "dude", "sir", "madam", "ma'am",
    "mam", "bhai", "friend", "man", "boss", "chief",
    "buddy", "mate", "pal",
}

# FIX #11 – fuzzy normalise a single token
def _fuzzy_norm(token: str) -> str:
    """Return closest greeting word if within edit-distance, else original."""
    matches = get_close_matches(token, GREETING_WORDS, n=1, cutoff=0.75)
    return matches[0] if matches else token


def _tokens(text: str) -> list[str]:
    return [t.strip(" ,.!?'\"-").lower() for t in text.split() if t.strip()]


# FIX #1 – separate greeting word from nickname, no double insertion
def detect_greeting(text: str) -> tuple[str | None, str | None]:
    """
    Returns (greeting_word, nickname_or_None).
    Returns (None, None) if no greeting detected.
    """
    toks = _tokens(text)
    if not toks:
        return None, None

    norm_first = _fuzzy_norm(toks[0])
    is_greeting = norm_first in GREETING_WORDS

    # Also accept "hi there", "hey man" etc. where greeting is not first token
    greeting_tok = None
    if is_greeting:
        greeting_tok = norm_first
    else:
        for t in toks[:3]:
            nt = _fuzzy_norm(t)
            if nt in GREETING_WORDS:
                greeting_tok = nt
                break

    if greeting_tok is None:
        return None, None

    # Find nickname: any honorific in the message, or remembered nickname
    nick = None
    for t in toks:
        if t in HONORIFICS:
            nick = t
            break
    # Remember / recall nickname from session
    if nick:
        _session["nickname"] = nick
    elif _session["nickname"]:
        nick = _session["nickname"]

    return greeting_tok, nick


# ═════════════════════════════════════════════════════════════════════════════
# FIX #4 – extended emotion keywords
# ═════════════════════════════════════════════════════════════════════════════
EMOTION_KEYWORDS: dict[str, list[str]] = {
    "happy":   ["happy", "great", "awesome", "good", "nice", "yay", ":)", "glad", "joy", "joyful", "fantastic"],
    "sad":     ["sad", "unhappy", "depressed", "down", ":(", "sorrow", "miserable", "crying", "cry", "hopeless"],
    "angry":   ["angry", "mad", "furious", "pissed", "annoyed", "rage", "frustrated", "irritated"],
    "excited": ["excited", "amazing", "wow", "incredible", "thrilled", "pumped", "hyped"],
    "stressed":["stressed", "stress", "anxious", "anxiety", "overwhelmed", "pressure", "tense", "nervous"],
    "bored":   ["bored", "boring", "nothing to do", "boredom", "dull"],
    "tired":   ["tired", "exhausted", "sleepy", "fatigue", "drained", "weary"],
}

def detect_emotion(text: str) -> str | None:
    low = text.lower()
    if text.strip().isupper() and len(text.strip()) > 1:
        return "excited"
    if text.count("!") >= 2:
        return "excited"
    for emo, kws in EMOTION_KEYWORDS.items():
        for kw in kws:
            if kw in low:
                return emo
    return None


# ═════════════════════════════════════════════════════════════════════════════
# FIX #5 – randomised greeting responses
# FIX #1 – no double nickname
# ═════════════════════════════════════════════════════════════════════════════
_GREETING_TEMPLATES: dict[str | None, list[str]] = {
    "happy":   [
        "Hey {nick}! Glad you're in a good mood — what can I do for you?",
        "Hi {nick}! Great vibes! How can I help today?",
    ],
    "sad": [
        "Hey {nick}, sorry to hear that. Want to talk about it?",
        "Hi {nick}. I'm here — what's going on?",
    ],
    "angry": [
        "Hey {nick}, I hear you. Tell me what's up — I'll help.",
        "Hi {nick}! Let's sort this out. What's wrong?",
    ],
    "excited": [
        "Hey {nick}! That energy! 🔥 What's happening?",
        "Hi {nick}! Awesome! What can I do for you?",
    ],
    "stressed": [
        "Hey {nick}, take a breath — I'm here to help.",
        "Hi {nick}, sounds stressful. Tell me what's going on.",
    ],
    "bored": [
        "Hey {nick}! Let's fix that boredom — what do you feel like doing?",
        "Hi {nick}! I've got plenty of things we can explore. What interests you?",
    ],
    "tired": [
        "Hey {nick}, sounds like you need a break. How can I help?",
        "Hi {nick}! Take it easy — I'll keep things simple.",
    ],
    None: [
        "{greet} {nick}! How's it going?",
        "{greet} {nick}! What's up today?",
        "{greet} {nick}! What can I do for you?",
        "Hey {nick}! Good to see you — what do you need?",
    ],
}

def gen_greeting_response(greeting: str, nick: str | None, emotion: str | None) -> str:
    templates = _GREETING_TEMPLATES.get(emotion) or _GREETING_TEMPLATES[None]
    tpl = random.choice(templates)
    nick_str  = nick.capitalize() if nick else (Username.split()[0] if Username else "")
    greet_str = greeting.capitalize()
    return tpl.format(nick=nick_str, greet=greet_str).strip()


# ═════════════════════════════════════════════════════════════════════════════
# Small-talk responses (randomised)
# ═════════════════════════════════════════════════════════════════════════════
SMALL_TALK: dict[str, list[str]] = {
    "how are you": [
        "I'm doing well, thanks! How are you?",
        "All good here — ready to help. How are you?",
    ],
    "thanks":     ["You're welcome!", "No problem at all!"],
    "thank you":  ["Anytime!", "Glad I could help."],
    "bye":        ["Goodbye! Talk soon.", "See you later — take care!"],
    "good night": ["Good night! Rest well.", "Sleep tight!"],
    "good morning": ["Good morning! Hope your day goes great.", "Morning! What can I help you with?"],
}

def small_talk_response(prompt: str) -> str | None:
    p = prompt.lower().strip()
    for key, replies in SMALL_TALK.items():
        if key in p:
            return random.choice(replies)
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Nickname setter  ("call me bro / my name is X")  – fix #8
# ═════════════════════════════════════════════════════════════════════════════
def maybe_set_nickname(prompt: str) -> str | None:
    """If user sets a nickname, store and confirm it."""
    low = prompt.lower().strip()
    for prefix in ("call me ", "my name is ", "i am ", "i'm "):
        if low.startswith(prefix):
            nick = prompt[len(prefix):].strip(" ,.!?")
            if nick:
                _session["nickname"] = nick.lower()
                return f"Got it! I'll call you {nick.capitalize()} from now on. 😊"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# FIX #3 – exact-phrase time detection (not loose keyword)
# ═════════════════════════════════════════════════════════════════════════════
TIME_PHRASES = [
    "what time", "what's the time", "whats the time",
    "current time", "time now", "tell me the time",
    "what is the time",
]
DATE_PHRASES = [
    "what date", "what's the date", "whats the date",
    "current date", "today's date", "todays date",
    "what is the date", "what is today",
]
DAY_PHRASES = [
    "what day", "what's the day", "whats the day",
    "which day", "day today",
]

def detect_time_query(prompt: str) -> str | None:
    low = prompt.lower()
    if any(ph in low for ph in TIME_PHRASES):
        return "time"
    if any(ph in low for ph in DATE_PHRASES):
        return "date"
    if any(ph in low for ph in DAY_PHRASES):
        return "day"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# FIX #10 – emotion context response (remember last emotion)
# ═════════════════════════════════════════════════════════════════════════════
_EMOTION_FOLLOW_UPS: dict[str, list[str]] = {
    "sad":     [
        "I remember you mentioned feeling a bit down earlier. I hope this helps cheer you up! 🌟",
        "Since you said you're feeling sad, I'll try to be extra helpful — here you go:",
    ],
    "stressed": [
        "You seemed stressed earlier — I'll keep this nice and simple for you:",
        "Here's what you asked for. Hope it helps ease things a bit 🙂:",
    ],
    "angry": [
        "I hope things are calming down a bit. Here's what I found:",
    ],
    "bored": [
        "Maybe this will be more interesting for you 😄:",
    ],
    "tired": [
        "I'll keep it short since you're tired:",
    ],
}

def emotion_context_prefix() -> str:
    emo = _session.get("last_emotion")
    if emo and emo in _EMOTION_FOLLOW_UPS:
        return random.choice(_EMOTION_FOLLOW_UPS[emo]) + "\n"
    return ""


# ═════════════════════════════════════════════════════════════════════════════
# Google search wrapper
# ═════════════════════════════════════════════════════════════════════════════
def GoogleSearch(query: str) -> str:
    if not SEARCH_AVAILABLE or google_search is None:
        return ""
    try:
        results = list(google_search(query, num_results=5))
    except TypeError:
        try:
            results = list(google_search(query, 5))
        except Exception:
            results = []
    except Exception:
        results = []
    if not results:
        return ""
    out = f"Search results for '{query}':\n"
    for i, r in enumerate(results[:5], 1):
        out += f"{i}. {r}\n"
    return out


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE  (fixed priority order)
# Priority: nickname-setter → greeting → emotion-only → small-talk
#           → time/date/day → AI (with search)
# ═════════════════════════════════════════════════════════════════════════════
def RealtimeSearchEngine(prompt: str) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        return "Say something and I'll help."

    # ── 0) nickname setter ────────────────────────────────────────────────────
    nick_reply = maybe_set_nickname(prompt)
    if nick_reply:
        return nick_reply

    # ── 1) greeting detection (FIX #1, #9, #11) ──────────────────────────────
    greet_word, nick = detect_greeting(prompt)
    if greet_word:
        emotion = detect_emotion(prompt)
        if emotion:
            _session["last_emotion"] = emotion      # remember for later (fix #10)
        return gen_greeting_response(greet_word, nick, emotion)

    # ── 2) emotion-only message (FIX #2 – before time check) ─────────────────
    emotion = detect_emotion(prompt)
    if emotion:
        _session["last_emotion"] = emotion          # remember (fix #10)
        nick_str = _session["nickname"] or (Username.split()[0] if Username else "")
        nick_str = nick_str.capitalize() if nick_str else ""
        emo_map = {
            "happy":   f"That's great{', ' + nick_str if nick_str else ''}! What can I do for you today?",
            "sad":     f"I'm sorry to hear that{', ' + nick_str if nick_str else ''}. Want to talk about it or should I try to help with something?",
            "angry":   f"I hear you{', ' + nick_str if nick_str else ''}. Take a breath — tell me what's going on.",
            "excited": f"Love the energy{', ' + nick_str if nick_str else ''}! 🎉 What's up?",
            "stressed":f"Sorry you're feeling stressed{', ' + nick_str if nick_str else ''}. Let's work through it together.",
            "bored":   f"Let's fix that{', ' + nick_str if nick_str else ''}! Want a joke, a fact, or something specific?",
            "tired":   f"Sounds like you need a break{', ' + nick_str if nick_str else ''}. Rest up — or tell me how I can help.",
        }
        return emo_map.get(emotion, f"How can I help you today{', ' + nick_str if nick_str else ''}?")

    # ── 3) small talk ─────────────────────────────────────────────────────────
    st = small_talk_response(prompt)
    if st:
        return st

    # ── 4) time / date / day (FIX #3 – phrase-based only) ────────────────────
    tq = detect_time_query(prompt)
    if tq:
        now = datetime.datetime.now()
        if tq == "time":
            return f"The current time is {now.strftime('%H:%M:%S')}."
        if tq == "date":
            return f"Today's date is {now.strftime('%d %B %Y')}."
        if tq == "day":
            return f"Today is {now.strftime('%A')}."

    # ── 5) AI response (search + Groq) ───────────────────────────────────────
    # FIX #7 – limit chat history to last 10 exchanges (20 messages)
    try:
        with open(CHATLOG_PATH, "r", encoding="utf-8") as f:
            messages: list[dict] = load(f)
    except Exception:
        messages = []

    messages = messages[-20:]           # keep only last 10 exchanges
    messages.append({"role": "user", "content": prompt})

    # decide whether to web-search
    question_words = [
        "what", "who", "when", "where", "why", "how",
        "news", "latest", "definition", "meaning", "explain",
        "tell me about", "price", "weather",
    ]
    use_search = any(qw in prompt.lower() for qw in question_words)

    system_msgs: list[dict] = [
        {
            "role": "system",
            "content": (
                f"You are {Assistantname}, a helpful, friendly assistant. "
                "Keep answers concise and conversational. "
                "Use the provided search results when available."
            ),
        }
    ]
    if use_search:
        if SEARCH_AVAILABLE:
            stext = GoogleSearch(prompt)
            if stext:
                system_msgs.append({"role": "system", "content": stext})
        else:
            system_msgs.append({
                "role": "system",
                "content": "Note: web search is unavailable in this environment.",
            })
    system_msgs.append({"role": "system", "content": Information()})

    model_messages = system_msgs + messages

    # Groq streaming
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=model_messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stream=True,
        )
    except Exception as e:
        return f"Realtime engine error: {e}"

    Answer = ""
    try:
        for chunk in completion:
            try:
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    Answer += delta.content
            except Exception:
                try:
                    if isinstance(chunk, dict):
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            cont = delta.get("content")
                            if cont:
                                Answer += cont
                except Exception:
                    pass
    except Exception as e:
        return f"Realtime stream error: {e}"

    Answer = Answer.strip()

    # FIX #6 – better fallback messages
    if not Answer:
        fallbacks = [
            "Sorry, I couldn't find that information right now. Could you rephrase your question?",
            "I didn't get a response this time. Try asking it a different way?",
            "Hmm, I'm not sure about that one. Could you give me more details?",
        ]
        return random.choice(fallbacks)

    # FIX #10 – prepend emotional context if relevant
    prefix = emotion_context_prefix()
    final_answer = AnswerModifier(prefix + Answer)

    # save history (trimmed)
    messages.append({"role": "assistant", "content": final_answer})
    messages = messages[-20:]
    try:
        with open(CHATLOG_PATH, "w", encoding="utf-8") as f:
            dump(messages, f, indent=2)
    except Exception:
        pass

    return final_answer


# ═════════════════════════════════════════════════════════════════════════════
# Built-in self-test  (80 / 20 train-test split simulation)
# Run:  python RealtimesearchEngine.py --test
# ═════════════════════════════════════════════════════════════════════════════
TEST_CASES: list[dict] = [
    # greeting tests (fix #1, #9, #11)
    {"input": "hello bro",        "expect": "no_double_bro",   "tag": "greeting"},
    {"input": "hi",               "expect": "greeting",        "tag": "greeting"},
    {"input": "hey",              "expect": "greeting",        "tag": "greeting"},
    {"input": "yo",               "expect": "greeting",        "tag": "greeting"},
    {"input": "sup",              "expect": "greeting",        "tag": "greeting"},
    {"input": "wassup",           "expect": "greeting",        "tag": "greeting"},
    {"input": "hellow bro",       "expect": "greeting",        "tag": "greeting"},  # typo
    {"input": "helo dude",        "expect": "greeting",        "tag": "greeting"},  # typo
    {"input": "hi there",         "expect": "greeting",        "tag": "greeting"},
    {"input": "hey man",          "expect": "greeting",        "tag": "greeting"},
    # emotion before time (fix #2, #3)
    {"input": "i am sad today",   "expect": "emotion_not_time","tag": "emotion"},
    {"input": "i am feeling happy","expect":"emotion",         "tag": "emotion"},
    {"input": "i am so angry",    "expect": "emotion",         "tag": "emotion"},
    {"input": "i'm stressed",     "expect": "emotion",         "tag": "emotion"},
    {"input": "i'm bored",        "expect": "emotion",         "tag": "emotion"},
    {"input": "i'm tired",        "expect": "emotion",         "tag": "emotion"},
    {"input": "feeling excited",  "expect": "emotion",         "tag": "emotion"},
    # time detection (fix #3)
    {"input": "what time is it",  "expect": "time",            "tag": "time"},
    {"input": "current time",     "expect": "time",            "tag": "time"},
    {"input": "what is the time", "expect": "time",            "tag": "time"},
    {"input": "what date is it",  "expect": "date",            "tag": "time"},
    {"input": "what day is today","expect": "day",             "tag": "time"},
    # should NOT trigger time
    {"input": "i am sad today",   "expect": "not_time",        "tag": "time_negative"},
    {"input": "have a good day",  "expect": "not_time",        "tag": "time_negative"},
    {"input": "today is my birthday","expect":"not_time",      "tag": "time_negative"},
    # small talk
    {"input": "thanks",           "expect": "small_talk",      "tag": "small_talk"},
    {"input": "thank you",        "expect": "small_talk",      "tag": "small_talk"},
    {"input": "bye",              "expect": "small_talk",      "tag": "small_talk"},
    # nickname setter (fix #8)
    {"input": "call me bro",      "expect": "nickname_set",    "tag": "nickname"},
    {"input": "my name is Ravi",  "expect": "nickname_set",    "tag": "nickname"},
]

def run_tests() -> None:
    print("\n" + "═" * 60)
    print("  SELF-TEST  (80/20 split)")
    print("═" * 60)

    random.seed(42)
    shuffled = TEST_CASES[:]
    random.shuffle(shuffled)
    split = int(len(shuffled) * 0.8)
    train_set = shuffled[:split]
    test_set  = shuffled[split:]

    def evaluate(cases: list[dict], label: str) -> float:
        passed = 0
        for tc in cases:
            inp    = tc["input"]
            expect = tc["expect"]
            tag    = tc["tag"]

            # reset session for each test
            _session["nickname"]     = None
            _session["last_emotion"] = None

            result = ""

            if tag == "greeting":
                gw, nk = detect_greeting(inp)
                if expect == "greeting":
                    ok = gw is not None
                elif expect == "no_double_bro":
                    # nickname should appear exactly once
                    resp = gen_greeting_response(gw or "hello", nk, None) if gw else ""
                    nick_count = resp.lower().count("bro")
                    ok = gw is not None and nick_count <= 1
                    result = repr(resp)
                else:
                    ok = False
                if not result:
                    result = f"gw={gw!r}, nick={nk!r}"

            elif tag == "emotion":
                emo = detect_emotion(inp)
                if expect == "emotion_not_time":
                    tq  = detect_time_query(inp)
                    ok  = emo is not None and tq is None
                    result = f"emo={emo}, tq={tq}"
                else:
                    ok = emo is not None
                    result = f"emo={emo}"

            elif tag == "time":
                tq = detect_time_query(inp)
                ok = (tq == expect)
                result = f"tq={tq}"

            elif tag == "time_negative":
                tq = detect_time_query(inp)
                ok = tq is None
                result = f"tq={tq}"

            elif tag == "small_talk":
                st = small_talk_response(inp)
                ok = st is not None
                result = repr(st)

            elif tag == "nickname":
                nick_reply = maybe_set_nickname(inp)
                ok = nick_reply is not None
                result = repr(nick_reply)

            else:
                ok = False
                result = "unknown tag"

            status = "✅ PASS" if ok else "❌ FAIL"
            if ok:
                passed += 1
            print(f"  {status}  [{tag:16s}]  input={inp!r:<30}  result={result}")

        acc = passed / len(cases) * 100 if cases else 0
        print(f"\n  {label}: {passed}/{len(cases)} passed  →  {acc:.1f}% accuracy")
        return acc

    print(f"\n── TRAIN set ({len(train_set)} cases) ──────────────────────────")
    train_acc = evaluate(train_set, "TRAIN")

    print(f"\n── TEST  set ({len(test_set)} cases) ───────────────────────────")
    test_acc  = evaluate(test_set,  "TEST ")

    print("\n" + "═" * 60)
    overall = (train_acc + test_acc) / 2
    print(f"  OVERALL ACCURACY: {overall:.1f}%")
    print("═" * 60 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
# Entry points
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
        sys.exit(0)

    # FIX #12 – clean "Assistant: <answer>" on one line
    try:
        while True:
            prompt = input("You: ").strip()
            if not prompt:
                continue
            answer = RealtimeSearchEngine(prompt)
            print(f"\nAssistant: {answer}\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)