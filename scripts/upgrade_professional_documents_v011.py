from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, new: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"start marker not found: {label}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"end marker not found: {label}")
    return text[:a] + new + text[b:]


# -----------------------------------------------------------------------------
# 1) Professional document generation
# -----------------------------------------------------------------------------
p = ROOT / "app/project_intake.py"
s = p.read_text(encoding="utf-8")
start = "def build_initial_documents(data: dict[str, Any]) -> dict[str, str]:\n"
end = "\n\ndef intake_metadata() -> dict[str, Any]:\n"
new_func = r'''def build_initial_documents(data: dict[str, Any]) -> dict[str, str]:
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
'''
s = replace_between(s, start, end, new_func, "build_initial_documents")
p.write_text(s, encoding="utf-8")


# -----------------------------------------------------------------------------
# 2) Professional baseline templates for all 13 shared artifacts
# -----------------------------------------------------------------------------
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8")
start = "DOCUMENT_TEMPLATES = [\n"
end = "]\n\n\n\n@contextmanager\ndef db():\n"
new_templates = r'''DOCUMENT_TEMPLATES = [
    ("proposal", "기획서", "# 기획서\n\n> 프로젝트 추진 배경·목표·범위·KPI를 합의하는 기준 문서\n\n## Executive Summary\n\n## 1. 추진 배경 및 문제 정의\n\n## 2. 프로젝트 목표 / KPI\n\n## 3. 이해관계자\n\n## 4. In Scope / Out of Scope\n\n## 5. AS-IS / TO-BE\n\n## 6. 산출물\n\n## 7. 제약사항 / 전제조건\n\n## 8. 리스크\n\n## 9. 승인 기준\n"),
    ("plan", "계획서", "# 프로젝트 계획서\n\n> 실행 일정·WBS·R&R·리스크·변경관리 기준\n\n## 1. 추진 전략\n\n## 2. 범위 / 산출물\n\n## 3. 일정 / 마일스톤\n\n## 4. Work Breakdown Structure\n\n## 5. 역할과 책임 (R&R)\n\n## 6. 제약사항 / 의존성\n\n## 7. 리스크 관리\n\n## 8. 품질 / 검증 계획\n\n## 9. 변경관리\n"),
    ("milestone", "마일스톤", "# 마일스톤 관리표\n\n| ID | Milestone | 목표 | 주요 산출물 | Entry Criteria | Exit Criteria | 목표일 | Owner | 상태 |\n|---|---|---|---|---|---|---|---|---|\n| M1 | Definition Baseline | 요구사항 기준선 | 기획/요구사항 | TBD | 핵심 REQ Review | TBD | TBD | Draft |\n| M2 | Design Baseline | 설계 기준선 | Process/Architecture/Data Flow | M1 | 설계 Review | TBD | TBD | Draft |\n"),
    ("backlog", "백로그", "# Product / Project Backlog\n\n| ID | Epic/Feature | 작업 항목 | Priority | Owner | Status | Requirement | Definition of Done |\n|---|---|---|---|---|---|---|---|\n| BL-001 | Definition | 핵심 요구사항 상세화 | High | TBD | Todo | REQ-* | Review 완료 |\n"),
    ("requirements", "요구사항 정의서", "# 요구사항 정의서\n\n> 구현·검증 가능한 Requirement 기준선\n\n## 1. 작성 원칙\n\n## 2. Functional Requirements\n\n| ID | Type | 요구사항 | 상세 | Priority | Acceptance Criteria | Verification | 상태 |\n|---|---|---|---|---|---|---|---|\n| REQ-001 | Functional | TBD | TBD | High | TBD | Test/Review | Draft |\n\n## 3. Non-Functional Requirements\n\n## 4. Traceability Matrix\n"),
    ("service_policy", "서비스 및 운영 정책서", "# 서비스 및 운영 정책서\n\n> 실제 운영 시 일관된 의사결정을 위한 정책 기준\n\n## 1. 목적 / 적용 범위\n\n## 2. 사용자 / 역할 / 권한 정책\n\n| Role | 허용 기능 | 제한 | 승인자 |\n|---|---|---|---|\n| TBD | TBD | TBD | TBD |\n\n## 3. 데이터 수집 / 보관 / 삭제 정책\n\n## 4. 장애 / 예외 / 복구 정책\n\n## 5. 로그 / 감사 / 모니터링 정책\n\n## 6. 배포 / 변경 / Rollback 정책\n\n## 7. 보안 / 개인정보 / 규제 Open Items\n"),
    ("function_definition", "기능 정의서", "# 기능 정의서\n\n> 사용자/시스템 기능의 입력·처리·출력·예외·검증 기준\n\n| 기능 ID | 기능명 | Actor/Trigger | 입력 | 정상 처리 | 출력 | 예외/오류 | Acceptance Criteria | 관련 REQ |\n|---|---|---|---|---|---|---|---|---|\n| FUNC-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |\n"),
    ("ia", "IA (Information Architecture, 정보구조도)", "# IA (Information Architecture)\n\n> 메뉴·화면·정보 구조와 이동 관계 정의\n\n## 1. Navigation Model\n\n```text\nRoot\n└─ TBD\n```\n\n## 2. 화면/메뉴 목록\n\n| IA ID | Depth | 메뉴/화면 | 목적 | 주요 사용자 | 연결 화면 | 권한 |\n|---|---|---|---|---|---|---|\n| IA-001 | 1 | TBD | TBD | TBD | TBD | TBD |\n\n## 3. 주요 사용자 Flow\n"),
    ("screen_design", "화면 설계서", "# 화면 설계서\n\n> 화면 목적·상태·사용자 동작·데이터·Validation 정의\n\n## SCREEN-001 · TBD\n\n| 항목 | 내용 |\n|---|---|\n| 목적 | TBD |\n| 대상 사용자 | TBD |\n| 진입 조건 | TBD |\n| 종료/성공 조건 | TBD |\n\n### 주요 컴포넌트\n\n| Component ID | UI 요소 | 표시 데이터 | 사용자 동작 | Validation | Error/Empty State |\n|---|---|---|---|---|---|\n| UI-001 | TBD | TBD | TBD | TBD | TBD |\n\n### 연결 기능 / API\n"),
    ("system_architecture", "시스템 구조도", "# 시스템 구조도\n\n> 시스템 경계·컴포넌트 책임·인터페이스·배포 구조 정의\n\n## 1. System Context\n\n## 2. Component Responsibilities\n\n| Component | Responsibility | Technology | Interface | Dependency | Owner |\n|---|---|---|---|---|---|\n| TBD | TBD | TBD | TBD | TBD | TBD |\n\n## 3. Interface / Integration\n\n## 4. Deployment / Runtime\n\n## 5. Availability / Security Considerations\n\n> Design > Architecture Canvas와 함께 관리합니다.\n"),
    ("data_flow", "데이터 플로우", "# 데이터 플로우\n\n> 데이터 생성·변환·저장·소비와 책임 경계 정의\n\n| Flow ID | Source | Data | Trigger/Frequency | Processing | Destination | Protocol/Format | Validation | Failure Handling |\n|---|---|---|---|---|---|---|---|---|\n| DF-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |\n\n## Data Ownership / Retention\n\n> Design > Data Flow Canvas와 함께 관리합니다.\n"),
    ("api_design", "API 설계 문서", "# API 설계 문서\n\n> 시스템 간 Contract와 오류/보안/호환성 기준 정의\n\n## 1. API Conventions\n- Base URL / Versioning: TBD\n- Authentication / Authorization: TBD\n- Content-Type: application/json (해당 시)\n\n## 2. Endpoint Catalog\n\n| API ID | Method | Path | 목적 | Auth | Request | Success Response | Error | 관련 REQ |\n|---|---|---|---|---|---|---|---|---|\n| API-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |\n\n## 3. Error Model\n\n## 4. Idempotency / Timeout / Retry\n"),
    ("qa", "QA 문서", "# QA / Test Plan & Result\n\n> Requirement 기반 검증 전략·Test Case·Evidence 관리\n\n## 1. Test Strategy\n\n| Test Level | Scope | Environment | Entry Criteria | Exit Criteria |\n|---|---|---|---|---|\n| Functional | 핵심 Requirement | TBD | 기능 구현 완료 | Critical TC PASS |\n\n## 2. Test Cases\n\n| TC ID | Requirement | Priority | Preconditions | Test Steps | Expected Result | Actual Result | Status | Evidence |\n|---|---|---|---|---|---|---|---|---|\n| TC-001 | REQ-001 | High | TBD | TBD | TBD | - | Not Run | TBD |\n\n## 3. Defect / Issue Summary\n\n## 4. Release / Acceptance Gate\n- Critical/Blocker 미해결 0건\n- 핵심 Requirement 검증 Evidence 확보\n"),
]
'''
s = replace_between(s, start, end, new_templates, "DOCUMENT_TEMPLATES")
p.write_text(s, encoding="utf-8")


