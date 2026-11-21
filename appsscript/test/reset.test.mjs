// The Sheet's own menu: removing the test people, resetting the studio, a new group code. The work functions run here
// as the menu runs them, and the menu's dialogs are answered through the fake Ui.
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, classStarted, freshBackend, setting, signup, teacherAndCode } from './helpers.mjs';

const PERSON_TABS = [['tokens', 'user_id'], ['checkins', 'user_id'], ['feedback', 'user_id'], ['shared_notes', 'user_id'], ['intake', 'user_id'],
  ['intake_ratings', 'user_id'], ['batch_changes', 'student_id'], ['practice', 'user_id'], ['solo_sessions', 'user_id'], ['asana_feedback', 'student_id']];
const KEPT_TABS = ['class_sessions', 'batches', 'library', 'curricula', 'curriculum_items', 'settings', 'Dashboard'];

const intake = { age: 40, height_cm: 160, weight_kg: 60, food: 'vegetarian', meals: 'dal, rice', pain: 'knee', pain_note: null,
  ratings: [{ item: 'tadasana', reaction: 3 }, { item: 'vajrasana', reaction: 1, pain: 1 }] };

/** One person doing everything a person can: a class (checked in, said how it went), practice on their own, the
 * intake, feedback, a shared note, a second sign-in; and the teacher's feedback to them and a move to another batch. */
function busy(b, t, s, session) {
  const ok = (r) => assert.equal(r.status, 200, JSON.stringify(r));
  const as = (method, path, body) => ok(b.call(method, path, { token: s.token, body }));
  as('POST', '/sessions/' + session + '/checkin', { phase: 'before', mood: 3 });
  as('POST', '/sessions/' + session + '/checkin', { phase: 'after', mood: 4 });
  as('POST', '/sessions/' + session + '/practice', { entries: [{ item: 'tadasana', reaction: 2 }, { item: 'vajrasana', pain: 1, note: 'knee' }] });
  as('POST', '/me/solo', { minutes: 10, entries: [{ item: 'vajrasana', hold_s: 60, reaction: 3 }] });
  as('PUT', '/me/intake', intake);
  as('POST', '/feedback', { screen: 'today', text: 'Lovely class' });
  as('POST', '/me/shared', { text: 'My knee felt better' });
  ok(b.call('POST', '/auth/login', { body: { phone: s.user.phone, password: 'secret1' } }));
  ok(b.call('POST', '/teacher/students/' + s.user.id + '/feedback', { token: t.token, body: { item: 'vajrasana', text: 'Knees together' } }));
  ok(b.call('PUT', '/teacher/students/' + s.user.id + '/batch', { token: t.token, body: { batch: 'intermediate', note: 'Ready' } }));
}

/** A studio in use: the teacher, two real students, three test people (one typed in by hand as "  test Meera", one
 * still waiting), each real and test student busy in today's class. */
function studio() {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const asha = signup(b, '9000000002', { code, name: 'Asha' });
  const tejas = signup(b, '9000000003', { code, name: 'Tejas Test' });
  const ravi = signup(b, '1000000001', { code, name: 'TEST Ravi' });
  const meera = signup(b, '1000000002', { code, name: 'Meera' });
  const waiting = signup(b, '1000000003', { name: 'TEST waiting' });
  b.call('PUT', '/me/intake', { token: waiting.token, body: intake });
  const users = b.ss.getSheetByName('users');
  users.getRange(users.rows().findIndex((r) => r[0] === meera.user.id) + 1, 2).setValue("'  test Meera");
  b.context.onEdit({});
  const session = classStarted(b, 50);
  for (const s of [asha, ravi, meera, tejas]) busy(b, t, s, session);
  b.call('POST', '/feedback', { token: t.token, body: { screen: 'insights', text: 'From the teacher' } });
  return { b, t, code, asha, tejas, ravi, meera, waiting, tests: [ravi.user.id, meera.user.id, waiting.user.id] };
}

const tab = (b, name) => b.ss.getSheetByName(name).rows();
const snapshot = (b, names) => Object.fromEntries(names.map((name) => [name, JSON.stringify(b.ss.getSheetByName(name).data)]));
const run = (b, expression) => JSON.parse(b.evaluate('JSON.stringify(' + expression + ')'));
const me = (b, s) => b.call('GET', '/me', { token: s.token });

