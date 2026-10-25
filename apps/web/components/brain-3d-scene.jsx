"use client";
import {useEffect,useRef,useState} from "react";
import {BRAIN_SHAPE,FOUNDER_POSITION,TONE_COLORS,projectPoint} from "./brain-network";

// Holographic company brain drawn with WebGL (no remote assets, no libraries).
// The glass cortex is decoration; every neuron is a real employee record,
// every synapse a recorded manager link, and red routes exist only while a
// persisted task is running along that recorded chain (see brain-network.js).

const SHELL_VERTEX=`
attribute vec4 position;
attribute vec3 normal;
uniform float yaw;
uniform float pitch;
uniform float aspect;
uniform float scale;
varying float fresnel;
varying float ridge;
varying float facing;
void main(){
 float cy=cos(yaw),sy=sin(yaw),cp=cos(pitch),sp=sin(pitch);
 vec3 p=vec3(cy*position.x+sy*position.z,position.y,-sy*position.x+cy*position.z);
 vec3 n=vec3(cy*normal.x+sy*normal.z,normal.y,-sy*normal.x+cy*normal.z);
 p=vec3(p.x,cp*p.y-sp*p.z,sp*p.y+cp*p.z);
 n=normalize(vec3(n.x,cp*n.y-sp*n.z,sp*n.y+cp*n.z));
 float perspective=2.8/(3.8-p.z);
 gl_Position=vec4(p.x*perspective*scale/aspect,p.y*perspective*scale,0.0,1.0);
 fresnel=1.0-abs(n.z);
 facing=step(0.0,n.z);
 ridge=position.w;
}`;
const SHELL_FRAGMENT=`
precision mediump float;
uniform float active;
varying float fresnel;
varying float ridge;
varying float facing;
void main(){
 float rim=pow(fresnel,2.2);
 float gyri=smoothstep(.62,.97,ridge);
 vec3 cool=mix(vec3(.10,.30,.78),vec3(.42,.86,1.0),rim);
 vec3 warm=mix(vec3(.45,.12,.42),vec3(1.0,.42,.66),rim);
 vec3 color=mix(cool,warm,active*.38);
 float alpha=(.018+.30*rim+.16*gyri*(.35+.65*facing))*(.55+.45*facing);
 gl_FragColor=vec4(color+gyri*vec3(.10,.22,.30),alpha);
}`;
const PARTICLE_VERTEX=`
attribute vec3 position;
attribute vec4 color;
attribute float size;
uniform float yaw;
uniform float pitch;
uniform float aspect;
uniform float scale;
uniform float ratio;
varying vec4 tint;
varying float ring;
void main(){
 float cy=cos(yaw),sy=sin(yaw),cp=cos(pitch),sp=sin(pitch);
 vec3 p=vec3(cy*position.x+sy*position.z,position.y,-sy*position.x+cy*position.z);
 p=vec3(p.x,cp*p.y-sp*p.z,sp*p.y+cp*p.z);
 float perspective=2.8/(3.8-p.z);
 gl_Position=vec4(p.x*perspective*scale/aspect,p.y*perspective*scale,0.0,1.0);
 gl_PointSize=abs(size)*perspective*ratio;
 ring=step(size,0.0);
 float depthFade=mix(.5,1.0,clamp((p.z+1.0)*.5,0.0,1.0));
 tint=vec4(color.rgb,color.a*depthFade);
}`;
const PARTICLE_FRAGMENT=`
precision mediump float;
uniform float points;
varying vec4 tint;
varying float ring;
void main(){
 if(points<.5){gl_FragColor=tint;return;}
 vec2 c=gl_PointCoord*2.0-1.0;
 float d=dot(c,c);
 if(d>1.0)discard;
 float shape=ring>.5?smoothstep(.62,.80,d)*smoothstep(1.0,.86,d):smoothstep(1.0,.0,d)*.55+smoothstep(.30,.12,d)*.9;
 gl_FragColor=vec4(tint.rgb+vec3(.25)*smoothstep(.2,.0,d)*(1.0-ring),tint.a*shape);
}`;

