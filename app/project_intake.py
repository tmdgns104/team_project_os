from __future__ import annotations

import re
from typing import Any

PROJECT_TYPES: dict[str, dict[str, Any]] = {
    "generic": {
        "label": "범용 프로젝트",
        "focus": "목표, 산출물, 이해관계자, 일정, 리스크를 중심으로 정의",
        "extra_questions": ["최종적으로 무엇이 남아야 하나요?", "완료를 누가 어떤 기준으로 승인하나요?"],
    },
    "software": {
        "label": "소프트웨어 / 앱 / 시스템",
        "focus": "사용자, 기능, 데이터, 인터페이스, 배포/운영 환경을 중심으로 정의",
        "extra_questions": ["사용 환경과 플랫폼은 무엇인가요?", "외부 시스템/DB/인증 연동이 있나요?"],
    },
    "ai_data": {
        "label": "AI / 데이터",
        "focus": "데이터 원천, 품질, 모델/분석 목표, 평가 지표, 운영 방식을 중심으로 정의",
        "extra_questions": ["데이터는 어디서 오며 품질은 어떤가요?", "정확도/지연시간/비용 등 평가 기준은 무엇인가요?"],
    },
    "embedded_hardware": {
        "label": "임베디드 / 하드웨어 / IoT",
        "focus": "장치, 센서/액추에이터, 통신, 전원, 환경조건, 안전/인증을 중심으로 정의",
        "extra_questions": ["사용할 장치·센서·통신 규격은 무엇인가요?", "전원·온도·내구성·안전 제약이 있나요?"],
    },
    "manufacturing_automation": {
        "label": "제조 / 자동화 / 스마트팩토리",
        "focus": "공정, 설비, PLC/로봇/센서, 생산 KPI, 장애/안전, MES 연계를 중심으로 정의",
        "extra_questions": ["현재 공정 순서와 병목은 무엇인가요?", "설비/PLC/로봇/센서 및 안전 인터록은 무엇인가요?"],
    },
    "research_rnd": {
        "label": "연구개발 / 실험 / PoC",
        "focus": "가설, 선행 근거, 실험 설계, 비교군, 평가 기준, 재현성을 중심으로 정의",
        "extra_questions": ["검증하려는 가설은 무엇인가요?", "실험 방법·비교 기준·성공/실패 판정은 무엇인가요?"],
    },
    "business_process": {
        "label": "업무개선 / 운영 / 프로세스",
        "focus": "현재 업무 흐름, 병목, 담당자, 승인 규칙, 개선 KPI를 중심으로 정의",
        "extra_questions": ["현재 업무가 어떤 순서로 진행되나요?", "시간/비용/오류 중 무엇을 얼마나 줄이고 싶나요?"],
    },
    "product_service": {
        "label": "제품 / 서비스 / 사업 기획",
        "focus": "고객 문제, 가치제안, 서비스 흐름, 정책, 수익/운영 구조를 중심으로 정의",
        "extra_questions": ["누가 어떤 문제 때문에 이 제품/서비스를 사용하나요?", "핵심 가치와 운영 정책은 무엇인가요?"],
    },
    "education_content": {
        "label": "교육 / 콘텐츠 / 가이드",
        "focus": "대상자 수준, 학습/전달 목표, 커리큘럼, 산출물, 평가 방식을 중심으로 정의",
        "extra_questions": ["대상자의 현재 수준과 최종 도달 수준은 무엇인가요?", "학습/콘텐츠 성과를 어떻게 확인하나요?"],
    },
    "event_campaign": {
        "label": "행사 / 캠페인 / 비개발 프로젝트",
        "focus": "대상, 일정, 채널, 운영 역할, 예산, 성과지표, 비상대응을 중심으로 정의",
        "extra_questions": ["행사/캠페인의 대상과 핵심 메시지는 무엇인가요?", "일정·예산·운영 인력·비상대응은 어떻게 되나요?"],
    },
}

