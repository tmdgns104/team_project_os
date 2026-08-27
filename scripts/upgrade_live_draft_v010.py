from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


# --- app/main.py ---
p = Path('app/main.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
    'from app.conversation import build_interviewer_prompt, combine_proposals, merge_project_brief, normalize_ai_result',
    'from app.conversation import PROJECT_FIELDS, build_interviewer_prompt, combine_proposals, merge_project_brief, normalize_ai_result',
)
s = s.replace('app = FastAPI(title="Team Project OS", version="0.7.0")', 'app = FastAPI(title="Team Project OS", version="0.10.0")')
s = s.replace('return {"status": "ok", "version": "0.7.0"}', 'return {"status": "ok", "version": "0.10.0"}')

classes_marker = '''class ConversationApply(BaseModel):
    apply_project: bool = True
    apply_requirements: bool = True
    apply_decisions: bool = True
    apply_documents: bool = True


'''
classes_new = classes_marker + '''class DesignDraftCreate(BaseModel):
    member_name: str = Field(default="CMD User", max_length=120)
    provider: str = Field(default="codex", max_length=40)
    name_hint: str = Field(default="AI Design Draft", max_length=120)


class DesignDraftSync(BaseModel):
    member_name: str = Field(default="CMD User", max_length=120)
    state: dict[str, Any] = Field(default_factory=dict)


'''
if 'class DesignDraftCreate' not in s:
    s = replace_once(s, classes_marker, classes_new, 'DesignDraft classes')

projects_schema_old = '''            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );'''
projects_schema_new = '''            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                goal TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                lifecycle TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );'''
if projects_schema_old in s:
    s = s.replace(projects_schema_old, projects_schema_new, 1)

migration_marker = '''        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
'''
migration_new = '''        project_columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        if "lifecycle" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active'")
        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
'''
if 'ALTER TABLE projects ADD COLUMN lifecycle' not in s:
    s = replace_once(s, migration_marker, migration_new, 'projects lifecycle migration')

helper_marker = '''def derived_trace_links(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
'''
helper_code = r'''def _live_graph_markdown(title: str, design: dict[str, Any] | None) -> str:
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
    generated = build_initial_documents(brief)
    requirements = state.get("requirements", []) or []
    decisions = state.get("decisions", []) or []
    pending_items = state.get("pending", []) or []

    if requirements:
        lines = ["# 요구사항 정의서", "", "> AI Design Session Live Draft", "", "| ID | 요구사항 | 상세 | 상태 |", "|---|---|---|---|"]
        for item in requirements:
            lines.append(f"| {item.get('ref','')} | {str(item.get('title','')).replace('|','/')} | {str(item.get('detail','')).replace('|','/')} | {item.get('status','defined')} |")
        generated["requirements"] = "\n".join(lines) + "\n"

    if decisions or pending_items:
        plan = generated.get("plan", "# 계획서\n")
        plan += "\n## Live Decisions\n\n"
        if decisions:
            for item in decisions:
                status = str(item.get("status") or "accepted")
                plan += f"- [{status}] **{item.get('title','')}** — {item.get('body','')}\n"
        else:
            plan += "- 아직 결정 없음\n"
        if pending_items:
            plan += "\n## Pending / TBD\n\n"
            for item in pending_items:
                plan += f"- {item}\n"
        generated["plan"] = plan

    designs = {str(d.get("view")): d for d in (state.get("design_updates", []) or []) if d.get("view")}
    if "architecture" in designs:
        generated["system_architecture"] = _live_graph_markdown("시스템 구조도", designs["architecture"])
    if "dataflow" in designs:
        generated["data_flow"] = _live_graph_markdown("데이터 플로우", designs["dataflow"])
    if "process" in designs:
        process = _live_graph_markdown("System Process", designs["process"])
        generated["function_definition"] = "# 기능 정의서\n\n" + process.split("\n", 1)[1]

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


''' + helper_marker
if 'def apply_live_draft_state' not in s:
    s = replace_once(s, helper_marker, helper_code, 'live draft helpers')

endpoint_marker = '''@app.get("/api/projects", dependencies=[])
def projects'''
endpoint_code = r'''@app.post("/api/design-drafts")
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
def projects'''
if '@app.post("/api/design-drafts")' not in s:
    s = replace_once(s, endpoint_marker, endpoint_code, 'live draft endpoints')

p.write_text(s, encoding='utf-8')


