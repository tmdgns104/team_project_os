from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


# index.html: load milestone renderer before app.js
p = ROOT / "app/static/index.html"
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    '  <script src="/static/diagram_layout.js"></script>\n  <script src="/static/app.js"></script>',
    '  <script src="/static/diagram_layout.js"></script>\n  <script src="/static/milestone_gantt.js"></script>\n  <script src="/static/app.js"></script>',
    "milestone script include",
)
p.write_text(s, encoding="utf-8")


# app.js: milestone documents use Gantt renderer in read mode
p = ROOT / "app/static/app.js"
s = p.read_text(encoding="utf-8")
anchor = "  const headings=markdownHeadings(d.content); const quality=documentQuality(d); const editing=state.documentEditMode;\n"
replacement = anchor + "  const renderedDocumentBody=d.doc_type==='milestone'&&typeof MilestoneGantt!=='undefined'?MilestoneGantt.render(d.content,d.title,s.project.name):renderMarkdownDocument(d.content);\n"
s = replace_once(s, anchor, replacement, "milestone rendered body")
s = replace_once(s, "<section class=\"doc-content-rendered\">${renderMarkdownDocument(d.content)}</section>", "<section class=\"doc-content-rendered\">${renderedDocumentBody}</section>", "document read body")
p.write_text(s, encoding="utf-8")


# Professional Gantt styles
p = ROOT / "app/static/styles.css"
s = p.read_text(encoding="utf-8")
marker = "/* V0.13 development milestone Gantt */"
if marker not in s:
    s += r'''

/* V0.13 development milestone Gantt */
.milestone-deliverable{margin:2px 0 22px}.milestone-summary{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--line)}.milestone-summary h2{margin:4px 0 6px;font-size:24px}.milestone-summary p{margin:0;color:var(--muted);font-size:12px}.milestone-kpis{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.milestone-kpis span{display:inline-flex;gap:5px;align-items:center;padding:7px 10px;border:1px solid var(--line);border-radius:999px;background:#fafbfc;color:#6b7585;font-size:10px}.milestone-kpis b{font-size:12px;color:var(--text)}.milestone-notice{padding:10px 12px;margin-bottom:12px;border-radius:10px;background:#fff7e8;border:1px solid #f2dfb7;color:#8b651c;font-size:11px}.gantt-legend{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0 12px;color:#697486;font-size:10px}.gantt-legend span{display:inline-flex;align-items:center;gap:5px}.gantt-legend i{display:inline-block;width:13px;height:8px;border-radius:3px;background:#b9c1ce}.gantt-legend i.status-done,.gantt-cell.status-done{background:#74a888}.gantt-legend i.status-in_progress,.gantt-cell.status-in_progress{background:#6f86df}.gantt-legend i.status-review,.gantt-cell.status-review{background:#b58bd5}.gantt-legend i.status-todo,.gantt-cell.status-todo,.gantt-cell.status-draft{background:#c6ccd5}.gantt-legend i.status-blocked,.gantt-cell.status-blocked{background:#d98282}.gantt-legend i.is-current{background:#f1cf45}.gantt-scroll{overflow:auto;border:1px solid #cfd5de;border-radius:10px;background:#fff}.gantt-table{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:10px}.gantt-table th,.gantt-table td{border-right:1px solid #d6dbe2;border-bottom:1px solid #d6dbe2;height:31px;padding:0}.gantt-table thead th{background:#2e3339;color:#fff;font-weight:700;text-align:center;position:sticky;top:0;z-index:3}.gantt-level{width:140px;min-width:140px;left:0;z-index:5!important}.gantt-task-head{width:300px;min-width:300px;left:140px;z-index:5!important}.gantt-month{height:25px;background:#20252a!important}.gantt-week{width:34px;min-width:34px;font-size:9px}.gantt-week.is-current{background:#d7b51e!important;color:#151515}.gantt-table tbody .gantt-phase{width:140px;min-width:140px;padding:10px;background:#f3f4f6;text-align:center;vertical-align:middle;position:sticky;left:0;z-index:2;border-right:2px solid #b8bec8}.gantt-phase strong{font-size:10px;line-height:1.45;white-space:pre-line}.gantt-task{width:300px;min-width:300px;padding:5px 8px!important;background:#fff;position:sticky;left:140px;z-index:2;display:flex;justify-content:space-between;gap:8px;align-items:center}.gantt-task div{display:grid;gap:2px;min-width:0}.gantt-task strong{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gantt-task small,.gantt-task span{font-size:8px;color:#8a94a3}.gantt-cell{width:34px;min-width:34px;background:#fafbfc;position:relative}.gantt-cell.is-current:not(.is-active){background:#fff7c8}.gantt-cell.is-active{box-shadow:inset 0 5px 0 rgba(255,255,255,.22),inset 0 -5px 0 rgba(0,0,0,.04)}.gantt-cell.bar-start{border-radius:5px 0 0 5px}.gantt-cell.bar-end{border-radius:0 5px 5px 0}.milestone-empty{min-height:260px;display:grid;place-items:center;align-content:center;gap:8px;border:1px dashed #d6dce5;border-radius:12px;color:#7c8796;text-align:center}.milestone-empty strong{color:#4c5666}@media(max-width:900px){.milestone-summary{display:grid}.milestone-kpis{justify-content:flex-start}.gantt-task-head,.gantt-task{width:245px;min-width:245px}.gantt-task{left:120px}.gantt-level,.gantt-table tbody .gantt-phase{width:120px;min-width:120px}}
'''
p.write_text(s, encoding="utf-8")


