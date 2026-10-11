import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {DecisionSession, CONNECTED_KEY} from '../web/learn/decision-session.js';
import {PROFILE_KEY} from '../web/learn/learning-outbox.js';
function storage() { const m = new Map([['magneto-stories-v1','keep books'],['magneto-learning-v1','keep progress'],['magneto-caterpillar-demo-v1','keep old demo']]); return {m,getItem:k=>m.get(k),setItem:(k,v)=>m.set(k,v)}; }
function result(req, action='continue') { return {request_id:req.request_id,session_id:req.session_id,model:'test-model',elapsed_ms:10,decision:{action,passage_id:req.passage_id,target_letter:action==='teach'?'P':null,prompt:action==='teach'?'Feel this letter.':null,reason:'Test transport response.',based_on_event_id:req.events.at(-1)?.event_id??null}}; }
const response = r => ({ok:true,json:async()=>r});
function session(fetcher, options={}) { return new DecisionSession({storage:storage(),fetcher,uuid:randomUUID,timeoutMs:30,...options}); }

for (const answer of ['correct','incorrect','help']) test(`saves ${answer} before requesting plum; obeys model action`,async()=>{
 const seen=[];const store=storage();
 const s=session(async(_,options)=>{const req=JSON.parse(options.body); seen.push(req);
 if(req.passage_id==='wednesday_plum') assert.equal(JSON.parse(store.getItem(CONNECTED_KEY)).events[0].response,answer);
 // All plum responses deliberately continue: transport must not decide based on answer.
 return response(result(req,req.passage_id==='tuesday_pear'?'teach':'continue'));},{storage:store});
 await s.request();s.advance();await s.request();s.record(answer);await s.request();
 assert.equal(seen.at(-1).events[0].response,answer);assert.equal(s.result.decision.action,'continue');
 const restored=session(null,{storage:store}); assert.equal(restored.state.step,2);assert.equal(restored.state.events.length,1);
 assert.equal(store.getItem('magneto-stories-v1'),'keep books');assert.equal(store.getItem('magneto-learning-v1'),'keep progress');assert.equal(store.getItem('magneto-caterpillar-demo-v1'),'keep old demo');
});
test('one pending request and cancellation rejects late response',async()=>{
 let finish,calls=0;
 const s=session(async(_,o)=>{calls++;const req=JSON.parse(o.body);return new Promise(resolve=>{finish=()=>resolve(response(result(req)));});});
 const first=s.request();await s.request();assert.equal(calls,1);s.cancel();finish();await first;
 assert.equal(s.result,undefined);assert.match(s.error,/cancelled/);
});
test('restart rejects old response and creates a new session',async()=>{
 let finish;const s=session(async(_,o)=>{const req=JSON.parse(o.body);return new Promise(resolve=>{finish=()=>resolve(response(result(req)));});});
 const id=s.state.session_id;const first=s.request();s.restart();finish();await first;
 assert.notEqual(s.state.session_id,id);assert.equal(s.result,undefined);assert.equal(s.state.events.length,0);
});
test('timeout has explicit error, no decision; skip is separate',async()=>{
 const s=session(()=>new Promise(()=>{}),{timeoutMs:5});await s.request();
 assert.match(s.error,/15 seconds/);assert.equal(s.result,undefined);assert.equal(s.pending,null);
 s.skip();assert.equal(s.skipped,true);assert.equal(s.result,undefined);s.advance();assert.equal(s.state.step,1);
});
test('malformed result can be retried with a fresh request ID',async()=>{
 const ids=[];const s=session(async(_,o)=>{const req=JSON.parse(o.body);ids.push(req.request_id);return response(ids.length===1?{}:result(req));});
 await s.request();assert.match(s.error,/invalid/);assert.equal(s.result,undefined);
 await s.request();assert.equal(s.result.decision.action,'continue');assert.notEqual(ids[0],ids[1]);
});
test('storage failure keeps working in memory',async()=>{
 const s=session(async(_,o)=>response(result(JSON.parse(o.body))),{storage:{getItem:()=>null,setItem:()=>{throw Error('quota');}}});
 await s.request();assert.equal(s.storageOK,false);assert.equal(s.result.decision.action,'continue');
});

test('restart retains profile while replacing session identity', () => {
 const store=storage(); const s=session(null,{storage:store});
 const profile=s.state.profile_id, previous=s.state.session_id;
 s.restart(); assert.equal(s.state.profile_id,profile); assert.notEqual(s.state.session_id,previous);
 assert.equal(session(null,{storage:store}).state.profile_id,profile);
});
test('pre-profile saved demo progress survives migration', () => {
 const store=storage();const old=session(null,{storage:store});old.state.step=1;
 delete old.state.profile_id;store.setItem(CONNECTED_KEY,JSON.stringify(old.state));store.m.delete(PROFILE_KEY);
 const restored=session(null,{storage:store});assert.equal(restored.state.step,1);
 assert.equal(restored.state.session_id,old.state.session_id);assert.ok(restored.state.profile_id);
});
test('support accompanies a confirmed response without altering v1 decision events', async () => {
 const store=storage();const s=session(async(_,o)=>response(result(JSON.parse(o.body),'teach')),{storage:store});
 s.outbox.profile.uploads_enabled=true;s.outbox.flush=async()=>{};
 s.state.step=1;await s.request();s.record('correct','hint');
 const attempt=s.outbox.attempts[0].attempt;
 assert.equal(attempt.support,'hint');assert.equal(attempt.result,'correct');assert.equal(attempt.assessment,'teacher_confirmed');
 assert.equal(attempt.attempt_id,s.state.events[0].event_id);
 assert.deepEqual(Object.keys(s.state.events[0]).sort(),['event_id','passage_id','response','target_letter']);
});
