// The API end to end through the envelope, route by route: sign-up and login, links, check-ins, the teacher's routes.
import assert from 'node:assert/strict';
import test from 'node:test';
import { attend, classStarted, DAY, freshBackend, MIN, setSetting, setting, signup, teacherAndCode, WEDNESDAY_6AM } from './helpers.mjs';

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

test('a student signs up with the group code, in any case, and waits to be placed in a batch', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const r = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000002', password: 'secret1', code: ' ' + code.toLowerCase() } });
  assert.equal(r.status, 200);
  assert.deepEqual([r.body.user.status, r.body.user.batch, r.body.user.batch_since], ['pending', null, null]);
  for (const bad of ['', 'WRONG1']) {
    const refused = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000004', password: 'secret1', code: bad } });
    assert.deepEqual(refused, { status: 400, body: { detail: 'bad_group_code' } }, bad);
  }
});

test('one account per number, and logging in however it is typed', () => {
  const b = freshBackend();
  signup(b, '+91 90000 00002');
  const again = b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000002', password: 'secret1', code: setting(b, 'group_code') } });
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
  for (const typed of ['98765 43210', '098765 43210', '+91 98765-43210', '0091 98765 43210', '919876543210', '९८७६५ ४३२१०',
    '+91 098765 43210', '0091 098765 43210']) {
    assert.equal(b.evaluate('normalizePhone_(' + JSON.stringify(typed) + ')'), '+919876543210', typed);
  }
  for (const [typed, number] of [['+44 20 7946 0958', '+442079460958'], ['+44 7911 123456', '+447911123456'], ['+1 415 555 1234', '+14155551234'],
    ['+971 50 123 4567', '+971501234567'], ['00971 50 123 4567', '+971501234567']]) {
    assert.equal(b.evaluate('normalizePhone_(' + JSON.stringify(typed) + ')'), number, typed);
  }
  for (const bad of ['12345', '0123456789012', '+1234567890123456', 'abc', '']) {
    assert.throws(() => b.evaluate('normalizePhone_(' + JSON.stringify(bad) + ')'), /bad_phone/, bad);
  }
});

test('an account stored with the trunk 0 after +91 still logs in, however the number is typed, and keeps its number', () => {
  const b = freshBackend();
  signup(b, '9000000002');
  const users = b.ss.getSheetByName('users');
  const row = users.rows().findIndex((r) => r[2] === '+919000000002') + 1;
  users.getRange(row, 3).setValue("'+9109000000002"); // "+91 090000 00002" stored with its trunk 0
  b.context.onEdit({});
  for (const typed of ['+91 090000 00002', '9000000002', '09000000002', '+91 90000 00002']) {
    const r = b.call('POST', '/auth/login', { body: { phone: typed, password: 'secret1' } });
    assert.deepEqual([r.status, r.body.user.phone], [200, '+9109000000002'], typed);
  }
  assert.deepEqual(b.call('POST', '/auth/signup', { body: { name: 'x', phone: '9000000002', password: 'secret1', code: setting(b, 'group_code') } }),
    { status: 409, body: { detail: 'phone_taken' } });
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

test('a pending student sees no classes; placed in a batch, only that batch\'s, with their links', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM }); // the day's classes all ahead
  const { t } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  assert.deepEqual(b.call('GET', '/home', { token: s.token }).body.sessions, []);
  const sessions = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  const mine = sessions.find((x) => x.batch.key === 'intermediate');
  const other = sessions.find((x) => x.batch.key === 'beginner');
  const r = b.call('PUT', '/teacher/sessions/' + mine.id, { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } });
  assert.equal(r.status, 200);
  assert.ok(r.body.text.includes('Intermediate') && r.body.text.includes('https://meet.google.com/abc-defg-hij'), r.body.text);
  assert.deepEqual(Object.keys(r.body), ['text']);
  assert.deepEqual(b.call('POST', '/sessions/' + mine.id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }),
    { status: 403, body: { detail: 'pending' } });
  const approve = (token = t.token) => b.call('POST', '/teacher/students/' + s.user.id + '/status', { token, body: { status: 'approved' } });
  assert.deepEqual(approve(), { status: 400, body: { detail: 'needs_batch' } });
  const placed = b.call('PUT', '/teacher/students/' + s.user.id + '/batch', { token: t.token, body: { batch: 'intermediate', note: 'Holds Trikonasana well' } });
  assert.deepEqual([placed.status, placed.body.student.status, placed.body.student.batch], [200, 'approved', 'intermediate']);
  const home = b.call('GET', '/home', { token: s.token }).body;
  assert.deepEqual([home.batch.key, home.batch.name, home.batch.time], ['intermediate', 'Intermediate', '08:00']);
  assert.ok(home.sessions.length > 0 && home.sessions.every((x) => x.batch.key === 'intermediate'));
  assert.equal(home.sessions.find((x) => x.id === mine.id).meet_link, 'https://meet.google.com/abc-defg-hij');
  assert.deepEqual(b.call('POST', '/sessions/' + other.id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }),
    { status: 403, body: { detail: 'other_batch' } });
});

test('a student moved after joining a class can still say how it went, and joins only the new batch', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000031', { code, batch: 'beginner' });
  const joined = classStarted(b, 50, 'beginner'); // under way, 5 minutes left: both check-ins open
  const checkin = (id, phase) => b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase, mood: 4 } });
  assert.equal(checkin(joined, 'before').status, 200);
  const move = b.call('PUT', '/teacher/students/' + s.user.id + '/batch', { token: t.token, body: { batch: 'intermediate', note: 'Ready' } });
  assert.equal(move.status, 200);
  assert.equal(checkin(joined, 'after').status, 200, 'the mood after the class joined before the move');
  const practice = b.call('POST', '/sessions/' + joined + '/practice', { token: s.token, body: { entries: [{ item: 'tadasana', reaction: 3 }] } });
  assert.deepEqual(practice, { status: 200, body: { ok: true, saved: 1 } });
  assert.deepEqual(checkin(classStarted(b, -30, 'beginner'), 'before'), { status: 403, body: { detail: 'other_batch' } },
    'a class of the old batch that starts after the move');
});

