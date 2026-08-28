from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

from app import main as core
from app.conversation_import import CATEGORY_SPECS, merge_structured_states
from app.live_state_v015 import sanitize_live_state_v015
from app.materializer_v015 import stable_ids


CATALOG_DOCUMENTS: dict[str, dict[str, Any]] = {
    "milestones": {
        "doc_type": "milestone",
        "id_field": "id",
        "id_index": 1,
        "id_pattern": r"MS-[A-Za-z0-9_-]+",
        "fields": (
            "phase", "id", "task", "start_week", "end_week", "owner",
            "status", "deliverable", "exit_criteria", "requirement_refs",
        ),
        "label_field": "task",
    },
    "backlog_items": {
        "doc_type": "backlog",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"BL-[A-Za-z0-9_-]+",
        "fields": (
            "id", "epic", "title", "detail", "priority", "estimate", "owner",
            "status", "requirement_refs", "dependencies", "definition_of_ready",
            "definition_of_done",
        ),
        "label_field": "title",
    },
    "functions": {
        "doc_type": "function_definition",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"FUNC-[A-Za-z0-9_-]+",
        "fields": (
            "id", "name", "actor", "trigger", "preconditions", "inputs",
            "business_rules", "normal_flow", "exception_flow", "outputs",
            "acceptance_criteria", "requirement_refs",
        ),
        "label_field": "name",
    },
    "screens": {
        "doc_type": "ia",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"SCR-[A-Za-z0-9_-]+",
        "fields": (
            "id", "name", "purpose", "users", "entry_conditions", "actions",
            "api_refs", "requirement_refs",
        ),
        "label_field": "name",
    },
    "interfaces": {
        "doc_type": "api_design",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"(?:API|IF)-[A-Za-z0-9_-]+",
        "fields": (
            "id", "kind", "method", "path", "purpose", "auth", "request",
            "response", "errors", "timeout_retry", "idempotency", "versioning",
            "requirement_refs",
        ),
        "label_field": "name",
    },
    "tests": {
        "doc_type": "qa",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"TC-[A-Za-z0-9_-]+",
        "fields": (
            "id", "requirement_refs", "priority", "preconditions", "steps",
            "expected", "evidence", "pass_fail", "status",
        ),
        "label_field": "expected",
    },
    "policies": {
        "doc_type": "service_policy",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"POL-[A-Za-z0-9_-]+",
        "fields": (
            "id", "category", "policy", "target", "monitoring", "response",
            "owner", "status", "requirement_refs",
        ),
        "label_field": "policy",
    },
    "data_items": {
        "doc_type": "data_flow",
        "id_field": "id",
        "id_index": 0,
        "id_pattern": r"DATA-[A-Za-z0-9_-]+",
        "fields": (
            "id", "name", "source", "fields", "validation", "processing",
            "destination", "protocol", "retention", "failure_handling",
            "requirement_refs",
        ),
        "label_field": "name",
    },
}


def _json_load(raw: str | None, fallback: Any) -> Any:
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return fallback


def _markdown_cells(line: str) -> list[str]:
    if not line.lstrip().startswith("|") or line.count("|") < 2:
        return []
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if not cells or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
        return []
    return cells


