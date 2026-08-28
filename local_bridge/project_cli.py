from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.conversation import PROJECT_FIELDS, merge_project_brief, normalize_ai_result
from app.project_intake import evaluate_intake
from local_bridge.providers import SUPPORTED_PROVIDERS, print_doctor, run_provider
from local_bridge.storage import atomic_write_json


WELCOME = (
    "AI Design Session을 시작합니다. 아직 Project OS 프로젝트는 생성되지 않습니다.\n"
    "막연한 아이디어부터 AI와 충분히 대화해서 구체화하세요.\n"
    "모르겠는 세부사항은 '알아서 임시로 정해줘'라고 하면 Autofill Mode로 채울 수 있습니다.\n"
    "명령: /status, /autofill on|off, /preview, /apply, /discard, /quit"
)

DEFAULT_SESSION_ROOT = Path.home() / ".team_project_os" / "design_sessions"


def http_json(method: str, url: str, payload=None, access_key: str = ""):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if access_key:
        headers["X-Access-Key"] = access_key
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Server connection failed: {exc}") from exc


def blank_brief() -> dict:
    data = {field: "" for field in PROJECT_FIELDS}
    data["project_type"] = "generic"
    return data


def _requests_autofill(text: str) -> bool:
    compact = "".join(str(text or "").lower().split())
    phrases = (
        "알아서해줘", "알아서정해", "알아서임시", "임시로다정", "임시로정해",
        "네가정해", "너가정해", "적당히정해", "세부적인건알아서", "세부사항은알아서",
        "알아서채워", "맡길게", "autofill",
    )
    return any(phrase in compact for phrase in phrases)


def build_design_chat_prompt(messages: list[dict], autofill_mode: bool = False) -> str:
    transcript = "\n\n".join(
        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\n{m['content']}"
        for m in messages
    )
    mode_rules = (
        "AUTOFILL MODE IS ON. When the user does not know a low-risk implementation detail, "
        "choose a sensible reversible default instead of repeatedly asking. Clearly call it an 'AI 임시 결정' "
        "and briefly explain why. Never treat it as user-confirmed. Still ask before irreversible/high-impact choices "
        "such as real spending, purchases, credentials/permissions, personal data policy, legal/regulatory commitments, "
        "or external production changes."
        if autofill_mode else
        "AUTOFILL MODE IS OFF. Recommend options, but do not choose unknown details for the user unless the user explicitly delegates that choice."
    )
    return f"""You are the user's project design partner inside Team Project OS.

PURPOSE
The user often starts with only a vague idea and cannot create a detailed plan alone.
Your job during this DESIGN SESSION is to think with the user until the idea becomes a realistic project.

CONVERSATION RULES
- Speak naturally in Korean unless the user asks otherwise.
- This is free-form design discussion. DO NOT output JSON in this phase.
- Ask only 1-3 high-value questions at a time.
- Help define the problem, goal, users, scope, deliverables, success criteria, process, architecture, data flow, schedule, risks, and verification approach when relevant.
- Explain alternatives and trade-offs when a choice is not obvious.
- Distinguish what the user confirmed from what you merely recommend.
- Never silently turn an unknown item into a USER-confirmed fact.
- {mode_rules}
- If the project is too large, proactively suggest a smaller V1.
- Do not create or modify Project OS state yet. The project will only be materialized after /apply outside this AI turn.
- Continue the discussion from the full transcript below. Answer the latest USER turn.

LIVE DRAFT CONTRACT
After your normal Korean conversational answer, append exactly one machine-readable block:
<PROJECT_OS_DELTA>{{"project_updates":{{}},"requirements":[],"decisions":[],"document_updates":[],"design_updates":[],"pending":[]}}</PROJECT_OS_DELTA>
Rules for this block:
- Keep it compact. It is hidden from the user and synchronized to the web Live Draft.
- Include only meaningful structured facts or decisions that became clearer in this turn.
- project_updates may include only fields actually established or safely provisional under Autofill Mode.
- A USER-confirmed choice uses decision status "accepted".
- An AI-selected reversible default under Autofill Mode uses decision status "provisional".
- Never mark an AI suggestion as accepted unless the USER explicitly accepted it.
- requirements should contain stable ref/title/detail/status values when a requirement became clear.
- If a process/architecture/dataflow view meaningfully changes, include the COMPLETE current graph for that view in design_updates, not just the new node.
- Do not emit full documents unless a document body was explicitly drafted. The server will progressively regenerate core draft documents from the structured state.
- If nothing structured changed, emit an empty object inside the marker.
- Never mention this marker in the conversational answer.

TRANSCRIPT
{transcript}
"""


