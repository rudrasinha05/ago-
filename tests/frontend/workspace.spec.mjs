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
  // Reuse an already rendered signed-out form after page.reload()/logout().
  // WebKit on constrained CI runners can crash on a redundant same-URL
  // navigation immediately following the privacy reload; this is not
  // necessary to verify a second login or server-side session revocation.
  // All original logout, reload, privacy and sign-in assertions still run.
  const onLoginPage = new URL(page.url()).pathname === '/workspace/'
    && await page.locator('#login-form').isVisible();
  if (!onLoginPage) await page.goto('/workspace/');
  await signInHere(page,'Your organization at a glance');
}
async function signInHere(page,heading) {
  await page.getByLabel('Organization ID').fill(tenant);
  await page.getByLabel('Work email').fill('fixture@example.test');
  await page.getByLabel('Password',{exact:true}).fill('fixture-only-password');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('#screen h1')).toHaveText(heading);
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
  // The suite-wide reduced-motion setting must actually reach the page.
  expect(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
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
    // Async Company Map data may re-render/reorder conditional nav links
    // between reading nth(i) and clicking it. Select by stable href so the
    // tested destination is always the link actually activated; do not
    // weaken the hash navigation assertion or skip a browser project.
    await nav.locator('a[href="'+fragment+'"]').click();
    await expect.poll(()=>new URL(page.url()).hash,{timeout:15000}).toBe(fragment);
  }
  await expect(nav.locator('a[href="#ago-workforce"]')).toHaveCount(0);
  await expect(nav.locator('a[href="#ago-opportunities"]')).toHaveCount(0);
  // This cross-workspace link MUST be an SPA navigation: a full reload loses tab-memory auth.
  await page.getByRole('link',{name:'View GitHub operations and CI'}).click();
  await expect.poll(()=>new URL(page.url()).pathname,{timeout:15000}).toBe('/workspace/tools/');
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
  // Issue #3: sign in again on the form the reload already shows, which also
  // proves the reloaded deep link returns to Strategy. Do not navigate away
  // here: in Playwright WebKit 26.0 (build 2215) any cross-document
  // navigation after history.pushState() + reload() crashes the content
  // process, even on a static JSON page without AGO code; Chromium and
  // Firefox are unaffected. The SPA move to Strategy above is a pushState.
  await expect(page).toHaveURL(/\/workspace\/strategy\/$/);
  await signInHere(page,'Strategy & execution');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();
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

test('red routed task follows the recorded manager line and opens actual worker',async({page})=>{
 const {errors}=await fixtures(page);
 // Since d2ac902 a route is drawn only over a recorded reporting line, never
 // over department grouping, so the worker needs a real manager record.
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:other,name:'Delivery specialist',department_id:department,kind:'ai',manager_id:user}
 ]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:[
  {id:'20000000-0000-4000-8000-000000000020',assignee_id:other,action:'internal:brief',status:'running',project_name:'Real reviewed project'}
 ]}));
 await login(page);await navigate(page,'Organization');
 await expect(page.locator('.company-world line.edge-live')).toHaveCount(1);
 await expect(page.locator('.company-world line.edge-pending')).toHaveCount(0);
 await page.getByRole('button',{name:'Fit all'}).click();
 await expect(page.locator('.company-world circle.route-hit-target.running')).toHaveCount(1);
 await page.locator('.company-world circle.route-hit-target.running').last().click();
 await expect(page.locator('.employee-inspector')).toContainText('Delivery specialist');
 await expect(page.locator('.employee-inspector')).toContainText('Real reviewed project');
 expect(errors).toEqual([]);
});

test('founder can create first real governed task then separately approve and dispatch once',async({page})=>{
 const {errors}=await fixtures(page);
 const rights=['brain:read','brain:manage','organization:read','organization:manage','task:read','task:create','approval:request','approval:read','approval:decide','approval:founder','agent:dispatch','task:execute'];
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
   approval_type:'task_execution',founder_solo_mode:true,requires_founder_decision:false,review_routing:'Sole active Founder, local-only internal task'});
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

