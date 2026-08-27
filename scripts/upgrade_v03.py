from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


main = Path("app/main.py")
s = main.read_text(encoding="utf-8")
s = replace_once(s, "import json\nimport os\nimport secrets\nimport sqlite3", "import io\nimport json\nimport os\nimport re\nimport secrets\nimport sqlite3\nimport zipfile", "main imports")
s = replace_once(s, "from fastapi.responses import FileResponse", "from fastapi.responses import FileResponse, Response", "Response import")
s = s.replace('version="0.2.0"', 'version="0.3.0"')
s = s.replace('"version": "0.2.0"', '"version": "0.3.0"')

old = '''class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    goal: str = Field(min_length=2, max_length=1000)
    description: str = Field(default="", max_length=2000)
'''
new = '''class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    goal: str = Field(min_length=2, max_length=1000)
    description: str = Field(default="", max_length=2000)
    problem: str = Field(default="", max_length=4000)
    users: str = Field(default="", max_length=2000)
    success_criteria: str = Field(default="", max_length=4000)
    scope: str = Field(default="", max_length=4000)
    constraints: str = Field(default="", max_length=4000)
'''
s = replace_once(s, old, new, "ProjectCreate")

old = '''class DocumentCommentCreate(BaseModel):
    author: str = Field(default="Team member", max_length=120)
    body: str = Field(min_length=1, max_length=4000)
'''
new = '''class DocumentCommentCreate(BaseModel):
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
'''
s = replace_once(s, old, new, "TraceLinkCreate")

old = '''            CREATE TABLE IF NOT EXISTS document_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
'''
new = '''            CREATE TABLE IF NOT EXISTS document_comments (
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
'''
s = replace_once(s, old, new, "trace_links table")

marker = 'def add_activity(conn: sqlite3.Connection, project_id: int, type_: str, message: str, actor: str = "System") -> None:\n'
helpers = '''def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
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
        for ref in sorted(set(re.findall(r"REQ-\\d+", task.get("requirement_ref", "") or ""))):
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
        note = str(link.get("note", "")).replace("|", "\\|")
        lines.append(f"| {src} | {link['relation']} | {dst} | {note} |")
    if len(lines) == 4:
        lines.append("| - | - | - | 아직 연결 없음 |")
    return "\\n".join(lines) + "\\n"


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
    return "\\n".join(lines) + "\\n"


'''
s = replace_once(s, marker, helpers + marker, "main helpers")

s = replace_once(s, '        ensure_project_documents(conn, pid)\n        add_activity(conn, pid, "project", "프로젝트가 생성되었습니다.")', '        ensure_project_documents(conn, pid)\n        apply_project_brief_to_documents(conn, pid, payload)\n        add_activity(conn, pid, "project", "프로젝트가 생성되었습니다.")', "apply project brief")
s = replace_once(s, '        progress = round((done / total) * 100) if total else 0\n        return {', '        progress = round((done / total) * 100) if total else 0\n        trace_links = [dict(r) for r in conn.execute("SELECT * FROM trace_links WHERE project_id=? ORDER BY id DESC", (project_id,))]\n        derived_links = derived_trace_links(tasks)\n        return {', "snapshot links")
s = replace_once(s, '            "document_comments": [dict(r) for r in conn.execute("SELECT c.* FROM document_comments c JOIN documents d ON d.id=c.document_id WHERE d.project_id=? ORDER BY c.id DESC LIMIT 100", (project_id,))],\n            "activity":', '            "document_comments": [dict(r) for r in conn.execute("SELECT c.* FROM document_comments c JOIN documents d ON d.id=c.document_id WHERE d.project_id=? ORDER BY c.id DESC LIMIT 100", (project_id,))],\n            "trace_links": trace_links,\n            "derived_trace_links": derived_links,\n            "activity":', "snapshot trace output")
s = replace_once(s, '                "documents_ready": conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=? AND status IN (\'review\',\'approved\',\'complete\')", (project_id,)).fetchone()["c"],\n', '                "documents_ready": conn.execute("SELECT COUNT(*) c FROM documents WHERE project_id=? AND status IN (\'review\',\'approved\',\'complete\')", (project_id,)).fetchone()["c"],\n                "trace_links": len(trace_links) + len(derived_links),\n', "snapshot trace stat")

