from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


# 1) Load shared deterministic diagram layout engine before app.js.
p = ROOT / "app/static/index.html"
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    '  <script src="/static/app.js"></script>',
    '  <script src="/static/diagram_layout.js"></script>\n  <script src="/static/app.js"></script>',
    "diagram layout script include",
)
p.write_text(s, encoding="utf-8")


# 2) Replace naive grid renderer with layered SVG renderer.
p = ROOT / "app/static/app.js"
s = p.read_text(encoding="utf-8")
start = "function layoutNodes(nodes){\n"
end = "function renderIdeas(){\n"
a = s.find(start)
b = s.find(end, a)
if a < 0 or b < 0:
    raise RuntimeError("diagram renderer markers not found")
new = r'''function diagramMeta(view){
  return {
    process:{
      eyebrow:'PROCESS FLOW', title:'System Process',
      description:'업무/시스템이 어떤 순서와 분기로 진행되는지 왼쪽에서 오른쪽으로 읽습니다.',
      guide:'이벤트 → 처리 → 판단 → 저장/표시 순서가 한눈에 보이도록 Step 기준으로 자동 정렬합니다.',
      legend:[['event','시작/이벤트'],['process','처리 단계'],['decision','판단/분기'],['ui','사용자 확인']]
    },
    architecture:{
      eyebrow:'SYSTEM STRUCTURE', title:'Architecture',
      description:'장치·서비스·데이터 저장소·UI의 책임과 의존관계를 계층으로 읽습니다.',
      guide:'Edge/Input → Application/Service → Data/Storage 또는 Output/UI 흐름으로 자동 정렬합니다.',
      legend:[['device','장치/외부'],['service','서비스'],['database','데이터 저장소'],['ui','UI/출력']]
    },
    dataflow:{
      eyebrow:'DATA MOVEMENT', title:'Data Flow',
      description:'데이터가 어디서 생성되고 어떤 처리를 거쳐 어디에 저장·소비되는지 보여줍니다.',
      guide:'Source → Processing → Store/Consumer 방향으로 배치하고 연결선 라벨을 데이터 이름으로 강조합니다.',
      legend:[['source','데이터 원천'],['process','변환/검증'],['database','저장'],['sink','소비처']]
    }
  }[view];
}
function renderDiagram(view){
  const nodes=state.snapshot.nodes.filter(n=>n.view===view);
  const edges=state.snapshot.edges.filter(e=>e.view===view);
  const meta=diagramMeta(view);
  const stats=`<div class="diagram-stats"><span><b>${nodes.length}</b> Nodes</span><span><b>${edges.length}</b> Connections</span><span class="diagram-auto-badge">AUTO LAYOUT</span></div>`;
  const legend=meta.legend.map(([kind,label])=>`<span class="diagram-legend-item"><i class="legend-dot kind-${kind}"></i>${esc(label)}</span>`).join('');
  const body=nodes.length
    ? `<div class="professional-diagram-canvas">${DiagramLayout.renderSvg(view,nodes,edges)}</div>`
    : `<div class="diagram-empty"><strong>아직 ${esc(meta.title)} 노드가 없습니다.</strong><span>AI Design Session에서 구조가 결정되면 여기에 자동 시각화됩니다.</span></div>`;
  return `<section class="diagram-workspace diagram-workspace-${view}">
    <div class="panel diagram-header-card">
      <div class="diagram-header-main"><div><div class="eyebrow">${meta.eyebrow}</div><h2>${esc(meta.title)}</h2><p>${esc(meta.description)}</p></div>${stats}</div>
      <div class="diagram-reading-guide"><strong>읽는 방법</strong><span>${esc(meta.guide)}</span></div>
      <div class="diagram-legend">${legend}</div>
      <div class="diagram-toolbar"><button class="mini-btn" data-action="add-node" data-view="${view}">+ 노드</button><button class="mini-btn" data-action="add-edge" data-view="${view}">+ 연결</button></div>
    </div>
    <div class="panel diagram-surface">${body}</div>
  </section>`;
}
'''
s = s[:a] + new + s[b:]
p.write_text(s, encoding="utf-8")


