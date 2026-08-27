from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


# ---------------- conversation contract ----------------
conv_path = Path("app/conversation.py")
c = conv_path.read_text(encoding="utf-8")

if "ALLOWED_DIAGRAM_VIEWS" not in c:
    c = replace_once(
        c,
        "ALLOWED_DOCUMENT_TYPES = {\n",
        "ALLOWED_DIAGRAM_VIEWS = {\"process\", \"architecture\", \"dataflow\"}\n\nALLOWED_DOCUMENT_TYPES = {\n",
        "diagram constants",
    )

pending_marker = '''    pending = []\n    for item in data.get("pending", []) if isinstance(data.get("pending"), list) else []:\n'''
if 'data.get("design_updates")' not in c:
    design_normalizer = '''    design_updates = []\n    for item in data.get("design_updates", []) if isinstance(data.get("design_updates"), list) else []:\n        if not isinstance(item, dict):\n            continue\n        view = _clip(item.get("view"), 40)\n        if view not in ALLOWED_DIAGRAM_VIEWS:\n            continue\n        mode = _clip(item.get("mode") or "merge", 20)\n        if mode not in {"merge", "replace"}:\n            mode = "merge"\n        nodes = []\n        node_keys = set()\n        for node in item.get("nodes", []) if isinstance(item.get("nodes"), list) else []:\n            if not isinstance(node, dict):\n                continue\n            key = _clip(node.get("key"), 80)\n            label = _clip(node.get("label"), 200)\n            if not key or not label or key in node_keys:\n                continue\n            node_keys.add(key)\n            nodes.append({\n                "key": key,\n                "label": label,\n                "kind": _clip(node.get("kind") or "component", 80),\n                "detail": _clip(node.get("detail"), 2000),\n            })\n        edges = []\n        for edge in item.get("edges", []) if isinstance(item.get("edges"), list) else []:\n            if not isinstance(edge, dict):\n                continue\n            source = _clip(edge.get("source"), 80)\n            target = _clip(edge.get("target"), 80)\n            if source not in node_keys or target not in node_keys or source == target:\n                continue\n            edges.append({\n                "source": source,\n                "target": target,\n                "label": _clip(edge.get("label"), 300),\n            })\n        if nodes:\n            design_updates.append({\n                "view": view,\n                "mode": mode,\n                "reason": _clip(item.get("reason"), 1000),\n                "nodes": nodes[:40],\n                "edges": edges[:80],\n            })\n\n'''
    c = replace_once(c, pending_marker, design_normalizer + pending_marker, "design normalizer")

old_return = '''        "document_updates": document_updates[:13],\n        "pending": pending[:20],\n    }\n'''
new_return = '''        "document_updates": document_updates[:13],\n        "design_updates": design_updates[:3],\n        "pending": pending[:20],\n    }\n'''
c = replace_once(c, old_return, new_return, "normalize return")

old_merged = '''        "requirements": [],\n        "decisions": [],\n        "document_updates": [],\n        "pending": [],\n    }\n'''
new_merged = '''        "requirements": [],\n        "decisions": [],\n        "document_updates": [],\n        "design_updates": [],\n        "pending": [],\n    }\n'''
c = replace_once(c, old_merged, new_merged, "proposal accumulator")

old_merge_lists = '''    merged["requirements"] = merge_list("requirements", lambda x: x.get("ref") or x.get("title"))[-30:]\n    merged["decisions"] = merge_list("decisions", lambda x: x.get("title"))[-20:]\n    merged["document_updates"] = merge_list("document_updates", lambda x: x.get("doc_type"))[-13:]\n'''
new_merge_lists = '''    merged["requirements"] = merge_list("requirements", lambda x: x.get("ref") or x.get("title"))[-30:]\n    merged["decisions"] = merge_list("decisions", lambda x: x.get("title"))[-20:]\n    merged["document_updates"] = merge_list("document_updates", lambda x: x.get("doc_type"))[-13:]\n    merged["design_updates"] = merge_list("design_updates", lambda x: x.get("view"))[-3:]\n'''
c = replace_once(c, old_merge_lists, new_merge_lists, "merge design proposals")

