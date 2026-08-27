# Team Project OS V0.9 프로젝트 흐름

현재 권장 시작 방식은 사람이 처음부터 기획서를 작성하는 것이 아니라 **AI와 프로젝트를 충분히 구체화한 뒤 Project OS로 전환하는 것**입니다.

```text
막연한 아이디어
   ↓
AI Design Session
   ↓
문제 / 목표 / 사용자 / 범위 / 기능 / 설계 구체화
   ↓
필요 시 Provisional Autofill
   ↓
/preview
   ↓
사람 확정 / AI 임시 결정 / Pending 확인
   ↓
/apply
   ↓
정식 Project OS 프로젝트 생성
   ↓
공동 문서 / 설계 / Task / QA 운영
```

## 1. AI Design Session

예:

```bat
python project_os.py design --provider codex --member "내 이름"
```

대화 중에는 아직 정식 프로젝트가 만들어지지 않습니다.

구체적인 방안을 모르겠다면:

```text
세부적인 건 잘 모르겠으니까 일반적으로 괜찮은 방식으로 알아서 임시로 다 정해줘.
```

라고 말할 수 있습니다. 저위험·되돌릴 수 있는 선택은 AI가 `provisional` Decision으로 임시 결정하고, 실제 비용/권한/법률/안전 관련 사항은 `pending`으로 남깁니다.

## 2. Preview

```text
/preview
```

전체 대화를 한 번 구조화하지만 아직 프로젝트는 생성하지 않습니다.

확인할 항목:

- Project Brief
- Requirements
- 사람 확정 Decision (`accepted`)
- AI 임시 Decision (`provisional`)
- Documents
- Process / Architecture / Data Flow
- Pending / TBD

## 3. Apply

```text
/apply
```

이 시점에만 정식 프로젝트를 생성합니다.

생성 결과에는 프로젝트 정보와 함께 Requirements, Decisions, 문서, Canvas가 포함될 수 있습니다.

---

## 자동 생성되는 13종 공동 문서

1. 기획서
2. 계획서
3. 마일스톤
4. 백로그
5. 요구사항 정의서
6. 서비스 및 운영 정책서
7. 기능 정의서
8. IA (Information Architecture)
9. 화면 설계서
10. 시스템 구조도
11. 데이터 플로우
12. API 설계 문서
13. QA 문서

문서는 Team Project OS 서버 DB에 저장되며 같은 프로젝트의 팀원은 같은 내용을 봅니다. 저장 시 이전 본문은 revision으로 남고 문서별 Discussion 댓글도 공유됩니다.

현재 V0.9는 모든 프로젝트 유형에 동일한 13종 기본 문서를 생성합니다. 프로젝트 유형별 Adaptive Document Pack은 후속 개선 대상입니다.

---

## 프로젝트 생성 후 운영 흐름

```text
Project Brief
   ↓
Requirements
   ↓
System Process
   ↓
Architecture / Data Flow
   ↓
Documents
   ↓
Backlog / Task
   ↓
Implementation
   ↓
QA / Evidence
   ↓
Decision / Revision
```

문서는 순차적으로만 작성할 필요는 없고 실제 프로젝트 상황에 따라 병렬로 발전시킬 수 있습니다.

## 권장 Traceability

```text
기획 / 목표
  ↓
Requirement (REQ)
  ↓
Process
  ↓
Component / Architecture
  ↓
Feature / Screen / API
  ↓
Backlog / Task
  ↓
QA / Test / Evidence
```

장기적으로는 Requirement 변경 시 영향받는 Process, Architecture, Documents, Task, Test를 자동으로 찾는 Change Impact Analysis로 확장하는 것을 목표로 합니다.

---

## Decision 운영 원칙

```text
accepted
= 사람이 직접 결정했거나 명시적으로 승인

provisional
= AI가 V1 진행을 위해 선택한 되돌릴 수 있는 임시 결정

pending
= 아직 정하지 않았거나 사람 확인이 필요한 항목
```

AI 임시 결정은 프로젝트 진행을 막지 않기 위한 기본안이며 최종 확정으로 간주하지 않습니다.

예:

```text
Mitsubishi PLC          accepted
SQLite                  provisional
FastAPI                 provisional
실제 장비 구매          pending
운영 보안 정책          pending
```

---

## 개발 단계

Development Progress에서 Task를 다음 상태로 관리합니다.

```text
Todo → In Progress → Review → Done
```

팀원이 직접 작업할 수도 있고 Local Bridge를 통해 자신의 Codex / Claude Code / OpenCode / Antigravity를 Worker로 사용할 수도 있습니다.

AI Task 결과는 사람의 최종 프로젝트 상태와 분리해 Evidence와 함께 검토하는 구조를 유지합니다.

---

## QA / Evidence

현재 프로젝트에서는 QA 문서와 Task/Requirement 상태를 공유할 수 있습니다. Git Commit/Test Evidence 자동 수집은 후속 개발 대상입니다.

권장 장기 Trace는 다음과 같습니다.

```text
Requirement
  ↓
Task
  ↓
Commit
  ↓
Test
  ↓
Evidence
```

---

## 관련 문서

- `DESIGN_SESSION.md` — AI와 프로젝트를 구체화하고 `/preview`, `/apply`하는 방법
- `AUTOFILL_MODE.md` — AI 임시 결정과 Human Gate 규칙
- `ANTIGRAVITY_CLI.md` — Antigravity CLI 연결 방법