# 3) Add professional diagram styles and remove visual dependence on old absolute nodes.
p = ROOT / "app/static/styles.css"
s = p.read_text(encoding="utf-8")
marker = "/* V0.12 professional design diagrams */"
if marker not in s:
    s += r'''

/* V0.12 professional design diagrams */
.diagram-workspace{display:grid;gap:18px}.diagram-header-card{padding:22px 24px}.diagram-header-main{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;flex-wrap:wrap}.diagram-header-main h2{margin:4px 0 7px;font-size:25px}.diagram-header-main p{margin:0;color:var(--muted);max-width:780px;line-height:1.55}.diagram-stats{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.diagram-stats>span{display:inline-flex;align-items:center;gap:5px;padding:7px 10px;border:1px solid var(--line);border-radius:999px;background:#fafbfc;color:#667085;font-size:11px}.diagram-stats b{color:var(--text);font-size:13px}.diagram-auto-badge{background:#edf7f2!important;border-color:#d7eee3!important;color:#2d7a59!important;font-weight:800;letter-spacing:.04em}.diagram-reading-guide{display:flex;gap:10px;align-items:flex-start;margin:16px 0 12px;padding:11px 13px;background:#f7f8fc;border:1px solid #e6e9f2;border-radius:11px;font-size:12px;line-height:1.5}.diagram-reading-guide strong{white-space:nowrap;color:#4f67e8}.diagram-reading-guide span{color:#5d6878}.diagram-legend{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px}.diagram-legend-item{display:inline-flex;align-items:center;gap:6px;color:#667085;font-size:11px}.legend-dot{width:9px;height:9px;border-radius:3px;background:#8892a5}.legend-dot.kind-device,.legend-dot.kind-source,.legend-dot.kind-event{background:#3d91a5}.legend-dot.kind-service,.legend-dot.kind-process{background:#536be8}.legend-dot.kind-database{background:#775fc9}.legend-dot.kind-ui,.legend-dot.kind-sink{background:#3a9b6d}.legend-dot.kind-decision{background:#cf8931}.diagram-toolbar{margin:0}.diagram-surface{padding:10px;overflow:hidden}.professional-diagram-canvas{width:100%;overflow:auto;border:1px solid #e5e9f0;border-radius:14px;background:linear-gradient(180deg,#fbfcfe 0%,#f7f9fc 100%)}.diagram-svg{display:block;width:100%;min-width:900px;height:auto;min-height:440px}.diagram-layer rect{fill:#f8fafc;stroke:#e9edf3;stroke-width:1}.diagram-layer text{fill:#8a94a4;font-size:11px;font-weight:800;letter-spacing:.08em}.diagram-svg-edge path{fill:none;stroke:#a5afbe;stroke-width:2.1}.diagram-svg marker path{fill:#8490a2}.edge-label-bg{fill:#fff;stroke:#dfe4ec;stroke-width:1}.edge-label-text{fill:#5b6677;font-size:11px;font-weight:700}.diagram-svg-node rect,.diagram-svg-node polygon{fill:#fff;stroke:#d9dfe8;stroke-width:1.4;filter:drop-shadow(0 4px 8px rgba(24,33,47,.07))}.diagram-svg-node.kind-device rect,.diagram-svg-node.kind-source rect,.diagram-svg-node.kind-event rect{stroke:#79b4c0;fill:#f8fcfd}.diagram-svg-node.kind-service rect,.diagram-svg-node.kind-process rect{stroke:#8393eb;fill:#fafbff}.diagram-svg-node.kind-database rect{stroke:#9888d8;fill:#fbfaff}.diagram-svg-node.kind-ui rect,.diagram-svg-node.kind-sink rect{stroke:#76b895;fill:#f9fdfb}.diagram-svg-node.kind-decision polygon{stroke:#d5a35e;fill:#fffaf2}.node-kind{fill:#8993a3;font-size:9px;font-weight:800;letter-spacing:.08em}.node-title{fill:#222c3b;font-size:13px;font-weight:800}.node-title.secondary{font-size:12px}.node-detail{fill:#7a8595;font-size:10px}.diagram-empty{min-height:420px;display:grid;place-items:center;align-content:center;gap:8px;color:#7a8595;text-align:center}.diagram-empty strong{font-size:15px;color:#4b5565}.diagram-empty span{font-size:12px}@media(max-width:900px){.diagram-header-main{display:grid}.diagram-svg{min-width:820px}.diagram-reading-guide{display:grid;gap:4px}}
'''
p.write_text(s, encoding="utf-8")


# 4) Version bump.
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8")
s = s.replace('version="0.11.0"', 'version="0.12.0"', 1)
p.write_text(s, encoding="utf-8")


# 5) README version and V0.12 explanation; also correct old pre-apply wording.
p = ROOT / "README.md"
s = p.read_text(encoding="utf-8")
s = s.replace("# Team Project OS V0.11", "# Team Project OS V0.12", 1)
anchor = "## V0.11 Professional Deliverables\n"
section = '''## V0.12 Human-readable Design Diagrams\n\nSystem Process / Architecture / Data Flow는 더 이상 동일한 단순 격자 배치를 사용하지 않습니다. 그래프 연결을 분석해 계층을 만들고, 노드가 겹치지 않도록 정렬하며, 연결선은 노드 경계에서 출발/도착합니다.\n\n- System Process: STEP 순서와 분기를 왼쪽→오른쪽으로 표현\n- Architecture: Edge/Input → Application/Service → Data/Storage 또는 Output/UI 계층\n- Data Flow: Source → Processing → Store/Consumer 단계와 데이터 라벨 강조\n- 같은 레벨/역방향 연결은 노드를 가로지르지 않도록 아래쪽 별도 경로 사용\n- AI가 만든 긴 라벨도 두 줄 제한/말줄임으로 다이어그램 크기를 안정적으로 유지\n- 연결선 라벨을 흰색 캡슐로 표시해 배경/선과 겹쳐도 읽을 수 있도록 개선\n\n`tests/test_diagram_layout.js`에서 노드 중첩, 경계 포트 연결, 유효 SVG, XSS escape를 검증하고 `tools/simulate_project_creation_v012.py`에서 프로젝트 생성부터 13종 문서와 3개 디자인 그래프까지 E2E로 검증합니다.\n\n'''
if section not in s:
    s = s.replace(anchor, section + anchor, 1)
s = s.replace("`/apply` 전에는 서버의 프로젝트/문서/Canvas를 변경하지 않습니다.", "Live Design이 켜진 경우 `/apply` 전에는 `lifecycle=draft`인 별도 Draft Workspace만 갱신되며, `/apply`에서 같은 Draft가 정식 active 프로젝트로 승격됩니다.", 1)
p.write_text(s, encoding="utf-8")

print("V0.12 diagram UI upgrade prepared")
