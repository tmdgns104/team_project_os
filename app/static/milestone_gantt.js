(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api;
  if(root) root.MilestoneGantt=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';

  function esc(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
  function cells(line){return String(line||'').trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());}
  function key(v){return String(v||'').toLowerCase().replace(/[\s_\-()/]/g,'');}
  function clampWeek(v){const n=Number.parseInt(String(v||'').replace(/[^0-9]/g,''),10);return Number.isFinite(n)?Math.max(1,Math.min(52,n)):null;}
  function normalizeStatus(v){
    const s=String(v||'Draft').trim().toLowerCase();
    if(/done|complete|완료|approved/.test(s)) return 'done';
    if(/progress|진행/.test(s)) return 'in_progress';
    if(/review|검토/.test(s)) return 'review';
    if(/block|지연|위험/.test(s)) return 'blocked';
    if(/todo|예정/.test(s)) return 'todo';
    return 'draft';
  }
  function findStartDate(md){
    const m=String(md||'').match(/(?:기준\s*시작일|Start\s*Date)\s*(?:\*\*)?\s*[·:]\s*(\d{4}-\d{2}-\d{2})/i);
    return m?m[1]:null;
  }
  function currentWeek(startDate){
    if(!startDate) return null;
    const s=new Date(startDate+'T00:00:00'); if(Number.isNaN(s.getTime())) return null;
    const diff=Date.now()-s.getTime(); if(diff<0) return null;
    return Math.floor(diff/(7*24*3600*1000))+1;
  }
  function parseScheduleTable(md){
    const lines=String(md||'').replace(/\r/g,'').split('\n');
    for(let i=0;i<lines.length-1;i++){
      if(!lines[i].includes('|')||!/^\s*\|?\s*:?-+/.test(lines[i+1].replace(/^\s*\|/,''))) continue;
      const head=cells(lines[i]); const hk=head.map(key);
      const phaseIdx=hk.findIndex(x=>['phase','level','단계','step'].includes(x));
      const taskIdx=hk.findIndex(x=>['task','작업','업무','taskname'].includes(x));
      const startIdx=hk.findIndex(x=>['startweek','시작주','시작주차','fromweek'].includes(x));
      const endIdx=hk.findIndex(x=>['endweek','종료주','종료주차','toweek'].includes(x));
      if(taskIdx<0||startIdx<0||endIdx<0) continue;
      const ownerIdx=hk.findIndex(x=>['owner','담당','담당자'].includes(x));
      const statusIdx=hk.findIndex(x=>['status','상태'].includes(x));
      const idIdx=hk.findIndex(x=>['id','taskid','wbs'].includes(x));
      const rows=[]; let j=i+2;
      while(j<lines.length&&lines[j].trim()&&lines[j].includes('|')){
        const c=cells(lines[j]);
        const start=clampWeek(c[startIdx]), end=clampWeek(c[endIdx]);
        const task=String(c[taskIdx]||'').trim();
        if(task) rows.push({
          phase:String(c[phaseIdx]||'기타').trim()||'기타', id:idIdx>=0?String(c[idIdx]||'').trim():'', task,
          start, end:end&&start?Math.max(start,end):end, owner:ownerIdx>=0?String(c[ownerIdx]||'').trim():'TBD',
          status:statusIdx>=0?String(c[statusIdx]||'Draft').trim():'Draft', inferred:false
        });
        j++;
      }
      if(rows.length) return rows;
    }
    return [];
  }
  function parseLegacyMilestones(md){
    const lines=String(md||'').replace(/\r/g,'').split('\n'); const rows=[];
    let found=false;
    for(let i=0;i<lines.length-1;i++){
      const h=cells(lines[i]).map(key);
      if(h.includes('milestone')&&h.includes('상태')){found=true;i+=2;break;}
    }
    if(!found) return rows;
    let idx=0;
    for(const line of lines){
      const c=cells(line); if(!/^M\d+/i.test(c[0]||'')) continue;
      const start=idx*4+1, end=start+3; idx++;
      rows.push({phase:`${c[0]} · ${c[1]||'Milestone'}`,id:c[0],task:c[2]||c[1]||'Milestone',start,end,owner:'TBD',status:c[c.length-1]||'Draft',inferred:true});
    }
    return rows;
  }
  function parse(md){
    let rows=parseScheduleTable(md); let inferred=false;
    if(!rows.length){rows=parseLegacyMilestones(md);inferred=rows.length>0;}
    const scheduled=rows.filter(r=>r.start&&r.end);
    const maxWeek=Math.max(16,...scheduled.map(r=>r.end||1));
    const weeks=Math.min(52,Math.ceil(maxWeek/4)*4);
    const startDate=findStartDate(md); const nowWeek=currentWeek(startDate);
    return {rows,weeks,startDate,currentWeek:nowWeek&&nowWeek<=weeks?nowWeek:null,inferred};
  }
  function phaseGroups(rows){
    const out=[]; let cur=null;
    rows.forEach((r,i)=>{
      if(!cur||cur.phase!==r.phase){cur={phase:r.phase,start:i,count:1};out.push(cur);} else cur.count++;
    });
    return out;
  }
  function render(md,title,projectName){
    const data=parse(md); const rows=data.rows;
    if(!rows.length) return `<div class="milestone-empty"><strong>아직 개발 일정이 구체화되지 않았습니다.</strong><span>Markdown 편집에서 Phase / Task / Start Week / End Week 표를 작성하면 Gantt 일정표로 자동 표시됩니다.</span></div>`;
    const groups=phaseGroups(rows); const phaseAt=new Map(groups.map(g=>[g.start,g]));
    const months=[]; for(let w=1;w<=data.weeks;w+=4) months.push({label:`${Math.floor((w-1)/4)+1} month`,start:w,count:Math.min(4,data.weeks-w+1)});
    const monthHead=months.map(m=>`<th class="gantt-month" colspan="${m.count}">${esc(m.label)}</th>`).join('');
    const weekHead=Array.from({length:data.weeks},(_,i)=>`<th class="gantt-week ${data.currentWeek===i+1?'is-current':''}">${i+1}W</th>`).join('');
    const body=rows.map((r,i)=>{
      const g=phaseAt.get(i); const status=normalizeStatus(r.status); const start=r.start, end=r.end;
      const weekCells=Array.from({length:data.weeks},(_,wi)=>{
        const w=wi+1, active=start&&end&&w>=start&&w<=end;
        const cls=['gantt-cell',data.currentWeek===w?'is-current':'',active?'is-active':'',active&&w===start?'bar-start':'',active&&w===end?'bar-end':'',active?`status-${status}`:''].filter(Boolean).join(' ');
        return `<td class="${cls}" title="${active?esc(`${r.task} · ${start}W~${end}W · ${r.status}`):''}"></td>`;
      }).join('');
      return `<tr>${g?`<td class="gantt-phase" rowspan="${g.count}"><strong>${esc(g.phase)}</strong></td>`:''}<td class="gantt-task"><div><strong>${esc(r.task)}</strong>${r.id?`<small>${esc(r.id)}</small>`:''}</div><span>${esc(r.owner||'TBD')}</span></td>${weekCells}</tr>`;
    }).join('');
    const scheduled=rows.filter(r=>r.start&&r.end).length;
    return `<section class="milestone-deliverable">
      <header class="milestone-summary"><div><div class="eyebrow">DEVELOPMENT MILESTONE · GANTT</div><h2>${esc(title||'개발 마일스톤')}</h2><p>${esc(projectName||'')} · ${data.startDate?`기준 시작일 ${esc(data.startDate)}`:'상대 주차 기준 계획'}</p></div><div class="milestone-kpis"><span><b>${new Set(rows.map(r=>r.phase)).size}</b> Phases</span><span><b>${rows.length}</b> Tasks</span><span><b>${scheduled}</b> Scheduled</span><span><b>${data.weeks}</b> Weeks</span></div></header>
      ${data.inferred?'<div class="milestone-notice">기존 Milestone 표를 기준으로 임시 주차를 추정해 표시했습니다. Markdown 편집에서 Gantt Schedule 표를 작성하면 정확한 일정으로 전환됩니다.</div>':''}
      <div class="gantt-legend"><span><i class="status-done"></i>완료</span><span><i class="status-in_progress"></i>진행</span><span><i class="status-review"></i>검토</span><span><i class="status-todo"></i>예정/초안</span><span><i class="status-blocked"></i>지연/차단</span>${data.currentWeek?'<span><i class="is-current"></i>현재 주차</span>':''}</div>
      <div class="gantt-scroll"><table class="gantt-table"><thead><tr><th class="gantt-level" rowspan="2">Level</th><th class="gantt-task-head" rowspan="2">Task</th>${monthHead}</tr><tr>${weekHead}</tr></thead><tbody>${body}</tbody></table></div>
    </section>`;
  }
  return {parse,render,normalizeStatus};
});
