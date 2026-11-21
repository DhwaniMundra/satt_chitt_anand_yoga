// What is particular to Apps Script: the envelope, the Sheet as storage, the lock, the cache, and setup().
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, freshBackend, setSetting, setting, signup, teacherAndCode, testBackend } from './helpers.mjs';

const post = (b, contents) => JSON.parse(b.context.doPost({ postData: { contents } }).getContent());

test('the envelope: what a bad one gets', () => {
  const b = freshBackend();
  assert.deepEqual(post(b, 'not json').status, 400);
  assert.equal(post(b, 'not json').body.detail, 'bad_envelope');
  assert.equal(post(b, '[]').body.detail, 'bad_envelope');
  assert.equal(post(b, JSON.stringify({ method: 'PATCH', path: '/me' })).body.detail, 'bad_envelope');
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: 'home' })).body.detail, 'bad_envelope');
  assert.equal(JSON.parse(b.context.doPost({}).getContent()).status, 400); // no body at all
  assert.deepEqual(post(b, JSON.stringify({ method: 'get', path: '/health' })), { status: 200, body: { ok: true, assistant: 'off', model: null } });
});

test('the envelope: query in the path or apart, the token with or without "Bearer"', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: '/studio?lang=hi' })).body.name, 'सत्·चित्·आनन्द योग');
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: '/studio?lang=hi', query: { lang: 'mr' } })).body.tagline, 'सत्य · चैतन्य · आनन्द');
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: '/me', token: 'Bearer ' + s.token })).status, 200);
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: '/me', token: s.token })).status, 200);
  assert.equal(post(b, JSON.stringify({ method: 'GET', path: '/me/practice', query: { days: 30 }, token: s.token })).body.detail, 'pending');
});

test('a write sent again with the same request id is answered as the first time, and written once', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const rows = (tab) => b.ss.getSheetByName(tab).rows().length - 1;
  const twice = (method, path, token, body, requestId) => [1, 2].map(() => b.call(method, path, { token, body, requestId }));

  const solo = { minutes: 10, entries: [{ item: 'vajrasana', hold_s: 60, reaction: 3 }] };
  const [first, again] = twice('POST', '/me/solo', s.token, solo, 'solo-1');
  assert.deepEqual([first, again], [first, first]);
  assert.deepEqual([rows('solo_sessions'), rows('practice')], [1, 1]);

  const feedback = { item: 'vajrasana', text: 'Keep the knees together' };
  const [said, saidAgain] = twice('POST', '/teacher/students/' + s.user.id + '/feedback', t.token, feedback, 'note-1');
  assert.deepEqual([said.body, saidAgain.body], [{ ok: true, id: 1 }, { ok: true, id: 1 }]);
  assert.equal(rows('asana_feedback'), 1);

  const move = { batch: 'intermediate', note: 'Ready for longer holds' };
  const [moved, movedAgain] = twice('PUT', '/teacher/students/' + s.user.id + '/batch', t.token, move, 'move-1');
  assert.deepEqual(movedAgain, moved);
  assert.equal(rows('batch_changes'), 1);

  b.call('POST', '/me/solo', { token: s.token, body: solo, requestId: 'solo-2' });
  b.call('POST', '/me/solo', { token: s.token, body: solo });
  assert.equal(rows('solo_sessions'), 3, 'a new id, or none, is a new practice');
  const other = signup(b, '9000000003', { code });
  b.call('POST', '/me/solo', { token: other.token, body: solo, requestId: 'solo-1' });
  assert.equal(rows('solo_sessions'), 4, 'the id is kept per login');
  assert.equal(b.call('POST', '/me/solo', { token: s.token, body: { minutes: 1, entries: [{ item: 'tadasana' }] }, requestId: 'empty' }).body.detail,
    'nothing_said');
  b.call('POST', '/me/solo', { token: s.token, body: solo, requestId: 'empty' });
  assert.equal(rows('solo_sessions'), 5, 'a refusal is not kept: the same id can try again');
  b.state.offsetMs += 11 * 60000;
  assert.deepEqual(b.call('POST', '/me/solo', { token: s.token, body: solo, requestId: 'solo-1' }), first,
    'a practice keeps its id in its row: written once past the ten minutes the answer is kept');
  assert.equal(rows('solo_sessions'), 5);
});

