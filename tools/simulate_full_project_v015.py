from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_v015_materialization.py", "-v"]
result = subprocess.run(cmd, cwd=ROOT)
if result.returncode:
    raise SystemExit(result.returncode)
print("V0.15 PROJECT + 13 DOCUMENTS + 3 DIAGRAMS + APPLY NON-REGRESSION: PASS")
