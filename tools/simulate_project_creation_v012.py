from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def check(name: str, value: bool) -> None:
    print(f"[V012 E2E] {name}: {'PASS' if value else 'FAIL'}")
    if not value:
        raise SystemExit(1)


def graph(view: str):
    if view == "process":
        nodes = [
            {"key":"detect","label":"제품/PLC 상태 감지","kind":"event","detail":"생산 이벤트 발생"},
            {"key":"collect","label":"PLC 데이터 수집","kind":"process","detail":"태그 정규화"},
            {"key":"judge","label":"상태 판정","kind":"decision","detail":"정상/이상 분기"},
            {"key":"save","label":"생산 실적 저장","kind":"process","detail":"수량/이력 기록"},
            {"key":"show","label":"HMI 현황 표시","kind":"ui","detail":"작업자 확인"},
        ]
        edges = [
            {"source":"detect","target":"collect","label":"trigger"},
            {"source":"collect","target":"judge","label":"normalized tags"},
            {"source":"judge","target":"save","label":"production result"},
            {"source":"judge","target":"show","label":"alarm/status"},
            {"source":"save","target":"show","label":"KPI"},
        ]
    elif view == "architecture":
        nodes = [
            {"key":"plc","label":"Mitsubishi PLC Simulator","kind":"device","detail":"V1 simulator"},
            {"key":"gateway","label":"PLC Gateway","kind":"service","detail":"adapter / normalization"},
            {"key":"backend","label":"MES Backend","kind":"service","detail":"FastAPI provisional"},
            {"key":"db","label":"Production DB","kind":"database","detail":"SQLite provisional"},
            {"key":"hmi","label":"Web HMI","kind":"ui","detail":"operator dashboard"},
        ]
        edges = [
            {"source":"plc","target":"gateway","label":"PLC tags"},
            {"source":"gateway","target":"backend","label":"events"},
            {"source":"backend","target":"db","label":"records"},
            {"source":"backend","target":"hmi","label":"REST / WebSocket"},
        ]
    else:
        nodes = [
            {"key":"source","label":"PLC Tag Source","kind":"source","detail":"status/count/alarm"},
            {"key":"normalize","label":"Normalize & Validate","kind":"process","detail":"schema validation"},
            {"key":"api","label":"MES Processing","kind":"service","detail":"business rules"},
            {"key":"store","label":"Production Store","kind":"database","detail":"production history"},
            {"key":"consumer","label":"HMI Consumer","kind":"sink","detail":"status/KPI visualization"},
        ]
        edges = [
            {"source":"source","target":"normalize","label":"raw tags"},
            {"source":"normalize","target":"api","label":"validated event"},
            {"source":"api","target":"store","label":"production record"},
            {"source":"api","target":"consumer","label":"live state"},
            {"source":"store","target":"consumer","label":"KPI query"},
        ]
    return {"view": view, "mode":"replace", "nodes":nodes, "edges":edges}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = str(Path(td) / "v012-e2e.db")
        from app import main as app_main
        app_main.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
        app_main.SEED_DEMO = False
        app_main.init_db()
        with TestClient(app_main.app) as client:
            draft = client.post("/api/design-drafts", json={"member_name":"sim-user","provider":"codex","name_hint":"HMI MES 실무 산출물 시뮬레이터"}).json()
            check("draft_created", draft.get("lifecycle") == "draft")

            state = {
                "project_updates": {
                    "name":"HMI MES Mini Production Line",
                    "goal":"소형 컨베이어 생산라인의 PLC 상태, 생산량, 불량량, 알람을 수집·저장·시각화한다.",
                    "project_type":"manufacturing_automation",
                    "problem":"수작업 상태 확인과 생산실적 기록 때문에 누락과 확인 지연이 발생한다.",
                    "users":"생산 작업자, 설비 담당자, 품질 담당자",
                    "deliverables":"PLC Gateway, MES Backend, Web HMI, 생산실적 DB, 운영/QA 문서",
                    "success_criteria":"Simulator E2E PASS, 핵심 요구사항 검증 Evidence 확보, 8시간 연속 시뮬레이션 오류 0건",
                    "scope":"포함=PLC Simulator, 수집, 저장, HMI / 제외=ERP 및 실제 장비 구매",
                    "current_state":"PLC 상태 확인과 생산실적 기록을 수동으로 수행",
                    "target_state":"PLC 이벤트 → 수집/정규화 → 저장/판정 → HMI 실시간 표시",
                    "constraints":"V1은 Windows Local 및 Simulator-first. 실제 비용/장비 구매는 승인 전 진행하지 않음",
                    "schedule":"Definition → Design → Implementation → QA",
                    "team":"Human PM + AI Design Worker + 개발/검증 담당",
                    "risks":"실제 PLC 통신 규격 및 현장 네트워크는 추후 확인 필요",
                },
                "requirements": [
                    {"ref":"REQ-001","title":"PLC 상태 수집","detail":"운전/정지/알람 태그를 수집한다","status":"defined"},
                    {"ref":"REQ-002","title":"생산 실적 저장","detail":"생산량/불량량과 시각을 저장한다","status":"defined"},
                    {"ref":"REQ-003","title":"HMI 실시간 표시","detail":"현재 상태와 KPI를 웹에서 확인한다","status":"defined"},
                ],
                "decisions": [
                    {"title":"PLC 계열","body":"Mitsubishi PLC","status":"accepted"},
                    {"title":"V1 Backend","body":"FastAPI","status":"provisional"},
                    {"title":"V1 Database","body":"SQLite","status":"provisional"},
                ],
                "document_updates": [],
                "design_updates": [graph("process"), graph("architecture"), graph("dataflow")],
                "pending": ["실제 PLC 프로토콜 최종 확정", "운영 보안 정책 승인"],
            }
            sync = client.put(f"/api/design-drafts/{draft['id']}/sync", json={"member_name":"sim-user","state":state})
            check("live_sync", sync.status_code == 200)
            snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()

            check("documents_13", len(snap["documents"]) == 13)
            by_type = {d["doc_type"]: d for d in snap["documents"]}
            check("proposal_professional", "Executive Summary" in by_type["proposal"]["content"] and "승인 기준" in by_type["proposal"]["content"])
            check("requirements_professional", "Acceptance Criteria" in by_type["requirements"]["content"])
            check("qa_professional", "Test Strategy" in by_type["qa"]["content"] and "Evidence" in by_type["qa"]["content"])
            check("requirements_materialized", len(snap["requirements"]) == 3)
            check("provisional_visible", sum(1 for d in snap["decisions"] if d["status"] == "provisional") == 2)

            for view, min_nodes, min_edges in [("process",5,5),("architecture",5,4),("dataflow",5,5)]:
                ns=[n for n in snap["nodes"] if n["view"]==view]
                es=[e for e in snap["edges"] if e["view"]==view]
                ids={n["id"] for n in ns}
                check(f"{view}_nodes", len(ns) >= min_nodes)
                check(f"{view}_edges", len(es) >= min_edges)
                check(f"{view}_edge_integrity", all(e["source_id"] in ids and e["target_id"] in ids and e["source_id"] != e["target_id"] for e in es))

            promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={"member_name":"sim-user","state":state}).json()["project"]
            check("promoted_active", promoted.get("lifecycle") == "active")
            final_snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check("documents_persist_after_apply", len(final_snap["documents"]) == 13)
            check("all_designs_persist_after_apply", {n["view"] for n in final_snap["nodes"]} == {"process","architecture","dataflow"})
            print(f"[V012 E2E] PROJECT CREATED: ID={promoted['id']} name={promoted['name']}")
            print("[V012 E2E] PROJECT + DOCUMENTS + 3 DIAGRAMS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