test('a removed student gets nothing class-related, not even the class they joined', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000032', { code, batch: 'beginner' });
  const joined = classStarted(b, 50, 'beginner');
  assert.equal(b.call('POST', '/sessions/' + joined + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  assert.equal(b.call('GET', '/home', { token: s.token }).body.after_checkin.id, joined);
  assert.equal(b.call('POST', '/teacher/students/' + s.user.id + '/status', { token: t.token, body: { status: 'rejected' } }).status, 200);
  const home = b.call('GET', '/home', { token: s.token }).body;
  assert.deepEqual([home.user.status, home.batch, home.sessions, home.after_checkin, home.group_link], ['rejected', null, [], null, null]);
});

test('bad links are refused', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const session = b.call('GET', '/teacher/home', { token: t.token }).body.sessions[0];
  const r = b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: 'https://evil.example/meet' } });
  assert.deepEqual(r, { status: 400, body: { detail: 'bad_meet_link' } });
  assert.equal(b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'not a link' } }).body.detail, 'bad_group_link');
  const ok = b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'https://chat.whatsapp.com/AbC123' } });
  assert.equal(ok.body.group_link, 'https://chat.whatsapp.com/AbC123');
  assert.equal(b.call('PUT', '/teacher/batches/beginner', { token: t.token, body: { meet_link: 'https://evil.example/meet' } }).body.detail, 'bad_meet_link');
  assert.deepEqual(b.call('PUT', '/teacher/batches/nope', { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } }),
    { status: 404, body: { detail: 'no_batch' } });
  for (const link of ['zoom.us/j/123456789', 'https://us02web.zoom.us/j/8765?pwd=ab.C-d_9', 'http://meet.google.com/abc-defg-hij']) {
    assert.equal(b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: link } }).status, 200, link);
  }
  for (const link of ['https://meet.google.com/abc-defg-hij/x', 'https://meet.google.com/abcd-efg-hij', 'https://zoom.us/j/abc', 'https://zoom.us/',
    'https://teams.microsoft.com/', 'https://meet.jit.si/', 'https://youtube.com/watch?v=abc', 'meet google com', '', null]) {
    assert.equal(b.call('PUT', '/teacher/sessions/' + session.id, { token: t.token, body: { meet_link: link } }).body.detail, 'bad_meet_link', link);
  }
});

test('the call links people paste are taken, made plain', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const meet = 'https://meet.google.com/abc-defg-hij';
  const cases = [
    ['https://meet.google.com/abc-defg-hij?authuser=0', meet], ['https://meet.google.com/abc-defg-hij?pli=1', meet],
    ['meet.google.com/abc-defg-hij/', meet], ['https://meet.google.com/ABC-DEFG-HIJ', meet], ['HTTPS://Meet.Google.com/abc-defg-hij', meet],
    ['Join: https://meet.google.com/abc-defg-hij.', meet], ['https://g.co/meet/abc-defg-hij', meet], ['g.co/meet/yoga-morning', 'https://g.co/meet/yoga-morning'],
    ['https://us02web.zoom.us/j/12345678901?pwd=AbCd.1', 'https://us02web.zoom.us/j/12345678901?pwd=AbCd.1'],
    ['https://zoom.us/j/123?pwd=a&uname=x', 'https://zoom.us/j/123?pwd=a'], ['zoom.us/j/98765432100', 'https://zoom.us/j/98765432100'],
    ['https://us02web.zoom.us/j/1234567890?pwd=a%3Db', 'https://us02web.zoom.us/j/1234567890?pwd=a%3Db'],
    ['https://zoom.us/my/ramit', 'https://zoom.us/my/ramit'], ['https://us06web.zoom.us/my/ramit.yoga', 'https://us06web.zoom.us/my/ramit.yoga'],
    ['https://teams.microsoft.com/meet/2345678?p=abc&x=1', 'https://teams.microsoft.com/meet/2345678?p=abc'],
    ['https://teams.microsoft.com/l/meetup-join/19%3ameeting_ab%40thread.v2/0?context=%7b%22Tid%22%3a%22x%22%7d',
      'https://teams.microsoft.com/l/meetup-join/19%3ameeting_ab%40thread.v2/0?context=%7b%22Tid%22%3a%22x%22%7d'],
    ['teams.live.com/meet/9876543210?p=AbC', 'https://teams.live.com/meet/9876543210?p=AbC'],
    ['https://meet.jit.si/SattChitt', 'https://meet.jit.si/SattChitt'], ['http://meet.jit.si/SattChitt', 'https://meet.jit.si/SattChitt'],
  ];
  for (const [pasted, kept] of cases) {
    const r = b.call('PUT', '/teacher/batches/beginner', { token: t.token, body: { meet_link: pasted } });
    assert.deepEqual(r, { status: 200, body: { ok: true, meet_link: kept } }, pasted);
  }
});

test('the class group link is optional: any group, any https link, and cleared by an empty one', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const save = (body) => b.call('PUT', '/teacher/settings', { token: t.token, body });
  const cases = [
    ['chat.whatsapp.com/AbC123', 'https://chat.whatsapp.com/AbC123'], ['https://chat.whatsapp.com/AbC123?mode=r_c', 'https://chat.whatsapp.com/AbC123'],
    ['https://chat.whatsapp.com/invite/AbC123', 'https://chat.whatsapp.com/AbC123'], ['https://t.me/joinchat/AbC123', 'https://t.me/joinchat/AbC123'],
    ['telegram.me/sattchitt', 'https://telegram.me/sattchitt'], ['https://signal.group/#CjQKIAb_c-D', 'https://signal.group/#CjQKIAb_c-D'],
    ['signal.group/#CjQKIA', 'https://signal.group/#CjQKIA'],
    ['https://example.com', 'https://example.com'], ['Join our group: t.me/joinchat/xyz', 'https://t.me/joinchat/xyz'],
    ['Hi Mr.Sharma, our group https://t.me/x', 'https://t.me/x'], ['http://classroom.example.org/c/yoga?x=1', 'https://classroom.example.org/c/yoga?x=1'],
  ];
  for (const [pasted, kept] of cases) {
    assert.deepEqual(save({ group_link: pasted }).body, { group_link: kept, group_code: setting(b, 'group_code') }, pasted);
    assert.equal(setting(b, 'group_link'), kept);
  }
  for (const bad of ['not a link', 'chat.whatsapp.com/', 'javascript:alert(1)', 'Mr.Sharma', 'e.g.', '7.00', 'example.com', 'https://7.00/x']) {
    assert.deepEqual(save({ group_link: bad }), { status: 400, body: { detail: 'bad_group_link' } }, bad);
    assert.equal(setting(b, 'group_link'), 'https://classroom.example.org/c/yoga?x=1', 'a refused link changes nothing');
  }
  assert.equal(save({}).body.group_link, 'https://classroom.example.org/c/yoga?x=1', 'left out: unchanged');
  assert.equal(save({ group_link: '' }).body.group_link, null);
  assert.ok(!setting(b, 'group_link'));
  save({ group_link: 't.me/x' });
  assert.equal(save({ group_link: null }).body.group_link, null);
  assert.equal(b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_link, null);
});

