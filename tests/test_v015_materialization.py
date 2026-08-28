from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class V015MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["PROJECT_OS_DB"] = str(Path(self.tmp.name) / "v015.db")
        os.environ["PROJECT_OS_SEED_DEMO"] = "0"
        from app import main as core
        from app import main_v015
        importlib.reload(core)
        importlib.reload(main_v015)
        self.main = main_v015
        self.main.core.init_db()
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def state(self):
        return {
            "project_updates": {
                "name": "PLC Mini Line HMI MES",
                "goal": "XG-SIM 기반 PLC-HMI-MES 통합 데모",
                "project_type": "manufacturing_automation",
                "problem": "PLC 제어/생산이력/HMI가 분리되어 통합 검증이 어렵다",
                "users": "운전 작업자, 생산 관리자, 개발자",
                "scope": "XG-SIM → XGT Ethernet → XGCommLib → x86 C# Bridge → Python MES → Web HMI",
                "deliverables": "PLC Sequence, Bridge, MES DB, Web HMI, 13종 문서, 3종 Design",
                "success_criteria": "1000개 처리 후 PLC/HMI/DB 수량 정합, 중복 이벤트 0",
                "schedule": "1인 개발 20주 PROVISIONAL",
                "constraints": "XGCommLib 32bit, 실제 PLC는 V1 제외",
                "risks": "통신단절, COM 호환성, 이벤트 중복",
            },
            "requirements": [
                {"ref": "REQ-PLC-001", "type": "Functional", "title": "PLC Snapshot 수집", "detail": "STEP/X/Y/M/D를 일관된 Snapshot으로 수집", "source": "사용자 요구", "priority": "High", "acceptance_criteria": "동일 Scan의 STEP/I/O 정합", "verification": "Integration Test", "owner": "Dev", "traceability": "FUNC-PLC-001, IF-PLC-001, TC-PLC-001", "status": "defined"},
                {"ref": "REQ-MES-001", "type": "Functional", "title": "생산 이벤트 저장", "detail": "제품별 PASS/FAIL 이벤트 저장", "source": "사용자 요구", "priority": "High", "acceptance_criteria": "1000개 처리 후 HMI/DB 집계 일치, 중복 0", "verification": "E2E Test", "owner": "Dev", "traceability": "FUNC-MES-001, API-WS-001, TC-MES-001", "status": "defined"},
            ],
            "decisions": [
                {"title": "SQLite V1", "body": "단일 PC V1 저장소", "status": "provisional"},
                {"title": "XG-SIM V1", "body": "최종 시연은 XG-SIM까지", "status": "accepted"},
            ],
            "milestones": [
                {"id": "MS-PLC-001", "phase": "A. PLC", "task": "Ladder/STEP/I/O 기준선", "start_week": "1", "end_week": "4", "owner": "Dev", "status": "Draft", "deliverable": "PLC 기준선", "exit_criteria": "Sequence Test PASS", "requirement_refs": "REQ-PLC-001"},
                {"id": "MS-MES-001", "phase": "B. MES", "task": "생산 이벤트/HMI 구현", "start_week": "8", "end_week": "16", "owner": "Dev", "status": "Todo", "deliverable": "MES/HMI", "exit_criteria": "E2E PASS", "requirement_refs": "REQ-MES-001"},
            ],
            "backlog_items": [
                {"id": "BL-PLC-001", "epic": "PLC Integration", "title": "Snapshot Adapter", "detail": "PLC 값을 Snapshot으로 매핑", "priority": "High", "estimate": "5d", "owner": "Dev", "status": "Todo", "requirement_refs": "REQ-PLC-001", "dependencies": "MS-PLC-001", "definition_of_ready": "I/O Map 기준선", "definition_of_done": "TC-PLC-001 PASS"}
            ],
            "functions": [
                {"id": "FUNC-MES-001", "name": "생산 이벤트 기록", "actor": "MES Service", "trigger": "제품 완료", "preconditions": "PLC 연결", "inputs": "PlcSnapshot", "business_rules": "제품 ID idempotency", "normal_flow": "완료 감지→판정→DB 저장→HMI publish", "exception_flow": "중복은 무시하고 로그", "outputs": "ProductionEvent", "acceptance_criteria": "중복 0", "requirement_refs": "REQ-MES-001"}
            ],
            "screens": [
                {"id": "SCR-HMI-001", "name": "메인 운전 HMI", "purpose": "실시간 설비/생산/알람 확인", "users": "운전 작업자", "entry_conditions": "서버 연결", "components": "공정 흐름, KPI, Alarm", "actions": "Start/Stop/Alarm Ack", "validation": "통신 상태 검증", "states": "Loading/Disconnected/Alarm/Run", "api_refs": "API-WS-001", "requirement_refs": "REQ-MES-001"}
            ],
            "interfaces": [
                {"id": "IF-PLC-001", "kind": "Bridge", "method": "TCP", "path": "localhost bridge", "name": "PLC Snapshot", "purpose": "x86 COM→Python", "auth": "local only", "request": "read snapshot", "response": "PlcSnapshot JSON", "errors": "COMM_TIMEOUT", "timeout_retry": "1s/3 retry", "idempotency": "read-only", "versioning": "v1", "requirement_refs": "REQ-PLC-001"},
                {"id": "API-WS-001", "kind": "WebSocket", "method": "WS", "path": "/ws/hmi", "name": "Live HMI", "purpose": "실시간 상태 push", "auth": "session", "request": "subscribe", "response": "HmiState", "errors": "disconnect/reconnect", "timeout_retry": "3s reconnect", "idempotency": "snapshot replacement", "versioning": "v1", "requirement_refs": "REQ-MES-001"},
            ],
            "tests": [
                {"id": "TC-PLC-001", "requirement_refs": "REQ-PLC-001", "priority": "High", "preconditions": "XG-SIM RUN", "steps": "STEP/I/O 변경→Snapshot 읽기", "expected": "동일 상태 정합", "evidence": "PLC/Harness log", "pass_fail": "Mismatch 0", "status": "Not Run"},
                {"id": "TC-MES-001", "requirement_refs": "REQ-MES-001", "priority": "High", "preconditions": "Simulator ready", "steps": "제품 1000개 처리", "expected": "HMI/DB 수량 일치, 중복 0", "evidence": "DB query + screenshot", "pass_fail": "불일치/중복 0", "status": "Not Run"},
            ],
            "policies": [
                {"id": "POL-ALARM-001", "category": "Incident", "policy": "알람 발생/확인/해제 이력 보존", "target": "모든 Alarm lifecycle 기록", "monitoring": "Alarm Event Log", "response": "Ack/Reset 후 원인 기록", "owner": "Operator", "status": "Draft", "requirement_refs": "REQ-MES-001"}
            ],
            "data_items": [
                {"id": "DATA-PLC-001", "name": "PlcSnapshot", "source": "XG-SIM/XGCommLib", "producer": "x86 Bridge", "fields": "step,x,y,m,d,timestamp", "validation": "주소/타임스탬프 검증", "processing": "normalize→state/event detect", "destination": "MES Service", "protocol": "TCP/JSON", "retention": "현재값 + 이벤트 파생", "failure_handling": "timeout/alarm/reconnect", "requirement_refs": "REQ-PLC-001"}
            ],
            "design_updates": [
                {"view": "process", "nodes": [{"key": "in", "label": "제품 투입", "kind": "event", "detail": "투입 센서"}, {"key": "move", "label": "컨베이어 이동", "kind": "process", "detail": "STEP 진행"}, {"key": "inspect", "label": "검사 판정", "kind": "decision", "detail": "PASS/FAIL"}, {"key": "save", "label": "생산실적 저장", "kind": "process", "detail": "ProductionEvent"}, {"key": "alarm", "label": "STOP/E-STOP/Alarm", "kind": "decision", "detail": "예외 분기"}], "edges": [{"source": "in", "target": "move", "label": "trigger"}, {"source": "move", "target": "inspect", "label": "arrive"}, {"source": "inspect", "target": "save", "label": "PASS/FAIL"}, {"source": "move", "target": "alarm", "label": "fault"}]},
                {"view": "architecture", "nodes": [{"key": "sim", "label": "XG-SIM", "kind": "device", "detail": "PLC Simulation"}, {"key": "bridge", "label": "x86 XGComm Bridge", "kind": "service", "detail": "XGCommLib COM"}, {"key": "mes", "label": "Python MES", "kind": "service", "detail": "Event/KPI"}, {"key": "db", "label": "SQLite", "kind": "database", "detail": "History"}, {"key": "hmi", "label": "Web HMI", "kind": "ui", "detail": "FastAPI/WS"}], "edges": [{"source": "sim", "target": "bridge", "label": "XGT Ethernet"}, {"source": "bridge", "target": "mes", "label": "PlcSnapshot"}, {"source": "mes", "target": "db", "label": "events"}, {"source": "mes", "target": "hmi", "label": "REST/WS"}]},
                {"view": "dataflow", "nodes": [{"key": "tags", "label": "PLC Tags", "kind": "source", "detail": "X/Y/M/D/STEP"}, {"key": "snap", "label": "PlcSnapshot", "kind": "process", "detail": "normalize"}, {"key": "event", "label": "Production/Alarm Event", "kind": "process", "detail": "derive"}, {"key": "store", "label": "History Store", "kind": "database", "detail": "SQLite"}, {"key": "view", "label": "HMI State", "kind": "consumer", "detail": "REST/WS"}], "edges": [{"source": "tags", "target": "snap", "label": "raw values"}, {"source": "snap", "target": "event", "label": "validated state"}, {"source": "event", "target": "store", "label": "records"}, {"source": "snap", "target": "view", "label": "live state"}]},
            ],
            "pending": ["실제 XGK-CPUH 연결 조건", "XGCommLib 최종 라이선스/버전", "Safety threshold"],
        }

    def test_full_materialization_and_apply_non_regression(self):
        response = self.client.post("/api/design-drafts", json={"member_name": "Tester", "provider": "codex", "name_hint": "PLC Draft"})
        self.assertEqual(response.status_code, 200, response.text)
        project_id = response.json()["id"]
        state = self.state()
        response = self.client.put(f"/api/design-drafts/{project_id}/sync", json={"member_name": "Tester", "state": state})
        self.assertEqual(response.status_code, 200, response.text)

        snapshot = self.client.get(f"/api/projects/{project_id}/snapshot").json()
        self.assertEqual(len(snapshot["documents"]), 13)
        docs = {doc["doc_type"]: doc["content"] for doc in snapshot["documents"]}
        expected = ("proposal", "plan", "milestone", "backlog", "requirements", "service_policy", "function_definition", "ia", "screen_design", "system_architecture", "data_flow", "api_design", "qa")
        for key in expected:
            self.assertGreater(len(docs[key]), 300, key)
        self.assertIn("MS-MES-001", docs["milestone"])
        self.assertIn("Exit Criteria", docs["milestone"])
        self.assertIn("BL-PLC-001", docs["backlog"])
        self.assertIn("FUNC-MES-001", docs["function_definition"])
        self.assertIn("SCR-HMI-001", docs["screen_design"])
        self.assertIn("API-WS-001", docs["api_design"])
        self.assertIn("TC-MES-001", docs["qa"])
        self.assertIn("PlcSnapshot", docs["data_flow"])
        self.assertIn("PROVISIONAL", docs["requirements"])
        self.assertEqual({node["view"] for node in snapshot["nodes"]}, {"process", "architecture", "dataflow"})
        before = {key: docs[key] for key in ("milestone", "api_design", "qa")}

        poorer = {
            "project_updates": state["project_updates"],
            "requirements": state["requirements"][:1],
            "decisions": state["decisions"],
            "document_updates": [{"doc_type": "milestone", "content": "# 마일스톤\n20주 개발."}],
            "design_updates": [{"view": "process", "nodes": [{"key": "a", "label": "Start"}, {"key": "b", "label": "End"}], "edges": [{"source": "a", "target": "b"}]}],
        }
        response = self.client.post(f"/api/design-drafts/{project_id}/promote", json={"member_name": "Tester", "state": poorer})
        self.assertEqual(response.status_code, 200, response.text)

        snapshot2 = self.client.get(f"/api/projects/{project_id}/snapshot").json()
        docs2 = {doc["doc_type"]: doc["content"] for doc in snapshot2["documents"]}
        for key, value in before.items():
            self.assertEqual(docs2[key], value, key)
        self.assertEqual(snapshot2["project"]["lifecycle"], "active")
        self.assertEqual(self.client.get("/api/health").json()["version"], "0.15.0")
        self.assertGreaterEqual(len([node for node in snapshot2["nodes"] if node["view"] == "process"]), 5)


if __name__ == "__main__":
    unittest.main()
