# Backend/Automation/whatsapp_system.py
# Jarvis AI — WhatsApp Messaging
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Send message by phone number
#   ✅ Send message by contact name (from contacts dict)
#   ✅ Scheduled messages (X minutes from now)
#   ✅ AI-generated message if no text given
#   ✅ 8GB RAM safe
#
# SETUP:
#   Add contacts to WHATSAPP_CONTACTS below
#   Phone numbers must include country code (91 for India)
#
# VOICE COMMANDS:
#   "whatsapp to 919876543210 message hello how are you"
#   "whatsapp to rahul message meeting at 5pm"
#   "send whatsapp to mom message I'll be late"
#   "whatsapp to 919876543210 message hi"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import datetime
import webbrowser
import requests
from typing import Optional

from dotenv import dotenv_values
from .notifier import notify

_env     = dotenv_values(".env")
GROQ_KEY = _env.get("GroqAPIKey") or _env.get("GROQ_API_KEY", "")
GROQ_MODEL = _env.get("GroqModel", "llama-3.1-8b-instant")

# ─────────────────────────────────────────────────────────────────────────────
# Add your contacts here — name (lowercase) → phone with country code
# India country code = 91
# ─────────────────────────────────────────────────────────────────────────────
WHATSAPP_CONTACTS: dict[str, str] = {
     "rajsheaker":  "919392149550",
    # "mom":    "919876543211",
    # "dad":    "919876543212",
    # "team":   "919876543213",
    # Add your contacts here ↑
}


def _normalize_number(number: str) -> str:
    """Ensure number has + prefix and country code."""
    num = number.strip().replace(" ", "").replace("-", "")
    if not num.startswith("+"):
        if num.startswith("91") and len(num) == 12:
            num = "+" + num
        elif len(num) == 10:
            num = "+91" + num  # assume India
        else:
            num = "+" + num
    return num


def _resolve_contact(name: str) -> Optional[str]:
    """Resolve contact name to phone number."""
    low = name.lower().strip()
    # Direct number
    digits = low.replace("+", "").replace(" ", "")
    if digits.isdigit():
        return _normalize_number(low)
    # Contacts dict
    return WHATSAPP_CONTACTS.get(low)


def _ai_message(topic: str) -> str:
    """Generate a short WhatsApp message using AI."""
    if not GROQ_KEY:
        return topic
    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=GROQ_KEY)
        resp   = client.chat.completions.create(
            model    = GROQ_MODEL,
            messages = [{"role": "user", "content":
                f"Write a short, friendly WhatsApp message about: {topic}. "
                "Max 2 sentences. No quotes."}],
            max_tokens  = 100,
            temperature = 0.7,
            stream      = False,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return topic


def SendWhatsApp(params: str) -> bool:
    """
    Send a WhatsApp message.

    Formats:
      "to 919876543210 message hello"
      "to rahul message project meeting at 5pm"
      "to mom message I'll be home late"

    Voice: "whatsapp to rahul message hi how are you"
    """
    try:
        import pywhatkit as pwk  # type: ignore

        lc      = params.lower()
        contact = ""
        message = ""

        # Parse "to X message Y"
        if " to " in lc:
            after = params[lc.index(" to ") + 4:].strip()
            if " message " in after.lower():
                idx     = after.lower().index(" message ")
                contact = after[:idx].strip()
                message = after[idx + 9:].strip()
            else:
                contact = after.strip()
        elif " message " in lc:
            idx     = lc.index(" message ")
            contact = params[:idx].strip()
            message = params[idx + 9:].strip()

        if not contact:
            print("[yellow]WhatsApp: no contact specified.[/yellow]")
            print("[yellow]Say: whatsapp to <name/number> message <text>[/yellow]")
            return False

        # Generate message if not provided
        if not message:
            message = _ai_message(f"hello from Jarvis AI")

        number = _resolve_contact(contact)

        if number:
            # Send via pywhatkit (2 minutes from now)
            now = datetime.datetime.now()
            send_hour   = now.hour
            send_minute = now.minute + 2
            if send_minute >= 60:
                send_hour   = (send_hour + 1) % 24
                send_minute = send_minute - 60

            print(f"[cyan]Sending WhatsApp to {number}:[/cyan] {message}")
            pwk.sendwhatmsg(
                number,
                message,
                send_hour,
                send_minute,
                wait_time = 15,
                tab_close = True,
                close_time= 3,
            )
            notify("Jarvis — WhatsApp ✅", f"Sent to {contact}: {message[:50]}")
            return True

        else:
            # No number found — open WhatsApp Web with message pre-filled
            print(f"[yellow]Contact '{contact}' not in contacts dict.[/yellow]")
            print(f"[yellow]Add it to WHATSAPP_CONTACTS in whatsapp_system.py[/yellow]")
            url = f"https://web.whatsapp.com/send?text={requests.utils.quote(message)}"
            webbrowser.open(url)
            notify("Jarvis — WhatsApp", f"Opened WhatsApp Web. Find {contact} and send.")
            return True

    except ImportError:
        print("[red]pywhatkit not installed.[/red] Run: pip install pywhatkit")
        return False
    except Exception as e:
        print(f"[red]WhatsApp failed:[/red] {e}")
        return False