import test from 'node:test';
import assert from 'node:assert/strict';
import {followupText,headline,needsYou,projectLine,stationState} from '../apps/web/components/founder-today-state.js';
import {boardMembers,boardMessage,initials,replyText,respondStatusText} from '../apps/web/components/board-codenames.js';

const founder='f0000000-0000-4000-8000-000000000001';
const stage=(name,status,verdict=null)=>({stage:name,task_id:name+'-task',task_status:status,qa_verdict:verdict,employee:'AI '+name});
const project=(extra={})=>({project_id:'p1',title:'AdmissionFlow',manager:'Project Manager',plan_status:'active',delivery_state:'blocked',pending_approvals:[],
 stages:[stage('discovery','completed','pass'),stage('architecture','completed','pass'),stage('implementation','completed','pass'),
  stage('quality','completed','fail'),stage('release',null)],followups:[],...extra});

test('stations follow recorded task and QA results only',()=>{
 assert.equal(stationState(stage('x','completed','pass')),'passed');
 assert.equal(stationState(stage('x','completed','fail')),'failed');
 assert.equal(stationState(stage('x','completed')),'review');
 assert.equal(stationState(stage('x','running')),'running');
 assert.equal(stationState(stage('x','waiting_approval')),'waiting');
 assert.equal(stationState(stage('x',null)),'idle');
 assert.equal(stationState(stage('x','completed','fail'),{id:'h'}),'hold');
 assert.equal(stationState(stage('x','completed','pass'),{id:'h'}),'passed');   // passed beats an old hold
});

test('the live AdmissionFlow hold reads as one plain sentence and a rework action',()=>{
 const hold={id:'h1',stage:'quality',code:'recovery_limit_reached',status:'blocked',owner_id:founder,
  feedback:'CEO REPORT: the AI CEO put the quality stage on hold after 6 automatic attempts…',next_action:'Review'};
 const p=project({followups:[hold,{...hold,id:'h0'}]});
 const line=projectLine(p,founder);
 assert.deepEqual(line.stations.map(s=>s.state),['passed','passed','passed','hold','idle']);
 assert.equal(line.passed,3);assert.equal(line.current,'quality');
 assert.match(line.now,/^Quality: On hold after 6 automatic attempts/);
 const items=needsYou([p],founder);
 assert.equal(items.length,1);                                   // newest blocker per stage only
 assert.equal(items[0].kind,'hold');assert.equal(items[0].rework,true);assert.equal(items[0].qaRework,true);
 assert.match(headline({projects:[p],needs:items,running:2}),/^1 project is active\. 1 thing needs you\. 2 AI tasks are running\.$/);
});

test('blockers owned by someone else, resolved ones and decisions are told apart',()=>{
 const p=project({followups:[{id:'a',stage:'quality',code:'qa_rework',status:'assigned',owner_id:'worker'},
  {id:'b',stage:'quality',code:'recovery_limit_reached',status:'resolved',owner_id:founder}],
  pending_approvals:[{approval_id:'ap1',type:'plan_review',requires_founder_decision:true},{approval_id:'ap2',requires_founder_decision:false}]});
 const items=needsYou([p],founder);
 assert.deepEqual(items.map(i=>[i.kind,i.title]),[['decision','Approve the project plan']]);
 assert.equal(projectLine(p,founder).now,'Quality: QA sent the work back. The team is redoing it.');
 assert.equal(headline({projects:[p],needs:[]}),'1 project is active. Nothing needs you right now.');
});

test('a finished project and unknown follow-up codes stay honest',()=>{
 const done=project({stages:[stage('discovery','completed','pass')]});
 assert.equal(projectLine(done,founder).now,'All 1 stages passed QA.');
 assert.equal(projectLine(done,founder).done,true);
 assert.equal(headline({projects:[done],needs:[]}),'0 projects are active. Nothing needs you right now.');
 assert.equal(followupText({code:'new_code',next_action:'  Do   this next.  '}),'Do this next.');
 assert.equal(followupText({code:'x',feedback:'y'.repeat(300)}).length,138);
 assert.equal(projectLine({project_id:'e',title:'Empty',stages:[]},founder).now,'No stages yet.');
});

test('Board call names map to approved seats; vacant seats stay vacant',()=>{
 const employees=[{id:'e1',name:'AGO AI CEO'},{id:'e2',name:'Old CTO'}];
 const members=boardMembers([{seat:'Strategy & Vision',employee_id:'e1'},{seat:'Technology Oversight',employee_id:'gone'}],employees);
 assert.deepEqual(members.map(m=>m.codename),['JARVIS','STARK','LUTHOR','SPECTRE','DR. STRANGE']);
 assert.equal(members[0].member.name,'AGO AI CEO');
 assert.equal(members[1].member,null);                           // appointment to a missing employee is not a member
 assert.equal(initials('DR. STRANGE'),'DS');assert.equal(initials('JARVIS'),'JA');
 assert.equal(boardMessage(members[0],'  kya haal hai? '),'Voice chat with JARVIS (Strategy & Vision): kya haal hai?');
});

test('spoken answers drop the record label and routing lines; statuses are plain',()=>{
 assert.equal(replyText('Local model reply (not task execution/QA evidence):\nAll good.\nDELEGATE_ID: NONE'),'All good.');
 assert.match(respondStatusText('local_model_disabled'),/turned off/);
 assert.match(respondStatusText('weird'),/weird/);
});
