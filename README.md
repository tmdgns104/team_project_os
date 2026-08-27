# Team Project OS V0.10

사람이 처음부터 완벽한 기획서를 작성하지 않아도, **자기 생성형 AI와 충분히 대화해 프로젝트를 구체화한 뒤 `/apply`로 Project OS에 정식 프로젝트를 만드는 팀 협업 프로그램**입니다.

AI는 프로젝트의 필수 의존성이 아니라 선택 가능한 Worker Provider입니다. AI를 사용하지 않는 팀원도 같은 웹 UI와 프로젝트 상태를 사용할 수 있고, AI를 사용하는 팀원은 자기 PC의 **Codex / Claude Code / OpenCode / Antigravity CLI**를 연결합니다.

## V0.10 Live Design Draft

AI Design Session을 오래 진행해도 웹이 빈 상태로 기다리지 않습니다. 세션 시작 시 `lifecycle=draft`인 Live Draft가 생성되고, **같은 AI 응답 안의 작은 구조화 delta**를 이용해 의미 있는 결정이 생긴 턴마다 웹을 즉시 갱신합니다. 추가 AI 호출을 만들지 않으므로 기존 대화 속도를 최대한 유지합니다.

```text
AI와 대화
  ↓
같은 응답의 숨은 PROJECT_OS_DELTA
  ↓
Live Draft Sync
  ↓
WebSocket
  ↓
Documents / Requirements / Decisions / Canvas 즉시 갱신
  ↓
/apply
  ↓
같은 Draft를 정식 active 프로젝트로 승격
```

웹의 프로젝트 선택 목록에는 `🟡 설계중`으로 표시되며 `/apply` 전까지 정식 확정본이 아닙니다. `/discard`로 Live Draft만 삭제할 수 있고, `--no-live`로 이전처럼 웹 실시간 동기화를 끌 수도 있습니다.

## 핵심 흐름

```text
막연한 아이디어
   ↓
AI Design Session
   ↓
Codex / Claude Code / OpenCode / Antigravity와 자유 대화
   ↓
문제 · 목표 · 범위 · 기능 · Process · Architecture · Data Flow 구체화
   ↓
모르는 저위험 세부사항은 AI가 PROVISIONAL로 임시 결정 가능
   ↓
/preview
   ↓
Project Distiller가 전체 대화를 한 번 구조화
   ↓
/apply
   ↓
Project OS 정식 프로젝트 생성
   ↓
웹 UI에서 문서 · 요구사항 · Decision · Canvas · Task를 팀이 공유
```

`/apply` 전에는 서버의 프로젝트/문서/Canvas를 변경하지 않습니다.

---

## 현재 주요 기능

- AI Design Session: 막연한 아이디어부터 자유 대화로 프로젝트 구체화
- Provisional Autofill: `알아서 임시로 정해줘`라고 하면 저위험 세부사항을 AI가 임시 결정
- `/preview`: 실제 생성 전에 전체 프로젝트 구조 확인
- `/apply`: Project Brief / Requirements / Decisions / Documents / Canvas 생성
- 사람 확정 Decision(`accepted`)과 AI 임시 Decision(`provisional`) 구분
- 미결정 또는 사람 확인이 필요한 항목은 `pending`으로 유지
- 기본 13종 공동 프로젝트 문서 Workspace + revision + discussion
- System Process / Architecture / Data Flow Canvas
- Traceability
- Development Progress Kanban
- Ideas & Decisions
- Team & AI / AI Task Queue
- Codex / Claude Code / OpenCode / Antigravity Provider Adapter
- Local Bridge를 통한 개인 AI Task 실행
- Docker 또는 Windows 로컬 실행
- 선택적 `APP_ACCESS_KEY`

---

# 가장 빠른 Windows 실행

Python 3.11+ 권장입니다.

```bat
git clone https://github.com/tmdgns104/team_project_os.git
cd team_project_os
run_windows.bat
```

브라우저:

```text
http://localhost:8000
```

AI CLI 설치 상태 확인:

```bat
python project_os.py doctor
```

## Codex와 프로젝트 구상 시작

```bat
python project_os.py design --provider codex --member "내 이름"
```

처음부터 AI에게 모르는 세부사항을 맡기고 싶다면:

```bat
python project_os.py design --provider codex --member "내 이름" --autofill
```

또는 대화 중 자연어로 말하면 됩니다.

```text
HMI MES 프로그램을 만들어보고 싶어.
세부적인 건 잘 모르겠으니까 일반적으로 괜찮은 방식으로 알아서 임시로 다 정해줘.
```

