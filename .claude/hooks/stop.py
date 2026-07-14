#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.contextual import contextual_completion_message
from core.env import load_hook_env
from core.presence import guard_voice_pipeline
from core.tts import speak

load_hook_env()


def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        args = parser.parse_args()

        input_data = json.load(sys.stdin)

        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "stop.json")

        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        log_data.append(input_data)
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        transcript_path = input_data.get("transcript_path")

        if args.chat and transcript_path and os.path.exists(transcript_path):
            chat_data = []
            try:
                with open(transcript_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                chat_data.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
                chat_file = os.path.join(log_dir, 'chat.json')
                with open(chat_file, 'w') as f:
                    json.dump(chat_data, f, indent=2)
            except Exception:
                pass

        status = input_data.get("status")
        if not guard_voice_pipeline("stop_hook"):
            sys.exit(0)
        message = contextual_completion_message(transcript_path, status=status)
        speak(message)

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception as exc:
        try:
            from core.contextual import _log_voice_event
            _log_voice_event({"event": "stop_hook_error", "error": str(exc)})
        except Exception:
            pass
        sys.exit(0)


if __name__ == '__main__':
    main()
