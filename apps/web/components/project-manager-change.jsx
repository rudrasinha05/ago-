"use client";
import {useEffect,useRef,useState} from 'react';

const PM_ROLES=new Set(['project manager','ai project manager','ai project manager (pm)','technical project manager']);
export function ProjectManagerChange({api,project,profiles=[],board=[],onSaved}){
 const [choice,setChoice]=useState(''),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const live=useRef(true);
 useEffect(()=>{live.current=true;return()=>{live.current=false}},[]);
 const ceo=board.find(b=>b.seat==='Strategy & Vision')?.employee_id;
 const ceoIsAI=profiles.some(e=>e.id===ceo&&e.kind==='ai');
 const excluded=new Set(board.map(b=>b.employee_id));
 for(const stage of project.stages||[]){
  if(['discovery','implementation','quality'].includes(stage.stage))excluded.add(stage.suggested_assignee_id);
  if(stage.approved_assignee_id)excluded.add(stage.approved_assignee_id);
 }
 const candidates=profiles.filter(e=>ceoIsAI&&e.kind==='ai'&&e.manager_id===ceo&&
  PM_ROLES.has((e.role_title||'').trim().toLowerCase())&&!excluded.has(e.id)&&e.id!==project.accountable_manager_id);
 const selected=candidates.find(e=>e.id===choice);
 const running=(project.stages||[]).some(s=>s.task_status==='running'||s.agent_run_status==='running');
 async function save(){
  if(busy||!confirm||!selected||running)return;
  setBusy(true);setError('');
  try{
   const result=await api.request('/v1/organization/company/projects/'+encodeURIComponent(project.id)+'/accountable-manager',{
    method:'POST',body:{employee_id:selected.id,expected_manager_id:project.accountable_manager_id}});
   if(!live.current)return;
   if(result?.id!==project.id||result?.accountable_manager_id!==selected.id||
      result?.manager_change?.manager_id!==selected.id)throw new Error('Manager response did not match this project. Refresh project details before retrying.');
   onSaved(result);
  }catch(e){if(live.current)setError(e.message||'Manager change failed. Refresh project details before retrying.');}
  finally{if(live.current)setBusy(false);}
 }
 return <section aria-label="Change accountable manager" className="project-manager-change">
  <h5>Change accountable manager</h5>
  <p>Keep this project, its tasks and approval history. Choose an AI Project Manager reporting to the appointed AI CEO.</p>
  {running?<p role="status">Wait for running project work to stop before changing manager.</p>:
   !candidates.length?<p role="status">No eligible replacement AI Project Manager is available. Check the PM role and reporting line in Board &amp; Roles; Board members and project workers cannot fill this role.</p>:<>
    <label>New accountable manager<select value={selected?.id||''} disabled={busy} onChange={e=>{setChoice(e.target.value);setConfirm(false);setError('')}}>
     <option value="">Select an eligible AI PM</option>
     {candidates.map(e=><option key={e.id} value={e.id}>{e.name} — {e.role_title}</option>)}
    </select></label>
    {selected&&<><p>Change from {project.accountable_manager_name} to {selected.name}. This records an audit entry; it does not approve or run work.</p>
     <label><input type="checkbox" checked={confirm} disabled={busy} onChange={e=>setConfirm(e.target.checked)}/>Confirm this manager change for {project.title}</label>
     <button type="button" disabled={busy||!confirm} onClick={save}>{busy?'Saving manager…':'Save accountable manager'}</button></>}
   </>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
