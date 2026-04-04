# Backend/Brain/__init__.py
# Safe imports — Brain modules load gracefully even if DB not ready
try:
    from .memory      import save_turn, get_recent, build_memory_context, save_user_fact, get_user_fact
    from .emotion     import detect_emotion, detect_emotion_intensity, get_emotion_system_addition, get_emotion_prefix, get_time_greeting, get_farewell
    from .personality import build_system_prompt, extract_topics
    from .self_upgrade import run_startup_upgrade_check
    _brain_loaded = True
except Exception as e:
    import logging
    logging.getLogger("jarvis.brain").warning("Brain module load error: %s", e)
    _brain_loaded = False