/** Two hemispheres with smooth normals and low-frequency gyri. */
function shellVertices() {
 const out=[],lat=46,lon=72,step=1e-3;
 const surface=(side,u,v)=>{
   const fold=Math.sin(8*v+1.8*Math.sin(3*u))*Math.cos(9*u+Math.sin(4*v));
   const bump=1+.03*fold;
   let x=Math.cos(u)*Math.sin(v),y=Math.sin(u),z=Math.cos(u)*Math.cos(v);
   if(x*side<0)x*=.42;           // flatter medial wall leaves a clear fissure
   if(y<0)y*=.74;                // flatter base
   const taper=1-.12*Math.max(0,-z); // narrower occipital end
   return [side*.43+x*.42*bump*taper*BRAIN_SHAPE.x/.8, y*.70*bump*BRAIN_SHAPE.y/.66+.04, z*1.02*bump*BRAIN_SHAPE.z, fold];
 };
 const vertex=(side,a,b)=>{
   const u=-Math.PI/2+.04+(a/lat)*(Math.PI-.08),v=(b/lon)*2*Math.PI;
   const p=surface(side,u,v),pu=surface(side,u+step,v),pv=surface(side,u,v+step);
   const du=[pu[0]-p[0],pu[1]-p[1],pu[2]-p[2]],dv=[pv[0]-p[0],pv[1]-p[1],pv[2]-p[2]];
   let n=[du[1]*dv[2]-du[2]*dv[1],du[2]*dv[0]-du[0]*dv[2],du[0]*dv[1]-du[1]*dv[0]];
   const out=[p[0]-side*.43,p[1],p[2]];
   if(n[0]*out[0]+n[1]*out[1]+n[2]*out[2]<0)n=n.map(x=>-x);
   const len=Math.hypot(...n)||1;
   return [...p,...n.map(x=>x/len)];
 };
 for(const side of [-1,1])for(let a=0;a<lat;a++)for(let b=0;b<lon;b++){
   const p=vertex(side,a,b),q=vertex(side,a+1,b),r=vertex(side,a+1,b+1),t=vertex(side,a,b+1);
   out.push(...p,...q,...t,...q,...r,...t);
 }
 return new Float32Array(out);
}

const LINK_COLORS={idle:[.38,.62,1,.30],waiting:[1,.78,.30,.85],running:[1,.24,.40,1]};
const FOUNDER_POINT=FOUNDER_POSITION;
/** Static particles (neurons, halos, synapses) for one network snapshot. */
function networkGeometry(network,selectedId,highlightId){
 const lines=[],points=[],byId=new Map([['founder',{position:FOUNDER_POINT}],...network.nodes.map(n=>[n.id,n])]);
 const push=(list,p,color,size)=>list.push(p[0],p[1],p[2],color[0],color[1],color[2],color[3],size);
 const routes=[];
 for(const link of network.links){
   const a=byId.get(link.from)?.position,b=byId.get(link.to)?.position;
   if(!a||!b)continue;
   const color=LINK_COLORS[link.state];
   push(lines,a,color,1);push(lines,b,color,1);
   if(link.state!=='idle'){
     routes.push({from:a,to:b,state:link.state});
     // Dotted trail thickens the 1px line so the recorded route reads at a glance.
     const length=Math.hypot(b[0]-a[0],b[1]-a[1],b[2]-a[2]),count=Math.max(3,Math.round(length/.05));
     for(let i=1;i<count;i++){
       const t=i/count;
       push(points,[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t],
         [color[0],color[1],color[2],link.state==='running'?.75:.45],link.state==='running'?4.5:3.5);
     }
   }
 }
 push(points,FOUNDER_POINT,[1,.86,.55,.22],46);
 push(points,FOUNDER_POINT,[1,.92,.70,1],15);
 for(const node of network.nodes){
   const color=TONE_COLORS[node.tone]||TONE_COLORS.unknown;
   if(node.running||node.signals)push(points,node.position,[color[0],color[1],color[2],node.running?.36:.2],node.running?40:30);
   push(points,node.position,[color[0],color[1],color[2],1],node.running?13:node.waiting?11:9);
   if(node.signals)push(points,node.position,[.55,.85,1,.75],-24);
   if(node.id===selectedId||node.id===highlightId)push(points,node.position,[1,1,1,.95],-32);
 }
 return {lines:new Float32Array(lines),points:new Float32Array(points),routes};
}

