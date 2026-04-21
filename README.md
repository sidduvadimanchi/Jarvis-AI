# 🤖 Jarvis AI — Voice-Controlled Desktop Assistant
### `VoiceAssistant_JarvisAI_SidduVadimanchi`

> A production-grade, multi-threaded AI desktop assistant built with Python.  
> Understands voice/text commands, automates tasks, answers questions with Groq LLM, and remembers every conversation.

---

## 👨‍💻 Project Details

| Field | Details |
|-------|---------|
| **Student Name** | Siddu Vadimanchi |
| **Roll Number** | BETN1DS23019 |
| **Semester** | 6th Semester |
| **Project Title** | Jarvis AI — Voice-Controlled Desktop Assistant |
| **Tech Stack** | Python 3.10+, Groq LLM, Cohere, Edge-TTS, Pygame, SQLite, Tkinter |

---

## 🎯 What It Does

Jarvis AI is a fully-featured voice and text-controlled desktop assistant that can:

- 🎤 **Listen** to voice commands via microphone (Speech Recognition)
- 🧠 **Understand** intent using Cohere AI + a fast local fallback classifier
- 💬 **Respond** intelligently using Groq (Llama 3.1) with streaming tokens
- 🔊 **Speak** responses aloud with Edge TTS (Microsoft Neural voices)
- 📧 **Send/Read Emails** via Gmail OAuth2 API
- 🌐 **Search** the web — Google, YouTube, real-time news, weather, stocks
- 📅 **Manage** study timetables, assignments, focus mode, reminders
- 💼 **Track Jobs** — GATE PSU alerts, govt jobs, market jobs, deadlines
- 🗂️ **Control Files** — open folders, find files, zip, backup
- 📊 **Monitor System** — RAM/CPU health, app usage, kill heavy processes
- 🧠 **Remember** across sessions using SQLite persistent memory

---

## 🏗️ Architecture

```
Main.py  (Entry Point)
├── Thread 1 (main)   → GUI  [Tkinter — must stay on main thread]
└── Thread 2 (daemon) → Backend Loop
       ├── SpeechRecognition  (interface/stt.py)
       ├── FirstLayerDMM      (core/intent.py)   ← Intent classifier
       ├── ChatBot            (core/chat.py)      ← Groq LLM
       ├── TextToSpeech       (interface/tts.py)  ← Edge TTS + Pygame
       └── Automation         (automation/engine.py)
              └── 18 Modules  (automation/modules/)
```

### Key Modules

| Module | Purpose |
|--------|---------|
| `core/intent.py` | Classifies voice intent using Cohere AI + regex fallback |
| `core/chat.py` | Groq LLM chatbot with emotion detection and memory |
| `core/brain/memory.py` | SQLite persistent memory with WAL mode |
| `core/brain/emotion.py` | Detects user mood and adapts responses |
| `core/state.py` | Thread-safe workflow state machine |
| `interface/stt.py` | Speech-to-Text (mic → text) |
| `interface/tts.py` | Text-to-Speech with audio cache + barge-in |
| `interface/terminal.py` | Tkinter GUI |
| `automation/engine.py` | Master command dispatcher (async parallel execution) |
| `automation/modules/` | 18 automation modules (email, apps, jobs, files, etc.) |

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 (uses Windows APIs for some features)
- Microphone

### 1. Clone the Repository
```bash
git clone https://github.com/sidduvadimanchi/VoiceAssistant_JarvisAI_SidduVadimanchi.git
cd VoiceAssistant_JarvisAI_SidduVadimanchi
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure `.env` File
Create a `.env` file in the root directory:
```env
# Required
GROQ_API_KEY=gsk_your_groq_key_here
Username=Your Name
Assistantname=Jarvis

# Optional but Recommended
CohereAPIKey=your_cohere_key_here
AssistantVoice=en-US-AriaNeural
VoiceRate=+0%
VoicePitch=+0Hz
VoiceVolume=1.0
City=YourCity

