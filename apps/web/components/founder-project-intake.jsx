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
    <p>Founder → Company Brain (draft goal and stages) → qualified discovery AI suggested; no automatic AI CEO/CTO or manager delegation. Approved actions require an independent human reviewer. Execution and publication remain approval-gated.</p></div>
  <form onSubmit={start}>
    <label>Founder project brief<textarea value={brief} onChange={e=>setBrief(e.target.value)}
      minLength={20} maxLength={12000} required
      placeholder="What should the company build? Who uses it, what must it deliver, and what would success look like?"/></label>
    <button disabled={busy||brief.trim().length<20}>{busy?'Preparing draft…':'Prepare project from brief'}</button>
  </form>
  {error&&<p role="alert">{error}</p>}
  {created&&<div aria-live="polite"><strong>{created.title}</strong>
    <p>Draft saved · Independent plan approval needed · No unapproved code or external GitHub action started.</p>
    <ol className="intake-stage-list">{created.stages.map(s=><li key={s.stage}>
      <strong>{s.position}. {s.stage}</strong><small>{s.deliverable}</small>
      <span>{s.suggested_assignee_name||'Staffing required'}</span>
      <small>{s.plan_step_id?'Allowlisted internal review step drafted':'Proposal only; tooling and approval required'}</small>
    </li>)}</ol>
    <p>Plan ID: <code>{created.plan_id}</code> · Status: {created.plan_status} · Independent reviewer approval is required before materialization. <a href="#company-approval-inbox">View approval inbox ↑</a></p>
    {created.plan_status==='draft'&&created.stages.some(s=>s.plan_step_id)&&
      <button type="button" disabled={reviewBusy} onClick={submitForReview}>{reviewBusy?'Submitting…':'Request independent plan review'}</button>}
    {created.plan_status==='draft'&&!created.stages.some(s=>s.plan_step_id)&&
      <p>Assign a qualified discovery AI employee before submitting this draft for approval.</p>}
  </div>}
  <div><h3>Recent founder projects</h3>
   {projects===null?<small>Project history unavailable</small>:!projects.length?<small>No founder projects yet</small>:
   <ol>{projects.slice(0,5).map(p=><li key={p.id}>
     <strong>{p.title}</strong> · <small>{p.plan_status} · {p.staffing_gaps} staffing gaps</small>
     <details className="founder-routing"><summary>Who received this project? View actual draft routing</summary>
      <p>The founder brief is stored in Company Brain. No AI CEO, CTO or manager automatically receives it. Only a qualified discovery AI with an actual plan step can be assigned an approved internal brief run. Every remaining employee shown is a suggestion, not an executed handoff.</p>
      <ol>{(p.stages||[]).map(s=><li key={s.stage}><strong>{s.stage}</strong> — {s.suggested_assignee_name||'No qualified employee'} {s.suggested_role?'('+s.suggested_role+')':''} · {s.plan_step_id?'Draft plan step (approval and materialization required)':'Suggestion only; no task assigned'}</li>)}</ol>
     </details>
   </li>)}</ol>}</div>
 </section>;
}
