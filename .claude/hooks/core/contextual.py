"""Build contextual completion lines for stop hooks."""

from __future__ import annotations

import json
import os
import random
import subprocess
from datetime import datetime, timezone
from typing import Any

from core.env import load_hook_env
from core.paths import llm_dir, repo_root
from core.transcript import read_turn_context

_COMPLETION_FALLBACKS = [
    "Work complete!",
    "All done!",
    "Task finished!",
    "Ready when you are.",
]

_ERROR_PREFIXES = ("Error generating",)


def _clean_llm_line(text: str) -> str:
    line = text.strip().strip('"').strip("'").split("\n")[0].strip()
    return line


def _log_voice_event(event: dict[str, Any]) -> None:
    try:
        log_dir = repo_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "jarvis_voice.jsonl"
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        with path.open("a") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass


def _run_contextual_llm(script_name: str, context: dict[str, Any]) -> str | None:
    load_hook_env()
    script = llm_dir() / script_name
    if not script.exists():
        return None
    payload = {
        "last_user": context.get("last_user"),
        "last_assistant": context.get("last_assistant"),
        "status": context.get("status"),
        "tts_summary": context.get("tts_summary"),
    }
    try:
        result = subprocess.run(
            ["uv", "run", str(script), "--contextual"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(repo_root()),
        )
        stdout = result.stdout.strip() if result.stdout else ""
        if result.returncode == 0 and stdout and not stdout.startswith(_ERROR_PREFIXES):
            return _clean_llm_line(stdout)
        _log_voice_event({
            "event": "contextual_llm_failed",
            "script": script_name,
            "returncode": result.returncode,
            "stdout": stdout[:500],
            "stderr": (result.stderr or "")[:500],
        })
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as exc:
        _log_voice_event({"event": "contextual_llm_error", "script": script_name, "error": str(exc)})
    return None


def _generic_completion() -> str:
    load_hook_env()
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        try:
            result = subprocess.run(
                ["uv", "run", str(llm_dir() / "oai.py"), "--completion"],
                capture_output=True,
                text=True,
                timeout=12,
                cwd=str(repo_root()),
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
                timeout=12,
                cwd=str(repo_root()),
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
    Contextual LLM (JARVIS persona) → generic completion → hardcoded fallback.
    TTS_SUMMARY is a hint only — always spoken through the persona LLM.
    """
    load_hook_env()
    ctx = read_turn_context(transcript_path)
    ctx["status"] = status

    has_context = ctx.get("last_user") or ctx.get("last_assistant") or ctx.get("tts_summary")
    message: str | None = None
    source = "fallback"

    if has_context:
        if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
            message = _run_contextual_llm("oai.py", ctx)
            if message:
                source = "contextual_openai"
        if not message and os.getenv("ANTHROPIC_API_KEY"):
            message = _run_contextual_llm("anth.py", ctx)
            if message:
                source = "contextual_anthropic"

    if not message:
        message = _generic_completion()
        source = "generic"

    _log_voice_event({
        "event": "stop_message",
        "source": source,
        "status": status,
        "transcript_path": transcript_path,
        "message": message,
        "had_tts_summary": bool(ctx.get("tts_summary")),
    })
    return message
