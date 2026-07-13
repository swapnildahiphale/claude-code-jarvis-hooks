import re

# High-signal shell commands that likely need user approval in Cursor.
_PATTERNS = [
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bssh\s", re.I),
    re.compile(r"\bscp\s", re.I),
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\brm\s+-r\b", re.I),
    re.compile(r"\bcurl\b", re.I),
    re.compile(r"\bwget\b", re.I),
    re.compile(r"\bnc\s", re.I),
    re.compile(r"\bkubectl\s+delete\b", re.I),
    re.compile(r"\bgit\s+push\b.*(-f|--force)\b", re.I),
]


def is_attention_command(command: str) -> bool:
    if not command or not command.strip():
        return False
    return any(p.search(command) for p in _PATTERNS)
