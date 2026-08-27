import io
import os
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient


class TraceabilityExportTests(unittest.TestCase):
    def test_project_brief_traceability_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "trace.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                p = client.post("/api/projects", json={
                    "name": "From Zero", "goal": "Build together", "description": "team project",
                    "problem": "Problem A", "users": "Operators", "success_criteria": "KPI 95%",
                    "scope": "Web + API", "constraints": "Internal network",
                }).json()
                pid = p["id"]
                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                proposal = next(d for d in snap["documents"] if d["doc_type"] == "proposal")
                self.assertIn("Problem A", proposal["content"])
                client.post(f"/api/projects/{pid}/requirements", json={"title":"REQ-001 Login","detail":"login"})
                task = client.post(f"/api/projects/{pid}/tasks", json={"title":"Implement login","requirement_ref":"REQ-001"}).json()
                link = client.post(f"/api/projects/{pid}/trace-links", json={"source_type":"requirement","source_ref":"REQ-001","target_type":"api","target_ref":"API-001","relation":"realized_by"})
                self.assertEqual(link.status_code, 200)
                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["trace_links"]), 1)
                self.assertTrue(any(x["target_ref"] == f"TASK-{task['id']}" for x in snap["derived_trace_links"]))
                exported = client.get(f"/api/projects/{pid}/export/documents.zip")
                self.assertEqual(exported.status_code, 200)
                self.assertEqual(exported.headers["content-type"], "application/zip")
                with zipfile.ZipFile(io.BytesIO(exported.content)) as zf:
                    names = zf.namelist()
                    self.assertIn("TRACEABILITY.md", names)
                    self.assertIn("project_snapshot.json", names)
                    self.assertEqual(len([n for n in names if n.startswith("documents/")]), 13)
                    self.assertIn("REQ-001", zf.read("TRACEABILITY.md").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
