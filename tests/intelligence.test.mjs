import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {LearningOutbox, INTELLIGENCE_KEY, ATTEMPTS_KEY} from '../web/learn/learning-outbox.js';
const storage = () => { const m=new Map();return {m,getItem:k=>m.get(k),setItem:(k,v)=>m.set(k,v)}; };
const ok = value => ({ok:true,json:async()=>value});
const ack = payload => ({schema_version:'3.0',profile_id:payload.profile_id,session_id:payload.session_id,attempt_ids:payload.attempts.map(a=>a.attempt_id)});
function setup(fetcher, store=storage()) {
 const box=new LearningOutbox({storage:store,uuid:randomUUID,fetcher});
 box.profileId();return box;
}
function add(box, session_id=randomUUID(), extra={}) {
 return box.enqueueAttempt({profile_id:box.profile.profile_id,session_id,activity_ref:'peter-rabbit/rabbit/identify-r@1',result:'correct',support:'none',...extra});
}
function enable(box) { box.profile.uploads_enabled=true;box.profileReady=true; }
test('uploads require explicit opt-in; profile grant is not inferred',async()=>{
 let calls=0;const box=setup(async()=>{calls++;});add(box);await box.flush();assert.equal(calls,0);
 await assert.rejects(box.createProfile({profile_id:box.profile.profile_id}),/Invalid/);
});
test('failed upload survives reload and retry with the same ID',async()=>{
 const store=storage();const box=setup(async()=>({ok:false,json:async()=>({error:'offline'})}),store);
 enable(box);box.saveProfile();const attempt=add(box);await assert.rejects(box.flush(),/offline/);
 const restored=setup(async(_,o)=>ok(ack(JSON.parse(o.body))),store);enable(restored);
 assert.equal(restored.attempts[0].attempt.attempt_id,attempt.attempt_id);
 await restored.flush();assert.equal(restored.attempts.length,0);
});
test('batches stay within 50 and one session, with no repeated envelope fields in attempts',async()=>{
 const sizes=[];const box=setup(async(_,o)=>{const p=JSON.parse(o.body);sizes.push(p.attempts.length);
 assert.ok(p.attempts.every(a=>!('profile_id' in a)&&!('schema_version' in a)&&!('client_sequence' in a)));return ok(ack(p));});
 enable(box);const s=randomUUID();for(let i=0;i<51;i++)add(box,s);add(box);
 await box.flush();assert.deepEqual(sizes,[50,1,1]);assert.equal(box.queuedCount,0);
});
test('overlapping flushes share one request and preserve observations added in flight',async()=>{
 let finish,calls=0;const box=setup(async(_,o)=>{calls++;const p=JSON.parse(o.body);return new Promise(resolve=>{finish=()=>resolve(ok(ack(p)));});});
 enable(box);add(box);const first=box.flush();const second=box.flush();assert.equal(first,second);
 const later=add(box);finish();await first;assert.equal(calls,1);assert.equal(box.attempts[0].attempt.attempt_id,later.attempt_id);
});
for(const kind of ['wrong-session','unknown-id','duplicate-id','empty']) test('rejects '+kind+' acknowledgement without losing records',async()=>{
 const box=setup(async(_,o)=>{const p=JSON.parse(o.body),r=ack(p);
 if(kind==='wrong-session')r.session_id=randomUUID();if(kind==='unknown-id')r.attempt_ids=[randomUUID()];
 if(kind==='duplicate-id')r.attempt_ids.push(r.attempt_ids[0]);if(kind==='empty')r.attempt_ids=[];
 return ok(r);});enable(box);add(box);await assert.rejects(box.flush());assert.equal(box.attempts.length,1);
});
test('partial acknowledgement retains the remaining records',async()=>{
 const box=setup(async(_,o)=>{const p=JSON.parse(o.body);return ok({...ack(p),attempt_ids:[p.attempts[0].attempt_id]});});
 enable(box);const s=randomUUID();add(box,s);const second=add(box,s);await box.flush();assert.equal(box.attempts[0].attempt.attempt_id,second.attempt_id);
});
test('legacy queues are drained only for the explicitly selected profile',async()=>{
 const store=storage(),box=setup(async(path,o)=>{assert.equal(path,'/api/learning/events');const p=JSON.parse(o.body);assert.ok(p.events.every(e=>e.profile_id===box.profile.profile_id));return ok({event_ids:p.events.map(e=>e.event_id)});},store);
 enable(box);const other=randomUUID();box.events=[{event_id:randomUUID(),profile_id:box.profile.profile_id},{event_id:randomUUID(),profile_id:other}];box.save();
 await box.flush();assert.equal(box.events.length,1);assert.equal(box.events[0].profile_id,other);
 assert.equal(JSON.parse(store.getItem(INTELLIGENCE_KEY)).length,1);
});
test('corrupt saved queue is preserved',()=>{
 const store=storage();store.setItem(ATTEMPTS_KEY,'broken');const box=setup(null,store);
 assert.throws(()=>add(box),/Repair/);box.save();assert.equal(store.getItem(ATTEMPTS_KEY),'broken');
});
test('same attempt cannot be silently overwritten or double enqueued',()=>{
 const box=setup(null),s=randomUUID(),first=add(box,s);
 add(box,s,{attempt_id:first.attempt_id});assert.equal(box.attempts.length,1);
 assert.throws(()=>add(box,s,{attempt_id:first.attempt_id,result:'incorrect'}),/conflict/);
});
test('unconfirmed observation cannot claim correctness',()=>{
 const box=setup(null);assert.throws(()=>add(box,randomUUID(),{assessment:'unconfirmed'}),/Invalid/);
});
test('disabling stops later batches even when one upload is already in flight',async()=>{
 let finish,calls=0;const box=setup(async(path,o)=>{
 const p=JSON.parse(o.body);if(path.endsWith('/profile'))return ok({profile_id:p.profile_id,consent:p.consent});
 calls++;return new Promise(resolve=>{finish=()=>resolve(ok(ack(p)));});});
 enable(box);const s=randomUUID();for(let i=0;i<51;i++)add(box,s);
 const pending=box.flush();await box.setUploadsEnabled(false);finish();await pending;
 assert.equal(calls,1);assert.equal(box.attempts.length,1);
});
test('failed consent revocation is retryable while uploads stay paused',async()=>{
 let fail=true;const box=setup(async(_,o)=>{if(fail)throw Error('offline');const p=JSON.parse(o.body);return ok({profile_id:p.profile_id,consent:p.consent});});
 enable(box);await assert.rejects(box.setUploadsEnabled(false));assert.equal(box.uploadsEnabled,false);
 fail=false;await box.flush();assert.equal(box.profile.consent_pending,false);
});
