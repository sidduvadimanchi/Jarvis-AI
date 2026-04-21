import os
import sys
from pathlib import Path

# Add project root to sys.path
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.chat import ChatBot, flush_chatbot

def test_chatbot():
    print("\n--- Testing Emoji Integration ---")
    resp1 = ChatBot("Hello Jarvis, how are you feeling today?")
    print(f"Jarvis: {resp1}")
    
    print("\n--- Testing Knowledge Extraction (Simulated) ---")
    # Tell Jarvis something new and concrete
    fact = "I am a CSE student and my enroll no is 0101CS221001. I love reading about quantum computing."
    print(f"User: {fact}")
    ChatBot(fact)
    
    print("\n--- Waiting for Brain to Process (7s) ---")
    import time
    time.sleep(7)
    
    print("\n--- Checking Database ---")
    import sqlite3
    conn = sqlite3.connect('d:/Jarvis ai/Data/jarvis_memory.db')
    cur = conn.cursor()
    cur.execute('SELECT topic, content FROM knowledge')
    rows = cur.fetchall()
    print(f"DB Knowledge Rows: {rows}")
    conn.close()

    print("\n--- Testing Knowledge Recall ---")
    resp2 = ChatBot("What is my enrollment number and what do I like?")
    print(f"Jarvis: {resp2}")

if __name__ == "__main__":
    try:
        test_chatbot()
    finally:
        flush_chatbot()
