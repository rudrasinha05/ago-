// Company Brain skills (SKL-001..005): plain projections of the server's view.

const AREA_NAMES={
 'development':'Development','architecture':'Architecture','devops':'DevOps & release','security':'Security',
 'qa':'Quality (QA)','data-ai':'Data & AI','design':'UI & UX design','graphics':'Graphics & brand',
 'product':'Product','project-management':'Project management','business':'Business & strategy',
 'marketing':'Marketing','sales':'Sales & customers','finance':'Finance','legal':'Legal & compliance',
 'hr':'People & HR','operations':'Operations','research-writing':'Research & writing',
 'politics-policy':'Politics & public policy','education':'Education','communication':'Communication',
};
/** A readable name for a skill area. */
export function areaName(domain){
 return AREA_NAMES[domain]||String(domain||'Other').replace(/[.-]+/g,' ').replace(/^./,c=>c.toUpperCase());
}

/** The server's Brain view, or null when the answer is not that shape. */
export function brainView(raw){
 if(!raw||typeof raw!=='object'||!Array.isArray(raw.skills)||!raw.counts)return null;
 return {...raw,gaps:Array.isArray(raw.gaps)?raw.gaps:[],decisions:Array.isArray(raw.decisions)?raw.decisions:[],
  domains:raw.domains&&typeof raw.domains==='object'?raw.domains:{}};
}

/** Skills matching the search words and area, active first, then by title. */
export function filterSkills(skills,{query='',area='all',showRetired=false}={}){
 const words=String(query).toLowerCase().split(/\s+/).filter(Boolean);
 return (skills||[]).filter(s=>(showRetired||!s.retired)&&(area==='all'||s.domain===area)&&words.every(w=>
  (s.title+' '+s.body+' '+(s.keywords||[]).join(' ')+' '+s.domain).toLowerCase().includes(w)))
  .sort((a,b)=>Number(a.retired)-Number(b.retired)||Number(a.builtin)-Number(b.builtin)||a.title.localeCompare(b.title));
}

/** "Used in 3 tasks · 2 passed QA · 1 failed" or "Not used yet". */
export function usageText(usage){
 if(!usage?.uses)return 'Not used yet';
 const parts=['Used in '+usage.uses+(usage.uses===1?' task':' tasks')];
 if(usage.passed)parts.push(usage.passed+' passed QA');
 if(usage.failed)parts.push(usage.failed+' failed QA');
 return parts.join(' · ');
}

/** Four headline numbers. */
export function brainStats(view){
 const skills=view?.skills||[];
 return {active:view?.counts?.active??0,areas:Object.keys(view?.domains||{}).length,
  learned:skills.filter(s=>!s.builtin&&!s.retired).length,
  used:skills.reduce((n,s)=>n+(s.usage?.uses||0),0),passed:skills.reduce((n,s)=>n+(s.usage?.passed||0),0)};
}

/** One sentence for a learn result. */
export function learnText(r){
 if(!r)return '';
 return r.status==='approved'
  ?r.reviewed_by+' approved "'+r.title+'" (drafted by '+r.drafted_by+'). AI employees get it from now on.'
  :r.reviewed_by+' did not approve "'+r.title+'": '+r.reason;
}
