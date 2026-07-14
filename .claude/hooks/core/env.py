"""Load hook environment from the repo .env reliably."""

from __future__ import annotations

from pathlib import Path

from core.paths import repo_root


def load_hook_env() -> None:
    """Load .env from repo root (works even when hook cwd differs)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = repo_root() / ".env"
    if env_path.exists():
        # Hook subprocesses may inherit empty parent env; repo .env should win.
        load_dotenv(env_path, override=True)
