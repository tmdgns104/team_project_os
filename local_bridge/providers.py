from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_PROVIDERS = ("codex", "claude", "opencode", "antigravity", "dry-run")


@dataclass
class ProviderInvocation:
    provider: str
    command: list[str]
    stdin_text: str | None = None
    prompt_file: Path | None = None


@dataclass
class ProviderResult:
    provider: str
    returncode: int
    stdout: str
    stderr: str
    command_display: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _utf8_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    # Python-based wrappers/custom CLIs otherwise inherit legacy Windows code pages
    # when stdout/stderr are redirected. These variables are harmless for Node/Rust CLIs.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _resolve_executable(executable: str) -> str:
    direct = Path(executable)
    if direct.is_file():
        return str(direct)
    resolved = shutil.which(executable)
    if not resolved:
        raise RuntimeError(
            f"Local CLI not found: {executable}. "
            f"Run 'python project_os.py doctor' and 'where {executable}' on Windows."
        )
    return resolved


def prepare_local_command(cmd: list[str]) -> list[str]:
    """Resolve executable and safely invoke npm .cmd/.bat shims on Windows."""
    if not cmd:
        raise RuntimeError("Empty local command")
    resolved = _resolve_executable(cmd[0])
    resolved_cmd = [resolved, *cmd[1:]]
    if platform.system() == "Windows" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        comspec = os.environ.get("COMSPEC") or shutil.which("cmd.exe") or "cmd.exe"
        # The model prompt is never embedded here. Only short, controlled arguments
        # are quoted into the cmd.exe command string.
        return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(resolved_cmd)]
    return resolved_cmd


def _prompt_file(cwd: Path, prompt: str) -> Path:
    tmp_dir = cwd / ".team_project_os_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / f"prompt-{uuid.uuid4().hex}.txt"
    path.write_text(prompt, encoding="utf-8")
    return path


def build_invocation(
    provider: str,
    prompt: str,
    *,
    cwd: Path,
    purpose: str = "interview",
    custom_command: str | None = None,
) -> ProviderInvocation:
    if provider not in SUPPORTED_PROVIDERS:
        raise RuntimeError(f"Unsupported provider: {provider}")

    if custom_command:
        # Safe custom mode: prefer {prompt_file}. {prompt} remains supported for
        # backwards compatibility but can hit Windows command-line limits.
        prompt_path = _prompt_file(cwd, prompt)
        parts = shlex.split(custom_command, posix=platform.system() != "Windows")
        out: list[str] = []
        used_file = False
        used_prompt = False
        for part in parts:
            if "{prompt_file}" in part:
                part = part.replace("{prompt_file}", str(prompt_path))
                used_file = True
            if "{prompt}" in part:
                part = part.replace("{prompt}", prompt)
                used_prompt = True
            out.append(part)
        if not used_file and not used_prompt:
            out.append(str(prompt_path))
            used_file = True
        return ProviderInvocation(provider=provider, command=out, prompt_file=prompt_path if used_file else None)

    if provider == "codex":
        # Codex explicitly supports "-" as "read the prompt from stdin".
        cmd = ["codex", "exec"]
        if purpose == "interview":
            cmd.append("--skip-git-repo-check")
        cmd.append("-")
        return ProviderInvocation(provider=provider, command=cmd, stdin_text=prompt)

    if provider == "claude":
        # Claude Code print mode consumes piped stdin. Keep argv intentionally short.
        instruction = (
            "Use the complete UTF-8 project request provided on stdin as the primary "
            "request. Follow it exactly and return only the requested response."
        )
        cmd = ["claude", "-p", instruction, "--output-format", "text"]
        return ProviderInvocation(provider=provider, command=cmd, stdin_text=prompt)

    if provider == "opencode":
        # OpenCode documents `opencode run [message..]`, but not a portable stdin
        # prompt contract. Put the full prompt in a UTF-8 workspace file and pass
        # only a short instruction on argv.
        prompt_path = _prompt_file(cwd, prompt)
        rel = prompt_path.relative_to(cwd)
        instruction = (
            f"Read the complete UTF-8 request from {rel.as_posix()} and follow it exactly. "
            "Return only the response requested by that file."
        )
        return ProviderInvocation(
            provider=provider,
            command=["opencode", "run", instruction],
            prompt_file=prompt_path,
        )

    if provider == "antigravity":
        # Antigravity headless mode is `agy -p`. Workspace file reads are allowed
        # by its normal permission model, avoiding long Windows argv values.
        prompt_path = _prompt_file(cwd, prompt)
        rel = prompt_path.relative_to(cwd)
        instruction = (
            f"Read the complete UTF-8 request from {rel.as_posix()} and follow it exactly. "
            "Return only the response requested by that file."
        )
        return ProviderInvocation(
            provider=provider,
            command=[
                "agy",
                "-p",
                instruction,
                "--output-format",
                "text",
                "--print-timeout",
                "45m",
            ],
            prompt_file=prompt_path,
        )

    return ProviderInvocation(
        provider=provider,
        command=[sys.executable, "-c", "print('{\"reply\":\"DRY RUN\",\"project_updates\":{},\"requirements\":[],\"decisions\":[],\"document_updates\":[],\"design_updates\":[],\"pending\":[]}')"],
    )


