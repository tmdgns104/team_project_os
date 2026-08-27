import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.delivery_documents import build_delivery_documents
from app.live_state import sanitize_live_state
from local_bridge.project_cli_v014 import read_clipboard_text


class V014ProfessionalDocumentTests(unittest.TestCase):
    def test_all_13_documents_have_delivery_grade_sections(self):
        docs = build_delivery_documents({
            "name": "HMI MES Mini Line",
            "goal": "생산/불량/설비상태/알람을 실시간 확인하고 이력을 저장",
            "project_type": "manufacturing_automation",
            "problem": "수기 확인과 기록 누락",
            "users": "운전 작업자, 생산 관리자",
            "deliverables": "Simulator, HMI, Backend, DB, QA",
            "success_criteria": "1000개 처리 시 화면/DB 수량 일치",
            "scope": "포함=Simulator/HMI/MES, 제외=실제 PLC 구매",
            "constraints": "Simulator-first",
            "schedule": "10일 V1",
            "team": "PM/Dev/QA",
            "risks": "실제 MC Protocol 현장 확인 필요",
        })
        self.assertEqual(len(docs), 13)
        checks = {
            "proposal": ["Executive Summary", "Approval"],
            "plan": ["Deliverable-oriented WBS", "RACI", "Change / Configuration"],
            "milestone": ["Gantt Schedule", "Start Week", "Milestone Gates"],
            "backlog": ["Definition of Ready", "Definition of Done", "Dependency"],
            "requirements": ["Source / Rationale", "Acceptance Criteria", "Verification", "Traceability"],
            "service_policy": ["Service Level", "Incident", "RPO", "RTO", "Rollback"],
            "function_definition": ["Preconditions", "Business Rules", "Exception / Error"],
            "ia": ["Navigation Model", "Page / Information Inventory", "User Journey"],
            "screen_design": ["Screen State Matrix", "Validation", "Error / Empty"],
            "system_architecture": ["Stakeholders & Concerns", "System Context", "Container / Major Component", "Deployment / Runtime"],
            "data_flow": ["Data Flow Register", "Data Dictionary", "Retention"],
            "api_design": ["openapi: 3.2.0", "Endpoint / Message Catalog", "Idempotency", "Deprecation"],
            "qa": ["Test Strategy", "Test Cases", "Evidence", "Release / Acceptance Gate"],
        }
        for doc_type, markers in checks.items():
            for marker in markers:
                self.assertIn(marker, docs[doc_type], f"{doc_type}: {marker}")
        # 10 working days becomes a compact 2-week provisional schedule instead of a fixed 16-week template.
        self.assertIn("| 1 | 2 |", docs["milestone"])

    def test_malformed_model_state_is_safely_normalized(self):
        safe = sanitize_live_state({
            "project_updates": {"goal": ["bad", "shape"], "project_type": "manufacturing_automation"},
            "requirements": [
                "bad",
                {"ref": "REQ-001", "title": "상태 저장", "priority": "High", "acceptance_criteria": "상태 변경 이벤트 기록"},
            ],
            "decisions": [42, {"title": "SQLite", "body": "V1", "status": "provisional"}],
            "design_updates": [{
                "view": "architecture",
                "nodes": ["bad", {"key": "a", "label": "Simulator", "kind": "device"}, {"key": "b", "label": "Backend", "kind": "service"}],
                "edges": [{"source": "a", "target": "b", "label": "events"}, {"source": "a", "target": "missing"}],
            }],
            "pending": [{"unexpected": "dict"}, "실제 PLC 연결 미정"],
        })
        self.assertNotIn("goal", safe["project_updates"])
        self.assertEqual(len(safe["requirements"]), 1)
        self.assertEqual(safe["requirements"][0]["priority"], "High")
        self.assertEqual(len(safe["design_updates"][0]["edges"]), 1)
        self.assertEqual(safe["pending"], ["실제 PLC 연결 미정"])

    @patch("local_bridge.project_cli_v014.platform.system", return_value="Darwin")
    @patch("local_bridge.project_cli_v014.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("local_bridge.project_cli_v014.subprocess.run")
    def test_macos_clipboard_supports_multiline(self, run, which, system):
        run.return_value.returncode = 0
        run.return_value.stdout = "첫 줄\n둘째 줄\n셋째 줄"
        run.return_value.stderr = ""
        self.assertEqual(read_clipboard_text(), "첫 줄\n둘째 줄\n셋째 줄")


class V014ServerCompatibilityTests(unittest.TestCase):
    def test_repeated_live_sync_with_malformed_items_does_not_500(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = str(Path(td) / "v014.db")
            from app import main as base
            base.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
            base.SEED_DEMO = False
            import app.main_v014 as v014
            base.init_db()
            with TestClient(v014.app) as client:
                draft = client.post("/api/design-drafts", json={"member_name": "승훈", "provider": "codex", "name_hint": "HMI MES"}).json()
                state = {
                    "project_updates": {
                        "name": "HMI MES Mini Line", "goal": "생산/불량/상태/알람 실시간 HMI",
                        "project_type": "manufacturing_automation", "schedule": "10일 V1",
                        "scope": "Simulator-first / 실제 PLC 연결 제외",
                    },
                    "requirements": [
                        {"ref": "REQ-001", "title": "생산수량 저장", "detail": "제품 완료 이벤트 저장", "priority": "High", "acceptance_criteria": "1000개 후 DB/화면 수량 일치", "verification": "E2E Test"},
                        "malformed",
                    ],
                    "decisions": [{"title": "V1 DB", "body": "SQLite", "status": "provisional"}, 123],
                    "design_updates": [
                        {"view": "process", "mode": "replace", "nodes": [{"key": "p1", "label": "제품 투입", "kind": "event"}, {"key": "p2", "label": "검사", "kind": "process"}, {"key": "p3", "label": "실적 저장", "kind": "database"}], "edges": [{"source": "p1", "target": "p2", "label": "product"}, {"source": "p2", "target": "p3", "label": "result"}]},
                        {"view": "architecture", "mode": "replace", "nodes": [{"key": "a1", "label": "Simulator", "kind": "device"}, {"key": "a2", "label": "FastAPI", "kind": "service"}, {"key": "a3", "label": "SQLite", "kind": "database"}, {"key": "a4", "label": "Web HMI", "kind": "ui"}], "edges": [{"source": "a1", "target": "a2", "label": "tags"}, {"source": "a2", "target": "a3", "label": "events"}, {"source": "a2", "target": "a4", "label": "WebSocket"}]},
                        {"view": "dataflow", "mode": "replace", "nodes": [{"key": "d1", "label": "Virtual X/Y/M/D", "kind": "source"}, {"key": "d2", "label": "Normalize", "kind": "process"}, {"key": "d3", "label": "Event Store", "kind": "database"}, {"key": "d4", "label": "HMI", "kind": "sink"}], "edges": [{"source": "d1", "target": "d2", "label": "raw tags"}, {"source": "d2", "target": "d3", "label": "events"}, {"source": "d2", "target": "d4", "label": "live state"}]},
                    ],
                    "document_updates": [],
                    "pending": [{"bad": "shape"}, "실제 PLC 통신/안전 정책은 추후 승인"],
                }
                for _ in range(5):
                    response = client.put(f"/api/design-drafts/{draft['id']}/sync", json={"member_name": "승훈", "state": state})
                    self.assertEqual(response.status_code, 200, response.text)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                self.assertEqual({n["view"] for n in snap["nodes"]}, {"process", "architecture", "dataflow"})
                reqdoc = next(d for d in snap["documents"] if d["doc_type"] == "requirements")
                self.assertIn("E2E Test", reqdoc["content"])
                self.assertEqual(client.get("/api/health").json()["version"], "0.14.0")


if __name__ == "__main__":
    unittest.main()
