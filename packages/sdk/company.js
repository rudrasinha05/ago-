/** Actual reporting links; unknown task activity must never become idle. */
export function employeeStatus(employeeId, tasks) {
  if (!Array.isArray(tasks)) return {label:'Unknown',tone:'unknown',tasks:[]};
  const assigned=tasks.filter(t=>t.assignee_id===employeeId);
  const running=assigned.some(t=>t.status==='running');
  const waiting=assigned.some(t=>['waiting_approval','proposed','ready'].includes(t.status));
  const blocked=assigned.some(t=>t.status==='blocked');
  const failed=assigned.some(t=>t.status==='failed');
  // Historical failures remain visible, but never trump genuinely running
  // or queued work. Missing/denied task evidence is Unknown, not Idle.
  const tone=running?'busy':waiting?'waiting':blocked?'blocked':failed?'failed':'idle';
  const labels={busy:'Busy',waiting:'Waiting',blocked:'Blocked',failed:'Failed work recorded',idle:'Idle'};
  return {label:labels[tone],tone,tasks:assigned};
}
export function companyLayout(departments, employees, founderId) {
  // A tidy, top-down REPORTING tree rather than an exploding radial spiderweb.
  // Department links are visual grouping only, NEVER a fabricated manager.
  const people=employees.filter(e=>e.id!==founderId);
  const byId=new Map(people.map(e=>[e.id,e]));
  const order=(a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id))||String(a.id).localeCompare(String(b.id));
  const directManager=new Map();
  for(const e of people) {
    if(!byId.has(e.manager_id)||e.id===e.manager_id)continue;
    const seen=new Set([e.id]);let parent=e.manager_id,cyclic=false;
    while(byId.has(parent)){
      if(seen.has(parent)){cyclic=true;break;}
      seen.add(parent);parent=byId.get(parent).manager_id;
    }
    if(!cyclic)directManager.set(e.id,e.manager_id);
  }
  const children=new Map(people.map(e=>[e.id,[]]));
  const roots=[];
  for(const e of people){
    const manager=directManager.get(e.id);
    if(manager)children.get(manager).push(e);else roots.push(e);
  }
  for(const group of children.values())group.sort(order);
  const existingDepartments=[...departments].sort(order);
  const groups=existingDepartments.map(d=>({
    department:d,roots:roots.filter(e=>e.department_id===d.id).sort(order)
  }));
  const ungrouped=roots.filter(e=>!existingDepartments.some(d=>d.id===e.department_id));
  if(ungrouped.length)groups.push({department:null,roots:ungrouped.sort(order)});
  // Preserve empty departments, expose missing managers as a separate root.
  let maxDepth=0;
  const weight=e=>Math.max(1,children.get(e.id).reduce((sum,c)=>sum+weight(c),0));
  const slot=280,groupGap=160;
  const widths=groups.map(g=>Math.max(slot,g.roots.reduce((sum,e)=>sum+weight(e)*slot,0)));
  const drawingWidth=widths.reduce((a,b)=>a+b,0)+Math.max(0,groups.length-1)*groupGap;
  const raw=[],edges=[];
  const positions=new Map();
  let x=0;
  const founderY=0,deptY=315,firstEmployeeY=665,levelGap=305;
  function place(e,left,width,depth,groupKey){
    const centerX=left+width/2,y=firstEmployeeY+depth*levelGap;
    maxDepth=Math.max(maxDepth,depth);
    const node={...e,key:'employee:'+e.id,type:'employee',x:centerX,y,depth:depth+1};
    raw.push(node);positions.set(node.key,node);
    const manager=directManager.get(e.id);
    const founderIsManager=e.manager_id===founderId;
    edges.push({
      from:manager?'employee:'+manager:founderIsManager?'founder':groupKey||'founder',
      to:node.key,kind:manager||founderIsManager?'reporting':'grouping'
    });
    let childLeft=left;
    for(const child of children.get(e.id)){
      const childWidth=weight(child)*slot;
      place(child,childLeft,childWidth,depth+1,groupKey);
      childLeft+=childWidth;
    }
  }
  for(let index=0;index<groups.length;index++){
    const group=groups[index],width=widths[index],mid=x+width/2;
    const groupKey=group.department?'department:'+group.department.id:null;
    if(group.department){
      const node={...group.department,key:groupKey,type:'department',x:mid,y:deptY};
      raw.push(node);positions.set(groupKey,node);
      edges.push({from:'founder',to:groupKey,kind:'grouping'});
    }
    const used=group.roots.reduce((sum,e)=>sum+weight(e)*slot,0);
    let rootLeft=x+(width-used)/2;
    for(const e of group.roots){
      const w=weight(e)*slot;
      place(e,rootLeft,w,0,groupKey);
      rootLeft+=w;
    }
    x+=width+groupGap;
  }
  // All coordinates are centered in a square scene; the viewport deliberately
  // starts centered on the Founder and lets users zoom or focus a department.
  const height=firstEmployeeY+(maxDepth+1)*levelGap+340;
  const size=Math.ceil(Math.max(1800,drawingWidth+360,height+300));
  const shiftX=(size-drawingWidth)/2,shiftY=(size-height)/2+140;
  const founder={x:size/2,y:founderY+shiftY};
  const nodes=raw.map(n=>({...n,x:n.x+shiftX,y:n.y+shiftY}));
  const coords=new Map(nodes.map(n=>[n.key,n]));
  // Department and real manager links remain distinct and inspectable.
  // Prevent visually misleading zero-length links and keep every node in bounds.
  const dangling=edges.filter(e=>e.from!=='founder'&&!coords.has(e.from));
  if(dangling.length)throw new Error('Reporting graph has an unresolved visual link');
  return {size,center:size/2,founder,nodes,edges,
    reportingEdges:edges.filter(e=>e.kind==='reporting').length,
    groupingEdges:edges.filter(e=>e.kind==='grouping').length};
}

