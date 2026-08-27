from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.conversation import PROJECT_FIELDS, merge_project_brief, normalize_ai_result
from app.project_intake import evaluate_intake
from local_bridge.providers import SUPPORTED_PROVIDERS, print_doctor, run_provider


WELCOME = (
    "AI Design Session을 시작합니다. 아직 Project OS 프로젝트는 생성되지 않습니다.\n"
    "막연한 아이디어부터 AI와 충분히 대화해서 구체화하세요.\n"
    "명령: /status 세션 상태, /preview 프로젝트 미리보기, /apply 정식 생성, /quit 종료"
)

SESSION_ROOT = Path.home() / ".team_project_os" / "design_sessions"


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


def build_design_chat_prompt(messages: list[dict]) -> str:
    transcript = "\n\n".join(
        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\n{m['content']}"
        for m in messages
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
- Never silently turn an unknown budget, deadline, KPI, technology, device, protocol, policy, or requirement into a confirmed fact.
- If the project is too large, proactively suggest a smaller V1.
- Do not create or modify Project OS state yet. The project will only be materialized after /apply outside this AI turn.
- Continue the discussion from the full transcript below. Answer the latest USER turn.

TRANSCRIPT
{transcript}
"""


def build_distiller_prompt(messages: list[dict]) -> str:
    transcript = "\n\n".join(
        f"{'USER' if m['role'] == 'user' else 'ASSISTANT'}:\n{m['content']}"
        for m in messages
    )
    return f"""You are the Project Distiller for Team Project OS.
The user has finished or paused a free-form project design conversation with an AI.
Analyze the ENTIRE transcript once and convert it into one structured project proposal.

AUTHORITY RULES
- USER statements and explicit USER acceptances are authoritative.
- ASSISTANT suggestions are NOT confirmed facts unless the USER accepted them or they are only used as clearly proposed/TBD items.
- Do not invent budget, deadline, KPI target values, users, hardware, protocols, databases, cloud providers, policies, or requirements.
- Unknown or unresolved facts go into pending.
- You may create a neutral working project name from the confirmed topic if the user never named the project; if you do, add that naming decision to pending.
- goal may summarize the user's confirmed intent without adding new scope.
- Requirements must be traceable to explicit user intent or accepted design discussion.
- Decisions should contain only confirmed decisions. Unaccepted alternatives belong in pending, not decisions.
- Create process/architecture/dataflow only when supported by the conversation. Do not fabricate missing components.
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
    {{"title":"...","body":"...","status":"accepted"}}
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
) -> tuple[dict, dict]:
    if not any(m.get("role") == "user" for m in messages):
        raise RuntimeError("아직 사용자와의 프로젝트 대화가 없습니다.")
    result = run_provider(
        provider,
        build_distiller_prompt(messages),
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
        f"확정 Decision: {len(pending.get('decisions', []))}개",
        f"문서 업데이트: {len(pending.get('document_updates', []))}개",
        f"Canvas 설계: {len(pending.get('design_updates', []))}개",
    ]
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
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return SESSION_ROOT / f"design-{stamp}-{args.provider}.json"


def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "provider": provider,
        "member": member,
        "messages": messages,
        "applied_project": applied_project,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def print_session_status(path: Path, provider: str, messages: list[dict]) -> None:
    user_turns = sum(1 for m in messages if m.get("role") == "user")
    assistant_turns = sum(1 for m in messages if m.get("role") == "assistant")
    print("\nDesign Session: 프로젝트 미생성 상태")
    print(f"AI Provider: {provider}")
    print(f"대화: 사용자 {user_turns}턴 / AI {assistant_turns}턴")
    print(f"세션 저장: {path}")
    print("/preview 또는 /apply 시점에만 전체 대화를 프로젝트 구조로 변환합니다.")


def interactive_design(args) -> int:
    provider = args.provider
    cwd = Path(args.cwd or ".").expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        print(f"작업 폴더가 없습니다: {cwd}")
        return 2
    session_file = _session_file(args)
    messages: list[dict] = []
    preview_cache: tuple[int, dict, dict] | None = None

    print(WELCOME)
    print(f"AI: {provider} / 세션: {session_file}")
    queued = args.initial or None

    while True:
        user_text = queued
        queued = None
        if user_text is None:
            try:
                user_text = input("\n나> ").strip()
            except (EOFError, KeyboardInterrupt):
                save_session(session_file, provider=provider, member=args.member, messages=messages)
                print("\n세션을 저장하고 종료합니다.")
                return 0
        if not user_text:
            continue

        command = user_text.lower()
        if command in {"/quit", "/exit"}:
            save_session(session_file, provider=provider, member=args.member, messages=messages)
            print(f"세션 저장: {session_file}")
            return 0
        if command == "/status":
            print_session_status(session_file, provider, messages)
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
            )
            print(f"\n프로젝트 생성 완료: ID={project['id']} / {project['name']}")
            print(f"브라우저: {args.server.rstrip('/')}")
            return 0

        messages.append({"role": "user", "content": user_text})
        preview_cache = None
        try:
            result = run_provider(
                provider,
                build_design_chat_prompt(messages),
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

        answer = result.stdout.strip()
        if not answer:
            messages.pop()
            print("\nAI 응답이 비어 있습니다.")
            continue
        messages.append({"role": "assistant", "content": answer})
        save_session(session_file, provider=provider, member=args.member, messages=messages)
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
