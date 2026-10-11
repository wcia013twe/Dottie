import { normalizeSpeech } from './voice-intents.js?v=conversational-navigation-2';
import { understandSpeech } from './voice-understanding.js?v=conversational-navigation-2';
import { navigationSpeaking, speakFeedback } from './navigation-voice.js?v=conversational-navigation-2';

export function pcmBase64(samples, muted = false) {
  const bytes = new Uint8Array(samples.length * 2), view = new DataView(bytes.buffer);
  samples.forEach((sample, i) => view.setInt16(i * 2, muted ? 0 : Math.round(Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767)), true));
  return btoa(String.fromCharCode(...bytes));
}

// Routine confirmations stay visible in the story reader. Requested help and
// errors may speak; successful answers never interrupt the story.
export function shouldSpeakFeedback(intent, context, message) {
  if (!context.storyReader) return true;
  if (['help','repeat','unknown'].includes(intent.type)) return true;
  return !/^(Your answer was captured\.|Continue reading\.|Page turns paused\.|Automatic page turns started\.|Spoken navigation is on\.)/.test(message);
}

export function mountVoice({context, perform, speak}) {
  const panel = document.querySelector('#voice-input-panel');
  const start = panel.querySelector('#start-listening'), stop = panel.querySelector('#stop-listening');
  const status = panel.querySelector('#listening-status'), transcript = panel.querySelector('#voice-transcript');
  let generation = 0, stream, audio, source, capture, socket, abort, navigationAbort, timer, poll;
  let active = false, ready = false, mutedUntil = 0, segmentContext = null, lastCommit = '', lastCommitAt = 0, busy = false;
  let pendingSegments = [], speechSeconds = 0, silenceSeconds = 0;
  const actionStatus=panel.querySelector('#voice-action-status');
  const compactStatus=panel.querySelector('#voice-compact-status');
  const headerMicrophone=document.querySelector('#voice-microphone');
  const preview=document.querySelector('#voice-feedback');
  if (preview && window.MutationObserver) {
    const updatePreview=()=>{
      preview.hidden=!active && !transcript.textContent && status.textContent.startsWith('Microphone off');
      preview.querySelector('[data-voice-status]').textContent=status.textContent;
      preview.querySelector('[data-voice-transcript]').textContent=transcript.textContent;
      preview.querySelector('[data-voice-result]').textContent=actionStatus?.textContent || '';
    };
    const observer=new window.MutationObserver(updatePreview);
    for(const node of [status,transcript,actionStatus].filter(Boolean))observer.observe(node,{childList:true,characterData:true,subtree:true});
  }
  function syncMicrophone() {
    if(!headerMicrophone)return;
    const label=active ? 'Stop listening' : 'Start listening';
    // The icon shows microphone state; the accessible label names its action.
    headerMicrophone.innerHTML=(active ? start : stop).innerHTML;
    headerMicrophone.setAttribute('aria-label',label);
    headerMicrophone.setAttribute('title',label);
    headerMicrophone.setAttribute('aria-pressed',String(active));
  }
  const stamp = () => JSON.stringify(context());
  const synthesis = window.speechSynthesis;
  const blocked = () => busy || navigationSpeaking() || (!synthesis?.paused && (synthesis?.speaking || synthesis?.pending)) || Date.now() < mutedUntil;
  // Each explicit commit has its own context in FIFO order, so delayed results
  // cannot borrow the context of a newer question or navigation destination.
  function flushSegment(contextOverride = segmentContext) {
    if (!segmentContext || socket?.readyState !== WebSocket.OPEN) return;
    pendingSegments.push(contextOverride);
    socket.send(JSON.stringify({message_type:'input_audio_chunk',audio_base_64:'',commit:true,sample_rate:audio.sampleRate}));
    segmentContext = null; speechSeconds = silenceSeconds = 0;
  }
  function invalidate() {
    navigationAbort?.abort();
    pendingSegments = pendingSegments.map(() => null);
    flushSegment(null); mutedUntil = Date.now() + 800;
  }
  function release() {
    clearTimeout(timer); clearInterval(poll); abort?.abort(); abort = null; navigationAbort?.abort(); navigationAbort=null;
    if (socket) { socket.onclose = socket.onerror = socket.onmessage = null; socket.close(); socket = null; }
    capture?.disconnect(); source?.disconnect(); capture = source = null;
    stream?.getTracks().forEach(track => track.stop()); stream = null;
    audio?.close().catch(() => {}); audio = null;
    ready = active = false; syncMicrophone(); segmentContext = null; pendingSegments = []; speechSeconds = silenceSeconds = 0; busy = false;
    if(compactStatus)compactStatus.textContent='Microphone off';
    start.disabled = false; stop.disabled = true; start.setAttribute('aria-pressed','false');
  }
  function end(message = 'Microphone off.') { generation++; release(); status.textContent = message; }
  function fail(message) { end(message); }
  function speakingFeedback(text) { invalidate(); speakFeedback(text, fallback=>speak(fallback, true)); }
  async function commit(text, id, committedContext) {
    if (!ready || id !== generation || !text?.trim() || blocked() || !committedContext || committedContext !== stamp()) return;
    const normalized = normalizeSpeech(text), now = Date.now();
    if (normalized === lastCommit && now - lastCommitAt < 1500) return;
    lastCommit = normalized; lastCommitAt = now;
    transcript.textContent = `Heard: ${text}`;
    let intent;
    busy = true; status.textContent = 'Working on your request…';
    const requestAbort = navigationAbort = new AbortController();
    try {
      intent = await understandSpeech(text,context(),{signal:requestAbort.signal});
      if (id !== generation || !ready || requestAbort.signal.aborted || committedContext !== stamp()) return;
      if (intent.type === 'stopListening') { const quiet=context().storyReader;end();if(!quiet)speakingFeedback('Microphone off.');return; }
      const result = await perform(intent);
      if (id !== generation) return;
      if(actionStatus)actionStatus.textContent=result || 'Request completed.';
      if (result) {if(shouldSpeakFeedback(intent,context(),result))speakingFeedback(result); }
    } catch (error) { if (id === generation && !requestAbort.signal.aborted) {const message=error.message || 'That action is unavailable. Please try again.';if(actionStatus)actionStatus.textContent=message;speakingFeedback(message);} }
    finally { if (navigationAbort===requestAbort)navigationAbort=null;if (id === generation) { busy = false; status.textContent = 'ElevenLabs connected. Tell me where you’d like to go, or answer the current question.'; } }
  }
  async function begin() {
    if (active) return;
    const id = ++generation;
    active = true;syncMicrophone();if(compactStatus)compactStatus.textContent='Connecting…';start.disabled = true; stop.disabled = false;
    status.textContent = 'Connecting your microphone…'; transcript.textContent = '';if(actionStatus)actionStatus.textContent='';
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) throw Error('Voice needs a supported browser on localhost or HTTPS.');
      const captured = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});
      if (id !== generation) { captured.getTracks().forEach(track => track.stop()); return; }
      stream = captured;
      stream.getAudioTracks()[0].addEventListener('ended', () => { if (id === generation) end('Microphone disconnected. Start listening to reconnect.'); });
      const Audio = window.AudioContext || window.webkitAudioContext;
      audio = new Audio({sampleRate:16000});
      await audio.resume();
      if (id !== generation) return;
      await audio.audioWorklet.addModule('./voice-worklet.js');
      if (id !== generation) return;
      abort = new AbortController();
      const response = await fetch('/api/voice-token',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',signal:abort.signal});
      if ([404,405,501].includes(response.status)) throw Error('Voice needs the updated local Magneto server. Restart python3 scripts/serve.py on this page’s port, then reload and start listening.');
      let result; try { result = await response.json(); } catch { throw Error('Voice needs the updated local Magneto server.'); }
      if (id !== generation) return;
      if (!response.ok) throw Error(result.error || 'Voice is unavailable.');
      if (typeof result.token !== 'string' || !result.token) throw Error('Voice returned an invalid connection token.');
      const params = new URLSearchParams({model_id:'scribe_v2_realtime',token:result.token,audio_format:`pcm_${audio.sampleRate}`,language_code:'en',commit_strategy:'manual'});
      socket = new WebSocket(`wss://api.elevenlabs.io/v1/speech-to-text/realtime?${params}`);
      timer = setTimeout(() => { if (id === generation) fail('Voice connection timed out. Start listening to retry.'); },15000);
      socket.onerror = () => { if (id === generation) fail('Could not connect to voice. Check your connection and retry.'); };
      socket.onclose = () => { if (id === generation) end('Voice disconnected. Start listening to reconnect.'); };
      source = audio.createMediaStreamSource(stream);
      capture = new AudioWorkletNode(audio,'magneto-voice-capture');
      source.connect(capture); capture.connect(audio.destination);
      capture.port.onmessage = ({data}) => {
        if (id !== generation || !ready || socket?.readyState !== WebSocket.OPEN) return;
        let muted = blocked();
        const seconds = data.length / audio.sampleRate;
        const voiced = !muted && Math.sqrt(data.reduce((sum, sample) => sum + sample * sample, 0) / data.length) > .01;
        if (voiced && !segmentContext) segmentContext = stamp();
        if (segmentContext && (muted || segmentContext !== stamp())) { invalidate(); muted = true; }
        if (segmentContext) {
          speechSeconds += seconds;
          silenceSeconds = voiced ? 0 : silenceSeconds + seconds;
        }
        if (socket.bufferedAmount > 262144) { fail('Voice connection is too slow. Start listening to retry.'); return; }
        socket.send(JSON.stringify({message_type:'input_audio_chunk',audio_base_64:pcmBase64(data,muted),sample_rate:audio.sampleRate}));
        if (segmentContext && (silenceSeconds >= .7 || speechSeconds >= 10)) flushSegment();
        if (pendingSegments.length > 10) fail('Voice is taking too long to respond. Start listening to retry.');
      };
      socket.onmessage = ({data}) => {
        if (id !== generation) return;
        let event; try { event = JSON.parse(data); } catch { fail('Voice sent an invalid response. Please reconnect.'); return; }
        if (event.message_type === 'session_started') {
          clearTimeout(timer); ready = true;if(compactStatus)compactStatus.textContent='Listening'; start.disabled = true; start.setAttribute('aria-pressed','true');
          status.textContent = 'ElevenLabs connected. Try “I want to practice” or “let’s read a story”.';
        } else if (event.message_type === 'partial_transcript') {
          if (!blocked() && segmentContext === stamp()) transcript.textContent = `Hearing: ${event.text}`;
        } else if (event.message_type === 'committed_transcript') {
          commit(event.text,id,pendingSegments.shift());
        } else if (event.error || /error|rate_limited|auth_error|quota_exceeded/.test(event.message_type || '')) {
          fail('ElevenLabs voice is unavailable. Check key access, quota, and connection, then retry.');
        }
      };
      poll = setInterval(() => {
        if (navigationSpeaking() || (!synthesis?.paused && (synthesis?.speaking || synthesis?.pending))) { invalidate();if(compactStatus)compactStatus.textContent='Listening paused';status.textContent = context().storyReader ? 'Reading or speaking. Pause reading or stop speech to give a command.' : 'Speaking. Listening resumes afterward.'; }
        else if (ready && !busy && Date.now() >= mutedUntil) {if(compactStatus)compactStatus.textContent='Listening';status.textContent='ElevenLabs connected. Tell me where you’d like to go, or answer the current question.';}
      },100);
    } catch (error) {
      if (id !== generation) return;
      fail(error.name === 'NotAllowedError' ? 'Microphone access was blocked. Allow it in your browser and retry.' : error.name === 'NotFoundError' ? 'No microphone found. Connect one and retry.' : error.message || 'Could not start voice. Please retry.');
    }
  }
  start.onclick = begin; stop.onclick = () => end();
  if(headerMicrophone)headerMicrophone.onclick=()=>active ? end() : begin();
  syncMicrophone();
  window.addEventListener('pagehide', () => end());
  document.addEventListener('visibilitychange', () => { if (document.hidden && active) end('Microphone off while this page is hidden.'); });
  window.addEventListener('magneto-voice-context', invalidate);
  return {invalidate, stop: end};
}
