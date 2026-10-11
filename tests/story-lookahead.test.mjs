import test from 'node:test';
import assert from 'node:assert/strict';
import {createLookahead,opportunityFor,plannedQuestion} from '../web/learn/story-lookahead.js';
import {feedbackFor} from '../web/learn/interaction-player.js';
const state={session_id:'s',revision:1,phase:'reading',passage_id:null,observations:[],activities_started:0,policy:{}};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('same candidate survives page revisions, applies only on matching page',async()=>{
 const calls=[];const cache=createLookahead(async(path,body)=>{calls.push(path);return {status:'ready',target:'rabbit',preparation_id:'h'};});
 cache.prepare(state,'rabbit');await tick();
 cache.prepare({...state,revision:2},'rabbit');assert.equal(calls.length,1);
 await assert.rejects(cache.apply(state));
 await cache.apply({...state,revision:2,passage_id:'rabbit'});assert.deepEqual(calls,['lookahead','apply-lookahead']);
 assert.equal(cache.status,'idle');
});
test('late results cannot revive invalidated lookahead',async()=>{
 let finish;const cache=createLookahead(()=>new Promise(r=>finish=r));
 cache.prepare(state,'rabbit');cache.invalidate();finish({status:'ready',target:'rabbit',preparation_id:'h'});await tick();assert.equal(cache.status,'idle');
});
test('new evidence starts new preparation; no opportunity clears it',async()=>{
 let count=0;const cache=createLookahead(async()=>{count++;return {status:'ready',target:'rabbit',preparation_id:'h'};});
 cache.prepare(state,'rabbit');await tick();cache.prepare({...state,activities_started:1},'rabbit');await tick();assert.equal(count,2);cache.prepare(state,null);assert.equal(cache.status,'idle');
});
test('feedback never grades a transcript or treats try-later as incorrect',()=>{
 assert.equal(feedbackFor('submit_response','independent'),null);
 assert.equal(feedbackFor('record_observation','try_later'),'skip');
 assert.equal(feedbackFor('record_observation','independent'),'success-independent');
 assert.equal(feedbackFor('record_observation','with_help'),'success-assisted');
 assert.equal(feedbackFor('give_hint'),null);
 assert.equal(opportunityFor('page-03',[{id:'rabbit',page_id:'page-03'}]),'rabbit');
 assert.equal(opportunityFor('four little Rabbits',[{id:'rabbit',page_id:'page-03'}]),null);
});

test('question markers track only ready or active questions in the current window',()=>{
 const candidate={state:null,passage:null,windowTargets:['rabbit'],status:'ready',preview:{tool:'propose_activity'},target:'rabbit'};
 assert.equal(plannedQuestion(candidate),'rabbit');
 for(const change of [{status:'preparing'},{status:'failed'},{preview:{tool:'recommend_continue'}},{preview:{tool:'propose_word_emphasis'}},{windowTargets:[]}])assert.equal(plannedQuestion({...candidate,...change}),null);
 const active={...candidate,status:'idle',passage:'rabbit',state:{passage_id:'rabbit',phase:'waiting_response',proposal:{activity:'identify'}}};
 assert.equal(plannedQuestion(active),'rabbit');
 assert.equal(plannedQuestion({...active,state:{...active.state,phase:'complete'}}),null);
 assert.equal(plannedQuestion({...active,passage:'gate'}),null);
});

test('recorded question results survive plan changes and keep status on a planned revisit',async()=>{
 const {questionStops}=await import('../web/learn/story-lookahead.js');
 const checkpoints=[{id:'rabbit'},{id:'gate'},{id:'lettuce'}];
 const row={passage_id:'rabbit',source:'teacher',activity:'identify',outcome:'independent',observed_at:'2026-10-11T12:00:00Z'};
 let stops=questionStops('gate',[row],checkpoints);
 assert.deepEqual(stops.map(s=>[s.id,s.status]),[['rabbit','solved'],['gate','planned']]);
 assert.equal(questionStops(null,[row],checkpoints)[0].status,'solved');
 stops=questionStops('rabbit',[row],checkpoints);
 assert.equal(stops[0].status,'solved');assert.equal(stops[0].planned,true);
 const assisted={...row,outcome:'with_help',observed_at:'2026-10-11T13:00:00Z'};
 assert.equal(questionStops(null,[assisted,row],checkpoints)[0].status,'assisted');
 assert.equal(questionStops(null,[{...row,outcome:'try_later'}],checkpoints)[0].status,'skipped');
 for(const change of [{activity:'emphasize'},{source:'agent'},{outcome:'unknown'},{passage_id:'unknown'},{observed_at:'invalid'}])
   assert.deepEqual(questionStops(null,[{...row,...change}],checkpoints),[]);
});
