# JARVIS Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan step-by-step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `scripts/install-jarvis.sh` + `scripts/install-jarvis.py` so users can one-command copy JARVIS hooks and merge config into any target project.

**Architecture:** Bash wrapper forwards to a Python stdlib script. Python copies `.claude/hooks/`, merges JARVIS entries into `.claude/settings.json` and `.cursor/hooks.json` via sentinel detection, handles `.env` safely, and optionally writes `.cursor/environment.json` with `--cloud`.

**Tech Stack:** Python 3.11+ stdlib (`argparse`, `json`, `pathlib`, `shutil`, `datetime`), bash wrapper, pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-jarvis-installer-design.md`

---

## File Map

| File | Responsibility |
|---|---|
| `scripts/install-jarvis.py` | Core installer logic |
| `scripts/install-jarvis.sh` | User-facing entrypoint |
| `tests/test_installer.py` | Installer unit tests |
| `tests/conftest.py` | Add `scripts/` to path for imports |
| `README.md` | Install section |

---

### Task 1: Installer Python core — helpers and copy

**Files:**
- Create: `scripts/install-jarvis.py`

- [ ] **Step 1: Create `scripts/install-jarvis.py` with constants and helpers**

```python
#!/usr/bin/env python3
"""Install JARVIS hooks into another project. See docs/superpowers/specs/2026-07-13-jarvis-installer-design.md"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

JARVIS_SENTINEL = ".claude/hooks/stop.py"
JARVIS_STOP_COMMAND = "uv run .claude/hooks/stop.py --chat"

CLAUDE_STOP_ENTRY = {
    "matcher": "",
    "hooks": [
        {"type": "command", "command": JARVIS_STOP_COMMAND},
    ],
}

CURSOR_STOP_ENTRY = {"command": JARVIS_STOP_COMMAND}

CLOUD_ENV_JSON = {
    "install": "curl -LsSf https://astral.sh/uv/install.sh | sh",
}


def repo_root() -> Path:
    env = Path(__file__).resolve().parent.parent
    if (env / ".claude" / "hooks" / "stop.py").exists():
        return env
    override = Path(__file__).resolve().parent.parent
    # Allow JARVIS_REPO_ROOT override
    import os
    raw = os.getenv("JARVIS_REPO_ROOT", "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        if (p / ".claude" / "hooks" / "stop.py").exists():
            return p
    if (override / ".claude" / "hooks" / "stop.py").exists():
        return override
    raise SystemExit("Cannot find jarvis repo root (.claude/hooks/stop.py missing)")


def is_jarvis_command(command: str | None) -> bool:
    return bool(command and JARVIS_SENTINEL in command)


def atomic_write_json(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".jarvis.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def copy_hooks(source_repo: Path, target: Path, dry_run: bool) -> None:
    src = source_repo / ".claude" / "hooks"
    dst = target / ".claude" / "hooks"
    if not src.is_dir():
        raise SystemExit(f"Source hooks missing: {src}")
    if dry_run:
        print(f"  [dry-run] would copy {src} -> {dst}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"  copied hooks -> {dst}")


def copy_env_example(source_repo: Path, target: Path, dry_run: bool) -> None:
    src = source_repo / ".env.example"
    dst = target / ".env.example"
    if dst.exists():
        print(f"  .env.example exists, skipped")
        return
    if not src.exists():
        print(f"  warning: no .env.example in source repo")
        return
    if dry_run:
        print(f"  [dry-run] would copy {src} -> {dst}")
        return
    shutil.copy2(src, dst)
    print(f"  copied .env.example")
```

- [ ] **Step 2: Verify script is syntactically valid**

Run: `python3 -m py_compile scripts/install-jarvis.py`  
Expected: exit 0, no output

---

### Task 2: Config merge functions

**Files:**
- Modify: `scripts/install-jarvis.py`

- [ ] **Step 1: Add merge functions**

Append to `scripts/install-jarvis.py`:

```python
def _filter_jarvis_stop_entries(entries: list) -> list:
    """Remove JARVIS-owned entries from a hook event list."""
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        inner = entry.get("hooks") or []
        if isinstance(inner, list):
            inner_kept = [
                h for h in inner
                if not (isinstance(h, dict) and is_jarvis_command(h.get("command")))
            ]
            if inner_kept:
                new_entry = dict(entry)
                new_entry["hooks"] = inner_kept
                kept.append(new_entry)
        elif is_jarvis_command(entry.get("command")):
            continue
        else:
            kept.append(entry)
    return kept


def merge_claude_settings(target: Path, dry_run: bool) -> None:
    path = target / ".claude" / "settings.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    stop_list = hooks.get("Stop", [])
    if not isinstance(stop_list, list):
        stop_list = []
    stop_list = _filter_jarvis_stop_entries(stop_list)
    stop_list.append(CLAUDE_STOP_ENTRY)
    hooks["Stop"] = stop_list

    atomic_write_json(path, data, dry_run)
    print(f"  merged JARVIS Stop -> {path}")


def merge_cursor_hooks(target: Path, dry_run: bool) -> None:
    path = target / ".cursor" / "hooks.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
    else:
        data = {"version": 1, "hooks": {}}

    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    stop_list = hooks.get("stop", [])
    if not isinstance(stop_list, list):
        stop_list = []
    stop_list = [e for e in stop_list if not (isinstance(e, dict) and is_jarvis_command(e.get("command")))]
    stop_list.append(dict(CURSOR_STOP_ENTRY))
    hooks["stop"] = stop_list

    atomic_write_json(path, data, dry_run)
    print(f"  merged JARVIS stop -> {path}")
```

- [ ] **Step 2: Verify compile**

Run: `python3 -m py_compile scripts/install-jarvis.py`  
Expected: exit 0

---

### Task 3: Env and cloud setup + main CLI

**Files:**
- Modify: `scripts/install-jarvis.py`

- [ ] **Step 1: Add env, cloud, and main**

Append to `scripts/install-jarvis.py`:

```python
def setup_env(source_repo: Path, target: Path, force: bool, dry_run: bool) -> None:
    env_path = target / ".env"
    example_src = source_repo / ".env.example"

    if env_path.exists() and not force:
        print("  .env exists, skipped (use --force-env to recreate)")
        return

    if not example_src.exists():
        print("  warning: no .env.example; cannot create .env")
        return

    if env_path.exists() and force:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = target / f".env.bak.{ts}"
        if dry_run:
            print(f"  [dry-run] would backup {env_path} -> {backup}")
        else:
            shutil.copy2(env_path, backup)
            print(f"  backed up .env -> {backup}")

    if dry_run:
        print(f"  [dry-run] would create {env_path} from .env.example")
        return

    shutil.copy2(example_src, env_path)
    print(f"  created .env from .env.example — fill in API keys")


def setup_cloud_env(target: Path, dry_run: bool) -> None:
    path = target / ".cursor" / "environment.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
        if "install" not in data:
            data["install"] = CLOUD_ENV_JSON["install"]
    else:
        data = dict(CLOUD_ENV_JSON)

    atomic_write_json(path, data, dry_run)
    print(f"  cloud environment -> {path}")
    print("  reminder: add API keys in Cursor Secrets dashboard for cloud agents")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install JARVIS voice hooks into another project.",
    )
    parser.add_argument("target", type=Path, help="Path to target project directory")
    parser.add_argument("--cloud", action="store_true", help="Also write .cursor/environment.json")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    parser.add_argument("--force-env", action="store_true", help="Recreate .env from example (backs up first)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.target.expanduser().resolve()

    if not target.is_dir():
        print(f"error: target is not a directory: {target}", file=sys.stderr)
        return 1

    source = repo_root()
    print(f"Installing JARVIS hooks from {source}")
    print(f"  -> {target}")
    if args.dry_run:
        print("  (dry run)")

    copy_hooks(source, target, args.dry_run)
    copy_env_example(source, target, args.dry_run)
    setup_env(source, target, args.force_env, args.dry_run)
    merge_claude_settings(target, args.dry_run)
    merge_cursor_hooks(target, args.dry_run)

    if args.cloud:
        setup_cloud_env(target, args.dry_run)

    print("\nDone.")
    print("  Local: enable third-party skills in Cursor; fill .env with API keys.")
    print("  Cloud: commit .cursor/hooks.json; add secrets in Cursor dashboard.")
    print("  Test:  uv run .claude/hooks/utils/tts/elevenlabs_tts.py \"JARVIS online, Sir.\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/install-jarvis.py`

---

### Task 4: Bash wrapper

**Files:**
- Create: `scripts/install-jarvis.sh`

- [ ] **Step 1: Create wrapper**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export JARVIS_REPO_ROOT="${REPO_ROOT}"

exec python3 "${SCRIPT_DIR}/install-jarvis.py" "$@"
```

- [ ] **Step 2: Make executable and smoke test dry-run**

Run:
```bash
chmod +x scripts/install-jarvis.sh
./scripts/install-jarvis.sh /tmp/jarvis-install-test --dry-run
```

Expected: prints planned copy/merge actions; exit 0

---

### Task 5: Unit tests

**Files:**
- Create: `tests/test_installer.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Extend conftest to expose installer module**

Add to `tests/conftest.py`:

```python
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
```

- [ ] **Step 2: Write tests**

Create `tests/test_installer.py`:

```python
import json
import sys
from pathlib import Path

import pytest

# Import from scripts/ via conftest path hook
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install_jarvis as installer  # noqa: E402

JARVIS_CMD = installer.JARVIS_STOP_COMMAND


@pytest.fixture
def source_repo(tmp_path):
    """Minimal fake jarvis repo."""
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "stop.py").write_text("# stub\n")
    (hooks / "core").mkdir()
    (hooks / "core" / "__init__.py").write_text("")
    (tmp_path / ".env.example").write_text("ENGINEER_NAME=Test\n")
    return tmp_path


@pytest.fixture
def target_project(tmp_path):
    t = tmp_path / "target"
    t.mkdir()
    return t


def test_fresh_install(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project)]) == 0
    assert (target_project / ".claude" / "hooks" / "stop.py").exists()
    settings = json.loads((target_project / ".claude" / "settings.json").read_text())
    assert any(
        JARVIS_CMD in h.get("command", "")
        for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
    )
    cursor = json.loads((target_project / ".cursor" / "hooks.json").read_text())
    assert any(JARVIS_CMD in e.get("command", "") for e in cursor["hooks"]["stop"])
    assert (target_project / ".env").exists()


def test_preserves_unrelated_hooks(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    settings_path = target_project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({
        "hooks": {
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "echo other"}]}],
        },
    }))
    cursor_path = target_project / ".cursor" / "hooks.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text(json.dumps({
        "version": 1,
        "hooks": {"stop": [{"command": "echo legacy"}]},
    }))
    assert installer.main([str(target_project)]) == 0
    settings = json.loads(settings_path.read_text())
    commands = [
        h.get("command")
        for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
    ]
    assert "echo other" in commands
    assert JARVIS_CMD in commands
    cursor = json.loads(cursor_path.read_text())
    cmds = [e.get("command") for e in cursor["hooks"]["stop"]]
    assert "echo legacy" in cmds
    assert JARVIS_CMD in cmds


def test_rerun_replaces_jarvis_only(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    installer.main([str(target_project)])
    # Tamper hook file
    (target_project / ".claude" / "hooks" / "stop.py").write_text("# old\n")
    installer.main([str(target_project)])
    assert "stub" in (target_project / ".claude" / "hooks" / "stop.py").read_text()
    settings = json.loads((target_project / ".claude" / "settings.json").read_text())
    jarvis_count = sum(
        1 for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
        if installer.is_jarvis_command(h.get("command"))
    )
    assert jarvis_count == 1


def test_dry_run_no_writes(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project), "--dry-run"]) == 0
    assert not (target_project / ".claude" / "hooks").exists()
    assert not (target_project / ".claude" / "settings.json").exists()


def test_cloud_flag(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project), "--cloud"]) == 0
    env_json = json.loads((target_project / ".cursor" / "environment.json").read_text())
    assert "install" in env_json
    assert "uv" in env_json["install"]


def test_invalid_json_fails(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    bad = target_project / ".claude" / "settings.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json")
    with pytest.raises(SystemExit):
        installer.main([str(target_project)])
```

- [ ] **Step 3: Run tests**

Run: `uv run --with pytest pytest tests/test_installer.py -v`  
Expected: all PASS

Note: rename import — Python module file is `install-jarvis.py` which can't be imported as `install-jarvis`. **Fix in implementation:** either rename to `install_jarvis.py` or use importlib. Plan should use `install_jarvis.py` as the Python filename to avoid import issues.

**Correction:** Use `scripts/install_jarvis.py` (underscore) instead of `install-jarvis.py`. Wrapper stays `install-jarvis.sh` and calls `install_jarvis.py`.

---

### Task 6: Fix module naming (install_jarvis.py)

**Files:**
- Rename: `scripts/install-jarvis.py` → `scripts/install_jarvis.py`
- Modify: `scripts/install-jarvis.sh`

- [ ] **Step 1: Use underscore filename for Python module**

Final paths:
- `scripts/install_jarvis.py` (implementation)
- `scripts/install-jarvis.sh` (calls `install_jarvis.py`)

Update wrapper:
```bash
exec python3 "${SCRIPT_DIR}/install_jarvis.py" "$@"
```

Update test import:
```python
import install_jarvis as installer
```

---

### Task 7: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add install section after Quick Start**

Insert after step 4 ("Activate the hooks"):

```markdown
### Install in another project

From this repo:

```bash
./scripts/install-jarvis.sh /path/to/your-project
./scripts/install-jarvis.sh /path/to/your-project --cloud   # + cloud environment.json
```

This copies `.claude/hooks/`, merges JARVIS entries into `.claude/settings.json` and `.cursor/hooks.json`, and creates `.env` from `.env.example` if missing. Safe to re-run after updates.

Requires `uv` on the machine running Cursor (not installed by this script).
```

---

### Task 8: End-to-end manual smoke test

- [ ] **Step 1: Install into temp dir**

```bash
TMP=$(mktemp -d)
./scripts/install-jarvis.sh "$TMP"
echo '{"transcript_path":"","status":"completed"}' | (cd "$TMP" && uv run .claude/hooks/stop.py --chat)
rm -rf "$TMP"
```

Expected: hook runs without import errors (TTS may skip if no API keys in temp `.env`)

- [ ] **Step 2: Re-run idempotency**

```bash
TMP=$(mktemp -d)
./scripts/install-jarvis.sh "$TMP"
./scripts/install-jarvis.sh "$TMP"
# settings.json should have exactly one JARVIS stop entry per file
python3 -c "
import json, pathlib
p = pathlib.Path('$TMP')
s = json.loads((p/'.claude/settings.json').read_text())
n = sum(1 for e in s['hooks']['Stop'] for h in e.get('hooks',[]) if '.claude/hooks/stop.py' in h.get('command',''))
assert n == 1, n
"
rm -rf "$TMP"
```

Expected: assertion passes

---

## Plan Self-Review

| Spec requirement | Task |
|---|---|
| Copy-only hooks | Task 1 `copy_hooks` |
| Replace JARVIS entries only | Task 2 merge functions |
| `--cloud` opt-in | Task 3 `setup_cloud_env` |
| `--dry-run` | All functions accept `dry_run` |
| `--force-env` with backup | Task 3 `setup_env` |
| No uv install | Not in scope |
| Tests | Task 5 |
| README | Task 7 |

**Naming fix:** Python file uses `install_jarvis.py` (importable); shell entrypoint remains `install-jarvis.sh`.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-07-13-jarvis-installer.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement in this session with checkpoints

Which approach do you want?