test('an unknown path is a 404, a wrong method a 405', () => {
  const b = freshBackend();
  assert.deepEqual(b.call('GET', '/nope'), { status: 404, body: { detail: 'Not Found' } });
  assert.deepEqual(b.call('GET', '/home/'), { status: 404, body: { detail: 'Not Found' } });
  assert.deepEqual(b.call('GET', '/teacher/sessions//share'), { status: 404, body: { detail: 'Not Found' } });
  assert.deepEqual(b.call('PUT', '/home'), { status: 405, body: { detail: 'Method Not Allowed' } });
  assert.deepEqual(b.call('GET', '/auth/login'), { status: 405, body: { detail: 'Method Not Allowed' } });
});

test('validation errors are a 422 with a list of problems, after the sign-in check', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const missing = b.call('POST', '/auth/signup', { body: { phone: '9000000003' } });
  assert.equal(missing.status, 422);
  assert.deepEqual(missing.body.detail.map((e) => [e.type, e.loc.join('.')]), [['missing', 'body.name'], ['missing', 'body.password']]);
  const wrong = b.call('POST', '/sessions/abc/checkin', { token: s.token, body: { phase: 'during', mood: 9 } });
  assert.deepEqual(wrong.body.detail.map((e) => [e.type, e.loc.join('.')]),
    [['int_parsing', 'path.session_id'], ['literal_error', 'body.phase'], ['less_than_equal', 'body.mood']]);
  assert.equal(b.call('POST', '/sessions/abc/checkin', { body: { phase: 'during' } }).status, 401); // who, before what
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x', phone: 9000000003, password: 'secret1' } }).body.detail[0].type, 'string_type');
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000003', password: 'short' } }).body.detail[0].type, 'string_too_short');
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x'.repeat(81), phone: '9000000003', password: 'secret1' } }).body.detail[0].type,
    'string_too_long');
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000003', password: 'secret1', role: 'admin' } }).status, 422);
  assert.equal(b.call('POST', '/auth/login', { body: null }).body.detail[0].type, 'missing');
  assert.equal(b.call('POST', '/auth/login', { body: ['9000000002'] }).body.detail[0].type, 'model_attributes_type');
  const mood = (value) => b.call('POST', '/sessions/1/checkin', { token: s.token, body: { phase: 'before', mood: value } });
  assert.equal(mood(2.5).body.detail[0].type, 'int_from_float');
  assert.equal(mood('x').body.detail[0].type, 'int_parsing');
  assert.notEqual(mood('3').status, 422); // "3" counts as an integer
});

test('the Sheet keeps text as typed: numbers, codes and formulas stay text', () => {
  const b = freshBackend();
  setSetting(b, 'teacher_code', '2E345678'); // a number to Sheets, but for the "'"
  const t = signup(b, '9000000001', { role: 'teacher', code: '2e345678', name: '=HYPERLINK("http://evil.example")' });
  assert.equal(t.user.name, '=HYPERLINK("http://evil.example")');
  const users = b.ss.getSheetByName('users');
  const row = users.rows()[1];
  assert.equal(row[1], '=HYPERLINK("http://evil.example")'); // text, not a formula
  assert.equal(row[2], '+919000000001'); // text, not the number 919000000001
  assert.equal(typeof row[0], 'number');
  assert.ok(row[7] instanceof Date);
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000001', password: 'secret1' } }).body.user.name, t.user.name);
  b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'chat.whatsapp.com/123456' } });
  assert.equal(setting(b, 'group_link'), 'https://chat.whatsapp.com/123456');
});

