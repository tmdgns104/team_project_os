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
    ptype = _text(data, "project_type") or "generic"
    meta = PROJECT_TYPES.get(ptype, PROJECT_TYPES["generic"])
    def v(key: str, fallback: str = "- 작성 필요") -> str:
        return _text(data, key) or fallback

    proposal = f"""# 기획서

## 1. 프로젝트 개요
- 프로젝트 유형: {meta['label']}
- 정의 초점: {meta['focus']}

## 2. 배경 및 문제 정의
{v('problem')}

## 3. 프로젝트 목표
{v('goal')}

## 4. 대상 사용자 / 이해관계자
{v('users')}

## 5. 주요 산출물
{v('deliverables')}

## 6. 성공 기준 / KPI
{v('success_criteria')}

## 7. 범위 / 제외 범위
{v('scope')}

## 8. 현재 상태 (AS-IS)
{v('current_state')}

## 9. 목표 상태 (TO-BE)
{v('target_state')}
"""

    plan = f"""# 계획서

## 1. 추진 범위
{v('scope')}

## 2. 주요 산출물
{v('deliverables')}

## 3. 일정 / 마일스톤
{v('schedule', '- 마일스톤 문서에서 구체화 필요')}

## 4. 역할과 책임
{v('team', '- Team & AI에서 구체화 필요')}

## 5. 기술·일정·예산·운영 제약
{v('constraints')}

## 6. 리스크 / 가정
{v('risks')}

## 7. 추가 설명 / 참고
{v('description')}
"""

    req = f"""# 요구사항 정의서

> 아래 항목은 프로젝트 시작 정보에서 도출한 요구사항 작성 가이드입니다. 실제 요구사항은 팀 검토 후 REQ ID를 부여하세요.

## 프로젝트 목표
{v('goal')}

## 성공 기준
{v('success_criteria')}

## 범위 경계
{v('scope')}

| ID | 요구사항 | 상세 | 우선순위 | 상태 | 검증 기준 |
|---|---|---|---|---|---|
| REQ-001 |  |  | High | Draft |  |
"""

    milestone = f"""# 마일스톤

## 초기 일정 정보
{v('schedule', '- 일정 미정')}

| Milestone | 목표 | 완료 조건 | 목표일 | 상태 |
|---|---|---|---|---|
| M1 | 기획/요구사항 기준선 확정 | 핵심 문서 Review 이상 |  | Draft |
| M2 | 설계 기준선 확정 | Process/Architecture/Data Flow 확정 |  | Draft |
| M3 | 구현 및 검증 | 핵심 Task/QA 완료 |  | Draft |
"""

    backlog = f"""# 백로그

## 초기 산출물
{v('deliverables')}

## 프로젝트 유형별 확인 질문
- {meta['extra_questions'][0]}
- {meta['extra_questions'][1]}

| ID | 항목 | 우선순위 | 담당 | 상태 | 연결 요구사항 |
|---|---|---|---|---|---|
| BL-001 | 기획/요구사항 상세화 | High |  | Todo |  |
"""
    return {"proposal": proposal, "plan": plan, "requirements": req, "milestone": milestone, "backlog": backlog}


def intake_metadata() -> dict[str, Any]:
    return {
        "project_types": [{"value": k, **v} for k, v in PROJECT_TYPES.items()],
        "fields": FIELD_GUIDE,
        "required": list(_REQUIRED),
        "recommended": list(_RECOMMENDED),
    }