# Gmail (for email feature)
GmailUser=your@gmail.com
GmailDisplayName=Your Name
```

> **Get API Keys:**
> - Groq (Free): https://console.groq.com/keys
> - Cohere (Free): https://dashboard.cohere.com/api-keys

### 5. Run
```bash
python Main.py
```

---

## 🗣️ Voice Command Examples

| Voice Command | Action |
|---------------|--------|
| `"Open Chrome"` | Opens Google Chrome |
| `"Play Shape of You"` | Plays on YouTube |
| `"What's the weather in Bhopal?"` | Live weather report |
| `"Send email to professor about assignment"` | Drafts & sends email |
| `"GATE PSU alerts"` | Shows latest PSU recruitments |
| `"Set alarm for 6 AM"` | Sets morning alarm |
| `"What is machine learning?"` | AI explanation |
| `"System health"` | Shows RAM/CPU usage |
| `"Start studying Python"` | Starts study timer |
| `"Show timetable"` | Displays weekly schedule |
| `"Close Jarvis"` | Exits the assistant |

---

## 🔐 Security

- `.env` file is **gitignored** — API keys are never committed
- `credentials.json` (Gmail OAuth) is **gitignored**
- Prompt injection detection built into the chatbot
- Gmail uses OAuth2 — password never stored

---

## 📁 Project Structure

```
Jarvis AI/
├── Main.py                    ← Entry point
├── requirements.txt           ← Python dependencies
├── .env.example               ← Template (copy → .env)
├── core/
│   ├── intent.py              ← Intent classifier (Cohere + fallback)
│   ├── chat.py                ← Groq LLM chatbot
│   ├── state.py               ← Thread-safe state machine
│   └── brain/
│       ├── memory.py          ← SQLite persistent memory
│       ├── emotion.py         ← Emotion detection
│       ├── personality.py     ← Dynamic system prompt builder
│       └── student_brain.py   ← Study-specific intelligence
├── interface/
│   ├── stt.py                 ← Speech-to-Text
│   ├── tts.py                 ← Text-to-Speech (Edge TTS)
│   └── terminal.py            ← Tkinter GUI
├── automation/
│   ├── engine.py              ← Async command dispatcher
│   └── modules/
│       ├── app_control.py     ← Open/Close applications
│       ├── email_system.py    ← Gmail send/read
│       ├── realtime_data.py   ← Weather/News/Stocks
│       ├── advanced_jobs.py   ← GATE PSU / Market jobs
│       ├── alarm_clock.py     ← Alarms and timers
│       ├── focus_mode.py      ← Study focus mode
│       ├── assignment_creator.py ← AI assignment writer
│       └── ...                ← 11 more modules
└── Data/                      ← Runtime data (gitignored)
```

---

## 🐛 Bug Fixes (Professional Audit)

A full code audit was performed identifying and fixing **12 critical bugs**:

| Severity | Count | Fixed |
|----------|-------|-------|
| 🔴 Critical (Crash/Freeze) | 4 | ✅ All Fixed |
| 🟠 High (Silent Failures) | 4 | ✅ All Fixed |
| 🟡 Medium (Performance) | 4 | ✅ All Fixed |

Key fixes:
- **Automation state freeze** — Jarvis no longer gets permanently stuck after errors
- **TTS async deadlock** — Replaced cross-thread asyncio scheduling with `asyncio.run()`
- **SQLite connection leak** — Single persistent WAL-mode connection instead of per-call opens
- **Dead code / NameError** — Removed 40 lines of unreachable code containing undefined `sys_msgs`
- **Groq API rate halved** — Background learning rate-limited to 1-in-5 interactions
- **Adaptive polling** — Backend loop uses 50ms active / 200ms idle instead of always 100ms

---

## 📄 License

MIT License — Free to use, modify, and distribute with attribution.

---

## 🙏 Acknowledgements

- [Groq](https://groq.com) — Ultra-fast LLM inference
- [Cohere](https://cohere.com) — Intent classification
- [Microsoft Edge TTS](https://github.com/rany2/edge-tts) — Neural voice synthesis
- [OpenAI Whisper](https://github.com/openai/whisper) — Speech recognition backbone

---

*Built with ❤️ by Siddu Vadimanchi | BETN1DS23019 | 6th Semester*
