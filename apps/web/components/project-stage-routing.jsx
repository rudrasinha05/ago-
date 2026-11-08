"use client";
import {useEffect,useMemo,useState} from 'react';
import {defaultStageCandidate,stageCandidates,verifiedStaffing} from './project-stage-routing-state';

const ROOT='/v1/organization/company/projects/';

export function ProjectStageRouting({api,project,employees,profiles,onUpdated}){
 const [delegations,setDelegations]=useState([]),[choices,setChoices]=useState({});
 const [staffing,setStaffing]=useState(null),[staffingError,setStaffingError]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const base=ROOT+encodeURIComponent(project.id)+'/delegations';
 const staffingUrl=ROOT+encodeURIComponent(project.id)+'/staffing-proposals';
 const titleFor=id=>profiles.find(p=>p.id===id)?.role_title||employees.find(e=>e.id===id)?.role_title||'Unconfigured role';
 const candidates=stage=>stageCandidates(project,stage,employees,profiles,staffing);
 const suggested=useMemo(()=>{
  const result={};
  for(const stage of project.stages||[]){
   result[stage.stage]=defaultStageCandidate(project,stage,employees,profiles,staffing);
  }
  return result;
 },[project,employees,profiles,staffing]);

 useEffect(()=>{
  let active=true;
  setDelegations([]);setChoices({});setStaffing(null);setStaffingError('');
  setError('');setNotice('');
  api.request(base).then(r=>{if(active)setDelegations(r)})
   .catch(e=>{if(active)setError(e.message||'Delegation records unavailable')});
  if(project.plan_status==='active'){
   api.request(staffingUrl).then(raw=>{
    if(!active)return;
    const verified=verifiedStaffing(project,raw);
    if(!verified)throw Error('Unverified staffing evidence');
    setStaffing(verified);setStaffingError('');
   }).catch(()=>{if(active){setStaffing(null);setStaffingError('Verified employee eligibility unavailable. Refresh before proposing a team.')}});
  }
  return()=>{active=false};
 },[api,base,staffingUrl,project.plan_status]);

 async function refresh(){
  const [rows,receipt]=await Promise.all([
   api.request(base),
   project.plan_status==='active'?api.request(staffingUrl):Promise.resolve(null),
  ]);
  const verified=project.plan_status==='active'?verifiedStaffing(project,receipt):null;
  if(project.plan_status==='active'&&!verified){
   setStaffing(null);setStaffingError('Verified employee eligibility unavailable. No new assignment proposal was authorized.');
   throw Error('Unverified staffing evidence; no further assignments proposed');
  }
  setDelegations(rows);setStaffing(verified);setStaffingError('');
  onUpdated?.();
 }
 async function propose(stage,worker){
  if(!worker||busy)return;
  const current=project.stages?.find(s=>s.stage===stage);
  if(!current||!candidates(current).some(e=>e.id===worker)){
   setError('Worker is not in the current verified eligible shortlist. Refresh before proposing.');return;
  }
  setBusy(true);setError('');setNotice('');
  try{
   const response=await api.request(base,{method:'POST',body:{stage,assignee_id:worker}});
   await refresh();
   setNotice(stage+' proposed: '+response.status+'. Review in Founder Approvals. No work executed.');
  }catch(e){setError(e.message||'Stage proposal failed; inspect approvals before retrying')}
  finally{setBusy(false)}
 }
 async function proposeAll(){
  if(busy)return;setBusy(true);setError('');setNotice('');let done=0;
  try{
   if(project.plan_status==='active'&&!verifiedStaffing(project,staffing)){
    throw Error('Verified employee eligibility is required before proposing a team.');
   }
   for(const stage of project.stages||[]){
    if(stage.approved_assignee_id||stage.approved_assignee_name||
       delegations.some(p=>p.stage===stage.stage&&['pending','approved'].includes(p.approval_status)))continue;
    const available=candidates(stage);
    const chosen=choices[stage.stage]||suggested[stage.stage];
    const worker=available.some(e=>e.id===chosen)?chosen:'';
    if(!worker)continue;
    await api.request(base,{method:'POST',body:{stage:stage.stage,assignee_id:worker}});
    done++;
   }
   await refresh();
   setNotice(done+' assignment requests submitted for reviewed approval. Unstaffed stages still require a real qualified worker.');
  }catch(e){
   setError(done+' proposal(s) recorded before stop: '+e.message);
   try{await refresh()}catch{}
  }finally{setBusy(false)}
 }
 async function activate(stage,id){
  if(busy)return;setBusy(true);setError('');setNotice('');
  try{
   await api.request(base+'/'+encodeURIComponent(id)+'/activate',{method:'POST'});
   await refresh();
   setNotice(stage+' owner activated. Task execution still requires a separate authorization.');
  }catch(e){setError(e.message||'Activation failed; inspect stage before retrying')}
  finally{setBusy(false)}
 }
 const active=project.plan_status==='active',verified=verifiedStaffing(project,staffing);
 return <section className="project-stage-routing" aria-label="Project stage specialist assignments">
  <h5>Assign a real team to each delivery stage</h5>
  <p>Propose Discovery, Architecture, Implementation, Quality and Release AI specialists. The CEO is accountable for quality evidence and approved project delivery; QA workers do not approve their own work. Assignments do not run AI or grant new privileges.</p>
  {active&&<p role="status">{verified
   ?'Verified HR shortlist loaded: '+verified.eligible_employee_ids.length+' active AI employees. All proposals still require approval.'
   :staffingError||'Checking real employee eligibility before proposing assignments…'}</p>}
  <button type="button" onClick={proposeAll} disabled={busy||(active&&!verified)}>
   {busy?'Submitting…':'Propose eligible specialists for open stages'}</button>
  <button type="button" disabled={busy} onClick={()=>refresh().catch(e=>setError(e.message))}>Refresh approvals and eligibility</button>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <div className="project-stage-grid">{(project.stages||[]).map(stage=>{
   const available=candidates(stage);
   const pending=delegations.find(d=>d.stage===stage.stage&&d.approval_status==='pending');
   const approved=delegations.find(d=>d.stage===stage.stage&&d.approval_status==='approved'&&!d.applied_at);
   const applied=delegations.find(d=>d.stage===stage.stage&&d.applied_at);
   const option=choices[stage.stage]||suggested[stage.stage]||'';
   const worker=available.some(e=>e.id===option)?option:'';
   return <article key={stage.stage}>
    <strong>{stage.stage}</strong>
    <label>Stage owner<select aria-label={stage.stage+' specialist'} value={worker} disabled={busy||!!applied||(active&&!verified)}
     onChange={e=>setChoices(v=>({...v,[stage.stage]:e.target.value}))}>
     <option value="">Qualified employee needed</option>
     {available.map(p=><option key={p.id} value={p.id}>{p.name} — {titleFor(p.id)}</option>)}
    </select></label>
    <small>{applied?'Assigned to '+applied.worker_name:
      pending?'Pending approval: '+pending.worker_name:
      approved?'Approved; activate next':
      active&&!verified?'Waiting for verified HR eligibility':
      available.length?'Select and propose (backend checks authority again)':'Staffing gap: no verified suitable worker'}</small>
    {!applied&&!pending&&!approved&&
     <button type="button" disabled={busy||!worker} onClick={()=>propose(stage.stage,worker)}>Request assignment approval</button>}
    {approved&&<button type="button" disabled={busy||project.plan_status!=='active'}
      onClick={()=>activate(stage.stage,approved.id)}>Activate reviewed assignment</button>}
   </article>;
  })}</div>
  <p>Verified shortlists are read-only. Historical suggestions and prior approvals are rechecked by the backend; no employee is automatically hired, approved or dispatched. Stage assignment is not proof of a running task, verified quality evidence, GitHub commit, or market-ready release.</p>
 </section>;
}
