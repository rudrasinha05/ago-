import {circularCompanyLayout} from './company-orbit.js';
export {companyLinkAnchors} from './company-orbit.js';
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
export function companyLayout(departments,employees,founderId){
  return circularCompanyLayout(departments,employees,founderId);
}

/** Highlight the recorded assignment chain up to the founder, never invented routes. */
export function activeRouteKeys(layout,employees,tasks){
  const routes=new Set(),waitingRoutes=new Set(),active=new Set(),running=new Set();
  if(!Array.isArray(tasks))return {routes,waitingRoutes,active,running};
  const people=new Map(employees.map(e=>[e.id,e]));
  // Department grouping never conveys actual authority or an execution route.
  const realEdges=new Map(layout.edges.filter(e=>e.kind==='reporting').map(e=>[e.to,e.from]));
  for(const task of tasks){
    if(!['proposed','ready','waiting_approval','running'].includes(task.status)||!people.has(task.assignee_id))continue;
    const isRunning=task.status==='running',target=isRunning?routes:waitingRoutes;
    let id=task.assignee_id;const seen=new Set();
    while(id&&people.has(id)&&!seen.has(id)){
      seen.add(id);active.add(id);if(isRunning)running.add(id);
      const parent=realEdges.get('employee:'+id);
      if(!parent)break; // No fabricated path to a department or Founder.
      target.add(parent+'>employee:'+id);
      id=parent.startsWith('employee:')?parent.slice(9):null;
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