test('every tab with a person column is cleared with them, and no other column names a person', () => {
  const b = freshBackend();
  assert.deepEqual(run(b, 'personTabs_()'), PERSON_TABS);
  const ids = run(b, 'Object.keys(TABLES_).map((t) => TABLES_[t].map(([c]) => c).filter((c) => /_id$/.test(c)))').flat();
  assert.deepEqual([...new Set(ids)].sort(), ['request_id', 'session_id', 'solo_id', 'student_id', 'user_id'], 'a request id is the phone\'s, no person\'s');
});

test('remove test people: only names starting with TEST go, with every row of theirs; everyone else\'s rows stay as they were', () => {
  const { b, tests } = studio();
  const before = Object.fromEntries(['users'].concat(PERSON_TABS.map(([name]) => name)).map((name) => [name, tab(b, name)]));
  const kept = snapshot(b, KEPT_TABS);
  const theirs = (name, col) => (r) => tests.includes(r[before[name][0].indexOf(col)]);
  for (const [name, col] of PERSON_TABS) assert.ok(before[name].slice(1).some(theirs(name, col)), name + ' has rows of test people to remove');

  const out = run(b, 'removeTestPeople_(new Db_())');
  assert.deepEqual([out.people, out.teacher], [3, false]);
  for (const [name, col] of [['users', 'id']].concat(PERSON_TABS)) {
    const [header, ...rows] = before[name];
    const others = rows.filter((r) => !theirs(name, col)(r));
    assert.deepEqual(tab(b, name), [header].concat(others), name + ': the header and everyone else\'s rows, in order');
    if (name !== 'users') assert.equal(out.rows[name], rows.length - others.length, name);
  }
  assert.equal(out.total, Object.values(out.rows).reduce((a, n) => a + n, 0));
  assert.deepEqual(snapshot(b, KEPT_TABS), kept, 'the classes, batches, curriculum, settings and the Dashboard\'s formulas');
  assert.deepEqual(tab(b, 'users').slice(1).map((r) => r[1]).sort(), ['Asha', 'Tejas Test', 'teacher 9000000001']);
  assert.equal(run(b, 'removeTestPeople_(new Db_())').people, 0, 'run again: no one left to remove');
});

test('a removed person is signed out at once; a write replayed with its request id brings nothing back; the next person gets an id of their own', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const ravi = signup(b, '1000000001', { code, name: 'TEST Ravi' });
  assert.equal(me(b, ravi).status, 200); // the token is now cached
  const solo = { minutes: 10, entries: [{ item: 'vajrasana', hold_s: 60, reaction: 3 }] };
  assert.equal(b.call('POST', '/me/solo', { token: ravi.token, body: solo, requestId: 'r-1' }).status, 200);
  run(b, 'removeTestPeople_(new Db_())');

  assert.deepEqual(me(b, ravi), { status: 401, body: { detail: 'signed_out' } });
  assert.equal(b.call('GET', '/home', { token: ravi.token }).status, 401);
  b.call('POST', '/me/solo', { token: ravi.token, body: solo, requestId: 'r-1' }); // the phone retrying: the kept answer, no write
  assert.equal(b.call('POST', '/me/solo', { token: ravi.token, body: solo, requestId: 'r-2' }).status, 401);
  assert.deepEqual([tab(b, 'solo_sessions').length, tab(b, 'practice').length, tab(b, 'tokens').length - 1], [1, 1, 1], 'the teacher\'s token only');

  const next = signup(b, '9000000002', { name: 'Asha' }); // waiting: no hand edit, so nothing else clears the cache
  assert.equal(next.user.id, ravi.user.id + 1, 'an id is never given again, so not Ravi\'s');
  assert.equal(me(b, ravi).status, 401, 'the old token, cached before, is not the new person\'s');
  assert.equal(me(b, next).body.user.name, 'Asha');
  b.call('POST', '/me/solo', { token: ravi.token, body: solo, requestId: 'r-1' });
  assert.equal(tab(b, 'solo_sessions').length, 1);
});

test('a login whose password check overlaps the removal gets no token', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const ravi = signup(b, '1000000001', { code, name: 'TEST Ravi' });
  b.evaluate('(() => { const check = checkPassword_; checkPassword_ = (p, s) => { const ok = check(p, s); removeTestPeople_(new Db_()); return ok; }; })()');
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '1000000001', password: 'secret1' } }), { status: 401, body: { detail: 'bad_login' } });
  assert.ok(!tab(b, 'tokens').some((r) => r[1] === ravi.user.id));
});