api_marker = '@app.post("/api/projects/{project_id}/nodes")\n'
api_block = '''@app.post("/api/projects/{project_id}/trace-links")
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
        summary = f"# {project['name']}\\n\\n## Goal\\n{project['goal']}\\n\\n## Description\\n{project['description']}\\n\\nGenerated: {now()}\\n"
        zf.writestr("00_PROJECT_SUMMARY.md", summary)
        for idx, doc in enumerate(documents, start=1):
            zf.writestr(f"documents/{idx:02d}_{doc['doc_type']}.md", doc["content"])
        zf.writestr("TRACEABILITY.md", traceability_markdown(explicit, derived))
        zf.writestr("design/SYSTEM_PROCESS.md", "# System Process\\n\\n" + mermaid_for_view(nodes, edges, "process"))
        zf.writestr("design/ARCHITECTURE.md", "# Architecture\\n\\n" + mermaid_for_view(nodes, edges, "architecture"))
        zf.writestr("design/DATA_FLOW.md", "# Data Flow\\n\\n" + mermaid_for_view(nodes, edges, "dataflow"))
        snapshot = {"project": project, "requirements": requirements, "tasks": tasks, "decisions": decisions, "nodes": nodes, "edges": edges, "trace_links": explicit, "derived_trace_links": derived}
        zf.writestr("project_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
    return Response(content=buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="team_project_os_{project_id}_documents.zip"'})


'''
s = replace_once(s, api_marker, api_block + api_marker, "trace/export APIs")
main.write_text(s, encoding="utf-8")

index = Path("app/static/index.html")
s = index.read_text(encoding="utf-8")
s = replace_once(s, '<button class="nav-item" data-view="documents">▤ <span>Documents</span></button>\n        <button class="nav-item" data-view="progress">▥ <span>Progress</span></button>', '<button class="nav-item" data-view="documents">▤ <span>Documents</span></button>\n        <button class="nav-item" data-view="traceability">⛓ <span>Traceability</span></button>\n        <button class="nav-item" data-view="progress">▥ <span>Progress</span></button>', "trace nav")
index.write_text(s, encoding="utf-8")

app = Path("app/static/app.js")
s = app.read_text(encoding="utf-8")
s = replace_once(s, "overview:'Overview', definition:'Goal & Requirements', documents:'Project Documents', progress:'Development Progress',", "overview:'Overview', definition:'Goal & Requirements', documents:'Project Documents', traceability:'Traceability', progress:'Development Progress',", "titles")
s = replace_once(s, "documents:renderDocuments,progress:renderProgress", "documents:renderDocuments,traceability:renderTraceability,progress:renderProgress", "render map")
s = replace_once(s, '<div class="documents-head"><div><div class="eyebrow">PROJECT DOCUMENT WORKSPACE</div><h2>프로젝트 문서 ${completed}/${s.documents.length}</h2><p class="muted">문서는 서버에 공유 저장되며 저장 전 내용은 revision으로 남습니다.</p></div></div>', '<div class="documents-head"><div><div class="eyebrow">PROJECT DOCUMENT WORKSPACE</div><h2>프로젝트 문서 ${completed}/${s.documents.length}</h2><p class="muted">문서는 서버에 공유 저장되며 저장 전 내용은 revision으로 남습니다.</p></div><div><button class="mini-btn" data-action="export-project">첨부 패키지 ZIP</button></div></div>', "document export button")
s = replace_once(s, '<div class="form-actions"><button type="button" class="primary-btn" data-action="save-document">문서 저장</button></div>', '<div class="form-actions"><button type="button" class="ghost-btn" data-action="export-document">Markdown 다운로드</button><button type="button" class="primary-btn" data-action="save-document">문서 저장</button></div>', "single export button")

