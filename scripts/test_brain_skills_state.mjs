import test from 'node:test';
import assert from 'node:assert/strict';
import {areaName,brainStats,brainView,filterSkills,learnText,usageText} from '../apps/web/components/brain-skills-state.js';

const skill=(ref,title,domain,extra={})=>({ref,title,domain,body:'Steps for '+title,keywords:[],builtin:true,retired:false,usage:{uses:0,passed:0,failed:0},...extra});
const view={counts:{active:3},domains:{development:2,'politics-policy':1},gaps:[],decisions:[],
 skills:[skill('ago:a','Python module','development',{usage:{uses:3,passed:2,failed:1}}),
  skill('co:b','Handloom export','trade',{builtin:false}),skill('ago:c','Policy analysis','politics-policy',{retired:true})]};

test('areas read as plain names',()=>{
 assert.equal(areaName('politics-policy'),'Politics & public policy');
 assert.equal(areaName('higher-education'),'Higher education');
});
test('search, area and retired filters',()=>{
 assert.deepEqual(filterSkills(view.skills).map(s=>s.ref),['co:b','ago:a']);           // company skills first
 assert.deepEqual(filterSkills(view.skills,{query:'python'}).map(s=>s.ref),['ago:a']);
 assert.deepEqual(filterSkills(view.skills,{area:'politics-policy',showRetired:true}).map(s=>s.ref),['ago:c']);
});
test('usage, stats and results are plain sentences',()=>{
 assert.equal(usageText({uses:3,passed:2,failed:1}),'Used in 3 tasks · 2 passed QA · 1 failed QA');
 assert.equal(usageText(null),'Not used yet');
 assert.deepEqual(brainStats(view),{active:3,areas:2,learned:1,used:3,passed:2});
 assert.match(learnText({status:'approved',title:'X',reviewed_by:'JARVIS',drafted_by:'STARK'}),/^JARVIS approved "X" \(drafted by STARK\)/);
 assert.equal(learnText({status:'denied',title:'X',reviewed_by:'JARVIS',reason:'Too vague.'}),'JARVIS did not approve "X": Too vague.');
 assert.equal(brainView([]),null);assert.equal(brainView({skills:[]}),null);
});
