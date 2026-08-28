# Team Project OS V0.15

> 사람과 팀이 자기 AI(Codex / Claude Code / OpenCode / Antigravity CLI)와 대화하면서 막연한 아이디어를 실제 프로젝트 산출물로 구체화하고, `/apply`로 승인한 결과만 팀의 Source of Truth로 승격하는 Human-centered Project OS.

## V0.15 핵심

V0.15는 V0.14의 Live Draft / Autofill / 전문 문서 / 3종 Design 흐름을 유지하면서 문서 생성 구조를 강화합니다.

- `REQ → Process/Architecture/Data/API → Backlog/Task → TC → Evidence` 추적성
- Milestone / Backlog / Function / Screen / Interface / Test / Policy / Data Catalog 구조화
- 13개 문서를 동일한 구조화 Project State에서 Materialization
- 모든 문서에 Version / Status / Confirmed / PROVISIONAL / Related REQ / Verification / Pending / 변경 이력 공통 메타데이터
- 마일스톤은 Phase / Task / Start Week / End Week / Owner / Status / Deliverable / Exit Criteria 기반 Gantt
- System Process / Architecture / Data Flow는 서로 다른 관점의 완전한 Graph로 관리
- `/apply` 시 기존 Live Draft의 Stable ID 또는 더 상세한 문서/Graph가 사라지면 기존 상세본 보존
- Windows / macOS / Ubuntu CI 검증

## 빠른 시작

### Windows

```bat
run_windows.bat
```

### macOS

```bash
bash run_mac.sh
```

### Linux

```bash
bash run_linux.sh
```

브라우저:

```text
http://localhost:8000
```

AI CLI 연결 확인:

```bash
python project_os.py doctor
```

Codex Design Session:

```bash
python project_os.py design --provider codex --member "사용자" --autofill
```

Windows CMD/macOS Terminal에서 긴 여러 줄 요구사항을 클립보드에 복사한 뒤 Design Session에서 다음을 입력할 수 있습니다.

```text
/paste
```

주요 명령:

```text
/status
/autofill on
/autofill off
/preview
/apply
/discard
/quit
```

## 프로젝트 생성 흐름

```text
막연한 아이디어
  ↓
AI Design Session
  ↓
Live Draft
  ├─ Project Brief
  ├─ Requirements
  ├─ Decisions
  ├─ Milestone / Backlog / Function / Screen / API / QA catalogs
  ├─ 13 professional documents
  └─ System Process / Architecture / Data Flow
  ↓
/preview
  ↓
/apply (Human Gate)
  ↓
Active Project / Source of Truth
```

`/apply`는 상세 Live Draft를 짧은 최종 요약으로 다시 덮어쓰는 단계가 아닙니다. V0.15는 기존 Stable ID와 상세 산출물의 비퇴행을 검사해 더 풍부한 Live Draft를 보존합니다.

## 13개 실무 문서

1. 기획서
2. 프로젝트 계획서
3. 개발 마일스톤 / Gantt
4. Product / Project Backlog
5. 요구사항 정의서
6. 서비스 및 운영 정책서
7. 기능 정의서
8. IA
9. 화면 설계서
10. 시스템 구조도
11. 데이터 플로우
12. API / Interface 설계 문서
13. QA / Test Plan & Result

문서들은 독립적인 템플릿 13장을 채우는 방식이 아니라 동일한 구조화 설계 상태를 공유합니다. 예를 들어 `REQ-MES-001`은 `FUNC-MES-001`, `SCR-HMI-001`, `API-WS-001`, `TC-MES-001` 같은 Stable ID와 연결될 수 있습니다.

## Design 3종

### System Process
업무/설비의 실제 실행 순서와 정상·분기·예외 흐름을 표현합니다.

### Architecture
Device / Adapter / Service / Data / UI의 책임과 인터페이스 경계를 표현합니다.

### Data Flow
데이터의 Source → Validation/Transform → Store → Consumer 이동을 표현합니다.

## Provider

지원 Provider:

- Codex
- Claude Code
- OpenCode
- Antigravity CLI
- dry-run

공유 서버는 사용자의 AI 구독을 소유하거나 대신 소비하지 않습니다. AI를 사용하는 팀원은 각자의 로컬 CLI를 사용합니다.

## 검증

CI는 Python 3.12 기준으로 다음 운영체제에서 실행됩니다.

- Ubuntu latest
- Windows latest
- macOS latest

주요 검증:

- Python compile
- Full regression
- Diagram layout readability
- Milestone Gantt renderer
- Design Session materialization
- Autofill materialization
- Live Draft sync
- V0.14 compatibility E2E
- V0.15 13 documents + 3 diagrams E2E
- `/apply` document/design non-regression
- Cross-platform launcher smoke
- CLI help
- JavaScript syntax

## 기본 원칙

- Human이 목적·중요 변경·최종 승인을 담당합니다.
- AI는 Worker/Advisor이며 프로젝트의 권위가 아닙니다.
- AI가 정한 가역적인 기본값은 `PROVISIONAL`로 표시합니다.
- 비용·권한·개인정보·법률/규제·실제 설비 Safety 같은 고위험 결정은 자동 확정하지 않습니다.
- Active Project와 Traceability/Evidence가 팀의 Source of Truth입니다.
