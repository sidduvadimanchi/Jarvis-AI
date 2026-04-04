# Backend/Brain/emotion.py
# Jarvis AI — Deep Emotion Engine
# ─────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import os
import datetime
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

# ══════════════════════════════════════════════════════════
# LAYER 0 — Style signals (runs FIRST — highest priority)
# FIX 1: ALL CAPS must run BEFORE keyword matching
# ══════════════════════════════════════════════════════════

def _style_signals(text: str) -> Optional[str]:
    """Checked FIRST — style overrides keywords."""
    if text.isupper() and len(text) > 8:
        return "angry"          # ALL CAPS = shouting
    if text.count("!") >= 3:
        return "excited"
    if text.count("?") >= 3:
        return "confused"
    if "..." in text or text.count(".") >= 4:
        return "sad"
    if re.search(r"(haha|lol|hehe|😂|😄|🙂)", text.lower()):
        return "happy"
    if re.search(r"(😢|😭|💔|😔|🥺)", text):
        return "sad"
    if re.search(r"(😤|😠|🤬|😡)", text):
        return "angry"
    return None


# ══════════════════════════════════════════════════════════
# LAYER 1 — Regex patterns (runs SECOND — specific context)
# FIX 2: "I failed my exam" → 'failed' pattern → sad
#         BEFORE "exam" keyword ever triggers stressed
# ══════════════════════════════════════════════════════════

_EMOTION_PATTERNS: dict[str, list[str]] = {
    "sad"      : [
        r"\b(failed|rejected|lost|broke up|miss you|miss him|miss her"
        r"|didn't pass|couldn't pass)\b",
        r"i (failed|lost|missed|didn't make)",
    ],
    "stressed" : [
        r"\b(due|deadline|submit|submission)\b.*\b(tomorrow|today|tonight|soon)\b",
        r"i (have|need) to (finish|complete|submit)",
        r"\b(exam|test)\b.*\b(tomorrow|today|tonight|in \d)\b",
    ],
    "tired"    : [
        r"(it'?s?|been) (late|2am|3am|1am|midnight)",
        r"can'?t (sleep|wake|focus|think)",
        r"been up (since|for) \d",
    ],
    "happy"    : [
        r"\b(got|passed|scored|cleared|selected|hired|accepted|promoted)\b",
        r"(birthday|celebration|party|vacation|holiday)",
    ],
    "confused" : [
        r"(what|how|why|when|where|which)\s+(does|do|is|are|means|mean)\s+",
        r"(don'?t|doesn'?t|can'?t)\s+(understand|get|know)",
    ],
}


# ══════════════════════════════════════════════════════════
# LAYER 2 — Keywords (runs LAST — broad fallback)
# FIX 2 cont: removed "exam" and "test" from stressed
#             — too generic, caused false positives
# ══════════════════════════════════════════════════════════

_EMOTION_KEYWORDS: dict[str, list[str]] = {
    "happy"    : ["happy","great","awesome","wonderful","excited","joy","yay",
                  "love","amazing","fantastic","brilliant","perfect","thrilled",
                  "glad","cheerful"],
    "sad"      : ["sad","unhappy","depressed","down","upset","cry","miss","lonely",
                  "heartbroken","miserable","hopeless","gloomy","grief","loss"],
    "angry"    : ["angry","mad","furious","hate","annoyed","frustrated","pissed",
                  "rage","irritated","disgusted","fed up"],
    "stressed" : ["stressed","anxious","overwhelmed","pressure","tense","worried",
                  "nervous","panic","deadline","submission"],
                  # NOTE: "exam" and "test" removed — too generic
    "tired"    : ["tired","exhausted","sleepy","drained","weary","fatigue",
                  "need sleep","can't focus","can't concentrate"],
    "confused" : ["confused","don't understand","don't get it","what does",
                  "not sure","lost","unclear","how does","explain","meaning of"],
    "bored"    : ["bored","boring","nothing to do","dull","uninteresting",
                  "waste of time"],
    "excited"  : ["can't wait","so excited","pumped","looking forward","finally",
                  "yes!","woohoo","awesome news"],
    "grateful" : ["thank you","thanks","appreciate","grateful","helped me",
                  "you're great","you saved me"],
}


# ══════════════════════════════════════════════════════════
# MAIN DETECT — new order: Style → Pattern → Keyword
# ══════════════════════════════════════════════════════════

def detect_emotion(text: str) -> Optional[str]:
    """
    3-layer detection. New order fixes both failures:

    FIX 1: Style first → ALL CAPS → angry (not confused)
    FIX 2: Patterns before keywords → 'failed' → sad
            before 'exam' keyword ever fires stressed
    """
    # Layer 0 — style signals (ALL CAPS, punctuation, emoji)
    style = _style_signals(text)
    if style:
        return style

    low = text.lower()

    # Layer 1 — regex patterns (specific phrases)
    for emotion, patterns in _EMOTION_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low):
                return emotion

    # Layer 2 — keywords (broad fallback)
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return emotion

    return None


def detect_emotion_intensity(text: str, emotion: str) -> int:
    """Rate emotion intensity 1-10."""
    low   = text.lower()
    kws   = _EMOTION_KEYWORDS.get(emotion, [])
    count = sum(1 for kw in kws if kw in low)
    base  = min(count * 2, 6)

    if text.isupper():                base += 3   # ALL CAPS = very intense
    if "very" in low or "so" in low:  base += 1
    if "extremely" in low:            base += 2
    if text.count("!") >= 2:          base += 1
    if text.count("!") >= 4:          base += 1

    return max(1, min(10, base))


