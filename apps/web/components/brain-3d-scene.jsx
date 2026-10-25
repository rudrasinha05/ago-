"use client";
import {useEffect,useRef,useState} from "react";

// Real 3D lobe surfaces, drawn through WebGL depth testing (no remote assets).
// Highlighting is tied ONLY to actual persisted running task count.
const VERTEX = `
attribute vec4 position;
attribute vec3 normal;
uniform float yaw;
uniform float pitch;
uniform float working;
varying float lit;
varying float groove;
varying float rim;
varying float activity;
void main(){
 float cy=cos(yaw),sy=sin(yaw),cp=cos(pitch),sp=sin(pitch);
 vec3 p=vec3(cy*position.x+sy*position.z,position.y,-sy*position.x+cy*position.z);
 vec3 n=normalize(vec3(cy*normal.x+sy*normal.z,normal.y,-sy*normal.x+cy*normal.z));
 p=vec3(p.x,cp*p.y-sp*p.z,sp*p.y+cp*p.z);
 n=normalize(vec3(n.x,cp*n.y-sp*n.z,sp*n.y+cp*n.z));
 float perspective=2.8/(3.8-p.z);
 gl_Position=vec4(p.x*.94*perspective,p.y*1.02*perspective,-p.z*.24,1.0);
 lit=clamp(.22+.84*max(dot(n,normalize(vec3(-.55,.70,1.0))),0.0),.15,1.0);
 groove=position.w;
 rim=pow(1.0-clamp(n.z,0.0,1.0),2.0);
 activity=working;
}`;
const FRAGMENT = `
precision mediump float;
varying float lit;
varying float groove;
varying float rim;
varying float activity;
void main(){
 float fold=smoothstep(-.35,.4,groove);
 vec3 cortex=mix(vec3(.035,.10,.24),vec3(.37,.73,.93),lit);
 cortex*=mix(.51,1.21,fold);
 cortex+=vec3(.07,.15,.25)*rim;
 if(activity>.5)cortex=mix(cortex,vec3(.96,.26,.48),.18+.18*(1.0-fold));
 gl_FragColor=vec4(cortex,1.0);
}`;

function brainVertices() {
 const out=[],latCount=42,lonCount=58;
 const surface=(side,a,b)=>{
   const u=-Math.PI/2+(a/latCount)*Math.PI,v=(b/lonCount)*2*Math.PI;
   const fold=Math.sin(14*v+1.5*Math.sin(5*u))*Math.cos(17*u+Math.sin(5*v))
     +.35*Math.sin(25*u+4*v);
   const size=1+.072*fold;
   const x=side*.47+Math.cos(u)*Math.cos(v)*.52*size;
   const y=Math.sin(u)*.83*size-.03*Math.cos(v*2);
   const z=Math.cos(u)*Math.sin(v)*.75*size;
   const cleft=side*.055*Math.exp(-Math.pow(x/.14,2))*Math.max(0,z+.3);
   return [x+cleft,y,z,fold];
 };
 const emit=(p,n)=>{out.push(...p,...n);};
 const tri=(p,q,r,side)=>{
   const a=q.map((v,i)=>i<3?v-p[i]:0),b=r.map((v,i)=>i<3?v-p[i]:0);
   let n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
   const center=(p[0]+q[0]+r[0])/3-side*.47;
   if(n[0]*center+n[1]*(p[1]+q[1]+r[1])/3+n[2]*(p[2]+q[2]+r[2])/3<0)n=n.map(x=>-x);
   const len=Math.hypot(...n)||1;n=n.map(x=>x/len);
   emit(p,n);emit(q,n);emit(r,n);
 };
 for(const side of [-1,1])for(let a=0;a<latCount;a++)for(let b=0;b<lonCount;b++){
    const p=surface(side,a,b),q=surface(side,a+1,b),r=surface(side,a+1,b+1),t=surface(side,a,b+1);
    tri(p,q,t,side);tri(q,r,t,side);
 }
 return new Float32Array(out);
}