test('passwords are salted and stretched, and tokens are kept only as hashes', () => {
  const b = freshBackend();
  const a = signup(b, '9000000002');
  const c = signup(b, '9000000003');
  const hashes = b.ss.getSheetByName('users').rows().slice(1).map((r) => r[5]);
  for (const hash of hashes) {
    const parts = hash.split('$');
    assert.deepEqual([parts.length, parts[0], parts[1], parts[2]], [5, 'sha256x', '100', '131072']);
    assert.match(parts[3], /^[0-9a-f]{32}$/);
    assert.match(parts[4], /^[0-9a-f]{64}$/);
    assert.ok(!hash.includes('secret1'));
  }
  assert.notEqual(hashes[0], hashes[1]); // the same password, different salts
  const tokens = b.ss.getSheetByName('tokens').rows().slice(1).map((r) => r[0]);
  assert.equal(tokens.length, 2);
  assert.ok(!tokens.includes(a.token) && !tokens.includes(c.token));
  assert.equal(tokens[0], b.evaluate('sha256Hex_(' + JSON.stringify(a.token) + ')'));
  assert.equal(b.evaluate("checkPassword_('secret1', " + JSON.stringify(hashes[0]) + ')'), true);
  assert.equal(b.evaluate("checkPassword_('secret2', " + JSON.stringify(hashes[0]) + ')'), false);
  assert.equal(b.evaluate("checkPassword_('secret1', 'pbkdf2$200000$00$00')"), false);
  const digests = b.state.digests;
  b.call('POST', '/auth/login', { body: { phone: '9000000099', password: 'secret1' } });
  assert.ok(b.state.digests - digests >= 100, 'an unknown number costs a full hash, so timing does not tell who has an account');
});

test('codes and tokens use the whole alphabet and do not repeat', () => {
  const b = freshBackend();
  const codes = new Set(Array.from({ length: 300 }, () => b.evaluate('newCode_(6)')));
  assert.equal(codes.size, 300);
  const letters = new Set([...codes].join(''));
  assert.equal(letters.size, 32);
  assert.ok(!/[01OI]/.test([...letters].join('')));
  assert.match(b.evaluate('newToken_()'), /^[A-Za-z0-9_-]{43}$/);
});

test('columns are found by name: the owner may move them and add her own', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const users = b.ss.getSheetByName('users');
  // Move "phone" to the end and put a column of her own in its place.
  users.data.forEach((line) => {
    const phone = line[2];
    line[2] = line === users.data[0] ? 'notes' : 'met at the park';
    line[10] = phone;
  });
  b.context.onEdit({});
  const s = signup(b, '9000000002', { code });
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000001', password: 'secret1' } }).status, 200);
  const last = users.rows()[users.getLastRow() - 1];
  assert.equal(last[10], '+919000000002');
  assert.equal(last[2], '');
  assert.equal(b.call('GET', '/teacher/students', { token: t.token }).body.students[0].phone, s.user.phone);
});

test('a tab without a needed column is reported, not guessed at', () => {
  const b = freshBackend();
  b.ss.getSheetByName('users').data[0][2] = 'mobile';
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '9000000001', password: 'secret1' } }), { status: 500, body: { detail: 'not_set_up' } });
  const raw = testBackend();
  assert.deepEqual(raw.call('POST', '/auth/login', { body: { phone: '9000000001', password: 'secret1' } }), { status: 500, body: { detail: 'not_set_up' } });
  raw.context.setup();
  b.ss.getSheetByName('users').data[0][2] = 'phone';
  b.context.setup(); // setup puts nothing back twice
  assert.equal(b.ss.getSheetByName('users').rows()[0].filter((h) => h === 'phone').length, 1);
});

test('setup adds a column the code needs to an existing tab', () => {
  const b = freshBackend();
  const checkins = b.ss.getSheetByName('checkins');
  checkins.data[0] = checkins.data[0].slice(0, 5); // a tab without class and class_date
  b.context.setup();
  assert.deepEqual(checkins.rows()[0], ['user_id', 'session_id', 'phase', 'mood', 'created_at', 'class', 'class_date']);
});

