from __future__ import annotations

import math
import re
from typing import Any

DOCUMENT_ORDER = [
    ("proposal", "기획서"), ("plan", "계획서"), ("milestone", "마일스톤"),
    ("backlog", "백로그"), ("requirements", "요구사항 정의서"),
    ("service_policy", "서비스 및 운영 정책서"), ("function_definition", "기능 정의서"),
    ("ia", "IA (Information Architecture, 정보구조도)"), ("screen_design", "화면 설계서"),
    ("system_architecture", "시스템 구조도"), ("data_flow", "데이터 플로우"),
    ("api_design", "API 설계 문서"), ("qa", "QA 문서"),
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


def gantt_rows(schedule: str) -> list[tuple[str, str, str, int, int, str, str]]:
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


def gantt_markdown(schedule: str) -> str:
    lines = ["| Phase | ID | Task | Start Week | End Week | Owner | Status |", "|---|---|---|---|---|---|---|"]
    lines += ["| " + " | ".join(map(str, row)) + " |" for row in gantt_rows(schedule)]
    return "\n".join(lines)


def build_requirements_register(data: dict[str, Any], requirements: list[dict[str, Any]] | None = None) -> str:
    name, goal, scope = _text(data, "name", "프로젝트명 TBD"), _text(data, "goal"), _text(data, "scope")
    rows = requirements or [{"ref": "REQ-001", "title": "TBD", "detail": "Design Session에서 구체화", "status": "Draft"}]
    body = []
    for idx, item in enumerate(rows, 1):
        body.append("| " + " | ".join([
            _safe(item.get("ref") or f"REQ-{idx:03d}"), _safe(item.get("type") or "Functional"),
            _safe(item.get("title") or "TBD"), _safe(item.get("detail") or "TBD"),
            _safe(item.get("source") or item.get("rationale") or "User / Design Session"),
            _safe(item.get("priority") or "TBD"), _safe(item.get("acceptance_criteria") or "TBD · 확인 필요"),
            _safe(item.get("verification") or "Test / Review"), _safe(item.get("owner") or "TBD"),
            _safe(item.get("status") or "Draft"), _safe(item.get("traceability") or "Process/Task/Test 연결 예정"),
        ]) + " |")
    return f"""# {name} 요구사항 정의서

> **Document Control** · Status: Draft · Revision: 0.1 · Owner: TBD · Approver: TBD
> **작성 원칙** · 명확성·추적성·검증 가능성을 유지하고 미확정 정보는 TBD로 둡니다.

## 1. Purpose / Scope
- 프로젝트 목표: {goal}
- 적용 범위: {scope}

## 2. Requirement Quality Rules
- 한 Requirement는 하나의 검증 가능한 결과를 표현합니다.
- 각 Requirement는 Source/Rationale, Priority, Acceptance Criteria, Verification을 가집니다.
- 변경 시 Process, Architecture, Backlog/Task, Test/Evidence 영향을 함께 확인합니다.

## 3. Requirements Register
| ID | Type | Requirement | Detail | Source / Rationale | Priority | Acceptance Criteria | Verification | Owner | Status | Traceability |
|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(body)}

## 4. Non-Functional Requirements
| NFR ID | Quality Attribute | Requirement / Target | Measurement | Verification | Status |
|---|---|---|---|---|---|
| NFR-001 | Performance / Quality | {_safe(_text(data, 'success_criteria'))} | TBD | Measurement / Test | Draft |
| NFR-002 | Reliability / Recovery | TBD | TBD | Recovery Test | Draft |
| NFR-003 | Security / Privacy | TBD · 실제 운영 승인 필요 | TBD | Review / Test | Draft |
| NFR-004 | Maintainability / Operability | {_safe(_text(data, 'constraints'))} | TBD | Review | Draft |

## 5. Traceability Matrix
| Requirement | Process / Architecture | Backlog / Task | Test Case | Evidence | Status |
|---|---|---|---|---|---|
| REQ-* | TBD | TBD | TBD | TBD | Draft |

## 6. Open Items / Approval
- Acceptance Criteria가 없는 항목은 Baseline 승인 전까지 Draft입니다.
- 비용·보안·개인정보·법규·실제 설비 제어는 담당자 승인 후 확정합니다.
"""


def build_delivery_documents(data: dict[str, Any]) -> dict[str, str]:
    name = _text(data, "name", "프로젝트명 TBD")
    goal, problem, users = _text(data, "goal"), _text(data, "problem"), _text(data, "users")
    deliverables, success, scope = _text(data, "deliverables"), _text(data, "success_criteria"), _text(data, "scope")
    current, target = _text(data, "current_state"), _text(data, "target_state")
    constraints, schedule, team, risks = _text(data, "constraints"), _text(data, "schedule"), _text(data, "team"), _text(data, "risks")
    ptype, weeks = _text(data, "project_type", "generic"), _total_weeks(schedule)

    proposal = f"""# {name} 프로젝트 기획서

> **Document Control** · Status: Draft · Revision: 0.1 · Owner: Project Owner TBD · Approver: Sponsor/Stakeholder TBD

## Executive Summary
| Item | Summary |
|---|---|
| Goal | {goal} |
| Problem | {problem} |
| Users / Stakeholders | {users} |
| Deliverables | {deliverables} |
| Success Criteria | {success} |

## 1. Business / Project Context
### 1.1 Problem Statement
{problem}

### 1.2 AS-IS / TO-BE
| AS-IS | TO-BE |
|---|---|
| {current} | {target} |

## 2. Objectives & Success Measures
| Objective ID | Objective | KPI / Measure | Target | Evidence | Status |
|---|---|---|---|---|---|
| OBJ-001 | {goal} | {success} | {success} | QA / Operational Evidence | Draft |

## 3. Stakeholders
| Stakeholder / Role | Concern | Responsibility / Expectation | Decision Authority | Status |
|---|---|---|---|---|
| {users} | Value / usability / operability | TBD | TBD | Draft |

## 4. Scope / Boundary
{scope}

## 5. Deliverables & Acceptance
| Deliverable | Purpose | Acceptance / Done Criteria | Owner | Status |
|---|---|---|---|---|
| {deliverables} | Project goal achievement | {success} | TBD | Draft |

## 6. Assumptions / Constraints
{constraints}

## 7. Top Risks
| Risk ID | Risk / Assumption | Probability | Impact | Response | Owner | Status |
|---|---|---|---|---|---|---|
| RISK-001 | {risks} | TBD | TBD | Mitigate / Validate | TBD | Open |

## 8. Governance / Decision Gate
- 비용, 권한/Secret, 개인정보/법규, 실제 설비 제어와 파괴적 변경은 Human Gate를 거칩니다.
- AI가 선택한 가역적 기본값은 `PROVISIONAL`이며 최종 승인으로 간주하지 않습니다.

## 9. Approval
| Role | Name | Decision | Date | Comment |
|---|---|---|---|---|
| Project Owner | TBD | Pending | TBD | - |
| Sponsor / Approver | TBD | Pending | TBD | - |
"""

    plan = f"""# {name} 프로젝트 수행 계획서

> **Document Control** · Status: Draft · Revision: 0.1 · Project Type: {ptype}

## 1. Planning Basis
- Goal: {goal}
- Scope: {scope}
- Schedule basis: {schedule}
- Constraints: {constraints}

## 2. Delivery Strategy / Lifecycle
| Phase | Purpose | Key Deliverables | Exit Criteria |
|---|---|---|---|
| Definition | 목표·범위·요구사항 기준선 | 기획서 / 요구사항서 | Core Requirement Review |
| Design | 구현 가능한 설계 기준선 | Process / Architecture / Data Flow / UI / API | Design Review |
| Build | 실행 가능한 V1 | Code / Config / Backlog Evidence | Core Integration Ready |
| Verify | 품질·운영성 검증 | QA / Test Evidence | Release Gate |
| Transition | 인수·운영 전환 | 운영가이드 / Release Note | Approver Acceptance |

## 3. Deliverable-oriented WBS
| WBS | Work Package | Deliverable | Owner | Dependency | Definition of Done | Status |
|---|---|---|---|---|---|---|
| 1.0 | Definition | 기획/요구사항 기준선 | TBD | - | Review 완료 | Todo |
| 2.0 | Design | Process/Architecture/Data Flow/UI/API | TBD | 1.0 | Design Review 완료 | Todo |
| 3.0 | Build | 실행 가능한 V1 | TBD | 2.0 | 핵심 기능 통합 | Todo |
| 4.0 | Verify | Test Result / Evidence | TBD | 3.0 | Critical Test PASS | Todo |
| 5.0 | Transition | 운영/인수 산출물 | TBD | 4.0 | Acceptance 승인 | Todo |

## 4. Schedule / Milestone
- 상세 일정 Source of Truth: `마일스톤` Gantt
- 현재 계획 길이: 약 {weeks}주. 실제 날짜/인력이 미정이면 PROVISIONAL 상대 주차입니다.

## 5. RACI / Roles
| Activity | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Scope / Requirement | {team} | TBD | Stakeholders | Team |
| Architecture / Interface | TBD | Technical Lead TBD | Dev / QA / Ops | Team |
| Verification / Acceptance | QA TBD | Project Owner TBD | Dev / Stakeholder | Team |

## 6. Dependencies / Assumptions
| ID | Dependency / Assumption | Needed By | Owner | Validation | Status |
|---|---|---|---|---|---|
| DEP-001 | {constraints} | Design / Build | TBD | Review / PoC | Open |

## 7. Risk / Issue Management
| ID | Type | Description | Probability | Impact | Response | Trigger | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| RISK-001 | Risk | {risks} | TBD | TBD | Mitigate | TBD | TBD | Open |

## 8. Quality / Verification Plan
- Requirement → Test Case → Evidence 추적성을 유지합니다.
- 완료 판단은 AI 자기보고가 아니라 Test/Evidence와 Exit Criteria를 기준으로 합니다.

## 9. Change / Configuration Management
- Scope/Architecture/Interface 변경은 Decision/ADR로 기록합니다.
- 변경 시 일정, Requirement, Task, QA 영향도를 함께 검토합니다.

## 10. Communication / Reporting
- Blocker, Risk, Decision, 일정 변경은 Project OS에 기록합니다.
"""

    milestone = f"""# {name} 개발 마일스톤 / Gantt

> **기준 일정** · {schedule}
> **기준 시작일** · TBD · 실제 날짜 확정 전에는 상대 주차 기준 PROVISIONAL

## 1. Gantt Schedule
{gantt_markdown(schedule)}

## 2. Milestone Gates
| Gate | Goal | Required Deliverables | Entry Criteria | Exit Criteria | Approver | Status |
|---|---|---|---|---|---|---|
| M1 · Definition Baseline | 목표/범위/REQ 기준선 | 기획서 / 요구사항서 | Project idea defined | Core REQ Review | TBD | Draft |
| M2 · Design Baseline | 구현 가능한 설계 | Process / Architecture / Data Flow / UI / API | M1 | Design Review | TBD | Draft |
| M3 · Build Complete | V1 구현 완료 | Code / Config / Task Evidence | M2 | Core integration ready | TBD | Draft |
| M4 · Verification Complete | 품질/인수 기준 충족 | QA / Test Evidence | M3 | Critical PASS / Blocker 0 | TBD | Draft |

## 3. Schedule Control
- WBS·Dependency·가용 인력을 기준으로 일정 기준선을 갱신합니다.
- 일정 변경은 원인, 영향, Recovery Plan과 함께 기록합니다.
"""

    backlog = f"""# {name} Product / Project Backlog

> **Goal** · {goal}

## 1. Prioritization / Readiness Rules
- High: V1 목표 또는 핵심 Requirement 달성에 필수
- Ready: 입력/Acceptance/Dependency가 구현 시작 가능한 수준
- Done: 구현 + Review + Test/Evidence + 관련 문서 갱신

## 2. Backlog Register
| ID | Epic / Feature | User / System Value | Requirement | Priority | Estimate | Owner | Dependency | Definition of Ready | Definition of Done | Milestone | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BL-001 | Definition | 목표/범위 합의 | REQ-* | High | TBD | TBD | - | Scope 확인 | Requirement Review | M1 | Todo |
| BL-002 | Design | 구현 가능한 설계 | REQ-* | High | TBD | TBD | BL-001 | Core REQ 정의 | Design Review | M2 | Todo |
| BL-003 | Build | 핵심 V1 동작 | REQ-* | High | TBD | TBD | BL-002 | Interface/AC 정의 | Test Evidence | M3 | Todo |
| BL-004 | Verification | 인수 가능한 품질 | REQ-* | High | TBD | TBD | BL-003 | Test Plan 준비 | Release Gate | M4 | Todo |

## 3. Backlog Governance
- Requirement/Decision 변경 시 Priority, Dependency, DoD를 재검토합니다.
"""

    service_policy = f"""# {name} 서비스 및 운영 정책서

> **Document Control** · Status: Draft · Service/Ops Owner: TBD · Approver: TBD

## 1. Service Scope / Operating Model
- Mission: {goal}
- Users: {users}
- Constraints: {constraints}

## 2. Role / Access Policy
| Role | Responsibility | Allowed Actions | Restricted Actions | Approval / Audit |
|---|---|---|---|---|
| Operator / User | TBD | TBD | TBD | TBD |
| Admin / Ops | TBD | TBD | 비용/고위험 변경 | Audit Log / Approval |

## 3. Service Level / Reliability Objectives
| SLI / Metric | SLO / Target | Window | Data Source | Breach Action | Status |
|---|---|---|---|---|---|
| Availability / Core Function | TBD | TBD | Monitoring | Incident Response | Draft |
| Latency / Freshness / Quality | {success} | TBD | Metrics / Test | Investigate / Recover | Draft |

## 4. Monitoring / Logging / Alerting
| Area | Signal | Alert Condition | Dashboard / Log | Owner | Response |
|---|---|---|---|---|---|
| Availability | Health / heartbeat | TBD | TBD | TBD | Runbook |
| Errors | Error / failed event rate | TBD | TBD | TBD | Incident |
| Capacity / Performance | Latency / resource | TBD | TBD | TBD | Tune / Scale |

## 5. Incident / Problem Management
- Severity, Incident Owner/Commander, communication channel, escalation, recovery, RCA/Preventive Action을 정의합니다.

## 6. Backup / Restore / Continuity
| Data / Component | Backup | Retention | RPO | RTO | Restore Test | Owner |
|---|---|---|---|---|---|---|
| Critical Data | TBD | TBD | TBD | TBD | TBD | TBD |

## 7. Data Lifecycle / Retention
- 수집 목적, 보존, 삭제/익명화, Export 정책: TBD · 실제 운영 승인 필요

## 8. Release / Change / Rollback
- Change approval, pre-release verification, Rollback condition, Emergency Change 절차를 정의합니다.

## 9. Security / Privacy / Compliance Open Items
- Secret/권한, 개인정보, 외부 전송, 법규/계약 의무는 Human Gate 후 확정합니다.
"""

    function_definition = f"""# {name} 기능 정의서

> **Document Control** · Status: Draft · Requirement를 구현 가능한 동작으로 구체화

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
"""

    ia = f"""# {name} IA (Information Architecture)

> **Document Control** · Status: Draft · 메뉴/화면/정보/Navigation 구조

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
- 같은 개념은 메뉴·화면·문서에서 같은 용어를 사용합니다.
- Role별 접근 가능 화면과 Empty/Error 상태를 명시합니다.
"""

    screen_design = f"""# {name} 화면 설계서

> **Document Control** · Status: Draft · 화면 목적·행동·상태·Validation 기준

## 1. Screen Inventory
| Screen ID | Screen | Purpose | User | Entry Condition | Success / Exit | Related IA/REQ | Status |
|---|---|---|---|---|---|---|---|
| SCR-001 | TBD | {goal} | {users} | TBD | TBD | IA-001 / REQ-* | Draft |

## 2. SCR-001 · Screen Specification
| UI ID | Component | Display Data | User Action | Validation | Permission | API / Event | Error / Empty Behaviour |
|---|---|---|---|---|---|---|---|
| UI-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 3. Screen State Matrix
| State | Trigger | What User Sees | Allowed Actions | Recovery / Next |
|---|---|---|---|---|
| Loading | Data request | Loading indicator | Wait / Cancel TBD | Success / Error |
| Empty | No data | Empty message + next action | TBD | TBD |
| Error | Request/validation failure | Error + cause/action | Retry / Back | TBD |
| Disabled / No Permission | Access restriction | Reason / contact path | None | Request access |

## 4. Interaction / Accessibility / Responsive Notes
- Keyboard/touch/responsive 기준과 위험 조작의 확인/권한 조건을 기록합니다.
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
- Boundary: {scope}

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
| Local / Dev | TBD | TBD | TBD | TBD | TBD | TBD |

## 6. Quality Attribute Scenarios
| QA ID | Attribute | Stimulus / Condition | Expected Response | Measure | Verification |
|---|---|---|---|---|---|
| QA-ARCH-001 | Performance / Reliability | TBD | {success} | TBD | Test |

## 7. Architecture Decisions / Risks
| ADR / Risk | Decision / Concern | Rationale | Alternative | Consequence | Status |
|---|---|---|---|---|---|
| ADR-001 | TBD | TBD | TBD | TBD | Proposed |

## 8. Traceability
- Requirement → Driver/Component/Interface → Task → Test/Evidence 연결을 유지합니다.
"""

    data_flow = f"""# {name} 데이터 플로우 / 데이터 계약서

> **Document Control** · Status: Draft · 데이터 생성→변환→저장→소비→보존 경계 정의

## 1. Data Flow Register
| Flow ID | Source | Data / Event | Trigger / Frequency | Validation / Transform | Destination | Protocol / Format | Failure Handling | Security | Related REQ |
|---|---|---|---|---|---|---|---|---|---|
| DF-001 | TBD | TBD | TBD | TBD | TBD | TBD | Retry / Recovery TBD | TBD | REQ-* |

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
- Breaking change, backward compatibility, deprecation window를 운영 전에 합의합니다.

## 6. Security / Reliability
- AuthN/AuthZ, rate limit, timeout, retry, idempotency, input validation, sensitive-data masking을 정의합니다.
"""

    qa = f"""# {name} QA / Test Plan & Result

> **Document Control** · Status: Draft · Test Owner: TBD · Release Approver: TBD

## 1. Test Strategy / Scope
| Test Level / Type | Scope | Environment | Entry Criteria | Exit Criteria | Owner |
|---|---|---|---|---|---|
| Requirement / Functional | Core Requirement | TBD | 구현/환경 준비 | Critical TC PASS | TBD |
| Integration / Interface | API/DB/Device/System | TBD | Interface baseline | Core Flow PASS | TBD |
| Non-functional | {success} | TBD | Measurement ready | Target met | TBD |
| Recovery / Operational | Failure/restart/backup/restore | TBD | Runbook ready | Recovery Criteria | TBD |

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
- Core Requirement Test/Evidence 확보
- 운영/복구/보안 Open Item 승인 또는 명시적 Risk Acceptance
- Final Approver 승인

## 7. Test Summary
| Metric | Result | Target / Gate | Decision |
|---|---|---|---|
| Passed / Failed / Blocked | TBD | TBD | Pending |
"""

    return {
        "proposal": proposal, "plan": plan, "milestone": milestone, "backlog": backlog,
        "requirements": build_requirements_register(data), "service_policy": service_policy,
        "function_definition": function_definition, "ia": ia, "screen_design": screen_design,
        "system_architecture": system_architecture, "data_flow": data_flow,
        "api_design": api_design, "qa": qa,
    }
