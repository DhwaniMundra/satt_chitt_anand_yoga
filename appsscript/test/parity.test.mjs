// A regression snapshot of the API: 101 requests (parity/scenario.json) at a frozen moment, and the answers recorded for
// them (parity/recorded.json). Every status and every JSON body must match. Login tokens and the two random values a
// step names (a reset password, a new group code) are left out; validation errors are compared by (type, location).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { loadBackend, ROOT } from './fakes.mjs';
import { attend, classStarted, setSetting } from './helpers.mjs';

const HERE = join(ROOT, 'test', 'parity');
const steps = JSON.parse(readFileSync(join(HERE, 'scenario.json'), 'utf8'));
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
  const b = loadBackend();
  b.state.frozenMs = Date.parse('2026-11-18T03:00:00Z'); // 8:30 in India, during the day's class
  b.context.setup();
  setSetting(b, 'teacher_code', 'TEACH123');
  setSetting(b, 'group_code', 'GRP234');
  const tokens = {};
  let i = 0;
  for (const step of steps) {
    if (step.do === 'class_started') {
      classStarted(b, step.minutes);
      continue;
    }
    if (step.do === 'attend') {
      attend(b, step.user, step.class, step.days, step.before, step.after);
      continue;
    }
    const [method, path, query = {}, body = null, who = null] = step.call;
    const r = b.call(method, path, { query, body, token: who ? tokens[who] || who : '' });
    if (step.save && r.status === 200) tokens[step.save] = r.body.token;
    const skip = step.normalize || [];
    assert.deepEqual(normalize(r, skip), normalize(recorded[i], skip), '#' + i + ' ' + method + ' ' + path);
    i++;
  }
  assert.equal(i, recorded.length);
});
