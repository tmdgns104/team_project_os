from __future__ import annotations

import re
from typing import Any

from app import main as base
from app.delivery_documents import DOCUMENT_ORDER, build_delivery_documents, build_requirements_register
from app.live_state import sanitize_live_state

# Keep the proven V0.13 API/DB implementation and replace only the document/live-state
# policy layer. Existing endpoint functions resolve these globals at call time.
base.app.version = "0.14.1"
base.build_initial_documents = build_delivery_documents

_BASE_DOCS = build_delivery_documents({})
base.DOCUMENT_TEMPLATES = [
    (doc_type, title, _BASE_DOCS[doc_type])
    for doc_type, title in DOCUMENT_ORDER
]

_original_build_live_draft_documents = base.build_live_draft_documents
_original_apply_live_draft_state = base.apply_live_draft_state


_DOC_MARKERS = {
    "proposal": ("Executive Summary", "Scope", "Success", "Risk", "Approval"),
    "plan": ("WBS", "RACI", "Dependency", "Risk", "Quality", "Change"),
    "milestone": ("Gantt", "Phase", "Start Week", "End Week", "Owner", "Status", "Deliverable", "Exit Criteria"),
    "backlog": ("Priority", "Estimate", "Dependency", "Definition of Ready", "Definition of Done"),
    "requirements": ("Acceptance Criteria", "Verification", "Traceability", "Priority", "Source"),
    "service_policy": ("SLI", "SLO", "Incident", "RPO", "RTO", "Rollback"),
    "function_definition": ("Preconditions", "Business Rules", "Normal Flow", "Exception", "Acceptance"),
    "ia": ("Navigation", "Page", "User Journey", "Permission"),
    "screen_design": ("Component", "Validation", "Loading", "Empty", "Error", "API"),
    "system_architecture": ("System Context", "Container", "Interface", "Deployment", "Risk"),
    "data_flow": ("Source", "Transform", "Destination", "Protocol", "Data Dictionary", "Retention"),
    "api_design": ("openapi", "Endpoint", "Error", "Timeout", "Retry", "Idempotency", "Deprecation"),
    "qa": ("Test Strategy", "Test ID", "Preconditions", "Expected", "Evidence", "Pass", "Release"),
}


def _document_quality(doc_type: str, content: str) -> int:
    """Estimate whether a document is delivery-grade enough to avoid regression on /apply.

    This is intentionally structural rather than semantic. /apply may enrich a draft,
    but it must not replace a detailed Live Draft with a shorter summary/template.
    """
    text = str(content or "")
    if not text.strip():
        return 0
    lower = text.lower()
    score = min(len(text), 30000) // 20
    score += len(re.findall(r"(?m)^#{1,6}\s+", text)) * 70
    score += len(re.findall(r"(?m)^\|.*\|\s*$", text)) * 18
    score += len(re.findall(r"\b(?:REQ|FUNC|API|SCR|TASK|TC|QA|EVD)-[A-Z0-9-]+\b", text, re.I)) * 20
    for marker in _DOC_MARKERS.get(doc_type, ()):
        if marker.lower() in lower:
            score += 130
    if doc_type == "milestone":
        score += len(re.findall(r"\bW\d+\b", text, re.I)) * 18
        score += len(re.findall(r"\b(?:Phase|W)\s*\d+\b", text, re.I)) * 12
    return score


def _snapshot_documents(conn, project_id: int) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT doc_type,content,status,updated_by FROM documents WHERE project_id=?",
        (project_id,),
    ).fetchall()
    return {str(row["doc_type"]): dict(row) for row in rows}


def _preserve_richer_documents(conn, project_id: int, member_name: str, before: dict[str, dict[str, Any]]) -> list[str]:
    after = _snapshot_documents(conn, project_id)
    preserved: list[str] = []
    for doc_type, old in before.items():
        old_content = str(old.get("content") or "")
        new_content = str((after.get(doc_type) or {}).get("content") or "")
        if not old_content.strip():
            continue
        # A Live Draft is the user's visible work product. Promotion may improve it,
        # but a shorter or structurally poorer Distiller rewrite must never replace it.
        old_score = _document_quality(doc_type, old_content)
        new_score = _document_quality(doc_type, new_content)
        materially_longer = len(old_content) > max(500, int(len(new_content) * 1.15))
        if old_score > new_score or materially_longer:
            conn.execute(
                "UPDATE documents SET content=?,status=?,updated_by=?,updated_at=? WHERE project_id=? AND doc_type=?",
                (
                    old_content,
                    old.get("status") or "draft",
                    f"Apply Preserve / {member_name}",
                    base.now(),
                    project_id,
                    doc_type,
                ),
            )
            preserved.append(doc_type)
    return preserved


