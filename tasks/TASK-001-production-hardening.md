# TASK-001 · Production hardening baseline

## Problem

Team Project OS works as a local/demo application, but its current defaults can expose
an unauthenticated server, its health endpoint does not prove database readiness, SQLite
connections have no explicit contention policy, and CLI session persistence is neither
atomic nor isolated in tests.

## Requirements

- Preserve the existing FastAPI routes, SQLite data model, document workflow, and V0.14
  entry point.
- Keep local development easy and bind local launchers to loopback by default.
- Fail fast when production mode is configured with a missing, placeholder, or short
  access key.
- Add production host validation, request-size protection, security response headers,
  database readiness reporting, SQLite busy timeout/WAL configuration, and explicit
  rollback on failure.
- Make CLI session paths configurable, unique, private where supported, and atomically
  written.
- Run the container as a non-root user and provide a health check.
- Keep unit tests hermetic: they must not contact a developer's running local server or
  write to the developer's home directory.

## Architecture impact

No architecture change. The application remains a single FastAPI process with SQLite,
the same REST/WebSocket contracts, and the same browser/CLI clients. Runtime settings
are extracted into one small module so startup policy can be tested without importing
the application or touching the database.

## Out of scope / Human Gate

- Multi-user login, SSO/OIDC, RBAC, tenant isolation, and per-project authorization.
- Replacing SQLite with a server database.
- TLS termination and reverse-proxy/WAF configuration.
- Removing legacy bridge query-token support; clients move to bearer headers while the
  old transport remains temporarily compatible.

## Acceptance criteria

1. Local launchers default to `127.0.0.1`.
2. Production settings reject weak access keys and wildcard/empty allowed-host lists.
3. `/api/health/live` reports process liveness and `/api/health/ready` verifies SQLite.
4. API responses include the defined defensive headers and oversized declared request
   bodies receive HTTP 413.
5. CLI sessions are atomically saved and the existing tests make no external writes or
   network calls.
6. Docker runs as a non-root user, requires production configuration, and has a health
   check.
7. Python regression tests, JavaScript tests/syntax checks, compile checks, and the V0.14
   full-project simulator pass.

## Verification commands

```text
python -m unittest discover -s tests -v
python -m py_compile app/*.py local_bridge/*.py project_os.py run_project_os.py
node tests/test_diagram_layout.js
node tests/test_milestone_gantt.js
node --check app/static/app.js
python tools/simulate_full_project_v014.py
docker compose config
```

## Result · 2026-08-27

Implementation is complete without changing the approved single-process FastAPI +
SQLite architecture or the V0.14 product workflow.

- Acceptance criteria 1–5: PASS.
- Acceptance criterion 6: static definition PASS; container runtime UNVERIFIED because
  Docker is unavailable on this machine.
- Acceptance criterion 7: Python/JavaScript/full simulator PASS; Compose runtime render
  and image health UNVERIFIED for the same environment limitation.
- Evidence and remaining risks are recorded in `STATUS.md`.
