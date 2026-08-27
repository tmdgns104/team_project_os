# Team Project OS 프로젝트 시작 흐름

새 프로젝트는 **목표 → 공동 문서 → 설계 → 개발 → QA** 순으로 발전시키되, 실제 프로젝트 상황에 따라 문서를 병렬로 작성할 수 있습니다.

## 자동 생성되는 13종 공동 문서

1. 기획서
2. 계획서
3. 마일스톤
4. 백로그
5. 요구사항 정의서
6. 서비스 및 운영 정책서
7. 기능 정의서
8. IA (Information Architecture, 정보구조도)
9. 화면 설계서
10. 시스템 구조도
11. 데이터 플로우
12. API 설계 문서
13. QA 문서

문서는 Team Project OS 서버 DB에 저장되며 다른 팀원과 같은 내용을 봅니다. 저장할 때 이전 본문은 revision으로 남고, 문서별 Discussion 댓글도 공유됩니다.

## 권장 Traceability

```text
기획서
  ↓
요구사항 정의서 (REQ)
  ↓
기능 정의서 (FUNC)
  ↓
IA / 화면 설계 (SCREEN)
  ↓
시스템 구조 / Data Flow / API
  ↓
Backlog / Task
  ↓
QA / Evidence
```

V0.2에서는 공동 문서와 기존 Requirement/Task/Design Canvas가 함께 존재합니다. 다음 단계에서는 문서 안의 REQ/FUNC/SCREEN/API/TC ID를 Project Graph 노드와 직접 연결합니다.
