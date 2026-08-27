# Team Project OS V0.14

사람이 처음부터 완벽한 기획·설계 지식을 갖고 있지 않아도 **자기 생성형 AI와 충분히 대화하면서 프로젝트를 구체화하고, 그 과정이 웹의 실무 문서와 디자인에 실시간 반영되는 Project OS**입니다.

AI는 프로젝트의 최종 권위가 아니라 선택 가능한 Worker Provider입니다. 사람의 명시적 결정은 `accepted`, AI가 대신 고른 가역적인 기본값은 `provisional`, 사람이 확인해야 할 항목은 `pending`으로 구분합니다.

## V0.14 핵심 개선

### Windows + macOS + Linux

같은 Python/FastAPI 서버 코드를 사용합니다.

- Windows: `run_windows.bat`
- macOS: `bash run_mac.sh`
- 공통 실행기: `python run_project_os.py` 또는 macOS/Linux의 `python3 run_project_os.py`
- Docker: `app.main_v014:app`
- CI: Windows / macOS / Ubuntu에서 동일한 회귀·프로젝트 생성 검증

### CMD/macOS 여러 줄 붙여넣기

Windows의 고전 CMD처럼 `Ctrl+V`가 불편하거나 여러 줄을 한 번에 넣기 어려운 터미널에서는 텍스트를 클립보드에 복사한 뒤 Design Session에서 다음만 입력합니다.

```text
/paste
```

Project OS가 OS 클립보드의 여러 줄을 **하나의 사용자 메시지**로 읽습니다.

- Windows: PowerShell `Get-Clipboard -Raw`
- macOS: `pbpaste`
- Linux: `wl-paste` / `xclip` / `xsel` fallback

### Live Draft HTTP 500 방어

AI의 숨은 `PROJECT_OS_DELTA`에 잘못된 list/object가 한 번 섞여도 이후 모든 턴이 망가지지 않도록 **클라이언트와 서버 양쪽에서 Live State를 whitelist/type-normalize**합니다. 잘못된 항목만 버리고 정상적인 Project/Requirement/Decision/Diagram 데이터는 계속 동기화합니다.

### 13종 실무 산출물 재설계

문서 양식은 특정 회사 서식을 복제하지 않고 ISO/IEC/IEEE Requirements·Architecture·Test 문서 기준, PMI WBS/Schedule 관행, C4 Architecture, OpenAPI, 운영/SRE 관행을 참고해 필요한 정보 구조를 다시 설계했습니다.

1. 기획서 — Executive Summary, Problem, KPI, Stakeholder, Scope, Deliverable, Risk, Approval
2. 계획서 — Lifecycle, Deliverable-oriented WBS, RACI, Dependency, Risk, Quality, Change, Communication
3. 마일스톤 — Gantt, Phase/Task, Start/End Week, Owner, Gate/Exit Criteria
4. 백로그 — Value, Requirement, Priority, Estimate, Dependency, Definition of Ready/Done, Milestone
5. 요구사항 정의서 — Source/Rationale, Priority, Acceptance Criteria, Verification, Owner, Traceability
6. 서비스/운영 정책서 — Role/Access, SLI/SLO, Monitoring, Incident, Backup/RPO/RTO, Retention, Rollback
7. 기능 정의서 — Actor/Trigger, Preconditions, Input, Business Rules, Normal/Exception Flow, Acceptance
8. IA — Navigation, Page Inventory, User Journey, Permission
9. 화면 설계서 — Components, Data/Action, Validation, Permission, Loading/Empty/Error State, API/Event
10. 시스템 구조도 — Drivers/Concerns, System Context, Containers/Components, Interfaces, Deployment, ADR/Risk
11. 데이터 플로우 — Source/Data/Event, Validation/Transform, Destination, Protocol, Failure, Data Dictionary, Retention
12. API 설계 문서 — Convention, Endpoint/Message, OpenAPI, Error, Timeout/Retry, Idempotency, Version/Deprecation
13. QA 문서 — Strategy, Environment, Test Case, Expected/Actual, Evidence, Defect, Coverage, Release Gate

상세 기준은 `docs/DELIVERABLE_STANDARDS_V014.md`를 참고하세요.

확인되지 않은 사실은 문서 형식만 유지하고 `TBD · 확인 필요`로 표시합니다. AI가 정한 일정·기술 같은 가역적 기본값은 PROVISIONAL이며 실제 비용·보안 권한·개인정보·법규·실제 설비 제어는 Human Gate 없이 확정하지 않습니다.

---

## 프로젝트 생성 흐름