mission_line = "- If the user asks to write or revise a project document, you may propose a complete replacement for that document in document_updates.\n"
if "design_updates" not in c[c.index("MISSION"):]:
    c = replace_once(
        c,
        mission_line,
        mission_line + "- When the conversation supports a system flow or technical structure, propose System Process, Architecture, and/or Data Flow as node/edge graphs in design_updates. Do not invent components, protocols, data, or ordering that the user did not state or reasonably confirm.\n- Diagram proposals are NOT approved until the human applies them. Prefer mode=merge unless the user explicitly asks to replace/redesign the current view.\n",
        "prompt design mission",
    )

contract_marker = '''  "document_updates": [\n    {{"doc_type":"proposal|plan|milestone|backlog|requirements|service_policy|function_definition|ia|screen_design|system_architecture|data_flow|api_design|qa", "content":"complete markdown content only when the user asked to write/update this document", "reason":"why"}}\n  ],\n  "pending": ["facts or decisions that are still unknown and worth resolving"]\n}}\n'''
contract_new = '''  "document_updates": [\n    {{"doc_type":"proposal|plan|milestone|backlog|requirements|service_policy|function_definition|ia|screen_design|system_architecture|data_flow|api_design|qa", "content":"complete markdown content only when the user asked to write/update this document", "reason":"why"}}\n  ],\n  "design_updates": [\n    {{\n      "view":"process|architecture|dataflow",\n      "mode":"merge|replace",\n      "reason":"why this graph follows from the conversation",\n      "nodes":[{{"key":"stable-short-key", "label":"visible node label", "kind":"step|component|service|database|device|source|sink|other", "detail":"known detail only"}}],\n      "edges":[{{"source":"node-key", "target":"node-key", "label":"sequence/protocol/data label if known"}}]\n    }}\n  ],\n  "pending": ["facts or decisions that are still unknown and worth resolving"]\n}}\n'''
c = replace_once(c, contract_marker, contract_new, "prompt output contract")
conv_path.write_text(c, encoding="utf-8")


# ---------------- backend ----------------
main_path = Path("app/main.py")
s = main_path.read_text(encoding="utf-8")
s = s.replace('version="0.5.0"', 'version="0.6.0"')
s = s.replace('"version": "0.5.0"', '"version": "0.6.0"')

