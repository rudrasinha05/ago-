import test from 'node:test';
import assert from 'node:assert/strict';
import {AgoReadClient} from '../index.js';
test('SDK rejects credentials, insecure foreign hosts and non-origin URLs',()=>{
  for(const origin of ['http://example.com','https://u:p@example.com','https://example.com/path','https://example.com/?token=secret']) assert.throws(()=>new AgoReadClient(origin));
});
test('SDK health stays on origin, refuses redirects and carries no credentials',async()=>{
  const client = new AgoReadClient('http://127.0.0.1:8000',async(url,options)=>{
    assert.equal(url.href,'http://127.0.0.1:8000/health/live'); assert.equal(options.redirect,'error'); assert.equal(options.credentials,'omit'); return {ok:true,json:async()=>({status:'ok'})};
  });
  assert.deepEqual(await client.health(),{status:'ok'});
});
test('SDK bounds timeout and rejects malformed health',async()=>{
  const client=new AgoReadClient('https://example.com',async()=>({ok:true,json:async()=>({secret:'hidden'})}));
  await assert.rejects(client.health({timeoutMs:0}));await assert.rejects(client.health(),/Invalid health/);
});
