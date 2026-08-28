from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.runtime import RuntimeConfigurationError, load_runtime_settings
from local_bridge.storage import atomic_write_json


class RuntimeSettingsTests(unittest.TestCase):
    def test_production_rejects_missing_short_and_placeholder_access_keys(self):
        base = {
            "PROJECT_OS_ENV": "production",
            "PROJECT_OS_ALLOWED_HOSTS": "project-os.example.com",
        }
        for access_key in ("", "too-short", "change-this-team-access-key"):
            with self.subTest(access_key=access_key):
                with self.assertRaises(RuntimeConfigurationError):
                    load_runtime_settings({**base, "APP_ACCESS_KEY": access_key})

    def test_production_uses_explicit_safe_defaults(self):
        settings = load_runtime_settings({
            "PROJECT_OS_ENV": "production",
            "PROJECT_OS_ALLOWED_HOSTS": "project-os.example.com,10.0.0.8",
            "APP_ACCESS_KEY": "a-secure-random-access-key-with-32-plus-characters",
        })
        self.assertTrue(settings.production)
        self.assertFalse(settings.interactive_docs_enabled)
        self.assertFalse(settings.seed_demo)
        self.assertEqual(
            settings.allowed_hosts,
            ("project-os.example.com", "10.0.0.8"),
        )

    def test_production_rejects_wildcard_hosts(self):
        with self.assertRaises(RuntimeConfigurationError):
            load_runtime_settings({
                "PROJECT_OS_ENV": "production",
                "PROJECT_OS_ALLOWED_HOSTS": "*",
                "APP_ACCESS_KEY": "a-secure-random-access-key-with-32-plus-characters",
            })


class OperationalApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        os.environ["PROJECT_OS_DB"] = str(
            Path(self.temporary_directory.name) / "operations.db"
        )
        from app import main

        self.main = main
        self.original_db_path = main.DB_PATH
        self.original_seed_demo = main.SEED_DEMO
        main.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
        main.SEED_DEMO = False
        main.init_db()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.main.DB_PATH = self.original_db_path
        self.main.SEED_DEMO = self.original_seed_demo
        self.temporary_directory.cleanup()

    def test_health_endpoints_and_defensive_headers(self):
        live = self.client.get("/api/health/live")
        ready = self.client.get("/api/health/ready")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["database"], "ready")
        self.assertEqual(ready.headers["x-content-type-options"], "nosniff")
        self.assertEqual(ready.headers["x-frame-options"], "DENY")
        self.assertEqual(ready.headers["cache-control"], "no-store")
        self.assertIn("frame-ancestors 'none'", ready.headers["content-security-policy"])

    def test_oversized_declared_request_is_rejected(self):
        response = self.client.post(
            "/api/projects",
            content=b"{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(self.main.SETTINGS.max_request_bytes + 1),
            },
        )
        self.assertEqual(response.status_code, 413)

    def test_database_context_rolls_back_failed_transaction(self):
        with self.assertRaises(RuntimeError):
            with self.main.db() as connection:
                connection.execute(
                    "INSERT INTO projects(name,goal,description,created_at) VALUES(?,?,?,?)",
                    ("rollback", "rollback", "", self.main.now()),
                )
                raise RuntimeError("force rollback")

        with self.main.db() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM projects WHERE name='rollback'"
            ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_bridge_accepts_bearer_header_without_query_secret(self):
        project = self.client.post(
            "/api/projects",
            json={"name": "Bearer project", "goal": "Verify bridge authentication"},
        ).json()
        registration = self.client.post(
            f"/api/projects/{project['id']}/bridges/register",
            json={"member_name": "tester", "provider": "codex"},
        ).json()

        response = self.client.get(
            "/api/bridge/jobs",
            headers={"Authorization": f"Bearer {registration['token']}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["job"])

    def test_websocket_uses_subprotocol_instead_of_query_secret(self):
        access_key = "websocket-access-key"
        encoded_key = base64.urlsafe_b64encode(access_key.encode("utf-8")).decode(
            "ascii"
        ).rstrip("=")
        original_access_key = self.main.ACCESS_KEY
        self.main.ACCESS_KEY = access_key
        try:
            with self.client.websocket_connect(
                "/ws/projects/1",
                subprotocols=["project-os", f"access-key.{encoded_key}"],
            ) as websocket:
                self.assertEqual(websocket.accepted_subprotocol, "project-os")
        finally:
            self.main.ACCESS_KEY = original_access_key


class AtomicStorageTests(unittest.TestCase):
    def test_atomic_json_write_replaces_complete_document(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "session.json"
            atomic_write_json(path, {"version": 1, "text": "첫 저장"})
            atomic_write_json(path, {"version": 2, "text": "완료"})

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"version": 2, "text": "완료"},
            )
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