apply_marker = '''        if payload.apply_documents:\n            for item in pending.get("document_updates", []):\n                doc = conn.execute("SELECT * FROM documents WHERE project_id=? AND doc_type=?", (pid, item.get("doc_type"))).fetchone()\n                content = str(item.get("content") or "")\n                if not doc or not content:\n                    continue\n                conn.execute(\n                    "INSERT INTO document_revisions(document_id,content,status,editor,created_at) VALUES(?,?,?,?,?)",\n                    (doc["id"], doc["content"], doc["status"], "AI Conversation", now()),\n                )\n                conn.execute(\n                    "UPDATE documents SET content=?,updated_by=?,updated_at=? WHERE id=?",\n                    (content, f"AI Conversation / {session['member_name']}", now(), doc["id"]),\n                )\n                applied += 1\n\n        conn.execute("UPDATE conversation_sessions SET pending_json='{}',updated_at=? WHERE id=?", (now(), session_id))\n'''
if 'pending.get("design_updates"' not in s:
    design_apply = '''        if payload.apply_documents:\n            for item in pending.get("document_updates", []):\n                doc = conn.execute("SELECT * FROM documents WHERE project_id=? AND doc_type=?", (pid, item.get("doc_type"))).fetchone()\n                content = str(item.get("content") or "")\n                if not doc or not content:\n                    continue\n                conn.execute(\n                    "INSERT INTO document_revisions(document_id,content,status,editor,created_at) VALUES(?,?,?,?,?)",\n                    (doc["id"], doc["content"], doc["status"], "AI Conversation", now()),\n                )\n                conn.execute(\n                    "UPDATE documents SET content=?,updated_by=?,updated_at=? WHERE id=?",\n                    (content, f"AI Conversation / {session['member_name']}", now(), doc["id"]),\n                )\n                applied += 1\n\n        # Visual design proposals are only materialized after this human Apply action.\n        for design in pending.get("design_updates", []):\n            view = str(design.get("view") or "")\n            if view not in {"process", "architecture", "dataflow"}:\n                continue\n            mode = str(design.get("mode") or "merge")\n            if mode == "replace":\n                conn.execute("DELETE FROM edges WHERE project_id=? AND view=?", (pid, view))\n                conn.execute("DELETE FROM nodes WHERE project_id=? AND view=?", (pid, view))\n\n            existing = {\n                r["label"]: r["id"]\n                for r in conn.execute("SELECT id,label FROM nodes WHERE project_id=? AND view=?", (pid, view))\n            }\n            key_to_id: dict[str, int] = {}\n            for idx, node in enumerate(design.get("nodes", [])):\n                key = str(node.get("key") or "").strip()\n                label = str(node.get("label") or "").strip()\n                if not key or not label:\n                    continue\n                node_id = existing.get(label) if mode == "merge" else None\n                if node_id is None:\n                    cur = conn.execute(\n                        "INSERT INTO nodes(project_id,view,label,kind,detail,x,y) VALUES(?,?,?,?,?,?,?)",\n                        (pid, view, label, node.get("kind") or "component", node.get("detail") or "", 80 + (idx % 4) * 220, 80 + (idx // 4) * 150),\n                    )\n                    node_id = cur.lastrowid\n                    existing[label] = node_id\n                    applied += 1\n                key_to_id[key] = node_id\n\n            for edge in design.get("edges", []):\n                source_id = key_to_id.get(str(edge.get("source") or ""))\n                target_id = key_to_id.get(str(edge.get("target") or ""))\n                if not source_id or not target_id or source_id == target_id:\n                    continue\n                label = str(edge.get("label") or "")\n                duplicate = conn.execute(\n                    "SELECT 1 FROM edges WHERE project_id=? AND view=? AND source_id=? AND target_id=? AND label=?",\n                    (pid, view, source_id, target_id, label),\n                ).fetchone()\n                if not duplicate:\n                    conn.execute(\n                        "INSERT INTO edges(project_id,view,source_id,target_id,label) VALUES(?,?,?,?,?)",\n                        (pid, view, source_id, target_id, label),\n                    )\n                    applied += 1\n\n        conn.execute("UPDATE conversation_sessions SET pending_json='{}',updated_at=? WHERE id=?", (now(), session_id))\n'''
    s = replace_once(s, apply_marker, design_apply, "apply design proposals")

# Safe permanent deletion endpoint: exact project name must be supplied.
projects_marker = '@app.patch("/api/projects/{project_id}/goal")\n'
if '@app.delete("/api/projects/{project_id}")' not in s:
    delete_api = '''@app.delete("/api/projects/{project_id}")\nasync def delete_project(project_id: int, confirm_name: str = Query(...), x_access_key: str | None = Header(default=None)):\n    require_access(x_access_key)\n    with db() as conn:\n        project = conn.execute("SELECT id,name FROM projects WHERE id=?", (project_id,)).fetchone()\n        if not project:\n            raise HTTPException(404, "Project not found")\n        if confirm_name != project["name"]:\n            raise HTTPException(400, "Project name confirmation does not match")\n        deleted_name = project["name"]\n        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))\n    await manager.broadcast(project_id, {"type": "project_deleted", "project_id": project_id})\n    return {"ok": True, "deleted_project_id": project_id, "deleted_name": deleted_name}\n\n\n'''
    s = replace_once(s, projects_marker, delete_api + projects_marker, "project delete endpoint")

main_path.write_text(s, encoding="utf-8")


# ---------------- frontend ----------------
index_path = Path("app/static/index.html")
h = index_path.read_text(encoding="utf-8")
old_top = '''          <button id="newProjectBtn" class="ghost-btn">+ 새 프로젝트</button>\n          <button id="accessKeyBtn" class="ghost-btn">접속키</button>\n'''
new_top = '''          <button id="newProjectBtn" class="ghost-btn">+ 새 프로젝트</button>\n          <button id="deleteProjectBtn" class="danger-btn">프로젝트 삭제</button>\n          <button id="accessKeyBtn" class="ghost-btn">접속키</button>\n'''
h = replace_once(h, old_top, new_top, "delete project button")
index_path.write_text(h, encoding="utf-8")

