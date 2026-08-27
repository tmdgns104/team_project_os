from __future__ import annotations

import json
from typing import Any

from app.project_intake import FIELD_GUIDE, PROJECT_TYPES, evaluate_intake

PROJECT_FIELDS = (
    "name",
    "goal",
    "project_type",
    "problem",
    "users",
    "deliverables",
    "success_criteria",
    "scope",
    "current_state",
    "target_state",
    "constraints",
    "schedule",
    "team",
    "risks",
    "description",
)

ALLOWED_DOCUMENT_TYPES = {
    "proposal",
    "plan",
    "milestone",
    "backlog",
    "requirements",
    "service_policy",
    "function_definition",
    "ia",
    "screen_design",
    "system_architecture",
    "data_flow",
    "api_design",
    "qa",
}


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first complete JSON object from common CLI model output."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("AI output is empty")
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    in_string = False
    escaped = False
    depth = 0
    start = None
    for index, char in enumerate(raw):
        if start is None:
            if char == "{":
                start = index
                depth = 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = raw[start : index + 1]
                value = json.loads(candidate)
                if not isinstance(value, dict):
                    raise ValueError("AI JSON root must be an object")
                return value
    raise ValueError("No complete JSON object found in AI output")


def normalize_ai_result(text: str) -> dict[str, Any]:
    data = extract_json_object(text)
    updates_in = data.get("project_updates") if isinstance(data.get("project_updates"), dict) else {}
    updates: dict[str, str] = {}
    for field in PROJECT_FIELDS:
        value = updates_in.get(field)
        if value is not None and str(value).strip():
            updates[field] = _clip(value, 4000 if field != "name" else 120)
    if updates.get("project_type") not in PROJECT_TYPES:
        updates.pop("project_type", None)

    requirements = []
    for item in data.get("requirements", []) if isinstance(data.get("requirements"), list) else []:
        if not isinstance(item, dict):
            continue
        title = _clip(item.get("title"), 300)
        if not title:
            continue
        requirements.append({
            "ref": _clip(item.get("ref"), 40),
            "title": title,
            "detail": _clip(item.get("detail"), 4000),
            "status": _clip(item.get("status") or "defined", 40),
        })

    decisions = []
    for item in data.get("decisions", []) if isinstance(data.get("decisions"), list) else []:
        if not isinstance(item, dict):
            continue
        title = _clip(item.get("title"), 300)
        if title:
            decisions.append({
                "title": title,
                "body": _clip(item.get("body"), 4000),
                "status": _clip(item.get("status") or "proposed", 40),
            })

    document_updates = []
    for item in data.get("document_updates", []) if isinstance(data.get("document_updates"), list) else []:
        if not isinstance(item, dict):
            continue
        doc_type = _clip(item.get("doc_type"), 80)
        content = _clip(item.get("content"), 200000)
        if doc_type in ALLOWED_DOCUMENT_TYPES and content:
            document_updates.append({
                "doc_type": doc_type,
                "content": content,
                "reason": _clip(item.get("reason"), 1000),
            })

    pending = []
    for item in data.get("pending", []) if isinstance(data.get("pending"), list) else []:
        value = _clip(item, 1000)
        if value:
            pending.append(value)

    return {
        "reply": _clip(data.get("reply") or "프로젝트 정보를 정리했습니다.", 12000),
        "project_updates": updates,
        "requirements": requirements[:30],
        "decisions": decisions[:20],
        "document_updates": document_updates[:13],
        "pending": pending[:20],
    }


