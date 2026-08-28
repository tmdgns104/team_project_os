# Project Status

## Current task

- `TASK-002` — V0.16 Native AI Conversation Import — IMPLEMENTED AND VERIFIED

## Architecture status

- The approved single-process FastAPI + SQLite architecture remains unchanged.
- V0.16 adds a read-only conversation-provider boundary, an incremental import service,
  additive SQLite metadata, and a reversible Live Draft overlay.
- V0.15 structured state, the 13-document Materializer, three design views, and the
  Apply non-regression boundary remain the only Source of Truth update path.
- Enterprise identity/RBAC and a server database remain future design decisions.

## V0.16 evidence — 2026-08-28

- Installed Codex CLI: `codex-cli 0.150.1`; local rollout JSONL store detected from
  `$CODEX_HOME`/`~/.codex` without a guessed absolute path.
- Native read-only integration: PASS; ten recent sessions inspected, one session read,
  cursor monotonicity checked, and only a SHA-256 prefix/count metadata printed.
- Python compileall: PASS.
- Python unit/regression: 78/78 PASS, including 14 focused blocker regressions.
- V0.14 compatibility E2E: PASS.
- V0.15 13-document/3-design E2E: PASS.
- V0.16 Conversation Import Scenarios A-H: 10/10 PASS.
- Diagram layout and Milestone Gantt JavaScript tests: PASS.
- JavaScript syntax checks: PASS.
- Windows launcher check: PASS.
- V0.16 blocker focused suite: 14/14 PASS; V0.16 combined suite: 24/24 PASS.
- Separate security review: PASS. The distiller runs from a disposable non-repository
  directory with an output schema, allowlisted environment, and Codex filesystem,
  browser, local-automation, plugin, image, multi-agent, hook, dependency-install,
  elicitation, and related tool features disabled. Codex 0.150.1 feature parsing
  confirmed the configured master capabilities are disabled.
- Browser GUI smoke: PASS; AI Conversations list rendered and browser console reported
  zero errors/warnings after reload. Native message preview was not captured in browser
  evidence so private conversation text could not enter test artifacts.
- Git diff whitespace check: PASS. Branch push is recorded in the final handoff.

## Acceptance status

1. Native Codex discovery and selected-session read-only preview — PASS.
2. Incremental cursor/hash import and idempotent stable-item merge — PASS.
3. Existing-state comparison and human-readable change preview — PASS.
4. Reversible Live Draft with 13 documents and three designs — PASS.
5. Explicit Apply through V0.15 non-regression protection — PASS.
6. Decision semantics and Human Gate preservation — PASS.
7. Transcript minimization, secret redaction, and corrupt-session isolation — PASS.
8. Codex-not-installed graceful degradation and manual fallback — PASS.
9. Windows local execution — PASS. Ubuntu/macOS remain CI-verified targets; no native
   Codex store from those operating systems was available for local integration testing.
10. Container hardening — STATIC REGRESSION PASS; Docker runtime remains UNVERIFIED
    because Docker is not installed in this environment.

## V0.16 blocker closure — 2026-08-28

All seven interrupted-review blockers are now mapped to deterministic regression
Evidence and pass:

1. DB/document-authoritative human edit preservation, including stale-cache removal.
2. V0.15-to-V0.16 bootstrap of all eight structured catalogs and Stable IDs.
3. Preview/Draft/Apply three-way rebase, same-identity conflict rejection, and
   unrelated human-edit preservation.
4. Contiguous bounded conversation chunks, skip rejection, and cursor progression.
5. Disposable, schema-constrained, environment-minimized, tool-disabled distillation.
6. One bounded non-regressive document addition block with prior Stable-ID retention.
7. Bounded session metadata caching with reuse and file-change invalidation.

V0.16 is merge-ready on `work/v016-native-conversation-import`; `main` has not been
merged. The pre-existing untracked `team_project_os-main.zip` remains outside the Task.

## Known remaining risks

- The native adapter is verified against the observed Codex 0.150.1 rollout format.
  Format changes are isolated to the adapter but require a new fixture/integration check.
- Claude Code and OpenCode native adapters are future work; V0.16 implements Codex plus
  a manual paste fallback.
- Distillation is bounded to protect request size and secret exposure; very large sessions
  may need multiple incremental imports.
- Shared-key authentication does not provide per-user identity, RBAC, or tenant isolation.
- Proxy-level TLS, rate limiting, and streamed/chunked body limits remain deployment work.
