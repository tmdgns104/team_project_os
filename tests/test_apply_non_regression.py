import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class ApplyNonRegressionTests(unittest.TestCase):
    def test_apply_preserves_richer_live_milestone_and_process_graph(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = str(Path(td) / "apply-preserve.db")
            from app import main as base
            base.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
            base.SEED_DEMO = False
            import app.main_v014 as v014
            base.init_db()

            with TestClient(v014.app) as client:
                draft = client.post("/api/design-drafts", json={
                    "member_name": "tester",
                    "provider": "codex",
                    "name_hint": "PLC HMI MES",
                }).json()
                pid = draft["id"]

                rich_milestone = """# 개발 마일스톤

## Gantt Schedule

| Phase | Task | Start Week | End Week | Owner | Status | Deliverable | Exit Criteria |
|---|---|---:|---:|---|---|---|---|
| 계획 | 요구사항 기준선 | 1 | 2 | 1인 개발자 | Planned | 요구사항 정의서 | REQ 승인 |
| Phase 1 | Ladder / I/O / STEP | 3 | 5 | 1인 개발자 | Planned | PLC Project | 정상 시퀀스 PASS |
| Phase 2 | XGCommLib / C# Bridge | 6 | 9 | 1인 개발자 | Planned | Bridge + Adapter | Snapshot 일치 |
| Phase 3 | MES / SQLite / OEE | 10 | 13 | 1인 개발자 | Planned | MES DB | Event 재계산 일치 |
| Phase 4 | FastAPI / Web HMI | 14 | 17 | 1인 개발자 | Planned | Web HMI | 화면 인수시험 PASS |
| 통합/QA | Recovery / 100 Cycle | 18 | 20 | 1인 개발자 | Planned | Evidence Pack | Release Gate PASS |

### 주차 기준
W1 W2 W3 W4 W5 W6 W7 W8 W9 W10 W11 W12 W13 W14 W15 W16 W17 W18 W19 W20
"""
                rich_process = {
                    "view": "process",
                    "mode": "replace",
                    "nodes": [
                        {"key": "p1", "label": "제품 투입", "kind": "step", "detail": "투입 센서 감지"},
                        {"key": "p2", "label": "컨베이어 이동", "kind": "step", "detail": "검사 위치 이동"},
                        {"key": "p3", "label": "가상 검사", "kind": "step", "detail": "PASS/FAIL 판정"},
                        {"key": "p4", "label": "분류", "kind": "step", "detail": "양품/불량 분기"},
                        {"key": "p5", "label": "실적 저장", "kind": "step", "detail": "Production Event 저장"},
                    ],
                    "edges": [
                        {"source": "p1", "target": "p2", "label": "product"},
                        {"source": "p2", "target": "p3", "label": "at inspection"},
                        {"source": "p3", "target": "p4", "label": "result"},
                        {"source": "p4", "target": "p5", "label": "complete"},
                    ],
                }
                live_state = {
                    "project_updates": {
                        "name": "PLC Mini Line HMI MES",
                        "goal": "XG-SIM에서 PLC부터 MES/HMI까지 통합 검증",
                        "project_type": "manufacturing_automation",
                        "schedule": "1인 개발 20주 PROVISIONAL",
                    },
                    "requirements": [{
                        "ref": "REQ-PLC-001",
                        "type": "Functional",
                        "title": "STEP 기반 생산 시퀀스",
                        "detail": "정상 생산 사이클을 STEP FSM으로 제어",
                        "priority": "Must",
                        "acceptance_criteria": "정의된 STEP 순서로 100사이클 완료",
                        "verification": "Ladder Trace + E2E Test",
                        "traceability": "FUNC-PLC-001 -> TC-CTRL-001",
                        "status": "defined",
                    }],
                    "decisions": [],
                    "document_updates": [{
                        "doc_type": "milestone",
                        "content": rich_milestone,
                        "reason": "상세 20주 Gantt",
                    }],
                    "design_updates": [rich_process],
                    "pending": [],
                }
                synced = client.put(f"/api/design-drafts/{pid}/sync", json={
                    "member_name": "tester",
                    "state": live_state,
                })
                self.assertEqual(synced.status_code, 200, synced.text)

                # Simulate a final Distiller that summarizes the same project too aggressively.
                poorer_final = {
                    "project_updates": dict(live_state["project_updates"]),
                    "requirements": list(live_state["requirements"]),
                    "decisions": [],
                    "document_updates": [{
                        "doc_type": "milestone",
                        "content": "# 개발 마일스톤\n\n20주 동안 개발한다.",
                        "reason": "final summary",
                    }],
                    "design_updates": [{
                        "view": "process",
                        "mode": "replace",
                        "nodes": [
                            {"key": "a", "label": "생산", "kind": "step", "detail": ""},
                            {"key": "b", "label": "저장", "kind": "step", "detail": ""},
                        ],
                        "edges": [{"source": "a", "target": "b", "label": ""}],
                    }],
                    "pending": [],
                }
                promoted = client.post(f"/api/design-drafts/{pid}/promote", json={
                    "member_name": "tester",
                    "state": poorer_final,
                })
                self.assertEqual(promoted.status_code, 200, promoted.text)

                snapshot = client.get(f"/api/projects/{pid}/snapshot").json()
                milestone = next(d for d in snapshot["documents"] if d["doc_type"] == "milestone")
                self.assertIn("Exit Criteria", milestone["content"])
                self.assertIn("W20", milestone["content"])
                self.assertNotEqual(milestone["content"].strip(), poorer_final["document_updates"][0]["content"].strip())
                process_nodes = [n for n in snapshot["nodes"] if n["view"] == "process"]
                process_edges = [e for e in snapshot["edges"] if e["view"] == "process"]
                self.assertEqual(len(process_nodes), 5)
                self.assertEqual(len(process_edges), 4)
                self.assertEqual(snapshot["project"]["lifecycle"], "active")
                self.assertEqual(client.get("/api/health").json()["version"], "0.14.1")


if __name__ == "__main__":
    unittest.main()
