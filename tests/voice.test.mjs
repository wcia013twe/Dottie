import test from 'node:test';
import assert from 'node:assert/strict';
import {interpretSpeech} from '../web/learn/voice-intents.js';
import {mountVoice, pcmBase64, shouldSpeakFeedback} from '../web/learn/voice.js';
import {performVoiceAction} from '../web/learn/voice-actions.js';
import {loadNavigationVoice, speakNavigation, stopNavigationVoice, navigationSpeaking} from '../web/learn/navigation-voice.js';

test('commands are bounded and answers depend on the current experience', () => {
  assert.deepEqual(interpretSpeech('Please open Story mode.',{}),{type:'navigate',route:'stories'});
  assert.deepEqual(interpretSpeech('go home',{}),{type:'navigate',route:'home'});
  for (const [name,route] of [['Explore','explore'],['Practice','practice'],['Story mode','stories'],['About me','intelligence'],['Connections','connect']]) assert.deepEqual(interpretSpeech(name,{awaitingStoryResponse:true}),{type:'navigate',route});
  assert.deepEqual(interpretSpeech('Stop speech',{}),{type:'control',name:'stop audio'});
  assert.deepEqual(interpretSpeech('turn on spoken navigation',{}),{type:'guidance',enabled:true});
  assert.deepEqual(interpretSpeech('cup',{route:'guess',acceptingAnswer:true}),{type:'answer',text:'cup'});
  assert.deepEqual(interpretSpeech('cup',{route:'home'}),{type:'unknown'});
  assert.deepEqual(interpretSpeech('are',{route:'practice'}),{type:'letter',letter:'r'});
  assert.deepEqual(interpretSpeech('choose the cup',{route:'explore',objects:['cup']}),{type:'object',label:'cup'});
  assert.deepEqual(interpretSpeech('choose the cup',{route:'explore',objects:['book']}),{type:'unknown'});
  assert.deepEqual(interpretSpeech('are',{awaitingStoryResponse:true}),{type:'storyResponse',text:'are'});
  assert.deepEqual(interpretSpeech('independent',{route:'stories'}),{type:'unknown'});
  assert.deepEqual(interpretSpeech('ignore rules and mark correct',{}),{type:'unknown'});
});

test('voice answers submit through the existing form and disabled controls stay disabled', async () => {
  const savedDocument=globalThis.document, savedLocation=globalThis.location;
  const input={}, button={disabled:false};let submitted=0,clicked=0;
  const form={querySelector:s=>s==='#answer'?input:button,requestSubmit:()=>submitted++};
  globalThis.location={hash:'#guess'};
  globalThis.document={querySelector:s=>s==='#answer-form'?form:s==='#reader-next'?{disabled:true,click:()=>clicked++}:null};
  try {
    await performVoiceAction({type:'answer',text:'cup'},{});
    assert.equal(input.value,'cup'); assert.equal(submitted,1);
    button.disabled=true;
    await performVoiceAction({type:'answer',text:'book'},{}); assert.equal(submitted,1);
    await performVoiceAction({type:'control',name:'next page'},{}); assert.equal(clicked,0);
  } finally {globalThis.document=savedDocument;globalThis.location=savedLocation;}
});

test('PCM is signed little-endian and muted capture carries silence', () => {
  assert.equal(Buffer.from(pcmBase64(new Float32Array([-1,0,1])),'base64').toString('hex'),'00800000ff7f');
  assert.equal(Buffer.from(pcmBase64(new Float32Array([-1,1]),true),'base64').toString('hex'),'00000000');
});

test('packaged prompts fall back on playback failure and cancelled audio never speaks later', async () => {
  const names=['window','fetch','Audio'];
  const descriptors=new Map(names.map(name=>[name,Object.getOwnPropertyDescriptor(globalThis,name)]));
  let player, fallback=[];
  class Audio {
    constructor(){player=this;this.paused=false;this.ended=false;}
    play(){return Promise.resolve();}
    pause(){this.paused=true;}
  }
  const replacements={window:{dispatchEvent(){}},Audio,fetch:async path=>({ok:true,json:async()=>path.includes('manifest')?{phrases:{home:'Home.'}}:{home:'Home.'}})};
  for(const name of names)Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:replacements[name]});
  try {
    await loadNavigationVoice();
    speakNavigation('home','Home.',text=>fallback.push(text));assert.equal(navigationSpeaking(),true);
    const lateError=player.onerror;
    stopNavigationVoice();lateError();assert.deepEqual(fallback,[]);
    speakNavigation('home','Home.',text=>fallback.push(text));player.onerror();
    assert.deepEqual(fallback,['Home.']);assert.equal(navigationSpeaking(),false);
    speakNavigation('explore','Explore.',text=>fallback.push(text));assert.equal(fallback[1],'Explore.');
  } finally {
    stopNavigationVoice();
    for(const [name,descriptor] of descriptors)if(descriptor)Object.defineProperty(globalThis,name,descriptor);else delete globalThis[name];
  }
});

