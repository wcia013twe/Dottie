const diagram=document.querySelector('#diagram'),svg=document.querySelector('#edges');
const title=document.querySelector('#detailTitle'),body=document.querySelector('#detailBody'),source=document.querySelector('#detailSource');
const nodes=new Map([...document.querySelectorAll('.node')].map(n=>[n.dataset.id,n]));
const info={
 synthetic_fixture:['Synthetic learner test CLI','Explicit fictional observations flow through a separate SQL table, Genie prose validation, isolated profile publication and read-only About me test mode. Cloud proof passed for seventeen fixture events and a saved Story UI identification observation, with unchanged replay. The Story identification proposal was a controlled test fixture. The isolated Story server also supplies Alex Morgan’s fictional starting profile to MCP/model context and accepts typed test replies plus bounded follow-up proposals. Persona assumptions are not observations; session snapshots stay in isolated JSONL logs. Never writes the live learner table or selects a live learner.','scripts/test_synthetic_cloud_flow.py · reports/storybook-session-test/audit.json'],
 synthetic_table:['Synthetic learner test table','workspace.magneto.synthetic_learner_e2e_v1 contains only explicitly fictional software-test events. SQL round-trip equality passed. Genie and the profile retain synthetic:true. This is separate from real learner evidence and approved research.','scripts/test_synthetic_cloud_flow.py · learner_genie.generate_synthetic_test'],
 story_narration:['Recorded story narration','Restored existing cached ElevenLabs passage player from the narrated-reader checkout. The synthetic-test server serves the same local manifest and generated WAV clips; each matched page starts its recorded audio when shown. The automatic page-turn control remains separate. Browser autoplay restrictions expose the existing audio play control.','web/learn/narration.js · web/learn/flipbook.js · web/learn/narration/builtin-peter-rabbit/manifest.json'],
 navigation_audio:['Navigation voice prompts','Fixed UI phrases and opt-in spoken navigation, quiet while a book is open. Turning guidance off stops only its own output. The packaging CLI reads the private root .env, preferring ELEVENLABS_VOICE_ID and ELEVENLABS_MODEL_ID over harness defaults, and caches generated clips. The browser plays packaged WAV files locally, independently of browser speech support. Audio on and Spoken navigation now share the saved opt-in; startup playback waits for the manifest, and blocked autoplay exposes a Retry audio action. Browser speech remains the fallback for missing or failed clips. Nine clips were generated successfully with the configured voice; the browser can play them locally.','web/learn/navigation-voice.js · navigation-prompts.json · scripts/package_navigation_voice.py'],
 eleven_tts:['ElevenLabs speech packaging','Explicit packaging command generates nine basic navigation clips once. Uses the existing cane_vision.ElevenLabsTTS cache and orin-harness speech configuration. The private root .env supplies the key and voice ID without including credentials in browser assets. Nine navigation clips were generated successfully; microphone transcription remains separately unverified.','cane-vision/cane_vision/elevenlabs.py · orin-harness/config.yaml'],
 scribe:['ElevenLabs Scribe','External realtime transcription service. Browser authentication uses a single-use token issued by the local broker. Requires an ElevenLabs key with speech-to-text access and quota. Live service and microphone execution are unverified.','scripts/voice_bridge.py · web/learn/voice.js'],
 device_status:['Device connection sidebar','Webcam state follows the actual browser media track, including mute, stop and navigation. Nano checks use a server-configured SSH target and verify the device-tree model. A successful SSH check verifies host identity, not the app runtime or physical Braille. The small Visualizer button opens the existing single-cell CAD with a browser-local Nano signal simulation: DOTS/CLEAR commands, simulated CELL responses and illustrative servo/reset motion. It has no hardware transport.','web/learn/device-status.js → scripts/nano_bridge.py → orin-harness/magneto_harness/devices/nano_status.py · web/learn/visualizer.js → web/signal-visualizer.js'],
 nano:['Jetson Nano host','Read-only, key-based SSH identity check. No target is configured by default. A trusted SSH host and noninteractive authentication are required; the check never changes host keys or starts hardware actions.','MAGNETO_NANO_SSH or .local/device-connections.json'],
 voice:['Browser voice input','Microphone PCM streams to ElevenLabs Scribe v2 Realtime using a single-use token from the local server. Committed speech routes to bounded navigation, reading, Explore selection and practice actions. Story transcripts remain unconfirmed. Routine Story confirmations are quiet; explicit reading has separate pause/resume controls. The server reads ELEVENLABS_API_KEY from the private root .env or environment at startup; live transcription has not been verified.','web/learn/voice.js → voice-actions.js · scripts/voice_bridge.py'],
 explore:['Explore camera','Browser webcam frames are sent to the same-origin local recognizer. Detected objects can be selected for browser speech and on-screen Braille. Frames stay in memory; no learner evidence is recorded.','web/learn/explore.js → scripts/explore_bridge.py'],
 vision:['Local camera recognizer','Persistent isolated Python worker reuses cane_vision.Detector and LabelMap. YOLO11n detects everyday COCO objects; dependencies and local model are required. Browser chooses a detected object; cane-tip targeting is not integrated.','scripts/explore_worker.py · .venv-camera · .local/camera/yolo11n.pt'],
 judged_updater:['Judged learner updater CLI','Opt-in CLI generates learner-profile prose using the hosted Qwen model, validates structure and provenance, and gates publication with the native MLflow learner_update_evidence_v1 judge. Writes versioned profiles to an isolated local store. The live page and automatic Story Mode updater use the separate Genie workflow with deterministic metrics.','scripts/learner_judged_updater.py · reports/learner-judge-proof.json'],
 browser:['Browser teaching demo','Sends complete approved snapshots to the localhost bridge. Validated decisions return here; teacher outcomes are saved locally before the next request. Braille is simulated.','web/learn/decision-session.js → scripts/decision_bridge.py'],
 bridge:['Local Python bridge','Uses Services.invoke_agent to call the director. Databricks credentials remain in the local authenticated adapter.','scripts/platform_invoke.py → databricks/platform/magneto_platform/services.py'],
 director:['Learning director App','One model call chooses teach or continue. The App validates the decision and traces context, output and timing with MLflow. Live preflight on 2026-10-11: App RUNNING, but local HTTPS invocation is blocked by DNS/security filtering. The hostname resolves to Cisco Umbrella block-page IP 146.112.61.110 and presents a Cisco/OpenDNS certificate. CLI authentication is valid; see reports/app-tls-diagnosis.json.','databricks/magneto-director/agent/agent.py · agent-bricks-magneto-director'],
 model:['Foundation model endpoint','databricks-qwen3-next-80b-a3b-instruct. Shared by the director, Story Mode, and the direct Orin planning mode. Metadata access does not run an inference.','databricks/platform/services.toml → Services.complete'],
 story:['Story Mode MCP','The local orchestrator discovers allowed MCP tools and calls the shared model directly. It does not invoke the deployed director. Teacher approval and controller revision checks govern the proposal.','story_mode/orchestrator.py → Services.complete'],
 harness:['Orin harness','Current configuration: backend sim, direct model, scripted listening. Agent mode can instead invoke the companion App. The harness validates and executes one tool; physical readiness needs a device acknowledgement.','orin-harness/config.yaml · magneto_harness/brain/'],
 companion:['Companion App','Optional alternative planner: agent-bricks-magneto-companion. It returns one tool plan; it never executes hardware or grades a response. Live preflight on 2026-10-11 returned NotFound: this optional App is not deployed.','databricks/magneto-companion/agent/agent.py → shared platform adapter'],
 schema:['Unity Catalog namespace','workspace.magneto governs the references volume, research Delta tables and MLflow UC trace tables. The namespace is shared; the workloads have separate lifecycles.','databricks/platform/services.toml · research-pipeline/config/operations.toml'],
 director_traces:['Director MLflow','/Shared/agentbricks_traces/magneto-director-uc. Traces use UC table prefix 948045133158359. Local reflection now consumes Story Mode observations, but does not retrieve these traces.','Services.configure_tracing · databricks/platform/services.toml'],
 references:['References volume','/Volumes/workspace/magneto/references stores explicitly uploaded PDFs and research artifacts. Files are not automatically supplied to the model.','research-pipeline/src/magneto_research/ · workspace.magneto.references'],
 warehouse:['SQL warehouse','a5e11b7fe2c6dbbc supports research SQL and trace setup/readback. Checking warehouse metadata does not start a query or prove table permissions.','research-pipeline/config/operations.toml · platform/services.toml'],
 processing:['Managed AI processing','Explicit intake, ai_parse_document, ai_prep_search and ai_extract feed research records. Human review determines publication eligibility; advisory judging is traced separately.','research-pipeline/src/magneto_research/pipeline.py'],
 tables:['Research Delta tables','Seven research-owned tables: sources, chunks, findings, recommendations, reviews, runs and search_documents. Eligibility views protect publication and retrieval. The access button does not query these tables.','research-pipeline/src/magneto_research/storage.py'],
 search_index:['AI Search','workspace.magneto.research_index on endpoint magneto-research. Delta-sync publishes search documents; retrieval revalidates eligibility and citations. The director now has an opt-in approved-guidance adapter with current Delta eligibility checks. MAGNETO_RESEARCH_ENABLED is absent from app.yaml; deployment, serving-identity data access and a live cited decision remain unverified.','magneto-director/agent/research.py → agent/decision.py · research-pipeline/config/operations.toml'],
 embeddings:['Embedding endpoint','databricks-qwen3-embedding-0-6b is the configured managed embedding endpoint for the Delta-sync index. Access to endpoint metadata does not prove indexing or inference.','research-pipeline/config/operations.toml'],
 research_traces:['Research MLflow','/Shared/magneto-research is separate from the director experiment. It records research operations and advisory judging. A model assessment does not grant human approval.','research-pipeline/src/magneto_research/tracking.py'],
 reflection:['Local learner reflection','Story Mode record_observation queues teacher-confirmed identification evidence immediately, syncs it through SQL, and reads it back for Genie prose generation. Closing a book only saves reading position; coach sessions are anonymous and in memory. Only identification has an automatic evidence adapter. Code validates deterministic metrics and conditional epochs. Trace joins and planner memory readback remain unconnected.','scripts/story_bridge.py → learner_bridge.publish_story → scripts/learner_intelligence.py'],
 learner_profile:['Local learner profile endpoint','GET /api/learner-profile supplies the live About me view, which polls profile and sync status. Mock mode is explicitly isolated. Existing live Genie proof has empty evidence; a nonempty confirmed-event run is still required.','scripts/serve.py → scripts/learner_bridge.py'],
 learner_evidence:['Learner evidence in Unity Catalog','SQL stores confirmed, non-synthetic Story observations in workspace.magneto.learner_observations_v1. Live preflight on 2026-10-11 found zero confirmed observations and zero linked traces. Synthetic tests cannot enter this table.','scripts/learner_cloud.py'],
 genie:['Genie MCP','Genie supplies six constrained prose summaries from SQL-backed evidence. Numeric counts remain deterministic and code validates provenance before publication. Empty real evidence and nonempty isolated synthetic SQL-to-Genie publication passed. A genuine confirmed-learner run is still unverified.','scripts/learner_genie.py · reports/genie-live-profile-proof.json'],
 about_me:['About me page','Reads and polls the active learner profile and sync status. Shows evidence, category summaries, metrics and epochs; mock preview is explicitly fictional.','web/learn/intelligence.js'],
 registry:['MLflow Prompt Registry','workspace.magneto.story_orchestrator. The tuning CLI registers and loads prompts and evaluates the model. The director can load a registry prompt when MAGNETO_PROMPT_URI is set; that variable is absent from the current app.yaml. Registry failure is explicit when enabled.','scripts/tune_story.py · databricks/magneto-director/agent/decision.py:resolve_prompt'],
 tuning:['Prompt tuning CLI','Explicit command with synthetic training/held-out fixtures. Loads registered prompts, calls the shared model, and records evaluation runs and traces in the research experiment. This does not train model weights or update learner profiles.','scripts/tune_story.py · scripts/story_tuning/ · reports/story-tuning-live.json']
};
const links=[
 ['synthetic_fixture','story','wired','Isolated Alex persona + unconfirmed test reply → Story MCP/model context'],
 ['synthetic_fixture','synthetic_table','wired','Fictional fixture → isolated SQL write and exact readback'],
 ['synthetic_table','genie','wired','Isolated synthetic SQL evidence → explicit Genie test producer'],
 ['synthetic_fixture','learner_profile','wired','Validated test profile → read-only synthetic-test endpoint'],
 ['browser','navigation_audio','wired','Route change → optional spoken navigation, local clip or browser speech'],
 ['story','story_narration','wired','Visible passage → existing narration matcher → local recorded WAV autoplay'],
 ['story_narration','eleven_tts','wired','Previously generated ElevenLabs audio; no runtime synthesis or browser key'],
 ['navigation_audio','eleven_tts','wired','Private .env → packaging CLI → nine verified ElevenLabs clips; cached local playback'],
 ['voice','scribe','optional','Browser audio → Scribe Realtime when server key and microphone permission are available'],
 ['device_status','explore','wired','Webcam track → sidebar live/off/paused state'],
 ['device_status','nano','optional','Configured SSH target → verified Jetson Nano identity'],
 ['nano','harness','planned','Verified SSH host → app runtime connection is not implemented'],
 ['voice','browser','wired','Committed speech → existing browser actions and practice grading'],
 ['voice','story','wired','Spoken response → Story Mode submit_response, teacher confirmation retained'],
 ['voice','explore','wired','Voice selection → current detected objects'],

 ['explore','vision','wired','Explore webcam → local YOLO recognition → detected objects, speech and visual Braille'],
 ['vision','harness','planned','Explore selection → physical device execution is not connected'],
 ['judged_updater','model','wired','Judged updater → hosted proposal and LLM judge'],
 ['judged_updater','research_traces','wired','Judged updater → registered MLflow judge, evaluation and UC traces'],
 ['judged_updater','learner_profile','planned','Judged profile store → live About me selection is not connected'],
 ['browser','bridge','wired','Browser snapshot → authenticated localhost bridge'],
 ['bridge','director','wired','Bridge invokes the director App'],
 ['director','model','wired','Director → foundation model → validated decision'],
 ['director','director_traces','wired','Director → MLflow tracing in Unity Catalog'],
 ['story','model','wired','Story MCP orchestrator → shared model directly'],
 ['harness','model','wired','Orin direct mode → shared model'],
 ['harness','companion','optional','Orin agent mode → companion App, as an alternative'],
 ['companion','model','optional','Companion planner → shared foundation model'],
 ['schema','references','wired','Unity Catalog contains the references volume'],
 ['schema','director_traces','wired','Unity Catalog stores director trace tables'],
 ['schema','tables','wired','Unity Catalog contains research tables'],
 ['references','processing','wired','Explicit PDFs → managed processing'],
 ['warehouse','processing','wired','SQL warehouse → managed AI functions'],
 ['processing','tables','wired','Parsed / reviewed evidence → Delta tables'],
 ['tables','search_index','wired','Eligible search documents → Delta-sync index'],
 ['embeddings','search_index','wired','Managed embeddings → AI Search index'],
 ['processing','research_traces','wired','Research operations → separate MLflow experiment'],
 ['story','reflection','wired','Teacher-confirmed story observations → local reflection'],
 ['reflection','learner_evidence','wired','Confirmed Story evidence → SQL ingestion and readback'],
 ['warehouse','learner_evidence','wired','SQL warehouse → confirmed learner evidence table'],
 ['learner_evidence','genie','wired','SQL-backed evidence → Genie prose generation'],
 ['genie','reflection','wired','Validated prose + deterministic counts → conditional profile epoch'],
 ['reflection','learner_profile','wired','Published profile → read-only profile endpoint'],
 ['learner_profile','about_me','wired','Live profile endpoint → About me polling and rendering'],
 ['tuning','registry','wired','Prompt tuning CLI → register / load prompt versions'],
 ['tuning','model','wired','Prompt evaluation → shared foundation model'],
 ['tuning','research_traces','wired','Synthetic prompt evaluations → MLflow runs and traces'],
 ['director','registry','optional','Director → Prompt Registry when MAGNETO_PROMPT_URI is enabled'],
 ['search_index','director','optional','Approved research → director model context when MAGNETO_RESEARCH_ENABLED=1; local tests passed, live activation pending'],
 ['director_traces','reflection','planned','Traces + confirmed outcomes → reflection is not connected'],
 ['reflection','companion','planned','Learner memory → planner is not connected']
];
let paths=[],packet,frameId=0,playing=false,step=0,start=0;
const animate=document.querySelector('#animate');
function element(tag,attrs,parent=svg){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);parent.append(e);return e;}
function select(id){const d=info[id];nodes.forEach((n,key)=>n.setAttribute('aria-pressed',String(key===id)));title.textContent=d[0];body.textContent=d[1];source.textContent=d[2];
 const list=document.querySelector('#detailLinks');list.replaceChildren();
 links.filter(p=>p[0]===id||p[1]===id).forEach(p=>{const li=document.createElement('li');li.textContent=p[3];list.append(li);});
}
nodes.forEach((node,id)=>node.addEventListener('click',()=>{stop();select(id);paths.forEach(p=>p.el.classList.toggle('active',p.from===id||p.to===id));document.querySelector('#flowStatus').textContent=`${info[id][0]} · connections highlighted; details below the map.`;}));
function stop(){cancelAnimationFrame(frameId);playing=false;animate.textContent='Animate flow';paths.forEach(p=>p.el.classList.remove('active'));if(packet)packet.setAttribute('visibility','hidden');}
function draw(){
 stop();svg.replaceChildren();paths=[];
 const rect=diagram.getBoundingClientRect();svg.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);
 const defs=element('defs',{});
 for(const [type,color] of [['wired','--connected'],['optional','--optional'],['planned','--line']]){
   const marker=element('marker',{id:`systemArrow-${type}`,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto'},defs);
   element('polygon',{points:'0,0 10,5 0,10',fill:`var(${color})`},marker);
 }
 links.forEach(([from,to,type,label],i)=>{
   const a=nodes.get(from).getBoundingClientRect(),b=nodes.get(to).getBoundingClientRect();
   let x1,y1,x2,y2,d;
   if(Math.abs(a.left-b.left)<10){
     x1=a.right-rect.left;y1=a.top+a.height/2-rect.top;x2=b.right-rect.left;y2=b.top+b.height/2-rect.top;
     const bend=x1+10+(i%3)*6;d=`M${x1},${y1} C${bend},${y1} ${bend},${y2} ${x2},${y2}`;
   }else{
     const right=b.left>a.left;x1=(right?a.right:a.left)-rect.left;x2=(right?b.left:b.right)-rect.left;
     y1=a.top+a.height/2-rect.top;y2=b.top+b.height/2-rect.top;
     const bend=(x1+x2)/2;d=`M${x1},${y1} C${bend},${y1} ${bend},${y2} ${x2},${y2}`;
   }
   const el=element('path',{d,class:type,'marker-end':`url(#systemArrow-${type})`});paths.push({el,from,to,type,label});
 });
 packet=element('circle',{r:5,visibility:'hidden'});
}
function tick(time){
 if(!playing)return;
 const p=paths[step];
 if(!start){start=time;p.el.classList.add('active');select(p.from);title.textContent=p.label;document.querySelector('#flowStatus').textContent=p.label;}
 const t=Math.min(1,(time-start)/1800),point=p.el.getPointAtLength(p.el.getTotalLength()*t);
 packet.style.fill=p.type==='wired'?'var(--connected)':'var(--optional)';
 packet.setAttribute('cx',point.x);packet.setAttribute('cy',point.y);packet.setAttribute('visibility',p.type==='planned'?'hidden':'visible');
 if(t===1){p.el.classList.remove('active');step++;start=0;if(step===paths.length){stop();select('reflection');return;}}
 frameId=requestAnimationFrame(tick);
}
animate.addEventListener('click',()=>{
 if(playing){stop();return;}
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){paths.forEach(p=>p.el.classList.remove('active'));const p=paths[step%paths.length];p.el.classList.add('active');select(p.from);title.textContent=p.label;document.querySelector('#flowStatus').textContent=p.label;step++;animate.textContent='Next connection';return;}
 playing=true;step=0;start=0;animate.textContent='Pause flow';frameId=requestAnimationFrame(tick);
});
new ResizeObserver(draw).observe(diagram);
const check=document.querySelector('#check'),checkStatus=document.querySelector('#checkStatus');
check.addEventListener('click',async()=>{
 check.disabled=true;checkStatus.textContent='Checking Databricks metadata access…';
 nodes.forEach(n=>{if(n.hasAttribute('data-status')){n.removeAttribute('data-status');n.querySelector('small').textContent='Unchecked';}});
 document.querySelector('#extraChecks').replaceChildren();
 try{
   const response=await fetch('/api/system-status',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(50000)});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Metadata check failed.');
   for(const [id,result] of Object.entries(data.resources)){
     const text=result.status==='reachable'?'Metadata accessible':'Unavailable / no access';
     if(nodes.has(id)){const node=nodes.get(id);node.dataset.status=result.status;node.querySelector('small').textContent=text;}
     else{const span=document.createElement('span');span.textContent=`${id==='catalog'?'Catalog workspace':'AI Search endpoint'}: ${text}`;document.querySelector('#extraChecks').append(span);}
   }
   checkStatus.textContent=`Checked ${new Date().toLocaleTimeString()}. Metadata access only; inference, table queries, trace writes and end-to-end integration were not tested.`;
 }catch(error){checkStatus.textContent=error.name==='TimeoutError'?'Check timed out. Access remains unchecked.':error.message;}
 finally{check.disabled=false;}
});
draw();
