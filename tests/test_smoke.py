import os
import tempfile
import unittest


class SmokeTests(unittest.TestCase):
    def test_import_and_snapshot_seed(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "test.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.init_db()
            with main.db() as conn:
                project = conn.execute("SELECT * FROM projects ORDER BY id LIMIT 1").fetchone()
                self.assertIsNotNone(project)
                tasks = conn.execute("SELECT COUNT(*) c FROM tasks WHERE project_id=?", (project["id"],)).fetchone()["c"]
                self.assertGreater(tasks, 0)


if __name__ == "__main__":
    unittest.main()