def blank_live_state() -> dict:
    return {
        "project_updates": {},
        "requirements": [],
        "decisions": [],
        "document_updates": [],
        "design_updates": [],
        "pending": [],
    }


def extract_live_delta(output: str) -> tuple[str, dict]:
    text = str(output or "")
    start = text.rfind("<PROJECT_OS_DELTA>")
    end = text.rfind("</PROJECT_OS_DELTA>")
    if start < 0 or end < start:
        return text.strip(), {}
    raw = text[start + len("<PROJECT_OS_DELTA>"):end].strip()
    visible = (text[:start] + text[end + len("</PROJECT_OS_DELTA>"):]).strip()
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {}
    return visible, parsed if isinstance(parsed, dict) else {}


def _merge_by_key(existing: list[dict], incoming: list[dict], key_name: str) -> list[dict]:
    ordered: list[dict] = [dict(item) for item in existing]
    positions = {str(item.get(key_name) or "").strip().lower(): idx for idx, item in enumerate(ordered) if str(item.get(key_name) or "").strip()}
    for raw in incoming or []:
        item = dict(raw)
        key = str(item.get(key_name) or "").strip().lower()
        if not key:
            continue
        if key in positions:
            ordered[positions[key]] = item
        else:
            positions[key] = len(ordered)
            ordered.append(item)
    return ordered


def merge_live_state(state: dict, delta: dict) -> dict:
    merged = {
        "project_updates": dict(state.get("project_updates") or {}),
        "requirements": list(state.get("requirements") or []),
        "decisions": list(state.get("decisions") or []),
        "document_updates": list(state.get("document_updates") or []),
        "design_updates": list(state.get("design_updates") or []),
        "pending": list(state.get("pending") or []),
    }
    merged["project_updates"].update({k: v for k, v in (delta.get("project_updates") or {}).items() if str(v or "").strip()})
    merged["requirements"] = _merge_by_key(merged["requirements"], delta.get("requirements") or [], "ref")
    merged["decisions"] = _merge_by_key(merged["decisions"], delta.get("decisions") or [], "title")
    merged["document_updates"] = _merge_by_key(merged["document_updates"], delta.get("document_updates") or [], "doc_type")
    merged["design_updates"] = _merge_by_key(merged["design_updates"], delta.get("design_updates") or [], "view")
    seen = {str(x).strip() for x in merged["pending"] if str(x).strip()}
    for item in delta.get("pending") or []:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            merged["pending"].append(value)
    return merged


def create_live_draft(server: str, access_key: str, member: str, provider: str) -> dict:
    return http_json("POST", f"{server.rstrip('/')}/api/design-drafts", {
        "member_name": member,
        "provider": provider,
        "name_hint": "AI Design Draft",
    }, access_key)


def sync_live_draft(server: str, access_key: str, project_id: int, member: str, state: dict) -> dict:
    return http_json("PUT", f"{server.rstrip('/')}/api/design-drafts/{project_id}/sync", {
        "member_name": member,
        "state": state,
    }, access_key)


def promote_live_draft(server: str, access_key: str, project_id: int, member: str, state: dict) -> dict:
    result = http_json("POST", f"{server.rstrip('/')}/api/design-drafts/{project_id}/promote", {
        "member_name": member,
        "state": state,
    }, access_key)
    return result["project"]


def final_state_from_distillation(brief: dict, pending: dict) -> dict:
    return {
        "project_updates": dict(brief),
        "requirements": list(pending.get("requirements") or []),
        "decisions": list(pending.get("decisions") or []),
        "document_updates": list(pending.get("document_updates") or []),
        "design_updates": list(pending.get("design_updates") or []),
        "pending": list(pending.get("pending") or []),
    }


