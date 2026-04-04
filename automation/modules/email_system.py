# Backend/Automation/email_system.py
# Jarvis AI — Gmail OAuth2 (Login Once, Works Forever)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import base64
import datetime
import logging
import os
import re
import sys
from email.mime.base      import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email                import encoders
from pathlib              import Path
from typing               import List, Optional

from dotenv import dotenv_values

try:
    from .notifier import notify
except ImportError:
    def notify(t, m): pass

from core.state import state_manager, TaskState

log = logging.getLogger("email_system")
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s | %(name)s | %(message)s")

# ── Fix working directory when run directly from subfolder ────────────────────
if __name__ == "__main__":
    _script = os.path.dirname(os.path.abspath(__file__))
    _root   = os.path.join(_script, "..", "..")
    os.chdir(_root)

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
_env = dotenv_values(".env")

GMAIL_USER   : str  = _env.get("GmailUser","") or _env.get("EmailAddress","")
DISPLAY_NAME : str  = _env.get("GmailDisplayName","") or _env.get("Username","")
SIGNATURE    : str  = _env.get("GmailSignature","")
USERNAME     : str  = _env.get("Username","User")
GROQ_KEY     : str  = _env.get("GroqAPIKey","") or _env.get("GROQ_API_KEY","")
GROQ_MODEL   : str  = _env.get("GroqModel","llama-3.1-8b-instant")

DATA_DIR     : Path = Path(_env.get("DataDir","Data"))
SENT_DIR     : Path = DATA_DIR / "sent_emails"
TOKEN_FILE   : Path = DATA_DIR / "gmail_token.json"
CREDS_FILE   : Path = Path("credentials.json")

SENT_DIR.mkdir(parents=True, exist_ok=True)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

CONTACTS: dict[str, str] = {}
for k, v in _env.items():
    if k.lower().startswith("contact_"):
        CONTACTS[k[8:].lower()] = v

LINE  = "─" * 58
DLINE = "═" * 58

TONE_DESCRIPTIONS = {
    "professional" : "Business/client — polished and concise",
    "friendly"     : "Casual — friends or familiar colleagues",
    "formal"       : "Official — university, government, legal",
    "followup"     : "Following up on a previous message",
    "apology"      : "Apologising for something",
    "request"      : "Politely requesting something",
}
TONE_PROMPTS = {
    "professional": "Write a professional business email. Tone: confident, respectful, concise.",
    "friendly"    : "Write a warm friendly email. Tone: casual but polite, use first names.",
    "formal"      : "Write a strictly formal official letter. No contractions. Begin with Dear Sir/Madam.",
    "followup"    : "Write a professional follow-up email. Reference the previous conversation politely.",
    "apology"     : "Write a sincere professional apology email. Acknowledge issue and offer resolution.",
    "request"     : "Write a polite request email. State what is needed, why, and by when.",
}


# ══════════════════════════════════════════════════════════
# OAUTH2
# ══════════════════════════════════════════════════════════

def _get_gmail_service():
    try:
        from google.oauth2.credentials         import Credentials
        from google.auth.transport.requests    import Request
        from google_auth_oauthlib.flow         import InstalledAppFlow
        from googleapiclient.discovery         import build
    except ImportError:
        _show_install_guide()
        return None

    if not CREDS_FILE.exists():
        _show_credentials_guide()
        return None

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                log.info("Gmail token refreshed automatically")
            except Exception:
                creds = None

        if not creds:
            print(f"\n  {DLINE}")
            print("  GMAIL LOGIN  —  One-time setup")
            print(f"  {DLINE}")
            print("  A browser will open. Login with your Gmail account.")
            print(f"  Account: {GMAIL_USER or 'your gmail'}")
            print("  After login, this window closes automatically.")
            print("  You will NEVER need to login again.\n")
            input("  Press Enter to open browser... ")

            flow  = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            print("\n  Login successful! Token saved.\n")

        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        log.info("Gmail token saved: %s", TOKEN_FILE)

    try:
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        print(f"\n  ERROR building Gmail service: {e}\n")
        return None


def _show_install_guide():
    print(f"\n  {DLINE}")
    print("  Gmail libraries not installed")
    print(f"  {DLINE}")
    print("\n  Run this command:\n")
    print("  pip install google-auth google-auth-oauthlib google-api-python-client\n")
    print(f"  {DLINE}\n")


