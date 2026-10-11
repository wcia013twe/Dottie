let active=null,generation=0;
const changed=()=>window.dispatchEvent(new Event('magneto-voice-context'));
export const narrationSpeaking=()=>!!active&&!active.paused;
export function stopNarration(){generation++;const old=active;active=null;old?.abort.abort();old?.audio.pause();old?.audio.remove();if(old?.url)URL.revokeObjectURL(old.url);changed();}
export function pauseNarration(){if(active){active.paused=true;active.audio.pause();changed();}}
export function resumeNarration(){if(!active)return false;active.paused=false;if(active.url)active.audio.play().catch(()=>{active.paused=true;active.onerror('Press Play again to allow story audio.');changed();});changed();return true;}
export function narrate(text,{onend,onerror,onstatus}){
  stopNarration();const id=generation;
  const audio=document.createElement('audio');audio.id='story-narration-audio';audio.hidden=true;document.body.append(audio);
  const entry={audio,abort:new AbortController(),paused:false,onerror};active=entry;
  const current=()=>generation===id&&active===entry;
  audio.onended=()=>{if(current()){stopNarration();onend();}};
  audio.onplaying=()=>{if(current()){onstatus('ElevenLabs narration playing');changed();}};
  audio.onerror=()=>{if(current()){stopNarration();onerror('Story audio could not play. Please retry.');}};
  onstatus('Preparing ElevenLabs narration…');changed();
  // Bound long spreads into chunks; never truncate a learner's story.
  const chunks=[];let rest=text.trim();
  while(rest){let end=Math.min(rest.length,3000);if(end<rest.length){const space=rest.lastIndexOf(' ',end);if(space>0)end=space;}chunks.push(rest.slice(0,end));rest=rest.slice(end).trim();}
  let index=0;
  const playChunk=async()=>{
    try{
      const response=await fetch('/api/story-narration',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:chunks[index]}),signal:entry.abort.signal});
      if(!response.ok)throw Error((await response.json()).error||'ElevenLabs narration unavailable.');
      const blob=await response.blob();if(!current())return;
      if(entry.url)URL.revokeObjectURL(entry.url);entry.url=URL.createObjectURL(blob);audio.src=entry.url;
      audio.onended=()=>{if(current()){if(++index<chunks.length)playChunk();else{stopNarration();onend();}}};
      if(!entry.paused)await audio.play();
    }catch(error){if(!current()||error.name==='AbortError')return;entry.paused=true;onerror(error.name==='NotAllowedError'?'Press Play again to allow story audio.':error.message);changed();}
  };
  if(chunks.length)playChunk();else{stopNarration();onerror('No story text on this page.');}
}