def build_distiller_prompt(messages: list[dict], autofill_mode: bool = False) -> str:
    transcript = "\n\n".join(
        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\n{m['content']}"
        for m in messages
    )
    autofill_rules = (
        "AUTOFILL MODE IS ON. Fill unresolved LOW-RISK, REVERSIBLE design/implementation details with practical V1 defaults. "
        "Every such AI-selected value MUST also create a decision with status='provisional', and the body must state why it was chosen and when it should be revisited. "
        "Examples: local DB choice, web framework, basic screen set, folder/module split, simulator-first approach, development order, local deployment. "
        "Do NOT autofill real spending/purchases, secrets or permission expansion, personal-data/legal/regulatory policy, contractual commitments, destructive production actions, or safety-critical thresholds; keep those in pending."
        if autofill_mode else
        "AUTOFILL MODE IS OFF. Do not fill unresolved facts unless the transcript contains an explicit user decision."
    )
    return f"""You are the Project Distiller for Team Project OS.
The user has finished or paused a free-form project design conversation with an AI.
Analyze the ENTIRE transcript once and convert it into one structured project proposal.

AUTHORITY RULES
- USER statements and explicit USER acceptances are authoritative.
- ASSISTANT suggestions are NOT confirmed facts unless the USER accepted them or they are only used as clearly proposed/TBD items.
- Never label AI-selected defaults as user-confirmed.
- {autofill_rules}
- Unknown or unresolved items that are not safely autofilled go into pending.
- You may create a neutral working project name from the confirmed topic if the user never named the project; if you do, add that naming decision to pending.
- goal may summarize the user's confirmed intent without adding new scope.
- Requirements must be traceable to explicit user intent or accepted design discussion.
- Decisions may contain USER-confirmed decisions with status='accepted' and AI-filled reversible defaults with status='provisional'.
- Provisional decisions are allowed to support a complete V1 process/architecture/dataflow when Autofill Mode is on.
- Create process/architecture/dataflow from confirmed facts plus clearly provisional defaults; do not hide which choices are provisional.
- Prefer a realistic V1 scope over an oversized project.

OUTPUT
Return exactly ONE JSON object and no markdown fence. Use this schema:
{{
  "reply": "short Korean summary for preview",
  "project_updates": {{
    "name": "working or confirmed project name",
    "goal": "confirmed goal",
    "project_type": "generic|software|ai_data|embedded_hardware|manufacturing_automation|research_rnd|business_process|product_service|education_content|event_campaign",
    "problem": "",
    "users": "",
    "deliverables": "",
    "success_criteria": "",
    "scope": "",
    "current_state": "",
    "target_state": "",
    "constraints": "",
    "schedule": "",
    "team": "",
    "risks": "",
    "description": ""
  }},
  "requirements": [
    {{"ref":"REQ-001","title":"...","detail":"...","status":"defined"}}
  ],
  "decisions": [
    {{"title":"...","body":"...","status":"accepted|provisional"}}
  ],
  "document_updates": [
    {{"doc_type":"proposal|plan|milestone|backlog|requirements|service_policy|function_definition|ia|screen_design|system_architecture|data_flow|api_design|qa","content":"complete markdown when enough evidence exists","reason":"..."}}
  ],
  "design_updates": [
    {{
      "view":"process|architecture|dataflow",
      "mode":"replace",
      "reason":"...",
      "nodes":[{{"key":"n1","label":"...","kind":"step|component|device|service|data|store","detail":"..."}}],
      "edges":[{{"source":"n1","target":"n2","label":"..."}}]
    }}
  ],
  "pending": ["unresolved facts, unaccepted alternatives, TBD decisions"]
}}

TRANSCRIPT
{transcript}
"""


def distill_design(
    provider: str,
    messages: list[dict],
    *,
    cwd: Path,
    custom_command: str | None = None,
    autofill_mode: bool = False,
) -> tuple[dict, dict]:
    if not any(m.get("role") == "user" for m in messages):
        raise RuntimeError("아직 사용자와의 프로젝트 대화가 없습니다.")
    result = run_provider(
        provider,
        build_distiller_prompt(messages, autofill_mode=autofill_mode),
        cwd=cwd,
        purpose="interview",
        custom_command=custom_command,
    )
    if not result.ok:
        detail = (result.stderr or result.stdout or "unknown provider error").strip()
        raise RuntimeError(f"{provider} Distiller 실행 실패 (exit={result.returncode}): {detail[-3000:]}")
    parsed = normalize_ai_result(result.stdout)
    brief = merge_project_brief(blank_brief(), parsed.get("project_updates", {}))
    return brief, parsed


