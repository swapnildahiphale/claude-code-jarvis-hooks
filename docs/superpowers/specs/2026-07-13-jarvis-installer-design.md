# JARVIS Hooks Installer — Design Spec

**Date:** 2026-07-13  
**Status:** Approved  
**Repo:** `claude-code-jarvis-hooks`

## Goal

Provide a one-command installer that configures JARVIS voice hooks in **another project**: copy hook scripts, merge hook config entries, and optionally set up Cloud Agent support. Does **not** install `uv`.

## Decisions

| Topic | Decision |
|---|---|
| File placement | **Copy only** — full `.claude/hooks/` tree into target; self-contained for Cloud VMs |
| Existing config | **Replace JARVIS entries only** — detect by sentinel `.claude/hooks/stop.py`; preserve unrelated hooks |
| Cloud setup | **Opt-in** via `--cloud` flag; writes `.cursor/environment.json` template |
| Implementation | Bash wrapper (`install-jarvis.sh`) + Python core (`install-jarvis.py`) |
| `.env` | Create from `.env.example` if missing; never overwrite unless `--force-env` (with backup) |
| Hook script updates | Re-run overwrites `.claude/hooks/` from source (sync upgrades) |

## CLI

```bash
./scripts/install-jarvis.sh /path/to/target-project [options]
```

| Flag | Behavior |
|---|---|
| *(none)* | Copy hooks, merge configs, create `.env` if missing |
| `--cloud` | Also write/merge `.cursor/environment.json` with `uv` install hint |
| `--dry-run` | Print planned actions; no filesystem writes |
| `--force-env` | Recreate `.env` from example (backs up existing to `.env.bak.<timestamp>`) |

**Requirements:**
- Run from jarvis repo (or pass `JARVIS_REPO_ROOT` env var)
- Target path must exist and be a directory
- Does not install `uv`, Python, or system packages

## Files Copied

| Source | Target | Rule |
|---|---|---|
| `.claude/hooks/` (entire tree) | `<target>/.claude/hooks/` | Always sync from source on install |
| `.env.example` | `<target>/.env.example` | Copy only if missing |

**Not copied:** `logs/`, `.env`, `tests/`, docs, `.git/`, `.cursor/hooks/state/`

## Config Merge Logic

### Sentinel

A hook entry is considered **JARVIS-owned** if its `command` string contains:

```
.claude/hooks/stop.py
```

### `.claude/settings.json`

Used by Claude Code and local Cursor (third-party hooks).

**If missing:** create minimal file:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run .claude/hooks/stop.py --chat"
          }
        ]
      }
    ]
  }
}
```

**If exists:** parse JSON → remove JARVIS `Stop` entries (sentinel match) → append fresh JARVIS `Stop` entry → preserve `permissions` and all non-JARVIS hooks.

### `.cursor/hooks.json`

Required for Cursor Cloud Agents; also works as native Cursor hook config.

**If missing:** create:

```json
{
  "version": 1,
  "hooks": {
    "stop": [
      {
        "command": "uv run .claude/hooks/stop.py --chat"
      }
    ]
  }
}
```

**If exists:** parse JSON → remove JARVIS `stop` entries (sentinel match) → append fresh entry → preserve `version` and all other hook events.

### Atomic writes

Write to `<file>.jarvis.tmp`, validate JSON, then `rename` to target. On failure, leave original untouched.

## `.env` Handling

1. If `<target>/.env` missing → copy from `.env.example`; print reminder to set API keys.
2. If exists → skip (print "`.env` exists, skipped").
3. If `--force-env` → backup to `.env.bak.<timestamp>`, then copy from example.

Post-install reminder: Cloud Agents use Cursor **Secrets** dashboard, not committed `.env`.

## `--cloud` Behavior

Write or merge `<target>/.cursor/environment.json`:

```json
{
  "install": "curl -LsSf https://astral.sh/uv/install.sh | sh"
}
```

- If file missing → create with above content.
- If file exists → merge `install` key only if not already set; preserve `build`, `terminals`, etc.

Post-install note: TTS plays on **local** Cursor only; cloud VMs have no speaker to the user.

## Error Handling

| Condition | Behavior |
|---|---|
| Target path invalid | Exit 1, error message |
| Source `.claude/hooks/` missing | Exit 1 |
| Target config JSON invalid | Exit 2, no partial writes |
| Permission denied | Exit 2 |

Exit codes: `0` success, `1` usage/validation, `2` write/merge failure.

## Architecture

```
scripts/install-jarvis.sh     → thin wrapper, forwards args
scripts/install-jarvis.py     → copy, merge, env, cloud logic
tests/test_installer.py       → unit tests with tmp_path
```

### Python module responsibilities

| Function | Purpose |
|---|---|
| `copy_hooks(src, dst, dry_run)` | Recursive copy/sync of `.claude/hooks/` |
| `merge_claude_settings(path, dry_run)` | Create or merge `.claude/settings.json` |
| `merge_cursor_hooks(path, dry_run)` | Create or merge `.cursor/hooks.json` |
| `setup_env(target, force, dry_run)` | `.env` / `.env.example` handling |
| `setup_cloud_env(target, dry_run)` | `.cursor/environment.json` |
| `is_jarvis_command(cmd)` | Sentinel check |
| `main()` | argparse, orchestration, summary output |

## Testing

`tests/test_installer.py` covers:

- Fresh project → hooks + both configs + `.env.example`
- Existing unrelated hooks in both configs → preserved, JARVIS added
- Re-run → JARVIS entry replaced, hook files updated, others untouched
- `--dry-run` → zero filesystem changes
- `--cloud` → `environment.json` created
- Invalid JSON in target → error, no corruption
- `--force-env` → backup + recreate

## Documentation Updates

- `README.md`: **Install in another project** section with example command
- Link to this spec

## Out of Scope

- Installing `uv`, Python, or OS packages
- Cursor Secrets / API key injection
- Global `~/.cursor/hooks.json` installer
- Symlink / submodule install modes
- Debounce wiring or Cursor-specific entrypoint scripts

## Done When

- [ ] `scripts/install-jarvis.sh` and `scripts/install-jarvis.py` exist and work
- [ ] Idempotent re-run updates hooks and JARVIS config entries only
- [ ] `--cloud`, `--dry-run`, `--force-env` flags work
- [ ] `tests/test_installer.py` passes
- [ ] README documents install flow
