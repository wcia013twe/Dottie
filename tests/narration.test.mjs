import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matchNarration} from '../web/learn/narration.js';
const passage={match_text:'four little Rabbits',audio:`rabbit-${'a'.repeat(64)}.wav`,duration_seconds:2};
const manifest={schema_version:'1.0',book_id:'rabbit',passages:[passage]};
test('matches normalized passage text and correct book',()=>{
 assert.equal(matchNarration(manifest,'rabbit','Four   little rabbits'),passage);
 assert.equal(matchNarration(manifest,'other','Four little rabbits'),null);
 assert.equal(matchNarration(manifest,'rabbit','unrelated page'),null);
});
test('rejects ambiguous passage and remote or traversing audio paths',()=>{
 assert.equal(matchNarration({...manifest,passages:[passage,passage]},'rabbit','four little rabbits'),null);
 for(const audio of ['../secret.wav','https://example.com/a.wav','bad.wav'])
  assert.equal(matchNarration({...manifest,passages:[{...passage,audio}]},'rabbit','four little rabbits'),null);
});

test('malformed passage entries are ignored',()=>{assert.equal(matchNarration({...manifest,passages:[null,{}]},'rabbit','four little rabbits'),null);});