function compile(gl,vertexCode,fragmentCode){
  const make=(type,code)=>{
    const result=gl.createShader(type);
    gl.shaderSource(result,code);gl.compileShader(result);
    if(!gl.getShaderParameter(result,gl.COMPILE_STATUS)){gl.deleteShader(result);throw Error("3D scene shader unavailable");}
    return result;
  };
  const program=gl.createProgram(),vertex=make(gl.VERTEX_SHADER,vertexCode),fragment=make(gl.FRAGMENT_SHADER,fragmentCode);
  gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);
  gl.deleteShader(vertex);gl.deleteShader(fragment);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)){gl.deleteProgram(program);throw Error("3D scene program unavailable");}
  const uniforms={};
  for(const name of ['yaw','pitch','aspect','scale','ratio','active','points'])uniforms[name]=gl.getUniformLocation(program,name);
  return {program,uniforms};
}
function initialize(gl) {
  const shell=compile(gl,SHELL_VERTEX,SHELL_FRAGMENT),particles=compile(gl,PARTICLE_VERTEX,PARTICLE_FRAGMENT);
  const shellBuffer=gl.createBuffer(),vertices=shellVertices();
  gl.bindBuffer(gl.ARRAY_BUFFER,shellBuffer);gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);
  shell.position=gl.getAttribLocation(shell.program,"position");shell.normal=gl.getAttribLocation(shell.program,"normal");
  particles.position=gl.getAttribLocation(particles.program,"position");
  particles.color=gl.getAttribLocation(particles.program,"color");
  particles.size=gl.getAttribLocation(particles.program,"size");
  if([shell.position,shell.normal,particles.position,particles.color,particles.size].some(x=>x<0))throw Error("Missing 3D attributes");
  gl.disable(gl.DEPTH_TEST);gl.enable(gl.BLEND);
  // Additive glow; alpha accumulates so the canvas composites as premultiplied light.
  gl.blendFuncSeparate(gl.SRC_ALPHA,gl.ONE,gl.ONE,gl.ONE);
  return {shell,particles,shellBuffer,shellCount:vertices.length/7,
    lineBuffer:gl.createBuffer(),pointBuffer:gl.createBuffer(),pulseBuffer:gl.createBuffer(),
    lineCount:0,pointCount:0};
}
function bindParticles(gl,objects,buffer){
  const {particles}=objects;
  gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.vertexAttribPointer(particles.position,3,gl.FLOAT,false,32,0);
  gl.vertexAttribPointer(particles.color,4,gl.FLOAT,false,32,12);
  gl.vertexAttribPointer(particles.size,1,gl.FLOAT,false,32,28);
}

