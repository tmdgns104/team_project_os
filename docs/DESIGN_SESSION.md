# AI Design Session

Team Project OS의 권장 프로젝트 시작 방식은 **막연한 아이디어 → AI와 자유 대화 → `/preview` → `/apply` → 정식 프로젝트 생성**입니다.

```bat
python project_os.py design --provider codex --member "승훈"
```

대화 중에는 Project OS의 프로젝트/문서/Canvas를 변경하지 않습니다. AI도 이 단계에서는 JSON을 만들지 않고 일반 대화로 문제, 목표, 사용자, 범위, 기능, Process, Architecture, Data Flow, 일정, 리스크, 테스트 방법을 함께 구체화합니다.

```text
나> HMI MES 프로그램을 만들어보고 싶어
codex> 어떤 생산라인과 PLC를 가정할까요? ...

나> Mitsubishi PLC 시뮬레이터와 작은 컨베이어로 시작하자
codex> V1 범위를 PLC 상태 수집, HMI 표시, 생산실적 저장 정도로 잡는 게 좋습니다. ...

나> /preview
```

`/preview`는 전체 대화를 Project Distiller가 한 번 읽고 다음 항목을 미리보기로 구조화하지만 서버에는 아직 프로젝트를 만들지 않습니다.

- Project Brief
- Requirements
- confirmed Decisions
- Documents
- System Process
- Architecture
- Data Flow
- pending / TBD

AI가 제안했지만 사용자가 수락하지 않은 내용은 확정 Decision으로 만들지 않습니다. 예산, 일정, KPI, 장비, DB, 프로토콜처럼 대화에서 정하지 않은 값은 임의로 확정하지 않고 pending/TBD에 남깁니다.

충분히 구체화되면:

```text
나> /apply
```

`/apply` 시점에만 같은 Distiller 결과를 Project OS에 실제로 생성합니다. 새 프로젝트에는 기본 13개 문서가 생성되고, 대화에서 근거가 있는 Requirements와 Process/Architecture/Data Flow Canvas가 함께 만들어집니다.

## 명령

- `/status`: 현재 Design Session 대화 턴과 세션 저장 위치 확인
- `/preview`: 전체 대화를 구조화해 미리보기. 프로젝트는 생성하지 않음
- `/apply`: 전체 대화를 구조화하고 Project OS에 정식 프로젝트 생성
- `/quit`: 세션을 저장하고 종료

대화 내용은 기본적으로 사용자 홈의 `~/.team_project_os/design_sessions/`에 저장됩니다.

## Provider

```bat
python project_os.py design --provider codex
python project_os.py design --provider claude
python project_os.py design --provider opencode
python project_os.py design --provider antigravity
```

Provider Adapter는 긴 한글/영문 Prompt가 Windows 명령행에서 분리되지 않도록 각 CLI별 안전한 전달 경로를 사용합니다.

## 시뮬레이터

```bat
python tools\simulate_design_session.py
```

HMI/MES의 막연한 아이디어에서 시작해 여러 턴의 설계 대화가 있었다고 가정한 뒤 `/apply` 결과를 실제 FastAPI/SQLite에 생성합니다. 아래를 모두 검증합니다.

- 프로젝트 생성
- 기본 문서 13개
- Requirements
- System Process Canvas
- Architecture Canvas
- Data Flow Canvas

CI에서는 이 시뮬레이터와 Codex / Claude Code / OpenCode / Antigravity Provider Adapter 시뮬레이션을 Windows와 Ubuntu에서 실행합니다.
