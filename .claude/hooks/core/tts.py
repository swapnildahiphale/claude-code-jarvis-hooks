import os
import shutil
import subprocess
from pathlib import Path

from core.contextual import _log_voice_event
from core.env import load_hook_env
from core.paths import tts_dir
from core.presence import should_notify

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
        load_hook_env()
        if not text.strip():
            return
        if not should_notify():
            _log_voice_event({
                "event": "presence_suppressed",
                "text_len": len(text),
            })
            return
        if should_use_local_tts():
            speak_local_async(text)
            return
        script = get_tts_script_path()
        if not script:
            _log_voice_event({"event": "tts_missing_script", "text_len": len(text)})
            return
        _log_voice_event({
            "event": "tts_started",
            "provider": Path(script).stem,
            "text_len": len(text),
        })
        result = subprocess.run(
            ["uv", "run", script, text],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            _log_voice_event({
                "event": "tts_failed",
                "provider": Path(script).stem,
                "returncode": result.returncode,
                "stderr": (result.stderr or "")[:500],
            })
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as exc:
        _log_voice_event({"event": "tts_error", "error": str(exc)})
