# Team Project OS V0.14 · 실무 산출물 설계 기준

Team Project OS의 문서 템플릿은 특정 회사 양식을 복사하지 않고, 공개된 국제 표준과 널리 쓰이는 실무 관행에서 **필요 정보의 종류·검증·추적 구조**를 가져옵니다.

## 참고 기준

- Requirements: ISO/IEC/IEEE 29148:2018 — Requirements engineering
  - https://www.iso.org/standard/72089.html
- Architecture Description: ISO/IEC/IEEE 42010:2022
  - https://www.iso.org/standard/74393.html
- Software Test Documentation: ISO/IEC/IEEE 29119-3:2021
  - https://www.iso.org/standard/79429.html
- Project Schedule / WBS: PMI Work Breakdown Structure / Scheduling guidance
  - https://www.pmi.org/standards/work-breakdown-structures-third-edition
  - https://www.pmi.org/learning/library/schedule-101-basic-best-practices-6701/
- Software Architecture Visualization: C4 Model
  - https://c4model.com/diagrams
- HTTP API Contract: OpenAPI Specification
  - https://spec.openapis.org/oas/latest.html
- Operational readiness / incident management: Google Cloud Well-Architected + Google SRE
  - https://docs.cloud.google.com/architecture/framework/operational-excellence
  - https://sre.google/resources/practices-and-processes/incident-management-guide/

## 13종 문서 역할

| 문서 | 실무 목적 | 핵심 필드 |
|---|---|---|
| 기획서 | 왜 하는지, 무엇을 성공으로 보는지 합의 | Executive Summary, Problem, Objectives/KPI, Stakeholder, Scope, Deliverable, Risk, Approval |
| 계획서 | 어떻게 수행하고 통제할지 정의 | Lifecycle, Deliverable-oriented WBS, RACI, Dependency, Risk, Quality, Change, Communication |
| 마일스톤 | 시간축 실행계획 | Phase/Task, Start/End Week, Owner, Status, Gate/Exit Criteria |
| 백로그 | 실행 단위 관리 | Epic/Feature, Value, Requirement, Priority, Estimate, Dependency, DoR/DoD, Milestone, Status |
| 요구사항 정의서 | 구현·검증 가능한 기준선 | ID, Type, Source/Rationale, Priority, Acceptance Criteria, Verification, Owner, Traceability |
| 서비스/운영 정책서 | 운영 책임과 장애/복구/변경 기준 | Role/Access, SLI/SLO, Monitoring, Incident, Backup/RPO/RTO, Retention, Release/Rollback |
| 기능 정의서 | Requirement를 시스템 동작으로 구체화 | Actor/Trigger, Preconditions, Input, Business Rules, Normal/Exception Flow, Output, Acceptance |
| IA | 메뉴·화면·정보 구조 | Navigation, Page Inventory, User Journey, Permission, Naming |
| 화면 설계서 | 화면 행동·상태 정의 | Screen ID, Components, Data/Action, Validation, Permission, Loading/Empty/Error State, API/Event |
| 시스템 구조도 | 시스템 경계·책임·관심사 설명 | Drivers/Concerns, Context, Containers/Components, Interfaces, Deployment, Quality Scenario, ADR/Risk |
| 데이터 플로우 | 데이터 생성·변환·저장·소비·보존 정의 | Source, Event/Data, Trigger, Validation/Transform, Destination, Protocol, Failure, Dictionary, Retention |
| API 설계 문서 | 구현 전 Interface Contract | Conventions, Endpoint, Schema, Error, Timeout/Retry, Idempotency, Version/Deprecation, Security |
| QA 문서 | 검증과 Release 판단 | Strategy, Environment, Test Case, Expected/Actual, Evidence, Defect, Traceability, Release Gate |

## 공통 품질 원칙

1. 문서 형식은 처음부터 완성된 실무 산출물의 구조를 유지합니다.
2. 확인되지 않은 사실을 그럴듯하게 꾸며내지 않고 `TBD · 확인 필요`로 표시합니다.
3. AI가 선택한 가역적 기본값은 `PROVISIONAL`로 구분합니다.
4. 비용/권한/개인정보/법규/실제 설비 제어는 Human Gate 없이는 확정하지 않습니다.
5. Requirement → Process/Architecture → Backlog/Task → Test/Evidence 추적성을 유지합니다.
6. 웹의 기본 화면은 읽기 좋은 산출물 뷰이며 Markdown은 편집/Export용 Source입니다.
7. Architecture Canvas는 Context/Boundary/Service/Data Store 책임을 읽기 쉽게 표현하고, Data Flow는 데이터 이름과 방향을 표현합니다.
8. 일정은 WBS/Dependency를 기반으로 하며 실제 시작일·인력이 정해지기 전 AI 일정은 PROVISIONAL입니다.

## V0.14의 플랫폼 기준

- Windows: `run_windows.bat`
- macOS: `bash run_mac.sh`
- Windows/macOS/Linux 공통: `python run_project_os.py` 또는 macOS/Linux에서는 `python3 run_project_os.py`
- Docker: `app.main_v014:app`

Design Session에서 여러 줄 복사/붙여넣기가 터미널 때문에 불편하면, 텍스트를 OS 클립보드에 복사하고 `/paste`를 입력합니다. Windows는 PowerShell `Get-Clipboard`, macOS는 `pbpaste`를 사용해 여러 줄을 한 번에 하나의 메시지로 읽습니다.
