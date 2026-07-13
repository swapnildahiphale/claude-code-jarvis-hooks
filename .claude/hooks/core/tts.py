import os
import subprocess

from core.paths import tts_dir


def get_tts_script_path() -> str | None:
    td = tts_dir()
    if os.getenv("ELEVENLABS_API_KEY"):
        p = td / "elevenlabs_tts.py"
        if p.exists():
            return str(p)
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        p = td / "openai_tts.py"
        if p.exists():
            return str(p)
    p = td / "pyttsx3_tts.py"
    return str(p) if p.exists() else None


def speak(text: str, timeout: int = 10) -> None:
    try:
        script = get_tts_script_path()
        if not script or not text.strip():
            return
        subprocess.run(
            ["uv", "run", script, text],
            capture_output=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
