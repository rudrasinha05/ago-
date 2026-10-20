/** Browser regression with explicitly mocked API. Database tests live in test_company_chat.py. */
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
const root=resolve('apps/web/out');
const server=createServer(async(req,res)=>{try{
 let pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\/workspace/,'');
 if(pathname.endsWith('/'))pathname+='index.html';
 const file=resolve(root,'.'+pathname);if(!file.startsWith(root+'/')){res.writeHead(403);res.end();return;}
 const content=await readFile(file);res.setHeader('Content-Type',({'.html':'text/html','.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml'})[extname(file)]||'application/octet-stream');res.end(content);
}catch{res.writeHead(404);res.end();}});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=process.env.AGO_PREVIEW_URL||'http://127.0.0.1:'+server.address().port;
const id=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const founder=id(1), tenant=id(2), department=id(3), cto=id(4), developer=id(5);
const employees=[{id:cto,name:'CTO',department_id:department,kind:'ai',manager_id:null},{id:developer,name:'Developer',department_id:department,kind:'ai',manager_id:cto}];
const departments=[{id:department,name:'Engineering'}];
let tasks=[{id:id(6),action:'research:brief',assignee_id:developer,status:'running',project_name:'Orchestration research'}];
let messages=[], calls=[];
let workEvents=[{id:1,employee_id:developer,task_id:id(6),body:'research:brief → running',created_at:new Date().toISOString()}];
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1700,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname,body=req.postDataJSON();let result=[];
  calls.push({path,method:req.method(),body});
  if(path==='/v1/sessions')result={access_token:'fixture-session'};
  else if(path==='/v1/console/me')result={id:founder,tenant_id:tenant,display_name:'Rudra',roles:['founder'],permissions:['organization:read','organization:manage','task:read','messages:write','brain:read']};
  else if(path==='/v1/organization/departments')result=departments;
  else if(path==='/v1/organization/employees')result=employees;
  else if(path.endsWith('/company/activity'))result=tasks;
  else if(path.endsWith('/company/notifications'))result={by_employee:{[developer]:workEvents.length,[cto]:0},recent:[...workEvents].reverse(),event_type:'committed_task_status'};
  else if(path==='/v1/platform/catalog')result={github_projects:[]};
  else if(path.endsWith('/company/chat')){
   if(req.method()==='POST'){result={...body,id:messages.length+1,author_name:'Rudra',kind:'message',created_at:new Date().toISOString()};messages.push(result);}
   else result={items:messages.filter(m=>url.searchParams.get('channel')==='global'||m.channel===url.searchParams.get('channel')),next_before:null};
  }else if(path.endsWith('/company/staffing')){result={id:id(7),department_id:body.department_id,manager_id:body.manager_id,name:body.name,kind:'ai'};employees.push(result);}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)});
 });
 async function login(){await page.getByLabel('Organization ID').fill(tenant);await page.getByLabel('Work email').fill('founder@example.test');await page.getByLabel('Password',{exact:true}).fill('test-only-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('heading',{name:'Company map',exact:true}).waitFor();}
 await page.goto(base+'/workspace/organization/');await login();
 await page.locator('.company-channels').getByRole('button',{name:'Developer',exact:true}).click();
 await page.getByText('Orchestration research',{exact:false}).waitFor();
 assert.match(await page.locator('.employee-inspector').innerText(),/Busy/);
 await page.locator('.map-node.employee.working').filter({hasText:'Developer'}).waitFor();
 assert.ok(await page.locator('.company-world .edge-live').count()>=2,'Entire assigned hierarchy glows red');
 assert.match(await page.locator('.map-node.employee').filter({hasText:'Developer'}).innerText(),/Orchestration research/);
 assert.match(await page.locator('.employee-inspector').innerText(),/Additional responsibilities/);
 await page.getByRole('heading',{name:'Board of Directors'}).waitFor();
 await page.getByRole('heading',{name:'AI Company Command Center'}).waitFor();
 await page.getByLabel('Message Developer',{exact:true}).fill('Please show the sources');await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.locator('.chat-message').getByText('Please show the sources',{exact:true}).waitFor();
 await page.locator('.chat-message').getByRole('button',{name:'Reply',exact:true}).click();
 await page.getByLabel('Message Developer',{exact:true}).fill('Include experimental evidence');await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.locator('.chat-message').getByText('Include experimental evidence',{exact:true}).waitFor();assert.equal(messages[1].reply_to,1);
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.getByRole('button',{name:'Founder',exact:true}).click();
 await page.getByLabel('Talk to your company',{exact:true}).fill('Founder project brief');await page.getByRole('button',{name:'Send to global chat',exact:true}).click();
 await page.locator('.chat-message').getByText('Founder project brief',{exact:true}).waitFor();assert.equal(messages[2].channel,'global');
 await page.getByRole('button',{name:'Add needed role',exact:true}).click();await page.getByLabel('Role name',{exact:true}).fill('QA Scientist');await page.getByLabel('Reports to',{exact:true}).selectOption(cto);await page.getByLabel('Why is this role needed?',{exact:true}).fill('Validate research experiment outputs');await page.getByRole('button',{name:'Create role',exact:true}).click();await page.locator('.map-node.employee').filter({hasText:'QA Scientist'}).waitFor();
 assert.equal(calls.find(c=>c.path.endsWith('/staffing')).body.manager_id,cto);
 tasks=[{...tasks[0],status:'completed'}];
 workEvents.push({id:2,employee_id:developer,task_id:id(6),body:'research:brief → completed',created_at:new Date().toISOString()});
 await page.getByRole('status').filter({hasText:'Developer'}).waitFor({timeout:15000});
 await page.locator('.map-node.employee.working').filter({hasText:'Developer'}).waitFor({state:'detached',timeout:15000});
 await page.locator('.company-channels .chat-event-count').filter({hasText:'2'}).waitFor();
 await page.screenshot({path:'/tmp/ago-company-desktop.png',fullPage:true});
 await page.addScriptTag({path:'node_modules/axe-core/axe.min.js'});
 const accessibility=await page.evaluate(async()=> (await axe.run(document.querySelector('.company-command'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}})).violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})));
 assert.deepEqual(accessibility,[],'Company map accessibility');
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile must not overflow horizontally');
 await page.screenshot({path:'/tmp/ago-company-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: map, assignment/status, chat, replies, centre composer, staffing, popup, mobile width; mocked API');
}finally{await browser.close();server.close();}