```text
막연한 아이디어
   ↓
AI Design Session
   ↓
Codex / Claude Code / OpenCode / Antigravity와 자유 대화
   ↓
Live Draft가 웹에 실시간 반영
   ├─ Project Brief
   ├─ Requirements / Decisions
   ├─ 13종 Documents
   ├─ System Process
   ├─ Architecture
   └─ Data Flow
   ↓
/preview
   ↓
전체 대화를 Project Distiller가 기준선으로 정리
   ↓
/apply
   ↓
같은 Draft가 active 프로젝트로 승격
```

`/apply` 전에는 프로젝트 목록에서 `🟡 설계중` Live Draft로 표시됩니다.

---

# Windows 사용법

Python 3.11+ 권장입니다.

처음 받는 경우:

```bat
git clone https://github.com/tmdgns104/team_project_os.git
cd team_project_os
run_windows.bat
```

이미 Git clone한 폴더가 있는 경우:

```bat
cd D:\team_project_os\team_project_os-main
git pull origin main
run_windows.bat
```

브라우저:

```text
http://localhost:8000
```

새 CMD를 열고 AI CLI 확인:

```bat
cd D:\team_project_os\team_project_os-main
python project_os.py doctor
```

Codex Design Session:

```bat
python project_os.py design --provider codex --member "승훈" --autofill
```

여러 줄을 붙여넣고 싶으면 원하는 내용을 복사한 뒤:

```text
나> /paste
```

이라고 입력합니다.

---

# macOS 사용법

Python 3.11+와 Git이 필요합니다.

처음 받는 경우:

```bash
git clone https://github.com/tmdgns104/team_project_os.git
cd team_project_os
bash run_mac.sh
```

이미 받은 경우:

```bash
cd team_project_os
git pull origin main
bash run_mac.sh
```

브라우저:

```text
http://localhost:8000
```

새 Terminal에서 AI CLI 확인:

```bash
cd team_project_os
python3 project_os.py doctor
```

Codex Design Session:

```bash
python3 project_os.py design --provider codex --member "내 이름" --autofill
```

여러 줄 입력은 클립보드에 복사한 뒤:

```text
나> /paste
```

를 사용합니다.

---

# AI Design Session 명령

| 명령 | 기능 |
|---|---|
| `/paste` | OS 클립보드의 여러 줄을 하나의 메시지로 입력 |
| `/status` | 현재 세션, Autofill, Live Draft 상태 확인 |
| `/autofill on` | 모르는 저위험 세부사항을 AI가 PROVISIONAL로 임시 결정 |
| `/autofill off` | 모르는 항목을 질문/TBD 방식으로 유지 |
| `/preview` | 전체 대화를 구조화해 최종 적용 전 확인 |
| `/apply` | Live Draft를 정식 active 프로젝트로 승격 |
| `/discard` | 현재 Live Draft 삭제 |
| `/quit` | 세션 저장 후 종료 |

Design Session 파일은 기본적으로 다음 위치에 저장됩니다.

```text
~/.team_project_os/design_sessions/
```

---

# Live Design Draft

대화 한 턴이 끝날 때마다 AI를 한 번 더 호출하지 않고, **같은 응답 안의 작은 구조화 Delta**를 사용해 웹을 갱신합니다.

```text
사용자 입력
  ↓
AI 1회 응답
  ├─ 사람이 읽는 대화
  └─ PROJECT_OS_DELTA
           ↓
      State 정규화
           ↓
      Live Draft API
           ↓
        WebSocket
           ↓
Documents / Requirements / Decisions / Canvas 갱신
```

V0.14에서는 잘못된 Delta 항목을 누적하지 않아 하나의 잘못된 AI 응답이 이후 모든 Sync의 HTTP 500으로 이어지는 것을 방지합니다.

---

# Documents

웹 Documents는 Markdown 원문 textarea가 기본 화면이 아니라 **Read-first 실무 산출물 Workspace**입니다.

- 보고서형 제목/문서 메타
- 자동 목차
- 제목 계층
- 표 / 체크리스트 / Callout / 코드블록
- Markdown 편집 모드
- Revision / Discussion
- 브라우저 인쇄/PDF 레이아웃

Markdown은 Source of Truth로 유지되므로 Export와 직접 편집이 가능합니다.

---

# 개발 마일스톤 Gantt

마일스톤 Markdown의 다음 표가 Source of Truth입니다.

