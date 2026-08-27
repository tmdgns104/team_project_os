from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.conversation import (
    PROJECT_FIELDS,
    build_interviewer_prompt,
    combine_proposals,
    merge_project_brief,
    normalize_ai_result,
)
from app.project_intake import build_initial_documents, evaluate_intake
from local_bridge.providers import SUPPORTED_PROVIDERS, print_doctor, run_provider


WELCOME = (
    "AI와 CMD에서 프로젝트를 정의합니다. 편하게 설명하세요.\n"
    "명령: /status 현재 정의 보기, /apply Project OS에 생성, /quit 종료"
)


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


def document_context(brief: dict) -> list[dict]:
    generated = build_initial_documents(brief)
    titles = {
        "proposal": "기획서",
        "plan": "계획서",
        "milestone": "마일스톤",
        "backlog": "백로그",
        "requirements": "요구사항 정의서",
    }
    return [
        {"doc_type": key, "title": titles.get(key, key), "content": value, "status": "draft"}
        for key, value in generated.items()
    ]


def print_status(brief: dict, pending: dict) -> None:
    quality = evaluate_intake(brief)
    print(f"\n정의 품질: {quality['score']}/100 ({quality['level']})")
    labels = {
        "name": "이름", "goal": "목표", "project_type": "유형", "problem": "문제",
        "users": "사용자/이해관계자", "deliverables": "산출물", "success_criteria": "성공 기준",
        "scope": "범위", "current_state": "AS-IS", "target_state": "TO-BE",
        "constraints": "제약", "schedule": "일정", "team": "팀", "risks": "리스크",
        "description": "추가 설명",
    }
    for field in PROJECT_FIELDS:
        value = str(brief.get(field) or "").strip()
        if value:
            print(f"- {labels.get(field, field)}: {value}")
    print(
        f"제안: 요구사항 {len(pending.get('requirements', []))}, "
        f"결정 {len(pending.get('decisions', []))}, "
        f"문서 {len(pending.get('document_updates', []))}, "
        f"설계 {len(pending.get('design_updates', []))}"
    )
    if pending.get("pending"):
        print("미결정:")
        for item in pending["pending"]:
            print(f"  - {item}")
    print()


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
                "author": f"AI proposal / {member}",
                "status": item.get("status", "proposed"),
            }, access_key)

    snapshot = http_json("GET", f"{base}/api/projects/{pid}/snapshot", None, access_key)
    docs_by_type = {d["doc_type"]: d for d in snapshot.get("documents", [])}
    for item in pending.get("document_updates", []):
        doc = docs_by_type.get(item.get("doc_type"))
        if doc and item.get("content"):
            http_json("PATCH", f"{base}/api/documents/{doc['id']}", {
                "content": item["content"],
                "status": "draft",
                "updated_by": f"CMD AI / {member}",
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


def interactive_create(args) -> int:
    provider = args.provider
    cwd = Path(args.cwd or ".").expanduser().resolve()
    brief = blank_brief()
    pending: dict = {}
    messages = [{"role": "assistant", "content": WELCOME}]
    print(WELCOME)
    if args.initial:
        queued = args.initial
    else:
        queued = None

    while True:
        user_text = queued
        queued = None
        if user_text is None:
            try:
                user_text = input("\n나> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n종료합니다.")
                return 0
        if not user_text:
            continue
        if user_text.lower() in {"/quit", "/exit"}:
            return 0
        if user_text.lower() == "/status":
            print_status(brief, pending)
            continue
        if user_text.lower() == "/apply":
            try:
                project = apply_to_server(args.server, args.access_key, args.member, brief, pending)
            except Exception as exc:
                print(f"생성 실패: {exc}")
                continue
            print(f"\n프로젝트 생성 완료: ID={project['id']} / {project['name']}")
            print(f"브라우저: {args.server.rstrip('/')}")
            return 0

        messages.append({"role": "user", "content": user_text})
        prompt = build_interviewer_prompt(
            project_id=0,
            brief=brief,
            messages=messages,
            documents=document_context(brief),
            previous_pending=pending,
        )
        try:
            result = run_provider(
                provider,
                prompt,
                cwd=cwd,
                purpose="interview",
                custom_command=args.command or None,
            )
        except Exception as exc:
            print(f"\n{provider} 실행 실패: {exc}")
            continue

        if not result.ok:
            print(f"\n{provider} 실행 실패 (exit={result.returncode})")
            if result.stderr.strip():
                print(result.stderr.strip())
            elif result.stdout.strip():
                print(result.stdout.strip())
            continue

        try:
            parsed = normalize_ai_result(result.stdout)
        except Exception as exc:
            print(f"\nAI 응답 JSON 해석 실패: {exc}")
            print("원본 응답:")
            print(result.stdout[-4000:])
            if result.stderr.strip():
                print("진단:")
                print(result.stderr[-2000:])
            continue

        pending = combine_proposals(pending, parsed)
        brief = merge_project_brief(brief, parsed.get("project_updates", {}))
        messages.append({"role": "assistant", "content": parsed["reply"]})
        print(f"\nAI Project Interviewer> {parsed['reply']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Team Project OS CMD Project Creator")
    sub = parser.add_subparsers(dest="sub", required=True)

    c = sub.add_parser("create", help="AI와 CMD에서 대화하며 프로젝트 생성")
    c.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="codex")
    c.add_argument("--server", default="http://localhost:8000")
    c.add_argument("--member", default="CMD User")
    c.add_argument("--access-key", default="")
    c.add_argument("--cwd", default=".")
    c.add_argument("--command", default="", help="Custom CLI template; prefer {prompt_file}")
    c.add_argument("--initial", default="", help="첫 메시지를 명령행에서 바로 전달")

    sub.add_parser("doctor", help="로컬 AI CLI 설치 상태 확인")

    args = parser.parse_args(argv)
    if args.sub == "doctor":
        print_doctor()
        return 0
    return interactive_create(args)


if __name__ == "__main__":
    raise SystemExit(main())
