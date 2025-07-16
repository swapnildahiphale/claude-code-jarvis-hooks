# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code hooks project that provides enhanced AI agent capabilities with voice notifications and safety features. The system integrates with OpenAI for LLM-generated messages and ElevenLabs for text-to-speech notifications.

## Architecture

### Hook System
The project uses Claude Code's hook system to intercept and enhance tool usage:

- **Pre-tool hooks** (`pre_tool_use.py`): Security validation including:
  - Blocks dangerous `rm -rf` commands with comprehensive pattern matching
  - Prevents access to `.env` files containing sensitive data
  - Logs all tool usage for auditing

- **Post-tool hooks** (`post_tool_use.py`): Logs completed tool usage

- **Notification hooks** (`notification.py`): Provides intelligent voice notifications using:
  - LLM-generated messages with sophisticated AI assistant persona
  - Multi-provider TTS support (ElevenLabs > OpenAI > pyttsx3)
  - Smart message prioritization to avoid spam

### Utilities Structure
- `utils/llm/`: LLM integration modules
  - `oai.py`: OpenAI integration for generating witty, professional completion/notification messages
  - `anth.py`: Anthropic integration (fallback)
  
- `utils/tts/`: Text-to-speech modules with fallback priority:
  - `elevenlabs_tts.py`: ElevenLabs TTS (highest quality)
  - `openai_tts.py`: OpenAI TTS (fallback)
  - `pyttsx3_tts.py`: Local TTS (no API required)

## Commands

The project uses `uv` for Python script execution:

```bash
# Run hooks (automatically called by Claude Code)
uv run .claude/hooks/pre_tool_use.py
uv run .claude/hooks/post_tool_use.py
uv run .claude/hooks/notification.py --notify

# Test TTS directly
uv run .claude/hooks/utils/tts/elevenlabs_tts.py "test message"

# Test LLM message generation
uv run .claude/hooks/utils/llm/oai.py --completion
uv run .claude/hooks/utils/llm/oai.py --notification
```

## Configuration

### Environment Variables
- `ENGINEER_NAME`: User's name for personalized messages
- `CLAUDE_HOOKS_OPENAI_API_KEY`: OpenAI API key
- `CLAUDE_HOOKS_OPENAI_API_BASE_URL`: OpenAI API base URL
- `CLAUDE_HOOKS_OPENAI_MODEL`: Model name (default: "gpt-4.1-nano")
- `ELEVENLABS_API_KEY`: ElevenLabs API key
- `ELEVENLABS_VOICE_ID`: ElevenLabs voice ID
- `ELEVENLABS_MODEL_ID`: ElevenLabs model ID

### Permissions
The `.claude/settings.json` configures allowed tools and commands:
- Bash commands: mkdir, uv, find, mv, grep, npm, ls, cp, python, chmod, touch
- File operations: Write, Edit
- Notification and Stop hooks enabled

## AI Persona

The system generates messages with a sophisticated AI assistant persona:
- Calm, articulate voice with subtle Irish accent
- Intelligent, efficient, quietly confident
- Sleek, slightly robotic timbre with warmth and gentle wit
- Precise diction, poised pacing, nuanced dry humor
- Professional yet approachable tone