import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.tts import (
    cloud_tts_available,
    get_tts_script_path,
    jarvis_say_path,
    local_tts_enabled,
    should_use_local_tts,
    speak,
    speak_local_async,
)


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "YES"])
def test_local_tts_enabled_truthy(value):
    with patch.dict(os.environ, {"JARVIS_USE_LOCAL_TTS": value}, clear=False):
        assert local_tts_enabled() is True


@pytest.mark.parametrize("value", ["", "false", "0", "no"])
def test_local_tts_enabled_falsey(value):
    env = {k: v for k, v in os.environ.items() if k != "JARVIS_USE_LOCAL_TTS"}
    if value:
        env["JARVIS_USE_LOCAL_TTS"] = value
    with patch.dict(os.environ, env, clear=True):
        assert local_tts_enabled() is False


def test_cloud_keys_beat_local_tts(tmp_path, monkeypatch):
    td = tmp_path / "tts"
    td.mkdir()
    (td / "elevenlabs_tts.py").write_text("# stub\n")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "key")
    monkeypatch.setenv("JARVIS_USE_LOCAL_TTS", "true")
    monkeypatch.setattr("core.tts.tts_dir", lambda: td)
    monkeypatch.setattr("core.tts.jarvis_say_path", lambda: "/bin/jarvis-say")
    assert cloud_tts_available() is True
    assert should_use_local_tts() is False


def test_local_tts_when_no_cloud_keys(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_HOOKS_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("JARVIS_USE_LOCAL_TTS", "true")
    monkeypatch.setattr("core.tts.jarvis_say_path", lambda: "/bin/jarvis-say")
    monkeypatch.setattr("core.tts.cloud_tts_available", lambda: False)
    assert should_use_local_tts() is True


def test_local_tts_missing_binary_falls_through(monkeypatch):
    monkeypatch.setenv("JARVIS_USE_LOCAL_TTS", "true")
    monkeypatch.setattr("core.tts.cloud_tts_available", lambda: False)
    monkeypatch.setattr("core.tts.jarvis_say_path", lambda: None)
    assert should_use_local_tts() is False


@patch("core.tts.should_notify", return_value=True)
@patch("core.tts.subprocess.Popen")
def test_speak_spawns_worker(mock_popen, _mock_notify, monkeypatch):
    monkeypatch.setattr("core.tts.should_use_local_tts", lambda: True)
    speak("Sir, online.")
    mock_popen.assert_called_once()
    args = mock_popen.call_args
    assert "jarvis_say_worker.py" in args[0][0][2]
    assert args[1]["start_new_session"] is True


@patch("core.tts.should_notify", return_value=True)
@patch("core.tts.subprocess.run")
@patch("core.tts.subprocess.Popen")
def test_speak_uses_sync_script_when_cloud(mock_popen, mock_run, _mock_notify, tmp_path, monkeypatch):
    td = tmp_path / "tts"
    td.mkdir()
    script = td / "elevenlabs_tts.py"
    script.write_text("# stub\n")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "key")
    monkeypatch.setattr("core.tts.tts_dir", lambda: td)
    mock_run.return_value = MagicMock(returncode=0, stderr="")
    speak("Hello")
    mock_popen.assert_not_called()
    mock_run.assert_called_once()
    assert str(script) in mock_run.call_args[0][0]


@patch("core.tts.subprocess.Popen")
def test_speak_local_async_command(mock_popen):
    speak_local_async("At your service, Sir.")
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "uv"
    assert cmd[-2] == "--text"
    assert cmd[-1] == "At your service, Sir."


def test_get_tts_script_path_pyttsx3_fallback(tmp_path, monkeypatch):
    td = tmp_path / "tts"
    td.mkdir()
    py = td / "pyttsx3_tts.py"
    py.write_text("# stub\n")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_HOOKS_OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("core.tts.tts_dir", lambda: td)
    assert get_tts_script_path() == str(py)


@patch("core.jarvis_say_worker.should_notify", return_value=True)
@patch("core.jarvis_say_worker.subprocess.run")
@patch("core.jarvis_say_worker._play_wav", return_value=True)
def test_worker_runs_jarvis_say_and_plays(mock_play, mock_run, _mock_notify, tmp_path, monkeypatch):
    from core.jarvis_say_worker import run_jarvis_say

    fake_bin = tmp_path / "jarvis-say"
    fake_bin.write_text("#!/bin/sh\n")
    fake_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):
        out_flag = cmd.index("-o") + 1
        Path(cmd[out_flag]).write_bytes(b"RIFF")
        return MagicMock(returncode=0, stderr="")

    mock_run.side_effect = fake_run
    monkeypatch.setattr("core.jarvis_say_worker.state_dir", lambda: tmp_path)
    monkeypatch.setenv("JARVIS_SAY_PATH", str(fake_bin))

    run_jarvis_say("JARVIS online.")

    jarvis_calls = [c for c in mock_run.call_args_list if c[0][0][0] == str(fake_bin)]
    assert len(jarvis_calls) == 1
    mock_play.assert_called_once()
