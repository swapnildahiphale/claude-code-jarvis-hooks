# 🤖 Claude Code Jarvis Hooks

> *"Sir, the code is polished and waiting—shall we embrace the future?"* - Enhance your Claude Code experience with intelligent voice notifications.

## 🎬 Demo

<div align="center">
  <a href="https://www.youtube.com/watch?v=5-75ju8RAG4">
    <img src="https://img.youtube.com/vi/5-75ju8RAG4/maxresdefault.jpg" alt="Claude Code Jarvis Demo" width="600">
  </a>
  <br><br>
  <strong>🎬 Watch the Demo: Claude Code with JARVIS-like Voice Notifications</strong>
  <br>
  <em>Experience enhanced development workflow with intelligent voice feedback</em>
</div>

---

## 🚀 What is Claude Code Jarvis?

Claude Code Jarvis is a sophisticated hook system that enhances your Claude Code CLI experience with intelligent voice notifications. Get spoken feedback when Claude needs your input with AI-generated messages and multiple TTS providers.

### ✨ Key Features

- 🎙️ **Voice Notifications** - Get spoken alerts when Claude needs your input
- 🎭 **AI-Generated Messages** - Witty, professional notification messages
- 🔄 **Multi-Provider TTS** - Works with ElevenLabs, OpenAI, and local TTS
- 📊 **Operation Logging** - Tracks notification events
- ⚡ **Seamless Integration** - Works transparently with Claude Code

## 🎯 Why Use Jarvis Hooks?

### Before Jarvis
- Silent CLI interactions
- No audio feedback when Claude needs input
- Generic notifications

### After Jarvis
- **"Sir, your expertise is needed"** 🔔
- **Voice notifications when Claude waits for input** 🎵
- **AI-generated witty notification messages** 🎭

## 🔧 Installation & Setup

### Prerequisites
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.8+

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/swapnildahiphale/claude-code-jarvis-hooks.git
   cd claude-code-jarvis-hooks
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Configure your API keys**
   ```bash
   # Required for AI-generated messages
   CLAUDE_HOOKS_OPENAI_API_KEY=your_openai_api_key_here
   
   # Optional: For premium voice quality
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ELEVENLABS_VOICE_ID=your_voice_id_here
   
   # Personalization
   ENGINEER_NAME=YourName
   ```

4. **Activate the hooks**
   ```bash
   # Copy this folder to your project's .claude directory
   # The hooks will automatically activate when using Claude Code
   ```

### Install in another project

From this repo:

```bash
./scripts/install-jarvis.sh /path/to/your-project
./scripts/install-jarvis.sh /path/to/your-project --cloud   # + cloud environment.json
```

This copies `.claude/hooks/`, merges JARVIS entries into `.claude/settings.json` and `.cursor/hooks.json`, and creates `.env` from `.env.example` if missing. Safe to re-run after updates.

Requires `uv` on the machine running Cursor (not installed by this script).

### Local JARVIS voice (optional, no API keys)

