# Professional Deliverables (V0.11)

Team Project OS의 Documents는 단순 메모나 Markdown 뷰어가 아니라 **실제 프로젝트 산출물 기준**으로 관리합니다.

## 기본 원칙

- Markdown은 Source Format으로 유지합니다.
- 웹 기본 화면은 읽기 좋은 보고서 형식으로 렌더링합니다.
- 정보가 없으면 임의로 꾸며내지 않고 `TBD / 확인 필요`로 표시합니다.
- 사람이 승인한 내용과 AI 임시 결정(`provisional`)을 구분합니다.
- Requirement → Design → Task → QA/Evidence 추적성을 유지합니다.
- `/apply` 전 Live Draft는 정식 승인본이 아닙니다.

## 웹 문서 화면

기본 `문서 보기` 모드에서는 다음을 제공합니다.

- 프로젝트명 / 문서명 중심의 표지형 Header
- 문서 상태, 작성자, 마지막 수정일, Lifecycle 메타데이터
- 자동 목차
- H1/H2/H3 제목 계층
- 실무형 Table 렌더링
- 체크리스트
- Callout / Note
- Code Block
- 문서 품질 상태 표시
- Review / Discussion
- 브라우저 인쇄 / PDF 레이아웃

`Markdown 편집` 모드에서는 기존 원본을 직접 수정할 수 있습니다.

## 13종 산출물 품질 기준

### 1. 기획서

- Executive Summary
- 추진 배경 / 문제 정의
- 목표 / KPI
- 이해관계자
- In Scope / Out of Scope
- AS-IS / TO-BE
- 산출물
- 제약 / 전제조건
- 리스크
- 승인 기준

### 2. 프로젝트 계획서

- 추진 전략
- 범위 / 산출물
- 일정 / Milestone
- WBS
- R&R
- 의존성 / 제약
- Risk Register
- 품질 / 검증 계획
- 변경관리
- 보고 / 커뮤니케이션

### 3. 마일스톤

각 Milestone은 최소 다음 필드를 가집니다.

- ID
- 목표
- 주요 산출물
- Entry Criteria
- Exit Criteria
- 목표일
- Owner
- 상태

### 4. 백로그

- ID
- Epic / Feature
- 작업 항목
- Priority
- Owner
- Status
- Requirement Link
- Definition of Done

### 5. 요구사항 정의서

- Requirement ID
- Type
- Requirement
- Detail
- Priority
- Acceptance Criteria
- Verification Method
- Status
- Traceability Matrix

### 6. 서비스 및 운영 정책서

- 적용 범위
- 사용자 / 역할 / 권한
- 데이터 수집 / 보관 / 삭제
- 장애 / 복구
- 로그 / 감사
- 배포 / 변경 / Rollback
- 보안 / 개인정보 / 규제 Open Items

### 7. 기능 정의서

- Function ID
- 기능명
- Actor / Trigger
- Input
- 정상 처리
- Output
- Error / Exception
- Acceptance Criteria
- 관련 Requirement

### 8. IA

- Navigation Model
- Depth
- 메뉴 / 화면
- 목적
- 사용자
- 연결 화면
- 권한
- 주요 User Flow

### 9. 화면 설계서

- Screen ID
- 목적
- 사용자
- 진입 조건
- 성공 / 종료 조건
- Component 목록
- 표시 데이터
- 사용자 동작
- Validation
- Error / Empty State
- 연결 기능 / API

### 10. 시스템 구조도

- System Context
- Component Responsibility
- Technology
- Interface
- Dependency
- Deployment / Runtime
- Availability / Security 고려사항

### 11. 데이터 플로우

- Flow ID
- Source
- Data
- Trigger / Frequency
- Processing
- Destination
- Protocol / Format
- Validation
- Failure Handling
- Data Ownership / Retention

### 12. API 설계 문서

- API Convention
- Versioning
- Auth
- Method / Path
- Request
- Success Response
- Error Model
- Idempotency / Timeout / Retry
- 관련 Requirement

### 13. QA 문서

- Test Strategy
- Test Level
- Environment
- Entry / Exit Criteria
- TC ID
- Requirement Link
- Preconditions
- Steps
- Expected / Actual Result
- Status
- Evidence
- Defect Summary
- Release / Acceptance Gate

## 기존 V0.10 데이터 마이그레이션

V0.11 시작 시 아직 `updated_by=System`, `status=draft`인 기본 문서만 최신 실무 템플릿으로 교체합니다.

다음 문서는 자동으로 덮어쓰지 않습니다.

- Live Design이 이미 수정한 문서
- Project Setup이 작성한 문서
- AI Conversation이 작성한 문서
- 사람이 직접 수정한 문서

따라서 기존 프로젝트 작업을 보존하면서 아직 손대지 않은 구형 템플릿만 개선합니다.
