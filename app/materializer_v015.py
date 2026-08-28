from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from app.delivery_documents import build_delivery_documents

DOC_TYPES = (
    "proposal", "plan", "milestone", "backlog", "requirements", "service_policy",
    "function_definition", "ia", "screen_design", "system_architecture", "data_flow", "api_design", "qa",
)


def _s(value: Any, fallback: str = "TBD") -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    return text or fallback


def _weeks(schedule: str) -> int:
    text = str(schedule or "").lower()
    for pattern, fn in (
        (r"(\d+)\s*(?:영업일|일|days?|day)", lambda n: math.ceil(n / 5)),
        (r"(\d+)\s*(?:주|weeks?|week)", lambda n: n),
        (r"(\d+)\s*(?:개월|달|months?|month)", lambda n: n * 4),
    ):
        match = re.search(pattern, text)
        if match:
            return max(2, min(52, fn(int(match.group(1)))))
    return 16


def _meta(state: dict[str, Any], status: str = "Draft") -> str:
    accepted = [d for d in state.get("decisions", []) if str(d.get("status", "")).lower() in {"accepted", "confirmed"}]
    provisional = [d for d in state.get("decisions", []) if str(d.get("status", "")).lower() in {"provisional", "proposed"}]
    alternatives = [d for d in state.get("decisions", []) if str(d.get("status", "")).lower() in {"rejected", "alternative"}]
    pending = state.get("pending", []) or []
    reqs = [r.get("ref") for r in state.get("requirements", []) if r.get("ref")]
    verification = sorted({str(r.get("verification") or "").strip() for r in state.get("requirements", []) if str(r.get("verification") or "").strip()})
    today = datetime.now(timezone.utc).date().isoformat()
    return f"""> **Document Control**  
> Version: 0.15-draft · Status: {status} · Updated: {today}  
> Confirmed Decisions: {', '.join(_s(d.get('title'), '') for d in accepted) or '없음'}  
> PROVISIONAL Decisions: {', '.join(_s(d.get('title'), '') for d in provisional) or '없음'}  
> Rejected / Alternatives: {', '.join(_s(d.get('title'), '') for d in alternatives) or '없음'}
> Related Requirements: {', '.join(reqs) or 'TBD'}  
> Verification: {', '.join(verification) or 'Review / Test'}  
> Pending: {'; '.join(_s(p, '') for p in pending) or '없음'}

## 변경 이력
| Version | Date | Change | Status |
|---|---|---|---|
| 0.15-draft | {today} | Live Design 구조화 상태에서 자동 Materialization | {status} |
"""


def _default_milestones(brief: dict[str, Any]) -> list[dict[str, str]]:
    total = _weeks(str(brief.get("schedule") or ""))
    specs = [
        ("A. 정의/설계", "MS-001", "착수 및 범위 기준선", .00, .07, "기획/계획 기준선", "목표·범위 승인"),
        ("A. 정의/설계", "MS-002", "요구사항/추적성 기준선", .02, .18, "요구사항 정의서", "핵심 REQ와 Acceptance Criteria 정의"),
        ("A. 정의/설계", "MS-003", "Process/Architecture/Data Flow 설계", .10, .28, "3종 Design", "주요 흐름/경계/데이터 이동 Review"),
        ("A. 정의/설계", "MS-004", "IA/화면/API 기준선", .18, .34, "IA/화면/API", "핵심 사용자 흐름과 Contract 정의"),
        ("B. 구현", "MS-005", "개발환경/기반 구조", .28, .40, "실행 가능한 Skeleton", "개발환경 Smoke PASS"),
        ("B. 구현", "MS-006", "핵심 도메인 기능", .34, .62, "핵심 기능", "핵심 REQ 기능시험 PASS"),
        ("B. 구현", "MS-007", "데이터/연동", .40, .66, "저장/연동", "데이터 정합성 시험 PASS"),
        ("B. 구현", "MS-008", "UI/HMI 기능", .46, .72, "사용자 화면", "화면별 Acceptance Criteria PASS"),
        ("C. 통합/검증", "MS-009", "모듈 통합", .64, .78, "통합 빌드", "E2E 주요 흐름 PASS"),
        ("C. 통합/검증", "MS-010", "기능/비기능/복구 시험", .72, .90, "QA Evidence", "Critical TC PASS"),
        ("C. 통합/검증", "MS-011", "결함 수정/안정화", .82, .96, "안정화 빌드", "Blocker/Critical 0"),
        ("D. 완료", "MS-012", "문서/인수/릴리스", .92, 1.00, "최종 산출물", "Release Gate 승인"),
    ]
    rows = []
    for phase, ident, task, start_ratio, end_ratio, deliverable, exit_criteria in specs:
        start = max(1, round(1 + (total - 1) * start_ratio))
        end = max(start, round(1 + (total - 1) * end_ratio))
        rows.append({
            "id": ident, "phase": phase, "task": task, "start_week": str(start), "end_week": str(end),
            "owner": "TBD", "status": "Draft", "deliverable": deliverable, "exit_criteria": exit_criteria,
            "requirement_refs": "REQ-*",
        })
    return rows