이 문장을 감지하면 Autofill Mode가 자동으로 켜집니다.

---

# AI Design Session 명령

```text
/status
```

현재 대화 턴, 세션 저장 위치, Autofill 상태를 확인합니다.

```text
/autofill on
/autofill off
```

AI 임시 결정 허용 여부를 바꿉니다.

```text
/preview
```

전체 대화를 Project Distiller가 분석해 다음 내용을 미리 보여줍니다. 아직 서버에 프로젝트를 생성하지 않습니다.

- Project Brief
- Requirements
- 사람 확정 Decisions
- AI 임시 Decisions
- Documents
- System Process
- Architecture
- Data Flow
- Pending / TBD

```text
/apply
```

현재 Distiller 결과를 Project OS에 실제 생성합니다.

```text
/quit
```

Design Session을 저장하고 종료합니다.

Design Session은 기본적으로 다음 위치에 저장됩니다.

```text
~/.team_project_os/design_sessions/
```

---

# Decision 상태

Team Project OS V0.10에서는 AI가 대신 고른 값과 사람이 직접 확정한 값을 구분합니다.

| 상태 | 의미 |
|---|---|
| `accepted` | 사람이 직접 정했거나 명시적으로 승인한 결정 |
| `provisional` | AI가 실행 가능한 V1을 만들기 위해 선택한 되돌릴 수 있는 임시 결정 |
| `pending` | 아직 정보가 부족하거나 AI가 임의로 정하면 안 되는 항목 |

Autofill이 대신 정할 수 있는 예:

- SQLite / FastAPI 같은 초기 기술 선택
- Web HMI 기본 화면 구성
- Simulator-first 개발 순서
- Windows Local 같은 초기 배포 방식
- 기본 Module / Folder 구조
- 현실적인 V1 범위

Autofill이 임의로 확정하지 않는 예:

- 실제 비용 지출 / 장비 구매
- Secret / 계정 / 권한 확대
- 개인정보 / 법률 / 규제 정책
- 계약 또는 외부 운영 의무
- 실제 생산라인의 파괴적 변경
- Safety Critical 임계값

자세한 내용: `docs/AUTOFILL_MODE.md`

---

# Provider 지원

```bat
python project_os.py design --provider codex
python project_os.py design --provider claude
python project_os.py design --provider opencode
python project_os.py design --provider antigravity
```

긴 한글/영문 Prompt 전체를 Windows 명령줄 인자로 직접 넣지 않습니다.

| Provider | 긴 Prompt 전달 방식 |
|---|---|
| Codex | stdin (`codex exec --skip-git-repo-check -`) |
| Claude Code | stdin + 짧은 headless 지시 |
| OpenCode | 임시 UTF-8 prompt 파일 |
| Antigravity CLI | 임시 UTF-8 prompt 파일 + headless print |

이 구조는 Windows에서 긴 Prompt가 공백 단위로 분리되는 문제를 피하기 위한 Provider Adapter 계층입니다.

---

# 웹 UI

## Overview

프로젝트 목표, 진행률, Requirement/Task 상태, 최근 활동을 봅니다.

## Goal & Requirements

프로젝트 목표와 요구사항을 공유합니다.

## AI Project Assistant

웹에서도 AI를 통해 프로젝트 변경 제안을 만들 수 있습니다. AI 응답과 Source of Truth 변경은 분리되며 사용자가 적용한 내용만 실제 프로젝트에 반영됩니다.

## Documents

새 프로젝트에는 기본 13종 문서가 생성됩니다.

1. 기획서
2. 계획서
3. 마일스톤
4. 백로그
5. 요구사항 정의서
6. 서비스 및 운영 정책서
7. 기능 정의서
8. IA
9. 화면 설계서
10. 시스템 구조도
11. 데이터 플로우
12. API 설계 문서
13. QA 문서

문서 수정 시 revision이 남고 Discussion 댓글을 공유합니다.

## System Process / Architecture / Data Flow

AI Design Session의 `/apply` 결과로 대화에서 정리된 노드와 연결을 자동 생성할 수 있습니다.

```text
System Process
제품 감지 → 데이터 수집 → 처리 → 저장 → 표시

Architecture
PLC / Device → Gateway → Backend → DB → UI

Data Flow
Source --data--> Gateway --record--> DB --query--> UI
```

## Development Progress

Todo / In Progress / Review / Done 상태를 공유합니다.

## Traceability

Requirement, Feature, Screen/API/Architecture, Task, QA 관계를 연결합니다.

