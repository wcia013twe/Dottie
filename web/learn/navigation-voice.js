// Fixed navigation prompts can be packaged once with ElevenLabs and then play
// locally. Existing browser speech remains the fallback until clips exist.
let prompts = {}, available = new Set(), audio = null, generation = 0, cancelFallback = null;
const playbackStatus = (state, message='') => window.dispatchEvent(new CustomEvent('magneto-navigation-audio',{detail:{state,message}}));
export async function loadNavigationVoice() {
  try {
    const response = await fetch('./navigation-prompts.json');
    if (response.ok) prompts = await response.json();
    const manifest = await fetch('./assets/navigation-voice/manifest.json');
    if (manifest.ok) {
      const packaged = await manifest.json();
      available = new Set(Object.keys(prompts).filter(route => packaged.phrases?.[route] === prompts[route]));
    }
  } catch { /* Local speech continues if packaged files are unavailable. */ }
}
export function navigationPrompt(route, fallback) { return prompts[route] || fallback; }
export function navigationSpeaking() { return !!audio && !audio.paused && !audio.ended; }
export function stopNavigationVoice() {
  generation++; audio?.pause(); audio?.remove?.(); audio = null;
  const cancel = cancelFallback; cancelFallback = null; if(typeof cancel === 'function')cancel();
  window.dispatchEvent(new Event('magneto-voice-context'));
}
export function speakNavigation(route, fallback, localSpeak) {
  stopNavigationVoice();
  const text = navigationPrompt(route, fallback);
  if (!available.has(route)) { cancelFallback = localSpeak(text); return; }
  const id = generation;
  audio = new Audio(`./assets/navigation-voice/${route}.wav`);
  audio.id='navigation-audio';audio.hidden=true;
  if(typeof document!=='undefined')document.body?.append(audio);
  window.dispatchEvent(new Event('magneto-voice-context'));
  audio.onplaying=()=>{if(id===generation)playbackStatus('playing');};
  audio.onended = () => { if (id === generation) { audio?.remove?.();audio = null; window.dispatchEvent(new Event('magneto-voice-context')); } };
  const fail = error => { if (id === generation) {
    stopNavigationVoice();
    if(error?.name==='NotAllowedError')playbackStatus('blocked','Click Retry audio to allow the ElevenLabs voice to play.');
    else {cancelFallback = localSpeak(text);if(!('speechSynthesis' in window))playbackStatus('failed','ElevenLabs audio could not play. Click Retry audio.');}
  } };
  audio.onerror = fail;
  audio.play().catch(fail);
}