def _show_credentials_guide():
    print(f"\n  {DLINE}")
    print("  credentials.json not found")
    print(f"  {DLINE}")
    print("""
  HOW TO GET credentials.json  (one time only — 3 minutes)
  ─────────────────────────────────────────────────────────
  STEP 1: Go to → https://console.cloud.google.com
  STEP 2: Create project → name it "Jarvis" → Create
  STEP 3: Search "Gmail API" → Enable
  STEP 4: APIs & Services → Credentials
          → Create Credentials → OAuth Client ID
          → Application type: Desktop App
          → Name: Jarvis → Create
  STEP 5: Download → save as credentials.json
          → Put in: D:\\Jarvis ai\\credentials.json
  STEP 6: Run this file again → browser opens → login once
  ─────────────────────────────────────────────────────────
""")
    guide_path = Path("GMAIL_SETUP_GUIDE.txt")
    guide_path.write_text("""
JARVIS GMAIL SETUP
==================
STEP 1: pip install google-auth google-auth-oauthlib google-api-python-client
STEP 2: Go to https://console.cloud.google.com
        Create Project → Jarvis
        Enable Gmail API
        Credentials → OAuth Client ID → Desktop App
        Download → credentials.json → put in D:\\Jarvis ai\\
STEP 3: Add to .env:
        GmailUser=youremail@gmail.com
        GmailDisplayName=Your Name
        GmailSignature=B.Tech CSE | University
        Contact_professor=prof@college.edu
STEP 4: python email_system.py → browser opens → login once → done!
""", encoding="utf-8")
    print("  Guide saved to: GMAIL_SETUP_GUIDE.txt\n")


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def _ask(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def _is_email(text: str) -> bool:
    return bool(re.match(r"^[\w.+-]+@[\w.-]+\.\w{2,}$", text.strip()))


def _resolve(text: str) -> str:
    key = text.lower().strip()
    if key in CONTACTS:
        email = CONTACTS[key]
        print(f"  Contact: {key} -> {email}")
        return email
    return text


def _collect_emails(title: str, required: bool = True) -> List[str]:
    emails: List[str] = []
    num = 1
    print(f"\n  {LINE}")
    print(f"  {title}")
    print(f"  {LINE}")
    if CONTACTS:
        print(f"  Saved contacts: {', '.join(CONTACTS.keys())}")
    if not required:
        print("  (Optional — press Enter to skip)\n")
    else:
        print("  One email per line. Type DONE when finished.\n")

    while True:
        raw = _ask(f"  Email {num}: ").strip()
        if raw.lower() in ("done", "finish", "no", "skip", ""):
            if not emails and required:
                print("  Need at least one recipient.")
                continue
            break
        resolved = _resolve(raw)
        if not _is_email(resolved):
            print(f"  Not a valid email: '{raw}'")
            print("  Example: someone@gmail.com")
            continue
        emails.append(resolved)
        print(f"  Added: {resolved}")
        num += 1
    return emails


def _collect_files() -> List[Path]:
    files: List[Path] = []
    num   = 1
    search = [
        Path.cwd(),
        Path.home() / "Desktop",
        Path.home() / "Downloads",
        Path.home() / "Documents",
        DATA_DIR / "Assignments",
        DATA_DIR / "Notes",
        DATA_DIR / "Reports",
    ]
    print(f"\n  {LINE}")
    print("  ATTACH FILES  (optional)")
    print(f"  {LINE}")
    print("  Type filename — searches Desktop, Downloads, Documents\n")

    while True:
        ans = _ask(f"  File {num} (Enter to skip): ")
        if ans.lower() in ("done", "no", "skip", ""):
            break
        found: Optional[Path] = None
        p = Path(ans)
        if p.exists() and p.is_file():
            found = p
        else:
            for folder in search:
                c = folder / ans
                if c.exists() and c.is_file():
                    found = c
                    break
        if found:
            files.append(found)
            print(f"  Attached: {found.name}  ({found.stat().st_size // 1024} KB)")
            num += 1
        else:
            print(f"  Not found: {ans}")
    return files


def _build_signature() -> str:
    parts = []
    if DISPLAY_NAME: parts.append(DISPLAY_NAME)
    if SIGNATURE:    parts.append(SIGNATURE)
    if GMAIL_USER and DISPLAY_NAME: parts.append(GMAIL_USER)
    return "\n\nBest regards,\n" + "\n".join(parts) if parts else f"\n\nBest regards,\n{USERNAME}"


def _select_tone(voice_cmd: str = "") -> str:
    cmd = voice_cmd.lower()
    tone_map = {
        "professional": ["client","business","work","office","company","professional"],
        "friendly"    : ["friend","buddy","casual","friendly"],
        "formal"      : ["formal","government","official","authority"],
        "followup"    : ["follow","remind","reminder","followup"],
        "apology"     : ["sorry","apologize","apology","mistake"],
        "request"     : ["request","ask","require","need help"],
    }
    for tone, keywords in tone_map.items():
        if any(k in cmd for k in keywords):
            print(f"  Tone auto-detected: {tone.upper()}")
            return tone

    print(f"\n  {LINE}")
    print("  EMAIL TONE — What kind of email?")
    print(f"  {LINE}\n")
    for i, (tone, desc) in enumerate(TONE_DESCRIPTIONS.items(), 1):
        print(f"  [{i}]  {tone.upper():<15} {desc}")
    print(f"\n  {LINE}")
    choice = _ask("\n  Choose [1-6] (Enter = Professional): ", "1")
    tones  = list(TONE_DESCRIPTIONS.keys())
    try:
        return tones[int(choice) - 1]
    except Exception:
        return "professional"


def _ai_write_body(subject: str, tone: str, context: str, recipient: str) -> str:
    system = TONE_PROMPTS.get(tone, TONE_PROMPTS["professional"])
    if not GROQ_KEY:
        return (f"Dear {recipient},\n\nI am writing regarding: {context or subject}.\n\n"
                f"Please let me know if you need anything further." + _build_signature())
    try:
        from groq import Groq
        resp = Groq(api_key=GROQ_KEY).chat.completions.create(
            model    = GROQ_MODEL,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content":
                    f"Subject: {subject}\nSender: {DISPLAY_NAME or USERNAME}\n"
                    f"Recipient: {recipient}\nContext: {context or 'None'}\n"
                    "Write email body only. Include greeting and content. "
                    "No subject line. No signature (added automatically)."},
            ],
            max_tokens=300, temperature=0.6,
        )
        body = resp.choices[0].message.content.strip()
        return body + _build_signature()
    except Exception as e:
        log.warning("AI failed: %s", e)
        return (f"Dear {recipient},\n\n{context or subject}." + _build_signature())


