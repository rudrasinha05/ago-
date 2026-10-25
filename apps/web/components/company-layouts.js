// Presentations of the validated company graph produced by
// circularCompanyLayout (@ago/sdk/company). Reporting lines (manager_id) are
// never added, removed or re-parented here, so task routes stay exactly the
// recorded ones. Department MEMBERSHIP (each employee's recorded
// department_id) is drawn as its own link kind: it shows where a person
// belongs, never who they report to and never a task route.

const NODE_W=200,NODE_H=150;   // employee/department card footprint
const COL=250,ROW=300;         // tree spacing
const FOUNDER_DROP=170;        // founder card is taller than other cards
const TAU=Math.PI*2;

const PALETTE=['#4fb3ff','#b48cff','#3fd6a3','#ffb547','#ff7aa8','#7fd6ff','#e3e36b','#ff8f5c','#8fa8ff','#5fe0d0'];
/** Stable colour per department (by name order, so it does not change on reload). */
export function departmentColors(departments){
  const sorted=[...departments].sort((a,b)=>String(a.name).localeCompare(String(b.name))||String(a.id).localeCompare(String(b.id)));
  return new Map(sorted.map((d,i)=>[d.id,PALETTE[i%PALETTE.length]]));
}

/** Add one membership link department → employee for every recorded member
 * that is not already linked from its own department by a grouping edge. */
export function withMembership(base){
  const departments=new Set(base.nodes.filter(n=>n.type==='department').map(n=>n.key));
  const existing=new Set(base.edges.map(e=>e.from+'>'+e.to));
  const membership=base.nodes
    .filter(n=>n.type==='employee'&&departments.has('department:'+n.department_id))
    .filter(n=>!existing.has('department:'+n.department_id+'>'+n.key))
    .map(n=>({from:'department:'+n.department_id,to:n.key,kind:'membership'}));
  return {...base,edges:[...base.edges,...membership]};
}

