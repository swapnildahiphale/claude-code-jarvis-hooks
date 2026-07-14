#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import json
import os
import sys

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-5-nano"
DEFAULT_MAX_COMPLETION_TOKENS = 2000

DEBUG_MODE = False


def debug_print(message: str) -> None:
    if DEBUG_MODE:
        print(f"DEBUG: {message}", file=sys.stderr)


def _max_completion_tokens() -> int:
    raw = os.getenv("CLAUDE_HOOKS_OPENAI_MAX_COMPLETION_TOKENS", "").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_MAX_COMPLETION_TOKENS


def _clean_line(text: str) -> str:
    line = text.strip().strip('"').strip("'").split("\n")[0].strip()
    return line


def prompt_llm(prompt_text: str) -> str | None:
    """Call gpt-5-nano via Chat Completions (max_completion_tokens only)."""
    load_dotenv()

    api_key = os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY")
    if not api_key:
        debug_print("Missing CLAUDE_HOOKS_OPENAI_API_KEY")
        return None

    model = os.getenv("CLAUDE_HOOKS_OPENAI_MODEL", DEFAULT_MODEL).strip()
    api_base_url = os.getenv("CLAUDE_HOOKS_OPENAI_API_BASE_URL")

    debug_print(f"Model: {model}")
    debug_print(f"max_completion_tokens: {_max_completion_tokens()}")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=api_base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt_text}],
            max_completion_tokens=_max_completion_tokens(),
        )
        result = (response.choices[0].message.content or "").strip()
        if not result:
            debug_print(f"Empty response (finish_reason={response.choices[0].finish_reason})")
            return None
        debug_print(f"Received response: {result}")
        return result
    except Exception as exc:
        debug_print(f"{type(exc).__name__}: {exc}")
        return None


def generate_completion_message() -> str | None:
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()
    if engineer_name:
        examples = f"""Examples:
- "Diagnostics complete, shall we proceed?"
- "Sir, the code is pristine as expected."
- "Brilliantly done, {engineer_name}, if I may say so."
- "Ready for your next challenge, {engineer_name}." """
    else:
        examples = """Examples:
- "Diagnostics complete, shall we proceed?"
- "Task executed flawlessly, naturally."
- "Another masterpiece delivered." """

    prompt = f"""You are JARVIS: calm, articulate, dry wit, address the user as Sir when natural.

Write one short completion line (15–28 words) for when a coding task just finished.
Return only the line, no quotes.

{examples}"""

    response = prompt_llm(prompt)
    return _clean_line(response) if response else None


def generate_contextual_completion_message(
    last_user: str | None,
    last_assistant: str | None,
    status: str | None = None,
    tts_summary: str | None = None,
) -> str | None:
    hooks_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if hooks_root not in sys.path:
        sys.path.insert(0, hooks_root)
    from core.env import load_hook_env
    from core.prompts import contextual_completion_prompt

    load_hook_env()
    prompt = contextual_completion_prompt(
        last_user=last_user,
        last_assistant=last_assistant,
        status=status,
        tts_summary=tts_summary,
    )
    response = prompt_llm(prompt)
    return _clean_line(response) if response else None


def generate_notification_message() -> str | None:
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()
    if engineer_name:
        examples = f"""Examples:
- "Your attention is required, if you please."
- "Sir, your expertise is needed."
- "{engineer_name}, a moment of your time?" """
    else:
        examples = """Examples:
- "Your attention is required, if you please."
- "Awaiting your guidance, naturally." """

    prompt = f"""You are JARVIS: calm, articulate, dry wit.

Write one short line (under 12 words) asking for the user's attention.
Return only the line, no quotes.

{examples}"""

    response = prompt_llm(prompt)
    return _clean_line(response) if response else None


def main() -> None:
    global DEBUG_MODE

    if "--debug" in sys.argv:
        DEBUG_MODE = True
        sys.argv.remove("--debug")

    if len(sys.argv) < 2:
        print(
            "Usage: oai.py [--debug] --completion | --notification | --contextual | 'prompt'"
        )
        return

    arg = sys.argv[1]
    if arg == "--completion":
        message = generate_completion_message()
    elif arg == "--notification":
        message = generate_notification_message()
    elif arg == "--contextual":
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            payload = {}
        message = generate_contextual_completion_message(
            last_user=payload.get("last_user"),
            last_assistant=payload.get("last_assistant"),
            status=payload.get("status"),
            tts_summary=payload.get("tts_summary"),
        )
    else:
        message = prompt_llm(" ".join(sys.argv[1:]))

    if message:
        print(message)
    else:
        print(f"Error generating message ({arg})")


if __name__ == "__main__":
    main()
