from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app.conversation import merge_project_brief, normalize_ai_result
from local_bridge.project_cli import (
    apply_to_server,
    blank_brief,
    build_design_chat_prompt,
    build_distiller_prompt,
    interactive_design,
)
from local_bridge.providers import ProviderResult


DISTILLED = json.dumps({
    "reply": "HMI/MES 미니 생산라인 V1로 정리했습니다.",
    "project_updates": {
        "name": "HMI MES 미니 생산라인",
        "goal": "Mitsubishi PLC 기반 생산라인의 상태와 생산 정보를 HMI에서 확인하고 MES 형태로 저장·조회하는 V1을 구현한다",
        "project_type": "manufacturing_automation",
        "problem": "HMI와 MES의 연결 구조를 직접 구현하며 익힐 실습 프로젝트가 필요하다",
        "users": "개발 학습자, 생산라인 작업자 역할 사용자",
        "deliverables": "PLC 시뮬레이션 연동, HMI 화면, 생산실적 저장, 기본 KPI 조회",
        "scope": "단일 미니 컨베이어 라인, 시뮬레이터 우선, 생산수량/불량수량/설비상태 저장",
        "constraints": "V1은 실제 PLC 없이 시뮬레이터로 시작",
        "description": "실제 PLC 연결로 확장 가능한 학습용 HMI/MES 프로젝트"
    },
    "requirements": [
        {"ref":"REQ-001","title":"PLC 상태 수집","detail":"PLC 시뮬레이터에서 운전/정지와 생산 카운트를 수집한다","status":"defined"},
        {"ref":"REQ-002","title":"HMI 상태 표시","detail":"현재 설비 상태와 생산수량을 화면에 표시한다","status":"defined"},
        {"ref":"REQ-003","title":"MES 생산실적 저장","detail":"생산수량과 불량수량을 시간 정보와 함께 저장한다","status":"defined"}
    ],
    "decisions": [
        {"title":"V1은 PLC 시뮬레이터 우선","body":"실제 Mitsubishi PLC 연결 전에 시뮬레이션으로 전체 흐름을 검증한다","status":"accepted"}
    ],
    "document_updates": [
        {"doc_type":"proposal","content":"# 기획서\n\nHMI/MES 미니 생산라인 V1을 구현한다.\n","reason":"대화에서 목표와 범위가 확인됨"},
        {"doc_type":"system_architecture","content":"# 시스템 구조도\n\nPLC Simulator → Python Gateway → DB → HMI/MES UI\n","reason":"구성요소가 합의됨"}
    ],
    "design_updates": [
        {
            "view":"process","mode":"replace","reason":"합의된 V1 공정",
            "nodes":[
                {"key":"run","label":"라인 운전","kind":"step","detail":"PLC 운전"},
                {"key":"collect","label":"생산 데이터 수집","kind":"step","detail":"상태/카운트"},
                {"key":"save","label":"생산실적 저장","kind":"step","detail":"DB 기록"},
                {"key":"display","label":"HMI/MES 표시","kind":"step","detail":"조회/표시"}
            ],
            "edges":[
                {"source":"run","target":"collect","label":"PLC 상태"},
                {"source":"collect","target":"save","label":"생산 데이터"},
                {"source":"save","target":"display","label":"조회 데이터"}
            ]
        },
        {
            "view":"architecture","mode":"replace","reason":"합의된 V1 구성",
            "nodes":[
                {"key":"plc","label":"Mitsubishi PLC Simulator","kind":"device","detail":"V1 입력"},
                {"key":"gateway","label":"Python Gateway","kind":"service","detail":"수집/변환"},
                {"key":"db","label":"Production DB","kind":"store","detail":"실적 저장"},
                {"key":"ui","label":"HMI / MES UI","kind":"component","detail":"상태와 실적 표시"}
            ],
            "edges":[
                {"source":"plc","target":"gateway","label":"PLC Data"},
                {"source":"gateway","target":"db","label":"Production Record"},
                {"source":"db","target":"ui","label":"Query Result"}
            ]
        },
        {
            "view":"dataflow","mode":"replace","reason":"대화에서 확인된 데이터 이동",
            "nodes":[
                {"key":"plc","label":"PLC","kind":"device","detail":"상태/카운트"},
                {"key":"gateway","label":"Gateway","kind":"service","detail":"정규화"},
                {"key":"db","label":"DB","kind":"store","detail":"생산실적"},
                {"key":"ui","label":"UI","kind":"component","detail":"표시"}
            ],
            "edges":[
                {"source":"plc","target":"gateway","label":"run/status/count"},
                {"source":"gateway","target":"db","label":"production record"},
                {"source":"db","target":"ui","label":"KPI/query"}
            ]
        }
    ],
    "pending": ["실제 PLC 연결 프로토콜은 V1 이후 확정", "운영용 DB 제품은 미정"]
}, ensure_ascii=False)


class Args:
    provider = "codex"
    server = "http://localhost:8000"
    member = "승훈"
    access_key = ""
    cwd = "."
    command = ""
    initial = "HMI MES 프로그램을 만들어보고 싶어"
    session_file = ""
    no_live = True