test('a batch\'s everyday link can be removed', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const set = (meet_link) => b.call('PUT', '/teacher/batches/beginner', { token: t.token, body: { meet_link } });
  set('meet.google.com/abc-defg-hij');
  assert.deepEqual(set('').body, { ok: true, meet_link: null });
  set('meet.google.com/abc-defg-hij');
  assert.deepEqual(set(null).body, { ok: true, meet_link: null });
  assert.equal(b.call('GET', '/teacher/home', { token: t.token }).body.batches[0].meet_link, null);
});

test('a batch\'s everyday link serves its classes without their own; a class\'s own link wins', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const set = b.call('PUT', '/teacher/batches/beginner', { token: t.token, body: { meet_link: 'meet.google.com/xyz-abcd-efg' } });
  assert.deepEqual(set.body, { ok: true, meet_link: 'https://meet.google.com/xyz-abcd-efg' });
  const s = signup(b, '9000000002', { code });
  const sessions = () => b.call('GET', '/home', { token: s.token }).body.sessions;
  assert.ok(sessions().every((x) => x.meet_link === 'https://meet.google.com/xyz-abcd-efg'));
  const home = b.call('GET', '/teacher/home', { token: t.token }).body;
  assert.ok(home.sessions.filter((x) => x.batch.key === 'beginner').every((x) => x.own_link === false && x.has_link));
  assert.ok(home.sessions.filter((x) => x.batch.key !== 'beginner').every((x) => !x.has_link));
  assert.equal(home.batches.find((x) => x.key === 'beginner').meet_link, 'https://meet.google.com/xyz-abcd-efg');
  const first = sessions()[0];
  b.call('PUT', '/teacher/sessions/' + first.id, { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } });
  assert.equal(sessions()[0].meet_link, 'https://meet.google.com/abc-defg-hij');
  assert.equal(sessions()[1].meet_link, 'https://meet.google.com/xyz-abcd-efg');
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
  assert.deepEqual(insights.students, { approved: 1 });
  const row = insights.sessions.find((x) => x.id === id);
  assert.deepEqual([row.class, row.joined, row.mood_before, row.mood_after], ['Beginner', 1, 2, 5]);
  const mr = b.call('GET', '/teacher/insights', { token: t.token, query: { lang: 'mr' } }).body;
  assert.equal(mr.sessions.find((x) => x.id === id).class, 'नवशिके', 'the batch names in the language asked');
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
  assert.equal(rows[0][5], 'Beginner'); // the copy for the owner's queries
});

test('the after check-in is offered once class ends, with what was said, to be changed until the window closes', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 50);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } });
  const home = () => b.call('GET', '/home', { token: s.token }).body.after_checkin;
  assert.deepEqual([home().id, home().meet_link, home().said], [id, null, null]);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 4 } });
  assert.deepEqual(home().said, { mood: 4, items: [] }, 'answered: still offered, to change');
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 5 } });
  assert.equal(home().said.mood, 5, 'a second answer replaces the first');
  b.state.offsetMs += 13 * 3600000;
  assert.equal(home(), null, 'the window has closed');
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
  const other = classStarted(b, 50, 'intermediate');
  assert.equal(b.call('POST', '/sessions/' + other + '/checkin', { token: s.token, body: { phase: 'after', mood: 3 } }).body.detail,
    'checkin_closed'); // another batch's class, not joined
  const soon = classStarted(b, -55);
  assert.equal(b.call('POST', '/sessions/' + soon + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  assert.deepEqual(b.call('POST', '/sessions/424242/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }),
    { status: 404, body: { detail: 'no_session' } });
});

test('the streak counts the batch\'s classes in a row the student came to', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const mate = signup(b, '9000000003', { code });
  for (const daysAgo of [1, 2, 3, 5]) attend(b, s.user.id, 'beginner', daysAgo, 3, 4);
  attend(b, mate.user.id, 'beginner', 4, 3, 4); // the class missed: a classmate came, so it was held
  const stats = b.call('GET', '/me', { token: s.token }).body.stats;
  assert.deepEqual(stats, { classes_joined: 4, streak_days: 3, mood_change: 1, mood_pairs: 4 });
  const live = classStarted(b, 20); // under way, the classmate in it: not missed yet
  b.call('POST', '/sessions/' + live + '/checkin', { token: mate.token, body: { phase: 'before', mood: 3 } });
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 3);
  attend(b, s.user.id, 'beginner', 0, 2, null); // checked in to a class under way: it counts already
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 4);
  assert.equal(b.call('GET', '/me', { token: mate.token }).body.stats.streak_days, 1, 'the classmate: today\'s, then yesterday\'s missed');
});

test('a Mon, Wed, Fri batch: the streak goes up each class, over the days between and the weekend', () => {
  const monday = Date.parse('2026-11-16T10:30:00Z'); // 16:00 in India, before Pain management at 17:30
  const b = freshBackend({ now: monday });
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000004', { code, batch: 'pain_management' });
  const checkIn = (days) => {
    b.state.offsetMs = days * DAY + 85 * MIN; // 17:25, five minutes before class
    const next = b.call('GET', '/home', { token: s.token }).body.sessions[0];
    return b.call('POST', '/sessions/' + next.id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).body.stats.streak_days;
  };
  assert.deepEqual([checkIn(0), checkIn(2), checkIn(4)], [1, 2, 3], 'Monday, Wednesday, Friday');
  b.state.offsetMs = 7 * DAY; // the next Monday, 16:00: no class since Friday's
  b.call('GET', '/teacher/home', { token: t.token });
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 3);
  b.state.offsetMs = 7 * DAY + 2 * 60 * MIN + 30 * MIN; // 18:30, Monday's class over and missed, but nobody came: not held
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 3);
});

test('a move between batches keeps the streak: each class counts in the batch the student was in then', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const mate = signup(b, '9000000003', { code, batch: 'intermediate' });
  for (const daysAgo of [3, 2]) attend(b, s.user.id, 'beginner', daysAgo, 3, 4);
  b.state.offsetMs = -36 * 3600000; // a day and a half ago, after those two
  assert.equal(b.call('PUT', '/teacher/students/' + s.user.id + '/batch', { token: t.token, body: { batch: 'intermediate' } }).status, 200);
  b.state.offsetMs = 0;
  attend(b, mate.user.id, 'beginner', 1, 3, 4); // Beginner's class after the move: no longer the student's
  attend(b, s.user.id, 'intermediate', 1, 3, 4);
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 3);
  attend(b, mate.user.id, 'intermediate', 2, 3, 4); // Intermediate's class before the move: not the student's then
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.streak_days, 3);
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

