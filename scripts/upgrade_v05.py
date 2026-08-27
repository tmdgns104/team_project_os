from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


# ----------------------------- backend -----------------------------
main = Path("app/main.py")
s = main.read_text(encoding="utf-8")

imports = "from app.project_intake import build_initial_documents, evaluate_intake, intake_metadata\n"
conv_imports = imports + "from app.conversation import build_interviewer_prompt, combine_proposals, merge_project_brief, normalize_ai_result\n"
if "from app.conversation import" not in s:
    s = replace_once(s, imports, conv_imports, "conversation import")
s = s.replace('version="0.4.0"', 'version="0.5.0"')
s = s.replace('"version": "0.4.0"', '"version": "0.5.0"')

model_marker = '''class TraceLinkCreate(BaseModel):
    source_type: str = Field(min_length=2, max_length=60)
    source_ref: str = Field(min_length=1, max_length=160)
    target_type: str = Field(min_length=2, max_length=60)
    target_ref: str = Field(min_length=1, max_length=160)
    relation: str = Field(default="relates_to", max_length=80)
    note: str = Field(default="", max_length=2000)
    created_by: str = Field(default="Team member", max_length=120)
'''
models = model_marker + '''\n\nclass AssistantBridgeRegister(BaseModel):
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
'''
if "class ConversationStart" not in s:
    s = replace_once(s, model_marker, models, "conversation models")

old_tables = '''            CREATE TABLE IF NOT EXISTS trace_links (
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
'''
new_tables = '''            CREATE TABLE IF NOT EXISTS trace_links (
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
'''
if "CREATE TABLE IF NOT EXISTS conversation_sessions" not in s:
    s = replace_once(s, old_tables, new_tables, "conversation tables")

old_init_tail = '''        for project_row in conn.execute("SELECT id FROM projects"):
            ensure_project_documents(conn, project_row["id"])
'''
new_init_tail = '''        for project_row in conn.execute("SELECT id FROM projects"):
            ensure_project_documents(conn, project_row["id"])
            ensure_project_brief(conn, project_row["id"])
'''
s = replace_once(s, old_init_tail, new_init_tail, "brief migration")

helper_marker = '''def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
    generated = build_initial_documents(payload.model_dump())
    for doc_type, content in generated.items():
        conn.execute(
            "UPDATE documents SET content=?,updated_by='Project Setup',updated_at=? WHERE project_id=? AND doc_type=?",
            (content, now(), project_id, doc_type),
        )
'''
helpers = '''def ensure_project_brief(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
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


def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
    data = payload.model_dump()
    save_project_brief(conn, project_id, data)
    generated = build_initial_documents(data)
    for doc_type, content in generated.items():
        conn.execute(
            "UPDATE documents SET content=?,updated_by='Project Setup',updated_at=? WHERE project_id=? AND doc_type=?",
            (content, now(), project_id, doc_type),
        )
'''
s = replace_once(s, helper_marker, helpers, "project brief helpers")

# Add snapshot fields.
snapshot_marker = '''        return {
            "project": project,
            "requirements": [dict(r) for r in conn.execute("SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,))],
'''
snapshot_new = '''        project_brief = ensure_project_brief(conn, project_id)
        conversation = conversation_snapshot(conn, project_id)
        return {
            "project": project,
            "project_brief": project_brief,
            "conversation": conversation,
            "requirements": [dict(r) for r in conn.execute("SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,))],
'''
s = replace_once(s, snapshot_marker, snapshot_new, "snapshot conversation fields")

# Add conversational API before normal project list endpoint.
api_marker = '@app.get("/api/projects", dependencies=[])\n'
conversation_api = r'''@app.post("/api/assistant-bridges/register")
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
def assistant_bridge_jobs(token: str = Query(...)):
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
async def assistant_bridge_result(payload: ConversationBridgeResult, token: str = Query(...)):
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

        conn.execute("UPDATE conversation_sessions SET pending_json='{}',updated_at=? WHERE id=?", (now(), session_id))
        add_activity(conn, pid, "conversation", f"대화 제안 {applied}개를 프로젝트에 적용", session["member_name"])
        quality = evaluate_intake(ensure_project_brief(conn, pid))
    await manager.broadcast(pid, {"type": "refresh", "scope": "conversation"})
    return {"ok": True, "applied": applied, "quality": quality}


'''
if "/api/conversations/start" not in s:
    s = replace_once(s, api_marker, conversation_api + api_marker, "conversation endpoints")

