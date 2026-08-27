from __future__ import annotations

import argparse
import subprocess
import sys

from local_bridge.project_cli import main as project_cli_main
from local_bridge.providers import SUPPORTED_PROVIDERS, print_doctor


def _add_design_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default="codex", choices=SUPPORTED_PROVIDERS)
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--member", default="CMD User")
    parser.add_argument("--access-key", default="")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--command", default="")
    parser.add_argument("--initial", default="")
    parser.add_argument("--session-file", default="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Team Project OS")
    sub = parser.add_subparsers(dest="sub", required=True)

    design = sub.add_parser("design", help="AI와 자유롭게 프로젝트를 구체화한 뒤 /apply로 생성")
    _add_design_args(design)
    create = sub.add_parser("create", help="design 명령의 호환 별칭")
    _add_design_args(create)

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
        "design",
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
    if args.session_file:
        cli_args += ["--session-file", args.session_file]
    return project_cli_main(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
