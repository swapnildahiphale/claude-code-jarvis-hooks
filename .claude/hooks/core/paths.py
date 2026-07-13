from pathlib import Path


def hooks_root() -> Path:
    return Path(__file__).resolve().parent.parent


def tts_dir() -> Path:
    return hooks_root() / "utils" / "tts"


def llm_dir() -> Path:
    return hooks_root() / "utils" / "llm"
