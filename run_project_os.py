from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-platform Team Project OS server launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true", help="platform/launcher smoke check only")
    parser.add_argument("--no-install", action="store_true", help="skip pip install")
    args = parser.parse_args()

    if args.check:
        print(f"platform={sys.platform}")
        print(f"root={ROOT}")
        print(f"venv_python={VENV_PYTHON}")
        print(f"requirements={'OK' if (ROOT / 'requirements.txt').exists() else 'MISSING'}")
        return 0 if (ROOT / "requirements.txt").exists() else 2

    if not VENV_PYTHON.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT)
    if not args.no_install:
        subprocess.check_call([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], cwd=ROOT)
    return subprocess.call([
        str(VENV_PYTHON), "-m", "uvicorn", "app.main_v016:app",
        "--host", args.host, "--port", str(args.port),
    ], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
