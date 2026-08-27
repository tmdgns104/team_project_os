import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.conversation import normalize_ai_result


class ConversationalVisualDesignContractTests(unittest.TestCase):
    def test_diagram_contract_filters_invalid_views_and_edges(self):
        raw = json.dumps({
            "reply": "설계 초안을 제안합니다.",
            "design_updates": [
                {
                    "view": "process",
                    "mode": "replace",
                    "reason": "사용자가 순서를 명시함",
                    "nodes": [
                        {"key": "sense", "label": "센서 감지", "kind": "step"},
                        {"key": "judge", "label": "AI 판정", "kind": "step"},
                    ],
                    "edges": [
                        {"source": "sense", "target": "judge", "label": ""},
                        {"source": "missing", "target": "judge", "label": "invalid"},
                    ],
                },
                {"view": "unknown", "nodes": [{"key": "x", "label": "X"}]},
            ],
        }, ensure_ascii=False)
        result = normalize_ai_result(raw)
        self.assertEqual(len(result["design_updates"]), 1)
        design = result["design_updates"][0]
        self.assertEqual(design["view"], "process")
        self.assertEqual(design["mode"], "replace")
        self.assertEqual(len(design["nodes"]), 2)
        self.assertEqual(len(design["edges"]), 1)


class ConversationalVisualDesignApiTests(unittest.TestCase):
    def test_design_is_not_drawn_before_apply_then_materializes_and_project_can_delete(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "v06.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                bridge = client.post("/api/assistant-bridges/register", json={
                    "member_name": "designer", "provider": "codex", "machine_name": "pc"
                }).json()
                token = bridge["token"]
                started = client.post("/api/conversations/start", json={
                    "member_name": "designer", "provider": "codex"
                }).json()
                pid = started["project"]["id"]
                sid = started["session"]["id"]
                project_name = started["project"]["name"]

                client.post(f"/api/conversations/{sid}/messages", json={"message": "센서 감지 후 카메라 촬영, AI 판정, PLC 배출 순서로 진행해"})
                job = client.get(f"/api/assistant-bridge/jobs?token={token}").json()["job"]
                output = json.dumps({
                    "reply": "말씀하신 순서로 프로세스와 구조를 제안합니다.",
                    "design_updates": [
                        {
                            "view": "process", "mode": "replace", "reason": "사용자가 공정 순서를 직접 설명함",
                            "nodes": [
                                {"key": "sensor", "label": "센서 감지", "kind": "step"},
                                {"key": "camera", "label": "카메라 촬영", "kind": "step"},
                                {"key": "ai", "label": "AI 판정", "kind": "step"},
                                {"key": "plc", "label": "PLC 배출", "kind": "step"},
                            ],
                            "edges": [
                                {"source": "sensor", "target": "camera", "label": ""},
                                {"source": "camera", "target": "ai", "label": "Image"},
                                {"source": "ai", "target": "plc", "label": "판정 결과"},
                            ],
                        },
                        {
                            "view": "architecture", "mode": "replace", "reason": "대화에서 장치 역할이 확인됨",
                            "nodes": [
                                {"key": "camera", "label": "Camera", "kind": "device"},
                                {"key": "ai", "label": "AI Inference", "kind": "service"},
                                {"key": "plc", "label": "PLC", "kind": "device"},
                            ],
                            "edges": [
                                {"source": "camera", "target": "ai", "label": ""},
                                {"source": "ai", "target": "plc", "label": ""},
                            ],
                        },
                        {
                            "view": "dataflow", "mode": "replace", "reason": "이미지와 판정 결과 이동이 확인됨",
                            "nodes": [
                                {"key": "camera", "label": "Camera", "kind": "source"},
                                {"key": "ai", "label": "AI Model", "kind": "process"},
                                {"key": "plc", "label": "PLC", "kind": "sink"},
                            ],
                            "edges": [
                                {"source": "camera", "target": "ai", "label": "Image"},
                                {"source": "ai", "target": "plc", "label": "판정 결과"},
                            ],
                        },
                    ],
                }, ensure_ascii=False)
                result = client.post(f"/api/assistant-bridge/results?token={token}", json={
                    "job_id": job["id"], "status": "completed", "output": output
                })
                self.assertEqual(result.status_code, 200)

                before = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(before["nodes"], [])
                self.assertEqual(len(before["conversation"]["pending"]["design_updates"]), 3)

                applied = client.post(f"/api/conversations/{sid}/apply", json={})
                self.assertEqual(applied.status_code, 200)
                after = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "process"]), 4)
                self.assertEqual(len([e for e in after["edges"] if e["view"] == "process"]), 3)
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "architecture"]), 3)
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "dataflow"]), 3)
                self.assertTrue(any(e["label"] == "Image" for e in after["edges"] if e["view"] == "dataflow"))

                wrong = client.delete(f"/api/projects/{pid}", params={"confirm_name": "wrong"})
                self.assertEqual(wrong.status_code, 400)
                deleted = client.delete(f"/api/projects/{pid}", params={"confirm_name": project_name})
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(client.get(f"/api/projects/{pid}/snapshot").status_code, 404)
                self.assertFalse(any(p["id"] == pid for p in client.get("/api/projects").json()))


if __name__ == "__main__":
    unittest.main()
