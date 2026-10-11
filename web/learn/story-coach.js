import { stopNavigationVoice } from './navigation-voice.js?v=eleven-autoplay-1';
// Teacher console. The server owns session state; model proposals never directly drive hardware.
let latestEvidence = null;
let activeVoiceCoach = null;
export const storyVoiceContext = () => activeVoiceCoach?.snapshot() || {};
export const performStoryVoice = (name, text) => activeVoiceCoach?.perform(name, text) || Promise.resolve('No story activity is ready.');
export const learnerCoachEvidence = () => latestEvidence ? structuredClone(latestEvidence) : null;
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function mountStoryCoach({player, enabled, pause}) {
  if(!enabled)return {context(){},dispose(){},isPaused(){return false;},observations(){return [];}};
  const panel=document.createElement('aside');panel.className='story-coach';panel.hidden=true;panel.setAttribute('aria-label','Teacher story coach');player.append(panel);
  let state=null,open=false,busy=false,error='',passage=null,version=0,disposed=false,lastSpeech='',latestText='';
  let queue=Promise.resolve();
  const lockedControls=new Map();
  function lockControls(locked){
    const controls=player.querySelectorAll('#reader-play,#reader-prev,#reader-next,#reader-seek,#reader-chapter');
    controls.forEach(control=>{if(locked){if(!lockedControls.has(control))lockedControls.set(control,control.disabled);control.disabled=true;}else if(lockedControls.has(control)){control.disabled=lockedControls.get(control);lockedControls.delete(control);}});
  }
  async function api(path,payload){const response=await fetch('/api/story/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let data;try{data=await response.json();}catch{throw Error('Story Mode needs the updated local server.');}if(!response.ok)throw Error(data.error||'Story Mode unavailable.');const snapshot=data.state||data;if(snapshot.session_id && Array.isArray(snapshot.observations)){latestEvidence={state:structuredClone(snapshot),observedAt:new Date().toISOString()};window.dispatchEvent(new Event('magneto-learner-evidence'));}return data;}
  function render(){
    if(disposed)return;window.dispatchEvent(new Event('magneto-voice-context'));lockControls(['awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state?.phase));panel.hidden=!open;if(!open)return;
    const phase=state?.phase||'reading',proposal=state?.proposal,persona=state?.synthetic_persona;
    const button=(action,label)=>`<button data-coach="${action}" ${busy?'disabled':''}>${label}</button>`;
    panel.innerHTML=`<header><span>TEACHER · STORY COACH</span><button data-coach="close" aria-label="Close teacher panel">×</button></header>${persona?`<p class="coach-note"><strong>Fictional test · ${esc(persona.display_name)}</strong> · ${esc(persona.experience_level)}. You play Alex; all recorded outcomes are synthetic.</p><details><summary>Alex’s starting profile</summary><p>${esc(persona.about_me)}</p><ul>${persona.teaching_preferences.map(p=>`<li>${esc(p)}</li>`).join('')}</ul><p>${esc(persona.testing_note)}</p></details>`:''}<p class="coach-state" role="status">${busy?'Orchestrator working…':esc(phase.replaceAll('_',' '))}</p>${error?`<p class="coach-error" role="alert">${esc(error)}</p>`:''}<h2>${proposal?.target?esc(proposal.kind+' · '+proposal.target):'A moment to learn'}</h2><p>${esc(proposal?.reason||'Ask the orchestrator whether a short Braille activity fits this passage.')}</p>${proposal?.prompt?`<div class="coach-prompt"><small>LEARNER PROMPT</small><p>${esc(proposal.prompt)}</p></div>`:''}${state?.braille?`<div class="coach-cells" aria-label="Visual Braille preview">${state.braille.cells.map(c=>`<span><b>${String.fromCodePoint(0x2800+c.dots.reduce((n,d)=>n+(1<<(d-1)),0))}</b><small>${esc(c.letter)} · ${c.dots.join(',')}</small></span>`).join('')}</div>`:''}${state?.response?`<p class="coach-response">Heard: ${esc(state.response.text)} · Unconfirmed. Teacher records the outcome.</p>`:''}<div class="coach-actions">${['reading','proposed','continue_proposed'].includes(phase)?button('orchestrate','Ask orchestrator'):persona&&phase==='awaiting_confirmation'?button('orchestrate','Ask for a follow-up'):''}${phase==='proposed'?button('approve_activity','Start activity'):''}${phase==='awaiting_tactile'?button('confirm_tactile','Tactile material offered'):''}${['ready','waiting_response'].includes(phase)?button('speak_prompt',phase==='ready'?'Speak prompt':'Repeat prompt'):''}${phase==='waiting_response'?button('give_hint','Give a hint'):''}${['waiting_response','awaiting_confirmation'].includes(phase)?`${button('independent','Independent')}${button('with_help','With help')}${button('try_later','Try later')}`:''}${button('resume_story',phase==='reading'?'Close and read':'Skip / Continue story')}</div>${persona&&phase==='waiting_response'?`<form data-test-reply><label for="alex-reply">Reply as Alex</label><input id="alex-reply" name="reply" maxlength="300" required placeholder="I’m confused. Which part should I learn first?" ${busy?'disabled':''}><button ${busy?'disabled':''}>Send test reply</button></form><p class="coach-note">Try one pattern at a time. A reply stays unconfirmed. A follow-up creates a new proposal for your review.</p>`:''}<p class="coach-note">${state?.braille?'Preview only. Teacher supplies tactile Braille.':'Live model via MCP · Teacher confirms learning observations.'} Use Start listening to answer. Spoken responses need teacher confirmation.</p><details><summary>Tool activity</summary><ol>${(state?.trace||[]).slice(-8).map(t=>`<li>${esc(t.actor)} · ${esc(t.tool)}</li>`).join('')}</ol></details>`;
  }
  async function syncContext(){
    if(!state)state=await api('session',{});
    else state=await api('action',{session_id:state.session_id,name:'get_story_context'});
    state=await api('action',{session_id:state.session_id,revision:state.revision,name:'set_context',arguments:{passage_id:passage}});
  }
  async function action(name,args={}){const token=version;const result=await api('action',{session_id:state.session_id,revision:state.revision,name,arguments:args});if(disposed||token!==version)throw Error('Story context changed.');state=result;}
  async function run(name,args={}){
    if(busy||disposed)return;pause();busy=true;error='';render();const token=version;
    try{
      await queue;
      if(disposed||token!==version)return;
      if(!state)await syncContext();
      if(name==='orchestrate'){
        if(!passage)throw Error('No curated opportunity on this spread. Try meeting Peter, the gate, or the vegetables.');
        const result=await api('orchestrate',{session_id:state.session_id,revision:state.revision});
        if(disposed||token!==version)return;state=result.state;
      }else if(['independent','with_help','try_later'].includes(name))await action('record_observation',{outcome:name});
      else{
        await action(name,args);
        if(name==='approve_activity')await action('prepare_braille');
        if(name==='resume_story'){window.speechSynthesis?.cancel();open=false;}
        if(['speak_prompt','give_hint'].includes(name)&&state.speech?.id!==lastSpeech){
          lastSpeech=state.speech.id;
          if('speechSynthesis'in window){stopNavigationVoice();speechSynthesis.cancel();speechSynthesis.resume();const utterance=new SpeechSynthesisUtterance(state.speech.text);utterance.rate=.85;speechSynthesis.speak(utterance);}else error='Speech is unavailable. Teacher can read the prompt aloud.';
        }
      }
    }catch(e){if(!disposed&&token===version)error=e.message;}
    finally{busy=false;render();}
    return !error;
  }
  panel.onsubmit=event=>{if(!event.target.matches('[data-test-reply]'))return;event.preventDefault();const text=new FormData(event.target).get('reply');if(text?.trim())run('submit_response',{text:text.trim()});};
  panel.onclick=event=>{const name=event.target.closest('[data-coach]')?.dataset.coach;if(!name)return;if(name==='close'){open=false;render();return;}run(name);};
  const trigger=player.querySelector('#open-story-coach');
  trigger.onclick=()=>{pause();open=!open;render();};
  const voiceCoach = {
    snapshot(){return {storySession:state?.session_id,storyRevision:state?.revision,storyPhase:state?.phase,awaitingStoryResponse:state?.phase==='waiting_response'};},
    async perform(name,text){
      if(disposed||busy)return 'The story is busy. Please wait.';
      if(!['submit_response','speak_prompt','give_hint','resume_story'].includes(name))return 'That voice action is unavailable.';
      if(name==='submit_response' && state?.phase!=='waiting_response')return 'The story is not waiting for an answer.';
      const ok=await run(name,name==='submit_response'?{text}:{});
      return ok ? (name==='submit_response'?'Your answer was captured. Your teacher will confirm the outcome.':name==='resume_story'?'Continue reading.':'') : error || 'That story action is unavailable.';
    }
  };
  activeVoiceCoach=voiceCoach;
  return {
    observations(){return structuredClone(state?.observations || []);},
    isPaused(){return ['awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state?.phase);},
    context(text){
      if(text===latestText)return;latestText=text;version++;error='';
      passage=/lettuces.*French beans.*radishes/s.test(text)?'lettuce':/four little Rabbits/i.test(text)?'rabbit':/squeezed under the gate/i.test(text)?'gate':null;
      window.speechSynthesis?.cancel();
      if(state){queue=queue.catch(()=>{}).then(syncContext).catch(e=>{error=e.message;}).finally(render);}
      render();
    },
    dispose(){if(activeVoiceCoach===voiceCoach)activeVoiceCoach=null;lockControls(false);disposed=true;version++;window.speechSynthesis?.cancel();if(state){queue.catch(()=>{}).then(()=>api('action',{session_id:state.session_id,revision:state.revision,name:'set_context',arguments:{passage_id:null}})).catch(()=>{});}panel.remove();}
  };
}
