export function opportunityFor(pageId, checkpoints = []) {
  return checkpoints.find(c=>c.page_id===pageId)?.id || null;
}
export function createLookahead(api, changed = () => {}) {
  let entry = null, generation = 0, timer = null;
  function invalidate() {generation++; clearTimeout(timer); entry = null; changed();}
  function prepare(state, target) {
    if (!target || state.phase !== 'reading') {invalidate(); return;}
    const key = JSON.stringify([state.session_id,target,state.observations,state.activities_started,state.policy,state.interaction_revision]);
    if (entry?.key === key && entry.status !== 'failed') return;
    invalidate(); const token = generation;
    entry = {key,target,status:'preparing'}; changed();
    const deadline = Date.now() + 240000;
    const fail = () => {if(token===generation){entry.status='failed';changed();}};
    const receive = result => {
      if(token!==generation)return;
      if(result.target!==target || typeof result.preparation_id!=='string') {fail();return;}
      entry.handle=result.preparation_id;
      if(result.status==='ready'){entry.status='ready';entry.preview=result.preview;changed();return;}
      if(Date.now()>deadline){fail();return;}
      timer=setTimeout(()=>api('lookahead-status',{session_id:state.session_id,preparation_id:entry.handle}).then(receive).catch(fail),1500);
    };
    api('lookahead',{session_id:state.session_id,revision:state.revision,target}).then(receive).catch(fail);
  }
  async function apply(state) {
    if(entry?.status!=='ready' || entry.target!==state.passage_id)throw Error('The upcoming exercise is not ready for this page.');
    const handle=entry.handle; invalidate();
    return api('apply-lookahead',{session_id:state.session_id,revision:state.revision,preparation_id:handle});
  }
  return {prepare,apply,invalidate,get preview(){return entry?.preview;},get target(){return entry?.target;},get status(){return entry?.status||'idle';}};
}

export function plannedQuestion({state, passage, windowTargets, status, preview, target}) {
  if(state?.passage_id===passage && ['proposed','awaiting_tactile','ready','waiting_response','awaiting_confirmation'].includes(state?.phase)
      && ['introduce','identify','match'].includes(state?.proposal?.activity))return passage;
  return status==='ready' && preview?.tool==='propose_activity' && windowTargets.includes(target)?target:null;
}

// Only accepted teacher outcomes count; exposure and unconfirmed proposals do not.
export function questionStops(planned, observations = [], checkpoints = []) {
  const stops = new Map(), known = new Set(checkpoints.map(c=>c.id));
  const outcomes = {independent:'solved',with_help:'assisted',try_later:'skipped'};
  for (const row of observations) {
    if (!row || !known.has(row.passage_id) || row.source!=='teacher' ||
        !['introduce','identify','match'].includes(row.activity) ||
        !Object.hasOwn(outcomes,row.outcome) || !Number.isFinite(Date.parse(row.observed_at))) continue;
    const previous=stops.get(row.passage_id);
    if (!previous || Date.parse(row.observed_at)>=Date.parse(previous.observedAt))
      stops.set(row.passage_id,{id:row.passage_id,status:outcomes[row.outcome],observedAt:row.observed_at,planned:false});
  }
  if (known.has(planned)) stops.set(planned,{...(stops.get(planned)||{id:planned,status:'planned'}),planned:true});
  return [...stops.values()];
}
