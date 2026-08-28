const state = {
  projects: [], projectId: null, snapshot: null, view: 'overview', ws: null, selectedDocumentId: null, documentEditMode: false,
  accessKey: sessionStorage.getItem('project_os_access_key') || ''
};
const titles = {
  overview:'Overview', definition:'Goal & Requirements', assistant:'AI Project Assistant', documents:'Project Documents', traceability:'Traceability', progress:'Development Progress',
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
  const map={done:['완료','good'],in_progress:['진행중','ai'],review:['검토','warn'],todo:['예정',''],blocked:['차단','danger'],defined:['정의됨','good'],accepted:['승인','good'],provisional:['AI 임시','warn'],open:['Open',''],discussing:['논의중','warn'],queued:['대기','warn'],claimed:['실행중','ai'],completed:['완료','good'],failed:['실패','danger'],draft:['초안',''],approved:['승인됨','good'],complete:['완료','good']};
  const [t,c]=map[status]||[status,'']; return `<span class="chip ${c}">${esc(t)}</span>`;
}
async function init(){
  bindNav();
  $('#newProjectBtn').addEventListener('click', newProject);
  $('#aiStartBtn').addEventListener('click', ()=>startAIProject(false));
  $('#deleteProjectBtn').addEventListener('click', deleteCurrentProject);
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
  select.innerHTML=state.projects.map(p=>`<option value="${p.id}">${p.lifecycle==='draft'?'🟡 설계중 · ':''}${esc(p.name)}</option>`).join('');
  if(state.projectId && !state.projects.some(p=>p.id===state.projectId)) state.projectId=null;
  if(!state.projectId && state.projects[0]) state.projectId=state.projects[0].id;
  select.value=state.projectId||'';
  $('#deleteProjectBtn').disabled=!state.projectId;
  select.onchange=async()=>{ state.projectId=Number(select.value); await loadSnapshot(); connectWs(); };
  if(state.projectId){ await loadSnapshot(); connectWs(); } else { state.snapshot=null; render(); }
}
async function loadSnapshot(){ state.snapshot=await api(`/api/projects/${state.projectId}/snapshot`); render(); }
function connectWs(){
  if(state.ws) state.ws.close();
  const proto=location.protocol==='https:'?'wss':'ws';
  const protocols=['project-os'];
  if(state.accessKey){
    const bytes=new TextEncoder().encode(state.accessKey);
    let binary=''; bytes.forEach(byte=>{binary+=String.fromCharCode(byte)});
    const encoded=btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    protocols.push(`access-key.${encoded}`);
  }
  state.ws=new WebSocket(`${proto}://${location.host}/ws/projects/${state.projectId}`,protocols);
  state.ws.onopen=()=>{ $('#liveText').textContent='실시간 공유 연결됨'; };
  state.ws.onmessage=e=>{ let msg={}; try{msg=JSON.parse(e.data||'{}')}catch(_e){}; if(msg.scope==='live_draft') $('#liveText').textContent='Live Draft 자동 반영됨'; if(msg.scope==='live_draft_promoted') $('#liveText').textContent='정식 프로젝트로 승격됨'; loadSnapshot().catch(()=>{}); };
  state.ws.onclose=()=>{ $('#liveText').textContent='연결 끊김 · 새로고침 필요'; };
}
function setAccessKey(){
  const v=prompt('서버에 APP_ACCESS_KEY를 설정했다면 접속키를 입력하세요.\n설정하지 않았다면 비워두세요.',state.accessKey||'');
  if(v===null) return; state.accessKey=v.trim(); sessionStorage.setItem('project_os_access_key',state.accessKey); loadProjects().catch(e=>toast(e.message));
}
function render(){
  if(!state.snapshot){ $('#content').innerHTML='<div class="panel onboarding"><h2>새 프로젝트를 시작하세요</h2><p class="muted">AI가 있으면 대화만으로 시작하고, 없으면 직접 입력할 수 있습니다.</p><div class="onboarding-actions"><button class="primary-btn" data-action="start-ai-project">✦ AI와 대화하며 시작</button><button class="ghost-btn" data-action="new-project">직접 입력해서 시작</button></div></div>'; bindViewActions(); return; }
  const fn={overview:renderOverview,definition:renderDefinition,assistant:renderAssistant,documents:renderDocuments,traceability:renderTraceability,progress:renderProgress,process:()=>renderDiagram('process'),architecture:()=>renderDiagram('architecture'),dataflow:()=>renderDiagram('dataflow'),ideas:renderIdeas,team:renderTeam}[state.view];
  const draftBanner=state.snapshot.project.lifecycle==='draft'?`<div class="notice" style="margin-bottom:16px"><strong>🟡 AI Design Live Draft</strong> · AI와 대화 중 결정되는 내용이 실시간 반영됩니다. <strong>/apply 전에는 정식 확정 프로젝트가 아닙니다.</strong><br><small>Documents · Requirements · Decisions · Process/Architecture/Data Flow가 WebSocket으로 자동 갱신됩니다.</small></div>`:'';
  $('#content').innerHTML=draftBanner+fn(); bindViewActions();
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
function renderAssistant(){
  const s=state.snapshot; const conv=s.conversation;
  if(!conv){
    return `<div class="panel onboarding"><div class="eyebrow">CONVERSATIONAL PROJECT SETUP</div><h2>이 프로젝트를 AI와 대화하며 정리</h2><p class="muted">Codex, Claude Code, OpenCode, Antigravity CLI 중 자신의 AI를 연결할 수 있습니다. AI가 제안한 내용은 승인 전까지 프로젝트에 적용되지 않습니다.</p><button class="primary-btn" data-action="start-assistant-current">✦ AI Project Interviewer 시작</button></div>`;
  }
  const session=conv.session, pending=conv.pending||{}, updates=pending.project_updates||{}, quality=conv.quality||{};
  const fields=Object.entries(s.project_brief||{});
  const hasPending=Object.keys(updates).length || (pending.requirements||[]).length || (pending.decisions||[]).length || (pending.document_updates||[]).length || (pending.design_updates||[]).length;
  const messages=(conv.messages||[]).map(m=>`<div class="chat-message ${m.role==='user'?'user':'assistant'}"><div class="chat-role">${m.role==='user'?'나':'AI Project Interviewer'}</div><div>${esc(m.content).replace(/\n/g,'<br>')}</div></div>`).join('');
  const proposalRows=Object.entries(updates).map(([k,v])=>`<div class="proposal-row"><strong>${esc(k)}</strong><span>${esc(v)}</span></div>`).join('');
  const reqs=(pending.requirements||[]).map(r=>`<div class="proposal-row"><strong>${esc(r.ref||'REQ')} ${esc(r.title)}</strong><span>${esc(r.detail||'')}</span></div>`).join('');
  const decisions=(pending.decisions||[]).map(d=>`<div class="proposal-row"><strong>Decision · ${esc(d.title)}</strong><span>${esc(d.body||'')}</span></div>`).join('');
  const docs=(pending.document_updates||[]).map(d=>`<div class="proposal-row"><strong>Document · ${esc(d.doc_type)}</strong><span>${esc(d.reason||'문서 수정 제안')}</span></div>`).join('');
  const designs=(pending.design_updates||[]).map(d=>`<div class="proposal-row design-proposal"><strong>Canvas · ${esc(d.view)} · ${esc(d.mode||'merge')}</strong><span>${esc(d.reason||'대화 기반 설계 제안')}<br><small>노드 ${(d.nodes||[]).length}개 · 연결 ${(d.edges||[]).length}개 · ${(d.nodes||[]).map(n=>esc(n.label)).join(' → ')}</small></span></div>`).join('');
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
      <div class="panel"><div style="display:flex;justify-content:space-between;gap:8px;align-items:center"><h3>AI 변경 제안</h3>${hasPending?'<button class="primary-btn" data-action="apply-conversation">제안 적용</button>':''}</div>${hasPending?(proposalRows+reqs+decisions+docs+designs):'<div class="empty">아직 적용 대기 중인 제안이 없습니다.</div>'}${(pending.pending||[]).length?`<div class="notice"><strong>아직 미정</strong><ul>${pending.pending.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}</div>
      <div class="panel"><h3>Local AI Connector</h3>${bridge?`<div class="notice">✓ ${esc(bridge.member_name)} / ${esc(bridge.provider)} 연결됨<br><small>${esc(bridge.machine_name)} · ${new Date(bridge.last_seen).toLocaleString('ko-KR')}</small></div>`:'<div class="notice">이 AI 계정의 Connector가 아직 감지되지 않았습니다.</div>'}<button class="ghost-btn" data-action="assistant-pair-help">연결 명령 보기</button></div>
    </div>
  </div>`;
}

function inlineMarkdown(text){
  let s=esc(text??'');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/\*([^*]+)\*/g,'<em>$1</em>');
  return s;
}
function markdownHeadings(md){
  return String(md||'').split(/\r?\n/).map((line,i)=>{const m=line.match(/^(#{2,3})\s+(.+)$/);return m?{level:m[1].length,text:m[2].replace(/[*_`]/g,'').trim(),id:`sec-${i}`}:null}).filter(Boolean);
}
function markdownTable(lines,start){
  if(start+1>=lines.length || !/^\s*\|?\s*:?-+/.test(lines[start+1].replace(/^\s*\|/,''))) return null;
  const rows=[]; let i=start;
  while(i<lines.length && lines[i].includes('|') && lines[i].trim()){ rows.push(lines[i]); i++; }
  if(rows.length<2) return null;
  const cells=row=>row.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
  const head=cells(rows[0]); const body=rows.slice(2).map(cells);
  return {html:`<div class="doc-table-wrap"><table class="doc-table"><thead><tr>${head.map(c=>`<th>${inlineMarkdown(c)}</th>`).join('')}</tr></thead><tbody>${body.map(r=>`<tr>${head.map((_,idx)=>`<td>${inlineMarkdown(r[idx]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,next:i};
}
function renderMarkdownDocument(md){
  const lines=String(md||'').replace(/\r/g,'').split('\n');
  let out='', i=0, inCode=false, code=[];
  const closeCode=()=>{if(inCode){out+=`<pre class="doc-code"><code>${esc(code.join('\n'))}</code></pre>`;inCode=false;code=[];}};
  while(i<lines.length){
    const line=lines[i];
    if(line.trim().startsWith('```')){ if(inCode) closeCode(); else {inCode=true;code=[];} i++; continue; }
    if(inCode){code.push(line);i++;continue;}
    const table=markdownTable(lines,i); if(table){out+=table.html;i=table.next;continue;}
    const h=line.match(/^(#{1,4})\s+(.+)$/);
    if(h){const level=h[1].length;const id=`sec-${i}`;out+=`<h${level} id="${id}">${inlineMarkdown(h[2])}</h${level}>`;i++;continue;}
    const quote=line.match(/^>\s?(.*)$/); if(quote){const q=[];while(i<lines.length&&/^>/.test(lines[i])){q.push(lines[i].replace(/^>\s?/,''));i++;}out+=`<div class="doc-callout">${q.map(x=>`<p>${inlineMarkdown(x)}</p>`).join('')}</div>`;continue;}
    const task=line.match(/^\s*-\s+\[([ xX])\]\s+(.+)$/); if(task){out+=`<div class="doc-check"><span class="doc-checkbox ${task[1].trim()?'checked':''}">${task[1].trim()?'✓':''}</span><span>${inlineMarkdown(task[2])}</span></div>`;i++;continue;}
    const bullet=line.match(/^\s*[-*]\s+(.+)$/); if(bullet){const arr=[];while(i<lines.length){const m=lines[i].match(/^\s*[-*]\s+(.+)$/);if(!m)break;arr.push(m[1]);i++;}out+=`<ul>${arr.map(x=>`<li>${inlineMarkdown(x)}</li>`).join('')}</ul>`;continue;}
    const num=line.match(/^\s*\d+\.\s+(.+)$/); if(num){const arr=[];while(i<lines.length){const m=lines[i].match(/^\s*\d+\.\s+(.+)$/);if(!m)break;arr.push(m[1]);i++;}out+=`<ol>${arr.map(x=>`<li>${inlineMarkdown(x)}</li>`).join('')}</ol>`;continue;}
    if(/^---+$/.test(line.trim())){out+='<hr>';i++;continue;}
    if(!line.trim()){i++;continue;}
    const para=[];while(i<lines.length&&lines[i].trim()&&!/^(#{1,4})\s+/.test(lines[i])&&!/^\s*[-*]\s+/.test(lines[i])&&!/^\s*\d+\.\s+/.test(lines[i])&&!/^>/.test(lines[i])&&!lines[i].trim().startsWith('```')){if(markdownTable(lines,i))break;para.push(lines[i].trim());i++;}
    if(para.length)out+=`<p>${inlineMarkdown(para.join(' '))}</p>`;else i++;
  }
  closeCode(); return out;
}
function documentQuality(d){
  const c=String(d.content||''); const headings=(c.match(/^##\s+/gm)||[]).length; const tables=(c.match(/^\|.+\|$/gm)||[]).length; const tbd=(c.match(/TBD|작성 필요|확인 필요/g)||[]).length;
  let score=Math.min(100,35+headings*7+Math.min(25,tables*2)-Math.min(25,tbd*3));
  if(c.length>1800)score+=8; score=Math.max(20,Math.min(100,score));
  const label=score>=85?'공유 가능':score>=65?'검토 필요':'작성 중'; return {score,label};
}
function renderDocuments(){
  const s=state.snapshot;
  if(!s.documents?.length) return '<div class="empty">프로젝트 문서가 없습니다.</div>';
  if(!state.selectedDocumentId || !s.documents.some(d=>d.id===state.selectedDocumentId)) state.selectedDocumentId=s.documents[0].id;
  const d=s.documents.find(x=>x.id===state.selectedDocumentId);
  const comments=s.document_comments.filter(c=>c.document_id===d.id);
  const completed=s.documents.filter(x=>['review','approved','complete'].includes(x.status)).length;
  const headings=markdownHeadings(d.content); const quality=documentQuality(d); const editing=state.documentEditMode;
  const renderedDocumentBody=d.doc_type==='milestone'&&typeof MilestoneGantt!=='undefined'?MilestoneGantt.render(d.content,d.title,s.project.name):renderMarkdownDocument(d.content);
  const toc=headings.length?`<nav class="doc-toc"><div class="doc-toc-title">목차</div>${headings.map(h=>`<a class="lv${h.level}" href="#${h.id}">${esc(h.text)}</a>`).join('')}</nav>`:'';
  return `<div class="documents-head"><div><div class="eyebrow">DELIVERABLE WORKSPACE</div><h2>프로젝트 공식 산출물 ${completed}/${s.documents.length}</h2><p class="muted">Markdown은 원본 포맷으로 유지하고, 기본 화면에서는 실무 보고서 형태로 렌더링합니다.</p></div><div><button class="mini-btn" data-action="export-project">산출물 패키지 ZIP</button></div></div>
  <div class="document-layout professional-doc-layout">
    <div class="panel document-list">${s.documents.map(x=>`<button class="document-item ${x.id===d.id?'active':''}" data-document-id="${x.id}"><span><strong>${esc(x.title)}</strong><small>${esc(x.updated_by)} · ${new Date(x.updated_at).toLocaleString('ko-KR')}</small></span>${statusChip(x.status)}</button>`).join('')}</div>
    <div class="document-stage">
      <div class="document-stage-toolbar">
        <div><span class="chip ${quality.score>=85?'good':quality.score>=65?'warn':''}">문서 품질 ${quality.score} · ${quality.label}</span>${s.project.lifecycle==='draft'?'<span class="chip warn">Live Draft</span>':''}</div>
        <div class="doc-view-actions"><button class="mini-btn ${!editing?'active':''}" data-action="document-read-mode">문서 보기</button><button class="mini-btn ${editing?'active':''}" data-action="document-edit-mode">Markdown 편집</button><button class="mini-btn" data-action="print-document">인쇄/PDF</button></div>
      </div>
      ${editing?`<div class="panel document-editor">
        <div class="document-editor-head"><div><h3>${esc(d.title)}</h3><small class="muted">${esc(d.doc_type)} · 마지막 수정 ${new Date(d.updated_at).toLocaleString('ko-KR')}</small></div>${statusChip(d.status)}</div>
        <div class="document-controls">${selectField('document_status','상태',[['draft','초안'],['review','검토중'],['approved','승인됨'],['complete','완료']],d.status)}${field('document_editor','작성자',d.updated_by||'Team member')}</div>
        <div class="field"><label>Markdown 원문</label><textarea id="documentContent" class="document-content">${esc(d.content)}</textarea></div>
        <div class="form-actions"><button type="button" class="ghost-btn" data-action="export-document">Markdown 다운로드</button><button type="button" class="primary-btn" data-action="save-document">문서 저장</button></div>
      </div>`:`<article class="professional-document" id="printableDocument">
        <header class="doc-cover">
          <div class="doc-cover-kicker">TEAM PROJECT OS · PROJECT DELIVERABLE</div>
          <h1>${esc(d.title)}</h1>
          <p class="doc-project-name">${esc(s.project.name)}</p>
          <div class="doc-meta-grid"><div><span>문서 상태</span><strong>${statusChip(d.status)}</strong></div><div><span>작성/갱신</span><strong>${esc(d.updated_by)}</strong></div><div><span>최종 수정</span><strong>${new Date(d.updated_at).toLocaleString('ko-KR')}</strong></div><div><span>Lifecycle</span><strong>${s.project.lifecycle==='draft'?'설계 중 Draft':'Active Project'}</strong></div></div>
        </header>
        <div class="doc-body-layout">${toc}<section class="doc-content-rendered">${renderedDocumentBody}</section></div>
        <footer class="doc-footer"><span>${esc(s.project.name)}</span><span>${esc(d.title)} · Team Project OS</span></footer>
      </article>`}
      <div class="panel document-comments"><h3>Review / Discussion</h3><form id="documentCommentForm" class="comment-form"><input name="author" value="Team member" aria-label="작성자"><input name="body" placeholder="검토 의견 또는 변경 요청" aria-label="댓글"><button class="mini-btn" type="submit">의견 등록</button></form>${comments.length?comments.map(c=>`<div class="comment"><strong>${esc(c.author)}</strong><span>${esc(c.body)}</span><small>${new Date(c.created_at).toLocaleString('ko-KR')}</small></div>`).join(''):'<div class="empty compact">아직 검토 의견이 없습니다.</div>'}</div>
    </div>
  </div>`;
}
function renderTraceability(){
  const s=state.snapshot; const explicit=s.trace_links||[]; const derived=s.derived_trace_links||[]; const all=[...explicit,...derived];
  return `<div class="panel"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap"><div><div class="eyebrow">END-TO-END TRACEABILITY</div><h2>요구사항부터 QA까지 연결</h2><p class="muted">기획/요구사항 → 기능 → IA/화면 → API/Architecture → Task → QA 관계를 연결합니다. Task의 REQ 참조는 자동 연결됩니다.</p></div><button class="mini-btn" data-action="add-trace-link">+ 연결 추가</button></div></div>
  <div class="panel" style="margin-top:18px">${all.length?`<table class="table"><thead><tr><th>Source</th><th>Relation</th><th>Target</th><th>Note</th><th></th></tr></thead><tbody>${all.map(l=>`<tr><td><strong>${esc(l.source_type)}:${esc(l.source_ref)}</strong></td><td>${esc(l.relation)}</td><td><strong>${esc(l.target_type)}:${esc(l.target_ref)}</strong></td><td>${esc(l.note||'')}</td><td>${l.derived?'<span class="chip ai">자동</span>':`<button class="mini-btn" data-action="delete-trace" data-view="${l.id}">삭제</button>`}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">아직 연결이 없습니다. 요구사항과 구현/QA 항목을 연결해보세요.</div>'}</div>`;
}
function renderProgress(){
  const cols=[['todo','예정'],['in_progress','진행중'],['review','검토'],['done','완료']];
  return `<div class="notice" style="margin-bottom:14px">AI 사용 여부와 관계없이 모든 작업은 같은 Task 상태와 Evidence 기준으로 표시됩니다. Task 카드를 누르면 상태를 바꿀 수 있습니다.</div><div class="kanban">${cols.map(([key,label])=>{const arr=state.snapshot.tasks.filter(t=>t.status===key);return `<div class="kanban-col"><div class="kanban-head"><span>${label}</span><span>${arr.length}</span></div>${arr.map(t=>`<div class="task-card" data-task-id="${t.id}"><div class="task-title">${esc(t.title)}</div><div style="margin-bottom:8px">${t.requirement_ref?`<span class="chip">${esc(t.requirement_ref)}</span>`:''} <span class="chip ${t.priority==='high'?'danger':''}">${esc(t.priority)}</span></div><div class="task-meta"><span>${esc(t.owner)}</span><span>#${t.id}</span></div></div>`).join('')||'<div class="empty">작업 없음</div>'}</div>`}).join('')}</div>`;
}
function diagramMeta(view){
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
  document.querySelectorAll('[data-document-id]').forEach(c=>c.addEventListener('click',()=>{state.selectedDocumentId=Number(c.dataset.documentId);state.documentEditMode=false;render();}));
  const commentForm=$('#documentCommentForm'); if(commentForm) commentForm.addEventListener('submit',submitDocumentComment);
  const conversationForm=$('#conversationForm'); if(conversationForm) conversationForm.addEventListener('submit',submitConversationMessage);
  const chat=$('#chatMessages'); if(chat) chat.scrollTop=chat.scrollHeight;
}
function closeModal(){ $('#modal').classList.add('hidden'); }
function openModal(title, html, onSubmit){
  $('#modalTitle').textContent=title; const f=$('#modalForm'); f.innerHTML=html+`<div class="form-actions"><button type="button" class="ghost-btn" id="cancelModal">취소</button><button type="submit" class="primary-btn">저장</button></div>`;
  $('#modal').classList.remove('hidden'); $('#cancelModal').onclick=closeModal;
  f.onsubmit=async e=>{ e.preventDefault(); try{ await onSubmit(new FormData(f)); closeModal(); await loadSnapshot(); toast('저장했습니다.'); }catch(err){toast(err.message);} };
}
function field(name,label,value='',type='text'){ return `<div class="field"><label>${esc(label)}</label><input name="${name}" type="${type}" value="${esc(value)}" required></div>`; }
function textarea(name,label,value=''){ return `<div class="field"><label>${esc(label)}</label><textarea name="${name}">${esc(value)}</textarea></div>`; }
function guidedTextarea(name,label,hint,example,value=''){
  return `<div class="field intake-field"><label>${esc(label)}</label><small class="field-hint">${esc(hint)}</small><textarea name="${name}" placeholder="${esc(example)}">${esc(value)}</textarea></div>`;
}
function selectField(name,label,options,current=''){ return `<div class="field"><label>${esc(label)}</label><select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}" ${v===current?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`; }
function openAddForView(){ handleAction({overview:'add-task',definition:'add-requirement',assistant:'start-assistant-current',documents:'document-help',traceability:'add-trace-link',progress:'add-task',process:'add-node',architecture:'add-node',dataflow:'add-node',ideas:'add-idea',team:'add-member'}[state.view],['process','architecture','dataflow'].includes(state.view)?state.view:null); }
function handleAction(action, view){
  if(action==='new-project') return newProject(); if(action==='start-ai-project') return startAIProject(false); if(action==='start-assistant-current') return startAIProject(true); if(action==='apply-conversation') return applyConversation(); if(action==='assistant-pair-help') return assistantPairHelp(); if(action==='add-task') return addTask(); if(action==='add-requirement') return addRequirement(); if(action==='edit-goal') return editGoal();
  if(action==='save-document') return saveDocument(); if(action==='document-help') return documentHelp(); if(action==='document-read-mode'){state.documentEditMode=false;return render();} if(action==='document-edit-mode'){state.documentEditMode=true;return render();} if(action==='print-document') return window.print(); if(action==='export-project') return exportProject(); if(action==='export-document') return exportDocument(); if(action==='add-trace-link') return addTraceLink(); if(action==='delete-trace') return deleteTrace(view);
  if(action==='add-node') return addNode(view); if(action==='add-edge') return addEdge(view); if(action==='add-idea') return addIdea(); if(action==='add-decision') return addDecision(); if(action==='add-member') return addMember(); if(action==='add-ai-job') return addAIJob(); if(action==='bridge-help') return bridgeHelp();
}
function startAIProject(useCurrent=false){
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

async function deleteCurrentProject(){
  if(!state.projectId || !state.snapshot?.project) return;
  const name=state.snapshot.project.name;
  const typed=prompt(`프로젝트를 영구 삭제합니다.\n문서, Task, Canvas, 대화 기록 등 이 프로젝트의 데이터가 함께 삭제됩니다.\n\n삭제하려면 프로젝트 이름을 정확히 입력하세요:\n${name}`);
  if(typed===null) return;
  if(typed!==name){ toast('프로젝트 이름이 일치하지 않아 삭제하지 않았습니다.'); return; }
  if(!confirm(`정말 "${name}" 프로젝트를 영구 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;
  try{
    await api(`/api/projects/${state.projectId}?confirm_name=${encodeURIComponent(name)}`,{method:'DELETE'});
    if(state.ws){ state.ws.close(); state.ws=null; }
    state.projectId=null; state.snapshot=null; state.selectedDocumentId=null;
    await loadProjects();
    toast('프로젝트를 삭제했습니다.');
  }catch(err){ toast(err.message); }
}

function assistantPairHelp(){
  const c=state.snapshot.conversation; if(!c)return;
  const member=c.session.member_name, provider=c.session.provider;
  const access=state.accessKey?` --access-key "${state.accessKey}"`:'';
  const register=`python local_bridge/bridge.py assistant-register --server ${location.origin} --member "${member}" --provider ${provider}${access}`;
  const run=`python local_bridge/bridge.py assistant-run`;
  openModal('AI Project Assistant Connector',`<div class="notice">프로젝트별로 다시 등록할 필요가 없습니다. 이 서버에 내 AI를 한 번 Pair하면 이후 대화형 프로젝트에서도 같은 Connector를 사용할 수 있습니다.</div><label>1. 최초 1회 Pair</label><div class="code-line">${esc(register)}</div><label>2. 대화 수신 실행</label><div class="code-line">${esc(run)}</div><div class="notice">Codex / Claude Code / OpenCode / Antigravity CLI는 먼저 각 CLI에서 로그인되어 있어야 합니다.</div>`,async()=>({}));
}

function newProject(){
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

async function downloadFile(url, filename){
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