# ══════════════════════════════════════════════════════════
# SEND VIA GMAIL API
# ══════════════════════════════════════════════════════════

def _send_via_api(
    service,
    to_list     : List[str],
    subject     : str,
    body        : str,
    cc_list     : List[str]  = [],
    bcc_list    : List[str]  = [],
    attach_files: List[Path] = [],
) -> bool:
    try:
        from_header  = f"{DISPLAY_NAME} <{GMAIL_USER}>" if DISPLAY_NAME else GMAIL_USER
        msg          = MIMEMultipart()
        msg["From"]  = from_header
        msg["To"]    = ", ".join(to_list)
        msg["Subject"] = subject
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

        msg.attach(MIMEText(body, "plain", "utf-8"))

        for fpath in attach_files:
            try:
                with open(fpath, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition",
                                f'attachment; filename="{fpath.name}"')
                msg.attach(part)
            except Exception as e:
                print(f"  Could not attach {fpath.name}: {e}")

        raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {"raw": raw}
        service.users().messages().send(userId="me", body=message).execute()

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        (SENT_DIR / f"email_{ts}.txt").write_text(
            f"FROM    : {from_header}\n"
            f"TO      : {', '.join(to_list)}\n"
            f"CC      : {', '.join(cc_list)  or 'None'}\n"
            f"BCC     : {', '.join(bcc_list) or 'None'}\n"
            f"SUBJECT : {subject}\n"
            f"FILES   : {', '.join(f.name for f in attach_files) or 'None'}\n"
            f"SENT    : {datetime.datetime.now().strftime('%d %B %Y %I:%M %p')}\n"
            f"{'─'*50}\n\n{body}",
            encoding="utf-8",
        )
        log.info("Email sent | to=%s", to_list)
        return True

    except Exception as e:
        log.error("Gmail API send failed: %s", e)
        print(f"\n  Send failed: {e}\n")
        return False