def preview_lines(brief: dict, pending: dict) -> list[str]:
    quality = evaluate_intake(brief)
    decisions = pending.get("decisions", [])
    accepted_count = sum(1 for d in decisions if str(d.get("status", "")).lower() in {"accepted", "confirmed"})
    provisional = [d for d in decisions if str(d.get("status", "")).lower() == "provisional"]
    lines = [
        "",
        "=" * 62,
        "Project OS 생성 미리보기",
        "=" * 62,
        f"프로젝트: {brief.get('name') or '(이름 미정)'}",
        f"목표: {brief.get('goal') or '(목표 미정)'}",
        f"유형: {brief.get('project_type') or 'generic'}",
        f"정의 품질: {quality['score']}/100 ({quality['level']})",
        f"요구사항: {len(pending.get('requirements', []))}개",
        f"사람 확정 Decision: {accepted_count}개",
        f"AI 임시 Decision: {len(provisional)}개",
        f"문서 업데이트: {len(pending.get('document_updates', []))}개",
        f"Canvas 설계: {len(pending.get('design_updates', []))}개",
    ]
    if provisional:
        lines.append("AI 임시 결정(PROVISIONAL):")
        lines.extend(f"  - {item.get('title', '')}: {item.get('body', '')}" for item in provisional[:12])
    unresolved = pending.get("pending", [])
    if unresolved:
        lines.append("미결정/TBD:")
        lines.extend(f"  - {item}" for item in unresolved[:12])
    lines.append("=" * 62)
    return lines


def print_preview(brief: dict, pending: dict) -> None:
    print("\n".join(preview_lines(brief, pending)))


def apply_to_server(server: str, access_key: str, member: str, brief: dict, pending: dict) -> dict:
    if len(str(brief.get("name") or "").strip()) < 2:
        raise RuntimeError("프로젝트 이름이 아직 정해지지 않았습니다. AI와 이름을 먼저 확정하세요.")
    if len(str(brief.get("goal") or "").strip()) < 2:
        raise RuntimeError("프로젝트 목표가 아직 정해지지 않았습니다. AI와 목표를 먼저 확정하세요.")

    base = server.rstrip("/")
    project_payload = {field: brief.get(field, "") for field in PROJECT_FIELDS}
    project = http_json("POST", f"{base}/api/projects", project_payload, access_key)
    pid = project["id"]

    for item in pending.get("requirements", []):
        title = f"{item.get('ref', '')} {item.get('title', '')}".strip()
        if title:
            http_json("POST", f"{base}/api/projects/{pid}/requirements", {
                "title": title,
                "detail": item.get("detail", ""),
                "status": item.get("status", "defined"),
            }, access_key)

    for item in pending.get("decisions", []):
        if item.get("title"):
            http_json("POST", f"{base}/api/projects/{pid}/decisions", {
                "title": item["title"],
                "body": item.get("body", ""),
                "author": f"AI Distiller / {member}",
                "status": item.get("status", "accepted"),
            }, access_key)

    snapshot = http_json("GET", f"{base}/api/projects/{pid}/snapshot", None, access_key)
    docs_by_type = {d["doc_type"]: d for d in snapshot.get("documents", [])}
    for item in pending.get("document_updates", []):
        doc = docs_by_type.get(item.get("doc_type"))
        if doc and item.get("content"):
            http_json("PATCH", f"{base}/api/documents/{doc['id']}", {
                "content": item["content"],
                "status": "draft",
                "updated_by": f"Design Session / {member}",
            }, access_key)

    for design in pending.get("design_updates", []):
        view = design.get("view")
        if view not in {"process", "architecture", "dataflow"}:
            continue
        key_to_id = {}
        for idx, node in enumerate(design.get("nodes", [])):
            created = http_json("POST", f"{base}/api/projects/{pid}/nodes", {
                "view": view,
                "label": node.get("label", ""),
                "kind": node.get("kind", "component"),
                "detail": node.get("detail", ""),
                "x": 80 + (idx % 4) * 220,
                "y": 80 + (idx // 4) * 150,
            }, access_key)
            key_to_id[node.get("key", "")] = created["id"]
        for edge in design.get("edges", []):
            source = key_to_id.get(edge.get("source"))
            target = key_to_id.get(edge.get("target"))
            if source and target:
                http_json("POST", f"{base}/api/projects/{pid}/edges", {
                    "view": view,
                    "source_id": source,
                    "target_id": target,
                    "label": edge.get("label", ""),
                }, access_key)

    return project


def _session_file(args) -> Path:
    explicit = getattr(args, "session_file", "") or ""
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured_root = os.getenv("PROJECT_OS_SESSION_DIR", "").strip()
    session_root = (
        Path(configured_root).expanduser().resolve()
        if configured_root
        else DEFAULT_SESSION_ROOT
    )
    session_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    suffix = uuid4().hex[:8]
    return session_root / f"design-{stamp}-{suffix}-{args.provider}.json"


def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None, autofill_mode: bool = False, draft_project: dict | None = None, live_state: dict | None = None) -> None:
    atomic_write_json(path, {
        "provider": provider,
        "member": member,
        "messages": messages,
        "applied_project": applied_project,
        "draft_project": draft_project,
        "live_state": live_state or blank_live_state(),
        "autofill_mode": autofill_mode,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })


