from __future__ import annotations

import io
import json
import os
import re
import secrets
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("PROJECT_OS_DB", BASE_DIR / "project_os.db"))
ACCESS_KEY = os.getenv("APP_ACCESS_KEY", "")
SEED_DEMO = os.getenv("PROJECT_OS_SEED_DEMO", "1").strip().lower() not in {"0", "false", "no"}
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Team Project OS", version="0.3.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

DOCUMENT_TEMPLATES = [
    ("proposal", "기획서", "# 기획서\n\n## 1. 배경 및 문제 정의\n\n## 2. 프로젝트 목표\n\n## 3. 대상 사용자\n\n## 4. 핵심 가치\n\n## 5. 성공 기준\n\n## 6. 범위 / 제외 범위\n"),
    ("plan", "계획서", "# 계획서\n\n## 1. 추진 범위\n\n## 2. 일정\n\n## 3. 역할과 책임\n\n## 4. 개발/운영 전략\n\n## 5. 리스크와 대응\n"),
    ("milestone", "마일스톤", "# 마일스톤\n\n| Milestone | 목표 | 완료 조건 | 목표일 | 상태 |\n|---|---|---|---|---|\n| M1 |  |  |  | Draft |\n"),
    ("backlog", "백로그", "# 백로그\n\n| ID | 항목 | 우선순위 | 담당 | 상태 | 연결 요구사항 |\n|---|---|---|---|---|---|\n"),
    ("requirements", "요구사항 정의서", "# 요구사항 정의서\n\n| ID | 요구사항 | 상세 | 우선순위 | 상태 | 검증 기준 |\n|---|---|---|---|---|---|\n"),
    ("service_policy", "서비스 및 운영 정책서", "# 서비스 및 운영 정책서\n\n## 1. 사용자/권한 정책\n\n## 2. 데이터 보관 정책\n\n## 3. 장애/예외 처리 정책\n\n## 4. 로그/감사 정책\n\n## 5. 운영 및 배포 정책\n"),
    ("function_definition", "기능 정의서", "# 기능 정의서\n\n| 기능 ID | 기능명 | 입력 | 처리 | 출력 | 예외 | 관련 요구사항 |\n|---|---|---|---|---|---|---|\n"),
    ("ia", "IA (Information Architecture, 정보구조도)", "# IA\n\n## 정보 구조\n\n- Home\n  - \n\n## 화면/메뉴 관계\n"),
    ("screen_design", "화면 설계서", "# 화면 설계서\n\n## SCREEN-001\n\n### 목적\n\n### 주요 컴포넌트\n\n### 사용자 동작\n\n### 연결 기능/API\n"),
    ("system_architecture", "시스템 구조도", "# 시스템 구조도\n\n## 구성 요소\n\n## 연결 관계\n\n## 배포 구조\n\n> Design > Architecture Canvas와 함께 관리합니다.\n"),
    ("data_flow", "데이터 플로우", "# 데이터 플로우\n\n| Source | Data | Processing | Destination | Protocol/Format |\n|---|---|---|---|---|\n\n> Design > Data Flow Canvas와 함께 관리합니다.\n"),
    ("api_design", "API 설계 문서", "# API 설계 문서\n\n| API ID | Method | Path | 목적 | Request | Response | Error |\n|---|---|---|---|---|---|---|\n"),
    ("qa", "QA 문서", "# QA 문서\n\n## QA Strategy\n\n## Test Cases\n\n| TC ID | 연결 요구사항 | 사전조건 | 절차 | Expected | Result | Evidence |\n|---|---|---|---|---|---|---|\n"),
]



@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_access(x_access_key: str | None = Header(default=None)) -> None:
    if ACCESS_KEY and x_access_key != ACCESS_KEY:
        raise HTTPException(status_code=401, detail="Invalid access key")


def rowdict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    goal: str = Field(min_length=2, max_length=1000)
    description: str = Field(default="", max_length=2000)
    problem: str = Field(default="", max_length=4000)
    users: str = Field(default="", max_length=2000)
    success_criteria: str = Field(default="", max_length=4000)
    scope: str = Field(default="", max_length=4000)
    constraints: str = Field(default="", max_length=4000)


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


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, project_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
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
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
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
            """
        )
        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        if count == 0 and SEED_DEMO:
            seed_demo(conn)
        for project_row in conn.execute("SELECT id FROM projects"):
            ensure_project_documents(conn, project_row["id"])


def ensure_project_documents(conn: sqlite3.Connection, project_id: int) -> None:
    for doc_type, title, content in DOCUMENT_TEMPLATES:
        conn.execute(
            "INSERT OR IGNORE INTO documents(project_id,doc_type,title,content,status,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (project_id, doc_type, title, content, "draft", "System", now(), now()),
        )


def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
    proposal = f"""# 기획서

## 1. 배경 및 문제 정의
{payload.problem or payload.description or '- 작성 필요'}

## 2. 프로젝트 목표
{payload.goal}

## 3. 대상 사용자
{payload.users or '- 작성 필요'}

## 4. 핵심 가치
{payload.description or '- 작성 필요'}

## 5. 성공 기준
{payload.success_criteria or '- 작성 필요'}

## 6. 범위 / 제외 범위
{payload.scope or '- 작성 필요'}
"""
    plan = f"""# 계획서

## 1. 추진 범위
{payload.scope or '- 작성 필요'}

## 2. 일정
- 마일스톤 문서에서 정의

## 3. 역할과 책임
- Team & AI에서 정의

## 4. 개발/운영 전략
{payload.description or '- 작성 필요'}

## 5. 리스크와 대응 / 제약조건
{payload.constraints or '- 작성 필요'}
"""
    for doc_type, content in (("proposal", proposal), ("plan", plan)):
        conn.execute(
            "UPDATE documents SET content=?,updated_by='Project Setup',updated_at=? WHERE project_id=? AND doc_type=?",
            (content, now(), project_id, doc_type),
        )


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
        note = str(link.get("note", "")).replace("|", "\|")
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


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.3.0"}


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
        add_activity(conn, pid, "project", "프로젝트가 생성되었습니다.")
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    return project


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
        return {
            "project": project,
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
def bridge_jobs(token: str = Query(...)):
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
async def bridge_result(payload: AIResult, token: str = Query(...)):
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
    key = websocket.query_params.get("key", "")
    if ACCESS_KEY and key != ACCESS_KEY:
        await websocket.close(code=4401)
        return
    await manager.connect(project_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(project_id, websocket)


init_db()
