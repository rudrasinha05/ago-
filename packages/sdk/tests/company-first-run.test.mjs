import test from 'node:test';
import assert from 'node:assert/strict';
import {FIRST_RUN_ACTIONS,firstRunReadiness,taskBootstrapBody} from '../company-first-run.js';
const staff=[{id:'human',kind:'human',name:'Founder'},{id:'ai-1',kind:'ai',name:'Analyst'}];
test('first-run only includes real AI employees and requires server task feed and permission',()=>{
 const ready=firstRunReadiness(staff,['task:create'],[]);
 assert.equal(ready.canStart,true);assert.deepEqual(ready.eligible.map(e=>e.id),['ai-1']);
 assert.equal(firstRunReadiness(staff,[],[]).canStart,false);
 assert.equal(firstRunReadiness(staff,['task:create'],null).canStart,false);
 assert.equal(firstRunReadiness([staff[0]],['task:create'],[]).canStart,false);
});
test('no invented specialist, privileged action or fake AI capability accepted',()=>{
 assert.deepEqual(taskBootstrapBody('research:brief','ai-1',staff),{action:'research:brief',assignee_id:'ai-1'});
 assert.deepEqual(taskBootstrapBody('internal:brief','ai-1',staff),{action:'internal:brief',assignee_id:'ai-1'});
 for(const [act,id] of [['tool:github','ai-1'],['internal:brief','human'],['research:brief','made-up']])
  assert.throws(()=>taskBootstrapBody(act,id,staff));
 assert.equal(FIRST_RUN_ACTIONS.find(x=>x.value==='research:brief').requiresModel,true);
 assert.equal(FIRST_RUN_ACTIONS.find(x=>x.value==='internal:brief').requiresModel,false);
});
