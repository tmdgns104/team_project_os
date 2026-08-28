from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from app.conversation import extract_json_object
from app.conversation_providers import ConversationMessage
from app.live_state_v015 import sanitize_live_state_v015
from local_bridge.providers import run_provider


REDACTED = "[REDACTED_SECRET]"
MAX_CHUNK_MESSAGES = 150
MAX_CHUNK_CHARACTERS = 150_000
MAX_TRANSCRIPT_CHARACTERS = 180_000

DISTILLER_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_updates": {"type": "object"},
        "requirements": {"type": "array", "items": {"type": "object"}},
        "decisions": {"type": "array", "items": {"type": "object"}},
        "milestones": {"type": "array", "items": {"type": "object"}},
        "backlog_items": {"type": "array", "items": {"type": "object"}},
        "functions": {"type": "array", "items": {"type": "object"}},
        "screens": {"type": "array", "items": {"type": "object"}},
        "interfaces": {"type": "array", "items": {"type": "object"}},
        "tests": {"type": "array", "items": {"type": "object"}},
        "policies": {"type": "array", "items": {"type": "object"}},
        "data_items": {"type": "array", "items": {"type": "object"}},
        "design_updates": {"type": "array", "items": {"type": "object"}},
        "pending": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "project_updates", "requirements", "decisions", "milestones",
        "backlog_items", "functions", "screens", "interfaces", "tests",
        "policies", "data_items", "design_updates", "pending",
    ],
    "additionalProperties": False,
}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.I | re.S),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b", re.I),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"(?i)(\b(?:api[_-]?key|access[_-]?key|secret|token|password|passwd|pwd|"
        r"private[_-]?key|client[_-]?secret)\b\s*[=:]\s*)([\"']?)[^\s,;\"']{4,}\2"
    ),
    re.compile(
        r"(?i)([?&](?:api[_-]?key|access[_-]?key|secret|token|password)=)[^&#\s]+"
    ),
)

CATEGORY_SPECS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "requirements": ("ref", "REQ", ("title", "detail")),
    "decisions": ("ref", "DEC", ("title", "body")),
    "milestones": ("id", "MS", ("task", "phase")),
    "backlog_items": ("id", "BL", ("title", "detail")),
    "functions": ("id", "FUNC", ("name", "normal_flow")),
    "screens": ("id", "SCR", ("name", "purpose")),
    "interfaces": ("id", "API", ("name", "path", "purpose")),
    "tests": ("id", "TC", ("expected", "steps", "requirement_refs")),
    "policies": ("id", "POL", ("policy", "category")),
    "data_items": ("id", "DATA", ("name", "fields")),
}


def redact_secrets(text: str) -> str:
    """Mask common credentials without retaining or reporting their original values."""

    redacted = str(text or "")
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 1 and "PRIVATE KEY" not in pattern.pattern and pattern.pattern.startswith("(?i)("):
            redacted = pattern.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redacted_messages(messages: list[ConversationMessage]) -> list[dict[str, Any]]:
    return [
        {
            "cursor": message.cursor,
            "role": message.role,
            "content": redact_secrets(message.content)[:40_000],
            "timestamp": message.timestamp,
        }
        for message in messages
    ]


def select_message_chunk(
    messages: list[ConversationMessage],
    *,
    after_cursor: int,
    to_cursor: int | None = None,
    max_messages: int = MAX_CHUNK_MESSAGES,
    max_characters: int = MAX_CHUNK_CHARACTERS,
) -> tuple[list[ConversationMessage], int]:
    """Return the next contiguous bounded range and the total remaining count."""

    eligible = [
        message
        for message in messages
        if message.cursor > after_cursor
        and (to_cursor is None or message.cursor <= to_cursor)
    ]
    selected: list[ConversationMessage] = []
    characters = 0
    for message in eligible:
        safe_length = len(redact_secrets(message.content)[:40_000])
        if selected and (
            len(selected) >= max_messages or characters + safe_length > max_characters
        ):
            break
        selected.append(message)
        characters += safe_length
    return selected, len(eligible)