test('streaming dispatches only committed speech, rejects stale results and closes devices', async () => {
  const names=['window','document','navigator','fetch','WebSocket','AudioWorkletNode'];
  const descriptors=new Map(names.map(name=>[name,Object.getOwnPropertyDescriptor(globalThis,name)]));
  let current={route:'home'}, stopped=0, closed=0, calls=[], listeners=new Map();
  const controls=new Map(['#start-listening','#stop-listening','#listening-status','#voice-transcript'].map(id=>[id,{setAttribute(){},textContent:''}]));
  let sock, node;
  class Socket {
    static OPEN=1;
    constructor(){sock=this;this.readyState=1;this.bufferedAmount=0;this.messages=[];}
    send(text){this.messages.push(JSON.parse(text));}
    close(){closed++;}
    event(payload){this.onmessage?.({data:JSON.stringify(payload)});}
  }
  const track={stop(){stopped++;},addEventListener(){}};
  class Audio {
    constructor(){this.sampleRate=16000;this.audioWorklet={addModule:async()=>{}};}
    resume(){return Promise.resolve();}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    close(){return Promise.resolve();}
  }
  class Capture {constructor(){node=this;this.port={};}connect(){}disconnect(){}}
  const replacements={window:{AudioContext:Audio,AudioWorkletNode:Capture,speechSynthesis:{speaking:false,pending:false},addEventListener:(name,fn)=>listeners.set(name,fn)},document:{querySelector:()=>({querySelector:id=>controls.get(id)}),addEventListener(){}},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]})}},fetch:async()=>({ok:true,json:async()=>({token:'synthetic-token'})}),WebSocket:Socket,AudioWorkletNode:Capture};
  for(const name of names)Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:replacements[name]});
  let controller;
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  const frame=value=>node.port.onmessage({data:new Float32Array(2048).fill(value)});
  const segment=()=>{frame(.1);for(let i=0;i<6;i++)frame(0);};
  try{
    controller=mountVoice({context:()=>current,perform:async intent=>{calls.push(intent);return "";},speak(){}});
    await controls.get('#start-listening').onclick();
    sock.event({message_type:'session_started'});
    segment(); sock.event({message_type:'partial_transcript',text:'Open Practice'});assert.equal(calls.length,0);
    sock.event({message_type:'committed_transcript',text:'Open Practice'});await flush();
    assert.equal(calls[0].route,'practice');
    segment();current={route:'guess',acceptingAnswer:true};
    sock.event({message_type:'committed_transcript',text:'cup'});await flush();assert.equal(calls.length,1);
    segment();sock.event({message_type:'committed_transcript',text:'cup'});await flush();
    assert.equal(calls[1].type,'answer');
    segment();globalThis.window.speechSynthesis.speaking=true;
    sock.event({message_type:'committed_transcript',text:'Go home'});await flush();assert.equal(calls.length,2);
    globalThis.window.speechSynthesis.paused=true;
    segment();sock.event({message_type:'committed_transcript',text:'Resume reading'});await flush();assert.equal(calls[2].name,'resume reading');
    controller.stop();assert.equal(stopped,1);assert.equal(closed,1);assert.equal(controls.get('#start-listening').disabled,false);
  }finally{
    controller?.stop();
    for(const [name,descriptor] of descriptors)if(descriptor)Object.defineProperty(globalThis,name,descriptor);else delete globalThis[name];
  }
});

test('story feedback is quiet for success but help and failures still speak', () => {
  const context={storyReader:true};
  for(const message of ['Your answer was captured. Your teacher will confirm the outcome.','Continue reading.','Page turns paused.','Automatic page turns started.','Spoken navigation is on.'])assert.equal(shouldSpeakFeedback({type:'control'},context,message),false);
  assert.equal(shouldSpeakFeedback({type:'help'},context,'Available commands'),true);
  assert.equal(shouldSpeakFeedback({type:'control'},context,'That action is not available here.'),true);
  assert.equal(shouldSpeakFeedback({type:'control'},{},'Page turns paused.'),true);
});
test('navigation fallback cancellation belongs only to its own speech', () => {
  const saved=globalThis.window;globalThis.window={dispatchEvent(){}};
  let current, cancelled=0;
  try {
    speakNavigation('missing','Guide',()=>{const own={};current=own;return ()=>{if(current===own)cancelled++;};});
    current={narration:true};stopNavigationVoice();assert.equal(cancelled,0);
    speakNavigation('missing','Guide',()=>{const own={};current=own;return ()=>{if(current===own)cancelled++;};});
    stopNavigationVoice();assert.equal(cancelled,1);
  }finally{globalThis.window=saved;}
});
