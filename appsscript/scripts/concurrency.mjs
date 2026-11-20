// A live check of sign-ups sent at once, against the deployed web app: ids, one account per number, and the answer
// to a sign-up sent again.
//
//   SCA_WEBAPP_URL=<the web app URL> SCA_GROUP_CODE=<the group code> node appsscript/scripts/concurrency.mjs [N]
//
// It writes to the Sheet: N students (6 unless given, at most 30) named "TEST concurrency 01" and on, with numbers that
// cannot be real mobiles (+91 10000 7xxxx), pending, each with a sign-in. Remove them afterwards from the Sheet's menu:
// Satt Chitt Anand → Remove test people…
//
// What it checks:
// 1. N sign-ups sent at once, and with them a second copy of the first one's number (a double tap, with its own
//    request id): every answer comes back, the N accounts have N different ids, and the number sent twice has one
//    account (one copy 200, the other 409 phone_taken).
// 2. A later sign-up of a number already taken gets 409 phone_taken.
// 3. Each token's GET /me shows its own account: its id, its name and its number.
// 4. A sign-up sent again with its request id (the app retrying after a lost answer) gets the first answer: the same
//    account, and a token that works.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';

const URL_ = process.env.SCA_WEBAPP_URL;
const CODE = process.env.SCA_GROUP_CODE;
if (!URL_ || !CODE) {
  console.error('Set SCA_WEBAPP_URL to the web app URL and SCA_GROUP_CODE to the group code.');
  process.exit(2);
}
const N = Math.max(2, Math.min(30, Number(process.argv[2] || 6)));
const TIMEOUT_MS = 60000; // longer than the backend's 20 s wait for the lock, as the app's read timeout is

async function call(method, path, { token, body, requestId } = {}) {
  const envelope = { method, path, query: {}, token: token || '', body: body ?? null };
  if (requestId) envelope.request_id = requestId;
  const start = performance.now();
  try {
    // Apps Script answers a POST with a redirect to the result; fetch follows it with a GET, as it should.
    const res = await fetch(URL_, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(envelope),
      redirect: 'follow', signal: AbortSignal.timeout(TIMEOUT_MS) });
    const text = await res.text();
    let out;
    try {
      out = JSON.parse(text);
    } catch {
      out = { status: 'not JSON', body: { detail: text.slice(0, 120).replace(/\s+/g, ' ') } };
    }
    return Object.assign(out, { ms: performance.now() - start });
  } catch (err) {
    return { status: 'no answer', body: { detail: err.name + ': ' + err.message }, ms: performance.now() - start };
  }
}

// Numbers for this run, out of the made-up range, so a run does not meet an earlier one's (unless both are left in
// the Sheet and happen to overlap: remove the test people between runs).
const first = Math.floor(Math.random() * (10000 - N - 2));
const people = Array.from({ length: N + 1 }, (_, i) => {
  const nn = String(i + 1).padStart(2, '0');
  const digits = String(first + i).padStart(4, '0');
  return { name: 'TEST concurrency ' + nn, phone: '+91 10000 7' + digits, e164: '+91100007' + digits, password: 'conc-' + randomUUID().slice(0, 12),
    requestId: randomUUID() };
});
const late = people.pop(); // its number is not sent: the sequential duplicate reuses an account's
const signupOf = (p, requestId = p.requestId) => call('POST', '/auth/signup', { requestId,
  body: { name: p.name, phone: p.phone, password: p.password, role: 'student', code: CODE, lang: 'en' } });

const results = [];
function check(name, fn) {
  try {
    fn();
    results.push([name, 'PASS', '']);
  } catch (err) {
    results.push([name, 'FAIL', err.message.split('\n')[0]]);
  }
}
const shown = (r) => r.status + (r.status === 200 ? '' : ' ' + JSON.stringify(r.body && r.body.detail));

console.log(`Sending ${N} sign-ups at once, and a second copy of the first one's number (+91 10000 7${String(first).padStart(4, '0')} and on)…`);
const copy = { ...people[0], name: people[0].name + ' (copy)', requestId: randomUUID() };
const burst = await Promise.all(people.map((p) => signupOf(p)).concat([signupOf(copy)]));
const answers = burst.slice(0, N);
const copyAnswer = burst[N];
burst.forEach((r, i) => console.log('  ' + (i < N ? people[i].name : copy.name).padEnd(30) + String(Math.round(r.ms)).padStart(6) + ' ms  ' + shown(r)));