# --- local_bridge/project_cli.py ---
p = Path('local_bridge/project_cli.py')
s = p.read_text(encoding='utf-8')
s = s.replace(
    '"명령: /status, /autofill on|off, /preview, /apply, /quit"',
    '"명령: /status, /autofill on|off, /preview, /apply, /discard, /quit"',
)

prompt_marker = '''- Continue the discussion from the full transcript below. Answer the latest USER turn.

TRANSCRIPT
{transcript}
"""
'''
prompt_new = '''- Continue the discussion from the full transcript below. Answer the latest USER turn.

LIVE DRAFT CONTRACT
After your normal Korean conversational answer, append exactly one machine-readable block:
<PROJECT_OS_DELTA>{"project_updates":{},"requirements":[],"decisions":[],"document_updates":[],"design_updates":[],"pending":[]}</PROJECT_OS_DELTA>
Rules for this block:
- Keep it compact. It is hidden from the user and synchronized to the web Live Draft.
- Include only meaningful structured facts or decisions that became clearer in this turn.
- project_updates may include only fields actually established or safely provisional under Autofill Mode.
- A USER-confirmed choice uses decision status "accepted".
- An AI-selected reversible default under Autofill Mode uses decision status "provisional".
- Never mark an AI suggestion as accepted unless the USER explicitly accepted it.
- requirements should contain stable ref/title/detail/status values when a requirement became clear.
- If a process/architecture/dataflow view meaningfully changes, include the COMPLETE current graph for that view in design_updates, not just the new node.
- Do not emit full documents unless a document body was explicitly drafted. The server will progressively regenerate core draft documents from the structured state.
- If nothing structured changed, emit an empty object inside the marker.
- Never mention this marker in the conversational answer.

TRANSCRIPT
{transcript}
"""
'''
if 'LIVE DRAFT CONTRACT' not in s:
    s = replace_once(s, prompt_marker, prompt_new, 'live delta prompt')

insert_marker = '''def build_distiller_prompt(messages: list[dict], autofill_mode: bool = False) -> str:
'''
live_helpers = r'''def blank_live_state() -> dict:
    return {
        "project_updates": {},
        "requirements": [],
        "decisions": [],
        "document_updates": [],
        "design_updates": [],
        "pending": [],
    }


def extract_live_delta(output: str) -> tuple[str, dict]:
    text = str(output or "")
    start = text.rfind("<PROJECT_OS_DELTA>")
    end = text.rfind("</PROJECT_OS_DELTA>")
    if start < 0 or end < start:
        return text.strip(), {}
    raw = text[start + len("<PROJECT_OS_DELTA>"):end].strip()
    visible = (text[:start] + text[end + len("</PROJECT_OS_DELTA>"):]).strip()
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = {}
    return visible, parsed if isinstance(parsed, dict) else {}


def _merge_by_key(existing: list[dict], incoming: list[dict], key_name: str) -> list[dict]:
    ordered: list[dict] = [dict(item) for item in existing]
    positions = {str(item.get(key_name) or "").strip().lower(): idx for idx, item in enumerate(ordered) if str(item.get(key_name) or "").strip()}
    for raw in incoming or []:
        item = dict(raw)
        key = str(item.get(key_name) or "").strip().lower()
        if not key:
            continue
        if key in positions:
            ordered[positions[key]] = item
        else:
            positions[key] = len(ordered)
            ordered.append(item)
    return ordered


def merge_live_state(state: dict, delta: dict) -> dict:
    merged = {
        "project_updates": dict(state.get("project_updates") or {}),
        "requirements": list(state.get("requirements") or []),
        "decisions": list(state.get("decisions") or []),
        "document_updates": list(state.get("document_updates") or []),
        "design_updates": list(state.get("design_updates") or []),
        "pending": list(state.get("pending") or []),
    }
    merged["project_updates"].update({k: v for k, v in (delta.get("project_updates") or {}).items() if str(v or "").strip()})
    merged["requirements"] = _merge_by_key(merged["requirements"], delta.get("requirements") or [], "ref")
    merged["decisions"] = _merge_by_key(merged["decisions"], delta.get("decisions") or [], "title")
    merged["document_updates"] = _merge_by_key(merged["document_updates"], delta.get("document_updates") or [], "doc_type")
    merged["design_updates"] = _merge_by_key(merged["design_updates"], delta.get("design_updates") or [], "view")
    seen = {str(x).strip() for x in merged["pending"] if str(x).strip()}
    for item in delta.get("pending") or []:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            merged["pending"].append(value)
    return merged


def create_live_draft(server: str, access_key: str, member: str, provider: str) -> dict:
    return http_json("POST", f"{server.rstrip('/')}/api/design-drafts", {
        "member_name": member,
        "provider": provider,
        "name_hint": "AI Design Draft",
    }, access_key)


def sync_live_draft(server: str, access_key: str, project_id: int, member: str, state: dict) -> dict:
    return http_json("PUT", f"{server.rstrip('/')}/api/design-drafts/{project_id}/sync", {
        "member_name": member,
        "state": state,
    }, access_key)


def promote_live_draft(server: str, access_key: str, project_id: int, member: str, state: dict) -> dict:
    result = http_json("POST", f"{server.rstrip('/')}/api/design-drafts/{project_id}/promote", {
        "member_name": member,
        "state": state,
    }, access_key)
    return result["project"]


def final_state_from_distillation(brief: dict, pending: dict) -> dict:
    return {
        "project_updates": dict(brief),
        "requirements": list(pending.get("requirements") or []),
        "decisions": list(pending.get("decisions") or []),
        "document_updates": list(pending.get("document_updates") or []),
        "design_updates": list(pending.get("design_updates") or []),
        "pending": list(pending.get("pending") or []),
    }


''' + insert_marker
if 'def extract_live_delta' not in s:
    s = replace_once(s, insert_marker, live_helpers, 'live state helpers')

