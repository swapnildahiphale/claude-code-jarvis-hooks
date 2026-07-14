import json
from pathlib import Path

from core.transcript import (
    extract_tts_summary,
    parse_transcript_lines,
    read_turn_context,
)


def test_extract_tts_summary_html_comment():
    text = "Done.\n<!-- TTS_SUMMARY\nThe plan is ready for review.\nTTS_SUMMARY -->"
    assert extract_tts_summary(text) == "The plan is ready for review."


def test_parse_cursor_format_messages():
    lines = [
        json.dumps({
            "role": "user",
            "message": {"content": [{"type": "text", "text": "Write a plan"}]},
        }),
        json.dumps({
            "role": "assistant",
            "message": {"content": [{"type": "text", "text": "Plan is in docs/plan.md"}]},
        }),
    ]
    user, assistant, summary = parse_transcript_lines(lines)
    assert user == "Write a plan"
    assert assistant == "Plan is in docs/plan.md"
    assert summary is None


def test_extract_tts_summary_ignores_code_fence_examples():
    text = (
        "See example:\n"
        "```html\n"
        "<!-- TTS_SUMMARY\n"
        "The plan is written and waiting for your inputs.\n"
        "TTS_SUMMARY -->\n"
        "```\n"
        "Done for real.\n"
        "<!-- TTS_SUMMARY\n"
        "Hooks documented, Sir.\n"
        "TTS_SUMMARY -->"
    )
    assert extract_tts_summary(text) == "Hooks documented, Sir."


def test_read_turn_context_from_file(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps({
            "role": "assistant",
            "message": {
                "content": [{
                    "type": "text",
                    "text": "<!-- TTS_SUMMARY\nHooks documented.\nTTS_SUMMARY -->",
                }],
            },
        }) + "\n"
    )
    ctx = read_turn_context(transcript)
    assert ctx["tts_summary"] == "Hooks documented."
