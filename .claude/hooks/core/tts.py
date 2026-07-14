import os
import shutil
import subprocess
from pathlib import Path

from core.paths import tts_dir

_WORKER = Path(__file__).resolve().parent / "jarvis_say_worker.py"


def local_tts_enabled() -> bool:
    """True when JARVIS_USE_LOCAL_TTS is set to a truthy value."""
    raw = os.getenv("JARVIS_USE_LOCAL_TTS", "").strip().lower()
    return raw in ("true", "1", "yes")


def jarvis_say_path() -> str | None:
    override = os.getenv("JARVIS_SAY_PATH", "").strip()
    if override and Path(override).is_file():
        return override
    return shutil.which("jarvis-say")


def cloud_tts_available() -> bool:
    td = tts_dir()
    if os.getenv("ELEVENLABS_API_KEY") and (td / "elevenlabs_tts.py").exists():
        return True
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY") and (td / "openai_tts.py").exists():
        return True
    return False


def should_use_local_tts() -> bool:
    if cloud_tts_available():
        return False
    return local_tts_enabled() and bool(jarvis_say_path())


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


def speak_local_async(text: str) -> None:
    """Spawn detached worker; hook returns immediately."""
    subprocess.Popen(
        ["uv", "run", str(_WORKER), "--text", text],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def speak(text: str, timeout: int = 10) -> None:
    try:
        if not text.strip():
            return
        if should_use_local_tts():
            speak_local_async(text)
            return
        script = get_tts_script_path()
        if not script:
            return
        subprocess.run(
            ["uv", "run", script, text],
            capture_output=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
