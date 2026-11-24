import test from 'node:test';
import assert from 'node:assert/strict';
import {errorText,providerStatus,routable,routeSummary,usageLine} from '../apps/web/components/ai-models-state.js';

const view={monthly_call_cap:100,routes:{code:'anthropic',qa:null,chat:null},
 usage:{month:'2026-11',calls:3,input_tokens:1200,output_tokens:450},
 providers:[{provider:'openai',saved:false},{provider:'anthropic',saved:true,model:'claude-x',test_status:'ok'},
  {provider:'gemini',saved:true,model:'g',test_status:'failed',last_error:'auth_failed'},{provider:'groq',saved:true,model:'q',test_status:null}]};

test('status chips say plainly where each key stands',()=>{
 assert.deepEqual(view.providers.map(p=>providerStatus(p).text),['Not connected','Working','Test failed','Saved, test it']);
 assert.equal(providerStatus({saved:true,test_status:'ok',last_error:'rate_limited_or_no_credit'}).tone,'warn');
});
test('only a saved and tested key can be chosen for work',()=>{
 assert.deepEqual(routable(view).map(p=>p.provider),['anthropic']);
});
test('usage, routes and errors read as one plain sentence each',()=>{
 assert.equal(usageLine(view),'3 of 100 cloud calls used in 2026-11 · 1,200 tokens in, 450 out');
 assert.deepEqual(routeSummary(view).map(r=>r.uses),['Claude (claude-x)','Local model (Ollama)','Local model (Ollama)']);
 assert.match(errorText('auth_failed'),/refused/);
 assert.equal(errorText('weird'),'Failed (weird).');
 assert.equal(errorText(null),'');
});
import {settingsView} from '../apps/web/components/ai-models-state.js';
test('an unexpected server answer is refused, never rendered half-broken',()=>{
 for(const bad of [null,[],{},{providers:[]},{providers:{},routes:{}}])assert.equal(settingsView(bad),null);
 const v=settingsView({providers:[{provider:'groq'},{provider:'evil'}],routes:{code:null}});
 assert.deepEqual(v.providers.map(p=>p.provider),['groq']);
 assert.equal(v.monthly_call_cap,0);assert.equal(v.usage.calls,0);
});
import {connectText} from '../apps/web/components/ai-models-state.js';
test('Connect results read as one sentence',()=>{
 assert.equal(connectText('Gemini',{ok:true,model:'gemini-3.8-flash',code_writing_routed:true}),'Gemini connected. Model: gemini-3.8-flash. Code writing now uses it.');
 assert.equal(connectText('Groq',{ok:false,code:'auth_failed',saved:false}),'Groq: The key was refused. Check it, or make a new key. The key was not saved.');
});
test('Connect says which busy models were tried first, and how to fix a workspace key',()=>{
 assert.equal(connectText('Gemini',{ok:true,model:'gemini-2.5-flash',code_writing_routed:true,tried:[{model:'gemini-3.8-flash',ok:false},{model:'gemini-2.5-flash',ok:true}]}),
  'Gemini connected. Model: gemini-2.5-flash (tried first: gemini-3.8-flash). Code writing now uses it.');
 assert.match(connectText('Claude',{ok:false,code:'workspace_id_needed',saved:false}),/Workspace ID .*wrkspc_.*The key was not saved\.$/);
});