test('a student moves between batches after a review; each move is logged with the teacher\'s note', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const move = (batch, note, token = t.token) => b.call('PUT', '/teacher/students/' + s.user.id + '/batch', { token, body: { batch, note } });
  b.state.offsetMs += DAY;
  assert.equal(move('intermediate', '  Ready for longer holds ').status, 200);
  const me = b.call('GET', '/me', { token: s.token }).body.user;
  assert.deepEqual([me.batch, me.batch_since], ['intermediate', new Date(b.clock()).toISOString().replace('.000', '')]);
  assert.deepEqual(move('expert', null).body, { detail: 'no_batch' });
  assert.deepEqual(move('beginner', null, s.token), { status: 403, body: { detail: 'teacher_only' } });
  assert.equal(b.call('PUT', '/teacher/students/' + t.user.id + '/batch', { token: t.token, body: { batch: 'beginner' } }).body.detail, 'no_student');
  const log = b.ss.getSheetByName('batch_changes').rows().slice(1);
  assert.deepEqual(log.map((r) => [r[1], r[2], r[3], r[4]]), [[s.user.id, 'beginner', 'intermediate', 'Ready for longer holds']]);
  assert.equal(b.call('POST', '/me', { token: s.token, body: { lang: 'mr' } }).body.user.lang, 'mr');
});

test('guessing the group code at sign-up is limited per number; a removed student can be taken back into their batch', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const attempt = (phone, c) => b.call('POST', '/auth/signup', { body: { name: 'x', phone, password: 'secret1', code: c } });
  for (let i = 0; i < 5; i++) assert.equal(attempt('9000000002', 'WRONG' + i).body.detail, 'bad_group_code');
  assert.deepEqual(attempt('9000000002', code), { status: 429, body: { detail: 'too_many_attempts' } });
  assert.equal(attempt('9000000003', code).status, 200, 'another number is not locked');
  b.state.offsetMs += 15 * MIN + 1000;
  assert.equal(attempt('9000000002', code).status, 200);
  const r = signup(b, '9000000004', { code });
  const status = (value) => b.call('POST', '/teacher/students/' + r.user.id + '/status', { token: t.token, body: { status: value } });
  assert.equal(status('rejected').status, 200);
  assert.equal(b.call('GET', '/me', { token: r.token }).body.user.status, 'rejected');
  assert.equal(status('approved').status, 200);
  assert.deepEqual(['approved', 'beginner'], ['status', 'batch'].map((k) => b.call('GET', '/me', { token: r.token }).body.user[k]));
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
  assert.deepEqual(Object.keys(list[0]), ['id', 'name', 'phone', 'role', 'status', 'lang', 'batch', 'batch_since', 'joined', 'intake']);
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
  attend(b, s.user.id, 'intermediate', 3, 2, 4);
  attend(b, s.user.id, 'beginner', 20, 1, 5);
  const insights = b.call('GET', '/teacher/insights', { token: t.token }).body;
  assert.deepEqual(insights.sessions.filter((x) => x.joined).map((x) => x.class), ['Intermediate']);
  assert.ok(insights.sessions.every((x, i, all) => i === 0 || all[i - 1].starts_at >= x.starts_at));
  assert.equal(insights.mood_change, 3); // all time: (2 + 4) / 2
  assert.equal(insights.mood_pairs, 2);
});

test('the invite carries the group code, as plain text for any app, and where to get the app once the owner sets it', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const invite = (lang) => b.call('GET', '/teacher/invite', { token: t.token, query: { lang } }).body;
  assert.deepEqual(invite('en'), { text: '🙏 Join Satt Chitt Anand Yoga in the app.\nSign up with your phone number and this group code: ' + code });
  assert.ok(invite('hi').text.startsWith('🙏 ऐप में सत्·चित्·आनन्द योग से जुड़ें।\nअपने फ़ोन नंबर'));
  assert.ok(!invite('mr').text.includes('*'), 'no stars: they show as stars in an SMS');
  setSetting(b, 'app_link', 'https://example.org/sca.apk');
  assert.equal(invite('en').text, '🙏 Join Satt Chitt Anand Yoga in the app.\n📲 Get the app: https://example.org/sca.apk\n' +
    'Sign up with your phone number and this group code: ' + code);
  assert.ok(invite('mr').text.includes('📲 ॲप इथून घ्या: https://example.org/sca.apk\n'));
});