class DesignSessionTests(unittest.TestCase):
    def test_chat_phase_is_freeform_and_distillation_happens_only_on_apply(self):
        chat1 = ProviderResult("codex", 0, "좋아요. 먼저 어떤 생산라인을 가정할지 정해보죠. 실제 PLC보다 시뮬레이터부터 시작할까요?", "", "codex exec -")
        chat2 = ProviderResult("codex", 0, "좋습니다. Mitsubishi PLC 시뮬레이터와 작은 컨베이어 라인을 V1로 두고 HMI 표시와 생산실적 저장 범위를 잡아보죠.", "", "codex exec -")
        distilled = ProviderResult("codex", 0, DISTILLED, "", "codex exec -")

        with tempfile.TemporaryDirectory() as td:
            args = Args()
            args.session_file = str(Path(td) / "session.json")
            with patch("local_bridge.project_cli.run_provider", side_effect=[chat1, chat2, distilled]) as run_mock, \
                 patch("builtins.input", side_effect=["Mitsubishi PLC 시뮬레이터랑 작은 컨베이어로 하자", "/apply"]), \
                 patch("local_bridge.project_cli.apply_to_server", return_value={"id": 88, "name": "HMI MES 미니 생산라인"}) as apply_mock:
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = interactive_design(args)

            self.assertEqual(rc, 0)
            self.assertEqual(run_mock.call_count, 3)
            first_prompt = run_mock.call_args_list[0].args[1]
            second_prompt = run_mock.call_args_list[1].args[1]
            final_prompt = run_mock.call_args_list[2].args[1]
            self.assertIn("DO NOT output JSON", first_prompt)
            self.assertIn("Mitsubishi PLC", second_prompt)
            self.assertIn("Project Distiller", final_prompt)
            self.assertTrue(apply_mock.called)
            brief = apply_mock.call_args.args[3]
            self.assertEqual(brief["name"], "HMI MES 미니 생산라인")
            self.assertIn("프로젝트 생성 완료", out.getvalue())
            saved = json.loads(Path(args.session_file).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["messages"]), 4)
            self.assertEqual(saved["applied_project"]["id"], 88)

    def test_preview_does_not_create_project(self):
        chat = ProviderResult("codex", 0, "범위를 더 정해보죠.", "", "codex exec -")
        distilled = ProviderResult("codex", 0, DISTILLED, "", "codex exec -")
        with tempfile.TemporaryDirectory() as td:
            args = Args()
            args.session_file = str(Path(td) / "session.json")
            with patch("local_bridge.project_cli.run_provider", side_effect=[chat, distilled]), \
                 patch("builtins.input", side_effect=["/preview", "/quit"]), \
                 patch("local_bridge.project_cli.apply_to_server") as apply_mock:
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = interactive_design(args)
            self.assertEqual(rc, 0)
            apply_mock.assert_not_called()
            self.assertIn("아직 프로젝트는 생성되지 않았습니다", out.getvalue())

    def test_chat_and_distiller_prompts_have_separate_roles(self):
        messages = [
            {"role":"user","content":"HMI MES를 만들고 싶어"},
            {"role":"assistant","content":"어떤 설비를 가정할까요?"},
            {"role":"user","content":"Mitsubishi PLC 시뮬레이터부터"},
        ]
        chat = build_design_chat_prompt(messages)
        distill = build_distiller_prompt(messages)
        self.assertIn("free-form design discussion", chat)
        self.assertIn("DO NOT output JSON", chat)
        self.assertIn("Return exactly ONE JSON object", distill)
        self.assertIn("ASSISTANT suggestions are NOT confirmed facts", distill)


class DesignSessionMaterializationTests(unittest.TestCase):
    def test_distilled_hmi_mes_project_materializes_in_real_app(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "design-session.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()

            parsed = normalize_ai_result(DISTILLED)
            brief = merge_project_brief(blank_brief(), parsed["project_updates"])

            with TestClient(main.app) as client:
                def client_http(method: str, url: str, payload=None, access_key: str = ""):
                    split = urlsplit(url)
                    target = split.path + (f"?{split.query}" if split.query else "")
                    headers = {"X-Access-Key": access_key} if access_key else {}
                    response = client.request(method, target, json=payload, headers=headers)
                    if response.status_code >= 400:
                        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
                    return response.json() if response.content else None

                with patch("local_bridge.project_cli.http_json", side_effect=client_http):
                    project = apply_to_server("http://testserver", "", "승훈", brief, parsed)

                snap = client.get(f"/api/projects/{project['id']}/snapshot").json()
                self.assertEqual(snap["project"]["name"], "HMI MES 미니 생산라인")
                self.assertEqual(len(snap["documents"]), 13)
                self.assertEqual(len(snap["requirements"]), 3)
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "process"]), 4)
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "architecture"]), 4)
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "dataflow"]), 4)
                self.assertTrue(any(e["label"] == "PLC Data" for e in snap["edges"]))
                proposal = next(d for d in snap["documents"] if d["doc_type"] == "proposal")
                self.assertIn("HMI/MES 미니 생산라인", proposal["content"])


if __name__ == "__main__":
    unittest.main()