function shader(gl,type,code){
  const result=gl.createShader(type);
  gl.shaderSource(result,code);
  gl.compileShader(result);
  if(!gl.getShaderParameter(result,gl.COMPILE_STATUS)){
    gl.deleteShader(result);
    throw Error("3D scene shader unavailable");
  }
  return result;
}
function initialize(gl) {
  const program=gl.createProgram();
  const vertex=shader(gl,gl.VERTEX_SHADER,VERTEX);
  const fragment=shader(gl,gl.FRAGMENT_SHADER,FRAGMENT);
  gl.attachShader(program,vertex);
  gl.attachShader(program,fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)){
    gl.deleteProgram(program);
    throw Error("3D scene program unavailable");
  }
  const buffer=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  const vertices=brainVertices();
  gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);
  gl.useProgram(program);
  const attr=gl.getAttribLocation(program,"position");
  const normal=gl.getAttribLocation(program,"normal");
  if(attr<0||normal<0)throw Error("Missing 3D vertices");
  gl.vertexAttribPointer(attr,4,gl.FLOAT,false,28,0);
  gl.vertexAttribPointer(normal,3,gl.FLOAT,false,28,16);
  gl.enableVertexAttribArray(attr);
  gl.enableVertexAttribArray(normal);
  gl.enable(gl.DEPTH_TEST);
  gl.depthFunc(gl.LEQUAL);
  return {program,buffer,count:vertices.length/7,
    yaw:gl.getUniformLocation(program,"yaw"),
    pitch:gl.getUniformLocation(program,"pitch"),
    working:gl.getUniformLocation(program,"working")};
}

export function Brain3DScene({running,rotation=0,onReady}) {
  const canvas=useRef(null),drag=useRef(null);
  const [dragAngle,setDragAngle]=useState(0);
  useEffect(()=>{
    let frame=0,gl=null,objects=null,alive=true;
    try{
      gl=canvas.current?.getContext("webgl",{alpha:true,antialias:true});
      if(!gl)throw Error("WebGL unavailable");
      objects=initialize(gl);
      onReady?.(true);
      const draw=()=>{
        if(!alive||!canvas.current)return;
        const deviceRatio=Math.min(window.devicePixelRatio||1,2);
        const displayWidth=Math.min(1024,Math.max(1,Math.floor(canvas.current.clientWidth*deviceRatio)));
        const displayHeight=Math.min(600,Math.max(1,Math.floor(canvas.current.clientHeight*deviceRatio)));
        if(canvas.current.width!==displayWidth||canvas.current.height!==displayHeight){
          canvas.current.width=displayWidth;canvas.current.height=displayHeight;
        }
        gl.viewport(0,0,displayWidth,displayHeight);
        gl.clearColor(0,0,0,0);
        gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
        gl.useProgram(objects.program);
        gl.uniform1f(objects.yaw,Math.PI*(rotation+dragAngle)/180);
        gl.uniform1f(objects.pitch,-.12);
        gl.uniform1f(objects.working,Math.max(0,running));
        gl.drawArrays(gl.TRIANGLES,0,objects.count);
        frame=requestAnimationFrame(draw);
      };
      frame=requestAnimationFrame(draw);
    }catch{
      // Existing layered SVG remains a usable, keyboard-accessible fallback.
      onReady?.(false);
    }
    return()=>{
      alive=false;
      cancelAnimationFrame(frame);
      if(gl&&objects){gl.deleteBuffer(objects.buffer);gl.deleteProgram(objects.program);}
    };
  },[running,rotation,dragAngle,onReady]);
  return <canvas ref={canvas} className="ago-real-3d-brain"
    aria-label={"Interactive 3D company brain. Verified running tasks: "+Math.max(0,running)}
    role="img"
    onPointerDown={event=>{drag.current={x:event.clientX,angle:dragAngle};
      event.currentTarget.setPointerCapture?.(event.pointerId);}}
    onPointerMove={event=>{if(drag.current){
      setDragAngle(Math.max(-75,Math.min(75,drag.current.angle+
        (event.clientX-drag.current.x)*.3)));
    }}}
    onPointerUp={()=>{drag.current=null;}}
    onPointerCancel={()=>{drag.current=null;}}
  />;
}
