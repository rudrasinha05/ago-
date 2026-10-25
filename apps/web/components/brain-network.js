// Pure model for the 3D Company Brain. Every node, link and highlight is
// derived from server records passed in by the caller: employees and their
// recorded manager_id links, persisted task states and durable work events.
// Nothing here invents activity: no task record means no route, no event
// record means no communication signal, and unknown task data stays Unknown.
import {employeeStatus} from '@ago/sdk/company';

const ACTIVE_WAITING=['proposed','ready','waiting_approval'];
// Inner radius for top-level managers, outer cortex for the deepest staff.
const CORE_RADIUS=.34,CORTEX_RADIUS=.9;
// Brain proportions (x: hemispheres, y: height, z: front-to-back).
export const BRAIN_SHAPE=Object.freeze({x:.8,y:.66,z:1.0});
const GOLDEN=Math.PI*(3-Math.sqrt(5));

function hash(text){
  let value=2166136261;
  for(const char of String(text)){value^=char.charCodeAt(0);value=Math.imul(value,16777619);}
  return (value>>>0)/4294967295;
}

/** Hierarchy depth over recorded manager links only; cycles are cut safely. */
function depths(employees){
  const byId=new Map(employees.map(e=>[e.id,e])),cache=new Map();
  const depthOf=id=>{
    if(cache.has(id))return cache.get(id);
    let depth=0,current=byId.get(id);const seen=new Set([id]);
    while(current?.manager_id&&byId.has(current.manager_id)&&!seen.has(current.manager_id)){
      seen.add(current.manager_id);depth++;current=byId.get(current.manager_id);
    }
    cache.set(id,depth);return depth;
  };
  for(const e of employees)depthOf(e.id);
  return cache;
}

/**
 * Build the brain network.
 * Returns {nodes, links, counts, known} where:
 *  - nodes: one per employee, with a deterministic 3D position inside the
 *    brain volume (department = sector, hierarchy depth = radius);
 *  - links: recorded reporting links only, flagged 'running' / 'waiting'
 *    when a persisted task's assignment chain passes through them.
 */
