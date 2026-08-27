import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.conversation import (
    build_interviewer_prompt,
    combine_proposals,
    extract_json_object,
    merge_project_brief,
    normalize_ai_result,
)


class ConversationCoreTests(unittest.TestCase):
    def test_extracts_json_from_cli_wrapped_output(self):
        raw = 'model output\n```json\n{"reply":"좋아요","project_updates":{"goal":"목표"}}\n```\nusage: 10'
        data = extract_json_object(raw)
        self.assertEqual(data["reply"], "좋아요")

    def test_normalizes_and_blocks_unknown_fields(self):
        raw = json.dumps({
            "reply": "확인했습니다.",
            "project_updates": {
                "goal": "검사 자동화",
                "project_type": "manufacturing_automation",
                "secret_field": "do not keep",
            },
            "requirements": [{"ref": "REQ-001", "title": "판정 시간", "detail": "500ms 이하"}],
            "document_updates": [{"doc_type": "qa", "content": "# QA"}, {"doc_type": "unknown", "content": "x"}],
        }, ensure_ascii=False)
        result = normalize_ai_result(raw)
        self.assertNotIn("secret_field", result["project_updates"])
        self.assertEqual(result["project_updates"]["project_type"], "manufacturing_automation")
        self.assertEqual(len(result["document_updates"]), 1)

    def test_combines_unapplied_proposals_without_duplicate_refs(self):
        old = {
            "project_updates": {"problem": "old"},
            "requirements": [{"ref": "REQ-001", "title": "old", "detail": "a"}],
            "decisions": [], "document_updates": [], "pending": ["PLC 통신 미정"],
        }
        cur = {
            "reply": "next",
            "project_updates": {"goal": "new goal"},
            "requirements": [{"ref": "REQ-001", "title": "new", "detail": "b"}],
            "decisions": [], "document_updates": [], "pending": ["PLC 통신 미정", "예산 미정"],
        }
        merged = combine_proposals(old, cur)
        self.assertEqual(merged["project_updates"]["problem"], "old")
        self.assertEqual(merged["project_updates"]["goal"], "new goal")
        self.assertEqual(len(merged["requirements"]), 1)
        self.assertEqual(merged["requirements"][0]["title"], "new")
        self.assertEqual(len(merged["pending"]), 2)

    def test_prompt_is_provider_neutral_and_forbids_guessing(self):
        prompt = build_interviewer_prompt(
            project_id=1,
            brief={"name": "대화 프로젝트", "goal": "", "project_type": "generic"},
            messages=[{"role": "user", "content": "공장 개선 프로젝트를 하고 싶어"}],
            documents=[],
        )
        self.assertIn("ANY kind of project", prompt)
        self.assertIn("Never invent", prompt)
        self.assertIn("Return exactly ONE JSON object", prompt)
        self.assertIn("공장 개선 프로젝트", prompt)

    def test_merge_brief_preserves_unknowns(self):
        merged = merge_project_brief({"name": "A", "goal": "G", "project_type": "generic"}, {"problem": "P"})
        self.assertEqual(merged["goal"], "G")
        self.assertEqual(merged["problem"], "P")


class ConversationApiTests(unittest.TestCase):
    def test_conversation_can_start_from_zero_and_apply_ai_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "conversation.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                bridge = client.post("/api/assistant-bridges/register", json={
                    "member_name": "tester",
                    "provider": "codex",
                    "machine_name": "test-pc",
                })
                self.assertEqual(bridge.status_code, 200)
                token = bridge.json()["token"]

                started = client.post("/api/conversations/start", json={
                    "member_name": "tester",
                    "provider": "codex",
                })
                self.assertEqual(started.status_code, 200)
                body = started.json()
                pid = body["project"]["id"]
                sid = body["session"]["id"]

                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                self.assertEqual(snap["conversation"]["session"]["id"], sid)

                sent = client.post(f"/api/conversations/{sid}/messages", json={
                    "message": "생산라인에서 육안검사 편차를 줄이는 비전 검사 프로젝트를 하고 싶어",
                })
                self.assertEqual(sent.status_code, 200)

                job = client.get(f"/api/assistant-bridge/jobs?token={token}").json()
                self.assertIsNotNone(job["job"])
                self.assertIn("Project Interviewer", job["prompt"])

                ai_output = json.dumps({
                    "reply": "비전검사 프로젝트로 이해했습니다. 다음으로 성공 기준을 정해볼게요.",
                    "project_updates": {
                        "name": "생산라인 비전검사 자동화",
                        "goal": "제품 불량을 자동 판정해 작업자 편차를 줄인다.",
                        "project_type": "manufacturing_automation",
                        "problem": "육안검사 판정 편차가 크다.",
                        "users": "생산 작업자와 품질팀",
                        "deliverables": "검사 시스템과 운영 가이드",
                        "success_criteria": "불량 검출 Recall 95% 이상",
                        "scope": "포함=검사/기록, 제외=ERP 교체",
                        "constraints": "기존 생산라인을 유지한다.",
                    },
                    "requirements": [{"ref": "REQ-001", "title": "불량 자동 판정", "detail": "불량을 자동 판정해야 한다."}],
                    "decisions": [{"title": "카메라 방식 검토", "body": "카메라 종류는 미정", "status": "proposed"}],
                    "document_updates": [{"doc_type": "qa", "content": "# QA 문서\n\n- Recall 95% 이상", "reason": "사용자 KPI 반영"}],
                    "pending": ["판정 시간 기준 미정"],
                }, ensure_ascii=False)
                result = client.post(f"/api/assistant-bridge/results?token={token}", json={
                    "job_id": job["job"]["id"],
                    "status": "completed",
                    "output": ai_output,
                })
                self.assertEqual(result.status_code, 200)

                before_apply = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(before_apply["project"]["name"], body["project"]["name"])
                self.assertEqual(before_apply["conversation"]["pending"]["project_updates"]["name"], "생산라인 비전검사 자동화")

                applied = client.post(f"/api/conversations/{sid}/apply", json={})
                self.assertEqual(applied.status_code, 200)
                after = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(after["project"]["name"], "생산라인 비전검사 자동화")
                self.assertEqual(after["project_brief"]["project_type"], "manufacturing_automation")
                self.assertTrue(any("REQ-001" in r["title"] for r in after["requirements"]))
                qa = next(d for d in after["documents"] if d["doc_type"] == "qa")
                self.assertIn("Recall 95%", qa["content"])
                self.assertFalse(after["conversation"]["pending"])


if __name__ == "__main__":
    unittest.main()
