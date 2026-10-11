import {LearningOutbox} from './learning-outbox.js';
export function observationAttempt(row,profile_id,session_id){
  if(!['independent','with_help'].includes(row.outcome))return null;
  return {attempt_id:row.id,profile_id,session_id,activity_ref:`peter-rabbit/${row.passage_id}/${row.activity}-${row.target}@1`,result:'correct',support:row.outcome==='independent'?'none':row.hint_used?'hint':'unknown',assessment:'teacher_confirmed'};
}
const outboxes=new WeakMap();
const KEY='magneto-story-practice-v1';
export class StoryMemory {
  constructor(storage=globalThis.localStorage){
    this.storage=storage;this.error='';this.rows=[];
    const profile=new LearningOutbox({storage});this.profileId=profile.profileId();
    const previous=outboxes.get(storage);
    this.outbox=previous?.profile?.profile_id===this.profileId?previous:profile;
    this.outbox.profile=profile.profile;outboxes.set(storage,this.outbox);
    this.key=KEY+':'+this.profileId;
    try{const rows=JSON.parse(storage.getItem(this.key)||'[]');if(!Array.isArray(rows))throw Error();this.rows=rows.slice(-40);}
    catch{this.error='Saved story practice could not be read. New observations remain in this session.';this.broken=true;}
  }
  remember(observations,sessionId){
    if(this.broken)return;
    const rows=new Map(this.rows.map(r=>[r.id,r]));
    for(const row of observations){
      if(!rows.has(row.id) && sessionId){
        const outbox=this.outbox;outbox.clock=()=>new Date(row.observed_at).toISOString();
        try{outbox.profile=JSON.parse(this.storage.getItem('magneto-learning-profile-v1')||'null');}catch{outbox.profile=null;}
        const attempt=observationAttempt(row,this.profileId,sessionId);
        if(attempt && outbox.profile?.profile_id===this.profileId && outbox.uploadsEnabled){
          try{outbox.enqueueAttempt(attempt);void outbox.flush().catch(()=>{this.error='Practice saved locally; learning upload is pending.';});}
          catch{this.error='Practice saved locally; learning upload could not be queued.';}
        }
      }
      rows.set(row.id,row);
    }
    this.rows=[...rows.values()].sort((a,b)=>a.observed_at.localeCompare(b.observed_at)).slice(-40);
    try{this.storage.setItem(this.key,JSON.stringify(this.rows));}
    catch{this.error='Practice is available this session, but browser storage could not save it.';}
  }
}
