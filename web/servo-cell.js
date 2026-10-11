import './header.js';
import {mountShell} from './cardboard-shell.js';
import {createDimensions} from './dimensions.js';
import {createServoGeometry} from './servo-geometry.js';
import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
const $=id=>document.getElementById(id),viewport=$('viewport');
const scene=new THREE.Scene();scene.background=new THREE.Color(0xf3f5f7);
const camera=new THREE.PerspectiveCamera(40,1,.1,2000);camera.up.set(0,0,1);
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));viewport.append(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x8195a4,2));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(-80,-120,200);scene.add(light);
const {groups,horns,pins,fingers,latched,chosen,carrier,lidMat,applyCatchFlex}=createServoGeometry(await (await fetch('models/servo-design.json',{cache:'no-store'})).json());
// The cell owns all passive parts. Only the base and servos stay in world space.
const cell=new THREE.Group();scene.add(cell);
groups.station=new THREE.Group();
const housing=groups.frame.children.find(m=>m.userData.sourcePart==='housing');
groups.station.add(housing);scene.add(groups.station,groups.servo);
cell.add(groups.frame,groups.pins,groups.catches);
const detachTravel=40;
const {shell:cardboard,input:shellToggle,electronics,electronicsToggle}=mountShell(scene,document.querySelector('aside'));
let animation=null,isolated=null;
const individual=[];Object.values(groups).forEach(g=>g.traverse(o=>{if(o.isMesh)individual.push(o);}));
individual.forEach((mesh,i)=>$('view').append(new Option(mesh.name,'part-'+i)));
const dimensions=createDimensions(viewport,camera,()=>isolated?[isolated]:Object.values(groups).filter(g=>g.visible),()=>$('view').value!=='all');
const labels={servo:'Six SG90s + horns',pins:'Plungers + 5 mm balls',catches:'Catches + reset tab',frame:'Cell base + reading plate',station:'Fixed servo base + locating posts'};
for(const key of Object.keys(groups)){const row=document.createElement('label');row.className='part';const input=document.createElement('input');input.type='checkbox';input.checked=true;input.id='show-'+key;input.onchange=applyView;row.append(input,document.createTextNode(labels[key]));$('layers').append(row);}
// Reading side numbering: 1 4 / 2 5 / 3 6.
for(const i of [0,3,1,4,2,5]){const b=document.createElement('button');b.textContent='Dot '+(i+1);b.id='dot-'+i;b.setAttribute('aria-pressed','false');b.onclick=()=>{chosen[i]=!chosen[i];syncButtons();};$('dotButtons').append(b);}
function syncButtons(){chosen.forEach((v,i)=>$('dot-'+i).setAttribute('aria-pressed',String(v)));}
function applyView(){const view=$('view').value;isolated=view.startsWith('part-')?individual[Number(view.slice(5))]:null;individual.forEach(mesh=>mesh.visible=!isolated||mesh===isolated);cardboard.visible=view==='all'&&shellToggle.checked;electronics.visible=view==='all'&&electronicsToggle.getAttribute('aria-pressed')==='true';const e=Number($('explode').value)/100;$('explodeValue').textContent=Math.round(e*100)+'%';for(const [key,g]of Object.entries(groups)){g.visible=isolated?true:(view==='all'||view===key)&&$('show-'+key).checked;g.position.z=e*({servo:0,frame:60,pins:40,catches:20,station:0}[key]);}lidMat.opacity=$('transparent').checked?.32:1;pins.forEach(p=>p.children.forEach(m=>{if(m.userData.ball)m.visible=(!isolated||m===isolated)&&(isolated||$('balls').checked);}));}
function fit(mode='iso'){const box=new THREE.Box3();if(cardboard.visible)box.expandByObject(cardboard);if(electronics.visible)box.expandByObject(electronics);(isolated?[isolated]:Object.values(groups).filter(g=>g.visible)).forEach(g=>box.expandByObject(g));if(box.isEmpty())return;const c=box.getCenter(new THREE.Vector3()),s=box.getSize(new THREE.Vector3());const d=Math.max(s.x,s.y,s.z,20)/(2*Math.tan(camera.fov*Math.PI/360))*(isolated?1.85:1.45)/Math.min(camera.aspect,1);const direction=mode==='top'?new THREE.Vector3(0,.001,1):mode==='side'?new THREE.Vector3(0,-1,.05):new THREE.Vector3(.8,-1,.7).normalize();controls.target.copy(c);camera.position.copy(c).add(direction.multiplyScalar(d));controls.update();}
function busy(value){const exploded=Number($('explode').value)>0;$('write').disabled=value||exploded||Math.abs(cell.position.z)>.01;$('reset').disabled=value||exploded;$('hi').disabled=value;$('detach').disabled=value||exploded;$('explode').disabled=value;$('detach').textContent=cell.position.z>20?'Reattach top module':'Detach top module';}
$('detach').onclick=()=>{if(animation)return;animation={kind:'detach',start:performance.now(),from:cell.position.z,to:cell.position.z>20?0:detachTravel};busy(true);$('readout').textContent='Separating the complete top module for inspection; its catches retain the pattern.';};
$('hi').onclick=()=>{chosen.fill(false);[0,1,4].forEach(i=>chosen[i]=true);syncButtons();};
$('write').onclick=()=>{if(animation||Math.abs(cell.position.z)>.01)return;const additions=chosen.map((v,i)=>v&&!latched[i]);if(!additions.some(Boolean)){$('readout').textContent='No new dots selected. Push the tab to clear existing dots.';return;}animation={kind:'write',start:performance.now(),additions};busy(true);$('readout').textContent='Servos lift selected pins; catches flex and engage.';};
$('reset').onclick=()=>{if(animation)return;animation={kind:'reset',start:performance.now(),before:[...latched]};busy(true);$('readout').textContent='Pushing the cell’s reset tab inward to release all catches…';};
shellToggle.onchange=applyView;
const toggleElectronics=electronicsToggle.onclick;electronicsToggle.onclick=()=>{toggleElectronics();applyView();fit();};
$('view').onchange=()=>{applyView();fit();};$('explode').oninput=()=>{applyView();busy(!!animation);};$('transparent').onchange=applyView;$('balls').onchange=applyView;$('fit').onclick=()=>fit();$('iso').onclick=()=>fit();$('top').onclick=()=>fit('top');$('side').onclick=()=>fit('side');
const resize=()=>{const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(viewport);resize();applyView();fit();$('status').textContent='Detachable cell concept · fit, catch flexure and gravity reset untested';
function frame(now){requestAnimationFrame(frame);
 if(animation){const t=(now-animation.start)/1000;
  if(animation.kind==='write'){
   const rise=Math.min(1,t/.8),retract=Math.max(0,Math.min(1,(t-1)/.7)),angle=(1-retract)*rise*Math.asin(4.75/16);
   for(let i=0;i<6;i++){if(!animation.additions[i])continue;horns[i].rotation.y=-horns[i].userData.sign*angle;pins[i].position.z=Math.max(0,4.75*rise-2.35);fingers[i].position.y=2.2*Math.sin(rise*Math.PI);}
   if(t>1){animation.additions.forEach((v,i)=>{if(v)latched[i]=true;});$('readout').textContent='Catches hold the pins while servo horns retract.';}
   if(t>=1.8){horns.forEach(h=>h.rotation.y=0);fingers.forEach(f=>f.position.y=0);animation=null;busy(false);$('readout').textContent='Letter held by catches. Servos are retracted. Detach the top module, or push its tab to reset.';}
  }else if(animation.kind==='detach'){
   const u=Math.min(1,t/1.6),smooth=u*u*(3-2*u);cell.position.z=animation.from+(animation.to-animation.from)*smooth;
   $('detachPosition').textContent=cell.position.z.toFixed(1)+' mm';
   if(u===1){animation=null;busy(false);fit();$('readout').textContent=cell.position.z>20?'Top module detached. Guides, plungers and catches stay together; pattern retained.':'Aligned over the servos. Ready to write.';}
  }else{
   const pull=Math.min(1,t/.6),fallSeconds=Math.max(0,t-.65)/20,fallDistance=Math.min(2.4,.5*9810*fallSeconds**2),release=Math.min(1,Math.max(0,(t-1.3)/.5));carrier.position.y=6*pull*(1-release);animation.before.forEach((v,i)=>pins[i].position.z=v?Math.max(0,2.4-fallDistance):0);
   if(t>=1.9){latched.fill(false);pins.forEach(p=>p.position.z=0);carrier.position.y=0;animation=null;busy(false);$('readout').textContent='Blank cell. Tab returned; ready to write again.';}
  }
 }
 applyCatchFlex();controls.update();dimensions.update();renderer.render(scene,camera);
}
requestAnimationFrame(frame);
// Read-only hooks for checking state during local QA.
window.servoCellState=()=>({latched:[...latched],selected:[...chosen],tabTravel:carrier.position.y,cellX:cell.position.x,cellZ:cell.position.z,stationX:groups.station.position.x,hornAngles:horns.map(h=>h.rotation.y),plungerLift:pins.map(p=>p.position.z),gravityStops:[45.4],busy:!!animation,parts:Object.keys(groups)});

if(new URLSearchParams(location.search).has('visualizer')){const {mountSignalVisualizer}=await import('./signal-visualizer.js');mountSignalVisualizer();}