## Ideas & Decisions

아이디어, 사람 확정 Decision, AI 임시 Decision을 프로젝트 기록으로 관리합니다.

---

# BYOAI Task Bridge

Design Session과 별개로, 이미 생성된 프로젝트의 공유 Task를 각 팀원의 개인 AI에 전달할 수 있습니다.

```text
Shared Task
   ↓
Local Bridge
   ↓
Codex / Claude Code / OpenCode / Antigravity
   ↓
코드 작업 / 검증
   ↓
Result + Evidence
   ↓
Shared Project
```

CLI 확인:

```bat
python local_bridge\bridge.py doctor
```

예: Codex Bridge 등록

```bat
python local_bridge\bridge.py register --server http://SERVER_IP:8000 --project 1 --member "내 이름" --provider codex --repo D:\my-project
```

한 번 실행:

```bat
python local_bridge\bridge.py run --repo D:\my-project --once
```

계속 대기:

```bat
python local_bridge\bridge.py run --repo D:\my-project --poll 10
```

Bridge Token은 사용자 홈의 `~/.team_project_os_bridge.json`에 저장되며 Git에 올리면 안 됩니다.

---

# Docker 실행

```bash
cp .env.example .env
docker compose up -d --build
```

브라우저:

```text
http://localhost:8000
```

외부 네트워크에서 사용할 때는 `.env`의 `APP_ACCESS_KEY`를 반드시 변경하세요.

```env
APP_ACCESS_KEY=your-long-random-team-key
```

---

# 검증

전체 테스트:

```bat
python -m unittest discover -s tests -v
```

기본 Design Session 실제 생성 시뮬레이터:

```bat
python tools\simulate_design_session.py
```

Provisional Autofill 실제 생성 시뮬레이터:

```bat
python tools\simulate_autofill_project.py
```

Live Design Draft 실시간 동기화 시뮬레이터:

```bat
python tools\simulate_live_design.py
```

CI는 **Windows와 Ubuntu**에서 다음을 검사합니다.

- Python compile
- 전체 regression tests
- Codex / Claude Code / OpenCode / Antigravity Provider Adapter simulation
- Design Session → 실제 FastAPI + SQLite 프로젝트 생성
- Provisional Autofill → accepted/provisional 분리 및 실제 프로젝트 생성
- 13개 Documents
- Requirements / Decisions
- Process / Architecture / Data Flow Canvas
- CLI smoke test
- JavaScript syntax

---

# 문서

- `docs/DESIGN_SESSION.md` — AI와 충분히 대화한 뒤 `/preview`, `/apply`하는 전체 흐름
- `docs/AUTOFILL_MODE.md` — 모르는 세부사항을 AI가 PROVISIONAL로 임시 결정하는 규칙
- `docs/PROJECT_WORKFLOW.md` — 프로젝트 생성 후 문서/설계/개발/QA 운영 흐름
- `docs/ANTIGRAVITY_CLI.md` — Antigravity CLI 연결

---

# 현재 보안 경계

현재 `APP_ACCESS_KEY`는 데모/소규모 팀용 공유키입니다. 기업 또는 실제 외부 운영 전에는 다음이 필요합니다.

- 사용자 로그인 / RBAC
- SSO/OIDC
- 프로젝트별 AI Provider 허용 정책
- Secret / 고객 데이터 Context 차단
- Audit Log
- Allowed Files / Allowed Commands
- Human Gate
- GitHub/GitLab 권한 연동
- 운영 DB 및 다중 서버 구조

AI Agent가 로컬 파일과 명령을 다룰 수 있으므로 실제 운영 환경에서는 프로젝트별 실행 범위를 명시적으로 제한해야 합니다.

---

# 다음 권장 개발 순서

1. Adaptive Document Packs — 프로젝트 유형별 문서 세트
2. Diagram drag/drop / edit / delete / auto-layout
3. Requirement 변경 영향 분석
4. Git/Test Evidence 자동 수집
5. Connector.exe GUI
6. 사용자 로그인 + RBAC
7. Postgres / Redis 기반 다중 사용자 운영 구조
8. 프로젝트별 Knowledge/RAG
9. DOCX/PDF 정식 Export

핵심 방향은 **“프로젝트 설계를 이미 아는 사람이 입력하는 도구”가 아니라, 사람이 AI와 함께 막연한 아이디어를 실행 가능한 프로젝트로 만든 뒤 그 결과를 팀의 Source of Truth로 전환하는 Project OS**입니다.
