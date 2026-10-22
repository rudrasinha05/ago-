"use client";
import {useEffect,useMemo,useState} from 'react';
const ROOT='/v1/organization/company/projects/';
const MATCH={discovery:/research|product|analyst|business/i,architecture:/architect|cto|engineering lead|tech/i,implementation:/engineer|developer|programmer|full.stack/i,quality:/qa|quality|test|reviewer/i,release:/release|devops|platform|sre|delivery/i};
export function ProjectStageRouting({api,project,employees,profiles,onUpdated}){
 const [delegations,setDelegations]=useState([]),[choices,setChoices]=useState({}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const base=ROOT+encodeURIComponent(project.id)+'/delegations';
 const titleFor=id=>profiles.find(p=>p.id===id)?.role_title||employees.find(e=>e.id===id)?.role_title||'Unconfigured role';
 const candidates=stage=>employees.filter(e=>stage.stage==='quality'?(e.kind==='human'&&e.id!==project.accountable_manager_id):(e.kind==='ai'&&(!stage.plan_step_id||!stage.suggested_assignee_id||e.id===stage.suggested_assignee_id)));
 const suggested=useMemo(()=>{
  const result={};
  for(const stage of project.stages||[]){
   const staff=candidates(stage);
   result[stage.stage]=staff.find(e=>e.id===stage.suggested_assignee_id)?.id||staff.find(e=>(MATCH[stage.stage]||/./).test(titleFor(e.id)))?.id||'';
  }return result;
 },[project,employees,profiles]);
 useEffect(()=>{let active=true;setDelegations([]);setChoices({});setError('');setNotice('');
  api.request(base).then(r=>{if(active)setDelegations(r)}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[api,base]);
 async function refresh(){setDelegations(await api.request(base));onUpdated?.()}
 async function propose(stage,worker){
  if(!worker||busy)return;setBusy(true);setError('');setNotice('');
  try{const response=await api.request(base,{method:'POST',body:{stage,assignee_id:worker}});
   await refresh();setNotice(stage+' proposed: '+response.status+'. Review in Founder Approvals. No work executed.');
  }catch(e){setError(e.message||'Stage proposal failed')}finally{setBusy(false)}
 }
 async function proposeAll(){
  if(busy)return;setBusy(true);setError('');setNotice('');let done=0;
  try{
   for(const stage of project.stages||[]){
    if(stage.approved_assignee_name||delegations.some(p=>p.stage===stage.stage&&['pending','approved'].includes(p.approval_status)))continue;
    const worker=choices[stage.stage]||suggested[stage.stage];if(!worker)continue;
    await api.request(base,{method:'POST',body:{stage:stage.stage,assignee_id:worker}});done++;
   }
   await refresh();setNotice(done+' assignment requests submitted for reviewed approval. Other stages may need staffing.');
  }catch(e){setError(done+' proposal(s) recorded before stop: '+e.message);try{await refresh()}catch{}}
  finally{setBusy(false)}
 }
 async function activate(stage,id){
  if(busy)return;setBusy(true);setError('');setNotice('');
  try{await api.request(base+'/'+encodeURIComponent(id)+'/activate',{method:'POST'});
   await refresh();setNotice(stage+' owner activated. Task execution still requires a separate authorization.');
  }catch(e){setError(e.message||'Activation failed')}finally{setBusy(false)}
 }
 return <section className="project-stage-routing" aria-label="Project stage specialist assignments">
  <h5>Assign a real team to each delivery stage</h5>
  <p>Propose Discovery, Architecture, Implementation, independent Quality, and Release specialists. AI workers handle delivery proposals; Quality requires a different authorized human reviewer. Approval and activation never run AI or grant extra privileges.</p>
  <button type="button" onClick={proposeAll} disabled={busy}>{busy?'Submitting…':'Propose eligible specialists for open stages'}</button>
  <button type="button" disabled={busy} onClick={()=>refresh().catch(e=>setError(e.message))}>Refresh approvals</button>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <div className="project-stage-grid">{(project.stages||[]).map(stage=>{
   const available=candidates(stage),pending=delegations.find(d=>d.stage===stage.stage&&d.approval_status==='pending');
   const approved=delegations.find(d=>d.stage===stage.stage&&d.approval_status==='approved'&&!d.applied_at),applied=delegations.find(d=>d.stage===stage.stage&&d.applied_at);
   const worker=choices[stage.stage]||suggested[stage.stage]||'';
   return <article key={stage.stage}>
    <strong>{stage.stage}</strong>
    <label>Stage owner<select aria-label={stage.stage+' specialist'} value={available.some(p=>p.id===worker)?worker:''} disabled={busy||!!applied} onChange={e=>setChoices(v=>({...v,[stage.stage]:e.target.value}))}>
     <option value="">Qualified employee needed</option>{available.map(p=><option key={p.id} value={p.id}>{p.name} — {titleFor(p.id)}</option>)}
    </select></label>
    <small>{applied?'Assigned to '+applied.worker_name:pending?'Pending approval: '+pending.worker_name:approved?'Approved; activate next':available.length?'Select and propose':'Staffing gap: no eligible worker'}</small>
    {!applied&&!pending&&!approved&&<button type="button" disabled={busy||!worker} onClick={()=>propose(stage.stage,worker)}>Request assignment approval</button>}
    {approved&&<button type="button" disabled={busy||project.plan_status!=='active'} onClick={()=>activate(stage.stage,approved.id)}>Activate reviewed assignment</button>}
   </article>;
  })}</div>
  <p>Stage assignment is not proof of a running task, independent QA pass, GitHub commit, or market-ready release.</p>
 </section>;
}