// Rendering policy (Issue #3): draw on demand — data change, drag, resize.
// Idle sway and route pulses run only while motion is allowed AND the canvas
// is on screen in a visible tab, throttled to ~15 fps. The WebGL context is
// released on unmount.
const IDLE_FRAME_MS=66;
// Fill the stage: as large as the height allows without clipping the width.
const BASE_YAW=-.62,BASE_PITCH=-.34,MAX_SCALE=1.5,WIDTH_FIT=1.15;
export function Brain3DScene({network,running,rotation=0,selectedId=null,highlightId=null,onPick,onReady}) {
  const canvas=useRef(null),labels=useRef(null),drag=useRef(null),requestDraw=useRef(()=>{});
  const dragAngle=useRef({yaw:0,pitch:0}),rotationRef=useRef(rotation),projected=useRef([]);
  const state=useRef({network,selectedId,highlightId,dirty:true});
  const [hovered,setHovered]=useState(null);
  useEffect(()=>{rotationRef.current=rotation;requestDraw.current();},[rotation]);
  useEffect(()=>{state.current={network,selectedId,highlightId,dirty:true};requestDraw.current();},[network,selectedId,highlightId]);
  useEffect(()=>{requestDraw.current();},[hovered]);
  useEffect(()=>{
    let frame=0,idle=0,gl=null,objects=null,alive=true,onScreen=true,routes=[];
    const element=canvas.current;
    const motion=window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const animate=()=>!motion?.matches&&onScreen&&document.visibilityState==='visible';
    let resize=null,visibility=null;
    const schedule=()=>{if(alive&&!frame&&objects)frame=requestAnimationFrame(draw);};
    function rebuild(){
      const geometry=networkGeometry(state.current.network,state.current.selectedId,state.current.highlightId);
      gl.bindBuffer(gl.ARRAY_BUFFER,objects.lineBuffer);gl.bufferData(gl.ARRAY_BUFFER,geometry.lines,gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER,objects.pointBuffer);gl.bufferData(gl.ARRAY_BUFFER,geometry.points,gl.STATIC_DRAW);
      objects.lineCount=geometry.lines.length/8;objects.pointCount=geometry.points.length/8;
      routes=geometry.routes;state.current.dirty=false;
    }
    function draw(){
      frame=0;
      if(!alive||!element||!objects)return;
      if(state.current.dirty)rebuild();
      const ratio=Math.min(window.devicePixelRatio||1,2);
      const width=Math.min(1400,Math.max(1,Math.floor(element.clientWidth*ratio)));
      const height=Math.min(900,Math.max(1,Math.floor(element.clientHeight*ratio)));
      if(element.width!==width||element.height!==height){element.width=width;element.height=height;}
      gl.viewport(0,0,width,height);
      gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
      const moving=animate(),now=performance.now();
      const view={
        yaw:BASE_YAW+Math.PI*(rotationRef.current)/180+dragAngle.current.yaw+(moving?Math.sin(now*.00022)*.07:0),
        pitch:BASE_PITCH+dragAngle.current.pitch,aspect:width/height,
        scale:Math.min(MAX_SCALE,WIDTH_FIT*width/height),
      };
      const network=state.current.network;
      const set=(program)=>{gl.useProgram(program.program);
        gl.uniform1f(program.uniforms.yaw,view.yaw);gl.uniform1f(program.uniforms.pitch,view.pitch);
        gl.uniform1f(program.uniforms.aspect,view.aspect);gl.uniform1f(program.uniforms.scale,view.scale);};
      // 1. Glass cortex.
      set(objects.shell);
      gl.uniform1f(objects.shell.uniforms.active,network.counts.running?1:0);
      gl.bindBuffer(gl.ARRAY_BUFFER,objects.shellBuffer);
      gl.enableVertexAttribArray(objects.shell.position);gl.enableVertexAttribArray(objects.shell.normal);
      gl.vertexAttribPointer(objects.shell.position,4,gl.FLOAT,false,28,0);
      gl.vertexAttribPointer(objects.shell.normal,3,gl.FLOAT,false,28,16);
      gl.drawArrays(gl.TRIANGLES,0,objects.shellCount);
      gl.disableVertexAttribArray(objects.shell.normal);
      // 2. Recorded reporting links, then neurons.
      set(objects.particles);
      gl.uniform1f(objects.particles.uniforms.ratio,ratio);
      for(const name of ['position','color','size'])gl.enableVertexAttribArray(objects.particles[name]);
      if(objects.lineCount){
        gl.uniform1f(objects.particles.uniforms.points,0);
        bindParticles(gl,objects,objects.lineBuffer);gl.drawArrays(gl.LINES,0,objects.lineCount);
      }
      gl.uniform1f(objects.particles.uniforms.points,1);
      bindParticles(gl,objects,objects.pointBuffer);gl.drawArrays(gl.POINTS,0,objects.pointCount);
      // 3. Moving pulses only on running routes and only while motion is allowed.
      if(moving&&routes.length){
        const pulses=[];
        routes.forEach((route,index)=>{
          if(route.state!=='running')return;
          for(const offset of [0,.5]){
            // Work flows from the manager down to the assignee.
            const t=(now*.00045+offset+index*.17)%1,{from:a,to:b}=route;
            pulses.push(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t,1,.55,.68,1,10);
          }
        });
        if(pulses.length){
          gl.bindBuffer(gl.ARRAY_BUFFER,objects.pulseBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(pulses),gl.DYNAMIC_DRAW);
          bindParticles(gl,objects,objects.pulseBuffer);gl.drawArrays(gl.POINTS,0,pulses.length/8);
        }
      }
      for(const name of ['color','size'])gl.disableVertexAttribArray(objects.particles[name]);
      // Screen positions for picking and the DOM labels (same math as the shaders).
      const w=element.clientWidth,h=element.clientHeight;
      projected.current=network.nodes.map(node=>{
        const p=projectPoint(node.position,view);
        return {id:node.id,x:(p.x*.5+.5)*w,y:(.5-p.y*.5)*h,z:p.z};
      });
      const founder=projectPoint(FOUNDER_POINT,view);
      const positions=new Map(projected.current.map(p=>[p.id,p]));
      positions.set('founder',{x:(founder.x*.5+.5)*w,y:(.5-founder.y*.5)*h});
      for(const label of labels.current?.children||[]){
        const point=positions.get(label.dataset.node);
        if(!point)continue;
        // Keep every label fully inside the stage: flip left near the right edge.
        const lw=label.offsetWidth,lh=label.offsetHeight;
        let x=point.x+12,y=point.y-lh-10;
        if(x+lw>w-6)x=point.x-12-lw;
        x=Math.max(6,Math.min(x,w-lw-6));y=Math.max(40,Math.min(y,h-lh-6));
        label.style.transform=`translate(${Math.round(x)}px,${Math.round(y)}px)`;
        // The neuron's own screen point, so tests and tools can target it.
        label.dataset.x=String(Math.round(point.x));label.dataset.y=String(Math.round(point.y));
      }
      if(moving&&!idle)idle=setTimeout(()=>{idle=0;schedule();},IDLE_FRAME_MS);
    }
    const onVisibility=()=>schedule();
    try{
      gl=element?.getContext("webgl",{alpha:true,antialias:true,premultipliedAlpha:true});
      if(!gl)throw Error("WebGL unavailable");
      objects=initialize(gl);
      requestDraw.current=schedule;
      if(typeof ResizeObserver==='function'){resize=new ResizeObserver(schedule);resize.observe(element);}
      if(typeof IntersectionObserver==='function'){
        visibility=new IntersectionObserver(entries=>{onScreen=entries.some(entry=>entry.isIntersecting);schedule();});
        visibility.observe(element);
      }
      motion?.addEventListener?.('change',schedule);
      document.addEventListener('visibilitychange',onVisibility);
      onReady?.(true);
      schedule();
    }catch{
      // The layered SVG and the neuron directory remain a usable fallback.
      objects=null;
      onReady?.(false);
    }
    return()=>{
      alive=false;
      requestDraw.current=()=>{};
      if(frame)cancelAnimationFrame(frame);
      if(idle)clearTimeout(idle);
      resize?.disconnect();visibility?.disconnect();
      motion?.removeEventListener?.('change',schedule);
      document.removeEventListener('visibilitychange',onVisibility);
      if(gl){
        if(objects){
          for(const buffer of [objects.shellBuffer,objects.lineBuffer,objects.pointBuffer,objects.pulseBuffer])gl.deleteBuffer(buffer);
          gl.deleteProgram(objects.shell.program);gl.deleteProgram(objects.particles.program);
        }
        // Free the GPU context now instead of waiting for garbage collection.
        gl.getExtension('WEBGL_lose_context')?.loseContext();
      }
    };
  },[onReady]);
  const pick=event=>{
    const box=event.currentTarget.getBoundingClientRect(),x=event.clientX-box.left,y=event.clientY-box.top;
    let best=null,distance=18*18;
    for(const point of projected.current){
      const d=(point.x-x)**2+(point.y-y)**2;
      if(d<distance||(d===distance&&best&&point.z>best.z)){distance=d;best=point;}
    }
    return best?.id||null;
  };
  const byId=new Map(network.nodes.map(n=>[n.id,n]));
  const shown=[...new Set([
    ...network.nodes.filter(n=>n.running).slice(0,5).map(n=>n.id),
    selectedId,highlightId,hovered,
  ].filter(id=>id&&byId.has(id)))];
  return <>
    <canvas ref={canvas} className="ago-real-3d-brain"
      aria-label={"Interactive 3D company brain. Verified running tasks: "+Math.max(0,running)+". Employees: "+network.nodes.length}
      role="img"
      onPointerDown={event=>{drag.current={x:event.clientX,y:event.clientY,start:{...dragAngle.current},moved:false};
        event.currentTarget.setPointerCapture?.(event.pointerId);}}
      onPointerMove={event=>{
        if(drag.current){
          const dx=event.clientX-drag.current.x,dy=event.clientY-drag.current.y;
          if(Math.abs(dx)+Math.abs(dy)>4)drag.current.moved=true;
          dragAngle.current={
            yaw:Math.max(-1.6,Math.min(1.6,drag.current.start.yaw+dx*.008)),
            pitch:Math.max(-.6,Math.min(.5,drag.current.start.pitch+dy*.005)),
          };
          requestDraw.current();
        }else{
          const id=event.pointerType==='mouse'?pick(event):null;
          if(id!==hovered)setHovered(id);
        }
      }}
      onPointerLeave={()=>setHovered(null)}
      onPointerUp={event=>{
        const wasClick=drag.current&&!drag.current.moved;drag.current=null;
        if(event.currentTarget.hasPointerCapture?.(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
        if(wasClick){const id=pick(event);if(id)onPick?.(id);}
      }}
      onPointerCancel={()=>{drag.current=null;}}
      style={{cursor:hovered?'pointer':undefined}}
    />
    <div className="brain-neuron-labels" ref={labels} aria-hidden="true">
      <span data-node="founder" className="brain-neuron-label founder">Founder · human authority</span>
      {shown.map(id=>{const node=byId.get(id);return <span key={id} data-node={id}
        className={'brain-neuron-label tone-'+node.tone+(id===selectedId||id===highlightId?' selected':'')}>
        {node.name}<small>{node.label}</small>
      </span>;})}
    </div>
  </>;
}