main.write_text(s, encoding="utf-8")

# ----------------------------- local bridge -----------------------------
bridge = Path("local_bridge/bridge.py")
b = bridge.read_text(encoding="utf-8")

register_marker = '''def submit_result(cfg, job_id: int, status: str, output: str, evidence: str):
'''
assistant_functions = r'''def assistant_register(args):
    access_headers = {"X-Access-Key": args.access_key} if args.access_key else {}
    data = http_json(
        "POST",
        f"{args.server.rstrip('/')}/api/assistant-bridges/register",
        {"member_name": args.member, "provider": args.provider, "machine_name": platform.node() or "local"},
        access_headers,
    )
    cfg = load_config()
    cfg.update({
        "assistant_server": args.server.rstrip('/'),
        "assistant_member": args.member,
        "assistant_provider": args.provider,
        "assistant_token": data["token"],
        "assistant_access_key": args.access_key or "",
        "assistant_command": args.command or "",
    })
    save_config(cfg)
    print(f"AI Project Assistant paired: {args.member} / {args.provider}")
    print(f"Config saved: {CONFIG_PATH}")
    print("Next: python local_bridge/bridge.py assistant-run --once")


def assistant_submit_result(cfg: dict, job_id: int, status: str, output: str):
    q = urlencode({"token": cfg["assistant_token"]})
    http_json("POST", f"{cfg['assistant_server']}/api/assistant-bridge/results?{q}", {
        "job_id": job_id, "status": status, "output": output
    })


def assistant_run_once(cfg: dict, cwd: Path, custom_command: str | None = None) -> bool:
    q = urlencode({"token": cfg["assistant_token"]})
    bundle = http_json("GET", f"{cfg['assistant_server']}/api/assistant-bridge/jobs?{q}")
    if not bundle or not bundle.get("job"):
        print("No queued Project Assistant message.")
        return False
    job = bundle["job"]
    prompt = bundle["prompt"]
    provider = cfg["assistant_provider"]
    cmd = provider_command(provider, prompt, custom_command or cfg.get("assistant_command") or None)
    print(f"Claimed Project Assistant Job #{job['id']} / {provider}")
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60 * 45)
        output = (result.stdout or "") + ("\nSTDERR:\n" + result.stderr if result.stderr else "")
        status = "completed" if result.returncode == 0 else "failed"
        assistant_submit_result(cfg, job["id"], status, output)
        print(f"Assistant Job #{job['id']} -> {status}")
        return True
    except Exception as exc:
        assistant_submit_result(cfg, job["id"], "failed", str(exc))
        raise


def assistant_run(args):
    cfg = load_config()
    required = ["assistant_server", "assistant_token", "assistant_provider"]
    if any(not cfg.get(k) for k in required):
        raise RuntimeError("Project Assistant is not paired. Run assistant-register first.")
    cwd = Path(args.cwd or ".").expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise RuntimeError(f"Working directory not found: {cwd}")
    if args.once:
        assistant_run_once(cfg, cwd, args.command)
        return
    print(f"Watching AI Project Assistant every {args.poll}s. Ctrl+C to stop.")
    while True:
        try:
            ran = assistant_run_once(cfg, cwd, args.command)
            time.sleep(1 if ran else args.poll)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"Assistant bridge error: {exc}", file=sys.stderr)
            time.sleep(args.poll)


'''
if "def assistant_register" not in b:
    b = replace_once(b, register_marker, assistant_functions + register_marker, "assistant bridge functions")

