// The API end to end through the envelope, route by route: sign-up and login, links, check-ins, the teacher's routes.
import assert from 'node:assert/strict';
import test from 'node:test';
import { attend, classStarted, DAY, freshBackend, MIN, setting, signup, teacherAndCode } from './helpers.mjs';

test('the teacher needs the teacher code, in any case', () => {
  const b = freshBackend();
  const r = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000001', password: 'secret1', role: 'teacher', code: 'nope' } });
  assert.deepEqual(r, { status: 400, body: { detail: 'bad_teacher_code' } });
  const { user } = signup(b, '9000000001', { role: 'teacher', code: 'teach123' });
  assert.equal(user.role, 'teacher');
  assert.equal(user.phone, '+919000000001');
  assert.equal(user.status, 'approved');
});

test('one teacher, and a code the owner typed in lowercase', () => {
  const b = freshBackend({ teacherCode: 'ramit2024' });
  signup(b, '9000000001', { role: 'teacher', code: 'ramit2024' });
  const r = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000009', password: 'secret1', role: 'teacher', code: 'RAMIT2024' } });
  assert.deepEqual(r, { status: 409, body: { detail: 'teacher_exists' } });
});

test('a wrong teacher code writes nothing and five lock the code for a while', () => {
  const b = freshBackend();
  const before = b.ss.writes;
  const wrong = () => b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000001', password: 'secret1', role: 'teacher', code: 'WRONG' } });
  for (let i = 0; i < 5; i++) assert.equal(wrong().body.detail, 'bad_teacher_code');
  assert.equal(b.ss.writes, before);
  assert.equal(wrong().body.detail, 'too_many_attempts');
  const right = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000001', password: 'secret1', role: 'teacher', code: 'TEACH123' } });
  assert.deepEqual(right, { status: 429, body: { detail: 'too_many_attempts' } });
  b.state.offsetMs += 15 * MIN + 1000;
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000001', password: 'secret1', role: 'teacher', code: 'TEACH123' } }).status, 200);
});

test('a student with the group code is approved, without it pending', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const withCode = signup(b, '9000000002', { code: code.toLowerCase() });
  const without = signup(b, '9000000003');
  assert.equal(withCode.user.status, 'approved');
  assert.equal(without.user.status, 'pending');
  const r = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000004', password: 'secret1', code: 'WRONG1' } });
  assert.deepEqual(r, { status: 400, body: { detail: 'bad_group_code' } });
});

test('one account per number, and logging in however it is typed', () => {
  const b = freshBackend();
  signup(b, '+91 90000 00002');
  const again = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000002', password: 'secret1' } });
  assert.deepEqual(again, { status: 409, body: { detail: 'phone_taken' } });
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'wrong' } }), { status: 401, body: { detail: 'bad_login' } });
  const ok = b.call('POST', '/auth/login', { body: { phone: '09000000002', password: 'secret1' } });
  assert.equal(ok.status, 200);
  assert.equal(ok.body.user.phone, '+919000000002');
  assert.equal(ok.body.token.length, 43);
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '9000000099', password: 'secret1' } }).body, { detail: 'bad_login' });
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '123', password: 'secret1' } }), { status: 400, body: { detail: 'bad_phone' } });
});

test('one number however it is typed', () => {
  const b = freshBackend();
  for (const typed of ['98765 43210', '098765 43210', '+91 98765-43210', '0091 98765 43210', '919876543210', '९८७६५ ४३२१०']) {
    assert.equal(b.evaluate('normalizePhone_(' + JSON.stringify(typed) + ')'), '+919876543210', typed);
  }
  assert.equal(b.evaluate("normalizePhone_('+44 20 7946 0958')"), '+442079460958');
  for (const bad of ['12345', '0123456789012', '+1234567890123456', 'abc', '']) {
    assert.throws(() => b.evaluate('normalizePhone_(' + JSON.stringify(bad) + ')'), /bad_phone/, bad);
  }
});

test('login locks after five wrong passwords, and unlocks after fifteen minutes', () => {
  const b = freshBackend();
  signup(b, '9000000002');
  for (let i = 0; i < 5; i++) assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'wrong!' } }).status, 401);
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }), { status: 429, body: { detail: 'too_many_attempts' } });
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000003', password: 'wrong!' } }).status, 401); // another number is not locked
  b.state.offsetMs += 15 * MIN + 1000;
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).status, 200);
});

