// A smoke test of the deployed web app that writes no row to the Sheet, with latencies.
//
//   SCA_WEBAPP_URL=<the web app URL> node appsscript/scripts/smoke.mjs [rounds]
//
// Every request either touches no tab or only reads: the health check, the studio in three languages, requests
// refused before any write (a bad envelope, an unknown path, a wrong method, signed-out calls, sign-ups that fail
// validation, a wrong group code), one sign-up with a wrong teacher code, and logins with a wrong password for numbers
// that cannot be real mobiles (+91 1…). Side effects, all in CacheService and none in the Sheet: each failed login and
// the wrong group code count toward that made-up number's lockout, and the one wrong teacher code counts toward the
// teacher code's (5 in 15 minutes); run it at most once per quarter hour before the teacher has signed up.
import assert from 'node:assert/strict';

const URL_ = process.env.SCA_WEBAPP_URL;
if (!URL_) {
  console.error('Set SCA_WEBAPP_URL to the web app URL.');
  process.exit(2);
}
const ROUNDS = Number(process.argv[2] || 5);

async function timed(fn) {
  const start = performance.now();
  const out = await fn();
  return { ms: performance.now() - start, out };
}

async function post(text) {
  // Apps Script answers a POST with a redirect to the result; fetch follows it with a GET, as it should.
  const res = await fetch(URL_, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: text, redirect: 'follow' });
  return JSON.parse(await res.text());
}

const call = (method, path, { query, token, body } = {}) => post(JSON.stringify({ method, path, query: query || {}, token: token || '', body: body ?? null }));
const get = async () => JSON.parse(await (await fetch(URL_, { redirect: 'follow' })).text());

let made = 0;
const madeUpPhone = () => '+91 10000 ' + String(Date.now() % 100000 + made++).padStart(5, '0').slice(-5);

const CHECKS = [
  ['GET (no envelope)', get, (r) => assert.deepEqual(r, { status: 200, body: { ok: true } })],
  ['/health', () => call('GET', '/health'), (r) => assert.equal(r.body.ok, true)],
  ['/studio en', () => call('GET', '/studio'), (r) => assert.equal(r.body.name, 'Satt Chitt Anand Yoga')],
  ['/studio hi', () => call('GET', '/studio', { query: { lang: 'hi' } }), (r) => assert.equal(r.body.name, 'सत्·चित्·आनन्द योग')],
  ['/studio mr', () => call('GET', '/studio?lang=mr'), (r) => {
    assert.deepEqual([r.body.batches.length, r.body.batches[0].key, r.body.batches[0].name], [4, 'beginner', 'नवशिके']);
    assert.equal(r.body.tagline, 'सत्य · चैतन्य · आनन्द');
  }],
  ['/studio bad lang', () => call('GET', '/studio', { query: { lang: 'fr' } }), (r) => assert.equal(r.status, 422)],
  ['bad envelope', () => post('not json'), (r) => assert.deepEqual([r.status, r.body.detail], [400, 'bad_envelope'])],
  ['unknown path', () => call('GET', '/chat'), (r) => assert.deepEqual(r, { status: 404, body: { detail: 'Not Found' } })],
  ['wrong method', () => call('DELETE', '/home'), (r) => assert.deepEqual(r, { status: 405, body: { detail: 'Method Not Allowed' } })],
  ['/home signed out', () => call('GET', '/home'), (r) => assert.deepEqual(r, { status: 401, body: { detail: 'signed_out' } })],
  ['/home bad token', () => call('GET', '/home', { token: 'not-a-real-token' }), (r) => assert.equal(r.status, 401)],
  ['/me/password signed out', () => call('POST', '/me/password', { body: { current_password: 'x', new_password: 'secret1' } }),
    (r) => assert.deepEqual(r, { status: 401, body: { detail: 'signed_out' } })],
  ['/teacher/home bad token', () => call('GET', '/teacher/home', { token: 'not-a-real-token' }), (r) => assert.equal(r.status, 401)],
  ['signup bad phone', () => call('POST', '/auth/signup', { body: { name: 'x', phone: '12345', password: 'secret1' } }),
    (r) => assert.deepEqual(r, { status: 400, body: { detail: 'bad_phone' } })],
  ['signup short password', () => call('POST', '/auth/signup', { body: { name: 'x', phone: madeUpPhone(), password: 'abc' } }),
    (r) => assert.equal(r.status, 422)],
  ['signup no name', () => call('POST', '/auth/signup', { body: { phone: madeUpPhone(), password: 'secret1' } }),
    (r) => assert.equal(r.status, 422)],
  // "0" is not in the code alphabet, so these codes can never match.
  ['signup wrong group code', () => call('POST', '/auth/signup', { body: { name: 'x', phone: madeUpPhone(), password: 'secret1', code: 'WRONG0' } }),
    (r) => assert.deepEqual(r, { status: 400, body: { detail: 'bad_group_code' } })],
  ['login wrong password', () => call('POST', '/auth/login', { body: { phone: madeUpPhone(), password: 'wrong-password' } }),
    (r) => assert.deepEqual(r, { status: 401, body: { detail: 'bad_login' } })],
];
const ONCE = [
  ['signup wrong teacher code', () => call('POST', '/auth/signup', { body: { name: 'x', phone: madeUpPhone(), password: 'secret1', role: 'teacher', code: 'WRONG000' } }),
    (r) => assert.ok(['bad_teacher_code', 'teacher_exists'].includes(r.body.detail) && [400, 409].includes(r.status), JSON.stringify(r))],
];

const stats = (list) => {
  const s = list.slice().sort((a, b) => a - b);
  return { n: s.length, min: s[0], median: s[Math.floor(s.length / 2)], max: s[s.length - 1] };
};

const times = {};
let failures = 0;
async function run([name, fn, check]) {
  const { ms, out } = await timed(fn);
  try {
    check(out);
  } catch (err) {
    failures++;
    console.log('FAIL ' + name + ': ' + JSON.stringify(out) + ' ' + err.message);
  }
  (times[name] = times[name] || []).push(ms);
  return ms;
}

const first = await run(CHECKS[0]);
console.log('first request: ' + first.toFixed(0) + ' ms');
for (const check of ONCE) await run(check);
for (let round = 0; round < ROUNDS; round++) for (const check of CHECKS) await run(check);
console.log('\nrequest'.padEnd(30) + 'n   min  median   max (ms, end to end)');
for (const [name, list] of Object.entries(times)) {
  const s = stats(list);
  console.log(name.padEnd(29) + String(s.n).padStart(2) + [s.min, s.median, s.max].map((v) => v.toFixed(0).padStart(6)).join(''));
}
console.log(failures ? '\n' + failures + ' check(s) failed' : '\nall checks passed');
process.exit(failures ? 1 : 0);
