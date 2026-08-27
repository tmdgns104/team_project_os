from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    if old not in s:
        if new in s:
            return
        raise RuntimeError(f"{label}: marker not found in {path}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


DELIVERY = r'''
from __future__ import annotations

import math
import re
from typing import Any

DOCUMENT_ORDER = [
    ("proposal", "기획서"),
    ("plan", "계획서"),
    ("milestone", "마일스톤"),
    ("backlog", "백로그"),
    ("requirements", "요구사항 정의서"),
    ("service_policy", "서비스 및 운영 정책서"),
    ("function_definition", "기능 정의서"),
    ("ia", "IA (Information Architecture, 정보구조도)"),
    ("screen_design", "화면 설계서"),
    ("system_architecture", "시스템 구조도"),
    ("data_flow", "데이터 플로우"),
    ("api_design", "API 설계 문서"),
    ("qa", "QA 문서"),
]


def _text(data: dict[str, Any], key: str, fallback: str = "TBD · 확인 필요") -> str:
    value = str((data or {}).get(key) or "").strip()
    return value or fallback


def _safe(value: Any) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").strip()


def _total_weeks(schedule: str) -> int:
    text = str(schedule or "").lower()
    m = re.search(r"(\d+)\s*(?:영업일|일|days?|day)", text)
    if m:
        return max(2, min(52, math.ceil(int(m.group(1)) / 5)))
    m = re.search(r"(\d+)\s*(?:주|weeks?|week)", text)
    if m:
        return max(2, min(52, int(m.group(1))))
    m = re.search(r"(\d+)\s*(?:개월|달|months?|month)", text)
    if m:
        return max(4, min(52, int(m.group(1)) * 4))
    return 16


def _week(total: int, ratio: float) -> int:
    return max(1, min(total, int(round(1 + (total - 1) * ratio))))


def _gantt_rows(schedule: str) -> list[tuple[str, str, str, int, int, str, str]]:
    total = _total_weeks(schedule)
    specs = [
        ("A. 정의 및 설계", "MS-001", "프로젝트 착수 / 목표·범위 정리", 0.00, 0.05),
        ("A. 정의 및 설계", "MS-002", "요구사항 분석 및 기준선", 0.00, 0.15),
        ("A. 정의 및 설계", "MS-003", "System Process / Architecture / Data Flow 설계", 0.08, 0.25),
        ("A. 정의 및 설계", "MS-004", "IA / 화면 / 인터페이스 기준선", 0.14, 0.28),
        ("B. 구현", "MS-005", "개발환경 / 기반 구조 준비", 0.22, 0.34),
        ("B. 구현", "MS-006", "핵심 기능 구현", 0.28, 0.58),
        ("B. 구현", "MS-007", "데이터 저장 / 외부 연동 구현", 0.34, 0.60),
        ("B. 구현", "MS-008", "UI / 사용자 기능 구현", 0.40, 0.66),
        ("B. 구현", "MS-009", "모듈 통합", 0.58, 0.72),
        ("C. 통합 및 검증", "MS-010", "통합 테스트", 0.68, 0.82),
        ("C. 통합 및 검증", "MS-011", "성능 / 비기능 / 운영 검증", 0.72, 0.88),
        ("C. 통합 및 검증", "MS-012", "결함 수정 / 안정화", 0.78, 0.94),
        ("D. 완료", "MS-013", "인수 기준 / Release Gate 확인", 0.90, 0.94),
        ("D. 완료", "MS-014", "문서 / 운영 가이드 정리", 0.90, 1.00),
        ("D. 완료", "MS-015", "최종 릴리스 / 인수", 1.00, 1.00),
    ]
    rows = []
    for phase, ident, task, a, b in specs:
        start, end = _week(total, a), _week(total, b)
        rows.append((phase, ident, task, start, max(start, end), "TBD", "Draft" if phase.startswith("A") else "Todo"))
    return rows


def _gantt_markdown(schedule: str) -> str:
    rows = _gantt_rows(schedule)
    lines = [
        "| Phase | ID | Task | Start Week | End Week | Owner | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(map(str, row)) + " |")
    return "\n".join(lines)


def build_requirements_register(data: dict[str, Any], requirements: list[dict[str, Any]] | None = None) -> str:
    name = _text(data, "name", "프로젝트명 TBD")
    goal = _text(data, "goal")
    scope = _text(data, "scope")
    rows = requirements or [{"ref": "REQ-001", "title": "TBD", "detail": "Design Session에서 구체화", "status": "Draft"}]
    body = []
    for idx, item in enumerate(rows, 1):
        ref = _safe(item.get("ref") or f"REQ-{idx:03d}")
        req_type = _safe(item.get("type") or "Functional")
        title = _safe(item.get("title") or "TBD")
        detail = _safe(item.get("detail") or "TBD")
        source = _safe(item.get("source") or item.get("rationale") or "User / Design Session")
        priority = _safe(item.get("priority") or "TBD")
        acceptance = _safe(item.get("acceptance_criteria") or "TBD · 확인 필요")
        verification = _safe(item.get("verification") or "Test / Review")
        owner = _safe(item.get("owner") or "TBD")
        status = _safe(item.get("status") or "Draft")
        trace = _safe(item.get("traceability") or "Process/Task/Test 연결 예정")
        body.append(f"| {ref} | {req_type} | {title} | {detail} | {source} | {priority} | {acceptance} | {verification} | {owner} | {status} | {trace} |")
    return f"""# {name} 요구사항 정의서

> **Document Control** · Status: Draft · Revision: 0.1 · Owner: TBD · Approver: TBD
> **작성 기준** · 요구사항은 명확성·추적성·검증 가능성을 유지하고, 미확정 정보는 TBD로 둡니다.

## 1. Purpose / Scope
- 프로젝트 목표: {goal}
- 요구사항 적용 범위: {scope}

## 2. Requirement Quality Rules
- 한 Requirement는 하나의 검증 가능한 결과를 표현합니다.
- 모호한 표현은 수치·조건·상태로 바꿉니다.
- 각 Requirement는 Source/Rationale, Priority, Acceptance Criteria, Verification을 가집니다.
- 변경 시 관련 Process, Architecture, Task, Test/Evidence 영향을 함께 확인합니다.

## 3. Requirements Register

| ID | Type | Requirement | Detail | Source / Rationale | Priority | Acceptance Criteria | Verification | Owner | Status | Traceability |
|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(body)}

## 4. Non-Functional Requirements

| NFR ID | Quality Attribute | Requirement / Target | Measurement | Verification | Status |
|---|---|---|---|---|---|
| NFR-001 | Performance | {_safe(_text(data, 'success_criteria'))} | TBD | Measurement/Test | Draft |
| NFR-002 | Reliability / Recovery | TBD | TBD | Recovery/Test | Draft |
| NFR-003 | Security / Privacy | TBD · 실제 운영 정책 승인 필요 | TBD | Review/Test | Draft |
| NFR-004 | Maintainability / Operability | {_safe(_text(data, 'constraints'))} | TBD | Review | Draft |

## 5. Traceability Matrix

| Requirement | Process / Architecture | Backlog / Task | Test Case | Evidence | Status |
|---|---|---|---|---|---|
| REQ-* | TBD | TBD | TBD | TBD | Draft |

## 6. Open Issues / Approval
- Acceptance Criteria가 없는 항목은 Baseline 승인 전까지 Draft입니다.
- 비용·보안·개인정보·법규·실제 설비 제어 등 고위험 항목은 담당자 승인 후 확정합니다.
"""


def build_delivery_documents(data: dict[str, Any]) -> dict[str, str]:
    name = _text(data, "name", "프로젝트명 TBD")
    goal = _text(data, "goal")
    problem = _text(data, "problem")
    users = _text(data, "users")
    deliverables = _text(data, "deliverables")
    success = _text(data, "success_criteria")
    scope = _text(data, "scope")
    current = _text(data, "current_state")
    target = _text(data, "target_state")
    constraints = _text(data, "constraints")
    schedule = _text(data, "schedule")
    team = _text(data, "team")
    risks = _text(data, "risks")
    ptype = _text(data, "project_type", "generic")
    weeks = _total_weeks(schedule)

    proposal = f"""# {name} 프로젝트 기획서

> **Document Control** · Status: Draft · Revision: 0.1 · Owner: Project Owner TBD · Approver: Sponsor/Stakeholder TBD

## Executive Summary
- **목표**: {goal}
- **해결 문제**: {problem}
- **대상/이해관계자**: {users}
- **주요 산출물**: {deliverables}
- **성공 기준**: {success}

## 1. Business / Project Context
### 1.1 추진 배경
{problem}

### 1.2 AS-IS / TO-BE
| 구분 | 내용 |
|---|---|
| AS-IS | {current} |
| TO-BE | {target} |

## 2. Objectives & Success Measures
| Objective ID | Objective | KPI / Measure | Target | Evidence | Status |
|---|---|---|---|---|---|
| OBJ-001 | {goal} | {success} | {success} | QA / 운영 Evidence | Draft |

## 3. Stakeholders
| Stakeholder / Role | 관심사 | 책임 / 기대 | 의사결정 권한 | 상태 |
|---|---|---|---|---|
| {users} | 프로젝트 결과 / 운영성 | TBD | TBD | Draft |

## 4. Scope
### In Scope / Out of Scope
{scope}

## 5. Deliverables & Acceptance
| Deliverable | 목적 | Acceptance / Done 기준 | Owner | 상태 |
|---|---|---|---|---|
| {deliverables} | 프로젝트 목표 달성 | {success} | TBD | Draft |

## 6. Assumptions / Constraints
{constraints}

## 7. Top Risks
| Risk ID | Risk / Assumption | Probability | Impact | Response | Owner | Status |
|---|---|---|---|---|---|---|
| RISK-001 | {risks} | TBD | TBD | Mitigate / Validate | TBD | Open |

## 8. Governance / Decision Gate
- 범위, 비용, 보안/권한, 개인정보/규제, 실제 생산설비 변경은 Human Gate를 통과합니다.
- AI가 제안한 가역적 기본값은 PROVISIONAL이며 승인 전 최종 기준이 아닙니다.

## 9. Approval
| Role | Name | Decision | Date | Comment |
|---|---|---|---|---|
| Project Owner | TBD | Pending | TBD | - |
| Sponsor / Approver | TBD | Pending | TBD | - |
"""

    plan = f"""# {name} 프로젝트 수행 계획서

> **Document Control** · Status: Draft · Revision: 0.1 · Project Type: {ptype}

## 1. Planning Basis
- 목표: {goal}
- 범위: {scope}
- 일정 기준: {schedule}
- 제약: {constraints}

## 2. Delivery Strategy / Lifecycle
| Phase | 목적 | 핵심 산출물 | Exit Criteria |
|---|---|---|---|
| Definition | 목표·범위·요구사항 기준선 | 기획서, 요구사항서 | 핵심 이해관계자 Review |
| Design | 구현 가능한 설계 기준선 | Process, Architecture, Data Flow, UI/API | 주요 설계 Review |
| Build | 실행 가능한 V1 | Code/Config, Backlog Evidence | 핵심 기능 통합 가능 |
| Verify | 품질/운영성 검증 | QA 결과, Evidence | Release Gate 충족 |
| Transition | 인수/운영 전환 | 운영가이드, Release Note | Approver 승인 |

## 3. Deliverable-oriented WBS
| WBS | Work Package | Deliverable | Owner | Dependency | Definition of Done | Status |
|---|---|---|---|---|---|---|
| 1.0 | Definition | 기획/요구사항 기준선 | TBD | - | Review 완료 | Todo |
| 2.0 | Design | Process/Architecture/Data Flow/UI/API | TBD | 1.0 | Design Review 완료 | Todo |
| 3.0 | Build | 실행 가능한 V1 | TBD | 2.0 | 핵심 기능 통합 | Todo |
| 4.0 | Verify | Test Result / Evidence | TBD | 3.0 | Critical Test PASS | Todo |
| 5.0 | Transition | 운영/인수 산출물 | TBD | 4.0 | Acceptance 승인 | Todo |

## 4. Schedule / Milestone
- 상세 일정은 `마일스톤` Gantt를 Source of Truth로 사용합니다.
- 현재 계획 길이: 약 {weeks}주(입력 일정이 구체적이지 않으면 상대 주차 기준 PROVISIONAL).

## 5. RACI / Roles
| Activity | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Scope / Requirement | {team} | TBD | Stakeholders | Team |
| Architecture / Interface | TBD | Technical Lead TBD | Dev/QA/Ops | Team |
| Verification / Acceptance | QA TBD | Project Owner TBD | Dev/Stakeholder | Team |

## 6. Dependency / Assumption Register
| ID | Dependency / Assumption | Needed By | Owner | Validation | Status |
|---|---|---|---|---|---|
| DEP-001 | {constraints} | Design/Build | TBD | Review / PoC | Open |

## 7. Risk / Issue Management
| ID | Type | Description | Probability | Impact | Response | Trigger | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| RISK-001 | Risk | {risks} | TBD | TBD | Mitigate | TBD | TBD | Open |

## 8. Quality / Verification Plan
- Requirement → Test Case → Evidence 추적성을 유지합니다.
- 완료 판단은 AI 자기보고가 아니라 Test/Evidence 및 Exit Criteria를 기준으로 합니다.

## 9. Change / Configuration Management
- Scope/Architecture/Interface 변경은 Decision/ADR로 남깁니다.
- 변경 시 일정, Requirement, Task, QA 영향도를 함께 검토합니다.

## 10. Communication / Reporting
- Blocker, Risk, Decision, 일정 변경은 Project OS에 기록합니다.
- 반복 상태 갱신은 자동화하고 고위험 변경에 Human Gate를 둡니다.
"""

    milestone = f"""# {name} 개발 마일스톤 / Gantt

> **기준 일정** · {schedule}
> **기준 시작일** · TBD · 실제 날짜 확정 전에는 상대 주차 기준 PROVISIONAL

## 1. Gantt Schedule

{_gantt_markdown(schedule)}

## 2. Milestone Gates
| Gate | Goal | Required Deliverables | Entry Criteria | Exit Criteria | Approver | Status |
|---|---|---|---|---|---|---|
| M1 · Definition Baseline | 목표/범위/REQ 기준선 | 기획서/요구사항서 | Project idea defined | 핵심 REQ Review | TBD | Draft |
| M2 · Design Baseline | 구현 가능한 설계 | Process/Architecture/Data Flow/UI/API | M1 | Design Review | TBD | Draft |
| M3 · Build Complete | V1 구현 완료 | Code/Config/Task Evidence | M2 | 핵심 기능 통합 | TBD | Draft |
| M4 · Verification Complete | 품질/인수 기준 충족 | QA/Test Evidence | M3 | Critical Test PASS / Blocker 0 | TBD | Draft |

## 3. Schedule Control
- WBS와 실제 의존성을 기준으로 주차를 갱신합니다.
- 일정 변경은 원인·영향·Recovery Plan과 함께 기록합니다.
- AI가 만든 기간은 승인 전 PROVISIONAL입니다.
"""

    backlog = f"""# {name} Product / Project Backlog

> **목표** · {goal}

## 1. Prioritization / Readiness Rules
- High: V1 목표 또는 핵심 Requirement에 필수
- Ready: 입력/Acceptance/의존성이 구현 시작 가능한 수준
- Done: 구현 + Review + Test/Evidence + 관련 문서 갱신 완료

## 2. Backlog Register
| ID | Epic / Feature | User / System Value | Requirement | Priority | Estimate | Owner | Dependency | Definition of Ready | Definition of Done | Milestone | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BL-001 | Definition | 목표/범위 합의 | REQ-* | High | TBD | TBD | - | 이해관계자/범위 확인 | Requirement Review 완료 | M1 | Todo |
| BL-002 | Design | 구현 가능한 설계 | REQ-* | High | TBD | TBD | BL-001 | 핵심 REQ 정의 | Design Review 완료 | M2 | Todo |
| BL-003 | Build | 핵심 V1 동작 | REQ-* | High | TBD | TBD | BL-002 | Interface/AC 정의 | Test Evidence 확보 | M3 | Todo |
| BL-004 | Verification | 인수 가능한 품질 | REQ-* | High | TBD | TBD | BL-003 | Test Plan 준비 | Release Gate 충족 | M4 | Todo |

## 3. Backlog Governance
- Requirement/Decision 변경 시 관련 Backlog 우선순위와 DoD를 재검토합니다.
- Blocked 항목은 원인/Owner/해제조건을 기록합니다.
"""

    requirements_doc = build_requirements_register(data)

    service_policy = f"""# {name} 서비스 및 운영 정책서

> **Document Control** · Status: Draft · Owner: Service/Ops Owner TBD · Approver: TBD

## 1. Service Scope / Operating Model
- 서비스/시스템 목적: {goal}
- 운영 대상 사용자: {users}
- 운영 제약: {constraints}

## 2. Role / Access Policy
| Role | Responsibility | Allowed Actions | Restricted Actions | Approval / Audit |
|---|---|---|---|---|
| Operator/User | TBD | TBD | TBD | TBD |
| Admin/Ops | TBD | TBD | 비용/고위험 변경은 승인 필요 | Audit Log |

## 3. Service Level / Reliability Objectives
| SLI / Metric | SLO / Target | Measurement Window | Data Source | Breach Action | Status |
|---|---|---|---|---|---|
| Availability / Core Function | TBD | TBD | Monitoring | Incident Response | Draft |
| Latency / Freshness | {success} | TBD | Metrics/Test | Investigate / Recover | Draft |

## 4. Monitoring / Logging / Alerting
| Area | Signal | Alert Condition | Dashboard / Log | Owner | Response |
|---|---|---|---|---|---|
| Availability | Health / heartbeat | TBD | TBD | TBD | Runbook |
| Errors | Error rate / failed events | TBD | TBD | TBD | Incident |
| Capacity / Performance | Latency / resource | TBD | TBD | TBD | Scale/Tune |

## 5. Incident / Problem Management
- Severity 기준, Incident Commander/담당자, 커뮤니케이션 채널을 정의합니다.
- 사용자 영향 중심으로 감지하고, 복구 후 Root Cause / Preventive Action을 남깁니다.

## 6. Backup / Restore / Continuity
| Data / Component | Backup | Retention | RPO | RTO | Restore Test | Owner |
|---|---|---|---|---|---|---|
| Critical Data | TBD | TBD | TBD | TBD | TBD | TBD |

## 7. Data Lifecycle / Retention
- 수집 목적, 보존기간, 삭제/익명화, Export 정책: TBD · 실제 운영 승인 필요

## 8. Release / Change / Rollback
- 변경 승인 기준, 배포 전 검증, Rollback 조건, Emergency Change 절차를 정의합니다.

## 9. Security / Privacy / Compliance Open Items
- Secret/권한 확대, 개인정보 처리, 외부 전송, 법규/계약 의무는 Human Gate 후 확정합니다.
"""

    function_definition = f"""# {name} 기능 정의서

> **Document Control** · Status: Draft · Purpose: Requirement를 구현 가능한 기능/행동으로 구체화

## 1. Feature Catalog
| Function ID | Feature | Actor / Trigger | Preconditions | Input | Business Rules / Normal Flow | Output | Exception / Error | Acceptance Criteria | Related REQ | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FUNC-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* | TBD | Draft |

## 2. Business Rules
| Rule ID | Rule | Rationale / Source | Exception | Related Function/REQ | Status |
|---|---|---|---|---|---|
| BR-001 | TBD | User / Policy / Requirement | TBD | FUNC-001 / REQ-* | Draft |

## 3. State / Event Behaviour
| State / Event | Entry Condition | Action | Exit / Next State | Failure Handling | Evidence |
|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD |

## 4. Open Items
- 미확정 기능/예외는 구현 전에 Acceptance Criteria와 함께 구체화합니다.
"""

    ia = f"""# {name} IA (Information Architecture)

> **Document Control** · Status: Draft · Scope: 메뉴/화면/정보/Navigation 구조

## 1. Navigation Model
```text
Root
├─ Dashboard / Home (TBD)
├─ Main Work Area (TBD)
├─ History / Search (TBD)
└─ Settings / Admin (TBD)
```

## 2. Page / Information Inventory
| IA ID | Depth | Menu / Screen | Purpose | Primary User | Core Information | Entry From | Exit / Link | Permission | Status |
|---|---|---|---|---|---|---|---|---|---|
| IA-001 | 1 | TBD | {goal} | {users} | TBD | Root | TBD | TBD | Draft |

## 3. User Journey / Task Flow
| Flow ID | User Goal | Start | Steps / Screens | Success End | Error / Alternate |
|---|---|---|---|---|---|
| FLOW-001 | TBD | TBD | TBD | TBD | TBD |

## 4. Naming / Navigation Rules
- 같은 개념은 메뉴/화면/문서에서 동일한 용어를 사용합니다.
- Role별 접근 가능 화면과 Empty/Error 상태를 명시합니다.
"""

    screen_design = f"""# {name} 화면 설계서

> **Document Control** · Status: Draft · Purpose: 화면 목적·행동·상태·Validation 기준 정의

## 1. Screen Inventory
| Screen ID | Screen | Purpose | User | Entry Condition | Success / Exit | Related IA/REQ | Status |
|---|---|---|---|---|---|---|---|
| SCR-001 | TBD | {goal} | {users} | TBD | TBD | IA-001 / REQ-* | Draft |

## 2. SCR-001 · Screen Specification
### Layout / Components
| UI ID | Component | Display Data | User Action | Validation | Permission | API / Event | Error / Empty Behaviour |
|---|---|---|---|---|---|---|---|
| UI-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

### Screen State Matrix
| State | Trigger | What User Sees | Allowed Actions | Recovery / Next |
|---|---|---|---|---|
| Loading | Data request | Loading indicator | Wait/Cancel TBD | Success/Error |
| Empty | No data | Empty message + next action | TBD | TBD |
| Error | Request/validation failure | Clear error + cause/action | Retry/Back | TBD |
| Disabled / No Permission | Access restriction | Reason / contact path | None | Request access |

## 3. Interaction / Accessibility / Responsive Notes
- Keyboard/touch/responsive 요구가 있으면 컴포넌트별 기준을 기록합니다.
- 위험한 조작은 확인/권한/상태 조건을 명시합니다.
"""

    system_architecture = f"""# {name} 시스템 아키텍처 설명서

> **Document Control** · Status: Draft · Revision: 0.1 · Architecture Owner: TBD
> **Architecture Basis** · Stakeholder/Concern → Viewpoint/View → Decision/Risk를 추적합니다.

## 1. Architecture Drivers / Stakeholders & Concerns
| Stakeholder | Concern / Quality Attribute | Architecture Response | Evidence / Decision | Status |
|---|---|---|---|---|
| {users} | {success} | TBD | ADR / Test | Draft |

## 2. System Context
- System of Interest: **{name}**
- Mission: {goal}
- External People/Systems: TBD
- 책임 경계: {scope}

> Design > Architecture Canvas에서는 System Boundary, External Actor/System, Application/Service, Data Store를 구분해 표시합니다.

## 3. Container / Major Component View
| Component / Container | Responsibility | Technology | Interface | Data Owned | Dependency | Runtime / Deployment | Owner |
|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 4. Interface / Integration Contracts
| Interface ID | From | To | Purpose | Protocol / Format | Auth / Security | Timeout / Retry | Failure Mode |
|---|---|---|---|---|---|---|---|
| INT-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 5. Deployment / Runtime View
| Environment | Node / Runtime | Deployed Component | Network / Port | Config / Secret | Observability | HA / Recovery |
|---|---|---|---|---|---|---|
| Local/Dev | TBD | TBD | TBD | TBD | TBD | TBD |

## 6. Quality Attribute Scenarios
| QA ID | Attribute | Stimulus / Condition | Expected Response | Measure | Verification |
|---|---|---|---|---|---|
| QA-ARCH-001 | Performance/Reliability | TBD | {success} | TBD | Test |

## 7. Architecture Decisions / Risks
| ADR / Risk | Decision / Concern | Rationale | Alternative | Consequence | Status |
|---|---|---|---|---|---|
| ADR-001 | TBD | TBD | TBD | TBD | Proposed |

## 8. Traceability
- Requirement → Architecture Driver/Component/Interface → Task → Test/Evidence 연결을 유지합니다.
"""

    data_flow = f"""# {name} 데이터 플로우 / 데이터 계약서

> **Document Control** · Status: Draft · Purpose: 데이터 생성→변환→저장→소비→보존 경계 정의

## 1. Data Flow Register
| Flow ID | Source | Data / Event | Trigger / Frequency | Validation / Transform | Destination | Protocol / Format | Failure Handling | Security | Related REQ |
|---|---|---|---|---|---|---|---|---|---|
| DF-001 | TBD | TBD | TBD | TBD | TBD | TBD | Retry/Dead-letter/TBD | TBD | REQ-* |

## 2. Data Dictionary / Contract
| Data ID | Field / Event | Type / Unit | Required | Source of Truth | Validation | Example / Enum | Sensitivity | Retention |
|---|---|---|---|---|---|---|---|---|
| DATA-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 3. State / Event Consistency
- Idempotency, ordering, duplicate handling, timestamp/timezone, reconciliation 기준: TBD

## 4. Ownership / Retention / Recovery
| Dataset | Owner | Store | Retention | Backup / Restore | Export / Delete | Audit |
|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

> Design > Data Flow Canvas는 Source → Processing → Store/Consumer 흐름과 데이터 이름을 함께 표시합니다.
"""

    api_design = f"""# {name} API / Interface 설계 문서

> **Document Control** · Status: Draft · Interface Contract는 구현보다 먼저 합의하고 변경을 추적합니다.

## 1. API Conventions
| Item | Decision |
|---|---|
| API Style | HTTP/REST 또는 프로젝트에 맞는 방식 · TBD |
| Base URL / Versioning | TBD |
| Content Type / Encoding | application/json; UTF-8 (해당 시) |
| Authentication / Authorization | TBD · 운영 보안 승인 필요 |
| Correlation / Request ID | TBD |
| Date / Time | ISO 8601 / timezone rule TBD |

## 2. Endpoint / Message Catalog
| API ID | Method / Type | Path / Topic | Purpose | Auth | Request / Input Schema | Success Response | Error | Timeout / Retry | Idempotency | Related REQ |
|---|---|---|---|---|---|---|---|---|---|---|
| API-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |

## 3. Request / Response Schema
```yaml
# OpenAPI-compatible contract can be generated once endpoints are confirmed.
openapi: 3.2.0
info:
  title: {name}
  version: 0.1.0
paths: {{}}
```

## 4. Error Model
| Code / HTTP | Meaning | Client Action | Retryable | Logging / Alert |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

## 5. Compatibility / Version / Deprecation
- Breaking change 기준, backward compatibility, deprecation window를 운영 전에 합의합니다.

## 6. Security / Reliability
- AuthN/AuthZ, rate limit, timeout, retry, idempotency, input validation, sensitive-data masking을 Interface별로 정의합니다.
"""

    qa = f"""# {name} QA / Test Plan & Result

> **Document Control** · Status: Draft · Test Owner: TBD · Release Approver: TBD

## 1. Test Strategy / Scope
| Test Level / Type | Scope | Environment | Entry Criteria | Exit Criteria | Owner |
|---|---|---|---|---|---|
| Requirement / Functional | 핵심 Requirement | TBD | 구현/환경 준비 | Critical TC PASS | TBD |
| Integration / Interface | API/DB/Device/System 연결 | TBD | Interface 기준선 | 주요 Flow PASS | TBD |
| Non-functional | {success} | TBD | 측정환경 준비 | Target 충족 | TBD |
| Recovery / Operational | 장애/재시작/백업/복구 | TBD | Runbook 준비 | Recovery Criteria 충족 | TBD |

## 2. Test Environment / Data
| Environment | Version / Config | Test Data | Dependency / Simulator | Logging / Evidence | Status |
|---|---|---|---|---|---|
| TEST-ENV-01 | TBD | TBD | TBD | TBD | Draft |

## 3. Test Cases
| TC ID | Requirement | Priority | Preconditions | Test Data | Steps / Action | Expected Result | Actual Result | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| TC-001 | REQ-001 | High | TBD | TBD | TBD | TBD | - | Not Run | TBD |

## 4. Defect / Incident Register
| DEF ID | Severity | Summary | Requirement / TC | Reproduction | Owner | Fix Version | Verification | Status |
|---|---|---|---|---|---|---|---|---|
| DEF-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Open |

## 5. Requirement Traceability / Coverage
| Requirement | Test Case | Result | Evidence | Defect | Coverage Status |
|---|---|---|---|---|---|
| REQ-* | TBD | Not Run | TBD | - | Draft |

## 6. Release / Acceptance Gate
- Critical/Blocker 미해결 0건
- 핵심 Requirement의 Test/Evidence 확보
- 운영/복구/보안 Open Item 승인 또는 명시적 Risk Acceptance
- 최종 Approver 승인

## 7. Test Summary
| Metric | Result | Target / Gate | Decision |
|---|---|---|---|
| Passed / Failed / Blocked | TBD | TBD | Pending |
"""

    return {
        "proposal": proposal,
        "plan": plan,
        "milestone": milestone,
        "backlog": backlog,
        "requirements": requirements_doc,
        "service_policy": service_policy,
        "function_definition": function_definition,
        "ia": ia,
        "screen_design": screen_design,
        "system_architecture": system_architecture,
        "data_flow": data_flow,
        "api_design": api_design,
        "qa": qa,
    }
'''

RUNNER = r'''
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-platform Team Project OS server launcher")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true", help="launcher/platform smoke check only")
    parser.add_argument("--no-install", action="store_true", help="skip pip install")
    args = parser.parse_args()
    if args.check:
        print(f"platform={sys.platform}")
        print(f"root={ROOT}")
        print(f"venv_python={VENV_PYTHON}")
        print(f"requirements={'OK' if (ROOT/'requirements.txt').exists() else 'MISSING'}")
        return 0 if (ROOT / "requirements.txt").exists() else 2
    if not VENV_PYTHON.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT)
    if not args.no_install:
        subprocess.check_call([str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], cwd=ROOT)
    return subprocess.call([str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", str(args.port)], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
'''

MAC = r'''
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" run_project_os.py "$@"
'''

STANDARDS = r'''
# 실무 산출물 설계 기준 (V0.14)

Team Project OS의 문서 템플릿은 특정 회사 양식을 복사하지 않고, 공개된 국제 표준과 널리 쓰이는 실무 관행에서 **필요 정보의 종류와 추적 구조**를 가져옵니다.

## 참고 기준

- Requirements: ISO/IEC/IEEE 29148:2018 — Requirements engineering
  - https://www.iso.org/standard/72089.html
- Architecture Description: ISO/IEC/IEEE 42010:2022
  - https://www.iso.org/standard/74393.html
- Software Test Documentation: ISO/IEC/IEEE 29119-3:2021
  - https://www.iso.org/standard/79429.html
- Project Schedule / WBS: PMI Work Breakdown Structure / Scheduling guidance
  - https://www.pmi.org/standards/work-breakdown-structures-third-edition
  - https://www.pmi.org/learning/library/schedule-101-basic-best-practices-6701/
- Software Architecture Visualization: C4 Model
  - https://c4model.com/diagrams
- HTTP API Contract: OpenAPI Specification 3.2.0
  - https://spec.openapis.org/oas/latest.html
- Operational readiness: Google Cloud Well-Architected / Google SRE
  - https://docs.cloud.google.com/architecture/framework/operational-excellence
  - https://sre.google/resources/practices-and-processes/incident-management-guide/

## 13종 문서 역할

| 문서 | 실무 목적 | 핵심 필드 |
|---|---|---|
| 기획서 | 왜 하는지, 무엇을 성공으로 보는지 합의 | Executive Summary, Problem, Objectives/KPI, Stakeholder, Scope, Deliverable, Risk, Approval |
| 계획서 | 어떻게 수행하고 통제할지 정의 | Lifecycle, deliverable-oriented WBS, RACI, Dependency, Risk, Quality, Change, Communication |
| 마일스톤 | 시간축 실행계획 | Phase/Task, Start/End Week, Owner, Status, Gate/Exit Criteria |
| 백로그 | 실행 단위 관리 | Epic/Feature, Value, Requirement, Priority, Estimate, Dependency, DoR/DoD, Milestone, Status |
| 요구사항 정의서 | 구현·검증 가능한 기준선 | ID, Type, Requirement, Source/Rationale, Priority, Acceptance Criteria, Verification, Owner, Traceability |
| 서비스/운영 정책서 | 운영 책임과 장애/복구/변경 기준 | Role/Access, SLI/SLO, Monitoring, Incident, Backup/RPO/RTO, Retention, Release/Rollback, Security Open Items |
| 기능 정의서 | Requirement를 동작으로 구체화 | Actor/Trigger, Preconditions, Input, Business Rule, Normal/Exception Flow, Output, Acceptance |
| IA | 메뉴·화면·정보 구조 | Navigation, Page Inventory, User Journey, Permission, Naming |
| 화면 설계서 | 화면 행동과 상태 정의 | Screen ID, Components, Data/Action, Validation, Permission, Loading/Empty/Error State, API/Event |
| 시스템 구조도 | 시스템 경계와 책임/관심사 설명 | Drivers/Concerns, Context, Containers/Components, Interfaces, Deployment, Quality Scenario, ADR/Risk |
| 데이터 플로우 | 데이터 수명주기/계약 정의 | Source, Event/Data, Trigger, Validation/Transform, Destination, Protocol, Failure, Dictionary, Retention |
| API 설계 문서 | 구현 전 인터페이스 Contract | Convention, Endpoint, Schema, Error, Timeout/Retry, Idempotency, Version/Deprecation, Security |
| QA 문서 | 검증과 Release 판단 | Strategy, Environment, Test Case, Expected/Actual, Evidence, Defect, Traceability, Release Gate |

## 공통 원칙

1. 문서 형식은 완성된 산출물 구조를 유지합니다.
2. 확인되지 않은 사실은 꾸며내지 않고 `TBD · 확인 필요`로 표시합니다.
3. AI가 선택한 가역적 기본값은 `PROVISIONAL`로 구분합니다.
4. 비용/권한/개인정보/법규/실제 설비 제어는 Human Gate 없이는 확정하지 않습니다.
5. Requirement → Process/Architecture → Backlog/Task → Test/Evidence 추적을 유지합니다.
6. 웹은 읽기 좋은 산출물 뷰가 기본이고 Markdown은 편집/Export용 Source입니다.
'''

TEST = r'''
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.project_intake import build_initial_documents
from local_bridge.project_cli import normalize_live_delta, read_clipboard_text


class V014ProfessionalDocumentsTests(unittest.TestCase):
    def test_all_13_documents_are_delivery_grade(self):
        docs = build_initial_documents({
            "name":"HMI MES Mini Line", "goal":"생산/불량/상태/알람을 실시간 확인하고 이력을 저장",
            "project_type":"manufacturing_automation", "problem":"수기 확인/기록 누락", "users":"작업자, 생산 관리자",
            "deliverables":"Simulator, HMI, Backend, DB, QA", "success_criteria":"1000개 처리 시 화면/DB 수량 일치",
            "scope":"포함=Simulator/HMI/MES, 제외=실제 PLC 구매", "constraints":"Simulator-first",
            "schedule":"10일 V1", "team":"PM/Dev/QA", "risks":"실제 MC Protocol 현장 확인 필요"
        })
        self.assertEqual(len(docs), 13)
        checks = {
            "proposal":["Executive Summary","Approval"],
            "plan":["Deliverable-oriented WBS","RACI","Change / Configuration"],
            "milestone":["Gantt Schedule","Start Week","Milestone Gates"],
            "backlog":["Definition of Ready","Definition of Done","Dependency"],
            "requirements":["Source / Rationale","Acceptance Criteria","Verification","Traceability"],
            "service_policy":["Service Level","Incident","RPO","RTO","Rollback"],
            "function_definition":["Preconditions","Business Rules","Exception / Error"],
            "ia":["Navigation Model","Page / Information Inventory","User Journey"],
            "screen_design":["Screen State Matrix","Validation","Error / Empty"],
            "system_architecture":["Stakeholders & Concerns","System Context","Container / Major Component","Deployment / Runtime"],
            "data_flow":["Data Flow Register","Data Dictionary","Retention"],
            "api_design":["OpenAPI","Endpoint / Message Catalog","Idempotency","Deprecation"],
            "qa":["Test Strategy","Test Cases","Evidence","Release / Acceptance Gate"],
        }
        for key, markers in checks.items():
            for marker in markers:
                self.assertIn(marker, docs[key], f"{key}: {marker}")
        self.assertIn("| 1 | 2 |", docs["milestone"])

    def test_live_delta_normalization_blocks_malformed_shapes(self):
        raw = {
            "project_updates":{"goal":["bad","shape"],"project_type":"manufacturing_automation"},
            "requirements":["bad", {"ref":"REQ-1","title":"상태 저장","acceptance_criteria":"상태 변경 이벤트 기록","priority":"High"}],
            "decisions":[42,{"title":"SQLite","body":"V1","status":"provisional"}],
            "design_updates":[{"view":"architecture","nodes":["bad",{"key":"a","label":"Simulator","kind":"device"},{"key":"b","label":"Backend","kind":"service"}],"edges":[{"source":"a","target":"b","label":"events"},{"source":"a","target":"missing"}]}],
            "pending":[{"unexpected":"dict"},"실제 PLC 연결 미정"]
        }
        result = normalize_live_delta(raw)
        self.assertEqual(len(result["requirements"]), 1)
        self.assertEqual(result["requirements"][0]["priority"], "High")
        self.assertEqual(len(result["design_updates"][0]["edges"]), 1)
        self.assertTrue(all(isinstance(x, str) for x in result["pending"]))

    @patch("local_bridge.project_cli.platform.system", return_value="Darwin")
    @patch("local_bridge.project_cli.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("local_bridge.project_cli.subprocess.run")
    def test_clipboard_reader_supports_multiline_on_macos(self, run, which, system):
        run.return_value.returncode = 0
        run.return_value.stdout = "첫 줄\n둘째 줄\n셋째 줄"
        run.return_value.stderr = ""
        self.assertEqual(read_clipboard_text(), "첫 줄\n둘째 줄\n셋째 줄")


class V014LiveDraftHardeningTests(unittest.TestCase):
    def test_malformed_accumulated_state_never_500s(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = str(Path(td) / "v014.db")
            from app import main
            main.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                draft = client.post("/api/design-drafts", json={"member_name":"승훈","provider":"codex","name_hint":"HMI MES"}).json()
                state = {
                    "project_updates":{"name":"HMI MES Mini Line","goal":"생산/불량/상태/알람 실시간 HMI","project_type":"manufacturing_automation","schedule":"10일 V1","scope":"Simulator-first / 실제 PLC 연결 제외"},
                    "requirements":[{"ref":"REQ-001","title":"생산수량 저장","detail":"제품 완료 이벤트 저장","priority":"High","acceptance_criteria":"1000개 처리 후 DB/화면 수량 일치","verification":"E2E Test"}, "malformed"],
                    "decisions":[{"title":"V1 DB","body":"SQLite","status":"provisional"}, 123],
                    "design_updates":[
                        {"view":"process","mode":"replace","nodes":[{"key":"p1","label":"제품 투입","kind":"event"},{"key":"p2","label":"검사","kind":"process"},{"key":"p3","label":"실적 저장","kind":"database"}],"edges":[{"source":"p1","target":"p2","label":"product"},{"source":"p2","target":"p3","label":"result"}]},
                        {"view":"architecture","mode":"replace","nodes":[{"key":"a1","label":"Simulator","kind":"device"},{"key":"a2","label":"FastAPI","kind":"service"},{"key":"a3","label":"SQLite","kind":"database"},{"key":"a4","label":"Web HMI","kind":"ui"}],"edges":[{"source":"a1","target":"a2","label":"tags"},{"source":"a2","target":"a3","label":"events"},{"source":"a2","target":"a4","label":"WebSocket"}]},
                        {"view":"dataflow","mode":"replace","nodes":[{"key":"d1","label":"Virtual X/Y/M/D","kind":"source"},{"key":"d2","label":"Normalize","kind":"process"},{"key":"d3","label":"Event Store","kind":"database"},{"key":"d4","label":"HMI","kind":"sink"}],"edges":[{"source":"d1","target":"d2","label":"raw tags"},{"source":"d2","target":"d3","label":"events"},{"source":"d2","target":"d4","label":"live state"}]}
                    ],
                    "document_updates":[],
                    "pending":[{"bad":"shape"},"실제 PLC 통신/안전 정책은 추후 승인"]
                }
                for _ in range(5):
                    res = client.put(f"/api/design-drafts/{draft['id']}/sync", json={"member_name":"승훈","state":state})
                    self.assertEqual(res.status_code, 200, res.text)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                self.assertEqual({n["view"] for n in snap["nodes"]}, {"process","architecture","dataflow"})
                reqdoc = next(d for d in snap["documents"] if d["doc_type"] == "requirements")
                self.assertIn("Acceptance Criteria", reqdoc["content"])
                self.assertIn("E2E Test", reqdoc["content"])
                milestone = next(d for d in snap["documents"] if d["doc_type"] == "milestone")
                self.assertIn("Gantt Schedule", milestone["content"])
                promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={"member_name":"승훈","state":state})
                self.assertEqual(promoted.status_code, 200, promoted.text)
                self.assertEqual(promoted.json()["project"]["lifecycle"], "active")


if __name__ == "__main__":
    unittest.main()
'''

SIM = r'''
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def ck(name, value):
    print(f"[V014 FULL] {name}: {'PASS' if value else 'FAIL'}")
    if not value:
        raise SystemExit(1)


def main():
    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = str(Path(td) / "full-v014.db")
        from app import main as app_main
        app_main.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
        app_main.SEED_DEMO = False
        app_main.init_db()
        with TestClient(app_main.app) as client:
            draft = client.post("/api/design-drafts", json={"member_name":"sim-user","provider":"codex","name_hint":"HMI MES"}).json()
            ck("draft", draft.get("lifecycle") == "draft")
            base = {
                "project_updates": {"name":"HMI MES Mini Line","goal":"Mitsubishi 호환 Simulator 기반으로 생산/불량/설비상태/알람을 실시간 표시·저장","project_type":"manufacturing_automation","problem":"수기 상태/실적 확인으로 누락·지연","users":"운전 작업자, 생산 관리자","deliverables":"Simulator, PLC Adapter, FastAPI, Web HMI, SQLite, QA/운영 문서","success_criteria":"제품 1000개 처리 후 화면/DB 수량 일치, 재시작 후 이력 조회","scope":"포함=Simulator/HMI/이력, 제외=실제 PLC 구매/실제 안전제어","current_state":"수기 확인/기록","target_state":"Simulator → Adapter → Service → DB/HMI","constraints":"Simulator-first; 실제 설비 제어는 별도 Human Gate","schedule":"10일 V1","team":"Human PM + Dev/QA + AI Design Worker","risks":"실제 FX5U/MC Protocol 현장 조건은 추후 확인"},
                "requirements":[
                    {"ref":"REQ-001","type":"Functional","title":"생산/불량 이벤트 저장","detail":"제품 완료 시 판정과 시각 저장","priority":"High","acceptance_criteria":"1000개 처리 후 중복 없이 화면/DB 수량 일치","verification":"E2E Test","source":"사용자 요청","status":"defined"},
                    {"ref":"REQ-002","type":"Functional","title":"설비상태/알람 이력","detail":"상태 변경과 알람 발생/확인/해제 기록","priority":"High","acceptance_criteria":"모든 상태전환과 알람 타임스탬프 조회 가능","verification":"Integration Test","source":"사용자 요청","status":"defined"},
                    {"ref":"REQ-003","type":"NonFunctional","title":"실시간 HMI","detail":"현재 상태를 WebSocket으로 반영","priority":"High","acceptance_criteria":"정상 연결 시 목표 500ms 이내 반영","verification":"Measurement","source":"AI provisional + 사용자 승인","status":"defined"}
                ],
                "decisions":[{"title":"Mitsubishi-compatible simulator","body":"X/Y/M/D 가상 디바이스와 교체 가능한 adapter","status":"accepted"},{"title":"V1 FastAPI + SQLite + Web HMI","body":"가역적 로컬 V1 기본값","status":"provisional"}],
                "document_updates":[],
                "design_updates":[
                    {"view":"process","mode":"replace","nodes":[{"key":"p1","label":"제품 투입","kind":"event"},{"key":"p2","label":"컨베이어 이동","kind":"process"},{"key":"p3","label":"검사/판정","kind":"decision"},{"key":"p4","label":"양품/불량 분류","kind":"process"},{"key":"p5","label":"이벤트 저장","kind":"database"},{"key":"p6","label":"HMI 갱신","kind":"ui"}],"edges":[{"source":"p1","target":"p2","label":"detect"},{"source":"p2","target":"p3","label":"arrive"},{"source":"p3","target":"p4","label":"result"},{"source":"p4","target":"p5","label":"production event"},{"source":"p5","target":"p6","label":"KPI/history"}]},
                    {"view":"architecture","mode":"replace","nodes":[{"key":"a1","label":"Conveyor Simulator","kind":"device"},{"key":"a2","label":"PLC Adapter","kind":"service"},{"key":"a3","label":"FastAPI MES Service","kind":"service"},{"key":"a4","label":"SQLite Event Store","kind":"database"},{"key":"a5","label":"Web HMI","kind":"ui"}],"edges":[{"source":"a1","target":"a2","label":"virtual X/Y/M/D"},{"source":"a2","target":"a3","label":"normalized state/events"},{"source":"a3","target":"a4","label":"event records"},{"source":"a3","target":"a5","label":"REST/WebSocket"}]},
                    {"view":"dataflow","mode":"replace","nodes":[{"key":"d1","label":"Virtual PLC Memory","kind":"source"},{"key":"d2","label":"Validate / Normalize","kind":"process"},{"key":"d3","label":"Business Event Processor","kind":"service"},{"key":"d4","label":"SQLite Store","kind":"database"},{"key":"d5","label":"HMI Consumer","kind":"sink"}],"edges":[{"source":"d1","target":"d2","label":"raw device values"},{"source":"d2","target":"d3","label":"validated event"},{"source":"d3","target":"d4","label":"production/state/alarm"},{"source":"d3","target":"d5","label":"live state"},{"source":"d4","target":"d5","label":"history/KPI"}]}
                ],
                "pending":["실제 PLC 모델/현장 네트워크/안전회로는 실제 적용 전 승인"]
            }
            # Repeated incremental syncs emulate the user's long Design Session and guard against the previous HTTP 500 regression.
            for i in range(8):
                state = dict(base)
                state["pending"] = list(base["pending"]) + ([{"malformed":"model delta"}] if i in {2,4,6} else [])
                if i == 3:
                    state["requirements"] = list(base["requirements"]) + ["malformed requirement"]
                res = client.put(f"/api/design-drafts/{draft['id']}/sync", json={"member_name":"sim-user","state":state})
                ck(f"live_sync_{i+1}", res.status_code == 200)
            snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            ck("documents_13", len(snap["documents"]) == 13)
            markers = {
                "proposal":"Executive Summary", "plan":"Deliverable-oriented WBS", "milestone":"Gantt Schedule",
                "backlog":"Definition of Done", "requirements":"Acceptance Criteria", "service_policy":"Incident",
                "function_definition":"Preconditions", "ia":"Navigation Model", "screen_design":"Screen State Matrix",
                "system_architecture":"System Context", "data_flow":"Data Dictionary", "api_design":"OpenAPI", "qa":"Test Strategy",
            }
            docs = {d["doc_type"]: d["content"] for d in snap["documents"]}
            for dt, marker in markers.items(): ck(f"doc_{dt}", marker in docs.get(dt, ""))
            ck("requirements_3", len(snap["requirements"]) == 3)
            ck("design_views", {n["view"] for n in snap["nodes"]} == {"process","architecture","dataflow"})
            for view in ("process","architecture","dataflow"):
                ids={n["id"] for n in snap["nodes"] if n["view"]==view}
                edges=[e for e in snap["edges"] if e["view"]==view]
                ck(f"{view}_edge_integrity", bool(ids) and all(e["source_id"] in ids and e["target_id"] in ids for e in edges))
            promoted=client.post(f"/api/design-drafts/{draft['id']}/promote", json={"member_name":"sim-user","state":base})
            ck("apply", promoted.status_code==200 and promoted.json()["project"]["lifecycle"]=="active")
            final=client.get(f"/api/projects/{draft['id']}/snapshot").json()
            ck("persist_documents", len(final["documents"])==13)
            ck("persist_designs", {n["view"] for n in final["nodes"]}=={"process","architecture","dataflow"})
            ck("health_v014", client.get('/api/health').json().get('version')=='0.14.0')
            print("[V014 FULL] PROJECT + 13 PROFESSIONAL DOCUMENTS + 3 DIAGRAMS + LIVE SYNC: PASS")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'''


write("app/delivery_documents.py", DELIVERY)
write("run_project_os.py", RUNNER)
write("run_mac.sh", MAC)
write("docs/DELIVERABLE_STANDARDS.md", STANDARDS)
write("tests/test_v014_hardening.py", TEST)
write("tools/simulate_full_project_v014.py", SIM)

# project_intake -> centralized 13-document builder
p = ROOT / "app/project_intake.py"
s = p.read_text(encoding="utf-8")
if "from app.delivery_documents import build_delivery_documents" not in s:
    s = s.replace("import re\nfrom typing import Any\n", "import re\nfrom typing import Any\n\nfrom app.delivery_documents import build_delivery_documents\n", 1)
a = s.index("def build_initial_documents(data: dict[str, Any]) -> dict[str, str]:")
b = s.index("\ndef intake_metadata()", a)
s = s[:a] + "def build_initial_documents(data: dict[str, Any]) -> dict[str, str]:\n    return build_delivery_documents(data)\n\n" + s[b+1:]
p.write_text(s, encoding="utf-8")

# conversation normalization: preserve professional requirement attributes
p = ROOT / "app/conversation.py"
s = p.read_text(encoding="utf-8")
old = '''        requirements.append({
            "ref": _clip(item.get("ref"), 40),
            "title": title,
            "detail": _clip(item.get("detail"), 4000),
            "status": _clip(item.get("status") or "defined", 40),
        })'''
new = '''        requirements.append({
            "ref": _clip(item.get("ref"), 40),
            "type": _clip(item.get("type") or "Functional", 60),
            "title": title,
            "detail": _clip(item.get("detail"), 4000),
            "source": _clip(item.get("source") or item.get("rationale") or "User / Design Session", 500),
            "priority": _clip(item.get("priority") or "TBD", 40),
            "acceptance_criteria": _clip(item.get("acceptance_criteria") or "TBD · 확인 필요", 2000),
            "verification": _clip(item.get("verification") or "Test / Review", 500),
            "owner": _clip(item.get("owner") or "TBD", 120),
            "traceability": _clip(item.get("traceability") or "Process/Task/Test 연결 예정", 500),
            "status": _clip(item.get("status") or "defined", 40),
        })'''
if old not in s and new not in s:
    raise RuntimeError("conversation requirement normalizer marker not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# app/main.py: centralized templates, sanitization, rich requirement live document, version
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8")
if "from app.delivery_documents import DOCUMENT_ORDER, build_delivery_documents, build_requirements_register" not in s:
    s = s.replace("from app.project_intake import build_initial_documents, evaluate_intake, intake_metadata\n", "from app.project_intake import build_initial_documents, evaluate_intake, intake_metadata\nfrom app.delivery_documents import DOCUMENT_ORDER, build_delivery_documents, build_requirements_register\n", 1)
s = s.replace('version="0.13.0"', 'version="0.14.0"', 1)
start = s.index("DOCUMENT_TEMPLATES = [")
end = s.index("\n\n\n\n\n@contextmanager", start)
replacement = '''_BASE_DOCUMENTS = build_delivery_documents({})
DOCUMENT_TEMPLATES = [
    (doc_type, title, _BASE_DOCUMENTS[doc_type])
    for doc_type, title in DOCUMENT_ORDER
]'''
s = s[:start] + replacement + s[end:]

# Replace simplified live requirements section with the same delivery-grade register.
a = s.index("    if requirements:\n", s.index("def build_live_draft_documents"))
b = s.index("\n    if decisions or pending_items:", a)
s = s[:a] + '    if requirements:\n        generated["requirements"] = build_requirements_register(brief, requirements)\n' + s[b:]

# Defensive server-side normalizer for any model delta/state.
marker = "\ndef apply_live_draft_state(conn: sqlite3.Connection, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = \"draft\") -> dict[str, Any]:\n"
helper = '''\ndef sanitize_live_state(state: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(state or {}) if isinstance(state, dict) else {}
    raw["reply"] = "Live Draft"
    try:
        parsed = normalize_ai_result(json.dumps(raw, ensure_ascii=False))
    except Exception:
        parsed = normalize_ai_result(json.dumps({"reply": "Live Draft"}, ensure_ascii=False))
    return {
        "project_updates": parsed.get("project_updates", {}),
        "requirements": parsed.get("requirements", []),
        "decisions": parsed.get("decisions", []),
        "document_updates": parsed.get("document_updates", []),
        "design_updates": parsed.get("design_updates", []),
        "pending": parsed.get("pending", []),
    }

'''
if helper.strip() not in s:
    if marker not in s:
        raise RuntimeError("apply_live_draft_state marker not found")
    s = s.replace(marker, helper + marker, 1)
needle = 'def apply_live_draft_state(conn: sqlite3.Connection, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft") -> dict[str, Any]:\n    project = conn.execute'
repl = 'def apply_live_draft_state(conn: sqlite3.Connection, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft") -> dict[str, Any]:\n    state = sanitize_live_state(state)\n    project = conn.execute'
if needle not in s and repl not in s:
    raise RuntimeError("state sanitize insertion marker not found")
s = s.replace(needle, repl, 1)
p.write_text(s, encoding="utf-8")

# project_cli: clipboard paste + normalized live deltas
p = ROOT / "local_bridge/project_cli.py"
s = p.read_text(encoding="utf-8")
if "import platform" not in s:
    s = s.replace("import json\nimport sys\n", "import json\nimport platform\nimport shutil\nimport subprocess\nimport sys\n", 1)
s = s.replace('"명령: /status, /autofill on|off, /preview, /apply, /discard, /quit"', '"명령: /status, /paste, /autofill on|off, /preview, /apply, /discard, /quit"', 1)
anchor = "\ndef _merge_by_key(existing: list[dict], incoming: list[dict], key_name: str) -> list[dict]:\n"
helpers = r'''

def normalize_live_delta(delta: dict) -> dict:
    """Apply the same whitelist/type normalization used by the final Distiller.

    Live model output is intentionally compact and can occasionally contain a
    malformed list/object. Normalizing before accumulation prevents one bad turn
    from poisoning every later Live Draft sync.
    """
    if not isinstance(delta, dict):
        return blank_live_state()
    payload = dict(delta)
    payload["reply"] = "Live Draft"
    try:
        parsed = normalize_ai_result(json.dumps(payload, ensure_ascii=False))
    except Exception:
        return blank_live_state()
    return {k: parsed.get(k, blank_live_state()[k]) for k in blank_live_state()}


def read_clipboard_text() -> str:
    """Read the OS clipboard without requiring Ctrl+V in legacy terminals."""
    system = platform.system()
    commands: list[list[str]] = []
    if system == "Windows":
        commands = [
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            ["pwsh", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
        ]
    elif system == "Darwin":
        commands = [["pbpaste"]]
    else:
        commands = [["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]
    for cmd in commands:
        if not shutil.which(cmd[0]):
            continue
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            if p.returncode == 0 and (p.stdout or "").strip():
                return (p.stdout or "").strip()
        except Exception:
            pass
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        value = root.clipboard_get(); root.destroy()
        return str(value or "").strip()
    except Exception as exc:
        raise RuntimeError("클립보드를 읽을 수 없습니다. Windows Terminal/macOS Terminal에서 다시 시도하거나 한 줄 입력을 사용하세요.") from exc
'''
if "def normalize_live_delta" not in s:
    if anchor not in s:
        raise RuntimeError("project_cli helper anchor not found")
    s = s.replace(anchor, helpers + anchor, 1)

old = '        command = user_text.lower()\n        if command in {"/quit", "/exit"}:'
new = '''        command = user_text.lower()
        if command == "/paste":
            try:
                user_text = read_clipboard_text()
            except Exception as exc:
                print(f"클립보드 읽기 실패: {exc}")
                continue
            if not user_text:
                print("클립보드가 비어 있습니다.")
                continue
            lines = user_text.count("\\n") + 1
            print(f"[Clipboard] {lines}줄을 하나의 메시지로 불러왔습니다.")
            command = user_text.lower()
        if command in {"/quit", "/exit"}:'''
if old not in s and new not in s:
    raise RuntimeError("project_cli command marker not found")
s = s.replace(old, new, 1)
s = s.replace("        if live_delta:\n            live_state = merge_live_state(live_state, live_delta)", "        if live_delta:\n            live_delta = normalize_live_delta(live_delta)\n            live_state = merge_live_state(live_state, live_delta)", 1)
p.write_text(s, encoding="utf-8")

# providers: platform-specific doctor hint
p = ROOT / "local_bridge/providers.py"
s = p.read_text(encoding="utf-8")
old = '''        raise RuntimeError(
            f"Local CLI not found: {executable}. "
            f"Run 'python project_os.py doctor' and 'where {executable}' on Windows."
        )'''
new = '''        locator = "where" if platform.system() == "Windows" else "which"
        py = "python" if platform.system() == "Windows" else "python3"
        raise RuntimeError(
            f"Local CLI not found: {executable}. "
            f"Run '{py} project_os.py doctor' and '{locator} {executable}'."
        )'''
if old not in s and new not in s:
    raise RuntimeError("provider missing-cli marker not found")
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# README lightweight version/mac/paste notes; detailed standards live in docs.
p = ROOT / "README.md"
s = p.read_text(encoding="utf-8")
s = s.replace("# Team Project OS V0.13", "# Team Project OS V0.14", 1)
s = s.replace("# Team Project OS V0.12", "# Team Project OS V0.14", 1)
s = s.replace("# Team Project OS V0.11", "# Team Project OS V0.14", 1)
if "## macOS 실행" not in s:
    insert = '''\n## macOS 실행\n\nPython 3.11+ 설치 후:\n\n```bash\ngit clone https://github.com/tmdgns104/team_project_os.git\ncd team_project_os\nbash run_mac.sh\n```\n\n브라우저: `http://localhost:8000`\n\nAI CLI 확인:\n\n```bash\npython3 project_os.py doctor\n```\n\nCodex Design Session:\n\n```bash\npython3 project_os.py design --provider codex --member "내 이름" --autofill\n```\n\nWindows CMD에서 Ctrl+V가 불편하거나 macOS에서 여러 줄을 한 번에 넣고 싶으면, 텍스트를 OS 클립보드에 복사한 뒤 Design Session에서 `/paste`를 입력합니다. 클립보드의 여러 줄을 **한 메시지**로 읽습니다.\n\n'''
    anchor = "# 가장 빠른 Windows 실행\n"
    if anchor in s:
        s = s.replace(anchor, insert + anchor, 1)
    else:
        s = s + insert
if "DELIVERABLE_STANDARDS.md" not in s:
    s += "\n- `docs/DELIVERABLE_STANDARDS.md` — 13종 실무 산출물의 국제표준/실무 기준과 필드 정의\n"
p.write_text(s, encoding="utf-8")

print("V0.14 upgrade prepared")
