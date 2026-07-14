from core.debounce import read_stop_state, write_stop_state, state_file_for

def test_write_and_read_stop_state(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_STATE_DIR", str(tmp_path))
    write_stop_state("sess-1", 12345.0)
    assert read_stop_state("sess-1") == 12345.0

def test_state_file_isolated_per_session(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_STATE_DIR", str(tmp_path))
    write_stop_state("a", 1.0)
    write_stop_state("b", 2.0)
    assert read_stop_state("a") == 1.0
    assert read_stop_state("b") == 2.0
    assert state_file_for("a") != state_file_for("b")