# app/main.py: version, health, and baseline template
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8")
s = s.replace('version="0.12.0"', 'version="0.13.0"', 1)
s = s.replace('return {"status": "ok", "version": "0.11.0"}', 'return {"status": "ok", "version": app.version}', 1)
old = '("milestone", "마일스톤", "# 마일스톤 관리표\\n\\n| ID | Milestone | 목표 | 주요 산출물 | Entry Criteria | Exit Criteria | 목표일 | Owner | 상태 |\\n|---|---|---|---|---|---|---|---|---|\\n| M1 | Definition Baseline | 요구사항 기준선 | 기획/요구사항 | TBD | 핵심 REQ Review | TBD | TBD | Draft |\\n| M2 | Design Baseline | 설계 기준선 | Process/Architecture/Data Flow | M1 | 설계 Review | TBD | TBD | Draft |\\n"),'
new = '("milestone", "마일스톤", "# 개발 마일스톤 / Gantt\\n\\n> **기준 시작일** · TBD · 실제 날짜가 정해지기 전에는 상대 주차 기준 초안\\n\\n## Gantt Schedule\\n\\n| Phase | ID | Task | Start Week | End Week | Owner | Status |\\n|---|---|---|---|---|---|---|\\n| A. 정의 및 설계 | MS-001 | 프로젝트 착수 / 목표·범위 정리 | 1 | 1 | TBD | Draft |\\n| A. 정의 및 설계 | MS-002 | 요구사항 분석 및 정의 | 1 | 2 | TBD | Draft |\\n| A. 정의 및 설계 | MS-003 | Process / Architecture / Data Flow 설계 | 2 | 4 | TBD | Draft |\\n| A. 정의 및 설계 | MS-004 | UI/IA 및 인터페이스 기준선 | 3 | 4 | TBD | Draft |\\n| B. 구현 | MS-005 | 개발환경 / 기반 구조 준비 | 4 | 5 | TBD | Todo |\\n| B. 구현 | MS-006 | 핵심 기능 구현 | 5 | 9 | TBD | Todo |\\n| B. 구현 | MS-007 | 데이터 저장 / 연동 구현 | 6 | 9 | TBD | Todo |\\n| B. 구현 | MS-008 | UI / 사용자 기능 구현 | 7 | 10 | TBD | Todo |\\n| B. 구현 | MS-009 | 모듈 통합 | 9 | 11 | TBD | Todo |\\n| C. 통합 및 검증 | MS-010 | 통합 테스트 | 11 | 13 | TBD | Todo |\\n| C. 통합 및 검증 | MS-011 | 시스템 / 비기능 검증 | 12 | 14 | TBD | Todo |\\n| C. 통합 및 검증 | MS-012 | 결함 수정 / 안정화 | 13 | 15 | TBD | Todo |\\n| D. 완료 | MS-013 | 인수 기준 확인 | 15 | 15 | TBD | Todo |\\n| D. 완료 | MS-014 | 문서 / 운영 가이드 정리 | 15 | 16 | TBD | Todo |\\n| D. 완료 | MS-015 | 최종 릴리스 / 인수 | 16 | 16 | TBD | Todo |\\n\\n> 이 일정은 프로젝트 유형·실제 시작일·인력·제약이 정해지면 Live Design에서 갱신합니다.\\n"),'
s = replace_once(s, old, new, "main milestone template")
p.write_text(s, encoding="utf-8")


