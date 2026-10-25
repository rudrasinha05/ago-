import test from 'node:test';
import assert from 'node:assert/strict';
import {employeeStatus,companyLayout,companyLinkAnchors,activeRouteKeys,employeeProjects,boardFunctionSeats} from '../company.js';
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
 assert.equal(layout.layout,'circular');
 assert.ok(live.routes.has('employee:lead>employee:dev'));
 assert.equal(live.routes.has('founder>department:d'),false,'Grouping cannot be an approval path');
 assert.equal(live.routes.has('department:d>employee:lead'),false,'Department is not the assigned manager');
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
 assert.deepEqual([...pending.waitingRoutes],['employee:lead>employee:dev'],'Only actual reporting goes amber');
 const mixed=activeRouteKeys(map,staff,[{assignee_id:'dev',status:'running'},{assignee_id:'lead',status:'proposed'}]);
 assert.equal(mixed.routes.has('founder>department:d'),false);
 assert.ok(mixed.routes.has('employee:lead>employee:dev'));
 assert.equal(mixed.waitingRoutes.size,0,'Groupings do not inherit running task colours');
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
 assert.ok(layout.nodes.find(n=>n.key==='employee:cto').radius < layout.nodes.find(n=>n.key==='employee:pm').radius);
 assert.equal(layout.founder.x,layout.center);
 assert.equal(layout.founder.y,layout.center);
 assert.equal(layout.layout,'circular');
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


test('one recorded CEO and its executive reports form outward circular sectors',()=>{
 const departments=[{id:'strategy',name:'Strategy'}];
 const employees=[{id:'ceo',name:'CEO',department_id:'strategy',manager_id:'founder'},
   ...['cto','cfo','ciso','cqo','coo'].map(id=>({id,name:id,department_id:'strategy',manager_id:'ceo'}))];
 const graph=companyLayout(departments,employees,'founder');
 const ceo=graph.nodes.find(n=>n.key==='employee:ceo');
 const direct=graph.nodes.filter(n=>n.type==='employee'&&n.id!=='ceo');
 assert.equal(graph.reportingEdges,6);
 assert.equal(graph.groupingEdges,1);
 assert.ok(direct.every(n=>n.radius>ceo.radius));
 assert.ok(direct.every(n=>Math.abs(n.angle-ceo.angle)<=1.201),
   'Subordinates must never be scattered opposite their CEO across Founder');
 assert.equal(graph.nodes.filter(n=>n.type==='employee').length,6);
 const running=activeRouteKeys(graph,employees,[{assignee_id:'cto',status:'running'}]);
 assert.deepEqual([...running.routes],['employee:ceo>employee:cto','founder>employee:ceo']);
 assert.equal([...running.routes].some(k=>k.includes('department:')),false);
});

test('unassigned, missing and cyclic managers remain visible but not fabricated as reports',()=>{
 const departments=[{id:'one',name:'People'}];
 const staff=[
  {id:'none',department_id:'one',manager_id:null},
  {id:'missing',department_id:'one',manager_id:'not-in-roster'},
  {id:'a',department_id:'one',manager_id:'b'},
  {id:'b',department_id:'one',manager_id:'a'},
  {id:'valid',department_id:'one',manager_id:'founder'},
 ];
 const graph=companyLayout(departments,staff,'founder');
 assert.equal(graph.nodes.filter(n=>n.type==='employee').length,5);
 assert.equal(graph.reportingEdges,1);
 assert.equal(graph.reportingIssues.length,4);
 assert.ok(graph.edges.find(e=>e.to==='employee:valid'&&e.from==='founder'&&e.kind==='reporting'));
 for(const id of ['none','missing','a','b']){
   assert.equal(graph.edges.find(e=>e.to==='employee:'+id).kind,'grouping');
   assert.equal(activeRouteKeys(graph,staff,[{assignee_id:id,status:'running'}]).routes.size,0);
 }
});

test('circular hierarchy anchors are finite, clipped and prevent card overlaps at scale',()=>{
 const departments=Array.from({length:12},(_,i)=>({id:'d'+i,name:'Dept '+i}));
 const employees=Array.from({length:100},(_,i)=>({
  id:'employee'+i,name:'Employee '+i,department_id:departments[i%12].id,
  manager_id:i%11===0?'founder':i%5===0?null:'employee'+Math.floor((i-1)/4)
 }));
 const graph=companyLayout(departments,employees,'founder');
 assert.equal(graph.nodes.length,112);
 for(const a of graph.nodes){
   assert.ok(a.x>0&&a.y>0&&a.x<graph.size&&a.y<graph.size);
   for(const b of graph.nodes){
     if(a.key!==b.key){
       const bothStaff=a.type==='employee'&&b.type==='employee';
       const bothDepartments=a.type==='department'&&b.type==='department';
       const width=bothStaff?230:225,height=bothStaff?300:bothDepartments?170:230;
       assert.ok(Math.abs(a.x-b.x)>=width||Math.abs(a.y-b.y)>=height,
         'Visible circular cards overlap: '+a.key+' / '+b.key);
     }
   }
 }
 const coords=new Map([['founder',graph.founder],...graph.nodes.map(n=>[n.key,n])]);
 for(const edge of graph.edges){
   assert.ok(coords.has(edge.from)&&coords.has(edge.to));
   const a=coords.get(edge.from),b=coords.get(edge.to);
   const anchors=companyLinkAnchors(a,b,edge.from==='founder'?'founder':a.type,b.type);
   assert.ok(Object.values(anchors).every(Number.isFinite),'Invalid radial link: '+edge.to);
   assert.ok(Math.hypot(anchors.x1-anchors.x2,anchors.y1-anchors.y2)>0);
 }
});

test('18 departments retain legible, collision-free circular grouping badges',()=>{
 const departments=Array.from({length:18},(_,i)=>({id:'department'+i,name:'Department '+i}));
 const employees=Array.from({length:126},(_,i)=>({
   id:'person'+i,name:'Person '+i,department_id:departments[i%18].id,
   manager_id:i%9===0?'founder':i%7===0?null:'person'+Math.floor((i-1)/3)
 }));
 const map=companyLayout(departments,employees,'founder');
 const badges=map.nodes.filter(n=>n.type==='department');
 assert.equal(badges.length,18);
 for(const a of badges)for(const b of badges){
   if(a===b)continue;
   assert.ok(Math.abs(a.x-b.x)>=225||Math.abs(a.y-b.y)>=170,
     'Department badges overlap: '+a.key+' / '+b.key);
 }
 assert.equal(map.edges.filter(e=>e.from==='founder'&&e.kind==='grouping').length,18);
});
