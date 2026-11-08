import test from 'node:test';
import assert from 'node:assert/strict';
import {canReadDelivery,deliveryEvidence,deliveryPage,founderDecisions,projectTaskIds,reviewedStages} from '../apps/web/components/founder-delivery-state.js';
const project=()=>({project_id:'p1',title:'Recorded project',delivery_state:'working',stages:[{stage:'discovery',task_id:'t1',task_status:'completed',qa_verdict:null}],pending_approvals:[]});
const page=()=>({kind:'ago_founder_delivery_overview_v1',read_only:true,projects:[project()],more_projects_possible:false});
test('overview needs every signed read permission and Founder presentation role',()=>{
 const me={roles:['founder'],permissions:['organization:read','brain:read','approval:read']};
 assert.equal(canReadDelivery(me),true);
 for(const p of me.permissions)assert.equal(canReadDelivery({...me,permissions:me.permissions.filter(x=>x!==p)}),false);
 assert.equal(canReadDelivery({...me,roles:['reviewer']}),false);
});
test('missing, malformed, duplicate or unknown records fail closed',()=>{
 for(const bad of [null,[],{}, {...page(),read_only:false},{...page(),projects:[project(),project()]},
  {...page(),projects:[{...project(),delivery_state:'released'}]},
  {...page(),projects:[{...project(),stages:null}]},
  {...page(),projects:[{...project(),manager:{name:'untrusted'}}]},
  {...page(),projects:[{...project(),stages:[{stage:'work',employee:{name:'wrong shape'},qa_verdict:null}]}]},
  {...page(),projects:[{...project(),stages:[{stage:'work',qa_verdict:'unknown'}]}]},
  {...page(),projects:[{...project(),pending_approvals:[{}]}]}])assert.throws(()=>deliveryPage(bad));
 assert.equal(deliveryPage(page()).projects.length,1);
});
test('completed execution is not passed QA; scope only includes exact recorded tasks',()=>{
 const p=project();assert.equal(reviewedStages(p),0);
 p.stages.push({stage:'quality',task_id:'t1',task_status:'completed',qa_verdict:'pass'},
  {stage:'release',task_id:null,task_status:null,qa_verdict:null});
 assert.deepEqual(projectTaskIds(p),['t1']);assert.equal(reviewedStages(p),1);
 assert.equal(p.release_ready,undefined);
});
test('only server-marked Founder decisions are actionable; evidence needs exact true',()=>{
 const p={...project(),pending_approvals:[{approval_id:'a1',type:'plan_review',requires_founder_decision:true},
  {approval_id:'a2',type:'task_execution',requires_founder_decision:false},{approval_id:'a3',requires_founder_decision:'true'}],
  docker_qa_verified:'true',github_commit_verified:true,draft_pr_verified:1};
 assert.deepEqual(founderDecisions(p),[{approval_id:'a1',label:'Approve the project plan'}]);
 assert.deepEqual(deliveryEvidence(p).filter(e=>e.verified).map(e=>e.key),['commit']);
 assert.deepEqual(deliveryEvidence(project()).filter(e=>e.verified),[]);
});
test('recovery guidance explains the recorded failure and never invents an outcome',async()=>{
 const {recoveryHint}=await import('../apps/web/components/recovery.js');
 const err=(status,message='x')=>Object.assign(new Error(message),{status});
 assert.equal(recoveryHint(null),null);
 assert.equal(recoveryHint(new Error('Incomplete project delivery record.')),null,'A validation error has no guessed cause');
 assert.match(recoveryHint(err(401)).what,/sign-in has expired/);
 assert.match(recoveryHint(err(403)).next,/does not skip these checks/);
 assert.doesNotMatch(recoveryHint(err(403)).what,/account is not allowed/,'403 may be a setup rule, not only a role');
 assert.match(recoveryHint(err(409)).next,/does not repeat/);
 for(const e of [err(503),err(0,'Request timed out'),new TypeError('Failed to fetch')])
  assert.match(recoveryHint(e).next,/may already have done it/,'Unknown outcome must warn before retry');
});
test('a real Founder /me (approval:founder is identity-derived, never listed) can read the overview',()=>{
 // Shape returned by the live server for an active human Founder.
 assert.equal(canReadDelivery({roles:['founder'],permissions:['organization:read','brain:read','approval:read','approval:decide']}),true);
 assert.equal(canReadDelivery({roles:['reviewer'],permissions:['organization:read','brain:read','approval:read','approval:founder']}),false);
});
test('an approved task waiting to be run is labelled from recorded approval state only',async()=>{
 const {taskApprovalStates,stageTaskLabel}=await import('../apps/web/components/founder-delivery-state.js');
 const states=taskApprovalStates([
  {task_id:'t1',status:'pending',created_at:'2026-10-20T00:00:00Z'},
  {task_id:'t1',status:'approved',created_at:'2026-10-25T00:00:00Z'},
  {task_id:'t2',status:'rejected',created_at:'2026-10-25T00:00:00Z'},
  {task_id:null,status:'approved'},{status:'approved'},null]);
 const wait=id=>({task_id:id,task_status:'waiting_approval'});
 assert.match(stageTaskLabel(wait('t1'),states),/^Approved — ready to run/);
 assert.match(stageTaskLabel(wait('t2'),states),/^Approval rejected/);
 assert.equal(stageTaskLabel(wait('t3'),states),'Waiting for approval','No record => not approved');
 assert.equal(stageTaskLabel(wait('t1'),null),'Waiting for approval','Inbox unavailable => not approved');
 // A server-provided field wins over the inbox.
 assert.equal(stageTaskLabel({...wait('t1'),task_approval_status:'pending'},states),'Waiting for approval');
 assert.match(stageTaskLabel({...wait('t3'),task_approval_status:'approved'},states),/^Approved/);
 // Only waiting tasks are relabelled; other states keep their meaning.
 assert.equal(stageTaskLabel({task_id:'t1',task_status:'running'},states),'Running');
 assert.equal(stageTaskLabel({task_status:null},states),'not created');
});
test('self-check explains every blocker with who fixes it and never invents readiness',async()=>{
 const {selfCheck}=await import('../apps/web/components/task-self-check-state.js');
 const base={kind:'ago_founder_engineering_preflight_v1',blocking_checks:[],unverified_execution_gates:['local_ollama_response','virtual_credit_budget'],assigned_role_names:['ceo','cto','pm','employee']};
 const ok=selfCheck(base);
 assert.equal(ok.ready,true);assert.deepEqual(ok.laterGates,['local Ollama model','budget']);
 const live=selfCheck({...base,blocking_checks:['board_pm_or_worker_not_ai','board_pm_or_worker_not_ai','brand_new_check']});
 assert.equal(live.ready,false);assert.equal(live.blockers.length,2,'duplicates collapse');
 assert.match(live.blockers[0].what,/not an AI employee/);assert.match(live.blockers[0].fix,/issue #9/);
 assert.match(live.blockers[1].what,/brand_new_check/,'unknown codes stay visible, never hidden');
 const repair=selfCheck({...base,blocking_checks:['worker_pm_reporting_path_missing'],reporting_repair_evidence:{worker_name:'AI Engineer',worker_manager_name:'AGO AI CEO',accountable_pm_name:'Project Manager'}});
 assert.equal(repair.repair,'AI Engineer reports to AGO AI CEO; it must report to project manager Project Manager.');
 for(const bad of [null,{},{kind:'other',blocking_checks:[]},{kind:base.kind}])assert.throws(()=>selfCheck(bad));
});
test('credit balance is read strictly and a low balance becomes a visible blocker',async()=>{
 const {creditBalance,creditBlocker,selfCheck}=await import('../apps/web/components/task-self-check-state.js');
 // The live Founder data: no allowance configured.
 assert.deepEqual(creditBalance({virtual_credit_budget:{ceiling:'0',consumed:'0',remaining:'0'}}),{ceiling:0,consumed:0,remaining:0});
 for(const bad of [null,{},{virtual_credit_budget:{ceiling:'x',consumed:'0',remaining:'0'}},{virtual_credit_budget:{ceiling:'-1',consumed:'0',remaining:'0'}}])
  assert.equal(creditBalance(bad),null);
 const ok=selfCheck({kind:'ago_founder_engineering_preflight_v1',blocking_checks:[]});
 assert.equal(creditBlocker(ok,{ceiling:0,consumed:0,remaining:0}).ready,false);
 assert.match(creditBlocker(ok,{remaining:0}).blockers[0].what,/0 left/);
 assert.equal(creditBlocker(ok,{remaining:7}).ready,true);
 assert.equal(creditBlocker(ok,null).ready,true,'unknown balance adds no invented blocker');
 assert.equal(creditBlocker(ok,undefined),ok);
});
test('failure reasons are plain text and only failed linked stages are recoverable',async()=>{
 const {failureReason,recoverableStage}=await import('../apps/web/components/founder-delivery-state.js');
 assert.match(failureReason('credit_budget_missing'),/credit allowance/);
 assert.match(failureReason('model_unreachable'),/Ollama/);
 assert.equal(failureReason('new_code'),'Recorded failure code: new_code');
 assert.equal(failureReason(null),null);
 assert.equal(recoverableStage({stage:'discovery',task_status:'failed',task_id:'t1'}),true);
 for(const s of [{stage:'discovery',task_status:'completed',task_id:'t1'},{stage:'discovery',task_status:'failed',task_id:null},
  {stage:'marketing',task_status:'failed',task_id:'t1'},null])assert.equal(recoverableStage(s),false);
});
test('only a finished, unreviewed stage offers AI QA, and only AI QA-role employees are offered',async()=>{
 const {aiQaReadyStage,aiQaReviewers}=await import('../apps/web/components/founder-delivery-state.js');
 const done={stage:'discovery',task_status:'completed',agent_run_status:'completed',qa_verdict:null,task_id:'t1'};
 assert.equal(aiQaReadyStage(done),true);
 for(const s of [{...done,qa_verdict:'pass'},{...done,qa_verdict:'fail'},{...done,agent_run_status:'failed'},
  {...done,task_status:'running'},{...done,task_id:null},{...done,stage:'marketing'},null])assert.equal(aiQaReadyStage(s),false);
 const people=[{id:'a',kind:'ai',role_title:'QA Engineer'},{id:'b',kind:'ai',role_title:'Quality Lead'},
  {id:'c',kind:'human',role_title:'QA Engineer'},{id:'d',kind:'ai',role_title:'Content Writer'},
  {id:'e',kind:'ai',role_title:'Software Tester'},{id:'f',kind:'ai',role_title:'QA Engineer',status:'terminated'},{kind:'ai',role_title:'QA'}];
 assert.deepEqual(aiQaReviewers(people).map(e=>e.id),['a','b','e']);
 assert.deepEqual(aiQaReviewers(null),[]);
});
test('portfolio rows show live status, team and only verified income; Founder decisions come first',async()=>{
 const {portfolioRows,portfolioCounts,portfolioGroup,projectTeam}=await import('../apps/web/components/project-portfolio-state.js');
 const base={project_id:'p1',title:'Admissions',manager:'Project Manager',plan_status:'active',delivery_state:'working',pending_approvals:[],
  stages:[{stage:'discovery',employee:'AI Engineer',task_status:'running',agent_run_status:'running',qa_verdict:null},
   {stage:'architecture',employee:'AI Engineer',task_status:'completed',agent_run_status:'completed',qa_verdict:'pass'},
   {stage:'implementation',employee:'Project Manager',task_status:'failed',agent_run_status:'failed',qa_verdict:null}]};
 const page={projects:[base,{...base,project_id:'p2',title:'Blocked one',delivery_state:'blocked',stages:[],manager:null},
  {...base,project_id:'p3',title:'Needs me',delivery_state:'blocked',pending_approvals:[{approval_id:'a',requires_founder_decision:true,type:'plan_review'}]}]};
 const rows=portfolioRows(page,[{id:'p1',verified_revenue_inr:5000,commercial_stage:'pilot'},{id:'p2',verified_revenue_inr:'5000'}]);
 assert.deepEqual(rows.map(r=>r.group),['running','blocked','needs_you']);
 assert.deepEqual(rows[0].team,['Project Manager','AI Engineer']);
 assert.deepEqual([rows[0].reviewed,rows[0].stageCount,rows[0].running,rows[0].failed],[1,3,1,1]);
 assert.equal(rows[0].income.verified,true);assert.match(rows[0].income.label,/5,000/);
 assert.equal(rows[1].income.verified,false,'a string is not verified income');
 assert.equal(rows[1].commercial,'Not recorded');assert.deepEqual(rows[1].team,[]);
 assert.equal(rows[2].decisions,1);
 assert.equal(portfolioRows(page,null)[0].income.label,'No verified income yet');
 const counts=portfolioCounts(rows);
 assert.deepEqual([counts.all,counts.running,counts.blocked,counts.needs_you,counts.done],[3,1,1,1,0]);
 assert.equal(portfolioGroup({...base,delivery_state:'internally_reviewed',stages:[]}),'done');
 assert.equal(portfolioGroup({...base,delivery_state:'awaiting_governed_execution',stages:[]}),'waiting');
 assert.deepEqual(projectTeam({manager:' ',stages:[{employee:null}]}),[]);
});
test('the AI hierarchy notice names each recorded approver and its level',async()=>{
 const {hierarchyApprovalLine}=await import('../apps/web/components/company-founder-decision.js');
 const line=hierarchyApprovalLine({task_approvers:[{task_id:'t',approver_name:'Mira',approver_level:'manager'},
  {task_id:'u',approver_name:'Ceo',approver_level:'ceo'},{approver_name:'Fake',approver_level:'board'}],blocked_task_ids:['x']});
 assert.match(line,/Mira \(direct manager\), Ceo \(AI CEO\)\./);
 assert.doesNotMatch(line,/Fake/);
 assert.match(line,/1 task\(s\) could not be approved by the AI team; they wait for the Founder\./);
 assert.match(hierarchyApprovalLine({}),/^No task needed an AI approval right now\. No work was run/);
});
test('a QA FAIL on a finished stage is recoverable as rework; a PASS or no verdict is not',async()=>{
 const {recoverableStage,qaReworkStage,aiQaReadyStage}=await import('../apps/web/components/founder-delivery-state.js');
 const done={stage:'discovery',task_status:'completed',agent_run_status:'completed',task_id:'t1'};
 assert.equal(qaReworkStage({...done,qa_verdict:'fail'}),true);
 assert.equal(recoverableStage({...done,qa_verdict:'fail'}),true);
 assert.equal(aiQaReadyStage({...done,qa_verdict:'fail'}),false);
 for(const v of ['pass',null,undefined])assert.equal(recoverableStage({...done,qa_verdict:v}),false);
 assert.equal(recoverableStage({...done,task_status:'failed',qa_verdict:null}),true);
});
test('advance picks the one next step from the first stage that has not passed QA',async()=>{
 const {nextAdvanceStep,pickQaReviewer,stepLabel,AUTOMATIC}=await import('../apps/web/components/project-advance-state.js');
 const s=(stage,position,extra)=>({stage,position,task_id:stage+'-task',...extra});
 const pass=s('discovery',1,{task_status:'completed',agent_run_status:'completed',qa_verdict:'pass'});
 const kind=(...stages)=>nextAdvanceStep({stages}).kind;
 assert.equal(kind(s('discovery',1,{task_status:'proposed'})),'request');
 assert.equal(kind(s('discovery',1,{task_status:'waiting_approval',task_approval_status:'pending'})),'approve');
 assert.equal(kind(s('discovery',1,{task_status:'waiting_approval',task_approval_status:'approved'})),'run');
 assert.equal(kind(s('discovery',1,{task_status:'waiting_approval',task_approval_status:'rejected'})),'rejected');
 assert.equal(kind(s('discovery',1,{task_status:'running'})),'running');
 assert.equal(kind(s('discovery',1,{task_status:'completed',agent_run_status:'completed'})),'qa');
 assert.equal(kind(s('discovery',1,{task_status:'completed',agent_run_status:'completed',qa_verdict:'fail'})),'rework');
 assert.equal(kind(s('discovery',1,{task_status:'failed'})),'failed');
 assert.equal(kind(s('discovery',1,{task_id:null})),'unstaffed');
 // Order is by position, and passed stages are skipped.
 const next=nextAdvanceStep({stages:[s('architecture',2,{task_status:'proposed'}),pass]});
 assert.deepEqual([next.kind,next.stage,next.task_id],['request','architecture','architecture-task']);
 assert.equal(kind(pass),'done');
 assert.equal(nextAdvanceStep({stages:[]}).kind,'unstaffed');
 assert.deepEqual([...AUTOMATIC].sort(),['approve','qa','request','retry_code','revise','run']);
 assert.match(stepLabel({kind:'run',stage:'discovery'}),/Run the discovery task with the AI team \(uses 7 internal credits\)/);
 const reviewers=[{id:'w'},{id:'q'}];
 assert.equal(pickQaReviewer(reviewers,{approved_assignee_id:'w'}).id,'q');
 assert.equal(pickQaReviewer([{id:'w'}],{suggested_assignee_id:'w'}),null);
});
test('advance explains a Board block instead of reporting a finished run',async()=>{
 const {runBlocker}=await import('../apps/web/components/project-advance-state.js');
 const live={status:'completed',delivery_status:'blocked',result:{board_blocked:true,blocked_by_board_seat:'Strategy & Vision',
  board_block_reason:'unverified',roles_completed:1,roles_expected:7}};
 assert.match(runBlocker(live),/^The Board stopped the AI team: Strategy & Vision — its AI answer had no single clear/);
 assert.match(runBlocker(live),/\(1 of 7 AI roles ran\)\. The stage is marked failed; recover it to try again\.$/);
 assert.match(runBlocker({...live,result:{...live.result,board_block_reason:'deny'}}),/it recommended DENY/);
 assert.equal(runBlocker({status:'completed',delivery_status:'completed',result:{board_blocked:false}}),null);
 assert.equal(runBlocker({status:'completed'}),null);
 assert.match(runBlocker({status:'failed'}),/^The run ended as failed/);
 assert.match(runBlocker(null),/no recorded result/);
});
test('a failed stage whose AI run completed is explained as a Board stop',async()=>{
 const {stageFailureReason}=await import('../apps/web/components/founder-delivery-state.js');
 assert.match(stageFailureReason({task_status:'failed',agent_run_status:'completed'}),/^The AI Board stopped the work/);
 assert.match(stageFailureReason({task_status:'failed',agent_run_status:'failed',agent_failure_code:'model_timeout'}),/did not answer in time/);
 assert.equal(stageFailureReason({task_status:'failed',agent_run_status:null}),null);
 assert.equal(stageFailureReason({task_status:'completed',agent_run_status:'completed'}),null);
});
test('board votes show who denied and why; only Finance/Risk/Quality after CEO+CTO approve can be allowed',async()=>{
 const {boardDenial}=await import('../apps/web/components/founder-delivery-state.js');
 const {runBlocker}=await import('../apps/web/components/project-advance-state.js');
 const v=(seat,recommendation,denial_reason='')=>({seat,recommendation,denial_reason});
 const result={kind:'local_company_governed_handoff',board_blocked:true,blocked_by_board_seat:'Finance & Budget',board_block_reason:'deny',
  founder_override_available:true,roles_completed:3,roles_expected:7,
  board_recommendations:[v('Strategy & Vision','approve'),v('Technology Oversight','approve'),v('Finance & Budget','deny','No cost estimate.')]};
 const view=boardDenial(result);
 assert.equal(view.stoppedBy,'Finance & Budget');assert.equal(view.overridable,true);
 assert.deepEqual(view.votes.map(x=>[x.seat,x.recommendation,x.reason]),[['Strategy & Vision','approve',''],
  ['Technology Oversight','approve',''],['Finance & Budget','deny','No cost estimate.']]);
 assert.equal(boardDenial({...result,blocked_by_board_seat:'Technology Oversight'}).overridable,false);
 assert.equal(boardDenial({...result,board_recommendations:[v('Strategy & Vision','approve'),v('Technology Oversight','unverified')]}).overridable,false);
 assert.equal(boardDenial({...result,board_blocked:false}),null);
 assert.equal(boardDenial(null),null);
 const line=runBlocker({status:'completed',delivery_status:'blocked',result});
 assert.match(line,/Reason given: “No cost estimate\.”\. The AI CEO and CTO approved, so you can allow the project on the stage card\.$/);
});
test('a Board stop is revised and resubmitted; a crash is not',async()=>{
 const {nextAdvanceStep,revisionReason,AUTOMATIC,MAX_REVISIONS,stepLabel}=await import('../apps/web/components/project-advance-state.js');
 const s=extra=>({stage:'discovery',position:1,task_id:'t',...extra});
 assert.equal(nextAdvanceStep({stages:[s({task_status:'failed',agent_run_status:'completed'})]}).kind,'revise');
 assert.equal(nextAdvanceStep({stages:[s({task_status:'failed',agent_run_status:'failed',agent_failure_code:'model_timeout'})]}).kind,'failed');
 assert.equal(nextAdvanceStep({stages:[s({task_status:'failed',agent_run_status:'completed',agent_failure_code:'handler_error'})]}).kind,'failed');
 assert.ok(AUTOMATIC.has('revise'));assert.equal(MAX_REVISIONS,2);
 assert.equal(revisionReason([{seat:'Strategy & Vision',recommendation:'deny',reason:'Brief lacks the problem it solves.'},
  {seat:'Technology Oversight',recommendation:'approve',reason:''},{seat:'Finance & Budget',recommendation:'unverified',reason:''}]),
  'Revise to fix Board feedback: Strategy & Vision: Brief lacks the problem it solves.; Finance & Budget: gave no clear vote');
 assert.equal(revisionReason(null),'Revise to fix Board feedback: Board did not approve');
 assert.ok(revisionReason([{seat:'X',recommendation:'deny',reason:'r'.repeat(900)}]).length<=500);
 assert.match(stepLabel({kind:'revise_limit',stage:'discovery'}),/after 2 revisions/);
});
test('an invalid code proposal is retried automatically and explained',async()=>{
 const {nextAdvanceStep,AUTOMATIC,stepLabel}=await import('../apps/web/components/project-advance-state.js');
 const {failureReason}=await import('../apps/web/components/founder-delivery-state.js');
 const step=nextAdvanceStep({stages:[{stage:'discovery',position:1,task_id:'t',task_status:'failed',agent_run_status:'failed',agent_failure_code:'engineering_candidate_invalid'}]});
 assert.equal(step.kind,'retry_code');assert.ok(AUTOMATIC.has('retry_code'));
 assert.match(stepLabel(step),/code failed AGO's code check/);
 assert.match(failureReason('engineering_candidate_invalid'),/failed AGO's code check twice/);
});


// Staff assignment never trusts browser name/role matching over the scoped HR receipt.
test('Founder project staffing never uses missing, cross-project or fabricated eligibility',async()=>{
 const {verifiedStaffing,stageCandidates}=await import('../apps/web/components/project-stage-routing-state.js');
 const project={id:'project-one',plan_status:'active',stages:[{stage:'implementation'}]};
 const members=[{id:'e1',name:'Software Developer',kind:'ai'}];
 const trust={kind:'ago_p1_readonly_staffing_proposals',project_id:'project-one',
  is_live_project_evidence:true,requires_founder_review:true,
  personnel_hired:false,permission_granted:false,charter_granted:false,
  source_sha256:'a'.repeat(64),eligible_employee_ids:['e1'],
  proposals:[{stage:'implementation',eligible_candidates:[{employee_id:'e1'}]}]};
 for(const wrong of [null,{}, {...trust,project_id:'other'}, {...trust,personnel_hired:true},
  {...trust,requires_founder_review:false},{...trust,source_sha256:'invalid'},
  {...trust,eligible_employee_ids:null},{...trust,proposals:null}]){
  assert.equal(verifiedStaffing(project,wrong),null);
  assert.deepEqual(stageCandidates(project,project.stages[0],members,[],wrong),[]);
 }
 assert.equal(stageCandidates(project,project.stages[0],members,[],trust)[0].id,'e1');
 assert.deepEqual(stageCandidates(project,project.stages[0],members,[],{
  ...trust,eligible_employee_ids:[],
 }),[]);
});

test('Active Founder stage roster excludes terminated, inappropriate and self-QA workers',async()=>{
 const {stageCandidates,defaultStageCandidate}=await import('../apps/web/components/project-stage-routing-state.js');
 const members=[
  {id:'manager',name:'QA Manager',kind:'ai'},
  {id:'builder',name:'Software Developer',kind:'ai'},
  {id:'qa',name:'Independent QA Engineer',kind:'ai'},
  {id:'inactive',name:'QA Engineer Former',kind:'ai'},
  {id:'human',name:'QA Reviewer',kind:'human'},
 ];
 const project={id:'p1',plan_status:'active',accountable_manager_id:'manager',
  stages:[{stage:'implementation',suggested_assignee_id:'builder'},
          {stage:'quality',suggested_assignee_id:null}]};
 const receipt={kind:'ago_p1_readonly_staffing_proposals',project_id:'p1',
  is_live_project_evidence:true,requires_founder_review:true,
  personnel_hired:false,permission_granted:false,charter_granted:false,
  source_sha256:'b'.repeat(64),
  eligible_employee_ids:['manager','builder','qa','human'],
  proposals:[{stage:'quality',eligible_candidates:[
   {employee_id:'manager'},{employee_id:'builder'},{employee_id:'qa'},
   {employee_id:'inactive'},{employee_id:'human'}]}]};
 const list=stageCandidates(project,project.stages[1],members,[],receipt);
 assert.deepEqual(list.map(x=>x.id),['qa']);
 assert.equal(defaultStageCandidate(project,project.stages[1],members,[],receipt),'qa');
 const formerlySuggested={...project.stages[0],suggested_assignee_id:'inactive'};
 assert.deepEqual(stageCandidates(project,formerlySuggested,members,[],receipt),[]);
 const draft={...project,plan_status:'draft'};
 assert.ok(stageCandidates(draft,draft.stages[1],members,[],null).some(x=>x.id==='qa'));
});
