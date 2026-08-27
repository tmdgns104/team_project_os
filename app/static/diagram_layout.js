(function(root, factory){
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.DiagramLayout = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function(){
  'use strict';

  const NODE_W = 220;
  const NODE_H = 88;
  const GAP_X = 150;
  const GAP_Y = 34;
  const PAD_X = 72;
  const PAD_TOP = 94;
  const PAD_BOTTOM = 70;

  function esc(value){
    return String(value == null ? '' : value)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  function cleanNodes(nodes){
    return (nodes || []).map((n, i) => ({
      id: n.id,
      label: String(n.label || `Node ${i + 1}`),
      kind: String(n.kind || 'component'),
      detail: String(n.detail || ''),
      _index: i,
    }));
  }

  function cleanEdges(edges, ids){
    return (edges || [])
      .filter(e => ids.has(e.source_id) && ids.has(e.target_id) && e.source_id !== e.target_id)
      .map((e, i) => ({
        id: e.id == null ? `e${i}` : e.id,
        source_id: e.source_id,
        target_id: e.target_id,
        label: String(e.label || ''),
      }));
  }

  function longestPathRanks(nodes, edges){
    const ids = nodes.map(n => n.id);
    const indegree = new Map(ids.map(id => [id, 0]));
    const outgoing = new Map(ids.map(id => [id, []]));
    for (const e of edges){
      indegree.set(e.target_id, (indegree.get(e.target_id) || 0) + 1);
      outgoing.get(e.source_id).push(e.target_id);
    }
    const rank = new Map(ids.map(id => [id, 0]));
    const queue = nodes.filter(n => indegree.get(n.id) === 0).map(n => n.id);
    const visited = new Set();
    while(queue.length){
      const id = queue.shift(); visited.add(id);
      const base = rank.get(id) || 0;
      for (const to of outgoing.get(id) || []){
        rank.set(to, Math.max(rank.get(to) || 0, base + 1));
        indegree.set(to, indegree.get(to) - 1);
        if (indegree.get(to) === 0) queue.push(to);
      }
    }
    // Cycles are common in real architectures. Keep cyclic nodes readable by
    // assigning them near the rank implied by already-ranked neighbours.
    for (const n of nodes){
      if (visited.has(n.id)) continue;
      const incoming = edges.filter(e => e.target_id === n.id).map(e => rank.get(e.source_id) || 0);
      const outgoingRanks = edges.filter(e => e.source_id === n.id).map(e => rank.get(e.target_id) || 0);
      const guess = incoming.length ? Math.max(...incoming) + 1 : outgoingRanks.length ? Math.max(0, Math.min(...outgoingRanks) - 1) : 0;
      rank.set(n.id, guess);
    }
    return rank;
  }

  function semanticRank(view, node, graphRank){
    const k = node.kind.toLowerCase();
    if (view === 'architecture'){
      if (['source','device','event'].includes(k)) return Math.min(graphRank, 0);
      if (['service','process','component'].includes(k)) return Math.max(1, graphRank);
      if (k === 'database') return Math.max(2, graphRank);
      if (['ui','sink'].includes(k)) return Math.max(2, graphRank);
    }
    if (view === 'dataflow'){
      if (['source','device','event'].includes(k)) return Math.min(graphRank, 0);
      if (['service','process','component'].includes(k)) return Math.max(1, graphRank);
      if (k === 'database') return Math.max(2, graphRank);
      if (['ui','sink'].includes(k)) return Math.max(2, graphRank);
    }
    return graphRank;
  }

  function compressRanks(nodes, rankMap, view){
    const raw = nodes.map(n => semanticRank(view, n, rankMap.get(n.id) || 0));
    const uniq = [...new Set(raw)].sort((a,b)=>a-b);
    const remap = new Map(uniq.map((v,i)=>[v,i]));
    const out = new Map();
    nodes.forEach((n,i)=>out.set(n.id, remap.get(raw[i])));
    return out;
  }

  function orderLayers(nodes, edges, ranks){
    const maxRank = Math.max(0, ...nodes.map(n => ranks.get(n.id) || 0));
    const layers = Array.from({length:maxRank+1}, () => []);
    for (const n of nodes) layers[ranks.get(n.id) || 0].push(n);
    layers.forEach(layer => layer.sort((a,b)=>a._index-b._index));

    // Two barycentric sweeps reduce edge crossings while keeping ordering stable.
    for (let sweep=0; sweep<2; sweep++){
      for (let r=1; r<layers.length; r++){
        const prevIndex = new Map(layers[r-1].map((n,i)=>[n.id,i]));
        layers[r].sort((a,b)=>{
          const score = node => {
            const incoming = edges.filter(e => e.target_id===node.id && prevIndex.has(e.source_id));
            if(!incoming.length) return node._index + 1000;
            return incoming.reduce((s,e)=>s+prevIndex.get(e.source_id),0)/incoming.length;
          };
          return score(a)-score(b) || a._index-b._index;
        });
      }
      for (let r=layers.length-2; r>=0; r--){
        const nextIndex = new Map(layers[r+1].map((n,i)=>[n.id,i]));
        layers[r].sort((a,b)=>{
          const score = node => {
            const outgoing = edges.filter(e => e.source_id===node.id && nextIndex.has(e.target_id));
            if(!outgoing.length) return node._index + 1000;
            return outgoing.reduce((s,e)=>s+nextIndex.get(e.target_id),0)/outgoing.length;
          };
          return score(a)-score(b) || a._index-b._index;
        });
      }
    }
    return layers;
  }

  function layerTitle(view, layer, index){
    if(view === 'process') return `STEP ${index + 1}`;
    const kinds = new Set(layer.map(n => n.kind.toLowerCase()));
    if(view === 'architecture'){
      if([...kinds].some(k=>['source','device','event'].includes(k))) return 'EDGE / INPUT';
      if([...kinds].some(k=>['service','process','component'].includes(k))) return 'APPLICATION / SERVICE';
      if(kinds.has('database')) return 'DATA / STORAGE';
      if([...kinds].some(k=>['ui','sink'].includes(k))) return 'OUTPUT / UI';
      return `LAYER ${index + 1}`;
    }
    if(view === 'dataflow'){
      if([...kinds].some(k=>['source','device','event'].includes(k))) return 'SOURCE';
      if([...kinds].some(k=>['service','process','component'].includes(k))) return 'PROCESSING';
      if(kinds.has('database')) return 'STORE';
      if([...kinds].some(k=>['ui','sink'].includes(k))) return 'CONSUMER';
      return `STAGE ${index + 1}`;
    }
    return `LAYER ${index + 1}`;
  }

  function layout(view, inputNodes, inputEdges){
    const nodes = cleanNodes(inputNodes);
    const ids = new Set(nodes.map(n=>n.id));
    const edges = cleanEdges(inputEdges, ids);
    if(!nodes.length) return {view,nodes:[],edges:[],layers:[],width:960,height:420};

    const graphRank = longestPathRanks(nodes, edges);
    const ranks = compressRanks(nodes, graphRank, view);
    const layers = orderLayers(nodes, edges, ranks);
    const maxRows = Math.max(1, ...layers.map(l=>l.length));
    const width = Math.max(960, PAD_X*2 + layers.length*NODE_W + Math.max(0,layers.length-1)*GAP_X);
    const height = Math.max(440, PAD_TOP + maxRows*NODE_H + Math.max(0,maxRows-1)*GAP_Y + PAD_BOTTOM);

    const positioned = [];
    layers.forEach((layer, rank) => {
      const columnHeight = layer.length*NODE_H + Math.max(0,layer.length-1)*GAP_Y;
      const y0 = PAD_TOP + Math.max(0,(height-PAD_TOP-PAD_BOTTOM-columnHeight)/2);
      layer.forEach((n,row)=>positioned.push({
        ...n, rank, row,
        x: PAD_X + rank*(NODE_W+GAP_X),
        y: y0 + row*(NODE_H+GAP_Y),
        width:NODE_W, height:NODE_H,
      }));
    });
    const pos = new Map(positioned.map(n=>[n.id,n]));
    const routed = edges.map((e,i)=>{
      const a=pos.get(e.source_id), b=pos.get(e.target_id);
      const forward = b.rank > a.rank;
      let x1,y1,x2,y2,path,labelX,labelY;
      if(forward){
        x1=a.x+a.width; y1=a.y+a.height/2; x2=b.x; y2=b.y+b.height/2;
        const dx=Math.max(48,(x2-x1)*0.48);
        path=`M ${x1} ${y1} C ${x1+dx} ${y1}, ${x2-dx} ${y2}, ${x2} ${y2}`;
        labelX=(x1+x2)/2; labelY=(y1+y2)/2-10;
      }else{
        // Same-rank/back edges are routed below nodes instead of cutting through them.
        x1=a.x+a.width/2; y1=a.y+a.height; x2=b.x+b.width/2; y2=b.y+b.height;
        const lane=height-PAD_BOTTOM/2 + (i%3)*10;
        path=`M ${x1} ${y1} C ${x1} ${lane}, ${x2} ${lane}, ${x2} ${y2}`;
        labelX=(x1+x2)/2; labelY=lane-9;
      }
      return {...e,x1,y1,x2,y2,path,labelX,labelY,forward};
    });
    return {
      view, nodes:positioned, edges:routed, width, height,
      layers:layers.map((layer,i)=>({rank:i,title:layerTitle(view,layer,i),x:PAD_X+i*(NODE_W+GAP_X),count:layer.length}))
    };
  }

  function splitLabel(label, maxChars){
    const text=String(label||'').trim();
    if(text.length<=maxChars) return [text];
    const words=text.split(/\s+/); const lines=[''];
    for(const word of words){
      const cur=lines[lines.length-1];
      if((cur+' '+word).trim().length<=maxChars) lines[lines.length-1]=(cur+' '+word).trim();
      else if(lines.length<2) lines.push(word); else lines[1]=(lines[1]+' '+word).trim();
    }
    if(lines.length===1){lines[0]=text.slice(0,maxChars);lines.push(text.slice(maxChars,maxChars*2));}
    if(lines[1] && lines[1].length>maxChars) lines[1]=lines[1].slice(0,maxChars-1)+'…';
    return lines.slice(0,2);
  }

  function kindLabel(kind){
    return ({database:'Database',device:'Device',service:'Service',process:'Process',decision:'Decision',ui:'UI',source:'Source',sink:'Sink',event:'Event',component:'Component'})[kind] || kind;
  }

  function nodeShape(n){
    const cls=`diagram-svg-node kind-${esc(n.kind)}`;
    const label=splitLabel(n.label,20);
    const labelY=n.y+31;
    const detail=n.detail ? (n.detail.length>34?n.detail.slice(0,33)+'…':n.detail) : kindLabel(n.kind);
    if(n.kind==='decision'){
      const cx=n.x+n.width/2, cy=n.y+n.height/2;
      const pts=`${cx},${n.y} ${n.x+n.width},${cy} ${cx},${n.y+n.height} ${n.x},${cy}`;
      return `<g class="${cls}"><polygon points="${pts}"/><text class="node-title" x="${cx}" y="${cy-5}" text-anchor="middle">${esc(label[0])}</text>${label[1]?`<text class="node-title secondary" x="${cx}" y="${cy+13}" text-anchor="middle">${esc(label[1])}</text>`:''}</g>`;
    }
    return `<g class="${cls}"><rect x="${n.x}" y="${n.y}" width="${n.width}" height="${n.height}" rx="15"/><text class="node-kind" x="${n.x+16}" y="${n.y+19}">${esc(kindLabel(n.kind).toUpperCase())}</text><text class="node-title" x="${n.x+16}" y="${labelY}">${esc(label[0])}</text>${label[1]?`<text class="node-title secondary" x="${n.x+16}" y="${labelY+18}">${esc(label[1])}</text>`:''}<text class="node-detail" x="${n.x+16}" y="${n.y+n.height-13}">${esc(detail)}</text></g>`;
  }

  function renderSvg(view, nodes, edges){
    const l=layout(view,nodes,edges);
    const marker=`arrow-${view}`;
    const bands=l.layers.map((layer,i)=>`<g class="diagram-layer"><rect x="${Math.max(18,layer.x-28)}" y="40" width="${NODE_W+56}" height="${l.height-82}" rx="20"/><text x="${layer.x}" y="68">${esc(layer.title)}</text></g>`).join('');
    const edgeSvg=l.edges.map((e,i)=>{
      const label=e.label.trim();
      const w=Math.min(220,Math.max(58,label.length*7.5+22));
      return `<g class="diagram-svg-edge"><path d="${e.path}" marker-end="url(#${marker})"/>${label?`<rect class="edge-label-bg" x="${e.labelX-w/2}" y="${e.labelY-13}" width="${w}" height="24" rx="12"/><text class="edge-label-text" x="${e.labelX}" y="${e.labelY+3}" text-anchor="middle">${esc(label.length>28?label.slice(0,27)+'…':label)}</text>`:''}</g>`;
    }).join('');
    const nodeSvg=l.nodes.map(nodeShape).join('');
    return `<svg class="diagram-svg diagram-${esc(view)}" viewBox="0 0 ${l.width} ${l.height}" role="img" aria-label="${esc(view)} diagram"><defs><marker id="${marker}" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,8 L9,4 z"/></marker></defs>${bands}${edgeSvg}${nodeSvg}</svg>`;
  }

  return {layout,renderSvg,constants:{NODE_W,NODE_H,GAP_X,GAP_Y}};
});
