# Jarvis Cursor Hooks — Design Spec

**Date:** 2026-07-13  
**Task:** `jarvis-cursor-hooks` (flow)  
**Repo:** `claude-code-jarvis-hooks`  
**Status:** Planning complete — **implementation deferred** (see `docs/superpowers/2026-07-13-jarvis-cursor-hooks-wrap-up.md`)

> **Post-plan discovery:** Cursor already runs `.claude/settings.json` `Stop` → `stop.py --chat`.
> Turn-end JARVIS voice works without a native `.cursor/hooks.json` port. `Notification` is not supported in Cursor.

## Goal

Extend the existing Claude Code JARVIS voice-notification hooks so the same LLM-generated messages and TTS pipeline work in **Cursor** via `.cursor/hooks.json`, while fixing known Claude-side gaps.

## Decisions

| Topic | Decision |
|---|---|
| Install model | **Both** — in-repo `.cursor/hooks.json` template + global installer script |
| Debounce | **Idle-after-stop** — speak only if no new `stop` within N seconds |
| MCP attention | **Skip for v1** |
| Naming | **Keep repo name** — document Cursor support in README only |
| Architecture | **Shared core + thin entrypoints** (Approach A) |

## Architecture

```
.claude/hooks/              Claude entrypoints (refactored → core)
.cursor/
  hooks.json                Project-level template
  hooks/                    Cursor entrypoints (thin adapters)
.claude/hooks/core/         Shared: TTS, LLM, logging, debounce
scripts/
  install-cursor-hooks.sh   Writes ~/.cursor/hooks.json (merge, preserve existing)
```

Claude and Cursor hook scripts read JSON from stdin, delegate to shared core, exit 0 on errors (fail open).

## Cursor Event Mapping (v1)

| Event | Script | Behavior |
|---|---|---|
| `stop` | `cursor_stop.py` | Reset idle timer; completion TTS after debounce |
| `beforeShellExecution` | `cursor_attention.py` | Voice on high-signal shell commands; always `permission: allow` |
| `subagentStop` | `cursor_subagent_stop.py` | Immediate subagent completion TTS |
| `beforeMCPExecution` | — | Out of scope v1 |

## Debounce (idle-after-stop)

- State dir: `~/.cursor/jarvis/` (created on first use)
- State file per session: `~/.cursor/jarvis/debounce-<session_key>.json`
- On `stop`: write `last_stop_at` timestamp; spawn detached debounce worker
- Worker sleeps `JARVIS_STOP_DEBOUNCE_SECS` (default **4**), re-reads state; if timestamp unchanged, run completion TTS
- New `stop` before timer fires: update timestamp, worker sees mismatch and exits silently
- Session key: `conversation_id` from hook JSON, fallback to `session_id`, fallback to `"default"`

## Shell Attention Patterns

`cursor_attention.py` speaks when command matches (case-insensitive):

- `sudo`
- `ssh ` / `scp `
- `rm -rf` / `rm -r `
- `curl` / `wget` / `nc `
- `kubectl delete`
- `git push --force` / `git push -f`

Returns `{ "permission": "allow" }` always.

## Claude-Side Fixes (same effort)

1. Wire `SubagentStop` → `subagent_stop.py` in `.claude/settings.json`
2. Remove skip of `"Claude is waiting for your input"` in `notification.py`
3. Update `CLAUDE.md` to match actual hook files (remove references to missing `pre_tool_use.py` / `post_tool_use.py`)

## Install

**Project-level:** Copy or symlink `.cursor/` into a project; paths relative to project root.

**Global:** `scripts/install-cursor-hooks.sh` merges hook entries into `~/.cursor/hooks.json` using absolute paths to this repo's scripts. Preserves unrelated existing hooks.

## Environment Variables

Existing vars unchanged. New:

```bash
JARVIS_STOP_DEBOUNCE_SECS=4   # idle seconds before stop TTS fires
JARVIS_STATE_DIR=~/.cursor/jarvis  # optional override for debounce state
```

## Done When

- [ ] `.cursor/hooks.json` template + installer exist and documented
- [ ] Cursor `stop` triggers debounced completion TTS
- [ ] `beforeShellExecution` triggers attention TTS on gated commands
- [ ] `subagentStop` triggers immediate TTS
- [ ] Shared core used by Claude + Cursor (no duplicated `get_tts_script_path`)
- [ ] Claude `SubagentStop` wired; notification skip bug fixed
- [ ] `CLAUDE.md` accurate; README has Cursor section
- [ ] Manual test commands documented

## Out of Scope

- Cursor CLI agent hook parity
- `beforeMCPExecution` attention hook
- Phone/push notifications (ntfy)
- Repo rename
- npm publish

## Known Limitations

- Cursor `stop` fires every model turn, not session end — debounce mitigates spam
- No first-class "approval dialog" event in Cursor
- Parallel sessions need per-session debounce keys (handled via `conversation_id`)