main_parser_marker = '''    r.set_defaults(func=register)
    runp = sub.add_parser("run", help="Fetch and execute queued tasks")
'''
main_parser_new = '''    r.set_defaults(func=register)
    ar = sub.add_parser("assistant-register", help="Pair this machine/provider once for conversational project setup")
    ar.add_argument("--server", required=True)
    ar.add_argument("--member", required=True)
    ar.add_argument("--provider", required=True, choices=["codex", "claude", "opencode", "antigravity", "dry-run"])
    ar.add_argument("--access-key", default="")
    ar.add_argument("--command", default="", help="Optional custom CLI template; {prompt} may be used")
    ar.set_defaults(func=assistant_register)
    arp = sub.add_parser("assistant-run", help="Fetch and answer conversational Project Assistant messages")
    arp.add_argument("--cwd", default=".")
    arp.add_argument("--once", action="store_true")
    arp.add_argument("--poll", type=int, default=5)
    arp.add_argument("--command", default="")
    arp.set_defaults(func=assistant_run)
    runp = sub.add_parser("run", help="Fetch and execute queued tasks")
'''
if "assistant-register" not in b:
    b = replace_once(b, main_parser_marker, main_parser_new, "assistant parser")
bridge.write_text(b, encoding="utf-8")

# ----------------------------- HTML -----------------------------
html = Path("app/static/index.html")
h = html.read_text(encoding="utf-8")
nav_marker = '        <button class="nav-item" data-view="definition">◎ <span>Goal & Requirements</span></button>\n'
if 'data-view="assistant"' not in h:
    h = replace_once(h, nav_marker, nav_marker + '        <button class="nav-item" data-view="assistant">✦ <span>AI Project Assistant</span></button>\n', "assistant nav")
button_marker = '          <button id="newProjectBtn" class="ghost-btn">+ 새 프로젝트</button>\n'
if 'id="aiStartBtn"' not in h:
    h = replace_once(h, button_marker, '          <button id="aiStartBtn" class="primary-btn">✦ AI와 새 프로젝트</button>\n' + button_marker, "assistant top button")
html.write_text(h, encoding="utf-8")

# ----------------------------- JS -----------------------------
js = Path("app/static/app.js")
j = js.read_text(encoding="utf-8")
j = j.replace("overview:'Overview', definition:'Goal & Requirements', documents:'Project Documents'", "overview:'Overview', definition:'Goal & Requirements', assistant:'AI Project Assistant', documents:'Project Documents'")
if "$('#aiStartBtn').addEventListener" not in j:
    j = replace_once(j, "  $('#newProjectBtn').addEventListener('click', newProject);\n", "  $('#newProjectBtn').addEventListener('click', newProject);\n  $('#aiStartBtn').addEventListener('click', ()=>startAIProject(false));\n", "AI start listener")

old_empty = "  if(!state.snapshot){ $('#content').innerHTML='<div class=\"panel onboarding\"><h2>새 프로젝트를 시작하세요</h2><p class=\"muted\">기획부터 설계, 개발, QA까지 팀이 같은 Workspace에서 진행할 수 있습니다.</p><button class=\"primary-btn\" data-action=\"new-project\">+ 프로젝트 생성</button></div>'; bindViewActions(); return; }"
new_empty = "  if(!state.snapshot){ $('#content').innerHTML='<div class=\"panel onboarding\"><h2>새 프로젝트를 시작하세요</h2><p class=\"muted\">AI가 있으면 대화만으로 시작하고, 없으면 직접 입력할 수 있습니다.</p><div class=\"onboarding-actions\"><button class=\"primary-btn\" data-action=\"start-ai-project\">✦ AI와 대화하며 시작</button><button class=\"ghost-btn\" data-action=\"new-project\">직접 입력해서 시작</button></div></div>'; bindViewActions(); return; }"
j = replace_once(j, old_empty, new_empty, "empty onboarding")

old_map = "  const fn={overview:renderOverview,definition:renderDefinition,documents:renderDocuments,traceability:renderTraceability,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];"
new_map = "  const fn={overview:renderOverview,definition:renderDefinition,assistant:renderAssistant,documents:renderDocuments,traceability:renderTraceability,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];"
j = replace_once(j, old_map, new_map, "assistant render map")

