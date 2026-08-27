from pathlib import Path

main = Path('app/main.py')
s = main.read_text(encoding='utf-8')

# Import universal intake helpers.
needle = 'from pydantic import BaseModel, Field\n'
insert = needle + '\nfrom app.project_intake import build_initial_documents, evaluate_intake, intake_metadata\n'
if 'from app.project_intake import' not in s:
    if needle not in s:
        raise RuntimeError('pydantic import marker not found')
    s = s.replace(needle, insert, 1)

# Bump version.
s = s.replace('version="0.3.0"', 'version="0.4.0"')
s = s.replace('"version": "0.3.0"', '"version": "0.4.0"')

# Expand the project creation contract without tying it to software-only projects.
start = s.index('class ProjectCreate(BaseModel):')
end = s.index('\n\nclass TaskCreate', start)
project_model = '''class ProjectCreate(BaseModel):
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
'''
s = s[:start] + project_model + s[end:]

# Replace initial document generation with universal intake module.
start = s.index('def apply_project_brief_to_documents(')
end = s.index('\n\ndef derived_trace_links', start)
helper = '''def apply_project_brief_to_documents(conn: sqlite3.Connection, project_id: int, payload: ProjectCreate) -> None:
    generated = build_initial_documents(payload.model_dump())
    for doc_type, content in generated.items():
        conn.execute(
            "UPDATE documents SET content=?,updated_by='Project Setup',updated_at=? WHERE project_id=? AND doc_type=?",
            (content, now(), project_id, doc_type),
        )
'''
s = s[:start] + helper + s[end:]

# Add universal intake metadata + simulation preview endpoints.
marker = '@app.get("/api/projects", dependencies=[])\n'
if '/api/project-intake/meta' not in s:
    endpoints = '''@app.get("/api/project-intake/meta")
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


'''
    if marker not in s:
        raise RuntimeError('projects endpoint marker not found')
    s = s.replace(marker, endpoints + marker, 1)

# Include quality summary in create response/activity.
old = '''        apply_project_brief_to_documents(conn, pid, payload)
        add_activity(conn, pid, "project", "프로젝트가 생성되었습니다.")
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
    return project
'''
new = '''        apply_project_brief_to_documents(conn, pid, payload)
        quality = evaluate_intake(payload.model_dump())
        add_activity(conn, pid, "project", f"프로젝트가 생성되었습니다. 초기 정의 품질 {quality['score']}점")
        project = rowdict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        if project is not None:
            project["intake_quality"] = quality
    return project
'''
if old not in s:
    raise RuntimeError('create project block not found')
s = s.replace(old, new, 1)
main.write_text(s, encoding='utf-8')

# Upgrade UI with a guided, domain-neutral project setup form and quality preview.
js_path = Path('app/static/app.js')
j = js_path.read_text(encoding='utf-8')

# Insert helper for optional guided textareas.
marker = "function textarea(name,label,value=''){ return `<div class=\"field\"><label>${esc(label)}</label><textarea name=\"${name}\">${esc(value)}</textarea></div>`; }\n"
if 'function guidedTextarea(' not in j:
    helper_js = marker + '''function guidedTextarea(name,label,hint,example,value=''){
  return `<div class="field intake-field"><label>${esc(label)}</label><small class="field-hint">${esc(hint)}</small><textarea name="${name}" placeholder="${esc(example)}">${esc(value)}</textarea></div>`;
}
'''
    if marker not in j:
        raise RuntimeError('textarea helper marker not found')
    j = j.replace(marker, helper_js, 1)

