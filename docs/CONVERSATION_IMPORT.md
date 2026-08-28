# Native AI Conversation Import

## Product flow

```text
Native AI conversation
  -> local session discovery
  -> redacted preview and incremental range
  -> conversation distiller
  -> structured delta versus current project state
  -> reversible Live Draft overlay
  -> 13 documents + System Process / Architecture / Data Flow
  -> human review
  -> Apply to Source of Truth
```

Project OS does not require users to conduct the original conversation in a dedicated
Project OS chat. V0.16 uses Codex CLI as the first native provider. Provider boundaries
allow later Claude Code, OpenCode, exported transcript, and paste adapters without
duplicating the import workflow.

## Components

- `ConversationProvider`: detection, session inventory, metadata, full read, and
  cursor-based read contract.
- `CodexConversationProvider`: read-only parser for the locally observed Codex rollout
  format, isolated by CLI/session version.
- Import service: secret redaction, content hashing, distiller prompt, V0.15
  normalization, stable-ID merge, and change summary.
- Live Draft overlay: persisted structured state, materialized documents, and designs
  that do not replace active Source of Truth before Apply.
- Import metadata: project/source/cursor/hash/timestamps only; raw transcripts are not
  retained.

## Storage and migration

V0.16 uses additive SQLite initialization. Existing databases receive new tables with
`CREATE TABLE IF NOT EXISTS`; existing tables and rows are not rewritten. A fresh or old
database can therefore start on V0.16 without a destructive migration.

## Failure boundaries

- Missing Codex: provider status is unavailable; the FastAPI application remains ready.
- Broken session: the inventory entry carries an error and other entries remain usable.
- Partial final JSONL line: complete earlier records remain previewable and the entry
  reports a warning.
- Distiller failure: the cursor does not advance and Source of Truth is unchanged.
- Draft cancellation: the preview/import attempt is cancelled and active project data is
  unchanged.
- Apply failure: SQLite transaction rollback and existing operational protections apply.
