from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.conversation import merge_project_brief, normalize_ai_result
from local_bridge.project_cli import apply_to_server, blank_brief, build_distiller_prompt

TRANSCRIPT = [
    {"role": "user", "content": "HMI MES 프로그램을 만들어보고 싶어"},
    {"role": "assistant", "content": "PLC와 생산라인 규모부터 잡아보면 좋습니다."},
    {"role": "user", "content": "Mitsubishi PLC로 작은 컨베이어를 생각하고 있어. 세부적인 건 잘 모르겠으니까 적당한 걸로 알아서 임시로 다 정해줘"},
    {"role": "assistant", "content": "좋습니다. 저위험 세부사항은 AI 임시 결정으로 채우고, 실제 비용·보안·운영 권한처럼 큰 결정은 사람 확인 대상으로 남기겠습니다."},
]

DISTILLED = {
    "reply": "실행 가능한 HMI/MES V1로 구성하고 AI 선택 사항은 임시 결정으로 표시했습니다.",
    "project_updates": {
        "name": "HMI MES Autofill 미니라인",
        "goal": "Mitsubishi PLC 기반 미니 생산라인 데이터를 수집해 HMI로 표시하고 MES 생산실적으로 저장·조회하는 V1을 구현한다",
        "project_type": "manufacturing_automation",
        "problem": "세부 구현 방안이 정해지지 않은 상태에서도 실행 가능한 프로젝트 초안을 만들 필요가 있다",
        "users": "개발 학습자와 작업자 역할 사용자",
        "deliverables": "PLC 시뮬레이터 연동, Web HMI, 생산실적 저장, KPI 조회",
        "success_criteria": "시뮬레이터의 상태/생산 데이터가 수집·저장되고 HMI에서 조회된다",
        "scope": "단일 미니 컨베이어 V1, 시뮬레이터 우선, Windows 로컬 실행",
        "constraints": "실제 장비 구매와 운영 배포는 별도 승인 후 진행",
        "description": "FastAPI, SQLite, Web UI는 AI 임시 결정이며 실제 환경 확정 시 교체 가능"
    },
    "requirements": [
        {"ref":"REQ-001","title":"PLC 데이터 수집","detail":"운전 상태, 생산수량, 불량수량을 수집한다","status":"defined"},
        {"ref":"REQ-002","title":"HMI 표시","detail":"현재 설비 상태와 생산지표를 표시한다","status":"defined"},
        {"ref":"REQ-003","title":"MES 저장/조회","detail":"시간별 생산실적을 저장하고 조회한다","status":"defined"}
    ],
    "decisions": [
        {"title":"Mitsubishi PLC 사용","body":"사용자가 직접 지정한 PLC 계열","status":"accepted"},
        {"title":"V1 DB는 SQLite","body":"AI 임시 결정. 로컬 V1에서 설치 부담이 낮아 선택하며 다중 사용자 운영 전 재검토","status":"provisional"},
        {"title":"Backend는 FastAPI","body":"AI 임시 결정. Python 통신 계층과 연결이 단순하여 선택하며 팀 표준 확정 시 재검토","status":"provisional"},
        {"title":"HMI는 Web UI","body":"AI 임시 결정. 브라우저 기반 데모가 쉬워 선택하며 전용 패널 요구 시 재검토","status":"provisional"},
        {"title":"V1은 Windows Local","body":"AI 임시 결정. 개발 PC에서 가장 빠르게 검증하기 위한 선택이며 운영 배포 전 재검토","status":"provisional"}
    ],
    "document_updates": [
        {"doc_type":"proposal","content":"# 기획서\n\nHMI/MES Autofill 미니라인 V1을 구현한다. AI가 선택한 세부 기술은 임시 결정으로 관리한다.\n","reason":"막연한 아이디어와 위임 요청을 실행 가능한 V1로 변환"},
        {"doc_type":"system_architecture","content":"# 시스템 구조\n\nMitsubishi PLC Simulator → Python/FastAPI Gateway → SQLite → Web HMI/MES\n\nFastAPI/SQLite/Web UI는 PROVISIONAL이다.\n","reason":"Autofill 기반 기본 구조"}
    ],
    "design_updates": [
        {"view":"process","mode":"replace","nodes":[
            {"key":"plc","label":"PLC 상태 발생","kind":"step"},
            {"key":"collect","label":"데이터 수집","kind":"step"},
            {"key":"save","label":"실적 저장","kind":"step"},
            {"key":"display","label":"HMI/MES 표시","kind":"step"}],
         "edges":[
            {"source":"plc","target":"collect","label":"status/count/defect"},
            {"source":"collect","target":"save","label":"record"},
            {"source":"save","target":"display","label":"query"}]},
        {"view":"architecture","mode":"replace","nodes":[
            {"key":"plc","label":"Mitsubishi PLC Simulator","kind":"device","detail":"사용자 확정"},
            {"key":"api","label":"Python + FastAPI Gateway","kind":"service","detail":"AI 임시 결정"},
            {"key":"db","label":"SQLite","kind":"store","detail":"AI 임시 결정"},
            {"key":"ui","label":"Web HMI/MES","kind":"component","detail":"AI 임시 결정"}],
         "edges":[
            {"source":"plc","target":"api","label":"PLC Data"},
            {"source":"api","target":"db","label":"Production Record"},
            {"source":"db","target":"ui","label":"Query"}]},
        {"view":"dataflow","mode":"replace","nodes":[
            {"key":"plc","label":"PLC","kind":"device"},
            {"key":"gateway","label":"Gateway","kind":"service"},
            {"key":"db","label":"SQLite","kind":"store"},
            {"key":"ui","label":"HMI/MES","kind":"component"}],
         "edges":[
            {"source":"plc","target":"gateway","label":"run/count/defect"},
            {"source":"gateway","target":"db","label":"normalized record"},
            {"source":"db","target":"ui","label":"KPI/query"}]}
    ],
    "pending": [
        "실제 PLC 연결 방식은 실제 장비 정보 확인 후 사람 승인",
        "운영 환경의 계정/보안/개인정보 정책은 배포 전 사람 승인"
    ]
}


