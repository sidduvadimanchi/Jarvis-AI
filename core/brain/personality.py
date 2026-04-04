# Backend/Brain/personality.py
# Jarvis AI — Human-like Personality System
# Builds dynamic system prompt using memory + emotion + time context
# ─────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

_USERNAME      = os.getenv("Username",      "Siddu")
_ASSISTANTNAME = os.getenv("Assistantname", "Jarvis")

# Base personality — never changes
_BASE_PROMPT = f"""Your name is {_ASSISTANTNAME}. You are {_USERNAME}'s personal AI assistant — intelligent, human-like, and deeply aware.

PERSONALITY:
- You speak like a smart, caring friend — not a robot
- You remember context from earlier in the conversation and from past sessions
- You notice how the user is feeling and adapt your tone accordingly
- You are proactive: if user seems stressed or tired, you acknowledge it
- You are concise by default (2-3 sentences) but go deep when asked
- You NEVER say "As an AI..." or add disclaimers
- You NEVER repeat the question back
- You use the user's name naturally (not every sentence — that's annoying)
- When the user says hi/hello — you greet warmly and ask what's on their mind
- When the user says bye/goodbye/goodnight — you respond with a warm farewell
- You think before answering: for complex questions, briefly show your reasoning

CONVERSATION RULES:
- If user greets: respond with time-aware greeting + one genuine question
- If user is emotional: acknowledge emotion FIRST, then answer
- If user asks something vague: ask one clarifying question
- If user seems confused: break answer into clear numbered steps
- If user says thanks: accept warmly, don't say "you're welcome" robotically
- If it's late (after 10pm): occasionally suggest rest naturally

ANSWER STYLE:
- Short questions → 1-3 sentence answer
- Technical questions → structured, use steps or bullets if helpful  
- Emotional support → warm, unhurried, no list format
- Complex analysis → "Let me think through this..." then reason step by step
"""


def build_system_prompt(
    emotion         : Optional[str]  = None,
    emotion_intensity: int           = 0,
    memory_context  : str            = "",
    recent_topics   : list[str]      = [],
    is_late_night   : bool           = False,
) -> str:
    """
    Build a complete, dynamic system prompt for this conversation turn.

    Parameters
    ----------
    emotion          : detected user emotion
    emotion_intensity: 1-10 scale
    memory_context   : string from memory.build_memory_context()
    recent_topics    : topics discussed recently
    is_late_night    : True if hour >= 22

    Returns
    -------
    str — full system prompt ready for Groq
    """
    parts = [_BASE_PROMPT]

    # Memory context (past sessions, user facts)
    if memory_context:
        parts.append(f"\nMEMORY CONTEXT:\n{memory_context}")

    # Recent topics for continuity
    if recent_topics:
        topics_str = ", ".join(recent_topics[-5:])
        parts.append(f"\nRecent conversation topics: {topics_str}.")

    # Emotion adaptation
    if emotion and emotion_intensity >= 3:
        emotion_instructions = {
            "stressed" : "User is stressed. Be BRIEF. Give direct answers. Skip pleasantries.",
            "tired"    : "User is tired. Ultra short answers. No fluff whatsoever.",
            "sad"      : "User seems sad. Acknowledge their feeling gently before answering.",
            "angry"    : "User is frustrated. Stay calm. Acknowledge their frustration in one sentence.",
            "confused" : "User is confused. Use SIMPLE words. Numbered steps. Analogies.",
            "happy"    : "User is happy. Match their positive energy.",
            "excited"  : "User is excited. Be enthusiastic and engaged.",
        }
        instruction = emotion_instructions.get(emotion, "")
        if instruction:
            parts.append(f"\nEMOTION AWARENESS: {instruction}")

    # Late night awareness
    if is_late_night:
        parts.append(
            f"\nLATE NIGHT: It's late. If appropriate, gently suggest {_USERNAME} should rest soon."
        )

    # Date/time awareness
    now = datetime.datetime.now()
    parts.append(
        f"\nCurrent time: {now.strftime('%A, %d %B %Y, %I:%M %p')}."
    )

    return "\n".join(parts)


def extract_topics(text: str) -> list[str]:
    """
    Extract key topic words from a conversation turn.
    Used to build topic continuity context.

    Parameters
    ----------
    text : str

    Returns
    -------
    list[str] — up to 3 topic keywords
    """
    import re
    # Remove common stopwords
    stopwords = {
        "the","a","an","is","are","was","were","be","been","being",
        "have","has","had","do","does","did","will","would","could",
        "should","may","might","shall","can","need","dare","ought",
        "i","you","he","she","they","we","it","this","that","these",
        "those","what","which","who","whom","whose","when","where",
        "why","how","me","my","your","his","her","their","our","its",
        "and","or","but","if","then","else","so","yet","both","either",
        "neither","not","no","nor","as","at","by","for","in","of",
        "on","to","up","with","from","into","through","during",
        "please","just","also","about","tell","jarvis","help",
    }
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    topics = [w for w in words if w not in stopwords]
    # Return up to 3 most relevant (last occurrence wins context)
    seen = []
    for w in reversed(topics):
        if w not in seen:
            seen.append(w)
        if len(seen) >= 3:
            break
    return seen