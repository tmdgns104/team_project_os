from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from local_bridge.project_cli import interactive_create
from local_bridge.providers import ProviderResult


class Args:
    provider = "codex"
    server = "http://localhost:8000"
    member = "승훈"
    access_key = ""
    cwd = "."
    command = ""
    initial = "HMI MES 프로그램을 제작해 보고 싶어"


AI_OUTPUT = json.dumps({
    "reply": "좋아요. HMI와 MES가 다룰 설비와 데이터 범위를 먼저 정해볼게요.",
    "project_updates": {
        "name": "HMI MES 프로그램 실습",
        "goal": "설비 상태를 HMI로 표시하고 생산 정보를 MES 흐름으로 관리한다",
        "project_type": "manufacturing_automation",
        "problem": "HMI와 MES 연동 구조를 직접 구현하며 익히고 싶다"
    },
    "requirements": [],
    "decisions": [],
    "document_updates": [],
    "design_updates": [],
    "pending": ["대상 설비", "PLC 종류", "수집 데이터"]
}, ensure_ascii=False)


class CmdProjectCreateTests(unittest.TestCase):
    def test_cmd_interview_can_apply_project(self):
        fake_result = ProviderResult(
            provider="codex",
            returncode=0,
            stdout=AI_OUTPUT,
            stderr="diagnostic text that must not corrupt JSON",
            command_display="codex exec --skip-git-repo-check -",
        )
        with patch("local_bridge.project_cli.run_provider", return_value=fake_result), \
             patch("builtins.input", side_effect=["/apply"]), \
             patch("local_bridge.project_cli.apply_to_server", return_value={"id": 77, "name": "HMI MES 프로그램 실습"}) as apply_mock:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = interactive_create(Args())
        self.assertEqual(rc, 0)
        self.assertTrue(apply_mock.called)
        brief = apply_mock.call_args.args[3]
        self.assertEqual(brief["name"], "HMI MES 프로그램 실습")
        self.assertIn("설비 상태", brief["goal"])
        self.assertIn("프로젝트 생성 완료", out.getvalue())


if __name__ == "__main__":
    unittest.main()
