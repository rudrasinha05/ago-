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
  const nodes=[], edges=[], count=Math.max(1,departments.length);
  departments.forEach((d,i)=>{
    const angle=i/count*Math.PI*2-Math.PI/2;
    const point=(r,a)=>({x:1300+Math.cos(a)*r,y:1300+Math.sin(a)*r});
    const dep={...d,key:'department:'+d.id,type:'department',...point(420,angle)};
    nodes.push(dep);edges.push({from:'founder',to:dep.key});
    const members=people.filter(e=>e.department_id===d.id);
    members.forEach((e,j)=>{
      let depth=0,cursor=e;const visited=new Set([e.id]);
      while(cursor.manager_id && byId.has(cursor.manager_id) && !visited.has(cursor.manager_id)) {
        visited.add(cursor.manager_id);depth++;cursor=byId.get(cursor.manager_id);
      }
      const sector=Math.min(1.4,Math.PI*2/count*.8);
      const a=angle+(j-(members.length-1)/2)*sector/Math.max(1,members.length);
      const radius=700+depth*190+(members.length>8?j%2*100:0);
      nodes.push({...e,key:'employee:'+e.id,type:'employee',...point(radius,a)});
      edges.push({from:byId.has(e.manager_id)?'employee:'+e.manager_id:'founder',to:'employee:'+e.id});
    });
  });
  return {nodes,edges};
}
