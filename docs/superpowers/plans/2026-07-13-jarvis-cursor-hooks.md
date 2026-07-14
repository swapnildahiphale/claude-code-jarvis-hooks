# Jarvis Cursor Hooks Implementation Plan

> **Status (2026-07-13):** **Paused after Task 4 partial.** Tasks 1–4 foundation committed; Tasks 5–8 not started. See wrap-up: `docs/superpowers/2026-07-13-jarvis-cursor-hooks-wrap-up.md`. Cursor already uses `.claude/settings.json` for stop TTS.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Cursor hook support with shared TTS/LLM core, debounced stop notifications, shell attention alerts, and Claude-side gap fixes.

**Architecture:** Extract shared logic into `.claude/hooks/core/`; Claude and Cursor entrypoints are thin stdin/stdout adapters. Debounce uses a detached worker subprocess keyed by `conversation_id`.

**Tech Stack:** Python 3.11+, `uv` PEP 723 scripts, Cursor hooks JSON v1, pytest for unit tests.

**Spec:** `docs/superpowers/specs/2026-07-13-jarvis-cursor-hooks-design.md`

---

## File Map

| File | Responsibility |
|---|---|
| `.claude/hooks/core/__init__.py` | Package marker |
| `.claude/hooks/core/paths.py` | Resolve hooks root, TTS/LLM script dirs |
| `.claude/hooks/core/tts.py` | `get_tts_script_path()`, `speak(text)` |
| `.claude/hooks/core/llm.py` | `notification_message()`, `completion_message()` |
| `.claude/hooks/core/log.py` | `append_json_log(filename, data)` |
| `.claude/hooks/core/debounce.py` | State read/write, `schedule_stop_notification(session_key)` |
| `.claude/hooks/core/attention.py` | `is_attention_command(cmd) -> bool` |
| `.claude/hooks/core/debounce_worker.py` | Detached worker: sleep, check state, speak |
| `.claude/hooks/notification.py` | Refactor to use core |
| `.claude/hooks/stop.py` | Refactor to use core |
| `.claude/hooks/subagent_stop.py` | Refactor to use core |
| `.cursor/hooks/cursor_stop.py` | Cursor `stop` adapter |
| `.cursor/hooks/cursor_attention.py` | Cursor `beforeShellExecution` adapter |
| `.cursor/hooks/cursor_subagent_stop.py` | Cursor `subagentStop` adapter |
| `.cursor/hooks.json` | Project-level hook wiring |
| `scripts/install-cursor-hooks.sh` | Global `~/.cursor/hooks.json` installer |
| `tests/test_attention.py` | Shell pattern unit tests |
| `tests/test_debounce.py` | Debounce state unit tests |
| `pyproject.toml` or `tests/conftest.py` | Minimal pytest config |
| `.claude/settings.json` | Wire `SubagentStop` |
| `CLAUDE.md` | Accurate hook list |
| `README.md` | Cursor setup section |
| `.env.example` | Add `JARVIS_STOP_DEBOUNCE_SECS` |

---

### Task 1: Test scaffolding

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_attention.py`
- Create: `tests/test_debounce.py`

- [ ] **Step 1: Create conftest with hooks root on sys.path**

```python
# tests/conftest.py
import sys
from pathlib import Path

HOOKS_ROOT = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_ROOT))
```

- [ ] **Step 2: Write failing attention tests**

```python
# tests/test_attention.py
from core.attention import is_attention_command

def test_sudo_triggers_attention():
    assert is_attention_command("sudo rm file") is True

def test_safe_ls_does_not_trigger():
    assert is_attention_command("ls -la") is False

def test_rm_rf_triggers():
    assert is_attention_command("rm -rf /tmp/foo") is True

def test_curl_triggers():
    assert is_attention_command("curl https://example.com") is True

def test_git_push_force_triggers():
    assert is_attention_command("git push --force origin main") is True
```

- [ ] **Step 3: Write failing debounce tests**

```python
# tests/test_debounce.py
import json
import time
from pathlib import Path

from core.debounce import read_stop_state, write_stop_state, state_file_for

