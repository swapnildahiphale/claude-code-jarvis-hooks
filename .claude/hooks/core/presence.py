"""Presence gate: suppress TTS when the user is already focused on the IDE."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any

from core.contextual import _log_voice_event
from core.env import load_hook_env


def presence_gate_enabled() -> bool:
    """True when JARVIS_NOTIFY_ONLY_WHEN_AWAY is set to a truthy value."""
    raw = os.getenv("JARVIS_NOTIFY_ONLY_WHEN_AWAY", "").strip().lower()
    return raw in ("true", "1", "yes")


def presence_apps() -> list[str]:
    """App names that count as 'present' (comma-separated env, default Cursor)."""
    raw = os.getenv("JARVIS_PRESENCE_APPS", "Cursor").strip()
    if not raw:
        return ["Cursor"]
    return [part.strip() for part in raw.split(",") if part.strip()]


def presence_fail_open() -> bool:
    """When detection fails, notify anyway if true (default)."""
    raw = os.getenv("JARVIS_PRESENCE_FAIL_OPEN", "true").strip().lower()
    return raw not in ("false", "0", "no")


def presence_timeout_ms() -> int:
    # osascript cold-start often exceeds 200ms on macOS; 2s is a safe default.
    try:
        return int(os.getenv("JARVIS_PRESENCE_TIMEOUT_MS", "2000"))
    except ValueError:
        return 2000


def _log_presence_decision(**fields: Any) -> None:
    _log_voice_event({"event": "presence_check", **fields})


def _probe_frontmost_darwin() -> tuple[str | None, str | None]:
    script = (
        'tell application "System Events" to get name of '
        "first process whose frontmost is true"
    )
    timeout_s = presence_timeout_ms() / 1000.0
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if result.returncode != 0:
            err = (result.stderr or "").strip()[:200]
            return None, f"osascript_rc_{result.returncode}:{err or 'unknown'}"
        name = (result.stdout or "").strip()
        if not name:
            return None, "osascript_empty"
        return name, None
    except subprocess.TimeoutExpired:
        return None, f"osascript_timeout_{presence_timeout_ms()}ms"
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"osascript_error:{exc}"


def _probe_frontmost_linux() -> tuple[str | None, str | None]:
    if not shutil.which("xdotool"):
        return None, "xdotool_missing"
    timeout_s = presence_timeout_ms() / 1000.0
    try:
        result = subprocess.run(
            ["xdotool", "getwindowfocus", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if result.returncode != 0:
            return None, f"xdotool_rc_{result.returncode}"
        name = (result.stdout or "").strip()
        if not name:
            return None, "xdotool_empty"
        return name, None
    except subprocess.TimeoutExpired:
        return None, f"xdotool_timeout_{presence_timeout_ms()}ms"
    except (subprocess.SubprocessError, OSError) as exc:
        return None, f"xdotool_error:{exc}"


def probe_frontmost() -> tuple[str | None, str | None]:
    """Return (app_name, error_reason). error_reason is set when name is None."""
    system = platform.system()
    if system == "Darwin":
        return _probe_frontmost_darwin()
    if system == "Linux":
        return _probe_frontmost_linux()
    return None, f"unsupported_platform:{system}"


def frontmost_app_name() -> str | None:
    """Return the frontmost application/window name, or None if unknown."""
    name, _ = probe_frontmost()
    return name


def _is_focused_app(frontmost: str, apps: list[str]) -> bool:
    frontmost_lower = frontmost.lower()
    for app in apps:
        if app.lower() == frontmost_lower:
            return True
        # Window titles on Linux may include the app name as a substring.
        if app.lower() in frontmost_lower:
            return True
    return False


def should_notify() -> bool:
    """
    Return True if TTS should fire.

    When the gate is off, always True. When on, False if a configured app
    is frontmost; on detection failure, honor JARVIS_PRESENCE_FAIL_OPEN.
    """
    load_hook_env()

    if not presence_gate_enabled():
        return True

    frontmost, detect_error = probe_frontmost()
    apps = presence_apps()

    if frontmost is None:
        notify = presence_fail_open()
        _log_presence_decision(
            gate_enabled=True,
            frontmost=None,
            presence_apps=apps,
            notify=notify,
            detect_error=detect_error,
            fail_open=presence_fail_open(),
            reason="detect_failed_fail_open" if notify else "detect_failed_fail_closed",
        )
        return notify

    focused = _is_focused_app(frontmost, apps)
    notify = not focused
    _log_presence_decision(
        gate_enabled=True,
        frontmost=frontmost,
        presence_apps=apps,
        notify=notify,
        reason="app_focused" if focused else "app_not_focused",
    )
    return notify


def guard_voice_pipeline(stage: str = "pipeline") -> bool:
    """
    Return True when LLM + TTS should run.

    Call before any OpenAI/Anthropic message generation to avoid wasted tokens
    when the user is already focused on the IDE.
    """
    if should_notify():
        return True
    _log_voice_event({
        "event": "presence_suppressed",
        "stage": stage,
        "skipped_llm": True,
    })
    return False