# -----------------------------------------------------------------------------
# 3) Professional read-first document workspace with safe markdown renderer
# -----------------------------------------------------------------------------
p = ROOT / "app/static/app.js"
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    "projects: [], projectId: null, snapshot: null, view: 'overview', ws: null, selectedDocumentId: null,\n",
    "projects: [], projectId: null, snapshot: null, view: 'overview', ws: null, selectedDocumentId: null, documentEditMode: false,\n",
    "state documentEditMode",
)

old_select = "document.querySelectorAll('[data-document-id]').forEach(c=>c.addEventListener('click',()=>{state.selectedDocumentId=Number(c.dataset.documentId);render();}));"
new_select = "document.querySelectorAll('[data-document-id]').forEach(c=>c.addEventListener('click',()=>{state.selectedDocumentId=Number(c.dataset.documentId);state.documentEditMode=false;render();}));"
s = replace_once(s, old_select, new_select, "document selection")

start = "function renderDocuments(){\n"
end = "function renderTraceability(){\n"
new_docs = r'''function inlineMarkdown(text){
  let s=esc(text??'');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/\*([^*]+)\*/g,'<em>$1</em>');
  return s;
}
function markdownHeadings(md){
  return String(md||'').split(/\r?\n/).map((line,i)=>{const m=line.match(/^(#{2,3})\s+(.+)$/);return m?{level:m[1].length,text:m[2].replace(/[*_`]/g,'').trim(),id:`sec-${i}`}:null}).filter(Boolean);
}
function markdownTable(lines,start){
  if(start+1>=lines.length || !/^\s*\|?\s*:?-+/.test(lines[start+1].replace(/^\s*\|/,''))) return null;
  const rows=[]; let i=start;
  while(i<lines.length && lines[i].includes('|') && lines[i].trim()){ rows.push(lines[i]); i++; }
  if(rows.length<2) return null;
  const cells=row=>row.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
  const head=cells(rows[0]); const body=rows.slice(2).map(cells);
  return {html:`<div class="doc-table-wrap"><table class="doc-table"><thead><tr>${head.map(c=>`<th>${inlineMarkdown(c)}</th>`).join('')}</tr></thead><tbody>${body.map(r=>`<tr>${head.map((_,idx)=>`<td>${inlineMarkdown(r[idx]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,next:i};
}
function renderMarkdownDocument(md){
  const lines=String(md||'').replace(/\r/g,'').split('\n');
  let out='', i=0, inCode=false, code=[];
  const closeCode=()=>{if(inCode){out+=`<pre class="doc-code"><code>${esc(code.join('\n'))}</code></pre>`;inCode=false;code=[];}};
  while(i<lines.length){
    const line=lines[i];
    if(line.trim().startsWith('```')){ if(inCode) closeCode(); else {inCode=true;code=[];} i++; continue; }
    if(inCode){code.push(line);i++;continue;}
    const table=markdownTable(lines,i); if(table){out+=table.html;i=table.next;continue;}
    const h=line.match(/^(#{1,4})\s+(.+)$/);
    if(h){const level=h[1].length;const id=`sec-${i}`;out+=`<h${level} id="${id}">${inlineMarkdown(h[2])}</h${level}>`;i++;continue;}
    const quote=line.match(/^>\s?(.*)$/); if(quote){const q=[];while(i<lines.length&&/^>/.test(lines[i])){q.push(lines[i].replace(/^>\s?/,''));i++;}out+=`<div class="doc-callout">${q.map(x=>`<p>${inlineMarkdown(x)}</p>`).join('')}</div>`;continue;}
    const task=line.match(/^\s*-\s+\[([ xX])\]\s+(.+)$/); if(task){out+=`<div class="doc-check"><span class="doc-checkbox ${task[1].trim()?'checked':''}">${task[1].trim()?'✓':''}</span><span>${inlineMarkdown(task[2])}</span></div>`;i++;continue;}
    const bullet=line.match(/^\s*[-*]\s+(.+)$/); if(bullet){const arr=[];while(i<lines.length){const m=lines[i].match(/^\s*[-*]\s+(.+)$/);if(!m)break;arr.push(m[1]);i++;}out+=`<ul>${arr.map(x=>`<li>${inlineMarkdown(x)}</li>`).join('')}</ul>`;continue;}
    const num=line.match(/^\s*\d+\.\s+(.+)$/); if(num){const arr=[];while(i<lines.length){const m=lines[i].match(/^\s*\d+\.\s+(.+)$/);if(!m)break;arr.push(m[1]);i++;}out+=`<ol>${arr.map(x=>`<li>${inlineMarkdown(x)}</li>`).join('')}</ol>`;continue;}
    if(/^---+$/.test(line.trim())){out+='<hr>';i++;continue;}
    if(!line.trim()){i++;continue;}
    const para=[];while(i<lines.length&&lines[i].trim()&&!/^(#{1,4})\s+/.test(lines[i])&&!/^\s*[-*]\s+/.test(lines[i])&&!/^\s*\d+\.\s+/.test(lines[i])&&!/^>/.test(lines[i])&&!lines[i].trim().startsWith('```')){if(markdownTable(lines,i))break;para.push(lines[i].trim());i++;}
    if(para.length)out+=`<p>${inlineMarkdown(para.join(' '))}</p>`;else i++;
  }
  closeCode(); return out;
}
function documentQuality(d){
  const c=String(d.content||''); const headings=(c.match(/^##\s+/gm)||[]).length; const tables=(c.match(/^\|.+\|$/gm)||[]).length; const tbd=(c.match(/TBD|작성 필요|확인 필요/g)||[]).length;
  let score=Math.min(100,35+headings*7+Math.min(25,tables*2)-Math.min(25,tbd*3));
  if(c.length>1800)score+=8; score=Math.max(20,Math.min(100,score));
  const label=score>=85?'공유 가능':score>=65?'검토 필요':'작성 중'; return {score,label};
}
function renderDocuments(){
  const s=state.snapshot;
  if(!s.documents?.length) return '<div class="empty">프로젝트 문서가 없습니다.</div>';
  if(!state.selectedDocumentId || !s.documents.some(d=>d.id===state.selectedDocumentId)) state.selectedDocumentId=s.documents[0].id;
  const d=s.documents.find(x=>x.id===state.selectedDocumentId);
  const comments=s.document_comments.filter(c=>c.document_id===d.id);
  const completed=s.documents.filter(x=>['review','approved','complete'].includes(x.status)).length;
  const headings=markdownHeadings(d.content); const quality=documentQuality(d); const editing=state.documentEditMode;
  const toc=headings.length?`<nav class="doc-toc"><div class="doc-toc-title">목차</div>${headings.map(h=>`<a class="lv${h.level}" href="#${h.id}">${esc(h.text)}</a>`).join('')}</nav>`:'';
  return `<div class="documents-head"><div><div class="eyebrow">DELIVERABLE WORKSPACE</div><h2>프로젝트 공식 산출물 ${completed}/${s.documents.length}</h2><p class="muted">Markdown은 원본 포맷으로 유지하고, 기본 화면에서는 실무 보고서 형태로 렌더링합니다.</p></div><div><button class="mini-btn" data-action="export-project">산출물 패키지 ZIP</button></div></div>
  <div class="document-layout professional-doc-layout">
    <div class="panel document-list">${s.documents.map(x=>`<button class="document-item ${x.id===d.id?'active':''}" data-document-id="${x.id}"><span><strong>${esc(x.title)}</strong><small>${esc(x.updated_by)} · ${new Date(x.updated_at).toLocaleString('ko-KR')}</small></span>${statusChip(x.status)}</button>`).join('')}</div>
    <div class="document-stage">
      <div class="document-stage-toolbar">
        <div><span class="chip ${quality.score>=85?'good':quality.score>=65?'warn':''}">문서 품질 ${quality.score} · ${quality.label}</span>${s.project.lifecycle==='draft'?'<span class="chip warn">Live Draft</span>':''}</div>
        <div class="doc-view-actions"><button class="mini-btn ${!editing?'active':''}" data-action="document-read-mode">문서 보기</button><button class="mini-btn ${editing?'active':''}" data-action="document-edit-mode">Markdown 편집</button><button class="mini-btn" data-action="print-document">인쇄/PDF</button></div>
      </div>
      ${editing?`<div class="panel document-editor">
        <div class="document-editor-head"><div><h3>${esc(d.title)}</h3><small class="muted">${esc(d.doc_type)} · 마지막 수정 ${new Date(d.updated_at).toLocaleString('ko-KR')}</small></div>${statusChip(d.status)}</div>
        <div class="document-controls">${selectField('document_status','상태',[['draft','초안'],['review','검토중'],['approved','승인됨'],['complete','완료']],d.status)}${field('document_editor','작성자',d.updated_by||'Team member')}</div>
        <div class="field"><label>Markdown 원문</label><textarea id="documentContent" class="document-content">${esc(d.content)}</textarea></div>
        <div class="form-actions"><button type="button" class="ghost-btn" data-action="export-document">Markdown 다운로드</button><button type="button" class="primary-btn" data-action="save-document">문서 저장</button></div>
      </div>`:`<article class="professional-document" id="printableDocument">
        <header class="doc-cover">
          <div class="doc-cover-kicker">TEAM PROJECT OS · PROJECT DELIVERABLE</div>
          <h1>${esc(d.title)}</h1>
          <p class="doc-project-name">${esc(s.project.name)}</p>
          <div class="doc-meta-grid"><div><span>문서 상태</span><strong>${statusChip(d.status)}</strong></div><div><span>작성/갱신</span><strong>${esc(d.updated_by)}</strong></div><div><span>최종 수정</span><strong>${new Date(d.updated_at).toLocaleString('ko-KR')}</strong></div><div><span>Lifecycle</span><strong>${s.project.lifecycle==='draft'?'설계 중 Draft':'Active Project'}</strong></div></div>
        </header>
        <div class="doc-body-layout">${toc}<section class="doc-content-rendered">${renderMarkdownDocument(d.content)}</section></div>
        <footer class="doc-footer"><span>${esc(s.project.name)}</span><span>${esc(d.title)} · Team Project OS</span></footer>
      </article>`}
      <div class="panel document-comments"><h3>Review / Discussion</h3><form id="documentCommentForm" class="comment-form"><input name="author" value="Team member" aria-label="작성자"><input name="body" placeholder="검토 의견 또는 변경 요청" aria-label="댓글"><button class="mini-btn" type="submit">의견 등록</button></form>${comments.length?comments.map(c=>`<div class="comment"><strong>${esc(c.author)}</strong><span>${esc(c.body)}</span><small>${new Date(c.created_at).toLocaleString('ko-KR')}</small></div>`).join(''):'<div class="empty compact">아직 검토 의견이 없습니다.</div>'}</div>
    </div>
  </div>`;
}
'''
s = replace_between(s, start, end, new_docs, "renderDocuments")

