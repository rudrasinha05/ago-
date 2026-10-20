"use client";
import {useCallback,useEffect,useRef,useState} from 'react';

const BASE='/v1/organization/company';
const fmt=date=>date?new Date(date).toLocaleString():'Not recorded';
const typeLabel={plan_review:'Strategy plan review',task_execution:'Governed task authorization',governance_action:'Other governed action'};
const subject=a=>a.plan_title||a.task_action||a.action;
const isMine=(a,me)=>a.requester_id===me.id;
const canDecide=(a,me)=>a.status==='pending'&&me.roles?.includes('founder')&&me.permissions?.includes('approval:decide');
// Presentation only: backend verifies active human founder, tenant, permission and immutable audit.

export function CompanyApprovals({api,me,employees=[],refreshSignal=0,onData,onReviewed}) {
 const [rows,setRows]=useState(null),[selected,setSelected]=useState(null);
 const [reason,setReason]=useState(''),[error,setError]=useState('');
 const [busy,setBusy]=useState(false),[toast,setToast]=useState(null);
 const [showAll,setShowAll]=useState(false);
 const previous=useRef(null),focusReturn=useRef(null),dialog=useRef(null);
 const readable=me.permissions?.includes('approval:read');

 const refresh=useCallback(async()=>{
  if(!readable)return;
  try{
   const latest=await api.request(BASE+'/approvals');
   if(!Array.isArray(latest))throw new Error('Approval inbox data unavailable.');
   const snapshot=new Map(latest.map(a=>[a.id,a.status]));
   if(previous.current===null){
    const waiting=latest.find(a=>a.status==='pending'&&canDecide(a,me));
    if(waiting)setToast({id:waiting.id,title:'Pending approval needs review',text:subject(waiting)});
   }else{
    const fresh=latest.find(a=>a.status==='pending'&&canDecide(a,me)&&!previous.current.has(a.id));
    const resolved=latest.find(a=>isMine(a,me)&&a.status!=='pending'&&previous.current.get(a.id)==='pending');
    if(fresh)setToast({id:fresh.id,title:'Approval requested',text:subject(fresh)});
    else if(resolved)setToast({id:resolved.id,title:'Approval decision recorded',text:subject(resolved)});
   }
   previous.current=snapshot;
   setRows(latest);
   onData?.(latest);
   setSelected(old=>old?latest.find(x=>x.id===old.id)||null:null);
  }catch{setRows(null);}
 },[api,me.id,me.roles,me.permissions,readable,onData]);
 useEffect(()=>{refresh();const interval=setInterval(refresh,8000);return()=>clearInterval(interval);},[refresh,refreshSignal]);
 useEffect(()=>{if(!selected)return;const focus=dialog.current?.querySelector('button');focus?.focus();
  const onKey=e=>{if(e.key==='Escape'){e.preventDefault();close();}if(e.key!=='Tab'||!dialog.current)return;
   const targets=[...dialog.current.querySelectorAll('button,textarea')].filter(x=>!x.disabled);
   if(!targets.length)return;const first=targets[0],last=targets.at(-1);
   if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
   if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  };
  document.addEventListener('keydown',onKey);
  return()=>document.removeEventListener('keydown',onKey);
 },[selected?.id]);
 function open(a){focusReturn.current=document.activeElement;setError('');setReason('');setSelected(a);setToast(null);}
 function close(){setSelected(null);setReason('');setError('');focusReturn.current?.focus?.();}
 async function decide(approve){
  if(!selected||busy||!canDecide(selected,me)||!reason.trim())return;
  setBusy(true);setError('');
  try{
   await api.request('/v1/governance/approvals/'+encodeURIComponent(selected.id)+'/decision',
    {method:'POST',body:{approve,reason:reason.trim()}});
   close();await refresh();await onReviewed?.();
  }catch(e){setError(e.message);}finally{setBusy(false);}
 }
 if(!readable)return <section id="company-approval-inbox" className="approval-inbox" aria-label="Approvals inbox">
   <h3>Approvals inbox</h3><p>Approval history is restricted to authorized employees.</p>
 </section>;
 const pending=(rows||[]).filter(a=>a.status==='pending');
 const actionable=pending.filter(a=>canDecide(a,me));
 const displayed=showAll?rows||[]:pending;
 return <section id="company-approval-inbox" className="approval-inbox" aria-label="Approvals inbox">
  <header className="approval-header">
   <div><h3>Approvals inbox <span className="approval-badge">{actionable.length} need my review</span></h3>
    <p>{pending.length} pending requests company-wide · Only the founder can approve or deny · Independent QA remains separate</p></div>
   <button type="button" onClick={()=>setShowAll(x=>!x)}>{showAll?'Show pending only':'Show history'}</button>
  </header>
  {rows===null?<p>Approval requests could not be loaded. Check permissions or connection.</p>:
   !displayed.length?<p>{showAll?'No recorded approval requests yet.':'No pending approval requests.'}</p>:
   <div className="approval-rows">{displayed.map(a=><article key={a.id} className="approval-entry">
    <div><strong>{subject(a)}</strong><small>{typeLabel[a.approval_type]} · {a.status} · Requested {fmt(a.created_at)}</small>
     <small>From: {a.requester_name} ({a.requester_role||'Role not recorded'})</small>
     <small>{canDecide(a,me)?'Founder decision required':isMine(a,me)?'Awaiting your founder decision':'Awaiting founder decision'}</small></div>
    <button type="button" onClick={()=>open(a)}>View approval details</button>
   </article>)}</div>}
  {toast&&<div className="approval-toast" role="status">
    <strong>{toast.title}</strong><p>{toast.text}</p>
    <button type="button" onClick={()=>{const match=rows?.find(x=>x.id===toast.id);if(match)open(match);}}>View details</button>
    <button type="button" onClick={()=>setToast(null)} aria-label="Dismiss approval notification">×</button>
  </div>}
  {selected&&<div className="approval-overlay" onMouseDown={e=>{if(e.target===e.currentTarget)close();}}>
   <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="approval-detail-title" className="approval-dialog">
    <header><div><small>{typeLabel[selected.approval_type]}</small><h2 id="approval-detail-title">Approval details</h2></div>
     <button type="button" onClick={close} aria-label="Close approval details">✕</button></header>
    <h3>{subject(selected)}</h3>
    <dl>
     <dt>Requested by</dt><dd>{selected.requester_name} · {selected.requester_role||'Role not recorded'}</dd>
     {selected.requester_manager_name&&<><dt>Reports to</dt><dd>{selected.requester_manager_name}</dd></>}
     <dt>Requested at</dt><dd>{fmt(selected.created_at)}</dd>
     <dt>Status</dt><dd>{selected.status}</dd>
     <dt>Who can approve?</dt><dd>{selected.review_routing}</dd>
     <dt>Approval ID</dt><dd><code>{selected.id}</code></dd>
     <dt>Exact governed action</dt><dd><code>{selected.action}</code></dd>
     {selected.department_name&&<><dt>Department</dt><dd>{selected.department_name}</dd></>}
     {selected.plan_title&&<><dt>Plan</dt><dd>{selected.plan_title}</dd></>}
     {selected.plan_id&&<><dt>Plan ID</dt><dd><code>{selected.plan_id}</code></dd></>}
     {selected.task_id&&<><dt>Task / assignee</dt><dd>{selected.task_action} · {selected.task_assignee_name||'Unassigned'}</dd></>}
     {selected.goal_brief_excerpt&&<><dt>Founder brief (excerpt)</dt><dd className="approval-long">{selected.goal_brief_excerpt}</dd></>}
     <dt>What approval enables</dt><dd>{selected.next_action}</dd>
     <dt>Evidence</dt><dd>{selected.goal_brief_excerpt?'Founder brief and stored plan are linked. No code, tests or external release evidence claimed.':'No additional evidence attached in this inbox; inspect the source workflow before deciding.'}</dd>
     {selected.reviewer_id&&<><dt>Decided by</dt><dd>{selected.reviewer_name}</dd><dt>Decision at</dt><dd>{fmt(selected.decided_at)}</dd></>}
     {selected.reason&&<><dt>Decision reason</dt><dd>{selected.reason}</dd></>}
    </dl>
    {selected.status==='pending'&&<div className="approval-review">
      {canDecide(selected,me)?<>
       <label htmlFor="approval-reason">Mandatory decision reason</label>
       <textarea id="approval-reason" value={reason} onChange={e=>setReason(e.target.value)}
         required maxLength={3000} rows={3} placeholder="Explain the reviewed scope and your decision"/>
       <div className="approval-actions"><button type="button" disabled={!reason.trim()||busy} onClick={()=>decide(true)}>Approve</button>
        <button type="button" disabled={!reason.trim()||busy} onClick={()=>decide(false)}>Deny</button></div>
      </>:<p>'Only the authenticated founder can approve or deny this request. You can still inspect its details.'</p>}
    </div>}
    {error&&<p role="alert">{error}</p>}
   </section>
  </div>}
 </section>;
}