insert_before = "function renderDocuments(){\n"
assistant_ui = r'''function renderAssistant(){
  const s=state.snapshot; const conv=s.conversation;
  if(!conv){
    return `<div class="panel onboarding"><div class="eyebrow">CONVERSATIONAL PROJECT SETUP</div><h2>이 프로젝트를 AI와 대화하며 정리</h2><p class="muted">Codex, Claude Code, OpenCode, Antigravity CLI 중 자신의 AI를 연결할 수 있습니다. AI가 제안한 내용은 승인 전까지 프로젝트에 적용되지 않습니다.</p><button class="primary-btn" data-action="start-assistant-current">✦ AI Project Interviewer 시작</button></div>`;
  }
  const session=conv.session, pending=conv.pending||{}, updates=pending.project_updates||{}, quality=conv.quality||{};
  const fields=Object.entries(s.project_brief||{});
  const hasPending=Object.keys(updates).length || (pending.requirements||[]).length || (pending.decisions||[]).length || (pending.document_updates||[]).length;
  const messages=(conv.messages||[]).map(m=>`<div class="chat-message ${m.role==='user'?'user':'assistant'}"><div class="chat-role">${m.role==='user'?'나':'AI Project Interviewer'}</div><div>${esc(m.content).replace(/\n/g,'<br>')}</div></div>`).join('');
  const proposalRows=Object.entries(updates).map(([k,v])=>`<div class="proposal-row"><strong>${esc(k)}</strong><span>${esc(v)}</span></div>`).join('');
  const reqs=(pending.requirements||[]).map(r=>`<div class="proposal-row"><strong>${esc(r.ref||'REQ')} ${esc(r.title)}</strong><span>${esc(r.detail||'')}</span></div>`).join('');
  const decisions=(pending.decisions||[]).map(d=>`<div class="proposal-row"><strong>Decision · ${esc(d.title)}</strong><span>${esc(d.body||'')}</span></div>`).join('');
  const docs=(pending.document_updates||[]).map(d=>`<div class="proposal-row"><strong>Document · ${esc(d.doc_type)}</strong><span>${esc(d.reason||'문서 수정 제안')}</span></div>`).join('');
  const missing=fields.filter(([k,v])=>!String(v||'').trim()).slice(0,8).map(([k])=>`<span class="chip">${esc(k)} 미정</span>`).join(' ');
  const bridge=conv.bridge;
  const latestJob=(conv.jobs||[])[0];
  return `<div class="assistant-layout">
    <div class="panel assistant-chat">
      <div class="assistant-head"><div><div class="eyebrow">${esc(session.provider)} · ${esc(session.member_name)}</div><h2>AI와 프로젝트 정의</h2></div>${latestJob?statusChip(latestJob.status):''}</div>
      <div class="chat-messages" id="chatMessages">${messages}</div>
      <form id="conversationForm" class="chat-input"><textarea name="message" placeholder="편하게 말하세요. 예: 공장에서 수작업으로 하던 검사를 자동화하고 싶어" required></textarea><button class="primary-btn" type="submit">전송</button></form>
      <small class="muted">AI는 답변과 변경 제안만 생성합니다. 아래 '제안 적용' 전에는 프로젝트 문서/요구사항을 확정 변경하지 않습니다.</small>
    </div>
    <div class="assistant-side">
      <div class="panel"><div class="eyebrow">PROJECT DEFINITION</div><h3>정의 품질 ${quality.score??0}점</h3><div class="progress-track"><div class="progress-fill" style="width:${quality.score??0}%"></div></div><div class="missing-fields">${missing||'<span class="chip good">핵심 정의 충실</span>'}</div></div>
      <div class="panel"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><h3>AI 변경 제안</h3>${hasPending?'<button class="primary-btn" data-action="apply-conversation">제안 적용</button>':''}</div>${hasPending?(proposalRows+reqs+decisions+docs):'<div class="empty">아직 적용 대기 중인 제안이 없습니다.</div>'}${(pending.pending||[]).length?`<div class="notice"><strong>아직 미정</strong><ul>${pending.pending.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}</div>
      <div class="panel"><h3>Local AI Connector</h3>${bridge?`<div class="notice">✓ ${esc(bridge.member_name)} / ${esc(bridge.provider)} 연결됨<br><small>${esc(bridge.machine_name)} · ${new Date(bridge.last_seen).toLocaleString('ko-KR')}</small></div>`:'<div class="notice">이 AI 계정의 Connector가 아직 감지되지 않았습니다.</div>'}<button class="ghost-btn" data-action="assistant-pair-help">연결 명령 보기</button></div>
    </div>
  </div>`;
}

'''
if "function renderAssistant(){" not in j:
    j = replace_once(j, insert_before, assistant_ui + insert_before, "assistant UI")