def _display_command(cmd: list[str]) -> str:
    # Do not expose prompt contents. Provider argv contains only controlled text.
    return subprocess.list2cmdline(cmd) if platform.system() == "Windows" else shlex.join(cmd)


def run_provider(
    provider: str,
    prompt: str,
    *,
    cwd: Path,
    purpose: str = "interview",
    custom_command: str | None = None,
    timeout_seconds: int = 60 * 45,
) -> ProviderResult:
    cwd = cwd.expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise RuntimeError(f"Working directory not found: {cwd}")

    invocation = build_invocation(
        provider,
        prompt,
        cwd=cwd,
        purpose=purpose,
        custom_command=custom_command,
    )
    launch_cmd = prepare_local_command(invocation.command)

    try:
        completed = subprocess.run(
            launch_cmd,
            cwd=cwd,
            input=invocation.stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_utf8_subprocess_env(),
            timeout=timeout_seconds,
        )
        return ProviderResult(
            provider=provider,
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            command_display=_display_command(invocation.command),
        )
    finally:
        if invocation.prompt_file:
            try:
                invocation.prompt_file.unlink(missing_ok=True)
                parent = invocation.prompt_file.parent
                if parent.name == ".team_project_os_tmp" and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass


def doctor() -> list[dict[str, str | bool]]:
    checks = [
        ("codex", "Codex", ["codex", "--version"]),
        ("claude", "Claude Code", ["claude", "--version"]),
        ("opencode", "OpenCode", ["opencode", "--version"]),
        ("antigravity", "Antigravity CLI", ["agy", "--version"]),
    ]
    rows = []
    for provider, label, cmd in checks:
        try:
            resolved = _resolve_executable(cmd[0])
            launch = prepare_local_command(cmd)
            p = subprocess.run(
                launch,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_utf8_subprocess_env(),
                timeout=10,
            )
            first = ((p.stdout or p.stderr).strip().splitlines() or [""])[0]
            rows.append({
                "provider": provider,
                "label": label,
                "ok": p.returncode == 0,
                "version": first,
                "path": resolved,
            })
        except Exception as exc:
            rows.append({
                "provider": provider,
                "label": label,
                "ok": False,
                "version": "",
                "path": "",
                "error": str(exc),
            })
    return rows


def print_doctor() -> None:
    for row in doctor():
        if row["ok"]:
            print(f"{row['label']}: OK {row['version']} [{row['path']}]")
        else:
            print(f"{row['label']}: not detected ({row.get('error', 'unknown error')})")
