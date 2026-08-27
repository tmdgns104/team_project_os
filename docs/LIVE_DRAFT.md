# Live Design Draft (V0.10)

AI와 프로젝트를 오래 설계할 때 `/apply`까지 웹이 기다리지 않도록 하는 실시간 Draft 기능입니다.

## 동작 원리

Design Session 시작 시 `lifecycle=draft` 프로젝트가 하나 생성됩니다. AI는 일반 대화 답변과 함께 숨은 `PROJECT_OS_DELTA`를 반환하고 CLI는 이 블록만 분리해 서버에 동기화합니다. 추가 Distiller 호출은 하지 않습니다.

의미 있는 결정이 생긴 턴마다 다음이 실시간으로 바뀔 수 있습니다.

- Project Brief / Goal
- Requirements
- `accepted` / `provisional` Decisions
- 기획서 / 계획서 / 요구사항 정의서
- 시스템 구조도 / 데이터 플로우 / 기능 정의서의 Live Draft 부분
- System Process / Architecture / Data Flow Canvas

서버는 동기화 후 WebSocket refresh를 보내므로 같은 Draft를 보고 있는 브라우저는 자동으로 최신 Snapshot을 다시 읽습니다.

## 승인 경계

Live Draft는 정식 프로젝트와 구분됩니다.

```text
lifecycle=draft
= 설계 중, 자동 갱신 가능

/apply
= 전체 대화를 마지막으로 Distill
= 같은 프로젝트를 lifecycle=active로 승격
```

따라서 실시간 시각화와 Human Gate를 동시에 유지합니다.

## 명령

```text
/status      Live Draft ID와 Autofill 상태 확인
/preview     전체 대화 기반 최종 구조 미리보기
/apply       Live Draft를 정식 프로젝트로 승격
/discard     현재 Live Draft 삭제
/quit        세션 저장 후 종료 (Draft는 유지)
```

실시간 동기화를 끄려면:

```bat
python project_os.py design --provider codex --no-live
```

## 성능 원칙

매 턴 별도 Distiller를 호출하지 않습니다. 기존 AI 응답 한 번에 conversational answer와 compact delta를 같이 받아 네트워크 동기화만 추가합니다.

## 검증

```bat
python tools\simulate_live_design.py
```

시뮬레이터는 두 번의 설계 턴을 서버에 순차 반영하고 문서/요구사항/Decision/Canvas가 중간 상태에서 실제로 바뀌는지 확인한 뒤 `/apply`에 해당하는 Draft 승격까지 검증합니다.
