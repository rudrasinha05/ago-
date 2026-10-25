import test from 'node:test';
import assert from 'node:assert/strict';
import {employeeStatus,companyLayout,activeRouteKeys,employeeProjects,boardFunctionSeats} from '../company.js';
test('missing activity stays unknown; running outranks waiting; idle is not online',()=>{
 assert.equal(employeeStatus('a',null).label,'Unknown');
 assert.equal(employeeStatus('a',[]).tone,'idle');
 assert.equal(employeeStatus('a',[{assignee_id:'a',status:'waiting_approval'}]).tone,'waiting');
 assert.equal(employeeStatus('a',[{assignee_id:'a',status:'running'},{assignee_id:'b',status:'failed'}]).tone,'busy');
});
test('map preserves manager links and places new root roles below founder',()=>{
 const result=companyLayout([{id:'d',name:'Engineering'}],[{id:'founder',department_id:'d'},{id:'cto',department_id:'d'},{id:'dev',department_id:'d',manager_id:'cto'}],'founder');
 assert.equal(result.nodes.filter(n=>n.type==='employee').length,2);
 assert.ok(result.edges.some(e=>e.from==='founder'&&e.to==='department:d'));
 assert.ok(result.edges.some(e=>e.from==='department:d'&&e.to==='employee:cto'));
 assert.ok(result.edges.some(e=>e.from==='employee:cto'&&e.to==='employee:dev'));
 assert.ok(result.nodes.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)));
});
test('cycles cannot hang layout and absent managers stay visible',()=>{
 const result=companyLayout([{id:'d'}],[{id:'a',department_id:'d',manager_id:'b'},{id:'b',department_id:'d',manager_id:'a'},{id:'c',department_id:'d',manager_id:'missing'}],'f');
 assert.equal(result.nodes.length,4);
 assert.ok(result.edges.some(e=>e.from==='department:d'&&e.to==='employee:c'));
});

test('46-person roster has separated cards and all links fit the drawing bounds',()=>{
 const departments=Array.from({length:12},(_,i)=>({id:'d'+i}));
 const people=departments.flatMap((d,i)=>Array.from({length:[3,3,6,5,3,4,4,3,4,4,3,4][i]},(_,j)=>({id:d.id+'e'+j,department_id:d.id,manager_id:j?d.id+'e0':null})));
 const map=companyLayout(departments,people,'founder');
 assert.equal(people.length,46);
 assert.equal(map.nodes.filter(n=>n.type==='employee').length,46);
 for(const a of map.nodes){assert.ok(a.x>0&&a.y>0&&a.x<map.size&&a.y<map.size);for(const b of map.nodes){if(a.key!==b.key)assert.ok(Math.abs(a.x-b.x)>210||Math.abs(a.y-b.y)>100,`${a.key} overlaps ${b.key}`);}}
});

test('assigned employees highlight entire actual reporting route; completed work clears it',()=>{
 const employees=[{id:'lead',department_id:'d'},{id:'dev',department_id:'d',manager_id:'lead'}];
 const layout=companyLayout([{id:'d'}],employees,'founder');
 const live=activeRouteKeys(layout,employees,[{assignee_id:'dev',status:'running'}]);
 assert.ok(live.routes.has('founder>department:d'));
 assert.ok(live.routes.has('department:d>employee:lead'));
 assert.ok(live.routes.has('employee:lead>employee:dev'));
 assert.equal(activeRouteKeys(layout,employees,[{assignee_id:'dev',status:'completed'}]).routes.size,0);
 assert.deepEqual(employeeProjects('dev',[{assignee_id:'dev',project_name:'Alpha'},{assignee_id:'dev',project_name:'Alpha'},{assignee_id:'dev',project_name:'Beta'}]),['Alpha','Beta']);
});
test('board functions never invent appointed directors',()=>{
 const seats=boardFunctionSeats([{name:'Engineer',id:'e'}]);
 assert.equal(seats.length,5);
 assert.ok(seats.every(s=>s.member===null));
});

test('red routes require running tasks; pending routes are amber and include departments',()=>{
 const staff=[{id:'lead',department_id:'d'},{id:'dev',department_id:'d',manager_id:'lead'}],map=companyLayout([{id:'d'}],staff,'founder');
 const pending=activeRouteKeys(map,staff,[{assignee_id:'dev',status:'waiting_approval'}]);
 assert.equal(pending.routes.size,0);
 for(const edge of ['founder>department:d','department:d>employee:lead','employee:lead>employee:dev'])assert.ok(pending.waitingRoutes.has(edge),edge);
 const mixed=activeRouteKeys(map,staff,[{assignee_id:'dev',status:'running'},{assignee_id:'lead',status:'proposed'}]);
 assert.ok(mixed.routes.has('founder>department:d'));
 assert.ok(mixed.routes.has('employee:lead>employee:dev'));
 assert.ok(!mixed.waitingRoutes.has('founder>department:d'));
 assert.ok(mixed.running.has('dev'));
 assert.equal(activeRouteKeys(map,staff,[{assignee_id:'dev',status:'completed'}]).routes.size,0);
 assert.equal(activeRouteKeys(map,staff,null).routes.size,0);
});

