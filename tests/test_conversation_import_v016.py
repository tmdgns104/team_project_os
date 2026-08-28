from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.conversation_import import REDACTED, parse_manual_transcript, redact_secrets
from app.conversation_providers import CodexConversationProvider


SESSION_ID = "01900000-0000-7000-8000-000000000016"
BROKEN_SESSION_ID = "01900000-0000-7000-8000-000000000099"


class CodexFixture:
    def __init__(self, root: Path):
        self.root = root
        self.session_path = root / "sessions" / "2026" / "08" / "28" / (
            f"rollout-2026-08-28T09-00-00-{SESSION_ID}.jsonl"
        )
        self.session_path.parent.mkdir(parents=True)
        (root / "session_index.jsonl").write_text(
            json.dumps(
                {"id": SESSION_ID, "thread_name": "PLC Mini Line 설계", "updated_at": "2026-08-28T09:20:00+09:00"},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        self.records: list[dict] = [
            {
                "timestamp": "2026-08-28T09:00:00+09:00",
                "ordinal": 0,
                "type": "session_meta",
                "payload": {
                    "id": SESSION_ID,
                    "session_id": SESSION_ID,
                    "timestamp": "2026-08-28T09:00:00+09:00",
                    "cli_version": "0.150.1",
                    "source": "cli",
                },
            }
        ]
        self.append("user", "XG-SIM과 Python으로 PLC 프로젝트를 만들자")
        self.append("assistant", "XGCommLib Bridge와 MES 구조를 검토할 수 있습니다.")
        self.append("user", "MES와 WebSocket API, 검증 테스트도 포함하자")
        self.append("assistant", "요구사항과 API/Test 추적성을 구성하겠습니다.")

    def append(self, role: str, text: str) -> None:
        ordinal = len(self.records)
        self.records.append(
            {
                "timestamp": f"2026-08-28T09:{ordinal:02d}:00+09:00",
                "ordinal": ordinal,
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": [
                        {
                            "type": "input_text" if role == "user" else "output_text",
                            "text": text,
                        }
                    ],
                },
            }
        )
        self.session_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in self.records),
            encoding="utf-8",
        )

    def add_broken_session(self) -> Path:
        path = self.session_path.with_name(
            f"rollout-2026-08-28T10-00-00-{BROKEN_SESSION_ID}.jsonl"
        )
        path.write_text('{"timestamp":"partial"\n', encoding="utf-8")
        return path


def first_delta() -> dict:
    return {
        "project_updates": {
            "name": "PLC Mini Line HMI MES",
            "goal": "XG-SIM 기반 PLC-HMI-MES 통합 검증",
            "project_type": "manufacturing_automation",
            "schedule": "20주 PROVISIONAL",
        },
        "requirements": [
            {
                "ref": "REQ-MES-001",
                "type": "Functional",
                "title": "생산 Event 저장",
                "detail": "제품 완료 이벤트를 중복 없이 저장",
                "source": "Native AI Conversation",
                "priority": "High",
                "acceptance_criteria": "1000개 처리 후 중복 0",
                "verification": "E2E Test",
                "traceability": "FUNC-MES-001, API-WS-001, TC-MES-001",
                "status": "defined",
            }
        ],
        "decisions": [
            {"ref": "DEC-DATA-001", "title": "SQLite 사용", "body": "V1 단일 PC", "status": "accepted"}
        ],
        "milestones": [
            {"id": "MS-MES-001", "phase": "Build", "task": "MES 구현", "start_week": "8", "end_week": "16", "status": "PROVISIONAL", "deliverable": "MES", "exit_criteria": "E2E PASS", "requirement_refs": "REQ-MES-001"}
        ],
        "functions": [
            {"id": "FUNC-MES-001", "name": "생산 Event 저장", "normal_flow": "완료 감지→저장", "exception_flow": "중복 무시", "requirement_refs": "REQ-MES-001"}
        ],
        "interfaces": [
            {"id": "API-WS-001", "kind": "WebSocket", "method": "WS", "path": "/ws/hmi", "name": "PLC State Stream", "purpose": "HMI 상태 push", "idempotency": "snapshot replace", "requirement_refs": "REQ-MES-001"}
        ],
        "tests": [
            {"id": "TC-MES-001", "requirement_refs": "REQ-MES-001", "priority": "High", "steps": "1000개 처리", "expected": "중복 0", "evidence": "DB query", "pass_fail": "duplicate=0", "status": "Not Run"}
        ],
        "design_updates": [
            {"view": "process", "mode": "merge", "nodes": [{"key": "start", "label": "제품 투입", "kind": "step"}, {"key": "save", "label": "실적 저장", "kind": "step"}], "edges": [{"source": "start", "target": "save", "label": "완료"}]},
            {"view": "architecture", "mode": "merge", "nodes": [{"key": "plc", "label": "XG-SIM", "kind": "device"}, {"key": "adapter", "label": "PLC Adapter Layer", "kind": "service"}, {"key": "mes", "label": "Python MES", "kind": "service"}], "edges": [{"source": "plc", "target": "adapter", "label": "XGCommLib"}, {"source": "adapter", "target": "mes", "label": "snapshot"}]},
            {"view": "dataflow", "mode": "merge", "nodes": [{"key": "tags", "label": "PLC Tags", "kind": "source"}, {"key": "events", "label": "Production Events", "kind": "database"}], "edges": [{"source": "tags", "target": "events", "label": "normalize/store"}]},
        ],
        "pending": ["실제 PLC I/O Address 확인 필요"],
    }


