import test from 'node:test';
import assert from 'node:assert/strict';
import {StoryMemory,observationAttempt} from '../web/learn/story-memory.js';
import {PROFILE_KEY} from '../web/learn/learning-outbox.js';
const storage=()=>{const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v)};};
test('confirmed records survive reload and stay isolated by profile',()=>{
 const s=storage(),a=new StoryMemory(s);const row={id:'one',observed_at:'2026-01-01T00:00:00Z'};
 a.remember([row,row]);assert.equal(new StoryMemory(s).rows.length,1);
 s.setItem(PROFILE_KEY,JSON.stringify({profile_id:'00000000-0000-4000-8000-000000000002',uploads_enabled:false}));
 assert.equal(new StoryMemory(s).rows.length,0);
});
test('storage failure stays in memory and reports it',()=>{
 const s=storage(),a=new StoryMemory(s);s.setItem=()=>{throw Error('full');};
 a.remember([{id:'one',observed_at:'2026-01-01'}]);assert.equal(a.rows.length,1);assert.ok(a.error);
});

test('telemetry mapping preserves uncertainty and excludes skips',()=>{
 const row={id:'id',passage_id:'gate',activity:'match',target:'g',outcome:'with_help',hint_used:false};
 assert.equal(observationAttempt(row,'p','s').support,'unknown');
 assert.equal(observationAttempt({...row,hint_used:true},'p','s').support,'hint');
 assert.equal(observationAttempt({...row,outcome:'independent'},'p','s').support,'none');
 assert.equal(observationAttempt({...row,outcome:'try_later'},'p','s'),null);
 assert.equal(observationAttempt(row,'p','s').activity_ref,'peter-rabbit/gate/match-g@1');
});
test('opted-in telemetry retains observation identity and time',async()=>{
 const s=storage(),memory=new StoryMemory(s);
 s.setItem(PROFILE_KEY,JSON.stringify({profile_id:memory.profileId,uploads_enabled:true}));
 memory.outbox.profileReady=true;
 let sent;
 memory.outbox.fetcher=async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({schema_version:'3.0',profile_id:sent.profile_id,session_id:sent.session_id,attempt_ids:sent.attempts.map(a=>a.attempt_id)})};};
 const id='00000000-0000-4000-8000-000000000001';
 memory.remember([{id,observed_at:'2026-01-01T12:00:00+00:00',passage_id:'gate',target:'g',activity:'match',outcome:'with_help',hint_used:false}], '00000000-0000-4000-8000-000000000003');
 await memory.outbox.pending;
 assert.equal(sent.attempts[0].attempt_id,id);
 assert.equal(sent.attempts[0].observed_at,'2026-01-01T12:00:00.000Z');
 assert.equal(sent.attempts[0].support,'unknown');
 assert.equal(memory.outbox.attempts.length,0);
});