test('P1 WebGL company brain reflects persisted active task, not simulated AI thinking',async({page})=>{
  const {errors}=await fixtures(page);
  await page.route('**/v1/organization/company/activity',async route=>{
    await route.fulfill({status:200,json:[{
      id:other,status:'running',assignee_id:user,project_name:'Actual persisted test project'
    }]});
  });
  await login(page);
  await navigate(page,'Organization');
  const scene=page.locator('canvas.ago-real-3d-brain');
  await expect(scene).toBeVisible();
  await expect(scene).toHaveAttribute('aria-label',/Verified running tasks: 1/);
  await expect(page.locator('.brain-volume-active')).toHaveCount(1);
  await page.getByRole('button',{name:'Rotate brain right'}).click();
  await expect(page.locator('.brain-volume')).toHaveAttribute('style',/--brain-rotation: 15deg/);
  await expect(page.locator('.brain-work-detail')).toContainText('Actual persisted test project');
  expect(errors).toEqual([]);
});

test('company brain neurons, red routes and work signals come only from persisted records',async({page})=>{
 const {errors}=await fixtures(page);
 const lead='10000000-0000-4000-8000-000000000011',specialist='10000000-0000-4000-8000-000000000012',analyst='10000000-0000-4000-8000-000000000013';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:lead,name:'Delivery lead',department_id:department,kind:'ai',manager_id:user},
  {id:specialist,name:'Delivery specialist',department_id:department,kind:'ai',manager_id:lead},
  {id:analyst,name:'Unlinked analyst',department_id:department,kind:'ai'},
 ]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:[
  {id:'20000000-0000-4000-8000-000000000031',assignee_id:specialist,action:'internal:brief',status:'running',project_name:'Recorded delivery'},
  {id:'20000000-0000-4000-8000-000000000032',assignee_id:analyst,action:'internal:review',status:'waiting_approval',project_name:'Pending review'},
 ]}));
 await page.route(/\/v1\/organization\/company\/notifications/,route=>route.fulfill({status:200,json:{
  by_employee:{[specialist]:2},event_type:'committed_task_status',
  recent:[{id:7,employee_id:specialist,task_id:'20000000-0000-4000-8000-000000000031',body:'internal:brief → running',created_at:new Date().toISOString()}],
 }}));
 await login(page);await navigate(page,'Organization');
 const scene=page.locator('canvas.ago-real-3d-brain');
 // The Founder is the human core, not an employee neuron.
 await expect(scene).toHaveAttribute('aria-label',/Verified running tasks: 1\. Employees: 3$/);
 // Founder→lead→specialist are recorded links; the waiting analyst has no manager, so no invented route.
 await expect(page.locator('.brain-stat').filter({hasText:'Red routes'}).locator('b')).toHaveText('2');
 const signals=page.getByRole('region',{name:'Communication and work signals'});
 await expect(signals.getByRole('button',{name:/Show Delivery specialist in the company brain: internal:brief → running/})).toBeVisible();
 await page.locator('.brain-directory summary').click();
 const neurons=page.getByRole('list',{name:'Company neurons'});
 await expect(neurons.getByRole('button')).toHaveCount(3);
 await expect(neurons.locator(`[data-neuron="${specialist}"]`)).toHaveAttribute('data-tone','busy');
 await expect(neurons.locator(`[data-neuron="${specialist}"]`)).toHaveAttribute('aria-label',/on a recorded task route, 2 work signals/);
 await expect(neurons.locator(`[data-neuron="${lead}"]`)).toHaveAttribute('aria-label',/Idle, on a recorded task route$/);
 await expect(neurons.locator(`[data-neuron="${analyst}"]`)).toHaveAttribute('data-tone','waiting');
 await expect(neurons.locator(`[data-neuron="${analyst}"]`)).not.toHaveAttribute('aria-label',/recorded task route/);
 await page.getByRole('button',{name:'Working',exact:true}).click();
 await expect(neurons.getByRole('button')).toHaveCount(1);
 await page.getByRole('button',{name:'All',exact:true}).click();
 // Keyboard path: a directory neuron opens the real employee record.
 await neurons.locator(`[data-neuron="${analyst}"]`).focus();
 await page.keyboard.press('Enter');
 await expect(page.locator('.employee-inspector')).toContainText('Unlinked analyst');
 if(await page.locator('.brain-volume.webgl-active').count()){
  // Pointer path: clicking the running neuron in the 3D scene selects that employee.
  const label=page.locator(`.brain-neuron-label[data-node="${specialist}"]`);
  await expect(label).toHaveAttribute('data-x',/\d/);
  await scene.scrollIntoViewIfNeeded();
  const x=Number(await label.getAttribute('data-x')),y=Number(await label.getAttribute('data-y'));
  await scene.click({position:{x,y}});
  await expect(page.locator('.employee-inspector')).toContainText('Delivery specialist');
  await expect(label).toHaveClass(/selected/);
 }
 // Open directory, signals, legend and labels together pass WCAG 2.1 AA, no horizontal scroll.
 await accessibility(page);
 expect(errors).toEqual([]);
});

