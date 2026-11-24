import test from 'node:test';
import assert from 'node:assert/strict';
import {connectText,decisionsView,errorText,managerPool,providerStatus,settingsView,usable,usageLine} from '../apps/web/components/ai-models-state.js';

const view={monthly_call_cap:100,allow_paid:true,
 usage:{month:'2026-11',calls:3,paid_calls:1,input_tokens:1200,output_tokens:450},
 providers:[{provider:'openai',saved:false},{provider:'anthropic',saved:true,model:'claude-x',test_status:'ok'},
  {provider:'gemini',saved:true,model:'g',test_status:'failed',last_error:'auth_failed'},{provider:'groq',saved:true,model:'q',test_status:'ok'}]};

test('status chips say plainly where each key stands',()=>{
 assert.deepEqual(view.providers.map(p=>providerStatus(p).text),['Not connected','Working','Test failed','Working']);
 assert.equal(providerStatus({saved:true,test_status:'ok',last_error:'rate_limited_or_no_credit'}).tone,'warn');
 assert.equal(providerStatus({saved:true,test_status:null}).text,'Saved, test it');
});
test('the Manager may use only saved and tested models; paid ones follow the Founder switch',()=>{
 assert.deepEqual(usable(view).map(p=>p.provider),['anthropic','groq']);
 assert.equal(managerPool(view),'Local model (Ollama) · Groq · Claude (paid, when the work needs it)');
 assert.equal(managerPool({...view,allow_paid:false}),'Local model (Ollama) · Groq · Claude (paid, switched off)');
});
test('usage and errors read as one plain sentence each',()=>{
 assert.equal(usageLine(view),'3 cloud calls in 2026-11 (1 of 100 paid) · 1,200 tokens in, 450 out');
 assert.match(errorText('auth_failed'),/refused/);
 assert.equal(errorText('weird'),'Failed (weird).');
 assert.equal(errorText(null),'');
});
test('an unexpected server answer is refused, never rendered half-broken',()=>{
 for(const bad of [null,[],{},{providers:{}}])assert.equal(settingsView(bad),null);
 const v=settingsView({providers:[{provider:'groq'},{provider:'evil'}]});
 assert.deepEqual(v.providers.map(p=>p.provider),['groq']);
 assert.equal(v.monthly_call_cap,0);assert.equal(v.usage.calls,0);assert.equal(v.allow_paid,true);
 assert.equal(settingsView({providers:[],allow_paid:false}).allow_paid,false);
});
test('Manager decisions are shown with plain work names; unknown records are dropped',()=>{
 assert.deepEqual(decisionsView(null),[]);
 assert.deepEqual(decisionsView({kind:'other',decisions:[]}),[]);
 const d=decisionsView({kind:'ago_model_decisions_v1',decisions:[
  {id:1,work:'code',role:'employee',model_label:'anthropic:claude-sonnet',reason:'rework',created_at:'t'},
  {id:2,work:'hack',model_label:'x'},{id:3,work:'qa',model_label:7}]});
 assert.equal(d.length,1);
 assert.deepEqual(d[0],{id:'1',work:'Code writing',role:'employee',model:'anthropic:claude-sonnet',reason:'rework',at:'t',paid:true});
});
test('Connect results read as one sentence',()=>{
 assert.equal(connectText('Gemini',{ok:true,model:'gemini-3.8-flash'}),'Gemini connected. Model: gemini-3.8-flash. The Employee Manager can now use it.');
 assert.equal(connectText('Groq',{ok:false,code:'auth_failed',saved:false}),'Groq: The key was refused. Check it, or make a new key. The key was not saved.');
});
test('Connect says which busy models were tried first, and how to fix a workspace key',()=>{
 assert.equal(connectText('Gemini',{ok:true,model:'gemini-2.5-flash',tried:[{model:'gemini-3.8-flash',ok:false},{model:'gemini-2.5-flash',ok:true}]}),
  'Gemini connected. Model: gemini-2.5-flash (tried first: gemini-3.8-flash). The Employee Manager can now use it.');
 assert.match(connectText('Claude',{ok:false,code:'workspace_id_needed',saved:false}),/Workspace ID .*wrkspc_.*The key was not saved\.$/);
});
