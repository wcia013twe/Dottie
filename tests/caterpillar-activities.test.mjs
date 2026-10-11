import {test} from 'node:test';
import assert from 'node:assert/strict';
import {caterpillarActivities,selectedCaterpillarActivities} from '../web/learn/caterpillar-activities.js';
test('ten unique opportunities preserve the three-stop default',()=>{
 assert.equal(caterpillarActivities.length,10);assert.equal(new Set(caterpillarActivities.map(a=>a.id)).size,10);
 assert.deepEqual(selectedCaterpillarActivities().map(a=>a.page),[9,11,25]);
 assert.ok(caterpillarActivities.every(a=>a.page>=1&&a.page<=26&&a.prompt));
});
test('teacher plan ignores unknown IDs and bounds active stops',()=>{
 assert.equal(selectedCaterpillarActivities([]).length,0);
 assert.equal(selectedCaterpillarActivities(['unknown']).length,0);
 assert.equal(selectedCaterpillarActivities(caterpillarActivities.map(a=>a.id)).length,4);
});
