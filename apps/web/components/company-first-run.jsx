"use client";
import {useMemo,useState} from 'react';
import {FIRST_RUN_ACTIONS,firstRunReadiness,taskBootstrapBody} from '@ago/sdk/company-first-run';
export function CompanyFirstRun({api,me,tasks,employees,onCreated}){
 const readiness=useMemo(()=>firstRunReadiness(employees,me.permissions,tasks),[employees,me.permissions,tasks]);
 const [employeeId,setEmployeeId]=useState(''),[action,setAction]=useState('internal:brief');
 const [creating,setCreating]=useState(false),[error,setError]=useState(''),[created,setCreated]=useState(null);
 const [expanded,setExpanded]=useState(false);
 const canCreate=readiness.canStart&&!creating;
 const assigned=readiness.eligible.some(x=>x.id===employeeId)?employeeId:readiness.eligible[0]?.id||'';
 async function create(event){
  event.preventDefault();
  if(!canCreate)return;
  setCreating(true);setError('');setCreated(null);
  try{
   const body=taskBootstrapBody(action,assigned,readiness.eligible);
   const result=await api.request('/v1/tasks',{method:'POST',body});
   if(!result?.id||result.status!=='proposed')throw new Error('Server did not confirm an exact proposed task; inspect the task register before retrying');
   setCreated({id:result.id,action:body.action,assignee_id:body.assignee_id});
   await onCreated?.();
  }catch(e){setError((e.message||'Task creation unavailable')+'. Inspect task register before retrying to avoid duplicates.');}
  finally{setCreating(false);}
 }
 if(!me.roles?.includes('founder')||!me.permissions?.includes('organization:read'))return null;
 return <section className="company-first-run" aria-label="First approved AI work setup">
  <header><div><h4>First AI employee run</h4>
   <p>Last dry-run returned zero eligible tasks? Start with a real registered employee and a new governed task. Creating a task does not approve or run it.</p></div>
   <button type="button" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?'Hide setup':'Set up first task'}</button>
  </header>
  {expanded&&<>
   <p role={!readiness.canStart?'status':undefined}>{readiness.reason}</p>
   <form onSubmit={create} className="first-run-form">
    <label htmlFor="first-run-specialist">AI employee</label>
    <select id="first-run-specialist" value={assigned} onChange={e=>setEmployeeId(e.target.value)} disabled={!readiness.canStart||creating}>
     {!readiness.eligible.length&&<option value="">No AI employee recorded</option>}
     {readiness.eligible.map(e=><option key={e.id} value={e.id}>{e.name} · {e.role_title||'Role from Company Planner'}</option>)}
    </select>
    <label htmlFor="first-run-action">First-run task type</label>
    <select id="first-run-action" value={action} onChange={e=>setAction(e.target.value)} disabled={!readiness.canStart||creating}>
     {FIRST_RUN_ACTIONS.map(item=><option key={item.value} value={item.value}>{item.label}</option>)}
    </select>
    <p>{action==='research:brief'?'Real text generation: requires a configured local Ollama provider, installed model, virtual credit allowance and reviewed execution. No browser-only switch can configure the backend.':'Deterministic internal control task: useful for testing approvals and independent QA. It does not call an AI model or generate code.'}</p>
    <button type="submit" disabled={!canCreate}>{creating?'Creating recorded proposal…':'Create proposed task (no execution)'}</button>
   </form>
   {created&&<div role="status" className="first-run-created"><strong>Proposed task recorded: {created.id}</strong>
    <p>Next: find this task in the queue below → Request approval → Founder Approvals (or independent reviewer) → Run approved AI → Governance QA.</p>
    {created.action==='research:brief'&&<p>For Ollama configuration use the local model check and restart the server with explicitly enabled local inference. This is not eligible for the separate internal:brief-only batch script.</p>}
   </div>}
   {error&&<p role="alert">{error}</p>}
   <ol><li>Create a proposed task for an actual AI employee.</li>
    <li>Request independent action approval from the task row below.</li>
    <li>Approve in the Founder Approvals inbox with an allowed human decision.</li>
    <li>Dispatch exactly once, then independently review task evidence in Governance.</li></ol>
   <small>This is an isolated internal validation task, not an automatically linked customer project or a claim of market-ready code.</small>
  </>}
 </section>;
}
