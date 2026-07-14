# jarvis-say Local TTS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Opt-in local JARVIS voice via `jarvis-say` with background playback when cloud TTS keys are absent.

**Architecture:** `speak()` checks ElevenLabs → OpenAI → local (`JARVIS_USE_LOCAL_TTS`) → pyttsx3. Local path spawns `jarvis_say_worker.py` detached; worker runs `jarvis-say` then `afplay`.

**Tech Stack:** Python 3.11, `jarvis-say` CLI (F5-TTS), `uv`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-13-jarvis-say-tts-design.md`

---

### Task 1: TTS selection helpers + worker

**Files:**
- Create: `.claude/hooks/core/jarvis_say_worker.py`
- Modify: `.claude/hooks/core/tts.py`
- Test: `tests/test_tts.py`

- [x] Add `local_tts_enabled()`, `jarvis_say_path()`, `should_use_local_tts()`, `speak_local_async()`
- [x] Worker: generate WAV, play via `afplay`/`ffplay`, log failures
- [x] Unit tests for provider order and async spawn

### Task 2: Configuration & docs

**Files:**
- Modify: `.env.example`, `README.md`, `scripts/install_jarvis.py`

- [x] Document `JARVIS_USE_LOCAL_TTS`, optional `JARVIS_SAY_PATH`, `JARVIS_SAY_TIMEOUT`
- [x] README local TTS setup section
- [x] Installer done-message line

### Task 3: Verify

- [x] Run: `uv run --with pytest pytest tests/ -v`
