from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from app.conversation import normalize_ai_result
from local_bridge.providers import build_invocation, run_provider


LONG_PROMPT = """You are the Project Interviewer.
사용자 요청: HMI MES 프로그램을 제작해 보고 싶어.
This prompt has many words, spaces, symbols: A -> B -> C, and multiple lines.
Return exactly one JSON object.
"""


FAKE_AI = r"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

provider = sys.argv[1]
args = sys.argv[2:]

if provider in {"codex", "claude"}:
    prompt = sys.stdin.read()
else:
    joined = " ".join(args)
    m = re.search(r"(\.team_project_os_tmp[/\\]prompt-[A-Za-z0-9]+\.txt)", joined)
    if not m:
        print("prompt file not found in argv: " + joined, file=sys.stderr)
        raise SystemExit(23)
    prompt = Path(m.group(1)).read_text(encoding="utf-8")

if "HMI MES" not in prompt or "multiple lines" not in prompt:
    print("prompt was corrupted", file=sys.stderr)
    raise SystemExit(24)

print(json.dumps({
    "reply": f"SIM_OK:{provider}",
    "project_updates": {
        "name": "HMI MES 실습 프로젝트",
        "goal": "HMI와 MES의 기본 흐름을 구현하고 검증한다",
        "project_type": "manufacturing_automation"
    },
    "requirements": [],
    "decisions": [],
    "document_updates": [],
    "design_updates": [],
    "pending": []
}, ensure_ascii=False))
"""


def make_fake_cli(bin_dir: Path, provider: str, executable: str, script: Path) -> None:
    if os.name == "nt":
        wrapper = bin_dir / f"{executable}.cmd"
        wrapper.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" {provider} %*\r\n',
            encoding="utf-8",
        )
    else:
        wrapper = bin_dir / executable
        wrapper.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" {provider} "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)


class ProviderAdapterTests(unittest.TestCase):
    def test_long_prompt_is_not_embedded_in_default_argv(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            for provider in ("codex", "claude", "opencode", "antigravity"):
                inv = build_invocation(provider, LONG_PROMPT, cwd=cwd, purpose="interview")
                joined = " ".join(inv.command)
                self.assertNotIn("HMI MES", joined, provider)
                self.assertNotIn("multiple lines", joined, provider)
                if inv.prompt_file:
                    inv.prompt_file.unlink(missing_ok=True)

    def test_all_provider_adapters_preserve_long_unicode_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            bin_dir = base / "bin"
            cwd = base / "workspace"
            bin_dir.mkdir()
            cwd.mkdir()
            fake_script = base / "fake_ai.py"
            fake_script.write_text(FAKE_AI, encoding="utf-8")

            make_fake_cli(bin_dir, "codex", "codex", fake_script)
            make_fake_cli(bin_dir, "claude", "claude", fake_script)
            make_fake_cli(bin_dir, "opencode", "opencode", fake_script)
            make_fake_cli(bin_dir, "antigravity", "agy", fake_script)

            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = str(bin_dir) + os.pathsep + old_path
            try:
                for provider in ("codex", "claude", "opencode", "antigravity"):
                    result = run_provider(provider, LONG_PROMPT, cwd=cwd, purpose="interview", timeout_seconds=30)
                    self.assertTrue(result.ok, f"{provider}: {result.stderr}")
                    parsed = normalize_ai_result(result.stdout)
                    self.assertEqual(parsed["reply"], f"SIM_OK:{provider}")
                    self.assertEqual(parsed["project_updates"]["name"], "HMI MES 실습 프로젝트")
                    self.assertFalse((cwd / ".team_project_os_tmp").exists(), provider)
            finally:
                os.environ["PATH"] = old_path

    def test_codex_uses_explicit_stdin_sentinel(self):
        with tempfile.TemporaryDirectory() as td:
            inv = build_invocation("codex", LONG_PROMPT, cwd=Path(td), purpose="interview")
            self.assertEqual(inv.command[-1], "-")
            self.assertEqual(inv.stdin_text, LONG_PROMPT)
            self.assertIn("--skip-git-repo-check", inv.command)

    def test_antigravity_does_not_auto_approve_all_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            inv = build_invocation("antigravity", LONG_PROMPT, cwd=Path(td), purpose="interview")
            self.assertNotIn("--dangerously-skip-permissions", inv.command)
            inv.prompt_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
