from __future__ import annotations

from typing import Any

from app.live_state import sanitize_live_state as sanitize_v014

CATALOG_LIMITS = {
    "milestones": 60,
    "backlog_items": 100,
    "functions": 100,
    "screens": 80,
    "interfaces": 100,
    "tests": 150,
    "policies": 80,
    "data_items": 120,
}


def _text(value: Any, limit: int = 4000) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value or "").strip()[:limit]


def _catalog(src: dict[str, Any], key: str, id_keys: tuple[str, ...], fields: tuple[str, ...]) -> list[dict[str, str]]:
    raw_list = src.get(key, []) if isinstance(src.get(key), list) else []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        ident = ""
        for id_key in id_keys:
            ident = _text(raw.get(id_key), 80)
            if ident:
                break
        if not ident or ident.lower() in seen:
            continue
        seen.add(ident.lower())
        item = {"id": ident}
        for field in fields:
            item[field] = _text(raw.get(field), 4000)
        result.append(item)
        if len(result) >= CATALOG_LIMITS[key]:
            break
    return result


def sanitize_live_state_v015(state: dict[str, Any] | None) -> dict[str, Any]:
    src = state if isinstance(state, dict) else {}
    out = sanitize_v014(src)
    out["milestones"] = _catalog(src, "milestones", ("id", "ref"), (
        "phase", "task", "start_week", "end_week", "owner", "status", "deliverable", "exit_criteria", "requirement_refs"
    ))
    out["backlog_items"] = _catalog(src, "backlog_items", ("id", "ref"), (
        "epic", "title", "detail", "priority", "estimate", "owner", "status", "requirement_refs", "dependencies", "definition_of_ready", "definition_of_done"
    ))
    out["functions"] = _catalog(src, "functions", ("id", "ref"), (
        "name", "actor", "trigger", "preconditions", "inputs", "business_rules", "normal_flow", "exception_flow", "outputs", "acceptance_criteria", "requirement_refs"
    ))
    out["screens"] = _catalog(src, "screens", ("id", "ref"), (
        "name", "purpose", "users", "entry_conditions", "components", "actions", "validation", "states", "api_refs", "requirement_refs"
    ))
    out["interfaces"] = _catalog(src, "interfaces", ("id", "ref"), (
        "kind", "method", "path", "name", "purpose", "auth", "request", "response", "errors", "timeout_retry", "idempotency", "versioning", "requirement_refs"
    ))
    out["tests"] = _catalog(src, "tests", ("id", "ref"), (
        "requirement_refs", "priority", "preconditions", "steps", "expected", "evidence", "pass_fail", "status"
    ))
    out["policies"] = _catalog(src, "policies", ("id", "ref"), (
        "category", "policy", "target", "monitoring", "response", "owner", "status", "requirement_refs"
    ))
    out["data_items"] = _catalog(src, "data_items", ("id", "ref"), (
        "name", "source", "producer", "fields", "validation", "processing", "destination", "protocol", "retention", "failure_handling", "requirement_refs"
    ))
    return out
