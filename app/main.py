from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
import secrets
import sqlite3
from time import perf_counter
import zipfile
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.project_intake import build_initial_documents, evaluate_intake, intake_metadata
from app.conversation import PROJECT_FIELDS, build_interviewer_prompt, combine_proposals, merge_project_brief, normalize_ai_result
from app.runtime import load_runtime_settings

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS = load_runtime_settings()
DB_PATH = Path(os.getenv("PROJECT_OS_DB", BASE_DIR / "project_os.db"))
ACCESS_KEY = SETTINGS.access_key
SEED_DEMO = SETTINGS.seed_demo
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOGGER = logging.getLogger("project_os")


@asynccontextmanager
async def application_lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Team Project OS",
    version="0.13.0",
    docs_url="/docs" if SETTINGS.interactive_docs_enabled else None,
    redoc_url="/redoc" if SETTINGS.interactive_docs_enabled else None,
    openapi_url="/openapi.json" if SETTINGS.interactive_docs_enabled else None,
    lifespan=application_lifespan,
)
if SETTINGS.production:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(SETTINGS.allowed_hosts))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _apply_defensive_headers(response: Response, *, api_response: bool) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self' ws: wss:; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'",
    )
    if api_response:
        response.headers.setdefault("Cache-Control", "no-store")


@app.middleware("http")
async def operational_safety_middleware(request: Request, call_next):
    """Apply small, explicit controls that are useful with or without a proxy."""

    started = perf_counter()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = -1
        if declared_size < 0:
            response = JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        elif declared_size > SETTINGS.max_request_bytes:
            response = JSONResponse({"detail": "Request body too large"}, status_code=413)
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)

    _apply_defensive_headers(
        response, api_response=request.url.path.startswith("/api/")
    )
    response.headers.setdefault("X-Request-Duration-Ms", f"{(perf_counter() - started) * 1000:.1f}")
    LOGGER.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started) * 1000,
    )
    return response

DOCUMENT_TEMPLATES = [
    ("proposal", "기획서", "# 기획서\n\n> 프로젝트 추진 배경·목표·범위·KPI를 합의하는 기준 문서\n\n## Executive Summary\n\n## 1. 추진 배경 및 문제 정의\n\n## 2. 프로젝트 목표 / KPI\n\n## 3. 이해관계자\n\n## 4. In Scope / Out of Scope\n\n## 5. AS-IS / TO-BE\n\n## 6. 산출물\n\n## 7. 제약사항 / 전제조건\n\n## 8. 리스크\n\n## 9. 승인 기준\n"),
    ("plan", "계획서", "# 프로젝트 계획서\n\n> 실행 일정·WBS·R&R·리스크·변경관리 기준\n\n## 1. 추진 전략\n\n## 2. 범위 / 산출물\n\n## 3. 일정 / 마일스톤\n\n## 4. Work Breakdown Structure\n\n## 5. 역할과 책임 (R&R)\n\n## 6. 제약사항 / 의존성\n\n## 7. 리스크 관리\n\n## 8. 품질 / 검증 계획\n\n## 9. 변경관리\n"),
    ("milestone", "마일스톤", "# 개발 마일스톤 / Gantt\n\n> **기준 시작일** · TBD · 실제 날짜가 정해지기 전에는 상대 주차 기준 초안\n\n## Gantt Schedule\n\n| Phase | ID | Task | Start Week | End Week | Owner | Status |\n|---|---|---|---|---|---|---|\n| A. 정의 및 설계 | MS-001 | 프로젝트 착수 / 목표·범위 정리 | 1 | 1 | TBD | Draft |\n| A. 정의 및 설계 | MS-002 | 요구사항 분석 및 정의 | 1 | 2 | TBD | Draft |\n| A. 정의 및 설계 | MS-003 | Process / Architecture / Data Flow 설계 | 2 | 4 | TBD | Draft |\n| A. 정의 및 설계 | MS-004 | UI/IA 및 인터페이스 기준선 | 3 | 4 | TBD | Draft |\n| B. 구현 | MS-005 | 개발환경 / 기반 구조 준비 | 4 | 5 | TBD | Todo |\n| B. 구현 | MS-006 | 핵심 기능 구현 | 5 | 9 | TBD | Todo |\n| B. 구현 | MS-007 | 데이터 저장 / 연동 구현 | 6 | 9 | TBD | Todo |\n| B. 구현 | MS-008 | UI / 사용자 기능 구현 | 7 | 10 | TBD | Todo |\n| B. 구현 | MS-009 | 모듈 통합 | 9 | 11 | TBD | Todo |\n| C. 통합 및 검증 | MS-010 | 통합 테스트 | 11 | 13 | TBD | Todo |\n| C. 통합 및 검증 | MS-011 | 시스템 / 비기능 검증 | 12 | 14 | TBD | Todo |\n| C. 통합 및 검증 | MS-012 | 결함 수정 / 안정화 | 13 | 15 | TBD | Todo |\n| D. 완료 | MS-013 | 인수 기준 확인 | 15 | 15 | TBD | Todo |\n| D. 완료 | MS-014 | 문서 / 운영 가이드 정리 | 15 | 16 | TBD | Todo |\n| D. 완료 | MS-015 | 최종 릴리스 / 인수 | 16 | 16 | TBD | Todo |\n\n> 이 일정은 프로젝트 유형·실제 시작일·인력·제약이 정해지면 Live Design에서 갱신합니다.\n"),
    ("backlog", "백로그", "# Product / Project Backlog\n\n| ID | Epic/Feature | 작업 항목 | Priority | Owner | Status | Requirement | Definition of Done |\n|---|---|---|---|---|---|---|---|\n| BL-001 | Definition | 핵심 요구사항 상세화 | High | TBD | Todo | REQ-* | Review 완료 |\n"),
    ("requirements", "요구사항 정의서", "# 요구사항 정의서\n\n> 구현·검증 가능한 Requirement 기준선\n\n## 1. 작성 원칙\n\n## 2. Functional Requirements\n\n| ID | Type | 요구사항 | 상세 | Priority | Acceptance Criteria | Verification | 상태 |\n|---|---|---|---|---|---|---|---|\n| REQ-001 | Functional | TBD | TBD | High | TBD | Test/Review | Draft |\n\n## 3. Non-Functional Requirements\n\n## 4. Traceability Matrix\n"),
    ("service_policy", "서비스 및 운영 정책서", "# 서비스 및 운영 정책서\n\n> 실제 운영 시 일관된 의사결정을 위한 정책 기준\n\n## 1. 목적 / 적용 범위\n\n## 2. 사용자 / 역할 / 권한 정책\n\n| Role | 허용 기능 | 제한 | 승인자 |\n|---|---|---|---|\n| TBD | TBD | TBD | TBD |\n\n## 3. 데이터 수집 / 보관 / 삭제 정책\n\n## 4. 장애 / 예외 / 복구 정책\n\n## 5. 로그 / 감사 / 모니터링 정책\n\n## 6. 배포 / 변경 / Rollback 정책\n\n## 7. 보안 / 개인정보 / 규제 Open Items\n"),
    ("function_definition", "기능 정의서", "# 기능 정의서\n\n> 사용자/시스템 기능의 입력·처리·출력·예외·검증 기준\n\n| 기능 ID | 기능명 | Actor/Trigger | 입력 | 정상 처리 | 출력 | 예외/오류 | Acceptance Criteria | 관련 REQ |\n|---|---|---|---|---|---|---|---|---|\n| FUNC-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |\n"),
    ("ia", "IA (Information Architecture, 정보구조도)", "# IA (Information Architecture)\n\n> 메뉴·화면·정보 구조와 이동 관계 정의\n\n## 1. Navigation Model\n\n```text\nRoot\n└─ TBD\n```\n\n## 2. 화면/메뉴 목록\n\n| IA ID | Depth | 메뉴/화면 | 목적 | 주요 사용자 | 연결 화면 | 권한 |\n|---|---|---|---|---|---|---|\n| IA-001 | 1 | TBD | TBD | TBD | TBD | TBD |\n\n## 3. 주요 사용자 Flow\n"),
    ("screen_design", "화면 설계서", "# 화면 설계서\n\n> 화면 목적·상태·사용자 동작·데이터·Validation 정의\n\n## SCREEN-001 · TBD\n\n| 항목 | 내용 |\n|---|---|\n| 목적 | TBD |\n| 대상 사용자 | TBD |\n| 진입 조건 | TBD |\n| 종료/성공 조건 | TBD |\n\n### 주요 컴포넌트\n\n| Component ID | UI 요소 | 표시 데이터 | 사용자 동작 | Validation | Error/Empty State |\n|---|---|---|---|---|---|\n| UI-001 | TBD | TBD | TBD | TBD | TBD |\n\n### 연결 기능 / API\n"),
    ("system_architecture", "시스템 구조도", "# 시스템 구조도\n\n> 시스템 경계·컴포넌트 책임·인터페이스·배포 구조 정의\n\n## 1. System Context\n\n## 2. Component Responsibilities\n\n| Component | Responsibility | Technology | Interface | Dependency | Owner |\n|---|---|---|---|---|---|\n| TBD | TBD | TBD | TBD | TBD | TBD |\n\n## 3. Interface / Integration\n\n## 4. Deployment / Runtime\n\n## 5. Availability / Security Considerations\n\n> Design > Architecture Canvas와 함께 관리합니다.\n"),
    ("data_flow", "데이터 플로우", "# 데이터 플로우\n\n> 데이터 생성·변환·저장·소비와 책임 경계 정의\n\n| Flow ID | Source | Data | Trigger/Frequency | Processing | Destination | Protocol/Format | Validation | Failure Handling |\n|---|---|---|---|---|---|---|---|---|\n| DF-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |\n\n## Data Ownership / Retention\n\n> Design > Data Flow Canvas와 함께 관리합니다.\n"),
    ("api_design", "API 설계 문서", "# API 설계 문서\n\n> 시스템 간 Contract와 오류/보안/호환성 기준 정의\n\n## 1. API Conventions\n- Base URL / Versioning: TBD\n- Authentication / Authorization: TBD\n- Content-Type: application/json (해당 시)\n\n## 2. Endpoint Catalog\n\n| API ID | Method | Path | 목적 | Auth | Request | Success Response | Error | 관련 REQ |\n|---|---|---|---|---|---|---|---|---|\n| API-001 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | REQ-* |\n\n## 3. Error Model\n\n## 4. Idempotency / Timeout / Retry\n"),
    ("qa", "QA 문서", "# QA / Test Plan & Result\n\n> Requirement 기반 검증 전략·Test Case·Evidence 관리\n\n## 1. Test Strategy\n\n| Test Level | Scope | Environment | Entry Criteria | Exit Criteria |\n|---|---|---|---|---|\n| Functional | 핵심 Requirement | TBD | 기능 구현 완료 | Critical TC PASS |\n\n## 2. Test Cases\n\n| TC ID | Requirement | Priority | Preconditions | Test Steps | Expected Result | Actual Result | Status | Evidence |\n|---|---|---|---|---|---|---|---|---|\n| TC-001 | REQ-001 | High | TBD | TBD | TBD | - | Not Run | TBD |\n\n## 3. Defect / Issue Summary\n\n## 4. Release / Acceptance Gate\n- Critical/Blocker 미해결 0건\n- 핵심 Requirement 검증 Evidence 확보\n"),
]




