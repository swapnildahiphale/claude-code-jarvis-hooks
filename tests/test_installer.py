import json

import install_jarvis as installer
import pytest

JARVIS_CMD = installer.JARVIS_STOP_COMMAND


@pytest.fixture
def source_repo(tmp_path):
    """Minimal fake jarvis repo."""
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "stop.py").write_text("# stub\n")
    (hooks / "core").mkdir()
    (hooks / "core" / "__init__.py").write_text("")
    (tmp_path / ".env.example").write_text("ENGINEER_NAME=Test\n")
    return tmp_path


@pytest.fixture
def target_project(tmp_path):
    t = tmp_path / "target"
    t.mkdir()
    return t


def test_fresh_install(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project)]) == 0
    assert (target_project / ".claude" / "hooks" / "stop.py").exists()
    settings = json.loads((target_project / ".claude" / "settings.json").read_text())
    assert any(
        JARVIS_CMD in h.get("command", "")
        for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
    )
    cursor = json.loads((target_project / ".cursor" / "hooks.json").read_text())
    assert any(JARVIS_CMD in e.get("command", "") for e in cursor["hooks"]["stop"])
    assert (target_project / ".env").exists()


def test_preserves_unrelated_hooks(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    settings_path = target_project / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "matcher": "",
                            "hooks": [{"type": "command", "command": "echo other"}],
                        }
                    ],
                },
            }
        )
    )
    cursor_path = target_project / ".cursor" / "hooks.json"
    cursor_path.parent.mkdir(parents=True)
    cursor_path.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {"stop": [{"command": "echo legacy"}]},
            }
        )
    )
    assert installer.main([str(target_project)]) == 0
    settings = json.loads(settings_path.read_text())
    commands = [
        h.get("command")
        for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
    ]
    assert "echo other" in commands
    assert JARVIS_CMD in commands
    cursor = json.loads(cursor_path.read_text())
    cmds = [e.get("command") for e in cursor["hooks"]["stop"]]
    assert "echo legacy" in cmds
    assert JARVIS_CMD in cmds


def test_rerun_replaces_jarvis_only(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    installer.main([str(target_project)])
    # Tamper hook file
    (target_project / ".claude" / "hooks" / "stop.py").write_text("# old\n")
    installer.main([str(target_project)])
    assert "stub" in (target_project / ".claude" / "hooks" / "stop.py").read_text()
    settings = json.loads((target_project / ".claude" / "settings.json").read_text())
    jarvis_count = sum(
        1
        for entry in settings["hooks"]["Stop"]
        for h in entry.get("hooks", [])
        if installer.is_jarvis_command(h.get("command"))
    )
    assert jarvis_count == 1


def test_dry_run_no_writes(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project), "--dry-run"]) == 0
    assert not (target_project / ".claude" / "hooks").exists()
    assert not (target_project / ".claude" / "settings.json").exists()


def test_cloud_flag(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    assert installer.main([str(target_project), "--cloud"]) == 0
    env_json = json.loads((target_project / ".cursor" / "environment.json").read_text())
    assert "install" in env_json
    assert "uv" in env_json["install"]


def test_invalid_json_fails(source_repo, target_project, monkeypatch):
    monkeypatch.setattr(installer, "repo_root", lambda: source_repo)
    bad = target_project / ".claude" / "settings.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json")
    with pytest.raises(SystemExit):
        installer.main([str(target_project)])