test('work notifications keep earlier events across cursor pages and never invent unread state',async({page})=>{
 const {errors,calls}=await fixtures(page);
 const worker='10000000-0000-4000-8000-000000000021';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:worker,name:'Report writer',department_id:department,kind:'ai',manager_id:user},
 ]}));
 const at=new Date().toISOString();
 let served=false;
 await page.route(/\/v1\/organization\/company\/notifications/,route=>{
  const after=new URL(route.request().url()).searchParams.get('after_id');
  if(after===null)return route.fulfill({status:200,json:{by_employee:{[worker]:2},event_type:'committed_work_event',
   recent:[{id:2,employee_id:worker,body:'Second recorded update',kind:'report',created_at:at},{id:1,employee_id:worker,body:'First recorded update',kind:'status',created_at:at}]}});
  // One new event arrives on the cursor page; earlier events are not repeated.
  const fresh=served?[]:[{id:3,employee_id:worker,body:'Third recorded update',kind:'qa',created_at:at}];served=true;
  return route.fulfill({status:200,json:{by_employee:{[worker]:3},event_type:'committed_work_event',recent:fresh}});
 });
 await login(page);await navigate(page,'Organization');
 const toggle=page.getByRole('button',{name:/^Work notifications, \d+ recorded events$/});
 await expect(toggle).toHaveAttribute('aria-label','Work notifications, 2 recorded events');
 await expect(page.locator('.notification-badge')).toHaveCount(0);
 await expect(toggle).toHaveAttribute('aria-label','Work notifications, 3 recorded events',{timeout:15000});
 await toggle.click();
 const panel=page.getByRole('region',{name:'Work notifications'});
 await expect(panel).toContainText('Unread tracking is unavailable');
 await expect(panel.getByRole('button',{name:'Mark all read'})).toHaveCount(0);
 for(const text of ['First recorded update','Second recorded update','Third recorded update'])await expect(panel).toContainText(text);
 await accessibility(page);
 await panel.getByRole('button',{name:/Report writer — Third recorded update/}).click();
 await expect(panel).toHaveCount(0);
 await expect(page.locator('.employee-inspector')).toContainText('Report writer');
 await expect(page.locator('.employee-inspector')).toContainText('First recorded update');
 expect(calls.some(c=>c.path.endsWith('/notifications/read'))).toBeFalsy();
 expect(errors).toEqual([]);
});

