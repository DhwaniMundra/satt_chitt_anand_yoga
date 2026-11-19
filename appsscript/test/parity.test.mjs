// A regression snapshot of the API: 101 requests (parity/scenario.json) at a frozen moment, and the answers recorded for
// them (parity/recorded.json). Every status and every JSON body must match. Login tokens and the two random values a
// step names (a reset password, a new group code) are left out; validation errors are compared by (type, location).
// A deliberate change to the answers is re-recorded with parity/record.mjs.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { answers, HERE } from './parity/run.mjs';

const recorded = JSON.parse(readFileSync(join(HERE, 'recorded.json'), 'utf8'));

function normalize(value, skip) {
  if (Array.isArray(value)) return value.map((v) => normalize(v, skip));
  if (value && typeof value === 'object') {
    const out = {};
    for (const [key, v] of Object.entries(value)) {
      if (key === 'token' || skip.includes(key)) out[key] = '<varies>';
      else if (key === 'detail' && Array.isArray(v)) out[key] = v.map((e) => e.type + ' ' + e.loc.join('.')).sort();
      else out[key] = normalize(v, skip);
    }
    return out;
  }
  return value;
}

test('every answer matches the recorded one', () => {
  const now = answers();
  now.forEach(({ call, answer, skip }, i) => {
    assert.deepEqual(normalize(answer, skip), normalize(recorded[i], skip), '#' + i + ' ' + call);
  });
  assert.equal(now.length, recorded.length);
});
