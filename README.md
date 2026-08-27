# Team Project OS V0.2

사람과 각자의 생성형 AI가 **같은 프로젝트 상태를 공유하면서 일하기 위한 팀 협업 프로그램**입니다.

AI가 없는 팀원도 그대로 사용할 수 있고, AI를 사용하는 팀원은 자기 PC의 **Codex / Claude Code / OpenCode / Antigravity CLI**를 Local Bridge로 연결할 수 있습니다.

## V1에서 바로 되는 것

- 새 프로젝트 생성 및 프로젝트 목표/요구사항 공유
- 13종 공동 프로젝트 문서 Workspace (revision + discussion)
- 개발 진척도 Kanban 보드
- 전체 System Process 시각화
- Architecture 구성도 시각화
- Data Flow 시각화
- 아이디어 / Decision(ADR) 공유
- 팀원별 AI 사용 여부 표시
- 실시간 WebSocket 갱신
- Codex / Claude Code / OpenCode / Antigravity CLI Local Bridge 등록
- 공유 Task를 개인 AI 대기열로 전달
- 개인 AI 실행 결과와 Evidence를 공유 서버로 회수
- Docker 기반 팀 서버 배포
- 선택적 `APP_ACCESS_KEY` 접근 보호

> V1은 제품 방향과 팀 협업 흐름을 검증하기 위한 실행 가능한 프로토타입입니다. 기업용 인증, 세밀한 RBAC, GitHub OAuth, DB 마이그레이션, 파일/Secret 정책은 V2 영역입니다.

---

## 구조

```text
                    Team Project OS Server
                            │
        Goal / Requirement / Task / Decision
        Process / Architecture / Data Flow
                            │
                     WebSocket/API
             ┌──────────────┼──────────────┐
             │              │              │
          Team A          Team B          Team C
             │              │              │
       Local Bridge    Local Bridge      AI 없음
             │              │
           Codex        Claude Code
```

핵심 원칙은 **AI가 프로젝트의 중심이 아니라 각 개인의 선택 가능한 작업 도구**라는 것입니다.

---

## 가장 빠른 실행: Docker

### 1. 환경 파일

```bash
cp .env.example .env
```

Windows CMD에서는 `.env.example`을 `.env`로 복사해도 됩니다.

팀 외부 네트워크에서 사용할 경우 `.env`의 키를 반드시 변경하세요.

```env
APP_ACCESS_KEY=your-long-random-team-key
```

### 2. 실행

```bash
docker compose up -d --build
```

브라우저:

```text
http://localhost:8000
```

다른 팀원은 서버 PC의 IP나 배포 도메인으로 접속합니다.

```text
http://SERVER_IP:8000
```

서버에서 `APP_ACCESS_KEY`를 설정했다면 화면 오른쪽 상단 **접속키**에 같은 키를 입력합니다.

---

## Docker 없이 실행

Python 3.11+ 권장.

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

# BYOAI: 팀원이 자기 AI 연결하기

## 개념

팀 서버가 팀원의 Codex/Claude 계정을 소유하지 않습니다.

각 팀원의 PC에서 Local Bridge가 실행되고, Team Project OS가 해당 팀원에게 배정한 Task만 가져옵니다.

```text
Shared Task
   ↓
Local Bridge
   ↓
Codex / Claude Code / OpenCode / Antigravity CLI
   ↓
코드 작업 / 검증
   ↓
Result + Evidence
   ↓
Shared Project
```

## 1. AI CLI 확인

```bash
python local_bridge/bridge.py doctor
```

## 2. Bridge 등록

예: 프로젝트 ID가 1이고 팀 서버가 `http://192.168.0.20:8000`인 경우

### Codex

```bash
python local_bridge/bridge.py register --server http://192.168.0.20:8000 --project 1 --member "승훈" --provider codex --repo D:\my-project
```

### Claude Code

```bash
python local_bridge/bridge.py register --server http://192.168.0.20:8000 --project 1 --member "서연" --provider claude --repo D:\my-project
```

접근키가 설정된 서버라면:

```bash
python local_bridge/bridge.py register --server http://192.168.0.20:8000 --project 1 --member "승훈" --provider codex --repo D:\my-project --access-key YOUR_KEY
```

등록 정보와 Bridge Token은 사용자 홈의 다음 파일에 저장됩니다.

```text
~/.team_project_os_bridge.json
```

이 파일은 개인 인증 정보이므로 Git에 올리지 마세요.

## 3. AI Task 실행

웹 UI에서 **Team & AI → AI Task Queue → + AI 작업**으로 Task를 등록한 뒤 팀원 PC에서:

```bash
python local_bridge/bridge.py run --repo D:\my-project --once
```

계속 대기시키려면:

```bash
python local_bridge/bridge.py run --repo D:\my-project --poll 10
```

### 기본 CLI 호출

V1 기본 Adapter는 다음 방식으로 실행합니다.

- Codex: `codex exec <project-task-prompt>`
- Claude Code: `claude -p <project-task-prompt> --output-format text`
- OpenCode: `opencode run <project-task-prompt>`

개인 설치나 버전에 따라 명령 형식이 다르면 등록 또는 run 시 `--command`로 덮어쓸 수 있습니다.

예:

```bash
python local_bridge/bridge.py run --repo D:\my-project --once --command "my-ai-cli run {prompt}"
```

---

# UI 화면

## Overview

- Project Goal
- 전체 진행률
- Requirement 수
- 완료 Task / Blocked Task
- Local AI Bridge 연결 수
- 최근 프로젝트 활동

## Goal & Requirements

