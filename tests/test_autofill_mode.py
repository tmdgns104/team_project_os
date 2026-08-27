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
    _requests_autofill,
    apply_to_server,
    blank_brief,
    build_design_chat_prompt,
    build_distiller_prompt,
    interactive_design,
    preview_lines,
)
from local_bridge.providers import ProviderResult


AUTOFILL_DISTILLED = json.dumps({
    "reply": "모르는 세부사항은 V1에 적합한 기본값으로 임시 결정했습니다.",
    "project_updates": {
        "name": "HMI MES Autofill 미니라인",
        "goal": "Mitsubishi PLC 기반 미니 생산라인의 상태와 생산실적을 HMI/MES 형태로 구현한다",
        "project_type": "manufacturing_automation",
        "problem": "구체적인 구현 방안을 모르는 상태에서도 실행 가능한 HMI/MES 실습 프로젝트를 시작하고 싶다",
        "users": "개발 학습자와 작업자 역할 사용자",
        "deliverables": "PLC 시뮬레이터 연동, HMI 화면, MES 생산실적 저장, 기본 KPI 조회",
        "success_criteria": "시뮬레이터 데이터가 수집·저장되고 HMI에서 상태와 생산실적을 조회할 수 있음",
        "scope": "단일 미니 컨베이어 V1, 시뮬레이터 우선, 로컬 실행",
        "constraints": "실제 장비 구매나 운영 배포는 V1 범위 밖",
        "description": "세부 기술은 AI 임시 결정으로 시작하고 이후 실제 환경에 맞게 교체한다"
    },
    "requirements": [
        {"ref":"REQ-001","title":"PLC 데이터 수집","detail":"PLC 시뮬레이터의 운전 상태와 생산 카운트를 수집한다","status":"defined"},
        {"ref":"REQ-002","title":"HMI 표시","detail":"설비 상태, 생산수량, 불량수량을 표시한다","status":"defined"},
        {"ref":"REQ-003","title":"MES 실적 저장","detail":"생산실적을 시간 정보와 함께 저장하고 조회한다","status":"defined"}
    ],
    "decisions": [
        {"title":"Mitsubishi PLC 시뮬레이터 우선","body":"사용자가 Mitsubishi PLC와 시뮬레이터 우선을 직접 지정함","status":"accepted"},
        {"title":"V1 DB는 SQLite","body":"AI 임시 결정. 로컬 단일 사용자 V1에서 설치 부담이 낮아 선택. 다중 사용자 운영 전 PostgreSQL 등으로 재검토","status":"provisional"},
        {"title":"Backend는 FastAPI","body":"AI 임시 결정. Python 기반 통신 계층과 결합하기 쉽고 API 분리가 간단해 선택. 팀 표준이 생기면 재검토","status":"provisional"},
        {"title":"HMI는 Web UI","body":"AI 임시 결정. 브라우저로 확인하기 쉽고 로컬 데모에 적합해 선택. 전용 패널 요구가 생기면 재검토","status":"provisional"},
        {"title":"초기 배포는 Windows Local","body":"AI 임시 결정. 개발 환경에서 가장 빠르게 검증하기 위한 선택. 운영 환경 확정 시 재검토","status":"provisional"}
    ],
    "document_updates": [
        {"doc_type":"proposal","content":"# 기획서\n\nHMI/MES Autofill 미니라인 V1을 구현한다. AI가 선택한 세부 기술은 임시 결정으로 관리한다.\n","reason":"아이디어와 Autofill 위임을 반영"},
        {"doc_type":"system_architecture","content":"# 시스템 구조\n\nPLC Simulator → Python/FastAPI Gateway → SQLite → Web HMI/MES\n\nSQLite/FastAPI/Web UI는 AI 임시 결정이다.\n","reason":"실행 가능한 V1 기본 아키텍처"}
    ],
    "design_updates": [
        {"view":"process","mode":"replace","reason":"V1 기본 공정","nodes":[
            {"key":"sense","label":"PLC 상태 발생","kind":"step","detail":"Simulator"},
            {"key":"collect","label":"데이터 수집","kind":"step","detail":"Python Gateway"},
            {"key":"save","label":"생산실적 저장","kind":"step","detail":"SQLite 임시 결정"},
            {"key":"view","label":"HMI/MES 조회","kind":"step","detail":"Web UI 임시 결정"}],
         "edges":[
            {"source":"sense","target":"collect","label":"status/count"},
            {"source":"collect","target":"save","label":"production record"},
            {"source":"save","target":"view","label":"query"}]},
        {"view":"architecture","mode":"replace","reason":"Autofill V1 아키텍처","nodes":[
            {"key":"plc","label":"Mitsubishi PLC Simulator","kind":"device","detail":"사용자 확정"},
            {"key":"api","label":"Python + FastAPI Gateway","kind":"service","detail":"AI 임시 결정"},
            {"key":"db","label":"SQLite","kind":"store","detail":"AI 임시 결정"},
            {"key":"ui","label":"Web HMI/MES","kind":"component","detail":"AI 임시 결정"}],
         "edges":[
            {"source":"plc","target":"api","label":"PLC Data"},
            {"source":"api","target":"db","label":"Record"},
            {"source":"db","target":"ui","label":"Query"}]},
        {"view":"dataflow","mode":"replace","reason":"기본 데이터 흐름","nodes":[
            {"key":"plc","label":"PLC","kind":"device"},
            {"key":"gateway","label":"Gateway","kind":"service"},
            {"key":"store","label":"SQLite","kind":"store"},
            {"key":"screen","label":"HMI/MES","kind":"component"}],
         "edges":[
            {"source":"plc","target":"gateway","label":"run/count/defect"},
            {"source":"gateway","target":"store","label":"normalized record"},
            {"source":"store","target":"screen","label":"KPI/query"}]}
    ],
    "pending": ["실제 PLC 통신 방식은 장비 연결 전에 확인", "실제 생산 배포 권한/보안 정책은 운영 전 사람 승인 필요"]
}, ensure_ascii=False)