```markdown
| Phase | ID | Task | Start Week | End Week | Owner | Status |
|---|---|---|---|---|---|---|
| A. 정의 및 설계 | MS-001 | 프로젝트 착수 | 1 | 1 | PM | Done |
| B. 구현 | MS-006 | 핵심 기능 구현 | 2 | 4 | Dev | In Progress |
```

웹에서는 이를 `Level + Task + Month + Week` 형태 Gantt로 보여줍니다.

일정이 `10일 V1`, `4주`, `3개월`처럼 정해지면 V0.14는 그 기간에 맞게 상대 주차를 조정합니다. 일정 정보가 부족한 경우에만 더 긴 PROVISIONAL 초안을 사용합니다.

---

# System Process / Architecture / Data Flow

세 디자인은 같은 그림을 반복하지 않습니다.

- **System Process** — 실제 처리 순서와 Decision/분기 중심
- **Architecture** — Input/Device → Application/Service → Data/UI 계층과 시스템 책임 중심
- **Data Flow** — Source → Validate/Process → Store/Consumer, 데이터 이름과 방향 중심

전용 SVG Layout Engine이 그래프 연결을 분석해 레이어를 만들고, 노드 겹침·연결선 교차를 줄이며 Edge는 노드 경계 포트에서 연결합니다.

---

# Provider 지원

```text
Codex
Claude Code
OpenCode
Antigravity CLI
```

긴 Prompt는 Windows/macOS 셸의 명령행 길이·인용 문제를 피하도록 stdin 또는 UTF-8 임시 파일로 전달합니다.

AI CLI 탐지:

Windows:

```bat
python project_os.py doctor
```

macOS/Linux:

```bash
python3 project_os.py doctor
```

---

# Docker

```bash
cp .env.example .env
docker compose up -d --build
```

브라우저:

```text
http://localhost:8000
```

외부 네트워크에서 사용할 때는 `.env`의 `APP_ACCESS_KEY`를 변경하세요.

---

# 검증

전체 Python 테스트:

```bash
python -m unittest discover -s tests -v
```

V0.14 전체 프로젝트 시뮬레이터:

```bash
python tools/simulate_full_project_v014.py
```

이 시뮬레이터는 HMI/MES 프로젝트를 처음부터 생성해 다음을 확인합니다.

```text
Live Draft 생성
→ 반복 Live Sync
→ 일부 malformed AI Delta 삽입
→ 모든 Sync HTTP 200
→ 13종 전문 문서 생성
→ Requirements / accepted / provisional
→ System Process 생성 및 Edge 무결성
→ Architecture 생성 및 Edge 무결성
→ Data Flow 생성 및 Edge 무결성
→ /apply 상당 Promote
→ lifecycle=active
→ 13종 문서 및 3개 디자인 유지
```

GitHub Actions는 **Windows / macOS / Ubuntu**에서 다음을 모두 실행합니다.

- Python compile
- 전체 regression
- Provider simulations
- Diagram readability
- Milestone Gantt renderer
- Design Session E2E
- Autofill E2E
- Live Draft E2E
- V0.12 documents + diagrams E2E
- Milestone E2E
- V0.14 full project + 13 professional docs + 3 diagrams + malformed Live Sync E2E
- Cross-platform launcher smoke
- macOS/POSIX shell syntax
- CLI smoke
- JavaScript syntax

---

# 관련 문서

- `docs/DESIGN_SESSION.md` — AI Design Session 흐름
- `docs/AUTOFILL_MODE.md` — AI 임시 결정 / Human Gate
- `docs/PROJECT_WORKFLOW.md` — 프로젝트 운영 흐름
- `docs/PROFESSIONAL_DOCUMENTS.md` — Read-first 문서 UI 기준
- `docs/DELIVERABLE_STANDARDS_V014.md` — V0.14 13종 실무 산출물 조사 기준
- `docs/ANTIGRAVITY_CLI.md` — Antigravity CLI 연결

---

# 현재 보안/운영 경계

현재 기본 구성은 개인/데모/소규모 팀 환경을 목표로 합니다. 실제 외부·기업 운영 전에는 사용자 로그인/RBAC, Secret 관리, Audit Log, SSO/OIDC, 프로젝트별 Provider 정책, 운영 DB, Backup/Restore, 보안/개인정보 검토를 별도로 완료해야 합니다.

핵심 방향은 **“문서를 이미 쓸 줄 아는 사람이 빈 양식에 입력하는 도구”가 아니라, 아이디어 단계의 사람이 AI와 대화하는 동안 프로젝트가 실무 산출물·일정·설계로 점진적으로 구체화되고 마지막에 팀의 Source of Truth로 승격되는 Project OS**입니다.