bind_marker = "  const commentForm=$('#documentCommentForm'); if(commentForm) commentForm.addEventListener('submit',submitDocumentComment);\n"
if "conversationForm" not in j[j.index("function bindViewActions"):j.index("function closeModal")]:
    j = replace_once(j, bind_marker, bind_marker + "  const conversationForm=$('#conversationForm'); if(conversationForm) conversationForm.addEventListener('submit',submitConversationMessage);\n  const chat=$('#chatMessages'); if(chat) chat.scrollTop=chat.scrollHeight;\n", "conversation bindings")

open_add_old = "function openAddForView(){ handleAction({overview:'add-task',definition:'add-requirement',documents:'document-help',traceability:'add-trace-link',progress:'add-task',process:'add-node',architecture:'add-node',dataflow:'add-node',ideas:'add-idea',team:'add-member'}[state.view],['process','architecture','dataflow'].includes(state.view)?state.view:null); }"
open_add_new = "function openAddForView(){ handleAction({overview:'add-task',definition:'add-requirement',assistant:'start-assistant-current',documents:'document-help',traceability:'add-trace-link',progress:'add-task',process:'add-node',architecture:'add-node',dataflow:'add-node',ideas:'add-idea',team:'add-member'}[state.view],['process','architecture','dataflow'].includes(state.view)?state.view:null); }"
j = replace_once(j, open_add_old, open_add_new, "assistant add mapping")

handle_old = "  if(action==='new-project') return newProject(); if(action==='add-task') return addTask(); if(action==='add-requirement') return addRequirement(); if(action==='edit-goal') return editGoal();\n"
handle_new = "  if(action==='new-project') return newProject(); if(action==='start-ai-project') return startAIProject(false); if(action==='start-assistant-current') return startAIProject(true); if(action==='apply-conversation') return applyConversation(); if(action==='assistant-pair-help') return assistantPairHelp(); if(action==='add-task') return addTask(); if(action==='add-requirement') return addRequirement(); if(action==='edit-goal') return editGoal();\n"
j = replace_once(j, handle_old, handle_new, "assistant actions")

new_project_marker = "function newProject(){\n"
assistant_functions_js = r'''function startAIProject(useCurrent=false){
  const providers=[['codex','Codex'],['claude','Claude Code'],['opencode','OpenCode'],['antigravity','Antigravity CLI']];
  openModal(useCurrent?'이 프로젝트에서 AI 대화 시작':'AI와 새 프로젝트 시작',
    `<div class="notice">프로젝트 내용을 폼으로 작성할 필요가 없습니다. 자신의 AI Provider와 이름만 선택한 뒤, 다음 화면에서 AI에게 만들고 싶은 프로젝트를 말하면 됩니다.</div>`+
    field('member_name','내 이름','Team member')+selectField('provider','사용할 개인 AI',providers,'codex'),async fd=>{
      const data=Object.fromEntries(fd); if(useCurrent) data.project_id=state.projectId;
      const started=await api('/api/conversations/start',{method:'POST',body:JSON.stringify(data)});
      state.projectId=started.project.id; await loadProjects(); connectWs(); state.view='assistant';
      document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.view==='assistant')); $('#pageTitle').textContent=titles.assistant;
    });
}

async function submitConversationMessage(e){
  e.preventDefault(); const fd=new FormData(e.currentTarget); const message=String(fd.get('message')||'').trim(); if(!message)return;
  const sid=state.snapshot.conversation?.session?.id; if(!sid)return;
  await api(`/api/conversations/${sid}/messages`,{method:'POST',body:JSON.stringify({message})}); e.currentTarget.reset(); await loadSnapshot(); toast('AI에 전달했습니다. Connector가 응답하면 자동으로 갱신됩니다.');
}

async function applyConversation(){
  const sid=state.snapshot.conversation?.session?.id; if(!sid)return;
  const result=await api(`/api/conversations/${sid}/apply`,{method:'POST',body:JSON.stringify({})}); await loadProjects(); await loadSnapshot(); toast(`${result.applied}개 제안을 적용했습니다. 정의 품질 ${result.quality.score}점`);
}

function assistantPairHelp(){
  const c=state.snapshot.conversation; if(!c)return;
  const member=c.session.member_name, provider=c.session.provider;
  const access=state.accessKey?` --access-key "${state.accessKey}"`:'';
  const register=`python local_bridge/bridge.py assistant-register --server ${location.origin} --member "${member}" --provider ${provider}${access}`;
  const run=`python local_bridge/bridge.py assistant-run`;
  openModal('AI Project Assistant Connector',`<div class="notice">프로젝트별로 다시 등록할 필요가 없습니다. 이 서버에 내 AI를 한 번 Pair하면 이후 대화형 프로젝트에서도 같은 Connector를 사용할 수 있습니다.</div><label>1. 최초 1회 Pair</label><div class="code-line">${esc(register)}</div><label>2. 대화 수신 실행</label><div class="code-line">${esc(run)}</div><div class="notice">Codex / Claude Code / OpenCode / Antigravity CLI는 먼저 각 CLI에서 로그인되어 있어야 합니다.</div>`,async()=>({}));
}

'''
if "function startAIProject(" not in j:
    j = replace_once(j, new_project_marker, assistant_functions_js + new_project_marker, "assistant client functions")

