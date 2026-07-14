#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Detached worker: speak completion TTS after idle debounce window."""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.debounce import read_stop_state
from core.llm import completion_message
from core.presence import guard_voice_pipeline
from core.tts import speak


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-key", required=True)
    parser.add_argument("--armed-at", type=float, required=True)
    parser.add_argument("--wait", type=float, required=True)
    args = parser.parse_args()

    time.sleep(args.wait)
    current = read_stop_state(args.session_key)
    if current is None or abs(current - args.armed_at) > 0.001:
        return
    if not guard_voice_pipeline("debounce_worker"):
        return
    speak(completion_message())


if __name__ == "__main__":
    main()
