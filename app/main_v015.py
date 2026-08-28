from __future__ import annotations

from typing import Any

from app import main as core
from app import main_v014 as v014
from app.live_state_v015 import sanitize_live_state_v015
from app.materializer_v015 import DOC_TYPES, document_regressed, graph_quality, materialize_documents

core.app.version = "0.15.0"

_original_apply = v014._original_apply_live_draft_state


def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    return materialize_documents(brief, sanitize_live_state_v015(state))


def _snapshot_documents(conn, project_id: int) -> dict[str, dict[str, Any]]:
    return {row["doc_type"]: dict(row) for row in conn.execute("SELECT * FROM documents WHERE project_id=?", (project_id,)).fetchall()}


def _snapshot_graphs(conn, project_id: int) -> dict[str, dict[str, list[dict[str, Any]]]]:
    out = {}
    for view in ("process", "architecture", "dataflow"):
        nodes = [dict(row) for row in conn.execute("SELECT * FROM nodes WHERE project_id=? AND view=? ORDER BY id", (project_id, view)).fetchall()]
        ids = {node["id"] for node in nodes}
        edges = [dict(row) for row in conn.execute("SELECT * FROM edges WHERE project_id=? AND view=? ORDER BY id", (project_id, view)).fetchall() if row["source_id"] in ids and row["target_id"] in ids]
        out[view] = {"nodes": nodes, "edges": edges}
    return out


def _restore_graph(conn, project_id: int, view: str, graph: dict[str, list[dict[str, Any]]]) -> None:
    conn.execute("DELETE FROM edges WHERE project_id=? AND view=?", (project_id, view))
    conn.execute("DELETE FROM nodes WHERE project_id=? AND view=?", (project_id, view))
    old_to_new = {}
    for node in graph.get("nodes", []):
        cur = conn.execute(
            "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",
            (project_id, view, node.get("label", ""), node.get("kind", "component"), node.get("detail", ""), node.get("x", 0), node.get("y", 0)),
        )
        old_to_new[node["id"]] = cur.lastrowid
    for edge in graph.get("edges", []):
        source = old_to_new.get(edge.get("source_id")); target = old_to_new.get(edge.get("target_id"))
        if source and target:
            conn.execute(
                "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",
                (project_id, view, source, target, edge.get("label", "")),
            )


def apply_live_draft_state(conn, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft"):
    safe = sanitize_live_state_v015(state)
    before_docs = _snapshot_documents(conn, project_id) if lifecycle == "active" else {}
    before_graphs = _snapshot_graphs(conn, project_id) if lifecycle == "active" else {}

    result = _original_apply(conn, project_id, member_name, safe, lifecycle=lifecycle)

    if lifecycle == "active":
        after_docs = _snapshot_documents(conn, project_id)
        for doc_type in DOC_TYPES:
            old = before_docs.get(doc_type); new = after_docs.get(doc_type)
            if not old or not new:
                continue
            if document_regressed(old.get("content", ""), new.get("content", "")):
                conn.execute(
                    "UPDATE documents SET content=?,updated_by=?,updated_at=? WHERE id=?",
                    (old["content"], old.get("updated_by") or "Live Design", core.now(), new["id"]),
                )

        for view, old_graph in before_graphs.items():
            new_nodes = [dict(row) for row in conn.execute("SELECT * FROM nodes WHERE project_id=? AND view=?", (project_id, view)).fetchall()]
            ids = {node["id"] for node in new_nodes}
            new_edges = [dict(row) for row in conn.execute("SELECT * FROM edges WHERE project_id=? AND view=?", (project_id, view)).fetchall() if row["source_id"] in ids and row["target_id"] in ids]
            if graph_quality(old_graph["nodes"], old_graph["edges"]) > graph_quality(new_nodes, new_edges) + 20:
                _restore_graph(conn, project_id, view, old_graph)
    return result


core.build_live_draft_documents = build_live_draft_documents
core.apply_live_draft_state = apply_live_draft_state

app = core.app
