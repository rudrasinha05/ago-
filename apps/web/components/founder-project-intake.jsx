"use client";
import {useCallback,useEffect,useRef,useState} from 'react';

export function FounderProjectIntake({api,me,onChanged}) {
 const [brief,setBrief]=useState('');
 const [projects,setProjects]=useState(null);
 const [created,setCreated]=useState(null);
 const [busy,setBusy]=useState(false),[reviewBusy,setReviewBusy]=useState(false),[error,setError]=useState('');
 const retry=useRef(null);
 const isFounder=me.roles?.includes('founder')&&me.permissions?.includes('brain:manage');
 const refresh=useCallback(async()=>{
   try {setProjects(await api.request('/v1/organization/company/projects'));} catch {setProjects(null);}
 },[api]);
 useEffect(()=>{if(isFounder)refresh();},[refresh,isFounder]);
 if(!isFounder)return null;
 async function start(e){e.preventDefault();if(busy||brief.trim().length<20)return;
  setBusy(true);setError('');
  if(!retry.current||retry.current.brief!==brief.trim())retry.current={brief:brief.trim(),key:crypto.randomUUID()};
  try {
    const response=await api.request('/v1/organization/company/projects/start',
      {method:'POST',body:{brief:retry.current.brief,operation_key:retry.current.key}});
    setCreated(response);setBrief('');retry.current=null;await refresh();onChanged?.();
  } catch(err){setError(err.message);}finally{setBusy(false);}
 }
 async function submitForReview(){
  if(!created||reviewBusy||created.plan_status!=='draft')return;
  setReviewBusy(true);setError('');
  try{const response=await api.request('/v1/brain/plans/'+encodeURIComponent(created.plan_id)+'/submit',{method:'POST'});
    setCreated(old=>({...old,plan_status:response.status,approval_id:response.approval_id}));
    await refresh();onChanged?.();
  }catch(e){setError(e.message);}finally{setReviewBusy(false);}
 }
  return <section className="founder-project-intake" aria-label="Start founder project">
  <div><h3>Start a governed project</h3>
    <p>Founder → Company Brain → accountable executive (CEO/COO/CTO/manager if actually configured; otherwise founder escalation) → suggested team. Higher management owns delivery, workers own execution. Approve/Deny is reserved for the founder; independent QA remains a separate check.</p></div>
  <form onSubmit={start}>
    <label>Founder project brief<textarea value={brief} onChange={e=>setBrief(e.target.value)}
      minLength={20} maxLength={12000} required
      placeholder="What should the company build? Who uses it, what must it deliver, and what would success look like?"/></label>
    <button disabled={busy||brief.trim().length<20}>{busy?'Preparing draft…':'Prepare project from brief'}</button>
  </form>
  {error&&<p role="alert">{error}</p>}
  {created&&<div aria-live="polite"><strong>{created.title}</strong>
    <p><b>Accountable delivery owner:</b> {created.accountable_manager_name} ({created.accountable_manager_role||'Founder authority'}) · {created.assignment_source==='founder_escalation'?'Management staffing escalation':'Recorded executive management responsibility'}</p>
    <p><b>Commercial goal:</b> {created.commercial_objective} · {created.commercial_stage} · No verified revenue evidence yet</p>
    <p>Draft saved · Founder approval needed · No unapproved code or external GitHub action started.</p>
    <ol className="intake-stage-list">{created.stages.map(s=><li key={s.stage}>
      <strong>{s.position}. {s.stage}</strong><small>{s.deliverable}</small>
      <span>{s.suggested_assignee_name||'Staffing required'}</span>
      <small>{s.plan_step_id?'Allowlisted internal review step drafted':'Proposal only; tooling and approval required'}</small>
    </li>)}</ol>
    <p>Plan ID: <code>{created.plan_id}</code> · Status: {created.plan_status} · Founder approval is required before materialization. <a href="#company-approval-inbox">View approval inbox ↑</a></p>
    {created.plan_status==='draft'&&created.stages.some(s=>s.plan_step_id)&&
      <button type="button" disabled={reviewBusy} onClick={submitForReview}>{reviewBusy?'Submitting…':'Submit plan for founder approval'}</button>}
    {created.plan_status==='draft'&&!created.stages.some(s=>s.plan_step_id)&&
      <p>Assign a qualified discovery AI employee before submitting this draft for approval.</p>}
  </div>}
  <div><h3>Recent founder projects</h3>
   {projects===null?<small>Project history unavailable</small>:!projects.length?<small>No founder projects yet</small>:
   <ol>{projects.slice(0,5).map(p=><li key={p.id}>
     <strong>{p.title}</strong> · <small>{p.plan_status} · {p.staffing_gaps} execution staffing gaps</small>
     <p><b>Delivery responsible:</b> {p.accountable_manager_name||'Unavailable'} ({p.accountable_manager_role||'Founder'}) · {p.assignment_source==='founder_escalation'?'Executive leader needed':'Executive leadership recorded'}</p>
     <p><b>Commercial objective:</b> {p.commercial_objective} · {p.commercial_stage} · Verified revenue: {p.verified_revenue_inr===null?'No evidence recorded':'₹'+p.verified_revenue_inr}</p>
     <details className="founder-routing"><summary>Who received this project? View actual draft routing</summary>
      <p>Company Brain has recorded a named higher-management delivery owner. This is a durable accountability assignment, not autonomous delegation or a completed project. Employee suggestions do not become executable tasks without authorization.</p>
      <ol>{(p.stages||[]).map(s=><li key={s.stage}><strong>{s.stage}</strong> — {s.suggested_assignee_name||'No qualified employee'} {s.suggested_role?'('+s.suggested_role+')':''} · {s.plan_step_id?'Draft plan step (approval and materialization required)':'Suggestion only; no task assigned'}</li>)}</ol>
     </details>
   </li>)}</ol>}</div>
 </section>;
}
