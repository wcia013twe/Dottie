import { restoreCoachSession } from './reading-session.js';
import { stopNavigationVoice } from './navigation-voice.js?v=conversational-navigation-2';
import {StoryMemory} from './story-memory.js?v=nano-story-4';
import {createLookahead, opportunityFor, plannedQuestion, questionStops, shouldOfferInteraction} from './story-lookahead.js?v=nano-story-4';
import {createInteractionPlayer, feedbackFor} from './interaction-player.js?v=nano-story-4';
import { createPreparation } from './story-preparation.js';
// Teacher console. The server owns session state; model proposals never directly drive hardware.
let latestEvidence = null;
let activeVoiceCoach = null;
export const storyVoiceContext = () => activeVoiceCoach?.snapshot() || {};
export const performStoryVoice = (name, text) => activeVoiceCoach?.perform(name, text) || Promise.resolve('No story activity is ready.');
export const learnerCoachEvidence = () => latestEvidence ? structuredClone(latestEvidence) : null;
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function mountStoryCoach({player, book, save = () => {}, enabled, checkpoints = [], pause, onResume = () => {}, onQuestionStops = () => {}}) {
  if(!enabled)return {context(){},dispose(){},isPaused(){return false;},observations(){return [];}};
  const readingSessionId=book?.readingSessionId;
  const panel=document.createElement('aside');panel.className='story-coach';panel.hidden=true;panel.setAttribute('aria-label','Teacher story coach');player.append(panel);
  let state=null,open=false,busy=false,error='',passage=null,version=0,disposed=false,lastSpeech='',latestPage=undefined;
  let queue=Promise.resolve();
  const lockedControls=new Map();
  const memory=new StoryMemory();
  const preparation=createPreparation(api, render);
  const lookahead=createLookahead(api,render), interaction=createInteractionPlayer(player);
  let interactionAudio={}, windowTargets=[], narrationEnded=false, review=null, reviewId=null;
  const offered=new Set();
  const generationStatus=document.createElement('p');generationStatus.className='question-stop-label';generationStatus.setAttribute('role','status');player.querySelector('.player-controls').append(generationStatus);
  const readyHere=()=>lookahead.status==='ready' && lookahead.target===passage;
  const preparationStatus=()=>readyHere()?'ready':['preparing','failed'].includes(lookahead.status)?lookahead.status:preparation.status;
  function lockControls(locked){
    const controls=player.querySelectorAll('#reader-play,#reader-prev,#reader-next,#reader-seek,#reader-chapter');
    controls.forEach(control=>{if(locked){if(!lockedControls.has(control))lockedControls.set(control,control.disabled);control.disabled=true;}else if(lockedControls.has(control)){control.disabled=lockedControls.get(control);lockedControls.delete(control);}});
  }
  async function api(path,payload){const response=await fetch('/api/story/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});let data;try{data=await response.json();}catch{throw Error('Story Mode needs the updated local server.');}if(!response.ok)throw Error(data.error||'Story Mode unavailable.');const snapshot=data.state||data;if(snapshot.session_id && Array.isArray(snapshot.observations)){latestEvidence={state:structuredClone(snapshot),observedAt:new Date().toISOString()};window.dispatchEvent(new Event('magneto-learner-evidence'));}return data;}
  function render(){
    if(disposed)return;window.dispatchEvent(new Event('magneto-voice-context'));
    onQuestionStops(questionStops(plannedQuestion({state,passage,windowTargets,status:lookahead.status,preview:lookahead.preview,target:lookahead.target}), [...memory.rows, ...(state?.observations||[])], checkpoints, memory.reviews));
    generationStatus.textContent=error || (lookahead.status==='failed'?'AI interaction unavailable. Check the local Databricks login and retry in Teacher coach.':lookahead.status==='preparing'?'Preparing the next narrated interaction…':lookahead.status==='ready'?(lookahead.preview?.tool==='recommend_continue'?'AI chose to continue the story.':'Narrated interaction ready for the upcoming story moment.'):'');
    generationStatus.hidden=!generationStatus.textContent;
    if(!review && shouldOfferInteraction({ended:narrationEnded,ready:readyHere() || (state?.phase==='proposed' && state?.passage_id===passage),busy,phase:state?.phase,offered:offered.has(passage)})){
      offered.add(passage);queueMicrotask(()=>{if(!disposed)run('auto_offer');});
    }
    lockControls(['awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state?.phase));panel.hidden=!open;if(!open)return;
    const phase=state?.phase||'reading',preview=readyHere()?lookahead.preview:null,proposal=state?.proposal||(['propose_activity','propose_word_emphasis'].includes(preview?.tool)?{...preview.arguments,kind:preview.arguments.target.length===1?'letter':'word'}:preview?.arguments);
    const button=(action,label)=>`<button data-coach="${action}" ${busy?'disabled':''}>${label}</button>`;
    const persona=state?.synthetic_persona;
    const checkpoint=checkpoints.find(c=>c.id===passage);
    const display=review || proposal;
    const waiting=['waiting_response','awaiting_confirmation'].includes(phase);
    const heading=review?'Your earlier activity':display?.target?`Explore ${display.target.toUpperCase()}`:'A moment to explore';
    const status=review?`Saved · ${review.status.replaceAll('_',' ')}`:busy?'Connecting…':waiting?'Your turn':state?.device?.state==='not_configured'?'Device not connected':phase==='proposed'?'Activity ready':'Reading';
    panel.innerHTML=`<header><span>${review?'STORY REVIEW':'STORY MOMENT'}</span><button data-coach="close" aria-label="Close activity">×</button></header>
      <p class="coach-state" role="status">${esc(status)}</p><h2>${esc(heading)}</h2>
      ${display?.prompt?`<p class="coach-question">${esc(display.prompt)}</p>`:'<p class="coach-question">An activity will appear here as you read.</p>'}
      ${error?`<p class="coach-error" role="alert">${esc(error)}</p>`:''}
      ${!review && state?.device?.message?`<p class="coach-device ${state.device.cell_ack?'acknowledged':''}"><span aria-hidden="true">${state.device.cell_ack?'●':'○'}</span> ${esc(state.device.message)}</p>`:''}
      ${review?.response || (!review && state?.response?.text)?`<p class="coach-response">You said: “${esc(review?.response||state.response.text)}”</p>`:''}
      <div class="coach-quick-actions">${display?.prompt?button(review?'replay_review':'replay_prompt','↻ Replay'):''}${!review && phase==='waiting_response'?button('give_hint','Hint'):''}${!review && phase==='proposed'?button('connect_activity','Retry device'):''}</div>
      ${!review && waiting?`<form data-test-reply><label for="story-reply">Your answer</label><div class="coach-answer"><input id="story-reply" name="reply" maxlength="300" required placeholder="Speak or type your answer" ${busy||phase==='awaiting_confirmation'?'disabled':''}><button ${busy||phase==='awaiting_confirmation'?'disabled':''}>Send</button></div></form>`:''}
      ${!review && waiting?`<details class="coach-record"><summary>Record an outcome</summary><p>Record what you observed. Spoken or typed answers remain unconfirmed.</p><div class="coach-actions">${button('independent','Independent')}${button('with_help','With help')}${button('try_later','Try later')}</div></details>`:''}
      <div class="coach-footer">${button(review?'close_review':'resume_story',review?'Back to reading':'Continue story →')}</div>
      <details class="coach-details"><summary>Activity details</summary>
        ${persona?`<p class="coach-note">Fictional test · ${esc(persona.display_name)}</p>`:''}
        ${checkpoint?`<p><strong>Materials</strong><br>${checkpoint.required_materials.map(esc).join('; ')}</p>`:''}
        ${display?.reason?`<p><strong>Why this activity</strong><br>${esc(display.reason)}</p>`:''}
        ${state?.braille && !review?`<div class="coach-cells" aria-label="Braille patterns">${state.braille.cells.map(c=>`<span><b>${String.fromCodePoint(0x2800+c.dots.reduce((n,d)=>n+(1<<(d-1)),0))}</b><small>${esc(c.letter)}</small></span>`).join('')}</div>`:''}
        ${state?.device?.receipt && !review?`<p class="coach-note">Last cell receipt: ${esc(state.device.receipt)}${state.device.sequence_started?' · word sequence started; completion not verified':''}</p>`:''}
        ${['reading','proposed','continue_proposed'].includes(phase) && !review?`<div class="coach-actions">${button('orchestrate','New suggestion')}${button('toggle_word_emphasis',state?.policy?.word_emphasis_enabled?'Word activities off':'Word activities on')}${phase==='proposed'?button('approve_activity','Use teacher-supplied Braille'):''}</div>`:''}
        ${memory.error?`<p role="alert">${esc(memory.error)}</p>`:''}
        <p class="coach-note">Saved activities stay in this browser. Device receipts confirm commands, not mechanical reliability.</p>
        <details><summary>Saved interactions</summary>${memory.reviews.filter(r=>r.passage_id===passage).map(r=>`<p><button data-review-id="${esc(r.id)}">${esc(r.target.toUpperCase())} · ${esc(r.status.replaceAll('_',' '))}</button></p>`).join('')||'<p>No saved interactions here yet.</p>'}</details>
        <details><summary>Practice history</summary>${(state?.review_candidates||[]).map(r=>`<p>${esc(r.target.toUpperCase())} · ${esc(r.reason)}</p>`).join('')||'<p>No recorded practice yet.</p>'}</details>
        <details><summary>Technical log</summary><ol>${(state?.trace||[]).slice(-8).map(t=>`<li>${esc(t.tool)}</li>`).join('')}</ol></details>
      </details>`;
  }
  async function syncContext(target=passage){
    if(!state)state=await restoreCoachSession({sessionId:book?.coachSessionId, api, history:memory.rows});
    else state=await api('action',{session_id:state.session_id,name:'get_story_context'});
    if(book && book.readingSessionId===readingSessionId){book.coachSessionId=state.session_id;save();}
    if(disposed)return;
    for(const saved of memory.reviews)if(saved.session_id===state.session_id)offered.add(saved.passage_id);
    if(state.phase==='proposed' && offered.has(state.passage_id))open=true;
    if(state.passage_id!==target || state.device_released)state=await api('action',{session_id:state.session_id,revision:state.revision,name:'set_context',arguments:{passage_id:target}});
    if(['awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state.phase)){open=true;reviewId=memory.reviews.filter(r=>r.session_id===state.session_id && r.passage_id===state.passage_id).at(-1)?.id||state.session_id+':'+state.revision;memory.saveReview(reviewId,state,interactionAudio,state.response?.text?'answer_unconfirmed':'presented');}
  }
  async function action(name,args={}){const token=version;const result=await api('action',{session_id:state.session_id,revision:state.revision,name,arguments:args});if(name==='record_observation'&&!result.synthetic_persona)memory.remember(result.observations,result.session_id);if(disposed||token!==version)throw Error('Story context changed.');state=result;if(reviewId && ['submit_response','record_observation'].includes(name))memory.saveReview(reviewId,state,interactionAudio,name==='record_observation'?args.outcome:'answer_unconfirmed');preparation.invalidate();}
  async function startActivity(){
    reviewId=reviewId||state.session_id+':'+state.revision;memory.saveReview(reviewId,state,interactionAudio,'presented');
    await action('approve_activity');await action(state.proposal.activity==='emphasize'?'prepare_word_sequence':'prepare_braille');await action('confirm_tactile');await action('speak_prompt');
    lastSpeech=state.speech.id;
    interaction.play({url:interactionAudio.prompt,text:state.speech.text});
  }
  async function resume(clip){
    const token=version;
    if(reviewId && state?.proposal)memory.saveReview(reviewId,state,interactionAudio,state.phase==='complete'?(state.observations.at(-1)?.outcome||'recorded'):state.response?.text?'answer_unconfirmed':'skipped');
    await action('resume_story');lookahead.invalidate();
    const completed=await interaction.play({clip});
    if(disposed||token!==version)return;
    open=false;render();
    if(completed)onResume();
    else error='Audio was interrupted. Continue with the page arrow when ready.';
  }
  async function run(name,args={}){
    if(busy||disposed)return;interaction.stop();stopNavigationVoice();pause();busy=true;error='';render();const token=version;
    try{
      await queue;
      if(disposed||token!==version)return;
      if(!state)await syncContext();
      if(name==='replay_review'){interaction.play({url:review?.audio,text:review?.prompt});return;}
      if(name==='close_review'){review=null;open=false;return;}
      if(name==='replay_prompt'){interaction.play({url:interactionAudio.prompt,text:state?.proposal?.prompt});return;}
      if(name==='connect_activity'){reviewId=reviewId||state.session_id+':'+state.revision;memory.saveReview(reviewId,state,interactionAudio,'presented');await action('start_device_activity');if(state.phase==='waiting_response')interaction.play({url:interactionAudio.prompt,text:state.speech.text});return;}
      if(name==='toggle_word_emphasis'){await action('set_word_emphasis',{enabled:!state.policy.word_emphasis_enabled});lookahead.invalidate();interactionAudio={};if(passage)lookahead.prepare(state,passage);return;}
      if(name==='orchestrate'||name==='start_prepared'||name==='auto_offer'){
        if(!passage)throw Error('No curated opportunity on this spread. Try meeting Peter, the gate, or the vegetables.');
        const result=name==='auto_offer' && state.phase==='proposed'?{state,interaction_audio:interactionAudio}:state.synthetic_persona&&state.phase==='awaiting_confirmation'?await api('orchestrate',{session_id:state.session_id,revision:state.revision}):readyHere()?await lookahead.apply(state):await preparation.apply(state);
        if(disposed||token!==version)return;state=result.state;interactionAudio=result.interaction_audio||{};
        if(name==='auto_offer'){
          if(state.phase==='proposed'){
            open=true;reviewId=state.session_id+':'+state.revision;
            memory.saveReview(reviewId,state,interactionAudio,'presented');
            await action('start_device_activity');
            lastSpeech='auto:'+state.revision;interaction.play({url:interactionAudio.prompt,text:state.proposal.prompt});
          }
          else {open=false;}
        }
        if(name==='start_prepared'){if(state.phase==='proposed')await startActivity();else await resume('return-to-story');}
      }else if(['independent','with_help','try_later'].includes(name)){await action('record_observation',{outcome:name});lookahead.invalidate();await resume(feedbackFor('record_observation',name));}
      else{
        if(name==='approve_activity'){await startActivity();return;}
        if(name==='resume_story'){if(state.phase==='reading'){open=false;return;}await resume(state.phase==='continue_proposed'?'return-to-story':'skip');return;}
        await action(name,args);
        if(['speak_prompt','give_hint'].includes(name)&&state.speech?.id!==lastSpeech){
          lastSpeech=state.speech.id;
          interaction.play({url:interactionAudio[name==='give_hint'?'hint':'prompt'],text:state.speech.text});
        }
      }
    }catch(e){if(!disposed&&token===version)error=e.message;}
    finally{busy=false;render();}
    return !error;
  }
  panel.onsubmit=event=>{if(!event.target.matches('[data-test-reply]'))return;event.preventDefault();const text=new FormData(event.target).get('reply');if(text?.trim())run('submit_response',{text:text.trim()});};
  panel.onclick=event=>{const saved=event.target.closest('[data-review-id]')?.dataset.reviewId;if(saved){interaction.stop();review=memory.reviews.find(r=>r.id===saved)||null;open=true;render();return;}const name=event.target.closest('[data-coach]')?.dataset.coach;if(!name)return;if(name==='close'){interaction.stop();review=null;open=false;render();return;}run(name);};
  const trigger=player.querySelector('#open-story-coach');
  trigger.onclick=()=>{interaction.stop();pause();open=!open;render();};
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
    async leaveForReview(){if(state){state=await api('release-device',{session_id:state.session_id});if(state.phase!=='reading')throw Error('Cell clear was not acknowledged.');}interaction.stop();},
    review(id){review=memory.reviews.filter(r=>r.passage_id===id).at(-1)||null;if(!review){const old=memory.rows.filter(r=>r.passage_id===id).at(-1);if(old)review={...old,prompt:'The original prompt was not saved for this earlier activity.',status:old.outcome};}if(review){pause();open=true;render();}},
    observations(){return structuredClone(state?.observations || []);},
    offerQuestion(){narrationEnded=true;render();},
    stopSpeech(){interaction.stop();},
    isPaused(){return ['awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state?.phase);},
    context(pageId,upcoming=[pageId]){
      if(pageId===latestPage)return;latestPage=pageId;version++;error='';narrationEnded=false;
      passage=opportunityFor(pageId,checkpoints);review=null;reviewId=null;interaction.stop();interactionAudio={};
      windowTargets=upcoming.slice(0,3).map(id=>opportunityFor(id,checkpoints)).filter(Boolean);
        window.speechSynthesis?.cancel();
      preparation.invalidate();
      const token=version,target=passage;
      if(!disposed){queue=queue.catch(()=>{}).then(async()=>{
        if(disposed||token!==version)return;
        await syncContext(target);
        if(!disposed&&token===version && !review)lookahead.prepare(state,windowTargets.find(id=>!offered.has(id))||null);
      }).catch(e=>{if(token===version)error=e.message;}).finally(render);}
      render();
    },
    dispose(){if(state)void api('release-device',{session_id:state.session_id}).catch(()=>{});if(activeVoiceCoach===voiceCoach)activeVoiceCoach=null;lookahead.invalidate();interaction.dispose();lockControls(false);disposed=true;version++;preparation.invalidate();window.speechSynthesis?.cancel();panel.remove();generationStatus.remove();}
  };
}