# ══════════════════════════════════════════════════════════
# RESPONSE ADAPTATION
# ══════════════════════════════════════════════════════════

_EMOTION_RESPONSES: dict[str, dict] = {
    "happy"   : {"prefix": "",
                 "tone"  : "Match their energy! Be upbeat and enthusiastic.",
                 "greeting": ["Great to hear!", "Love the positive energy!"]},
    "sad"     : {"prefix": "I can sense you might be going through something tough. ",
                 "tone"  : "Be gentle and supportive. Acknowledge before solving.",
                 "greeting": ["Hey, I'm here for you.", "I'm listening."]},
    "angry"   : {"prefix": "",
                 "tone"  : "Stay calm. Acknowledge frustration briefly.",
                 "greeting": ["I understand that's frustrating.",
                              "Let me help sort this out."]},
    "stressed": {"prefix": "Let me keep this simple: ",
                 "tone"  : "Be concise. Give clear actionable steps.",
                 "greeting": ["Quick answer:", "Here's what you need:"]},
    "tired"   : {"prefix": "",
                 "tone"  : "Very brief. No fluff.",
                 "greeting": ["Quick answer:", "Here you go:"]},
    "confused": {"prefix": "",
                 "tone"  : "Simple language. Analogies. Numbered steps.",
                 "greeting": ["Let me break this down:", "Step by step:"]},
    "excited" : {"prefix": "",
                 "tone"  : "Match excitement! Enthusiastic and informative.",
                 "greeting": ["Awesome, let's go!", "Here we go!"]},
    "grateful": {"prefix": "",
                 "tone"  : "Warm and humble.",
                 "greeting": ["Happy to help!", "That's what I'm here for!"]},
    "bored"   : {"prefix": "",
                 "tone"  : "Suggest something interesting.",
                 "greeting": ["Let me suggest something!", "How about this:"]},
}


def get_emotion_system_addition(emotion: Optional[str], intensity: int = 5) -> str:
    if not emotion or emotion not in _EMOTION_RESPONSES:
        return ""
    tone = _EMOTION_RESPONSES[emotion]["tone"]
    if intensity >= 8:
        extra = (f" User seems VERY {emotion} ({intensity}/10)"
                 f" — prioritise emotional tone.")
    elif intensity >= 5:
        extra = f" User appears {emotion}."
    else:
        extra = ""
    return f"\nEmotion awareness: {tone}{extra}"


def get_emotion_prefix(emotion: Optional[str]) -> str:
    if not emotion or emotion not in _EMOTION_RESPONSES:
        return ""
    return _EMOTION_RESPONSES[emotion].get("prefix", "")


# ══════════════════════════════════════════════════════════
# TIME-AWARE GREETING
# ══════════════════════════════════════════════════════════

_USERNAME = os.getenv("Username", "Siddu")

def get_time_greeting() -> str:
    hour = datetime.datetime.now().hour
    if   5  <= hour < 12: return f"Good morning {_USERNAME}! Ready to take on the day?"
    elif 12 <= hour < 17: return f"Good afternoon {_USERNAME}! How's your day going?"
    elif 17 <= hour < 21: return f"Good evening {_USERNAME}! Productive day?"
    elif 21 <= hour < 24: return f"Hey {_USERNAME}, it's getting late. Need help?"
    else:                  return f"Still up {_USERNAME}? What do you need?"


def get_farewell(emotion: Optional[str] = None) -> str:
    hour = datetime.datetime.now().hour
    if emotion == "tired" or hour >= 22:
        return f"Goodnight {_USERNAME}! Rest well."
    elif emotion == "stressed":
        return f"Take care {_USERNAME}. You've got this!"
    elif emotion == "happy":
        return f"Bye {_USERNAME}! Have a wonderful day!"
    else:
        return f"Goodbye {_USERNAME}! Talk soon."


# ══════════════════════════════════════════════════════════
# TEST SUITE
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        ("I'm so happy today, got selected for internship!", "happy"),
        ("I'm really stressed, exam tomorrow",               "stressed"),
        ("WHAT IS WRONG WITH THIS CODE",                     "angry"),   # was failing
        ("i'm tired, been up since 4am",                     "tired"),
        ("what does polymorphism mean",                      "confused"),
        ("hey",                                              None),
        ("thanks jarvis you saved me!",                      "grateful"),
        ("I'm so bored today",                               "bored"),
        ("I failed my exam",                                 "sad"),     # was failing
        ("can't wait for the results tomorrow!!",            "excited"),
        # Extra edge cases
        ("STOP IT NOW",                                      "angry"),
        ("i failed the test yesterday",                      "sad"),
        ("deadline is tomorrow and i haven't started",       "stressed"),
        ("what is machine learning",                         "confused"),
    ]

    print("\n=== EMOTION DETECTION TEST SUITE ===\n")
    passed = 0
    for text, expected in tests:
        detected  = detect_emotion(text)
        intensity = detect_emotion_intensity(text, detected or "") if detected else 0
        ok        = detected == expected
        if ok: passed += 1
        status = "OK  " if ok else "FAIL"
        print(f"[{status}] '{text[:50]}'")
        print(f"       Expected: {str(expected):<10} Got: {detected}"
              f" (intensity {intensity}/10)\n")

    total = len(tests)
    pct   = 100 * passed // total
    bar   = "#" * passed + "-" * (total - passed)
    print(f"Score: {passed}/{total} = {pct}%  [{bar}]")
    print("\nTime greeting:", get_time_greeting())