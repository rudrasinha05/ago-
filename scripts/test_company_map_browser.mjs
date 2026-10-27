/** Browser regression with explicitly mocked API. Database tests live in test_company_chat.py. */
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
// Issue #3: job logs are not always reachable, so also report a failure as a
// GitHub check annotation. Diagnostics only: the exit code stays non-zero.
for(const event of ['uncaughtException','unhandledRejection'])process.on(event,error=>{
 const text=String(error?.stack||error).split('\n').slice(0,10).join('\n');
 console.log('::error title=Company map browser regression::'+text.replace(/%/g,'%25').replace(/\r/g,'%0D').replace(/\n/g,'%0A'));
 console.error(error);process.exitCode=1;
});
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
let founderBriefSnapshot='';
const employees=[{id:cto,name:'CTO',department_id:department,kind:'ai',manager_id:null},{id:developer,name:'Developer',department_id:department,kind:'ai',manager_id:cto}];
const departments=[{id:department,name:'Engineering'}];
let tasks=[{id:id(6),action:'research:brief',assignee_id:developer,status:'running',project_name:'Orchestration research'}];
let messages=[], calls=[];
let appointments=[],roles={},reports=[],founderProjects=[],approvalRecords=[],asReviewer=false;
let companyDocs=[],docAccess=[],docAudit=[];
let githubProjects=[],githubOperations=[],integrationProposals=[],githubRunState=null;
let workEvents=[{id:1,employee_id:developer,task_id:id(6),body:'research:brief → running',created_at:new Date().toISOString()}];
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1700,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname,body=req.postDataJSON();let result=[];
  calls.push({path,method:req.method(),body});
  if(path==='/v1/sessions')result={access_token:'fixture-session'};
  else if(path==='/v1/console/me')result=asReviewer?{id:id(31),tenant_id:tenant,display_name:'Reviewer',roles:['member'],permissions:['approval:read']}:{id:founder,tenant_id:tenant,display_name:'Rudra',roles:['founder'],permissions:['organization:read','organization:manage','task:read','messages:write','brain:read','brain:manage','approval:read','approval:decide']};
  else if(path==='/v1/organization/departments')result=departments;
  else if(path==='/v1/organization/employees')result=employees;
  else if(path.endsWith('/company/activity'))result=tasks;
  else if(path.endsWith('/company/notifications'))result={by_employee:{[developer]:workEvents.length,[cto]:0},recent:[...workEvents].reverse(),event_type:'committed_task_status'};
  else if(path==='/v1/platform/catalog')result={github_projects:githubProjects,github_operations:githubOperations};
  else if(path.startsWith('/v1/platform/github/projects/')&&path.endsWith('/status'))result=githubRunState||{status:'unavailable'};
  else if(path.startsWith('/v1/platform/github/operations/')&&path.endsWith('/execute')){
    assert.ok(githubRunState?.repository_private===true,'No public GitHub write even through mocks');
    const opId=path.split('/')[5];
    githubRunState.operations.push({operation_id:opId,status:'succeeded',result:{sha:'c'.repeat(40)}});
    result={status:'succeeded',operation_id:opId,result:{sha:'c'.repeat(40)}};
  }
  else if(path==='/v1/enterprise/reviews/integration')result={revision:0,proposals:integrationProposals};
  else if(path.endsWith('/company/projects/start')){
    const title=body.brief.split('\n')[0].slice(0,220);
    const stages=['discovery','architecture','implementation','quality','release'].map((stage,i)=>({
      stage,position:i+1,deliverable:'Testable milestone '+stage,
      suggested_assignee_name:i===0?'Developer':null,
      staffing_required:i!==0,plan_step_id:i===0?id(22):null
    }));
    result={id:id(20),title,goal_id:id(21),plan_id:id(23),stages,
      plan_status:'draft',automatic_execution:false,approval_required:true,reused:false,
      accountable_manager_id:cto,accountable_manager_name:'CTO',accountable_manager_role:'CTO',
      assignment_source:'executive_manager',commercial_objective:'Find paying customers',
      commercial_stage:'offer_needed',verified_revenue_inr:null};
    founderProjects.unshift({...result,staffing_gaps:4});
  }
  else if(path.endsWith('/company/projects'))result=founderProjects;
  else if(path==='/v1/organization/company/projects/'+id(20)){
    result={...founderProjects[0],brief:founderBriefSnapshot||founderProjects[0]?.title,
      qa_passed_stages:0,stage_count:5,completion_percent:0,
      running_stages:0,failed_stages:0,unassigned_stages:4,
      reviewed_delegations_count:0,project_health:'staffing_required',
      status_label:'under_process',revenue_record_status:'no_verified_evidence'};
  }
  else if(path==='/v1/organization/company/projects/'+id(20)+'/documents/eligible'){
    result=[{id:id(35),name:'QA Reviewer',role_title:'Project Reviewer'}];
  }
  else if(path==='/v1/organization/company/projects/'+id(20)+'/documents'){
    if(req.method()==='POST'){
      const doc={id:id(40+companyDocs.length),project_id:id(20),title:body.title,
        classification:body.classification,created_by:founder,revision:1,body:body.body};
      companyDocs.push(doc);docAudit.push({document_id:doc.id,action:'revise',actor_id:founder,occurred_at:new Date().toISOString()});
      result=doc;
    }else result=companyDocs.map(({body:ignore,revision:ignore2,...rest})=>rest);
  }
  else if(path.startsWith('/v1/organization/company/documents/')){
    const pieces=path.split('/'),documentId=pieces[5],doc=companyDocs.find(d=>d.id===documentId);
    if(!doc)throw new Error('Unexpected document fixture ID '+documentId);
    if(path.endsWith('/permissions')){
      docAccess.push({...body,document_id:doc.id});result={document_id:doc.id,grantee_id:body.grantee_id,action:body.event,effective:body.event==='grant'};
      docAudit.push({document_id:doc.id,actor_id:founder,action:body.event,occurred_at:new Date().toISOString()});
    }else if(path.endsWith('/revisions')){
      doc.revision+=1;doc.body=body.body;result={id:doc.id,revision:doc.revision};
      docAudit.push({document_id:doc.id,actor_id:founder,action:'revise',occurred_at:new Date().toISOString()});
    }else if(path.endsWith('/audit'))result=docAudit.filter(x=>x.document_id===doc.id);
    else result={...doc};
  }
  else if(path.endsWith('/company/management/workload'))result={
    employees:employees.map(e=>({...e,running:e.id===developer?1:0,queued:0,failed:0,
      completed:0,projects_accountable:e.id===cto?founderProjects.length:0})),
    leaders:[],idle_employees:employees.length-1,pending_employee_work:0,unassigned_work_generated:false
  };
  else if(path.endsWith('/company/approvals'))result=approvalRecords;
  else if(path.startsWith('/v1/governance/approvals/')&&path.endsWith('/decision')){
   const record=approvalRecords.find(a=>path.includes(a.id));assert.ok(record);
   if(asReviewer)
    return route.fulfill({status:403,json:{detail:'Strategic decisions require a human founder'}});
   if(!record.requires_founder_decision)
    return route.fulfill({status:403,json:{detail:'CEO handles scoped project tasks; no extra Founder decision'}});
   record.status=body.approve?'approved':'rejected';record.reason=body.reason;
   record.reviewer_id=asReviewer?id(31):founder;
   record.reviewer_name=asReviewer?'Reviewer':'Founder';
   record.decided_at=new Date().toISOString();result={request_id:record.id,status:record.status};
  }
  else if(path.includes('/v1/brain/plans/')&&path.endsWith('/submit')){
    result={approval_id:id(24),status:'pending_approval'};
    approvalRecords.push({id:id(24),requester_id:founder,requester_name:'Founder',
     requester_role:'Founder',action:'brain:activate:'+id(23),status:'pending',
     approval_type:'plan_review',requires_founder_decision:true,plan_title:founderProjects[0].title,
     plan_id:id(23),founder_intake_id:id(20),goal_brief_excerpt:founderBriefSnapshot,
     created_at:new Date().toISOString(),
     review_routing:'Founder only — authenticated active human founder',
     next_action:'An approved plan requires separate activation and per-task approvals.'});
  }
  else if(path==='/v1/brain/plans/'+id(23)+'/activate')result={status:'active'};
  else if(path==='/v1/brain/plans/'+id(23)+'/materialize')result={task_ids:[]};
  else if(path==='/v1/organization/company/projects/'+id(20)+'/ceo/reconcile')
    result={ceo_name:'CEO',verified_task_count:0,approved_stage_count:0,tasks_executed:0};
  else if(path.endsWith('/company/governance'))result={board:appointments,employees:employees.map(e=>({...e,...(roles[e.id]||{})})),board_grants_authority:false};
  else if(path.endsWith('/company/board/appoint')){appointments=appointments.filter(a=>a.seat!==body.seat);appointments.push({seat:body.seat,employee_id:body.employee_id});result={...body,authority_granted:false};}
  else if(path.includes('/company/employees/')&&path.endsWith('/role')){const worker=path.split('/').at(-2);roles[worker]=body;result={id:worker,...body};}
  else if(path.endsWith('/company/reports'))result=reports;
  else if(path.endsWith('/company/chat')){
   if(req.method()==='POST'){result={...body,id:messages.length+1,author_name:'Rudra',kind:'message',created_at:new Date().toISOString()};messages.push(result);}
   else result={items:messages.filter(m=>url.searchParams.get('channel')==='global'||m.channel===url.searchParams.get('channel')),next_before:null};
  }else if(path.endsWith('/company/staffing')){result={id:id(7),department_id:body.department_id,manager_id:body.manager_id,name:body.name,kind:'ai'};employees.push(result);}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)});
 });
 async function login(){await page.getByLabel('Organization ID').fill(tenant);await page.getByLabel('Work email').fill('founder@example.test');await page.getByLabel('Password',{exact:true}).fill('test-only-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('heading',{name:'Company map',exact:true}).waitFor();}
 // Organization sections live in tabs (all stay mounted; one is shown).
 async function tab(name){
  await page.getByRole('navigation',{name:'Company control center sections'}).locator('a').filter({hasText:name}).first().click();
  await page.waitForFunction(n=>[...document.querySelectorAll('.company-tabs a[aria-current="page"]')].some(a=>a.textContent.startsWith(n)),name);
 }
 await page.goto(base+'/workspace/organization/');await login();
 // The real visual page must have no path back to the retired legacy UI.
 assert.equal(await page.locator('a[href="/console/"]').count(),0,'No duplicate Control Center link');
 assert.equal(await page.locator('a[href="/tools/"]').count(),0,'No links bypass the /workspace basePath');
 assert.ok(await page.locator('.command-delivery a[href="/workspace/tools/"]').count()>=1,
   'GitHub/Tools links must target the real workspace route');
 for(const link of await page.locator('.company-cockpit-nav a[href^="#"]').all()){
   const destination=await link.getAttribute('href');
   assert.equal(await page.locator(destination).count(),1,'Company section exists: '+destination);
 }
 // Navigate via the real GitHub/Tools link: authentication must survive SPA navigation.
 await tab('Organization & Chat');
 await page.getByRole('link',{name:'View GitHub operations and CI'}).click();
 await page.locator('#screen .workspace-view').waitFor();
 assert.equal(new URL(page.url()).pathname,'/workspace/tools/');
 assert.equal(await page.locator('#login-form').count(),0,'Tools link must not lose tab-memory sign-in');
 await page.getByRole('navigation',{name:'Workspaces'}).getByRole('link',{name:'Organization',exact:true}).click();
 await page.getByRole('heading',{name:'Company map',exact:true}).waitFor();
 await tab('Execution & Delivery');
 await page.getByRole('heading',{name:'Project Delivery Center'}).waitFor();
 await page.locator('#ago-github-delivery').getByText('No approved GitHub project is linked.',{exact:false}).waitFor();
 assert.equal(await page.locator('#ago-github-delivery').getByRole('button',{name:/Execute approved GitHub/}).count(),0,
   'A Founder with no approved private project cannot dispatch GitHub work.');
 // Simulated AGO signed provider records: execute only after independent approval and explicit Founder choice.
 const mockedProject=id(70),mockedOperation=id(71),mockedProposal=id(72);
 const operation={id:mockedOperation,project_id:mockedProject,operation:'commit_files',
  payload:{expected_sha:'a'.repeat(40),message:'Test-only vetted source',
   files:[{path:'src/main.py',content:'print("mock-only")'}]}};
 githubProjects=[{payload:{id:mockedProject,repository:'ago-private-test',developer_ids:[]}}];
 githubOperations=[{kind:'github_operation',payload:operation,proposal_id:mockedProposal}];
 integrationProposals=[{id:mockedProposal,operation_key:mockedOperation,command:'github_operation',
  specification:operation,status:'approved',actor_id:founder}];
 githubRunState={project_id:mockedProject,repository:'rudrasinha05/ago-private-test',
  repository_private:true,develop_sha:'a'.repeat(40),operations:[]};
 const delivery=page.locator('#ago-github-delivery');
 await delivery.getByRole('button',{name:'Refresh live records'}).click();
 await delivery.getByText('AI-generated code commit').waitFor();
 const execute=delivery.getByRole('button',{name:'Execute approved GitHub commit'});
 await execute.click();
 await delivery.getByText('Select the exact confirmation',{exact:false}).waitFor();
 assert.equal(calls.filter(c=>c.path.endsWith('/execute')&&c.method==='POST').length,0);
 await delivery.getByLabel('Explicit Founder confirmation for selected step')
  .selectOption('EXECUTE_VERIFIED_GITHUB_OPERATION');
 await execute.click();
 await delivery.getByText('Verified commit:',{exact:false}).waitFor();
 assert.equal(calls.filter(c=>c.path.endsWith('/execute')&&c.method==='POST').length,1,
  'One Founder confirmation permits at most one real provider dispatch request');
 await delivery.getByRole('button',{name:'Refresh live records'}).click();
 assert.equal(await delivery.getByRole('button',{name:'Execute approved GitHub commit'}).count(),0,
  'Committed operation must not expose a second execution action');
 githubRunState={...githubRunState,repository_private:false};
 await delivery.getByRole('button',{name:'Refresh live records'}).click();
 await delivery.getByText('This repository is public',{exact:false}).waitFor();
 assert.equal(await delivery.getByRole('button',{name:/Execute approved GitHub/}).count(),0);
 // Reset simulated records for remaining company and independent reviewer tests.
 githubProjects=[];githubOperations=[];integrationProposals=[];githubRunState=null;
 await delivery.getByRole('button',{name:'Refresh live records'}).click();

 await tab('Organization & Chat');
 await page.locator('.company-channels').getByRole('button',{name:'Developer',exact:true}).click();
 await page.locator('.employee-inspector').getByText('Orchestration research',{exact:true}).waitFor();
 assert.match(await page.locator('.employee-inspector').innerText(),/Busy/);
 await page.locator('.map-node.employee.working').filter({hasText:'Developer'}).waitFor();
 assert.equal(await page.locator('.map-node.employee').filter({hasText:'CTO'}).locator('.map-count').count(),0);
 assert.equal(await page.locator('.company-channels .chat-event-count').filter({hasText:'0'}).count(),0);
 await page.getByRole('button',{name:'Full screen map'}).click();
 await page.locator('.company-shell.company-fullscreen').waitFor();
 assert.ok(await page.evaluate(()=>document.querySelector('.company-shell.company-fullscreen').getBoundingClientRect().height>=window.innerHeight-2));
 await page.keyboard.press('Escape');
 await page.locator('.company-shell.company-fullscreen').waitFor({state:'detached'});
 assert.equal(await page.locator('.company-world line.manager-link.edge-live').count(),1,'Only actual reporting routes glow red');
 assert.equal(await page.locator('.company-world line.department-link.edge-live').count(),0,'Grouping is not task authority');
 assert.ok(await page.locator('.company-world .company-orbit-ring').count()>0,'Circular guides must remain visible');
 assert.match(await page.locator('.map-node.employee').filter({hasText:'Developer'}).innerText(),/Orchestration research/);
 assert.match(await page.locator('.employee-inspector').innerText(),/Additional responsibilities/);
 await tab('Board & Roles');
 await page.getByRole('heading',{name:'Board of Directors'}).waitFor();
 await tab('Command Center');
 await page.getByRole('heading',{name:'AI Company Command Center'}).waitFor();
 const brain=page.locator('.brain-volume');
 const initialRotation=await brain.evaluate(n=>n.style.getPropertyValue('--brain-rotation'));
 assert.equal(await brain.locator('.brain-depth-slice').count(),8);
 const depthValues=await brain.locator('.brain-depth-slice').evaluateAll(nodes=>nodes.map(n=>n.style.getPropertyValue('--cortex-depth')));
 assert.equal(new Set(depthValues).size,8);
 assert.equal(await brain.evaluate(n=>getComputedStyle(n).transformStyle),'preserve-3d');
 assert.equal(await brain.locator('[data-verified-running="true"]').count(),1);
 assert.equal(await brain.locator('[data-verified-running="false"]').count(),5);
 const verifiedQueue=page.getByRole('region',{name:'Recorded company task assignments'});
 await verifiedQueue.getByText('Orchestration research',{exact:true}).waitFor();
 await verifiedQueue.getByText('Running',{exact:true}).waitFor();
 await verifiedQueue.getByRole('button',{name:'Open Developer work details'}).click();
 await page.locator('.employee-inspector').getByText('Orchestration research',{exact:true}).waitFor();
 await tab('Command Center');
 await page.getByRole('button',{name:'Rotate brain right'}).click();
 assert.notEqual(await brain.evaluate(n=>n.style.getPropertyValue('--brain-rotation')),initialRotation);
 assert.match(await brain.getAttribute('aria-label'),/verified running tasks/);
 await page.getByRole('button',{name:'Reset brain rotation'}).click();
 assert.equal(await brain.evaluate(n=>n.style.getPropertyValue('--brain-rotation')),'0deg');
 const founderBrief='Build a complete project management system with audit trails, secure access, automated tests and documentation';
 await tab('Projects');
 await page.getByLabel('Founder project brief').fill(founderBrief);
 await page.getByRole('button',{name:'Prepare project from brief'}).click();
 await page.getByText('Draft saved · Founder approval needed',{exact:false}).waitFor();
 assert.equal(founderProjects.length,1);
 assert.equal(founderProjects[0].automatic_execution,false);
 assert.equal(founderProjects[0].stages.length,5);
 // Test fixture is a founder-inspector replay, not a fabricated release.
 founderProjects[0].stages[0].founder_agent_result={
   kind:'local_company_governed_handoff',roles_completed:4,roles_expected:7,
   board_review_mode:'full_five_seat',board_review_cleared:false,
   board_blocked:true,board_block_reason:'deny',
   blocked_by_board_seat:'Risk & Compliance',
   board_recommendations:[
     {seat:'Strategy & Vision',recommendation:'approve'},
     {seat:'Technology Oversight',recommendation:'approve'},
     {seat:'Finance & Budget',recommendation:'approve'},
     {seat:'Risk & Compliance',recommendation:'deny'},
   ],
   handoffs:[{role:'risk',employee_name:'Risk Director',employee_id:id(27),
     human_qa_approved:false,draft:'BOARD_RECOMMENDATION: DENY'}],
   github_commits_created:false,project_released:false,
 };
 // UI regression: founder manages per-document ACL inside AGO; no GitHub calls.
 await page.getByRole('button',{name:/Inspect full project/}).first().click();
 await page.locator('.ago-ai-chain summary').getByText('4/7 recorded AI passes',{exact:false}).waitFor();
 await page.locator('.ago-ai-chain summary').click();
 await page.getByText('Board objection recorded',{exact:false}).waitFor();
 await page.getByText('Board review incomplete or stopped',{exact:false}).waitFor();
 const vault=page.locator('.ago-document-vault');
 await vault.getByRole('heading',{name:'Confidential documents · AGO local vault'}).waitFor();
 await vault.getByLabel('Title',{exact:true}).fill('Review-only API plan');
 await vault.getByLabel('Content',{exact:true}).fill('Sensitive local engineering notes');
 await vault.getByLabel('Classification').selectOption('project_restricted');
 await vault.getByRole('button',{name:'Save locally'}).click();
 await vault.getByText('Document saved to AGO local PostgreSQL.').waitFor();
 assert.equal(companyDocs.length,1);
 await vault.getByLabel('Employee').selectOption(id(35));
 await vault.getByLabel('Reason for the permission change').fill('Independent QA needs explicit access');
 await vault.getByRole('button',{name:'Grant read access'}).click();
 await vault.getByText('Specific employee now has document access.').waitFor();
 assert.equal(docAccess.at(-1).event,'grant');
 await vault.getByLabel('Employee').selectOption(id(35));
 await vault.getByLabel('Reason for the permission change').fill('QA scope review is complete now');
 await vault.getByRole('button',{name:'Revoke access'}).click();
 await vault.getByText('Access revoked. Next read will be denied.').waitFor();
 assert.equal(docAccess.at(-1).event,'revoke');
 await vault.getByLabel('Document content / next revision').fill('Updated local requirements');
 await vault.getByRole('button',{name:'Save new revision'}).click();
 assert.equal(companyDocs[0].revision,2);
 assert.equal(companyDocs[0].body,'Updated local requirements');
 assert.equal(calls.some(c=>c.path.includes('github')&&c.body?.body?.includes('Sensitive local')),false);

 await page.getByText('Accountable delivery owner: CTO',{exact:false}).waitFor();
 await tab('Execution & Delivery');
 await page.getByRole('heading',{name:'Management ownership and workforce utilization'}).waitFor();
 await page.getByRole('button',{name:'Inspect employee workload'}).click();
 await page.locator('.management-people').getByText('Developer',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Hide employee workload'}).click();
 await tab('Projects');
 await page.getByRole('button',{name:'Submit plan for founder approval'}).click();
 await page.getByText('Status: pending_approval',{exact:false}).waitFor();
 assert.ok(calls.some(c=>c.path==='/v1/brain/plans/'+id(23)+'/submit'));
 await tab('Approvals');
 await page.locator('.approval-inbox').getByText('1 pending requests company-wide').waitFor({timeout:15000});
 await page.locator('.approval-inbox').getByRole('button',{name:'View approval details'}).click();
 await page.getByRole('dialog',{name:'Approval details'}).getByText('Founder',{exact:false}).first().waitFor();
 assert.match(await page.getByRole('dialog',{name:'Approval details'}).innerText(),/Founder only/i);
 assert.equal(await page.getByRole('dialog',{name:'Approval details'}).getByRole('button',{name:'Approve',exact:true}).count(),1);
 await page.getByRole('button',{name:'Close approval details'}).click();
 await tab('Board & Roles');
 await page.getByLabel('Appoint AI CTO · Chief Technology Officer').selectOption(cto);
 await page.locator('.board-seat').filter({hasText:'Technology Oversight'}).getByRole('button',{name:'Appoint AI officer'}).click();
 await page.locator('.board-seat').filter({hasText:'Technology Oversight'}).getByRole('button',{name:'View officer profile'}).waitFor();
 await tab('Organization & Chat');
 await page.locator('.company-channels').getByRole('button',{name:'Developer',exact:true}).click();
 await page.getByRole('button',{name:'Edit employee accountability'}).click();
 await page.getByLabel('Official role title').fill('Backend Engineer');
 await page.getByLabel('Core responsibilities').fill('Build and independently test approved backend modules');
 await page.getByLabel('Additional responsibilities').fill('Maintain documentation and review own performance');
 await page.getByRole('button',{name:'Save role details'}).click();
 await page.locator('.accountability-panel').getByText('Backend Engineer').waitFor();
 assert.equal(roles[developer].role_title,'Backend Engineer');
 assert.equal(appointments[0].employee_id,cto);
 await page.getByLabel('Message Developer',{exact:true}).fill('Please show the sources');await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.locator('.chat-message').getByText('Please show the sources',{exact:true}).waitFor();
 await page.locator('.chat-message').getByRole('button',{name:'Reply',exact:true}).click();
 await page.getByLabel('Message Developer',{exact:true}).fill('Include experimental evidence');await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.locator('.chat-thread-reply').getByText('Include experimental evidence',{exact:true}).waitFor();
 assert.equal(messages[1].reply_to,1);
 assert.equal(await page.locator('.chat-message').filter({hasText:'Please show the sources'}).first().locator('.chat-thread-children .chat-message').count(),1);
 await page.getByRole('button',{name:'Hide profile'}).click();
 await page.locator('.employee-inspector').waitFor({state:'detached'});
 await page.getByRole('button',{name:'Show profile'}).click();
 await page.locator('.employee-inspector').waitFor();
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
 await mkdir('tests/frontend/artifacts',{recursive:true});
 await page.screenshot({path:'tests/frontend/artifacts/ago-company-command-desktop.png',fullPage:true});
 await page.addScriptTag({path:'node_modules/axe-core/axe.min.js'});
 const accessibility=await page.evaluate(async()=> (await axe.run(document.querySelector('.company-command'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa']}})).violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})));
 assert.deepEqual(accessibility,[],'Company map accessibility');
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile must not overflow horizontally');
 await page.screenshot({path:'tests/frontend/artifacts/ago-company-command-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 // Founder-alone approval policy: unprivileged logins can inspect, not decide.
 approvalRecords.push({id:id(37),requester_id:founder,requester_name:'Founder',
  requester_role:'Founder',action:'tool:review:'+id(6),status:'pending',
  approval_type:'governance_action',requires_founder_decision:false,
  review_routing:'Founder-only human decision',
  next_action:"Founder's own reviewed decision",created_at:new Date().toISOString()});
 approvalRecords.push({id:id(38),requester_id:developer,requester_name:'Developer',
  requester_role:'Engineer',action:'tool:review:'+id(7),status:'pending',
  approval_type:'governance_action',requires_founder_decision:false,
  review_routing:'Founder-only human decision',
  next_action:'CEO handles scoped project work, Founder holds exceptional decisions',
  created_at:new Date().toISOString()});
 await page.setViewportSize({width:1700,height:1100});
 asReviewer=true; // ordinary read-only company member, not a reviewer
 await page.goto(base+'/workspace/organization/');
 await page.getByLabel('Organization ID').fill(tenant);
 await page.getByLabel('Work email').fill('member@example.test');
 await page.getByLabel('Password',{exact:true}).fill('test-member-password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 assert.equal(await page.locator('#ago-github-delivery').count(),0,
   'Regular company members cannot view Founder GitHub dispatch controls.');
 await tab('Approvals');
 await page.locator('#company-approval-inbox').getByText('0 need my review',{exact:false}).waitFor();
 const readOnly=page.locator('#company-approval-inbox .approval-entry');
 await readOnly.first().getByRole('button',{name:'View approval details'}).click();
 const modal=page.getByRole('dialog',{name:'Approval details'});
 assert.equal(await modal.getByRole('button',{name:'Approve',exact:true}).count(),0);
 await modal.getByRole('button',{name:'Close approval details'}).click();
 asReviewer=false;
 await page.goto(base+'/workspace/organization/');await login();
 await tab('Approvals');
 await page.locator('#company-approval-inbox').getByText('1 need my review',{exact:false}).waitFor();
 const entries=page.locator('#company-approval-inbox .approval-entry');
 const founderDialog=page.getByRole('dialog',{name:'Approval details'});
 await entries.filter({hasText:'tool:review:'+id(7)})
  .getByRole('button',{name:'View approval details'}).click();
 assert.equal(await founderDialog.getByRole('button',{name:'Approve',exact:true}).count(),0,
  'CEO-scoped operational work cannot demand a second Founder decision');
 await founderDialog.getByRole('button',{name:'Close approval details'}).click();
 // After a fresh Founder login the map defaults to Leadership, which hides
 // ordinary contributors. Explicitly enter All employees to inspect their counters.
 await tab('Organization & Chat');
 await page.getByRole('button',{name:'All employees',exact:true}).click();
 const developerCard=page.locator('.map-node-wrap').filter({hasText:'Developer'}).first();
 await developerCard.waitFor({state:'visible'});
 await developerCard.locator('.employee-approval-counter').click();
 await developerCard.locator('.employee-approval-flyout')
  .getByText('CEO verifies routine work',{exact:false}).waitFor();
 assert.equal(await developerCard.locator('.employee-approval-flyout').getByRole('button',{name:'Approve'}).count(),0);
 await page.locator('.map-founder .employee-approval-counter').click();
 await page.locator('.map-founder .employee-approval-flyout')
  .getByRole('button',{name:'Approve',exact:true}).click();
 await page.locator('.map-founder .employee-approval-flyout')
  .getByText('Founder approved once',{exact:false}).waitFor();
 assert.equal(approvalRecords[0].status,'approved');
 assert.equal(approvalRecords[0].reviewer_id,founder);
 assert.equal(calls.filter(c=>c.path.endsWith('/ceo/reconcile')&&c.method==='POST').length,1,
  'Exact Founder project approval hands off once to CEO');
 // The inbox must keep its own Founder decision receipt visible after refresh.
 // This is an exceptional Founder authorization with no project handoff,
 // distinct from the previously verified once-only CEO project reconciliation.
 const exceptional={...approvalRecords[0],id:id(99),plan_id:null,founder_intake_id:null,
  plan_title:null,action:'founder:exception:'+id(99),approval_type:'governance_action',
  requires_founder_decision:true,status:'pending',reviewer_id:null,reason:null};
 approvalRecords.push(exceptional);
 await tab('Approvals');
 await page.locator('#company-approval-inbox').getByText('1 need my review',{exact:false}).waitFor({timeout:16000});
 await page.locator('#company-approval-inbox .approval-entry')
  .filter({hasText:exceptional.action})
  .getByRole('button',{name:'View approval details'}).click();
 await founderDialog.getByLabel('Mandatory decision reason').fill('Founder approves recorded exceptional request');
 await founderDialog.getByRole('button',{name:'Approve',exact:true}).click();
 await page.getByRole('status',{name:'Founder decision result'})
  .getByText('Founder approved request.',{exact:true}).waitFor();
 assert.equal(exceptional.status,'approved');
 await page.locator('#company-approval-inbox').getByText('0 need my review',{exact:false}).waitFor();
 assert.equal(await page.getByRole('status',{name:'Founder decision result'}).count(),1,
  'Founder decision result must survive notification refresh until dismissed');
 await page.getByRole('button',{name:'Dismiss Founder decision result'}).click();
 assert.equal(await page.getByRole('status',{name:'Founder decision result'}).count(),0);
 assert.deepEqual(errors,[]);
 console.log('PASS: single Founder decision, CEO handoff, lasting receipt, employee notifications and WCAG; mocked API');
}finally{await browser.close();server.close();}