@contextmanager
def db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=SETTINGS.sqlite_busy_timeout_ms / 1000,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {SETTINGS.sqlite_busy_timeout_ms}")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_access(x_access_key: str | None = Header(default=None)) -> None:
    if ACCESS_KEY and (
        not x_access_key or not secrets.compare_digest(x_access_key, ACCESS_KEY)
    ):
        raise HTTPException(status_code=401, detail="Invalid access key")


def bridge_bearer_token(
    authorization: str | None,
    legacy_query_token: str | None,
) -> str:
    """Prefer a bearer header while retaining the V0.14 query-token contract."""

    if authorization:
        scheme, separator, credential = authorization.partition(" ")
        if separator and scheme.lower() == "bearer" and credential.strip():
            return credential.strip()
    if legacy_query_token:
        return legacy_query_token
    raise HTTPException(status_code=401, detail="Missing bridge token")


def rowdict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    goal: str = Field(min_length=2, max_length=1000)
    project_type: str = Field(default="generic", max_length=80)
    problem: str = Field(default="", max_length=4000)
    users: str = Field(default="", max_length=3000)
    deliverables: str = Field(default="", max_length=4000)
    success_criteria: str = Field(default="", max_length=4000)
    scope: str = Field(default="", max_length=4000)
    current_state: str = Field(default="", max_length=4000)
    target_state: str = Field(default="", max_length=4000)
    constraints: str = Field(default="", max_length=4000)
    schedule: str = Field(default="", max_length=3000)
    team: str = Field(default="", max_length=3000)
    risks: str = Field(default="", max_length=4000)
    description: str = Field(default="", max_length=4000)


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    status: str = "todo"
    owner: str = "Unassigned"
    priority: str = "medium"
    requirement_ref: str = ""


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    owner: str | None = None
    priority: str | None = None
    requirement_ref: str | None = None


class NodeCreate(BaseModel):
    view: str
    label: str
    kind: str = "component"
    detail: str = ""
    x: float = 0
    y: float = 0


class EdgeCreate(BaseModel):
    view: str
    source_id: int
    target_id: int
    label: str = ""


class IdeaCreate(BaseModel):
    title: str
    body: str = ""
    author: str = "Team member"
    status: str = "open"


class DecisionCreate(BaseModel):
    title: str
    body: str = ""
    author: str = "Team"
    status: str = "accepted"


class MemberCreate(BaseModel):
    name: str
    role: str = "Developer"
    ai_provider: str = "none"


class BridgeRegister(BaseModel):
    member_name: str
    provider: str
    machine_name: str = "local"


class AIJobCreate(BaseModel):
    task_id: int
    provider: str
    member_name: str
    repo_hint: str = ""
    instruction: str = ""


class AIResult(BaseModel):
    job_id: int
    status: str
    output: str = ""
    evidence: str = ""


class GoalPatch(BaseModel):
    goal: str
    description: str = ""


class RequirementCreate(BaseModel):
    title: str
    detail: str = ""
    status: str = "defined"


class RequirementPatch(BaseModel):
    title: str | None = None
    detail: str | None = None
    status: str | None = None


class DocumentPatch(BaseModel):
    content: str = Field(default="", max_length=200000)
    status: str = "draft"
    updated_by: str = Field(default="Team member", max_length=120)


class DocumentCommentCreate(BaseModel):
    author: str = Field(default="Team member", max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class TraceLinkCreate(BaseModel):
    source_type: str = Field(min_length=2, max_length=60)
    source_ref: str = Field(min_length=1, max_length=160)
    target_type: str = Field(min_length=2, max_length=60)
    target_ref: str = Field(min_length=1, max_length=160)
    relation: str = Field(default="relates_to", max_length=80)
    note: str = Field(default="", max_length=2000)
    created_by: str = Field(default="Team member", max_length=120)


class AssistantBridgeRegister(BaseModel):
    member_name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=2, max_length=40)
    machine_name: str = Field(default="local", max_length=160)


class ConversationStart(BaseModel):
    member_name: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=2, max_length=40)
    project_id: int | None = None


class ConversationMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=12000)


class ConversationBridgeResult(BaseModel):
    job_id: int
    status: str
    output: str = Field(default="", max_length=250000)


class ConversationApply(BaseModel):
    apply_project: bool = True
    apply_requirements: bool = True
    apply_decisions: bool = True
    apply_documents: bool = True


class DesignDraftCreate(BaseModel):
    member_name: str = Field(default="CMD User", max_length=120)
    provider: str = Field(default="codex", max_length=40)
    name_hint: str = Field(default="AI Design Draft", max_length=120)


