/** Browser/axe acceptance against shipped export; isolated API contract fixtures.
 * Actual signed-session/PostgreSQL journeys are a separate backend browser gate.
 */
import {test,expect} from '@playwright/test';
import axe from 'axe-core';
const tenant='10000000-0000-4000-8000-000000000001';
const user='10000000-0000-4000-8000-000000000002';
const department='10000000-0000-4000-8000-000000000003';
const other='10000000-0000-4000-8000-000000000004';
const permissions=['brain:manage','approval:decide','organization:manage','calendar:write','knowledge:write','tool:manage','council:propose','meta:manage'];
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
  await expect(page.locator('#screen .workspace-view')).toBeVisible();
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
  expect(calls.some(x=>x.path==='/v1/console/logout'&&x.auth==='Bearer browser-fixture-only-token')).toBeTruthy();
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
