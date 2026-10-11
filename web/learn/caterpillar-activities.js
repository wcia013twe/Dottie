// Fixed local demo opportunities. No hardware, AI grading, or learner publication.
export const caterpillarActivities = [
  {id:'egg',page:4,label:'Find the egg',prompt:'Find the tiny egg on the leaf. What shape is the egg?'},
  {id:'moon',page:5,label:'Moon shape',prompt:'Explore the moon. Is its shape round or square?'},
  {id:'sun',page:7,label:'Sun color',prompt:'Look at the big sun. Name one color you can see in it.'},
  {id:'apple',page:9,label:'Apple and A',prompt:'Find the apple. Apple begins with A. Can you say the letter A?'},
  {id:'pears',page:11,label:'Two pears and P',prompt:'Count the two pears. Pear begins with P. Can you say the letter P?'},
  {id:'plums',page:13,label:'Count three plums',prompt:'Find the purple plums. How many plums are there?'},
  {id:'berries',page:15,label:'Count four strawberries',prompt:'Find the red strawberries. Count them slowly. How many are there?'},
  {id:'oranges',page:17,label:'Count five oranges',prompt:'Find the oranges. Count them from left to right. How many are there?'},
  {id:'leaf',page:20,label:'Leaf and L',prompt:'Explore the green leaf. Leaf begins with L. Can you say the letter L?'},
  {id:'butterfly',page:25,label:'Butterfly and B',prompt:'Explore the butterfly wings. Butterfly begins with B. Can you say the letter B?'}
];
export const defaultCaterpillarPlan = ['apple','pears','butterfly'];
export function selectedCaterpillarActivities(plan){
  const ids=Array.isArray(plan)?plan:defaultCaterpillarPlan;
  return caterpillarActivities.filter(a=>ids.includes(a.id)).slice(0,4);
}
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function mountCaterpillarActivities({player,book,save,pause,onResume,onQuestionStops}){
  const panel=document.createElement('aside');panel.className='story-coach';panel.hidden=true;panel.setAttribute('aria-label','Caterpillar demo activity');player.append(panel);
  const audio=new Audio();let manifest=null,disposed=false,currentPage=null,active=null,config=false;
  const offered=new Set();
  if(book.demoActivitySession!==book.readingSessionId){book.demoActivitySession=book.readingSessionId;book.demoActivityResults={};save();}
  if(!book.demoActivityResults || typeof book.demoActivityResults!=='object')book.demoActivityResults={};
  const results=book.demoActivityResults;
  fetch('./narration/caterpillar-demo-activities/manifest.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(m=>{if(!disposed)manifest=m;}).catch(()=>{});
  function stops(){onQuestionStops(selectedCaterpillarActivities(book.demoActivityPlan).map(a=>({id:a.id,status:results[a.id]?.status||'planned',planned:!results[a.id]})));}
  function stopSpeech(){audio.pause();window.speechSynthesis?.cancel();}
  function speak(){
    stopSpeech();const clip=manifest?.book_id==='caterpillar-demo-activities'?manifest.passages?.find(p=>p.id===active?.id):null;
    const fallback=()=>{if(active && 'speechSynthesis' in window){const speech=new SpeechSynthesisUtterance(active.prompt);speech.rate=.85;speechSynthesis.speak(speech);}};
    if(clip && /^[a-zA-Z0-9_-]+-[a-f0-9]{64}\.wav$/.test(clip.audio)){audio.src='./narration/caterpillar-demo-activities/'+clip.audio;audio.onerror=fallback;audio.play().catch(fallback);}else fallback();
  }
  function render(){
    panel.hidden=!active&&!config;if(panel.hidden)return;
    if(config){panel.innerHTML=`<header><span>DEMO QUESTION PLAN</span><button data-close aria-label="Close question plan">×</button></header><h2>Choose up to four stops</h2><p>Ten candidate opportunities. Three selected by default. Fixed local demo; no hardware or learner-profile updates.</p><form id="demo-plan">${caterpillarActivities.map(a=>`<label class="demo-plan-choice"><input type="checkbox" name="activity" value="${a.id}" ${selectedCaterpillarActivities(book.demoActivityPlan).some(s=>s.id===a.id)?'checked':''}> Page ${a.page} · ${esc(a.label)}</label>`).join('')}<p role="alert" id="demo-plan-error"></p><button type="submit">Save question plan</button></form>`;
      panel.querySelector('form').onsubmit=e=>{e.preventDefault();const ids=[...panel.querySelectorAll('input:checked')].map(i=>i.value);if(ids.length>4){panel.querySelector('#demo-plan-error').textContent='Choose at most four stops.';return;}book.demoActivityPlan=ids;save();stops();close();};
    }else{
      const row=results[active.id];panel.innerHTML=`<header><span>LOCAL DEMO · PAGE ${active.page}</span><button data-close aria-label="Close demo activity">×</button></header><h2>${esc(active.label)}</h2><p class="coach-question">${esc(active.prompt)}</p><p class="coach-note">Spoken, typed or assisted responses are welcome. Teacher records the outcome; this demo does not update learner evidence.</p>${row?`<p role="status">Saved demo result: ${esc(row.status)}</p>`:''}<button data-replay>Replay prompt</button><label for="demo-answer">Demo answer (optional)</label><input id="demo-answer" maxlength="300" value="${esc(row?.answer||'')}" placeholder="Type an answer, or observe a spoken response"><div class="coach-actions"><button data-outcome="solved">Independent</button><button data-outcome="assisted">With help</button><button data-outcome="skipped">Skip</button></div><button data-continue>Continue story →</button>`;
      panel.querySelector('[data-replay]').onclick=speak;
      panel.querySelectorAll('[data-outcome]').forEach(b=>b.onclick=()=>{results[active.id]={status:b.dataset.outcome,answer:panel.querySelector('#demo-answer').value,recordedAt:new Date().toISOString()};save();stops();render();});
      panel.querySelector('[data-continue]').onclick=()=>{if(!results[active.id]){results[active.id]={status:'skipped',answer:panel.querySelector('#demo-answer').value,recordedAt:new Date().toISOString()};save();stops();}close();onResume();};
    }
    panel.querySelector('[data-close]').onclick=close;
  }
  function close(){stopSpeech();active=null;config=false;render();}
  function review(id){active=caterpillarActivities.find(a=>a.id===id);if(!active)return;config=false;offered.add(active.id);pause();render();speak();}
  const planButton=player.querySelector('#open-story-coach');
  if(planButton){planButton.textContent='Demo questions';planButton.onclick=()=>{pause();stopSpeech();active=null;config=true;render();};}
  queueMicrotask(()=>{if(!disposed)stops();});
  return {context(page){currentPage=Number(page);if(active||config)close();},offerQuestion(){const a=selectedCaterpillarActivities(book.demoActivityPlan).find(a=>a.page===currentPage&&!results[a.id]&&!offered.has(a.id));if(a)review(a.id);},review,stopSpeech,isPaused(){return !!active||config;},observations(){return [];},leaveForReview(){close();},dispose(){disposed=true;stopSpeech();panel.remove();}};
}