def test_write_and_read_stop_state(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_STATE_DIR", str(tmp_path))
    write_stop_state("sess-1", 12345.0)
    assert read_stop_state("sess-1") == 12345.0

def test_state_file_isolated_per_session(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_STATE_DIR", str(tmp_path))
    write_stop_state("a", 1.0)
    write_stop_state("b", 2.0)
    assert read_stop_state("a") == 1.0
    assert read_stop_state("b") == 2.0
    assert state_file_for("a") != state_file_for("b")
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /Users/Swapnil/workspace/swapnil/claude-code-jarvis-hooks && uv run --with pytest pytest tests/ -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'core'`

---

### Task 2: Shared core — paths and attention

**Files:**
- Create: `.claude/hooks/core/__init__.py`
- Create: `.claude/hooks/core/paths.py`
- Create: `.claude/hooks/core/attention.py`

- [ ] **Step 1: Create package marker**

```python
# .claude/hooks/core/__init__.py
# Shared JARVIS hook core used by Claude Code and Cursor entrypoints.
```

- [ ] **Step 2: Implement paths.py**

```python
# .claude/hooks/core/paths.py
from pathlib import Path

def hooks_root() -> Path:
    return Path(__file__).resolve().parent.parent

def tts_dir() -> Path:
    return hooks_root() / "utils" / "tts"

def llm_dir() -> Path:
    return hooks_root() / "utils" / "llm"
```

- [ ] **Step 3: Implement attention.py**

```python
# .claude/hooks/core/attention.py
import re

# High-signal shell commands that likely need user approval in Cursor.
_PATTERNS = [
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bssh\s", re.I),
    re.compile(r"\bscp\s", re.I),
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\brm\s+-r\b", re.I),
    re.compile(r"\bcurl\b", re.I),
    re.compile(r"\bwget\b", re.I),
    re.compile(r"\bnc\s", re.I),
    re.compile(r"\bkubectl\s+delete\b", re.I),
    re.compile(r"\bgit\s+push\b.*(-f|--force)\b", re.I),
]

def is_attention_command(command: str) -> bool:
    if not command or not command.strip():
        return False
    return any(p.search(command) for p in _PATTERNS)
```

- [ ] **Step 4: Run attention tests**

Run: `uv run --with pytest pytest tests/test_attention.py -v`

Expected: PASS (all 5)

---

### Task 3: Shared core — TTS and LLM

**Files:**
- Create: `.claude/hooks/core/tts.py`
- Create: `.claude/hooks/core/llm.py`

- [ ] **Step 1: Implement tts.py** (extract from `notification.py`)

```python
# .claude/hooks/core/tts.py
import os
import subprocess
from pathlib import Path

from core.paths import tts_dir

def get_tts_script_path() -> str | None:
    td = tts_dir()
    if os.getenv("ELEVENLABS_API_KEY"):
        p = td / "elevenlabs_tts.py"
        if p.exists():
            return str(p)
    if os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY"):
        p = td / "openai_tts.py"
        if p.exists():
            return str(p)
    p = td / "pyttsx3_tts.py"
    return str(p) if p.exists() else None

def speak(text: str, timeout: int = 10) -> None:
    try:
        script = get_tts_script_path()
        if not script or not text.strip():
            return
        subprocess.run(
            ["uv", "run", script, text],
            capture_output=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
```

- [ ] **Step 2: Implement llm.py** (extract from `notification.py` / `stop.py`)

```python
# .claude/hooks/core/llm.py
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
            timeout=10,
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
```

- [ ] **Step 3: Smoke-test TTS/LLM manually**

Run: `uv run --with pytest pytest tests/ -v` (still only attention + debounce after Task 4)

---

### Task 4: Shared core — logging and debounce

**Files:**
- Create: `.claude/hooks/core/log.py`
- Create: `.claude/hooks/core/debounce.py`
- Create: `.claude/hooks/core/debounce_worker.py`

- [ ] **Step 1: Implement log.py**

```python
# .claude/hooks/core/log.py
import json
import os
from typing import Any

def append_json_log(filename: str, data: dict[str, Any]) -> None:
    log_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, filename)
    log_data: list = []
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                log_data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            log_data = []
    log_data.append(data)
    with open(path, "w") as f:
        json.dump(log_data, f, indent=2)
```

- [ ] **Step 2: Implement debounce.py**

```python
# .claude/hooks/core/debounce.py
import json
import os
import subprocess
import sys
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
            "uv", "run", str(worker),
            "--session-key", session_key,
            "--armed-at", str(now),
            "--wait", str(debounce_secs()),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
```

- [ ] **Step 3: Implement debounce_worker.py**

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import argparse
import sys
import time
from pathlib import Path

# Allow importing core when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.debounce import read_stop_state
from core.llm import completion_message
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
        return  # newer stop arrived; stay silent
    speak(completion_message())

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run debounce tests**

Run: `uv run --with pytest pytest tests/test_debounce.py -v`

Expected: PASS (all 2)

---

### Task 5: Refactor Claude hooks to use core

**Files:**
- Modify: `.claude/hooks/notification.py`
- Modify: `.claude/hooks/stop.py`
- Modify: `.claude/hooks/subagent_stop.py`

- [ ] **Step 1: Refactor notification.py**

Replace duplicated `get_tts_script_path`, `get_llm_notification_message`, and inline logging with:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.log import append_json_log
from core.llm import notification_message
from core.tts import speak
```

In `main()`:
- Use `append_json_log("notification.json", input_data)`
- **Remove** the skip: `if args.notify and input_data.get('message') != 'Claude is waiting for your input':`
- Replace with: `if args.notify: speak(notification_message())`

Delete the now-unused local helper functions.

- [ ] **Step 2: Refactor stop.py**

Same pattern: import `append_json_log`, `completion_message`, `speak`. Remove duplicated helpers. Keep `--chat` transcript logic unchanged.

- [ ] **Step 3: Refactor subagent_stop.py**

Import `append_json_log`, `speak`. Use fixed message `"Subagent Complete"`. Remove duplicated `get_tts_script_path`.

- [ ] **Step 4: Manual smoke test**

Run: `echo '{}' | uv run .claude/hooks/stop.py`

Expected: exit 0, `logs/stop.json` appended (TTS may fire if keys configured)

---

### Task 6: Cursor hook entrypoints

**Files:**
- Create: `.cursor/hooks/cursor_stop.py`
- Create: `.cursor/hooks/cursor_attention.py`
- Create: `.cursor/hooks/cursor_subagent_stop.py`

Each Cursor script is a PEP 723 uv script that prepends `.claude/hooks` to `sys.path` and imports core.

- [ ] **Step 1: Create cursor_stop.py**

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

from core.log import append_json_log
from core.debounce import schedule_stop_notification

def session_key(data: dict) -> str:
    return (
        data.get("conversation_id")
        or data.get("session_id")
        or "default"
    )

def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        append_json_log("cursor_stop.json", data)
        schedule_stop_notification(session_key(data))
    except Exception:
        pass
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create cursor_attention.py**

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

from core.attention import is_attention_command
from core.llm import notification_message
from core.log import append_json_log
from core.tts import speak

def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        append_json_log("cursor_attention.json", data)
        cmd = data.get("command") or data.get("shell_command") or ""
        if is_attention_command(cmd):
            speak(notification_message())
        print(json.dumps({"permission": "allow"}))
    except Exception:
        print(json.dumps({"permission": "allow"}))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create cursor_subagent_stop.py**

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv"]
# ///
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

from core.log import append_json_log
from core.tts import speak

def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        append_json_log("cursor_subagent_stop.json", data)
        speak("Subagent Complete")
    except Exception:
        pass
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Make scripts executable**

Run: `chmod +x .cursor/hooks/*.py .claude/hooks/core/debounce_worker.py`

- [ ] **Step 5: Manual tests**

```bash
echo '{"conversation_id":"test-1"}' | uv run .cursor/hooks/cursor_stop.py
echo '{"command":"sudo apt update"}' | uv run .cursor/hooks/cursor_attention.py
echo '{"subagent_type":"explore"}' | uv run .cursor/hooks/cursor_subagent_stop.py
```

Expected: exit 0; log files in `logs/`; attention/subagent speak immediately; stop schedules debounced TTS after ~4s

---

### Task 7: Cursor hooks.json and global installer

**Files:**
- Create: `.cursor/hooks.json`
- Create: `scripts/install-cursor-hooks.sh`

- [ ] **Step 1: Create project-level hooks.json**

```json
{
  "version": 1,
  "hooks": {
    "stop": [
      {
        "command": "uv run .cursor/hooks/cursor_stop.py"
      }
    ],
    "beforeShellExecution": [
      {
        "command": "uv run .cursor/hooks/cursor_attention.py"
      }
    ],
    "subagentStop": [
      {
        "command": "uv run .cursor/hooks/cursor_subagent_stop.py"
      }
    ]
  }
}
```

- [ ] **Step 2: Create install-cursor-hooks.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CURSOR_DIR="${HOME}/.cursor"
HOOKS_JSON="${CURSOR_DIR}/hooks.json"
mkdir -p "${CURSOR_DIR}"

# Backup existing hooks.json if present
if [[ -f "${HOOKS_JSON}" ]]; then
  cp "${HOOKS_JSON}" "${HOOKS_JSON}.bak.$(date +%Y%m%d%H%M%S)"
fi

# Write jarvis hooks using absolute paths
cat > "${HOOKS_JSON}.jarvis.new" <<EOF
{
  "version": 1,
  "hooks": {
    "stop": [{"command": "uv run ${REPO_ROOT}/.cursor/hooks/cursor_stop.py"}],
    "beforeShellExecution": [{"command": "uv run ${REPO_ROOT}/.cursor/hooks/cursor_attention.py"}],
    "subagentStop": [{"command": "uv run ${REPO_ROOT}/.cursor/hooks/cursor_subagent_stop.py"}]
  }
}
EOF

# If no existing file, use new; else instruct user to merge manually
if [[ ! -f "${HOOKS_JSON}" ]]; then
  mv "${HOOKS_JSON}.jarvis.new" "${HOOKS_JSON}"
  echo "Installed global hooks to ${HOOKS_JSON}"
else
  echo "Existing ${HOOKS_JSON} backed up. Merge from ${HOOKS_JSON}.jarvis.new"
fi
```

- [ ] **Step 3: Make installer executable**

Run: `chmod +x scripts/install-cursor-hooks.sh`

---

### Task 8: Claude settings + docs

**Files:**
- Modify: `.claude/settings.json`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Wire SubagentStop in settings.json**

Add inside `"hooks"`:

```json
"SubagentStop": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "uv run .claude/hooks/subagent_stop.py"
      }
    ]
  }
]
```

- [ ] **Step 2: Update CLAUDE.md**

Replace references to `pre_tool_use.py` / `post_tool_use.py` with actual hooks:
- `notification.py`, `stop.py`, `subagent_stop.py`
- Note shared `core/` package
- Note `.cursor/hooks/` for Cursor support

- [ ] **Step 3: Add Cursor section to README.md**

Include:
- Prerequisites (`uv`, env vars)
- Project install: use in-repo `.cursor/hooks.json`
- Global install: `./scripts/install-cursor-hooks.sh`
- Test commands (from Task 6)
- Limitations: `stop` per-turn, no MCP v1, CLI inconsistency
- `JARVIS_STOP_DEBOUNCE_SECS` config

- [ ] **Step 4: Update .env.example**

Add:

```bash
JARVIS_STOP_DEBOUNCE_SECS=4
# JARVIS_STATE_DIR=~/.cursor/jarvis
```

- [ ] **Step 5: Run full test suite**

Run: `uv run --with pytest pytest tests/ -v`

Expected: all PASS

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| Shared core, no duplication | Tasks 2–4, 5 |
| Cursor stop + debounce | Tasks 4, 6 |
| Shell attention | Tasks 2, 6 |
| subagentStop | Task 6 |
| Skip MCP v1 | — (not implemented) |
| Project + global install | Task 7 |
| Claude SubagentStop wire | Task 8 |
| Notification skip fix | Task 5 |
| CLAUDE.md accuracy | Task 8 |
| README Cursor section | Task 8 |
| Manual test commands | Tasks 6, 8 |

## Execution Order

Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (sequential; do not skip refactor before Cursor scripts).