test('a column that came later reads as empty on a Sheet set up before it, and its first write adds its header', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const solo = b.ss.getSheetByName('solo_sessions');
  solo.data[0] = ['id', 'user_id', 'started_at', 'ended_at', 'notes']; // the live Sheet before request_id, with a column of the owner's
  addRow(b, 'solo_sessions', { id: 1, user_id: s.user.id, started_at: b.clock() - 3600000, ended_at: b.clock() - 1800000 });
  b.context.onEdit({});
  assert.equal(b.call('GET', '/me/practice', { token: s.token }).body.solo.length, 1, 'read as it is');
  const send = () => b.call('POST', '/me/solo', { token: s.token, requestId: 'r-1', body: { minutes: 10, entries: [{ item: 'vajrasana', reaction: 3 }] } });
  assert.equal(send().body.id, 2);
  assert.deepEqual(solo.rows()[0], ['id', 'user_id', 'started_at', 'ended_at', 'notes', 'request_id'], 'added after the owner\'s column');
  assert.deepEqual(solo.rows().slice(1).map((r) => [r[0], r[5]]), [[1, ''], [2, 'r-1']]);
  b.cache.clear();
  assert.equal(send().body.id, 2, 'and it is read back');
  assert.equal(solo.rows().length, 3);
  const classes = b.ss.getSheetByName('class_sessions');
  const head = classes.data[0].length;
  classes.data[0] = classes.data[0].filter((h) => h !== 'time_set_by');
  b.context.onEdit({});
  assert.ok(b.call('GET', '/home', { token: s.token }).body.sessions.length > 0);
  assert.equal(classes.rows()[0].length, head - 1, 'reads and writes of no value add nothing');
  b.context.setup();
  assert.equal(classes.rows()[0].at(-1), 'time_set_by', 'setup adds it too');
});

test('ids are allocated one after the other, under the lock', () => {
  const b = freshBackend();
  const ids = ['9000000002', '9000000003', '9000000004'].map((p) => signup(b, p).user.id);
  assert.deepEqual(ids, [1, 2, 3]);
  assert.equal(b.state.lockHeld, 0);
  const s = signup(b, '9000000005');
  const first = b.call('POST', '/feedback', { token: s.token, body: { screen: 'me', text: 'one' } });
  b.call('POST', '/feedback', { token: s.token, body: { screen: 'me', text: 'two' } });
  assert.equal(first.status, 200);
  assert.deepEqual(b.ss.getSheetByName('feedback').rows().slice(1).map((r) => r[0]), [1, 2]);
});

test('every write happens under the lock, which is always let go', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  b.state.lockFree = false;
  const writes = b.ss.writes;
  assert.deepEqual(b.call('POST', '/feedback', { token: s.token, body: { screen: 'me', text: 'x' } }), { status: 503, body: { detail: 'busy' } });
  assert.deepEqual(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000003', password: 'secret1', code: setting(b, 'group_code') } }).body,
    { detail: 'busy' });
  assert.equal(b.ss.writes, writes);
  assert.equal(b.call('GET', '/studio').status, 200); // reading needs no lock
  b.state.lockFree = true;
  assert.equal(b.call('POST', '/me', { token: s.token, body: { name: '' } }).status, 422);
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'nope' } }).status, 401);
  assert.equal(b.state.lockHeld, 0);
});

test('a failure inside a route is a 500 with no details, and the lock is let go', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  b.ss.getSheetByName('feedback').maxRows = 0; // writing anywhere in it fails
  const r = b.call('POST', '/feedback', { token: s.token, body: { screen: 'me', text: 'x' } });
  assert.deepEqual(r, { status: 500, body: { detail: 'Internal Server Error' } });
  assert.equal(b.state.lockHeld, 0);
  assert.ok(b.state.logs.some((line) => line.startsWith('ERROR')));
});

test('tabs grow past their first thousand rows', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  const sheet = b.ss.getSheetByName('feedback');
  sheet.maxRows = 3;
  for (let i = 0; i < 4; i++) assert.equal(b.call('POST', '/feedback', { token: s.token, body: { screen: 'me', text: 'n' + i } }).status, 200);
  assert.equal(sheet.rows().length, 5);
});