save_old = '''def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None, autofill_mode: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "provider": provider,
        "member": member,
        "messages": messages,
        "applied_project": applied_project,
        "autofill_mode": autofill_mode,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
'''
save_new = '''def save_session(path: Path, *, provider: str, member: str, messages: list[dict], applied_project: dict | None = None, autofill_mode: bool = False, draft_project: dict | None = None, live_state: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "provider": provider,
        "member": member,
        "messages": messages,
        "applied_project": applied_project,
        "draft_project": draft_project,
        "live_state": live_state or blank_live_state(),
        "autofill_mode": autofill_mode,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
'''
if save_old in s:
    s = s.replace(save_old, save_new, 1)

status_old = '''def print_session_status(path: Path, provider: str, messages: list[dict], autofill_mode: bool = False) -> None:
'''
status_new = '''def print_session_status(path: Path, provider: str, messages: list[dict], autofill_mode: bool = False, draft_project: dict | None = None) -> None:
'''
s = s.replace(status_old, status_new, 1)
status_tail = '''    print(f"Autofill Mode: {'ON - 모르는 저위험 세부사항은 AI 임시 결정' if autofill_mode else 'OFF'}")
    print("/preview 또는 /apply 시점에만 전체 대화를 프로젝트 구조로 변환합니다.")
'''
status_tail_new = '''    print(f"Autofill Mode: {'ON - 모르는 저위험 세부사항은 AI 임시 결정' if autofill_mode else 'OFF'}")
    if draft_project:
        print(f"Live Draft: ID={draft_project.get('id')} · 웹에서 실시간 확인 가능")
        print("의미 있는 결정이 생긴 턴마다 Documents / Requirements / Decisions / Canvas가 자동 갱신됩니다.")
    else:
        print("Live Draft: OFF 또는 서버 연결 실패")
    print("/preview는 전체 구조 확인, /apply는 Live Draft를 정식 프로젝트로 승격합니다.")
'''
if status_tail in s:
    s = s.replace(status_tail, status_tail_new, 1)

init_old = '''    preview_cache: tuple[int, dict, dict] | None = None
    autofill_mode = bool(getattr(args, "autofill", False))

    print(WELCOME)
'''
init_new = '''    preview_cache: tuple[int, dict, dict] | None = None
    autofill_mode = bool(getattr(args, "autofill", False))
    live_state = blank_live_state()
    draft_project: dict | None = None
    if not bool(getattr(args, "no_live", False)):
        try:
            draft_project = create_live_draft(args.server, args.access_key, args.member, provider)
        except Exception as exc:
            print(f"Live Draft 연결 실패: {exc}")
            print("대화는 계속할 수 있지만 웹 실시간 시각화는 비활성화됩니다.")

    print(WELCOME)
'''
if init_old in s:
    s = s.replace(init_old, init_new, 1)

