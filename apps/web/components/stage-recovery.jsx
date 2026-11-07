"use client";
import {useState} from 'react';
import {qaReworkStage} from './founder-delivery-state';

/** Founder: create a NEW proposed task for a failed stage (issue #10). Never approves or runs. */
export function StageRecovery({api,project,stage,onRecovered}){
 const [open,setOpen]=useState(false),[reason,setReason]=useState(''),[confirm,setConfirm]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const label=stage.stage+' stage of '+project.title;
 const text=reason.trim();
 async function save(){
  if(busy||!confirm||!text||text.length>500)return;
  setBusy(true);setError('');
  try{
   const result=await api.request('/v1/organization/company/projects/'+encodeURIComponent(project.project_id)+
    '/stages/'+encodeURIComponent(stage.stage)+'/recovery',{method:'POST',body:{failed_task_id:stage.task_id,reason:text}});
   if(result?.kind!=='ago_stage_task_recovery_v1'||result.failed_task_id!==stage.task_id||
      typeof result.recovery_task_id!=='string'||result.run_started!==false)
    throw new Error('The server did not confirm this recovery. Refresh before trying again.');
   setOpen(false);setReason('');setConfirm(false);onRecovered?.(result);
  }catch(e){setError(e.message||'Recovery not created.');}
  finally{setBusy(false);}
 }
 const rework=qaReworkStage(stage);
 const name=rework?'Rework the QA-failed '+label:'Recover the failed '+label;
 if(!open)return <button type="button" className="stage-recovery-open" onClick={()=>setOpen(true)}
  aria-label={name}>{rework?'Rework after QA FAIL':'Recover failed stage'}</button>;
 return <div className="stage-recovery" role="group" aria-label={name}>
  {rework?<p>AI QA said this stage does <strong>not</strong> meet its goal. This creates a <strong>new</strong> task for the same employee
   to redo the work; the old work and its QA FAIL stay as evidence. The new task needs its own approval and a new QA, and nothing runs now.</p>
  :<p>Creates a <strong>new</strong> task for this stage with the same employee. The failed task and its run stay as evidence.
   The new task still needs its own approval, and nothing runs now.</p>}
  <label>{rework?'What should change in the redo?':'Why is it safe to try again?'}<textarea value={reason} maxLength={500} disabled={busy}
   onChange={e=>{setReason(e.target.value);setConfirm(false);}} placeholder={rework?'For example: add the missing acceptance checklist the QA found.':'For example: the AI credit allowance is now set.'}/></label>
  <label className="stage-recovery-confirm"><input type="checkbox" checked={confirm} disabled={busy||!text}
   onChange={e=>setConfirm(e.target.checked)}/>{rework?'Create a rework task for the '+label:'Create a recovery task for the '+label}</label>
  <div className="delivery-actions">
   <button type="button" disabled={busy||!confirm||!text} onClick={save}>{busy?'Creating…':rework?'Create rework task':'Create recovery task'}</button>
   <button type="button" disabled={busy} onClick={()=>{setOpen(false);setError('');}}>Cancel</button>
  </div>
  {error&&<p role="alert">{error}</p>}
 </div>;
}