js_path = Path("app/static/app.js")
j = js_path.read_text(encoding="utf-8")

init_marker = "  $('#aiStartBtn').addEventListener('click', ()=>startAIProject(false));\n"
if "deleteProjectBtn" not in j:
    j = replace_once(j, init_marker, init_marker + "  $('#deleteProjectBtn').addEventListener('click', deleteCurrentProject);\n", "delete button listener")

load_marker = "  select.value=state.projectId||'';\n"
if "deleteProjectBtn').disabled" not in j:
    j = replace_once(j, load_marker, load_marker + "  $('#deleteProjectBtn').disabled=!state.projectId;\n", "delete disabled state")

old_pending = "  const hasPending=Object.keys(updates).length || (pending.requirements||[]).length || (pending.decisions||[]).length || (pending.document_updates||[]).length;\n"
new_pending = "  const hasPending=Object.keys(updates).length || (pending.requirements||[]).length || (pending.decisions||[]).length || (pending.document_updates||[]).length || (pending.design_updates||[]).length;\n"
j = replace_once(j, old_pending, new_pending, "design pending flag")

old_docs = "  const docs=(pending.document_updates||[]).map(d=>`<div class=\"proposal-row\"><strong>Document · ${esc(d.doc_type)}</strong><span>${esc(d.reason||'문서 수정 제안')}</span></div>`).join('');\n"
new_docs = old_docs + "  const designs=(pending.design_updates||[]).map(d=>`<div class=\"proposal-row design-proposal\"><strong>Canvas · ${esc(d.view)} · ${esc(d.mode||'merge')}</strong><span>${esc(d.reason||'대화 기반 설계 제안')}<br><small>노드 ${(d.nodes||[]).length}개 · 연결 ${(d.edges||[]).length}개 · ${(d.nodes||[]).map(n=>esc(n.label)).join(' → ')}</small></span></div>`).join('');\n"
j = replace_once(j, old_docs, new_docs, "design proposal render")

old_render = "${hasPending?(proposalRows+reqs+decisions+docs):'<div class=\"empty\">아직 적용 대기 중인 제안이 없습니다.</div>'}"
new_render = "${hasPending?(proposalRows+reqs+decisions+docs+designs):'<div class=\"empty\">아직 적용 대기 중인 제안이 없습니다.</div>'}"
j = replace_once(j, old_render, new_render, "design proposal list")

apply_func = '''async function applyConversation(){\n  const sid=state.snapshot.conversation?.session?.id; if(!sid)return;\n  const result=await api(`/api/conversations/${sid}/apply`,{method:'POST',body:JSON.stringify({})}); await loadProjects(); await loadSnapshot(); toast(`${result.applied}개 제안을 적용했습니다. 정의 품질 ${result.quality.score}점`);\n}\n'''
if "async function deleteCurrentProject" not in j:
    delete_func = apply_func + '''\nasync function deleteCurrentProject(){\n  if(!state.projectId || !state.snapshot?.project) return;\n  const name=state.snapshot.project.name;\n  const typed=prompt(`프로젝트를 영구 삭제합니다.\\n문서, Task, Canvas, 대화 기록 등 이 프로젝트의 데이터가 함께 삭제됩니다.\\n\\n삭제하려면 프로젝트 이름을 정확히 입력하세요:\\n${name}`);\n  if(typed===null) return;\n  if(typed!==name){ toast('프로젝트 이름이 일치하지 않아 삭제하지 않았습니다.'); return; }\n  if(!confirm(`정말 "${name}" 프로젝트를 영구 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;\n  try{\n    await api(`/api/projects/${state.projectId}?confirm_name=${encodeURIComponent(name)}`,{method:'DELETE'});\n    if(state.ws){ state.ws.close(); state.ws=null; }\n    state.projectId=null; state.snapshot=null; state.selectedDocumentId=null;\n    await loadProjects();\n    toast('프로젝트를 삭제했습니다.');\n  }catch(err){ toast(err.message); }\n}\n'''
    j = replace_once(j, apply_func, delete_func, "delete project function")