def print_session_status(path: Path, provider: str, messages: list[dict], autofill_mode: bool = False, draft_project: dict | None = None) -> None:
    user_turns = sum(1 for m in messages if m.get("role") == "user")
    assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
    print("\nDesign Session: 프로젝트 미생성 상태")
    print(f"AI Provider: {provider}")
    print(f"대화: 사용자 {user_turns}턴 / AI {assistant_turns}턴")
    print(f"세션 저장: {path}")
    print(f"Autofill Mode: {'ON - 모르는 저위험 세부사항은 AI 임시 결정' if autofill_mode else 'OFF'}")
    if draft_project:
        print(f"Live Draft: ID={draft_project.get('id')} · 웹에서 실시간 확인 가능")
        print("의미 있는 결정이 생긴 턴마다 Documents / Requirements / Decisions / Canvas가 자동 갱신됩니다.")
    else:
        print("Live Draft: OFF 또는 서버 연결 실패")
    print("/preview는 전체 구조 확인, /apply는 Live Draft를 정식 프로젝트로 승격합니다.")


def interactive_design(args) -> int:
    provider = args.provider
    cwd = Path(args.cwd or ".").expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        print(f"작업 폴더가 없습니다: {cwd}")
        return 2
    session_file = _session_file(args)
    messages: list[dict] = []
    preview_cache: tuple[int, dict, dict] | None = None
    autofill_mode = bool(getattr(args, "autofill", False))
    live_state = blank_live_state()
    draft_project: dict | None = None
    if not bool(getattr(args, "no_live", False)):
        try:
            draft_project = create_live_draft(args.server, args.access_key, args.member, provider)
        except Exception as exc:
            print(f"Live Draft 연결 실패: {exc}")
            print("대화는 계속할 수 있지만 웹 실시간 시각화는 비활성화됩니다.")

    print(WELCOME)
    print(f"AI: {provider} / 세션: {session_file}")
    if draft_project:
        print(f"Live Draft: ID={draft_project['id']} · {args.server.rstrip('/')} 에서 실시간 확인")
    if autofill_mode:
        print("Autofill Mode: ON (AI 임시 결정 허용)")
    queued = args.initial or None

    while True:
        user_text = queued
        queued = None
        if user_text is None:
            try:
                user_text = input("\n나> ").strip()
            except (EOFError, KeyboardInterrupt):
                save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
                print("\n세션을 저장하고 종료합니다.")
                return 0
        if not user_text:
            continue

        command = user_text.lower()
        if command in {"/quit", "/exit"}:
            save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
            print(f"세션 저장: {session_file}")
            return 0
        if command == "/status":
            print_session_status(session_file, provider, messages, autofill_mode, draft_project)
            continue
        if command == "/discard":
            if not draft_project:
                print("삭제할 Live Draft가 없습니다.")
                continue
            try:
                http_json("DELETE", f"{args.server.rstrip('/')}/api/design-drafts/{draft_project['id']}", None, args.access_key)
                print(f"Live Draft #{draft_project['id']} 삭제 완료")
                draft_project = None
                live_state = blank_live_state()
            except Exception as exc:
                print(f"Live Draft 삭제 실패: {exc}")
            continue
        if command.startswith("/autofill"):
            parts = command.split()
            if len(parts) == 1:
                print(f"Autofill Mode: {'ON' if autofill_mode else 'OFF'}")
            elif parts[1] in {"on", "1", "true"}:
                autofill_mode = True
                preview_cache = None
                print("Autofill Mode ON: 모르는 저위험 세부사항은 AI가 PROVISIONAL로 임시 결정합니다.")
            elif parts[1] in {"off", "0", "false"}:
                autofill_mode = False
                preview_cache = None
                print("Autofill Mode OFF: 모르는 사항은 다시 질문하거나 TBD로 남깁니다.")
            else:
                print("사용법: /autofill on 또는 /autofill off")
            continue
        if command in {"/preview", "/apply"}:
            version = len(messages)
            try:
                if preview_cache and preview_cache[0] == version:
                    _, brief, pending = preview_cache
                else:
                    print("\n전체 대화를 Project Distiller가 분석 중...")
                    brief, pending = distill_design(
                        provider,
                        messages,
                        cwd=cwd,
                        custom_command=args.command or None,
                        autofill_mode=autofill_mode,
                    )
                    preview_cache = (version, brief, pending)
                print_preview(brief, pending)
            except Exception as exc:
                print(f"미리보기 생성 실패: {exc}")
                continue

            if command == "/preview":
                print("아직 프로젝트는 생성되지 않았습니다. 계속 대화하거나 /apply 하세요.")
                continue

            try:
                final_state = final_state_from_distillation(brief, pending)
                if draft_project:
                    project = promote_live_draft(args.server, args.access_key, draft_project["id"], args.member, final_state)
                    live_state = final_state
                else:
                    project = apply_to_server(args.server, args.access_key, args.member, brief, pending)
            except Exception as exc:
                print(f"프로젝트 생성 실패: {exc}")
                continue
            save_session(
                session_file,
                provider=provider,
                member=args.member,
                messages=messages,
                applied_project=project,
                autofill_mode=autofill_mode,
                draft_project=None,
                live_state=live_state,
            )
            print(f"\n프로젝트 생성 완료: ID={project['id']} / {project['name']}")
            print(f"브라우저: {args.server.rstrip('/')}")
            return 0

        if _requests_autofill(user_text) and not autofill_mode:
            autofill_mode = True
            print("Autofill Mode ON: '알아서/임시로 정해줘' 요청을 감지했습니다.")
        messages.append({"role": "user", "content": user_text})
        preview_cache = None
        try:
            result = run_provider(
                provider,
                build_design_chat_prompt(messages, autofill_mode=autofill_mode),
                cwd=cwd,
                purpose="interview",
                custom_command=args.command or None,
            )
        except Exception as exc:
            messages.pop()
            print(f"\n{provider} 실행 실패: {exc}")
            continue

        if not result.ok:
            messages.pop()
            print(f"\n{provider} 실행 실패 (exit={result.returncode})")
            print((result.stderr or result.stdout or "").strip())
            continue

        answer, live_delta = extract_live_delta(result.stdout)
        if not answer:
            messages.pop()
            print("\nAI 응답이 비어 있습니다.")
            continue
        messages.append({"role": "assistant", "content": answer})
        if live_delta:
            live_state = merge_live_state(live_state, live_delta)
            if draft_project:
                try:
                    synced = sync_live_draft(args.server, args.access_key, draft_project["id"], args.member, live_state)
                    draft_project = synced.get("project") or draft_project
                    print(f"\n[Live Draft] 웹 자동 업데이트 · Project #{draft_project['id']}")
                except Exception as exc:
                    print(f"\n[Live Draft] 동기화 실패: {exc}")
        save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
        print(f"\n{provider}> {answer}")