class Args:
    provider = "codex"
    server = "http://localhost:8000"
    member = "승훈"
    access_key = ""
    cwd = "."
    command = ""
    initial = "HMI MES를 만들어보고 싶어. 세부적인 건 잘 모르겠으니까 적당한 걸로 알아서 임시로 다 정해줘"
    session_file = ""
    autofill = False


class AutofillModeTests(unittest.TestCase):
    def test_natural_language_enables_autofill(self):
        self.assertTrue(_requests_autofill("세부적인 건 잘 모르겠으니까 알아서 임시로 다 정해줘"))
        self.assertTrue(_requests_autofill("DB 같은 건 네가 정해"))
        self.assertFalse(_requests_autofill("DB 후보를 비교해서 설명해줘"))

    def test_prompts_make_provisional_boundary_explicit(self):
        messages = [{"role":"user","content":"HMI MES 만들고 싶은데 세부사항은 알아서 해줘"}]
        chat = build_design_chat_prompt(messages, autofill_mode=True)
        distill = build_distiller_prompt(messages, autofill_mode=True)
        self.assertIn("AUTOFILL MODE IS ON", chat)
        self.assertIn("AI 임시 결정", chat)
        self.assertIn("status='provisional'", distill)
        self.assertIn("real spending/purchases", distill)
        self.assertIn("safety-critical", distill)

    def test_preview_separates_human_and_ai_decisions(self):
        parsed = normalize_ai_result(AUTOFILL_DISTILLED)
        brief = merge_project_brief(blank_brief(), parsed["project_updates"])
        text = "\n".join(preview_lines(brief, parsed))
        self.assertIn("사람 확정 Decision: 1개", text)
        self.assertIn("AI 임시 Decision: 4개", text)
        self.assertIn("SQLite", text)

    def test_interactive_phrase_turns_autofill_on_before_chat_and_apply(self):
        chat = ProviderResult("codex", 0, "좋습니다. 모르는 세부 기술은 AI 임시 결정으로 채우고, 실제 비용/보안 같은 것은 확인받겠습니다.", "", "codex exec -")
        distilled = ProviderResult("codex", 0, AUTOFILL_DISTILLED, "", "codex exec -")
        with tempfile.TemporaryDirectory() as td:
            args = Args()
            args.session_file = str(Path(td) / "autofill-session.json")
            with patch("local_bridge.project_cli.run_provider", side_effect=[chat, distilled]) as run_mock, \
                 patch("builtins.input", side_effect=["/apply"]), \
                 patch("local_bridge.project_cli.apply_to_server", return_value={"id": 91, "name": "HMI MES Autofill 미니라인"}) as apply_mock:
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = interactive_design(args)
            self.assertEqual(rc, 0)
            self.assertIn("Autofill Mode ON", out.getvalue())
            self.assertIn("AUTOFILL MODE IS ON", run_mock.call_args_list[0].args[1])
            self.assertIn("status='provisional'", run_mock.call_args_list[1].args[1])
            parsed = apply_mock.call_args.args[4]
            self.assertEqual(len([d for d in parsed["decisions"] if d["status"] == "provisional"]), 4)
            saved = json.loads(Path(args.session_file).read_text(encoding="utf-8"))
            self.assertTrue(saved["autofill_mode"])

    def test_autofill_project_materializes_with_provisional_decisions(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "autofill.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()

            parsed = normalize_ai_result(AUTOFILL_DISTILLED)
            brief = merge_project_brief(blank_brief(), parsed["project_updates"])

            with TestClient(main.app) as client:
                def client_http(method: str, url: str, payload=None, access_key: str = ""):
                    split = urlsplit(url)
                    target = split.path + (f"?{split.query}" if split.query else "")
                    response = client.request(method, target, json=payload)
                    if response.status_code >= 400:
                        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
                    return response.json() if response.content else None

                with patch("local_bridge.project_cli.http_json", side_effect=client_http):
                    project = apply_to_server("http://testserver", "", "승훈", brief, parsed)

                snap = client.get(f"/api/projects/{project['id']}/snapshot").json()
                self.assertEqual(snap["project"]["name"], "HMI MES Autofill 미니라인")
                self.assertEqual(len(snap["documents"]), 13)
                self.assertEqual(len(snap["requirements"]), 3)
                provisional = [d for d in snap["decisions"] if d["status"] == "provisional"]
                self.assertEqual(len(provisional), 4)
                self.assertTrue(any("SQLite" in d["title"] for d in provisional))
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "process"]), 4)
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "architecture"]), 4)
                self.assertEqual(len([n for n in snap["nodes"] if n["view"] == "dataflow"]), 4)


if __name__ == "__main__":
    unittest.main()