test('the cache: a token is looked up once, and forgotten at logout', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  b.call('GET', '/me', { token: s.token });
  const tokens = b.ss.getSheetByName('tokens');
  const saved = tokens.data.slice();
  tokens.data = [tokens.data[0]]; // the tab is not read again while the token is cached
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 200);
  tokens.data = saved;
  b.call('POST', '/auth/logout', { token: s.token });
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 401);
});

test('the cache: a hand edit or ten minutes and the Sheet is read again', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const read = () => b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_link;
  assert.equal(read(), null);
  const sheet = b.ss.getSheetByName('settings');
  const row = sheet.rows().findIndex((r) => r[0] === 'group_link') + 1;
  sheet.getRange(row, 2).setValue("'https://chat.whatsapp.com/AAA");
  assert.equal(read(), null, 'cached');
  b.context.onEdit({});
  assert.equal(read(), 'https://chat.whatsapp.com/AAA');
  sheet.getRange(row, 2).setValue("'https://chat.whatsapp.com/BBB");
  b.state.offsetMs += 601000;
  assert.equal(read(), 'https://chat.whatsapp.com/BBB');
  b.cache.clear(); // an eviction loses nothing but speed
  assert.equal(read(), 'https://chat.whatsapp.com/BBB');
});

test('a token row deleted by hand stops working within the cache time', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  b.call('GET', '/me', { token: s.token });
  b.ss.getSheetByName('tokens').deleteRow(2);
  b.state.offsetMs += 601000;
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 401);
});

