import test from 'node:test';
import assert from 'node:assert/strict';
import {employeeStatus,companyLayout} from '../company.js';
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
