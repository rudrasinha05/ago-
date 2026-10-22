"use client";
import Link from 'next/link';
import {useState} from 'react';
import {executionSummary,nextTaskAction} from '@ago/sdk/company-execution';
export function CompanyExecutionDesk({api,me,tasks,approvals,employees,onChange,onEmployee}){
 const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[showAll,setShowAll]=useState(false);
 const canView=me.permissions?.includes('task:read')&&me.permissions?.includes('organization:read');
 if(!canView)return null;
 const summary=executionSummary(tasks);
 const pending=(tasks||[]).filter(t=>['proposed','waiting_approval','ready','running'].includes(t.status));
 const completed=(tasks||[]).filter(t=>['completed','failed'].includes(t.status));
 const rows=showAll?[...pending,...completed].slice(0,75):pending.slice(0,20);
 const approvalsById=new Map((approvals||[]).map(x=>[x.id,x]));
 const name=id=>employees.find(x=>x.id===id)?.name||'Employee not found';
 async function execute(task,operation){
  if(busy)return;
  // Recheck the UI transition: server also independently enforces approval and rights.
  const gate=nextTaskAction(task,approvalsById.get(task.approval_id),me.permissions,false);
  if(gate.action!==operation){setError('Action unavailable: '+gate.reason);return}
  setError('');setNotice('');setBusy(task.id);
  try{
   if(operation==='request'){
    const response=await api.request('/v1/console/tasks/'+encodeURIComponent(task.id)+'/request-approval',{method:'POST'});
    setNotice('Task approval submitted: '+response.status+'. Independent/founder decision required.');
   }else{
    const result=await api.request('/v1/agents/tasks/'+encodeURIComponent(task.id)+'/run',{method:'POST',timeoutMs:270000});
    setNotice(result.status==='completed'?'AI execution recorded. Independent human QA required.':'Agent outcome: '+result.status+'. Verify persisted task status before further action.');
   }
  }catch(e){
   setError((e.message||'Task operation failed')+'. Check recorded task history before any retry. The server may have completed a run even if the browser timed out.');
  }finally{setBusy('');await onChange?.()}
 }
 return <section className="company-execution-desk" id="ago-execution-desk" aria-label="Governed AI task execution queue">
   <h3>Execution Desk · Approved company work</h3>
   <p>Real server-side task records only. Approval enables governed execution; no automatic model run, source commit, or release occurs from viewing this desk.</p>
   {summary===null?<p role="alert">Task activity unavailable. Execution is disabled until the authenticated server responds.</p>:<>
    <div className="execution-metrics">
      <span><strong>{summary.proposed}</strong>Needs task approval request</span>
      <span><strong>{summary.awaiting}</strong>Awaiting decision / dispatch</span>
      <span><strong>{summary.running}</strong>Recorded running</span>
      <span><strong>{summary.completed}</strong>Needs QA / reviewed</span>
      <span><strong>{summary.failed}</strong>Failed evidence</span>
    </div>
    {!pending.length?<p>No runnable or queued governed tasks. Project plans must be active and tasks materialized first.</p>:null}
    <button type="button" onClick={()=>setShowAll(v=>!v)}>{showAll?'Show active work only':'Include completed and failed tasks'}</button>
    <div className="execution-task-list">{rows.map(t=>{
      const choice=nextTaskAction(t,approvalsById.get(t.approval_id),me.permissions,Boolean(busy));
      return <article key={t.id}>
        <div><strong>{t.project_name||'Unlinked governed task'}</strong><small>{t.action} · {t.status} · {t.id.slice(0,8)}…</small></div>
        <div><button type="button" className="execution-worker-link" onClick={()=>onEmployee?.(t.assignee_id)}>{name(t.assignee_id)} ↗</button><small>{choice.reason}</small></div>
        {choice.action&&<button type="button" disabled={Boolean(busy)} onClick={()=>execute(t,choice.action)}>
          {busy===t.id?'Processing…':choice.action==='request'?'Request approval':'Run approved AI'}
        </button>}
        {t.status==='completed'&&<Link href="/governance/">Review independent QA in Governance →</Link>}
      </article>;
    })}</div>
   </>}
   {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
   <small>Dispatch is one task at a time, from a founder/user action. Failed/time-out runs are not automatically replayed. For bounded batch use, run the separate founder-confirmed local script. All execution authority remains enforced by AGO backend.</small>
  </section>;
}
