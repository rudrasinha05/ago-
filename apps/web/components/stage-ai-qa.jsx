"use client";
import {useState} from 'react';
import {aiQaReviewers} from './founder-delivery-state';

const VERDICT={pass:'PASS — the stage passed AI QA.',fail:'FAIL — the stage did not pass AI QA. Read the findings below.',
 unverified:'No clear verdict from the model. Nothing was recorded as QA; you can ask again.'};

/** Founder asks an independent AI QA employee to check a finished stage (issue #8 M4). */
export function StageAiQa({api,project,stage,profiles,onReviewed}){
 const reviewers=aiQaReviewers(profiles);
 const [open,setOpen]=useState(false),[choice,setChoice]=useState(''),[confirm,setConfirm]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState(null);
 const label=stage.stage+' stage of '+project.title;
 async function run(){
  if(busy||!confirm||!choice)return;
  setBusy(true);setError('');setResult(null);
  try{
   const r=await api.request('/v1/organization/company/projects/'+encodeURIComponent(project.project_id)+
    '/stages/'+encodeURIComponent(stage.stage)+'/ai-qa',{method:'POST',body:{qa_employee_id:choice,operation_key:crypto.randomUUID()}});
   if(r?.kind!=='ago_ai_qa_review_v1'||r.task_id!==stage.task_id||!['pass','fail','unverified'].includes(r.verdict)||r.executed_or_released!==false)
    throw new Error('The server did not confirm this AI QA review. Refresh before trying again.');
   setResult(r);setConfirm(false);onReviewed?.(r);
  }catch(e){setError(e.message||'AI QA was not recorded.');}
  finally{setBusy(false);}
 }
 if(!open)return <button type="button" className="stage-ai-qa-open" onClick={()=>setOpen(true)}
  aria-label={'Ask AI QA to check the '+label}>Ask AI QA to check</button>;
 return <div className="stage-ai-qa" role="group" aria-label={'AI QA for the '+label}>
  <p>An AI QA employee who did <strong>not</strong> build this work checks it against the stage goal.
   It uses 1 internal AI credit and one local model answer. Nothing is run, committed or released.</p>
  {!reviewers.length?<p role="status">No AI employee with a QA role yet. Hire or retitle an AI employee as “QA Engineer” in Board &amp; Roles.</p>:<>
   <label>AI QA employee<select value={choice} disabled={busy} onChange={e=>{setChoice(e.target.value);setConfirm(false);}}>
    <option value="">Choose…</option>
    {reviewers.map(e=><option key={e.id} value={e.id}>{e.name} — {e.role_title}</option>)}
   </select></label>
   <label className="stage-ai-qa-confirm"><input type="checkbox" checked={confirm} disabled={busy||!choice}
    onChange={e=>setConfirm(e.target.checked)}/>Ask this AI QA employee to check the {label}</label>
  </>}
  <div className="delivery-actions">
   <button type="button" disabled={busy||!confirm||!choice} onClick={run}>{busy?'AI QA is checking… (up to 1 minute)':'Run AI QA check'}</button>
   <button type="button" disabled={busy} onClick={()=>{setOpen(false);setError('');setResult(null);}}>Close</button>
  </div>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status" className={'stage-ai-qa-result verdict-'+result.verdict}>
   <strong>{VERDICT[result.verdict]}</strong>
   <small>Reviewer: {result.qa_employee_name} · model {result.model} · receipt {result.receipt_id.slice(0,8)}…</small>
   <details><summary>AI QA findings</summary><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{result.response_text}</p></details>
  </div>}
 </div>;
}
