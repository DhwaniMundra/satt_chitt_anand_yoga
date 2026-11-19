// The snapshot's scenario: the requests of scenario.json, made at a frozen moment on a fresh backend. Each answer comes
// with the keys its step leaves out of the comparison (random values such as a reset password).
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { loadBackend, ROOT } from '../fakes.mjs';
import { attend, classStarted, setSetting } from '../helpers.mjs';

export const HERE = join(ROOT, 'test', 'snapshot');

/** [{call: "METHOD /path", answer: {status, body}, skip: [keys]}], in order. */
export function answers() {
  const steps = JSON.parse(readFileSync(join(HERE, 'scenario.json'), 'utf8'));
  const b = loadBackend({ now: Date.parse('2026-11-18T03:00:00Z') }); // 8:30 in India, during the day's class
  b.context.setup();
  setSetting(b, 'teacher_code', 'TEACH123');
  setSetting(b, 'group_code', 'GRP234');
  const tokens = {};
  const out = [];
  for (const step of steps) {
    if (step.do === 'class_started') classStarted(b, step.minutes);
    else if (step.do === 'attend') attend(b, step.user, step.class, step.days, step.before, step.after);
    else {
      const [method, path, query = {}, body = null, who = null] = step.call;
      const answer = b.call(method, path, { query, body, token: who ? tokens[who] || who : '' });
      if (step.save && answer.status === 200) tokens[step.save] = answer.body.token;
      out.push({ call: method + ' ' + path, answer: answer, skip: step.normalize || [] });
    }
  }
  return out;
}