js_path.write_text(j, encoding="utf-8")

css_path = Path("app/static/styles.css")
css = css_path.read_text(encoding="utf-8")
if ".danger-btn" not in css:
    css += '''\n.danger-btn{border:1px solid #d66;background:#fff;color:#a22;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}.danger-btn:hover{background:#fff5f5}.danger-btn:disabled{opacity:.45;cursor:not-allowed}.design-proposal small{display:block;margin-top:5px;color:#748095;line-height:1.45}\n'''
css_path.write_text(css, encoding="utf-8")

# README
readme_path = Path("README.md")
r = readme_path.read_text(encoding="utf-8")
if "Conversational Visual Design (V0.6)" not in r:
    r += '''\n\n## Conversational Visual Design (V0.6)\n\nAI Project Assistant 대화에서 **System Process / Architecture / Data Flow**를 `node + edge` 구조로 제안할 수 있습니다. 제안은 `pending` 상태로만 보관되며 사용자가 **제안 적용**을 누르기 전에는 Canvas를 변경하지 않습니다. 승인 시 `merge` 또는 `replace` 모드에 따라 Canvas 노드/연결을 생성하고 자동 위치를 배정합니다.\n\n예: 사용자가 `센서 감지 → 카메라 촬영 → AI 판정 → PLC 배출 → 결과 저장`이라고 설명하면 AI는 Process 노드/연결을 제안하고, 사용자가 승인하면 System Process Canvas에 실제 그래프로 반영할 수 있습니다. Protocol/Data label이 확인된 경우 Data Flow edge label에도 반영합니다. 모르는 구성요소나 통신방식은 추측하지 않고 Pending으로 남깁니다.\n\n### Project Delete\n\n상단 `프로젝트 삭제` 버튼으로 현재 프로젝트를 영구 삭제할 수 있습니다. 실수를 막기 위해 프로젝트 이름을 정확히 다시 입력하고 마지막 확인을 거쳐야 합니다. 삭제 시 SQLite foreign-key cascade에 따라 해당 프로젝트의 문서/revision/comment, Requirement/Task, Canvas node/edge, Traceability, Idea/Decision, Project Brief, Conversation/AI Job 등이 함께 제거됩니다.\n'''
readme_path.write_text(r, encoding="utf-8")