check('every sign-up answered (no time-out, no 503 busy)', () => {
  const missing = burst.filter((r) => r.status !== 200 && r.status !== 409);
  assert.equal(missing.length, 0, missing.map(shown).join('; '));
});
const pair = [answers[0], copyAnswer];
const won = pair.find((r) => r.status === 200);
check('the number sent twice at once has one account: one copy 200, the other 409 phone_taken', () => {
  assert.deepEqual(pair.map((r) => r.status).sort(), [200, 409], pair.map(shown).join(' and '));
  assert.equal(pair.find((r) => r.status === 409).body.detail, 'phone_taken');
});
// The accounts made: the first number's from whichever copy won, every other number's own.
const made = answers.map((r, i) => (i === 0 ? won : r.status === 200 ? r : null));
check(`the other ${N - 1} sign-ups made an account each`, () => {
  const refused = answers.slice(1).filter((r) => r.status !== 200);
  assert.equal(refused.length, 0, refused.map(shown).join('; '));
});
const accounts = made.filter(Boolean);
check('every account has an id of its own', () => {
  const ids = accounts.map((r) => r.body.user.id);
  assert.equal(new Set(ids).size, ids.length, 'ids ' + ids.join(', '));
});
check('each account has the number it was sent with', () => {
  made.forEach((r, i) => r && assert.equal(r.body.user.phone, people[i].e164, people[i].name));
});

console.log('\nA later sign-up of a number already taken…');
const again = await signupOf({ ...people[1], name: late.name }, randomUUID());
console.log('  ' + shown(again));
check('a later sign-up of a taken number gets 409 phone_taken', () => assert.deepEqual([again.status, again.body.detail], [409, 'phone_taken']));

console.log('\nEach token\'s GET /me…');
const mine = await Promise.all(made.map((r) => (r ? call('GET', '/me', { token: r.body.token }) : null)));
check('each token opens its own account: the id, the name and the number it signed up with', () => {
  const wrong = [];
  mine.forEach((r, i) => {
    if (!r) return;
    const want = made[i].body.user;
    const got = r.body && r.body.user;
    if (r.status !== 200 || !got || got.id !== want.id || got.name !== want.name || got.phone !== want.phone) {
      wrong.push(people[i].name + ': ' + (got ? `id ${got.id} "${got.name}"` : shown(r)));
    }
  });
  assert.equal(wrong.length, 0, wrong.join('; '));
});

console.log('\nA sign-up sent again with its request id…');
const k = made.findIndex((r, i) => i > 0 && r);
let replay = null;
let replayMe = null;
if (k > 0) {
  replay = await signupOf(people[k]);
  replayMe = replay.status === 200 ? await call('GET', '/me', { token: replay.body.token }) : null;
  console.log('  ' + people[k].name + ': ' + shown(replay) + (replay.status === 200 ? (replay.body.token === made[k].body.token ? ', the same token' : ', another token') : ''));
}
check('a sign-up sent again with its request id gets the first answer: the same account, a token that works', () => {
  assert.ok(replay, 'no account to replay');
  assert.equal(replay.status, 200, shown(replay));
  assert.equal(replay.body.user.id, made[k].body.user.id);
  assert.equal(replayMe && replayMe.status, 200);
  assert.equal(replayMe.body.user.name, people[k].name);
});

const times = burst.map((r) => r.ms).sort((a, b) => a - b);
console.log(`\nSign-ups at once: ${burst.length}, answered in ${Math.round(times[0])} to ${Math.round(times[times.length - 1])} ms ` +
  `(median ${Math.round(times[Math.floor(times.length / 2)])}).`);
console.log('\n' + results.map(([name, verdict, why]) => verdict + '  ' + name + (why ? '\n      ' + why : '')).join('\n'));
const failed = results.filter(([, verdict]) => verdict === 'FAIL').length;
console.log(failed ? `\n${failed} of ${results.length} checks failed.` : `\nAll ${results.length} checks passed.`);
console.log(`Remove the ${accounts.length} test people from the Sheet's menu: Satt Chitt Anand → Remove test people…`);
process.exit(failed ? 1 : 0);
