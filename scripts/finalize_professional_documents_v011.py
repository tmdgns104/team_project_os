from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / 'app/main.py'
s = p.read_text(encoding='utf-8')

s = s.replace('app = FastAPI(title="Team Project OS", version="0.10.0")', 'app = FastAPI(title="Team Project OS", version="0.11.0")', 1)
s = s.replace('return {"status": "ok", "version": "0.10.0"}', 'return {"status": "ok", "version": "0.11.0"}', 1)

old = '''def ensure_project_documents(conn: sqlite3.Connection, project_id: int) -> None:\n    for doc_type, title, content in DOCUMENT_TEMPLATES:\n        conn.execute(\n            "INSERT OR IGNORE INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",\n            (project_id, doc_type, title, content, "draft", "System", now(), now()),\n        )\n'''
new = '''def ensure_project_documents(conn: sqlite3.Connection, project_id: int) -> None:\n    """Ensure all shared deliverables exist and safely refresh untouched System templates.\n\n    A document already touched by Live Design, Project Setup, AI Conversation, or a human\n    is never overwritten here. This lets old V0.10 databases receive the professional\n    V0.11 baseline for still-untouched documents without losing project work.\n    """\n    for doc_type, title, content in DOCUMENT_TEMPLATES:\n        row = conn.execute(\n            "SELECT id,status,updated_by,content FROM documents WHERE project_id=? AND doc_type=?",\n            (project_id, doc_type),\n        ).fetchone()\n        if row is None:\n            conn.execute(\n                "INSERT INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",\n                (project_id, doc_type, title, content, "draft", "System", now(), now()),\n            )\n            continue\n        if row["status"] == "draft" and row["updated_by"] == "System" and row["content"] != content:\n            conn.execute(\n                "UPDATE documents SET title=?,content=?,updated_at=? WHERE id=?",\n                (title, content, now(), row["id"]),\n            )\n'''
if old not in s:
    raise RuntimeError('ensure_project_documents marker not found')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

pt = ROOT / 'tests/test_professional_doc_migration.py'
pt.write_text(r'''import sqlite3
import unittest

from app.main import DOCUMENT_TEMPLATES, app, ensure_project_documents


class ProfessionalDocumentMigrationTests(unittest.TestCase):
    def test_version_is_v011(self):
        self.assertEqual(app.version, "0.11.0")

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
        ensure_project_documents(conn, 1)
        policy = conn.execute("SELECT * FROM documents WHERE project_id=1 AND doc_type='service_policy'").fetchone()
        screen = conn.execute("SELECT * FROM documents WHERE project_id=1 AND doc_type='screen_design'").fetchone()
        self.assertNotEqual(policy['content'], 'OLD SYSTEM')
        self.assertIn('사용자 / 역할 / 권한 정책', policy['content'])
        self.assertEqual(screen['content'], 'KEEP LIVE WORK')
        self.assertEqual(conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=1").fetchone()['c'], len(DOCUMENT_TEMPLATES))
        conn.close()


if __name__ == '__main__':
    unittest.main()
''', encoding='utf-8')

print('V0.11 professional document migration finalized')