export function ApprovalTopAlerts({api,me,onView,enabled=true}) {
 const [pending,setPending]=useState(0),[notice,setNotice]=useState(null);
 const prior=useRef(null);
 const readable=me.permissions?.includes('approval:read');
 useEffect(()=>{
  if(!enabled||!readable)return;
  let live=true;
  async function check(){
   try {
    const data=await api.request(BASE+'/approvals');
    if(!live||!Array.isArray(data))return;
    const needs=data.filter(a=>canDecide(a,me));
    const known=new Set(data.map(a=>a.id));
    const arrived=needs.find(a=>prior.current===null||!prior.current.has(a.id));
    setPending(needs.length);
    if(arrived)setNotice({id:arrived.id,requester:arrived.requester_name,title:subject(arrived)});
    prior.current=known;
   }catch{if(live)setPending(0);}
  }
  check();const timer=setInterval(check,8000);
  return()=>{live=false;clearInterval(timer);};
 },[api,me.id,me.permissions,me.roles,enabled,readable]);
 if(!readable||!enabled)return null;
 return <div className="approval-top-alerts">
  <button type="button" className="approval-top-button" onClick={onView}>
   Approvals {pending>0&&<span aria-label={pending+' approvals need your review'}>{pending}</span>}
  </button>
  {notice&&<div className="approval-top-notice" role="status">
   <strong>Founder approval needed</strong>
   <p>{notice.requester||'Employee'} requests: {notice.title}</p>
   <button type="button" onClick={()=>{setNotice(null);onView?.();}}>View details</button>
   <button type="button" onClick={()=>setNotice(null)} aria-label="Dismiss approval popup">×</button>
  </div>}
 </div>;
}