print_ai_marker = '''    print(f"AI: {provider} / 세션: {session_file}")
'''
print_ai_new = '''    print(f"AI: {provider} / 세션: {session_file}")
    if draft_project:
        print(f"Live Draft: ID={draft_project['id']} · {args.server.rstrip('/')} 에서 실시간 확인")
'''
s = s.replace(print_ai_marker, print_ai_new, 1)

# Replace common save_session calls in quit/interrupt with extra live state.
s = s.replace(
    'save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode)',
    'save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)',
)
s = s.replace('print_session_status(session_file, provider, messages, autofill_mode)', 'print_session_status(session_file, provider, messages, autofill_mode, draft_project)')

# Add /discard handler before autofill command.
discard_marker = '''        if command.startswith("/autofill"):
'''
discard_code = '''        if command == "/discard":
            if not draft_project:
                print("삭제할 Live Draft가 없습니다.")
                continue
            try:
                http_json("DELETE", f"{args.server.rstrip('/')}/api/design-drafts/{draft_project['id']}", None, args.access_key)
                print(f"Live Draft #{draft_project['id']} 삭제 완료")
                draft_project = None
                live_state = blank_live_state()
            except Exception as exc:
                print(f"Live Draft 삭제 실패: {exc}")
            continue
        if command.startswith("/autofill"):
'''
if 'if command == "/discard":' not in s:
    s = replace_once(s, discard_marker, discard_code, 'discard command')

apply_old = '''            try:
                project = apply_to_server(args.server, args.access_key, args.member, brief, pending)
            except Exception as exc:
                print(f"프로젝트 생성 실패: {exc}")
                continue
'''
apply_new = '''            try:
                final_state = final_state_from_distillation(brief, pending)
                if draft_project:
                    project = promote_live_draft(args.server, args.access_key, draft_project["id"], args.member, final_state)
                    live_state = final_state
                else:
                    project = apply_to_server(args.server, args.access_key, args.member, brief, pending)
            except Exception as exc:
                print(f"프로젝트 생성 실패: {exc}")
                continue
'''
if apply_old in s:
    s = s.replace(apply_old, apply_new, 1)

save_apply_old = '''                applied_project=project,
                autofill_mode=autofill_mode,
            )
'''
save_apply_new = '''                applied_project=project,
                autofill_mode=autofill_mode,
                draft_project=None,
                live_state=live_state,
            )
'''
if save_apply_old in s:
    s = s.replace(save_apply_old, save_apply_new, 1)

answer_old = '''        answer = result.stdout.strip()
        if not answer:
            messages.pop()
            print("\nAI 응답이 비어 있습니다.")
            continue
        messages.append({"role": "assistant", "content": answer})
        save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
        print(f"\n{provider}> {answer}")
'''
answer_new = '''        answer, live_delta = extract_live_delta(result.stdout)
        if not answer:
            messages.pop()
            print("\nAI 응답이 비어 있습니다.")
            continue
        messages.append({"role": "assistant", "content": answer})
        if live_delta:
            live_state = merge_live_state(live_state, live_delta)
            if draft_project:
                try:
                    synced = sync_live_draft(args.server, args.access_key, draft_project["id"], args.member, live_state)
                    draft_project = synced.get("project") or draft_project
                    print(f"\n[Live Draft] 웹 자동 업데이트 · Project #{draft_project['id']}")
                except Exception as exc:
                    print(f"\n[Live Draft] 동기화 실패: {exc}")
        save_session(session_file, provider=provider, member=args.member, messages=messages, autofill_mode=autofill_mode, draft_project=draft_project, live_state=live_state)
        print(f"\n{provider}> {answer}")
'''
if answer_old not in s:
    raise RuntimeError('answer handling marker not found')
s = s.replace(answer_old, answer_new, 1)

args_marker = '''    parser.add_argument("--autofill", action="store_true", help="모르는 저위험 세부사항을 AI가 PROVISIONAL로 임시 결정")
'''
args_new = args_marker + '''    parser.add_argument("--no-live", action="store_true", help="대화 중 웹 Live Draft 자동 동기화 비활성화")
'''
if '--no-live' not in s:
    s = replace_once(s, args_marker, args_new, 'no-live arg')

p.write_text(s, encoding='utf-8')


