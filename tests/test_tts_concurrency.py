import threading
import time
import sys
import os

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interface.tts import TextToSpeech

def test_overlap():
    print("\n--- TTS CONCURRENCY TEST ---")
    print("Testing 'Barge-in' (Interrupt) logic...")
    
    def speak_1():
        print("[Thread 1] Starting long speech...")
        TextToSpeech("This is a very long sentence designed to test if the second thread can correctly interrupt the first voice stream without causing any overlapping audio artifacts.")

    def speak_2():
        time.sleep(1) # Wait for thread 1 to start
        print("[Thread 2] Interrupting with short speech...")
        TextToSpeech("RESTORATION COMPLETE.")

    t1 = threading.Thread(target=speak_1)
    t2 = threading.Thread(target=speak_2)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
    print("--- TEST FINISHED ---\n")

if __name__ == "__main__":
    test_overlap()
