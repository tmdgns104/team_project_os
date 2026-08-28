# TASK-002 — V0.16 Native AI Conversation Import

## Problem

Team Project OS currently offers an AI Design Session, but the product goal is to let
people keep using their normal native AI conversation and import the resulting project
knowledge afterward. V0.16 must support the installed Codex CLI first without weakening
V0.15 materialization, Apply non-regression, or production hardening.

## Outcome contract

- Discover native Codex sessions locally and read only the session selected by the user.
- Preview redacted messages and the exact incremental range before analysis.
- Distill that range into the existing V0.15 structured-state schema.
- Compare the delta with the target project's current structured state.
- Materialize a reversible Live Draft overlay with 13 documents and 3 designs.
- Commit the overlay to Source of Truth only through an explicit human Apply action.
- Re-import only messages after the committed cursor and remain idempotent.

## Local Codex evidence — Windows, 2026-08-28

- Installed CLI: `codex-cli 0.150.1` (`codex.cmd` is usable; PowerShell blocks the
  `codex.ps1` shim under the current execution policy).
- The CLI help declares `$CODEX_HOME`, defaulting to `~/.codex`.
- The current machine contains 234 active files under
  `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl` and one archived session.
- Actual rollout records have top-level `timestamp`, `ordinal`, `type`, and `payload`.
- Session metadata is a `session_meta` record. Conversation messages are
  `response_item` records whose payload is `type=message` and `role=user|assistant`.
- `$CODEX_HOME/session_index.jsonl` records `id`, `thread_name`, and `updated_at`.
- `codex exec --help` supports `--ephemeral`, so Project OS distillation can avoid
  creating another importable Codex session.
- No Codex file or database was modified during investigation.

The V0.16 adapter treats these as versioned, read-only implementation details. It does
not use `history.jsonl`, Codex SQLite databases, or guessed OS-specific absolute paths as
the primary source.

## Architecture impact

No high-level architecture change. The approved single-process FastAPI + SQLite system,
V0.15 structured state, Materializer, and Apply non-regression wrapper remain in place.

V0.16 adds four bounded responsibilities:

1. A provider adapter that detects and parses local Codex rollout files read-only.
2. A redaction/distillation/merge service that emits the V0.15 state shape.
3. SQLite metadata for imported cursors, import attempts, persisted structured state,
   and reversible Live Draft overlays. Migration is additive `CREATE TABLE IF NOT EXISTS`.
4. An `AI Conversations` browser workspace for list, preview, distill, draft, and Apply.

The Live Draft overlay is stored separately from active documents and graph tables.
Only explicit Apply invokes the existing V0.15 `apply_live_draft_state(...,
lifecycle="active")` path. This preserves the Source of Truth boundary.

## Security and privacy invariants

- Never write to `$CODEX_HOME` or invoke Codex session mutation commands.
- Resolve session IDs from the provider's own inventory; never accept a filesystem path
  from the browser.
- Do not store raw transcripts. Persist only import metadata and redacted structured
  results.
- Redact common credentials, private keys, bearer tokens, and secret assignments before
  preview or distillation.
- Do not put message text, prompts, model output, or secrets in application logs.
- Corruption is isolated to one session and does not fail session listing or the server.
- When Codex is absent, the server and all existing project functionality remain healthy.

## Incremental and idempotency contract

- Source identity: `(provider, external_session_id, project_id)`.
- Cursor: the highest consumed rollout `ordinal`, with line position as a legacy fallback.
- Content identity: SHA-256 over provider/session/range/redacted canonical messages.
- Cursor advances only when a preview is accepted into Live Draft.
- Repeating an already accepted range returns a no-change result.
- Stable IDs and semantic identities merge existing items instead of appending duplicates.

## Decision semantics

- `ACCEPTED`: only explicit user agreement or an existing accepted decision.
- `PROVISIONAL`: reversible, low-risk working choice.
- `PENDING`: unresolved or requiring a human gate.
- `REJECTED` / `ALTERNATIVE`: considered but not selected.
- Cost, security/permissions, privacy/legal, and physical safety choices remain Pending
  unless clear human approval is present.

## Acceptance criteria

1. Scenario A: first Codex import produces Requirement/Decision/API/Test delta, a Live
   Draft, 13 documents, and 3 designs.
2. Scenario B: later messages in the same session start after the imported cursor and do
   not duplicate existing items.
3. Scenario C: identical re-import is idempotent.
4. Scenario D: Redis considered then SQLite chosen becomes Alternative/Rejected versus
   Accepted.
5. Scenario E: secrets do not appear in preview, stored delta, documents, or logs.
6. Scenario F: final Apply preserves stable IDs, rich Gantt/API/QA, and designs.
7. Scenario G: a malformed/partial session is isolated and other sessions/projects work.
8. Scenario H: no Codex installation/store leaves the server healthy and reports
   `Codex not detected`.

## Verification commands

