import test from 'node:test';
import assert from 'node:assert/strict';
import {MAX_WAIT_MS,lostAnswerWaitMs,stepLabel,transientError,waitMs} from '../apps/web/components/project-advance-state.js';

test('a scheduled wait is honoured, bounded to 15 s .. 5 min', ()=>{
 const now=Date.parse('2026-11-18T12:00:00Z');
 const at=m=>new Date(now+m*60000).toISOString();
 assert.equal(waitMs({progressed:false,followup:{eligible_at:at(3)}},now),180000);
 assert.equal(waitMs({progressed:false,schedule_at:at(90)},now),MAX_WAIT_MS);
 assert.equal(waitMs({progressed:false,followup:{eligible_at:at(-1)}},now),15000);
 assert.equal(waitMs({progressed:false,step:'running'},now),20000);
 for(const r of [{progressed:true},{done:true},{needs_founder:true},null])assert.equal(waitMs(r,now),0);
});

test('only lost answers are retried; refusals and expired sessions stop', ()=>{
 for(const e of [new TypeError('fetch failed'),{status:0},{status:502},{status:503},{status:504}])
  assert.equal(transientError(e),true);
 for(const status of [400,401,403,404,409,422,500])assert.equal(transientError({status}),false);
 assert.deepEqual([1,2,3,4,5,9].map(lostAnswerWaitMs),[20000,40000,80000,160000,300000,300000]);
});

test('labels no longer send failed or unstaffed stages to the Founder', ()=>{
 assert.match(stepLabel({kind:'failed',stage:'quality'}),/AI project manager starts a fresh attempt/);
 assert.match(stepLabel({kind:'unstaffed',stage:'release'}),/AI CEO assigns one/);
});