# ══════════════════════════════════════════════════════════
# MAIN COMPOSER
# ══════════════════════════════════════════════════════════

    print(f"  Connected to Gmail as {GMAIL_USER}\n")

    # [TASK 1/3] State & Context Locking
    state_manager.set_context("email")
    state_manager.set_tone("professional") # Force professional tone for email
    state_manager.set_state(TaskState.COLLECTING)

    try:
        # ── STEP 1: RECIPIENTS ────────────────────────────────
        print("  STEP 1 — WHO are you sending to?")
        print(f"  {LINE}")

        hint = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", params) if params else []
        if hint:
            print(f"\n  Detected from voice: {', '.join(hint)}")
            use = _ask("  Use these? (yes/no): ", "yes").lower()
            to_list = hint if use in ("yes", "y", "") else _collect_emails("TO — Recipients")
        else:
            to_list = _collect_emails("TO — Recipients")

        if not to_list:
            print("\n  No recipients. Cancelled.\n")
            return False

        # ── STEP 2: TONE ──────────────────────────────────────
        print(f"\n  STEP 2 — TONE")
        print(f"  {LINE}")
        tone = _select_tone(params)
        print(f"  Tone: {tone.upper()}")

        # ── STEP 3: CC / BCC ──────────────────────────────────
        cc_list : List[str] = []
        bcc_list: List[str] = []
        if _ask("\n  Add CC? (yes/no): ", "no").lower() in ("yes", "y"):
            cc_list  = _collect_emails("CC — Visible copies", required=False)
        if _ask("  Add BCC? (yes/no): ", "no").lower() in ("yes", "y"):
            bcc_list = _collect_emails("BCC — Hidden copies", required=False)

        # ── STEP 4: SUBJECT ───────────────────────────────────
        lc        = params.lower()
        hint_subj = params[lc.index(" about ") + 7:].strip().title() if " about " in lc else ""
        if hint_subj:
            print(f"\n  Detected subject: '{hint_subj}'")
            subject = _ask("  Subject (Enter to use above): ") or hint_subj
        else:
            subject = _ask("\n  Subject: ") or "Message from Jarvis"
        print(f"  Subject: {subject}")

        # ── STEP 5: ATTACHMENTS ───────────────────────────────
        attachments: List[Path] = []
        if _ask("\n  Attach files? (yes/no): ", "no").lower() in ("yes", "y"):
            attachments = _collect_files()

        # ── STEP 6: BODY ──────────────────────────────────────
        print(f"\n  STEP 6 — MESSAGE")
        print(f"  {LINE}")
        print(f"  Press Enter for AI ({tone} tone)")
        print("  Or type your message (DONE to finish)\n")

        recipient_name = to_list[0].split("@")[0].replace(".", " ").title()
        first = _ask("  Your message (Enter for AI): ")

        if not first or first.lower() in ("ai", "auto", "write", ""):
            print(f"\n  Writing {tone} email with AI...")
            body = _ai_write_body(subject, tone, params, recipient_name)
            print("  Done!\n")
        else:
            lines = [first]
            while True:
                line = _ask("  > ")
                if line.lower() in ("done", "finish", "send", ""):
                    break
                lines.append(line)
            body = "\n".join(lines)
            if not any(c in body.lower() for c in ["regards", "sincerely", "thanks"]):
                body += _build_signature()

        # ── PREVIEW ───────────────────────────────────────────
        print(f"\n  {DLINE}")
        print("  PREVIEW")
        print(f"  {DLINE}")
        print(f"  From    : {DISPLAY_NAME or USERNAME} <{GMAIL_USER}>")
        print(f"  To      : {', '.join(to_list)}")
        if cc_list:     print(f"  CC      : {', '.join(cc_list)}")
        if bcc_list:    print(f"  BCC     : {', '.join(bcc_list)}")
        print(f"  Subject : {subject}")
        print(f"  Tone    : {tone.upper()}")
        if attachments: print(f"  Files   : {', '.join(f.name for f in attachments)}")
        print(f"  {LINE}")
        for line in body.split("\n"):
            print(f"  {line}")
        print(f"\n  {DLINE}\n")

        # ── CONFIRM ───────────────────────────────────────────
        if _ask("  Send? (yes/no): ", "no").lower() not in ("yes", "y", "send", "ok"):
            print("\n  Cancelled.\n")
            return False

        print("\n  Sending via Gmail API...")
        state_manager.set_state(TaskState.PROCESSING)
        ok = _send_via_api(service, to_list, subject, body,
                           cc_list, bcc_list, attachments)

        if ok:
            print(f"\n  {DLINE}")
            print("  EMAIL SENT!")
            print(f"  {DLINE}")
            print(f"  From        : {DISPLAY_NAME} <{GMAIL_USER}>")
            print(f"  Recipients  : {len(to_list)}")
            if attachments:
                print(f"  Attachments : {len(attachments)}")
            print(f"  Saved copy  : Data/sent_emails/")
            print(f"  {DLINE}\n")
            notify("Jarvis — Email Sent!",
                   f"To: {', '.join(to_list[:2])}\nSubject: {subject}")
        
    finally:
        # [TASK 1/3] Cleanup
        state_manager.set_context(None)
        state_manager.set_state(TaskState.IDLE)

    return ok


# ══════════════════════════════════════════════════════════
# VOICE COMMAND HANDLER  (called by AutomationEngine)
# ══════════════════════════════════════════════════════════

def handle_email_command(command: str = "") -> bool:
    """Called by AutomationEngine for voice commands."""
    return SendEmail(params=command)


# ══════════════════════════════════════════════════════════
# DIRECT TERMINAL ENTRY POINT  ← THIS IS WHAT WAS MISSING
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Optional: pass voice command as argument
    # python email_system.py "send email to professor about assignment"
    voice_cmd = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""

    print("\n" + "═" * 58)
    print("  JARVIS EMAIL SYSTEM — Terminal Mode")
    print("═" * 58)

    if voice_cmd:
        print(f"\n  Voice command: '{voice_cmd}'")

    try:
        result = SendEmail(params=voice_cmd)
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n  Cancelled.\n")
        sys.exit(0)