test('setup: the Dashboard formulas point at the right columns', () => {
  const b = freshBackend();
  const dashboard = b.ss.getSheetByName('Dashboard');
  const formulas = dashboard.data.flatMap((line, r) => (line || []).map((v, c) => [r + 1, c + 1, v])).filter(([, , v]) => v && v.formula);
  assert.equal(formulas.length, 12);
  assert.equal(Object.keys(dashboard.notes).length, 12, 'each block title explains its block');
  const text = formulas.map(([, , v]) => v.formula).join('\n');
  assert.match(text, /QUERY\(users!A1:J, "select E, count\(A\) where D = 'student' group by E/);
  assert.match(text, /QUERY\(users!A1:J, "select I, count\(A\) where D = 'student' and E = 'approved' group by I/);
  assert.match(text, /VLOOKUP\(batch_changes!B2:B, \{users!A2:A, users!B2:B\}, 2, FALSE\)/);
  assert.match(text, /users!E2:E, users!I2:I, users!G2:G/);
  assert.match(text, /\{"knee", COUNTIF\(intake!G2:G, "\*knee\*"\); "back", COUNTIF/, 'pain areas as counts, no names');
  assert.match(text, /QUERY\(checkins!A1:G, "select G, F, count\(A\) where C = 'before' group by G, F order by G desc/);
  assert.match(text, /select F, avg\(D\) where A is not null group by F pivot C/);
  assert.match(text, /VLOOKUP\(feedback!B2:B, \{users!A2:A, users!B2:B\}, 2, FALSE\)/);
  assert.match(text, /VLOOKUP\(shared_notes!B2:B, \{users!A2:A, users!B2:B\}, 2, FALSE\)/);
  assert.match(text, /COUNTIFS\(checkins!A2:A, users!A2:A, checkins!C2:C, "before"\)/);
  assert.match(text, /practice!F2:F\}, "select Col1, Col2, Col3, Col4 where Col5 = 1 and Col1 >= datetime '" & TEXT\(TODAY\(\) - 14/);
  assert.match(text, /QUERY\(practice!A1:L, "select I, avg\(E\) where E is not null group by I pivot J", 1\)/);
  for (const [, , v] of formulas) {
    assert.equal((v.formula.match(/\(/g) || []).length, (v.formula.match(/\)/g) || []).length, v.formula);
    assert.equal((v.formula.match(/"/g) || []).length % 2, 0, v.formula);
    assert.ok(v.formula.startsWith('=IFERROR(QUERY('), v.formula);
  }
  dashboard.getRange('Z1').setValue('my own block');
  b.context.setup();
  assert.equal(dashboard.getRange('Z1').getValue(), 'my own block', 'setup leaves an existing Dashboard alone');
});

test('setup: the data tabs warn before a hand edit; the batches tab is seeded once and is the owner\'s', () => {
  const b = freshBackend();
  for (const tab of ['users', 'checkins', 'settings', 'batch_changes']) {
    const protections = b.ss.getSheetByName(tab).getProtections();
    assert.equal(protections.length, 1, tab);
    assert.equal(protections[0].warningOnly, true);
  }
  assert.equal(b.ss.getSheetByName('batches').getProtections().length, 0, 'no warning on the owner\'s own tab');
  const batches = b.ss.getSheetByName('batches');
  assert.deepEqual(batches.rows()[0], ['key', 'name', 'name_hi', 'name_mr', 'curriculum', 'days', 'time', 'duration_min', 'meet_link', 'about',
    'about_hi', 'about_mr']);
  batches.getRange(2, 2).setValue("'Foundations");
  b.context.setup();
  assert.equal(b.ss.getSheetByName('users').getProtections().length, 1);
  assert.equal(batches.rows().length, 5);
  assert.equal(batches.rows()[1][1], 'Foundations', 'setup leaves the owner\'s edits alone');
});

test('setup keeps a tab that is not empty, and fills an empty settings row', () => {
  const b = testBackend();
  b.ss.getSheetByName('Sheet1').getRange(1, 1).setValue('mine');
  b.context.setup();
  assert.ok(b.ss.getSheetByName('Sheet1'));
  const settings = b.ss.getSheetByName('settings');
  const row = settings.rows().findIndex((r) => r[0] === 'group_code') + 1;
  settings.getRange(row, 2).setValue('');
  b.context.setup();
  assert.match(setting(b, 'group_code'), /^[A-HJ-NP-Z2-9]{6}$/);
});

test('a hand-typed row is read like the app’s own', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  addRow(b, 'feedback', { id: 7, user_id: t.user.id, screen: 'paper', text: 'typed in by hand', created_at: b.clock() });
  const sheet = b.ss.getSheetByName('feedback');
  sheet.getRange(sheet.getLastRow() + 2, 1).setValue(''); // a blank row in between is skipped
  assert.equal(b.call('GET', '/teacher/insights', { token: t.token }).body.feedback[0].text, 'typed in by hand');
});

// Sheets keeps at least one row below a tab's frozen header: deleting every row a full tab has would fail, so a write
// that does gets an empty row added first. The tokens tab is full here: its grid ends at its last row.
const fullTokens = (b) => {
  const tokens = b.ss.getSheetByName('tokens');
  tokens.maxRows = tokens.getLastRow();
  return tokens;
};

test('a full tokens tab: a reset, the next sign-up, and its logout, which deletes the tab\'s every row', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  signup(b, '9000000002', { code, name: 'Asha' });
  const tokens = fullTokens(b);
  b.evaluate('resetStudio_(new Db_())');
  assert.equal(tokens.rows().length, 1, 'the header alone');
  const teacher = signup(b, '9000000009', { role: 'teacher', code: 'TEACH123' });
  fullTokens(b);
  assert.deepEqual(b.call('POST', '/auth/logout', { token: teacher.token }), { status: 200, body: { ok: true } });
  assert.equal(b.call('GET', '/me', { token: teacher.token }).status, 401);
  assert.equal(tokens.rows().length, 1);
  assert.ok(tokens.getMaxRows() >= 2, 'a row kept below the header');
});

test('a new password for a student whose sign-ins are every row of a full tokens tab', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } });
  b.call('GET', '/me', { token: t.token }); // the teacher's sign-in, cached, then its row deleted by hand
  const tokens = b.ss.getSheetByName('tokens');
  const header = tokens.rows()[0];
  tokens.deleteRow(tokens.rows().findIndex((r) => r[header.indexOf('user_id')] === t.user.id) + 1);
  fullTokens(b);
  const reset = b.call('POST', '/teacher/students/' + s.user.id + '/password', { token: t.token });
  assert.equal(reset.status, 200, JSON.stringify(reset));
  assert.equal(tokens.rows().length, 1, 'her sign-ins gone, the header kept');
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 401);
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: reset.body.password } }).status, 200);
});
