import time
import sys
from pathlib import Path

# Add project root to sys.path
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from automation.modules.app_control import OpenApp, CloseApp

def benchmark():
    print("\n--- Benchmarking OpenApp('instagram') ---")
    start = time.time()
    OpenApp("instagram")
    end = time.time()
    print(f"Time taken: {end-start:.4f}s")
    
    # Give some time for browser to start (simulated)
    time.sleep(3)
    
    print("\n--- Benchmarking CloseApp('instagram') ---")
    start = time.time()
    result = CloseApp("instagram")
    end = time.time()
    print(f"Time taken: {end-start:.4f}s")
    print(f"Success: {result}")

if __name__ == "__main__":
    benchmark()