trace_ui = '''function renderTraceability(){
  const s=state.snapshot; const explicit=s.trace_links||[]; const derived=s.derived_trace_links||[]; const all=[...explicit,...derived];
  return `<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap"><div><div class="eyebrow">END-TO-END TRACEABILITY</div><h2>요구사항부터 QA까지 연결</h2><p class="muted">기획/요구사항 → 기능 → IA/화면 → API/Architecture → Task → QA 관계를 연결합니다. Task의 REQ 참조는 자동 연결됩니다.</p></div><button class="mini-btn" data-action="add-trace-link">+ 연결 추가</button></div></div>
  <div class="panel" style="margin-top:18px">${all.length?`<table class="table"><thead><tr><th>Source</th><th>Relation</th><th>Target</th><th>Note</th><th></th></tr></thead><tbody>${all.map(l=>`<tr><td><strong>${esc(l.source_type)}:${esc(l.source_ref)}</strong></td><td>${esc(l.relation)}</td><td><strong>${esc(l.target_type)}:${esc(l.target_ref)}</strong></td><td>${esc(l.note||'')}</td><td>${l.derived?'<span class="chip ai">자동</span>':`<button class="mini-btn" data-action="delete-trace" data-view="${l.id}">삭제</button>`}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">아직 연결이 없습니다. 요구사항과 구현/QA 항목을 연결해보세요.</div>'}</div>`;
}
'''
s = replace_once(s, 'function renderProgress(){\n', trace_ui + 'function renderProgress(){\n', "trace UI")
s = replace_once(s, "documents:'document-help',progress:'add-task'", "documents:'document-help',traceability:'add-trace-link',progress:'add-task'", "add map")
s = replace_once(s, "if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp();", "if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp(); if(action==='export-project') return exportProject(); if(action==='export-document') return exportDocument(); if(action==='add-trace-link') return addTraceLink(); if(action==='delete-trace') return deleteTrace(view);", "handle trace")
s = replace_once(s, "openModal('새 프로젝트 시작',field('name','프로젝트 이름')+textarea('goal','프로젝트 목표')+textarea('description','배경 / 문제 / 성공 기준'),async fd=>{", "openModal('새 프로젝트 시작',field('name','프로젝트 이름')+textarea('goal','프로젝트 목표')+textarea('problem','해결하려는 문제')+textarea('users','대상 사용자 / 이해관계자')+textarea('success_criteria','성공 기준 / KPI')+textarea('scope','포함 범위 / 제외 범위')+textarea('constraints','기술·일정·예산·운영 제약')+textarea('description','추가 설명'),async fd=>{", "project wizard")

ui_helpers = '''async function downloadFile(url, filename){
  const headers={}; if(state.accessKey) headers['X-Access-Key']=state.accessKey;
  const r=await fetch(url,{headers}); if(!r.ok) throw new Error('파일 생성 실패');
  const blob=await r.blob(); const href=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=href; a.download=filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(href),1000);
}
function exportProject(){ return downloadFile(`/api/projects/${state.projectId}/export/documents.zip`,`team_project_${state.projectId}_documents.zip`).then(()=>toast('프로젝트 첨부 패키지를 생성했습니다.')).catch(e=>toast(e.message)); }
function exportDocument(){ const d=state.snapshot.documents.find(x=>x.id===state.selectedDocumentId); if(!d)return; return downloadFile(`/api/documents/${d.id}/export.md`,`${d.doc_type}.md`).catch(e=>toast(e.message)); }
function addTraceLink(){
  const types=[['requirement','Requirement'],['feature','Feature'],['ia','IA'],['screen','Screen'],['api','API'],['architecture','Architecture'],['data','Data Flow'],['task','Task'],['qa','QA/Test'],['decision','Decision'],['document','Document']];
  openModal('Traceability 연결 추가',selectField('source_type','Source 종류',types,'requirement')+field('source_ref','Source ID','REQ-001')+selectField('target_type','Target 종류',types,'feature')+field('target_ref','Target ID','FUNC-001')+selectField('relation','관계',[['defines','defines'],['realized_by','realized_by'],['implemented_by','implemented_by'],['verified_by','verified_by'],['depends_on','depends_on'],['relates_to','relates_to']],'realized_by')+textarea('note','메모')+field('created_by','작성자','Team member'),fd=>api(`/api/projects/${state.projectId}/trace-links`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))}));
}
async function deleteTrace(id){ if(!confirm('이 연결을 삭제할까요?'))return; await api(`/api/trace-links/${id}`,{method:'DELETE'}); await loadSnapshot(); toast('연결을 삭제했습니다.'); }
'''
s = replace_once(s, "function documentHelp(){ toast(", ui_helpers + "function documentHelp(){ toast(", "UI helpers")
app.write_text(s, encoding="utf-8")

