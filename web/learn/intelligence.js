const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = 'magneto-learner-facts-v1';
let facts = [], storageOK = true;
try {
  const saved = JSON.parse(localStorage.getItem(key) || '[]');
  if (!Array.isArray(saved)) throw Error('Invalid facts');
  facts = saved.filter(f => typeof f?.id === 'string' && typeof f.text === 'string' && f.text.length <= 240 && typeof f.updatedAt === 'string');
} catch { storageOK = false; }
function persist() {
  try { localStorage.setItem(key, JSON.stringify(facts)); storageOK = true; }
  catch { storageOK = false; }
}
const category = (id, title, status, finding, action, body) => `<details class="learning-category category-${id}"><summary><span class="category-heading"><strong>${title}</strong><span class="category-status">${status}</span></span><span class="category-finding">${finding}</span><span class="category-chevron" aria-hidden="true">⌄</span></summary><div class="category-body">${body}</div></details>`;
const teaching = (label, action) => `<div class="teaching-adjustment"><small>${label}</small><p>${action}</p></div>`;
let syntheticTestMode = new URLSearchParams(location.search).get('profile') === 'synthetic-test';
let profile = null, loaded = false, pending = false, profileError = '', mockMode = syntheticTestMode, feedStatus = null, poll = null;
window.addEventListener('magneto-learner-evidence', () => { loaded = false; });
const percent = metric => Math.round(metric.numerator / metric.denominator * 100);
const date = value => value ? new Date(value).toLocaleString() : 'Not yet updated';
function evidenceList(ids) {
  return `<ul class="profile-evidence">${ids.map(id => {
    const e = profile.evidence.find(item => item.id === id);
    return e ? `<li>${esc(e.target)} · ${esc(e.task)} · ${esc(e.outcome.replaceAll('_',' '))}<br><small>${esc(e.condition)} · ${esc(e.session_id)} · ${esc(date(e.occurred_at))}<br>Event ${esc(e.id)}${e.trace_id ? ` · Trace ${esc(e.trace_id)}` : ' · No MLflow trace linked'}</small></li>` : '';
  }).join('')}</ul>`;
}
function trend(chart) {
  if (!chart || chart.type !== 'session_progress') return '';
  return `<section class="learner-trend"><h3>Independent recognition across sessions</h3><div class="trend-chart">${chart.points.map(p => `<div class="trend-row"><span>${esc(p.session_id)}</span><div class="trend-track" aria-hidden="true"><span class="trend-independent" style="width:${percent(p)}%"></span></div><strong>${percent(p)}% independent</strong></div>`).join('')}</div><p class="hint">Comparable target, task and conditions. Supporting counts are listed below.</p></section>`;
}
function knownFacts() {
  return `<div class="category-facts"><h2>Known facts</h2><p>Preferences and context supplied by you or a teacher.</p>
    ${facts.length ? `<ul class="learner-facts">${facts.map(f => `<li><div><strong>${esc(f.text)}</strong><small>User supplied · ${esc(new Date(f.updatedAt).toLocaleDateString())}</small></div><button class="text-button" data-edit-fact="${esc(f.id)}">Edit<span class="sr-only"> ${esc(f.text)}</span></button><button class="text-button" data-delete-fact="${esc(f.id)}">Remove<span class="sr-only"> ${esc(f.text)}</span></button></li>`).join('')}</ul>` : '<p class="hint">No facts added. Start with a preference that helps learning.</p>'}
    <form id="learner-fact-form"><label for="learner-fact">Add a learner fact</label><div class="fact-form-row"><input id="learner-fact" name="fact" required maxlength="240" placeholder="For example: prefers short practice sessions"><button class="primary" type="submit">Save fact</button><button class="text-button" id="cancel-fact-edit" type="button" hidden>Cancel edit</button></div></form><p class="hint" id="fact-storage" role="status">${storageOK ? 'Saved in this browser only. Facts are not sent to the agent.' : 'Storage unavailable. Changes last for this visit only.'}</p></div>`;
}
function validProfile(p) {
  const ids=['braille','tactile','instructions','answering','transfer','interests'];
  if(p?.schema_version!=='1.0' || typeof p.display_name!=='string' || !Array.isArray(p.categories) || p.categories.length!==6 || !Array.isArray(p.stats) || !Array.isArray(p.evidence) || !Array.isArray(p.updates)) throw Error('Unsupported learner profile.');
  if(p.categories.some((c,i)=>c.id!==ids[i] || ['title','status','finding','action','reasoning'].some(k=>typeof c[k]!=='string') || !Array.isArray(c.history) || !Array.isArray(c.evidence_ids)))throw Error('Invalid learner summaries.');
  for(const c of p.categories) for(const m of [c.metric,...(c.chart?.points||[])].filter(Boolean)) if(!Number.isInteger(m.numerator)||!Number.isInteger(m.denominator)||m.denominator<1||m.numerator<0||m.numerator>m.denominator)throw Error('Invalid learner metric.');
  return p;
}
export function intelligence() {
  const previewNotice = mockMode ? `<p class="hint" role="status">${syntheticTestMode ? 'Synthetic test · fictional learner' : 'Mock preview · fictional data'} · no live learner records changed. <button id="toggle-profile-preview" class="text-button">Return to live data</button></p>` : '';
  if (!profile) return `<div class="learner-dashboard"><span class="tag">About me</span><h1>A little more you.</h1>${previewNotice}<p role="status">${profileError ? esc(profileError) : 'Loading learner intelligence…'}</p>${profileError ? '<button id="retry-profile" class="primary">Retry</button>' : ''}</div>`;
  const name=esc(profile.display_name), subject=profile.display_name==='This learner'?'this learner':name, latest=profile.updates.at(-1);
  const sourceLink = url => { try { const u=new URL(url); return u.protocol==='https:' && u.hostname==='dbc-129a8d44-1940.cloud.databricks.com' && u.pathname.startsWith('/one/chat/threads/') ? `<a href="${esc(u.href)}" target="_blank" rel="noopener noreferrer">View Genie source</a>` : ''; } catch { return ''; } };
  return `<div class="learner-dashboard"><div class="intelligence-heading"><div><span class="tag">About me</span><h1>A little more you.</h1></div></div><p class="intro">Six ways to understand what helps ${subject} learn.</p>${previewNotice}
    <section class="learner-hero" aria-labelledby="learner-hero-title"><span class="sample-profile-label">${name} · ${profile.synthetic ? 'illustrative learner profile' : profile.evidence.length ? 'anonymous story session' : 'live profile · awaiting evidence'}</span>
      <div class="character-stage"><span class="character-orbit" aria-hidden="true"></span><span class="character-spark spark-one" aria-hidden="true">✦</span><span class="character-spark spark-two" aria-hidden="true">✦</span><img class="learner-character" src="./assets/learner-explorer-v1.png" alt="A cheerful explorer wearing teal headphones and holding a tactile Braille tile."><span class="character-caption">One curious explorer.</span></div>
      <h2 id="learner-hero-title">Discoveries, one step at a time.</h2><p>Small moments of independence deserve a little celebration.</p>
      <div class="learner-milestones">${profile.stats.map((stat,i)=>`<div><span class="milestone-symbol" aria-hidden="true">${['⠁','✦','↗'][i]||'✦'}</span><strong>${esc(stat.value)}</strong><small>${esc(stat.label)}</small></div>`).join('')}</div>
      <p class="sample-footnote">${profile.synthetic ? (profile.evidence.length ? 'Fictional evidence processed by the real local workflow. This is not a learner’s recorded history.' : 'Fictional persona · no test observations recorded yet.') : profile.evidence.length ? 'Teacher-confirmed evidence from this anonymous session. No identity or history from other sessions is assumed.' : 'No confirmed learner observations recorded yet. Complete an activity and record an outcome in Story Mode to begin.'}</p>
    </section>
    ${profile.analysis?.summary ? `<section class="profile-summary" aria-labelledby="profile-summary-title"><h2 id="profile-summary-title">Learning at a glance</h2><p>${esc(profile.analysis.summary)}</p></section>` : ''}
    ${profileError ? `<p role="status">${esc(profileError)} Showing the last loaded profile.</p>` : ''}
    <section class="learning-categories" aria-labelledby="categories-title"><div class="insights-heading"><h2 id="categories-title">What we’re learning about ${subject}</h2>${profile.synthetic ? '<span class="sample-chip">Illustrative summaries</span>' : ''}</div><p class="hint">Open a learning area to see supporting observations and suggested activities.</p>
    ${profile.categories.map(c=>category(c.id,esc(c.title),esc(c.status),esc(c.finding),esc(c.action),`
      <h3>Why this insight</h3><p>${esc(c.reasoning)}</p>${profile.analysis ? sourceLink(profile.analysis.source_url) : ''}${teaching('TRY NEXT',esc(c.action))}${trend(c.chart)}
      ${c.metric ? `<p class="hint">Supporting count: ${c.metric.numerator} of ${c.metric.denominator} comparable opportunities in the latest session.</p>` : ''}
      <details><summary>View evidence (${c.evidence_ids.length})</summary>${c.evidence_ids.length ? evidenceList(c.evidence_ids) : '<p>No supported pattern established yet.</p>'}</details>
      <details class="insight-history"><summary>How this understanding changed (${c.history.length})</summary>${c.history.slice().reverse().map(h=>`<article><small>Update ${h.epoch} · ${esc(date(h.at))}</small>${sourceLink(profile.updates.find(u=>u.epoch===h.epoch)?.source_url)}${h.previous_finding ? `<p><strong>Before:</strong> ${esc(h.previous_finding)}</p>` : ''}<p><strong>Now:</strong> ${esc(h.finding)}</p><p><strong>Why:</strong> ${esc(h.reasoning)}</p><p><strong>Next:</strong> ${esc(h.action)}</p><details><summary>Supporting evidence (${h.evidence_ids.length})</summary>${evidenceList(h.evidence_ids)}</details></article>`).join('') || '<p>No published change yet.</p>'}</details>
      ${c.id==='answering' ? (mockMode ? '<p class="hint">Learner facts can be edited in the live view.</p>' : knownFacts()) : ''}`)).join('')}
    </section>
    <details class="profile-update"><summary>About this summary${profile.updated_at ? `<span>Updated ${esc(new Date(profile.updated_at).toLocaleDateString(undefined, {month:'short',day:'numeric',year:'numeric'}))}</span>` : ''}</summary><div><p>${profile.epoch ? `Version ${profile.epoch} · ${latest?.changed_categories.length || 0} learning areas revised in this update.` : 'No learning update recorded yet.'}</p><p>These summaries are refreshed when recorded observations support a change. Open a learning area above to see its evidence and suggested next step.</p>${profile.analysis ? sourceLink(profile.analysis.source_url) : ''}</div></details>
    </div>`;
}
function loadProfile(refresh) {
  if(pending)return;
  pending=true;
  const mode=()=>mockMode ? (syntheticTestMode ? 'synthetic-test' : 'mock') : '';
  const requestedMode=mode();
  const before=JSON.stringify([profile,feedStatus?.state,feedStatus?.event_count,feedStatus?.genie,profileError]);
  Promise.all([fetch('/api/learner-profile'+(requestedMode?'?mode='+requestedMode:''),{cache:'no-store'}),requestedMode ? Promise.resolve(null) : fetch('/api/learner-profile/status',{cache:'no-store'})]).then(async ([response,status])=>{
    if(!response.ok)throw Error('Learner profile unavailable.');
    const result=validProfile(await response.json());
    const nextStatus=status?.ok?await status.json():null;
    if(mode()!==requestedMode)return;
    profile=result;feedStatus=nextStatus;profileError='';
  }).catch(error=>{if(mode()===requestedMode)profileError=error.message;}).finally(()=>{
    loaded=mode()===requestedMode;pending=false;
    const changed=before!==JSON.stringify([profile,feedStatus?.state,feedStatus?.event_count,feedStatus?.genie,profileError]);
    if(location.hash==='#intelligence' && (changed || !loaded))refresh();
  });
}
export function bindIntelligence(main, refresh, announce) {
  const toggle=main.querySelector('#toggle-profile-preview');
  if(toggle)toggle.onclick=()=>{mockMode=!mockMode;syntheticTestMode=false;profile=null;loaded=false;profileError='';refresh();};
  if (!poll) poll=setInterval(()=>{if(location.hash==='#intelligence' && !mockMode)loadProfile(refresh);},15000);
  if (!loaded)loadProfile(refresh);
  const retry=main.querySelector('#retry-profile');
  if(retry)retry.onclick=()=>{loaded=false;profileError='';refresh();};
  const form = main.querySelector('#learner-fact-form');
  if(!form)return;
  const focusFacts = () => { const field = main.querySelector('#learner-fact'); field.closest('.learning-category').open = true; field.focus(); };
  let editing = null;
  main.querySelectorAll('[data-edit-fact]').forEach(button => button.onclick = () => {
    editing = button.dataset.editFact;
    form.elements.fact.value = facts.find(f => f.id === editing).text;
    form.querySelector('label').textContent = 'Edit learner fact';
    form.querySelector('[type=submit]').textContent = 'Save changes';
    main.querySelector('#cancel-fact-edit').hidden = false;
    form.elements.fact.focus();
  });
  main.querySelector('#cancel-fact-edit').onclick = () => { refresh(); focusFacts(); };
  form.onsubmit = event => {
    event.preventDefault();
    const text = form.elements.fact.value.trim();
    if (!text) { form.elements.fact.focus(); return; }
    const fact = {id: editing || crypto.randomUUID(), text, updatedAt: new Date().toISOString()};
    if (editing) facts = facts.map(f => f.id === editing ? fact : f); else facts.push(fact);
    persist(); refresh(); focusFacts();
    announce(storageOK ? 'Learner fact saved in this browser.' : 'Learner fact added for this visit. Browser storage is unavailable.');
  };
  main.querySelectorAll('[data-delete-fact]').forEach(button => button.onclick = () => {
    facts = facts.filter(f => f.id !== button.dataset.deleteFact);
    persist(); refresh(); focusFacts();
    announce(storageOK ? 'Learner fact removed.' : 'Fact removed for this visit. Browser storage is unavailable.');
  });
}
