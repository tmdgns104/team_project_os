from __future__ import annotations

from typing import Any

PROJECT_FIELDS = {
    "name", "goal", "project_type", "problem", "users", "deliverables",
    "success_criteria", "scope", "current_state", "target_state", "constraints",
    "schedule", "team", "risks", "description",
}
PROJECT_TYPES = {
    "generic", "software", "ai_data", "embedded_hardware", "manufacturing_automation",
    "research_rnd", "business_process", "product_service", "education_content", "event_campaign",
}
DOC_TYPES = {
    "proposal", "plan", "milestone", "backlog", "requirements", "service_policy",
    "function_definition", "ia", "screen_design", "system_architecture", "data_flow", "api_design", "qa",
}
VIEWS = {"process", "architecture", "dataflow"}


def _text(value: Any, limit: int) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "").strip()[:limit]


def sanitize_live_state(state: dict[str, Any] | None) -> dict[str, Any]:
    src = state if isinstance(state, dict) else {}
    updates: dict[str, str] = {}
    raw_updates = src.get("project_updates") if isinstance(src.get("project_updates"), dict) else {}
    for field in PROJECT_FIELDS:
        value = _text(raw_updates.get(field), 120 if field == "name" else 4000)
        if value:
            updates[field] = value
    if updates.get("project_type") not in PROJECT_TYPES:
        updates.pop("project_type", None)

    requirements = []
    for raw in src.get("requirements", []) if isinstance(src.get("requirements"), list) else []:
        if not isinstance(raw, dict):
            continue
        title = _text(raw.get("title"), 300)
        if not title:
            continue
        requirements.append({
            "ref": _text(raw.get("ref"), 40),
            "type": _text(raw.get("type") or "Functional", 60),
            "title": title,
            "detail": _text(raw.get("detail"), 4000),
            "source": _text(raw.get("source") or raw.get("rationale") or "User / Design Session", 500),
            "priority": _text(raw.get("priority") or "TBD", 40),
            "acceptance_criteria": _text(raw.get("acceptance_criteria") or "TBD · 확인 필요", 2000),
            "verification": _text(raw.get("verification") or "Test / Review", 500),
            "owner": _text(raw.get("owner") or "TBD", 120),
            "traceability": _text(raw.get("traceability") or "Process/Task/Test 연결 예정", 500),
            "status": _text(raw.get("status") or "defined", 40),
        })

    decisions = []
    for raw in src.get("decisions", []) if isinstance(src.get("decisions"), list) else []:
        if not isinstance(raw, dict):
            continue
        title = _text(raw.get("title"), 300)
        if title:
            status = _text(raw.get("status") or "provisional", 40).lower()
            if status not in {
                "accepted", "confirmed", "provisional", "proposed", "pending",
                "rejected", "alternative",
            }:
                status = "provisional"
            decisions.append({
                "ref": _text(raw.get("ref"), 80),
                "title": title,
                "body": _text(raw.get("body"), 4000),
                "status": status,
            })

    document_updates = []
    for raw in src.get("document_updates", []) if isinstance(src.get("document_updates"), list) else []:
        if not isinstance(raw, dict):
            continue
        doc_type = _text(raw.get("doc_type"), 80)
        content = _text(raw.get("content"), 200000)
        if doc_type in DOC_TYPES and content:
            document_updates.append({"doc_type": doc_type, "content": content, "reason": _text(raw.get("reason"), 1000)})

    design_updates = []
    for raw in src.get("design_updates", []) if isinstance(src.get("design_updates"), list) else []:
        if not isinstance(raw, dict):
            continue
        view = _text(raw.get("view"), 40)
        if view not in VIEWS:
            continue
        nodes = []
        keys = set()
        for node in raw.get("nodes", []) if isinstance(raw.get("nodes"), list) else []:
            if not isinstance(node, dict):
                continue
            key = _text(node.get("key"), 80)
            label = _text(node.get("label"), 200)
            if not key or not label or key in keys:
                continue
            keys.add(key)
            nodes.append({"key": key, "label": label, "kind": _text(node.get("kind") or "component", 80), "detail": _text(node.get("detail"), 2000)})
        edges = []
        for edge in raw.get("edges", []) if isinstance(raw.get("edges"), list) else []:
            if not isinstance(edge, dict):
                continue
            source, target = _text(edge.get("source"), 80), _text(edge.get("target"), 80)
            if source in keys and target in keys and source != target:
                edges.append({"source": source, "target": target, "label": _text(edge.get("label"), 300)})
        if nodes:
            mode = _text(raw.get("mode") or "replace", 20)
            design_updates.append({
                "view": view,
                "mode": mode if mode in {"merge", "replace"} else "replace",
                "reason": _text(raw.get("reason"), 1000),
                "nodes": nodes[:50],
                "edges": edges[:100],
            })

    pending = []
    for raw in src.get("pending", []) if isinstance(src.get("pending"), list) else []:
        value = _text(raw, 1000)
        if value and value not in pending:
            pending.append(value)

    return {
        "project_updates": updates,
        "requirements": requirements[:50],
        "decisions": decisions[:40],
        "document_updates": document_updates[:13],
        "design_updates": design_updates[:3],
        "pending": pending[:30],
    }