test('server read cursor drives unread badge and Mark all read',async({page})=>{
 const {errors}=await fixtures(page);
 const worker='10000000-0000-4000-8000-000000000022';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:worker,name:'QA reviewer',department_id:department,kind:'ai',manager_id:user},
 ]}));
 let readThrough=1;const posted=[];
 await page.route(/\/v1\/organization\/company\/notifications\/read$/,route=>{
  posted.push(route.request().postDataJSON());readThrough=posted.at(-1).through_id;
  return route.fulfill({status:200,json:{read_through_id:readThrough}});
 });
 await page.route(/\/v1\/organization\/company\/notifications(\?.*)?$/,route=>route.fulfill({status:200,json:{
  by_employee:{[worker]:2},event_type:'committed_work_event',read_through_id:readThrough,
  unread_count:readThrough>=2?0:1,unread_by_employee:{[worker]:readThrough>=2?0:1},
  recent:new URL(route.request().url()).searchParams.get('after_id')===null?[
   {id:2,employee_id:worker,body:'QA passed for stage',kind:'qa',created_at:new Date().toISOString()},
   {id:1,employee_id:worker,body:'Review started',kind:'status',created_at:new Date().toISOString()}]:[],
 }}));
 await login(page);await navigate(page,'Organization');
 const toggle=page.getByRole('button',{name:'Work notifications, 1 unread'});
 await expect(toggle).toBeVisible();
 await expect(page.locator('.notification-badge')).toHaveText('1');
 await toggle.click();
 const panel=page.getByRole('region',{name:'Work notifications'});
 await expect(panel.getByRole('button',{name:/^Unread: QA reviewer — QA passed for stage/})).toBeVisible();
 await expect(panel.getByRole('button',{name:/^QA reviewer — Review started/})).toBeVisible();
 await panel.getByRole('button',{name:'Mark all read'}).click();
 await expect.poll(()=>posted).toEqual([{through_id:2}]);
 await expect(page.getByRole('button',{name:'Work notifications, 0 unread'})).toBeVisible();
 await expect(page.locator('.notification-badge')).toHaveCount(0);
 await page.keyboard.press('Escape');
 await expect(panel).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Work notifications, 0 unread'})).toBeFocused();
 expect(errors).toEqual([]);
});

test('map views re-arrange the same recorded links: circular, tree and department lanes',async({page})=>{
 const {errors}=await fixtures(page);
 const lead='10000000-0000-4000-8000-000000000041',worker='10000000-0000-4000-8000-000000000042';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:lead,name:'Lane lead',department_id:department,kind:'ai',manager_id:user},
  {id:worker,name:'Lane worker',department_id:department,kind:'ai',manager_id:lead},
 ]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:[
  {id:'20000000-0000-4000-8000-000000000041',assignee_id:worker,action:'internal:build',status:'running',project_name:'Lane project'}]}));
 await login(page);await navigate(page,'Organization');
 const world=page.locator('.company-world'),views=page.getByRole('group',{name:'Map view'});
 await expect(views.getByRole('button',{name:'Circular'})).toHaveAttribute('aria-pressed','true');
 const count=async()=>({live:await world.locator('.company-link.edge-live').count(),links:await world.locator('.company-link').count()});
 const circular=await count();
 expect(circular.live).toBe(2); // Founder→lead and lead→worker carry the running task
 for(const [name,cls] of [['Tree','view-tree'],['Departments','view-departments'],['Circular','view-circular']]){
  await views.getByRole('button',{name}).click();
  await expect(views.getByRole('button',{name})).toHaveAttribute('aria-pressed','true');
  await expect(world).toHaveClass(new RegExp(cls));
  // Same graph in every view: no link added, removed or re-routed.
  expect(await count()).toEqual(circular);
  if(name!=='Circular')await expect(world.locator('path.company-link.edge-live')).toHaveCount(2);
 }
 await views.getByRole('button',{name:'Tree'}).click();
 await page.getByRole('button',{name:'Fit all'}).click();
 await world.locator('circle.route-hit-target.running').last().click();
 await expect(page.locator('.employee-inspector')).toContainText('Lane worker');
 expect(errors).toEqual([]);
});