/** Highlight the recorded assignment chain up to the founder, never invented routes. */
export function activeRouteKeys(layout, employees, tasks) {
  const routes=new Set(), waitingRoutes=new Set(), active=new Set(), running=new Set();
  if(!Array.isArray(tasks))return {routes,waitingRoutes,active,running};
  const people=new Map(employees.map(e=>[e.id,e]));
  const valid=new Set(layout.edges.map(e=>e.from+'>'+e.to));
  const incoming=new Map(layout.edges.map(e=>[e.to,e.from]));
  for(const task of tasks){
    if(!['proposed','ready','waiting_approval','running'].includes(task.status)||!people.has(task.assignee_id))continue;
    const isRunning=task.status==='running', target=isRunning?routes:waitingRoutes;
    let id=task.assignee_id,seen=new Set();
    while(id&&people.has(id)&&!seen.has(id)){
      seen.add(id);active.add(id);if(isRunning)running.add(id);
      const from=incoming.get('employee:'+id);
      if(!from)break;
      const edge=from+'>employee:'+id;
      if(valid.has(edge))target.add(edge);
      if(from.startsWith('department:')){
        const root='founder>'+from;if(valid.has(root))target.add(root);
      }
      id=from.startsWith('employee:')?from.slice(9):null;
    }
  }
  for(const key of routes)waitingRoutes.delete(key);
  return {routes,waitingRoutes,active,running};
}
export function employeeProjects(id,tasks){
  if(!Array.isArray(tasks))return [];
  return [...new Set(tasks.filter(t=>t.assignee_id===id&&t.project_name).map(t=>t.project_name))];
}
export function boardFunctionSeats(employees, approvedAppointments=[]){
  // Membership requires an authoritative, approved record; names/job titles confer no authority.
  const duties=[
    ['Strategy & Vision','Corporate direction, long-term goals, major project review'],
    ['Technology Oversight','Architecture, security, technical risk'],
    ['Finance & Budget','Spend oversight, approved allocation, economics'],
    ['Risk & Compliance','Policy, audit independence, incident escalation'],
    ['Quality & Release','Milestone evidence, publishability and release governance']
  ];
  const byId=new Map(employees.map(e=>[e.id,e]));
  return duties.map(([title,responsibility])=>{
    const appointment=approvedAppointments.find(a=>a.seat===title&&a.approved===true);
    return {title,responsibility,member:appointment?byId.get(appointment.member_id)||null:null};
  });
}