def main() -> int:
    print("[AUTOFILL SIM] vague project idea")
    for message in TRANSCRIPT:
        print(f"[AUTOFILL SIM] {message['role']}: {message['content']}")

    prompt = build_distiller_prompt(TRANSCRIPT, autofill_mode=True)
    prompt_checks = {
        "autofill_on": "AUTOFILL MODE IS ON" in prompt,
        "provisional_contract": "status='provisional'" in prompt,
        "high_risk_gate": "real spending/purchases" in prompt,
    }
    for name, ok in prompt_checks.items():
        print(f"[AUTOFILL SIM] {name}: {'PASS' if ok else 'FAIL'}")
    if not all(prompt_checks.values()):
        return 1

    parsed = normalize_ai_result(json.dumps(DISTILLED, ensure_ascii=False))
    brief = merge_project_brief(blank_brief(), parsed["project_updates"])

    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = os.path.join(td, "autofill-sim.db")
        from app import main as app_main
        app_main.DB_PATH = app_main.Path(os.environ["PROJECT_OS_DB"])
        app_main.SEED_DEMO = False
        app_main.init_db()

        with TestClient(app_main.app) as client:
            def client_http(method: str, url: str, payload=None, access_key: str = ""):
                split = urlsplit(url)
                target = split.path + (f"?{split.query}" if split.query else "")
                response = client.request(method, target, json=payload)
                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
                return response.json() if response.content else None

            with patch("local_bridge.project_cli.http_json", side_effect=client_http):
                project = apply_to_server("http://simulator", "", "sim-user", brief, parsed)

            snap = client.get(f"/api/projects/{project['id']}/snapshot").json()
            provisional = [d for d in snap["decisions"] if d["status"] == "provisional"]
            checks = {
                "project_created": snap["project"]["name"] == "HMI MES Autofill 미니라인",
                "documents_13": len(snap["documents"]) == 13,
                "requirements_3": len(snap["requirements"]) == 3,
                "human_decision": any(d["status"] == "accepted" for d in snap["decisions"]),
                "provisional_decisions_4": len(provisional) == 4,
                "sqlite_is_provisional": any("SQLite" in d["title"] for d in provisional),
                "process_canvas": len([n for n in snap["nodes"] if n["view"] == "process"]) == 4,
                "architecture_canvas": len([n for n in snap["nodes"] if n["view"] == "architecture"]) == 4,
                "dataflow_canvas": len([n for n in snap["nodes"] if n["view"] == "dataflow"]) == 4,
            }
            for name, ok in checks.items():
                print(f"[AUTOFILL SIM] {name}: {'PASS' if ok else 'FAIL'}")
            if not all(checks.values()):
                return 1
            print(f"[AUTOFILL SIM] PROJECT CREATED: ID={project['id']} name={project['name']}")
            print("[AUTOFILL SIM] PROVISIONAL AUTOFILL E2E: PASS")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
