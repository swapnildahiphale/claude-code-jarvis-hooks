# Jarvis Cursor Hooks — Session Wrap-Up

**Date:** 2026-07-13  
**Flow task:** `jarvis-cursor-hooks`  
**Branch:** `feature/jarvis-cursor-hooks`

## Summary

Planning and partial implementation for native Cursor hook support. **Discovery during implementation:** Cursor already runs JARVIS voice via existing Claude Code hook compatibility — no full port required for turn-end notifications.

## Key finding

Cursor loads `.claude/settings.json` from the project and maps the agent `stop` event to the Claude `Stop` hook:

```
uv run .claude/hooks/stop.py --chat
```

Verified in Cursor hooks log (`cursor.hooks.workspaceId-*.log`). This is why JARVIS speaks on every agent turn in Cursor today.

**Not supported in Cursor:** Claude `Notification` hook (`notification.py --notify`) is explicitly ignored. Attention/approval voice alerts still require a future `.cursor/hooks.json` `beforeShellExecution` hook if desired.

## What was written this session

| Artifact | Path | Status |
|---|---|---|
| Design spec | `docs/superpowers/specs/2026-07-13-jarvis-cursor-hooks-design.md` | Complete — reflects original plan |
| Implementation plan | `docs/superpowers/plans/2026-07-13-jarvis-cursor-hooks.md` | Complete — 8 tasks, **not executed past partial core** |
| Shared core (foundation) | `.claude/hooks/core/` | Partial — utils extracted, **not wired** into live hooks |
| Unit tests | `tests/` | 7 tests passing |
| Live hooks | `.claude/hooks/{notification,stop,subagent_stop}.py` | **Unchanged** — still what Cursor runs |

## Implementation deferred

The full plan (Cursor entrypoints, debounce wiring, installer, Claude hook refactor) is **paused**. Rationale:

1. Turn-end voice already works via `.claude/settings.json`.
2. Debounce would reduce speech frequency — user prefers current per-turn behavior.
3. Refactoring working hooks adds risk without immediate benefit.

## If resumed later (minimal scope)

1. **Document** Cursor compatibility in README (copy `.claude/` per project).
2. **Optional:** `.cursor/hooks.json` + `cursor_attention.py` for shell approval alerts only.
3. **Small fixes:** wire `SubagentStop`, fix `notification.py` skip bug, align `CLAUDE.md`.

## How to use JARVIS in Cursor today

1. Copy this repo's `.claude/` tree into your project (or work from this repo).
2. Set env vars per `.env.example`.
3. Cursor runs `Stop` → `stop.py --chat` automatically.

No `.cursor/hooks.json` required for completion voice.

## Test commands

```bash
uv run --with pytest pytest tests/ -v
echo '{"conversation_id":"test"}' | uv run .claude/hooks/stop.py --chat
```
