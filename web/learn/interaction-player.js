// Respond only to accepted controller actions. Never infer an outcome from a transcript.
export function feedbackFor(action, outcome) {
  if(action==='record_observation')return {independent:'success-independent',with_help:'success-assisted',try_later:'skip'}[outcome] || null;
  if(action==='resume_story')return 'return-to-story';
  return null;
}
export function createInteractionPlayer(player) {
  const audio = new Audio(); audio.controls=true; audio.setAttribute('aria-label','Interaction narration');
  const area=document.createElement('div');area.className='local-narration';area.hidden=true;
  const label=document.createElement('span');label.textContent='Interaction narration';area.append(label,audio);
  player.querySelector('.player-controls').prepend(area);
  let generation=0, disposed=false, finish=null;
  const pack=fetch('./narration/peter-rabbit-interactions/manifest.json',{cache:'no-store'})
    .then(r=>r.ok?r.json():null).catch(()=>null);
  function stop(){finish?.(false);finish=null;generation++;area.hidden=true;audio.pause();audio.removeAttribute('src');audio.load();window.speechSynthesis?.cancel();}
  async function play({clip,url,text}) {
    stop();const token=generation;
    if(clip){const manifest=await pack;const p=manifest?.book_id==='peter-rabbit-interactions'?manifest.passages?.find(p=>p.id===clip):null;
      if(p && /^[a-zA-Z0-9_-]+-[a-f0-9]{64}\.wav$/.test(p.audio))url='/learn/narration/peter-rabbit-interactions/'+p.audio;
      text ||= p?.text;
    }
    if(disposed||token!==generation)return;
    if(url && /^\/learn\/narration\/peter-rabbit-(?:interactions|exercises)\/[a-zA-Z0-9_-]+-[a-f0-9]{64}\.wav$/.test(url)){
      area.hidden=false;audio.src=url;
      try{
        const ended=new Promise(resolve=>{finish=resolve;audio.onended=()=>{finish=null;resolve(true);};audio.onerror=()=>{finish=null;resolve(false);};});
        await audio.play();return await ended;
      }catch{finish?.(false);finish=null;/* Fall back to browser speech. */}
    }
    if(disposed||token!==generation)return;
    if(text && 'speechSynthesis' in window){const speech=new SpeechSynthesisUtterance(text);speech.rate=.85;return await new Promise(resolve=>{finish=resolve;speech.onend=()=>{finish=null;resolve(true);};speech.onerror=()=>{finish=null;resolve(false);};speechSynthesis.speak(speech);});}
    return false;
  }
  return {play,stop,dispose(){disposed=true;stop();area.remove();}};
}
