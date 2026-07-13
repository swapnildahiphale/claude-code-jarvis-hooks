"""Build contextual completion lines for stop hooks."""

from __future__ import annotations

import json
import os
import random
import subprocess
from typing import Any

from core.paths import llm_dir
from core.prompts import contextual_completion_prompt
from core.transcript import read_turn_context

_COMPLETION_FALLBACKS = [
    "Work complete!",
    "All done!",
    "Task finished!",
    "Ready when you are.",
]


def _clean_llm_line(text: str) -> str:
    line = text.strip().strip('"').strip("'").split("\n")[0].strip()
    return line


def _run_contextual_llm(script_name: str, context: dict[str, Any]) -> str | None:
    script = llm_dir() / script_name
    if not script.exists():
        return None
    payload = {
        "last_user": context.get("last_user"),
        "last_assistant": context.get("last_assistant"),
        "status": context.get("status"),
    }
    try:
        result = subprocess.run(
            ["uv", "run", str(script), "--contextual"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _clean_llm_line(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return None


def _generic_completion() -> str:
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        try:
            result = subprocess.run(
                ["uv", "run", str(llm_dir() / "oai.py"), "--completion"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _clean_llm_line(result.stdout)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            result = subprocess.run(
                ["uv", "run", str(llm_dir() / "anth.py"), "--completion"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return _clean_llm_line(result.stdout)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
    return random.choice(_COMPLETION_FALLBACKS)


def contextual_completion_message(
    transcript_path: str | None,
    status: str | None = None,
) -> str:
    """
    Hybrid: TTS_SUMMARY tag → contextual LLM → generic completion → fallback.
    """
    ctx = read_turn_context(transcript_path)
    ctx["status"] = status

    if ctx.get("tts_summary"):
        return _clean_llm_line(str(ctx["tts_summary"]))

    has_context = ctx.get("last_user") or ctx.get("last_assistant")
    if has_context:
        if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
            msg = _run_contextual_llm("oai.py", ctx)
            if msg:
                return msg
        if os.getenv("ANTHROPIC_API_KEY"):
            msg = _run_contextual_llm("anth.py", ctx)
            if msg:
                return msg

    return _generic_completion()