def _snapshot_designs(conn, project_id: int) -> list[dict[str, Any]]:
    nodes = [dict(row) for row in conn.execute(
        "SELECT id,view,label,kind,detail FROM nodes WHERE project_id=? ORDER BY id",
        (project_id,),
    ).fetchall()]
    edges = [dict(row) for row in conn.execute(
        "SELECT view,source_id,target_id,label FROM edges WHERE project_id=? ORDER BY id",
        (project_id,),
    ).fetchall()]
    by_view: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        by_view.setdefault(str(node["view"]), []).append(node)
    result: list[dict[str, Any]] = []
    for view, view_nodes in by_view.items():
        keys = {int(node["id"]): f"live-{view}-{node['id']}" for node in view_nodes}
        graph_nodes = [
            {
                "key": keys[int(node["id"])],
                "label": str(node.get("label") or ""),
                "kind": str(node.get("kind") or "component"),
                "detail": str(node.get("detail") or ""),
            }
            for node in view_nodes
        ]
        graph_edges = []
        for edge in edges:
            if str(edge.get("view")) != view:
                continue
            source = keys.get(int(edge["source_id"]))
            target = keys.get(int(edge["target_id"]))
            if source and target:
                graph_edges.append({
                    "source": source,
                    "target": target,
                    "label": str(edge.get("label") or ""),
                })
        result.append({
            "view": view,
            "mode": "replace",
            "reason": "Preserved from richer Live Draft during /apply",
            "nodes": graph_nodes,
            "edges": graph_edges,
        })
    return result


def _graph_quality(graph: dict[str, Any] | None) -> int:
    if not isinstance(graph, dict):
        return 0
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    score = len(nodes) * 20 + len(edges) * 16
    score += sum(5 for node in nodes if isinstance(node, dict) and str(node.get("detail") or "").strip())
    score += sum(3 for edge in edges if isinstance(edge, dict) and str(edge.get("label") or "").strip())
    return score


def _preserve_richer_designs(state: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    safe = dict(state)
    incoming = {
        str(item.get("view")): item
        for item in (safe.get("design_updates") or [])
        if isinstance(item, dict) and item.get("view")
    }
    for graph in existing:
        view = str(graph.get("view") or "")
        if view and _graph_quality(graph) > _graph_quality(incoming.get(view)):
            incoming[view] = graph
    safe["design_updates"] = list(incoming.values())
    return safe


def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    safe_state = sanitize_live_state(state)
    docs = _original_build_live_draft_documents(brief, safe_state)
    # The base function already keeps all 13 docs and adds live graph snapshots.
    # Replace only the requirements register with the richer ISO-29148-inspired view.
    if safe_state.get("requirements"):
        docs["requirements"] = build_requirements_register(brief, safe_state["requirements"])
    return docs


def apply_live_draft_state(conn, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft"):
    # A malformed AI delta must never poison all subsequent design turns.
    safe_state = sanitize_live_state(state)
    before_docs: dict[str, dict[str, Any]] = {}
    if lifecycle == "active":
        before_docs = _snapshot_documents(conn, project_id)
        safe_state = _preserve_richer_designs(safe_state, _snapshot_designs(conn, project_id))

    result = _original_apply_live_draft_state(
        conn,
        project_id,
        member_name,
        safe_state,
        lifecycle=lifecycle,
    )

    if lifecycle == "active":
        preserved = _preserve_richer_documents(conn, project_id, member_name, before_docs)
        if preserved:
            base.add_activity(
                conn,
                project_id,
                "document",
                "Apply 비퇴행 보호 · 더 풍부한 Live Draft 문서 보존: " + ", ".join(preserved),
                member_name,
            )
    return result


base.build_live_draft_documents = build_live_draft_documents
base.apply_live_draft_state = apply_live_draft_state

# Export the same FastAPI application with the V0.14.1 policy layer installed.
app = base.app
