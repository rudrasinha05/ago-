// PROJ-014 / PROJ-016: the module plan of a project, in plain words.
// The server decides; this only reads its answer and refuses any other shape.

const UNIT_STATUS={planned:'Waiting',in_progress:'Being built',integrated:'Integrated'};

/** The server's module view, or null when the answer is not that shape. */
export function modulesView(raw){
 if(!raw||raw.kind!=='ago_project_modules_v1'||typeof raw.status!=='string')return null;
 const unit=u=>u&&typeof u.code==='string'&&typeof u.title==='string';
 return {
  status:['not_planned','proposed','approved'].includes(raw.status)?raw.status:'not_planned',
  preview:Array.isArray(raw.preview)?raw.preview.filter(unit):[],
  units:Array.isArray(raw.units)?raw.units.filter(unit).map(u=>({...u,label:UNIT_STATUS[u.status]||'Waiting'})):[],
  deferred:Array.isArray(raw.deferred)?raw.deferred.filter(c=>typeof c==='string'):[],
  integrated:Number.isInteger(raw.integrated)?raw.integrated:0,
  total:Number.isInteger(raw.total)?raw.total:0,
  latest:raw.latest_version&&Number.isInteger(raw.latest_version.version)?raw.latest_version:null,
 };
}

/** One sentence for where the project's implementation stands. */
export function modulesSummary(v){
 if(!v)return '';
 if(v.status==='not_planned')return v.preview.length
  ?'AGO will propose a working prototype and '+v.preview.length+' modules ('+v.preview.map(m=>m.code).join(', ')+') when implementation is next.'
  :'No module list found in the brief yet; the architect will list the modules in the architecture stage.';
 if(v.status==='proposed')return 'Module plan waiting for your approval: a working prototype, then '+(v.total-1)+' modules. Nothing is built until you approve.';
 if(v.integrated===v.total)return 'All '+v.total+' units are integrated and every test of the complete product passed together.';
 const now=v.units.find(u=>u.status==='in_progress');
 return v.integrated+' of '+v.total+' units integrated'+(now?'. Now building: '+now.code+' '+now.title:'')+'.';
}
