import test from 'node:test';
import assert from 'node:assert/strict';
import {CompanyAPI} from '../platform.js';

test('platform credentials stay on canonical origin and reject path escapes',async()=>{
  const calls=[];const sdk=new CompanyAPI('https://ago.example','secret',{fetcher:async(url,options)=>{calls.push({url,options});return Response.json({tasks:[]});}});
  for(const path of ['https://evil.test/v1/platform/tasks','/v1/platform/../sessions','/v1/platform/%2e%2e/sessions','/v1/platform/\\..\\sessions'])await assert.rejects(sdk.request(path));
  await sdk.tasks();assert.equal(calls.length,1);assert.equal(calls[0].options.redirect,'error');assert.equal(calls[0].options.headers.Authorization,'Bearer secret');
});
test('platform refuses implicit write retries and requires task idempotency',async()=>{
  let calls=0;const sdk=new CompanyAPI('http://127.0.0.1:8000','secret',{fetcher:async()=>{calls++;return new Response('',{status:503});}});
  await assert.rejects(sdk.request('/v1/platform/tasks',{method:'POST',body:{}}));assert.equal(calls,1);
  assert.throws(()=>sdk.proposeTask('brief','employee',''));
});
test('platform stream parses split frames and releases reader',async()=>{
  const encoder=new TextEncoder();let canceled=false;
  const sdk=new CompanyAPI('https://ago.example','secret',{fetcher:async()=>new Response(new ReadableStream({start(c){c.enqueue(encoder.encode('id: 9\nevent: task.changed.v1\nda'));c.enqueue(encoder.encode('ta: {"status":"ready"}\n\n'));},cancel(){canceled=true;}}))});
  for await(const item of sdk.stream()){assert.equal(item.id,9);assert.equal(item.data.status,'ready');break;}
  assert.equal(canceled,true);
});
