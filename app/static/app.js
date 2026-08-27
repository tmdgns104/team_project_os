const state = {
  projects: [], projectId: null, snapshot: null, view: 'overview', ws: null, selectedDocumentId: null,
  accessKey: localStorage.getItem('project_os_access_key') || ''
};
const titles = {
  overview:'Overview', definition:'Goal & Requirements', documents:'Project Documents', progress:'Development Progress',
  process:'System Process', architecture:'Architecture', dataflow:'Data Flow',
  ideas:'Ideas & Decisions', team:'Team & AI'
};
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const api = async (url, opts={}) => {
  opts.headers = {...(opts.headers||{}), 'Content-Type':'application/json'};
  if (state.accessKey) opts.headers['X-Access-Key'] = state.accessKey;
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(()=>({detail:r.statusText}))).detail || r.statusText);
  return r.status===204 ? null : r.json();
};
function toast(msg){ const el=$('#toast'); el.textContent=msg; el.classList.remove('hidden'); setTimeout(()=>el.classList.add('hidden'),2400); }
function statusChip(status){
  const map={done:['완료','good'],in_progress:['진행중','ai'],review:['검토','warn'],todo:['예정',''],blocked:['차단','danger'],defined:['정의됨','good'],accepted:['승인','good'],open:['Open',''],discussing:['논의중','warn'],queued:['대기','warn'],claimed:['실행중','ai'],completed:['완료','good'],failed:['실패','danger'],draft:['초안',''],approved:['승인됨','good'],complete:['완료','good']};
  const [t,c]=map[status]||[status,'']; return `<span class="chip ${c}">${esc(t)}</span>`;
}
async function init(){
  bindNav();
  $('#newProjectBtn').addEventListener('click', newProject);
  $('#accessKeyBtn').addEventListener('click', setAccessKey);
  $('#addBtn').addEventListener('click', openAddForView);
  $('#modalClose').addEventListener('click', closeModal);
  $('#modal').addEventListener('click', e=>{ if(e.target.id==='modal') closeModal(); });
  try { await loadProjects(); } catch(e){ if(String(e).includes('access')) setAccessKey(); else toast(e.message); }
}
function bindNav(){
  $('#nav').addEventListener('click', e=>{
    const b=e.target.closest('.nav-item'); if(!b) return;
    state.view=b.dataset.view; document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x===b));
    $('#pageTitle').textContent=titles[state.view]; render();
  });
}
async function loadProjects(){
  state.projects=await api('/api/projects');
  const select=$('#projectSelect');
  select.innerHTML=state.projects.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
  if(state.projectId && !state.projects.some(p=>p.id===state.projectId)) state.projectId=null;
  if(!state.projectId && state.projects[0]) state.projectId=state.projects[0].id;
  select.value=state.projectId||'';
  select.onchange=async()=>{ state.projectId=Number(select.value); await loadSnapshot(); connectWs(); };
  if(state.projectId){ await loadSnapshot(); connectWs(); } else { state.snapshot=null; render(); }
}
async function loadSnapshot(){ state.snapshot=await api(`/api/projects/${state.projectId}/snapshot`); render(); }
function connectWs(){
  if(state.ws) state.ws.close();
  const proto=location.protocol==='https:'?'wss':'ws';
  const key=encodeURIComponent(state.accessKey||'');
  state.ws=new WebSocket(`${proto}://${location.host}/ws/projects/${state.projectId}?key=${key}`);
  state.ws.onopen=()=>{ $('#liveText').textContent='실시간 공유 연결됨'; };
  state.ws.onmessage=()=>loadSnapshot().catch(()=>{});
  state.ws.onclose=()=>{ $('#liveText').textContent='연결 끊김 · 새로고침 필요'; };
}
function setAccessKey(){
  const v=prompt('서버에 APP_ACCESS_KEY를 설정했다면 접속키를 입력하세요.\n설정하지 않았다면 비워두세요.',state.accessKey||'');
  if(v===null) return; state.accessKey=v.trim(); localStorage.setItem('project_os_access_key',state.accessKey); loadProjects().catch(e=>toast(e.message));
}
function render(){
  if(!state.snapshot){ $('#content').innerHTML='<div class="panel onboarding"><h2>새 프로젝트를 시작하세요</h2><p class="muted">기획부터 설계, 개발, QA까지 팀이 같은 Workspace에서 진행할 수 있습니다.</p><button class="primary-btn" data-action="new-project">+ 프로젝트 생성</button></div>'; bindViewActions(); return; }
  const fn={overview:renderOverview,definition:renderDefinition,documents:renderDocuments,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];
  $('#content').innerHTML=fn(); bindViewActions();
}
function renderOverview(){
  const s=state.snapshot, st=s.stats;
  return `<div class="hero">
    <div class="panel goal-card"><div class="eyebrow">PROJECT GOAL</div><h2>${esc(s.project.goal)}</h2><p class="muted">${esc(s.project.description)}</p><div class="progress-track"><div class="progress-fill" style="width:${st.progress}%"></div></div><p class="muted"><strong>${st.progress}%</strong> 완료 · 완료 Task ${st.tasks_done}/${st.tasks_total}</p></div>
    <div class="panel"><h3>Project Health</h3><div style="font-size:44px;font-weight:800">${st.progress}%</div><p class="muted">Task 완료율 기준 V1 지표</p>${st.tasks_blocked?`<div class="notice">차단된 작업 ${st.tasks_blocked}건을 먼저 확인하세요.</div>`:'<div class="notice">현재 명시적으로 차단된 작업이 없습니다.</div>'}</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-label">Requirements</div><div class="stat-value">${st.requirements}</div></div>
    <div class="stat"><div class="stat-label">Tasks Done</div><div class="stat-value">${st.tasks_done}/${st.tasks_total}</div></div>
    <div class="stat"><div class="stat-label">Blocked</div><div class="stat-value">${st.tasks_blocked}</div></div>
    <div class="stat"><div class="stat-label">AI Bridges</div><div class="stat-value">${s.bridges.length}</div></div>
  </div>
  <div class="section-grid">
    <div class="panel"><h3>현재 개발 작업</h3>${s.tasks.slice(0,6).map(t=>`<div class="activity"><div class="activity-icon">T</div><div style="flex:1"><strong>${esc(t.title)}</strong><div><small>${esc(t.owner)} · ${esc(t.requirement_ref||'연결 요구사항 없음')}</small></div></div>${statusChip(t.status)}</div>`).join('')}</div>
    <div class="panel"><h3>최근 활동</h3>${s.activity.length?s.activity.slice(0,8).map(a=>`<div class="activity"><div class="activity-icon">${a.type==='ai'?'AI':'•'}</div><div><strong>${esc(a.message)}</strong><div><small>${esc(a.actor)} · ${new Date(a.created_at).toLocaleString('ko-KR')}</small></div></div></div>`).join(''):'<div class="empty">활동 없음</div>'}</div>
  </div>`;
}
function renderDefinition(){
  const s=state.snapshot;
  return `<div class="section-grid"><div class="panel"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center"><h3>Project Definition</h3><button class="mini-btn" data-action="edit-goal">목표 수정</button></div><div class="eyebrow">GOAL</div><h2 style="line-height:1.4">${esc(s.project.goal)}</h2><p class="muted">${esc(s.project.description)}</p></div>
  <div class="panel"><h3>설계 준비도</h3><p class="muted">요구사항 → 프로세스 → 아키텍처 → 데이터 흐름 → Task가 연결될수록 프로젝트 상태를 이해하기 쉬워집니다.</p><div class="progress-track"><div class="progress-fill" style="width:${Math.min(100,45+s.requirements.length*8)}%"></div></div></div></div>
  <div class="panel" style="margin-top:18px"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Requirements</h3><button class="mini-btn" data-action="add-requirement">+ 요구사항</button></div><div class="req-list">${s.requirements.map(r=>`<div class="req"><div style="display:flex;justify-content:space-between;gap:10px"><strong>${esc(r.title)}</strong>${statusChip(r.status)}</div><div class="muted">${esc(r.detail)}</div></div>`).join('')}</div></div>`;
}
function renderDocuments(){
  const s=state.snapshot;
  if(!s.documents?.length) return '<div class="empty">프로젝트 문서가 없습니다.</div>';
  if(!state.selectedDocumentId || !s.documents.some(d=>d.id===state.selectedDocumentId)) state.selectedDocumentId=s.documents[0].id;
  const d=s.documents.find(x=>x.id===state.selectedDocumentId);
  const comments=s.document_comments.filter(c=>c.document_id===d.id);
  const completed=s.documents.filter(x=>['review','approved','complete'].includes(x.status)).length;
  return `<div class="documents-head"><div><div class="eyebrow">PROJECT DOCUMENT WORKSPACE</div><h2>프로젝트 문서 ${completed}/${s.documents.length}</h2><p class="muted">문서는 서버에 공유 저장되며 저장 전 내용은 revision으로 남습니다.</p></div></div>
  <div class="document-layout">
    <div class="panel document-list">${s.documents.map(x=>`<button class="document-item ${x.id===d.id?'active':''}" data-document-id="${x.id}"><span><strong>${esc(x.title)}</strong><small>${esc(x.updated_by)} · ${new Date(x.updated_at).toLocaleString('ko-KR')}</small></span>${statusChip(x.status)}</button>`).join('')}</div>
    <div class="panel document-editor">
      <div class="document-editor-head"><div><h3>${esc(d.title)}</h3><small class="muted">${esc(d.doc_type)} · 마지막 수정 ${new Date(d.updated_at).toLocaleString('ko-KR')}</small></div>${statusChip(d.status)}</div>
      <div class="document-controls">${selectField('document_status','상태',[['draft','초안'],['review','검토중'],['approved','승인됨'],['complete','완료']],d.status)}${field('document_editor','작성자',d.updated_by||'Team member')}</div>
      <div class="field"><label>공동 문서 내용 (Markdown)</label><textarea id="documentContent" class="document-content">${esc(d.content)}</textarea></div>
      <div class="form-actions"><button type="button" class="primary-btn" data-action="save-document">문서 저장</button></div>
      <div class="document-comments"><h3>Discussion</h3><form id="documentCommentForm" class="comment-form"><input name="author" value="Team member" aria-label="작성자"><input name="body" placeholder="이 문서에 의견 남기기" aria-label="댓글"><button class="mini-btn" type="submit">댓글</button></form>${comments.length?comments.map(c=>`<div class="comment"><strong>${esc(c.author)}</strong><span>${esc(c.body)}</span><small>${new Date(c.created_at).toLocaleString('ko-KR')}</small></div>`).join(''):'<div class="empty compact">아직 의견이 없습니다.</div>'}</div>
    </div>
  </div>`;
}
function renderProgress(){
  const cols=[['todo','예정'],['in_progress','진행중'],['review','검토'],['done','완료']];
  return `<div class="notice" style="margin-bottom:14px">AI 사용 여부와 관계없이 모든 작업은 같은 Task 상태와 Evidence 기준으로 표시됩니다. Task 카드를 누르면 상태를 바꿀 수 있습니다.</div><div class="kanban">${cols.map(([key,label])=>{const arr=state.snapshot.tasks.filter(t=>t.status===key);return `<div class="kanban-col"><div class="kanban-head"><span>${label}</span><span>${arr.length}</span></div>${arr.map(t=>`<div class="task-card" data-task-id="${t.id}"><div class="task-title">${esc(t.title)}</div><div style="margin-bottom:8px">${t.requirement_ref?`<span class="chip">${esc(t.requirement_ref)}</span>`:''} <span class="chip ${t.priority==='high'?'danger':''}">${esc(t.priority)}</span></div><div class="task-meta"><span>${esc(t.owner)}</span><span>#${t.id}</span></div></div>`).join('')||'<div class="empty">작업 없음</div>'}</div>`}).join('')}</div>`;
}
function layoutNodes(nodes){
  return nodes.map((n,i)=>({ ...n, px: 60+(i%5)*185, py: 70+Math.floor(i/5)*150 }));
}
function renderDiagram(view){
  const nodes=layoutNodes(state.snapshot.nodes.filter(n=>n.view===view));
  const edges=state.snapshot.edges.filter(e=>e.view===view);
  const pos=Object.fromEntries(nodes.map(n=>[n.id,n]));
  const lines=edges.map(e=>{ const a=pos[e.source_id],b=pos[e.target_id]; if(!a||!b)return''; const x1=a.px+150,y1=a.py+35,x2=b.px,y2=b.py+35; const mx=(x1+x2)/2,my=(y1+y2)/2; return `<g><path d="M${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}" fill="none" stroke="#aab4c3" stroke-width="2" marker-end="url(#arrow)"/>${e.label?`<text x="${mx}" y="${my-7}" text-anchor="middle" class="edge-label">${esc(e.label)}</text>`:''}</g>`}).join('');
  const labels={process:'시스템이 어떤 순서로 동작하는지',architecture:'어떤 시스템과 컴포넌트로 구성되는지',dataflow:'데이터가 어디서 생겨 어디로 이동하는지'};
  return `<div class="panel"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><div><h3>${titles[view]}</h3><p class="muted">${labels[view]}</p></div><div class="diagram-toolbar"><button class="mini-btn" data-action="add-node" data-view="${view}">+ 노드</button><button class="mini-btn" data-action="add-edge" data-view="${view}">+ 연결</button></div></div><div class="diagram-wrap"><div class="diagram"><svg viewBox="0 0 1000 520" preserveAspectRatio="none"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#aab4c3"/></marker></defs>${lines}</svg>${nodes.map(n=>`<div class="diagram-node" data-kind="${esc(n.kind)}" style="left:${n.px}px;top:${n.py}px"><strong>${esc(n.label)}</strong><small>${esc(n.kind)}${n.detail?' · '+esc(n.detail):''}</small></div>`).join('')}</div></div></div>`;
}
function renderIdeas(){
  const s=state.snapshot;
  return `<div class="split"><div class="panel"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Ideas</h3><button class="mini-btn" data-action="add-idea">+ 아이디어</button></div>${s.ideas.length?s.ideas.map(i=>`<div class="idea-card"><div style="display:flex;justify-content:space-between;gap:10px"><strong>${esc(i.title)}</strong>${statusChip(i.status)}</div><p class="muted">${esc(i.body)}</p><small>${esc(i.author)}</small></div>`).join(''):'<div class="empty">아이디어 없음</div>'}</div>
  <div class="panel"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Decisions / ADR</h3><button class="mini-btn" data-action="add-decision">+ 결정</button></div>${s.decisions.length?s.decisions.map(d=>`<div class="decision-card"><div style="display:flex;justify-content:space-between;gap:10px"><strong>${esc(d.title)}</strong>${statusChip(d.status)}</div><p class="muted">${esc(d.body)}</p><small>${esc(d.author)}</small></div>`).join(''):'<div class="empty">결정 없음</div>'}</div></div>`;
}
function renderTeam(){
  const s=state.snapshot;
  return `<div class="section-grid"><div class="panel"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Team</h3><button class="mini-btn" data-action="add-member">+ 팀원</button></div>${s.members.map(m=>`<div class="member-card"><div class="member-row"><div class="avatar">${esc(m.name.slice(0,1))}</div><div class="member-info"><strong>${esc(m.name)}</strong><div><small>${esc(m.role)}</small></div></div>${m.ai_provider==='none'?'<span class="chip">Human only</span>':`<span class="chip ai">${esc(m.ai_provider)}</span>`}</div></div>`).join('')}</div>
  <div><div class="ai-box"><strong>Bring Your Own AI</strong><p style="color:#aeb9cc">각 팀원이 자기 PC의 Codex / Claude Code / OpenCode / Antigravity CLI를 Local Bridge로 연결합니다. AI가 없어도 일반 팀원 기능은 동일합니다.</p><button class="mini-btn" data-action="bridge-help">Local Bridge 연결 방법</button></div><div class="panel" style="margin-top:18px"><h3>연결된 Bridge</h3>${s.bridges.length?s.bridges.map(b=>`<div class="member-card"><strong>${esc(b.member_name)} · ${esc(b.provider)}</strong><div><small>${esc(b.machine_name)} · 최근 연결 ${new Date(b.last_seen).toLocaleString('ko-KR')}</small></div></div>`).join(''):'<div class="empty">아직 연결된 AI Bridge가 없습니다.</div>'}</div></div></div>
  <div class="panel" style="margin-top:18px"><div style="display:flex;justify-content:space-between;align-items:center"><h3>AI Task Queue</h3><button class="mini-btn" data-action="add-ai-job">+ AI 작업</button></div>${s.ai_jobs.length?`<table class="table"><thead><tr><th>Job</th><th>Task</th><th>Provider</th><th>Member</th><th>Status</th></tr></thead><tbody>${s.ai_jobs.map(j=>`<tr><td>#${j.id}</td><td>#${j.task_id}</td><td>${esc(j.provider)}</td><td>${esc(j.member_name)}</td><td>${statusChip(j.status)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">AI 작업 없음</div>'}</div>`;
}
function bindViewActions(){
  document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>handleAction(b.dataset.action,b.dataset.view)));
  document.querySelectorAll('[data-task-id]').forEach(c=>c.addEventListener('click',()=>editTask(Number(c.dataset.taskId))));
  document.querySelectorAll('[data-document-id]').forEach(c=>c.addEventListener('click',()=>{state.selectedDocumentId=Number(c.dataset.documentId);render();}));
  const commentForm=$('#documentCommentForm'); if(commentForm) commentForm.addEventListener('submit',submitDocumentComment);
}
function closeModal(){ $('#modal').classList.add('hidden'); }
function openModal(title, html, onSubmit){
  $('#modalTitle').textContent=title; const f=$('#modalForm'); f.innerHTML=html+`<div class="form-actions"><button type="button" class="ghost-btn" id="cancelModal">취소</button><button type="submit" class="primary-btn">저장</button></div>`;
  $('#modal').classList.remove('hidden'); $('#cancelModal').onclick=closeModal;
  f.onsubmit=async e=>{ e.preventDefault(); try{ await onSubmit(new FormData(f)); closeModal(); await loadSnapshot(); toast('저장했습니다.'); }catch(err){toast(err.message);} };
}
function field(name,label,value='',type='text'){ return `<div class="field"><label>${esc(label)}</label><input name="${name}" type="${type}" value="${esc(value)}" required></div>`; }
function textarea(name,label,value=''){ return `<div class="field"><label>${esc(label)}</label><textarea name="${name}">${esc(value)}</textarea></div>`; }
function selectField(name,label,options,current=''){ return `<div class="field"><label>${esc(label)}</label><select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`; }
function openAddForView(){ handleAction({overview:'add-task',definition:'add-requirement',documents:'document-help',progress:'add-task',process:'add-node',architecture:'add-node',dataflow:'add-node',ideas:'add-idea',team:'add-member'}[state.view],['process','architecture','dataflow'].includes(state.view)?state.view:null); }
function handleAction(action, view){
  if(action==='new-project') return newProject(); if(action==='add-task') return addTask(); if(action==='add-requirement') return addRequirement(); if(action==='edit-goal') return editGoal();
  if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp();
  if(action==='add-node') return addNode(view); if(action==='add-edge') return addEdge(view); if(action==='add-idea') return addIdea(); if(action==='add-decision') return addDecision(); if(action==='add-member') return addMember(); if(action==='add-ai-job') return addAIJob(); if(action==='bridge-help') return bridgeHelp();
}
function newProject(){
  openModal('새 프로젝트 시작',field('name','프로젝트 이름')+textarea('goal','프로젝트 목표')+textarea('description','배경 / 문제 / 성공 기준'),async fd=>{
    const p=await api('/api/projects',{method:'POST',body:JSON.stringify(Object.fromEntries(fd))});
    state.projectId=p.id; state.selectedDocumentId=null; await loadProjects(); connectWs(); state.view='documents'; document.querySelectorAll('.nav-item').forEach(x=>x.classList.toggle('active',x.dataset.view==='documents')); $('#pageTitle').textContent=titles.documents;
  });
}
function documentHelp(){ toast('왼쪽 문서를 선택해 공동 작성하세요. 새 프로젝트에는 13종 템플릿이 자동 생성됩니다.'); }
async function saveDocument(){
  const d=state.snapshot.documents.find(x=>x.id===state.selectedDocumentId); if(!d)return;
  const content=$('#documentContent').value; const status=document.querySelector('[name="document_status"]').value; const updated_by=document.querySelector('[name="document_editor"]').value||'Team member';
  await api(`/api/documents/${d.id}`,{method:'PATCH',body:JSON.stringify({content,status,updated_by})}); await loadSnapshot(); toast('문서를 공유 저장했습니다.');
}
async function submitDocumentComment(e){
  e.preventDefault(); const d=state.snapshot.documents.find(x=>x.id===state.selectedDocumentId); const fd=new FormData(e.currentTarget); const o=Object.fromEntries(fd); if(!o.body?.trim()) return;
  await api(`/api/documents/${d.id}/comments`,{method:'POST',body:JSON.stringify(o)}); await loadSnapshot(); toast('댓글을 등록했습니다.');
}
function addTask(){ openModal('Task 추가',field('title','작업명')+textarea('description','설명')+field('owner','담당자','Unassigned')+field('requirement_ref','관련 요구사항','')+selectField('priority','우선순위',[['low','Low'],['medium','Medium'],['high','High']],'medium'),fd=>api(`/api/projects/${state.projectId}/tasks`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))})); }
function editTask(id){ const t=state.snapshot.tasks.find(x=>x.id===id); openModal(`Task #${id}`,field('title','작업명',t.title)+textarea('description','설명',t.description)+field('owner','담당자',t.owner)+selectField('status','상태',[['todo','예정'],['in_progress','진행중'],['review','검토'],['done','완료'],['blocked','차단']],t.status)+selectField('priority','우선순위',[['low','Low'],['medium','Medium'],['high','High']],t.priority)+field('requirement_ref','관련 요구사항',t.requirement_ref),fd=>api(`/api/tasks/${id}`,{method:'PATCH',body:JSON.stringify(Object.fromEntries(fd))})); }
function addRequirement(){ openModal('요구사항 추가',field('title','요구사항 제목')+textarea('detail','상세'),fd=>api(`/api/projects/${state.projectId}/requirements`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))})); }
function editGoal(){ const p=state.snapshot.project; openModal('프로젝트 목표 수정',textarea('goal','프로젝트 목표',p.goal)+textarea('description','설명',p.description),fd=>api(`/api/projects/${state.projectId}/goal`,{method:'PATCH',body:JSON.stringify(Object.fromEntries(fd))})); }
function addNode(view){ openModal(`${titles[view]} 노드 추가`,field('label','노드 이름')+selectField('kind','종류',[['service','Service'],['device','Device'],['database','Database'],['process','Process'],['decision','Decision'],['ui','UI'],['source','Source'],['sink','Sink'],['event','Event']],'service')+field('detail','설명',''),fd=>api(`/api/projects/${state.projectId}/nodes`,{method:'POST',body:JSON.stringify({...Object.fromEntries(fd),view})})); }
function addEdge(view){ const nodes=state.snapshot.nodes.filter(n=>n.view===view); const opts=nodes.map(n=>[String(n.id),n.label]); openModal(`${titles[view]} 연결 추가`,selectField('source_id','출발 노드',opts)+selectField('target_id','도착 노드',opts)+field('label','연결/데이터 라벨',''),fd=>{const o=Object.fromEntries(fd);return api(`/api/projects/${state.projectId}/edges`,{method:'POST',body:JSON.stringify({...o,source_id:Number(o.source_id),target_id:Number(o.target_id),view})})}); }
function addIdea(){ openModal('아이디어 추가',field('title','아이디어')+textarea('body','내용')+field('author','제안자','Team member'),fd=>api(`/api/projects/${state.projectId}/ideas`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))})); }
function addDecision(){ openModal('Decision / ADR 추가',field('title','결정 제목')+textarea('body','결정 이유와 영향')+field('author','작성자','Team'),fd=>api(`/api/projects/${state.projectId}/decisions`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))})); }
function addMember(){ openModal('팀원 추가',field('name','이름')+field('role','역할','Developer')+selectField('ai_provider','개인 AI',[['none','AI 사용 안 함'],['codex','Codex'],['claude','Claude Code'],['opencode','OpenCode'],['antigravity','Antigravity CLI']],'none'),fd=>api(`/api/projects/${state.projectId}/members`,{method:'POST',body:JSON.stringify(Object.fromEntries(fd))})); }
function addAIJob(){ const tasks=state.snapshot.tasks.filter(t=>t.status!=='done'); const members=state.snapshot.members.filter(m=>m.ai_provider!=='none'); if(!tasks.length||!members.length){toast('미완료 Task와 AI 사용 팀원이 필요합니다.');return;} openModal('개인 AI에 Task 전달',selectField('task_id','Task',tasks.map(t=>[String(t.id),`#${t.id} ${t.title}`]))+selectField('member_name','팀원',members.map(m=>[m.name,`${m.name} (${m.ai_provider})`]))+selectField('provider','Provider',[['codex','Codex'],['claude','Claude Code'],['opencode','OpenCode'],['antigravity','Antigravity CLI']],'codex')+field('repo_hint','로컬 Repository 경로 힌트','')+textarea('instruction','추가 지시','현재 Task 범위만 수행하고 변경 내용과 검증 결과를 남겨주세요.'),fd=>{const o=Object.fromEntries(fd);o.task_id=Number(o.task_id);return api(`/api/projects/${state.projectId}/ai-jobs`,{method:'POST',body:JSON.stringify(o)})}); }
function bridgeHelp(){
  const cmd=`python local_bridge/bridge.py register --server ${location.origin} --project ${state.projectId} --member "내 이름" --provider antigravity --repo D:\\my-project`;
  openModal('Local Bridge 연결',`<div class="notice">1) 프로그램을 팀원 PC에 내려받고 2) Codex / Claude Code / OpenCode / Antigravity CLI 중 사용할 CLI에 로그인한 뒤 3) Provider를 지정해 Bridge를 등록합니다.</div><div class="code-line">${esc(cmd)}</div><div class="notice">등록 시 발급된 token을 사용해 <b>run</b> 명령을 실행하면 해당 팀원에게 배정된 AI Task를 가져옵니다. 자세한 내용은 README의 BYOAI 항목을 참고하세요.</div>`,async()=>({}));
}
init();