# --- app/static/app.js ---
p = Path('app/static/app.js')
s = p.read_text(encoding='utf-8')
s = s.replace("accepted:['승인','good']", "accepted:['승인','good'],provisional:['AI 임시','warn']")
s = s.replace(
    "select.innerHTML=state.projects.map(p=>`<option value=\"${p.id}\">${esc(p.name)}</option>`).join('');",
    "select.innerHTML=state.projects.map(p=>`<option value=\"${p.id}\">${p.lifecycle==='draft'?'🟡 설계중 · ':''}${esc(p.name)}</option>`).join('');",
)
s = s.replace(
    "state.ws.onmessage=()=>loadSnapshot().catch(()=>{});",
    "state.ws.onmessage=e=>{ let msg={}; try{msg=JSON.parse(e.data||'{}')}catch(_e){}; if(msg.scope==='live_draft') $('#liveText').textContent='Live Draft 자동 반영됨'; if(msg.scope==='live_draft_promoted') $('#liveText').textContent='정식 프로젝트로 승격됨'; loadSnapshot().catch(()=>{}); };",
)
render_old = '''  const fn={overview:renderOverview,definition:renderDefinition,assistant:renderAssistant,documents:renderDocuments,traceability:renderTraceability,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];
  $('#content').innerHTML=fn(); bindViewActions();
'''
render_new = '''  const fn={overview:renderOverview,definition:renderDefinition,assistant:renderAssistant,documents:renderDocuments,traceability:renderTraceability,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];
  const draftBanner=state.snapshot.project.lifecycle==='draft'?`<div class="notice" style="margin-bottom:16px"><strong>🟡 AI Design Live Draft</strong> · AI와 대화 중 결정되는 내용이 실시간 반영됩니다. <strong>/apply 전에는 정식 확정 프로젝트가 아닙니다.</strong><br><small>Documents · Requirements · Decisions · Process/Architecture/Data Flow가 WebSocket으로 자동 갱신됩니다.</small></div>`:'';
  $('#content').innerHTML=draftBanner+fn(); bindViewActions();
'''
if render_old in s:
    s = s.replace(render_old, render_new, 1)
p.write_text(s, encoding='utf-8')


# --- tests/test_live_design.py ---
Path('tests/test_live_design.py').write_text(r'''from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from local_bridge.project_cli import blank_live_state, extract_live_delta, merge_live_state, promote_live_draft, sync_live_draft


class LiveDeltaTests(unittest.TestCase):
    def test_extract_live_delta_hides_machine_block(self):
        raw = '좋습니다. SQLite로 임시 진행하겠습니다.\n<PROJECT_OS_DELTA>{"decisions":[{"title":"DB","body":"SQLite","status":"provisional"}]}</PROJECT_OS_DELTA>'
        answer, delta = extract_live_delta(raw)
        self.assertEqual(answer, '좋습니다. SQLite로 임시 진행하겠습니다.')
        self.assertEqual(delta['decisions'][0]['status'], 'provisional')

    def test_merge_live_state_is_incremental_and_idempotent(self):
        state = blank_live_state()
        state = merge_live_state(state, {
            'project_updates': {'name': 'HMI MES'},
            'requirements': [{'ref':'REQ-001','title':'수집','detail':'PLC','status':'defined'}],
            'decisions': [{'title':'DB','body':'SQLite','status':'provisional'}],
        })
        state = merge_live_state(state, {
            'project_updates': {'goal': '실시간 생산 현황 표시'},
            'requirements': [{'ref':'REQ-001','title':'PLC 데이터 수집','detail':'운전/수량','status':'defined'}],
            'decisions': [{'title':'DB','body':'SQLite for V1','status':'provisional'}],
        })
        self.assertEqual(state['project_updates']['name'], 'HMI MES')
        self.assertEqual(state['project_updates']['goal'], '실시간 생산 현황 표시')
        self.assertEqual(len(state['requirements']), 1)
        self.assertEqual(state['requirements'][0]['title'], 'PLC 데이터 수집')
        self.assertEqual(len(state['decisions']), 1)
        self.assertIn('V1', state['decisions'][0]['body'])


class LiveDraftApiTests(unittest.TestCase):
    def test_live_draft_sync_updates_web_state_then_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ['PROJECT_OS_DB'] = os.path.join(td, 'live.db')
            from app import main as app_main
            app_main.DB_PATH = app_main.Path(os.environ['PROJECT_OS_DB'])
            app_main.SEED_DEMO = False
            app_main.init_db()
            with TestClient(app_main.app) as client:
                draft = client.post('/api/design-drafts', json={'member_name':'tester','provider':'codex','name_hint':'AI Design Draft'}).json()
                self.assertEqual(draft['lifecycle'], 'draft')

                state = {
                    'project_updates': {'name':'HMI MES Live','goal':'PLC 생산 데이터를 HMI/MES에서 실시간 표시','project_type':'manufacturing_automation'},
                    'requirements': [{'ref':'REQ-001','title':'PLC 데이터 수집','detail':'운전/수량/불량','status':'defined'}],
                    'decisions': [{'title':'V1 DB','body':'SQLite를 임시 사용','status':'provisional'}],
                    'document_updates': [],
                    'design_updates': [{
                        'view':'architecture','mode':'replace','nodes':[
                            {'key':'plc','label':'Mitsubishi PLC','kind':'device','detail':'user confirmed'},
                            {'key':'api','label':'FastAPI Gateway','kind':'service','detail':'AI provisional'},
                            {'key':'db','label':'SQLite','kind':'store','detail':'AI provisional'}],
                        'edges':[{'source':'plc','target':'api','label':'PLC Data'},{'source':'api','target':'db','label':'Record'}]
                    }],
                    'pending':['실제 PLC 통신 방식'],
                }
                r = client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'tester','state':state})
                self.assertEqual(r.status_code, 200)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(snap['project']['lifecycle'], 'draft')
                self.assertEqual(snap['project']['name'], 'HMI MES Live')
                self.assertEqual(len(snap['requirements']), 1)
                self.assertEqual(len(snap['decisions']), 1)
                self.assertEqual(snap['decisions'][0]['status'], 'provisional')
                self.assertEqual(len([n for n in snap['nodes'] if n['view']=='architecture']), 3)
                proposal = next(d for d in snap['documents'] if d['doc_type']=='proposal')
                self.assertIn('PLC 생산 데이터를', proposal['content'])
                plan = next(d for d in snap['documents'] if d['doc_type']=='plan')
                self.assertIn('SQLite', plan['content'])

                state['requirements'].append({'ref':'REQ-002','title':'생산 실적 조회','detail':'시간별 조회','status':'defined'})
                state['decisions'].append({'title':'PLC 계열','body':'Mitsubishi 사용','status':'accepted'})
                client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'tester','state':state})
                snap2 = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(len(snap2['requirements']), 2)
                self.assertEqual(len(snap2['decisions']), 2)

                promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={'member_name':'tester','state':state}).json()['project']
                self.assertEqual(promoted['lifecycle'], 'active')
                final = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(final['project']['lifecycle'], 'active')
                self.assertEqual(final['project']['name'], 'HMI MES Live')


if __name__ == '__main__':
    unittest.main()
''', encoding='utf-8')


