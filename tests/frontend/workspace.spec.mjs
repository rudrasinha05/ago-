/** Browser/axe acceptance against shipped export; isolated API contract fixtures.
 * Actual signed-session/PostgreSQL journeys are a separate backend browser gate.
 */
import {test,expect} from '@playwright/test';
import axe from 'axe-core';
const tenant='10000000-0000-4000-8000-000000000001';
const user='10000000-0000-4000-8000-000000000002';
const department='10000000-0000-4000-8000-000000000003';
const other='10000000-0000-4000-8000-000000000004';
const permissions=['brain:manage','approval:decide','organization:manage','calendar:write','knowledge:write','tool:manage','council:propose','meta:manage','meta:simulate'];
async function fixtures(page,{reviewer=false}={}) {
  const calls=[],errors=[],goals=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/v1/**',async route=>{
    const request=route.request(), url=new URL(request.url());calls.push({path:url.pathname,method:request.method(),auth:request.headers().authorization,body:request.postDataJSON()});
    let data=[];
    if(url.pathname==='/v1/sessions')data={access_token:'browser-fixture-only-token'};
    else if(url.pathname==='/v1/console/me')data={id:user,tenant_id:tenant,display_name:'Test member',roles:[reviewer?'reviewer':'founder'],permissions:reviewer?['approval:decide']:permissions};
    else if(reviewer&&url.pathname==='/v1/organization/departments')return route.fulfill({status:403,json:{detail:'Forbidden'}});
    else if(url.pathname==='/v1/insights/scorecard')data={counts:{tasks:2,agent_runs:0},virtual_credit_budget:{remaining:100}};
    else if(url.pathname==='/v1/tasks')data=[{id:user,action:'My evidence brief',status:'proposed',assignee_id:user},{id:other,action:'Other member task',status:'completed',assignee_id:other}];
    else if(url.pathname==='/v1/meta/brief')data={};
    else if(url.pathname==='/v1/meta/dna/active')data={profile:{qa_target_pct:85,backlog_limit:50,budget_alert_pct:80}};
    else if(url.pathname==='/v1/organization/company/chat')data={items:[],next_before:null};
    else if(url.pathname==='/v1/organization/departments')data=[{id:department,name:'Research'}];
    else if(url.pathname==='/v1/organization/employees')data=[{id:user,name:'Test member',department_id:department,kind:'human'}];
    else if(url.pathname==='/v1/brain/goals'){if(request.method()==='POST')goals.push({id:other,status:'active',...request.postDataJSON()});data=request.method()==='POST'?goals.at(-1):goals;}
    else if(url.pathname==='/v1/operations/calendar')data=[{id:other,title:'Evidence review',status:'scheduled',starts_at:'2026-10-10T10:00:00Z',ends_at:'2026-10-10T11:00:00Z'}];
    else if(url.pathname==='/v1/knowledge/nodes')data=[{id:other,label:'<img src=x onerror="window.xss=true">',statement:'Untrusted evidence is displayed as text',source_ref:'test-only'}];
    await route.fulfill({status:200,json:data});
  });
  return {calls,errors};
}
async function login(page) {
  await page.goto('/workspace/');
  await page.getByLabel('Organization ID').fill(tenant);
  await page.getByLabel('Work email').fill('fixture@example.test');
  await page.getByLabel('Password',{exact:true}).fill('fixture-only-password');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('#screen h1')).toHaveText('Your organization at a glance');
}
async function navigate(page,label) {
  if(await page.getByRole('button',{name:'Menu',exact:true}).isVisible())await page.getByRole('button',{name:'Menu',exact:true}).click();
  await page.getByRole('navigation',{name:'Workspaces'}).getByRole('link',{name:label,exact:true}).click();
  await expect(page.locator(label==='Organization'?'#screen .company-command':'#screen .workspace-view')).toBeVisible();
}
async function accessibility(page) {
  await page.evaluate(axe.source);
  const violations=await page.evaluate(async()=> (await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)})));
  expect(violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
}
test('eight routes, responsive layout and WCAG AA scans',async({page})=>{
  const {errors}=await fixtures(page);await page.goto('/workspace/');await accessibility(page);await login(page);await page.screenshot({path:test.info().outputPath("overview.png"),fullPage:true});
  for(const label of ['Overview','Strategy','Governance','Organization','Knowledge','Operations & Tools','Calendar','Digital Twin']){await navigate(page,label);await accessibility(page);}
  await expect(page.locator('#screen')).toContainText('Simulation only.');expect(errors).toEqual([]);
  expect(await page.evaluate(()=>window.xss)).toBeUndefined();
});
test('Control Center redirects to authenticated Company Map and internal links preserve session',async({page})=>{
  const {errors}=await fixtures(page);
  for(const oldEntry of ['/console','/console/']){
    await page.goto(oldEntry);
    await expect.poll(()=>new URL(page.url()).pathname).toBe('/workspace/organization/');
    await expect(page.locator('#login-form')).toBeVisible();
  }
  await page.getByLabel('Organization ID').fill(tenant);
  await page.getByLabel('Work email').fill('fixture@example.test');
  await page.getByLabel('Password',{exact:true}).fill('fixture-only-password');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Company map',exact:true})).toBeVisible();
  await expect(page.locator('.company-command')).toBeVisible();
  await expect(page.getByText('People & departments',{exact:true})).toHaveCount(0);
  // Only advertise fragments that exist for this signed-in role.
  const nav=page.getByRole('navigation',{name:'Company control center sections'});
  const links=nav.locator('a[href^="#"]');
  for(let i=0;i<await links.count();i++){
    const fragment=await links.nth(i).getAttribute('href');
    await expect(page.locator(fragment)).toHaveCount(1);
    await links.nth(i).click();
    await expect.poll(()=>new URL(page.url()).hash).toBe(fragment);
  }
  await expect(nav.locator('a[href="#ago-workforce"]')).toHaveCount(0);
  await expect(nav.locator('a[href="#ago-opportunities"]')).toHaveCount(0);
  // This cross-workspace link MUST be an SPA navigation: a full reload loses tab-memory auth.
  await page.getByRole('link',{name:'View GitHub operations and CI'}).click();
  await expect.poll(()=>new URL(page.url()).pathname).toBe('/workspace/tools/');
  await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();
  await expect(page.locator('#login-form')).toHaveCount(0);
  await navigate(page,'Organization');
  await expect(page.getByRole('heading',{name:'Company map',exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});
test('dashboards use personal and department assignments; denial is explicit',async({page})=>{
  await fixtures(page);await login(page);
  await page.getByRole('button',{name:'Employee dashboard',exact:true}).click();
  const panel=page.getByRole('heading',{name:'Employee dashboard',exact:true}).locator('..').locator('..');
  await expect(panel).toContainText('My evidence brief');await expect(panel).not.toContainText('Other member task');
  await page.getByRole('button',{name:'Department dashboard',exact:true}).click();
  await expect(page.getByLabel('Department',{exact:true})).toBeVisible();
  await expect(page.locator('.role-dashboard')).toContainText('Research');await accessibility(page);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();
  await page.unroute('**/v1/**');await fixtures(page,{reviewer:true});await login(page);
  await page.getByRole('button',{name:'Department dashboard',exact:true}).click();
  await expect(page.locator('.role-dashboard')).toContainText('Departments unavailable to your role');
  await navigate(page,'Strategy');await expect(page.getByRole('button',{name:'New goal'})).toHaveCount(0);
});
test('keyboard dialog, escaped mutations, logout and reload privacy',async({page})=>{
  const {calls}=await fixtures(page);await login(page);await navigate(page,'Strategy');
  const create=page.getByRole('button',{name:'New goal',exact:true});await create.focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();await accessibility(page);
  await page.getByLabel('Goal title',{exact:true}).fill('Keyboard evidence <script>window.xss=true</script>');
  await page.getByLabel('Context',{exact:true}).fill('No implicit approvals');
  await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toBeHidden();
  await create.click();await page.getByLabel('Goal title',{exact:true}).fill('Keyboard evidence <script>window.xss=true</script>');
  await page.getByLabel('Context',{exact:true}).fill('No implicit approvals');await page.locator('#operation-submit').click();
  await expect(page.getByRole('dialog')).toBeHidden();await expect(page.locator('#screen')).toContainText('Keyboard evidence <script>');
  expect(await page.evaluate(()=>window.xss)).toBeUndefined();
  expect(calls.find(x=>x.path==='/v1/brain/goals'&&x.method==='POST').auth).toBe('Bearer browser-fixture-only-token');
  await page.reload();await expect(page.locator('#login-form')).toBeVisible();
  expect(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length}))).toEqual({local:0,session:0});
  await login(page);await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();
  await expect.poll(()=>calls.some(x=>x.path==='/v1/console/logout'&&x.auth==='Bearer browser-fixture-only-token')).toBeTruthy();
});
test('direct route refresh, expired session and failed resource isolation',async({page})=>{
  await fixtures(page);await page.goto('/workspace/strategy/');await expect(page.locator('#login-form')).toBeVisible();
  await page.getByLabel('Organization ID').fill(tenant);await page.getByLabel('Work email').fill('fixture@example.test');await page.getByLabel('Password',{exact:true}).fill('fixture-only-password');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('#screen h1')).toHaveText('Strategy & execution');
  await page.route('**/v1/tasks',route=>route.fulfill({status:403,json:{detail:'Forbidden'}}));
  await navigate(page,'Overview');await expect(page.locator('#screen')).toContainText('Not available to your role');await expect(page.locator('#screen')).toContainText('2');
  await page.route('**/v1/insights/scorecard',route=>route.fulfill({status:401,json:{detail:'Expired'}}));
  await page.getByRole('button',{name:'Refresh',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();await expect(page.locator('#login-form [role=alert]')).toContainText('session expired');
});
test('hypothetical thresholds reach simulation without applying live policy',async({page})=>{
  const {calls}=await fixtures(page);
  await page.route('**/v1/meta/snapshots',route=>route.fulfill({status:200,json:[{id:other,created_at:'2026-10-10T10:00:00Z',fitness:null,digest:'test-only',risk_flags:['insufficient_data']}]}));
  await page.route('**/v1/meta/simulate',route=>{
    calls.push({path:'/v1/meta/simulate',method:'POST',body:route.request().postDataJSON()});
    return route.fulfill({status:200,json:{assessment:{fitness:null,risk_flags:['insufficient_data']}}});
  });
  await login(page);await navigate(page,'Digital Twin');
  await page.locator('#range-qa_target_pct').evaluate(node=>{node.value='90';node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));});
  await expect(page.locator('#output-qa_target_pct')).toHaveText('90%');
  await page.getByRole('button',{name:'Run comparison',exact:true}).click();
  await expect(page.locator('.workspace-announcement')).toContainText('No changes were applied');
  expect(calls.find(x=>x.path==='/v1/meta/simulate').body.profile.qa_target_pct).toBe(90);
  expect(calls.some(x=>x.method==='POST'&&x.path.includes('/dna'))).toBeFalsy();
  await accessibility(page);
});

