"use client";
import {useState} from 'react';
import {decideFounderScope} from './company-founder-decision';
export function CompanyApprovalBadge({employee,approvals,updates=0,api,me,onDone,zoom=1}){
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const pending=(approvals||[]).filter(a=>a.status==='pending'&&
  (a.requester_id===employee.id||a.task_assignee_id===employee.id));
 const count=updates+pending.length;
 if(!count&&!notice&&!error)return null;
 const founder=me.roles?.includes('founder');
 async function decide(request,approve){
  if(!founder||!request.requires_founder_decision||busy)return;
  setBusy(request.id);setError('');
  try{
   const result=await decideFounderScope(api,request,approve,
    'Founder '+(approve?'approved':'denied')+' exact scope '+request.action+' from employee notification.');
   setNotice(result.notice);
   setOpen(true);
   await onDone?.();
  }catch(e){setError(e.message||'Decision was not recorded');}
  finally{setBusy('');}
 }
 return <div className="employee-approval-zone" style={{'--employee-popup-zoom':Math.min(5,Math.max(.75,1/zoom))}} onMouseEnter={()=>setOpen(true)} onMouseLeave={()=>setOpen(false)}
  onFocus={()=>setOpen(true)} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setOpen(false)}}>
  <button className="employee-approval-counter" type="button" aria-label={count+' notifications for '+employee.name}
   aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{count}</button>
  {open&&<section className="employee-approval-flyout" aria-label={employee.name+' notification actions'}>
   <strong>{employee.name} · {count} update(s)</strong>
   {!!updates&&<p>{updates} recorded work updates. Select the employee for details.</p>}
   {!pending.length&&<p>No pending Founder decisions.</p>}
   {pending.map(a=><article key={a.id}><p><b>{a.action}</b> · pending</p>
    {founder&&a.requires_founder_decision?<div className="employee-approval-actions"><button type="button" disabled={!!busy}
      onClick={()=>decide(a,true)}>Approve</button><button type="button" disabled={!!busy}
      onClick={()=>decide(a,false)}>Deny</button></div>:<p>CEO verifies routine work within the Founder-approved scope.</p>}
   </article>)}
   {notice&&<div role="status"><p>{notice}</p><button type="button" onClick={()=>{setNotice('');setOpen(false);}}>Dismiss confirmation</button></div>}
   {error&&<p role="alert">{error}</p>}
  </section>}
 </div>;
}
