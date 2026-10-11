// Local generated audio only. API keys and synthesis never enter the browser.
const normalize = text => String(text).replace(/\s+/g, ' ').trim().toLowerCase();
export function matchNarration(manifest, bookId, text) {
  if (manifest?.schema_version !== '1.0' || manifest.book_id !== bookId || !Array.isArray(manifest.passages)) return null;
  const matches = manifest.passages.filter(p => p && typeof p.match_text === 'string' && normalize(p.match_text) && normalize(text).includes(normalize(p.match_text)));
  if (matches.length !== 1) return null;
  const passage = matches[0];
  if (!/^[a-zA-Z0-9_-]+-[a-f0-9]{64}\.wav$/.test(passage.audio) || typeof passage.duration_seconds !== 'number' || !Number.isFinite(passage.duration_seconds) || passage.duration_seconds <= 0) return null;
  return passage;
}

export function mountNarration({player, bookId, onPlay, onEnded = () => {}, onProgress = () => {}}) {
  if (!/^[a-zA-Z0-9_-]{1,100}$/.test(bookId)) return {context(){}, pause(){}, dispose(){}};
  const area = document.createElement('div'); area.hidden = true; area.className = 'local-narration';
  const label = document.createElement('span'); label.textContent = 'Recorded narration';
  const audio = document.createElement('audio'); audio.controls = false; audio.preload = 'auto'; audio.setAttribute('aria-label', 'Read this passage');
  const description = document.createElement('details');
  const summary = document.createElement('summary'); summary.textContent = 'Picture description';
  const transcript = document.createElement('p'); description.append(summary, transcript);
  const replay = document.createElement('button'); replay.type = 'button'; replay.textContent = 'Replay description';
  replay.onclick = () => { audio.currentTime = 0; audio.play().catch(() => { label.textContent = 'Press play to hear this page'; }); };
  area.append(label, replay, description, audio); player.querySelector('.player-controls').prepend(area);
  let disposed = false, manifest = null, currentText = '', source = '';
  function context(text) {
    currentText = text;
    const passage = matchNarration(manifest, bookId, text);
    const next = passage ? `./narration/${bookId}/${passage.audio}` : '';
    if (next === source) {if(manifest && !next)onEnded();return;}
    const visual = String(manifest?.script_version || '').startsWith('visual-description-');
    audio.pause(); label.textContent = visual ? 'Original visual narration' : 'Recorded narration'; source = next; area.hidden = !(visual && next);
    transcript.textContent = visual ? passage?.text || '' : '';
    description.hidden = replay.hidden = !visual;
    if (next) audio.src = next; else {audio.removeAttribute('src');if(manifest)onEnded();}
    audio.load();
    onProgress(0);
    if (next) audio.play().catch(() => {
      if (!disposed && source === next && audio.paused) label.textContent = 'Press play to hear this page';
    });
  }
  function reportProgress(){onProgress(Number.isFinite(audio.duration) && audio.duration > 0 ? Math.min(1,audio.currentTime/audio.duration) : 0);}
  audio.ontimeupdate = audio.onloadedmetadata = audio.onseeked = reportProgress;
  audio.onended = () => {if(!disposed)onEnded();};
  audio.onplay = () => { onPlay(); window.speechSynthesis?.cancel(); };
  audio.onerror = () => { label.textContent = 'Narration unavailable. Continue reading or rebuild this audio.'; };
  fetch(`./narration/${bookId}/manifest.json`, {cache:'no-store'})
    .then(response => response.ok ? response.json() : null)
    .then(data => { if (!disposed) { manifest = data; context(currentText); } }).catch(() => {});
  return {context, seek(fraction){if(source && Number.isFinite(audio.duration) && audio.duration > 0){audio.currentTime=Math.max(0,Math.min(1,fraction))*audio.duration;reportProgress();}}, resume(){if(source && audio.paused)audio.play().catch(() => {label.textContent='Press play to hear this page';});}, isPlaying(){return !audio.paused && !audio.ended;}, pause(){audio.pause();}, dispose(){disposed=true;audio.pause();audio.removeAttribute('src');audio.load();area.remove();}};
}