test('red routed task follows founder, department and employee and opens actual worker',async({page})=>{
 const {errors}=await fixtures(page);
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:other,name:'Delivery specialist',department_id:department,kind:'ai'}
 ]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:[
  {id:'20000000-0000-4000-8000-000000000020',assignee_id:other,action:'internal:brief',status:'running',project_name:'Real reviewed project'}
 ]}));
 await login(page);await navigate(page,'Organization');
 await expect(page.locator('.company-world line.edge-live')).toHaveCount(2);
 await expect(page.locator('.company-world line.edge-pending')).toHaveCount(0);
 await page.getByRole('button',{name:'Fit all'}).click();
 await expect(page.locator('.company-world circle.route-hit-target.running')).toHaveCount(2);
 await page.locator('.company-world circle.route-hit-target.running').last().click();
 await expect(page.locator('.employee-inspector')).toContainText('Delivery specialist');
 await expect(page.locator('.employee-inspector')).toContainText('Real reviewed project');
 expect(errors).toEqual([]);
});

test('founder can create first real governed task then separately approve and dispatch once',async({page})=>{
 const {errors}=await fixtures(page);
 const rights=['brain:read','organization:read','task:read','task:create','approval:request','approval:read','approval:decide','agent:dispatch','task:execute'];
 const realTaskId='30000000-0000-4000-8000-000000000011';
 const approvalId='30000000-0000-4000-8000-000000000012';
 const tasks=[],approvals=[];
 let dispatched=0,proposed=0;
 await page.route('**/v1/console/me',route=>route.fulfill({status:200,json:{
   id:user,tenant_id:tenant,display_name:'Founder',roles:['founder'],permissions:rights
 }}));
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Founder',department_id:department,kind:'human'},
  {id:other,name:'Research specialist',department_id:department,kind:'ai'}
 ]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:tasks}));
 await page.route('**/v1/organization/company/approvals',route=>route.fulfill({status:200,json:approvals}));
 await page.route('**/v1/tasks',route=>{
  if(route.request().method()!=='POST')return route.fulfill({status:200,json:tasks});
  proposed++;
  const body=route.request().postDataJSON();
  expect(body).toEqual({action:'internal:brief',assignee_id:other});
  const task={id:realTaskId,action:body.action,assignee_id:body.assignee_id,status:'proposed'};
  tasks.push(task);
  return route.fulfill({status:200,json:task});
 });
 await page.route('**/v1/console/tasks/*/request-approval',route=>{
  expect(route.request().method()).toBe('POST');
  tasks[0].status='waiting_approval';tasks[0].approval_id=approvalId;
  approvals.push({id:approvalId,action:'internal:brief',status:'pending',requester_id:user,requester_name:'Founder',
   task_id:realTaskId,task_action:'internal:brief',task_assignee_name:'Research specialist',
   approval_type:'task_execution',founder_solo_mode:true,review_routing:'Explicit local founder review'});
  return route.fulfill({status:200,json:{approval_id:approvalId,status:'waiting_approval'}});
 });
 await page.route('**/v1/governance/approvals/*/decision',route=>{
  expect(route.request().postDataJSON()).toMatchObject({approve:true});
  approvals[0].status='approved';
  return route.fulfill({status:200,json:{status:'approved'}});
 });
 await page.route('**/v1/agents/tasks/*/run',route=>{
  dispatched++;
  tasks[0].status='completed';
  return route.fulfill({status:200,json:{task_id:realTaskId,status:'completed'}});
 });
 await login(page);await navigate(page,'Organization');
 await page.getByRole('button',{name:'Set up first task'}).click();
 await expect(page.getByLabel('First approved AI work setup')).toBeVisible();
 await expect(page.getByLabel('AI employee')).toHaveValue(other);
 await expect(page.getByLabel('First-run task type')).toHaveValue('internal:brief');
 await page.getByRole('button',{name:'Create proposed task (no execution)'}).click();
 await expect(page.getByText('Proposed task recorded:',{exact:false})).toContainText(realTaskId);
 await expect(page.getByRole('button',{name:'Request approval',exact:true})).toBeVisible();
 expect(proposed).toBe(1);expect(dispatched).toBe(0);
 await page.getByRole('button',{name:'Request approval',exact:true}).click();
 await expect.poll(()=>approvals.length).toBe(1);
 expect(dispatched).toBe(0);
 await page.locator('#company-approval-inbox').getByRole('button',{name:'View approval details'}).click();
 await page.getByLabel('Mandatory decision reason').fill('Authorized local isolated brief validation');
 await page.getByRole('button',{name:'Approve',exact:true}).click();
 await expect.poll(()=>approvals[0].status).toBe('approved');
 await expect(page.getByRole('button',{name:'Run approved AI'})).toBeVisible();
 expect(dispatched).toBe(0);
 await page.getByRole('button',{name:'Run approved AI'}).click();
 await expect.poll(()=>dispatched).toBe(1);
 await expect(page.locator('#ago-execution-desk')).toContainText('Needs QA');
 expect(errors).toEqual([]);
});