interactive_create = interactive_design


def _add_design_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="codex")
    parser.add_argument("--server", default="http://localhost:8000")
    parser.add_argument("--member", default="CMD User")
    parser.add_argument("--access-key", default="")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--command", default="", help="Custom CLI template; prefer {prompt_file}")
    parser.add_argument("--initial", default="", help="첫 아이디어를 바로 전달")
    parser.add_argument("--session-file", default="", help="Design Session 저장 파일 경로")
    parser.add_argument("--autofill", action="store_true", help="모르는 저위험 세부사항을 AI가 PROVISIONAL로 임시 결정")
    parser.add_argument("--no-live", action="store_true", help="대화 중 웹 Live Draft 자동 동기화 비활성화")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Team Project OS AI Design Session")
    sub = parser.add_subparsers(dest="sub", required=True)

    d = sub.add_parser("design", help="AI와 충분히 대화한 뒤 /apply로 프로젝트 생성")
    _add_design_args(d)
    c = sub.add_parser("create", help="design 명령의 호환 별칭")
    _add_design_args(c)
    sub.add_parser("doctor", help="로컬 AI CLI 설치 상태 확인")

    args = parser.parse_args(argv)
    if args.sub == "doctor":
        print_doctor()
        return 0
    return interactive_design(args)


if __name__ == "__main__":
    raise SystemExit(main())