# ---------------- tests ----------------
test = r'''import json
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.conversation import normalize_ai_result


class ConversationalVisualDesignContractTests(unittest.TestCase):
    def test_diagram_contract_filters_invalid_views_and_edges(self):
        raw = json.dumps({
            "reply": "설계 초안을 제안합니다.",
            "design_updates": [
                {
                    "view": "process",
                    "mode": "replace",
                    "reason": "사용자가 순서를 명시함",
                    "nodes": [
                        {"key": "sense", "label": "센서 감지", "kind": "step"},
                        {"key": "judge", "label": "AI 판정", "kind": "step"},
                    ],
                    "edges": [
                        {"source": "sense", "target": "judge", "label": ""},
                        {"source": "missing", "target": "judge", "label": "invalid"},
                    ],
                },
                {"view": "unknown", "nodes": [{"key": "x", "label": "X"}]},
            ],
        }, ensure_ascii=False)
        result = normalize_ai_result(raw)
        self.assertEqual(len(result["design_updates"]), 1)
        design = result["design_updates"][0]
        self.assertEqual(design["view"], "process")
        self.assertEqual(design["mode"], "replace")
        self.assertEqual(len(design["nodes"]), 2)
        self.assertEqual(len(design["edges"]), 1)


class ConversationalVisualDesignApiTests(unittest.TestCase):
    def test_design_is_not_drawn_before_apply_then_materializes_and_project_can_delete(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["PROJECT_OS_DB"] = os.path.join(td, "v06.db")
            from app import main
            main.DB_PATH = main.Path(os.environ["PROJECT_OS_DB"])
            main.SEED_DEMO = False
            main.init_db()
            with TestClient(main.app) as client:
                bridge = client.post("/api/assistant-bridges/register", json={
                    "member_name": "designer", "provider": "codex", "machine_name": "pc"
                }).json()
                token = bridge["token"]
                started = client.post("/api/conversations/start", json={
                    "member_name": "designer", "provider": "codex"
                }).json()
                pid = started["project"]["id"]
                sid = started["session"]["id"]
                project_name = started["project"]["name"]

                client.post(f"/api/conversations/{sid}/messages", json={"message": "센서 감지 후 카메라 촬영, AI 판정, PLC 배출 순서로 진행해"})
                job = client.get(f"/api/assistant-bridge/jobs?token={token}").json()["job"]
                output = json.dumps({
                    "reply": "말씀하신 순서로 프로세스와 구조를 제안합니다.",
                    "design_updates": [
                        {
                            "view": "process", "mode": "replace", "reason": "사용자가 공정 순서를 직접 설명함",
                            "nodes": [
                                {"key": "sensor", "label": "센서 감지", "kind": "step"},
                                {"key": "camera", "label": "카메라 촬영", "kind": "step"},
                                {"key": "ai", "label": "AI 판정", "kind": "step"},
                                {"key": "plc", "label": "PLC 배출", "kind": "step"},
                            ],
                            "edges": [
                                {"source": "sensor", "target": "camera", "label": ""},
                                {"source": "camera", "target": "ai", "label": "Image"},
                                {"source": "ai", "target": "plc", "label": "판정 결과"},
                            ],
                        },
                        {
                            "view": "architecture", "mode": "replace", "reason": "대화에서 장치 역할이 확인됨",
                            "nodes": [
                                {"key": "camera", "label": "Camera", "kind": "device"},
                                {"key": "ai", "label": "AI Inference", "kind": "service"},
                                {"key": "plc", "label": "PLC", "kind": "device"},
                            ],
                            "edges": [
                                {"source": "camera", "target": "ai", "label": ""},
                                {"source": "ai", "target": "plc", "label": ""},
                            ],
                        },
                        {
                            "view": "dataflow", "mode": "replace", "reason": "이미지와 판정 결과 이동이 확인됨",
                            "nodes": [
                                {"key": "camera", "label": "Camera", "kind": "source"},
                                {"key": "ai", "label": "AI Model", "kind": "process"},
                                {"key": "plc", "label": "PLC", "kind": "sink"},
                            ],
                            "edges": [
                                {"source": "camera", "target": "ai", "label": "Image"},
                                {"source": "ai", "target": "plc", "label": "판정 결과"},
                            ],
                        },
                    ],
                }, ensure_ascii=False)
                result = client.post(f"/api/assistant-bridge/results?token={token}", json={
                    "job_id": job["id"], "status": "completed", "output": output
                })
                self.assertEqual(result.status_code, 200)

                before = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(before["nodes"], [])
                self.assertEqual(len(before["conversation"]["pending"]["design_updates"]), 3)

                applied = client.post(f"/api/conversations/{sid}/apply", json={})
                self.assertEqual(applied.status_code, 200)
                after = client.get(f"/api/projects/{pid}/snapshot").json()
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "process"]), 4)
                self.assertEqual(len([e for e in after["edges"] if e["view"] == "process"]), 3)
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "architecture"]), 3)
                self.assertEqual(len([n for n in after["nodes"] if n["view"] == "dataflow"]), 3)
                self.assertTrue(any(e["label"] == "Image" for e in after["edges"] if e["view"] == "dataflow"))

                wrong = client.delete(f"/api/projects/{pid}", params={"confirm_name": "wrong"})
                self.assertEqual(wrong.status_code, 400)
                deleted = client.delete(f"/api/projects/{pid}", params={"confirm_name": project_name})
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(client.get(f"/api/projects/{pid}/snapshot").status_code, 404)
                self.assertFalse(any(p["id"] == pid for p in client.get("/api/projects").json()))


if __name__ == "__main__":
    unittest.main()
'''
Path("tests/test_visual_design_delete.py").write_text(test, encoding="utf-8")