test('a right password clears the failures', () => {
  const b = freshBackend();
  signup(b, '9000000002');
  for (let i = 0; i < 4; i++) b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'wrong!' } });
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).status, 200);
  for (let i = 0; i < 4; i++) b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'wrong!' } });
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).status, 200);
});

test('a pending student sees no link until approved', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  const session = b.call('GET', '/teacher/home', { token: t.token }).body.sessions[0];
  const r = b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } });
  assert.equal(r.status, 200);
  assert.ok(r.body.text.includes('https://meet.google.com/abc-defg-hij'));
  assert.ok(r.body.url.startsWith('https://wa.me/?text='));
  const first = b.call('GET', '/home', { token: s.token }).body.sessions[0];
  assert.equal(first.meet_link, null);
  assert.equal(first.has_link, true);
  assert.deepEqual(b.call('POST', '/sessions/' + session.id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }),
    { status: 403, body: { detail: 'pending' } });
  assert.equal(b.call('POST', '/teacher/students/' + s.user.id + '/status', { token: t.token, body: { status: 'approved' } }).status, 200);
  assert.equal(b.call('GET', '/home', { token: s.token }).body.sessions[0].meet_link, 'https://meet.google.com/abc-defg-hij');
});

test('bad links are refused', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const session = b.call('GET', '/teacher/home', { token: t.token }).body.sessions[0];
  const r = b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: 'https://evil.example/meet' } });
  assert.deepEqual(r, { status: 400, body: { detail: 'bad_meet_link' } });
  assert.equal(b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'https://example.com' } }).body.detail, 'bad_group_link');
  const ok = b.call('PUT', '/teacher/settings', { token: t.token,
    body: { group_link: 'https://chat.whatsapp.com/AbC123', default_meet_link: 'https://meet.google.com/xyz-abcd-efg' } });
  assert.equal(ok.body.group_link, 'https://chat.whatsapp.com/AbC123');
  for (const link of ['zoom.us/j/123456789', 'https://us02web.zoom.us/j/8765?pwd=ab.C-d_9', 'http://meet.google.com/abc-defg-hij']) {
    assert.equal(b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: link } }).status, 200, link);
  }
  for (const link of ['meet.google.com/ABC-defg-hij', 'https://meet.google.com/abc-defg-hij/x', 'https://zoom.us/j/abc', '']) {
    assert.equal(b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: link } }).body.detail, 'bad_meet_link', link);
  }
});

test('settings save both or neither', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const bad = b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'https://example.com/x', default_meet_link: 'meet.google.com/abc-defg-hij' } });
  assert.equal(bad.body.detail, 'bad_group_link');
  assert.equal(b.call('GET', '/teacher/home', { token: t.token }).body.settings.default_meet_link, null);
  const ok = b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'chat.whatsapp.com/AbC123' } });
  assert.deepEqual(ok.body, { group_link: 'https://chat.whatsapp.com/AbC123', group_code: setting(b, 'group_code'), default_meet_link: null });
  assert.equal(setting(b, 'group_link'), 'https://chat.whatsapp.com/AbC123');
});

test('the standing link is used when a session has none', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  b.call('PUT', '/teacher/settings', { token: t.token, body: { default_meet_link: 'https://meet.google.com/xyz-abcd-efg' } });
  const s = signup(b, '9000000002', { code });
  assert.ok(b.call('GET', '/home', { token: s.token }).body.sessions.every((x) => x.meet_link === 'https://meet.google.com/xyz-abcd-efg'));
  const teacherSessions = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  assert.ok(teacherSessions.every((x) => x.own_link === false && x.has_link));
});

test('no link at all: sharing a session says so', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const session = b.call('GET', '/teacher/home', { token: t.token }).body.sessions[0];
  assert.deepEqual(b.call('GET', '/teacher/sessions/' + session.id + '/share', { token: t.token }), { status: 400, body: { detail: 'no_link' } });
  assert.deepEqual(b.call('GET', '/teacher/sessions/99999/share', { token: t.token }), { status: 404, body: { detail: 'no_session' } });
});

test('students cannot use teacher routes, and nobody signed out can use any', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  for (const [method, path] of [['GET', '/teacher/students'], ['GET', '/teacher/home'], ['GET', '/teacher/insights'], ['GET', '/teacher/shared'],
    ['POST', '/teacher/group_code'], ['GET', '/teacher/invite'], ['PUT', '/teacher/settings'], ['POST', '/teacher/students/1/password']]) {
    assert.deepEqual(b.call(method, path, { token: s.token, body: {} }), { status: 403, body: { detail: 'teacher_only' } }, path);
  }
  for (const [method, path] of [['GET', '/home'], ['GET', '/me'], ['POST', '/feedback'], ['GET', '/teacher/home'], ['GET', '/me/practice']]) {
    assert.deepEqual(b.call(method, path, { body: {} }), { status: 401, body: { detail: 'signed_out' } }, path);
  }
});