def _catalog_from_document(content: str, spec: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    fields = tuple(spec["fields"])
    for line in str(content or "").splitlines():
        cells = _markdown_cells(line)
        id_index = int(spec["id_index"])
        if len(cells) <= id_index:
            continue
        identifier = cells[id_index]
        if not re.fullmatch(str(spec["id_pattern"]), identifier, re.I):
            continue
        marker = identifier.lower()
        if marker in seen:
            continue
        seen.add(marker)
        padded = [*cells, *([""] * max(0, len(fields) - len(cells)))]
        item = {field: padded[index] for index, field in enumerate(fields)}
        item[str(spec["id_field"])] = identifier
        items.append(item)

    # A human-edited canonical document may no longer use the generated table layout.
    # Preserve only explicit stable IDs; do not infer acceptance or detailed semantics.
    for identifier in sorted(stable_ids(content)):
        if not re.fullmatch(str(spec["id_pattern"]), identifier, re.I):
            continue
        if identifier.lower() in seen:
            continue
        seen.add(identifier.lower())
        items.append(
            {
                str(spec["id_field"]): identifier,
                str(spec["label_field"]): f"Preserved from existing {spec['doc_type']} document",
            }
        )
    return items


def bootstrap_catalogs_from_documents(
    conn: sqlite3.Connection, project_id: int
) -> dict[str, list[dict[str, str]]]:
    documents = {
        row["doc_type"]: str(row["content"] or "")
        for row in conn.execute(
            "SELECT doc_type,content FROM documents WHERE project_id=?", (project_id,)
        )
    }
    return {
        category: _catalog_from_document(documents.get(spec["doc_type"], ""), spec)
        for category, spec in CATALOG_DOCUMENTS.items()
    }


def _requirements_from_database(
    conn: sqlite3.Connection, project_id: int
) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    for row in conn.execute(
        "SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,)
    ):
        title = str(row["title"] or "")
        parts = title.split(" ", 1)
        ref = parts[0] if parts and parts[0].upper().startswith("REQ-") else ""
        requirements.append(
            {
                "ref": ref,
                "title": parts[1] if ref and len(parts) > 1 else title,
                "detail": str(row["detail"] or ""),
                "status": str(row["status"] or "defined"),
                "source": "Current Project Database",
            }
        )
    return requirements


def _decisions_from_database(
    conn: sqlite3.Connection,
    project_id: int,
    cached: dict[str, Any],
) -> list[dict[str, str]]:
    cached_refs = {
        str(item.get("title") or "").strip().lower(): str(item.get("ref") or "")
        for item in cached.get("decisions", [])
        if isinstance(item, dict) and item.get("title")
    }
    decisions: list[dict[str, str]] = []
    for row in conn.execute(
        "SELECT * FROM decisions WHERE project_id=? ORDER BY id", (project_id,)
    ):
        title = str(row["title"] or "")
        parts = title.split(" ", 1)
        explicit_ref = parts[0] if parts and parts[0].upper().startswith("DEC-") else ""
        clean_title = parts[1] if explicit_ref and len(parts) > 1 else title
        decisions.append(
            {
                "ref": explicit_ref or cached_refs.get(clean_title.strip().lower(), ""),
                "title": clean_title,
                "body": str(row["body"] or ""),
                "status": str(row["status"] or "pending"),
            }
        )
    return decisions


def _designs_from_database(
    conn: sqlite3.Connection,
    project_id: int,
    cached: dict[str, Any],
) -> list[dict[str, Any]]:
    cached_keys: dict[tuple[str, str], str] = {}
    for design in cached.get("design_updates", []) or []:
        view = str(design.get("view") or "")
        for node in design.get("nodes", []) or []:
            label = str(node.get("label") or "").strip().lower()
            key = str(node.get("key") or "").strip()
            if view and label and key:
                cached_keys[(view, label)] = key

    designs: list[dict[str, Any]] = []
    for view in ("process", "architecture", "dataflow"):
        rows = conn.execute(
            "SELECT * FROM nodes WHERE project_id=? AND view=? ORDER BY id",
            (project_id, view),
        ).fetchall()
        if not rows:
            continue
        key_by_id: dict[int, str] = {}
        nodes: list[dict[str, str]] = []
        for row in rows:
            label = str(row["label"] or "")
            key = cached_keys.get((view, label.strip().lower()))
            if not key:
                digest = hashlib.sha256(
                    f"{view}:{label}:{row['kind']}".lower().encode("utf-8")
                ).hexdigest()[:12]
                key = f"db-{digest}"
            key_by_id[int(row["id"])] = key
            nodes.append(
                {
                    "key": key,
                    "label": label,
                    "kind": str(row["kind"] or "component"),
                    "detail": str(row["detail"] or ""),
                }
            )
        edges = [
            {
                "source": key_by_id[int(row["source_id"])],
                "target": key_by_id[int(row["target_id"])],
                "label": str(row["label"] or ""),
            }
            for row in conn.execute(
                "SELECT * FROM edges WHERE project_id=? AND view=? ORDER BY id",
                (project_id, view),
            )
            if int(row["source_id"]) in key_by_id and int(row["target_id"]) in key_by_id
        ]
        designs.append(
            {
                "view": view,
                "mode": "merge",
                "reason": "Current Project Database graph",
                "nodes": nodes,
                "edges": edges,
            }
        )
    return designs


def _cached_state(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT state_json FROM project_structured_states WHERE project_id=?",
        (project_id,),
    ).fetchone()
    return sanitize_live_state_v015(_json_load(row["state_json"], {})) if row else {}


def _persist_cache(conn: sqlite3.Connection, project_id: int, state: dict[str, Any]) -> None:
    safe = sanitize_live_state_v015(state)
    safe["document_updates"] = []
    serialized = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    existing = conn.execute(
        "SELECT state_json FROM project_structured_states WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if existing:
        current = json.dumps(
            sanitize_live_state_v015(_json_load(existing["state_json"], {})),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if current == serialized:
            return
    conn.execute(
        """
        INSERT INTO project_structured_states(project_id,state_json,updated_at)
        VALUES(?,?,?)
        ON CONFLICT(project_id) DO UPDATE SET
          state_json=excluded.state_json,
          updated_at=excluded.updated_at
        """,
        (project_id, serialized, core.now()),
    )


def reconcile_structured_state(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    seed_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild the cache from current Source of Truth rows and canonical documents."""

    cached = sanitize_live_state_v015(seed_state) if seed_state is not None else _cached_state(conn, project_id)
    document_state = bootstrap_catalogs_from_documents(conn, project_id)
    reconciled = dict(cached)
    # These catalogs are materialized in canonical documents. Rebuild them from the
    # current documents so a stale cache cannot restore a row that a human removed.
    for category, items in document_state.items():
        reconciled[category] = items

    brief = core.ensure_project_brief(conn, project_id)
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise ValueError("Project not found")
    project_updates = {**reconciled.get("project_updates", {}), **brief}
    for field in ("name", "goal", "description"):
        value = project[field]
        if value is not None:
            project_updates[field] = value

    reconciled["project_updates"] = project_updates
    reconciled["requirements"] = _requirements_from_database(conn, project_id)
    reconciled["decisions"] = _decisions_from_database(conn, project_id, reconciled)
    reconciled["design_updates"] = _designs_from_database(conn, project_id, reconciled)
    reconciled = sanitize_live_state_v015(reconciled)
    _persist_cache(conn, project_id, reconciled)
    return reconciled


def source_of_truth_revision(
    conn: sqlite3.Connection, project_id: int, state: dict[str, Any]
) -> str:
    """Hash official rows plus reconciled structure; the cache row itself is excluded."""

    tables = {
        "project": [dict(row) for row in conn.execute(
            "SELECT id,name,goal,description,lifecycle FROM projects WHERE id=?", (project_id,)
        )],
        "requirements": [dict(row) for row in conn.execute(
            "SELECT id,title,detail,status FROM requirements WHERE project_id=? ORDER BY id",
            (project_id,),
        )],
        "decisions": [dict(row) for row in conn.execute(
            "SELECT id,title,body,author,status FROM decisions WHERE project_id=? ORDER BY id",
            (project_id,),
        )],
        "nodes": [dict(row) for row in conn.execute(
            "SELECT id,view,label,kind,detail,x,y FROM nodes WHERE project_id=? ORDER BY id",
            (project_id,),
        )],
        "edges": [dict(row) for row in conn.execute(
            "SELECT id,view,source_id,target_id,label FROM edges WHERE project_id=? ORDER BY id",
            (project_id,),
        )],
        "documents": [dict(row) for row in conn.execute(
            "SELECT doc_type,title,content,status,updated_by FROM documents WHERE project_id=? ORDER BY doc_type",
            (project_id,),
        )],
    }
    safe = sanitize_live_state_v015(state)
    safe["document_updates"] = []
    payload = json.dumps(
        {"state": safe, "source": tables},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _items_by_id(state: dict[str, Any], category: str, id_field: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(id_field) or "").strip().lower(): item
        for item in state.get(category, []) or []
        if isinstance(item, dict) and str(item.get(id_field) or "").strip()
    }


def rebase_conflicts(
    base: dict[str, Any], current: dict[str, Any], delta: dict[str, Any]
) -> list[str]:
    """Return only concurrent edits that target the same stable identity."""

    safe_base = sanitize_live_state_v015(base)
    safe_current = sanitize_live_state_v015(current)
    safe_delta = sanitize_live_state_v015(delta)
    desired = merge_structured_states(safe_base, safe_delta)
    conflicts: list[str] = []

    for field in safe_delta.get("project_updates", {}):
        before = safe_base.get("project_updates", {}).get(field)
        latest = safe_current.get("project_updates", {}).get(field)
        incoming = safe_delta.get("project_updates", {}).get(field)
        if latest != before and incoming != latest:
            conflicts.append(f"project_updates.{field}")

    for category, (id_field, _prefix, _semantic_fields) in CATEGORY_SPECS.items():
        base_items = _items_by_id(safe_base, category, id_field)
        current_items = _items_by_id(safe_current, category, id_field)
        desired_items = _items_by_id(desired, category, id_field)
        for incoming in safe_delta.get(category, []) or []:
            identifier = str(incoming.get(id_field) or "").strip().lower()
            if not identifier:
                continue
            before = base_items.get(identifier)
            latest = current_items.get(identifier)
            intended = desired_items.get(identifier)
            if latest != before and latest != intended:
                conflicts.append(f"{category}.{incoming.get(id_field)}")
    return sorted(set(conflicts))
