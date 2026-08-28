from __future__ import annotations

import subprocess
import sys


command = [
    sys.executable,
    "-m",
    "unittest",
    "discover",
    "-s",
    "tests",
    "-p",
    "test_conversation_import_v016.py",
    "-v",
]
completed = subprocess.run(command, check=False)
if completed.returncode != 0:
    raise SystemExit(completed.returncode)
print("V0.16 NATIVE CONVERSATION IMPORT SCENARIOS A-H: PASS")
