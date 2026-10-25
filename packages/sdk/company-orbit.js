/** Deterministic circular reporting map. Presentation only; never changes authority.
 * Blue reporting links come exclusively from actual, acyclic manager_id records.
 * Grey department links represent grouping, not authorization or task execution.
 */
const TAU=Math.PI*2;
const byName=(a,b)=>String(a.name||a.id).localeCompare(String(b.name||b.id))||String(a.id).localeCompare(String(b.id));

export function circularCompanyLayout(departments,employees,founderId){
  const people=employees.filter(e=>e.id!==founderId).slice().sort(byName);
  const byId=new Map(people.map(e=>[e.id,e]));
  const children=new Map(people.map(e=>[e.id,[]]));
  const validManager=new Map(),reportingIssues=[];
  for(const employee of people){
    if(employee.manager_id===founderId)continue;
    if(!employee.manager_id){reportingIssues.push({employee_id:employee.id,reason:'manager_not_assigned'});continue;}
    if(employee.manager_id===employee.id){reportingIssues.push({employee_id:employee.id,reason:'self_reporting'});continue;}
    if(!byId.has(employee.manager_id)){reportingIssues.push({employee_id:employee.id,reason:'manager_not_in_roster'});continue;}
    const seen=new Set([employee.id]);let parent=employee.manager_id,cycle=false;
    while(byId.has(parent)){
      if(seen.has(parent)){cycle=true;break;}
      seen.add(parent);parent=byId.get(parent).manager_id;
    }
    if(cycle){reportingIssues.push({employee_id:employee.id,reason:'reporting_cycle'});continue;}
    validManager.set(employee.id,employee.manager_id);
    children.get(employee.manager_id).push(employee.id);
  }
  for(const list of children.values())list.sort((a,b)=>byName(byId.get(a),byId.get(b)));
  const roots=people.filter(e=>!validManager.has(e.id));
  const depts=departments.slice().sort(byName),deptIds=new Set(depts.map(d=>d.id));
  const groups=depts.map(d=>({department:d,roots:roots.filter(e=>e.department_id===d.id)}));
  const outside=roots.filter(e=>!deptIds.has(e.department_id));
  if(outside.length)groups.push({department:null,roots:outside});
  const leafWeights=new Map();
  function weight(id){
    if(leafWeights.has(id))return leafWeights.get(id);
    const c=children.get(id)||[];
    const result=Math.max(1,c.reduce((sum,child)=>sum+weight(child),0));
    leafWeights.set(id,result);
    return result;
  }
  const widths=groups.map(g=>Math.max(1,g.roots.reduce((sum,e)=>sum+weight(e.id),0)));
  const total=widths.reduce((a,b)=>a+b,0);
  const raw=[],edges=[],depthAngles=new Map();
  let cursor=-Math.PI/2;
  function place(person,start,end,depth){
    const angle=(start+end)/2,key='employee:'+person.id;
    raw.push({...person,key,type:'employee',depth:depth+1,angle});
    if(!depthAngles.has(depth))depthAngles.set(depth,[]);
    depthAngles.get(depth).push(angle);
    const parent=validManager.get(person.id);
    edges.push({
      from:parent?'employee:'+parent:person.manager_id===founderId?'founder':deptIds.has(person.department_id)?'department:'+person.department_id:'founder',
      to:key,
      kind:parent||person.manager_id===founderId?'reporting':'grouping'
    });
    const childIds=children.get(person.id)||[];
    // Keep subordinates in the parent's outward sector: a single CEO with
    // many direct reports must not draw links straight across the Founder.
    const spread=Math.min(end-start,2.4);
    let left=angle-spread/2;
    const units=childIds.reduce((sum,id)=>sum+weight(id),0);
    for(const childId of childIds){
      const arc=spread*weight(childId)/units;
      place(byId.get(childId),left,left+arc,depth+1);
      left+=arc;
    }
  }
  groups.forEach((group,index)=>{
    const end=cursor+(total?TAU*widths[index]/total:0);
    let left=cursor;
    for(const employee of group.roots){
      const arc=(end-cursor)*weight(employee.id)/widths[index];
      place(employee,left,left+arc,0);
      left+=arc;
    }
    cursor=end;
  });
  const departmentCount=depts.length;
  const departmentRadius=departmentCount?Math.max(600,departmentCount>1?340/(2*Math.sin(Math.PI/departmentCount)):0):0;
  depts.forEach((department,index)=>{
    // Distinct orbit; never insert a department as an employee's manager.
    const angle=-Math.PI/2+TAU*index/departmentCount;
    const key='department:'+department.id;
    raw.push({...department,key,type:'department',depth:0,angle,radius:departmentRadius});
    edges.push({from:'founder',to:key,kind:'grouping'});
  });
  const radii=new Map();let lastRadius=departmentRadius;
  for(const depth of [...depthAngles.keys()].sort((a,b)=>a-b)){
    const angles=depthAngles.get(depth).slice().sort((a,b)=>a-b);
    let minimum=0;
    if(angles.length>1){
      let minGap=TAU;
      for(let i=0;i<angles.length;i++){
        minGap=Math.min(minGap,(angles[(i+1)%angles.length]-angles[i]+TAU)%TAU);
      }
      // Reserve enough room for full employee cards and hover enlargement.
      minimum=minGap>0?390/(2*Math.sin(minGap/2)):Infinity;
    }
    const radius=Math.ceil(Math.max(1000+depth*480,minimum,lastRadius+455));
    if(!Number.isFinite(radius))throw new Error('Invalid circular employee angle');
    radii.set(depth,radius);
    lastRadius=radius;
  }
  const maxRadius=Math.max(departmentRadius,...radii.values(),0);
  const center=Math.ceil(Math.max(900,maxRadius+420)),size=center*2;
  const nodes=raw.map(node=>{
    const radius=node.type==='department'?departmentRadius:radii.get(node.depth-1);
    return {...node,radius,x:center+radius*Math.cos(node.angle),y:center+radius*Math.sin(node.angle)};
  });
  const founder={x:center,y:center};
  const allKeys=new Set(['founder',...nodes.map(n=>n.key)]);
  if(edges.some(e=>!allKeys.has(e.from)||!allKeys.has(e.to)))throw new Error('Unresolved circular reporting link');
  return {size,center,founder,nodes,edges,layout:'circular',reportingIssues,
    reportingEdges:edges.filter(e=>e.kind==='reporting').length,
    groupingEdges:edges.filter(e=>e.kind==='grouping').length};
}

/** Clip edges to rectangular cards at any angle, not only top/bottom. */
export function companyLinkAnchors(a,b,fromType='employee',toType='employee'){
  const dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy);
  if(len<1)return {x1:a.x,y1:a.y,x2:b.x,y2:b.y,cx:a.x,cy:a.y};
  const ux=dx/len,uy=dy/len;
  const bounds=type=>type==='founder'?{w:210,h:190}:type==='department'?{w:112,h:82}:{w:112,h:100};
  const clip=shape=>Math.min(Math.abs(ux)<1e-8?Infinity:shape.w/Math.abs(ux),Math.abs(uy)<1e-8?Infinity:shape.h/Math.abs(uy))+13;
  const start=Math.min(clip(bounds(fromType)),len/3),end=Math.min(clip(bounds(toType)),len/3);
  const x1=a.x+ux*start,y1=a.y+uy*start,x2=b.x-ux*end,y2=b.y-uy*end;
  return {x1,y1,x2,y2,cx:(x1+x2)/2,cy:(y1+y2)/2};
}