old_actions = "if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp(); if(action==='export-project') return exportProject(); if(action==='export-document') return exportDocument();"
new_actions = "if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp(); if(action==='document-read-mode'){state.documentEditMode=false;return render();} if(action==='document-edit-mode'){state.documentEditMode=true;return render();} if(action==='print-document') return window.print(); if(action==='export-project') return exportProject(); if(action==='export-document') return exportDocument();"
s = replace_once(s, old_actions, new_actions, "document actions")
p.write_text(s, encoding="utf-8")


# -----------------------------------------------------------------------------
# 4) Print-quality visual treatment
# -----------------------------------------------------------------------------
p = ROOT / "app/static/styles.css"
s = p.read_text(encoding="utf-8")
css = r'''

/* V0.11 Professional Deliverable Workspace */
.document-stage{min-width:0}.document-stage-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;flex-wrap:wrap}.document-stage-toolbar>div{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.doc-view-actions .mini-btn.active{background:#172033;color:#fff;border-color:#172033}.professional-document{background:#fff;border:1px solid #dfe4ec;box-shadow:0 14px 38px rgba(20,31,48,.09);border-radius:8px;overflow:hidden;max-width:1050px;margin:0 auto}.doc-cover{padding:54px 64px 34px;border-bottom:1px solid #e4e8ef;background:linear-gradient(180deg,#fff 0%,#fbfcff 100%)}.doc-cover-kicker{font-size:10px;font-weight:800;letter-spacing:.18em;color:#778299}.doc-cover h1{font-size:38px;letter-spacing:-.035em;line-height:1.18;margin:14px 0 8px;color:#121927}.doc-project-name{font-size:17px;color:#596579;margin:0 0 30px}.doc-meta-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:#e4e8ef;border:1px solid #e4e8ef;border-radius:10px;overflow:hidden}.doc-meta-grid>div{background:#fff;padding:12px 14px;min-height:68px}.doc-meta-grid span{display:block;font-size:10px;color:#8993a3;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}.doc-meta-grid strong{font-size:12px;color:#283446}.doc-body-layout{display:grid;grid-template-columns:190px minmax(0,1fr);gap:36px;padding:34px 64px 70px}.doc-toc{position:sticky;top:112px;align-self:start;border-right:1px solid #e8ebf0;padding-right:20px;max-height:70vh;overflow:auto}.doc-toc-title{font-size:11px;font-weight:800;color:#7d8797;letter-spacing:.09em;margin-bottom:11px}.doc-toc a{display:block;text-decoration:none;color:#606b7c;font-size:11px;line-height:1.45;padding:5px 0}.doc-toc a.lv3{padding-left:12px;color:#8993a2}.doc-toc a:hover{color:var(--accent)}.doc-content-rendered{min-width:0;color:#253043;font-size:14px;line-height:1.82}.doc-content-rendered>h1:first-child{display:none}.doc-content-rendered h1{font-size:30px;margin:0 0 24px;color:#151d2a}.doc-content-rendered h2{font-size:21px;letter-spacing:-.02em;margin:42px 0 14px;padding-bottom:9px;border-bottom:2px solid #202b3d;color:#182130}.doc-content-rendered h3{font-size:16px;margin:27px 0 10px;color:#28364b}.doc-content-rendered h4{font-size:14px;margin:22px 0 8px}.doc-content-rendered p{margin:8px 0 14px}.doc-content-rendered ul,.doc-content-rendered ol{margin:8px 0 18px;padding-left:24px}.doc-content-rendered li{margin:5px 0}.doc-content-rendered code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f1f3f6;border-radius:5px;padding:2px 5px;font-size:.92em}.doc-code{background:#111827;color:#e5edf9;border-radius:9px;padding:15px 17px;overflow:auto;font-size:12px;line-height:1.6}.doc-callout{margin:18px 0;padding:13px 16px;border-left:4px solid #6176e9;background:#f4f6ff;border-radius:0 8px 8px 0;color:#40509b}.doc-callout p{margin:3px 0}.doc-table-wrap{overflow:auto;margin:15px 0 25px;border:1px solid #dfe4ea;border-radius:8px}.doc-table{width:100%;border-collapse:collapse;font-size:12px;line-height:1.45}.doc-table th{background:#f3f5f8;color:#344054;font-weight:750;text-align:left;padding:10px 11px;border-bottom:1px solid #d8dde5;white-space:nowrap}.doc-table td{padding:10px 11px;border-bottom:1px solid #e8ebef;vertical-align:top;min-width:80px}.doc-table tbody tr:last-child td{border-bottom:0}.doc-table tbody tr:hover{background:#fbfcfe}.doc-check{display:flex;align-items:flex-start;gap:9px;margin:6px 0}.doc-checkbox{width:17px;height:17px;border:1px solid #b9c2cf;border-radius:4px;display:grid;place-items:center;font-size:11px;margin-top:3px}.doc-checkbox.checked{background:#2f7d5c;color:#fff;border-color:#2f7d5c}.doc-content-rendered hr{border:0;border-top:1px solid #e0e4ea;margin:34px 0}.doc-footer{border-top:1px solid #e5e8ed;padding:17px 64px;display:flex;justify-content:space-between;gap:20px;font-size:10px;color:#8993a3;background:#fbfcfd}.professional-doc-layout{grid-template-columns:minmax(250px,.28fr) minmax(0,1fr)}
@media(max-width:1100px){.doc-cover{padding:38px 38px 28px}.doc-body-layout{grid-template-columns:1fr;padding:28px 38px 55px}.doc-toc{position:static;border-right:0;border-bottom:1px solid #e6e9ef;padding:0 0 18px;max-height:none}.doc-toc a{display:inline-block;margin-right:14px}.doc-meta-grid{grid-template-columns:1fr 1fr}.doc-footer{padding:15px 38px}}
@media(max-width:700px){.doc-cover{padding:28px 22px}.doc-cover h1{font-size:28px}.doc-body-layout{padding:22px 22px 44px}.doc-meta-grid{grid-template-columns:1fr}.doc-footer{padding:14px 22px;flex-direction:column}.professional-document{border-radius:0}.document-stage-toolbar{align-items:flex-start}}
@media print{body{background:#fff}.sidebar,.topbar,.documents-head,.document-list,.document-stage-toolbar,.document-comments,.notice{display:none!important}.app-shell{display:block}.content{padding:0;max-width:none}.document-layout,.professional-doc-layout{display:block}.professional-document{box-shadow:none;border:0;max-width:none;border-radius:0}.doc-cover{padding:18mm 18mm 10mm}.doc-body-layout{grid-template-columns:1fr;padding:10mm 18mm 18mm}.doc-toc{position:static;border-right:0;border-bottom:1px solid #ddd;padding-bottom:6mm;margin-bottom:6mm}.doc-footer{padding:5mm 18mm}.doc-content-rendered h2{break-after:avoid}.doc-table-wrap,.doc-callout{break-inside:avoid}.doc-table{font-size:9pt}}
'''
if "/* V0.11 Professional Deliverable Workspace */" not in s:
    s += css
