import test from 'node:test';
import assert from 'node:assert/strict';
import {departmentBlueprint,buildCompanyRolePlan,buildLeadershipPlan} from '../company-roles.js';
test('department expertise gives distinct software, security, QA, commercial and people work',()=>{
 for(const name of ['Engineering','Cyber Security','Quality Assurance','Growth & Sales','Finance','People Operations','Research','Platform']){
  const b=departmentBlueprint(name);assert.notEqual(b.name,'Unclassified Department',name);
  assert.ok(b.roles.length>=4);
  assert.ok(b.roles.every(x=>x.title&&x.focus&&x.deliverable));
 }
});
test('every real nonfounder employee receives scoped draft without inventing people or board privileges',()=>{
 const deps=[{id:'d',name:'Engineering'}];
 const people=[{id:'f',name:'Founder',department_id:'d'},{id:'1',name:'A',kind:'ai',department_id:'d'},{id:'2',name:'B',kind:'ai',department_id:'d'}];
 const p=buildCompanyRolePlan(people,deps,[],'f');
 assert.equal(p.length,2);assert.notEqual(p[0].role_title,p[1].role_title);
 assert.ok(p.every(x=>x.status==='proposed'&&x.core_responsibilities.includes('Expected deliverable')));
 assert.ok(p.every(x=>x.extra_responsibilities.includes('not a verified skill assessment')));
});
test('existing company records and founder-entered job titles remain intact',()=>{
 const employees=[{id:'a',name:'Architect',kind:'ai',department_id:'d'},{id:'b',name:'Engineer',kind:'ai',department_id:'d'}];
 const profiles=[{id:'a',role_title:'Security Reviewer',core_responsibilities:'Personally assigned exact security reviews',extra_responsibilities:'Existing duties'},{id:'b',role_title:'Senior Engineer',core_responsibilities:'',extra_responsibilities:''}];
 const plan=buildCompanyRolePlan(employees,[{id:'d',name:'Engineering'}],profiles,'founder');
 assert.equal(plan[0].status,'configured');assert.equal(plan[0].core_responsibilities,'Personally assigned exact security reviews');
 assert.equal(plan[1].role_title,'Senior Engineer');assert.equal(plan[1].status,'proposed');
});
test('46 real members are all covered across unknown and classified teams with stable assignment',()=>{
 const deps=Array.from({length:12},(_,i)=>({id:'d'+i,name:i===0?'Engineering':i===1?'Security':i===2?'Quality':'Team '+i}));
 const people=deps.flatMap((d,i)=>Array.from({length:[3,3,6,5,3,4,4,3,4,4,3,4][i]},(_,j)=>({id:d.id+'e'+j,name:'Person '+i+' '+j,department_id:d.id,kind:'ai'})));
 const first=buildCompanyRolePlan(people,deps,[],'founder');
 assert.equal(first.length,46);
 assert.deepEqual(first,buildCompanyRolePlan([...people].reverse(),deps,[],'founder'));
 assert.ok(first.some(x=>x.department==='Team 3'));
});

test('CEO CTO CFO CISO CQO seats use real distinct AI members',()=>{
 const staff=['CEO','CTO','Finance','Security','Quality'].map((name,i)=>({id:String(i),name,kind:'ai'}));
 const rows=buildLeadershipPlan([{id:'owner',name:'Founder',kind:'human'},...staff],[],[],'owner');
 assert.deepEqual(rows.map(x=>x.employee_id),['0','1','2','3','4']);
 assert.equal(new Set(rows.map(x=>x.employee_id)).size,5);
 assert.deepEqual(buildLeadershipPlan([staff[0]],[],[],'owner').filter(x=>!x.employee_id).length,4);
});

test('board uses recorded department expertise before inventing executive skills',()=>{
 const deps=[{id:'executive',name:'Executive Office'},{id:'engineering',name:'Engineering'},
  {id:'finance',name:'Finance'},{id:'security',name:'Cyber Security'},
  {id:'quality',name:'Quality Assurance'}];
 const people=deps.map((d,i)=>({id:'ai'+i,name:'Agent '+i,kind:'ai',department_id:d.id}));
 const board=buildLeadershipPlan(people,[],[],'founder',deps);
 assert.deepEqual(board.map(x=>x.employee_id),['ai0','ai1','ai2','ai3','ai4']);
 assert.ok(board.every(x=>!x.existing));
 const noEvidence=buildLeadershipPlan([{id:'g',kind:'ai',name:'Generic Agent',department_id:'unknown'}],[],[],'founder',deps);
 assert.equal(noEvidence.filter(x=>!x.employee_id).length,5);
});
