# AI Design Session - Provisional Autofill Mode

Team Project OS의 AI Design Session은 사용자가 세부 구현 방안을 모르더라도 프로젝트를 시작할 수 있도록 **Provisional Autofill Mode**를 지원합니다.

## 시작

```bat
python project_os.py design --provider codex --member "승훈"
```

처음부터 Autofill을 켜려면:

```bat
python project_os.py design --provider codex --member "승훈" --autofill
```

대화 중 자연어로 아래처럼 말해도 자동으로 켜집니다.

```text
세부적인 건 잘 모르겠으니까 적당한 걸로 알아서 임시로 다 정해줘
DB나 화면 구성은 네가 정해
```

또는 명령으로 직접 전환할 수 있습니다.

```text
/autofill on
/autofill off
```

## 결정 구분

- `accepted`: 사용자가 직접 정하거나 명시적으로 승인한 결정
- `provisional`: AI가 실행 가능한 V1을 만들기 위해 대신 선택한 되돌릴 수 있는 임시 결정
- `pending`: AI가 임의로 결정하면 안 되거나 정보가 부족한 항목

Autofill 예시:

- SQLite / FastAPI 같은 초기 기술 선택
- Web HMI 기본 화면 구성
- Simulator-first 개발 순서
- 로컬 V1 배포 방식
- 기본 Module/Folder 구조

사람 확인을 유지하는 예시:

- 실제 비용 지출/장비 구매
- Secret, 계정, 권한 확대
- 개인정보/법률/규제 정책
- 계약 또는 외부 운영 의무
- 실제 생산라인의 파괴적 변경
- 안전 임계값

## Preview / Apply

```text
/preview
```

현재 대화를 전체 분석하지만 프로젝트는 생성하지 않습니다. 사람 확정 Decision과 AI 임시 Decision을 따로 표시합니다.

```text
/apply
```

전체 대화를 Project Distiller가 한 번 구조화한 뒤 Project Brief, Requirements, Decisions, Documents, System Process, Architecture, Data Flow를 Project OS에 생성합니다. `provisional` 상태는 그대로 저장되어 나중에 실제 결정으로 교체할 수 있습니다.

## 검증

CI는 Windows와 Ubuntu에서 다음을 검증합니다.

1. 자연어 Autofill 위임 감지
2. AI 임시 결정이 `provisional`로 구분되는지
3. 사람 확정과 AI 임시 결정이 Preview에서 분리되는지
4. Codex/Claude/OpenCode/Antigravity Provider Adapter 회귀 테스트
5. HMI/MES Autofill 시나리오의 실제 FastAPI + SQLite 프로젝트 생성
6. 13개 문서, Requirements, Decisions, Process/Architecture/Data Flow Canvas 생성
