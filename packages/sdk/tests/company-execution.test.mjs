import test from 'node:test';
import assert from 'node:assert/strict';
import {nextTaskAction,executionSummary} from '../company-execution.js';
const t={id:'t',assignee_id:'ai',action:'internal:brief',status:'waiting_approval',approval_id:'a'};
const good={id:'a',action:'internal:brief',status:'approved'};
const rights=['task:create','approval:request','agent:dispatch','task:execute'];
test('only exact approved task can dispatch, without a false green approval',()=>{
 assert.equal(nextTaskAction(t,good,rights).action,'run');
 assert.equal(nextTaskAction(t,{...good,id:'wrong'},rights).action,null);
 assert.equal(nextTaskAction(t,{...good,action:'other'},rights).action,null);
 assert.equal(nextTaskAction(t,{...good,status:'pending'},rights).action,null);
 assert.equal(nextTaskAction(t,null,rights).action,null);
 assert.equal(nextTaskAction(t,good,['agent:dispatch']).action,null);
 assert.equal(nextTaskAction(t,good,rights,true).action,null);
});
test('proposed requests need actual privileges, unsupported tools cannot be run through AI desk',()=>{
 assert.equal(nextTaskAction({...t,status:'proposed'},null,rights).action,'request');
 assert.equal(nextTaskAction({...t,status:'proposed'},null,[]).action,null);
 assert.equal(nextTaskAction({...t,action:'tool:github'}, {...good,action:'tool:github'},rights).action,null);
 for(const status of ['running','completed','failed']){
  assert.equal(nextTaskAction({...t,status},good,rights).action,null);
 }
});
test('summary counts are derived only from real server records',()=>{
 assert.equal(executionSummary(null),null);
 assert.deepEqual(executionSummary([{status:'proposed'},{status:'waiting_approval'},{status:'running'},{status:'completed'},{status:'failed'}]),{proposed:1,awaiting:1,running:1,completed:1,failed:1});
});
