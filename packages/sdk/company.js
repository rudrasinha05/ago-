/** Actual reporting links; unknown task activity must never become idle. */
export function employeeStatus(employeeId, tasks) {
  if (!Array.isArray(tasks)) return {label:'Unknown',tone:'unknown',tasks:[]};
  const assigned=tasks.filter(t=>t.assignee_id===employeeId);
  const running=assigned.filter(t=>t.status==='running');
  const waiting=assigned.filter(t=>['waiting_approval','proposed','ready'].includes(t.status));
  return {label:running.length?'Busy':waiting.length?'Waiting':'Idle',tone:running.length?'busy':waiting.length?'waiting':'idle',tasks:assigned};
}
export function companyLayout(departments, employees, founderId) {
  const people=employees.filter(e=>e.id!==founderId), byId=new Map(people.map(e=>[e.id,e]));
  const children=new Map(people.map(e=>[e.id,[]])), roots=[];
  for(const e of people){
    // Invalid imported cycles are made visible as roots; never recurse indefinitely.
    const seen=new Set([e.id]);let cursor=e,cycle=false;
    while(byId.has(cursor.manager_id)){if(seen.has(cursor.manager_id)){cycle=true;break;}seen.add(cursor.manager_id);cursor=byId.get(cursor.manager_id);}
    if(!cycle&&byId.has(e.manager_id))children.get(e.manager_id).push(e);else roots.push(e);
  }
  const weight=e=>children.get(e.id).reduce((sum,c)=>sum+weight(c),0)||1;
  const leaves=departments.reduce((sum,d)=>sum+Math.max(1,roots.filter(e=>e.department_id===d.id).reduce((n,e)=>n+weight(e),0)),0)||1;
  // Each leaf gets a 280px arc. Depth rings separate managers and their reports.
  const inner=Math.max(700,leaves*280/(2*Math.PI)), step=420;
  const raw=[], edges=[];let cursor=-Math.PI/2;
  function place(e,start,span,depth){
    const angle=start+span/2, radius=inner+depth*step;
    raw.push({...e,key:'employee:'+e.id,type:'employee',angle,radius});
    edges.push({from:byId.has(e.manager_id)&&!roots.includes(e)?'employee:'+e.manager_id:'founder',to:'employee:'+e.id});
    let offset=start;for(const child of children.get(e.id)){const width=span*weight(child)/weight(e);place(child,offset,width,depth+1);offset+=width;}
  }
  for(const d of departments){
    const team=roots.filter(e=>e.department_id===d.id), size=team.reduce((sum,e)=>sum+weight(e),0);
    const span=(size||1)/leaves*2*Math.PI;
    {raw.push({...d,key:'department:'+d.id,type:'department',angle:cursor+span/2,radius:Math.max(360,inner-350)});edges.push({from:'founder',to:'department:'+d.id});}
    if(!size)cursor+=span;
    for(const e of team){const width=weight(e)/leaves*2*Math.PI;place(e,cursor,width,0);cursor+=width;}
  }
  const extent=Math.max(1000,...raw.map(n=>n.radius))+250, center=extent,size=extent*2;
  return {size,center,nodes:raw.map(n=>({...n,x:center+Math.cos(n.angle)*n.radius,y:center+Math.sin(n.angle)*n.radius})),edges};
}

/** Highlight the recorded assignment chain up to the founder, never invented routes. */
export function activeRouteKeys(layout, employees, tasks) {
  const routes=new Set(), active=new Set();
  if(!Array.isArray(tasks))return {routes,active};
  const people=new Map(employees.map(e=>[e.id,e]));
  const valid=new Set(layout.edges.map(e=>e.from+'>'+e.to));
  for(const task of tasks){
    if(!['proposed','ready','waiting_approval','running'].includes(task.status))continue;
    let id=task.assignee_id;const seen=new Set();
    while(id&&people.has(id)&&!seen.has(id)){
      seen.add(id);active.add(id);
      const employee=people.get(id);
      const from=employee.manager_id&&people.has(employee.manager_id)?'employee:'+employee.manager_id:'founder';
      const edge=from+'>employee:'+id;
      if(valid.has(edge))routes.add(edge);
      id=employee.manager_id&&people.has(employee.manager_id)?employee.manager_id:null;
    }
  }
  return {routes,active};
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
