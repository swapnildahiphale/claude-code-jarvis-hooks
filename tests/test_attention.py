from core.attention import is_attention_command

def test_sudo_triggers_attention():
    assert is_attention_command("sudo rm file") is True

def test_safe_ls_does_not_trigger():
    assert is_attention_command("ls -la") is False

def test_rm_rf_triggers():
    assert is_attention_command("rm -rf /tmp/foo") is True

def test_curl_triggers():
    assert is_attention_command("curl https://example.com") is True

def test_git_push_force_triggers():
    assert is_attention_command("git push --force origin main") is True
