"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {deliverySteps,githubDeliveryRows,sameRecord,verifiedGitHubChecks} from './company-github-delivery-state';
import {RecoveryHint} from './recovery-hint';

const STEP_STATE={done:'Done',action:'Your action',waiting:'Waiting for reviewer',blocked:'Blocked',todo:'Not yet'};
function Steps({row,label}){
 return <ol className="github-steps" aria-label={'Delivery steps: '+label}>{deliverySteps(row).map(s=>
  <li key={s.key} className={'step-'+s.state} data-step={s.key} data-state={s.state}>
   <span aria-hidden="true"/>{s.title}<small>{STEP_STATE[s.state]}</small></li>)}</ol>;
}

/** Read authenticated evidence only; backend remains the sole approval/write authority. */
export function CompanyGithubDelivery({api,me}){
 const [projects,setProjects]=useState(null);
 const [operations,setOperations]=useState([]);
 const [proposals,setProposals]=useState([]);
 const [error,setError]=useState('');
 const [notice,setNotice]=useState('');
 const [busy,setBusy]=useState('');
 const [pending,setPending]=useState(null),[failure,setFailure]=useState(null);
 const used=useRef(new Set());
 const founder=me?.roles?.includes('founder')&&me.permissions?.includes('organization:manage');
 const refresh=useCallback(async()=>{
  if(!founder)return;
  try{
   const [catalog,review]=await Promise.all([
    api.request('/v1/platform/catalog'),
    api.request('/v1/enterprise/reviews/integration'),
   ]);
   if(!Array.isArray(catalog?.github_projects)||!Array.isArray(catalog?.github_operations)||
      !Array.isArray(review?.proposals))throw new Error('Complete authenticated AGO GitHub evidence unavailable');
   const all=await Promise.all(catalog.github_projects.slice(0,20).map(async row=>{
    const record=row.payload||row;
    if(!record?.id||!record?.repository)return null;
    try{
     const status=await api.request('/v1/platform/github/projects/'+encodeURIComponent(record.id)+'/status');
     return {id:record.id,repository:record.repository,status};
    }catch{return {id:record.id,repository:record.repository,status:null};}
   }));
   setProjects(all.filter(Boolean));setOperations(catalog.github_operations);
   setProposals(review.proposals);setError('');setFailure(null);
  }catch(e){setProjects(null);setOperations([]);setProposals([]);setFailure(e);
   setError('Live GitHub delivery evidence is unavailable. '+(e.message||'Check access or connectivity'));}
 },[api,founder]);
 useEffect(()=>{if(!founder)return;
  let on=true;
  const check=()=>{if(on)refresh();};
  check();const timer=setInterval(check,45000);
  return()=>{on=false;clearInterval(timer);};
 },[founder,refresh]);
 if(!founder)return null;
 // First click only asks; the write needs a second, explicit confirmation of
 // this exact operation on this exact repository.
 function request(step,project,entry,label){
  if(busy)return;
  setError('');setFailure(null);setNotice('');
  setPending({key:step+':'+entry.operation?.id,step,project,entry,label});
 }
 async function act(step,project,entry,confirmed){
  if(busy||!project?.status||project.status.repository_private!==true||
     project.status.project_id!==project.id||
     project.status.repository!=='rudrasinha05/'+project.repository)return;
  const op=entry.operation;
  const proposal=entry.proposal;
  const row=entry.row;
  const key=step+':'+op.id;
  if(confirmed!==key){setError('Confirm this exact step first. Nothing was sent.');return;}
  if(used.current.has(key)){setError('This action was already attempted in this browser session. Inspect AGO before any retry.');return;}
  if(!proposal||proposal.status!=='approved'||proposal.actor_id!==me.id||
     proposal.command!=='github_operation'||!sameRecord(proposal.specification,op)||
     (step==='apply'?entry.applied:!row?.eligibleExecute)){
    setError('Original Founder proposal, independent approval or current private GitHub state is missing.');return;
  }
  if(step==='execute'&&op.operation==='create_pull_request'&&
      !verifiedGitHubChecks(project.status,op.payload?.required_checks)){
   setError('Required real GitHub CI is incomplete or ambiguous. PR blocked.');return;
  }
  used.current.add(key);setBusy(key);setError('');setFailure(null);setNotice('');setPending(null);
  try{
   if(step==='apply'){
    await api.request('/v1/enterprise/reviews/integration/apply',
     {method:'POST',body:{proposal_id:proposal.id}});
    setNotice('Approved operation recorded in AGO. No GitHub write occurred.');
   }else{
    const result=await api.request('/v1/platform/github/operations/'+encodeURIComponent(op.id)+'/execute',
     {method:'POST',body:{},timeoutMs:30000});
    setNotice(result.status==='succeeded'?
     'AGO server recorded a GitHub dispatch. Verify the live receipt below.':
     'Dispatch outcome is not confirmed. Inspect the recorded marker before any further action.');
   }
  }catch(e){setFailure(e);setError('Outcome may be uncertain. No automatic retry: '+(e.message||'Inspect AGO dispatch and GitHub receipts.'));}
  finally{setBusy('');await refresh();}
 }
 const cards=(projects||[]).map(project=>{
  const {rows,health,blocker}=githubDeliveryRows(project,operations,proposals);
  const approved=(proposals||[]).filter(p=>p.command==='github_operation'&&
   p.specification?.project_id===project.id&&p.status==='approved'&&p.actor_id===me.id);
  const appliedIds=new Set((operations||[]).filter(x=>x.kind==='github_operation').map(x=>x.payload?.id));
  const needApply=approved.filter(p=>!appliedIds.has(p.specification?.id));
  return {project,rows,health,blocker,needApply};
 });
 return <section id="ago-github-delivery" className="company-github-desk" aria-label="Verified project delivery and GitHub approvals">
  <header><div><h3>Project Delivery Center</h3>
   <p>One Founder dashboard for approved code delivery, CI and draft Pull Requests. No invented AI work or auto-merge.</p></div>
   <button type="button" disabled={Boolean(busy)} onClick={refresh}>Refresh live records</button></header>
  {projects===null?<><p role="alert">GitHub delivery cannot be verified. {error||'Signed project status is unavailable.'}</p><RecoveryHint error={failure}/></>:
   !cards.length?<p>No approved GitHub project is linked. Connect a private repository through reviewed AGO governance first.</p>:
   cards.map(({project,rows,health,blocker,needApply})=><article className="company-github-project" key={project.id}>
    <h4>{project.repository}</h4>
    <p>{health==='verified'?'Private repository verified':'Delivery blocked'} · develop: {project.status?.develop_sha?.slice(0,12)||'unavailable'}</p>
    {blocker&&<small role="status">{blocker}</small>}
    {needApply.map(proposal=><div className="github-delivery-operation" key={proposal.id}>
      <b>Independent approval recorded · awaiting Founder apply</b>
      <small>{proposal.specification?.operation==='create_pull_request'?'Review-only draft Pull Request':proposal.specification?.operation==='commit_files'?'AI-generated code commit':'GitHub operation'}</small>
      <Steps row={{awaitingApply:true}} label={project.repository}/>
      <button type="button" disabled={Boolean(busy)||health!=='verified'} onClick={()=>request('apply',project,{
       operation:proposal.specification,proposal,applied:false},'Record the approved operation in AGO for '+project.repository+'. This does not write to GitHub.')}>
       Apply approved operation in AGO (no GitHub write)
      </button>
    </div>)}
    {rows.map(row=>{
      const entry=(operations||[]).find(x=>x.payload?.id===row.id);
      const proposal=(proposals||[]).find(x=>x.command==='github_operation'&&x.specification?.id===row.id&&sameRecord(x.specification,entry?.payload));
      return <div key={row.id} className="github-delivery-operation">
       <strong>{row.label}</strong>
       <Steps row={row} label={row.label}/>
       <small>Approval: {row.approved?'independently approved':'not independently approved'} · GitHub: {row.dispatch.replaceAll('_',' ')}</small>
       {row.committed&&<small>Verified commit: <code>{row.commitSha}</code></small>}
       {row.prUrl&&<a href={row.prUrl} target="_blank" rel="noreferrer">Open verified draft PR ↗</a>}
       {row.blocker&&<small>{row.blocker}</small>}
       {row.eligibleExecute&&<button type="button" disabled={Boolean(busy)} onClick={()=>request('execute',project,{
        operation:entry.payload,proposal,row,applied:true},
        'Send the approved '+(row.type==='commit_files'?'commit':'draft Pull Request')+' to GitHub repository '+project.repository+
        ' at develop '+(project.status?.develop_sha?.slice(0,12)||'unknown')+'. This writes to GitHub and is not retried automatically.')}>Execute approved GitHub {row.type==='commit_files'?'commit':'draft PR'}</button>}
      </div>;
    })}
   </article>)}
  {pending&&<div className="company-github-confirm" role="group" aria-label="Confirm this delivery step">
    <p><strong>Please confirm:</strong> {pending.label}</p>
    <small>A separate independent human already approved this. The server re-checks permissions, the exact repository, GitHub HEAD and required CI.</small>
    <div className="delivery-actions">
     <button type="button" disabled={Boolean(busy)} onClick={()=>act(pending.step,pending.project,pending.entry,pending.key)}>Yes, confirm this step</button>
     <button type="button" disabled={Boolean(busy)} onClick={()=>setPending(null)}>Cancel</button>
    </div>
   </div>}
  {notice&&<p role="status">{notice}</p>}
  {error&&projects!==null&&<p role="alert">{error}</p>}
  <RecoveryHint error={failure}/>
  <p className="company-github-footnote">The private-source export and independent QA evidence are separate prerequisites. This dashboard does not mark a product released or run unseen AI code.</p>
 </section>;
}
