import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionClient} from '../session.js';
import {readPlan,loadWorkspace,dashboardRecords} from '../workspace.js';
const id='10000000-0000-4000-8000-000000000001';
test('clearing a session aborts pending requests and rejects ignored cancellation',async()=>{
  let finish,signal;
  const client=new SessionClient({fetchImpl:(_url,options)=>{signal=options.signal;return new Promise(resolve=>{finish=resolve;});}});
  const pending=client.request('/v1/tasks');client.clear();assert.equal(signal.aborted,true);
  finish({ok:true,json:async()=>[{secret:'old tenant'}]});await assert.rejects(pending,/Session changed/);
});
test('all eight read plans use same-origin routes and correct calendar contract',()=>{
  for(const page of ['overview','strategy','governance','organization','knowledge','tools','calendar','twin'])assert.ok(readPlan(page).every(([,path])=>path.startsWith('/v1/')));
  assert.equal(readPlan('calendar')[0][0],'events');assert.throws(()=>readPlan('unknown'));
});
test('department employee denial cannot masquerade as a zero-sized team',async()=>{
  const api={readMany:async entries=>entries[0][0]==='departments'?{departments:{status:'ok',data:[{id}]}}:{[id]:{status:'forbidden',data:null}}};
  const result=await loadWorkspace(api,'organization');assert.equal(result.employees.status,'forbidden');assert.equal(result.employees.data,null);
});
test('employee and department views derive assignments from explicit identities',()=>{
  const data={tasks:{status:'ok',data:[{id:'a',assignee_id:id},{id:'b',assignee_id:'other'}]},employees:{status:'ok',data:{dept:[{id}]}},departments:{status:'ok',data:[{id:'dept'}]}};
  const result=dashboardRecords(data,{id},'dept');assert.deepEqual(result.myTasks.map(x=>x.id),['a']);assert.deepEqual(result.departmentTasks.map(x=>x.id),['a']);
  assert.equal(dashboardRecords({}, {id}, 'dept').departmentTasks,null);
});
test('logout clears local authority immediately while revoking the captured session',async()=>{
  let finish,revoked=false;
  const client=new SessionClient({fetchImpl:async(path,options)=>{
    if(path==='/v1/sessions')return {ok:true,json:async()=>({access_token:'test-only'})};
    if(path==='/v1/console/logout'){assert.equal(options.headers.Authorization,'Bearer test-only');assert.equal(options.credentials,'omit');revoked=true;return new Promise(resolve=>{finish=resolve;});}
    assert.equal(options.headers.Authorization,undefined);return {ok:true,json:async()=>[]};
  }});
  await client.login({tenant:id,email:'test@example.test',password:'exact password'});
  const pending=client.logout();assert.equal(client.authenticated,false);assert.equal(revoked,true);
  await client.request('/v1/tasks');finish({ok:true});await pending;
});