def materialize_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    base = build_delivery_documents(brief)
    docs = {key: base.get(key, f"# {key}\n") for key in DOC_TYPES}
    name = _s(brief.get("name"), "Project")
    goal = _s(brief.get("goal")); problem = _s(brief.get("problem")); users = _s(brief.get("users")); scope = _s(brief.get("scope"))
    success = _s(brief.get("success_criteria")); constraints = _s(brief.get("constraints")); schedule = _s(brief.get("schedule")); risks = _s(brief.get("risks"))
    reqs = state.get("requirements", []) or []
    milestones = state.get("milestones", []) or _default_milestones(brief)
    backlog = state.get("backlog_items", []) or [
        {"id": f"BL-{i:03d}", "epic": "Requirement Delivery", "title": _s(r.get("title")), "detail": _s(r.get("detail")),
         "priority": _s(r.get("priority")), "estimate": "TBD", "owner": _s(r.get("owner")), "status": "Todo",
         "requirement_refs": _s(r.get("ref")), "dependencies": "TBD", "definition_of_ready": "Acceptance Criteria 정의",
         "definition_of_done": _s(r.get("acceptance_criteria"))}
        for i, r in enumerate(reqs, 1)
    ]
    funcs = state.get("functions", []) or [
        {"id": f"FUNC-{i:03d}", "name": _s(r.get("title")), "actor": "System/User", "trigger": "관련 이벤트/사용자 동작",
         "preconditions": "관련 선행조건 충족", "inputs": _s(r.get("detail")), "business_rules": "REQ 기준 처리",
         "normal_flow": "입력 → 검증 → 처리 → 결과", "exception_flow": "검증 실패/통신 실패 시 오류 처리",
         "outputs": "처리 결과/상태", "acceptance_criteria": _s(r.get("acceptance_criteria")), "requirement_refs": _s(r.get("ref"))}
        for i, r in enumerate(reqs, 1)
    ]
    screens = state.get("screens", []) or []
    interfaces = state.get("interfaces", []) or []
    tests = state.get("tests", []) or [
        {"id": f"TC-{i:03d}", "requirement_refs": _s(r.get("ref")), "priority": _s(r.get("priority")),
         "preconditions": "Test Environment Ready", "steps": f"{_s(r.get('title'))} 시나리오 실행",
         "expected": _s(r.get("acceptance_criteria")), "evidence": "로그/스크린샷/DB/측정값",
         "pass_fail": "Expected Result 충족", "status": "Not Run"}
        for i, r in enumerate(reqs, 1)
    ]
    policies = state.get("policies", []) or []
    data_items = state.get("data_items", []) or []

    docs["proposal"] = f"# {name} 프로젝트 기획서\n\n{_meta(state)}\n## Executive Summary\n| 항목 | 내용 |\n|---|---|\n| 문제 | {problem} |\n| 목표 | {goal} |\n| 사용자/이해관계자 | {users} |\n| Scope | {scope} |\n| 성공 기준 | {success} |\n| 일정 | {schedule} |\n| 주요 리스크 | {risks} |\n\n## AS-IS / TO-BE\n| AS-IS | TO-BE |\n|---|---|\n| {_s(brief.get('current_state'))} | {_s(brief.get('target_state'))} |\n\n## 승인 기준\n- Scope/성공 기준/고위험 Pending은 Human Gate에서 승인\n- Requirement와 QA Evidence가 Release Gate를 만족해야 완료\n"

    docs["plan"] = f"# {name} 프로젝트 계획서\n\n{_meta(state)}\n## 1. 실행 전략\n- 목표: {goal}\n- 범위: {scope}\n- 일정 기준: {schedule}\n- 팀: {_s(brief.get('team'))}\n\n## 2. WBS / Delivery Strategy\n| Workstream | Deliverable | Dependency | Verification |\n|---|---|---|---|\n| Definition | 요구사항/설계 기준선 | Project Brief | Review |\n| Build | 기능/데이터/UI | Definition | Unit/Integration Test |\n| Verify | QA Evidence | Build | E2E/Measurement |\n| Release | 문서/인수 | Verify | Release Gate |\n\n## 3. Risk / Change Management\n- 제약: {constraints}\n- 리스크: {risks}\n- 변경은 관련 REQ → Design/API/Data → Backlog → Test/Evidence 영향을 검토\n"

    lines = ["# 개발 마일스톤 / Gantt", "", _meta(state), "## Gantt Schedule", "", "| Phase | ID | Task | Start Week | End Week | Owner | Status | Deliverable | Exit Criteria | Related REQ |", "|---|---|---|---:|---:|---|---|---|---|---|"]
    for item in milestones:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("phase", "id", "task", "start_week", "end_week", "owner", "status", "deliverable", "exit_criteria", "requirement_refs")) + " |")
    lines += ["", "> 일정은 실제 시작일/인력/의존성이 확정되기 전까지 PROVISIONAL 상대 주차 기준입니다."]
    docs["milestone"] = "\n".join(lines)

    lines = ["# Product / Project Backlog", "", _meta(state), "| ID | Epic | 작업 | Detail | Priority | Estimate | Owner | Status | Related REQ | Dependencies | DoR | DoD |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for item in backlog:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "epic", "title", "detail", "priority", "estimate", "owner", "status", "requirement_refs", "dependencies", "definition_of_ready", "definition_of_done")) + " |")
    docs["backlog"] = "\n".join(lines)

    lines = ["# 요구사항 정의서", "", _meta(state), "## Requirements Register", "", "| ID | Type | Requirement | Detail | Source/Rationale | Priority | Acceptance Criteria | Verification | Owner | Status | Traceability |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for item in reqs:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("ref", "type", "title", "detail", "source", "priority", "acceptance_criteria", "verification", "owner", "status", "traceability")) + " |")
    lines += ["", "## Traceability Rule", "REQ → Process/Architecture/Data/API → Backlog/Task → TC → Evidence 순으로 연결합니다."]
    docs["requirements"] = "\n".join(lines)

    lines = ["# 서비스 및 운영 정책서", "", _meta(state), "## 운영 기준", "", "| Policy ID | Category | Policy | Target | Monitoring | Response | Owner | Status | Related REQ |", "|---|---|---|---|---|---|---|---|---|"]
    if policies:
        for item in policies:
            lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "category", "policy", "target", "monitoring", "response", "owner", "status", "requirement_refs")) + " |")
    else:
        defaults = [
            ("POL-001", "Availability", "서비스/통신 상태 모니터링", "TBD", "Health/Log", "장애 감지 후 원인/복구 기록"),
            ("POL-002", "Backup/Recovery", "데이터 보존 및 복구 절차", "RPO/RTO TBD", "Backup Evidence", "복구 시험 수행"),
            ("POL-003", "Change", "변경 영향과 Rollback 관리", "승인된 변경만 반영", "Change Log", "실패 시 Rollback"),
            ("POL-004", "Security", "권한/비밀값 최소화", "운영 승인 필요", "Audit/Review", "보안 이슈 격리/보고"),
        ]
        for ident, category, policy, target, monitoring, response in defaults:
            lines.append(f"| {ident} | {category} | {policy} | {target} | {monitoring} | {response} | TBD | Draft | REQ-* |")
    lines += ["", "## Incident / Change / Recovery", "- Incident: 탐지 → 영향 판단 → 우회/복구 → Evidence → 재발방지", "- Change: Impact Analysis → 승인 → 배포 → 검증 → Rollback 가능성 유지"]
    docs["service_policy"] = "\n".join(lines)

    lines = ["# 기능 정의서", "", _meta(state), "| FUNC ID | 기능명 | Actor | Trigger | Preconditions | Inputs | Business Rules | Normal Flow | Exception Flow | Outputs | Acceptance Criteria | Related REQ |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for item in funcs:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "name", "actor", "trigger", "preconditions", "inputs", "business_rules", "normal_flow", "exception_flow", "outputs", "acceptance_criteria", "requirement_refs")) + " |")
    docs["function_definition"] = "\n".join(lines)

    lines = ["# IA (Information Architecture)", "", _meta(state), "## Navigation / Page Inventory", "", "| Screen ID | 화면 | 목적 | 사용자 | Entry | 주요 Action | API/Interface | Related REQ |", "|---|---|---|---|---|---|---|---|"]
    if screens:
        for item in screens:
            lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "name", "purpose", "users", "entry_conditions", "actions", "api_refs", "requirement_refs")) + " |")
    else:
        lines.append(f"| SCR-001 | Main / Overview | 핵심 상태와 진행 확인 | {users} | Project 접속 | 조회/탐색 | TBD | REQ-* |")
    lines += ["", "## 주요 User Journey", "1. 진입 → 현재 상태 확인 → 상세 화면 이동 → 작업/조회 → 결과/오류 확인"]
    docs["ia"] = "\n".join(lines)

    lines = ["# 화면 설계서", "", _meta(state)]
    screen_rows = screens or [{"id": "SCR-001", "name": "Main / Overview", "purpose": goal, "users": users, "entry_conditions": "Project 접속", "components": "Status/KPI/Main actions", "actions": "조회/탐색", "validation": "입력/연결상태 검증", "states": "Loading/Empty/Error/Normal", "api_refs": "TBD", "requirement_refs": "REQ-*"}]
    for item in screen_rows:
        lines += [f"## {_s(item.get('id'))} · {_s(item.get('name'))}", "", "| 항목 | 내용 |", "|---|---|", f"| 목적 | {_s(item.get('purpose'))} |", f"| 사용자 | {_s(item.get('users'))} |", f"| 진입 조건 | {_s(item.get('entry_conditions'))} |", f"| 주요 Component | {_s(item.get('components'))} |", f"| Action | {_s(item.get('actions'))} |", f"| Validation | {_s(item.get('validation'))} |", f"| Loading/Empty/Error/Normal | {_s(item.get('states'))} |", f"| API/Event | {_s(item.get('api_refs'))} |", f"| Related REQ | {_s(item.get('requirement_refs'))} |", ""]
    docs["screen_design"] = "\n".join(lines)

    architecture = next((item for item in state.get("design_updates", []) if item.get("view") == "architecture"), None)
    lines = ["# 시스템 구조도", "", _meta(state), "## Component / Responsibility", "", "| Component | Kind | Responsibility / Detail | Interfaces | Related REQ |", "|---|---|---|---|---|"]
    if architecture:
        edge_map: dict[str, list[str]] = {}
        labels = {node.get("key"): node.get("label") for node in architecture.get("nodes", [])}
        for edge in architecture.get("edges", []):
            edge_map.setdefault(edge.get("source"), []).append(f"{_s(edge.get('label'), '')}→{_s(labels.get(edge.get('target')))}")
        for node in architecture.get("nodes", []):
            lines.append(f"| {_s(node.get('label'))} | {_s(node.get('kind'))} | {_s(node.get('detail'))} | {_s(', '.join(edge_map.get(node.get('key'), [])))} | REQ-* |")
    else:
        lines.append("| TBD | component | Architecture Design Session에서 구체화 | TBD | REQ-* |")
    lines += ["", "## Quality / Deployment Considerations", f"- Constraints: {constraints}", "- Availability/Security/Recovery 요구사항은 운영정책 및 QA와 추적합니다."]
    docs["system_architecture"] = "\n".join(lines)

    dataflow = next((item for item in state.get("design_updates", []) if item.get("view") == "dataflow"), None)
    lines = ["# 데이터 플로우", "", _meta(state), "## Data Dictionary / Flow Catalog", "", "| Data ID | Data | Source/Producer | Fields | Validation | Processing | Destination | Protocol | Retention | Failure Handling | Related REQ |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    if data_items:
        for item in data_items:
            lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "name", "source", "fields", "validation", "processing", "destination", "protocol", "retention", "failure_handling", "requirement_refs")) + " |")
    elif dataflow:
        labels = {node.get("key"): node.get("label") for node in dataflow.get("nodes", [])}
        for index, edge in enumerate(dataflow.get("edges", []), 1):
            lines.append(f"| DATA-{index:03d} | {_s(edge.get('label'), 'Data/Event')} | {_s(labels.get(edge.get('source')))} | TBD | Validate | Transform/Route | {_s(labels.get(edge.get('target')))} | TBD | TBD | Retry/Log/Alarm | REQ-* |")
    else:
        lines.append("| DATA-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |")
    docs["data_flow"] = "\n".join(lines)

    lines = ["# API / Interface 설계 문서", "", _meta(state), "## Interface Catalog", "", "| API/IF ID | Kind | Method | Path/Event | Purpose | Auth | Request | Success Response | Error Model | Timeout/Retry | Idempotency | Versioning | Related REQ |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    interface_rows = interfaces or [{"id": "API-001", "kind": "REST/Event", "method": "TBD", "path": "TBD", "purpose": "Project Interface", "auth": "TBD", "request": "TBD", "response": "TBD", "errors": "Standard Error Model", "timeout_retry": "TBD", "idempotency": "TBD", "versioning": "v1", "requirement_refs": "REQ-*"}]
    for item in interface_rows:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "kind", "method", "path", "purpose", "auth", "request", "response", "errors", "timeout_retry", "idempotency", "versioning", "requirement_refs")) + " |")
    docs["api_design"] = "\n".join(lines)

    lines = ["# QA / Test Plan & Result", "", _meta(state), "## Test Strategy", "- Requirement 기반으로 Functional / Integration / Recovery / Non-functional Evidence를 관리합니다.", "", "## Test Cases", "", "| TC ID | Related REQ | Priority | Preconditions | Test Steps | Expected Result | Evidence | Pass/Fail Criteria | Status |", "|---|---|---|---|---|---|---|---|---|"]
    for item in tests:
        lines.append("| " + " | ".join(_s(item.get(key)) for key in ("id", "requirement_refs", "priority", "preconditions", "steps", "expected", "evidence", "pass_fail", "status")) + " |")
    lines += ["", "## Release Gate", "- Blocker/Critical 미해결 0건", "- 핵심 REQ Acceptance Criteria 충족", "- Test Evidence 확보 및 Traceability 결손 없음"]
    docs["qa"] = "\n".join(lines)

    for item in state.get("document_updates", []) or []:
        doc_type = str(item.get("doc_type") or "")
        content = str(item.get("content") or "").strip()
        if doc_type in docs and content and document_quality(content) > document_quality(docs[doc_type]):
            docs[doc_type] = content
    return docs