def redact_structure(value: Any) -> Any:
    """Recursively redact model output before it can reach storage or logs."""

    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [redact_structure(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_structure(item) for key, item in value.items()}
    return value


def conversation_content_hash(
    provider: str,
    session_id: str,
    messages: list[dict[str, Any]],
) -> str:
    canonical = json.dumps(
        {
            "provider": provider,
            "session_id": session_id,
            "messages": [
                {
                    "cursor": item.get("cursor"),
                    "role": item.get("role"),
                    "content": item.get("content"),
                }
                for item in messages
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_manual_transcript(transcript: str) -> list[ConversationMessage]:
    """Parse a simple pasted transcript while keeping paste as a fallback path."""

    text = str(transcript or "").strip()
    if not text:
        return []
    role_pattern = re.compile(
        r"^(user|human|사용자|나|assistant|ai|codex|claude|opencode)\s*:\s*(.*)$",
        re.I,
    )
    parsed: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = role_pattern.match(line.strip())
        if match:
            raw_role = match.group(1).lower()
            role = "user" if raw_role in {"user", "human", "사용자", "나"} else "assistant"
            parsed.append((role, [match.group(2)]))
        elif parsed:
            parsed[-1][1].append(line)
    if not parsed:
        parsed = [("user", [text])]
    return [
        ConversationMessage(cursor=index, role=role, content="\n".join(lines).strip(), timestamp="")
        for index, (role, lines) in enumerate(parsed)
        if "\n".join(lines).strip()
    ]


def _semantic_text(item: dict[str, Any], fields: tuple[str, ...]) -> str:
    values = [str(item.get(field) or "").strip().lower() for field in fields]
    combined = " ".join(value for value in values if value)
    return re.sub(r"[^0-9a-z가-힣]+", " ", combined).strip()[:500]


def _stable_import_id(prefix: str, category: str, item: dict[str, Any], fields: tuple[str, ...]) -> str:
    semantic = _semantic_text(item, fields) or json.dumps(item, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{category}:{semantic}".encode("utf-8")).hexdigest()[:8].upper()
    return f"{prefix}-IMP-{digest}"


def _normal_identity(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def ensure_stable_ids(delta: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assign deterministic IDs and reuse a current semantic match when possible."""

    current = current or {}
    for category, (id_field, prefix, semantic_fields) in CATEGORY_SPECS.items():
        current_items = [item for item in current.get(category, []) if isinstance(item, dict)]
        semantic_to_id = {
            _semantic_text(item, semantic_fields): str(item.get(id_field) or "")
            for item in current_items
            if _semantic_text(item, semantic_fields) and item.get(id_field)
        }
        for item in delta.get(category, []) if isinstance(delta.get(category), list) else []:
            if not isinstance(item, dict):
                continue
            existing_id = str(item.get(id_field) or "").strip()
            if existing_id:
                continue
            semantic = _semantic_text(item, semantic_fields)
            item[id_field] = semantic_to_id.get(semantic) or _stable_import_id(
                prefix, category, item, semantic_fields
            )
    return delta


def normalize_import_delta(model_output: str, current: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = extract_json_object(model_output)
    safe = sanitize_live_state_v015(parsed)
    return ensure_stable_ids(safe, current)


def _merge_catalog(
    current_items: list[dict[str, Any]],
    delta_items: list[dict[str, Any]],
    *,
    id_field: str,
    semantic_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    result = [dict(item) for item in current_items if isinstance(item, dict)]

    def identity(item: dict[str, Any]) -> tuple[str, str]:
        identifier = _normal_identity(item.get(id_field))
        semantic = _normal_identity(_semantic_text(item, semantic_fields))
        return identifier, semantic

    for incoming in delta_items:
        if not isinstance(incoming, dict):
            continue
        incoming_id, incoming_semantic = identity(incoming)
        match_index = None
        for index, existing in enumerate(result):
            existing_id, existing_semantic = identity(existing)
            if incoming_id and incoming_id == existing_id:
                match_index = index
                break
            if incoming_semantic and incoming_semantic == existing_semantic:
                match_index = index
                break
        if match_index is None:
            result.append(dict(incoming))
        else:
            result[match_index] = {**result[match_index], **incoming}
    return result


def _merge_designs(
    current_designs: list[dict[str, Any]], delta_designs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_view = {str(item.get("view")): dict(item) for item in current_designs if item.get("view")}
    for incoming in delta_designs:
        view = str(incoming.get("view") or "")
        if not view:
            continue
        if incoming.get("mode") == "replace" or view not in by_view:
            by_view[view] = dict(incoming)
            continue
        existing = by_view[view]
        nodes = [dict(item) for item in existing.get("nodes", []) if isinstance(item, dict)]
        node_index = {
            _normal_identity(item.get("key") or item.get("label")): index
            for index, item in enumerate(nodes)
        }
        for node in incoming.get("nodes", []):
            if not isinstance(node, dict):
                continue
            marker = _normal_identity(node.get("key") or node.get("label"))
            if marker in node_index:
                index = node_index[marker]
                nodes[index] = {**nodes[index], **node}
            else:
                node_index[marker] = len(nodes)
                nodes.append(dict(node))
        edges = [dict(item) for item in existing.get("edges", []) if isinstance(item, dict)]
        edge_markers = {
            (_normal_identity(item.get("source")), _normal_identity(item.get("target")), _normal_identity(item.get("label")))
            for item in edges
        }
        for edge in incoming.get("edges", []):
            if not isinstance(edge, dict):
                continue
            marker = (
                _normal_identity(edge.get("source")),
                _normal_identity(edge.get("target")),
                _normal_identity(edge.get("label")),
            )
            if marker not in edge_markers:
                edges.append(dict(edge))
                edge_markers.add(marker)
        by_view[view] = {**existing, **incoming, "mode": "merge", "nodes": nodes, "edges": edges}
    return [by_view[view] for view in ("process", "architecture", "dataflow") if view in by_view]


def merge_structured_states(current: dict[str, Any] | None, delta: dict[str, Any]) -> dict[str, Any]:
    old = sanitize_live_state_v015(current or {})
    incoming = ensure_stable_ids(sanitize_live_state_v015(delta), old)
    merged: dict[str, Any] = {
        "project_updates": {**old.get("project_updates", {}), **incoming.get("project_updates", {})},
        "document_updates": _merge_catalog(
            old.get("document_updates", []),
            incoming.get("document_updates", []),
            id_field="doc_type",
            semantic_fields=("doc_type",),
        ),
        "design_updates": _merge_designs(
            old.get("design_updates", []), incoming.get("design_updates", [])
        ),
        "pending": [],
    }
    for category, (id_field, _prefix, semantic_fields) in CATEGORY_SPECS.items():
        merged[category] = _merge_catalog(
            old.get(category, []),
            incoming.get(category, []),
            id_field=id_field,
            semantic_fields=semantic_fields,
        )
    for item in [*old.get("pending", []), *incoming.get("pending", [])]:
        text = str(item or "").strip()
        if text and text not in merged["pending"]:
            merged["pending"].append(text)
    return sanitize_live_state_v015(merged)


def _item_label(category: str, item: dict[str, Any]) -> str:
    id_field = CATEGORY_SPECS[category][0]
    identifier = str(item.get(id_field) or "").strip()
    name = str(
        item.get("title")
        or item.get("name")
        or item.get("task")
        or item.get("policy")
        or item.get("expected")
        or ""
    ).strip()
    return " ".join(part for part in (identifier, name) if part)


def summarize_changes(current: dict[str, Any], merged: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    summary: dict[str, list[dict[str, str]]] = {"project_updates": []}
    old_updates = current.get("project_updates", {}) or {}
    for field, value in (merged.get("project_updates", {}) or {}).items():
        if value != old_updates.get(field):
            summary["project_updates"].append(
                {"op": "~" if field in old_updates else "+", "label": f"{field}: {value}"}
            )
    for category, (id_field, _prefix, semantic_fields) in CATEGORY_SPECS.items():
        old_items = current.get(category, []) or []
        old_by_id = {_normal_identity(item.get(id_field)): item for item in old_items if item.get(id_field)}
        old_semantics = {_normal_identity(_semantic_text(item, semantic_fields)): item for item in old_items}
        changes: list[dict[str, str]] = []
        for item in merged.get(category, []) or []:
            identifier = _normal_identity(item.get(id_field))
            semantic = _normal_identity(_semantic_text(item, semantic_fields))
            previous = old_by_id.get(identifier) if identifier else old_semantics.get(semantic)
            if previous is None:
                changes.append({"op": "+", "label": _item_label(category, item)})
            elif previous != item:
                changes.append({"op": "~", "label": _item_label(category, item)})
        summary[category] = changes
    old_designs = {item.get("view"): item for item in current.get("design_updates", []) or []}
    summary["design_updates"] = [
        {
            "op": "~" if item.get("view") in old_designs else "+",
            "label": f"{item.get('view')} · nodes {len(item.get('nodes', []))} / edges {len(item.get('edges', []))}",
        }
        for item in merged.get("design_updates", []) or []
        if old_designs.get(item.get("view")) != item
    ]
    old_pending = set(current.get("pending", []) or [])
    summary["pending"] = [
        {"op": "+", "label": str(item)}
        for item in merged.get("pending", []) or []
        if item not in old_pending
    ]
    return summary


def build_distiller_prompt(
    *,
    messages: list[dict[str, Any]],
    current_state: dict[str, Any],
    project_name: str,
) -> str:
    transcript = "\n\n".join(
        f"[{item.get('cursor')}] {str(item.get('role')).upper()}:\n{item.get('content')}"
        for item in messages
    )
    if len(transcript) > MAX_TRANSCRIPT_CHARACTERS:
        raise ValueError("Selected conversation range is too large; choose a smaller range")
    current_json = json.dumps(
        redact_structure(current_state), ensure_ascii=False, separators=(",", ":")
    )
    return f"""You are the Conversation Distiller for Team Project OS V0.16.

Extract only durable project meaning from a previously completed native AI conversation.
Do not continue the conversation and do not quote the transcript into documents.

TARGET PROJECT
{project_name}

CURRENT V0.15 STRUCTURED STATE
{current_json}

NEW REDACTED MESSAGE RANGE
{transcript}

RULES
- Return exactly one JSON object and no markdown fence.
- Use the existing V0.15 keys shown in the output contract. Do not invent a parallel schema.
- Include only additions or corrections supported by the conversation.
- Reuse an existing stable ID when the same item already exists. A missing ID may be left empty;
  Project OS assigns a deterministic import ID.
- ACCEPTED requires explicit user agreement such as "하자", "선택", or an equivalent clear commitment.
- A suggestion or reversible AI working choice is PROVISIONAL.
- Unresolved matters are PENDING. A considered but unselected option is REJECTED or ALTERNATIVE.
- Cost, security/permissions, privacy/legal, and physical equipment safety remain PENDING unless
  the human clearly approves them.
- Never output credentials, keys, tokens, passwords, private keys, environment secret values, or
  sensitive raw excerpts. Use {REDACTED} if a sensitive fact must be referenced.
- Build traceability references where the conversation supports them.
- Prefer merge-mode designs. Never delete existing detail merely because this range omits it.

OUTPUT CONTRACT
{{
  "project_updates": {{}},
  "requirements": [{{"ref":"REQ-* or empty","type":"Functional|Non-Functional","title":"","detail":"","source":"Native AI Conversation","priority":"","acceptance_criteria":"","verification":"","owner":"","traceability":"","status":"defined"}}],
  "decisions": [{{"ref":"DEC-* or empty","title":"","body":"reason, impact, and alternatives","status":"accepted|provisional|pending|rejected|alternative"}}],
  "milestones": [{{"id":"MS-* or empty","phase":"","task":"","start_week":"","end_week":"","owner":"","status":"","deliverable":"","exit_criteria":"","requirement_refs":""}}],
  "backlog_items": [{{"id":"BL-* or empty","epic":"","title":"","detail":"","priority":"","estimate":"","owner":"","status":"","requirement_refs":"","dependencies":"","definition_of_ready":"","definition_of_done":""}}],
  "functions": [{{"id":"FUNC-* or empty","name":"","actor":"","trigger":"","preconditions":"","inputs":"","business_rules":"","normal_flow":"","exception_flow":"","outputs":"","acceptance_criteria":"","requirement_refs":""}}],
  "screens": [{{"id":"SCR-* or empty","name":"","purpose":"","users":"","entry_conditions":"","components":"","actions":"","validation":"","states":"","api_refs":"","requirement_refs":""}}],
  "interfaces": [{{"id":"API-* or IF-* or empty","kind":"","method":"","path":"","name":"","purpose":"","auth":"","request":"","response":"","errors":"","timeout_retry":"","idempotency":"","versioning":"","requirement_refs":""}}],
  "tests": [{{"id":"TC-* or empty","requirement_refs":"","priority":"","preconditions":"","steps":"","expected":"","evidence":"","pass_fail":"","status":"Not Run"}}],
  "policies": [{{"id":"POL-* or empty","category":"","policy":"","target":"","monitoring":"","response":"","owner":"","status":"","requirement_refs":""}}],
  "data_items": [{{"id":"DATA-* or empty","name":"","source":"","producer":"","fields":"","validation":"","processing":"","destination":"","protocol":"","retention":"","failure_handling":"","requirement_refs":""}}],
  "design_updates": [{{"view":"process|architecture|dataflow","mode":"merge","reason":"","nodes":[{{"key":"","label":"","kind":"","detail":""}}],"edges":[{{"source":"","target":"","label":""}}]}}],
  "pending": []
}}
"""


def distill_conversation(
    *,
    messages: list[dict[str, Any]],
    current_state: dict[str, Any],
    project_name: str,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Run structured inference in a disposable directory with agent tools disabled."""

    prompt = build_distiller_prompt(
        messages=messages,
        current_state=current_state,
        project_name=project_name,
    )
    with tempfile.TemporaryDirectory(prefix="project-os-distiller-") as directory:
        isolation_root = Path(directory).resolve()
        schema_path = isolation_root / "conversation-delta.schema.json"
        schema_path.write_text(
            json.dumps(DISTILLER_OUTPUT_SCHEMA, ensure_ascii=False), encoding="utf-8"
        )
        result = run_provider(
            "codex",
            prompt,
            cwd=isolation_root,
            purpose="conversation-import",
            timeout_seconds=15 * 60,
            output_schema=schema_path,
            environment=_distiller_environment(isolation_root),
        )
    if not result.ok:
        raise RuntimeError(f"Codex distiller failed with exit code {result.returncode}")
    return redact_structure(normalize_import_delta(redact_secrets(result.stdout), current_state))


def _distiller_environment(isolation_root: Path) -> dict[str, str]:
    """Allow only process/runtime paths; omit project configuration and credential env vars."""

    allowed = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "APPDATA",
        "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }
    codex_home = os.getenv("CODEX_HOME") or str(Path.home() / ".codex")
    environment.update(
        {
            "CODEX_HOME": codex_home,
            "TEMP": str(isolation_root),
            "TMP": str(isolation_root),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )
    return environment
