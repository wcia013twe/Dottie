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

export function mountNarration({player, bookId, onPlay}) {
  if (!/^[a-zA-Z0-9_-]{1,100}$/.test(bookId)) return {context(){}, pause(){}, dispose(){}};
  const area = document.createElement('div'); area.hidden = true; area.className = 'local-narration';
  const label = document.createElement('span'); label.textContent = 'Recorded narration';
  const audio = document.createElement('audio'); audio.controls = true; audio.preload = 'auto'; audio.setAttribute('aria-label', 'Read this passage');
  area.append(label, audio); player.querySelector('.player-controls').prepend(area);
  let disposed = false, manifest = null, currentText = '', source = '';
  function context(text) {
    currentText = text;
    const passage = matchNarration(manifest, bookId, text);
    const next = passage ? `./narration/${bookId}/${passage.audio}` : '';
    if (next === source) return;
    audio.pause(); label.textContent = 'Recorded narration'; source = next; area.hidden = !next;
    if (next) audio.src = next; else audio.removeAttribute('src');
    audio.load();
    if (next) audio.play().catch(() => {
      if (!disposed && source === next && audio.paused) label.textContent = 'Press play to hear this page';
    });
  }
  audio.onplay = () => { onPlay(); window.speechSynthesis?.cancel(); };
  audio.onerror = () => { label.textContent = 'Narration unavailable. Continue reading or rebuild this audio.'; };
  fetch(`./narration/${bookId}/manifest.json`, {cache:'no-store'})
    .then(response => response.ok ? response.json() : null)
    .then(data => { if (!disposed) { manifest = data; context(currentText); } }).catch(() => {});
  return {context, pause(){audio.pause();}, dispose(){disposed=true;audio.pause();audio.removeAttribute('src');audio.load();area.remove();}};
}
