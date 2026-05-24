"""CI smoke test module (also invoked by scripts/ci_smoke.py)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_smoke_script_exits_zero():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ci_smoke.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout
