import { demoCompletionRecap, mountStoryCompletion } from './story-completion.js';
import { preparePeterReading, PETER_READING_VERSION } from './peter-reading.js?v=merge-main-1';
import { DecisionSession } from './decision-session.js';
import { peterActivities, bindPeterActivities } from './peter-activities.js';
import { mountFlipbook } from './flipbook.js?v=merge-main-1';
import { importEbook, ebookStore } from './ebook.js?v=merge-main-1';
// Reading records are separate from learning progress and saved CAD designs.
const key = 'magneto-stories-v1';
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeLink = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } };
let books = [], storageOK = true;
const loadedEbooks = new Map();
let readerSize = 20;
let disposeReader = null;
let disposeCompletion = null;
let celebratedDemoSession = null;
export function cleanupStoryReader() {
  const voice=document.querySelector('#voice-input-panel');
  if (voice?.closest('.book-player')) { voice.open=false; document.querySelector('.workspace').insertBefore(voice,document.querySelector('.voice-bar')); }
 disposeCompletion?.(); disposeCompletion = null; disposeReader?.(); disposeReader = null; if (location.hash !== '#stories') director.cancel(); }
try {
  const saved = JSON.parse(localStorage.getItem(key) || '[]');
  if (!Array.isArray(saved)) throw new Error('Invalid shelf');
  books = saved.filter(b => b && typeof b.id === 'string' && typeof b.title === 'string' && typeof b.author === 'string' && ['pages','chapters'].includes(b.unit) && Number.isSafeInteger(b.total) && b.total > 0 && Number.isSafeInteger(b.current) && b.current >= 0 && b.current <= b.total);
} catch { storageOK = false; }
const peterKey = 'magneto-peter-rabbit-v1';
const peter = {id:'builtin-peter-rabbit', title:'The Tale of Peter Rabbit', author:'Beatrix Potter', imported:true, bundled:true, unit:'chapters', total:1, current:0, position:0};
try {
  const saved = JSON.parse(localStorage.getItem(peterKey) || '{}');
  for (const field of ['current','position','page','total','textSize']) {
    if (Number.isSafeInteger(saved[field]) && saved[field] >= 0 && (field !== 'total' || saved[field] > 0)) peter[field] = saved[field];
  }
  if (typeof saved.finished === 'boolean') peter.finished = saved.finished;
  if (typeof saved.readingVersion === 'string') peter.readingVersion = saved.readingVersion;
  if (saved.previousReadingPosition && typeof saved.previousReadingPosition === 'object') {
    peter.previousReadingPosition = {};
    for (const field of ['position','page','pageFraction']) {
      const value = saved.previousReadingPosition[field];
      if (Number.isFinite(value) && value >= 0) peter.previousReadingPosition[field] = value;
    }
  }
  if (Number.isFinite(saved.pageFraction) && saved.pageFraction >= 0 && saved.pageFraction <= 1) peter.pageFraction = saved.pageFraction;
} catch { storageOK = false; }
const selectedBook = () => opened === 'peter' ? peter : Number.isInteger(opened) ? books[opened] : null;
async function loadBook(book) {
  if (!book.bundled) return ebookStore('get',book.id);
  const response = await fetch('./books/the-tale-of-peter-rabbit.epub');
  if (!response.ok) throw Error('Peter Rabbit could not be opened. Please reload and try again.');
  const mapResponse=await fetch('./books/peter-rabbit-checkpoints.json');
  if(!mapResponse.ok)throw Error('Checkpoint map is unavailable.');
  const content = preparePeterReading(await importEbook(new File([await response.blob()], 'the-tale-of-peter-rabbit.epub')),await mapResponse.json());
  if(book.readingVersion !== PETER_READING_VERSION){
    book.previousReadingPosition={position:book.position,page:book.page,pageFraction:book.pageFraction};
    Object.assign(book,{position:content.readingStart,page:0,pageFraction:0,current:content.readingStart,finished:false,readingVersion:PETER_READING_VERSION});
  }
  book.total = content.chapters.length;
  book.position = Math.min(book.position, book.total-1);
  book.current = Math.min(book.current, book.total);
  return content;
}
function save() {
  try { localStorage.setItem(key, JSON.stringify(books)); localStorage.setItem(peterKey, JSON.stringify(peter)); storageOK = true; }
  catch { storageOK = false; }
}
const director = new DecisionSession();
if (director.state.step === 3) celebratedDemoSession = director.state.session_id;
// Read the validated in-memory session without introducing another wire format.
export function learnerStoryEvidence() {
  return structuredClone({session: director.state, error: director.error, pending: !!director.pending});
}
let opened = null;
export function isStoryOpen() { return opened !== null; }
const caterpillar = `<svg viewBox="0 0 260 140" aria-hidden="true"><path d="M32 116Q130 85 239 116" fill="none" stroke="#a2ac61" stroke-width="3"/>${[0,1,2,3,4].map((n)=>`<ellipse cx="${66+n*31}" cy="${91-Math.sin(n)*12}" rx="25" ry="31" fill="${['#719851','#448567','#88a654','#428062','#98aa51'][n]}" transform="rotate(${n*8-15} ${66+n*31} 85)"/>`).join('')}<ellipse cx="207" cy="65" rx="29" ry="33" fill="#c35c48"/><path d="M194 34l-7-16m31 15 8-19" stroke="#766089" stroke-width="5" stroke-linecap="round"/><ellipse cx="199" cy="61" rx="6" ry="9" fill="#e8d679"/><ellipse cx="218" cy="59" rx="6" ry="9" fill="#e8d679"/><path d="M205 78q7 6 12-2" fill="none" stroke="#563e33" stroke-width="3"/></svg>`;
function demoView() {
  const step = director.state.step, result = director.result, decision = result?.decision;
  const heading = ['Monday · The apple','Tuesday · The pears','Wednesday · The plums','A lovely little adventure.'][step];
  const fruit = ['🍎','🍐','🟣','🦋'][step];
  const copy = [
    'The teacher reads the apple passage from their own book and offers the apple prop.',
    'The teacher reads the pear passage from their own book and offers the pear prop.',
    'The teacher reads the plum passage from their own book and offers the plum prop.',
    'You’ve finished this simulated activity. Your teacher can continue reading the original book.'
  ][step];
  const uploads = director.outbox;
  const sharing = '<details class="panel"><summary>Learning history</summary><p>One student profile in this browser. Uploads save confirmed responses and support used for later review.</p><label><input type="checkbox" id="learning-uploads"' + (uploads.uploadsEnabled ? ' checked' : '') + '> Enable learning history uploads</label><p role="status" id="learning-status">' + (uploads.uploadsEnabled ? 'Uploads enabled. ' : 'Uploads paused. Existing cloud records are retained. ') + uploads.queuedCount + ' records waiting.</p>' + '<p role="status" id="learning-error">' + escape(uploads.error) + '</p>' + '<button type="button" class="secondary" id="learning-retry">Retry pending uploads</button></details>';
  const raised = decision?.target_letter === 'A' ? [1] : [1,2,3,4];
  const activity = decision?.action === 'teach' ? `<div class="demo-letter"><span class="braille" role="img" aria-label="Braille ${escape(decision.target_letter)}: dots ${raised.join(', ')}">${[1,2,3,4,5,6].map(n=>`<span class="dot ${raised.includes(n)?'raised':''}"></span>`).join('')}</span><div><strong>Magneto previews ${escape(decision.target_letter)}</strong><p>On-screen simulation. The teacher supplies tactile Braille.</p></div></div><p class="intro">${escape(decision.prompt)}</p>` : '';
  let controls = '';
  if (step === 3) controls = '<button class="primary" id="story-close-done">Back to my books</button><button class="secondary" id="demo-restart">Try another response</button>';
  else if (director.pending) controls = '<p role="status" aria-live="polite">Databricks is deciding the next interaction…</p>';
  else if (director.error) controls = `<p role="alert">${escape(director.error)}</p><div class="choices"><button class="primary" id="decision-retry">Retry</button><button class="secondary" id="decision-skip">Continue without activity</button></div>`;
  else if (director.skipped) controls = '<p role="status">Teacher chose to continue without an activity. This is not an agent decision.</p><button class="primary" id="demo-next">Continue reading →</button>';
  else if (decision?.action === 'teach' && step > 0) controls = '<h2>What happened?</h2><p>Teacher: record the learner’s spoken, signed, or assisted response.</p><label for="response-support">Support used</label><select id="response-support"><option value="unknown">Not recorded</option><option value="none">No support</option><option value="hint">Hint</option><option value="modeled_answer">Answer demonstrated</option></select><div class="choices"><button class="secondary" data-response="incorrect">Incorrect</button><button class="primary" data-response="correct">Correct</button><button class="secondary" data-response="help">Help</button></div>';
  else if (decision) controls = `<aside class="demo-decision"><strong>${decision.action === 'continue' ? 'Continue the story' : 'A short practice moment'}</strong></aside><button class="primary" id="demo-next">Continue reading →</button>`;
  const details = result ? `<details class="demo-decision"><summary>Developer details · Databricks decision</summary><p>${escape(decision.reason)}</p><dl><dt>Model</dt><dd>${escape(result.model)}</dd><dt>Model call + validation</dt><dd>${result.elapsed_ms} ms</dd><dt>Browser round trip</dt><dd>${result.round_trip_ms} ms</dd><dt>Based on learner event</dt><dd>${escape(decision.based_on_event_id || 'No live response yet; synthetic starting history')}</dd><dt>Request</dt><dd>${escape(result.request_id)}</dd></dl></details>` : '';
  return `<button class="back text-button" id="story-close">← Back to my books</button><p class="tag">The Very Hungry Caterpillar · Live Databricks decisions</p><h1>${heading}</h1><section class="panel demo-scene"><div class="demo-fruit" aria-hidden="true">${fruit}</div><p class="intro">${copy}</p>${activity}${controls}${details}</section>${sharing}<p class="hint">Simulated Braille · Teacher-provided test props · Synthetic starting history: A familiar, P needs practice. Camera and physical Braille are not connected to this story demo. Read the original story from your own book.</p>${!director.storageOK ? '<p role="status">Browser storage is unavailable. This session may not survive a reload.</p>' : ''}`;
}
export function stories() {
  if (opened === 'peter-activities') return peterActivities();
  if (opened === 'demo') return demoView();
  const selected = selectedBook();
  if (selected?.imported) {
    const content = loadedEbooks.get(selected.id), position = Math.min(selected.position || 0, selected.total-1);
    readerSize = [20,24,30].includes(selected.textSize) ? selected.textSize : 20;
    return `<section class="book-player" aria-label="Story player"><header class="player-header"><button class="player-button" id="story-close" aria-label="Back to my books" title="Back to my books">←</button><div class="player-title"><h1>${escape(selected.title)}</h1><p>${escape(selected.author)}</p></div>${selected.bundled ? '<button class="player-activity" id="open-story-coach">⠗ <span>Teacher coach</span></button>' : ''}</header><div id="ebook-status" role="status">${content ? '' : 'Opening your book…'}</div>${content ? `<div class="player-stage"><article class="flipbook" id="ebook-content" tabindex="0" aria-label="Book text" style="font-size:${readerSize}px"><div class="book-sheet" id="book-sheet"><div class="page-window" id="page-window"><div class="page-text" id="page-text"></div></div></div></article></div><footer class="player-controls"><label class="sr-only" for="reader-seek">Page in this chapter</label><div class="reader-timeline"><input id="reader-seek" type="range" min="1" max="1" value="1" step="1"><div id="question-markers" aria-label="Question stops and results"></div></div><p id="question-stop-label" class="question-stop-label" hidden></p><div class="player-control-row"><button class="player-button" id="reader-play" aria-label="Play automatic page turns" title="Auto-turn pages every 12 seconds">▶</button><button class="player-button" id="reader-prev" aria-label="Previous page" title="Previous page">❮</button><button class="player-button" id="reader-next" aria-label="Next page" title="Next page">❯</button><span id="reader-feedback" role="status"></span><span class="player-spacer"></span><details class="player-settings"><summary aria-label="Reader settings" title="Reader settings">⚙</summary><div class="player-settings-panel"><label for="reader-chapter">Chapter</label><select id="reader-chapter">${content.chapters.map((chapter,i)=>`<option value="${i}" ${i===position?'selected':''}>${escape(chapter.title)}</option>`).join('')}</select><label for="reader-size">Text size</label><select id="reader-size"><option value="20" ${readerSize===20?'selected':''}>Standard</option><option value="24" ${readerSize===24?'selected':''}>Large</option><option value="30" ${readerSize===30?'selected':''}>Extra large</option></select><p>Play turns a page every 12 seconds. Arrow keys or swipe to turn manually.</p></div></details><button class="player-button" id="reader-fullscreen" aria-label="Enter fullscreen" title="Fullscreen">⛶</button></div><div class="player-meta"><span id="player-mode">Read at your own pace</span><span>Your place is saved automatically</span></div></footer>` : ''}</section>`;
  }
  if (selected) {
    const link = safeLink(selected.url);
    return `<button class="back text-button" id="story-close">← Back to my books</button><h1>${escape(selected.title)}</h1><p class="intro">${escape(selected.author)}</p><section class="panel"><form data-book="${opened}" class="story-update"><label for="book-place-${opened}">${selected.unit === 'pages' ? 'Pages' : 'Chapters'} read</label><div><input id="book-place-${opened}" name="current" type="number" min="0" max="${selected.total}" required step="1" value="${selected.current}"><button class="secondary">Save progress</button></div></form><div class="story-actions">${link ? `<a class="primary" href="${escape(link)}" target="_blank" rel="noopener noreferrer">Open ebook ↗</a>` : ''}<button class="secondary" data-finish="${opened}">Mark finished</button><button class="text-button" data-remove="${opened}">Remove from shelf</button></div></section>`;
  }
  return `<a class="back" href="#home">← Back to home</a><h1>Story mode</h1><p class="intro">Pick a book. Find your next little adventure.</p>
  <div class="ebook-import"><label class="primary" for="ebook-file">Import ebook ↗</label><input class="sr-only" id="ebook-file" type="file" accept=".epub,.txt"><p class="hint">EPUB or plain text · DRM-free · Up to 25 MB · Stays on this device</p><p id="import-status" role="status"></p></div><section class="story-shelf" aria-label="Your ebook shelf"><article class="shelf-book"><button class="book-cover caterpillar-cover" id="open-demo" aria-label="Open The Very Hungry Caterpillar live decision demo"><span class="cover-kicker">An interactive story demo</span><strong>The Very Hungry<br>Caterpillar</strong>${caterpillar}<span class="cover-author">Eric Carle</span><span class="cover-action">${director.state.step ? 'Continue the adventure' : 'Let’s begin'} ↗</span></button><progress value="${director.state.step}" max="3" aria-label="The Very Hungry Caterpillar demo progress"></progress></article>
  <article class="shelf-book"><button class="book-cover personal-cover has-cover" id="open-peter" aria-label="Open The Tale of Peter Rabbit"><span class="cover-kicker">Included storybook</span><strong>The Tale of Peter Rabbit</strong><span class="cover-symbol" aria-hidden="true"><img src="./books/peter-rabbit-cover.jpg" alt=""></span><span class="cover-author">Beatrix Potter</span><span class="cover-action">Open book ↗</span></button><progress value="${peter.current}" max="${peter.total}" aria-label="The Tale of Peter Rabbit reading progress"></progress><button class="secondary" id="open-peter-activities">Try Braille activities →</button></article>
  ${books.map((b,i)=>`<article class="shelf-book"><button class="book-cover personal-cover" data-open-book="${i}" aria-label="Open ${escape(b.title)}"><span class="cover-kicker">My reading shelf</span><strong>${escape(b.title)}</strong><span class="cover-symbol" data-cover="${i}" aria-hidden="true">⠎</span><span class="cover-author">${escape(b.author)}</span><span class="cover-action">Open book ↗</span></button><progress value="${b.current}" max="${b.total}" aria-label="${escape(b.title)} reading progress"></progress></article>`).join('')}</section>
  <p class="hint" id="story-storage">${storageOK ? 'Your place is saved in this browser.' : 'Browser storage is unavailable. Changes may last for this visit only.'}</p>
  <details class="panel story-add-panel"><summary>Add an ebook</summary><form id="story-add" class="story-add"><div><label for="story-title">Book title</label><input id="story-title" name="title" required maxlength="160"></div><div><label for="story-author">Author (optional)</label><input id="story-author" name="author" maxlength="160"></div><div><label for="story-unit">Track by</label><select id="story-unit" name="unit"><option value="pages">Pages</option><option value="chapters">Chapters</option></select></div><div><label for="story-total">Total pages or chapters</label><input id="story-total" name="total" type="number" min="1" max="1000000" step="1" required></div><div><label for="story-current">Already read</label><input id="story-current" name="current" type="number" min="0" step="1" required value="0"></div><div><label for="story-url">Ebook link (optional)</label><input id="story-url" name="url" type="url" placeholder="https://…"></div><button class="primary" type="submit">Add to my shelf</button></form></details>`;
}
export function bindStories(main, render, announce) {
  const refresh = (message, focus) => {
    save(); render(); main.querySelector(focus)?.focus();
    announce(message + (storageOK ? '' : ' Browser storage is unavailable; this change may last for this visit only.'));
  };
  const show = () => { render(); main.focus(); window.scrollTo(0,0); };
  main.querySelector('#open-peter')?.addEventListener('click', () => { director.cancel(); opened = 'peter'; show(); });
  main.querySelector('#open-peter-activities')?.addEventListener('click', () => { opened = 'peter-activities'; show(); });
  if (opened === 'peter-activities') bindPeterActivities(main, show, () => { opened = 'peter'; show(); });
  if (opened === 'demo' && director.state.step === 3 && celebratedDemoSession !== director.state.session_id) {
    celebratedDemoSession = director.state.session_id;
    const completion = mountStoryCompletion({parent:main,title:'The Very Hungry Caterpillar · story demo'});
    disposeCompletion = () => completion.dispose();
    completion.show(demoCompletionRecap(director.state.events));
  }
  const selected = selectedBook();
  const header=main.querySelector('.player-header');
  if(header && document.querySelector('#voice-input-panel'))header.append(document.querySelector('#voice-input-panel'));
  if (selected?.imported) {
    if (!loadedEbooks.has(selected.id)) {
      loadBook(selected).then(content=>{
        if (!content) throw Error('This ebook is no longer in browser storage. Remove it and import the file again.');
        loadedEbooks.set(selected.id,content);
        if (main.querySelector('#ebook-status') && selectedBook()?.id===selected.id) show();
      }).catch(error=>{ const status=main.querySelector('#ebook-status'); if(status) status.textContent=error.message; });
    } else {
      disposeReader = mountFlipbook({main, book:selected, content:loadedEbooks.get(selected.id), save, announce});
    }
  }
  main.querySelectorAll('[data-cover]').forEach(async element=>{
    const book=books[Number(element.dataset.cover)]; if(!book.imported)return;
    try { const content=loadedEbooks.get(book.id)||await ebookStore('get',book.id); if(!content?.cover || !element.isConnected)return; const image=document.createElement('img');image.src=content.cover;image.alt='';element.replaceChildren(image);element.closest('.book-cover').classList.add('has-cover'); } catch { /* Title remains available without cover storage. */ }
  });
  main.querySelector('#ebook-file')?.addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    const status=main.querySelector('#import-status');event.target.disabled=true;status.textContent='Importing your ebook…';
    try {
      const content=await importEbook(file), id=crypto.randomUUID();
      await ebookStore('put',id,content);
      const book={id,title:content.title,author:content.author,unit:'chapters',total:content.chapters.length,current:0,position:0,scroll:0,url:'',imported:true};
      books.unshift(book);save();
      if(!storageOK){books.shift();await ebookStore('delete',id);throw Error('Your shelf could not be saved. Free browser storage and try again.');}
      loadedEbooks.set(id,content);opened=0;show();announce('Ebook imported. Ready to read.');
    } catch(error){status.textContent=error instanceof RangeError ? 'This EPUB is damaged or unsupported.' : error.message;event.target.disabled=false;event.target.value='';}
  });
  const redrawDemo = () => { if (opened === 'demo' && location.hash === '#stories') show(); };
  const refreshLearningStatus = () => {
    const outbox = director.outbox;
    const status = main.querySelector('#learning-status');
    const error = main.querySelector('#learning-error');
    if (status) status.textContent = (outbox.uploadsEnabled ? 'Uploads enabled. ' : 'Uploads paused. Existing cloud records are retained. ') + outbox.queuedCount + ' records waiting.';
    if (error) error.textContent = outbox.error;
  };
  main.querySelector('#learning-uploads')?.addEventListener('change', async event => {
    const checkbox = event.target; checkbox.disabled = true;
    try { await director.outbox.setUploadsEnabled(checkbox.checked); } catch {} finally { checkbox.disabled = false; refreshLearningStatus(); }
  });
  main.querySelector('#learning-retry')?.addEventListener('click', async event => {
    event.target.disabled = true;
    try { await director.outbox.flush(); } catch {} finally { event.target.disabled = false; refreshLearningStatus(); }
  });
  main.querySelector('#open-demo')?.addEventListener('click', () => { opened = 'demo'; show(); void director.outbox.flush().catch(() => {}).finally(refreshLearningStatus); });
  main.querySelectorAll('[data-open-book]').forEach(button => button.addEventListener('click', () => { director.cancel(); opened = Number(button.dataset.openBook); show(); }));
  main.querySelectorAll('#story-close, #story-close-done').forEach(button => button.addEventListener('click', () => { director.cancel(); opened = null; show(); }));
  main.querySelector('#demo-next')?.addEventListener('click', () => { director.advance(); show(); });
  main.querySelectorAll('[data-response]').forEach(button => button.addEventListener('click', () => { director.record(button.dataset.response, main.querySelector('#response-support')?.value || 'unknown'); show(); void director.outbox.flush().catch(() => {}).finally(refreshLearningStatus); }));
  main.querySelector('#demo-restart')?.addEventListener('click', () => { director.restart(); show(); });
  main.querySelector('#decision-retry')?.addEventListener('click', () => director.request(redrawDemo));
  main.querySelector('#decision-skip')?.addEventListener('click', () => { director.skip(); show(); });
  if (opened === 'demo' && director.state.step < 3 && !director.pending && !director.result && !director.error && !director.skipped) {
    director.request(redrawDemo);
  }
  main.querySelector('#story-add')?.addEventListener('submit' , event => {
    event.preventDefault(); const form = event.target, data = new FormData(form);
    const title = data.get('title').trim(), total = Number(data.get('total')), current = Number(data.get('current')), url = data.get('url').trim();
    form.elements.title.setCustomValidity(title ? '' : 'Enter a book title.');
    form.elements.current.setCustomValidity(Number.isSafeInteger(current) && current >= 0 && current <= total ? '' : 'Enter a whole number between zero and the total.');
    form.elements.url.setCustomValidity(!url || safeLink(url) ? '' : 'Use an http or https ebook link.');
    if (!form.reportValidity() || !Number.isSafeInteger(total) || total < 1) return;
    books.unshift({id:crypto.randomUUID(), title, author:data.get('author').trim(), unit:data.get('unit'), total, current, url:safeLink(url)});
    opened = 0; refresh(`${title} added to your shelf.`, '#book-place-0');
  });
  main.querySelector('#story-add')?.addEventListener('input', event => {
    event.target.setCustomValidity?.('');
    main.querySelector('#story-current').setCustomValidity('');
  });
  main.querySelectorAll('[data-book]').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault(); const index = Number(form.dataset.book), current = Number(new FormData(form).get('current'));
    if (!Number.isSafeInteger(current) || current < 0 || current > books[index].total) return;
    books[index].current = current;
    refresh(`Progress saved for ${books[index].title}. ${current === books[index].total ? 'Book finished. Well done!' : ''}`, `#book-place-${index}`);
  }));
  main.querySelectorAll('[data-finish]').forEach(button => button.addEventListener('click', () => {
    const index = Number(button.dataset.finish); books[index].current = books[index].total;
    refresh(`${books[index].title} finished. Well done!`, `#book-place-${index}`);
  }));
  main.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
    const index = Number(button.dataset.remove);
    if (!confirm(`Remove “${books[index].title}” and its reading progress from your shelf?`)) return;
    if (books[index].imported) { ebookStore('delete',books[index].id).catch(()=>{}); loadedEbooks.delete(books[index].id); }
    books.splice(index, 1); opened = null; refresh('Book removed from your shelf.', '#story-title');
  }));
}
