from __future__ import annotations

import argparse
import json
import platform
import shlex
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CONFIG_PATH = Path.home() / ".team_project_os_bridge.json"


def http_json(method: str, url: str, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"Server connection failed: {e}") from e


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_prompt(bundle: dict) -> str:
    project = bundle["project"]
    task = bundle["task"]
    job = bundle["job"]
    reqs = bundle.get("requirements", [])
    relevant = [r for r in reqs if not task.get("requirement_ref") or r["title"].split()[0] in task.get("requirement_ref", "")]
    req_text = "\n".join(f"- {r['title']}: {r['detail']}" for r in (relevant or reqs[:6]))
    docs = bundle.get("documents", [])
    doc_text = "\n\n".join(
        f"[{d['title']}] status={d['status']}\n{d['content'][:1600]}" for d in docs
    )
    return f"""You are contributing to a shared team project through Team Project OS.

PROJECT
Name: {project['name']}
Goal: {project['goal']}
Description: {project['description']}

CURRENT TASK
ID: TASK-{task['id']}
Title: {task['title']}
Description: {task['description']}
Owner: {task['owner']}
Priority: {task['priority']}
Requirement reference: {task['requirement_ref']}

RELATED REQUIREMENTS
{req_text or '- none registered'}

RELATED PROJECT DOCUMENT EXCERPTS
{doc_text or '- none registered'}

ADDITIONAL INSTRUCTION
{job.get('instruction') or 'Work only within the current task scope.'}

COLLABORATION RULES
- Do not silently change project goals, requirements, or architecture.
- If a design-level change is required, report it as a proposal instead of treating it as approved.
- Perform the task in the repository currently opened by the bridge.
- Run reasonable verification/tests when possible.
- At the end, summarize changed files, verification evidence, remaining risks, and any proposed design change.
"""


def provider_command(provider: str, prompt: str, custom: str | None = None) -> list[str]:
    if custom:
        # Custom command may contain {prompt}. This is intentionally user-controlled local config.
        parts = shlex.split(custom, posix=platform.system() != "Windows")
        out = []
        replaced = False
        for p in parts:
            if "{prompt}" in p:
                out.append(p.replace("{prompt}", prompt))
                replaced = True
            else:
                out.append(p)
        if not replaced:
            out.append(prompt)
        return out
    if provider == "codex":
        return ["codex", "exec", prompt]
    if provider == "claude":
        return ["claude", "-p", prompt, "--output-format", "text"]
    if provider == "opencode":
        return ["opencode", "run", prompt]
    if provider == "antigravity":
        return ["agy", "-p", prompt, "--output-format", "text", "--print-timeout", "45m"]
    if provider == "dry-run":
        return [sys.executable, "-c", "print('DRY RUN: no AI command executed')"]
    raise RuntimeError(f"Unsupported provider: {provider}. Use --command for a custom CLI.")


def register(args):
    access_headers = {"X-Access-Key": args.access_key} if args.access_key else {}
    data = http_json(
        "POST",
        f"{args.server.rstrip('/')}/api/projects/{args.project}/bridges/register",
        {"member_name": args.member, "provider": args.provider, "machine_name": platform.node() or "local"},
        access_headers,
    )
    cfg = load_config()
    cfg.update({
        "server": args.server.rstrip('/'), "project": args.project, "member": args.member,
        "provider": args.provider, "token": data["token"], "repo": args.repo or "",
        "access_key": args.access_key or "", "command": args.command or ""
    })
    save_config(cfg)
    print(f"Bridge registered: {args.member} / {args.provider}")
    print(f"Config saved: {CONFIG_PATH}")
    print("Next: python local_bridge/bridge.py run --repo <your-repository-path> --once")


def assistant_register(args):
    access_headers = {"X-Access-Key": args.access_key} if args.access_key else {}
    data = http_json(
        "POST",
        f"{args.server.rstrip('/')}/api/assistant-bridges/register",
        {"member_name": args.member, "provider": args.provider, "machine_name": platform.node() or "local"},
        access_headers,
    )
    cfg = load_config()
    cfg.update({
        "assistant_server": args.server.rstrip('/'),
        "assistant_member": args.member,
        "assistant_provider": args.provider,
        "assistant_token": data["token"],
        "assistant_access_key": args.access_key or "",
        "assistant_command": args.command or "",
    })
    save_config(cfg)
    print(f"AI Project Assistant paired: {args.member} / {args.provider}")
    print(f"Config saved: {CONFIG_PATH}")
    print("Next: python local_bridge/bridge.py assistant-run --once")


def assistant_submit_result(cfg: dict, job_id: int, status: str, output: str):
    q = urlencode({"token": cfg["assistant_token"]})
    http_json("POST", f"{cfg['assistant_server']}/api/assistant-bridge/results?{q}", {
        "job_id": job_id, "status": status, "output": output
    })