test('failed and blocked persisted task states are never shown as idle',()=>{
 const assigned=(status)=>[{assignee_id:'e',status}];
 assert.deepEqual([employeeStatus('e',assigned('blocked')).tone,
   employeeStatus('e',assigned('failed')).tone],['blocked','failed']);
 assert.equal(employeeStatus('e',assigned('failed')).label,'Failed work recorded');
 assert.equal(employeeStatus('e',assigned('completed')).tone,'idle');
 assert.equal(employeeStatus('e',[...assigned('running'),...assigned('failed')]).tone,'busy');
 assert.equal(employeeStatus('e',[...assigned('waiting_approval'),...assigned('failed')]).tone,'waiting');
 assert.equal(employeeStatus('e',[{assignee_id:'somebody-else',status:'failed'}]).tone,'idle');
 assert.equal(employeeStatus('e',undefined).tone,'unknown');
});


test('hierarchy graph draws recorded managers as reporting, department as grouping',()=>{
 const departments=[{id:'dA',name:'Strategy'},{id:'dB',name:'Engineering'}];
 const people=[
  {id:'ceo',name:'CEO',department_id:'dA',manager_id:'founder'},
  {id:'cto',name:'CTO',department_id:'dB',manager_id:'ceo'},
  {id:'pm',name:'PM',department_id:'dB',manager_id:'cto'},
  {id:'dev',name:'Engineer',department_id:'dB',manager_id:'pm'},
  {id:'isolated',name:'Unassigned',department_id:'dB',manager_id:null},
 ];
 const layout=companyLayout(departments,people,'founder');
 assert.equal(layout.edges.find(e=>e.to==='employee:ceo').from,'founder');
 assert.equal(layout.edges.find(e=>e.to==='employee:ceo').kind,'reporting');
 assert.equal(layout.edges.find(e=>e.to==='employee:cto').from,'employee:ceo');
 assert.equal(layout.edges.find(e=>e.to==='employee:pm').kind,'reporting');
 assert.equal(layout.edges.find(e=>e.to==='employee:dev').from,'employee:pm');
 assert.equal(layout.edges.find(e=>e.to==='employee:isolated').kind,'grouping');
 assert.equal(layout.edges.find(e=>e.to==='department:dB').from,'founder');
 assert.ok(layout.nodes.find(n=>n.key==='employee:cto').y < layout.nodes.find(n=>n.key==='employee:pm').y);
 assert.ok(layout.founder.y < layout.nodes.find(n=>n.key==='department:dA').y);
 assert.ok(layout.nodes.every(n=>n.x>0&&n.y>0&&n.x<layout.size&&n.y<layout.size));
});

test('unknown manager and cycles never draw invented employee reporting paths',()=>{
 const deps=[{id:'d',name:'Support'}];
 const staff=[
  {id:'a',name:'A',department_id:'d',manager_id:'b'},
  {id:'b',name:'B',department_id:'d',manager_id:'a'},
  {id:'c',name:'C',department_id:'d',manager_id:'missing'},
 ];
 const layout=companyLayout(deps,staff,'founder');
 assert.equal(layout.edges.filter(e=>e.kind==='reporting').length,0);
 assert.equal(layout.nodes.filter(n=>n.type==='employee').length,3);
 assert.equal(layout.edges.filter(e=>e.from==='department:d').length,3);
});

test('51 staff are laid out as a non-overlapping reporting tree',()=>{
 const deps=Array.from({length:9},(_,i)=>({id:'dept'+i,name:'Team '+i}));
 const people=deps.flatMap((dep,i)=>Array.from({length:i<6?6:5},(_,j)=>({
  id:dep.id+'-'+j,name:'Employee '+i+' '+j,department_id:dep.id,
  manager_id:j?dep.id+'-0':null,
 })));
 assert.equal(people.length,51);
 const layout=companyLayout(deps,people,'founder');
 for(const a of layout.nodes){
  for(const b of layout.nodes){
   if(a.key===b.key)continue;
   assert.ok(Math.abs(a.x-b.x)>210||Math.abs(a.y-b.y)>110,'Cards overlapping: '+a.key+' / '+b.key);
  }
 }
 assert.equal(layout.reportingEdges,42);
 assert.equal(layout.groupingEdges,18);
});