test('reset the studio: everyone goes, the teacher too, and rows left by anyone; the classes, batches, curriculum and settings stay; the codes work again', () => {
  const { b, t, code } = studio();
  const kept = snapshot(b, KEPT_TABS); // as setup left them: no link or curriculum set by the teacher yet
  const ok = (r) => assert.equal(r.status, 200, JSON.stringify(r));
  ok(b.call('PUT', '/teacher/settings', { token: t.token, body: { group_link: 'https://chat.whatsapp.com/AbCdEf123' } }));
  for (const key of ['beginner', 'intermediate', 'advanced', 'pain_management']) {
    ok(b.call('PUT', '/teacher/batches/' + key, { token: t.token, body: { meet_link: 'https://meet.google.com/abc-defg-hij' } }));
  }
  const day = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  ok(b.call('PUT', '/teacher/sessions/' + day[0].id, { token: t.token, body: { meet_link: 'https://meet.google.com/xyz-abcd-efg' } }));
  ok(b.call('PUT', '/teacher/sessions/' + day[1].id + '/curriculum', { token: t.token, body: { curriculum: 'pain_management' } }));
  addRow(b, 'checkins', { user_id: 99, session_id: 1, phase: 'before', mood: 3, created_at: b.clock() }); // someone deleted from users by hand
  const users = tab(b, 'users').length - 1;
  const lastId = Math.max(...tab(b, 'users').slice(1).map((r) => r[0]));
  const classes = tab(b, 'class_sessions').length;
  const headers = Object.fromEntries(['users'].concat(PERSON_TABS.map(([name]) => name)).map((name) => [name, tab(b, name)[0]]));

  const out = run(b, 'resetStudio_(new Db_())');
  assert.deepEqual([out.people, out.teacher, out.cleared], [users, true, 6], 'four batches, a class\'s link, a class\'s curriculum');
  for (const name of Object.keys(headers)) assert.deepEqual(tab(b, name), [headers[name]], name + ': the header alone');
  const now = snapshot(b, KEPT_TABS);
  for (const name of ['batches', 'library', 'curricula', 'curriculum_items', 'Dashboard']) {
    assert.deepEqual(now[name], kept[name], name + ': as setup left it');
  }
  assert.equal(tab(b, 'class_sessions').length, classes, 'the week of classes stays');
  const [head, ...rows] = tab(b, 'class_sessions');
  assert.deepEqual(rows.filter((r) => r[head.indexOf('meet_link')] !== '' || r[head.indexOf('curriculum')] !== ''), [],
    'no class keeps a link or a curriculum of its own');
  assert.equal(me(b, t).status, 401, 'the teacher too is signed out');

  const teacher = signup(b, '9000000009', { role: 'teacher', code: 'TEACH123' });
  assert.deepEqual([teacher.user.id, teacher.user.role], [lastId + 1, 'teacher'], 'the teacher code works again, and ids go on from the last');
  const home = b.call('GET', '/teacher/home', { token: teacher.token }).body;
  assert.deepEqual([home.settings.group_code, home.settings.group_link], [code, 'https://chat.whatsapp.com/AbCdEf123'], 'the settings stay');
  assert.deepEqual(home.batches.map((x) => x.meet_link), [null, null, null, null], 'no batch keeps an everyday link');
  assert.deepEqual(home.sessions.map((s) => [s.meet_link, s.has_link, s.curriculum]),
    home.sessions.map((s) => [null, false, home.batches.find((x) => x.key === s.batch.key)?.curriculum ?? s.curriculum]),
    'each class follows its batch again: no link, and its batch\'s curriculum');
  assert.equal(signup(b, '9000000002', { code, name: 'Asha' }).user.status, 'approved', 'and the group code');
  assert.equal(b.call('GET', '/teacher/students', { token: teacher.token }).body.students[0].joined, 0, 'no check-in of anyone before');
});

test('a tab whose rows fill its grid is emptied down to its header', () => {
  const { b } = studio();
  const tokens = b.ss.getSheetByName('tokens');
  tokens.maxRows = tokens.getLastRow(); // Sheets keeps one row below a frozen header: none to spare here
  run(b, 'resetStudio_(new Db_())');
  assert.deepEqual(tab(b, 'tokens'), [['token_hash', 'user_id', 'created_at']]);
  assert.equal(tokens.getMaxRows(), 2);
  const teacher = signup(b, '9000000009', { role: 'teacher', code: 'TEACH123' });
  assert.deepEqual(tab(b, 'tokens').slice(1).map((r) => r[1]), [teacher.user.id], 'and it takes rows again');
});

