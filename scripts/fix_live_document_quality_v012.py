from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8")
start = "def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:\n"
end = "\n\ndef apply_live_draft_state("
a = s.find(start)
b = s.find(end, a)
if a < 0 or b < 0:
    raise RuntimeError("build_live_draft_documents markers not found")

new = r'''def build_live_draft_documents(brief: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
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
'''

s = s[:a] + new + s[b:]
p.write_text(s, encoding="utf-8")
print("V0.12 Live Draft professional document preservation applied")