test('check-ins feed the stats and the insights', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 50);
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 2 } }).status, 200);
  const after = b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 5 } });
  assert.deepEqual(after.body, { ok: true, stats: { classes_joined: 1, streak_days: 1, mood_change: 3, mood_pairs: 1 } });
  const stats = b.call('GET', '/me', { token: s.token }).body.stats;
  assert.equal(stats.classes_joined, 1);
  assert.equal(stats.mood_change, 3);
  assert.equal(stats.mood_pairs, 1);
  const insights = b.call('GET', '/teacher/insights', { token: t.token }).body;
  assert.equal(insights.mood_change, 3);
  assert.deepEqual(insights.students, { approved: 1, pending: 0 });
  assert.deepEqual(insights.questions, { count: 0, gemma_latency_s: null });
  const row = insights.sessions.find((x) => x.id === id);
  assert.deepEqual([row.class, row.joined, row.mood_before, row.mood_after, row.answered_after], ['Hatha Yoga', 1, 2, 5, 1]);
});

test('checking in twice changes the mood, not the count', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 10);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 2 } });
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 4 } });
  const rows = b.ss.getSheetByName('checkins').rows().slice(1);
  assert.equal(rows.length, 1);
  assert.deepEqual(rows[0].slice(0, 4), [s.user.id, id, 'before', 4]);
  assert.equal(rows[0][5], 'Hatha Yoga'); // the copy for the owner's queries
});

test('the after check-in is offered once class ends, and only until it is answered', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 50);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } });
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin.id, id);
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin.meet_link, null);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 4 } });
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin, null);
});

test('the after check-in is not offered half a day after class', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 30);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } });
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin, null); // still in class
  b.state.offsetMs += 13 * 3600000;
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin, null); // too late
});

test('check-ins only around class time', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const home = b.call('GET', '/home', { token: s.token }).body;
  const later = home.sessions.filter((x) => Date.parse(x.starts_at) > b.clock() + 2 * 3600000);
  assert.equal(b.call('POST', '/sessions/' + later[0].id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).body.detail,
    'checkin_closed'); // tomorrow's class cannot be checked into today
  const old = classStarted(b, 60 * 24 * 3);
  assert.equal(b.call('POST', '/sessions/' + old + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).body.detail, 'checkin_closed');
  const now = classStarted(b, 50);
  assert.equal(b.call('POST', '/sessions/' + now + '/checkin', { token: s.token, body: { phase: 'after', mood: 3 } }).body.detail,
    'checkin_closed'); // no "after" without a "before"
  const soon = classStarted(b, -55);
  assert.equal(b.call('POST', '/sessions/' + soon + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  assert.deepEqual(b.call('POST', '/sessions/424242/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }),
    { status: 404, body: { detail: 'no_session' } });
});

test('the streak counts consecutive days with a class', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  for (const daysAgo of [1, 2, 3, 5]) attend(b, s.user.id, 'hatha', daysAgo, 3, 4);
  const stats = b.call('GET', '/me', { token: s.token }).body.stats;
  assert.deepEqual(stats, { classes_joined: 4, streak_days: 3, mood_change: 1, mood_pairs: 4 }); // today's class may not have happened
  attend(b, s.user.id, 'hatha', 0, 2, null);
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 4);
});

test('the chat and the health notes have no routes: they stay on the phone', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  for (const [method, path] of [['POST', '/ask'], ['GET', '/chat'], ['POST', '/chat'], ['DELETE', '/chat'], ['GET', '/me/notes'], ['DELETE', '/me/notes/1']]) {
    assert.deepEqual(b.call(method, path, { token: s.token, body: { question: 'hello' } }), { status: 404, body: { detail: 'Not Found' } }, path);
  }
});

