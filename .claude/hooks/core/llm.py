import os
import random
import subprocess

from core.paths import llm_dir

_COMPLETION_FALLBACKS = [
    "Work complete!",
    "All done!",
    "Task finished!",
    "Job complete!",
    "Ready for next task!",
]


def _run_llm_script(script_name: str, flag: str) -> str | None:
    script = llm_dir() / script_name
    if not script.exists():
        return None
    try:
        result = subprocess.run(
            ["uv", "run", str(script), flag],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return None


def notification_message() -> str:
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        msg = _run_llm_script("oai.py", "--notification")
        if msg:
            return msg
    if os.getenv("ANTHROPIC_API_KEY"):
        msg = _run_llm_script("anth.py", "--notification")
        if msg:
            return msg
    engineer = os.getenv("ENGINEER_NAME", "").strip()
    if engineer and random.random() < 0.3:
        return f"{engineer}, your agent needs your input"
    return "Your agent needs your input"


def completion_message() -> str:
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        msg = _run_llm_script("oai.py", "--completion")
        if msg:
            return msg
    if os.getenv("ANTHROPIC_API_KEY"):
        msg = _run_llm_script("anth.py", "--completion")
        if msg:
            return msg
    return random.choice(_COMPLETION_FALLBACKS)
