import sqlite3
import unittest

from app import main as base
import app.main_v014 as current


class ProfessionalDocumentMigrationTests(unittest.TestCase):
    def test_version_is_current(self):
        self.assertEqual(current.app.version, "0.14.0")

    def test_only_untouched_system_templates_are_refreshed(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, doc_type)
            )
        """)
        conn.execute("INSERT INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(1,'service_policy','서비스 및 운영 정책서','OLD SYSTEM','draft','System','x','x')")
        conn.execute("INSERT INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(1,'screen_design','화면 설계서','KEEP LIVE WORK','draft','Live Design / user','x','x')")
        base.ensure_project_documents(conn, 1)
        policy = conn.execute("SELECT * FROM documents WHERE project_id=1 AND doc_type='service_policy'").fetchone()
        screen = conn.execute("SELECT * FROM documents WHERE project_id=1 AND doc_type='screen_design'").fetchone()
        self.assertNotEqual(policy['content'], 'OLD SYSTEM')
        self.assertIn('Role / Access Policy', policy['content'])
        self.assertEqual(screen['content'], 'KEEP LIVE WORK')
        self.assertEqual(conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=1").fetchone()['c'], len(base.DOCUMENT_TEMPLATES))
        conn.close()


if __name__ == '__main__':
    unittest.main()
