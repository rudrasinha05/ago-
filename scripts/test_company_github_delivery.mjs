import assert from 'node:assert/strict';
import test from 'node:test';
import {githubDeliveryRows,sameRecord,verifiedGitHubChecks} from '../apps/web/components/company-github-delivery-state.js';

const uuid=n=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0');
const commit={id:uuid(9),project_id:uuid(1),operation:'commit_files',
 payload:{expected_sha:'a'.repeat(40),message:'Reviewed project code',
 files:[{path:'src/main.py',content:'print("ok")'}]}};
const pr={id:uuid(10),project_id:uuid(1),operation:'create_pull_request',
 payload:{expected_sha:'c'.repeat(40),title:'Review AI project',body:'Human QA',
 required_checks:['Backend QA','Browser QA']}};
const project={id:uuid(1),repository:'private-project',
 status:{project_id:uuid(1),repository:'rudrasinha05/private-project',repository_private:true,
  develop_sha:'a'.repeat(40),operations:[]}};
const proposal=op=>({id:uuid(30),command:'github_operation',operation_key:op.id,
 specification:op,status:'approved',actor_id:uuid(40)});
const stored=op=>({kind:'github_operation',payload:op,proposal_id:uuid(30)});

test('immutably equivalent JSON proposal matches regardless of field order',()=>{
 assert.equal(sameRecord(commit,{payload:{files:commit.payload.files,message:commit.payload.message,
 expected_sha:commit.payload.expected_sha},operation:commit.operation,
 project_id:commit.project_id,id:commit.id}),true);
 assert.equal(sameRecord(commit,{...commit,operation:'create_pull_request'}),false);
});

test('unknown or public provider state is never claimed as delivery',()=>{
 for(const status of [null,undefined,{...project.status,repository_private:false},
  {repository_private:true,operations:null}]){
  const out=githubDeliveryRows({...project,status},[stored(commit)],[proposal(commit)]);
  assert.equal(out.health,'unavailable');
  assert.deepEqual(out.rows,[]);
 }
});

test('cross-project or alternate repository receipts never confer delivery access',()=>{
 for(const status of [
  {...project.status,project_id:uuid(200)},
  {...project.status,repository:'rudrasinha05/unrelated-project'},
  {...project.status,repository:'attacker/private-project'},
 ]){
  const out=githubDeliveryRows({...project,status},[stored(commit)],[proposal(commit)]);
  assert.equal(out.health,'unavailable');
  assert.deepEqual(out.rows,[]);
 }
});

test('unapproved operation has no execution action, missing approval cannot be forged',()=>{
 const out=githubDeliveryRows(project,[stored(commit)],[]);
 assert.equal(out.health,'verified');
 assert.equal(out.rows[0].eligibleExecute,false);
 assert.match(out.rows[0].blocker,/proposal not visible/);
 const bad={...proposal(commit),specification:{...commit,payload:{...commit.payload,message:'changed'}}};
 assert.equal(githubDeliveryRows(project,[stored(commit)],[bad]).rows[0].approved,false);
});

test('exact independent approval and unchanged SHA enables one commit action',()=>{
 const out=githubDeliveryRows(project,[stored(commit)],[proposal(commit)]);
 assert.equal(out.rows.length,1);
 assert.equal(out.rows[0].approved,true);
 assert.equal(out.rows[0].eligibleExecute,true);
 assert.equal(out.rows[0].committed,false);
 const changed=githubDeliveryRows({...project,status:{...project.status,develop_sha:'b'.repeat(40)}},
  [stored(commit)],[proposal(commit)]);
 assert.equal(changed.rows[0].eligibleExecute,false);
 assert.match(changed.rows[0].blocker,/develop changed/);
});

test('only server-recorded completed commit with full SHA is verified',()=>{
 const cases=[
  {status:'started',result:{sha:'c'.repeat(40)}},
  {status:'uncertain',result:{sha:'c'.repeat(40)}},
  {status:'succeeded',result:{sha:'invalid'}},
 ];
 for(const event of cases){
  const out=githubDeliveryRows({...project,status:{...project.status,operations:[
   {operation_id:commit.id,...event}]}},[stored(commit)],[proposal(commit)]);
  assert.equal(out.rows[0].committed,false);
  assert.equal(out.rows[0].eligibleExecute,false);
 }
 const done=githubDeliveryRows({...project,status:{...project.status,operations:[
  {operation_id:commit.id,status:'succeeded',result:{sha:'c'.repeat(40)}}
 ]}},[stored(commit)],[proposal(commit)]);
 assert.equal(done.rows[0].committed,true);
 assert.equal(done.rows[0].eligibleExecute,false);
});

test('draft PR is only verified with bound exact-number provider receipt',()=>{
 const reference={...project,status:{...project.status,develop_sha:'c'.repeat(40)}};
 const candidate={...reference,status:{...reference.status,operations:[{
  operation_id:pr.id,status:'succeeded',
  result:{number:5,url:'https://github.com/rudrasinha05/private-project/pull/5',
   head_sha:'c'.repeat(40)}}]}};
 const ok=githubDeliveryRows(candidate,[stored(pr)],[proposal(pr)]);
 assert.equal(ok.rows[0].createdPr,true);
 assert.equal(ok.rows[0].prUrl,'https://github.com/rudrasinha05/private-project/pull/5');
 const wrong=githubDeliveryRows({...candidate,status:{...candidate.status,
  operations:[{operation_id:pr.id,status:'succeeded',
   result:{number:5,url:'https://evil.example/pull/5',head_sha:'c'.repeat(40)}}]}},
  [stored(pr)],[proposal(pr)]);
 assert.equal(wrong.rows[0].createdPr,false);
 assert.equal(wrong.rows[0].prUrl,null);
});


test('PR execution unavailable until complete single provider CI evidence passes',()=>{
 const reviewed={...project,status:{...project.status,develop_sha:'c'.repeat(40),
  ci_truncated:false,ci_check_truncated:false,ci_status_truncated:false,
  ci_check_runs:[
   {name:'Backend QA',status:'completed',conclusion:'success'},
   {name:'Browser QA',status:'completed',conclusion:'success'},
  ],ci_check_total:2,ci_statuses:[]}};
 const good=githubDeliveryRows(reviewed,[stored(pr)],[proposal(pr)]);
 assert.equal(good.rows[0].eligibleExecute,true);
 assert.equal(verifiedGitHubChecks(reviewed.status,pr.payload.required_checks),true);
 for(const altered of [
  {...reviewed.status,ci_check_truncated:true},
  {...reviewed.status,ci_truncated:true},
  {...reviewed.status,ci_check_total:10},
  {...reviewed.status,ci_check_runs:[{name:'Backend QA',status:'completed',conclusion:'success'}]},
  {...reviewed.status,ci_check_runs:[...reviewed.status.ci_check_runs,
   reviewed.status.ci_check_runs[0]]},
  {...reviewed.status,ci_check_runs:[{name:'Backend QA',status:'completed',
   conclusion:'failure'},reviewed.status.ci_check_runs[1]]},
  {...reviewed.status,ci_check_runs:[{name:'Backend QA',status:'in_progress',
   conclusion:null},reviewed.status.ci_check_runs[1]]},
 ]){
  const out=githubDeliveryRows({...reviewed,status:altered},[stored(pr)],[proposal(pr)]);
  assert.equal(out.rows[0].eligibleExecute,false);
  assert.match(out.rows[0].blocker,/CI checks incomplete/);
 }
});
