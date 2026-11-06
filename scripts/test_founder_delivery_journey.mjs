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
 assert.match(recoveryHint(err(403)).next,/does not skip permission/);
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
