import json
import os
import subprocess
import time
from pathlib import Path


def state_dir() -> Path:
    raw = os.getenv("JARVIS_STATE_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser()
    else:
        p = Path.home() / ".cursor" / "jarvis"
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_file_for(session_key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_key)
    return state_dir() / f"debounce-{safe}.json"


def write_stop_state(session_key: str, timestamp: float) -> None:
    path = state_file_for(session_key)
    path.write_text(json.dumps({"last_stop_at": timestamp}))


def read_stop_state(session_key: str) -> float | None:
    path = state_file_for(session_key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return float(data.get("last_stop_at"))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def debounce_secs() -> float:
    try:
        return float(os.getenv("JARVIS_STOP_DEBOUNCE_SECS", "4"))
    except ValueError:
        return 4.0


def schedule_stop_notification(session_key: str) -> None:
    """Write timestamp and spawn detached worker to speak after idle period."""
    now = time.time()
    write_stop_state(session_key, now)
    worker = Path(__file__).resolve().parent / "debounce_worker.py"
    subprocess.Popen(
        [
            "uv",
            "run",
            str(worker),
            "--session-key",
            session_key,
            "--armed-at",
            str(now),
            "--wait",
            str(debounce_secs()),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