Use the [`jarvis-voice`](https://github.com/swapnildahiphale/jarvis-voice) F5-TTS clone instead of ElevenLabs/OpenAI when cloud keys are absent:

1. Set up jarvis-voice: `./scripts/setup.sh`, ensure `jarvis-say` is on PATH.
2. In `.env`: `JARVIS_USE_LOCAL_TTS=true`
3. Test: `uv run .claude/hooks/core/jarvis_say_worker.py --text "JARVIS online, Sir."`

Playback runs in the background after each stop hook (~30–55s for the first clip on Apple Silicon). Cloud agents should leave `JARVIS_USE_LOCAL_TTS=false`.

### Presence gate (optional, speak only when away)

Skip voice when you are already focused on Cursor — useful when you are watching the agent work:

1. In `.env`: `JARVIS_NOTIFY_ONLY_WHEN_AWAY=true`
2. Optional: `JARVIS_PRESENCE_APPS=Cursor` (comma-separated app names)
3. Debug suppressions in `logs/jarvis_voice.jsonl` (`presence_suppressed` events)

When suppressed, the hook skips **both** LLM message generation and TTS (no OpenAI/ElevenLabs tokens spent). Look for `"skipped_llm": true` in `presence_suppressed` log lines.

**Three checkpoints** (each logs `presence_check` or `presence_suppressed` to `logs/jarvis_voice.jsonl`):

| When | What it decides | If Cursor focused |
|------|-----------------|-------------------|
| 1. `guard_voice_pipeline` (start of stop/notification hook) | Skip LLM? | No LLM call, no TTS |
| 2. `speak()` (after message generated) | Skip TTS? | No voice — even if you were away during LLM |
| 3. `jarvis_say_worker` playback (local TTS only, after audio file built) | Skip playback? | No voice if you returned during generation |

So: away when the task finishes → LLM runs → you switch back to Cursor before audio → **step 2 suppresses voice** (`presence_suppressed` without `skipped_llm`). That is intentional.

On macOS, minimized Cursor windows count as away (`reason: app_minimized`). Linux is best-effort via `xdotool`. When detection fails, `JARVIS_PRESENCE_FAIL_OPEN=false` suppresses; `true` plays anyway.

## 🎮 Usage

### Automatic Operation
Once installed, Jarvis hooks work automatically with Claude Code:

```bash
# Normal Claude Code usage
claude

# Jarvis automatically:
# ✅ Provides voice notifications when Claude needs input
# ✅ Generates AI-powered notification messages
# ✅ Handles stop events with voice feedback
```

### Manual Testing

```bash
# Test voice notifications
uv run .claude/hooks/utils/tts/elevenlabs_tts.py "Test message"

# Test AI message generation
uv run .claude/hooks/utils/llm/oai.py --completion
uv run .claude/hooks/utils/llm/oai.py --notification

# Test notification hook
uv run .claude/hooks/notification.py --notify
```

### Cursor IDE

Cursor reads this project's `.claude/settings.json` and runs the same hooks. **Turn-end JARVIS voice works today** via the `Stop` hook (`stop.py --chat`) — no separate `.cursor/hooks.json` setup required.

Copy the `.claude/` folder (and `.env`) into any project, or open this repo directly in Cursor.

**Limitation:** Cursor ignores the Claude `Notification` hook, so "agent needs your input" voice alerts do not fire in Cursor. Completion voice on `stop` does.

**Contextual voice:** On each `stop`, JARVIS reads `transcript_path` from the hook payload, extracts the last turn (or a `<!-- TTS_SUMMARY ... TTS_SUMMARY -->` tag if present), and speaks a one-liner about what just happened. Optional env: `JARVIS_TRANSCRIPT_SETTLE_SECS=2` (wait for transcript flush).

See `docs/superpowers/2026-07-13-jarvis-cursor-hooks-wrap-up.md` for planning notes and future work.

## 🏗️ Architecture

### Hook System
```mermaid
graph TD
    A[Claude Code Notification Event] --> B[notification.py]
    B --> C[Voice Notification]
    
    D[Claude Code Stop Event] --> E[stop.py]
    E --> F[Voice Notification]
```

### Component Structure
```
.claude/
├── hooks/
│   ├── notification.py      # Voice notifications
│   ├── stop.py              # Stop event notifications
│   ├── subagent_stop.py     # Subagent stop notifications
│   └── utils/
│       ├── llm/             # AI message generation
│       │   ├── oai.py       # OpenAI integration
│       │   └── anth.py      # Anthropic fallback
│       └── tts/             # Text-to-speech
│           ├── elevenlabs_tts.py
│           ├── openai_tts.py
│           └── pyttsx3_tts.py
├── settings.json            # Hook configuration
```


## 🎨 AI-Generated Notifications

Jarvis generates sophisticated notification messages with:
- **Calm, articulate tone** with subtle Irish accent
- **Quietly confident** with gentle wit
- **Professional yet approachable** style
- **Precise diction** and poised pacing

### Sample Notification Messages
- *"Sir, your input is needed—lest I proceed without divine guidance."*
- *"Swapnil, your input is kindly requested—no pressure, Sir."*
- *"The code is polished and waiting—shall we embrace the future, Sir?"*
- *"All set, Swapnil—ready for whatever’s next with quiet confidence."*

## 📊 Logging & Monitoring

All operations are logged to `logs/`:
- `notification.json` - Voice notifications
- `stop.json` - Stop event notifications
- `chat.json` - Chat-related events

## 🛠️ Configuration

### Environment Variables
```bash
# Core Configuration
ENGINEER_NAME=YourName                    # For personalized messages
CLAUDE_HOOKS_OPENAI_API_KEY=sk-...        # OpenAI API key
CLAUDE_HOOKS_OPENAI_MODEL=gpt-5-nano

# Voice Configuration
ELEVENLABS_API_KEY=sk_...                 # ElevenLabs API key
ELEVENLABS_VOICE_ID=HzHW0uLdA9prFl1Z5krC # Voice selection
ELEVENLABS_MODEL_ID=eleven_turbo_v2_5     # Model selection
```

### Permissions
Configure allowed tools in `.claude/settings.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(mkdir:*)",
      "Bash(uv:*)",
      "Write",
      "Edit"
    ]
  }
}
```

## 🔄 Fallback System

Jarvis uses intelligent fallbacks:
1. **ElevenLabs TTS** (Premium quality) → 
2. **OpenAI TTS** (Good quality) → 
3. **pyttsx3** (Local, no API required)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Anthropic** for the amazing Claude Code CLI
- **OpenAI** for powering the AI personality
- **ElevenLabs** for premium voice synthesis
- **Iron Man** for the JARVIS inspiration

---

<div align="center">
  <h3>🚀 Ready to enhance your development workflow?</h3>
  <p><em>"Sir, your workspace awaits—shall we craft something remarkable?"</em></p>
</div>