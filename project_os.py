from __future__ import annotations

import argparse
import subprocess
import sys

from local_bridge.project_cli import main as project_cli_main
from local_bridge.providers import print_doctor


def main() -> int:
    parser = argparse.ArgumentParser(description="Team Project OS")
    sub = parser.add_subparsers(dest="sub", required=True)

    create = sub.add_parser("create", help="AI와 CMD에서 대화하며 새 프로젝트 생성")
    create.add_argument("--provider", default="codex", choices=["codex", "claude", "opencode", "antigravity", "dry-run"])
    create.add_argument("--server", default="http://localhost:8000")
    create.add_argument("--member", default="CMD User")
    create.add_argument("--access-key", default="")
    create.add_argument("--cwd", default=".")
    create.add_argument("--command", default="")
    create.add_argument("--initial", default="")

    sub.add_parser("doctor", help="연결 가능한 AI CLI 확인")

    server = sub.add_parser("server", help="Team Project OS 웹 서버 실행")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", default="8000")

    args = parser.parse_args()
    if args.sub == "doctor":
        print_doctor()
        return 0
    if args.sub == "server":
        return subprocess.call([
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", args.host, "--port", args.port,
        ])
    cli_args = [
        "create",
        "--provider", args.provider,
        "--server", args.server,
        "--member", args.member,
        "--cwd", args.cwd,
    ]
    if args.access_key:
        cli_args += ["--access-key", args.access_key]
    if args.command:
        cli_args += ["--command", args.command]
    if args.initial:
        cli_args += ["--initial", args.initial]
    return project_cli_main(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
