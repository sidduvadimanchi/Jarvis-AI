# Backend/Automation/media_control.py
# Jarvis AI — Media & Search Control
# ─────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   ✅ Play songs on YouTube
#   ✅ Google search
#   ✅ YouTube search
#   ✅ Open specific YouTube channels
#   ✅ Pause/resume media (keyboard)
#   ✅ 8GB RAM safe
#
# VOICE COMMANDS:
#   "play aashiq banaya aapne"
#   "play despacito"
#   "google search python tutorials"
#   "youtube search machine learning"
#   "next song" / "pause music"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import webbrowser
import requests
import keyboard  # type: ignore
from pywhatkit import search, playonyt  # type: ignore


def PlayYoutube(query: str) -> bool:
    """
    Play a song/video on YouTube.
    Voice: "play despacito", "play aashiq banaya aapne"
    """
    try:
        print(f"[cyan]Playing on YouTube:[/cyan] {query}")
        playonyt(query)
        return True
    except Exception as e:
        # Fallback: open YouTube search
        try:
            url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
            webbrowser.open(url)
            print(f"[yellow]Fallback: opened YouTube search for '{query}'[/yellow]")
            return True
        except Exception as e2:
            print(f"[red]PlayYoutube failed:[/red] {e2}")
            return False


def GoogleSearch(topic: str) -> bool:
    """
    Search Google for a topic.
    Voice: "google search python tutorials"
    """
    try:
        search(topic)
        print(f"[cyan]Google search:[/cyan] {topic}")
        return True
    except Exception:
        try:
            url = f"https://www.google.com/search?q={requests.utils.quote(topic)}"
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"[red]GoogleSearch failed:[/red] {e}")
            return False


def YouTubeSearch(topic: str) -> bool:
    """
    Search YouTube for a topic (without auto-playing).
    Voice: "youtube search machine learning tutorials"
    """
    try:
        url = f"https://www.youtube.com/results?search_query={requests.utils.quote(topic)}"
        webbrowser.open(url)
        print(f"[cyan]YouTube search:[/cyan] {topic}")
        return True
    except Exception as e:
        print(f"[red]YouTubeSearch failed:[/red] {e}")
        return False


def MediaControl(command: str) -> bool:
    """
    Control media playback using keyboard shortcuts.
    Voice: "pause", "resume", "next song", "previous song"
    """
    cmd = command.lower().strip()
    media_map = {
        "pause":          "play/pause media",
        "resume":         "play/pause media",
        "play pause":     "play/pause media",
        "next":           "next track",
        "next song":      "next track",
        "previous":       "prev track",
        "previous song":  "prev track",
        "stop music":     "stop media",
    }
    if cmd in media_map:
        try:
            keyboard.press_and_release(media_map[cmd])
            print(f"[green]Media:[/green] {cmd}")
            return True
        except Exception as e:
            print(f"[red]Media control failed:[/red] {e}")
            return False
    print(f"[yellow]MediaControl: unknown '{command}'[/yellow]")
    return False