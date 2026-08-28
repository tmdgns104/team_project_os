from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.conversation_import import distill_conversation, select_message_chunk
from app.conversation_providers import CodexConversationProvider, ConversationMessage
from app.materializer_v015 import (
    V016_ADDITIONS_BEGIN,
    merge_document_non_regressive,
)
from app.structured_state_v016 import rebase_conflicts
from local_bridge.providers import ProviderResult, build_invocation
from tests.test_conversation_import_v016 import CodexFixture, SESSION_ID


EMPTY_DELTA = {
    "project_updates": {},
    "requirements": [],
    "decisions": [],
    "milestones": [],
    "backlog_items": [],
    "functions": [],
    "screens": [],
    "interfaces": [],
    "tests": [],
    "policies": [],
    "data_items": [],
    "design_updates": [],
    "pending": [],
}


class V016BlockerUnitTests(unittest.TestCase):
    def test_session_metadata_cache_reuses_unchanged_rollout_and_invalidates_on_change(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CodexFixture(Path(directory))
            provider = CodexConversationProvider(fixture.root, executable="")
            provider.clear_metadata_cache()

            with patch.object(
                provider, "_parse_rollout", wraps=provider._parse_rollout
            ) as parser:
                first = provider.list_sessions()
                second = provider.list_sessions()
                self.assertEqual(parser.call_count, 1)
                self.assertEqual(second, first)

                fixture.append("user", "A later message")
                changed = provider.list_sessions()
                self.assertEqual(parser.call_count, 2)
                self.assertEqual(changed[0].message_count, first[0].message_count + 1)

    def test_message_chunk_is_contiguous_and_bounded(self):
        messages = [
            ConversationMessage(cursor, "user", "x" * 10, "")
            for cursor in range(1, 7)
        ]

        selected, total = select_message_chunk(
            messages,
            after_cursor=1,
            max_messages=3,
            max_characters=1_000,
        )
        self.assertEqual([item.cursor for item in selected], [2, 3, 4])
        self.assertEqual(total, 5)

        character_limited, total = select_message_chunk(
            messages,
            after_cursor=1,
            max_messages=10,
            max_characters=20,
        )
        self.assertEqual([item.cursor for item in character_limited], [2, 3])
        self.assertEqual(total, 5)

    def test_distiller_uses_disposable_tool_disabled_environment_and_schema(self):
        captured: dict[str, object] = {}

        def fake_provider(_provider: str, _prompt: str, **kwargs):
            isolation_root = Path(kwargs["cwd"])
            schema_path = Path(kwargs["output_schema"])
            environment = dict(kwargs["environment"])
            self.assertTrue(isolation_root.is_dir())
            self.assertEqual(schema_path.parent, isolation_root)
            self.assertTrue(schema_path.is_file())
            self.assertFalse((isolation_root / ".git").exists())
            self.assertNotIn("APP_ACCESS_KEY", environment)
            self.assertNotIn("PROJECT_OS_DB", environment)
            captured.update(
                cwd=isolation_root,
                schema=json.loads(schema_path.read_text(encoding="utf-8")),
                environment=environment,
            )
            return ProviderResult(
                provider="codex",
                returncode=0,
                stdout=json.dumps(EMPTY_DELTA),
                stderr="",
                command_display="codex exec",
            )

        with patch.dict(
            os.environ,
            {
                "APP_ACCESS_KEY": "must-not-reach-distiller",
                "PROJECT_OS_DB": "must-not-reach-distiller.db",
            },
            clear=False,
        ), patch("app.conversation_import.run_provider", side_effect=fake_provider):
            result = distill_conversation(
                messages=[{"cursor": 1, "role": "user", "content": "Project fact"}],
                current_state={},
                project_name="Test project",
                cwd=Path(__file__).resolve().parents[1],
            )

        self.assertEqual(result["requirements"], [])
        self.assertFalse(Path(captured["cwd"]).exists())
        self.assertFalse(captured["schema"]["additionalProperties"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema_path = root / "schema.json"
            schema_path.write_text("{}", encoding="utf-8")
            invocation = build_invocation(
                "codex",
                "untrusted transcript",
                cwd=root,
                purpose="conversation-import",
                output_schema=schema_path,
            )
            command = invocation.command
            self.assertIn("--strict-config", command)
            self.assertIn("sandbox_workspace_write.network_access=false", command)
            self.assertIn(str(schema_path), command)
            disabled = {
                command[index + 1]
                for index, value in enumerate(command[:-1])
                if value == "--disable"
            }
            self.assertTrue(
                {
                    "shell_tool",
                    "unified_exec",
                    "code_mode_host",
                    "apps",
                    "plugins",
                    "browser_use",
                    "view_image",
                    "image_generation",
                    "multi_agent",
                    "in_app_local_automation",
                    "hooks",
                    "skill_mcp_dependency_install",
                    "tool_call_mcp_elicitation",
                    "auth_elicitation",
                    "remote_plugin",
                    "goals",
                }.issubset(disabled)
            )

    def test_rebase_conflicts_use_requirement_ref_and_true_three_way_semantics(self):
        base = {
            "requirements": [
                {"ref": "REQ-HUMAN-001", "title": "Owned", "detail": "Base"},
                {"ref": "REQ-HUMAN-002", "title": "Other", "detail": "Base"},
            ]
        }
        unrelated_current = {
            "requirements": [
                {"ref": "REQ-HUMAN-001", "title": "Owned", "detail": "Base"},
                {"ref": "REQ-HUMAN-002", "title": "Other", "detail": "Human edit"},
            ]
        }
        delta = {
            "requirements": [
                {"ref": "REQ-HUMAN-001", "title": "Owned", "detail": "Imported edit"}
            ]
        }
        self.assertEqual(rebase_conflicts(base, unrelated_current, delta), [])

        target_current = {
            "requirements": [
                {"ref": "REQ-HUMAN-001", "title": "Owned", "detail": "Human edit"},
                {"ref": "REQ-HUMAN-002", "title": "Other", "detail": "Base"},
            ]
        }
        self.assertEqual(
            rebase_conflicts(base, target_current, delta),
            ["requirements.REQ-HUMAN-001"],
        )

        same_result = {
            "requirements": [
                {"ref": "REQ-HUMAN-001", "title": "Owned", "detail": "Imported edit"},
                {"ref": "REQ-HUMAN-002", "title": "Other", "detail": "Base"},
            ]
        }
        self.assertEqual(rebase_conflicts(base, same_result, delta), [])

        concurrent_creation = {
            "requirements": [
                {"ref": "REQ-HUMAN-003", "title": "Human", "detail": "Human value"}
            ]
        }
        incoming_creation = {
            "requirements": [
                {"ref": "REQ-HUMAN-003", "title": "Imported", "detail": "Model value"}
            ]
        }
        self.assertEqual(
            rebase_conflicts({}, concurrent_creation, incoming_creation),
            ["requirements.REQ-HUMAN-003"],
        )

    def test_non_regressive_document_merge_rebuilds_one_bounded_addition_block(self):
        old = (
            "# Human Requirements\n\n"
            "| Ref | Requirement | Detail |\n"
            "|---|---|---|\n"
            "| REQ-HUMAN-001 | Human-owned | Preserve this detailed requirement |\n"
            + ("Human rationale and acceptance evidence.\n" * 60)
        )
        generated = (
            "# Requirements\n\n"
            "| Ref | Requirement | Detail |\n"
            "|---|---|---|\n"
            "| REQ-IMPORT-001 | Imported | New conversation requirement |\n"
        )

        once = merge_document_non_regressive(old, generated)
        twice = merge_document_non_regressive(once, generated)

        self.assertIn("REQ-HUMAN-001", once)
        self.assertIn("REQ-IMPORT-001", once)
        self.assertEqual(once.count(V016_ADDITIONS_BEGIN), 1)
        self.assertEqual(twice, once)

        later_generated = (
            "# Requirements\n\n"
            "| Ref | Requirement | Detail |\n"
            "|---|---|---|\n"
            "| REQ-IMPORT-002 | Later import | Another conversation requirement |\n"
        )
        later = merge_document_non_regressive(once, later_generated)
        repeated_later = merge_document_non_regressive(later, later_generated)

        self.assertIn("REQ-HUMAN-001", later)
        self.assertIn("REQ-IMPORT-001", later)
        self.assertIn("REQ-IMPORT-002", later)
        self.assertEqual(later.count(V016_ADDITIONS_BEGIN), 1)
        self.assertEqual(repeated_later, later)


class V016BlockerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_environment = {
            key: os.environ.get(key)
            for key in (
                "PROJECT_OS_DB",
                "PROJECT_OS_SEED_DEMO",
                "PROJECT_OS_CODEX_HOME",
            )
        }

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.original_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
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
                "name": "V0.16 blocker regression",
                "goal": "Preserve human edits while importing conversations",
                "project_type": "software",
                "schedule": "8 weeks",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.project_id = response.json()["id"]

    def tearDown(self):
        self.client.close()
        CodexConversationProvider.clear_metadata_cache()
        os.environ.pop("PROJECT_OS_CODEX_HOME", None)
        self.tmp.cleanup()

    def _preview(self, delta: dict, **overrides):
        payload = {
            "project_id": self.project_id,
            "provider": "codex",
            "session_id": SESSION_ID,
            **overrides,
        }
        with patch("app.main_v016.distill_conversation", return_value=delta):
            return self.client.post("/api/conversation-import/preview", json=payload)

    def test_api_exposes_and_processes_only_the_next_bounded_chunk(self):
        for index in range(151):
            role = "user" if index % 2 == 0 else "assistant"
            self.fixture.append(role, f"Additional message {index}")

        selected = self.client.get(
            f"/api/conversation-import/sessions/{SESSION_ID}",
            params={"project_id": self.project_id},
        )
        self.assertEqual(selected.status_code, 200, selected.text)
        session = selected.json()
        self.assertEqual(session["total_unimported"], 155)
        self.assertEqual(len(session["analysis_messages"]), 150)
        self.assertTrue(session["has_more"])
        self.assertEqual(session["remaining_after_chunk"], 5)

        preview = self._preview(
            EMPTY_DELTA,
            from_cursor=session["imported_cursor"],
            to_cursor=session["next_to_cursor"],
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        payload = preview.json()
        self.assertEqual(len(payload["messages"]), 150)
        self.assertEqual(payload["remaining_after_chunk"], 5)
        self.assertTrue(payload["has_more"])

    def test_api_rejects_a_cursor_that_skips_unimported_messages(self):
        with patch("app.main_v016.distill_conversation") as distiller:
            response = self.client.post(
                "/api/conversation-import/preview",
                json={
                    "project_id": self.project_id,
                    "provider": "codex",
                    "session_id": SESSION_ID,
                    "from_cursor": 1,
                },
            )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("cannot be skipped", response.text)
        distiller.assert_not_called()

    def test_structured_state_reconciles_current_database_and_canonical_documents(self):
        requirement = self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-HUMAN-001 Human-owned requirement",
                "detail": "Original detail",
                "status": "defined",
            },
        ).json()
        with self.main.core.db() as conn:
            initial = self.main.load_structured_state(conn, self.project_id)
        self.assertEqual(
            next(item for item in initial["requirements"] if item["ref"] == "REQ-HUMAN-001")["detail"],
            "Original detail",
        )

        self.client.patch(
            f"/api/requirements/{requirement['id']}",
            json={"detail": "Latest human detail"},
        ).raise_for_status()
        snapshot = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        backlog = next(
            item for item in snapshot["documents"] if item["doc_type"] == "backlog"
        )
        self.client.patch(
            f"/api/documents/{backlog['id']}",
            json={
                "content": (
                    "# Human Backlog\n\n"
                    "| ID | Title |\n|---|---|\n"
                    "| BL-HUMAN-001 | Human-authored backlog item |\n"
                ),
                "status": "review",
                "updated_by": "Human",
            },
        ).raise_for_status()

        with self.main.core.db() as conn:
            reconciled = self.main.load_structured_state(conn, self.project_id)
        requirement_state = next(
            item
            for item in reconciled["requirements"]
            if item["ref"] == "REQ-HUMAN-001"
        )
        self.assertEqual(requirement_state["detail"], "Latest human detail")
        self.assertIn(
            "BL-HUMAN-001",
            {item["id"] for item in reconciled["backlog_items"]},
        )

    def test_reconciliation_prefers_official_rows_and_documents_over_stale_cache(self):
        self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-HUMAN-001 Human-owned requirement",
                "detail": "Current database detail",
                "status": "defined",
            },
        ).raise_for_status()
        self.client.post(
            f"/api/projects/{self.project_id}/decisions",
            json={
                "title": "Human database decision",
                "body": "Current database body",
                "author": "Human",
                "status": "accepted",
            },
        ).raise_for_status()
        self.client.post(
            f"/api/projects/{self.project_id}/nodes",
            json={
                "view": "architecture",
                "label": "Human database node",
                "kind": "service",
                "detail": "Current database node detail",
            },
        ).raise_for_status()

        snapshot = self.client.get(f"/api/projects/{self.project_id}/snapshot").json()
        backlog = next(
            item for item in snapshot["documents"] if item["doc_type"] == "backlog"
        )
        self.client.patch(
            f"/api/documents/{backlog['id']}",
            json={
                "content": "# Human Backlog\n\nBL-DOC-001 is the current canonical item.\n",
                "status": "review",
                "updated_by": "Human",
            },
        ).raise_for_status()

        stale = {
            **EMPTY_DELTA,
            "project_updates": {"goal": "Stale cached goal"},
            "requirements": [
                {
                    "ref": "REQ-HUMAN-001",
                    "title": "Human-owned requirement",
                    "detail": "Stale cached detail",
                }
            ],
            "decisions": [
                {
                    "ref": "DEC-HUMAN-001",
                    "title": "Human database decision",
                    "body": "Stale cached body",
                    "status": "pending",
                }
            ],
            "backlog_items": [
                {"id": "BL-STALE-001", "title": "Removed from canonical document"}
            ],
            "design_updates": [
                {
                    "view": "architecture",
                    "mode": "merge",
                    "nodes": [
                        {
                            "key": "stable-human-node",
                            "label": "Human database node",
                            "kind": "service",
                            "detail": "Stale cached node detail",
                        }
                    ],
                    "edges": [],
                }
            ],
        }
        with self.main.core.db() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO project_structured_states(project_id,state_json,updated_at)
                VALUES(?,?,?)
                """,
                (self.project_id, json.dumps(stale), self.main.core.now()),
            )
            reconciled = self.main.load_structured_state(conn, self.project_id)
            first_revision = self.main.source_of_truth_revision(
                conn, self.project_id, reconciled
            )

            conn.execute(
                "UPDATE project_structured_states SET state_json=? WHERE project_id=?",
                (json.dumps(stale), self.project_id),
            )
            reconciled_again = self.main.load_structured_state(conn, self.project_id)
            second_revision = self.main.source_of_truth_revision(
                conn, self.project_id, reconciled_again
            )

        requirement = next(
            item
            for item in reconciled["requirements"]
            if item["ref"] == "REQ-HUMAN-001"
        )
        decision = next(
            item
            for item in reconciled["decisions"]
            if item["title"] == "Human database decision"
        )
        design_node = reconciled["design_updates"][0]["nodes"][0]
        self.assertEqual(
            reconciled["project_updates"]["goal"],
            "Preserve human edits while importing conversations",
        )
        self.assertEqual(requirement["detail"], "Current database detail")
        self.assertEqual(decision["ref"], "DEC-HUMAN-001")
        self.assertEqual(decision["body"], "Current database body")
        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(design_node["key"], "stable-human-node")
        self.assertEqual(design_node["detail"], "Current database node detail")
        self.assertEqual(
            {item["id"] for item in reconciled["backlog_items"]},
            {"BL-DOC-001"},
        )
        self.assertEqual(reconciled_again, reconciled)
        self.assertEqual(second_revision, first_revision)

    def test_v015_bootstrap_recovers_all_catalog_stable_ids_without_a_cache(self):
        stable_ids_by_document = {
            "milestone": ("milestones", "MS-BOOT-001"),
            "backlog": ("backlog_items", "BL-BOOT-001"),
            "function_definition": ("functions", "FUNC-BOOT-001"),
            "ia": ("screens", "SCR-BOOT-001"),
            "api_design": ("interfaces", "API-BOOT-001"),
            "qa": ("tests", "TC-BOOT-001"),
            "service_policy": ("policies", "POL-BOOT-001"),
            "data_flow": ("data_items", "DATA-BOOT-001"),
        }
        with self.main.core.db() as conn:
            conn.execute(
                "DELETE FROM project_structured_states WHERE project_id=?",
                (self.project_id,),
            )
            for doc_type, (_category, identifier) in stable_ids_by_document.items():
                conn.execute(
                    "UPDATE documents SET content=? WHERE project_id=? AND doc_type=?",
                    (
                        f"# Human {doc_type}\n\n{identifier} remains canonical.\n",
                        self.project_id,
                        doc_type,
                    ),
                )
            bootstrapped = self.main.load_structured_state(conn, self.project_id)

        for category, identifier in stable_ids_by_document.values():
            self.assertIn(identifier, {item["id"] for item in bootstrapped[category]})

    def test_preview_detects_a_same_identity_edit_during_distillation(self):
        requirement = self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-RACE-001 Concurrent requirement",
                "detail": "Base detail",
                "status": "defined",
            },
        ).json()
        delta = {
            "requirements": [
                {
                    "ref": "REQ-RACE-001",
                    "title": "Concurrent requirement",
                    "detail": "Imported detail",
                }
            ]
        }

        def edit_during_distillation(**_kwargs):
            with self.main.core.db() as conn:
                conn.execute(
                    "UPDATE requirements SET detail=? WHERE id=?",
                    ("Human edit during distillation", requirement["id"]),
                )
            return delta

        with patch(
            "app.main_v016.distill_conversation",
            side_effect=edit_during_distillation,
        ):
            response = self.client.post(
                "/api/conversation-import/preview",
                json={
                    "project_id": self.project_id,
                    "provider": "codex",
                    "session_id": SESSION_ID,
                },
            )

        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(
            response.json()["detail"]["conflicts"],
            ["requirements.REQ-RACE-001"],
        )
        with self.main.core.db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS count FROM conversation_imports"
            ).fetchone()["count"]
            self.assertEqual(count, 0)

    def test_non_conflicting_edits_rebase_through_draft_and_apply(self):
        self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-REBASE-001 Imported target",
                "detail": "Base target detail",
                "status": "defined",
            },
        ).raise_for_status()
        unrelated = self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-HUMAN-002 Human-owned requirement",
                "detail": "Base human detail",
                "status": "defined",
            },
        ).json()
        preview = self._preview(
            {
                "requirements": [
                    {
                        "ref": "REQ-REBASE-001",
                        "title": "Imported target",
                        "detail": "Imported target detail",
                    }
                ]
            }
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        import_id = preview.json()["import_id"]

        self.client.patch(
            f"/api/requirements/{unrelated['id']}",
            json={"detail": "Human edit before draft"},
        ).raise_for_status()
        self.client.post(
            f"/api/conversation-imports/{import_id}/draft"
        ).raise_for_status()

        with self.main.core.db() as conn:
            current_unrelated = conn.execute(
                "SELECT id FROM requirements WHERE project_id=? AND title LIKE ?",
                (self.project_id, "REQ-HUMAN-002%"),
            ).fetchone()
        self.client.patch(
            f"/api/requirements/{current_unrelated['id']}",
            json={"detail": "Human edit before apply"},
        ).raise_for_status()
        applied = self.client.post(f"/api/conversation-imports/{import_id}/apply")
        self.assertEqual(applied.status_code, 200, applied.text)

        with self.main.core.db() as conn:
            rows = {
                row["title"].split(" ", 1)[0]: row["detail"]
                for row in conn.execute(
                    "SELECT title,detail FROM requirements WHERE project_id=?",
                    (self.project_id,),
                )
            }
        self.assertEqual(rows["REQ-REBASE-001"], "Imported target detail")
        self.assertEqual(rows["REQ-HUMAN-002"], "Human edit before apply")

    def test_cursor_progresses_across_multiple_bounded_chunks(self):
        for index in range(151):
            role = "user" if index % 2 == 0 else "assistant"
            self.fixture.append(role, f"Chunked message {index}")

        selected = self.client.get(
            f"/api/conversation-import/sessions/{SESSION_ID}",
            params={"project_id": self.project_id},
        ).json()
        first_preview = self._preview(
            EMPTY_DELTA,
            from_cursor=selected["imported_cursor"],
            to_cursor=selected["next_to_cursor"],
        )
        self.assertEqual(first_preview.status_code, 200, first_preview.text)
        first_id = first_preview.json()["import_id"]
        self.client.post(f"/api/conversation-imports/{first_id}/draft").raise_for_status()

        drafted_session = self.client.get(
            f"/api/conversation-import/sessions/{SESSION_ID}",
            params={"project_id": self.project_id},
        ).json()
        self.assertEqual(drafted_session["imported_cursor"], selected["next_to_cursor"])
        self.assertEqual(len(drafted_session["analysis_messages"]), 5)

        self.client.post(f"/api/conversation-imports/{first_id}/apply").raise_for_status()
        second_preview = self._preview(
            EMPTY_DELTA,
            from_cursor=drafted_session["imported_cursor"],
            to_cursor=drafted_session["next_to_cursor"],
        )
        self.assertEqual(second_preview.status_code, 200, second_preview.text)
        self.assertEqual(len(second_preview.json()["messages"]), 5)
        self.assertFalse(second_preview.json()["has_more"])

    def test_conflicting_stable_ref_is_rejected_before_draft_and_apply(self):
        requirement = self.client.post(
            f"/api/projects/{self.project_id}/requirements",
            json={
                "title": "REQ-HUMAN-001 Human-owned requirement",
                "detail": "Base detail",
                "status": "defined",
            },
        ).json()
        delta = {
            "requirements": [
                {
                    "ref": "REQ-HUMAN-001",
                    "title": "Human-owned requirement",
                    "detail": "Imported detail",
                }
            ]
        }
        preview = self._preview(delta)
        self.assertEqual(preview.status_code, 200, preview.text)
        import_id = preview.json()["import_id"]

        self.client.patch(
            f"/api/requirements/{requirement['id']}",
            json={"detail": "Concurrent edit before draft"},
        ).raise_for_status()
        rejected_draft = self.client.post(
            f"/api/conversation-imports/{import_id}/draft"
        )
        self.assertEqual(rejected_draft.status_code, 409, rejected_draft.text)
        self.assertEqual(
            rejected_draft.json()["detail"]["conflicts"],
            ["requirements.REQ-HUMAN-001"],
        )

        self.client.patch(
            f"/api/requirements/{requirement['id']}",
            json={"detail": "Base detail"},
        ).raise_for_status()
        drafted = self.client.post(f"/api/conversation-imports/{import_id}/draft")
        self.assertEqual(drafted.status_code, 200, drafted.text)

        self.client.patch(
            f"/api/requirements/{requirement['id']}",
            json={"detail": "Concurrent edit before apply"},
        ).raise_for_status()
        rejected_apply = self.client.post(
            f"/api/conversation-imports/{import_id}/apply"
        )
        self.assertEqual(rejected_apply.status_code, 409, rejected_apply.text)
        self.assertEqual(
            rejected_apply.json()["detail"]["conflicts"],
            ["requirements.REQ-HUMAN-001"],
        )
        with self.main.core.db() as conn:
            stored_detail = conn.execute(
                "SELECT detail FROM requirements WHERE id=?", (requirement["id"],)
            ).fetchone()["detail"]
        self.assertEqual(stored_detail, "Concurrent edit before apply")


if __name__ == "__main__":
    unittest.main()