# --- tools/simulate_live_design.py ---
Path('tools/simulate_live_design.py').write_text(r'''from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def check(name: str, value: bool) -> None:
    print(f"[LIVE SIM] {name}: {'PASS' if value else 'FAIL'}")
    if not value:
        raise SystemExit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ['PROJECT_OS_DB'] = str(Path(td) / 'live-sim.db')
        from app import main as app_main
        app_main.DB_PATH = Path(os.environ['PROJECT_OS_DB'])
        app_main.SEED_DEMO = False
        app_main.init_db()
        with TestClient(app_main.app) as client:
            draft = client.post('/api/design-drafts', json={'member_name':'sim-user','provider':'codex','name_hint':'AI Design Draft'}).json()
            check('draft_created', draft.get('lifecycle') == 'draft')

            turns = [
                {
                    'project_updates': {'name':'HMI MES Live Simulator','goal':'작은 컨베이어 생산라인의 상태와 실적을 HMI/MES에서 확인한다','project_type':'manufacturing_automation'},
                    'requirements': [{'ref':'REQ-001','title':'PLC 상태 수집','detail':'운전 상태를 수집한다','status':'defined'}],
                    'decisions': [{'title':'PLC 계열','body':'Mitsubishi PLC','status':'accepted'}],
                    'document_updates': [], 'design_updates': [], 'pending': []
                },
                {
                    'project_updates': {'name':'HMI MES Live Simulator','goal':'작은 컨베이어 생산라인의 상태와 실적을 HMI/MES에서 확인한다','project_type':'manufacturing_automation','scope':'시뮬레이터 우선 V1'},
                    'requirements': [
                        {'ref':'REQ-001','title':'PLC 상태 수집','detail':'운전 상태를 수집한다','status':'defined'},
                        {'ref':'REQ-002','title':'생산 실적 저장','detail':'생산/불량 수량을 저장한다','status':'defined'}],
                    'decisions': [
                        {'title':'PLC 계열','body':'Mitsubishi PLC','status':'accepted'},
                        {'title':'V1 DB','body':'SQLite를 AI 임시 결정으로 사용','status':'provisional'}],
                    'document_updates': [],
                    'design_updates': [{
                        'view':'process','mode':'replace',
                        'nodes':[{'key':'plc','label':'PLC 감지','kind':'step'},{'key':'collect','label':'데이터 수집','kind':'step'},{'key':'save','label':'실적 저장','kind':'step'}],
                        'edges':[{'source':'plc','target':'collect','label':'status'},{'source':'collect','target':'save','label':'record'}]
                    }],
                    'pending':['실제 PLC 통신 방식']
                }
            ]
            for idx, state in enumerate(turns, 1):
                result = client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'sim-user','state':state})
                check(f'turn_{idx}_sync', result.status_code == 200)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                print(f"[LIVE SIM] turn={idx} docs_updated_by={next(d for d in snap['documents'] if d['doc_type']=='plan')['updated_by']} req={len(snap['requirements'])} decisions={len(snap['decisions'])} nodes={len(snap['nodes'])}")

            final_snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check('documents_live', 'SQLite' in next(d for d in final_snap['documents'] if d['doc_type']=='plan')['content'])
            check('requirements_live', len(final_snap['requirements']) == 2)
            check('provisional_visible', any(d['status']=='provisional' for d in final_snap['decisions']))
            check('process_canvas_live', len([n for n in final_snap['nodes'] if n['view']=='process']) == 3)

            promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={'member_name':'sim-user','state':turns[-1]}).json()['project']
            check('promoted_to_active', promoted.get('lifecycle') == 'active')
            print(f"[LIVE SIM] PROJECT PROMOTED: ID={promoted['id']} name={promoted['name']}")
            print('[LIVE SIM] LIVE DESIGN DRAFT E2E: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
''', encoding='utf-8')


