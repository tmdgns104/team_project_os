# AI Design Session

Team Project OS V0.10의 권장 프로젝트 시작 방식은 **막연한 아이디어 → AI와 자유 대화 → 필요하면 Autofill → `/preview` → `/apply` → 정식 프로젝트 생성**입니다.

```bat
python project_os.py design --provider codex --member "내 이름"
```

대화 중에는 정식 Source of Truth를 확정 변경하지 않습니다. 대신 V0.10에서는 `lifecycle=draft`인 **Live Draft**가 만들어지고, 의미 있는 결정이 생긴 턴마다 Documents / Requirements / Decisions / Canvas가 웹에서 실시간 갱신됩니다. `/apply` 시 같은 Draft를 정식 프로젝트로 승격합니다. 자세한 내용은 `LIVE_DRAFT.md`를 참고하세요.

AI는 이 단계에서 일반 대화로 문제, 목표, 사용자, 범위, 기능, Process, Architecture, Data Flow, 일정, 리스크, 테스트 방법을 함께 구체화합니다. AI도 이 단계에서는 JSON을 만들지 않고 일반 대화로 문제, 목표, 사용자, 범위, 기능, Process, Architecture, Data Flow, 일정, 리스크, 테스트 방법을 함께 구체화합니다.

## 기본 예시

```text
나> HMI MES 프로그램을 만들어보고 싶어

codex> 어떤 생산라인과 PLC를 가정할까요? 처음에는 시뮬레이터로 시작해도 됩니다.

나> Mitsubishi PLC와 작은 컨베이어를 생각하고 있어.

codex> 그러면 V1은 PLC 데이터 수집, HMI 표시, 생산실적 저장 정도로 줄일 수 있습니다.
```

사용자가 세부 구현을 잘 모르면 AI에게 위임할 수 있습니다.

```text
나> 세부적인 건 잘 모르겠으니까 일반적으로 괜찮은 방식으로 알아서 임시로 다 정해줘.
```

이 표현을 감지하면 **Autofill Mode**가 자동으로 켜집니다.

Autofill Mode에서는 DB, Backend Framework, 기본 화면 구성, Simulator-first 개발 순서처럼 **되돌릴 수 있는 저위험 선택**을 AI가 `provisional` Decision으로 임시 결정할 수 있습니다.

반대로 실제 비용 지출, 장비 구매, Secret/권한 확대, 개인정보·법률·규제 정책, 계약, 실제 생산설비의 파괴적 변경, Safety Critical 임계값 등은 임의 확정하지 않고 `pending`으로 남깁니다.

자세한 규칙은 `AUTOFILL_MODE.md`를 참고하세요.

---

## `/preview`

```text
나> /preview
```

Project Distiller가 **전체 대화를 한 번** 읽고 프로젝트 구조를 만듭니다. 서버에는 아직 프로젝트가 생성되지 않습니다.

미리보기 항목:

- Project Brief
- Requirements
- 사람 확정 Decisions (`accepted`)
- AI 임시 Decisions (`provisional`)
- Documents
- System Process
- Architecture
- Data Flow
- Pending / TBD

예:

```text
Project OS 생성 미리보기

프로젝트: HMI MES 미니 생산라인
요구사항: 8개
사람 확정 Decision: 2개
AI 임시 Decision: 5개
Canvas 설계: 3개

AI 임시 결정(PROVISIONAL):
- DB: SQLite
- Backend: FastAPI
- HMI: Web UI
- V1 실행환경: Windows Local

미결정/TBD:
- 실제 PLC 통신 방식
- 운영 보안 정책
```

사용자가 AI 제안을 직접 승인한 경우는 `accepted`로 만들 수 있지만, AI가 대신 선택한 기본값은 반드시 `provisional`로 유지합니다.

---

## `/apply`

```text
나> /apply
```

`/apply` 시점에만 Distiller 결과를 Project OS에 실제 생성합니다.

생성 가능한 항목:

```text
Project Brief
Requirements
Decisions
13개 기본 Documents
System Process Canvas
Architecture Canvas
Data Flow Canvas
```

AI 임시 Decision도 `provisional` 상태 그대로 저장되므로 이후 실제 팀 결정이 생기면 교체하거나 수정할 수 있습니다.

---

## 명령

- `/status` — 현재 대화 턴, Session 저장 위치, Autofill 상태 확인
- `/autofill on` — 모르는 저위험 세부사항을 AI 임시 결정으로 채우기
- `/autofill off` — 자동 임시 결정을 끄고 질문/TBD 방식으로 돌아가기
- `/preview` — 전체 대화를 구조화해 미리보기. 프로젝트 생성 안 함
- `/apply` — 전체 대화를 구조화하고 Project OS에 정식 프로젝트 생성
- `/quit` — Session 저장 후 종료

Design Session은 기본적으로 다음 위치에 저장됩니다.

```text
~/.team_project_os/design_sessions/
```

처음부터 Autofill을 켜고 시작할 수도 있습니다.

```bat
python project_os.py design --provider codex --member "내 이름" --autofill
```

---

## Provider

```bat
python project_os.py design --provider codex
python project_os.py design --provider claude
python project_os.py design --provider opencode
python project_os.py design --provider antigravity
```

Provider Adapter는 긴 한글/영문 Prompt가 Windows 명령행에서 분리되지 않도록 CLI별 안전한 전달 경로를 사용합니다.

- Codex: stdin
- Claude Code: stdin 기반 headless 호출
- OpenCode: 임시 UTF-8 prompt 파일
- Antigravity: 임시 UTF-8 prompt 파일 + headless print

---

## 검증

기본 Design Session E2E:

```bat
python tools\simulate_design_session.py
```

Autofill E2E:

```bat
python tools\simulate_autofill_project.py
```

Autofill 시뮬레이터는 HMI/MES의 막연한 아이디어에서 시작해 AI 임시 결정을 포함한 프로젝트를 실제 FastAPI + SQLite에 생성하고 다음을 확인합니다.

- 프로젝트 생성
- 기본 Documents 13개
- Requirements
- `accepted` Decision 존재
- `provisional` Decision 존재
- System Process Canvas
- Architecture Canvas
- Data Flow Canvas

CI에서는 Codex / Claude Code / OpenCode / Antigravity Provider Adapter와 두 E2E 시뮬레이터를 Windows와 Ubuntu에서 실행합니다.