test('map zooms at the pointer and pans from any point without opening the card under the drag',async({page,isMobile})=>{
 test.skip(isMobile,'Wheel and mouse-drag gestures; touch pinch is exercised manually on devices.');
 const {errors}=await fixtures(page);
 const worker='10000000-0000-4000-8000-000000000051';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:worker,name:'Pan target',department_id:department,kind:'ai',manager_id:user},
 ]}));
 await login(page);await navigate(page,'Organization');
 const canvas=page.locator('.company-canvas');await canvas.scrollIntoViewIfNeeded();
 await page.getByRole('button',{name:'All employees'}).click();
 const card=page.locator('.map-node.employee').filter({hasText:'Pan target'});
 await expect(card).toBeVisible();
 await page.waitForTimeout(300); // let the automatic fit for the new mode settle
 const zoomText=async()=>Number((await page.locator('.map-controls span').last().innerText()).match(/(\d+)%/)[1]);
 const centre=async()=>{const b=await card.boundingBox();return {x:b.x+b.width/2,y:b.y+b.height/2};};
 const before=await centre(),z0=await zoomText();
 const scrollY=await page.evaluate(()=>scrollY);
 // Fit keeps cards clear of the floating controls and legend.
 expect(await page.evaluate(([x,y])=>Boolean(document.elementFromPoint(x,y)?.closest('.map-node')),[before.x,before.y])).toBeTruthy();
 await page.mouse.move(before.x,before.y);
 await page.mouse.wheel(0,-300);
 await expect.poll(zoomText).toBeGreaterThan(z0);
 // The card under the pointer stays under the pointer and the page does not scroll.
 await expect.poll(async()=>{const a=await centre();return Math.round(Math.hypot(a.x-before.x,a.y-before.y));}).toBeLessThan(8);
 const after=await centre();
 expect(await page.evaluate(()=>scrollY)).toBe(scrollY);
 // Drag that starts ON the card pans the map and does not open the card.
 await page.mouse.move(after.x,after.y);await page.mouse.down();
 await page.mouse.move(after.x-120,after.y+60,{steps:8});await page.mouse.up();
 // Continuous pointer events may commit a frame later under load: poll the final position.
 await expect.poll(async()=>{const m=await centre();return Math.round(Math.hypot(m.x-(after.x-120),m.y-(after.y+60)));}).toBeLessThan(8);
 await expect(page.locator('.employee-inspector')).toHaveCount(0);
 // A plain click still opens it (re-fit first so no floating panel covers it).
 await page.getByRole('button',{name:'Fit all'}).click();
 await card.click();
 await expect(page.locator('.employee-inspector')).toContainText('Pan target');
 expect(errors).toEqual([]);
});

test('3D brain wheel zoom keeps the point under the cursor and Reset view restores framing',async({page,isMobile})=>{
 test.skip(isMobile,'Wheel gesture; pinch is the touch equivalent.');
 const {errors}=await fixtures(page);
 const worker='10000000-0000-4000-8000-000000000061';
 await page.route(/\/v1\/organization\/employees\?department_id=/,route=>route.fulfill({status:200,json:[
  {id:user,name:'Test member',department_id:department,kind:'human'},
  {id:worker,name:'Brain zoom worker',department_id:department,kind:'ai',manager_id:user}]}));
 await page.route('**/v1/organization/company/activity',route=>route.fulfill({status:200,json:[
  {id:'20000000-0000-4000-8000-000000000061',assignee_id:worker,action:'internal:build',status:'running',project_name:'Zoom project'}]}));
 await login(page);await navigate(page,'Organization');
 test.skip(!(await page.locator('.brain-volume.webgl-active').count()),'No WebGL in this browser: SVG fallback has no zoom.');
 const scene=page.locator('canvas.ago-real-3d-brain');await scene.scrollIntoViewIfNeeded();
 const founder=page.locator('.brain-neuron-label[data-node="founder"]'),neuron=page.locator(`.brain-neuron-label[data-node="${worker}"]`);
 await expect(neuron).toHaveAttribute('data-x',/\d/);
 const point=async l=>({x:Number(await l.getAttribute('data-x')),y:Number(await l.getAttribute('data-y'))});
 const box=await scene.boundingBox(),n0=await point(neuron),f0=await point(founder);
 const gap0=Math.hypot(n0.x-f0.x,n0.y-f0.y);
 await page.mouse.move(box.x+n0.x,box.y+n0.y);
 await page.mouse.wheel(0,-300);
 await expect.poll(async()=>{const f=await point(founder);return Math.hypot(n0.x-f.x,n0.y-f.y);}).toBeGreaterThan(gap0*1.08);
 const n1=await point(neuron);
 expect(Math.hypot(n1.x-n0.x,n1.y-n0.y)).toBeLessThan(6);
 await page.getByRole('button',{name:'Reset brain rotation'}).click();
 await expect.poll(async()=>{const f=await point(founder),n=await point(neuron);return Math.round(Math.hypot(n.x-f.x,n.y-f.y));}).toBeLessThan(gap0*1.04);
 expect(errors).toEqual([]);
});

