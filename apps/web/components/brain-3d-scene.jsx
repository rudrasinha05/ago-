"use client";
import {useEffect,useRef,useState} from "react";

// Real 3D lobe surfaces, drawn through WebGL depth testing (no remote assets).
// Highlighting is tied ONLY to actual persisted running task count.
const VERTEX = `
attribute vec4 position;
uniform float yaw;
uniform float pitch;
uniform float working;
varying float lighting;
varying float ridge;
varying float activity;
void main() {
  float cy = cos(yaw), sy = sin(yaw);
  float cp = cos(pitch), sp = sin(pitch);
  vec3 p = vec3(cy*position.x+sy*position.z,position.y,-sy*position.x+cy*position.z);
  p = vec3(p.x,cp*p.y-sp*p.z,sp*p.y+cp*p.z);
  float depth = 2.9/(2.9-p.z*.24);
  gl_Position = vec4(p.x*.57*depth,p.y*.72*depth,p.z*.22,1.0);
  lighting = clamp(.3+.6*(p.z+1.4)/2.8,0.2,1.0);
  ridge = position.w;
  activity = working;
}
`;
const FRAGMENT = `
precision mediump float;
varying float lighting;
varying float ridge;
varying float activity;
void main() {
  vec3 cool = mix(vec3(.05,.18,.46),vec3(.31,.73,.95),lighting);
  vec3 hot = mix(vec3(.36,.08,.39),vec3(.98,.26,.45),lighting);
  vec3 tone = mix(cool,hot,step(1.0,activity)*.85);
  gl_FragColor = vec4(tone*(.66+.34*ridge),1.0);
}
`;

function brainVertices() {
  const verts=[];
  const latCount=30,lonCount=38;
  // Left and right lobes contain 3D sulci/gyral ridges, not duplicated flat planes.
  const surface=(side,a,b)=>{
    const lat=(a/latCount)*Math.PI;
    const lon=(b/lonCount)*2*Math.PI;
    const folds=Math.sin(9*lon+2*Math.sin(4*lat))*Math.cos(13*lat);
    const warp=1+.055*folds;
    const x=side*.58+Math.sin(lat)*Math.cos(lon)*.54*warp;
    const y=Math.cos(lat)*.9*warp;
    const z=Math.sin(lat)*Math.sin(lon)*.79*warp;
    return [x,y,z,.7+.3*(folds+1)/2];
  };
  for(const side of [-1,1]){
    for(let a=0;a<latCount;a++){
      for(let b=0;b<lonCount;b++){
        const p=surface(side,a,b),q=surface(side,a+1,b);
        const r=surface(side,a+1,b+1),s=surface(side,a,b+1);
        verts.push(...p,...q,...s,...q,...r,...s);
      }
    }
  }
  return new Float32Array(verts);
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
  if(attr<0)throw Error("Missing 3D vertices");
  gl.vertexAttribPointer(attr,4,gl.FLOAT,false,0,0);
  gl.enableVertexAttribArray(attr);
  gl.enable(gl.DEPTH_TEST);
  gl.depthFunc(gl.LEQUAL);
  return {program,buffer,count:vertices.length/4,
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