test('a group code pasted with stars, spaces or a full stop around it works, and is not counted as a wrong one', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const attempt = (phone, c) => b.call('POST', '/auth/signup', { body: { name: 'x', phone, password: 'secret1', code: c } });
  for (let i = 0; i < 4; i++) assert.equal(attempt('9000000002', 'WRONG' + i).body.detail, 'bad_group_code');
  assert.equal(attempt('9000000002', ' *' + code + '*. ').status, 200, 'the fifth try, right: no lockout');
  assert.equal(attempt('9000000003', code.toLowerCase() + '.').status, 200);
  assert.equal(attempt('9000000005', '"' + code + '"').status, 200);
  assert.equal(attempt('9000000006', code.slice(0, 3) + ' ' + code.slice(3)).body.detail, 'bad_group_code', 'a space inside is not forgiven');
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

test('the teacher home: the next day\'s classes, every batch\'s, with links and counts, and the batches', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const { t, code } = teacherAndCode(b);
  const home = b.call('GET', '/teacher/home', { token: t.token, query: { lang: 'mr' } }).body;
  assert.deepEqual(home.sessions.map((x) => x.batch.key), ['beginner', 'intermediate', 'advanced', 'pain_management']); // Wednesday
  assert.deepEqual(Object.keys(home.sessions[0]), ['id', 'starts_at', 'duration_min', 'batch', 'meet_link', 'has_link', 'own_link', 'joined', 'curriculum']);
  assert.deepEqual(home.sessions.map((x) => x.curriculum), ['beginner', 'intermediate', 'advanced', 'pain_management']);
  assert.deepEqual(home.settings, { group_link: null, group_code: code });
  assert.deepEqual(home.batches.map((x) => [x.key, x.name, x.time, x.meet_link]), [['beginner', 'नवशिके', '07:00', null],
    ['intermediate', 'मध्यम', '08:00', null], ['advanced', 'प्रगत', '09:00', null], ['pain_management', 'वेदना व्यवस्थापन', '17:30', null]]);
  b.state.offsetMs += 13 * 3600000; // 19:00, the day's classes over (Pain management ends at 18:15): Thursday's
  const thursday = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  assert.deepEqual(thursday.map((x) => x.batch.key), ['beginner', 'intermediate', 'advanced'], 'no Pain management on Thursdays');
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

test('the studio in three languages, with its batches', () => {
  const b = freshBackend();
  const en = b.call('GET', '/studio').body;
  assert.deepEqual(Object.keys(en), ['name', 'tagline', 'since', 'teacher', 'batches']);
  assert.deepEqual(en.batches.map((x) => x.key), ['beginner', 'intermediate', 'advanced', 'pain_management']);
  assert.deepEqual(en.batches[3].days, ['mon', 'wed', 'fri']);
  assert.equal(b.call('GET', '/studio', { query: { lang: 'hi' } }).body.batches[3].name, 'दर्द प्रबंधन');
  assert.equal(b.call('GET', '/studio?lang=mr').body.batches[0].name, 'नवशिके');
});

test('each batch\'s classes are made once, on its days, at its time in India', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const { t } = teacherAndCode(b);
  b.call('GET', '/teacher/home', { token: t.token });
  const locks = b.state.locks;
  b.call('GET', '/teacher/home', { token: t.token });
  assert.equal(b.state.locks, locks, 'no lock when the week is there');
  const rows = b.ss.getSheetByName('class_sessions').rows().slice(1);
  assert.equal(rows.length, 3 * 6 + 3); // Wednesday to Tuesday: six days of three batches, three days of Pain management
  const days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const want = { beginner: [7, 0, 55], intermediate: [8, 0, 55], advanced: [9, 0, 55], pain_management: [17, 30, 45] };
  for (const row of rows) {
    const india = new Date(row[2].getTime() + 330 * MIN);
    assert.deepEqual([india.getUTCHours(), india.getUTCMinutes(), row[3]], want[row[1]], row[1]);
    assert.notEqual(days[india.getUTCDay()], 'sun');
    if (row[1] === 'pain_management') assert.ok(['mon', 'wed', 'fri'].includes(days[india.getUTCDay()]));
  }
  b.state.offsetMs += DAY; // Thursday: the next Wednesday's four come in
  b.call('GET', '/teacher/home', { token: t.token });
  assert.equal(b.ss.getSheetByName('class_sessions').rows().length - 1, 21 + 4);
});

test('the owner\'s edits to the batches tab are the schedule: new days, a time typed as a time', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const { t } = teacherAndCode(b);
  const sheet = b.ss.getSheetByName('batches');
  const header = sheet.rows()[0];
  sheet.getRange(5, header.indexOf('days') + 1).setValue("'Tue, Thu");
  // 18:00 typed as a time of day: Sheets dates it 30 December 1899, when India's offset was +5:21:10
  sheet.getRange(5, header.indexOf('time') + 1).setValue(new Date(Date.parse('1899-12-30T12:38:50Z')));
  b.context.onEdit({});
  const pain = b.call('GET', '/studio').body.batches[3];
  assert.deepEqual([pain.days, pain.time], [['tue', 'thu'], '18:00']);
  b.call('GET', '/teacher/home', { token: t.token });
  const starts = b.ss.getSheetByName('class_sessions').rows().slice(1).filter((r) => r[1] === 'pain_management')
    .map((r) => new Date(r[2].getTime() + 330 * MIN));
  assert.deepEqual(starts.map((d) => [d.getUTCDay(), d.getUTCHours()]), [[4, 18], [2, 18]], 'Thursday and Tuesday; Monday\'s, Wednesday\'s and Friday\'s removed');
});

test('a time the owner types reads as typed, whatever the cell: text, a time of day dated 1899, or 5:30 pm', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const { t } = teacherAndCode(b);
  const sheet = b.ss.getSheetByName('batches');
  const column = sheet.rows()[0].indexOf('time') + 1;
  const type = (row, value) => sheet.getRange(row, column).setValue(value);
  type(2, new Date(Date.parse('1899-12-30T01:38:50Z'))); // 07:00, as Sheets keeps a time of day: +5:21:10 that year
  type(3, "'8.15");
  type(4, "'5:30 pm");
  type(5, 0.75); // 18:00 as a fraction of a day
  b.context.onEdit({});
  assert.deepEqual(b.call('GET', '/studio').body.batches.map((x) => x.time), ['07:00', '08:15', '17:30', '18:00']);
  const beginner = b.call('GET', '/teacher/home', { token: t.token }).body.sessions.find((s) => s.batch.key === 'beginner');
  assert.equal(beginner.starts_at, '2026-11-18T01:30:00Z', '7:00 in India');
  for (const [typed, minutes] of [['07:00', 420], ['7 am', 420], ['7:05 AM', 425], ['12:30 pm', 750], ['12 am', 0], ['17:30', 1050], ['08:00 IST', 480]]) {
    assert.equal(b.evaluate('startMinutes_(' + JSON.stringify(typed) + ')'), minutes, typed);
  }
});

test('setup makes the batches\' times plain text, keeping a time Sheets took as a time of day as the text it showed', () => {
  const b = freshBackend();
  const sheet = b.ss.getSheetByName('batches');
  const column = sheet.rows()[0].indexOf('time') + 1;
  sheet.getRange(3, column).setValue(new Date(Date.parse('1899-12-30T02:38:50Z'))); // 08:00
  b.context.setup();
  assert.deepEqual(sheet.rows().slice(1).map((r) => r[column - 1]), ['07:00', '08:00', '09:00', '17:30']);
});

test('the first view that makes a day\'s classes shows each with its curriculum', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const t = signup(b, '9000000001', { role: 'teacher', code: 'TEACH123' });
  assert.deepEqual(b.call('GET', '/teacher/home', { token: t.token }).body.sessions.map((s) => s.curriculum),
    ['beginner', 'intermediate', 'advanced', 'pain_management']);
  const s = signup(b, '9000000002', { code: setting(b, 'group_code') });
  b.state.offsetMs = 7 * DAY; // a week on: the student's visit makes the new day's classes
  const sessions = b.call('GET', '/home', { token: s.token }).body.sessions;
  assert.ok(sessions.length === 6 && sessions.every((x) => x.curriculum === 'beginner'), JSON.stringify(sessions.map((x) => x.curriculum)));
});

