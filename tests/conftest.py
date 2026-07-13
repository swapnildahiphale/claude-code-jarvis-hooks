import sys
from pathlib import Path

HOOKS_ROOT = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_ROOT))
