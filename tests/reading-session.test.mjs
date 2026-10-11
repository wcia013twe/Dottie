import test from 'node:test';
import assert from 'node:assert/strict';
import { ensureReadingSession, finishReadingSession, restartReadingSession, readingLabel } from '../web/learn/reading-session.js';
test('continue preserves identity, completion and bookmark across storage reload', () => {
  const book={total:3,current:1,position:1,page:4};
  const id=ensureReadingSession(book);
  const restored=JSON.parse(JSON.stringify(book));
  assert.equal(ensureReadingSession(restored),id);
  assert.equal(restored.page,4);
  finishReadingSession(restored);
  const completedAt=restored.completedAt;
  finishReadingSession(restored);
  assert.equal(restored.completedAt,completedAt);
  restored.page=2;
  assert.equal(readingLabel(restored),'Completed · Review book');
  assert.equal(restored.finished,true);
});
test('restart archives completion and creates a fresh identity at reading start', () => {
  const book={total:3,current:3,position:2,page:4,coachSessionId:'old-coach'};
  finishReadingSession(book);
  const oldId=book.readingSessionId;
  restartReadingSession(book,1);
  assert.notEqual(book.readingSessionId,oldId);
  assert.equal(book.position,1);
  assert.equal(book.pageFraction,0);
  assert.equal(book.finished,false);
  assert.equal(book.coachSessionId,null);
  assert.equal(book.readingSessions[0].id,oldId);
  assert.equal(book.readingSessions[0].finished,true);
  assert.equal(book.readingSessions[0].coachSessionId,'old-coach');
  assert.equal(readingLabel(book),'Continue reading');
});

import { restoreCoachSession } from '../web/learn/reading-session.js';
test('coach continuation retrieves the same session and pending activity', async () => {
  const calls=[];
  const api=async (path,body)=>{calls.push([path,body]);return {session_id:'same',phase:'awaiting_confirmation',response:{text:'unconfirmed'}};};
  const state=await restoreCoachSession({sessionId:'same',api,history:[]});
  assert.equal(state.phase,'awaiting_confirmation');
  assert.equal(calls.length,1);
  assert.equal(calls[0][1].session_id,'same');
  assert.equal(calls[0][1].name,'get_story_context');
});
test('expired server sessions are recreated with history; outages do not fork', async () => {
  const history=[{id:'confirmed'}], calls=[];
  const api=async (path,body)=>{calls.push([path,body]);if(path==='action')throw Error('Session expired. Reopen the teacher panel.');return {session_id:'new'};};
  assert.equal((await restoreCoachSession({sessionId:'old',api,history})).session_id,'new');
  assert.deepEqual(calls[1],['session',{history}]);
  let attempts=0;
  await assert.rejects(restoreCoachSession({sessionId:'old',history,api:async()=>{attempts++;throw Error('Network unavailable');}}),/Network unavailable/);
  assert.equal(attempts,1);
});
