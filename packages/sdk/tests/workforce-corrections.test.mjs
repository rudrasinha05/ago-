import test from 'node:test';
import assert from 'node:assert/strict';
import {areaFor,buildWorkforceCorrections} from '../workforce-corrections.js';
import {buildCompanyRolePlan} from '../company-roles.js';

// The Founder's real roster (2026-11-24): 46 workers + 5 Board seats.
const NAMES=['Data Analyst','Data Engineer','Knowledge Curator','Knowledge Manager','Design Manager','UI Designer','UX Researcher',
 'Backend Developer','Engineering Manager','Frontend Developer','Integration Engineer','Mobile Developer','Software Architect',
 'Cost Analyst','Finance Analyst','Operations Manager','Resource Planner','Build Engineer','DevOps Manager','Infrastructure Engineer',
 'Release Coordinator','Content Specialist','Customer Success Specialist','Market Researcher','Marketing Manager','Learning Coordinator',
 'People Manager','Skills Analyst','Delivery Coordinator','Project Manager','Requirements Analyst','Accessibility Tester',
 'Automation Tester','QA Manager','Test Engineer','AI Engineer','Experiment Analyst','Research Manager','Research Scientist',
 'Technical Writer','Compliance Analyst','Security Analyst','Security Manager','Business Analyst','Strategic Planner','Strategy Manager'];
const SEATS=[['Strategy & Vision','ceo','AGO AI CEO'],['Technology Oversight','cto','AGO AI CTO'],['Finance & Budget','cfo','AGO AI CFO'],
 ['Risk & Compliance','ciso','AGO AI CISO'],['Quality & Release','cqo','AGO AI CQO']];
const id=name=>name.toLowerCase().replace(/[^a-z]+/g,'-');
function company(){
 const board=SEATS.map(([seat,eid])=>({seat,employee_id:eid}));
 const employees=[{id:'founder',name:'Rudra',kind:'human'},
  ...SEATS.map(([,eid,name])=>({id:eid,name,kind:'ai',manager_id:eid==='ceo'?'founder':'ceo'})),
  // The scrambled live state: everybody under the CEO, titles by position.
  ...NAMES.map(n=>({id:id(n),name:n,kind:'ai',manager_id:'ceo'}))];
 const profiles=[...SEATS.map(([,eid])=>({id:eid,role_title:'Chief '+eid,core_responsibilities:'Board'})),
  {id:'ai-engineer',role_title:'Research Director',core_responsibilities:'Research governance'},
  {id:'accessibility-tester',role_title:'QA Manager',core_responsibilities:'x'},
  {id:'business-analyst',role_title:'Chief of Staff',core_responsibilities:'x'},
  {id:'project-manager',role_title:'Project Manager',core_responsibilities:'Project accountability'},
  {id:'qa-manager',role_title:'QA Manager',core_responsibilities:'Independent QA'}];
 return {employees,profiles,board,founderId:'founder'};
}

test('every live employee name lands in a real area',()=>{
 for(const n of NAMES)assert.ok(areaFor(n),n);
 assert.equal(areaFor('Test Engineer').key,'qa');
 assert.equal(areaFor('Market Researcher').key,'marketing');
 assert.equal(areaFor('Strategic Planner').key,'strategy');
 assert.equal(areaFor('UX Researcher').key,'design');
});

test('designations follow the name; Board titles and the Project Manager title are kept',()=>{
 const {rows}=buildWorkforceCorrections(company());
 const row=n=>rows.find(r=>r.name===n);
 assert.equal(row('AI Engineer').proposed_title,'AI Engineer');
 assert.match(row('AI Engineer').proposed_core,/Source code, unit tests/);
 assert.equal(row('Accessibility Tester').proposed_title,'Accessibility Tester');
 assert.equal(row('Business Analyst').proposed_title,'Business Analyst');
 assert.ok(!row('QA Manager').changes.includes('designation'));
 assert.ok(!row('Project Manager')?.changes.includes('designation'));
 assert.ok(rows.every(r=>!['ceo','cto','cfo','ciso','cqo'].includes(r.id)||!r.changes.includes('designation')));
});

test('hierarchy is Founder → CEO → leadership → department heads → employees, not everyone under the CEO',()=>{
 const c=company();
 const {rows,notes}=buildWorkforceCorrections(c);
 const to=n=>rows.find(r=>r.name===n)?.proposed_manager_id;
 assert.equal(to('QA Manager'),'cqo');
 assert.equal(to('Accessibility Tester'),'qa-manager');
 assert.equal(to('Test Engineer'),'qa-manager');
 assert.equal(to('Engineering Manager'),'cto');
 assert.equal(to('AI Engineer'),'engineering-manager');
 assert.equal(to('Security Analyst'),'security-manager');
 assert.equal(to('Security Manager'),'ciso');
 assert.equal(to('Cost Analyst'),'cfo');                 // finance has no head: its Board leader
 assert.equal(to('Data Engineer'),'cto');
 assert.equal(to('Project Manager'),undefined);          // already reports to the CEO, as AGO requires
 assert.equal(to('Delivery Coordinator'),'project-manager');
 assert.equal(to('Strategic Planner'),'strategy-manager');
 assert.ok(notes.some(n=>/Data & Analytics has 2 employees but no head/.test(n)));
 // Nobody is moved under the CEO except heads of CEO-led areas.
 const underCeo=rows.filter(r=>r.changes.includes('reporting')&&r.proposed_manager_id==='ceo').map(r=>r.name).sort();
 assert.deepEqual(underCeo,[]);                         // CEO-led heads already report to the CEO
 const after=new Map(c.employees.map(e=>[e.id,rows.find(r=>r.id===e.id)?.proposed_manager_id??e.manager_id]));
 const ceoReports=[...after].filter(([eid,m])=>m==='ceo').map(([eid])=>eid).sort();
 assert.deepEqual(ceoReports,['cfo','ciso','cqo','cto','knowledge-manager','marketing-manager','operations-manager',
  'people-manager','project-manager','strategy-manager']);
 // Tree order: heads are approved before the people who will report to them.
 const order=rows.map(r=>r.name);
 assert.ok(order.indexOf('QA Manager')<order.indexOf('Test Engineer'));
});

test('a proposal changes nothing that is already right, and needs an appointed CEO',()=>{
 const c=company();
 const {rows}=buildWorkforceCorrections(c);
 const fixed=c.employees.map(e=>{const r=rows.find(x=>x.id===e.id);return r?{...e,manager_id:r.proposed_manager_id}:e;});
 const profiles=c.profiles.filter(p=>!rows.some(r=>r.id===p.id)).concat(rows.map(r=>({id:r.id,role_title:r.proposed_title,core_responsibilities:r.proposed_core})));
 assert.deepEqual(buildWorkforceCorrections({...c,employees:fixed,profiles}).rows,[]);
 const noCeo=buildWorkforceCorrections({...c,board:[]});
 assert.equal(noCeo.rows.length,0);assert.match(noCeo.notes[0],/Appoint the CEO first/);
});

test('the role planner no longer hands out titles by position',()=>{
 const plan=buildCompanyRolePlan([{id:'x',name:'AI Engineer',kind:'ai',department_id:'r'},{id:'y',name:'Agent 1',kind:'ai',department_id:'r'}],
  [{id:'r',name:'Research & Innovation'}],[],'founder');
 assert.equal(plan.find(p=>p.id==='x').role_title,'AI Engineer');
 assert.match(plan.find(p=>p.id==='x').core_responsibilities,/Source code/);
 assert.equal(plan.find(p=>p.id==='y').role_title,'Research Director');  // a name that says nothing keeps the old fallback
});
