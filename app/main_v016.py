from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import main as core
from app import main_v015 as v015
from app.conversation_import import (
    conversation_content_hash,
    distill_conversation,
    merge_structured_states,
    parse_manual_transcript,
    redact_secrets,
    redact_structure,
    redacted_messages,
    select_message_chunk,
    summarize_changes,
)
from app.conversation_providers import CodexConversationProvider
from app.live_state_v015 import sanitize_live_state_v015
from app.materializer_v015 import DOC_TYPES, materialize_documents, merge_document_non_regressive
from app.structured_state_v016 import (
    rebase_conflicts,
    reconcile_structured_state,
    source_of_truth_revision,
)


core.app.version = "0.16.0"

_original_init_db = core.init_db
_original_apply_live_draft_state = core.apply_live_draft_state


class ImportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int
    provider: str = "codex"
    session_id: str = ""
    from_cursor: int | None = None
    to_cursor: int | None = None
    transcript: str = Field(default="", max_length=1_000_000)


def init_db() -> None:
    """Run the approved schema initialization, then additive V0.16 migrations."""

    _original_init_db()
    with core.db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS project_structured_states (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                external_session_id TEXT NOT NULL,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                imported_cursor INTEGER NOT NULL DEFAULT -1,
                imported_at TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                source_version TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, external_session_id, project_id)
            );
            CREATE TABLE IF NOT EXISTS conversation_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES conversation_sources(id) ON DELETE CASCADE,
                start_cursor INTEGER NOT NULL,
                end_cursor INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'preview',
                delta_json TEXT NOT NULL DEFAULT '{}',
                merged_state_json TEXT NOT NULL DEFAULT '{}',
                diff_json TEXT NOT NULL DEFAULT '{}',
                base_state_hash TEXT NOT NULL DEFAULT '',
                base_state_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT '',
                UNIQUE(source_id, content_hash)
            );
            CREATE TABLE IF NOT EXISTS project_live_drafts (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                import_id INTEGER NOT NULL UNIQUE REFERENCES conversation_imports(id) ON DELETE CASCADE,
                state_json TEXT NOT NULL,
                documents_json TEXT NOT NULL,
                designs_json TEXT NOT NULL,
                base_state_hash TEXT NOT NULL DEFAULT '',
                base_state_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversation_sources_project
                ON conversation_sources(project_id, provider);
            CREATE INDEX IF NOT EXISTS idx_conversation_imports_source_status
                ON conversation_imports(source_id, status);
            """
        )
        _ensure_column(
            conn, "conversation_imports", "base_state_hash", "TEXT NOT NULL DEFAULT ''"
        )
        _ensure_column(
            conn, "conversation_imports", "base_state_json", "TEXT NOT NULL DEFAULT '{}'"
        )
        _ensure_column(
            conn, "project_live_drafts", "base_state_hash", "TEXT NOT NULL DEFAULT ''"
        )
        _ensure_column(
            conn, "project_live_drafts", "base_state_json", "TEXT NOT NULL DEFAULT '{}'"
        )


def _json_load(raw: str | None, fallback: Any) -> Any:
    try:
        value = json.loads(raw or "")
    except json.JSONDecodeError:
        return fallback
    return value


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _designs_from_database(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    designs: list[dict[str, Any]] = []
    for view in ("process", "architecture", "dataflow"):
        rows = conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND view=? ORDER BY id",
            (project_id, view),
        ).fetchall()
        if not rows:
            continue
        key_by_id = {row["id"]: f"existing-{row['id']}" for row in rows}
        nodes = [
            {
                "key": key_by_id[row["id"]],
                "label": row["label"],
                "kind": row["kind"],
                "detail": row["detail"],
            }
            for row in rows
        ]
        edges = [
            {
                "source": key_by_id[row["source_id"]],
                "target": key_by_id[row["target_id"]],
                "label": row["label"],
            }
            for row in conn.execute(
                "SELECT * FROM edges WHERE project_id=? AND view=? ORDER BY id",
                (project_id, view),
            ).fetchall()
            if row["source_id"] in key_by_id and row["target_id"] in key_by_id
        ]
        designs.append(
            {
                "view": view,
                "mode": "merge",
                "reason": "Existing Source of Truth graph",
                "nodes": nodes,
                "edges": edges,
            }
        )
    return designs


def load_structured_state(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    return reconcile_structured_state(conn, project_id)


def save_structured_state(
    conn: sqlite3.Connection, project_id: int, state: dict[str, Any]
) -> None:
    reconcile_structured_state(conn, project_id, seed_state=state)


def apply_live_draft_state(
    conn: sqlite3.Connection,
    project_id: int,
    member_name: str,
    state: dict[str, Any],
    *,
    lifecycle: str = "draft",
):
    result = _original_apply_live_draft_state(
        conn, project_id, member_name, state, lifecycle=lifecycle
    )
    save_structured_state(conn, project_id, state)
    return result


def _provider() -> CodexConversationProvider:
    return CodexConversationProvider()


def _source_row(
    conn: sqlite3.Connection,
    *,
    provider: str,
    session_id: str,
    project_id: int,
    source_version: str,
) -> sqlite3.Row:
    timestamp = core.now()
    conn.execute(
        """
        INSERT INTO conversation_sources(
          provider,external_session_id,project_id,source_version,created_at,updated_at
        ) VALUES(?,?,?,?,?,?)
        ON CONFLICT(provider,external_session_id,project_id) DO UPDATE SET
          source_version=excluded.source_version,
          updated_at=excluded.updated_at
        """,
        (provider, session_id, project_id, source_version, timestamp, timestamp),
    )
    return conn.execute(
        """
        SELECT * FROM conversation_sources
        WHERE provider=? AND external_session_id=? AND project_id=?
        """,
        (provider, session_id, project_id),
    ).fetchone()


def _overlay_design_rows(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    next_node_id = 1
    next_edge_id = 1
    for design in state.get("design_updates", []) or []:
        view = str(design.get("view") or "")
        key_to_id: dict[str, int] = {}
        for index, node in enumerate(design.get("nodes", []) or []):
            node_id = next_node_id
            next_node_id += 1
            key_to_id[str(node.get("key") or "")] = node_id
            nodes.append(
                {
                    "id": node_id,
                    "project_id": 0,
                    "view": view,
                    "label": node.get("label", ""),
                    "kind": node.get("kind", "component"),
                    "detail": node.get("detail", ""),
                    "x": 80 + (index % 4) * 220,
                    "y": 80 + (index // 4) * 150,
                }
            )
        for edge in design.get("edges", []) or []:
            source = key_to_id.get(str(edge.get("source") or ""))
            target = key_to_id.get(str(edge.get("target") or ""))
            if not source or not target or source == target:
                continue
            edges.append(
                {
                    "id": next_edge_id,
                    "project_id": 0,
                    "view": view,
                    "source_id": source,
                    "target_id": target,
                    "label": edge.get("label", ""),
                }
            )
            next_edge_id += 1
    return {"nodes": nodes, "edges": edges}


def _materialize_overlay(
    conn: sqlite3.Connection, project_id: int, merged_state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    brief = core.merge_project_brief(
        core.ensure_project_brief(conn, project_id),
        merged_state.get("project_updates", {}),
    )
    state_without_replacements = dict(merged_state)
    state_without_replacements["document_updates"] = []
    generated = materialize_documents(brief, state_without_replacements)
    existing = {
        row["doc_type"]: dict(row)
        for row in conn.execute(
            "SELECT * FROM documents WHERE project_id=? ORDER BY id", (project_id,)
        )
    }
    documents: list[dict[str, Any]] = []
    timestamp = core.now()
    for doc_type in DOC_TYPES:
        current = existing.get(doc_type, {})
        new_content = generated.get(doc_type, "")
        old_content = str(current.get("content") or "")
        if old_content:
            new_content = merge_document_non_regressive(old_content, new_content)
        documents.append(
            {
                "id": current.get("id", len(documents) + 1),
                "project_id": project_id,
                "doc_type": doc_type,
                "title": current.get("title", doc_type),
                "content": new_content,
                "status": "draft",
                "updated_by": "V0.16 Conversation Import",
                "created_at": current.get("created_at", timestamp),
                "updated_at": timestamp,
            }
        )
    apply_state = dict(merged_state)
    apply_state["document_updates"] = [
        {
            "doc_type": item["doc_type"],
            "content": item["content"],
            "reason": "Reviewed V0.16 Conversation Import Live Draft",
        }
        for item in documents
    ]
    apply_state = sanitize_live_state_v015(apply_state)
    return apply_state, documents, _overlay_design_rows(apply_state)


def conversation_live_draft_snapshot(
    conn: sqlite3.Connection, project_id: int
) -> dict[str, Any] | None:
    if not _table_exists(conn, "project_live_drafts"):
        return None
    row = conn.execute(
        """
        SELECT d.*,i.status AS import_status,s.provider,s.external_session_id
        FROM project_live_drafts d
        JOIN conversation_imports i ON i.id=d.import_id
        JOIN conversation_sources s ON s.id=i.source_id
        WHERE d.project_id=?
        """,
        (project_id,),
    ).fetchone()
    if not row:
        return None
    state = _json_load(row["state_json"], {})
    designs = _json_load(row["designs_json"], {"nodes": [], "edges": []})
    return {
        "import_id": row["import_id"],
        "status": row["import_status"],
        "provider": row["provider"],
        "session_id": row["external_session_id"],
        "updated_at": row["updated_at"],
        "documents": _json_load(row["documents_json"], []),
        "nodes": designs.get("nodes", []),
        "edges": designs.get("edges", []),
        "requirements": state.get("requirements", []),
        "decisions": state.get("decisions", []),
        "state": state,
    }


def _import_response(row: sqlite3.Row, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "import_id": row["id"],
        "status": row["status"],
        "start_cursor": row["start_cursor"],
        "end_cursor": row["end_cursor"],
        "content_hash": row["content_hash"],
        "delta": _json_load(row["delta_json"], {}),
        "changes": _json_load(row["diff_json"], {}),
        "base_state_hash": row["base_state_hash"],
        "messages": messages or [],
    }


def _rebase_import(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> tuple[dict[str, Any], str]:
    """Reapply only the stored delta to the latest official project state."""

    current = reconcile_structured_state(conn, int(row["project_id"]))
    current_revision = source_of_truth_revision(conn, int(row["project_id"]), current)
    base = sanitize_live_state_v015(_json_load(row["base_state_json"], {}))
    delta = sanitize_live_state_v015(_json_load(row["delta_json"], {}))
    if row["base_state_hash"] and row["base_state_hash"] != current_revision:
        conflicts = rebase_conflicts(base, current, delta)
        if conflicts:
            raise HTTPException(
                409,
                detail={
                    "message": "Project changed after Preview; review the conflicting stable IDs",
                    "conflicts": conflicts,
                },
            )

    merged = merge_structured_states(current, delta)
    changes = summarize_changes(current, merged)
    timestamp = core.now()
    conn.execute(
        """
        UPDATE conversation_imports
        SET base_state_hash=?,base_state_json=?,merged_state_json=?,diff_json=?,updated_at=?
        WHERE id=?
        """,
        (
            current_revision,
            json.dumps(current, ensure_ascii=False),
            json.dumps(merged, ensure_ascii=False),
            json.dumps(changes, ensure_ascii=False),
            timestamp,
            row["id"],
        ),
    )
    return merged, current_revision


@core.app.get("/api/conversation-import/providers")
def conversation_import_providers(x_access_key: str | None = Header(default=None)):
    core.require_access(x_access_key)
    return {"providers": [_provider().detect()], "primary": "codex", "fallback": "manual"}


@core.app.get("/api/conversation-import/sessions")
def conversation_import_sessions(
    project_id: int = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    x_access_key: str | None = Header(default=None),
):
    core.require_access(x_access_key)
    provider = _provider()
    status = provider.detect()
    try:
        sessions = [item.to_dict() for item in provider.list_sessions(limit=limit)]
    except Exception as exc:
        status = {**status, "message": f"Codex sessions unavailable: {type(exc).__name__}"}
        sessions = []
    with core.db() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        sources = {
            row["external_session_id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM conversation_sources WHERE project_id=? AND provider='codex'",
                (project_id,),
            )
        }
    for session in sessions:
        session["title"] = redact_secrets(session.get("title", ""))
        source = sources.get(session["session_id"])
        session["imported"] = bool(source and source["imported_cursor"] >= 0)
        session["imported_cursor"] = source["imported_cursor"] if source else -1
        session["imported_at"] = source["imported_at"] if source else ""
    return {"provider": status, "sessions": sessions}


@core.app.get("/api/conversation-import/sessions/{session_id}")
def conversation_import_session(
    session_id: str,
    project_id: int = Query(...),
    x_access_key: str | None = Header(default=None),
):
    core.require_access(x_access_key)
    provider = _provider()
    try:
        metadata = provider.get_session_metadata(session_id)
        native_messages = provider.read_messages(session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, str(exc)) from exc
    with core.db() as conn:
        source = conn.execute(
            """
            SELECT * FROM conversation_sources
            WHERE provider='codex' AND external_session_id=? AND project_id=?
            """,
            (session_id, project_id),
        ).fetchone()
    cursor = source["imported_cursor"] if source else -1
    selected, total_unimported = select_message_chunk(
        native_messages, after_cursor=int(cursor)
    )
    all_messages = redacted_messages(native_messages)
    analysis_messages = redacted_messages(selected)
    safe_metadata = metadata.to_dict()
    safe_metadata["title"] = redact_secrets(safe_metadata.get("title", ""))
    return {
        "session": safe_metadata,
        "messages": all_messages,
        "imported_cursor": cursor,
        "analysis_messages": analysis_messages,
        "total_unimported": total_unimported,
        "remaining_after_chunk": max(0, total_unimported - len(analysis_messages)),
        "has_more": total_unimported > len(analysis_messages),
        "next_to_cursor": analysis_messages[-1]["cursor"] if analysis_messages else cursor,
        "imported_at": source["imported_at"] if source else "",
    }


@core.app.post("/api/conversation-import/preview")
async def preview_conversation_import(
    payload: ImportPreviewRequest,
    x_access_key: str | None = Header(default=None),
):
    core.require_access(x_access_key)
    if payload.provider not in {"codex", "manual"}:
        raise HTTPException(400, "Unsupported conversation provider")
    with core.db() as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id=?", (payload.project_id,)
        ).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        if conn.execute(
            "SELECT 1 FROM project_live_drafts WHERE project_id=?", (payload.project_id,)
        ).fetchone():
            raise HTTPException(409, "Review, Apply, or discard the current Live Draft first")
        current_state = load_structured_state(conn, payload.project_id)
        current_revision = source_of_truth_revision(conn, payload.project_id, current_state)

    source_version = "manual-v1"
    if payload.provider == "codex":
        if not payload.session_id:
            raise HTTPException(400, "Codex session ID is required")
        provider = _provider()
        try:
            metadata = provider.get_session_metadata(payload.session_id)
            native_messages = provider.read_messages(payload.session_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        session_id = metadata.session_id
        source_version = metadata.source_version or provider.detect().get("version", "")
    else:
        native_messages = parse_manual_transcript(payload.transcript)
        if not native_messages:
            raise HTTPException(400, "Transcript is empty")
        digest = hashlib.sha256(payload.transcript.encode("utf-8")).hexdigest()[:24]
        session_id = payload.session_id.strip() or f"manual-{digest}"

    with core.db() as conn:
        source = _source_row(
            conn,
            provider=payload.provider,
            session_id=session_id,
            project_id=payload.project_id,
            source_version=source_version,
        )
        imported_cursor = int(source["imported_cursor"])
    if payload.from_cursor is not None and payload.from_cursor != imported_cursor:
        raise HTTPException(
            409,
            "from_cursor must equal the latest imported cursor; conversation ranges cannot be skipped",
        )
    start_cursor = imported_cursor
    if payload.to_cursor is not None and payload.to_cursor <= start_cursor:
        raise HTTPException(400, "to_cursor must be after the imported cursor")
    selected, _bounded_total = select_message_chunk(
        native_messages,
        after_cursor=start_cursor,
        to_cursor=payload.to_cursor,
    )
    total_unimported = sum(message.cursor > start_cursor for message in native_messages)
    messages = redacted_messages(selected)
    if not messages:
        return {
            "status": "no_changes",
            "session_id": session_id,
            "start_cursor": start_cursor,
            "end_cursor": start_cursor,
            "messages": [],
            "changes": {},
            "total_unimported": total_unimported,
            "remaining_after_chunk": 0,
            "has_more": False,
        }
    content_hash = conversation_content_hash(payload.provider, session_id, messages)
    with core.db() as conn:
        existing = conn.execute(
            """
            SELECT i.*,s.project_id FROM conversation_imports i
            JOIN conversation_sources s ON s.id=i.source_id
            WHERE i.source_id=? AND i.content_hash=?
            """,
            (source["id"], content_hash),
        ).fetchone()
        if existing:
            _rebase_import(conn, existing)
            refreshed = conn.execute(
                "SELECT * FROM conversation_imports WHERE id=?", (existing["id"],)
            ).fetchone()
            return {
                **_import_response(refreshed, messages),
                "session_id": session_id,
                "total_unimported": total_unimported,
                "remaining_after_chunk": max(0, total_unimported - len(messages)),
                "has_more": total_unimported > len(messages),
            }

    try:
        delta = await asyncio.to_thread(
            distill_conversation,
            messages=messages,
            current_state=current_state,
            project_name=project["name"],
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    delta = redact_structure(delta)
    end_cursor = max(int(item["cursor"]) for item in messages)
    timestamp = core.now()
    with core.db() as conn:
        latest_state = load_structured_state(conn, payload.project_id)
        latest_revision = source_of_truth_revision(conn, payload.project_id, latest_state)
        if latest_revision != current_revision:
            conflicts = rebase_conflicts(current_state, latest_state, delta)
            if conflicts:
                raise HTTPException(
                    409,
                    detail={
                        "message": "Project changed during Preview; review the conflicting stable IDs",
                        "conflicts": conflicts,
                    },
                )
            current_state = latest_state
            current_revision = latest_revision
        merged = merge_structured_states(current_state, delta)
        changes = summarize_changes(current_state, merged)
        conn.execute(
            """
            INSERT OR IGNORE INTO conversation_imports(
              source_id,start_cursor,end_cursor,content_hash,status,delta_json,
              merged_state_json,diff_json,base_state_hash,base_state_json,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                source["id"],
                start_cursor,
                end_cursor,
                content_hash,
                "preview",
                json.dumps(delta, ensure_ascii=False),
                json.dumps(merged, ensure_ascii=False),
                json.dumps(changes, ensure_ascii=False),
                current_revision,
                json.dumps(current_state, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM conversation_imports WHERE source_id=? AND content_hash=?",
            (source["id"], content_hash),
        ).fetchone()
    return {
        **_import_response(row, messages),
        "session_id": session_id,
        "total_unimported": total_unimported,
        "remaining_after_chunk": max(0, total_unimported - len(messages)),
        "has_more": total_unimported > len(messages),
    }


@core.app.post("/api/conversation-imports/{import_id}/draft")
async def stage_conversation_import(
    import_id: int, x_access_key: str | None = Header(default=None)
):
    core.require_access(x_access_key)
    with core.db() as conn:
        row = conn.execute(
            """
            SELECT i.*,s.project_id,s.provider,s.external_session_id
            FROM conversation_imports i
            JOIN conversation_sources s ON s.id=i.source_id
            WHERE i.id=?
            """,
            (import_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Conversation import not found")
        if row["status"] == "applied":
            raise HTTPException(409, "Conversation import is already applied")
        existing = conn.execute(
            "SELECT * FROM project_live_drafts WHERE project_id=?", (row["project_id"],)
        ).fetchone()
        if existing and existing["import_id"] != import_id:
            raise HTTPException(409, "Another Live Draft is already active")
        merged, current_revision = _rebase_import(conn, row)
        apply_state, documents, designs = _materialize_overlay(conn, row["project_id"], merged)
        timestamp = core.now()
        conn.execute(
            """
            INSERT INTO project_live_drafts(
              project_id,import_id,state_json,documents_json,designs_json,
              base_state_hash,base_state_json,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(project_id) DO UPDATE SET
              import_id=excluded.import_id,
              state_json=excluded.state_json,
              documents_json=excluded.documents_json,
              designs_json=excluded.designs_json,
              base_state_hash=excluded.base_state_hash,
              base_state_json=excluded.base_state_json,
              updated_at=excluded.updated_at
            """,
            (
                row["project_id"],
                import_id,
                json.dumps(apply_state, ensure_ascii=False),
                json.dumps(documents, ensure_ascii=False),
                json.dumps(designs, ensure_ascii=False),
                current_revision,
                json.dumps(reconcile_structured_state(conn, row["project_id"]), ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        conn.execute(
            "UPDATE conversation_imports SET status='drafted',updated_at=? WHERE id=?",
            (timestamp, import_id),
        )
        conn.execute(
            """
            UPDATE conversation_sources
            SET imported_cursor=?,imported_at=?,content_hash=?,updated_at=?
            WHERE id=?
            """,
            (row["end_cursor"], timestamp, row["content_hash"], timestamp, row["source_id"]),
        )
        core.add_activity(
            conn,
            row["project_id"],
            "conversation_import",
            f"{row['provider']} conversation imported to Live Draft",
            "Conversation Import",
        )
        response = conversation_live_draft_snapshot(conn, row["project_id"])
    await core.manager.broadcast(row["project_id"], {"type": "refresh", "scope": "conversation_live_draft"})
    return response


@core.app.post("/api/conversation-imports/{import_id}/apply")
async def apply_conversation_import(
    import_id: int, x_access_key: str | None = Header(default=None)
):
    core.require_access(x_access_key)
    with core.db() as conn:
        row = conn.execute(
            """
            SELECT i.*,s.project_id FROM conversation_imports i
            JOIN conversation_sources s ON s.id=i.source_id WHERE i.id=?
            """,
            (import_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Conversation import not found")
        draft = conn.execute(
            "SELECT * FROM project_live_drafts WHERE project_id=? AND import_id=?",
            (row["project_id"], import_id),
        ).fetchone()
        if not draft or row["status"] != "drafted":
            raise HTTPException(409, "Import is not an active Live Draft")
        merged, current_revision = _rebase_import(conn, row)
        state, documents, designs = _materialize_overlay(
            conn, row["project_id"], merged
        )
        timestamp = core.now()
        conn.execute(
            """
            UPDATE project_live_drafts
            SET state_json=?,documents_json=?,designs_json=?,base_state_hash=?,
                base_state_json=?,updated_at=?
            WHERE project_id=? AND import_id=?
            """,
            (
                json.dumps(state, ensure_ascii=False),
                json.dumps(documents, ensure_ascii=False),
                json.dumps(designs, ensure_ascii=False),
                current_revision,
                json.dumps(reconcile_structured_state(conn, row["project_id"]), ensure_ascii=False),
                timestamp,
                row["project_id"],
                import_id,
            ),
        )
        project = core.apply_live_draft_state(
            conn,
            row["project_id"],
            "Conversation Import",
            state,
            lifecycle="active",
        )
        conn.execute(
            "UPDATE conversation_imports SET status='applied',applied_at=?,updated_at=? WHERE id=?",
            (timestamp, timestamp, import_id),
        )
        conn.execute("DELETE FROM project_live_drafts WHERE project_id=?", (row["project_id"],))
    await core.manager.broadcast(row["project_id"], {"type": "refresh", "scope": "conversation_import_applied"})
    return {"status": "applied", "import_id": import_id, "project": project}


@core.app.post("/api/conversation-imports/{import_id}/cancel")
async def cancel_conversation_import(
    import_id: int, x_access_key: str | None = Header(default=None)
):
    core.require_access(x_access_key)
    with core.db() as conn:
        row = conn.execute(
            """
            SELECT i.*,s.project_id FROM conversation_imports i
            JOIN conversation_sources s ON s.id=i.source_id WHERE i.id=?
            """,
            (import_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Conversation import not found")
        if row["status"] == "applied":
            raise HTTPException(409, "Applied imports cannot be cancelled")
        conn.execute("DELETE FROM project_live_drafts WHERE import_id=?", (import_id,))
        previous = conn.execute(
            """
            SELECT end_cursor,content_hash,applied_at FROM conversation_imports
            WHERE source_id=? AND status='applied' AND end_cursor<=?
            ORDER BY end_cursor DESC,id DESC LIMIT 1
            """,
            (row["source_id"], row["start_cursor"]),
        ).fetchone()
        restored_cursor = previous["end_cursor"] if previous else row["start_cursor"]
        restored_hash = previous["content_hash"] if previous else ""
        restored_at = previous["applied_at"] if previous else ""
        timestamp = core.now()
        conn.execute(
            "UPDATE conversation_imports SET status='cancelled',updated_at=? WHERE id=?",
            (timestamp, import_id),
        )
        conn.execute(
            """
            UPDATE conversation_sources SET imported_cursor=?,content_hash=?,imported_at=?,updated_at=?
            WHERE id=?
            """,
            (restored_cursor, restored_hash, restored_at, timestamp, row["source_id"]),
        )
    await core.manager.broadcast(row["project_id"], {"type": "refresh", "scope": "conversation_import_cancelled"})
    return {"status": "cancelled", "import_id": import_id}


core.init_db = init_db
core.apply_live_draft_state = apply_live_draft_state
core.conversation_live_draft_snapshot = conversation_live_draft_snapshot

app = core.app
