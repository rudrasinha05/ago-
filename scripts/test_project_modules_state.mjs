import test from 'node:test';
import assert from 'node:assert/strict';
import {modulesSummary,modulesView} from '../apps/web/components/project-modules-state.js';

const u=(code,status)=>({code,title:code+' title',status});
test('an unexpected server answer is refused, never rendered half-broken',()=>{
 for(const bad of [null,[],{},{kind:'x',status:'approved'},{kind:'ago_project_modules_v1'}])assert.equal(modulesView(bad),null);
 const v=modulesView({kind:'ago_project_modules_v1',status:'weird',units:[u('M01','integrated'),{code:7}],deferred:['M14',3]});
 assert.equal(v.status,'not_planned');assert.deepEqual(v.units.map(x=>x.label),['Integrated']);assert.deepEqual(v.deferred,['M14']);
});
test('each state reads as one plain sentence',()=>{
 const base={kind:'ago_project_modules_v1',deferred:[],latest_version:null};
 assert.match(modulesSummary(modulesView({...base,status:'not_planned',preview:[u('M01'),u('M02')]})),/working prototype and 2 modules \(M01, M02\)/);
 assert.match(modulesSummary(modulesView({...base,status:'not_planned',preview:[]})),/architect will list the modules/);
 assert.equal(modulesSummary(modulesView({...base,status:'proposed',total:4,units:[]})),
  'Module plan waiting for your approval: a working prototype, then 3 modules. Nothing is built until you approve.');
 assert.equal(modulesSummary(modulesView({...base,status:'approved',total:3,integrated:1,
  units:[u('PROTOTYPE','integrated'),u('M01','in_progress'),u('M02','planned')]})),'1 of 3 units integrated. Now building: M01 M01 title.');
 assert.equal(modulesSummary(modulesView({...base,status:'approved',total:2,integrated:2,units:[]})),
  'All 2 units are integrated and every test of the complete product passed together.');
});