# project_intake.py: generated professional milestone document
p = ROOT / "app/project_intake.py"
s = p.read_text(encoding="utf-8")
start = '    milestone = f"""# {name} 마일스톤 관리표\n'
end = '    backlog = f"""# {name} Product / Project Backlog\n'
a=s.find(start); b=s.find(end,a)
if a<0 or b<0: raise RuntimeError('project intake milestone block not found')
block = '''    milestone = f"""# {name} 개발 마일스톤 / Gantt\n\n> **기준 일정** · {schedule}\n> **기준 시작일** · TBD · 실제 날짜 확정 전에는 상대 주차 기준 초안\n\n## 1. Gantt Schedule\n\n| Phase | ID | Task | Start Week | End Week | Owner | Status |\n|---|---|---|---|---|---|---|\n| A. 정의 및 설계 | MS-001 | 프로젝트 착수 / 목표·범위 정리 | 1 | 1 | TBD | Draft |\n| A. 정의 및 설계 | MS-002 | 요구사항 분석 및 정의 | 1 | 2 | TBD | Draft |\n| A. 정의 및 설계 | MS-003 | Process / Architecture / Data Flow 설계 | 2 | 4 | TBD | Draft |\n| A. 정의 및 설계 | MS-004 | UI/IA 및 인터페이스 기준선 | 3 | 4 | TBD | Draft |\n| B. 구현 | MS-005 | 개발환경 / 기반 구조 준비 | 4 | 5 | TBD | Todo |\n| B. 구현 | MS-006 | 핵심 기능 구현 | 5 | 9 | TBD | Todo |\n| B. 구현 | MS-007 | 데이터 저장 / 연동 구현 | 6 | 9 | TBD | Todo |\n| B. 구현 | MS-008 | UI / 사용자 기능 구현 | 7 | 10 | TBD | Todo |\n| B. 구현 | MS-009 | 모듈 통합 | 9 | 11 | TBD | Todo |\n| C. 통합 및 검증 | MS-010 | 통합 테스트 | 11 | 13 | TBD | Todo |\n| C. 통합 및 검증 | MS-011 | 시스템 / 비기능 검증 | 12 | 14 | TBD | Todo |\n| C. 통합 및 검증 | MS-012 | 결함 수정 / 안정화 | 13 | 15 | TBD | Todo |\n| D. 완료 | MS-013 | 인수 기준 확인 | 15 | 15 | TBD | Todo |\n| D. 완료 | MS-014 | 문서 / 운영 가이드 정리 | 15 | 16 | TBD | Todo |\n| D. 완료 | MS-015 | 최종 릴리스 / 인수 | 16 | 16 | TBD | Todo |\n\n## 2. Milestone Gates\n\n| Gate | 목표 | 핵심 산출물 | Exit Criteria | 상태 |\n|---|---|---|---|---|\n| M1 · Definition Baseline | 프로젝트 정의 확정 | 기획서 / 요구사항서 | 핵심 목표·범위·REQ Review | Draft |\n| M2 · Design Baseline | 구현 가능한 설계 확정 | Process / Architecture / Data Flow | 주요 인터페이스/데이터 흐름 Review | Draft |\n| M3 · Build Complete | V1 구현 완료 | 기능 / 코드 / 구성 | 핵심 Task 완료 및 통합 가능 | Draft |\n| M4 · Verification Complete | 품질 기준 충족 | QA / Evidence | Critical Test PASS, Blocker 0 | Draft |\n\n## 3. 일정 운영 원칙\n- Gantt의 주차는 실제 시작일·팀 가용성·의존성이 확정되면 갱신한다.\n- AI가 정한 기간은 `PROVISIONAL` 성격의 계획 초안이며 사람 승인 전 확정 일정으로 간주하지 않는다.\n- Exit Criteria 미충족 시 다음 단계 완료로 표시하지 않는다.\n- 범위/Architecture 변경이 일정에 영향을 주면 관련 Task와 리스크를 함께 갱신한다.\n"""\n\n'''
s=s[:a]+block+s[b:]
p.write_text(s,encoding='utf-8')


# README version and section
p=ROOT/'README.md'; s=p.read_text(encoding='utf-8')
s=s.replace('# Team Project OS V0.12','# Team Project OS V0.13',1)
anchor='## V0.12 Human-readable Design Diagrams\n'
section='''## V0.13 Development Milestone Gantt\n\n`마일스톤` 문서는 Markdown 원본을 유지하면서 웹에서는 실무 프로젝트 일정표처럼 **Level / Task / Month / Week** 구조의 Gantt로 표시합니다. `Phase | ID | Task | Start Week | End Week | Owner | Status` 표가 Source of Truth이며 Markdown 편집 후 저장하면 Gantt가 즉시 다시 렌더링됩니다. 실제 시작일이 정해진 경우 현재 주차도 강조할 수 있습니다. 일정이 미정이면 16주 상대 주차 기준 초안을 사용하되 확정 일정으로 간주하지 않습니다.\n\n'''
if section not in s: s=s.replace(anchor,section+anchor,1)
p.write_text(s,encoding='utf-8')

print('V0.13 milestone Gantt upgrade prepared')
