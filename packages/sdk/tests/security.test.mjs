import test from 'node:test';
import assert from 'node:assert/strict';
import {SessionClient} from '../session.js';

test('MFA is carried only in sign-in body and cookie handoff is restricted to SSO routes',async()=>{
  const calls=[];
  const client=new SessionClient({fetchImpl:async(path,options)=>{
    calls.push({path,options});
    return {ok:true,json:async()=>({access_token:'memory-only-fixture-token'})};
  }});
  await client.login({tenant:'a1111111-1111-4111-8111-111111111111',email:'fixture@test',password:'fixture-password',factorCode:'123456'});
  assert.equal(JSON.parse(calls[0].options.body).factor_code,'123456');
  assert.equal(calls[0].options.credentials,'omit');
  client.clear();
  assert.equal(await client.completeSSO(),true);
  assert.equal(calls[1].path,'/v1/security/sso/session');
  assert.equal(calls[1].options.credentials,'same-origin');
  await client.request('/v1/console/me');
  assert.equal(calls[2].options.credentials,'omit');
  assert.equal(calls[2].options.headers.Authorization,'Bearer memory-only-fixture-token');
});

test('SSO refuses insecure redirects and late handoff cannot restore a cleared session',async()=>{
  const bad=new SessionClient({fetchImpl:async()=>({ok:true,json:async()=>({authorization_url:'http://attacker.test'})})});
  await assert.rejects(bad.startSSO('a1111111-1111-4111-8111-111111111111'),/Invalid SSO/);
  let release;
  const client=new SessionClient({fetchImpl:()=>new Promise(resolve=>{release=resolve;})});
  const pending=client.completeSSO();
  client.clear();
  release({ok:true,json:async()=>({access_token:'late-token'})});
  assert.equal(await pending,false);
  assert.equal(client.authenticated,false);
});