test('the removal takes the script lock, and waits for none when the app holds it', () => {
  const { b } = studio();
  const locks = b.state.locks;
  run(b, 'removeTestPeople_(new Db_())');
  assert.deepEqual([b.state.locks, b.state.lockHeld], [locks + 1, 0]);
  b.state.lockFree = false;
  const users = tab(b, 'users');
  assert.throws(() => b.evaluate('resetStudio_(new Db_())'), /busy/);
  assert.deepEqual(tab(b, 'users'), users);
});

test('the menu: its items, and each asks before it removes anything', () => {
  const { b, t, code } = studio();
  const { state, context } = b;
  context.onOpen();
  assert.deepEqual(state.menus.map((m) => [m.caption, m.items]), [['Satt Chitt Anand', [['Remove test people…', 'removeTestPeople'],
    ['Reset the studio…', 'resetStudio'], ['-'], ['New group code…', 'newGroupCode']]]]);
  for (const [, fn] of state.menus[0].items.filter(([, fn]) => fn)) assert.equal(typeof context[fn], 'function', fn);
  const users = () => tab(b, 'users').length - 1;

  state.answers.push('NO');
  context.removeTestPeople();
  const [ask] = state.dialogs.splice(0);
  assert.equal(ask.buttons, 'YES_NO');
  assert.match(ask.prompt, /^Remove 3 people whose names start with TEST, and the \d+ rows that are theirs\?\n\n• TEST Ravi \(\+911000000001\)\n/);
  assert.match(ask.prompt, /• {3}test Meera \(\+911000000002\)\n• TEST waiting \(\+911000000003\)\n\nTheir rows: \d+ sign-ins, \d+ check-ins, /);
  assert.match(ask.prompt, /This cannot be undone\.$/);
  assert.equal(users(), 6, 'NO removes no one');
  state.answers.push('YES');
  context.removeTestPeople();
  assert.match(state.dialogs.splice(0)[1].prompt, /^Removed 3 people and \d+ rows\.$/);
  assert.equal(users(), 3);
  context.removeTestPeople();
  assert.equal(state.dialogs.splice(0)[0].prompt, 'No one\'s name starts with TEST, so there is no one to remove.');

  for (const answers of [['NO'], ['YES', ['CANCEL', 'RESET']], ['YES', ['OK', 'reset']]]) {
    state.answers.push(...answers);
    context.resetStudio();
    assert.equal(users(), 3, JSON.stringify(answers) + ' removes no one');
  }
  assert.equal(state.dialogs.at(-1).prompt, 'Nothing was removed: the box did not say RESET.');
  assert.match(state.dialogs[0].prompt, /^This removes everyone signed up \(3 people, the teacher among them\) and every row they made/);
  assert.match(state.dialogs[0].prompt, /The Meet links the teacher set go too, each batch's and each class's own, and the curriculum chosen for a class/);
  assert.match(state.dialogs[0].prompt, /What stays: the batches \(their names, days and times\), the curriculum \(library, curricula, curriculum_items\), the classes/);
  assert.equal(state.dialogs[2].kind, 'prompt');
  state.dialogs.splice(0);
  state.answers.push('YES', ['OK', ' RESET ']);
  context.resetStudio();
  assert.equal(users(), 0);
  assert.match(state.dialogs.at(-1).prompt, /^The studio is reset: 3 people and \d+ rows were removed, and the Meet links and curricula the teacher set cleared\./);

  state.answers.push('NO');
  context.newGroupCode();
  assert.equal(setting(b, 'group_code'), code);
  state.answers.push('YES');
  context.newGroupCode();
  const fresh = setting(b, 'group_code');
  assert.notEqual(fresh, code);
  assert.match(state.dialogs.at(-1).prompt, new RegExp('^The new group code is ' + fresh + '\\. '));
  const signupWith = (c) => b.call('POST', '/auth/signup', { body: { name: 'Asha', phone: '9000000002', password: 'secret1', role: 'student', code: c } });
  assert.equal(signupWith(code).body.detail, 'bad_group_code', 'the old code is refused at once');
  assert.equal(signupWith(fresh).status, 200);
  assert.equal(me(b, t).status, 401);
});
