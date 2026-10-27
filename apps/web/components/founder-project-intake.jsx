"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {CompanyDocumentVault} from './company-document-vault';
import {ProjectStageRouting} from './project-stage-routing';

export function FounderProjectIntake({api,me,employees=[],profiles=[],onChanged}) {
 const [brief,setBrief]=useState('');
 const [projects,setProjects]=useState(null);
 const [projectDetail,setProjectDetail]=useState(null),[selectedProject,setSelectedProject]=useState(null);
 const [moreBusy,setMoreBusy]=useState(false),[hasMore,setHasMore]=useState(false),[projectError,setProjectError]=useState('');
 const [created,setCreated]=useState(null);
 const [busy,setBusy]=useState(false),[reviewBusy,setReviewBusy]=useState(false),[error,setError]=useState('');
 const [ceoBusy,setCeoBusy]=useState(false),[ceoNotice,setCeoNotice]=useState('');
 const retry=useRef(null);
 const isFounder=me.roles?.includes('founder')&&me.permissions?.includes('brain:manage');
 const refresh=useCallback(async()=>{
   try {const batch=await api.request('/v1/organization/company/projects?limit=50&offset=0');setProjects(batch);setHasMore(batch.length===50);} catch {setProjects(null);setHasMore(false);}
 },[api]);
 useEffect(()=>{if(isFounder)refresh();},[refresh,isFounder]);
 // While a just-created plan waits for a decision taken elsewhere (Approvals
 // tab), keep its status live instead of showing the stale creation state.
 const PLAN_ORDER=['draft','pending_approval','approved','active','rejected','cancelled','completed'];
 const liveCreated=created?projects?.find(p=>p.id===created.id):null;
 const createdStatus=created?[created.plan_status,liveCreated?.plan_status].filter(Boolean)
   .sort((a,b)=>PLAN_ORDER.indexOf(b)-PLAN_ORDER.indexOf(a))[0]:null;
 useEffect(()=>{
  if(!isFounder||!created||!['draft','pending_approval'].includes(createdStatus))return undefined;
  const timer=setInterval(refresh,10000);return()=>clearInterval(timer);
 },[isFounder,created,createdStatus,refresh]);
 async function loadMore(){
  if(moreBusy||!hasMore||!projects)return;setMoreBusy(true);setProjectError('');
  try{const batch=await api.request('/v1/organization/company/projects?limit=50&offset='+projects.length);
    setProjects(old=>[...(old||[]),...batch]);setHasMore(batch.length===50);
  }catch(e){setProjectError(e.message||'Could not fetch project page.');}finally{setMoreBusy(false);}
 }
 async function inspectProject(project){
  if(selectedProject===project.id){setSelectedProject(null);setProjectDetail(null);return;}
  setSelectedProject(project.id);setProjectDetail(null);setProjectError('');
  try{const result=await api.request('/v1/organization/company/projects/'+encodeURIComponent(project.id));setProjectDetail(result);}
  catch(e){setProjectError(e.message||'Project details are unavailable.');}
 }
 async function resumeCeo(){
  if(!projectDetail||ceoBusy||projectDetail.plan_status!=='active')return;
  setCeoBusy(true);setProjectError('');setCeoNotice('');
  let requested=0;
  try{
   for(const stage of projectDetail.stages||[]){
    if(stage.task_id&&stage.task_status==='proposed'&&
      ['internal:brief','research:brief','project:plan'].includes(stage.task_action)){
     await api.request('/v1/console/tasks/'+encodeURIComponent(stage.task_id)+'/request-approval',{method:'POST'});
     requested++;
    }
   }
   const result=await api.request('/v1/organization/company/projects/'+encodeURIComponent(projectDetail.id)+'/ceo/reconcile',{method:'POST'});
   setCeoNotice('CEO '+result.ceo_name+' verified '+result.verified_task_count+
     ' internal task(s). '+requested+' new approval requests. No execution or external action started.');
   setProjectDetail(await api.request('/v1/organization/company/projects/'+encodeURIComponent(projectDetail.id)));
   await onChanged?.();
  }catch(e){
   setProjectError('CEO handoff incomplete after '+requested+' requests: '+(e.message||'Blocked')+
    '. Inspect CEO appointment and approval state; do not reapprove Founder scope.');
  }finally{setCeoBusy(false);}
 }
 function exportEngineeringCandidate(run){
  if(!run?.board_review_cleared||!run.engineering_candidate)return;
  // Portable receipt for the local CLI. Preserve exact source bytes and hashes.
  // A download does not execute files, submit a GitHub change or pass QA.
  const portable={result:{
    board_review_cleared:true,
    engineering_candidate:run.engineering_candidate,
  }};
  const blob=new Blob([JSON.stringify(portable,null,2)],{type:'application/json;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;
  link.download='ago-engineering-'+run.engineering_candidate.candidate_sha256.slice(0,16)+'.json';
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 function exportProjectReport(){
  if(!projectDetail)return;
  const p=projectDetail;
  const lines=[
    '# Project evidence report: '+p.title,
    '',
    'Generated from the founder-authorized AGO project record. Nothing below proves public release.',
    '',
    'Project ID: '+p.id,
    'Plan: '+p.plan_status,
    'Recorded status: '+p.status_label,
    'Delivery health: '+p.project_health,
    'Stage QA coverage: '+p.qa_passed_stages+'/'+p.stage_count,
    'Responsible manager: '+p.accountable_manager_name,
    'Commercial stage: '+p.commercial_stage,
    'Verified recorded revenue: '+(p.verified_revenue_inr===null?'Not verified':'INR '+p.verified_revenue_inr),
    '',
    '## Founder requirement','',p.brief,'',
    '## Governed stage and QA evidence','',
    ...(p.stages||[]).flatMap(x=>[
      '### '+x.position+'. '+x.stage,
      x.deliverable,
      'Suggested employee: '+(x.suggested_assignee_name||'Not assigned'),
      'Authorized stage employee: '+(x.approved_assignee_name||'Not delegated'),
      'Executing employee: '+(x.executing_employee||'None'),
      'Task: '+(x.task_id||'Not materialized')+' | Status: '+(x.task_status||'Not started'),
      'Agent run: '+(x.agent_run_status||'No run')+' | Failure code: '+(x.agent_failure_code||'None'),
      'CEO-led QA evidence: '+(x.qa_verdict||'Not reviewed'),
      'QA evidence: '+(x.qa_evidence||'Not attached'),
      ''
    ]),
    '## Acceptance gates','',
    'Verified QA evidence must pass for actual implementation deliverables.',
    'Release and financial evidence must be verified separately.',
  ];
  const blob=new Blob([lines.join('\n')],{type:'text/markdown;charset=utf-8'});
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download='ago-project-'+p.id+'.md';
  document.body.appendChild(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
 }
 if(!isFounder)return null;
 async function start(e){e.preventDefault();if(busy||brief.trim().length<20)return;
  setBusy(true);setError('');
  if(!retry.current||retry.current.brief!==brief.trim())retry.current={brief:brief.trim(),key:crypto.randomUUID()};
  try {
    const response=await api.request('/v1/organization/company/projects/start',
      {method:'POST',body:{brief:retry.current.brief,operation_key:retry.current.key}});
    setCreated(response);setBrief('');retry.current=null;await refresh();onChanged?.();
  } catch(err){setError(err.message);}finally{setBusy(false);}
 }
 async function submitForReview(){
  if(!created||reviewBusy||created.plan_status!=='draft')return;
  setReviewBusy(true);setError('');
  try{const response=await api.request('/v1/brain/plans/'+encodeURIComponent(created.plan_id)+'/submit',{method:'POST'});
    setCreated(old=>({...old,plan_status:response.status,approval_id:response.approval_id}));
    await refresh();onChanged?.();
  }catch(e){setError(e.message);}finally{setReviewBusy(false);}
 }
  return <section className="founder-project-intake" aria-label="Start founder project">
  <div><h3>Start a governed project</h3>
    <p>Founder → Company Brain → accountable executive (CEO/COO/CTO/manager if actually configured; otherwise founder escalation) → suggested team. Higher management owns delivery, workers own execution. Approve/Deny is reserved for the founder; CEO-led QA remains a separate check.</p></div>
  <form onSubmit={start}>
    <label>Founder project brief<textarea value={brief} onChange={e=>setBrief(e.target.value)}
      minLength={20} maxLength={12000} required
      placeholder="What should the company build? Who uses it, what must it deliver, and what would success look like?"/></label>
    <button disabled={busy||brief.trim().length<20}>{busy?'Preparing draft…':'Prepare project from brief'}</button>
  </form>
  {error&&<p role="alert">{error}</p>}
  {created&&<div aria-live="polite"><strong>{created.title}</strong>
    <p><b>Accountable delivery owner:</b> {created.accountable_manager_name} ({created.accountable_manager_role||'Founder authority'}) · {created.assignment_source==='founder_escalation'?'Management staffing escalation':'Recorded executive management responsibility'}</p>
    <p><b>Commercial goal:</b> {created.commercial_objective} · {created.commercial_stage} · No verified revenue evidence yet</p>
    <p>{createdStatus==='draft'?'Draft saved · Founder approval needed'
      :createdStatus==='pending_approval'?'Submitted · waiting for the Founder decision in Approvals'
      :createdStatus==='rejected'?'Founder rejected this plan'
      :['approved','active'].includes(createdStatus)?'Founder approved · CEO handoff and execution stay separate steps (Project portfolio)'
      :'Plan status: '+createdStatus} · No unapproved code or external GitHub action started.</p>
    <ol className="intake-stage-list">{created.stages.map(s=><li key={s.stage}>
      <strong>{s.position}. {s.stage}</strong><small>{s.deliverable}</small>
      <span>{s.suggested_assignee_name||'Staffing required'}</span>
      <small>{s.plan_step_id?'Allowlisted internal review step drafted':'Proposal only; tooling and approval required'}</small>
    </li>)}</ol>
    <p>Plan ID: <code>{created.plan_id}</code> · Status: {createdStatus} · Founder approval is required before materialization. <a href="#company-approval-inbox">View approval inbox ↑</a></p>
    {createdStatus==='draft'&&created.stages.some(s=>s.plan_step_id)&&
      <button type="button" disabled={reviewBusy} onClick={submitForReview}>{reviewBusy?'Submitting…':'Submit plan for founder approval'}</button>}
    {createdStatus==='draft'&&!created.stages.some(s=>s.plan_step_id)&&
      <p>Assign a qualified discovery AI employee before submitting this draft for approval.</p>}
  </div>}
  <div id="ago-project-portfolio" className="founder-project-portfolio">
   <h3>All company projects · Recent founder projects</h3>
   <p>Click any project to inspect full brief, current plan, assigned specialists, task state, CEO-led QA and commercial evidence. A project with no verified release is under process, not automatically complete.</p>
   {projects===null?<small>Project history unavailable</small>:!projects.length?<small>No approved or draft founder projects recorded yet.</small>:
    <div className="project-portfolio-grid">{projects.map(p=><article key={p.id} className="project-portfolio-card">
      <button type="button" className="project-portfolio-open" aria-expanded={selectedProject===p.id} onClick={()=>inspectProject(p)}>
       <strong>{p.title}</strong><small>Plan: {p.plan_status} · {p.staffing_gaps} staffing gaps</small>
       <small>Executive: {p.accountable_manager_name||'Unassigned'} · {p.assignment_source==='founder_escalation'?'Escalated':'Accountable manager'}</small>
       <small>Commercial: {p.commercial_stage} · Revenue: {p.verified_revenue_inr===null?'Not verified':'₹'+p.verified_revenue_inr}</small>
       <span>{selectedProject===p.id?'Collapse details ↑':'Inspect full project →'}</span>
      </button>
      {selectedProject===p.id&&
       <div className="project-portfolio-details">
        {!projectDetail?<p>Loading live project details…</p>:<>
         <h4>{projectDetail.title}</h4>
         <p><b>Status:</b> {projectDetail.status_label} · <b>Strategy:</b> {projectDetail.plan_status} · <b>Delivery health:</b> {projectDetail.project_health}</p>
         {projectDetail.plan_status==='active'&&<div className="project-ceo-handoff">
          <button type="button" disabled={ceoBusy} onClick={resumeCeo}>
           {ceoBusy?'Checking the approved scope…':'Resume CEO verification (no new Founder approval)'}
          </button>
          {ceoNotice&&<p role="status">{ceoNotice}</p>}
         </div>}
         <p><b>Evidence-backed QA completion:</b> {projectDetail.qa_passed_stages}/{projectDetail.stage_count} stages · {projectDetail.completion_percent}% · {projectDetail.running_stages} running · {projectDetail.failed_stages} failed · {projectDetail.unassigned_stages} staffing gaps.</p>
         <p><b>Reviewed workforce assignments:</b> {projectDetail.reviewed_delegations_count??0}/{projectDetail.stage_count}. Suggestions are not approved assignments; assignments do not execute tasks.</p>
         <button type="button" onClick={exportProjectReport}>Export current evidence report (.md)</button>
         <p><b>Founder requirement:</b> {projectDetail.brief}</p>
         <p><b>Accountable manager:</b> {projectDetail.accountable_manager_name}</p>
         <p><b>Revenue plan:</b> {projectDetail.commercial_objective} · {projectDetail.commercial_stage}</p>
         <p><b>Actual income evidence:</b> {projectDetail.revenue_record_status==='no_verified_evidence'?'Not recorded':'₹'+projectDetail.verified_revenue_inr}</p>
         <ol className="intake-stage-list">{(projectDetail.stages||[]).map(st=><li key={st.stage}>
          <strong>{st.position}. {st.stage}</strong>
          <small>{st.deliverable}</small>
          <small>Suggested: {st.suggested_assignee_name||'Employee needed'} · Executing: {st.executing_employee||'No governed task started'}</small>
          <small>Task: {st.task_status||'not materialized'} · QA: {st.qa_verdict||'no QA verdict'}</small>
          <small>Delegated stage worker: {st.approved_assignee_name||'Awaiting authorized personnel decision'} {st.delegated_at?'· applied '+new Date(st.delegated_at).toLocaleString():''}</small>
          <small>AI execution: {st.agent_run_status||'no recorded run'} {st.agent_failure_code?'· Failure: '+st.agent_failure_code:''}</small>
          {st.founder_agent_result?.kind==='local_company_governed_handoff'&&
           <details className="ago-ai-chain">
            <summary>Ollama Board → PM → employee · {st.founder_agent_result.roles_completed}/{st.founder_agent_result.roles_expected||4} recorded AI passes · Quality verification pending</summary>
            <p>Board recommendations (nonbinding): {(st.founder_agent_result.board_recommendations||[]).map(v=>v.seat+': '+v.recommendation.toUpperCase()).join(' · ')||'No verified Board recommendation recorded'} — Founder makes the actual decision.</p>
            {st.founder_agent_result.board_blocked&&<p role="status"><strong>Board {st.founder_agent_result.board_block_reason==='unverified'?'decision unverified':'objection recorded'} — internal handoff paused after {st.founder_agent_result.blocked_by_board_seat||'Board'}.</strong> Downstream AI roles did not execute in this run. Founder must examine the objection and authorize an appropriately reviewed next action; this is not an automatic project rejection or release.</p>}
            {st.founder_agent_result.board_review_mode==='full_five_seat'&&<p>Five-seat governance review: {st.founder_agent_result.board_review_cleared?'All five AI Board recommendations recorded APPROVE; founder authority and CEO-led QA are still required.':'Board review incomplete or stopped — never an automatic approval.'}</p>}
            {st.founder_agent_result.engineering_candidate&&<section className="ago-engineering-review" aria-label="Uncommitted engineering candidate">
              <h5>Generated source candidate — not built, tested or committed</h5>
              <button type="button" onClick={()=>exportEngineeringCandidate(st.founder_agent_result)}>Export exact files for local Founder review</button>
              <p>Proposal checksum: <code>{st.founder_agent_result.engineering_candidate.candidate_sha256}</code></p>
              <ul>{st.founder_agent_result.engineering_candidate.file_evidence.map(f=><li key={f.path}><code>{f.path}</code> · {f.bytes} bytes · syntax {f.python_syntax_checked?'checked':'not checked'} · <code>{f.sha256.slice(0,12)}</code></li>)}</ul>
              <p>Founder must inspect source, run verified tests and approve a separate GitHub operation. No auto-commit.</p>
            </section>}
            <ol>{(st.founder_agent_result.handoffs||[]).map(h=><li key={h.role}>
              <strong>{h.role.toUpperCase()} · {h.employee_name}</strong>
              <small>Employee record: {h.employee_id} · {h.human_qa_approved?'QA passed':'CEO quality verification required'}</small>
              <p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{h.draft}</p>
             </li>)}</ol>
            <p>These are AI-generated review drafts, not executed GitHub changes or a published release.</p>
           </details>}
          {st.qa_evidence&&<details><summary>QA evidence</summary><p>{st.qa_evidence}</p></details>}
         </li>)}</ol>
         <ProjectStageRouting api={api} project={projectDetail} employees={employees} profiles={profiles} onUpdated={onChanged}/>
          <CompanyDocumentVault api={api} project={projectDetail}/>
         <p>No external publication is claimed without a linked verified release. {me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read')&&<a href="#ago-opportunities">Promotion desk ↑</a>}</p>
        </>}
       </div>}
     </article>)}</div>}
   {hasMore&&<button type="button" disabled={moreBusy} onClick={loadMore}>{moreBusy?'Loading…':'Load more projects'}</button>}
   {projectError&&<p role="alert">{projectError}</p>}
  </div>
 </section>;
}
