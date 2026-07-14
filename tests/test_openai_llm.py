import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

LLM_DIR = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "utils" / "llm"
sys.path.insert(0, str(LLM_DIR))

import oai  # noqa: E402


def test_max_completion_tokens_default():
    os.environ.pop("CLAUDE_HOOKS_OPENAI_MAX_COMPLETION_TOKENS", None)
    assert oai._max_completion_tokens() == 2000


def test_max_completion_tokens_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_HOOKS_OPENAI_MAX_COMPLETION_TOKENS", "3000")
    assert oai._max_completion_tokens() == 3000


def test_prompt_llm_uses_gpt5_nano_conventions(monkeypatch):
    monkeypatch.setenv("CLAUDE_HOOKS_OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("CLAUDE_HOOKS_OPENAI_MODEL", raising=False)
    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            msg = MagicMock(content="Sir, online.")
            choice = MagicMock(message=msg, finish_reason="stop")
            return MagicMock(choices=[choice])

    class FakeClient:
        chat = MagicMock(completions=FakeCompletions())

    with patch("openai.OpenAI", return_value=FakeClient()):
        result = oai.prompt_llm("hello")

    assert result == "Sir, online."
    assert captured["model"] == "gpt-5-nano"
    assert captured["max_completion_tokens"] == 2000
    assert "max_tokens" not in captured
    assert "temperature" not in captured
