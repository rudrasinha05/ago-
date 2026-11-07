"use client";
import {useEffect,useState} from 'react';
import {boardDenial} from './founder-delivery-state';

const VOTE={approve:'APPROVE',deny:'DENY',unverified:'no clear vote'};

/** Who on the AI Board stopped a stage, why, and (Founder rule) the option to allow it. */
export function BoardDenial({api,project,stage,onAllowed}){
 const [view,setView]=useState(null),[error,setError]=useState('');
 const [open,setOpen]=useState(false),[reason,setReason]=useState(''),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false);
 useEffect(()=>{
  let live=true;
  api.request('/v1/organization/company/projects/'+encodeURIComponent(project.project_id))
   .then(detail=>{if(!live)return;const s=(detail?.stages||[]).find(x=>x.task_id===stage.task_id);setView(boardDenial(s?.founder_agent_result));})
   .catch(e=>{if(live)setError(e.message||'Board votes unavailable.');});
  return()=>{live=false;};
 },[api,project.project_id,stage.task_id]);
 if(error)return <small role="status">{error}</small>;
 if(!view)return null;
 const label=stage.stage+' stage of '+project.title;
 const text=reason.trim();
 async function allow(){
  if(busy||!confirm||!text)return;
  setBusy(true);setError('');
  try{
   const r=await api.request('/v1/organization/company/projects/'+encodeURIComponent(project.project_id)+
    '/stages/'+encodeURIComponent(stage.stage)+'/board-override',{method:'POST',body:{failed_task_id:stage.task_id,seat:view.stoppedBy,reason:text}});
   if(r?.kind!=='ago_board_founder_override_v1'||r.seat!==view.stoppedBy||r.run_started!==false)
    throw new Error('The server did not confirm this decision. Refresh before trying again.');
   onAllowed?.(r);
  }catch(e){setError(e.message||'Decision not recorded.');}
  finally{setBusy(false);}
 }
 return <div className="board-denial" role="group" aria-label={'AI Board votes for the '+label}>
  <strong>AI Board votes</strong>
  <ul>{view.votes.map(v=><li key={v.seat} className={'vote-'+v.recommendation}>
   <span>{v.seat}: <b>{VOTE[v.recommendation]||v.recommendation}</b>{v.override?' (allowed by the Founder)':''}</span>
   {v.recommendation!=='approve'&&<small>{v.reason?'Reason: '+v.reason:'No reason was given.'}</small>}
  </li>)}</ul>
  <p>Stopped by <b>{view.stoppedBy}</b>.</p>
  {view.overridable?(!open
   ?<button type="button" onClick={()=>setOpen(true)} aria-label={'Founder: allow the '+label+' despite the '+view.stoppedBy+' vote'}>Founder: allow the project anyway</button>
   :<div className="board-denial-allow">
    <p>The AI CEO and AI CTO approved. If you allow it, the {view.stoppedBy} vote stays recorded as advice for this project,
     no longer stops the AI team, and the stage gets a new task (it still needs its own approval; nothing runs now).</p>
    <label>Why do you allow it?<textarea value={reason} maxLength={500} disabled={busy} onChange={e=>{setReason(e.target.value);setConfirm(false);}}/></label>
    <label className="board-denial-confirm"><input type="checkbox" checked={confirm} disabled={busy||!text} onChange={e=>setConfirm(e.target.checked)}/>
     Allow {project.title} past the {view.stoppedBy} vote</label>
    <div className="delivery-actions">
     <button type="button" disabled={busy||!confirm||!text} onClick={allow}>{busy?'Recording…':'Allow and create the new task'}</button>
     <button type="button" disabled={busy} onClick={()=>setOpen(false)}>Cancel</button>
    </div>
   </div>)
  :<p>Only a Finance, Risk or Quality vote can be allowed by the Founder, and only after the AI CEO and AI CTO approved. Recover the stage to try again.</p>}
  {error&&<p role="alert">{error}</p>}
 </div>;
}