FIELD_GUIDE: dict[str, dict[str, str]] = {
    "name": {
        "label": "프로젝트 이름",
        "question": "팀원이 이름만 보고 무엇을 하는 프로젝트인지 알 수 있나요?",
        "example": "예: 생산라인 비전검사 자동화 시스템 구축",
    },
    "goal": {
        "label": "프로젝트 목표",
        "question": "무엇을, 누구/어디에 적용해, 어떤 결과를 만들 것인지 한두 문장으로 적으세요.",
        "example": "예: 생산라인 제품 이미지를 실시간 분석해 불량을 자동 판정하고 PLC에 배출 신호를 전달한다.",
    },
    "problem": {
        "label": "해결하려는 문제 / 배경",
        "question": "현재 무엇이 불편하거나 비효율적이며, 왜 지금 해결해야 하나요? 가능하면 현재 수치도 적으세요.",
        "example": "예: 육안 검사는 작업자 편차가 크고 시간당 2,000개 검사에서 누락이 발생함.",
    },
    "users": {
        "label": "대상 사용자 / 이해관계자",
        "question": "직접 사용자, 결과를 받는 사람, 승인자, 운영자를 구분해서 적으세요.",
        "example": "예: 생산 작업자(사용), 품질팀(결과 확인), 설비팀(운영), 공장장(승인)",
    },
    "deliverables": {
        "label": "주요 산출물",
        "question": "프로젝트가 끝났을 때 실제로 무엇이 만들어져 있어야 하나요?",
        "example": "예: 검사 장치 1식, 추론 SW, PLC 연동, 대시보드, 설치 가이드, QA 결과서",
    },
    "success_criteria": {
        "label": "성공 기준 / KPI",
        "question": "성공/실패를 누가 봐도 판단할 수 있도록 숫자·조건·완료 기준을 적으세요.",
        "example": "예: 불량 검출 Recall 95% 이상, 판정 500ms 이하, 8시간 연속 운전 오류 0건",
    },
    "scope": {
        "label": "포함 범위 / 제외 범위",
        "question": "이번 프로젝트에서 하는 것과 하지 않는 것을 둘 다 적으세요.",
        "example": "예: 포함=카메라·추론·PLC·대시보드 / 제외=ERP·전사 MES 고도화",
    },
    "current_state": {
        "label": "현재 상태 (AS-IS)",
        "question": "지금은 사람/시스템/장비가 어떤 흐름으로 일을 처리하나요?",
        "example": "예: 작업자가 육안 검사 → 수기 기록 → 불량품 수동 분리",
    },
    "target_state": {
        "label": "목표 상태 (TO-BE)",
        "question": "완료 후 업무/시스템/제품이 어떤 흐름으로 바뀌어야 하나요?",
        "example": "예: 센서 감지 → 촬영 → 자동 판정 → PLC 배출 → DB 저장 → 대시보드 확인",
    },
    "constraints": {
        "label": "기술·일정·예산·운영 제약",
        "question": "반드시 지켜야 하는 기술, 장비, 일정, 예산, 보안, 법규, 운영 조건을 적으세요.",
        "example": "예: Jetson Orin Nano 사용, 공장 내부망, 10월 말 완료, 장비 예산 500만원 이내",
    },
    "schedule": {
        "label": "일정 / 마일스톤 조건",
        "question": "언제까지 어떤 중간 결과가 나와야 하나요? 날짜가 없으면 순서라도 적으세요.",
        "example": "예: 9월 PoC → 10월 통합 → 11월 현장검증 및 인수",
    },
    "team": {
        "label": "팀 / 역할",
        "question": "기획, 개발, 현업, 검증, 승인 역할을 누가 맡나요?",
        "example": "예: PM 1, Vision 1, PLC 1, Backend 1, 현업 검증 2",
    },
    "risks": {
        "label": "리스크 / 가정",
        "question": "실패 가능성이 큰 조건과 아직 확인되지 않은 가정을 적으세요.",
        "example": "예: 조명 변화로 정확도 저하 가능, PLC 통신 규격 현장 확인 필요",
    },
    "description": {
        "label": "추가 설명 / 참고",
        "question": "기존 시스템, 참고 문서, 용어, 결정사항 등 위 항목에 들어가지 않은 내용을 적으세요.",
        "example": "예: 기존 Python 검사 코드를 재사용하며 고객 데이터는 외부 AI로 전송 금지",
    },
}

_REQUIRED = ("name", "goal", "problem", "users", "deliverables", "success_criteria", "scope", "constraints")
_RECOMMENDED = ("current_state", "target_state", "schedule", "team", "risks")


def _text(data: dict[str, Any], key: str) -> str:
    return str(data.get(key) or "").strip()