test('after class, one who joined from the class\'s message, with no check-in, can still say how it went: that records coming', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const mate = signup(b, '9000000003', { code });
  const id = classStarted(b, 50); // five minutes left: the after-class window is open
  b.call('POST', '/sessions/' + id + '/checkin', { token: mate.token, body: { phase: 'before', mood: 2 } });
  const home = () => b.call('GET', '/home', { token: s.token }).body;
  assert.equal(home().after_checkin, null, 'for the apps that offer only a class checked in to');
  assert.deepEqual([home().after_class.id, home().after_class.checked_in, home().after_class.said], [id, false, null]);
  const after = b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 4 } });
  assert.deepEqual(after.body.stats, { classes_joined: 1, streak_days: 1, mood_change: null, mood_pairs: 0 });
  const rows = b.ss.getSheetByName('checkins').rows().slice(1).filter((r) => r[0] === s.user.id);
  assert.deepEqual(rows.map((r) => [r[2], r[3], r[5]]), [['before', '', 'Beginner'], ['after', 4, 'Beginner']], 'coming, with no mood before');
  assert.deepEqual([home().after_checkin.id, home().after_class.checked_in, home().after_class.said.mood], [id, true, 4]);
  const insights = b.call('GET', '/teacher/insights', { token: t.token }).body;
  const row = insights.sessions.find((x) => x.id === id);
  assert.deepEqual([row.joined, row.mood_before, row.mood_after, insights.mood_pairs], [2, 2, 4, 0]);
  const practice = b.call('GET', '/me/practice', { token: s.token }).body;
  assert.deepEqual([practice.classes_joined, practice.average_mood_before, practice.average_mood_after], [1, null, 4]);
  assert.deepEqual(practice.classes.map((c) => [c.mood_before, c.mood_after]), [[null, 4]]);
  assert.equal(b.call('GET', '/teacher/sessions/' + id + '/practice', { token: t.token }).body.joined, 2);
});

test('saying how each item went, with no check-in, records coming too; another batch\'s class stays closed', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 60); // just over
  const said = b.call('POST', '/sessions/' + id + '/practice', { token: s.token, body: { entries: [{ item: 'tadasana', reaction: 3 }] } });
  assert.deepEqual(said, { status: 200, body: { ok: true, saved: 1 } });
  assert.equal(b.call('GET', '/me', { token: s.token }).body.stats.classes_joined, 1);
  b.call('POST', '/sessions/' + id + '/practice', { token: s.token, body: { entries: [{ item: 'tadasana', reaction: 4 }] } });
  assert.equal(b.ss.getSheetByName('checkins').rows().length - 1, 1, 'recorded once');
  const other = classStarted(b, 60, 'intermediate');
  assert.equal(b.call('POST', '/sessions/' + other + '/practice', { token: s.token, body: { entries: [] } }).body.detail, 'checkin_closed');
  b.state.offsetMs = 13 * 3600000;
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'after', mood: 3 } }).body.detail, 'checkin_closed');
});

test('a check-in takes the lock once, and answers busy when it stays taken', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const id = classStarted(b, 10);
  b.state.lockFree = false; // another write holds it
  assert.deepEqual(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }), { status: 503, body: { detail: 'busy' } });
  b.state.lockFree = true;
  const locks = b.state.locks;
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  assert.deepEqual([b.state.locks, b.state.lockHeld], [locks + 1, 0]);
});

test('a student changes their own password: the current one first, under the login\'s brake; this login stays', () => {
  const b = freshBackend();
  const s = signup(b, '9000000002');
  const other = b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).body.token;
  const change = (current, next, token = s.token) => b.call('POST', '/me/password', { token, body: { current_password: current, new_password: next } });
  assert.deepEqual(change('wrong!', 'better1'), { status: 400, body: { detail: 'bad_password' } });
  assert.equal(change('secret1', 'short').status, 422);
  assert.deepEqual(change('secret1', 'better1'), { status: 200, body: { ok: true } });
  assert.equal(b.call('GET', '/me', { token: s.token }).status, 200, 'this login stays signed in');
  assert.deepEqual(b.call('GET', '/me', { token: other }), { status: 401, body: { detail: 'signed_out' } }, 'every other is signed out');
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).status, 401);
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'better1' } }).status, 200);
  for (let i = 0; i < 5; i++) change('wrong!', 'better2');
  assert.deepEqual(change('better1', 'better2'), { status: 429, body: { detail: 'too_many_attempts' } });
  assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'better1' } }).body.detail, 'too_many_attempts', 'the same brake');
  b.state.offsetMs += 15 * MIN + 1000;
  assert.deepEqual(change('better1', 'better2'), { status: 200, body: { ok: true } });
  assert.deepEqual(b.call('POST', '/me/password', { body: { current_password: 'x', new_password: 'secret9' } }), { status: 401, body: { detail: 'signed_out' } });
});

test('a class review names a student whose row was deleted "a former student", in the teacher\'s language', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Test Student' });
  const id = classStarted(b, 50);
  b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } });
  b.call('POST', '/sessions/' + id + '/practice', { token: s.token, body: { entries: [{ item: 'tadasana', reaction: 2, pain: 1, note: 'knee' }] } });
  const users = b.ss.getSheetByName('users');
  users.deleteRow(users.rows().findIndex((r) => r[0] === s.user.id) + 1);
  b.context.onEdit({});
  const review = (lang) => b.call('GET', '/teacher/sessions/' + id + '/practice', { token: t.token, query: { lang } }).body.items[0];
  assert.deepEqual(review('en'), { item: 'tadasana', reactions: [0, 1, 0, 0], pain: [{ name: 'A former student', note: 'knee' }], notes: [] });
  assert.equal(review('hi').pain[0].name, 'एक पूर्व विद्यार्थी');
  assert.equal(review('mr').pain[0].name, 'एक माजी विद्यार्थी');
});

test('a time Sheets kept as a number reads as typed (7.15 is 07:15), and setup writes it back as text', () => {
  const b = freshBackend();
  const sheet = b.ss.getSheetByName('batches');
  const column = sheet.rows()[0].indexOf('time') + 1;
  const cells = () => sheet.rows().slice(1).map((r) => r[column - 1]);
  const times = () => b.call('GET', '/studio').body.batches.map((x) => x.time);
  ['7.15', '17.3', '8', '6.30'].forEach((typed, i) => sheet.getRange(i + 2, column).setValue(typed)); // into Automatic cells
  b.context.onEdit({});
  assert.deepEqual(cells(), [7.15, 17.3, 8, 6.3], 'Sheets keeps them as numbers');
  assert.deepEqual(times(), ['07:15', '17:30', '08:00', '06:30']);
  b.context.setup();
  assert.deepEqual(cells(), ['07:15', '17:30', '08:00', '06:30']);
  assert.deepEqual(times(), ['07:15', '17:30', '08:00', '06:30']);
  for (const [n, text] of [[0.75, '18:00'], [0.2916666667, '07:00'], [7.75, '07:45'], [12, '12:00'], [7.05, '07:05']]) {
    assert.equal(b.evaluate('clockText_(' + n + ')'), text, String(n));
  }
});

