// Fixed navigation prompts can be packaged once with ElevenLabs and then play
// locally. Existing browser speech remains the fallback until clips exist.
let prompts = {}, available = new Set(), audio = null, generation = 0, cancelFallback = null;
let packagedVoice = '';
const playbackStatus = (state, message='') => window.dispatchEvent(new CustomEvent('magneto-navigation-audio',{detail:{state,message}}));
export async function loadNavigationVoice() {
  try {
    const response = await fetch('./navigation-prompts.json');
    if (response.ok) prompts = await response.json();
    const manifest = await fetch('./assets/navigation-voice/manifest.json', {cache:'no-store'});
    if (manifest.ok) {
      const packaged = await manifest.json();
      packagedVoice = typeof packaged.voice_id === 'string' ? packaged.voice_id : '';
      available = new Set(Object.keys(prompts).filter(route => packaged.phrases?.[route] === prompts[route]));
    }
  } catch { /* Local speech continues if packaged files are unavailable. */ }
}
export function navigationPrompt(route, fallback) { return prompts[route] || fallback; }
export function navigationSpeaking() { return !!audio && !audio.paused && !audio.ended; }
export function speakFeedback(text, localSpeak) {
  const clip=Object.keys(prompts).find(key=>key.startsWith('feedback-') && prompts[key]===text);
  speakNavigation(clip || 'feedback-missing', text, localSpeak);
}
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
  audio = new Audio(`./assets/navigation-voice/${route}.wav?voice=${encodeURIComponent(packagedVoice)}`);
  audio.id='navigation-audio';audio.hidden=true;
  if(typeof document!=='undefined')document.body?.append(audio);
  window.dispatchEvent(new Event('magneto-voice-context'));
  audio.onplaying=()=>{if(id===generation)playbackStatus('playing');};
  audio.onended = () => { if (id === generation) { audio?.remove?.();audio = null; window.dispatchEvent(new Event('magneto-voice-context')); } };
  const fail = error => { if (id === generation) {
    stopNavigationVoice();
    if(error?.name==='NotAllowedError')playbackStatus('blocked','Turn spoken navigation off and on in Voice settings to retry audio.');
    else {cancelFallback = localSpeak(text);if(!('speechSynthesis' in window))playbackStatus('failed','ElevenLabs audio could not play. Turn spoken navigation off and on in Voice settings to retry.');}
  } };
  audio.onerror = fail;
  audio.play().catch(fail);
}