```text
python -m unittest discover -s tests -v
python tools/simulate_full_project_v014.py
python tools/simulate_full_project_v015.py
python tools/simulate_conversation_import_v016.py
node tests/test_diagram_layout.js
node tests/test_milestone_gantt.js
node --check app/static/app.js
python run_project_os.py --check
git diff --check
git status --short --branch
```

The native integration check may output only provider/version/count/hash metadata. It
must never print actual conversation content.

## Result — 2026-08-28

Status: IMPLEMENTED AND VERIFIED.

- Added the `ConversationProvider` contract and a read-only Codex 0.150.1 rollout
  adapter discovered from the installed CLI and its actual local store.
- Added incremental source/import metadata, structured-state persistence, and a
  separately stored Live Draft overlay through additive SQLite initialization.
- Added redacted preview, existing-state delta comparison, stable semantic merge,
  decision-state handling, explicit draft/cancel/apply, and manual fallback endpoints.
- Added the browser `AI Conversations` workspace without replacing the V0.15
  Materializer or Apply path.
- Added ten V0.16 automated tests covering Scenarios A-H and a content-suppressing
  real native-session integration check.

Verification result before the final commit cycle:

- Python regression: 64/64 PASS.
- V0.14 E2E: PASS.
- V0.15 E2E: PASS.
- V0.16 Scenario A-H E2E: 10/10 PASS.
- Diagram/Gantt JavaScript: PASS.
- Windows launcher and real browser smoke: PASS.
- Real local Codex read: PASS with conversation content suppressed.

## Blocker closure result — 2026-08-28

The interrupted hardening baseline was independently re-reviewed against the seven
known blockers. Existing production remediation was preserved, missing deterministic
tests were added, and four defects exposed by the expanded tests were fixed minimally.

| Blocker | Production Evidence | Regression Evidence | Result |
|---|---|---|---|
| 1. Human Edit Preservation / DB-authoritative reconciliation | `reconcile_structured_state` rebuilds official rows and canonical-document catalogs; stale catalog cache entries cannot restore deleted human content | current requirement/document reconciliation; stale cache versus project/requirement/decision/design/catalog precedence; non-conflicting Draft/Apply rebase | PASS |
| 2. V0.15 → V0.16 catalog/Stable-ID bootstrap | canonical milestone/backlog/function/IA/API/QA/policy/data documents are parsed into the V0.16 cache | cache-free bootstrap verifies all eight catalog prefixes | PASS |
| 3. Stale Preview/Draft/Apply | persisted base revision/state plus true three-way `rebase_conflicts`; same intended result is non-conflicting and concurrent creation/update is detected | unit three-way semantics; Preview race; Draft/Apply conflict rejection; unrelated human edit preservation | PASS |
| 4. Large conversation chunking | next range is contiguous and bounded by message/character limits; `from_cursor` cannot skip; UI sends the exact next `to_cursor` | unit bounds; 155-message API range; skip rejection; two-chunk cursor progression | PASS |
| 5. Distiller isolation | disposable non-repository cwd, strict output schema, allowlisted environment, ephemeral/read-only Codex invocation, broad tool-feature deny-list | isolated cwd/schema/env assertions; required deny-list assertions; Codex 0.150.1 feature parsing | PASS |
| 6. Repeated document import non-growth | one rebuilt marker block retains human base and prior imported Stable IDs while preferring current generated rows | identical and successive import idempotency/non-growth assertions | PASS |
| 7. Session inventory performance | thread-safe bounded LRU metadata cache keyed by resolved path, mtime, size, archive state, and indexed title | unchanged rollout reuse and changed rollout invalidation | PASS |

Defects found by the expanded focused tests:

- stale cached catalog IDs survived a canonical-document deletion;
- the distiller deny-list omitted image and multi-agent tools;
- a later generated document could discard an earlier imported Stable ID;
- the conflict detector did not implement same-result/concurrent-creation three-way semantics.

Final verification Evidence:

- Focused blocker suite: 14/14 PASS.
- Combined V0.16 suite: 24/24 PASS.
- Full Python regression: 78/78 PASS.
- Python compile: PASS.
- V0.14 full simulator: PASS.
- V0.15 materialization/non-regression simulator: PASS.
- V0.16 Scenarios A-H simulator: 10/10 PASS.
- Diagram layout and Milestone Gantt JavaScript tests: PASS.
- JavaScript syntax and Windows launcher checks: PASS.
- Native Codex 0.150.1 read-only check: PASS; conversation output suppressed.
- Git diff whitespace check: PASS.
- Docker runtime/config rendering: UNVERIFIED because Docker is not installed; the
  existing static container regression remains PASS.

Security was reviewed separately. No raw transcript is persisted or logged, browser
session IDs cannot select filesystem paths, subprocess input remains stdin/list-argv,
and the distiller receives no Project OS access key or database path. This closes the
seven blockers without changing the approved Architecture or expanding permissions.

Merge readiness: READY on `work/v016-native-conversation-import` after the verified
Task commit. Do not merge to `main` as part of this Task.
