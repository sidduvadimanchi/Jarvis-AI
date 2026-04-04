# core/state.py
# Jarvis AI — Global Workflow State Manager
# ─────────────────────────────────────────────────────────────────────────────
import threading
from enum import Enum, auto

class TaskState(Enum):
    IDLE       = auto()  # Waiting for user command
    COLLECTING = auto()  # Actively gathering parameters (e.g. email recipient)
    PROCESSING = auto()  # Executing automation (e.g. sending email)
    COMPLETED  = auto()  # Task finished, showing final results

class WorkflowManager:
    """
    Thread-safe Singleton to manage Jarvis's operational state.
    Prevents context switching and duplicate prompts.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WorkflowManager, cls).__new__(cls)
                cls._instance._init_once()
            return cls._instance

    def _init_once(self):
        self.state = TaskState.IDLE
        self.context = None      # Name of active workflow (e.g. 'email')
        self.tone = "professional"
        self.lock = threading.Lock()

    def set_state(self, state: TaskState):
        with self.lock:
            self.state = state

    def get_state(self) -> TaskState:
        with self.lock:
            return self.state

    def set_context(self, context: str | None):
        with self.lock:
            self.context = context

    def get_context(self) -> str | None:
        with self.lock:
            return self.context

    def set_tone(self, tone: str):
        with self.lock:
            self.tone = tone

    def get_tone(self) -> str:
        with self.lock:
            return self.tone

    def is_locked(self) -> bool:
        """Returns True if a workflow is actively blocking other intents."""
        return self.context is not None and self.state != TaskState.IDLE

# Singleton instance
state_manager = WorkflowManager()