- 프로젝트 목표 수정
- 요구사항 등록
- 프로젝트 초기 정의 공유

## Development Progress

- Todo
- In Progress
- Review
- Done

사람이 직접 작업해도, Codex가 작업해도, Claude Code가 작업해도 같은 Task 보드에서 보입니다.

## System Process

예:

```text
제품 투입 → 센서 감지 → 촬영 → AI 추론 → 판정 → PLC → 저장 → Dashboard
```

노드와 연결을 웹 UI에서 추가할 수 있습니다.

## Architecture

예:

```text
Camera → Jetson → Inference Service → Backend → PostgreSQL → Dashboard
```

## Data Flow

각 연결에 `RGB Image`, `Tensor`, `DetectionResult`, `JSON` 같은 데이터 이름을 붙일 수 있습니다.

## Ideas & Decisions

회의 중 나온 아이디어를 바로 구현 Task로 만들기 전에 별도로 남기고, 합의된 내용은 Decision/ADR로 기록합니다.

## Team & AI

팀원별로 다음처럼 표시됩니다.

```text
승훈       Project Lead    Codex
민수       Backend         Codex
지현       Edge/PLC        Human only
서연       Frontend        Claude Code
```

---

# 외부 서버에 배포

가장 간단한 방식은 Docker가 가능한 Linux VM/VPS에 저장소를 복사한 후:

```bash
docker compose up -d --build
```

을 실행하는 것입니다.

실제 인터넷 공개 환경에서는 다음을 권장합니다.

```text
Internet
   ↓
HTTPS Reverse Proxy (Caddy / Nginx / Cloudflare Tunnel 등)
   ↓
Team Project OS :8000
```

V1 자체에는 TLS 인증서 발급 기능을 넣지 않았습니다.

---

# 현재 보안 경계

V1의 `APP_ACCESS_KEY`는 데모/소규모 팀용 공유키입니다.

기업 또는 공개 서비스용으로 발전시킬 경우 다음을 추가해야 합니다.

- 사용자 계정 / 로그인
- Project별 RBAC
- SSO/OIDC
- AI Provider 허용 정책
- Secret / 고객 데이터 Context 차단
- Audit Log
- GitHub/GitLab 권한 연동
- AI 작업별 Allowed Files / Allowed Commands
- 승인 Gate

특히 AI Agent는 로컬 파일과 명령을 다룰 수 있으므로, 운영 환경에서는 **프로젝트별 권한과 실행 범위를 명시적으로 제한**하는 것이 중요합니다.

---

# 다음 V2 권장 순서

1. GitHub Repository 연결 및 Commit/PR 자동 동기화
2. 사용자 로그인 + 역할 권한
3. Project Graph 관계 모델 (`Requirement → Process → Component → Task → Evidence`)
4. Diagram drag/drop 편집
5. Requirement 변경 영향 분석
6. AI Context Builder
7. Allowed/Forbidden Scope + Human Gate
8. Test/Git Evidence 자동 수집
9. 프로젝트별 Knowledge/RAG
10. Slack/Teams/Notion 연동



---

# V0.2: 프로젝트를 처음부터 시작하기

웹 상단의 **+ 새 프로젝트**를 누르면 프로젝트 이름, 목표, 배경/성공 기준을 입력해 빈 프로젝트를 만들 수 있습니다. 새 프로젝트에는 아래 13종 문서가 자동 생성됩니다.

- 기획서
- 계획서
- 마일스톤
- 백로그
- 요구사항 정의서
- 서비스 및 운영 정책서
- 기능 정의서
- IA (Information Architecture, 정보구조도)
- 화면 설계서
- 시스템 구조도
- 데이터 플로우
- API 설계 문서
- QA 문서

`Documents` 화면에서 팀이 같은 문서를 작성합니다. 저장 전 내용은 revision으로 남고, 문서별 Discussion 댓글도 공유됩니다. 자세한 흐름은 `docs/PROJECT_WORKFLOW.md`를 참고하세요.

## Antigravity CLI

Local Bridge에서 `antigravity` provider를 선택할 수 있습니다. Antigravity CLI는 공식 headless print mode를 사용합니다.

```bash
python local_bridge/bridge.py doctor
python local_bridge/bridge.py register --server http://SERVER_IP:8000 --project 1 --member "내 이름" --provider antigravity --repo D:\my-project
python local_bridge/bridge.py run --repo D:\my-project --once
```

Bridge 기본 실행은 `agy -p ... --output-format text --print-timeout 45m`이며, 전체 도구 권한을 자동 승인하는 옵션은 기본 적용하지 않습니다. 자세한 내용은 `docs/ANTIGRAVITY_CLI.md`를 참고하세요.


## V0.3 - 프로젝트 처음부터 생성 / Traceability / 첨부 패키지

- 새 프로젝트 생성 시 문제, 대상 사용자, 성공 기준, 범위, 제약조건을 입력할 수 있습니다.
- 입력값은 기획서와 계획서 초기 초안에 자동 반영됩니다.
- Traceability 화면에서 Requirement → Feature → IA/Screen → API/Architecture → Task → QA 관계를 연결할 수 있습니다.
- Task의 `REQ-xxx` 참조는 자동 Trace로 표시됩니다.
- Documents에서 선택 문서를 Markdown으로 다운로드할 수 있습니다.
- `첨부 패키지 ZIP`은 13종 문서, Traceability Matrix, Process/Architecture/Data Flow Mermaid 문서, 구조화 snapshot JSON을 묶어 생성합니다.

> 현재 Export는 Markdown/ZIP 중심입니다. PDF/DOCX 제출본 렌더링은 후속 버전에서 확장할 수 있습니다.