test('resetting a password signs the student out', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }); // a second device
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 200); // the token is now cached
  const r = b.call('POST', '/teacher/students/' + s.user.id + '/password', { token: t.token });
  assert.match(r.body.password, /^[A-HJ-NP-Z2-9]{8}$/);
  assert.deepEqual(b.call('GET', '/me', { token: s.token }), { status: 401, body: { detail: 'signed_out' } });
  const tokens = b.ss.getSheetByName('tokens').rows().slice(1);
  assert.ok(tokens.every((row) => row[1] !== s.user.id));
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: r.body.password } }).status, 200);
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).status, 401);
  assert.deepEqual(b.call('POST', '/teacher/students/' + t.user.id + '/password', { token: t.token }), { status: 404, body: { detail: 'no_student' } });
});

test('a pending student can enter the group code later', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  assert.equal(b.call('POST', '/me/group_code', { token: s.token, body: { code: 'WRONG1' } }).body.detail, 'bad_group_code');
  assert.equal(b.call('POST', '/me/group_code', { token: s.token, body: { code: ' ' + code.toLowerCase() } }).body.user.status, 'approved');
  assert.equal(b.call('POST', '/me', { token: s.token, body: { lang: 'mr' } }).body.user.lang, 'mr');
});

test('guessing the group code is limited per student; a rejected student stays rejected', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  for (let i = 0; i < 5; i++) b.call('POST', '/me/group_code', { token: s.token, body: { code: 'WRONG' + i } });
  assert.deepEqual(b.call('POST', '/me/group_code', { token: s.token, body: { code } }), { status: 429, body: { detail: 'too_many_attempts' } });
  const r = signup(b, '9000000003');
  b.call('POST', '/teacher/students/' + r.user.id + '/status', { token: t.token, body: { status: 'rejected' } });
  assert.equal(b.call('POST', '/me/group_code', { token: r.token, body: { code } }).body.user.status, 'rejected');
});

test('the teacher sees students, pending first, then the newest', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const a = signup(b, '9000000002', { code });
  b.state.offsetMs += 1000;
  const p = signup(b, '9000000003');
  b.state.offsetMs += 1000;
  const c = signup(b, '9000000004', { code });
  b.call('POST', '/sessions/' + classStarted(b, 10) + '/checkin', { token: a.token, body: { phase: 'before', mood: 3 } });
  const list = b.call('GET', '/teacher/students', { token: t.token }).body.students;
  assert.deepEqual(list.map((x) => x.id), [p.user.id, c.user.id, a.user.id]);
  assert.deepEqual(list.map((x) => x.joined), [0, 0, 1]);
  assert.deepEqual(Object.keys(list[0]), ['id', 'name', 'phone', 'role', 'status', 'lang', 'joined', 'created_at']);
  assert.match(list[0].created_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  assert.equal(b.call('GET', '/teacher/home', { token: t.token }).body.pending_students, 1);
  assert.deepEqual(b.call('POST', '/teacher/students/' + t.user.id + '/status', { token: t.token, body: { status: 'approved' } }),
    { status: 404, body: { detail: 'no_student' } });
  assert.equal(b.call('POST', '/teacher/students/' + p.user.id + '/status', { token: t.token, body: { status: 'maybe' } }).status, 422);
});

test('feedback reaches the insights with the name, newest first, at most twenty', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Student One' });
  for (let i = 0; i < 22; i++) {
    b.state.offsetMs += 1000;
    assert.deepEqual(b.call('POST', '/feedback', { token: s.token, body: { screen: 'today', text: ' note ' + i + ' ' } }).body, { ok: true });
  }
  const feedback = b.call('GET', '/teacher/insights', { token: t.token }).body.feedback;
  assert.equal(feedback.length, 20);
  assert.deepEqual(Object.keys(feedback[0]), ['screen', 'text', 'created_at', 'name']);
  assert.deepEqual([feedback[0].text, feedback[0].name, feedback[0].screen], ['note 21', 'Student One', 'today']);
  assert.equal(b.call('POST', '/feedback', { token: s.token, body: { screen: 'x'.repeat(41), text: 'hi' } }).status, 422);
  assert.equal(b.call('POST', '/feedback', { token: s.token, body: { screen: 'today', text: '' } }).status, 422);
});

test('the insights cover the last two weeks of classes', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  attend(b, s.user.id, 'pranayama', 3, 2, 4);
  attend(b, s.user.id, 'hatha', 20, 1, 5);
  const insights = b.call('GET', '/teacher/insights', { token: t.token }).body;
  assert.deepEqual(insights.sessions.filter((x) => x.joined).map((x) => x.class), ['Pranayama']);
  assert.ok(insights.sessions.every((x, i, all) => i === 0 || all[i - 1].starts_at >= x.starts_at));
  assert.equal(insights.mood_change, 3); // all time: (2 + 4) / 2
  assert.equal(insights.mood_pairs, 2);
});