def document_quality(content: str) -> int:
    text = str(content or "")
    score = min(len(text), 12000) // 20
    score += text.count("## ") * 25 + text.count("|---") * 40
    score += len(re.findall(r"\b(?:REQ|FUNC|SCR|API|IF|TC|MS|BL|POL|DATA)-[A-Za-z0-9_-]+", text)) * 10
    score -= text.upper().count("TBD") * 2
    return max(0, score)


def stable_ids(content: str) -> set[str]:
    return set(re.findall(r"\b(?:REQ|FUNC|SCR|API|IF|TC|MS|BL|POL|DATA)-[A-Za-z0-9_-]+", str(content or "")))


def document_regressed(old_content: str, new_content: str) -> bool:
    old_ids = stable_ids(old_content)
    new_ids = stable_ids(new_content)
    if old_ids and not old_ids.issubset(new_ids):
        return True
    old_quality = document_quality(old_content)
    new_quality = document_quality(new_content)
    if old_quality > new_quality + 40:
        return True
    if len(str(old_content or "")) > max(900, int(len(str(new_content or "")) * 1.35)):
        return True
    return False


def graph_quality(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> int:
    return len(nodes) * 20 + len(edges) * 12 + sum(1 for node in nodes if str(node.get("detail") or "").strip()) * 3 + sum(1 for edge in edges if str(edge.get("label") or "").strip()) * 3
