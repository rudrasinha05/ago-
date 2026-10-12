/** v1 integration client. Tokens remain caller-owned; retries preserve idempotency. */
export class CompanyAPI {
  constructor(origin, token, {fetcher=fetch,retries=2}={}) {
    const url=new URL(origin);
    if(!['','/'].includes(url.pathname) || url.username || url.password || url.search || url.hash || (url.protocol!=='https:' && !(url.protocol==='http:' && ['127.0.0.1','[::1]'].includes(url.hostname))))throw new Error('HTTPS or loopback origin required');
    this.origin=url.origin;this.token=token;this.fetcher=fetcher;this.retries=Math.max(0,Math.min(3,retries));
  }
  async request(path,{method='GET',body,idempotencyKey,signal}={}) {
    if(!path.startsWith('/v1/platform/') || path.includes('..') || path.includes('://'))throw new Error('Scoped v1 platform path required');
    const target=new URL(path,this.origin);if(target.origin!==this.origin || !target.pathname.startsWith('/v1/platform/') || /[%\\#\u0000-\u0020]/.test(path.split('?')[0]))throw new Error('Canonical platform path required');
    const headers={Authorization:'Bearer '+this.token,'X-Request-ID':crypto.randomUUID()};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(idempotencyKey)headers['Idempotency-Key']=idempotencyKey;
    for(let attempt=0;;attempt++) {
      const response=await this.fetcher(this.origin+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),redirect:'error',signal});
      if(response.ok)return response.json();
      if(attempt>=this.retries || ![429,502,503,504].includes(response.status) || method!=='GET' && !idempotencyKey)throw new Error('AGO request failed: '+response.status+'; request '+(response.headers.get('x-request-id') || 'unknown'));
      const delay=Math.min(5,Math.max(0,Number(response.headers.get('retry-after')) || 2**attempt));
      await new Promise(resolve=>setTimeout(resolve,delay*1000));
    }
  }
  events(after=0,limit=100){return this.request('/v1/platform/events?'+new URLSearchParams({after,limit}));}
  tasks(after='',limit=50){return this.request('/v1/platform/tasks?'+new URLSearchParams({...(after?{after}:{}),limit}));}
  proposeTask(action,assigneeId,idempotencyKey){if(!idempotencyKey)throw new Error('Stable idempotency key required');return this.request('/v1/platform/tasks',{method:'POST',body:{action,assignee_id:assigneeId},idempotencyKey});}
  async *stream(after=0,{signal}={}) {
    const response=await this.fetcher(this.origin+'/v1/platform/stream?after='+encodeURIComponent(after),{headers:{Authorization:'Bearer '+this.token},redirect:'error',signal});
    if(!response.ok || !response.body)throw new Error('Stream unavailable');
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
    try{while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});if(buffer.length>262144)throw new Error('Stream frame too large');let end;while((end=buffer.indexOf('\n\n'))>=0){const frame=buffer.slice(0,end);buffer=buffer.slice(end+2);const fields=Object.fromEntries(frame.split('\n').filter(x=>x.includes(':')).map(x=>[x.slice(0,x.indexOf(':')),x.slice(x.indexOf(':')+1).trim()]));if(fields.data)yield {id:Number(fields.id),event:fields.event,data:JSON.parse(fields.data)};}}}finally{await reader.cancel();}
  }
}