def combine_proposals(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    old = previous or {}
    merged = {
        "reply": current.get("reply", ""),
        "project_updates": {**old.get("project_updates", {}), **current.get("project_updates", {})},
        "requirements": [],
        "decisions": [],
        "document_updates": [],
        "pending": [],
    }

    def merge_list(key: str, identity):
        values = []
        seen = set()
        for item in [*old.get(key, []), *current.get(key, [])]:
            marker = identity(item)
            if marker in seen:
                values = [x for x in values if identity(x) != marker]
            seen.add(marker)
            values.append(item)
        return values

    merged["requirements"] = merge_list("requirements", lambda x: x.get("ref") or x.get("title"))[-30:]
    merged["decisions"] = merge_list("decisions", lambda x: x.get("title"))[-20:]
    merged["document_updates"] = merge_list("document_updates", lambda x: x.get("doc_type"))[-13:]
    pending_seen = []
    for item in [*old.get("pending", []), *current.get("pending", [])]:
        if item and item not in pending_seen:
            pending_seen.append(item)
    merged["pending"] = pending_seen[-20:]
    return merged


def merge_project_brief(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current or {})
    for field in PROJECT_FIELDS:
        if field in updates and str(updates[field]).strip():
            merged[field] = updates[field]
    if merged.get("project_type") not in PROJECT_TYPES:
        merged["project_type"] = "generic"
    return merged


def build_interviewer_prompt(
    *,
    project_id: int,
    brief: dict[str, Any],
    messages: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    previous_pending: dict[str, Any] | None = None,
) -> str:
    ptype = brief.get("project_type") or "generic"
    meta = PROJECT_TYPES.get(ptype, PROJECT_TYPES["generic"])
    quality = evaluate_intake(brief)
    field_state = []
    for field in PROJECT_FIELDS:
        guide = FIELD_GUIDE.get(field, {})
        value = str(brief.get(field) or "").strip()
        field_state.append(f"- {field} ({guide.get('label', field)}): {value or '[미정]'}")

    history = "\n".join(
        f"{str(m.get('role', '')).upper()}: {str(m.get('content', ''))[:5000]}" for m in messages[-16:]
    ) or "- no conversation yet"
    docs = "\n\n".join(
        f"[{d.get('doc_type')} / {d.get('title')} / status={d.get('status')}]\n{str(d.get('content') or '')[:900]}"
        for d in documents
    )
    previous = json.dumps(previous_pending or {}, ensure_ascii=False)

    return f"""You are the Project Interviewer inside Team Project OS.
The user is defining ANY kind of project: software, AI/data, embedded/hardware, manufacturing, R&D, business process, product/service, education/content, event/campaign, or another domain.

MISSION
- Continue a natural Korean conversation that helps the user define the project from zero.
- Extract facts the user actually provided into structured project fields.
- Ask only 1 to 3 high-value questions at a time; do not interrogate with a long checklist.
- Never invent budget, schedule, KPI, users, technology, architecture, policy, or requirements. Unknown facts stay unknown or become pending questions.
- Do not ask again for information already present unless there is a contradiction.
- If the user corrects earlier information, propose the corrected value.
- If the user asks to write or revise a project document, you may propose a complete replacement for that document in document_updates.
- Do NOT edit files, run commands, browse, or change a repository. This turn is conversation + structured JSON only.
- AI suggestions are proposals, not approved project facts. The server will show a diff and the human decides what to apply.

PROJECT
Project ID: {project_id}
Detected type: {meta['label']}
Type focus: {meta['focus']}
Current intake quality: {quality['score']}/100 ({quality['level']})

CURRENT STRUCTURED PROJECT BRIEF
{chr(10).join(field_state)}

TYPE-SPECIFIC QUESTIONS TO CONSIDER
{chr(10).join('- ' + q for q in meta['extra_questions'])}

CONVERSATION HISTORY
{history}

CURRENT PROJECT DOCUMENT EXCERPTS
{docs or '- no documents'}

UNAPPLIED PROPOSALS FROM EARLIER TURNS
{previous}

OUTPUT CONTRACT
Return exactly ONE JSON object and nothing else. No markdown fence.
{{
  "reply": "Natural Korean assistant response. Summarize what you understood, mention TBDs when useful, then ask the next 1-3 questions.",
  "project_updates": {{
    "name": "only if the conversation supports it",
    "goal": "...",
    "project_type": "generic|software|ai_data|embedded_hardware|manufacturing_automation|research_rnd|business_process|product_service|education_content|event_campaign",
    "problem": "...",
    "users": "...",
    "deliverables": "...",
    "success_criteria": "...",
    "scope": "...",
    "current_state": "...",
    "target_state": "...",
    "constraints": "...",
    "schedule": "...",
    "team": "...",
    "risks": "...",
    "description": "..."
  }},
  "requirements": [
    {{"ref":"REQ-001 or empty", "title":"requirement title", "detail":"testable detail", "status":"defined"}}
  ],
  "decisions": [
    {{"title":"decision or pending decision", "body":"reason/impact", "status":"proposed"}}
  ],
  "document_updates": [
    {{"doc_type":"proposal|plan|milestone|backlog|requirements|service_policy|function_definition|ia|screen_design|system_architecture|data_flow|api_design|qa", "content":"complete markdown content only when the user asked to write/update this document", "reason":"why"}}
  ],
  "pending": ["facts or decisions that are still unknown and worth resolving"]
}}

Rules for project_updates: omit unsupported fields rather than guessing. Empty objects/lists are valid.
"""