def evaluate_intake(data: dict[str, Any]) -> dict[str, Any]:
    score = 0
    feedback: list[str] = []
    detail: dict[str, int] = {}

    for key in _REQUIRED:
        value = _text(data, key)
        pts = 10 if len(value) >= 25 else 6 if len(value) >= 10 else 2 if value else 0
        detail[key] = pts
        score += pts
        if pts < 6:
            feedback.append(f"{FIELD_GUIDE[key]['label']}: {FIELD_GUIDE[key]['question']}")

    for key in _RECOMMENDED:
        value = _text(data, key)
        pts = 3 if len(value) >= 15 else 1 if value else 0
        detail[key] = pts
        score += pts

    success = _text(data, "success_criteria")
    if re.search(r"\d", success):
        score += 5
        detail["measurable_kpi_bonus"] = 5
    else:
        feedback.append("성공 기준: 숫자, 임계값, 완료 조건 중 하나 이상을 넣으면 문서와 QA가 훨씬 좋아집니다.")

    scope = _text(data, "scope")
    if any(word in scope.lower() for word in ("제외", "out", "미포함", "하지 않")):
        score += 3
        detail["scope_boundary_bonus"] = 3
    else:
        feedback.append("범위: '포함'뿐 아니라 '제외/하지 않는 것'도 적어 범위 팽창을 막으세요.")

    ptype = _text(data, "project_type") or "generic"
    if ptype not in PROJECT_TYPES:
        ptype = "generic"
    score = min(100, score)
    level = "excellent" if score >= 85 else "good" if score >= 70 else "needs_detail" if score >= 50 else "insufficient"
    return {
        "score": score,
        "level": level,
        "project_type": ptype,
        "project_type_label": PROJECT_TYPES[ptype]["label"],
        "feedback": feedback[:8],
        "detail": detail,
        "type_questions": PROJECT_TYPES[ptype]["extra_questions"],
    }


