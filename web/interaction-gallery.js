const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let activities=[];
let tool,selected,resumeTimer;
const list=document.querySelector('#tools'),detail=document.querySelector('#detail'),search=document.querySelector('#search');
function renderList(){
 const rows=activities.filter(a=>`${a.title} ${a.id} ${a.description}`.toLowerCase().includes(search.value.toLowerCase()));
 document.querySelector('#count').textContent=`${rows.length} story interactions`;
 list.innerHTML=rows.map(a=>`<button data-id="${a.id}" aria-current="${a===selected}"><strong>${esc(a.title)}</strong><small>${esc(a.id)} · story moment</small></button>`).join('')||'<p>No matching interactions.</p>';
}
function select(a){
 clearTimeout(resumeTimer);selected=a;renderList();
 detail.innerHTML=`<div class="interaction-stage"><div class="story-card"><div class="rabbit-mark" aria-hidden="true">🐇</div><h2>${esc(a.narrator_line)}</h2><div class="tactile-marker" aria-label="Visual preview of Braille r">⠗</div><p id="preview-status" role="status">${a.id==='introduce'?'Take your time exploring.':'Say your answer, or choose below.'}</p><div class="answer-grid ${a.choices.length===1?'single-answer':''}">${a.choices.map((choice,i)=>`<button class="answer-tile tile-${i}" data-answer="${esc(choice)}"><span aria-hidden="true">${['▲','◆','●','■'][i]}</span>${esc(choice)}</button>`).join('')}</div><details class="quiet-controls"><summary>Need a moment?</summary><div class="actions"><button data-preview="repeat">Repeat</button><button data-preview="hint">Hint</button><button data-preview="skip">Skip</button></div></details></div></div><aside class="facilitator-note" aria-label="Facilitator information"><span class="facilitator-label">FACILITATOR NOTE</span><p><strong>${esc(a.id[0].toUpperCase()+a.id.slice(1))} · r</strong><span class="reason-tag">${esc(a.reason)}</span></p><details><summary>More context</summary><p>One brief checkpoint in Peter’s story. The narrator gives the prompt; the student responds directly. This example uses fictional content and fixed answers, with no learner records or MLflow evidence attached.</p><p>The proposed live flow waits for tactile readiness before presenting the question. Unclear speech goes to facilitator confirmation. This gallery does not capture speech or operate hardware.</p><code>${esc(tool.source)}:${tool.line} · propose_activity(${esc(a.id)})</code></details></aside>`;
}
function finish(message){
 const card=detail.querySelector('.story-card');card.querySelector('.answer-grid').innerHTML='';card.querySelector('.quiet-controls').hidden=true;
 document.querySelector('#preview-status').textContent=message;
 resumeTimer=setTimeout(()=>{
  document.querySelector('#preview-status').textContent='Peter’s adventure continues…';
  card.classList.add('story-resumed');card.querySelector('h2').textContent='Back to the story';card.querySelector('.tactile-marker').hidden=true;
 },2000);
}
list.onclick=e=>{const id=e.target.closest('[data-id]')?.dataset.id;if(id)select(activities.find(a=>a.id===id));};
detail.onclick=e=>{
 const answer=e.target.closest('[data-answer]')?.dataset.answer;
 if(answer){
  if(answer===selected.answer)finish(selected.feedback);
  else document.querySelector('#preview-status').textContent='Not quite, little explorer. Feel it once more—you can try again.';
  return;
 }
 const action=e.target.closest('[data-preview]')?.dataset.preview;
 if(action==='hint')document.querySelector('#preview-status').textContent='Feel three dots on the left and the middle dot on the right. Peter’s word is rabbit.';
 if(action==='repeat')document.querySelector('#preview-status').textContent=selected.narrator_line;
 if(action==='skip')finish('We can explore this another time. Let’s follow Peter.');
};
search.oninput=renderList;
try{
 const [inventoryResponse,scriptResponse]=await Promise.all([fetch('interaction-tools.json'),fetch('interaction-gallery-script.json')]);
 if(!inventoryResponse.ok||!scriptResponse.ok)throw Error();
 tool=(await inventoryResponse.json()).tools.find(t=>t.name==='propose_activity');
 activities=(await scriptResponse.json()).activities;
 if(!tool||!activities.length)throw Error();select(activities[0]);
}catch{detail.textContent='Unable to load the Story interaction script.';}
