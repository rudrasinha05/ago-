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
 assert.ok(result.edges.some(e=>e.from==='founder'&&e.to==='employee:cto'));
 assert.ok(result.edges.some(e=>e.from==='employee:cto'&&e.to==='employee:dev'));
 assert.ok(result.nodes.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)));
});
test('cycles cannot hang layout and absent managers stay visible',()=>{
 const result=companyLayout([{id:'d'}],[{id:'a',department_id:'d',manager_id:'b'},{id:'b',department_id:'d',manager_id:'a'},{id:'c',department_id:'d',manager_id:'missing'}],'f');
 assert.equal(result.nodes.length,4);
 assert.ok(result.edges.some(e=>e.from==='founder'&&e.to==='employee:c'));
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
 assert.ok(live.routes.has('founder>employee:lead'));
 assert.ok(live.routes.has('employee:lead>employee:dev'));
 assert.equal(activeRouteKeys(layout,employees,[{assignee_id:'dev',status:'completed'}]).routes.size,0);
 assert.deepEqual(employeeProjects('dev',[{assignee_id:'dev',project_name:'Alpha'},{assignee_id:'dev',project_name:'Alpha'},{assignee_id:'dev',project_name:'Beta'}]),['Alpha','Beta']);
});
test('board functions never invent appointed directors',()=>{
 const seats=boardFunctionSeats([{name:'Engineer',id:'e'}]);
 assert.equal(seats.length,5);
 assert.ok(seats.every(s=>s.member===null));
});