function children(edges,nodes){
  const map=new Map();
  for(const edge of edges){
    if(!map.has(edge.from))map.set(edge.from,[]);
    map.get(edge.from).push(edge.to);
  }
  const byKey=new Map(nodes.map(n=>[n.key,n]));
  const order=(a,b)=>String(byKey.get(a)?.name||'').localeCompare(String(byKey.get(b)?.name||''))||String(a).localeCompare(String(b));
  for(const list of map.values())list.sort(order);
  return map;
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

/** Circular, by department: each department owns a sector of the circle.
 * Department hubs sit on the inner ring; their members fan out inside the
 * same sector, one ring per reporting level, linked to their department. */
export function circularDepartmentLayout(base){
  const departments=base.nodes.filter(n=>n.type==='department')
    .sort((a,b)=>String(a.name).localeCompare(String(b.name))||String(a.key).localeCompare(String(b.key)));
  const people=base.nodes.filter(n=>n.type==='employee');
  const sectorOf=n=>departments.some(d=>d.key==='department:'+n.department_id)?'department:'+n.department_id:'unassigned';
  const sectors=[...departments.map(d=>d.key)];
  if(people.some(n=>sectorOf(n)==='unassigned'))sectors.push('unassigned');
  const members=new Map(sectors.map(k=>[k,people.filter(n=>sectorOf(n)===k)]));
  const weights=sectors.map(k=>Math.max(1,members.get(k).length)+.6);
  const total=weights.reduce((a,b)=>a+b,0)||1;
  const arcs=new Map();let cursor=-Math.PI/2;
  sectors.forEach((k,i)=>{const arc=TAU*weights[i]/total;arcs.set(k,{start:cursor,arc});cursor+=arc;});
  const HUB=520,STEP=340,GAP=245;
  // Ring radius per reporting level, wide enough for the busiest sector.
  const levels=[...new Set(people.map(n=>Math.max(1,n.depth||1)))].sort((a,b)=>a-b);
  const radius=new Map();let last=HUB;
  for(const level of levels){
    let needed=0;
    for(const k of sectors){
      const count=members.get(k).filter(n=>Math.max(1,n.depth||1)===level).length;
      const usable=Math.max(.15,arcs.get(k).arc-.12);
      if(count)needed=Math.max(needed,count*GAP/usable);
    }
    last=Math.ceil(Math.max(HUB+STEP*level,last+STEP,needed));
    radius.set(level,last);
  }
  const angle=new Map(),position=new Map();
  const reportsTo=new Map(base.edges.filter(e=>e.kind==='reporting').map(e=>[e.to,e.from]));
  departments.forEach(d=>{
    const {start,arc}=arcs.get(d.key),a=start+arc/2;angle.set(d.key,a);
    position.set(d.key,{x:Math.cos(a)*HUB,y:Math.sin(a)*HUB,radius:HUB});
  });
  for(const level of levels)for(const k of sectors){
    const ring=members.get(k).filter(n=>Math.max(1,n.depth||1)===level)
      // Keep reports near their manager to shorten reporting lines.
      .sort((a,b)=>(angle.get(reportsTo.get(a.key))??0)-(angle.get(reportsTo.get(b.key))??0)
        ||String(a.name).localeCompare(String(b.name)));
    const {start,arc}=arcs.get(k),usable=Math.max(.15,arc-.12),r=radius.get(level);
    ring.forEach((n,i)=>{
      const a=start+(arc-usable)/2+usable*(i+.5)/ring.length;angle.set(n.key,a);
      position.set(n.key,{x:Math.cos(a)*r,y:Math.sin(a)*r,radius:r});
    });
  }
  const max=Math.max(HUB,...radius.values());
  const center=Math.ceil(max+420),size=center*2;
  const nodes=base.nodes.map(n=>{
    const p=position.get(n.key)||{x:0,y:0,radius:HUB};
    return {...n,x:center+p.x,y:center+p.y,radius:p.radius,angle:angle.get(n.key)};
  });
  // Coloured wedges make each department's territory visible behind its members.
  const wedges=sectors.filter(k=>k!=='unassigned').map(k=>{
    const {start,arc}=arcs.get(k),inner=HUB-170,outer=max+190,pad=Math.min(.03,arc/8);
    const a0=start+pad,a1=start+arc-pad,large=a1-a0>Math.PI?1:0;
    const pt=(r,a)=>`${(center+Math.cos(a)*r).toFixed(1)} ${(center+Math.sin(a)*r).toFixed(1)}`;
    const label=start+arc/2,lr=outer-60;
    return {key:k,departmentId:k.slice(11),
      path:`M${pt(inner,a0)} L${pt(outer,a0)} A${outer} ${outer} 0 ${large} 1 ${pt(outer,a1)} L${pt(inner,a1)} A${inner} ${inner} 0 ${large} 0 ${pt(inner,a0)}Z`,
      label:{x:center+Math.cos(label)*lr,y:center+Math.sin(label)*lr}};
  });
  return {...base,size,center,founder:{x:center,y:center},nodes,wedges,layout:'circular'};
}

/** Orthogonal "org chart" link from the bottom of a parent to the top of a child. */
function elbow(a,b,fromFounder){
  const startY=a.y+(fromFounder?FOUNDER_DROP:NODE_H/2)+8,endY=b.y-NODE_H/2-10;
  const midY=startY+Math.max(24,(endY-startY)*.5);
  return {path:`M${a.x} ${startY} V${midY} H${b.x} V${endY}`,mid:{x:b.x,y:(midY+endY)/2}};
}

/** Top-down reporting chart (manager → report). Department is shown on each
 * card; people with no recorded manager hang from the Founder on a dashed
 * "no manager recorded" connector, which is not an authority line. */
export function treeCompanyLayout(base){
  const people=base.nodes.filter(n=>n.type==='employee');
  const reporting=base.edges.filter(e=>e.kind==='reporting');
  const hasParent=new Set(reporting.map(e=>e.to));
  const edges=[...reporting,...people.filter(n=>!hasParent.has(n.key)).map(n=>({from:'founder',to:n.key,kind:'unassigned'}))];
  const reduced={...base,nodes:people,edges};
  const kids=children(edges,people),depth=new Map([['founder',0]]),x=new Map();
  let cursor=0,maxDepth=0;const seen=new Set();
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
  for(const n of people)if(!seen.has(n.key)){x.set(n.key,cursor);cursor+=COL;depth.set(n.key,maxDepth+1);}
  const width=Math.max(COL,cursor-COL)+NODE_W,height=(maxDepth+1)*ROW+FOUNDER_DROP+NODE_H;
  const yOf=key=>key==='founder'?FOUNDER_DROP:FOUNDER_DROP*2+depth.get(key)*ROW;
  const positions=new Map(people.map(n=>[n.key,{x:x.get(n.key)+NODE_W/2,y:yOf(n.key)}]));
  const founder={x:(x.get('founder')??0)+NODE_W/2,y:yOf('founder')};
  return finish(reduced,positions,founder,width,height,(a,b,edge)=>elbow(a,b,edge.from==='founder'),'tree');
}

/** Department lanes: one column per department. A spine on the left joins
 * the department to every member; reporting lines use the right side
 * (same lane) or an S-curve (across lanes). */
export function departmentCompanyLayout(base){
  const LANE=320,STACK=250,TOP=FOUNDER_DROP+460; // room for the scaled Founder card
  const lanes=base.nodes.filter(n=>n.type==='department')
    .sort((a,b)=>String(a.name).localeCompare(String(b.name))||String(a.key).localeCompare(String(b.key)));
  const laneKeys=lanes.map(d=>d.key);
  const laneFor=n=>n.type==='department'?n.key
    :laneKeys.includes('department:'+n.department_id)?'department:'+n.department_id:'unassigned';
  const columns=[...laneKeys,'unassigned'].filter(key=>base.nodes.some(n=>laneFor(n)===key));
  const byDepth=(a,b)=>(a.depth||0)-(b.depth||0)||String(a.name||'').localeCompare(String(b.name||''))||String(a.key).localeCompare(String(b.key));
  const position=new Map();let tallest=1;
  columns.forEach((lane,col)=>{
    const head=base.nodes.filter(n=>n.type==='department'&&n.key===lane);
    const staff=base.nodes.filter(n=>n.type!=='department'&&laneFor(n)===lane).sort(byDepth);
    [...head,...staff].forEach((n,index)=>{
      const indent=n.type==='department'?0:28+Math.min(3,Math.max(0,(n.depth||1)-1))*14;
      position.set(n.key,{x:col*LANE+40+NODE_W/2+indent,y:TOP+index*STACK});
    });
    tallest=Math.max(tallest,head.length+staff.length);
  });
  const width=Math.max(1,columns.length)*LANE,height=TOP+tallest*STACK;
  const founder={x:width/2,y:FOUNDER_DROP};
  return finish(base,position,founder,width,height,(a,b,edge)=>{
    if(edge.from==='founder')return elbow(a,b,true);
    if(edge.from.startsWith('department:')){
      // Membership spine down the lane's left edge.
      const spine=a.x-NODE_W/2-16;
      return {path:`M${a.x-NODE_W/2} ${a.y} H${spine} V${b.y} H${b.x-NODE_W/2-6}`,mid:{x:spine,y:(a.y+b.y)/2}};
    }
    if(Math.abs(a.x-b.x)<80){
      const x=Math.max(a.x,b.x)+NODE_W/2+18;
      return {path:`M${a.x+NODE_W/2} ${a.y} H${x} V${b.y} H${b.x+NODE_W/2+6}`,mid:{x,y:(a.y+b.y)/2}};
    }
    const right=b.x>a.x,sx=a.x+(right?1:-1)*NODE_W/2,ex=b.x+(right?-1:1)*(NODE_W/2+8),bend=(ex-sx)/2;
    return {path:`M${sx} ${a.y} C${sx+bend} ${a.y} ${ex-bend} ${b.y} ${ex} ${b.y}`,mid:{x:(sx+ex)/2,y:(a.y+b.y)/2}};
  },'departments');
}

export const MAP_VIEWS=Object.freeze([
  ['circular','Circular','Each department owns a sector; members fan out from their department'],
  ['tree','Tree','Reporting chart: manager above report; department shown on every card'],
  ['departments','Departments','One column per department, every member joined to it'],
]);