test('one class per batch per day: a changed time moves the coming classes in their rows, keeping their links, and leaves one checked in to', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM });
  const sheet = b.ss.getSheetByName('batches');
  const cell = sheet.getRange(2, sheet.rows()[0].indexOf('time') + 1);
  cell.setValue("'07:08"); // the Beginner classes made at 07:08 by a misread 07:00 time cell
  b.context.onEdit({});
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const beginner = () => b.ss.getSheetByName('class_sessions').rows().slice(1).filter((r) => r[1] === 'beginner')
    .map((r) => ({ id: r[0], at: new Date(r[2].getTime() + 330 * MIN).toISOString().slice(0, 16), link: r[4], curriculum: r[5] }));
  b.call('GET', '/teacher/home', { token: t.token });
  const made = beginner();
  assert.deepEqual(made.map((c) => c.at.slice(11)), ['07:08', '07:08', '07:08', '07:08', '07:08', '07:08']);
  const [today, tomorrow, third] = made.map((c) => c.id);
  b.call('PUT', '/teacher/sessions/' + tomorrow, { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } });
  b.call('PUT', '/teacher/sessions/' + third + '/curriculum', { token: t.token, body: { curriculum: 'pain_management' } });
  b.state.offsetMs = 10 * MIN; // 06:10: today's check-in is open
  assert.equal(b.call('POST', '/sessions/' + today + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  cell.setValue(new Date(Date.parse('1899-12-30T01:38:50Z'))); // the time cell, read as Sheets shows it: 07:00
  b.context.onEdit({});
  b.call('GET', '/teacher/home', { token: t.token });
  const now = beginner();
  assert.deepEqual(now.map((c) => c.id), made.map((c) => c.id), 'the same rows: no class removed, none added');
  assert.deepEqual(now.map((c) => c.at.slice(11)), ['07:08', '07:00', '07:00', '07:00', '07:00', '07:00'], 'the one checked in to stays');
  assert.deepEqual([now[1].link, now[2].curriculum], ['https://meet.google.com/abc-defg-hij', 'pain_management']);
  const home = b.call('GET', '/home', { token: s.token }).body.sessions;
  assert.deepEqual([home[0].id, home[0].checked_in, home[1].meet_link], [today, true, 'https://meet.google.com/abc-defg-hij']);
  assert.equal(new Set(home.map((x) => x.starts_at.slice(0, 10))).size, home.length, 'one a day');
});

test('after class, a class is offered to the batch the student was in at its time: none from before they were placed, the old batch\'s after a move', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  b.state.offsetMs = -3 * 60 * MIN;
  const r = b.call('POST', '/auth/signup', { body: { name: 'New', phone: '9000000004', password: 'secret1', code } }).body;
  const move = (batch) => b.call('PUT', '/teacher/students/' + r.user.id + '/batch', { token: t.token, body: { batch } });
  assert.equal(move('beginner').status, 200); // placed three hours ago
  b.state.offsetMs = 0;
  const early = classStarted(b, 240); // began before the placement
  const old = classStarted(b, 120); // the Beginner class after it
  b.state.offsetMs = -30 * MIN;
  assert.equal(move('intermediate').status, 200);
  b.state.offsetMs = 0;
  const after = (id) => b.call('POST', '/sessions/' + id + '/checkin', { token: r.token, body: { phase: 'after', mood: 4 } });
  const said = (id) => b.call('POST', '/sessions/' + id + '/practice', { token: r.token, body: { entries: [{ item: 'tadasana', reaction: 3 }] } });
  assert.notEqual(b.call('GET', '/home', { token: r.token }).body.after_class.id, early, 'not one from before the placement');
  assert.equal(after(old).status, 200, 'the old batch\'s class, from before the move');
  assert.deepEqual([after(early).body.detail, said(early).body.detail], ['checkin_closed', 'checkin_closed'], 'not theirs: before they were placed');
});

test('two accounts stored for one number, with and without the 0 after +91: each logs in as it was typed', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const first = signup(b, '9876543210', { code });
  const twin = b.call('POST', '/auth/signup', { body: { name: 'Twin', phone: '9000000077', password: 'twin123', code } }).body.user;
  const users = b.ss.getSheetByName('users');
  users.getRange(users.rows().findIndex((r) => r[0] === twin.id) + 1, 3).setValue("'+9109876543210"); // as stored when typed with the 0
  b.context.onEdit({});
  const login = (phone, password) => b.call('POST', '/auth/login', { body: { phone, password } }).body.user;
  assert.equal(login('+91 098765 43210', 'twin123').id, twin.id);
  assert.equal(login('98765 43210', 'secret1').id, first.user.id);
  assert.equal(login('+91 98765 43210', 'secret1').id, first.user.id);
});

/** Wednesday 10:00 in India, Pain management (17:30, Mon, Wed, Fri) with its week made, a student in it, and its time cell. */
function painManagementAt10() {
  const b = freshBackend({ now: Date.parse('2026-11-18T04:30:00Z') });
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, batch: 'pain_management' });
  const sheet = b.ss.getSheetByName('batches');
  const cell = sheet.getRange(sheet.rows().findIndex((r) => r[0] === 'pain_management') + 1, sheet.rows()[0].indexOf('time') + 1);
  const classes = () => b.ss.getSheetByName('class_sessions').rows().slice(1).filter((r) => r[1] === 'pain_management')
    .map((r) => ({ id: r[0], at: new Date(r[2].getTime() + 330 * MIN).toISOString().slice(0, 16), link: r[4] }));
  const type = (time) => {
    cell.setValue(time);
    b.context.onEdit({});
    b.call('GET', '/teacher/home', { token: t.token });
  };
  b.call('GET', '/teacher/home', { token: t.token });
  return { b, t, s, classes, type };
}

test('a time moved to earlier than now moves only the classes more than an hour away; today\'s stays, and a revert finds it', () => {
  const { b, t, classes, type } = painManagementAt10();
  const before = classes();
  b.call('PUT', '/teacher/sessions/' + before[0].id, { token: t.token, body: { meet_link: 'meet.google.com/abc-defg-hij' } });
  type("'07:00"); // meant from tomorrow: today's 07:00 is past
  assert.deepEqual(classes().map((c) => c.at.slice(11)), ['17:30', '07:00', '07:00']);
  assert.equal(classes()[0].link, 'https://meet.google.com/abc-defg-hij');
  type("'17:30"); // put back
  assert.deepEqual(classes(), before.map((c, i) => (i === 0 ? { ...c, link: 'https://meet.google.com/abc-defg-hij' } : c)), 'the same classes, at 17:30');
});