start = j.index('function newProject(){')
end = j.index('\nasync function downloadFile', start)
new_project_js = r'''function newProject(){
  const types=[
    ['generic','범용 프로젝트'],['software','소프트웨어 / 앱 / 시스템'],['ai_data','AI / 데이터'],
    ['embedded_hardware','임베디드 / 하드웨어 / IoT'],['manufacturing_automation','제조 / 자동화 / 스마트팩토리'],
    ['research_rnd','연구개발 / 실험 / PoC'],['business_process','업무개선 / 운영 / 프로세스'],
    ['product_service','제품 / 서비스 / 사업 기획'],['education_content','교육 / 콘텐츠 / 가이드'],
    ['event_campaign','행사 / 캠페인 / 비개발 프로젝트']
  ];
  const html=`<div class="notice"><strong>작성 원칙</strong><br>좋은 입력은 길기만 한 문장이 아니라 <b>현재 문제 → 목표 → 산출물 → 측정 가능한 성공기준 → 범위/제약</b>이 서로 이어집니다. 모르는 항목은 추측하지 말고 '미정' 또는 '확인 필요'라고 적어도 됩니다.</div>`+
    selectField('project_type','프로젝트 유형',types,'generic')+
    field('name','프로젝트 이름')+
    guidedTextarea('goal','프로젝트 목표','무엇을, 어디/누구에게 적용해, 어떤 결과를 만들지 적으세요.','예: 생산라인 제품을 자동 검사해 불량 판정과 결과 기록을 자동화한다.')+
    guidedTextarea('problem','해결하려는 문제 / 배경','현재 무엇이 불편하거나 비효율적이며 왜 해결해야 하는지 적으세요.','예: 육안 검사 편차와 누락이 발생하고 결과 집계가 수작업이다.')+
    guidedTextarea('users','대상 사용자 / 이해관계자','직접 사용자·운영자·결과 확인자·승인자를 구분하면 좋습니다.','예: 작업자(사용), 품질팀(확인), 설비팀(운영), 책임자(승인)')+
    guidedTextarea('deliverables','주요 산출물','프로젝트가 끝났을 때 실제로 남아 있어야 하는 결과물을 적으세요.','예: 실행 결과물, 운영 절차, 사용자 가이드, 검증 결과서')+
    guidedTextarea('success_criteria','성공 기준 / KPI','숫자·임계값·완료조건처럼 성공 여부를 판정할 수 있게 적으세요.','예: 처리시간 30% 단축, 오류 50% 감소, 인수 테스트 95% 이상 통과')+
    guidedTextarea('scope','포함 범위 / 제외 범위','이번에 하는 것과 하지 않는 것을 모두 적으세요.','예: 포함=핵심 프로세스/검증, 제외=전사 시스템 전체 교체')+
    guidedTextarea('current_state','현재 상태 (AS-IS)','현재 사람·시스템·장비가 어떤 순서로 처리하는지 적으세요.','예: 요청 접수 → 수작업 처리 → 엑셀 기록 → 담당자 보고')+
    guidedTextarea('target_state','목표 상태 (TO-BE)','완료 후 흐름이 어떻게 바뀌어야 하는지 적으세요.','예: 요청 접수 → 표준 처리 → 자동 기록 → 공유 대시보드 확인')+
    guidedTextarea('constraints','기술·일정·예산·운영 제약','반드시 지켜야 하는 조건을 기술/일정/예산/보안/법규 관점에서 적으세요.','예: 3개월 내 완료, 기존 장비 유지, 외부 반출 금지, 예산 500만원 이내')+
    guidedTextarea('schedule','일정 / 마일스톤 조건','언제까지 어떤 중간 결과가 필요한지 적으세요.','예: 1개월 기획 → 2개월 구현 → 3개월 검증/인수')+
    guidedTextarea('team','팀 / 역할','기획·실행·검증·승인 역할을 적으세요.','예: PM 1, 실무 2, 구현 2, 검증 1, 승인 1')+
    guidedTextarea('risks','리스크 / 가정','실패 가능성이 큰 조건이나 아직 확인되지 않은 사항을 적으세요.','예: 기존 데이터 품질 미확인, 현장 장비 규격 확인 필요')+
    guidedTextarea('description','추가 설명 / 참고','기존 자산, 참고자료, 용어, 이미 정해진 결정사항 등을 적으세요.','예: 기존 산출물 재사용, 고객 데이터 외부 AI 전송 금지')+
    `<div class="intake-preview-box"><button type="button" class="ghost-btn" id="previewIntakeBtn">작성 품질 점검</button><div id="intakePreviewResult" class="muted">프로젝트 생성 전에 입력 품질을 점검할 수 있습니다.</div></div>`;
  openModal('새 프로젝트 시작',html,async fd=>{
    const p=await api('/api/projects',{method:'POST',body:JSON.stringify(Object.fromEntries(fd))});
    state.projectId=p.id; state.selectedDocumentId=null; await loadProjects(); connectWs(); state.view='documents'; document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.view==='documents')); $('#pageTitle').textContent=titles.documents;
    const q=p.intake_quality; if(q) toast(`프로젝트 생성 · 초기 정의 품질 ${q.score}점`);
  });
  const btn=$('#previewIntakeBtn');
  if(btn) btn.onclick=async()=>{
    try{
      const form=$('#modalForm'); const data=Object.fromEntries(new FormData(form));
      const result=await api('/api/project-intake/preview',{method:'POST',body:JSON.stringify(data)});
      const q=result.quality; const box=$('#intakePreviewResult');
      const level={excellent:'매우 좋음',good:'좋음',needs_detail:'보완 권장',insufficient:'정보 부족'}[q.level]||q.level;
      box.innerHTML=`<div class="quality-score"><strong>${q.score}점 · ${esc(level)}</strong> · ${esc(q.project_type_label)}</div>`+
        (q.feedback.length?`<ul>${q.feedback.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<div>핵심 입력이 충분합니다. 생성 후 세부 문서를 팀과 보완하세요.</div>')+
        `<div class="type-questions"><strong>이 유형에서 추가로 확인할 질문</strong><ul>${q.type_questions.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
    }catch(err){ toast(err.message); }
  };
}
'''
j = j[:start] + new_project_js + j[end:]
js_path.write_text(j, encoding='utf-8')

