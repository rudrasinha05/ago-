"use client";
import {useEffect,useState} from 'react';
import {creditBlocker,selfCheck} from './task-self-check-state';

/** Read-only "can this run?" check shown before the Founder presses Run. */
export function TaskSelfCheck({api,me,task,refreshSignal=0,credits}){
 const [result,setResult]=useState(null),[state,setState]=useState('loading'),[attempt,setAttempt]=useState(0);
 const eligible=Boolean(me.roles?.includes('founder')&&me.permissions?.includes('agent:read')&&task?.id);
 useEffect(()=>{
  if(!eligible)return undefined;
  let live=true;setState('loading');
  api.request('/v1/agents/tasks/'+encodeURIComponent(task.id)+'/engineering-preflight')
   .then(report=>{if(live){setResult(selfCheck(report));setState('ok');}})
   // 403: not available to this session or outside local development: stay silent.
   .catch(e=>{if(live){setResult(null);setState(e?.status===403?'hidden':'error');}});
  return()=>{live=false;};
 },[api,eligible,task?.id,task?.status,refreshSignal,attempt]);
 if(!eligible||state==='hidden')return null;
 const label='AGO self-check for '+(task.project_name||'task')+' · '+task.id.slice(0,8);
 if(state==='loading')return <div className="task-self-check" role="status" aria-label={label}>AGO is checking whether this task can run…</div>;
 const view=result&&creditBlocker(result,credits);
 if(state==='error'||!result)return <div className="task-self-check" role="status" aria-label={label}>Self-check unavailable right now. The server still checks everything when you press Run.</div>;
 return <div className={'task-self-check '+(view.ready?'ready':'blocked')} role="group" aria-label={label}>
  {view.ready
   ?<p><strong>Self-check passed.</strong> Approval, project link and AI team{view.roles.length?' ('+view.roles.join(', ')+')':''} are in place.</p>
   :<><p><strong>Self-check: Run will be refused.</strong> AGO found {view.blockers.length} problem{view.blockers.length===1?'':'s'}:</p>
    <ul>{view.blockers.map(b=><li key={b.code}><span>{b.what}</span><small>Who fixes it: {b.fix}</small></li>)}</ul>
    {view.repair&&<p>{view.repair}</p>}</>}
  {view.laterGates.length>0&&<small>Checked only when Run is pressed: {view.laterGates.join(', ')}.</small>}
  <button type="button" className="task-self-check-again" onClick={()=>setAttempt(n=>n+1)}
   aria-label={'Check again: '+label}>Check again</button>
 </div>;
}
