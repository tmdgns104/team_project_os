from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.conversation import merge_project_brief, normalize_ai_result
from local_bridge.project_cli import apply_to_server, blank_brief


TRANSCRIPT = [
    ("user", "HMI MES 프로그램을 만들어보고 싶어"),
    ("assistant", "어떤 설비와 PLC를 가정할까요? 처음엔 시뮬레이터로 시작해도 됩니다."),
    ("user", "Mitsubishi PLC를 쓰고 작은 컨베이어 생산라인으로 하자. 처음엔 시뮬레이터로 하고 싶어"),
    ("assistant", "그러면 V1은 PLC 상태/생산 카운트 수집, HMI 표시, 생산실적 저장 정도로 줄이는 게 좋습니다."),
    ("user", "좋아. 생산수량, 불량수량, 설비상태를 저장하고 HMI에서 보게 하자. 실제 PLC 연결은 나중에 하자"),
]

DISTILLED = {
    "reply": "HMI/MES 미니 생산라인 V1로 정리했습니다.",
    "project_updates": {
        "name": "HMI MES 미니 생산라인",
        "goal": "Mitsubishi PLC 기반 미니 생산라인의 상태와 생산 정보를 HMI에서 확인하고 MES 형태로 저장·조회한다",
        "project_type": "manufacturing_automation",
        "problem": "HMI/MES 연동 흐름을 구현하며 익힐 실습 프로젝트가 필요하다",
        "users": "개발 학습자 및 작업자 역할 사용자",
        "deliverables": "PLC 시뮬레이터 연동, HMI, 생산실적 저장, 기본 조회",
        "scope": "단일 컨베이어, 시뮬레이터 우선, 생산수량/불량수량/설비상태",
        "constraints": "실제 PLC 연결은 V1 이후",
    },
    "requirements": [
        {"ref":"REQ-001","title":"PLC 데이터 수집","detail":"운전 상태와 생산 카운트를 수집","status":"defined"},
        {"ref":"REQ-002","title":"HMI 표시","detail":"설비 상태와 생산실적을 표시","status":"defined"},
        {"ref":"REQ-003","title":"MES 저장","detail":"생산/불량 수량을 저장","status":"defined"},
    ],
    "decisions": [
        {"title":"시뮬레이터 우선","body":"V1은 실제 PLC 대신 시뮬레이터로 검증","status":"accepted"}
    ],
    "document_updates": [
        {"doc_type":"proposal","content":"# 기획서\n\nHMI/MES 미니 생산라인을 구현한다.\n","reason":"확정 범위"}
    ],
    "design_updates": [
        {"view":"process","mode":"replace","nodes":[
            {"key":"plc","label":"PLC 운전","kind":"step"},
            {"key":"collect","label":"데이터 수집","kind":"step"},
            {"key":"save","label":"실적 저장","kind":"step"},
            {"key":"display","label":"HMI 표시","kind":"step"}],
         "edges":[
            {"source":"plc","target":"collect","label":"상태/카운트"},
            {"source":"collect","target":"save","label":"생산실적"},
            {"source":"save","target":"display","label":"조회"}]},
        {"view":"architecture","mode":"replace","nodes":[
            {"key":"plc","label":"Mitsubishi PLC Simulator","kind":"device"},
            {"key":"gateway","label":"Python Gateway","kind":"service"},
            {"key":"db","label":"Production DB","kind":"store"},
            {"key":"ui","label":"HMI/MES UI","kind":"component"}],
         "edges":[
            {"source":"plc","target":"gateway","label":"PLC Data"},
            {"source":"gateway","target":"db","label":"Production Record"},
            {"source":"db","target":"ui","label":"Query"}]},
        {"view":"dataflow","mode":"replace","nodes":[
            {"key":"plc","label":"PLC","kind":"device"},
            {"key":"gateway","label":"Gateway","kind":"service"},
            {"key":"db","label":"DB","kind":"store"},
            {"key":"ui","label":"UI","kind":"component"}],
         "edges":[
            {"source":"plc","target":"gateway","label":"status/count"},
            {"source":"gateway","target":"db","label":"record"},
            {"source":"db","target":"ui","label":"KPI/query"}]},
    ],
    "pending": ["실제 PLC 통신 프로토콜 미정", "운영 DB 제품 미정"],
}


def main() -> int:
    print("[SIM] vague idea -> multi-turn design discussion")
    for role, text in TRANSCRIPT:
        print(f"[SIM] {role}: {text}")
    print("[SIM] /apply -> one-time Project Distiller")

    parsed = normalize_ai_result(json.dumps(DISTILLED, ensure_ascii=False))
    brief = merge_project_brief(blank_brief(), parsed["project_updates"])

    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = os.path.join(td, "sim.db")
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
            checks = {
                "project_name": snap["project"]["name"] == "HMI MES 미니 생산라인",
                "documents_13": len(snap["documents"]) == 13,
                "requirements_3": len(snap["requirements"]) == 3,
                "process_canvas": len([n for n in snap["nodes"] if n["view"] == "process"]) == 4,
                "architecture_canvas": len([n for n in snap["nodes"] if n["view"] == "architecture"]) == 4,
                "dataflow_canvas": len([n for n in snap["nodes"] if n["view"] == "dataflow"]) == 4,
            }
            for name, ok in checks.items():
                print(f"[SIM] {name}: {'PASS' if ok else 'FAIL'}")
            if not all(checks.values()):
                return 1
            print(f"[SIM] PROJECT CREATED: ID={project['id']} name={project['name']}")
            print("[SIM] DESIGN SESSION E2E: PASS")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