test('3D company brain draws on demand under reduced motion and releases its GPU context',async({page})=>{
 // Issue #3: a continuous 60 fps WebGL redraw starved the main thread and
 // crashed WebKit content processes on GPU-less runners. Count real WebGL
 // calls made by the shipped page; no rendering code is mocked.
 await page.addInitScript(()=>{
  const stats={draws:0,frames:0,contexts:0,lost:0};window.__agoBrainGl=stats;
  const original=HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext=function(type,...rest){
   const gl=original.call(this,type,...rest);
   if(gl&&type==='webgl'&&!gl.__agoCounted){
    gl.__agoCounted=true;stats.contexts++;
    const drawArrays=gl.drawArrays.bind(gl);gl.drawArrays=(...args)=>{stats.draws++;return drawArrays(...args);};
    const clear=gl.clear.bind(gl);gl.clear=(...args)=>{stats.frames++;return clear(...args);};
    const getExtension=gl.getExtension.bind(gl);
    gl.getExtension=name=>{const ext=getExtension(name);
     if(ext&&name==='WEBGL_lose_context'){const lose=ext.loseContext.bind(ext);return {...ext,loseContext:()=>{stats.lost++;return lose();},restoreContext:ext.restoreContext.bind(ext)};}
     return ext;};
   }
   return gl;
  };
 });
 // Set explicitly: this test is about the reduced-motion contract itself.
 await page.emulateMedia({reducedMotion:'reduce'});
 const {errors}=await fixtures(page);
 await login(page);await navigate(page,'Organization');
 await expect(page.locator('.ago-real-3d-brain')).toBeVisible();
 expect(await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)).toBeTruthy();
 await page.waitForTimeout(800);
 const settled=await page.evaluate(()=>({...window.__agoBrainGl}));
 await page.waitForTimeout(1500);
 const later=await page.evaluate(()=>({...window.__agoBrainGl}));
 // Without WebGL the keyboard-accessible SVG fallback is used and nothing is drawn.
 expect(later.draws).toBe(settled.draws);
 if(settled.contexts>0){
  expect(settled.draws).toBeGreaterThan(0);
  await navigate(page,'Overview');
  await expect.poll(()=>page.evaluate(()=>window.__agoBrainGl.lost)).toBe(settled.contexts);
 }
 expect(errors).toEqual([]);
});

test('3D company brain idle motion is throttled when motion is allowed',async({page})=>{
 // Decorative sway only: it must stay far below a 60 fps loop.
 await page.addInitScript(()=>{
  const stats={draws:0,frames:0,contexts:0,lost:0};window.__agoBrainGl=stats;
  const original=HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext=function(type,...rest){
   const gl=original.call(this,type,...rest);
   if(gl&&type==='webgl'&&!gl.__agoCounted){
    gl.__agoCounted=true;stats.contexts++;
    const drawArrays=gl.drawArrays.bind(gl);gl.drawArrays=(...args)=>{stats.draws++;return drawArrays(...args);};
    const clear=gl.clear.bind(gl);gl.clear=(...args)=>{stats.frames++;return clear(...args);};
    const getExtension=gl.getExtension.bind(gl);
    gl.getExtension=name=>{const ext=getExtension(name);
     if(ext&&name==='WEBGL_lose_context'){const lose=ext.loseContext.bind(ext);return {...ext,loseContext:()=>{stats.lost++;return lose();},restoreContext:ext.restoreContext.bind(ext)};}
     return ext;};
   }
   return gl;
  };
 });
 await page.emulateMedia({reducedMotion:'no-preference'});
 const {errors}=await fixtures(page);
 await login(page);await navigate(page,'Organization');
 await expect(page.locator('.ago-real-3d-brain')).toBeVisible();
 // Off-screen the scene does not animate at all (phone layouts start below it).
 await page.locator('.ago-real-3d-brain').scrollIntoViewIfNeeded();
 await page.waitForTimeout(500);
 const before=await page.evaluate(()=>window.__agoBrainGl.frames);
 await page.waitForTimeout(1500);
 const drawn=await page.evaluate(()=>window.__agoBrainGl.frames)-before;
 if(await page.evaluate(()=>window.__agoBrainGl.contexts)>0){
  expect(drawn).toBeGreaterThan(0);
  // A frame is one clear() followed by the cortex, link and neuron passes.
  // >=66 ms between idle frames allows at most ~22 frames in 1.5 s on any
  // machine. An unthrottled loop draws ~90 at 60 fps; on a slow software
  // renderer it may also stay low, so this is an upper-bound guard only.
  expect(drawn).toBeLessThanOrEqual(25);
 } else expect(drawn).toBe(0);
 expect(errors).toEqual([]);
});

