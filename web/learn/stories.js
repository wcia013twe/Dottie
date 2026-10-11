import { ensureReadingSession, finishReadingSession, restartReadingSession, readingLabel } from './reading-session.js';
import { demoCompletionRecap, mountStoryCompletion } from './story-completion.js';
import { preparePeterReading, PETER_READING_VERSION } from './peter-reading.js?v=merge-main-1';
import { DecisionSession } from './decision-session.js';
import { peterActivities, bindPeterActivities } from './peter-activities.js';
import { mountFlipbook } from './flipbook.js?v=caterpillar-demo-1';
import { childrenBooks } from './book-catalog.js';
import { importEbook, ebookStore } from './ebook.js?v=merge-main-1';
// Reading records are separate from learning progress and saved CAD designs.
const key = 'magneto-stories-v1';
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeLink = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } };
let books = [], storageOK = true;
const loadedEbooks = new Map();
let readerSize = 20;
let catalogQuery = '';
let catalogLoading = false;
const matchesCatalog = book => `${book.title} ${book.author}`.toLocaleLowerCase().includes(catalogQuery.trim().toLocaleLowerCase());
let disposeReader = null;
let disposeCompletion = null;
let celebratedDemoSession = null;
export function cleanupStoryReader() {
  const microphone=document.querySelector('#voice-microphone');
  if(microphone?.closest('.book-player'))document.querySelector('.topbar').insertBefore(microphone,document.querySelector('.profile-dropdown'));
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
  for (const field of ['readingSessionId','startedAt','completedAt','coachSessionId']) {
    if (typeof saved[field] === 'string') peter[field] = saved[field];
  }
  if (Array.isArray(saved.readingSessions)) peter.readingSessions = saved.readingSessions;
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
  if (!book.bundled) {
    const stored = await ebookStore('get',book.id);
    if (stored) return stored;
    const entry = childrenBooks.find(entry => entry.id === book.id);
    if (!entry) return;
    const response = await fetch(entry.file);
    if (!response.ok) throw Error('This library book could not be opened. Try again.');
    return importEbook(new File([await response.blob()], entry.file.split('/').pop()));
  }
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
    return `<section class="book-player" aria-label="Story player"><header class="player-header"><button class="player-button" id="story-close" aria-label="Save and leave book" title="Save and leave book">←</button><div class="player-title"><h1>${escape(selected.title)}</h1><p>${escape(selected.author)}</p></div>${(selected.bundled || selected.id==='local-very-hungry-caterpillar') ? '<button class="player-activity" id="open-story-coach">⠗ <span>Teacher coach</span></button>' : ''}</header><div id="ebook-status" role="status">${content ? '' : 'Opening your book…'}</div>${content ? `<div class="player-stage"><article class="flipbook" id="ebook-content" tabindex="0" aria-label="Book text" style="font-size:${readerSize}px"><div class="book-sheet" id="book-sheet"><div class="page-window" id="page-window"><div class="page-text" id="page-text"></div></div></div></article></div><footer class="player-controls"><label class="sr-only" for="reader-seek">Page in this chapter</label><div class="reader-timeline"><input id="reader-seek" type="range" min="1" max="1" value="1" step="1"><div id="question-markers" aria-label="Question stops and results"></div></div><p id="question-stop-label" class="question-stop-label" hidden></p><div class="player-control-row"><button class="player-button" id="reader-play" aria-label="Play automatic page turns" title="Auto-turn pages every 12 seconds">▶</button><button class="player-button" id="reader-prev" aria-label="Previous page" title="Previous page">❮</button><button class="player-button" id="reader-next" aria-label="Next page" title="Next page">❯</button><span id="reader-feedback" role="status"></span><span class="player-spacer"></span><details class="player-settings"><summary aria-label="Reader settings" title="Reader settings">⚙</summary><div class="player-settings-panel"><button type="button" id="reader-finish">Mark book completed</button><button type="button" id="reader-restart"><span aria-hidden="true">↻</span> Restart book</button><label for="reader-chapter">Chapter</label><select id="reader-chapter">${content.chapters.map((chapter,i)=>`<option value="${i}" ${i===position?'selected':''}>${escape(chapter.title)}</option>`).join('')}</select><label for="reader-size">Text size</label><select id="reader-size"><option value="20" ${readerSize===20?'selected':''}>Standard</option><option value="24" ${readerSize===24?'selected':''}>Large</option><option value="30" ${readerSize===30?'selected':''}>Extra large</option></select><p>Pages turn automatically every 12 seconds, waiting while narration plays. Pause, use arrow keys or swipe to read at your own pace.</p></div></details><button class="player-button" id="reader-fullscreen" aria-label="Enter fullscreen" title="Fullscreen">⛶</button></div><div class="player-meta"><span id="player-mode">Read at your own pace</span><span>Your place is saved automatically</span></div></footer>` : ''}</section>`;
  }
  if (selected) {
    const link = safeLink(selected.url);
    return `<button class="back text-button" id="story-close">← Back to my books</button><h1>${escape(selected.title)}</h1><p class="intro">${escape(selected.author)}</p><section class="panel"><form data-book="${opened}" class="story-update"><label for="book-place-${opened}">${selected.unit === 'pages' ? 'Pages' : 'Chapters'} read</label><div><input id="book-place-${opened}" name="current" type="number" min="0" max="${selected.total}" required step="1" value="${selected.current}"><button class="secondary">Save progress</button></div></form><div class="story-actions">${link ? `<a class="primary" href="${escape(link)}" target="_blank" rel="noopener noreferrer">Open ebook ↗</a>` : ''}<button class="secondary" data-finish="${opened}">Mark completed</button><button class="story-restart" title="Start a new reading session from the beginning" data-restart-book="${opened}"><span aria-hidden="true">↻</span> Restart book</button><button class="text-button" data-remove="${opened}">Remove from shelf</button></div></section>`;
  }
  return `<a class="back" href="#home">← Back to home</a><h1>Story mode</h1><p class="intro">Pick a book. Find your next little adventure.</p>
  <div class="ebook-import"><div class="story-actions"><button class="secondary" id="ebook-search" type="button">Search ebook</button><label class="primary" for="ebook-file">Import ebook ↗</label></div><input class="sr-only" id="ebook-file" type="file" accept=".epub,.txt"><p class="hint">Find a classic in our library below, or import your own ebook.</p><p class="hint">EPUB or plain text · DRM-free · Up to 25 MB · Stays on this device</p><p id="import-status" role="status"></p></div><h2>My books</h2><section class="story-shelf" aria-label="Your ebook shelf">
  <article class="shelf-book"><button class="book-cover personal-cover has-cover" id="open-peter" aria-label="Open The Tale of Peter Rabbit"><span class="cover-kicker">Included storybook</span><strong>The Tale of Peter Rabbit</strong><span class="cover-symbol" aria-hidden="true"><img src="./books/peter-rabbit-cover.jpg" alt=""></span><span class="cover-author">Beatrix Potter</span><span class="cover-action">${readingLabel(peter)} ↗</span></button><progress value="${peter.current}" max="${peter.total}" aria-label="The Tale of Peter Rabbit reading progress"></progress><div class="shelf-actions"><button class="story-restart" title="Start a new reading session from the beginning" data-restart-book="peter"><span aria-hidden="true">↻</span> Restart book</button></div></article>
  ${books.map((b,i)=>`<article class="shelf-book"><button class="book-cover personal-cover" data-open-book="${i}" aria-label="Open ${escape(b.title)}"><span class="cover-kicker">My reading shelf</span><strong>${escape(b.title)}</strong><span class="cover-symbol" data-cover="${i}" aria-hidden="true">⠎</span><span class="cover-author">${escape(b.author)}</span><span class="cover-action">${readingLabel(b)} ↗</span></button><progress value="${b.current}" max="${b.total}" aria-label="${escape(b.title)} reading progress"></progress><div class="shelf-actions"><button class="story-restart" title="Start a new reading session from the beginning" data-restart-book="${i}"><span aria-hidden="true">↻</span> Restart book</button></div></article>`).join('')}</section>
  <p class="hint" id="story-storage">${storageOK ? 'Your place is saved in this browser.' : 'Browser storage is unavailable. Changes may last for this visit only.'}</p>
  <section class="ebook-catalog" aria-labelledby="catalog-heading"><h2 id="catalog-heading">Find a story</h2><p class="hint">Children’s classics, ready to read here.</p><label for="catalog-query">Search by title or author</label><input id="catalog-query" type="search" value="${escape(catalogQuery)}" placeholder="Try Winnie-the-Pooh or Lewis Carroll" autocomplete="off"><p id="catalog-count" class="hint" role="status">${childrenBooks.filter(matchesCatalog).length} books found</p><p id="catalog-status" role="status"></p><div class="catalog-grid">${childrenBooks.map(book => `<article class="catalog-card" data-catalog-card="${book.id}" ${matchesCatalog(book) ? '' : 'hidden'}><button class="catalog-open" data-catalog-book="${book.id}" aria-label="${books.some(saved => saved.id === book.id) ? 'Continue reading' : 'Read'} ${escape(book.title)}"><span class="catalog-cover">${book.cover ? `<img src="${book.cover}" alt="" loading="lazy">` : `<span>${escape(book.title)}</span>`}</span><span class="catalog-title">${escape(book.title)}</span><span class="catalog-author">${escape(book.author)}</span><span class="catalog-description">${escape(book.description)}</span><span class="catalog-read">${books.some(saved => saved.id === book.id) ? 'Continue reading' : 'Add & read'} →</span></button><a class="catalog-source" href="${book.source}" target="_blank" rel="noopener noreferrer" aria-label="${escape(book.sourceLabel || 'Project Gutenberg')} source for ${escape(book.title)} (opens in a new tab)">${escape(book.sourceLabel || 'Project Gutenberg')} ↗</a></article>`).join('')}</div><p class="hint">Classic editions from Project Gutenberg retain their notices. User-supplied books retain their original source.</p></section>
`;
}
export function bindStories(main, render, announce) {
  const refresh = (message, focus) => {
    save(); render(); main.querySelector(focus)?.focus();
    announce(message + (storageOK ? '' : ' Browser storage is unavailable; this change may last for this visit only.'));
  };
  const show = () => { render(); main.focus(); window.scrollTo(0,0); };
  main.querySelector('#ebook-search')?.addEventListener('click', () => {
    const input = main.querySelector('#catalog-query');
    input?.scrollIntoView({block:'center',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    input?.focus({preventScroll:true});
  });
  main.querySelector('#catalog-query')?.addEventListener('input', event => {
    catalogQuery = event.target.value;
    main.querySelectorAll('[data-catalog-card]').forEach(card => {
      card.hidden = !matchesCatalog(childrenBooks.find(book => book.id === card.dataset.catalogCard));
    });
    const count = childrenBooks.filter(matchesCatalog).length;
    main.querySelector('#catalog-count').textContent = count ? `${count} ${count === 1 ? 'book' : 'books'} found` : 'No books found. Try another title or author.';
  });
  main.querySelectorAll('[data-catalog-book]').forEach(button => button.addEventListener('click', async () => {
    if (catalogLoading) return;
    const entry = childrenBooks.find(book => book.id === button.dataset.catalogBook);
    const existing = books.findIndex(book => book.id === entry.id);
    if (existing >= 0) { director.cancel(); opened = existing; show(); return; }
    catalogLoading = true;
    const status = main.querySelector('#catalog-status');
    main.querySelectorAll('[data-catalog-book]').forEach(control => { control.disabled = true; });
    status.textContent = `Opening ${entry.title}…`;
    try {
      const response = await fetch(entry.file);
      if (!response.ok) throw Error('This library book could not be loaded. Try again.');
      const content = await importEbook(new File([await response.blob()], entry.file.split('/').pop()));
      await ebookStore('put', entry.id, content);
      books.unshift({id:entry.id,title:entry.title,author:entry.author,unit:'chapters',total:content.chapters.length,current:0,position:0,imported:true});
      save();
      if (!storageOK) { books.shift(); await ebookStore('delete',entry.id); throw Error('Your shelf could not be saved. Free browser storage and try again.'); }
      loadedEbooks.set(entry.id, content);
      if (status.isConnected && location.hash === '#stories') {
        director.cancel(); opened = 0; show(); announce(`${entry.title} added. Ready to read.`);
      }
    } catch (error) { if (status.isConnected) status.textContent = error.message; }
    finally { catalogLoading = false; main.querySelectorAll('[data-catalog-book]').forEach(control => { control.disabled = false; }); }
  }));
  main.querySelector('#open-peter')?.addEventListener('click', () => { director.cancel(); opened = 'peter'; show(); });
  if (opened === 'peter-activities') bindPeterActivities(main, show, () => { opened = 'peter'; show(); });
  if (opened === 'demo' && director.state.step === 3 && celebratedDemoSession !== director.state.session_id) {
    celebratedDemoSession = director.state.session_id;
    const completion = mountStoryCompletion({parent:main,title:'The Very Hungry Caterpillar · story demo'});
    disposeCompletion = () => completion.dispose();
    completion.show(demoCompletionRecap(director.state.events));
  }
  const selected = selectedBook();
  if (selected) { ensureReadingSession(selected); save(); }
  let restarting = false;
  const restart = async (book, destination) => {
    if (restarting) return;
    restarting = true;
    try {
      if (book.imported && !loadedEbooks.has(book.id)) {
        const content = await loadBook(book);
        if (!content) throw Error('This ebook is no longer in browser storage.');
        loadedEbooks.set(book.id, content);
      }
      disposeReader?.(); disposeReader = null;
      restartReadingSession(book, loadedEbooks.get(book.id)?.readingStart || 0);
      save(); opened = destination; show(); announce('New reading session started.');
    } catch (error) { announce(error.message); }
    finally { restarting = false; }
  };
  main.querySelector('#reader-restart')?.addEventListener('click', () => restart(selected, opened));
  main.querySelectorAll('[data-restart-book]').forEach(button => button.addEventListener('click', () => {
    const destination = button.dataset.restartBook === 'peter' ? 'peter' : Number(button.dataset.restartBook);
    restart(destination === 'peter' ? peter : books[destination], destination);
  }));
  const header=main.querySelector('.player-header');
  if(header && document.querySelector('#voice-microphone'))header.append(document.querySelector('#voice-microphone'));
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
  main.querySelectorAll('[data-open-book]').forEach(button => button.addEventListener('click', () => { director.cancel(); opened = Number(button.dataset.openBook); show(); }));
  main.querySelectorAll('#story-close, #story-close-done').forEach(button => button.addEventListener('click', () => { director.cancel(); save(); opened = null; if (document.fullscreenElement) void document.exitFullscreen().catch(()=>{}); show(); }));
  main.querySelector('#demo-next')?.addEventListener('click', () => { director.advance(); show(); });
  main.querySelectorAll('[data-response]').forEach(button => button.addEventListener('click', () => { director.record(button.dataset.response, main.querySelector('#response-support')?.value || 'unknown'); show(); void director.outbox.flush().catch(() => {}).finally(refreshLearningStatus); }));
  main.querySelector('#demo-restart')?.addEventListener('click', () => { director.restart(); show(); });
  main.querySelector('#decision-retry')?.addEventListener('click', () => director.request(redrawDemo));
  main.querySelector('#decision-skip')?.addEventListener('click', () => { director.skip(); show(); });
  if (opened === 'demo' && director.state.step < 3 && !director.pending && !director.result && !director.error && !director.skipped) {
    director.request(redrawDemo);
  }
  main.querySelectorAll('[data-book]').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault(); const index = Number(form.dataset.book), current = Number(new FormData(form).get('current'));
    if (!Number.isSafeInteger(current) || current < 0 || current > books[index].total) return;
    books[index].current = current;
    if (current === books[index].total) finishReadingSession(books[index]);
    refresh(`Progress saved for ${books[index].title}. ${current === books[index].total ? 'Book finished. Well done!' : ''}`, `#book-place-${index}`);
  }));
  main.querySelectorAll('[data-finish]').forEach(button => button.addEventListener('click', () => {
    const index = Number(button.dataset.finish); finishReadingSession(books[index]);
    refresh(`${books[index].title} finished. Well done!`, `#book-place-${index}`);
  }));
  main.querySelectorAll('[data-remove]').forEach(button => button.addEventListener('click', () => {
    const index = Number(button.dataset.remove);
    if (!confirm(`Remove “${books[index].title}” and its reading progress from your shelf?`)) return;
    if (books[index].imported) { ebookStore('delete',books[index].id).catch(()=>{}); loadedEbooks.delete(books[index].id); }
    books.splice(index, 1); opened = null; refresh('Book removed from your shelf.', '#ebook-search');
  }));
}
