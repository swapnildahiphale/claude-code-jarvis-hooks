"""Parse agent transcript JSONL for contextual stop-hook voice lines."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

TTS_SUMMARY_RE = re.compile(
    r"<!--\s*TTS_SUMMARY\s*(.*?)\s*TTS_SUMMARY\s*-->",
    re.DOTALL | re.IGNORECASE,
)
TTS_SUMMARY_PLAIN_RE = re.compile(
    r"TTS_SUMMARY\s*\n(.*?)\nTTS_SUMMARY",
    re.DOTALL | re.IGNORECASE,
)

# Cap context sent to the summarizer LLM (chars).
_MAX_ASSISTANT_CTX = 1200
_MAX_USER_CTX = 400


def settle_transcript(path: str | Path, max_wait: float | None = None) -> None:
    """Wait for transcript JSONL to stop growing (flush race mitigation)."""
    if max_wait is None:
        try:
            max_wait = float(os.getenv("JARVIS_TRANSCRIPT_SETTLE_SECS", "2.0"))
        except ValueError:
            max_wait = 2.0

    p = Path(path)
    if not p.exists():
        return

    deadline = time.time() + max_wait
    prev_lines = -1
    interval = 0.1

    while time.time() < deadline:
        try:
            line_count = sum(1 for _ in p.open())
        except OSError:
            return
        if line_count == prev_lines and prev_lines >= 0:
            return
        prev_lines = line_count
        time.sleep(interval)


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text" and block.get("text"):
                parts.append(str(block["text"]))
            elif block.get("text"):
                parts.append(str(block["text"]))
    return "\n".join(parts).strip()


def _role_and_text(entry: dict[str, Any]) -> tuple[str | None, str]:
    """Support Cursor and Claude Code JSONL shapes."""
    role = entry.get("role")
    message = entry.get("message") or {}

    if not role and entry.get("type") in ("user", "assistant"):
        role = entry["type"]
        message = entry

    if not role and isinstance(message, dict):
        role = message.get("role")

    if not role:
        return None, ""

    content = message.get("content") if isinstance(message, dict) else None
    if content is None and isinstance(entry.get("content"), (str, list)):
        content = entry["content"]

    text = _text_from_content(content)
    return str(role), text


def extract_tts_summary(text: str) -> str | None:
    if not text:
        return None
    for pattern in (TTS_SUMMARY_RE, TTS_SUMMARY_PLAIN_RE):
        match = pattern.search(text)
        if match:
            summary = match.group(1).strip()
            if summary:
                return summary
    return None


def parse_transcript_lines(lines: list[str]) -> tuple[str, str, str | None]:
    """
    Return (last_user_text, last_assistant_text, tts_summary_from_assistant).
    """
    last_user = ""
    last_assistant = ""
    tts_summary: str | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("type") in ("turn_ended", "progress"):
            continue

        role, text = _role_and_text(entry)
        if not text:
            continue
        if role == "user":
            last_user = text
        elif role == "assistant":
            last_assistant = text
            found = extract_tts_summary(text)
            if found:
                tts_summary = found

    return last_user, last_assistant, tts_summary


def read_turn_context(transcript_path: str | Path | None) -> dict[str, str | None]:
    """Read transcript after settle; return context dict for the LLM."""
    empty: dict[str, str | None] = {
        "last_user": None,
        "last_assistant": None,
        "tts_summary": None,
    }
    if not transcript_path:
        return empty

    path = Path(transcript_path)
    if not path.exists():
        return empty

    settle_transcript(path)

    try:
        lines = path.read_text().splitlines()
    except OSError:
        return empty

    last_user, last_assistant, tts_summary = parse_transcript_lines(lines)

    def _trim(text: str, limit: int) -> str | None:
        text = text.strip()
        if not text:
            return None
        if len(text) <= limit:
            return text
        return "…" + text[-limit:]

    return {
        "last_user": _trim(last_user, _MAX_USER_CTX),
        "last_assistant": _trim(last_assistant, _MAX_ASSISTANT_CTX),
        "tts_summary": tts_summary,
    }
