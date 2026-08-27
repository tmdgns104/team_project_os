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
    print(f"[V014 FULL] {name}: {'PASS' if value else 'FAIL'}")
    if not value:
        raise SystemExit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = str(Path(td) / "full-v014.db")
        from app import main as base
        base.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
        base.SEED_DEMO = False
        import app.main_v014 as v014
        base.init_db()

        with TestClient(v014.app) as client:
            draft = client.post("/api/design-drafts", json={"member_name": "sim-user", "provider": "codex", "name_hint": "HMI MES"}).json()
            check("draft_created", draft.get("lifecycle") == "draft")

            state = {
                "project_updates": {
                    "name": "HMI MES Mini Line",
                    "goal": "Mitsubishi 호환 Simulator 기반으로 생산/불량/설비상태/알람을 실시간 표시·저장한다.",
                    "project_type": "manufacturing_automation",
                    "problem": "수기 상태 확인과 생산실적 기록으로 누락과 확인 지연이 발생한다.",
                    "users": "운전 작업자, 생산 관리자",
                    "deliverables": "Conveyor Simulator, PLC Adapter, FastAPI, Web HMI, SQLite, QA/운영 문서",
                    "success_criteria": "제품 1000개 처리 후 화면/DB 수량 일치, 재시작 후 이력 정상 조회",
                    "scope": "포함=Simulator/HMI/MES 이력, 제외=실제 PLC 구매/실제 안전제어",
                    "current_state": "수기 확인/기록",
                    "target_state": "Simulator → Adapter → Service → DB/HMI",
                    "constraints": "Simulator-first; 실제 설비 제어는 별도 Human Gate",
                    "schedule": "10일 V1",
                    "team": "Human PM + Dev/QA + AI Design Worker",
                    "risks": "실제 FX5U/MC Protocol 현장 조건은 추후 확인",
                },
                "requirements": [
                    {"ref": "REQ-001", "type": "Functional", "title": "생산/불량 이벤트 저장", "detail": "제품 완료 시 판정과 시각 저장", "priority": "High", "acceptance_criteria": "1000개 처리 후 중복 없이 화면/DB 수량 일치", "verification": "E2E Test", "source": "사용자 요청", "status": "defined"},
                    {"ref": "REQ-002", "type": "Functional", "title": "설비상태/알람 이력", "detail": "상태 변경과 알람 발생/확인/해제 기록", "priority": "High", "acceptance_criteria": "모든 상태전환과 알람 타임스탬프 조회 가능", "verification": "Integration Test", "source": "사용자 요청", "status": "defined"},
                    {"ref": "REQ-003", "type": "NonFunctional", "title": "실시간 HMI", "detail": "현재 상태를 WebSocket으로 반영", "priority": "High", "acceptance_criteria": "정상 연결 시 목표 500ms 이내 반영", "verification": "Measurement", "source": "AI provisional + 사용자 승인", "status": "defined"},
                ],
                "decisions": [
                    {"title": "Mitsubishi-compatible simulator", "body": "X/Y/M/D 가상 디바이스와 교체 가능한 adapter", "status": "accepted"},
                    {"title": "V1 FastAPI + SQLite + Web HMI", "body": "가역적 로컬 V1 기본값", "status": "provisional"},
                ],
                "document_updates": [],
                "design_updates": [
                    {"view": "process", "mode": "replace", "nodes": [{"key": "p1", "label": "제품 투입", "kind": "event"}, {"key": "p2", "label": "컨베이어 이동", "kind": "process"}, {"key": "p3", "label": "검사/판정", "kind": "decision"}, {"key": "p4", "label": "양품/불량 분류", "kind": "process"}, {"key": "p5", "label": "이벤트 저장", "kind": "database"}, {"key": "p6", "label": "HMI 갱신", "kind": "ui"}], "edges": [{"source": "p1", "target": "p2", "label": "detect"}, {"source": "p2", "target": "p3", "label": "arrive"}, {"source": "p3", "target": "p4", "label": "result"}, {"source": "p4", "target": "p5", "label": "production event"}, {"source": "p5", "target": "p6", "label": "KPI/history"}]},
                    {"view": "architecture", "mode": "replace", "nodes": [{"key": "a1", "label": "Conveyor Simulator", "kind": "device"}, {"key": "a2", "label": "PLC Adapter", "kind": "service"}, {"key": "a3", "label": "FastAPI MES Service", "kind": "service"}, {"key": "a4", "label": "SQLite Event Store", "kind": "database"}, {"key": "a5", "label": "Web HMI", "kind": "ui"}], "edges": [{"source": "a1", "target": "a2", "label": "virtual X/Y/M/D"}, {"source": "a2", "target": "a3", "label": "normalized state/events"}, {"source": "a3", "target": "a4", "label": "event records"}, {"source": "a3", "target": "a5", "label": "REST/WebSocket"}]},
                    {"view": "dataflow", "mode": "replace", "nodes": [{"key": "d1", "label": "Virtual PLC Memory", "kind": "source"}, {"key": "d2", "label": "Validate / Normalize", "kind": "process"}, {"key": "d3", "label": "Business Event Processor", "kind": "service"}, {"key": "d4", "label": "SQLite Store", "kind": "database"}, {"key": "d5", "label": "HMI Consumer", "kind": "sink"}], "edges": [{"source": "d1", "target": "d2", "label": "raw device values"}, {"source": "d2", "target": "d3", "label": "validated event"}, {"source": "d3", "target": "d4", "label": "production/state/alarm"}, {"source": "d3", "target": "d5", "label": "live state"}, {"source": "d4", "target": "d5", "label": "history/KPI"}]},
                ],
                "pending": ["실제 PLC 모델/현장 네트워크/안전회로는 실제 적용 전 승인"],
            }

            # Reproduce a long Design Session: valid state is repeatedly synced while a few turns contain malformed AI list entries.
            for i in range(8):
                noisy = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in state.items()}
                if i in {2, 4, 6}:
                    noisy["pending"] = list(state["pending"]) + [{"malformed": "model delta"}]
                if i == 3:
                    noisy["requirements"] = list(state["requirements"]) + ["malformed requirement"]
                response = client.put(f"/api/design-drafts/{draft['id']}/sync", json={"member_name": "sim-user", "state": noisy})
                check(f"live_sync_{i + 1}", response.status_code == 200)

            snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check("documents_13", len(snap["documents"]) == 13)
            docs = {d["doc_type"]: d["content"] for d in snap["documents"]}
            markers = {
                "proposal": "Executive Summary", "plan": "Deliverable-oriented WBS", "milestone": "Gantt Schedule",
                "backlog": "Definition of Done", "requirements": "Acceptance Criteria", "service_policy": "Incident",
                "function_definition": "Preconditions", "ia": "Navigation Model", "screen_design": "Screen State Matrix",
                "system_architecture": "System Context", "data_flow": "Data Dictionary", "api_design": "openapi: 3.2.0", "qa": "Test Strategy",
            }
            for doc_type, marker in markers.items():
                check(f"doc_{doc_type}", marker in docs.get(doc_type, ""))
            check("requirements_3", len(snap["requirements"]) == 3)
            check("design_views_3", {n["view"] for n in snap["nodes"]} == {"process", "architecture", "dataflow"})
            for view in ("process", "architecture", "dataflow"):
                ids = {n["id"] for n in snap["nodes"] if n["view"] == view}
                edges = [e for e in snap["edges"] if e["view"] == view]
                check(f"{view}_edge_integrity", bool(ids) and all(e["source_id"] in ids and e["target_id"] in ids for e in edges))

            promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={"member_name": "sim-user", "state": state})
            check("apply", promoted.status_code == 200 and promoted.json()["project"]["lifecycle"] == "active")
            final = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check("persist_documents", len(final["documents"]) == 13)
            check("persist_designs", {n["view"] for n in final["nodes"]} == {"process", "architecture", "dataflow"})
            check("health_v014", client.get("/api/health").json().get("version") == "0.14.0")
            print("[V014 FULL] PROJECT + 13 PROFESSIONAL DOCUMENTS + 3 DIAGRAMS + LIVE SYNC: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