# --- CI ---
p = Path('.github/workflows/ci.yml')
s = p.read_text(encoding='utf-8')
s = s.replace('tools/simulate_design_session.py tools/simulate_autofill_project.py', 'tools/simulate_design_session.py tools/simulate_autofill_project.py tools/simulate_live_design.py')
if 'Live Design Draft simulator' not in s:
    s = s.replace('''      - name: Provisional Autofill materialization simulator
        run: python tools/simulate_autofill_project.py
''', '''      - name: Provisional Autofill materialization simulator
        run: python tools/simulate_autofill_project.py
      - name: Live Design Draft simulator
        run: python tools/simulate_live_design.py
''')
p.write_text(s, encoding='utf-8')


# --- README ---
p = Path('README.md')
s = p.read_text(encoding='utf-8')
s = s.replace('# Team Project OS V0.9', '# Team Project OS V0.10', 1)
anchor = '## 핵심 흐름\n'
if '## V0.10 Live Design Draft' not in s:
    live_section = '''## V0.10 Live Design Draft\n\nAI Design Session을 오래 진행해도 웹이 빈 상태로 기다리지 않습니다. 세션 시작 시 `lifecycle=draft`인 Live Draft가 생성되고, **같은 AI 응답 안의 작은 구조화 delta**를 이용해 의미 있는 결정이 생긴 턴마다 웹을 즉시 갱신합니다. 추가 AI 호출을 만들지 않으므로 기존 대화 속도를 최대한 유지합니다.\n\n```text\nAI와 대화\n  ↓\n같은 응답의 숨은 PROJECT_OS_DELTA\n  ↓\nLive Draft Sync\n  ↓\nWebSocket\n  ↓\nDocuments / Requirements / Decisions / Canvas 즉시 갱신\n  ↓\n/apply\n  ↓\n같은 Draft를 정식 active 프로젝트로 승격\n```\n\n웹의 프로젝트 선택 목록에는 `🟡 설계중`으로 표시되며 `/apply` 전까지 정식 확정본이 아닙니다. `/discard`로 Live Draft만 삭제할 수 있고, `--no-live`로 이전처럼 웹 실시간 동기화를 끌 수도 있습니다.\n\n'''
    s = s.replace(anchor, live_section + anchor, 1)