test('Inspect evidence loads exact source bytes for the Founder only from the audited item endpoint',async({page})=>{
 // Contract: GET /v1/operations/enterprise/evidence stays redacted; GET
 // /v1/operations/enterprise/evidence/{id} is Founder-only (JARVIS, 180e0f8).
 const evidenceId='40000000-0000-4000-8000-000000000041';
 const source='Inspect this exact prompt <script>window.xss=true</script>';
 const listed={id:evidenceId,kind:'quality_subject',operation_key:'subject',created_at:'2026-10-25T10:00:00Z',digest:'d'.repeat(64),
  payload:{dimension:'prompt',content_digest:'c'.repeat(64),content_bytes:source.length,content_withheld:true}};
 const exact={...listed,payload:{dimension:'prompt',content_digest:'c'.repeat(64),content_bytes:source.length,
  content_base64:Buffer.from(source).toString('base64')}};
 async function prepare(roles){
  const {calls,errors}=await fixtures(page);
  await page.route('**/v1/console/me',route=>route.fulfill({status:200,json:{id:user,tenant_id:tenant,display_name:'Test member',roles,permissions:[...permissions,'operations:read']}}));
  await page.route('**/v1/operations/enterprise/evidence',route=>route.fulfill({status:200,json:[listed]}));
  await page.route('**/v1/operations/enterprise/evidence/*',route=>{calls.push({path:new URL(route.request().url()).pathname,auth:route.request().headers().authorization});
   return route.fulfill({status:200,json:exact});});
  return {calls,errors};
 }
 let {calls,errors}=await prepare(['founder']);
 await login(page);await navigate(page,'Operations & Tools');
 await page.locator('tr').filter({hasText:'quality_subject'}).getByRole('button',{name:'Inspect evidence',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText(source);
 await expect(page.getByRole('dialog').locator('script')).toHaveCount(0);
 expect(await page.evaluate(()=>window.xss)).toBeUndefined();
 const itemCalls=calls.filter(c=>c.path==='/v1/operations/enterprise/evidence/'+evidenceId);
 expect(itemCalls).toHaveLength(1);expect(itemCalls[0].auth).toBe('Bearer browser-fixture-only-token');
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toBeHidden();
 expect(errors).toEqual([]);
 // A manager with organization:manage but no Founder role gets the redacted record and no item request.
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();
 await page.unroute('**/v1/**');await page.unroute('**/v1/console/me');
 await page.unroute('**/v1/operations/enterprise/evidence');await page.unroute('**/v1/operations/enterprise/evidence/*');
 ({calls,errors}=await prepare(['manager']));
 await login(page);await navigate(page,'Operations & Tools');
 await page.locator('tr').filter({hasText:'quality_subject'}).getByRole('button',{name:'Inspect evidence',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('content_withheld');
 await expect(page.getByRole('dialog')).not.toContainText('Inspect this exact prompt');
 expect(calls.some(c=>c.path.startsWith('/v1/operations/enterprise/evidence/'))).toBeFalsy();
 expect(errors).toEqual([]);
});
