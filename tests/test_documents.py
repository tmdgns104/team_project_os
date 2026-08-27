import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class DocumentWorkspaceTests(unittest.TestCase):
    def test_new_project_gets_13_shared_documents_and_revision(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "docs.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                res = client.post("/api/projects", json={
                    "name": "New Project",
                    "goal": "Start from planning",
                    "description": "shared docs",
                })
                self.assertEqual(res.status_code, 200)
                pid = res.json()["id"]
                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                doc = snap["documents"][0]
                save = client.patch(f"/api/documents/{doc['id']}", json={
                    "content": "# updated",
                    "status": "review",
                    "updated_by": "tester",
                })
                self.assertEqual(save.status_code, 200)
                revisions = client.get(f"/api/documents/{doc['id']}/revisions").json()
                self.assertEqual(len(revisions), 1)
                comment = client.post(f"/api/documents/{doc['id']}/comments", json={
                    "author": "reviewer",
                    "body": "check this",
                })
                self.assertEqual(comment.status_code, 200)


if __name__ == "__main__":
    unittest.main()