s = s.replace('Team Project OS V0.9에서는', 'Team Project OS V0.10에서는')
s = s.replace('Provisional Autofill 실제 생성 시뮬레이터:\n\n```bat\npython tools\\simulate_autofill_project.py\n```', 'Provisional Autofill 실제 생성 시뮬레이터:\n\n```bat\npython tools\\simulate_autofill_project.py\n```\n\nLive Design Draft 실시간 동기화 시뮬레이터:\n\n```bat\npython tools\\simulate_live_design.py\n```')
p.write_text(s, encoding='utf-8')

# --- docs/LIVE_DRAFT.md ---
Path('docs/LIVE_DRAFT.md').write_text('''# Live Design Draft (V0.10)\n\nAI와 프로젝트를 오래 설계할 때 `/apply`까지 웹이 기다리지 않도록 하는 실시간 Draft 기능입니다.\n\n## 동작 원리\n\nDesign Session 시작 시 `lifecycle=draft` 프로젝트가 하나 생성됩니다. AI는 일반 대화 답변과 함께 숨은 `PROJECT_OS_DELTA`를 반환하고 CLI는 이 블록만 분리해 서버에 동기화합니다. 추가 Distiller 호출은 하지 않습니다.\n\n의미 있는 결정이 생긴 턴마다 다음이 실시간으로 바뀔 수 있습니다.\n\n- Project Brief / Goal\n- Requirements\n- `accepted` / `provisional` Decisions\n- 기획서 / 계획서 / 요구사항 정의서\n- 시스템 구조도 / 데이터 플로우 / 기능 정의서의 Live Draft 부분\n- System Process / Architecture / Data Flow Canvas\n\n서버는 동기화 후 WebSocket refresh를 보내므로 같은 Draft를 보고 있는 브라우저는 자동으로 최신 Snapshot을 다시 읽습니다.\n\n## 승인 경계\n\nLive Draft는 정식 프로젝트와 구분됩니다.\n\n```text\nlifecycle=draft\n= 설계 중, 자동 갱신 가능\n\n/apply\n= 전체 대화를 마지막으로 Distill\n= 같은 프로젝트를 lifecycle=active로 승격\n```\n\n따라서 실시간 시각화와 Human Gate를 동시에 유지합니다.\n\n## 명령\n\n```text\n/status      Live Draft ID와 Autofill 상태 확인\n/preview     전체 대화 기반 최종 구조 미리보기\n/apply       Live Draft를 정식 프로젝트로 승격\n/discard     현재 Live Draft 삭제\n/quit        세션 저장 후 종료 (Draft는 유지)\n```\n\n실시간 동기화를 끄려면:\n\n```bat\npython project_os.py design --provider codex --no-live\n```\n\n## 성능 원칙\n\n매 턴 별도 Distiller를 호출하지 않습니다. 기존 AI 응답 한 번에 conversational answer와 compact delta를 같이 받아 네트워크 동기화만 추가합니다.\n\n## 검증\n\n```bat\npython tools\\simulate_live_design.py\n```\n\n시뮬레이터는 두 번의 설계 턴을 서버에 순차 반영하고 문서/요구사항/Decision/Canvas가 중간 상태에서 실제로 바뀌는지 확인한 뒤 `/apply`에 해당하는 Draft 승격까지 검증합니다.\n''', encoding='utf-8')

# DESIGN_SESSION add live reference
p = Path('docs/DESIGN_SESSION.md')
s = p.read_text(encoding='utf-8')
s = s.replace('Team Project OS V0.9의 권장 프로젝트 시작 방식', 'Team Project OS V0.10의 권장 프로젝트 시작 방식', 1)
if 'Live Draft' not in s.split('---', 1)[0]:
    s = s.replace('대화 중에는 Project OS의 프로젝트/문서/Canvas를 변경하지 않습니다.', '대화 중에는 정식 Source of Truth를 확정 변경하지 않습니다. 대신 V0.10에서는 `lifecycle=draft`인 **Live Draft**가 만들어지고, 의미 있는 결정이 생긴 턴마다 Documents / Requirements / Decisions / Canvas가 웹에서 실시간 갱신됩니다. `/apply` 시 같은 Draft를 정식 프로젝트로 승격합니다. 자세한 내용은 `LIVE_DRAFT.md`를 참고하세요.\n\nAI는 이 단계에서 일반 대화로 문제, 목표, 사용자, 범위, 기능, Process, Architecture, Data Flow, 일정, 리스크, 테스트 방법을 함께 구체화합니다.', 1)
p.write_text(s, encoding='utf-8')

print('V0.10 live design draft upgrade prepared')
