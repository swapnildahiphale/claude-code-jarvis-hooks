# JARVIS local TTS (`jarvis-say`) integration

**Date:** 2026-07-13  
**Status:** Approved — implemented 2026-07-13

## Goal

Add optional local JARVIS voice playback via the `jarvis-say` CLI when cloud TTS API keys are absent. Opt-in only; non-blocking (background worker); documented in install steps.

## Background

| Provider | Trigger | Latency | Voice |
|----------|---------|---------|-------|
| ElevenLabs | `ELEVENLABS_API_KEY` | ~1–3s | Premium preset |
| OpenAI TTS | `CLAUDE_HOOKS_OPENAI_API_KEY` | ~2–5s | Nova |
| **jarvis-say** (new) | `JARVIS_USE_LOCAL_TTS=true` + binary on PATH | ~30–55s cold | F5-TTS JARVIS clone |
| pyttsx3 | fallback | <1s | Generic system voice |

`jarvis-say` lives in the separate [`jarvis-voice`](https://github.com/swapnildahiphale/jarvis-voice) repo. It writes a WAV file; playback is the hook's responsibility (`afplay` on macOS).

Cold `jarvis-say` is too slow to block stop hooks (`speak()` timeout is 10s today). A planned warm-server (~10s) is out of scope for this change.

## Decisions (locked)

1. **Background playback** — stop hook spawns a detached worker and returns immediately.
2. **Opt-in** — only when `JARVIS_USE_LOCAL_TTS=true` (truthy: `true`, `True`, `1`, `yes`).
3. **Fallback chain** — ElevenLabs → OpenAI → jarvis-say (if opted in) → pyttsx3.
4. **Cloud agents** — not supported; no `jarvis-say` on cloud VMs. Unset or leave `false` in cloud secrets.
5. **Installer** — document the flag in `.env.example`, README, and installer completion message.

## Architecture

```
stop.py / notification.py
        │
        ▼
   core/tts.py :: speak(text)
        │
        ├─ cloud keys? ──► uv run elevenlabs_tts.py | openai_tts.py  (sync, ~10s timeout)
        │
        ├─ JARVIS_USE_LOCAL_TTS + jarvis-say on PATH?
        │       └─► Popen jarvis_say_worker.py --text "..."  (detached, hook returns 0)
        │
        └─ else ──► uv run pyttsx3_tts.py  (sync)
```

### New module: `core/jarvis_say_worker.py`

Detached PEP 723 script (same pattern as `debounce_worker.py`):

1. Resolve `jarvis-say` path: `JARVIS_SAY_PATH` env or `shutil.which("jarvis-say")`.
2. Write WAV to temp file under `JARVIS_STATE_DIR` (or system temp).
3. Run `jarvis-say -o <tmp.wav> "<text>"` with long timeout (default 120s).
4. Play via `afplay` (macOS). On Linux, try `ffplay -nodisp -autoexit` or skip playback with a log entry (jarvis-say is primarily a macOS/local tool today).
5. Delete temp WAV.
6. Log failures to `logs/jarvis_voice.jsonl` (reuse `_log_voice_event` pattern).

`jarvis-say` already honors `JARVIS_SPEED`, `JARVIS_NFE`, `JARVIS_DEVICE` — no need to duplicate in hooks.

### Changes to `core/tts.py`

- Add `_local_tts_enabled()` — parse `JARVIS_USE_LOCAL_TTS` truthily.
- Add `_jarvis_say_available()` — binary exists on PATH or `JARVIS_SAY_PATH`.
- Add `speak_local_async(text)` — spawn worker via `subprocess.Popen(..., start_new_session=True)`.
- Update `get_tts_script_path()` / `speak()`:
  - If local TTS enabled and binary found → `speak_local_async(text)`; return.
  - Else existing provider selection unchanged.

Do **not** increase the sync `speak()` timeout for jarvis-say; generation runs entirely in the worker.

## Configuration

### `.env.example` (new lines)

```bash
# Optional: local JARVIS voice via jarvis-say (requires jarvis-voice setup; macOS/local only)
JARVIS_USE_LOCAL_TTS=false
# JARVIS_SAY_PATH=/opt/homebrew/bin/jarvis-say   # override if not on PATH
# JARVIS_SAY_TIMEOUT=120                          # worker generation timeout (seconds)
```

Existing `JARVIS_SPEED` / `JARVIS_DEVICE` are read by `jarvis-say` itself when set in `.env`.

## Installation documentation

### README — new subsection under setup

**Local JARVIS voice (optional, no API keys)**

1. Set up [`jarvis-voice`](https://github.com/swapnildahiphale/jarvis-voice): `./scripts/setup.sh`, ensure `jarvis-say` is on PATH.
2. In `.env`: `JARVIS_USE_LOCAL_TTS=true`
3. Test: `uv run .claude/hooks/core/jarvis_say_worker.py --text "JARVIS online, Sir."`

Note: first clip after boot takes ~30–55s; playback starts in the background after the agent turn ends.

### Installer (`scripts/install_jarvis.py`)

Append to the "Done." footer:

```
  Local TTS: install jarvis-voice, set JARVIS_USE_LOCAL_TTS=true in .env (macOS only).
```

No installer flag for local TTS — purely env-driven.

## Error handling

| Condition | Behavior |
|-----------|----------|
| `JARVIS_USE_LOCAL_TTS=true` but binary missing | Log warning; fall through to pyttsx3 |
| `jarvis-say` generation fails | Log event; no retry; silent to user |
| `afplay` missing | Log event; WAV still written (optional: log path) |
| Overlapping stop events | Each spawns its own worker (acceptable; rare). Future: warm-server queue. |

## Testing

| Test | Type |
|------|------|
| `_local_tts_enabled()` truthy parsing | unit |
| Provider order: keys beat local; local beats pyttsx3 | unit |
| `speak()` spawns worker when local enabled (mock Popen) | unit |
| Worker command construction (mock subprocess) | unit |
| No test against real F5 model in CI | — |

## Out of scope

- `jarvis-voice` warm-server HTTP client (follow-up when server exists).
- Bundling `jarvis-voice` into this repo or installer copy.
- Linux-first playback polish (document macOS as primary).
- Changing cloud `environment.json` for F5.

## Files to touch

| File | Change |
|------|--------|
| `.claude/hooks/core/tts.py` | Provider selection + async spawn |
| `.claude/hooks/core/jarvis_say_worker.py` | **new** detached worker |
| `.env.example` | New env vars |
| `README.md` | Local TTS setup section |
| `scripts/install_jarvis.py` | Done-message line |
| `tests/test_tts.py` | **new** unit tests |
