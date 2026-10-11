import test from 'node:test';
import assert from 'node:assert/strict';
import { completionRecap, demoCompletionRecap } from '../web/learn/story-completion.js';
const event = (id, extra = {}) => ({id, source:'teacher', activity:'identify', target:'r', outcome:'independent', ...extra});

test('achievements use confirmed practice and keep the shorter list to three', () => {
  const recap = completionRecap([event('one'), event('two', {target:'l', outcome:'with_help', hint_used:true})]);
  assert.deepEqual(recap.achievements, ['Finished the story.', 'Practised R, L.', 'Answered on your own.']);
  assert.equal(recap.moments[1].text, 'L: practised with a hint.');
  assert.deepEqual(recap.moments.map(m => m.eventId), ['one', 'two']);
});

test('unconfirmed transcripts, duplicates and missing evidence create no extra achievement', () => {
  assert.deepEqual(completionRecap().achievements, ['Finished the story.']);
  const recap = completionRecap([event('one'), event('one'), event('heard', {source:'unconfirmed transcript'}), null]);
  assert.equal(recap.moments.length, 1);
});

test('an introduction is exploration, not an independent recognition achievement', () => {
  const recap = completionRecap([event('one', {activity:'introduce'})]);
  assert.deepEqual(recap.achievements, ['Finished the story.', 'Explored R.']);
  assert.equal(recap.moments[0].text, 'Explored R together.');
});

test('assistance and deferred outcomes never become independent success', () => {
  const recap = completionRecap([event('one', {outcome:'with_help'}), event('later', {target:'d', outcome:'try_later'})]);
  assert.deepEqual(recap.achievements, ['Finished the story.', 'Practised R.', 'Practised with help.']);
  assert.equal(recap.moments[1].text, 'D: left for another time.');
  assert.deepEqual(completionRecap([event('later', {outcome:'try_later'})]).achievements, ['Finished the story.']);
});

test('demo correctness does not establish independent performance or mastery', () => {
  const recap = demoCompletionRecap([{event_id:'one', target_letter:'P', response:'correct'}]);
  assert.deepEqual(recap.achievements, ['Finished the story.', 'Practised P.']);
  assert.equal(recap.moments[0].text, 'P: a correct response.');
});