# Add a small amount of styling for the guided form.
css_path = Path('app/static/styles.css')
c = css_path.read_text(encoding='utf-8')
if '.field-hint' not in c:
    c += '''\n.field-hint{display:block;color:#7d899d;font-size:12px;line-height:1.45;margin:4px 0 7px}.intake-field textarea{min-height:92px}.intake-preview-box{margin-top:12px;padding:14px;border:1px solid #dce2eb;border-radius:12px;background:#f8fafc}.quality-score{margin:12px 0 6px}.type-questions{margin-top:10px}.intake-preview-box ul{margin:6px 0 0;padding-left:20px}\n'''
css_path.write_text(c, encoding='utf-8')

# README: state that the intake is universal, not web/API-specific.
readme = Path('README.md')
r = readme.read_text(encoding='utf-8')
section = '''\n## Universal Project Setup (V0.4)\n\n새 프로젝트 입력은 웹/API 개발에 한정되지 않습니다. 범용 프로젝트를 기본값으로 두고 소프트웨어, AI/데이터, 임베디드/하드웨어/IoT, 제조/자동화, 연구개발/PoC, 업무개선, 제품/서비스 기획, 교육/콘텐츠, 행사/캠페인까지 같은 Project OS에서 시작할 수 있습니다.\n\n프로젝트 생성 전 **작성 품질 점검**을 누르면 목표·문제·이해관계자·산출물·KPI·범위·제약의 구체성을 점수와 피드백으로 확인합니다. 프로젝트 유형별 추가 확인 질문도 제공합니다. 입력 내용은 기획서, 계획서, 요구사항 정의서, 마일스톤, 백로그의 초기 초안에 반영됩니다.\n'''
if '## Universal Project Setup (V0.4)' not in r:
    r += section
readme.write_text(r, encoding='utf-8')
