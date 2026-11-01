"use client";
import Link from 'next/link';
import {useEffect,useRef,useState} from 'react';
import {RecoveryHint} from './recovery-hint';
import {canReadDelivery,deliveryPage,DELIVERY_STATES,deliveryEvidence,founderDecisions,projectTaskIds,reviewedStages} from './founder-delivery-state';

export function FounderDeliveryJourney({api,me,active=true,refreshSignal=0,onProject,onWork,onSection,onApproval}){
 const [page,setPage]=useState(null),[offset,setOffset]=useState(0),[loading,setLoading]=useState(false);
 const [error,setError]=useState(''),[failure,setFailure]=useState(null),[refresh,setRefresh]=useState(0);
 const sequence=useRef(0);
 const readable=canReadDelivery(me);
 useEffect(()=>{
  if(!readable||!active){sequence.current++;setPage(null);return undefined;}
  let live=true;
  async function load(){
   const version=++sequence.current;setLoading(true);
   try{
    const result=deliveryPage(await api.request('/v1/organization/company/projects/delivery-overview?limit=20&offset='+offset));
    if(live&&version===sequence.current){setPage(result);setError('');setFailure(null);}
   }catch(e){if(live&&version===sequence.current){setPage(null);setFailure(e);setError(e.message||'Delivery overview unavailable.');}}
   finally{if(live&&version===sequence.current)setLoading(false);}
  }
  setPage(null);load();
  const timer=setInterval(load,15000);
  return()=>{live=false;sequence.current++;clearInterval(timer);};
 },[api,readable,active,offset,refresh,refreshSignal]);
 if(!readable)return null;
 const canInspect=me.permissions?.includes('brain:manage');
 return <section className="founder-delivery-journey" aria-label="Project delivery journey" aria-busy={loading}>
  <header><div><h2>Project delivery journey</h2><p>Describe → approve scope → follow team work → review evidence</p></div>
   <div className="delivery-actions">{canInspect&&<button type="button" onClick={()=>onSection('ago-tab-projects')}>Start a project</button>}
    <button type="button" disabled={loading} onClick={()=>setRefresh(x=>x+1)}>Refresh delivery status</button></div>
  </header>
  {error&&<p role="alert">{error} Use Refresh to retry; no previous success is assumed.</p>}
  {error&&<RecoveryHint error={failure}/>}
  {!page&&!error&&<p role="status">Loading current project evidence…</p>}
  {page&&page.projects.length>0&&(()=>{const n=page.projects.reduce((sum,p)=>sum+founderDecisions(p).length,0);
   return <p role="status" className="delivery-decision-summary">{n?n+' decision(s) on this page wait for you.':'No decision on this page waits for you.'}</p>;})()}
  {page&&!page.projects.length&&<p>No projects on this page. {offset===0?'Start with a project brief.':'Return to the previous page.'}</p>}
  <div className="delivery-project-grid">{page?.projects.map(p=>{
   const [label,guidance]=DELIVERY_STATES[p.delivery_state];
   const taskIds=projectTaskIds(p);
   return <article key={p.project_id} aria-label={'Delivery: '+p.title}>
    <h3>{p.title}</h3><p className={'delivery-state state-'+p.delivery_state}>{label}</p>
    <p>Responsible manager: {p.manager||'Not assigned'}</p><p>{guidance}</p>
    <p>{reviewedStages(p)} of {p.stages.length} stages have completed work and passed QA.</p>
    <ol>{p.stages.map((s,i)=><li key={s.stage+':'+i}>
     <strong>{s.stage}</strong><span>{s.employee||'Employee not assigned'}</span>
     <small>Task: {s.task_status||'not created'} · QA: {s.qa_verdict||'not reviewed'}</small>
     {s.agent_failure_code&&<small>Recorded failure: {s.agent_failure_code}</small>}
    </li>)}</ol>
    <ul className="delivery-evidence" aria-label={'Delivery evidence for '+p.title}>{deliveryEvidence(p).map(e=>
     <li key={e.key} className={e.verified?'verified':undefined}>{e.label}: {e.verified?'Verified':'Not verified'}</li>)}</ul>
    {p.pending_approvals.length>0&&<p>{p.pending_approvals.length} linked pending request(s) in the current approval inbox.</p>}
    {onApproval&&founderDecisions(p).length>0&&<section className="delivery-decisions" aria-label={'Decisions waiting for you: '+p.title}>
     <h4>Your decision is needed</h4>
     <ul>{founderDecisions(p).map(a=><li key={a.approval_id}><span>{a.label}</span>
      <button type="button" onClick={()=>onApproval(a.approval_id)} aria-label={'Review and decide: '+a.label+' for '+p.title}>Review &amp; decide</button></li>)}</ul>
    </section>}
    <div className="delivery-actions">
     {canInspect&&<button type="button" onClick={()=>onProject(p)}>Inspect project</button>}
     {me.permissions?.includes('task:read')&&taskIds.length>0&&<button type="button" onClick={()=>onWork({id:p.project_id,title:p.title,taskIds})}>View project work</button>}
     {p.pending_approvals.length>0&&<button type="button" onClick={()=>onSection('company-approval-inbox')}>Open approval inbox</button>}
     {p.delivery_state==='waiting_for_independent_qa'&&<Link href="/governance/">Open independent QA</Link>}
     {me.permissions?.includes('organization:manage')&&<button type="button" onClick={()=>onSection('ago-github-delivery')}>View GitHub evidence</button>}
    </div>
    <small>Stage review does not certify Docker tests, a GitHub delivery or release.</small>
   </article>;
  })}</div>
  <nav className="delivery-actions" aria-label="Project delivery pages">
   <button type="button" disabled={offset===0||loading} onClick={()=>setOffset(x=>Math.max(0,x-20))}>Previous projects</button>
   <span>Page {offset/20+1}</span>
   <button type="button" disabled={loading||!page?.more_projects_possible} onClick={()=>setOffset(x=>x+20)}>Next projects</button>
  </nav>
 </section>;
}
