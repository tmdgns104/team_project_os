# Project Status

## Current task

- `TASK-001` · Production hardening baseline — IMPLEMENTED, DOCKER RUNTIME UNVERIFIED

## Baseline evidence

- 2026-08-27: `python -m unittest discover -s tests -v`
  - 42 tests run
  - 39 passed
  - 1 failed and 2 errored because CLI tests contacted a live localhost service and/or
    attempted to persist sessions outside the workspace.

## Architecture status

- Existing single-process FastAPI + SQLite architecture remains approved and unchanged.
- Enterprise identity/RBAC and a server database remain future design decisions.

## Completion evidence

- 2026-08-27: Python compileall — PASS.
- 2026-08-27: Python unit/regression — 51/51 PASS.
- 2026-08-27: Python dependency consistency (`pip check`) — PASS.
- 2026-08-27: Diagram layout and Milestone Gantt JavaScript tests — PASS.
- 2026-08-27: JavaScript syntax checks — PASS.
- 2026-08-27: V0.14 full-project / 13 documents / 3 diagrams / malformed
  live-sync simulator — PASS.
- 2026-08-27: Weak production key rejected and valid production import with docs disabled
  — PASS.
- 2026-08-27: Compose YAML static parse and hardening assertions — PASS.
- 2026-08-27: Git diff whitespace check — PASS.

## Acceptance status

1. Local launcher loopback defaults — PASS.
2. Production fail-fast configuration — PASS.
3. Liveness/readiness endpoints — PASS.
4. Defensive headers and declared request-size limit — PASS.
5. Atomic sessions and hermetic CLI tests — PASS.
6. Non-root/read-only/capability-dropped container definition and health check —
   STATIC PASS, RUNTIME UNVERIFIED because Docker is not installed in this environment.
7. Repository regression/simulator verification — PASS; `docker compose config` and
   image health remain UNVERIFIED for the same reason. POSIX shell syntax is covered by
   CI but was not locally rerun because `bash` is unavailable.

## Known remaining risks

- Shared-key authentication does not provide per-user identity, RBAC, or tenant isolation.
- Proxy-level TLS, rate limiting, and streamed/chunked body limits remain deployment work.
- The installed FastAPI test client emits a deprecation warning recommending `httpx2`;
  tests pass and no dependency migration was made without a separate compatibility task.