js.write_text(j, encoding="utf-8")

# ----------------------------- CSS -----------------------------
css = Path("app/static/styles.css")
c = css.read_text(encoding="utf-8")
if ".assistant-layout" not in c:
    c += r'''

.onboarding-actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:18px}
.assistant-layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(320px,.85fr);gap:18px;align-items:start}
.assistant-chat{min-height:650px;display:flex;flex-direction:column}.assistant-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.chat-messages{flex:1;min-height:420px;max-height:62vh;overflow:auto;padding:12px 4px;display:flex;flex-direction:column;gap:12px}
.chat-message{max-width:86%;padding:13px 15px;border-radius:16px;line-height:1.55;background:#f2f5f9;border:1px solid #e1e6ee}.chat-message.user{margin-left:auto;background:#172033;color:white;border-color:#172033}.chat-role{font-size:11px;font-weight:800;opacity:.65;margin-bottom:5px;text-transform:uppercase}
.chat-input{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end;border-top:1px solid #e7eaf0;padding-top:14px}.chat-input textarea{min-height:78px;resize:vertical}
.assistant-side{display:flex;flex-direction:column;gap:18px}.proposal-row{display:flex;flex-direction:column;gap:4px;padding:10px 0;border-bottom:1px solid #edf0f4}.proposal-row span{font-size:13px;color:#667085;white-space:pre-wrap}.missing-fields{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
@media(max-width:1050px){.assistant-layout{grid-template-columns:1fr}.chat-messages{max-height:50vh}}
'''
css.write_text(c, encoding="utf-8")

# ----------------------------- README -----------------------------
readme = Path("README.md")
r = readme.read_text(encoding="utf-8")
if "Conversational Project Setup (V0.5)" not in r:
    r += r'''

## Conversational Project Setup (V0.5)

AI를 사용하는 팀원은 프로젝트 입력 폼을 작성하지 않고 **AI와 대화만으로 새 프로젝트를 시작**할 수 있습니다.

1. 웹에서 `AI와 새 프로젝트` 선택
2. 내 이름 + Codex / Claude Code / OpenCode / Antigravity CLI 선택
3. 최초 1회 Local Bridge를 서버에 `assistant-register`
4. `assistant-run` 실행
5. 프로젝트에 대해 자연스럽게 대화
6. AI가 Project Brief / Requirement / Decision / 13종 문서 변경안을 구조화해 제안
7. 웹에서 변경 Diff를 확인하고 `제안 적용`

AI가 말한 내용은 자동으로 확정되지 않습니다. 응답(`reply`)과 프로젝트 변경 제안(`project_updates`, `requirements`, `decisions`, `document_updates`)이 분리되며, 사용자가 적용한 내용만 Source of Truth에 반영됩니다. 모르는 내용은 AI가 추측하지 않고 Pending/TBD로 남기도록 Prompt Contract를 고정했습니다.

### 대화형 AI Connector

```bash
python local_bridge/bridge.py assistant-register --server http://SERVER:8000 --member "내 이름" --provider codex
python local_bridge/bridge.py assistant-run
```

Provider는 `codex`, `claude`, `opencode`, `antigravity`를 지원합니다. 일반 Task 실행용 `register/run`과 프로젝트 대화용 `assistant-register/assistant-run`은 분리되어 있습니다.
'''
readme.write_text(r, encoding="utf-8")