readme = Path("README.md")
s = readme.read_text(encoding="utf-8")
section = '''

## V0.3 - 프로젝트 처음부터 생성 / Traceability / 첨부 패키지

- 새 프로젝트 생성 시 문제, 대상 사용자, 성공 기준, 범위, 제약조건을 입력할 수 있습니다.
- 입력값은 기획서와 계획서 초기 초안에 자동 반영됩니다.
- Traceability 화면에서 Requirement → Feature → IA/Screen → API/Architecture → Task → QA 관계를 연결할 수 있습니다.
- Task의 `REQ-xxx` 참조는 자동 Trace로 표시됩니다.
- Documents에서 선택 문서를 Markdown으로 다운로드할 수 있습니다.
- `첨부 패키지 ZIP`은 13종 문서, Traceability Matrix, Process/Architecture/Data Flow Mermaid 문서, 구조화 snapshot JSON을 묶어 생성합니다.

> 현재 Export는 Markdown/ZIP 중심입니다. PDF/DOCX 제출본 렌더링은 후속 버전에서 확장할 수 있습니다.
'''
if "## V0.3 - 프로젝트 처음부터 생성" not in s:
    readme.write_text(s + section, encoding="utf-8")

Path("tests/test_traceability_export.py").write_text('''import io
import os
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient


class TraceabilityExportTests(unittest.TestCase):
    def test_project_brief_traceability_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "trace.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                p = client.post("/api/projects", json={
                    "name": "From Zero", "goal": "Build together", "description": "team project",
                    "problem": "Problem A", "users": "Operators", "success_criteria": "KPI 95%",
                    "scope": "Web + API", "constraints": "Internal network",
                }).json()
                pid = p["id"]
                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["documents"]), 13)
                proposal = next(d for d in snap["documents"] if d["doc_type"] == "proposal")
                self.assertIn("Problem A", proposal["content"])
                client.post(f"/api/projects/{pid}/requirements", json={"title":"REQ-001 Login","detail":"login"})
                task = client.post(f"/api/projects/{pid}/tasks", json={"title":"Implement login","requirement_ref":"REQ-001"}).json()
                link = client.post(f"/api/projects/{pid}/trace-links", json={"source_type":"requirement","source_ref":"REQ-001","target_type":"api","target_ref":"API-001","relation":"realized_by"})
                self.assertEqual(link.status_code, 200)
                snap = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len(snap["trace_links"]), 1)
                self.assertTrue(any(x["target_ref"] == f"TASK-{task['id']}" for x in snap["derived_trace_links"]))
                exported = client.get(f"/api/projects/{pid}/export/documents.zip")
                self.assertEqual(exported.status_code, 200)
                self.assertEqual(exported.headers["content-type"], "application/zip")
                with zipfile.ZipFile(io.BytesIO(exported.content)) as zf:
                    names = zf.namelist()
                    self.assertIn("TRACEABILITY.md", names)
                    self.assertIn("project_snapshot.json", names)
                    self.assertEqual(len([n for n in names if n.startswith("documents/")]), 13)
                    self.assertIn("REQ-001", zf.read("TRACEABILITY.md").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")

print("v0.3 patch applied")