test('a time cell that is no time, while the owner retypes it, leaves its batch\'s classes as they are', () => {
  const { b, s, classes, type } = painManagementAt10();
  const before = classes();
  for (const blank of ['', "'17h30"]) {
    type(blank);
    b.call('GET', '/home', { token: s.token });
    assert.deepEqual(classes(), before, JSON.stringify(blank));
    assert.equal(b.call('GET', '/studio').body.batches[3].time, null);
  }
  type("'17:30");
  assert.deepEqual(classes(), before);
});

test('a class within an hour of its start, or moved to within an hour, stays where it is', () => {
  const { b, classes, type } = painManagementAt10();
  b.state.offsetMs = (6 * 60 + 40) * MIN; // 16:40: today's 17:30 check-in is open
  type("'18:30");
  assert.deepEqual(classes().map((c) => c.at.slice(11)), ['17:30', '18:30', '18:30'], 'today\'s stays at 17:30');
  type("'16:50"); // ten minutes ahead
  assert.deepEqual(classes().map((c) => c.at.slice(11)), ['17:30', '16:50', '16:50']);
});

test('a class is a student\'s when they were in its batch while it ran, by the app\'s moves or one made by hand in the users tab', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  b.state.offsetMs = -10 * DAY;
  const r = b.call('POST', '/auth/signup', { body: { name: 'N', phone: '9000000004', password: 'secret1', code } }).body;
  assert.equal(b.call('PUT', '/teacher/students/' + r.user.id + '/batch', { token: t.token, body: { batch: 'beginner' } }).status, 200);
  b.state.offsetMs = -2 * DAY; // moved by hand in the users tab, which logs no change
  const users = b.ss.getSheetByName('users');
  const header = users.rows()[0];
  const row = users.rows().findIndex((x) => x[0] === r.user.id) + 1;
  users.getRange(row, header.indexOf('batch') + 1).setValue("'intermediate");
  users.getRange(row, header.indexOf('batch_since') + 1).setValue(new Date(b.clock()));
  b.context.onEdit({});
  b.state.offsetMs = 0;
  const inter = classStarted(b, 60, 'intermediate');
  const beginner = classStarted(b, 120, 'beginner');
  const said = (id) => b.call('POST', '/sessions/' + id + '/practice', { token: r.token, body: { entries: [{ item: 'tadasana', reaction: 3 }] } });
  assert.equal(b.call('GET', '/home', { token: r.token }).body.after_class.batch.key, 'intermediate');
  assert.deepEqual([said(inter).status, said(beginner).body.detail], [200, 'checkin_closed'], 'the new batch\'s, not the old');
});

test('a student placed during her first class can check in to it and say how it went', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const r = b.call('POST', '/auth/signup', { body: { name: 'N', phone: '9000000004', password: 'secret1', code } }).body;
  const first = classStarted(b, 30, 'beginner'); // under way
  assert.equal(b.call('PUT', '/teacher/students/' + r.user.id + '/batch', { token: t.token, body: { batch: 'beginner' } }).status, 200);
  const checkin = (phase) => b.call('POST', '/sessions/' + first + '/checkin', { token: r.token, body: { phase, mood: 3 } }).status;
  assert.equal(checkin('before'), 200);
  const other = b.call('POST', '/auth/signup', { body: { name: 'M', phone: '9000000005', password: 'secret1', code } }).body;
  b.call('PUT', '/teacher/students/' + other.user.id + '/batch', { token: t.token, body: { batch: 'beginner' } });
  b.state.offsetMs = 20 * MIN; // the class's last five minutes: she never checked in
  assert.equal(b.call('POST', '/sessions/' + first + '/checkin', { token: other.token, body: { phase: 'after', mood: 4 } }).status, 200);
  assert.equal(b.call('GET', '/home', { token: other.token }).body.after_class.id, first);
});

test('a time typed as the hour alone, or in Devanagari digits, reads as typed; one that is no time reads as none', () => {
  const b = freshBackend();
  const cases = [['7', 420], ['17', 1020], [' 7 ', 420], ['५:३०', 330], ['१७:३०', 1050], ['5.30 PM', 1050], ['17h30', null], ['', null], ['25:00', null], ['7:75', null]];
  for (const [typed, minutes] of cases) assert.equal(b.evaluate('startMinutes_(' + JSON.stringify(typed) + ')'), minutes, typed);
});

test('a batch set by hand in the users tab is the student\'s batch from then on, whatever batch_since says', () => {
  const ist = (s) => Date.parse(s + '+05:30');
  for (const [name, since] of [['the date typed', ist('2026-11-19T00:00')], ['cleared', ''], ['as the app wrote it', undefined]]) {
    const b = freshBackend({ now: ist('2026-11-19T09:00') });
    const { t, code } = teacherAndCode(b);
    const r = b.call('POST', '/auth/signup', { body: { name: 'Meera', phone: '9000000004', password: 'secret1', code } }).body;
    assert.equal(b.call('PUT', '/teacher/students/' + r.user.id + '/batch', { token: t.token, body: { batch: 'beginner' } }).status, 200);
    b.state.offsetMs = 5 * 60 * MIN; // 14:00: moved to Intermediate by hand
    const users = b.ss.getSheetByName('users');
    const header = users.rows()[0];
    const row = users.rows().findIndex((x) => x[0] === r.user.id) + 1;
    users.getRange(row, header.indexOf('batch') + 1).setValue("'intermediate");
    if (since !== undefined) users.getRange(row, header.indexOf('batch_since') + 1).setValue(since === '' ? '' : new Date(since));
    b.context.onEdit({});
    b.state.offsetMs = (24 + 23) * 60 * MIN - 30 * MIN; // the next day, 07:30: Intermediate's 08:00 check-in is open
    const next = b.call('GET', '/home', { token: r.token }).body.sessions[0];
    const checkin = (id) => b.call('POST', '/sessions/' + id + '/checkin', { token: r.token, body: { phase: 'before', mood: 3 } });
    assert.deepEqual([next.batch.key, checkin(next.id).status], ['intermediate', 200], name);
    assert.equal(checkin(classStarted(b, -30, 'beginner')).body.detail, 'other_batch', name + ': the old batch\'s');
  }
});
