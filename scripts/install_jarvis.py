#!/usr/bin/env python3
"""Install JARVIS hooks into another project. See docs/superpowers/specs/2026-07-13-jarvis-installer-design.md"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

JARVIS_SENTINEL = ".claude/hooks/stop.py"
JARVIS_STOP_COMMAND = "uv run .claude/hooks/stop.py --chat"

CLAUDE_STOP_ENTRY = {
    "matcher": "",
    "hooks": [
        {"type": "command", "command": JARVIS_STOP_COMMAND},
    ],
}

CURSOR_STOP_ENTRY = {"command": JARVIS_STOP_COMMAND}

CLOUD_ENV_JSON = {
    "install": "curl -LsSf https://astral.sh/uv/install.sh | sh",
}


def repo_root() -> Path:
    """Resolve jarvis repo root; honors JARVIS_REPO_ROOT when set."""
    default = Path(__file__).resolve().parent.parent
    if (default / ".claude" / "hooks" / "stop.py").exists():
        return default

    raw = os.getenv("JARVIS_REPO_ROOT", "").strip()
    if raw:
        override = Path(raw).expanduser().resolve()
        if (override / ".claude" / "hooks" / "stop.py").exists():
            return override

    if (default / ".claude" / "hooks" / "stop.py").exists():
        return default

    raise SystemExit("Cannot find jarvis repo root (.claude/hooks/stop.py missing)")


def is_jarvis_command(command: str | None) -> bool:
    return bool(command and JARVIS_SENTINEL in command)


def atomic_write_json(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".jarvis.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def copy_hooks(source_repo: Path, target: Path, dry_run: bool) -> None:
    src = source_repo / ".claude" / "hooks"
    dst = target / ".claude" / "hooks"
    if not src.is_dir():
        raise SystemExit(f"Source hooks missing: {src}")
    if dry_run:
        print(f"  [dry-run] would copy {src} -> {dst}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"  copied hooks -> {dst}")


def copy_env_example(source_repo: Path, target: Path, dry_run: bool) -> None:
    src = source_repo / ".env.example"
    dst = target / ".env.example"
    if dst.exists():
        print("  .env.example exists, skipped")
        return
    if not src.exists():
        print("  warning: no .env.example in source repo")
        return
    if dry_run:
        print(f"  [dry-run] would copy {src} -> {dst}")
        return
    shutil.copy2(src, dst)
    print("  copied .env.example")


def _filter_jarvis_stop_entries(entries: list) -> list:
    """Remove JARVIS-owned entries from a hook event list."""
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            kept.append(entry)
            continue
        inner = entry.get("hooks") or []
        if isinstance(inner, list):
            inner_kept = [
                h
                for h in inner
                if not (isinstance(h, dict) and is_jarvis_command(h.get("command")))
            ]
            if inner_kept:
                new_entry = dict(entry)
                new_entry["hooks"] = inner_kept
                kept.append(new_entry)
        elif is_jarvis_command(entry.get("command")):
            continue
        else:
            kept.append(entry)
    return kept


def merge_claude_settings(target: Path, dry_run: bool) -> None:
    path = target / ".claude" / "settings.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    stop_list = hooks.get("Stop", [])
    if not isinstance(stop_list, list):
        stop_list = []
    stop_list = _filter_jarvis_stop_entries(stop_list)
    stop_list.append(CLAUDE_STOP_ENTRY)
    hooks["Stop"] = stop_list

    atomic_write_json(path, data, dry_run)
    print(f"  merged JARVIS Stop -> {path}")


def merge_cursor_hooks(target: Path, dry_run: bool) -> None:
    path = target / ".cursor" / "hooks.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
    else:
        data = {"version": 1, "hooks": {}}

    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    stop_list = hooks.get("stop", [])
    if not isinstance(stop_list, list):
        stop_list = []
    stop_list = [
        e
        for e in stop_list
        if not (isinstance(e, dict) and is_jarvis_command(e.get("command")))
    ]
    stop_list.append(dict(CURSOR_STOP_ENTRY))
    hooks["stop"] = stop_list

    atomic_write_json(path, data, dry_run)
    print(f"  merged JARVIS stop -> {path}")


def setup_env(source_repo: Path, target: Path, force: bool, dry_run: bool) -> None:
    env_path = target / ".env"
    example_src = source_repo / ".env.example"

    if env_path.exists() and not force:
        print("  .env exists, skipped (use --force-env to recreate)")
        return

    if not example_src.exists():
        print("  warning: no .env.example; cannot create .env")
        return

    if env_path.exists() and force:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = target / f".env.bak.{ts}"
        if dry_run:
            print(f"  [dry-run] would backup {env_path} -> {backup}")
        else:
            shutil.copy2(env_path, backup)
            print(f"  backed up .env -> {backup}")

    if dry_run:
        print(f"  [dry-run] would create {env_path} from .env.example")
        return

    shutil.copy2(example_src, env_path)
    print("  created .env from .env.example — fill in API keys")


def setup_cloud_env(target: Path, dry_run: bool) -> None:
    path = target / ".cursor" / "environment.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise SystemExit(f"Expected object in {path}")
        if "install" not in data:
            data["install"] = CLOUD_ENV_JSON["install"]
    else:
        data = dict(CLOUD_ENV_JSON)

    atomic_write_json(path, data, dry_run)
    print(f"  cloud environment -> {path}")
    print("  reminder: add API keys in Cursor Secrets dashboard for cloud agents")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install JARVIS voice hooks into another project.",
    )
    parser.add_argument("target", type=Path, help="Path to target project directory")
    parser.add_argument("--cloud", action="store_true", help="Also write .cursor/environment.json")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    parser.add_argument(
        "--force-env",
        action="store_true",
        help="Recreate .env from example (backs up first)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target = args.target.expanduser().resolve()

    if not target.is_dir():
        print(f"error: target is not a directory: {target}", file=sys.stderr)
        return 1

    source = repo_root()
    print(f"Installing JARVIS hooks from {source}")
    print(f"  -> {target}")
    if args.dry_run:
        print("  (dry run)")

    copy_hooks(source, target, args.dry_run)
    copy_env_example(source, target, args.dry_run)
    setup_env(source, target, args.force_env, args.dry_run)
    merge_claude_settings(target, args.dry_run)
    merge_cursor_hooks(target, args.dry_run)

    if args.cloud:
        setup_cloud_env(target, args.dry_run)

    print("\nDone.")
    print("  Local: enable third-party skills in Cursor; fill .env with API keys.")
    print("  Cloud: commit .cursor/hooks.json; add secrets in Cursor dashboard.")
    print("  Local TTS: install jarvis-voice, set JARVIS_USE_LOCAL_TTS=true in .env (macOS only).")
    print('  Test:  uv run .claude/hooks/utils/tts/elevenlabs_tts.py "JARVIS online, Sir."')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