class ConversationProviderTests(unittest.TestCase):
    def test_codex_adapter_detects_lists_and_reads_incrementally(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CodexFixture(Path(directory))
            provider = CodexConversationProvider(fixture.root, executable="")
            detected = provider.detect()
            self.assertTrue(detected["detected"])
            self.assertTrue(detected["store_found"])
            self.assertFalse(detected["installed"])
            sessions = provider.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, SESSION_ID)
            self.assertEqual(sessions[0].title, "PLC Mini Line 설계")
            self.assertEqual(sessions[0].message_count, 4)
            self.assertEqual(len(provider.read_since(SESSION_ID, 2)), 2)

    def test_broken_session_is_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CodexFixture(Path(directory))
            fixture.add_broken_session()
            sessions = CodexConversationProvider(fixture.root, executable="").list_sessions()
            self.assertEqual(len(sessions), 2)
            broken = next(item for item in sessions if item.session_id == BROKEN_SESSION_ID)
            healthy = next(item for item in sessions if item.session_id == SESSION_ID)
            self.assertIn("malformed", broken.error)
            self.assertEqual(healthy.message_count, 4)

    def test_missing_codex_is_reported_without_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = CodexConversationProvider(Path(directory) / "missing", executable="")
            self.assertEqual(provider.detect()["message"], "Codex not detected")
            self.assertEqual(provider.list_sessions(), [])

    def test_secret_redaction_and_manual_fallback(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
        text = f"USER: OPENAI_API_KEY={secret}\nCodex: 저장하지 않겠습니다"
        redacted = redact_secrets(text)
        self.assertNotIn(secret, redacted)
        self.assertIn(REDACTED, redacted)
        messages = parse_manual_transcript(text)
        self.assertEqual([item.role for item in messages], ["user", "assistant"])


class ConversationImportApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in ("PROJECT_OS_DB", "PROJECT_OS_SEED_DEMO", "PROJECT_OS_CODEX_HOME")
        }

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        # The legacy tests intentionally inspect their versioned entry points in the
        # same interpreter. Restore that baseline after exercising V0.16 wrappers.
        from app import main as core
        from app import main_v014

        importlib.reload(core)
        importlib.reload(main_v014)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fixture = CodexFixture(self.root / "codex")
        os.environ["PROJECT_OS_DB"] = str(self.root / "project-os.db")
        os.environ["PROJECT_OS_SEED_DEMO"] = "0"
        os.environ["PROJECT_OS_CODEX_HOME"] = str(self.fixture.root)

        from app import main as core
        from app import main_v014, main_v015, main_v016

        importlib.reload(core)
        importlib.reload(main_v014)
        importlib.reload(main_v015)
        importlib.reload(main_v016)
        self.main = main_v016
        self.main.core.init_db()
        self.client = TestClient(self.main.app)
        response = self.client.post(
            "/api/projects",
            json={
                "name": "PLC Existing Project",
                "goal": "기존 프로젝트를 대화로 확장",
                "project_type": "manufacturing_automation",
                "schedule": "16주",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.project_id = response.json()["id"]

    def tearDown(self):
        self.client.close()
        os.environ.pop("PROJECT_OS_CODEX_HOME", None)
        self.tmp.cleanup()

    def preview(self, delta: dict | None = None):
        with patch("app.main_v016.distill_conversation", return_value=delta or first_delta()):
            return self.client.post(
                "/api/conversation-import/preview",
                json={
                    "project_id": self.project_id,
                    "provider": "codex",
                    "session_id": SESSION_ID,
                },
            )

    def test_scenario_a_first_import_materializes_13_documents_and_3_designs(self):
        before = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        original_requirements = next(
            item["content"] for item in before["documents"] if item["doc_type"] == "requirements"
        )
        preview = self.preview()
        self.assertEqual(preview.status_code, 200, preview.text)
        payload = preview.json()
        self.assertEqual(payload["status"], "preview")
        self.assertEqual(len(payload["messages"]), 4)
        self.assertTrue(payload["changes"]["requirements"])

        unchanged = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        self.assertIsNone(unchanged["live_draft"])
        self.assertEqual(
            next(item["content"] for item in unchanged["documents"] if item["doc_type"] == "requirements"),
            original_requirements,
        )

        drafted = self.client.post(f"/api/conversation-imports/{payload['import_id']}/draft")
        self.assertEqual(drafted.status_code, 200, drafted.text)
        snapshot = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        live = snapshot["live_draft"]
        self.assertEqual(len(live["documents"]), 13)
        self.assertEqual({item["view"] for item in live["nodes"]}, {"process", "architecture", "dataflow"})
        docs = {item["doc_type"]: item["content"] for item in live["documents"]}
        self.assertIn("REQ-MES-001", docs["requirements"])
        self.assertIn("API-WS-001", docs["api_design"])
        self.assertIn("TC-MES-001", docs["qa"])

        applied = self.client.post(f"/api/conversation-imports/{payload['import_id']}/apply")
        self.assertEqual(applied.status_code, 200, applied.text)
        final = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        self.assertIsNone(final["live_draft"])
        self.assertEqual(len(final["documents"]), 13)
        self.assertEqual({item["view"] for item in final["nodes"]}, {"process", "architecture", "dataflow"})

    def test_scenarios_b_and_c_incremental_reimport_and_idempotency(self):
        first = self.preview().json()
        self.client.post(f"/api/conversation-imports/{first['import_id']}/draft").raise_for_status()
        self.client.post(f"/api/conversation-imports/{first['import_id']}/apply").raise_for_status()

        self.fixture.append("user", "Work Order 관리도 추가하자")
        self.fixture.append("assistant", "새 MES 요구사항과 API/Test로 연결할 수 있습니다.")
        delta = {
            "requirements": [
                {"ref": "REQ-MES-001", "title": "생산 Event 저장", "detail": "제품 완료 이벤트를 중복 없이 저장"},
                {"ref": "REQ-MES-004", "title": "Work Order 관리", "detail": "작업지시 생성/상태 관리"},
            ],
            "interfaces": [
                {"id": "API-WS-001", "name": "PLC State Stream", "path": "/ws/hmi"},
                {"id": "API-WO-001", "name": "Work Order API", "method": "POST", "path": "/api/work-orders", "requirement_refs": "REQ-MES-004"},
            ],
            "tests": [
                {"id": "TC-MES-004", "requirement_refs": "REQ-MES-004", "steps": "작업지시 생성", "expected": "상태 저장"}
            ],
        }
        second_response = self.preview(delta)
        self.assertEqual(second_response.status_code, 200, second_response.text)
        second = second_response.json()
        self.assertEqual(len(second["messages"]), 2)
        self.client.post(f"/api/conversation-imports/{second['import_id']}/draft").raise_for_status()
        self.client.post(f"/api/conversation-imports/{second['import_id']}/apply").raise_for_status()

        with self.main.core.db() as conn:
            state = json.loads(
                conn.execute(
                    "SELECT state_json FROM project_structured_states WHERE project_id=?",
                    (self.project_id,),
                ).fetchone()["state_json"]
            )
        self.assertEqual([item["ref"] for item in state["requirements"]].count("REQ-MES-001"), 1)
        self.assertEqual([item["id"] for item in state["interfaces"]].count("API-WS-001"), 1)
        third = self.preview(delta)
        self.assertEqual(third.json()["status"], "no_changes")

    def test_scenario_d_decision_change_preserves_alternative_semantics(self):
        delta = first_delta()
        delta["decisions"] = [
            {"ref": "DEC-DATA-ALT-001", "title": "Redis", "body": "검토 후 V1 제외", "status": "alternative"},
            {"ref": "DEC-DATA-001", "title": "SQLite 사용", "body": "사용자가 선택", "status": "accepted"},
        ]
        preview = self.preview(delta).json()
        self.client.post(f"/api/conversation-imports/{preview['import_id']}/draft").raise_for_status()
        live = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()["live_draft"]
        statuses = {item["title"]: item["status"] for item in live["decisions"]}
        self.assertEqual(statuses["Redis"], "alternative")
        self.assertEqual(statuses["SQLite 사용"], "accepted")
        plan = next(item["content"] for item in live["documents"] if item["doc_type"] == "plan")
        self.assertIn("Rejected / Alternatives: Redis", plan)

    def test_scenario_e_secrets_never_reach_preview_database_or_documents(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        self.fixture.append("user", f"OPENAI_API_KEY={secret}")
        leaked_delta = first_delta()
        leaked_delta["pending"] = [f"token={secret}"]
        captured: dict = {}

        def fake_distiller(**kwargs):
            captured["messages"] = kwargs["messages"]
            return leaked_delta

        with patch("app.main_v016.distill_conversation", side_effect=fake_distiller):
            preview = self.client.post(
                "/api/conversation-import/preview",
                json={"project_id": self.project_id, "provider": "codex", "session_id": SESSION_ID},
            )
        self.assertEqual(preview.status_code, 200, preview.text)
        serialized = json.dumps(preview.json(), ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(secret, json.dumps(captured, ensure_ascii=False))
        import_id = preview.json()["import_id"]
        self.client.post(f"/api/conversation-imports/{import_id}/draft").raise_for_status()
        with self.main.core.db() as conn:
            stored = "\n".join(
                str(row[0])
                for table, column in (
                    ("conversation_imports", "delta_json"),
                    ("project_live_drafts", "state_json"),
                    ("project_live_drafts", "documents_json"),
                )
                for row in conn.execute(f"SELECT {column} FROM {table}")
            )
        self.assertNotIn(secret, stored)

    def test_scenario_f_apply_preserves_rich_existing_gantt_and_design(self):
        snapshot = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        milestone = next(item for item in snapshot["documents"] if item["doc_type"] == "milestone")
        rich = "# Gantt\n\n| ID | Start Week | End Week | Exit Criteria |\n|---|---:|---:|---|\n| MS-OLD-001 | 1 | 20 | W20 Release Gate PASS |\n"
        self.client.patch(
            f"/api/documents/{milestone['id']}",
            json={"content": rich, "status": "review", "updated_by": "Human"},
        ).raise_for_status()
        n1 = self.client.post(f"/api/projects/{self.project_id}/nodes", json={"view": "process", "label": "기존 상세 시작", "kind": "step", "detail": "preserve"}).json()
        n2 = self.client.post(f"/api/projects/{self.project_id}/nodes", json={"view": "process", "label": "기존 상세 종료", "kind": "step", "detail": "preserve"}).json()
        self.client.post(f"/api/projects/{self.project_id}/edges", json={"view": "process", "source_id": n1["id"], "target_id": n2["id"], "label": "existing"}).raise_for_status()

        delta = first_delta()
        delta["milestones"] = [{"id": "MS-NEW-001", "phase": "New", "task": "새 작업", "start_week": "1", "end_week": "2"}]
        preview = self.preview(delta).json()
        self.client.post(f"/api/conversation-imports/{preview['import_id']}/draft").raise_for_status()
        self.client.post(f"/api/conversation-imports/{preview['import_id']}/apply").raise_for_status()
        final = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        final_milestone = next(item["content"] for item in final["documents"] if item["doc_type"] == "milestone")
        self.assertIn("MS-OLD-001", final_milestone)
        self.assertIn("MS-NEW-001", final_milestone)
        labels = {item["label"] for item in final["nodes"] if item["view"] == "process"}
        self.assertIn("기존 상세 시작", labels)
        self.assertIn("제품 투입", labels)

    def test_scenarios_g_and_h_api_survives_broken_or_missing_codex(self):
        self.fixture.add_broken_session()
        response = self.client.get(
            "/api/conversation-import/sessions", params={"project_id": self.project_id}
        )
        self.assertEqual(response.status_code, 200, response.text)
        sessions = response.json()["sessions"]
        self.assertTrue(any(item["error"] for item in sessions))
        self.assertTrue(any(item["session_id"] == SESSION_ID and item["message_count"] == 4 for item in sessions))
        with tempfile.TemporaryDirectory() as directory:
            missing = CodexConversationProvider(Path(directory) / "none", executable="")
            with patch("app.main_v016._provider", return_value=missing):
                absent = self.client.get(
                    "/api/conversation-import/sessions", params={"project_id": self.project_id}
                )
        self.assertEqual(absent.status_code, 200)
        self.assertEqual(absent.json()["provider"]["message"], "Codex not detected")
        self.assertEqual(self.client.get("/api/health/ready").status_code, 200)


if __name__ == "__main__":
    unittest.main()
