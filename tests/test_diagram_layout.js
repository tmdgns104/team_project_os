const assert = require('assert');
const DiagramLayout = require('../app/static/diagram_layout.js');

function overlap(a,b){
  return !(a.x+a.width<=b.x || b.x+b.width<=a.x || a.y+a.height<=b.y || b.y+b.height<=a.y);
}

const nodes = [
  {id:1,label:'PLC Simulator',kind:'device',detail:'Mitsubishi simulator'},
  {id:2,label:'PLC Gateway',kind:'service',detail:'Protocol adapter'},
  {id:3,label:'MES Backend',kind:'service',detail:'FastAPI service'},
  {id:4,label:'Production Database',kind:'database',detail:'SQLite provisional'},
  {id:5,label:'Operator HMI',kind:'ui',detail:'Web dashboard'},
  {id:6,label:'Alarm Decision',kind:'decision',detail:'Abnormal state branch'},
];
const edges = [
  {id:1,source_id:1,target_id:2,label:'PLC tags'},
  {id:2,source_id:2,target_id:3,label:'normalized events'},
  {id:3,source_id:3,target_id:4,label:'production record'},
  {id:4,source_id:3,target_id:5,label:'status / KPI'},
  {id:5,source_id:3,target_id:6,label:'evaluate alarm'},
  {id:6,source_id:6,target_id:5,label:'warning'},
];

for (const view of ['process','architecture','dataflow']){
  const layout = DiagramLayout.layout(view,nodes,edges);
  assert.strictEqual(layout.nodes.length,nodes.length,`${view}: all nodes laid out`);
  assert.strictEqual(layout.edges.length,edges.length,`${view}: all edges routed`);
  assert(layout.width>=960 && layout.height>=440,`${view}: usable canvas`);

  for(let i=0;i<layout.nodes.length;i++){
    for(let j=i+1;j<layout.nodes.length;j++){
      assert(!overlap(layout.nodes[i],layout.nodes[j]),`${view}: nodes must not overlap (${layout.nodes[i].label}/${layout.nodes[j].label})`);
    }
  }

  const pos = new Map(layout.nodes.map(n=>[n.id,n]));
  for(const e of layout.edges){
    assert(!/NaN|undefined/.test(e.path),`${view}: valid edge path`);
    const a=pos.get(e.source_id), b=pos.get(e.target_id);
    if(e.forward){
      assert.strictEqual(e.x1,a.x+a.width,`${view}: edge leaves source boundary`);
      assert.strictEqual(e.x2,b.x,`${view}: edge enters target boundary`);
      assert(b.rank>a.rank,`${view}: forward edge moves to later layer`);
    }
  }

  const svg = DiagramLayout.renderSvg(view,nodes,edges);
  assert(svg.includes(`diagram-${view}`),`${view}: renderer identifies view`);
  assert(svg.includes('normalized events'),`${view}: edge labels visible`);
  assert(svg.includes('Production Database'),`${view}: node labels visible`);
  assert(!/NaN|undefined/.test(svg),`${view}: SVG contains no invalid coordinates`);
}

// Escaping is important because AI supplied labels can contain markup-like text.
const safe = DiagramLayout.renderSvg('process',[{id:1,label:'<script>alert(1)</script>',kind:'process'}],[]);
assert(!safe.includes('<script>'),'renderer must escape node labels');
assert(safe.includes('&lt;script&gt;'),'escaped label remains visible');

console.log('Diagram layout/readability tests: PASS');