p.write_text(s, encoding="utf-8")


# -----------------------------------------------------------------------------
# 5) README version/feature note
# -----------------------------------------------------------------------------
p = ROOT / "README.md"
s = p.read_text(encoding="utf-8")
s = s.replace("# Team Project OS V0.10", "# Team Project OS V0.11", 1)
marker = "## V0.10 Live Design Draft\n"
feature = """## V0.11 Professional Deliverables\n\nDocuments는 단순 Markdown textarea가 아니라 **실무 산출물용 Read-first Workspace**로 표시됩니다. Markdown 원본은 그대로 보존하면서 기본 화면은 표지, 문서 메타, 목차, 제목 계층, 표, 체크리스트, Callout, 코드블록을 갖춘 보고서 형태로 렌더링합니다. `Markdown 편집`으로 원문을 수정할 수 있고 `인쇄/PDF`로 브라우저 인쇄 레이아웃을 사용할 수 있습니다.\n\n13종 기본 문서 템플릿도 실무 기준 필드로 확장했습니다. 정보가 없는 경우 임의로 꾸며내지 않고 `TBD/확인 필요`로 유지합니다.\n\n"""
if feature not in s:
    s = s.replace(marker, feature + marker, 1)
p.write_text(s, encoding="utf-8")


# -----------------------------------------------------------------------------
# 6) Regression tests
# -----------------------------------------------------------------------------
p = ROOT / "tests/test_professional_documents.py"
p.write_text(r'''import os
import tempfile
import unittest
from pathlib import Path

from app.project_intake import build_initial_documents


class ProfessionalDocumentTests(unittest.TestCase):
    def test_initial_documents_have_delivery_grade_structure(self):
        docs = build_initial_documents({
            "name": "HMI MES Mini Line",
            "project_type": "manufacturing_automation",
            "goal": "PLC 생산 데이터를 수집해 HMI와 MES에서 실시간 확인한다.",
            "problem": "수기 생산 기록 때문에 실적 집계와 이상 추적이 늦다.",
            "users": "생산 작업자, 설비 담당자, 품질 담당자",
            "deliverables": "PLC 연동, HMI, 생산실적 DB, 운영 가이드, QA 결과",
            "success_criteria": "생산수량/불량수량/설비상태를 실시간 표시하고 테스트 시나리오를 통과한다.",
            "scope": "포함=시뮬레이터, Python Gateway, Web HMI, SQLite / 제외=ERP",
            "constraints": "V1은 Windows Local과 PLC Simulator를 우선 사용한다.",
        })
        self.assertIn("Executive Summary", docs["proposal"])
        self.assertIn("승인 기준", docs["proposal"])
        self.assertIn("Work Breakdown Structure", docs["plan"])
        self.assertIn("변경관리", docs["plan"])
        self.assertIn("Acceptance Criteria", docs["requirements"])
        self.assertIn("Traceability Matrix", docs["requirements"])
        self.assertIn("Exit Criteria", docs["milestone"])
        self.assertIn("Definition of Done", docs["backlog"])

    def test_web_workspace_is_read_first_and_printable(self):
        js = Path("app/static/app.js").read_text(encoding="utf-8")
        css = Path("app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("function renderMarkdownDocument", js)
        self.assertIn("문서 보기", js)
        self.assertIn("Markdown 편집", js)
        self.assertIn("print-document", js)
        self.assertIn("professional-document", css)
        self.assertIn("@media print", css)


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("V0.11 professional document upgrade prepared")
