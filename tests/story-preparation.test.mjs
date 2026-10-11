import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createPreparation} from '../web/learn/story-preparation.js';
const state={session_id:'session',revision:1};
const ready={status:'ready',revision:1,preparation_id:'prepared'};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
test('preparation is deduplicated and only explicit apply executes',async()=>{
  const calls=[],pending=deferred();
  const cache=createPreparation(async(path,body)=>{calls.push({path,body});return path==='prepare'?pending.promise:{state:{revision:2}};});
  const first=cache.prepare(state);assert.equal(cache.prepare(state),first);
  assert.equal(cache.status,'preparing');assert.deepEqual(calls.map(c=>c.path),['prepare']);
  pending.resolve(ready);await first;assert.equal(cache.status,'ready');
  const result=await cache.apply(state);assert.equal(result.state.revision,2);
  assert.deepEqual(calls.map(c=>c.path),['prepare','apply-prepared']);
  assert.equal(calls[1].body.preparation_id,'prepared');assert.equal(cache.status,'idle');
});
test('navigation while preparing discards late results and never applies them',async()=>{
  const pending=deferred(),calls=[];
  const cache=createPreparation(async path=>{calls.push(path);return pending.promise;});
  const applying=cache.apply(state);cache.invalidate();pending.resolve(ready);
  await assert.rejects(applying,/context changed/);assert.deepEqual(calls,['prepare']);
  assert.equal(cache.status,'idle');
});
test('failed preparation can be retried without an automatic fallback action',async()=>{
  let count=0;const cache=createPreparation(async()=>{if(!count++)throw Error('unavailable');return ready;});
  await assert.rejects(cache.prepare(state));assert.equal(cache.status,'failed');
  await cache.prepare(state);assert.equal(count,2);assert.equal(cache.status,'ready');
});
test('late old failure does not clear a newer ready preparation',async()=>{
  const pending=deferred();const cache=createPreparation(async(path,body)=>body.revision===1?pending.promise:{...ready,revision:2});
  const old=cache.prepare(state);cache.invalidate();await cache.prepare({...state,revision:2});
  pending.reject(Error('old failure'));await assert.rejects(old);assert.equal(cache.status,'ready');
});
test('wrong revision from server never becomes ready',async()=>{
  const cache=createPreparation(async()=>({...ready,revision:9}));
  await assert.rejects(cache.prepare(state),/Invalid prepared/);assert.equal(cache.status,'failed');
});
