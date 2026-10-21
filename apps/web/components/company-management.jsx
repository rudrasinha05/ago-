"use client";
import {useEffect,useState} from 'react';

export function ManagementWorkload({api,me,refreshSignal=0}) {
 const [report,setReport]=useState(null),[expanded,setExpanded]=useState(false);
 useEffect(()=>{
  if(!me.permissions?.includes('task:read')||!me.permissions?.includes('organization:read'))return;
  let active=true;
  async function poll(){
   try{const data=await api.request('/v1/organization/company/management/workload');
    if(active)setReport(data);
   }catch{if(active)setReport(null);}
  }
  poll();const interval=setInterval(poll,13000);
  return()=>{active=false;clearInterval(interval);};
 },[api,me.permissions,refreshSignal]);
 if(!me.permissions?.includes('task:read'))return null;
 return <section id="ago-workforce" className="management-workload" aria-label="Management and employee work accountability">
  <h3>Management ownership and workforce utilization</h3>
  <p>Leadership is accountable for useful delivery and commercial outcomes. An idle record is a workload alert, not permission to create pointless tasks or bypass reviews.</p>
  {report===null?<p>Verified workforce status unavailable.</p>:<>
   <div className="management-metrics"><span><strong>{report.employees.length}</strong>Employees tracked</span>
    <span><strong>{report.idle_employees}</strong>No governed work queued/running</span>
    <span><strong>{report.pending_employee_work}</strong>Governed tasks awaiting action</span>
    <span><strong>{report.unmanaged_task_alerts??0}</strong>Tasks needing management escalation</span>
    <span><strong>{report.qa_passed_count??'—'}</strong>Independently passed QA</span>
    <span><strong>{report.qa_failed_count??'—'}</strong>Failed QA assessments</span>
    <span><strong>{report.awaiting_qa_count??'—'}</strong>Completed tasks awaiting QA</span>
    <span><strong>{report.recommended_placements??'—'}</strong>Suggested existing candidates</span></div>
   {report.employees.length>0&&report.idle_employees===report.employees.length&&
    <div className="management-backlog" role="status">
     <h4>Company delivery idle — management attention required</h4>
     <p>No tracked employee has a running or queued governed task. This is a recorded
      workload gap, not proof that external commercial work is absent. Review
      <a href="#ago-opportunities"> Company Opportunity Radar</a>, then
      <a href="#company-approval-inbox"> founder approvals</a>. Do not manufacture
      tasks or start unapproved customer outreach.</p>
    </div>}
   {(report.unassigned_project_stages||[]).length>0&&<div className="management-backlog">
      <h4>Management work queue — unstaffed project stages</h4>
      <p>These are documented delivery responsibilities, not dispatched or approved execution tasks. Responsible leaders must arrange capable staff.</p>
      <ol>{report.unassigned_project_stages.slice(0,12).map((s,i)=><li key={s.project_title+'-'+s.stage+'-'+i}>
       <strong>{s.project_title} — {s.stage}</strong> · {s.responsible_manager_name} accountable
       <small>{s.deliverable}</small>
       <small>{s.candidate_name?'Workload-aware suggestion: '+s.candidate_name+' ('+s.candidate_workload+' active/queued tasks)':'No qualified matching active staff; review HR request'}{s.founder_local_qa_candidate?' · Founder-only local QA candidate; requires separate AI delivery manager and actual reviewed evidence.':''}. No autonomous assignment has occurred.</small>
       <a href="#ago-project-portfolio">Inspect project record ↗</a>
      </li>)}</ol>
    </div>}
   <button type="button" onClick={()=>setExpanded(x=>!x)}>{expanded?'Hide':'Inspect'} employee workload</button>
   {expanded&&<div className="management-people">{report.employees.map(e=><article key={e.id}>
    <b>{e.name}</b><small>{e.role_title||e.kind} · {e.running} running · {e.queued} queued · {e.failed} failed · {e.projects_accountable} managed projects</small>
    <small>Evidence-backed QA: {e.qa_passed??0} passed · {e.qa_failed??0} failed · {e.unreviewed??0} waiting for independent review</small>
    <small>{e.running||e.queued?'Governed work recorded':'Idle in recorded governed queue; management needs to assess useful next assignment'}</small>
    {(e.leadership_gaps??0)>0&&<small>Management escalation required on {e.leadership_gaps} standalone task(s)</small>}
   </article>)}</div>}
  </>}
 </section>;
}