test('the invite carries the group code', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const invite = b.call('GET', '/teacher/invite', { token: t.token, query: { lang: 'hi' } }).body;
  assert.ok(invite.text.includes('*' + code + '*'));
  assert.ok(invite.text.startsWith('🙏 ऐप में सत् चित् आनंद योग से जुड़ें।'));
  assert.equal(invite.group_link, null);
});

test('a new group code works and the old one does not', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const fresh = b.call('POST', '/teacher/group_code', { token: t.token }).body.group_code;
  assert.notEqual(fresh, code);
  assert.equal(b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_code, fresh); // not the cached one
  assert.equal(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000002', password: 'secret1', code } }).body.detail, 'bad_group_code');
  assert.equal(signup(b, '9000000003', { code: fresh }).user.status, 'approved');
});

test('the teacher home: a week of classes, with links and counts', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const home = b.call('GET', '/teacher/home', { token: t.token, query: { lang: 'mr' } }).body;
  assert.equal(home.sessions.length >= 6, true);
  assert.deepEqual(Object.keys(home.sessions[0]), ['id', 'starts_at', 'duration_min', 'class', 'meet_link', 'has_link', 'own_link', 'joined', 'curriculum']);
  assert.deepEqual(home.settings, { group_link: null, group_code: code, default_meet_link: null });
  const names = home.sessions.map((x) => x.class.name);
  assert.ok(names.every((name) => /[\u0900-\u097f]/.test(name)), names.join());
});

test('logging out ends that token only', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  const other = b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).body.token;
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 200);
  assert.deepEqual(b.call('POST', '/auth/logout', { token: s.token }), { status: 200, body: { ok: true } });
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 401);
  assert.equal(b.call('GET', '/me', { token: other }).status, 200);
  assert.deepEqual(b.call('POST', '/auth/logout', { token: 'nothing' }), { status: 200, body: { ok: true } });
  assert.deepEqual(b.call('POST', '/auth/logout'), { status: 200, body: { ok: true } });
});

test('a name is updated trimmed, and must not be empty', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  assert.equal(b.call('POST', '/me', { token: s.token, body: { name: '  Student 1  ' } }).body.user.name, 'Student 1');
  assert.equal(b.call('POST', '/me', { token: s.token, body: { name: '' } }).status, 422);
  assert.equal(b.call('POST', '/me', { token: s.token, body: { lang: 'fr' } }).status, 422);
  assert.equal(b.call('POST', '/me', { token: s.token, body: {} }).body.user.name, 'Student 1');
  assert.equal(b.call('GET', '/me', { token: s.token }).body.user.name, 'Student 1');
});

test('the studio in three languages', () => {
  const b = freshBackend();
  const en = b.call('GET', '/studio').body;
  assert.deepEqual(Object.keys(en), ['name', 'tagline', 'since', 'teacher', 'classes', 'weekly', 'class_start_ist', 'duration_min']);
  assert.equal(en.weekly[0].day, 'mon');
  assert.equal(en.weekly[6].class.key, 'satsang');
  assert.equal(b.call('GET', '/studio', { query: { lang: 'hi' } }).body.classes[0].name, 'हठ योग');
  assert.equal(b.call('GET', '/studio?lang=mr').body.classes[0].name, 'हठयोग');
});

test('the week of classes is made once, at 8:00 India time, on the weekly rhythm', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  b.call('GET', '/teacher/home', { token: t.token });
  const locks = b.state.locks;
  b.call('GET', '/teacher/home', { token: t.token });
  assert.equal(b.state.locks, locks, 'no lock when the week is there');
  const rows = b.ss.getSheetByName('class_sessions').rows().slice(1);
  assert.equal(rows.length, 7);
  const days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const weekly = JSON.parse(b.evaluate('JSON.stringify(STUDIO.weekly)'));
  for (const row of rows) {
    const india = new Date(row[2].getTime() + 330 * MIN);
    assert.deepEqual([india.getUTCHours(), india.getUTCMinutes()], [8, 0]);
    assert.equal(row[1], weekly[days[india.getUTCDay()]]);
  }
  b.state.offsetMs += DAY;
  b.call('GET', '/teacher/home', { token: t.token });
  assert.equal(b.ss.getSheetByName('class_sessions').rows().length - 1, 8);
});
