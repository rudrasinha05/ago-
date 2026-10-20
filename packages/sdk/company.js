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