def build_initial_documents(data: dict[str, Any]) -> dict[str, str]:
    """Build shareable, professional-grade project document baselines.

    Unknown information is shown as TBD instead of being invented. The documents are
    intentionally structured like real delivery artifacts so that Live Design can
    progressively replace TBD sections without changing the document shape.
    """
    ptype = _text(data, "project_type") or "generic"
    meta = PROJECT_TYPES.get(ptype, PROJECT_TYPES["generic"])

    def v(key: str, fallback: str = "TBD · 확인 필요") -> str:
        return _text(data, key) or fallback

    def safe(value: str) -> str:
        return str(value or "").replace("|", "/").replace("\n", " ").strip()

    name = v("name", "프로젝트명 TBD")
    goal = v("goal")
    problem = v("problem")
    users = v("users")
    deliverables = v("deliverables")
    success = v("success_criteria")
    scope = v("scope")
    current_state = v("current_state")
    target_state = v("target_state")
    constraints = v("constraints")
    schedule = v("schedule")
    team = v("team")
    risks = v("risks")
    description = v("description", "추가 참고사항 없음")

    proposal = f"""# {name} 기획서

> **문서 목적** · 프로젝트 추진 배경, 목표, 범위, 성공 기준을 합의하기 위한 기준 문서  
> **문서 상태** · Draft / Live Design  
> **프로젝트 유형** · {meta['label']}

## Executive Summary

| 항목 | 내용 |
|---|---|
| 프로젝트 | {safe(name)} |
| 해결 문제 | {safe(problem)} |
| 목표 | {safe(goal)} |
| 주요 사용자/이해관계자 | {safe(users)} |
| 주요 산출물 | {safe(deliverables)} |
| 성공 기준 | {safe(success)} |

## 1. 추진 배경 및 문제 정의
{problem}

### 1.1 왜 지금 필요한가
- 현재 문제로 인한 업무/품질/비용/리스크 영향을 구체화한다.
- 정량 수치가 확인되지 않은 항목은 **TBD**로 관리한다.

## 2. 프로젝트 목표
{goal}

### 2.1 성공 기준 / KPI
{success}

| KPI | 목표값 | 측정 방법 | 측정 시점 | 상태 |
|---|---|---|---|---|
| 핵심 KPI | {safe(success)} | TBD | 검증 단계 | Draft |

## 3. 대상 사용자 및 이해관계자
{users}

| 구분 | 역할/관심사 | 주요 책임 | 승인/협의 |
|---|---|---|---|
| 사용자/운영자 | {safe(users)} | TBD | TBD |

## 4. 프로젝트 범위
{scope}

### 4.1 In Scope
- 위 범위 정의 중 이번 V1에서 반드시 제공할 항목을 관리한다.

### 4.2 Out of Scope
- 명시되지 않은 범위는 자동으로 확정하지 않는다. 제외 범위는 팀 합의 후 기록한다.

## 5. AS-IS / TO-BE

| 구분 | 내용 |
|---|---|
| AS-IS | {safe(current_state)} |
| TO-BE | {safe(target_state)} |

## 6. 주요 산출물
{deliverables}

## 7. 제약사항 및 전제조건
{constraints}

## 8. 핵심 리스크
{risks}

| Risk | 영향 | 대응 방향 | Owner | 상태 |
|---|---|---|---|---|
| 초기 리스크 | {safe(risks)} | 회피/완화 방안 구체화 필요 | TBD | Open |

## 9. 승인 기준
- 목표, 범위, KPI, 주요 산출물에 이해관계자가 합의해야 한다.
- `provisional` 결정은 정식 승인 전까지 임시안으로 취급한다.
- 미결정 고위험 항목은 승인 없이 확정하지 않는다.

## 10. 참고사항
{description}
"""

    plan = f"""# {name} 프로젝트 계획서

> **문서 목적** · 프로젝트 실행 방식, 일정, 역할, 리스크 및 변경관리 기준 정의

## 1. 추진 전략

### 1.1 목표
{goal}

### 1.2 추진 원칙
- V1 범위를 우선 확정하고 작은 단위로 검증한다.
- Requirement → Design → Task → QA Evidence 추적성을 유지한다.
- AI 임시 결정은 `provisional`, 사람 승인 결정은 `accepted`로 구분한다.

## 2. 범위 및 산출물

### 2.1 범위
{scope}

### 2.2 산출물
{deliverables}

## 3. 일정 및 마일스톤
{schedule}

| Milestone | 주요 목표 | 핵심 산출물 | Entry Criteria | Exit Criteria | 목표일 | 상태 |
|---|---|---|---|---|---|---|
| M1 · Definition Baseline | 목표/요구사항 기준선 | 기획서, 요구사항서 | 아이디어 정의 | 핵심 요구사항 Review | TBD | Draft |
| M2 · Design Baseline | 설계 기준선 | Process, Architecture, Data Flow | 요구사항 Review | 주요 설계 Review | TBD | Draft |
| M3 · Implementation | 기능 구현 | 코드, 구성, Task Evidence | 설계 기준선 | 핵심 기능 구현 | TBD | Draft |
| M4 · Verification | 검증 및 인수 | QA 결과, 인수 기준 | 구현 완료 | Exit Criteria 충족 | TBD | Draft |

## 4. Work Breakdown Structure

| WBS | Work Package | 주요 작업 | 산출물 | Owner | 선행조건 | 상태 |
|---|---|---|---|---|---|---|
| 1.0 | Definition | 목표/범위/요구사항 상세화 | 기준 문서 | TBD | - | Todo |
| 2.0 | Design | Process/Architecture/Data Flow | 설계 산출물 | TBD | 1.0 | Todo |
| 3.0 | Build | 기능 구현 및 통합 | 실행 가능 제품 | TBD | 2.0 | Todo |
| 4.0 | Verify | Test/QA/Evidence | 검증 결과 | TBD | 3.0 | Todo |

## 5. 역할과 책임 (R&R)
{team}

| Role | Responsibility | Accountable/Approver | 비고 |
|---|---|---|---|
| PM / Owner | 범위·일정·의사결정 관리 | TBD | TBD |
| Engineering | 설계·구현·기술검증 | TBD | TBD |
| QA / Reviewer | 요구사항 기반 검증 | TBD | TBD |

## 6. 제약사항 및 의존성
{constraints}

## 7. 리스크 관리
{risks}

| ID | Risk | Probability | Impact | Mitigation | Trigger | Owner | 상태 |
|---|---|---|---|---|---|---|---|
| RISK-001 | {safe(risks)} | TBD | TBD | 대응안 구체화 | TBD | TBD | Open |

## 8. 품질 및 검증 계획
- 각 핵심 요구사항은 최소 1개 이상의 검증 기준/테스트와 연결한다.
- 완료 판단은 AI 자기보고가 아니라 Test/Evidence 기준으로 수행한다.

## 9. 변경관리
- 범위/Architecture/외부 인터페이스 변경은 Decision/ADR로 기록한다.
- 변경 시 영향받는 Requirement, Task, QA를 함께 검토한다.

## 10. 커뮤니케이션 / 보고
- 주요 Decision, Blocker, 범위 변경은 팀 공용 Project OS에 기록한다.
- 반복 상태 갱신은 자동화하고 승인/위험 변경에 Human Gate를 둔다.
"""

    req = f"""# {name} 요구사항 정의서

> **문서 목적** · 구현·검증 가능한 요구사항 기준선과 추적성 관리

## 1. 요구사항 작성 원칙
- 한 요구사항은 하나의 명확한 결과를 표현한다.
- 모호한 표현(빠르게, 적절히, 편리하게)은 측정 가능한 기준으로 바꾼다.
- 각 요구사항은 Acceptance Criteria와 검증 방법을 가져야 한다.

## 2. 프로젝트 목표
{goal}

## 3. 범위 경계
{scope}

## 4. 요구사항 목록

| ID | Type | 요구사항 | 상세 | Priority | Acceptance Criteria | Verification | 상태 |
|---|---|---|---|---|---|---|---|
| REQ-001 | Functional | TBD | 프로젝트 대화에서 구체화 필요 | High | TBD | Test/Review | Draft |

## 5. 비기능 요구사항

| ID | Category | Requirement | Target | Verification | 상태 |
|---|---|---|---|---|---|
| NFR-001 | Performance/Quality | {safe(success)} | {safe(success)} | Measurement/Test | Draft |
| NFR-002 | Constraint | {safe(constraints)} | 준수 | Review/Test | Draft |

## 6. Traceability Matrix

| Requirement | Process/Component | Task | Test Case | Evidence | 상태 |
|---|---|---|---|---|---|
| REQ-001 | TBD | TBD | TBD | TBD | Draft |

## 7. 미결정 / Open Items
- 구체적 Acceptance Criteria가 없는 Requirement는 Review 전까지 Draft로 유지한다.
- 정책·보안·법규·실제 비용/장비 관련 항목은 담당자 확인 후 확정한다.
"""

    milestone = f"""# {name} 마일스톤 관리표

> **기준 일정** · {schedule}

## 1. Milestone Overview

| ID | Milestone | 목표 | 주요 산출물 | 완료 조건 (Exit Criteria) | 목표일 | Owner | 상태 |
|---|---|---|---|---|---|---|---|
| M1 | Definition Baseline | 프로젝트 정의 확정 | 기획서/요구사항서 | 핵심 목표·범위·REQ Review | TBD | TBD | Draft |
| M2 | Design Baseline | 구현 가능한 설계 확정 | Process/Architecture/Data Flow | 주요 인터페이스/데이터 흐름 Review | TBD | TBD | Draft |
| M3 | Build Complete | V1 구현 완료 | 기능/코드/구성 | 핵심 Task 완료 및 통합 가능 | TBD | TBD | Draft |
| M4 | Verification Complete | 품질 기준 충족 | QA/Evidence | Critical Test PASS, Blocker 0 | TBD | TBD | Draft |

## 2. Gate 운영 원칙
- Exit Criteria 미충족 시 다음 단계 완료로 표시하지 않는다.
- 범위 변경이 Milestone에 영향을 주면 일정과 리스크를 함께 갱신한다.
"""

    backlog = f"""# {name} Product / Project Backlog

> **주요 산출물** · {deliverables}

## 1. 우선순위 기준
- **High**: V1 목표/핵심 Requirement 달성에 필수
- **Medium**: 품질/운영성 향상에 중요
- **Low**: 후속 개선 가능

## 2. Backlog

| ID | Epic/Feature | 작업 항목 | Priority | Owner | Status | Requirement | Definition of Done |
|---|---|---|---|---|---|---|---|
| BL-001 | Definition | 핵심 요구사항 상세화 | High | TBD | Todo | REQ-* | 요구사항 Review 완료 |
| BL-002 | Design | System Process/Architecture 기준선 | High | TBD | Todo | REQ-* | 설계 Review 완료 |
| BL-003 | Verification | QA/Test Case 및 Evidence 기준 정의 | High | TBD | Todo | REQ-* | Requirement별 검증 연결 |

## 3. 프로젝트 유형별 확인 질문
- {meta['extra_questions'][0]}
- {meta['extra_questions'][1]}
"""

    return {
        "proposal": proposal,
        "plan": plan,
        "requirements": req,
        "milestone": milestone,
        "backlog": backlog,
    }


def intake_metadata() -> dict[str, Any]:
    return {
        "project_types": [{"value": k, **v} for k, v in PROJECT_TYPES.items()],
        "fields": FIELD_GUIDE,
        "required": list(_REQUIRED),
        "recommended": list(_RECOMMENDED),
    }