export const FOUNDER_POSITION=Object.freeze([0,.06,0]);
export function brainNetwork({employees=[],departments=[],tasks,notifications,founderId=null}={}){
  const known=Array.isArray(tasks);
  // One neuron per employee id even if a caller passes overlapping groups.
  const people=[...new Map(employees.filter(e=>e&&e.id&&e.id!==founderId).map(e=>[e.id,e])).values()];
  const byId=new Map(people.map(e=>[e.id,e]));
  const depth=depths(people);
  const maxDepth=Math.max(1,...depth.values());
  // Department sectors in stable order; unknown departments share one sector.
  const order=[...new Set([...departments.map(d=>d.id),...people.map(e=>e.department_id||'none')])];
  const sector=new Map(order.map((id,i)=>[id,i]));
  const sectorCount=Math.max(1,order.length);
  const members=new Map();
  for(const e of people){
    const key=e.department_id||'none';
    if(!members.has(key))members.set(key,[]);
    members.get(key).push(e);
  }
  const departmentName=new Map(departments.map(d=>[d.id,d.name]));
  const events=Array.isArray(notifications?.recent)?notifications.recent:[];
  const counts=notifications?.by_employee&&typeof notifications.by_employee==='object'?notifications.by_employee:{};
  const latestEvent=new Map();
  for(const event of events){
    if(!event?.employee_id||!byId.has(event.employee_id))continue;
    const previous=latestEvent.get(event.employee_id);
    if(!previous||String(event.created_at||'')>String(previous.created_at||''))latestEvent.set(event.employee_id,event);
  }
  // Routes: walk recorded manager links upward from each active assignee.
  const runningLinks=new Set(),waitingLinks=new Set();
  if(known)for(const task of tasks){
    const running=task.status==='running';
    if(!(running||ACTIVE_WAITING.includes(task.status))||!byId.has(task.assignee_id))continue;
    let id=task.assignee_id;const seen=new Set();
    while(id&&byId.has(id)&&!seen.has(id)){
      seen.add(id);
      const manager=byId.get(id).manager_id;
      // A recorded manager_id equal to the Founder is a real reporting link.
      if(founderId&&manager===founderId){(running?runningLinks:waitingLinks).add('founder>'+id);break;}
      if(!manager||!byId.has(manager))break; // never route to an unrecorded parent
      (running?runningLinks:waitingLinks).add(manager+'>'+id);
      id=manager;
    }
  }
  for(const key of runningLinks)waitingLinks.delete(key);
  // "On a route" means an endpoint of a recorded link that carries work,
  // not merely having a task: an unlinked assignee has no route to show.
  const routed=new Set([...runningLinks,...waitingLinks].flatMap(key=>key.split('>')));

  const nodes=people.map(e=>{
    const key=e.department_id||'none',group=members.get(key),index=group.indexOf(e);
    const level=depth.get(e.id)||0;
    // Sector centre around the vertical axis, spread within the sector by a
    // golden-angle spiral so large departments do not stack on one point.
    const base=(sector.get(key)/sectorCount)*Math.PI*2+hash(key)*.4;
    const width=(Math.PI*2/sectorCount)*.72;
    const spread=group.length>1?((index*GOLDEN)%1-.5)*width:0;
    const theta=base+spread;
    const lat=((index*.61803)%1-.5)*1.25+(hash(e.id)-.5)*.18;
    const radius=CORE_RADIUS+(CORTEX_RADIUS-CORE_RADIUS)*Math.min(1,(level+.6)/(maxDepth+.6));
    const cosLat=Math.cos(lat);
    const position=[
      Math.sin(theta)*cosLat*radius*BRAIN_SHAPE.x,
      Math.sin(lat)*radius*BRAIN_SHAPE.y+.06,
      Math.cos(theta)*cosLat*radius*BRAIN_SHAPE.z,
    ];
    const status=employeeStatus(e.id,known?tasks:undefined);
    const running=status.tasks.filter(t=>t.status==='running').length;
    const waiting=status.tasks.filter(t=>ACTIVE_WAITING.includes(t.status)).length;
    const event=latestEvent.get(e.id)||null;
    return {
      id:e.id,name:e.name||'Unnamed employee',kind:e.kind,role:e.role_title||'',
      department:departmentName.get(e.department_id)||'Unassigned department',
      level,position,tone:status.tone,label:status.label,running,waiting,
      routed:routed.has(e.id),
      signals:Math.max(0,Number(counts[e.id])||0),
      lastEvent:event,
    };
  });
  const links=people.filter(e=>e.manager_id&&(byId.has(e.manager_id)||(founderId&&e.manager_id===founderId))).map(e=>{
    const from=byId.has(e.manager_id)?e.manager_id:'founder',key=from+'>'+e.id;
    return {key,from,to:e.id,state:runningLinks.has(key)?'running':waitingLinks.has(key)?'waiting':'idle'};
  });
  return {
    known,nodes,links,
    counts:{
      employees:nodes.length,
      running:nodes.filter(n=>n.running).length,
      waiting:nodes.filter(n=>!n.running&&n.waiting).length,
      routes:runningLinks.size,
      signals:nodes.filter(n=>n.signals>0).length,
    },
  };
}

/** Same projection as the vertex shader, for hit-testing and DOM labels. */
export function projectPoint([x,y,z],{yaw,pitch,aspect,scale}){
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const rx=cy*x+sy*z,rz=-sy*x+cy*z;
  const py=cp*y-sp*rz,pz=sp*y+cp*rz;
  const perspective=2.8/(3.8-pz);
  return {x:rx*perspective*scale/aspect,y:py*perspective*scale,z:pz,perspective};
}

export const TONE_COLORS=Object.freeze({
  busy:[1,.27,.42],waiting:[1,.78,.3],blocked:[1,.55,.25],failed:[.72,.55,1],
  idle:[.3,.92,.7],unknown:[.62,.68,.78],
});
