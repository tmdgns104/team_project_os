# V0.12 Design Diagram Standards

Team Project OS의 `System Process`, `Architecture`, `Data Flow`는 같은 노드 그래프를 단순 격자로 그리지 않습니다. 각 화면의 목적에 맞게 사람이 읽는 순서와 계층을 우선합니다.

## System Process

목적: 시스템/업무의 실행 순서와 분기를 빠르게 이해합니다.

- 왼쪽 → 오른쪽 순서
- `STEP 1`, `STEP 2` 같은 단계 레이어
- Event / Process / Decision / UI를 시각적으로 구분
- Decision은 별도 다이아몬드 형태
- 분기 연결 라벨을 의미 있게 표시

예시:

```text
제품/PLC 상태 감지
        ↓
PLC 데이터 수집
        ↓
상태 판정
     ↙      ↘
실적 저장   HMI 경고
     └──────→ HMI KPI
```

## Architecture

목적: 시스템을 구성하는 장치·서비스·데이터 저장소·UI와 책임 경계를 이해합니다.

권장 흐름:

```text
EDGE / INPUT
    ↓
APPLICATION / SERVICE
    ↓
DATA / STORAGE 또는 OUTPUT / UI
```

Node detail에는 기술 이름 자체보다 해당 컴포넌트의 책임을 우선 기록합니다.

## Data Flow

목적: 데이터 생성 → 변환/검증 → 처리 → 저장/소비 흐름을 이해합니다.

권장 흐름:

```text
SOURCE → PROCESSING → STORE / CONSUMER
```

연결선 라벨에는 가능한 경우 실제 이동 데이터나 형식을 적습니다.

예:

- `raw PLC tags`
- `validated event`
- `production record`
- `REST / WebSocket`
- `KPI query`

## Layout 규칙

V0.12 Layout Engine은 다음을 자동 처리합니다.

1. Edge 연결관계로 Topological Rank 계산
2. 순환 구조가 있어도 주변 Rank를 이용해 안전한 fallback 배치
3. Rank별 노드 배치
4. Barycentric ordering으로 연결선 교차 감소
5. 노드 겹침 방지
6. 연결선은 노드 중심이 아니라 경계 포트에서 시작/종료
7. 같은 Rank 또는 역방향 연결은 노드 아래 별도 Lane으로 우회
8. 긴 AI 라벨은 최대 두 줄 + 말줄임
9. Edge Label은 흰색 Capsule 배경으로 가독성 확보

## 검증

```bat
node tests\test_diagram_layout.js
python tools\simulate_project_creation_v012.py
```

`test_diagram_layout.js`는 다음을 확인합니다.

- Node overlap 없음
- 모든 Edge의 Source/Target 존재
- Forward Edge가 Source 오른쪽 경계에서 출발하고 Target 왼쪽 경계로 진입
- SVG 좌표에 `NaN` / `undefined` 없음
- Node/Edge Label이 실제 SVG에 렌더링됨
- AI 입력 Label HTML escape

`simulate_project_creation_v012.py`는 실제 FastAPI + SQLite 임시 DB에서 다음 전체 흐름을 검증합니다.

```text
AI Design Draft 생성
→ Project Brief 구체화
→ Requirements / Decisions 생성
→ 13종 Professional Documents 생성
→ System Process 생성
→ Architecture 생성
→ Data Flow 생성
→ Edge integrity 확인
→ /apply 상당 Promote
→ active 프로젝트에서 문서/디자인 유지 확인
```

이 검증은 Windows와 Ubuntu CI에서 함께 실행합니다.
