#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///
"""Detached worker: generate JARVIS voice via jarvis-say and play locally."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.contextual import _log_voice_event
from core.debounce import state_dir
from core.env import load_hook_env


def _jarvis_say_binary() -> str | None:
    override = os.getenv("JARVIS_SAY_PATH", "").strip()
    if override and Path(override).is_file():
        return override
    return shutil.which("jarvis-say")


def _timeout_secs() -> int:
    try:
        return int(os.getenv("JARVIS_SAY_TIMEOUT", "120"))
    except ValueError:
        return 120


def _play_wav(path: Path) -> bool:
    if shutil.which("afplay"):
        subprocess.run(
            ["afplay", str(path)],
            capture_output=True,
            timeout=120,
            check=False,
        )
        return True
    if shutil.which("ffplay"):
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", str(path)],
            capture_output=True,
            timeout=120,
            check=False,
        )
        return True
    return False


def run_jarvis_say(text: str) -> None:
    load_hook_env()
    binary = _jarvis_say_binary()
    if not binary:
        _log_voice_event({"event": "jarvis_say_missing", "text_len": len(text)})
        return

    out_dir = state_dir()
    wav = out_dir / f"tts-{uuid.uuid4().hex}.wav"
    try:
        result = subprocess.run(
            [binary, "-o", str(wav), text],
            capture_output=True,
            text=True,
            timeout=_timeout_secs(),
            env=os.environ.copy(),
        )
        if result.returncode != 0 or not wav.is_file() or wav.stat().st_size == 0:
            _log_voice_event({
                "event": "jarvis_say_failed",
                "returncode": result.returncode,
                "stderr": (result.stderr or "")[:500],
            })
            return

        if not _play_wav(wav):
            _log_voice_event({"event": "jarvis_say_playback_missing", "wav": str(wav)})
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as exc:
        _log_voice_event({"event": "jarvis_say_error", "error": str(exc)})
    finally:
        try:
            wav.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    run_jarvis_say(args.text)


if __name__ == "__main__":
    main()
