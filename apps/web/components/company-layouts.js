// Alternative presentations of the SAME validated company graph produced by
// circularCompanyLayout (@ago/sdk/company). These functions only move nodes
// and shape links; they never add, remove or re-parent an edge, so reporting
// lines, grouping links and task routes stay exactly the recorded ones.

const NODE_W=200,NODE_H=150;   // employee/department card footprint
const COL=250,ROW=300;         // tree spacing
const FOUNDER_DROP=170;        // founder card is taller than other cards

function children(base){
  const map=new Map();
  for(const edge of base.edges){
    if(!map.has(edge.from))map.set(edge.from,[]);
    map.get(edge.from).push(edge.to);
  }
  const byKey=new Map(base.nodes.map(n=>[n.key,n]));
  const order=(a,b)=>{
    const x=byKey.get(a),y=byKey.get(b);
    // Departments first, then people by name, stable by key.
    return (x?.type==='department'?0:1)-(y?.type==='department'?0:1)
      ||String(x?.name||'').localeCompare(String(y?.name||''))||String(a).localeCompare(String(b));
  };
  for(const list of map.values())list.sort(order);
  return map;
}

/** Orthogonal "org chart" link from the bottom of a parent to the top of a child. */
function elbow(a,b,fromFounder){
  const startY=a.y+(fromFounder?FOUNDER_DROP:NODE_H/2)+8,endY=b.y-NODE_H/2-10;
  const midY=startY+Math.max(24,(endY-startY)*.5);
  return {path:`M${a.x} ${startY} V${midY} H${b.x} V${endY}`,mid:{x:b.x,y:(midY+endY)/2}};
}

function finish(base,positions,founder,width,height,shape,layoutName){
  const size=Math.ceil(Math.max(width,height)+600),center=size/2;
  const dx=center-width/2,dy=center-height/2;
  const place=p=>({x:p.x+dx,y:p.y+dy});
  const nodes=base.nodes.map(n=>({...n,...place(positions.get(n.key)||{x:width/2,y:height/2}),radius:undefined}));
  const where=new Map([['founder',place(founder)],...nodes.map(n=>[n.key,n])]);
  const edges=base.edges.map(edge=>({...edge,...shape(where.get(edge.from),where.get(edge.to),edge)}));
  return {...base,size,center,founder:place(founder),nodes,edges,layout:layoutName};
}

/** Top-down org chart: Founder → departments → recorded reporting tree. */
export function treeCompanyLayout(base){
  const kids=children(base),depth=new Map([['founder',0]]),x=new Map();
  let cursor=0,maxDepth=0;
  const seen=new Set();
  const walk=(key,level)=>{
    if(seen.has(key))return;seen.add(key);
    depth.set(key,level);maxDepth=Math.max(maxDepth,level);
    const list=(kids.get(key)||[]).filter(k=>!seen.has(k));
    if(!list.length){x.set(key,cursor);cursor+=COL;return;}
    for(const child of list)walk(child,level+1);
    const xs=list.map(k=>x.get(k)).filter(Number.isFinite);
    x.set(key,(Math.min(...xs)+Math.max(...xs))/2);
  };
  walk('founder',0);
  // Any node not reachable from the Founder (should not happen) goes on the last row.
  for(const n of base.nodes)if(!seen.has(n.key)){x.set(n.key,cursor);cursor+=COL;depth.set(n.key,maxDepth+1);}
  const width=Math.max(COL,cursor-COL)+NODE_W,height=(maxDepth+1)*ROW+FOUNDER_DROP+NODE_H;
  const yOf=key=>key==='founder'?FOUNDER_DROP:FOUNDER_DROP*2+depth.get(key)*ROW;
  const positions=new Map(base.nodes.map(n=>[n.key,{x:x.get(n.key)+NODE_W/2,y:yOf(n.key)}]));
  const founder={x:x.get('founder')+NODE_W/2,y:yOf('founder')};
  return finish(base,positions,founder,width,height,(a,b,edge)=>elbow(a,b,edge.from==='founder'),'tree');
}

/** Department lanes: one column per department (by recorded membership),
 * staff ordered managers-first by reporting depth. Links are unchanged. */
export function departmentCompanyLayout(base){
  const LANE=300,STACK=250,TOP=FOUNDER_DROP+460; // room for the scaled Founder card
  const lanes=base.nodes.filter(n=>n.type==='department');
  const laneKeys=lanes.map(d=>d.key);
  const laneFor=n=>n.type==='department'?n.key
    :laneKeys.includes('department:'+n.department_id)?'department:'+n.department_id:'unassigned';
  const columns=[...laneKeys,'unassigned'].filter(key=>base.nodes.some(n=>laneFor(n)===key));
  const byName=(a,b)=>(a.depth||0)-(b.depth||0)||String(a.name||'').localeCompare(String(b.name||''))||String(a.key).localeCompare(String(b.key));
  const position=new Map();let tallest=1;
  columns.forEach((lane,col)=>{
    const head=base.nodes.filter(n=>n.type==='department'&&n.key===lane);
    const staff=base.nodes.filter(n=>n.type!=='department'&&laneFor(n)===lane).sort(byName);
    [...head,...staff].forEach((n,index)=>{
      const indent=n.type==='department'?0:Math.min(3,Math.max(0,(n.depth||1)-1))*16;
      position.set(n.key,{x:col*LANE+NODE_W/2+indent,y:TOP+index*STACK});
    });
    tallest=Math.max(tallest,head.length+staff.length);
  });
  const width=Math.max(1,columns.length)*LANE,height=TOP+tallest*STACK;
  const founder={x:width/2-LANE/2+NODE_W/2,y:FOUNDER_DROP};
  return finish(base,position,founder,width,height,(a,b,edge)=>{
    if(edge.from==='founder')return elbow(a,b,true);
    // Same lane: a bracket along the column's left edge; across lanes: a curve.
    if(Math.abs(a.x-b.x)<60){
      const x=Math.min(a.x,b.x)-NODE_W/2-18;
      return {path:`M${a.x-NODE_W/2} ${a.y} H${x} V${b.y} H${b.x-NODE_W/2-6}`,mid:{x,y:(a.y+b.y)/2}};
    }
    // Across lanes: a horizontal S-curve between the facing card edges.
    const right=b.x>a.x,sx=a.x+(right?1:-1)*NODE_W/2,ex=b.x+(right?-1:1)*(NODE_W/2+8),bend=(ex-sx)/2;
    return {path:`M${sx} ${a.y} C${sx+bend} ${a.y} ${ex-bend} ${b.y} ${ex} ${b.y}`,mid:{x:(sx+ex)/2,y:(a.y+b.y)/2}};
  },'departments');
}

export const MAP_VIEWS=Object.freeze([
  ['circular','Circular','Founder at the centre; each reporting level on its own ring'],
  ['tree','Tree','Top-down organisation chart'],
  ['departments','Departments','One column per department'],
]);
