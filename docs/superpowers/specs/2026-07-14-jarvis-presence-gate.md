# JARVIS Presence Gate — Design Spec

**Date:** 2026-07-14  
**Status:** Implemented

## Problem

Stop-hook voice fires on every agent turn. When the user is already in Cursor watching the agent work, audio is redundant and distracting.

Cursor hooks do not expose focus/presence in the `stop` payload. A hook-side OS probe is required.

## Solution

Opt-in presence gate in `core/presence.py`, enforced centrally in `core.tts.speak()` so all TTS paths share one policy.

```
stop / notification / subagent_stop / debounce_worker
  → speak()
    → should_notify()  [loads .env, probes frontmost app]
      → False: log presence_suppressed, return
      → True:  existing TTS chain (cloud / jarvis-say / pyttsx3)
```

`jarvis_say_worker.py` re-checks before playback because generation can take 30–55s.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `JARVIS_NOTIFY_ONLY_WHEN_AWAY` | `false` | Master switch (`true` enables gate) |
| `JARVIS_PRESENCE_APPS` | `Cursor` | Comma-separated frontmost app names that suppress voice |
| `JARVIS_PRESENCE_FAIL_OPEN` | `true` | When probe fails: `true` = speak anyway, `false` = suppress |
| `JARVIS_PRESENCE_TIMEOUT_MS` | `2000` | Probe timeout (200ms was too short for cold `osascript`) |

## Platform probes

- **macOS:** `osascript` → System Events frontmost process name
- **Linux:** `xdotool getwindowfocus getwindowname` (best-effort)

## Logging (`logs/jarvis_voice.jsonl`)

| Event | When |
|-------|------|
| `presence_check` | Gate enabled; records `frontmost`, `notify`, `reason`, `detect_error` |
| `presence_suppressed` | TTS skipped (`speak()` or worker playback stage) |

Example (suppressed while in Cursor):

```json
{"event": "presence_check", "gate_enabled": true, "frontmost": "Cursor", "notify": false, "reason": "app_focused"}
{"event": "presence_suppressed", "text_len": 115}
```

## Known limitations

- App-level only (cannot detect wrong chat tab inside Cursor)
- Cursor frontmost while reading code in editor still suppresses (intended)
- Cloud/headless: probe fails; behavior follows `JARVIS_PRESENCE_FAIL_OPEN`

## Files changed

- `core/presence.py` — probe + gate logic
- `core/tts.py` — gate before TTS
- `core/jarvis_say_worker.py` — gate before playback
- `notification.py`, `subagent_stop.py` — route through `speak()`
- `tests/test_presence.py` — unit tests
- `.env.example`, `README.md`, `scripts/install_jarvis.py` — docs