def assistant_run_once(cfg: dict, cwd: Path, custom_command: str | None = None) -> bool:
    q = urlencode({"token": cfg["assistant_token"]})
    bundle = http_json("GET", f"{cfg['assistant_server']}/api/assistant-bridge/jobs?{q}")
    if not bundle or not bundle.get("job"):
        print("No queued Project Assistant message.")
        return False
    job = bundle["job"]
    prompt = bundle["prompt"]
    provider = cfg["assistant_provider"]
    cmd = provider_command(provider, prompt, custom_command or cfg.get("assistant_command") or None)
    print(f"Claimed Project Assistant Job #{job['id']} / {provider}")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60 * 45)
        output = (result.stdout or "") + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
        status = "completed" if result.returncode == 0 else "failed"
        assistant_submit_result(cfg, job["id"], status, output)
        print(f"Assistant Job #{job['id']} -> {status}")
        return True
    except Exception as exc:
        assistant_submit_result(cfg, job["id"], "failed", str(exc))
        raise


def assistant_run(args):
    cfg = load_config()
    required = ["assistant_server", "assistant_token", "assistant_provider"]
    if any(not cfg.get(k) for k in required):
        raise RuntimeError("Project Assistant is not paired. Run assistant-register first.")
    cwd = Path(args.cwd or ".").expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise RuntimeError(f"Working directory not found: {cwd}")
    if args.once:
        assistant_run_once(cfg, cwd, args.command)
        return
    print(f"Watching AI Project Assistant every {args.poll}s. Ctrl+C to stop.")
    while True:
        try:
            ran = assistant_run_once(cfg, cwd, args.command)
            time.sleep(1 if ran else args.poll)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"Assistant bridge error: {exc}", file=sys.stderr)
            time.sleep(args.poll)


def submit_result(cfg, job_id: int, status: str, output: str, evidence: str):
    q = urlencode({"token": cfg["token"]})
    http_json("POST", f"{cfg['server']}/api/bridge/results?{q}", {
        "job_id": job_id, "status": status, "output": output, "evidence": evidence
    })


def run_once(cfg: dict, repo: Path, custom_command: str | None = None) -> bool:
    q = urlencode({"token": cfg["token"]})
    bundle = http_json("GET", f"{cfg['server']}/api/bridge/jobs?{q}")
    if not bundle or not bundle.get("job"):
        print("No queued AI job.")
        return False
    job = bundle["job"]
    prompt = build_prompt(bundle)
    provider = cfg["provider"]
    cmd = provider_command(provider, prompt, custom_command or cfg.get("command") or None)
    print(f"Claimed AI Job #{job['id']} / Task #{job['task_id']} / {provider}")
    print(f"Repository: {repo}")
    try:
        result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=60 * 45)
        output = (result.stdout or "") + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
        status = "completed" if result.returncode == 0 else "failed"
        evidence = f"provider={provider}; returncode={result.returncode}; repo={repo}"
        submit_result(cfg, job["id"], status, output, evidence)
        print(f"Job #{job['id']} -> {status}")
        if output:
            print(output[-4000:])
        return True
    except Exception as e:
        submit_result(cfg, job["id"], "failed", str(e), f"provider={provider}; repo={repo}")
        raise


def run(args):
    cfg = load_config()
    required = ["server", "token", "provider"]
    if any(not cfg.get(k) for k in required):
        raise RuntimeError(f"Bridge is not registered. Run the register command first. Config: {CONFIG_PATH}")
    repo = Path(args.repo or cfg.get("repo") or ".").expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise RuntimeError(f"Repository path not found: {repo}")
    if args.once:
        run_once(cfg, repo, args.command)
        return
    print(f"Watching Team Project OS every {args.poll}s. Ctrl+C to stop.")
    while True:
        try:
            ran = run_once(cfg, repo, args.command)
            time.sleep(1 if ran else args.poll)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Bridge error: {e}", file=sys.stderr)
            time.sleep(args.poll)


def doctor(_args):
    cfg = load_config()
    print(f"Config: {CONFIG_PATH} {'OK' if cfg else 'NOT REGISTERED'}")
    for name, cmd in [("Codex", ["codex", "--version"]), ("Claude Code", ["claude", "--version"]), ("OpenCode", ["opencode", "--version"]), ("Antigravity CLI", ["agy", "--version"])]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            text = (p.stdout or p.stderr).strip().splitlines()
            print(f"{name}: {'OK' if p.returncode == 0 else 'ERROR'} {text[0] if text else ''}")
        except Exception:
            print(f"{name}: not detected")


def main():
    parser = argparse.ArgumentParser(description="Team Project OS Local AI Bridge")
    sub = parser.add_subparsers(dest="sub", required=True)
    r = sub.add_parser("register", help="Pair this machine/provider with a team project")
    r.add_argument("--server", required=True)
    r.add_argument("--project", required=True, type=int)
    r.add_argument("--member", required=True)
    r.add_argument("--provider", required=True, choices=["codex", "claude", "opencode", "antigravity", "dry-run"])
    r.add_argument("--repo", default="")
    r.add_argument("--access-key", default="")
    r.add_argument("--command", default="", help="Optional custom CLI template; {prompt} may be used")
    r.set_defaults(func=register)
    runp = sub.add_parser("run", help="Fetch and execute queued tasks")
    runp.add_argument("--repo", default="")
    runp.add_argument("--once", action="store_true")
    runp.add_argument("--poll", type=int, default=10)
    runp.add_argument("--command", default="")
    runp.set_defaults(func=run)
    d = sub.add_parser("doctor", help="Detect installed AI CLIs")
    d.set_defaults(func=doctor)
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