class DesignDraftSync(BaseModel):
    member_name: str = Field(default="CMD User", max_length=120)
    state: dict[str, Any] = Field(default_factory=dict)


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(
        self,
        project_id: int,
        websocket: WebSocket,
        subprotocol: str | None = None,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self.connections.setdefault(project_id, set()).add(websocket)

    def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        self.connections.get(project_id, set()).discard(websocket)

    async def broadcast(self, project_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self.connections.get(project_id, set()):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


manager = ConnectionManager()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                lifecycle TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'defined',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                owner TEXT NOT NULL DEFAULT 'Unassigned',
                priority TEXT NOT NULL DEFAULT 'medium',
                requirement_ref TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                view TEXT NOT NULL,
                label TEXT NOT NULL,
                kind TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                x REAL NOT NULL DEFAULT 0,
                y REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                view TEXT NOT NULL,
                source_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                target_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
                label TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                ai_provider TEXT NOT NULL DEFAULT 'none',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'System',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bridges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                member_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                machine_name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                member_name TEXT NOT NULL,
                repo_hint TEXT NOT NULL DEFAULT '',
                instruction TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                bridge_id INTEGER REFERENCES bridges(id),
                output TEXT NOT NULL DEFAULT '',
                evidence TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                updated_by TEXT NOT NULL DEFAULT 'System',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, doc_type)
            );
            CREATE TABLE IF NOT EXISTS document_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                status TEXT NOT NULL,
                editor TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trace_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                relation TEXT NOT NULL DEFAULT 'relates_to',
                note TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT 'Team member',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_briefs (
                project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                data_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assistant_bridges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                machine_name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                last_seen TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                member_name TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                pending_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                member_name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                bridge_id INTEGER REFERENCES assistant_bridges(id),
                output TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        if "lifecycle" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active'")
        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        if count == 0 and SEED_DEMO:
            seed_demo(conn)
        for project_row in conn.execute("SELECT id FROM projects"):
            ensure_project_documents(conn, project_row["id"])
            ensure_project_brief(conn, project_row["id"])


def ensure_project_documents(conn: sqlite3.Connection, project_id: int) -> None:
    """Ensure all shared deliverables exist and safely refresh untouched System templates.

    A document already touched by Live Design, Project Setup, AI Conversation, or a human
    is never overwritten here. This lets old V0.10 databases receive the professional
    V0.11 baseline for still-untouched documents without losing project work.
    """
    for doc_type, title, content in DOCUMENT_TEMPLATES:
        row = conn.execute(
            "SELECT id,status,updated_by,content FROM documents WHERE project_id=? AND doc_type=?",
            (project_id, doc_type),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (project_id, doc_type, title, content, "draft", "System", now(), now()),
            )
            continue
        if row["status"] == "draft" and row["updated_by"] == "System" and row["content"] != content:
            conn.execute(
                "UPDATE documents SET title=?,content=?,updated_at=? WHERE id=?",
                (title, content, now(), row["id"]),
            )


def ensure_project_brief(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT data_json FROM project_briefs WHERE project_id=?", (project_id,)).fetchone()
    if row:
        try:
            return json.loads(row["data_json"])
        except json.JSONDecodeError:
            pass
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise ValueError("Project not found")
    brief = {
        "name": project["name"],
        "goal": project["goal"],
        "project_type": "generic",
        "problem": "",
        "users": "",
        "deliverables": "",
        "success_criteria": "",
        "scope": "",
        "current_state": "",
        "target_state": "",
        "constraints": "",
        "schedule": "",
        "team": "",
        "risks": "",
        "description": project["description"],
    }
    conn.execute(
        "INSERT OR REPLACE INTO project_briefs(project_id,data_json,updated_at) VALUES(?,?,?)",
        (project_id, json.dumps(brief, ensure_ascii=False), now()),
    )
    return brief


def save_project_brief(conn: sqlite3.Connection, project_id: int, brief: dict[str, Any]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO project_briefs(project_id,data_json,updated_at) VALUES(?,?,?)",
        (project_id, json.dumps(brief, ensure_ascii=False), now()),
    )


def conversation_snapshot(conn: sqlite3.Connection, project_id: int) -> dict[str, Any] | None:
    session = conn.execute(
        "SELECT * FROM conversation_sessions WHERE project_id=? ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if not session:
        return None
    messages = [dict(r) for r in conn.execute(
        "SELECT * FROM conversation_messages WHERE session_id=? ORDER BY id",
        (session["id"],),
    )]
    jobs = [dict(r) for r in conn.execute(
        "SELECT id,session_id,provider,member_name,status,created_at,updated_at FROM conversation_jobs WHERE session_id=? ORDER BY id DESC LIMIT 10",
        (session["id"],),
    )]
    try:
        pending = json.loads(session["pending_json"] or "{}")
    except json.JSONDecodeError:
        pending = {}
    bridge = conn.execute(
        "SELECT id,member_name,provider,machine_name,last_seen FROM assistant_bridges WHERE member_name=? AND provider=? ORDER BY id DESC LIMIT 1",
        (session["member_name"], session["provider"]),
    ).fetchone()
    brief = ensure_project_brief(conn, project_id)
    return {
        "session": dict(session),
        "messages": messages,
        "jobs": jobs,
        "pending": pending,
        "bridge": dict(bridge) if bridge else None,
        "quality": evaluate_intake(brief),
    }


def conversation_live_draft_snapshot(
    conn: sqlite3.Connection, project_id: int
) -> dict[str, Any] | None:
    """V0.16 extension point; older entry points have no overlay."""

    return None


def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
    data = payload.model_dump()
    save_project_brief(conn, project_id, data)
    generated = build_initial_documents(data)
    for doc_type, content in generated.items():
        conn.execute(
            "UPDATE documents SET content=?,updated_by='Project Setup',updated_at=? WHERE project_id=? AND doc_type=?",
            (content, now(), project_id, doc_type),
        )


def _live_graph_markdown(title: str, design: dict[str, Any] | None) -> str:
    lines = [f"# {title}", "", "> AI Design Session Live Draft. `/apply` 전까지 정식 확정본이 아닙니다.", ""]
    if not design:
        lines.append("아직 대화에서 구조가 정리되지 않았습니다.")
        return "\n".join(lines) + "\n"
    nodes = design.get("nodes", []) or []
    edges = design.get("edges", []) or []
    if nodes:
        lines.extend(["## 구성", ""])
        for node in nodes:
            detail = str(node.get("detail") or "").strip()
            suffix = f" — {detail}" if detail else ""
            lines.append(f"- **{node.get('label', '')}** ({node.get('kind', 'component')}){suffix}")
    if edges:
        lines.extend(["", "## 연결", ""])
        labels = {str(n.get("key")): str(n.get("label")) for n in nodes}
        for edge in edges:
            src = labels.get(str(edge.get("source")), str(edge.get("source") or ""))
            dst = labels.get(str(edge.get("target")), str(edge.get("target") or ""))
            label = str(edge.get("label") or "").strip()
            middle = f" --{label}--> " if label else " --> "
            lines.append(f"- {src}{middle}{dst}")
    return "\n".join(lines) + "\n"


def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    """Build Live Draft documents without degrading the professional V0.11 schema.

    Live Design may fill data progressively, but it must not replace delivery-grade
    document structures with simplified scratch tables.
    """
    generated = build_initial_documents(brief)
    templates = {doc_type: content for doc_type, _title, content in DOCUMENT_TEMPLATES}
    requirements = state.get("requirements", []) or []
    decisions = state.get("decisions", []) or []
    pending_items = state.get("pending", []) or []

    if requirements:
        lines = [
            "# 요구사항 정의서", "",
            "> AI Design Session Live Draft · 구현/검증 가능한 Requirement 기준선", "",
            "## 1. 작성 원칙", "",
            "- 각 요구사항은 고유 ID로 관리하고 구현/검증 가능하게 작성합니다.",
            "- Acceptance Criteria와 Verification이 확정되지 않은 항목은 TBD로 유지합니다.", "",
            "## 2. Functional Requirements", "",
            "| ID | Type | 요구사항 | 상세 | Priority | Acceptance Criteria | Verification | 상태 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for item in requirements:
            ref = str(item.get("ref") or "").replace("|", "/")
            title = str(item.get("title") or "").replace("|", "/")
            detail = str(item.get("detail") or "").replace("|", "/")
            priority = str(item.get("priority") or "TBD").replace("|", "/")
            acceptance = str(item.get("acceptance_criteria") or "TBD · 확인 필요").replace("|", "/")
            verification = str(item.get("verification") or "Test / Review").replace("|", "/")
            status = str(item.get("status") or "defined").replace("|", "/")
            req_type = str(item.get("type") or "Functional").replace("|", "/")
            lines.append(f"| {ref} | {req_type} | {title} | {detail} | {priority} | {acceptance} | {verification} | {status} |")
        lines.extend([
            "", "## 3. Non-Functional Requirements", "",
            "TBD · 성능, 보안, 가용성, 운영성 등 비기능 요구사항을 Design Session에서 구체화합니다.", "",
            "## 4. Traceability Matrix", "",
            "Requirement → Process/Component → Task → QA/Test 연결은 Traceability 화면에서 관리합니다.", "",
        ])
        generated["requirements"] = "\n".join(lines)

    if decisions or pending_items:
        plan = generated.get("plan", "# 프로젝트 계획서\n")
        plan += "\n## 10. Live Decisions / Open Items\n\n"
        if decisions:
            plan += "| 상태 | 결정 | 내용 |\n|---|---|---|\n"
            for item in decisions:
                status = str(item.get("status") or "accepted")
                title = str(item.get("title") or "").replace("|", "/")
                body = str(item.get("body") or "").replace("|", "/")
                plan += f"| {status} | {title} | {body} |\n"
        else:
            plan += "- 아직 결정 없음\n"
        if pending_items:
            plan += "\n### Pending / TBD\n\n"
            for item in pending_items:
                plan += f"- {item}\n"
        generated["plan"] = plan

    designs = {str(d.get("view")): d for d in (state.get("design_updates", []) or []) if d.get("view")}
    if "architecture" in designs:
        generated["system_architecture"] = templates["system_architecture"] + "\n## 6. Live Architecture Snapshot\n\n" + _live_graph_markdown("Architecture Snapshot", designs["architecture"])
    if "dataflow" in designs:
        generated["data_flow"] = templates["data_flow"] + "\n## Live Data Flow Snapshot\n\n" + _live_graph_markdown("Data Flow Snapshot", designs["dataflow"])
    if "process" in designs:
        generated["function_definition"] = templates["function_definition"] + "\n## Live System Process Snapshot\n\n" + _live_graph_markdown("System Process Snapshot", designs["process"])

    # Explicit document_updates are intentional replacements from the Design
    # Session. They still win over auto-generated baselines.
    for item in state.get("document_updates", []) or []:
        doc_type = str(item.get("doc_type") or "")
        content = str(item.get("content") or "")
        if doc_type and content:
            generated[doc_type] = content
    return generated


def apply_live_draft_state(conn: sqlite3.Connection, project_id: int, member_name: str, state: dict[str, Any], *, lifecycle: str = "draft") -> dict[str, Any]:
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(404, "Project not found")
    if project["lifecycle"] != "draft" and lifecycle == "draft":
        raise HTTPException(409, "Project is not a live design draft")

    updates = {k: v for k, v in (state.get("project_updates") or {}).items() if k in PROJECT_FIELDS and str(v or "").strip()}
    brief = merge_project_brief(ensure_project_brief(conn, project_id), updates)
    if not str(brief.get("name") or "").strip():
        brief["name"] = project["name"] or "AI Design Draft"
    if not str(brief.get("goal") or "").strip():
        brief["goal"] = "AI와 프로젝트 설계 중"
    save_project_brief(conn, project_id, brief)
    conn.execute(
        "UPDATE projects SET name=?,goal=?,description=?,lifecycle=? WHERE id=?",
        (brief["name"], brief["goal"], brief.get("description", ""), lifecycle, project_id),
    )

    conn.execute("DELETE FROM requirements WHERE project_id=?", (project_id,))
    for item in state.get("requirements", []) or []:
        title = f"{item.get('ref','')} {item.get('title','')}".strip()
        if title:
            conn.execute(
                "INSERT INTO requirements(project_id,title,detail,status,created_at) VALUES(?,?,?,?,?)",
                (project_id, title, item.get("detail", ""), item.get("status", "defined"), now()),
            )

    conn.execute("DELETE FROM decisions WHERE project_id=?", (project_id,))
    for item in state.get("decisions", []) or []:
        if item.get("title"):
            conn.execute(
                "INSERT INTO decisions(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
                (project_id, item["title"], item.get("body", ""), f"Live Design / {member_name}", item.get("status", "accepted"), now()),
            )

    live_docs = build_live_draft_documents(brief, state)
    for doc_type, content in live_docs.items():
        conn.execute(
            "UPDATE documents SET content=?,status='draft',updated_by=?,updated_at=? WHERE project_id=? AND doc_type=?",
            (content, f"Live Design / {member_name}", now(), project_id, doc_type),
        )

    conn.execute("DELETE FROM edges WHERE project_id=?", (project_id,))
    conn.execute("DELETE FROM nodes WHERE project_id=?", (project_id,))
    for design in state.get("design_updates", []) or []:
        view = str(design.get("view") or "")
        if view not in {"process", "architecture", "dataflow"}:
            continue
        key_to_id: dict[str, int] = {}
        for idx, node in enumerate(design.get("nodes", []) or []):
            key = str(node.get("key") or "").strip()
            label = str(node.get("label") or "").strip()
            if not key or not label:
                continue
            cur = conn.execute(
                "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",
                (project_id, view, label, node.get("kind") or "component", node.get("detail") or "", 80 + (idx % 4) * 220, 80 + (idx // 4) * 150),
            )
            key_to_id[key] = cur.lastrowid
        for edge in design.get("edges", []) or []:
            source = key_to_id.get(str(edge.get("source") or ""))
            target = key_to_id.get(str(edge.get("target") or ""))
            if source and target and source != target:
                conn.execute(
                    "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",
                    (project_id, view, source, target, edge.get("label", "")),
                )

    add_activity(
        conn,
        project_id,
        "live_design",
        f"Live Draft 동기화 · 요구사항 {len(state.get('requirements', []) or [])} · 결정 {len(state.get('decisions', []) or [])} · Canvas {len(state.get('design_updates', []) or [])}",
        member_name,
    )
    return rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()) or {}


def derived_trace_links(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for task in tasks:
        for ref in sorted(set(re.findall(r"REQ-\d+", task.get("requirement_ref", "") or ""))):
            links.append({
                "id": f"derived-task-{task['id']}-{ref}",
                "source_type": "requirement",
                "source_ref": ref,
                "target_type": "task",
                "target_ref": f"TASK-{task['id']}",
                "relation": "implemented_by",
                "note": task.get("title", ""),
                "created_by": "System",
                "derived": True,
            })
    return links


def traceability_markdown(explicit: list[dict[str, Any]], derived: list[dict[str, Any]]) -> str:
    lines = ["# Traceability Matrix", "", "| Source | Relation | Target | Note |", "|---|---|---|---|"]
    for link in [*explicit, *derived]:
        src = f"{link['source_type']}:{link['source_ref']}"
        dst = f"{link['target_type']}:{link['target_ref']}"
        note = str(link.get("note", "")).replace("|", r"\|")
        lines.append(f"| {src} | {link['relation']} | {dst} | {note} |")
    if len(lines) == 4:
        lines.append("| - | - | - | 아직 연결 없음 |")
    return "\n".join(lines) + "\n"


def mermaid_for_view(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], view: str) -> str:
    selected = [n for n in nodes if n.get("view") == view]
    ids = {n["id"] for n in selected}
    lines = ["```mermaid", "flowchart LR"]
    for n in selected:
        label = str(n.get("label", "")).replace('"', "'")
        lines.append(f'  N{n["id"]}["{label}"]')
    for e in edges:
        if e.get("view") != view or e.get("source_id") not in ids or e.get("target_id") not in ids:
            continue
        label = str(e.get("label", "")).replace('"', "'")
        suffix = f'|"{label}"|' if label else ''
        lines.append(f'  N{e["source_id"]} -->{suffix} N{e["target_id"]}')
    lines.append("```")
    return "\n".join(lines) + "\n"


def add_activity(conn: sqlite3.Connection, project_id: int, type_: str, message: str, actor: str = "System") -> None:
    conn.execute(
        "INSERT INTO activity(project_id,type,message,actor,created_at) VALUES(?,?,?,?,?)",
        (project_id, type_, message, actor, now()),
    )


def seed_demo(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "INSERT INTO projects(name,goal,description,created_at) VALUES(?,?,?,?)",
        (
            "Factory Vision Project",
            "생산라인에서 제품 불량을 실시간 검출하고 판정 결과를 PLC와 대시보드에 전달한다.",
            "사람과 각자의 AI 도구가 같은 프로젝트 모델을 공유하는 협업 예시 프로젝트",
            now(),
        ),
    )
    p = cur.lastrowid
    ensure_project_documents(conn, p)
    for title, detail in [
        ("REQ-001 실시간 검사", "제품 유입 후 500ms 안에 판정 결과 생성"),
        ("REQ-002 불량 이력 저장", "검사 결과와 이미지 참조를 저장"),
        ("REQ-003 PLC 연동", "불량 판정 시 배출 신호 전송"),
        ("REQ-004 운영 대시보드", "생산/불량/장애 현황을 웹에서 확인"),
    ]:
        conn.execute(
            "INSERT INTO requirements(project_id,title,detail,status,created_at) VALUES(?,?,?,?,?)",
            (p, title, detail, "defined", now()),
        )
    tasks = [
        ("카메라 캡처 모듈", "done", "승훈", "high", "REQ-001"),
        ("AI 추론 API", "in_progress", "민수 + Codex", "high", "REQ-001"),
        ("PLC 어댑터", "review", "지현", "high", "REQ-003"),
        ("검사 결과 DB", "done", "민수", "medium", "REQ-002"),
        ("운영 대시보드", "todo", "서연 + Claude Code", "medium", "REQ-004"),
        ("E2E 통합 테스트", "todo", "Unassigned", "high", "REQ-001~004"),
    ]
    for title, status, owner, priority, req in tasks:
        conn.execute(
            "INSERT INTO tasks(project_id,title,status,owner,priority,requirement_ref,description,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (p, title, status, owner, priority, req, "", now(), now()),
        )
    views = {
        "process": [
            ("제품 투입", "event"), ("센서 감지", "event"), ("카메라 촬영", "service"),
            ("AI 추론", "service"), ("불량 판정", "decision"), ("PLC 배출", "device"),
            ("결과 저장", "database"), ("Dashboard", "ui"),
        ],
        "architecture": [
            ("Camera", "device"), ("Jetson Edge", "device"), ("Inference Service", "service"),
            ("Backend API", "service"), ("PostgreSQL", "database"), ("PLC", "device"), ("Web Dashboard", "ui"),
        ],
        "dataflow": [
            ("Camera", "source"), ("Preprocessor", "process"), ("AI Model", "process"),
            ("Backend API", "service"), ("Inspection DB", "database"), ("PLC", "sink"), ("Dashboard", "sink"),
        ],
    }
    node_ids: dict[str, list[int]] = {}
    for view, items in views.items():
        node_ids[view] = []
        for idx, (label, kind) in enumerate(items):
            cur = conn.execute(
                "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",
                (p, view, label, kind, "", idx * 180, 80 + (idx % 2) * 120),
            )
            node_ids[view].append(cur.lastrowid)
    for view, ids in node_ids.items():
        for i in range(len(ids) - 1):
            label = ""
            if view == "dataflow":
                labels = ["RGB Image", "Tensor", "DetectionResult", "JSON", "InspectionResult", "RejectSignal"]
                label = labels[i] if i < len(labels) else ""
            conn.execute(
                "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",
                (p, view, ids[i], ids[i + 1], label),
            )
    conn.execute(
        "INSERT INTO ideas(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
        (p, "Edge 이미지 압축 검토", "네트워크 부하 감소를 위해 전송 전 압축 여부를 실험", "지현", "discussing", now()),
    )
    conn.execute(
        "INSERT INTO decisions(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
        (p, "ADR-001 MQTT QoS 1 사용", "검사 이벤트 유실 방지를 위해 최소 1회 전달을 선택", "Team", "accepted", now()),
    )
    for name, role, ai in [("승훈", "Project Lead", "codex"), ("민수", "Backend", "codex"), ("지현", "Edge/PLC", "none"), ("서연", "Frontend", "claude")]:
        conn.execute(
            "INSERT INTO members(project_id,name,role,ai_provider,created_at) VALUES(?,?,?,?,?)",
            (p, name, role, ai, now()),
        )
    add_activity(conn, p, "project", "프로젝트 데모가 생성되었습니다.")
    add_activity(conn, p, "task", "AI 추론 API 작업이 진행 중입니다.", "민수 + Codex")
    add_activity(conn, p, "decision", "ADR-001 MQTT QoS 1 사용이 승인되었습니다.", "Team")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/api/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/api/health/ready")
def health_ready() -> dict[str, str]:
    try:
        with db() as conn:
            conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except sqlite3.Error as exc:
        LOGGER.error("Database readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return {"status": "ok", "database": "ready", "version": app.version}


@app.get("/api/project-intake/meta")
def project_intake_meta(x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    return intake_metadata()


@app.post("/api/project-intake/preview")
def project_intake_preview(payload: ProjectCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    data = payload.model_dump()
    quality = evaluate_intake(data)
    generated = build_initial_documents(data)
    return {
        "quality": quality,
        "preview": {
            "proposal": generated["proposal"],
            "plan": generated["plan"],
        },
    }


@app.post("/api/assistant-bridges/register")
def register_assistant_bridge(payload: AssistantBridgeRegister, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    token = secrets.token_urlsafe(32)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO assistant_bridges(member_name,provider,machine_name,token,last_seen,created_at) VALUES(?,?,?,?,?,?)",
            (payload.member_name, payload.provider, payload.machine_name, token, now(), now()),
        )
    return {"bridge_id": cur.lastrowid, "token": token, "member_name": payload.member_name, "provider": payload.provider}


@app.post("/api/conversations/start")
async def start_conversation(payload: ConversationStart, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        if payload.project_id is not None:
            project = conn.execute("SELECT * FROM projects WHERE id=?", (payload.project_id,)).fetchone()
            if not project:
                raise HTTPException(404, "Project not found")
            pid = payload.project_id
            ensure_project_brief(conn, pid)
        else:
            stamp = datetime.now().strftime("%m%d-%H%M")
            cur = conn.execute(
                "INSERT INTO projects(name,goal,description,created_at) VALUES(?,?,?,?)",
                (f"AI 대화 프로젝트 {stamp}", "AI 대화로 프로젝트 목표 정의 중", "Conversational Project Setup draft", now()),
            )
            pid = cur.lastrowid
            ensure_project_documents(conn, pid)
            ensure_project_brief(conn, pid)
        cur = conn.execute(
            "INSERT INTO conversation_sessions(project_id,member_name,provider,status,pending_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (pid, payload.member_name, payload.provider, "active", "{}", now(), now()),
        )
        sid = cur.lastrowid
        welcome = "프로젝트를 대화로 같이 정의해볼게요. 만들고 싶은 것을 편하게 설명해주세요. 소프트웨어가 아니어도 되고, 아직 정하지 못한 내용은 모른다고 해도 됩니다."
        conn.execute(
            "INSERT INTO conversation_messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
            (sid, "assistant", welcome, now()),
        )
        add_activity(conn, pid, "conversation", f"AI Project Interviewer 시작 ({payload.provider})", payload.member_name)
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        session = rowdict(conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (sid,)).fetchone())
    await manager.broadcast(pid, {"type": "refresh", "scope": "conversation"})
    return {"project": project, "session": session, "welcome": welcome}


@app.post("/api/conversations/{session_id}/messages")
async def conversation_message(session_id: int, payload: ConversationMessageCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        session = conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            raise HTTPException(404, "Conversation not found")
        if session["status"] != "active":
            raise HTTPException(409, "Conversation is not active")
        conn.execute(
            "INSERT INTO conversation_messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
            (session_id, "user", payload.message, now()),
        )
        messages = [dict(r) for r in conn.execute(
            "SELECT role,content,created_at FROM conversation_messages WHERE session_id=? ORDER BY id",
            (session_id,),
        )]
        brief = ensure_project_brief(conn, session["project_id"])
        documents = [dict(r) for r in conn.execute(
            "SELECT doc_type,title,content,status FROM documents WHERE project_id=? ORDER BY id",
            (session["project_id"],),
        )]
        try:
            pending = json.loads(session["pending_json"] or "{}")
        except json.JSONDecodeError:
            pending = {}
        prompt = build_interviewer_prompt(
            project_id=session["project_id"],
            brief=brief,
            messages=messages,
            documents=documents,
            previous_pending=pending,
        )
        cur = conn.execute(
            "INSERT INTO conversation_jobs(session_id,provider,member_name,prompt,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (session_id, session["provider"], session["member_name"], prompt, "queued", now(), now()),
        )
        conn.execute("UPDATE conversation_sessions SET updated_at=? WHERE id=?", (now(), session_id))
        job = rowdict(conn.execute("SELECT id,session_id,provider,member_name,status,created_at,updated_at FROM conversation_jobs WHERE id=?", (cur.lastrowid,)).fetchone())
        pid = session["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "conversation"})
    return {"job": job}


@app.get("/api/assistant-bridge/jobs")
def assistant_bridge_jobs(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    token = bridge_bearer_token(authorization, token)
    with db() as conn:
        bridge = conn.execute("SELECT * FROM assistant_bridges WHERE token=?", (token,)).fetchone()
        if not bridge:
            raise HTTPException(401, "Invalid assistant bridge token")
        conn.execute("UPDATE assistant_bridges SET last_seen=? WHERE id=?", (now(), bridge["id"]))
        job = conn.execute(
            "SELECT * FROM conversation_jobs WHERE provider=? AND member_name=? AND status='queued' ORDER BY id LIMIT 1",
            (bridge["provider"], bridge["member_name"]),
        ).fetchone()
        if not job:
            return {"job": None}
        conn.execute(
            "UPDATE conversation_jobs SET status='claimed',bridge_id=?,updated_at=? WHERE id=?",
            (bridge["id"], now(), job["id"]),
        )
        return {"job": {"id": job["id"], "session_id": job["session_id"], "provider": job["provider"], "member_name": job["member_name"]}, "prompt": job["prompt"]}


@app.post("/api/assistant-bridge/results")
async def assistant_bridge_result(
    payload: ConversationBridgeResult,
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    token = bridge_bearer_token(authorization, token)
    with db() as conn:
        bridge = conn.execute("SELECT * FROM assistant_bridges WHERE token=?", (token,)).fetchone()
        if not bridge:
            raise HTTPException(401, "Invalid assistant bridge token")
        job = conn.execute(
            "SELECT * FROM conversation_jobs WHERE id=? AND bridge_id=?",
            (payload.job_id, bridge["id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "Conversation job not found")
        session = conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (job["session_id"],)).fetchone()
        if not session:
            raise HTTPException(404, "Conversation session not found")
        final_status = payload.status
        assistant_text = payload.output[-12000:] if payload.output else "AI 응답이 비어 있습니다."
        if payload.status == "completed":
            try:
                parsed = normalize_ai_result(payload.output)
                try:
                    previous = json.loads(session["pending_json"] or "{}")
                except json.JSONDecodeError:
                    previous = {}
                pending = combine_proposals(previous, parsed)
                assistant_text = parsed["reply"]
                conn.execute(
                    "UPDATE conversation_sessions SET pending_json=?,updated_at=? WHERE id=?",
                    (json.dumps(pending, ensure_ascii=False), now(), session["id"]),
                )
            except Exception as exc:
                final_status = "failed"
                assistant_text = f"AI 응답을 Project OS 형식으로 해석하지 못했습니다: {exc}"
        conn.execute(
            "INSERT INTO conversation_messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
            (session["id"], "assistant", assistant_text, now()),
        )
        conn.execute(
            "UPDATE conversation_jobs SET status=?,output=?,updated_at=? WHERE id=?",
            (final_status, payload.output[-250000:], now(), job["id"]),
        )
        add_activity(conn, session["project_id"], "conversation", f"AI Project Interviewer 응답 ({final_status})", bridge["member_name"])
        pid = session["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "conversation"})
    return {"ok": True, "status": final_status}


@app.post("/api/conversations/{session_id}/apply")
async def apply_conversation(session_id: int, payload: ConversationApply, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        session = conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            raise HTTPException(404, "Conversation not found")
        try:
            pending = json.loads(session["pending_json"] or "{}")
        except json.JSONDecodeError:
            pending = {}
        if not pending:
            return {"ok": True, "applied": 0, "quality": evaluate_intake(ensure_project_brief(conn, session["project_id"]))}
        pid = session["project_id"]
        applied = 0
        brief = ensure_project_brief(conn, pid)
        if payload.apply_project:
            brief = merge_project_brief(brief, pending.get("project_updates", {}))
            save_project_brief(conn, pid, brief)
            conn.execute(
                "UPDATE projects SET name=?,goal=?,description=? WHERE id=?",
                (brief.get("name") or "대화형 프로젝트", brief.get("goal") or "목표 정의 중", brief.get("description") or "", pid),
            )
            generated = build_initial_documents(brief)
            for doc_type, content in generated.items():
                doc = conn.execute("SELECT * FROM documents WHERE project_id=? AND doc_type=?", (pid, doc_type)).fetchone()
                if not doc or doc["status"] != "draft" or doc["updated_by"] not in {"System", "Project Setup", "AI Conversation"}:
                    continue
                if doc["content"] != content:
                    conn.execute(
                        "INSERT INTO document_revisions(document_id,content,status,editor,created_at) VALUES(?,?,?,?,?)",
                        (doc["id"], doc["content"], doc["status"], "AI Conversation", now()),
                    )
                    conn.execute(
                        "UPDATE documents SET content=?,updated_by='AI Conversation',updated_at=? WHERE id=?",
                        (content, now(), doc["id"]),
                    )
            applied += len(pending.get("project_updates", {}))

        if payload.apply_requirements:
            for item in pending.get("requirements", []):
                ref = str(item.get("ref") or "").strip()
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                full_title = f"{ref} {title}".strip()
                exists = conn.execute("SELECT 1 FROM requirements WHERE project_id=? AND title=?", (pid, full_title)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO requirements(project_id,title,detail,status,created_at) VALUES(?,?,?,?,?)",
                        (pid, full_title, item.get("detail") or "", item.get("status") or "defined", now()),
                    )
                    applied += 1

        if payload.apply_decisions:
            for item in pending.get("decisions", []):
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                exists = conn.execute("SELECT 1 FROM decisions WHERE project_id=? AND title=?", (pid, title)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO decisions(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
                        (pid, title, item.get("body") or "", f"AI proposal / {session['member_name']}", item.get("status") or "proposed", now()),
                    )
                    applied += 1

        if payload.apply_documents:
            for item in pending.get("document_updates", []):
                doc = conn.execute("SELECT * FROM documents WHERE project_id=? AND doc_type=?", (pid, item.get("doc_type"))).fetchone()
                content = str(item.get("content") or "")
                if not doc or not content:
                    continue
                conn.execute(
                    "INSERT INTO document_revisions(document_id,content,status,editor,created_at) VALUES(?,?,?,?,?)",
                    (doc["id"], doc["content"], doc["status"], "AI Conversation", now()),
                )
                conn.execute(
                    "UPDATE documents SET content=?,updated_by=?,updated_at=? WHERE id=?",
                    (content, f"AI Conversation / {session['member_name']}", now(), doc["id"]),
                )
                applied += 1

        # Visual design proposals are only materialized after this human Apply action.
        for design in pending.get("design_updates", []):
            view = str(design.get("view") or "")
            if view not in {"process", "architecture", "dataflow"}:
                continue
            mode = str(design.get("mode") or "merge")
            if mode == "replace":
                conn.execute("DELETE FROM edges WHERE project_id=? AND view=?", (pid, view))
                conn.execute("DELETE FROM nodes WHERE project_id=? AND view=?", (pid, view))

            existing = {
                r["label"]: r["id"]
                for r in conn.execute("SELECT id,label FROM nodes WHERE project_id=? AND view=?", (pid, view))
            }
            key_to_id: dict[str, int] = {}
            for idx, node in enumerate(design.get("nodes", [])):
                key = str(node.get("key") or "").strip()
                label = str(node.get("label") or "").strip()
                if not key or not label:
                    continue
                node_id = existing.get(label) if mode == "merge" else None
                if node_id is None:
                    cur = conn.execute(
                        "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",
                        (pid, view, label, node.get("kind") or "component", node.get("detail") or "", 80 + (idx % 4) * 220, 80 + (idx // 4) * 150),
                    )
                    node_id = cur.lastrowid
                    existing[label] = node_id
                    applied += 1
                key_to_id[key] = node_id

            for edge in design.get("edges", []):
                source_id = key_to_id.get(str(edge.get("source") or ""))
                target_id = key_to_id.get(str(edge.get("target") or ""))
                if not source_id or not target_id or source_id == target_id:
                    continue
                label = str(edge.get("label") or "")
                duplicate = conn.execute(
                    "SELECT 1 FROM edges WHERE project_id=? AND view=? AND source_id=? AND target_id=? AND label=?",
                    (pid, view, source_id, target_id, label),
                ).fetchone()
                if not duplicate:
                    conn.execute(
                        "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",
                        (pid, view, source_id, target_id, label),
                    )
                    applied += 1

        conn.execute("UPDATE conversation_sessions SET pending_json='{}',updated_at=? WHERE id=?", (now(), session_id))
        add_activity(conn, pid, "conversation", f"대화 제안 {applied}개를 프로젝트에 적용", session["member_name"])
        quality = evaluate_intake(ensure_project_brief(conn, pid))
    await manager.broadcast(pid, {"type": "refresh", "scope": "conversation"})
    return {"ok": True, "applied": applied, "quality": quality}


@app.post("/api/design-drafts")
async def create_design_draft(payload: DesignDraftCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    name = payload.name_hint.strip() or "AI Design Draft"
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name,goal,description,lifecycle,created_at) VALUES(?,?,?,?,?)",
            (name, "AI와 프로젝트 설계 중", "AI Design Session Live Draft · /apply 전 정식 확정본 아님", "draft", now()),
        )
        pid = cur.lastrowid
        ensure_project_documents(conn, pid)
        brief = ensure_project_brief(conn, pid)
        brief["name"] = name
        brief["goal"] = "AI와 프로젝트 설계 중"
        brief["description"] = "AI Design Session Live Draft · /apply 전 정식 확정본 아님"
        save_project_brief(conn, pid, brief)
        conn.execute(
            "INSERT INTO members(project_id,name,role,ai_provider,created_at) VALUES(?,?,?,?,?)",
            (pid, payload.member_name, "Design Session", payload.provider, now()),
        )
        add_activity(conn, pid, "live_design", "AI Design Session Live Draft가 시작되었습니다.", payload.member_name)
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    return project


@app.put("/api/design-drafts/{project_id}/sync")
async def sync_design_draft(project_id: int, payload: DesignDraftSync, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = apply_live_draft_state(conn, project_id, payload.member_name, payload.state, lifecycle="draft")
    await manager.broadcast(project_id, {"type": "refresh", "scope": "live_draft"})
    return {"ok": True, "project": project}


@app.post("/api/design-drafts/{project_id}/promote")
async def promote_design_draft(project_id: int, payload: DesignDraftSync, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        if project["lifecycle"] != "draft":
            raise HTTPException(409, "Project is not a live design draft")
        promoted = apply_live_draft_state(conn, project_id, payload.member_name, payload.state, lifecycle="active")
        add_activity(conn, project_id, "project", "Live Draft가 정식 프로젝트로 승격되었습니다.", payload.member_name)
    await manager.broadcast(project_id, {"type": "refresh", "scope": "live_draft_promoted"})
    return {"ok": True, "project": promoted}


@app.delete("/api/design-drafts/{project_id}")
async def discard_design_draft(project_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        if project["lifecycle"] != "draft":
            raise HTTPException(409, "Only design drafts can be discarded here")
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    await manager.broadcast(project_id, {"type": "project_deleted", "project_id": project_id})
    return {"ok": True, "deleted_project_id": project_id}


@app.get("/api/projects", dependencies=[])
def projects(_: None = Header(default=None, alias="x-ignore"), x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY id DESC")]


@app.post("/api/projects")
async def create_project(payload: ProjectCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name,goal,description,created_at) VALUES(?,?,?,?)",
            (payload.name, payload.goal, payload.description, now()),
        )
        pid = cur.lastrowid
        ensure_project_documents(conn, pid)
        apply_project_brief_to_documents(conn, pid, payload)
        quality = evaluate_intake(payload.model_dump())
        add_activity(conn, pid, "project", f"프로젝트가 생성되었습니다. 초기 정의 품질 {quality['score']}점")
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        if project is not None:
            project["intake_quality"] = quality
    return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, confirm_name: str = Query(...), x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = conn.execute("SELECT id,name FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        if confirm_name != project["name"]:
            raise HTTPException(400, "Project name confirmation does not match")
        deleted_name = project["name"]
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    await manager.broadcast(project_id, {"type": "project_deleted", "project_id": project_id})
    return {"ok": True, "deleted_project_id": project_id, "deleted_name": deleted_name}


@app.patch("/api/projects/{project_id}/goal")
async def update_goal(project_id: int, payload: GoalPatch, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        conn.execute("UPDATE projects SET goal=?, description=? WHERE id=?", (payload.goal, payload.description, project_id))
        add_activity(conn, project_id, "project", "프로젝트 목표가 수정되었습니다.")
    await manager.broadcast(project_id, {"type": "refresh", "scope": "goal"})
    return {"ok": True}


@app.get("/api/projects/{project_id}/snapshot")
def snapshot(project_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not project:
            raise HTTPException(404, "Project not found")
        tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY id", (project_id,))]
        total = len(tasks)
        done = sum(1 for t in tasks if t["status"] == "done")
        progress = round((done / total) * 100) if total else 0
        trace_links = [dict(r) for r in conn.execute("SELECT * FROM trace_links WHERE project_id=? ORDER BY id DESC", (project_id,))]
        derived_links = derived_trace_links(tasks)
        project_brief = ensure_project_brief(conn, project_id)
        conversation = conversation_snapshot(conn, project_id)
        live_draft = conversation_live_draft_snapshot(conn, project_id)
        return {
            "project": project,
            "project_brief": project_brief,
            "conversation": conversation,
            "live_draft": live_draft,
            "requirements": [dict(r) for r in conn.execute("SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,))],
            "tasks": tasks,
            "nodes": [dict(r) for r in conn.execute("SELECT * FROM nodes WHERE project_id=? ORDER BY id", (project_id,))],
            "edges": [dict(r) for r in conn.execute("SELECT * FROM edges WHERE project_id=? ORDER BY id", (project_id,))],
            "ideas": [dict(r) for r in conn.execute("SELECT * FROM ideas WHERE project_id=? ORDER BY id DESC", (project_id,))],
            "decisions": [dict(r) for r in conn.execute("SELECT * FROM decisions WHERE project_id=? ORDER BY id DESC", (project_id,))],
            "members": [dict(r) for r in conn.execute("SELECT * FROM members WHERE project_id=? ORDER BY id", (project_id,))],
            "documents": [dict(r) for r in conn.execute("SELECT * FROM documents WHERE project_id=? ORDER BY id", (project_id,))],
            "document_comments": [dict(r) for r in conn.execute("SELECT c.* FROM document_comments c JOIN documents d ON d.id=c.document_id WHERE d.project_id=? ORDER BY c.id DESC LIMIT 100", (project_id,))],
            "trace_links": trace_links,
            "derived_trace_links": derived_links,
            "activity": [dict(r) for r in conn.execute("SELECT * FROM activity WHERE project_id=? ORDER BY id DESC LIMIT 30", (project_id,))],
            "bridges": [dict(r) for r in conn.execute("SELECT id,project_id,member_name,provider,machine_name,last_seen,created_at FROM bridges WHERE project_id=? ORDER BY id DESC", (project_id,))],
            "ai_jobs": [dict(r) for r in conn.execute("SELECT * FROM ai_jobs WHERE project_id=? ORDER BY id DESC LIMIT 30", (project_id,))],
            "stats": {
                "progress": progress,
                "tasks_total": total,
                "tasks_done": done,
                "tasks_blocked": sum(1 for t in tasks if t["status"] == "blocked"),
                "requirements": conn.execute("SELECT COUNT(*) c FROM requirements WHERE project_id=?", (project_id,)).fetchone()["c"],
                "decisions_pending": conn.execute("SELECT COUNT(*) c FROM decisions WHERE project_id=? AND status!='accepted'", (project_id,)).fetchone()["c"],
                "documents_total": conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=?", (project_id,)).fetchone()["c"],
                "documents_ready": conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=? AND status IN ('review','approved','complete')", (project_id,)).fetchone()["c"],
                "trace_links": len(trace_links) + len(derived_links),
            },
        }


@app.post("/api/projects/{project_id}/requirements")
async def create_requirement(project_id: int, payload: RequirementCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO requirements(project_id,title,detail,status,created_at) VALUES(?,?,?,?,?)",
            (project_id, payload.title, payload.detail, payload.status, now()),
        )
        add_activity(conn, project_id, "requirement", f"요구사항 추가: {payload.title}")
        item = rowdict(conn.execute("SELECT * FROM requirements WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "requirements"})
    return item


@app.patch("/api/requirements/{requirement_id}")
async def patch_requirement(requirement_id: int, payload: RequirementPatch, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    data = payload.model_dump(exclude_none=True)
    if not data:
        return {"ok": True}
    with db() as conn:
        row = conn.execute("SELECT * FROM requirements WHERE id=?", (requirement_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Requirement not found")
        sets = ",".join(f"{k}=?" for k in data)
        conn.execute(f"UPDATE requirements SET {sets} WHERE id=?", (*data.values(), requirement_id))
        add_activity(conn, row["project_id"], "requirement", f"요구사항 수정: {data.get('title', row['title'])}")
        pid = row["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "requirements"})
    return {"ok": True}


@app.post("/api/projects/{project_id}/tasks")
async def create_task(project_id: int, payload: TaskCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks(project_id,title,description,status,owner,priority,requirement_ref,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id, payload.title, payload.description, payload.status, payload.owner, payload.priority, payload.requirement_ref, now(), now()),
        )
        add_activity(conn, project_id, "task", f"Task 추가: {payload.title}", payload.owner)
        item = rowdict(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "tasks"})
    return item


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: int, payload: TaskPatch, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    data = payload.model_dump(exclude_none=True)
    if not data:
        return {"ok": True}
    with db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Task not found")
        data["updated_at"] = now()
        sets = ",".join(f"{k}=?" for k in data)
        conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*data.values(), task_id))
        pid = row["project_id"]
        add_activity(conn, pid, "task", f"Task 변경: {row['title']} → {data.get('status', row['status'])}", data.get("owner", row["owner"]))
    await manager.broadcast(pid, {"type": "refresh", "scope": "tasks"})
    return {"ok": True}


@app.patch("/api/documents/{document_id}")
async def patch_document(document_id: int, payload: DocumentPatch, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        conn.execute(
            "INSERT INTO document_revisions(document_id,content,status,editor,created_at) VALUES(?,?,?,?,?)",
            (document_id, row["content"], row["status"], payload.updated_by, now()),
        )
        conn.execute(
            "UPDATE documents SET content=?,status=?,updated_by=?,updated_at=? WHERE id=?",
            (payload.content, payload.status, payload.updated_by, now(), document_id),
        )
        pid = row["project_id"]
        add_activity(conn, pid, "document", f"문서 수정: {row['title']}", payload.updated_by)
        item = rowdict(conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone())
    await manager.broadcast(pid, {"type": "refresh", "scope": "documents", "document_id": document_id})
    return item


@app.get("/api/documents/{document_id}/revisions")
def document_revisions(document_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id,document_id,status,editor,created_at FROM document_revisions WHERE document_id=? ORDER BY id DESC LIMIT 50",
            (document_id,),
        )]


@app.post("/api/documents/{document_id}/comments")
async def add_document_comment(document_id: int, payload: DocumentCommentCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")
        cur = conn.execute(
            "INSERT INTO document_comments(document_id,author,body,created_at) VALUES(?,?,?,?)",
            (document_id, payload.author, payload.body, now()),
        )
        add_activity(conn, doc["project_id"], "document", f"문서 댓글: {doc['title']}", payload.author)
        item = rowdict(conn.execute("SELECT * FROM document_comments WHERE id=?", (cur.lastrowid,)).fetchone())
        pid = doc["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "documents", "document_id": document_id})
    return item


@app.post("/api/projects/{project_id}/trace-links")
async def create_trace_link(project_id: int, payload: TraceLinkCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        if not conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        cur = conn.execute(
            "INSERT INTO trace_links(project_id,source_type,source_ref,target_type,target_ref,relation,note,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id, payload.source_type, payload.source_ref, payload.target_type, payload.target_ref, payload.relation, payload.note, payload.created_by, now()),
        )
        add_activity(conn, project_id, "trace", f"Trace 연결: {payload.source_ref} → {payload.target_ref}", payload.created_by)
        item = rowdict(conn.execute("SELECT * FROM trace_links WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "traceability"})
    return item


@app.delete("/api/trace-links/{link_id}")
async def delete_trace_link(link_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        row = conn.execute("SELECT * FROM trace_links WHERE id=?", (link_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Trace link not found")
        conn.execute("DELETE FROM trace_links WHERE id=?", (link_id,))
        add_activity(conn, row["project_id"], "trace", f"Trace 연결 삭제: {row['source_ref']} → {row['target_ref']}")
        pid = row["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "traceability"})
    return {"ok": True}


@app.get("/api/documents/{document_id}/export.md")
def export_document_markdown(document_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "Document not found")
        body = doc["content"]
    return Response(content=body, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="document_{document_id}.md"'})


@app.get("/api/projects/{project_id}/export/documents.zip")
def export_project_documents(project_id: int, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
        if not project:
            raise HTTPException(404, "Project not found")
        documents = [dict(r) for r in conn.execute("SELECT * FROM documents WHERE project_id=? ORDER BY id", (project_id,))]
        requirements = [dict(r) for r in conn.execute("SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,))]
        tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY id", (project_id,))]
        nodes = [dict(r) for r in conn.execute("SELECT * FROM nodes WHERE project_id=? ORDER BY id", (project_id,))]
        edges = [dict(r) for r in conn.execute("SELECT * FROM edges WHERE project_id=? ORDER BY id", (project_id,))]
        decisions = [dict(r) for r in conn.execute("SELECT * FROM decisions WHERE project_id=? ORDER BY id", (project_id,))]
        explicit = [dict(r) for r in conn.execute("SELECT * FROM trace_links WHERE project_id=? ORDER BY id", (project_id,))]
    derived = derived_trace_links(tasks)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        summary = f"# {project['name']}\n\n## Goal\n{project['goal']}\n\n## Description\n{project['description']}\n\nGenerated: {now()}\n"
        zf.writestr("00_PROJECT_SUMMARY.md", summary)
        for idx, doc in enumerate(documents, start=1):
            zf.writestr(f"documents/{idx:02d}_{doc['doc_type']}.md", doc["content"])
        zf.writestr("TRACEABILITY.md", traceability_markdown(explicit, derived))
        zf.writestr("design/SYSTEM_PROCESS.md", "# System Process\n\n" + mermaid_for_view(nodes, edges, "process"))
        zf.writestr("design/ARCHITECTURE.md", "# Architecture\n\n" + mermaid_for_view(nodes, edges, "architecture"))
        zf.writestr("design/DATA_FLOW.md", "# Data Flow\n\n" + mermaid_for_view(nodes, edges, "dataflow"))
        snapshot = {"project": project, "requirements": requirements, "tasks": tasks, "decisions": decisions, "nodes": nodes, "edges": edges, "trace_links": explicit, "derived_trace_links": derived}
        zf.writestr("project_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
    return Response(content=buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="team_project_os_{project_id}_documents.zip"'})


@app.post("/api/projects/{project_id}/nodes")
async def create_node(project_id: int, payload: NodeCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    if payload.view not in {"process", "architecture", "dataflow"}:
        raise HTTPException(400, "Invalid view")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",
            (project_id, payload.view, payload.label, payload.kind, payload.detail, payload.x, payload.y),
        )
        add_activity(conn, project_id, "design", f"{payload.view} 노드 추가: {payload.label}")
        item = rowdict(conn.execute("SELECT * FROM nodes WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": payload.view})
    return item


@app.post("/api/projects/{project_id}/edges")
async def create_edge(project_id: int, payload: EdgeCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",
            (project_id, payload.view, payload.source_id, payload.target_id, payload.label),
        )
        add_activity(conn, project_id, "design", f"{payload.view} 연결 추가")
        item = rowdict(conn.execute("SELECT * FROM edges WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": payload.view})
    return item


@app.post("/api/projects/{project_id}/ideas")
async def create_idea(project_id: int, payload: IdeaCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO ideas(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
            (project_id, payload.title, payload.body, payload.author, payload.status, now()),
        )
        add_activity(conn, project_id, "idea", f"아이디어 제안: {payload.title}", payload.author)
        item = rowdict(conn.execute("SELECT * FROM ideas WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "ideas"})
    return item


@app.post("/api/projects/{project_id}/decisions")
async def create_decision(project_id: int, payload: DecisionCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO decisions(project_id,title,body,author,status,created_at) VALUES(?,?,?,?,?,?)",
            (project_id, payload.title, payload.body, payload.author, payload.status, now()),
        )
        add_activity(conn, project_id, "decision", f"결정 등록: {payload.title}", payload.author)
        item = rowdict(conn.execute("SELECT * FROM decisions WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "decisions"})
    return item


@app.post("/api/projects/{project_id}/members")
async def create_member(project_id: int, payload: MemberCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO members(project_id,name,role,ai_provider,created_at) VALUES(?,?,?,?,?)",
            (project_id, payload.name, payload.role, payload.ai_provider, now()),
        )
        add_activity(conn, project_id, "member", f"팀원 참여: {payload.name}")
        item = rowdict(conn.execute("SELECT * FROM members WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "members"})
    return item


@app.post("/api/projects/{project_id}/bridges/register")
def register_bridge(project_id: int, payload: BridgeRegister, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    token = secrets.token_urlsafe(32)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO bridges(project_id,member_name,provider,machine_name,token,last_seen,created_at) VALUES(?,?,?,?,?,?,?)",
            (project_id, payload.member_name, payload.provider, payload.machine_name, token, now(), now()),
        )
        add_activity(conn, project_id, "ai", f"Local Bridge 등록: {payload.member_name} / {payload.provider}", payload.member_name)
        bridge_id = cur.lastrowid
    return {"bridge_id": bridge_id, "token": token, "provider": payload.provider}


@app.post("/api/projects/{project_id}/ai-jobs")
async def create_ai_job(project_id: int, payload: AIJobCreate, x_access_key: str | None = Header(default=None)):
    require_access(x_access_key)
    with db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id=? AND project_id=?", (payload.task_id, project_id)).fetchone()
        if not task:
            raise HTTPException(404, "Task not found")
        cur = conn.execute(
            "INSERT INTO ai_jobs(project_id,task_id,provider,member_name,repo_hint,instruction,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (project_id, payload.task_id, payload.provider, payload.member_name, payload.repo_hint, payload.instruction, "queued", now(), now()),
        )
        add_activity(conn, project_id, "ai", f"AI 작업 대기열 등록: {task['title']} ({payload.provider})", payload.member_name)
        job = rowdict(conn.execute("SELECT * FROM ai_jobs WHERE id=?", (cur.lastrowid,)).fetchone())
    await manager.broadcast(project_id, {"type": "refresh", "scope": "ai"})
    return job


@app.get("/api/bridge/jobs")
def bridge_jobs(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    token = bridge_bearer_token(authorization, token)
    with db() as conn:
        bridge = conn.execute("SELECT * FROM bridges WHERE token=?", (token,)).fetchone()
        if not bridge:
            raise HTTPException(401, "Invalid bridge token")
        conn.execute("UPDATE bridges SET last_seen=? WHERE id=?", (now(), bridge["id"]))
        job = conn.execute(
            "SELECT * FROM ai_jobs WHERE project_id=? AND provider=? AND member_name=? AND status='queued' ORDER BY id LIMIT 1",
            (bridge["project_id"], bridge["provider"], bridge["member_name"]),
        ).fetchone()
        if not job:
            return {"job": None}
        conn.execute("UPDATE ai_jobs SET status='claimed',bridge_id=?,updated_at=? WHERE id=?", (bridge["id"], now(), job["id"]))
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (job["task_id"],)).fetchone()
        project = conn.execute("SELECT * FROM projects WHERE id=?", (job["project_id"],)).fetchone()
        reqs = [dict(r) for r in conn.execute("SELECT * FROM requirements WHERE project_id=?", (job["project_id"],))]
        docs = [dict(r) for r in conn.execute("SELECT * FROM documents WHERE project_id=? AND doc_type IN ('requirements','function_definition','system_architecture','api_design','qa') ORDER BY id", (job["project_id"],))]
        return {
            "job": dict(job),
            "task": dict(task),
            "project": dict(project),
            "requirements": reqs,
            "documents": docs,
        }


@app.post("/api/bridge/results")
async def bridge_result(
    payload: AIResult,
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    token = bridge_bearer_token(authorization, token)
    with db() as conn:
        bridge = conn.execute("SELECT * FROM bridges WHERE token=?", (token,)).fetchone()
        if not bridge:
            raise HTTPException(401, "Invalid bridge token")
        job = conn.execute("SELECT * FROM ai_jobs WHERE id=? AND bridge_id=?", (payload.job_id, bridge["id"])).fetchone()
        if not job:
            raise HTTPException(404, "Job not found")
        conn.execute(
            "UPDATE ai_jobs SET status=?,output=?,evidence=?,updated_at=? WHERE id=?",
            (payload.status, payload.output[-30000:], payload.evidence[-10000:], now(), payload.job_id),
        )
        add_activity(conn, job["project_id"], "ai", f"AI 작업 결과: Job #{payload.job_id} → {payload.status}", bridge["member_name"])
        pid = job["project_id"]
    await manager.broadcast(pid, {"type": "refresh", "scope": "ai"})
    return {"ok": True}


@app.websocket("/ws/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int):
    requested_protocols = [
        value.strip()
        for value in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if value.strip()
    ]
    key = ""
    for protocol in requested_protocols:
        if not protocol.startswith("access-key."):
            continue
        encoded = protocol.removeprefix("access-key.")
        try:
            padding = "=" * (-len(encoded) % 4)
            key = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            key = ""
        break
    # V0.14 compatibility: old clients may still send the key in the query string.
    if not key:
        key = websocket.query_params.get("key", "")
    if ACCESS_KEY and (
        not key or not secrets.compare_digest(key, ACCESS_KEY)
    ):
        await websocket.close(code=4401)
        return
    accepted_protocol = "project-os" if "project-os" in requested_protocols else None
    await manager.connect(project_id, websocket, accepted_protocol)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)
