import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.presence import (
    frontmost_app_name,
    presence_apps,
    presence_fail_open,
    presence_gate_enabled,
    presence_timeout_ms,
    probe_frontmost,
    should_notify,
)
from core.tts import speak


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "YES"])
def test_presence_gate_enabled_truthy(value):
    with patch.dict(os.environ, {"JARVIS_NOTIFY_ONLY_WHEN_AWAY": value}, clear=False):
        assert presence_gate_enabled() is True


@pytest.mark.parametrize("value", ["", "false", "0", "no"])
def test_presence_gate_enabled_falsey(value):
    env = {k: v for k, v in os.environ.items() if k != "JARVIS_NOTIFY_ONLY_WHEN_AWAY"}
    if value:
        env["JARVIS_NOTIFY_ONLY_WHEN_AWAY"] = value
    with patch.dict(os.environ, env, clear=True):
        assert presence_gate_enabled() is False


def test_presence_apps_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("JARVIS_PRESENCE_APPS", None)
        assert presence_apps() == ["Cursor"]


def test_presence_apps_custom_list():
    with patch.dict(
        os.environ,
        {"JARVIS_PRESENCE_APPS": "Cursor, Code, Safari"},
        clear=False,
    ):
        assert presence_apps() == ["Cursor", "Code", "Safari"]


def test_should_notify_gate_disabled():
    with patch.dict(os.environ, {"JARVIS_NOTIFY_ONLY_WHEN_AWAY": "false"}, clear=False):
        assert should_notify() is True


@patch("core.presence.probe_frontmost", return_value=("Cursor", None))
def test_should_notify_cursor_frontmost_suppresses(_mock_probe):
    with patch.dict(os.environ, {"JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true"}, clear=False):
        assert should_notify() is False


@patch("core.presence.probe_frontmost", return_value=("Safari", None))
def test_should_notify_other_app_notifies(_mock_probe):
    with patch.dict(os.environ, {"JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true"}, clear=False):
        assert should_notify() is True


@patch("core.presence.probe_frontmost", return_value=(None, "osascript_error"))
def test_should_notify_detection_failure_fail_open(_mock_probe):
    with patch.dict(
        os.environ,
        {"JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true", "JARVIS_PRESENCE_FAIL_OPEN": "true"},
        clear=False,
    ):
        assert should_notify() is True


@patch("core.presence.probe_frontmost", return_value=(None, "osascript_error"))
def test_should_notify_detection_failure_fail_closed(_mock_probe):
    with patch.dict(
        os.environ,
        {
            "JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true",
            "JARVIS_PRESENCE_FAIL_OPEN": "false",
        },
        clear=False,
    ):
        assert should_notify() is False


def test_presence_fail_open_default():
    os.environ.pop("JARVIS_PRESENCE_FAIL_OPEN", None)
    assert presence_fail_open() is True


def test_presence_timeout_default_is_two_seconds():
    os.environ.pop("JARVIS_PRESENCE_TIMEOUT_MS", None)
    assert presence_timeout_ms() == 2000


@patch("core.presence.subprocess.run")
def test_probe_frontmost_darwin_timeout(mock_run):
    mock_run.side_effect = __import__("subprocess").TimeoutExpired(cmd="osascript", timeout=2)
    with patch("core.presence.platform.system", return_value="Darwin"):
        name, err = probe_frontmost()
    assert name is None
    assert "osascript_timeout" in (err or "")


@patch("core.presence.probe_frontmost", return_value=(None, "osascript_timeout_200ms"))
def test_should_notify_timeout_fail_closed(_mock_probe, monkeypatch):
    with patch.dict(
        os.environ,
        {
            "JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true",
            "JARVIS_PRESENCE_FAIL_OPEN": "false",
        },
        clear=False,
    ):
        assert should_notify() is False


@patch("core.presence.probe_frontmost", return_value=(None, "osascript_timeout_200ms"))
def test_should_notify_timeout_fail_open(_mock_probe, monkeypatch):
    with patch.dict(
        os.environ,
        {
            "JARVIS_NOTIFY_ONLY_WHEN_AWAY": "true",
            "JARVIS_PRESENCE_FAIL_OPEN": "true",
        },
        clear=False,
    ):
        assert should_notify() is True


@patch("core.presence.subprocess.run")
def test_frontmost_app_darwin(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Cursor\n")
    with patch("core.presence.platform.system", return_value="Darwin"):
        assert frontmost_app_name() == "Cursor"
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0][0] == "osascript"


@patch("core.tts.should_notify", return_value=False)
@patch("core.tts.subprocess.run")
@patch("core.tts.subprocess.Popen")
def test_speak_respects_presence_gate(mock_popen, mock_run, _mock_notify, monkeypatch):
    monkeypatch.setattr("core.tts.should_use_local_tts", lambda: False)
    monkeypatch.setattr("core.tts.get_tts_script_path", lambda: None)
    speak("Sir, suppressed.")
    mock_popen.assert_not_called()
    mock_run.assert_not_called()


@patch("core.jarvis_say_worker.should_notify", return_value=False)
@patch("core.jarvis_say_worker.subprocess.run")
@patch("core.jarvis_say_worker._play_wav", return_value=True)
def test_worker_skips_playback_when_not_notifying(
    mock_play, mock_run, _mock_notify, tmp_path, monkeypatch
):
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

    mock_play.assert_not_called()
