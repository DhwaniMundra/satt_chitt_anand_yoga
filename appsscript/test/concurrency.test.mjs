// Two requests at once, as a class sends them: sign-ups, logouts, the first visits of a day, a login that overlaps a
// removal, a password change, a new password for a student and intakes, each with another request run in its middle
// (meanwhile() in fakes.mjs) and the Sheet read as we believe Apps Script reads it when executions overlap (the
// stale-read mode in fakes.mjs: a tab read twice in one execution comes back the second time as it was the first).
// Each runs in two models: `believed`, where a flush makes the next reads go to the Sheet, and `worst`, where it
// refreshes nothing and only a tab first read under the lock is read right. Then the guards that hold whatever a read
// misses: ids that never repeat, one account per number, a shared id refused, the writes answered again for their
// request id (two copies arriving together too), and an intake's short hold on the lock.
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, classStarted, DAY, freshBackend, MIN, setting, signup, teacherAndCode } from './helpers.mjs';

const MODELS = { believed: { flushRefreshes: true }, worst: { flushRefreshes: false } };

/** A studio with its teacher, in the stale-read model `model`, and a second request's backend. */
function studio(model) {
  const b = freshBackend({ staleReads: MODELS[model] });
  const { t, code } = teacherAndCode(b);
  return { b, other: b.twin(), t, code };
}

const join = (b, phone, name, { requestId, code } = {}) => b.call('POST', '/auth/signup', { requestId,
  body: { name, phone, password: 'secret1', code: code ?? setting(b, 'group_code') } });
const me = (b, token) => b.call('GET', '/me', { token });
const tab = (b, name) => b.ss.getSheetByName(name).rows();
const column = (b, name, col) => {
  const [header, ...rows] = tab(b, name);
  return rows.filter((r) => r.some((v) => v !== '')).map((r) => r[header.indexOf(col)]);
};
const intake = (age, ratings) => ({ age, height_cm: 160, weight_kg: 60, food: 'vegetarian', meals: null, pain: null, pain_note: null, ratings });
const rated = (items, reaction) => items.map((item) => ({ item, reaction }));
const ASKED = ['tadasana', 'vrikshasana', 'trikonasana', 'vajrasana', 'bhujangasana', 'paschimottanasana'];

// ---------- two requests at once ----------

for (const model of Object.keys(MODELS)) {
  for (const moment of [{ read: 'users' }, { lock: 2 }]) {
    const when = JSON.stringify(moment);

    test(`two sign-ups at once get two ids, and each token opens its own account (${model}, the other at ${when})`, () => {
      const { b, other } = studio(model);
      let second;
      b.meanwhile(moment, () => { second = join(other, '9000000003', 'Bela'); });
      const first = join(b, '9000000002', 'Asha');
      assert.ok(second, 'the other sign-up ran in the middle');
      assert.deepEqual([first.status, second.status], [200, 200], JSON.stringify([first, second]));
      assert.notEqual(first.body.user.id, second.body.user.id);
      assert.equal(new Set(column(b, 'users', 'id')).size, 3, 'the teacher and two students, each with an id of their own');
      assert.deepEqual([me(b, first.body.token).body.user.name, me(b, second.body.token).body.user.name], ['Asha', 'Bela']);
    });

    test(`two sign-ups of one number at once make one account (${model}, the other at ${when})`, () => {
      const { b, other } = studio(model);
      let second;
      b.meanwhile(moment, () => { second = join(other, '9000000002', 'Asha again'); });
      const first = join(b, '9000000002', 'Asha');
      assert.deepEqual([first, second].map((r) => r.status).sort(), [200, 409], JSON.stringify([first, second]));
      assert.equal([first, second].find((r) => r.status === 409).body.detail, 'phone_taken');
      assert.equal(column(b, 'users', 'phone').filter((p) => p === '+919000000002').length, 1);
    });
  }

  for (const moment of [{ read: 'tokens' }, { lock: 1 }]) {
    test(`two logouts at once sign out the two who asked and no one else (${model}, the other at ${JSON.stringify(moment)})`, () => {
      const { b, other, t } = studio(model);
      const [s1, s2, s3] = ['9000000002', '9000000003', '9000000004'].map((p) => signup(b, p));
      let ran = false;
      b.meanwhile(moment, () => { ran = other.call('POST', '/auth/logout', { token: s1.token }).status === 200; });
      assert.equal(b.call('POST', '/auth/logout', { token: s2.token }).status, 200);
      assert.ok(ran);
      assert.deepEqual([t, s1, s2, s3].map((s) => me(b, s.token).status), [200, 401, 401, 200]);
    });
  }

  for (const moment of [{ read: 'class_sessions' }, { lock: 1 }]) {
    test(`two first visits of a day at once make its classes once (${model}, the other at ${JSON.stringify(moment)})`, () => {
      const { b, other, t, code } = studio(model);
      const s = signup(b, '9000000002', { code });
      // On to a day whose window ends on a day some batch meets, so the first visit has classes to add.
      const weekday = (ms) => (Math.floor((ms + 330 * MIN) / DAY) + 3) % 7; // 0 is Monday
      const days = weekday(b.clock() + 7 * DAY) === 6 ? 2 : 1;
      b.state.offsetMs += days * DAY;
      let theirs;
      b.meanwhile(moment, () => { theirs = other.call('GET', '/home', { token: s.token }); });
      const mine = b.call('GET', '/teacher/home', { token: t.token });
      assert.deepEqual([mine.status, theirs && theirs.status], [200, 200]);
      const ids = column(b, 'class_sessions', 'id');
      assert.equal(new Set(ids).size, ids.length, 'no two classes share an id');
      const [header, ...rows] = tab(b, 'class_sessions');
      const days_ = rows.map((r) => r[header.indexOf('batch')] + '@' + Math.floor((r[header.indexOf('starts_at')].getTime() + 330 * MIN) / DAY));
      assert.equal(new Set(days_).size, days_.length, 'one class per batch per day');
      for (const id of mine.body.sessions.concat(theirs.body.sessions).map((x) => x.id)) assert.ok(ids.includes(id), 'class ' + id + ' is in the tab');
    });
  }

  for (const moment of [{ read: 'users' }, { lock: 1 }]) {
    test(`two intakes at once both stay as sent (${model}, the other at ${JSON.stringify(moment)})`, () => {
      const { b, other } = studio(model);
      const [s1, s2, s3] = ['9000000002', '9000000003', '9000000004'].map((p) => signup(b, p));
      for (const s of [s1, s2, s3]) assert.equal(b.call('PUT', '/me/intake', { token: s.token, body: intake(30, rated(ASKED.slice(0, 3), 2)) }).status, 200);
      b.meanwhile(moment, () => other.call('PUT', '/me/intake', { token: s2.token, body: intake(41, rated(ASKED.slice(0, 5), 3)) }));
      assert.equal(b.call('PUT', '/me/intake', { token: s1.token, body: intake(25, rated(ASKED.slice(4), 4)) }).status, 200);
      const read = (s) => b.call('GET', '/me/intake', { token: s.token }).body.intake;
      assert.deepEqual([read(s1).age, read(s1).ratings], [25, rated(ASKED.slice(4), 4).map((r) => ({ ...r, pain: 0 }))]);
      assert.deepEqual([read(s2).age, read(s2).ratings], [41, rated(ASKED.slice(0, 5), 3).map((r) => ({ ...r, pain: 0 }))]);
      assert.deepEqual([read(s3).age, read(s3).ratings], [30, rated(ASKED.slice(0, 3), 2).map((r) => ({ ...r, pain: 0 }))]);
      assert.equal(column(b, 'intake', 'user_id').length, 3, 'one intake row each');
    });
  }

  test(`a token given to someone removed meanwhile opens no one else's account (${model})`, () => {
    const { b, other, code } = studio(model);
    const ravi = signup(b, '1000000001', { code, name: 'TEST Ravi' });
    // The removal runs between the login's password check and its lock.
    b.meanwhile({ lock: 2 }, () => other.execution(() => other.evaluate('removeTestPeople_(new Db_())')));
    const login = b.call('POST', '/auth/login', { body: { phone: '1000000001', password: 'secret1' } });
    const next = signup(b, '9000000002', { name: 'Asha' });
    assert.notEqual(next.user.id, ravi.user.id, 'a removed person\'s id is not given again');
    if (login.status === 200) assert.equal(me(b, login.body.token).status, 401);
  });
}

// What rests on the flush right after the lock: a route that must know who is asking before its slow password hash
// reads the users and tokens tabs before the lock, and under it reads them again.

test('a login whose password check overlaps a removal gets no token (believed)', () => {
  const { b, other, code } = studio('believed');
  signup(b, '1000000001', { code, name: 'TEST Ravi' });
  signup(b, '9000000002', { code, name: 'Asha' }); // so Ravi's is not the last row, whose loss the tab's size alone would show
  b.meanwhile({ lock: 2 }, () => other.execution(() => other.evaluate('removeTestPeople_(new Db_())')));
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '1000000001', password: 'secret1' } }), { status: 401, body: { detail: 'bad_login' } });
});

test('a password change signs out its own other logins and no one else\'s, while another logs out (believed)', () => {
  const { b, other, t } = studio('believed');
  const classmate = signup(b, '9000000002');
  const older = signup(b, '9000000003');
  const current = b.call('POST', '/auth/login', { body: { phone: '9000000003', password: 'secret1' } }).body.token;
  b.cache.clear(); // so the change reads the tokens tab, before its lock
  b.meanwhile({ read: 'tokens' }, () => other.call('POST', '/auth/logout', { token: classmate.token }));
  const r = b.call('POST', '/me/password', { token: current, body: { current_password: 'secret1', new_password: 'secret2' } });
  assert.equal(r.status, 200, JSON.stringify(r));
  assert.deepEqual([t.token, classmate.token, older.token, current].map((token) => me(b, token).status), [200, 401, 401, 200]);
});

test('the menu removes the right rows though the app wrote between its question and the owner\'s yes (believed)', () => {
  const { b, other, t, code } = studio('believed');
  const asha = signup(b, '9000000002', { code, name: 'Asha' });
  signup(b, '1000000001', { code, name: 'TEST Ravi' });
  const login = (phone) => b.call('POST', '/auth/login', { body: { phone, password: 'secret1' } }).body.token;
  const ashaAgain = login('9000000002');
  login('1000000001');
  b.state.answers.push('YES');
  // While the dialog waits for the owner, Asha logs out on her first phone: a sign-in row above Ravi's goes.
  b.meanwhile({ lock: 1 }, () => other.call('POST', '/auth/logout', { token: asha.token }));
  b.execution(() => b.context.removeTestPeople());
  assert.deepEqual([t.token, asha.token, ashaAgain].map((token) => me(b, token).status), [200, 401, 200]);
  assert.deepEqual(column(b, 'tokens', 'user_id').sort(), [t.user.id, asha.user.id].sort());
});

test('the week is made once and then checked every ten minutes: other visits take no lock', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const visit = () => {
    const locks = b.state.locks;
    assert.equal(b.call('GET', '/teacher/home', { token: t.token }).status, 200);
    return b.state.locks - locks;
  };
  assert.equal(visit(), 0, 'teacherAndCode made it');
  b.state.offsetMs += 5 * MIN;
  assert.equal(visit(), 0);
  b.state.offsetMs += 6 * MIN;
  assert.equal(visit(), 1, 'ten minutes on, as the cache forgets');
  assert.equal(visit(), 0);
  const batches = b.ss.getSheetByName('batches');
  batches.getRange(2, batches.rows()[0].indexOf('time') + 1).setValue("'07:30");
  assert.equal(visit(), 1, 'a batch\'s new time: the week is made again');
  assert.equal(visit(), 0);
  b.state.offsetMs += DAY;
  assert.equal(visit(), 1, 'a new day');
  // A visit that cannot have the lock goes on with the classes as they are, and the next one makes the week.
  b.state.offsetMs += 11 * MIN;
  const before = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  b.state.offsetMs += 11 * MIN;
  b.state.lockFree = false;
  const busy = b.call('GET', '/teacher/home', { token: t.token });
  b.state.lockFree = true;
  assert.deepEqual([busy.status, busy.body.sessions.map((s) => s.id)], [200, before.map((s) => s.id)]);
  assert.equal(visit(), 1);
});

// ---------- the guards that hold whatever a read misses ----------

test('ids are never given twice: not after a removal or a reset, nor when a read of the tab misses rows', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const ravi = signup(b, '1000000001', { name: 'TEST Ravi' });
  b.evaluate('removeTestPeople_(new Db_())');
  const asha = signup(b, '9000000002', { name: 'Asha' });
  assert.equal(asha.user.id, ravi.user.id + 1, 'not Ravi\'s');
  addRow(b, 'users', { id: 50, name: 'Typed in by hand', phone: '+919000000050', role: 'student', status: 'pending', lang: 'en', created_at: b.clock() });
  assert.equal(signup(b, '9000000003').user.id, 51, 'after a row typed in by hand, the next id');
  b.evaluate('resetStudio_(new Db_())');
  assert.equal(signup(b, '9000000009', { role: 'teacher', code: 'TEACH123' }).user.id, 52, 'and on after a reset');
  // A read that misses rows: the tab's largest id + 1 is 1 every time.
  b.evaluate('Table_.prototype.nextId = function () { return 1; }');
  const ids = ['9000000011', '9000000012'].map((p) => signup(b, p).user.id);
  assert.deepEqual(ids, [53, 54]);
  b.state.offsetMs += 2 * DAY; // the classes of two more days, under the same miss
  assert.equal(b.call('GET', '/teacher/home', { token: signup(b, '9000000013').token }).status, 403); // a student: no teacher home
  const t = b.call('POST', '/auth/login', { body: { phone: '9000000009', password: 'secret1' } }).body.token;
  assert.equal(b.call('GET', '/teacher/home', { token: t }).status, 200);
  const classes = column(b, 'class_sessions', 'id');
  assert.equal(new Set(classes).size, classes.length, 'no two classes share an id');
});

test('one account per number even when the read of the users tab misses the newest row', () => {
  const b = freshBackend();
  teacherAndCode(b);
  b.evaluate(`(() => {
    const t = Db_.prototype.t;
    Db_.prototype.t = function (name) {
      const fresh = !this.tables[name];
      const table = t.call(this, name);
      if (fresh && name === 'users' && globalThis.MISSED_) table.rows = table.rows.filter((u) => u.phone !== globalThis.MISSED_);
      return table;
    };
  })()`);
  const asha = signup(b, '9000000002', { name: 'Asha' });
  b.evaluate('MISSED_ = "+919000000002"');
  assert.deepEqual(join(b, '9000000002', 'Asha again'), { status: 409, body: { detail: 'phone_taken' } });
  assert.equal(column(b, 'users', 'phone').filter((p) => p === '+919000000002').length, 1);
  assert.ok(b.state.logs.some((line) => /^ERROR /.test(line) && line.includes(String(asha.user.id))), 'the miss is logged');
});

test('a number whose row the owner deleted by hand signs up again after a few minutes; the menu forgets the numbers it removes', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const asha = signup(b, '9000000002', { name: 'Asha' });
  const users = b.ss.getSheetByName('users');
  users.deleteRow(users.rows().findIndex((r) => r[0] === asha.user.id) + 1);
  assert.equal(join(b, '9000000002', 'Asha').body.detail, 'phone_taken', 'just written: a read may have missed it');
  b.state.offsetMs += 7 * MIN;
  assert.equal(join(b, '9000000002', 'Asha').status, 200, 'minutes later, the row is gone for good');

  const keys = () => b.props.getKeys().filter((k) => k.startsWith('phone:')).sort();
  signup(b, '1000000001', { name: 'TEST Ravi' });
  signup(b, '1000000002', { name: 'TEST Meera' });
  assert.deepEqual(keys(), ['phone:+911000000001', 'phone:+911000000002', 'phone:+919000000001', 'phone:+919000000002']);
  b.evaluate('removeTestPeople_(new Db_())');
  assert.deepEqual(keys(), ['phone:+919000000001', 'phone:+919000000002']);
  assert.equal(join(b, '1000000001', 'TEST Ravi').status, 200, 'a removed number signs up again at once');
  b.evaluate('resetStudio_(new Db_())');
  assert.deepEqual(keys(), []);
  assert.equal(join(b, '9000000002', 'Asha').status, 200);
});

test('two users rows with one id: its token opens neither, the teacher finds neither, and the execution log says so', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const asha = signup(b, '9000000002', { code, name: 'Asha' });
  addRow(b, 'users', { id: asha.user.id, name: 'Copy', phone: '+919000000077', role: 'student', status: 'approved', lang: 'en', created_at: b.clock() });
  b.context.onEdit({});
  assert.deepEqual(me(b, asha.token), { status: 401, body: { detail: 'signed_out' } });
  assert.ok(b.state.logs.some((line) => /^ERROR /.test(line) && line.includes('share')), b.state.logs.join('\n'));
  assert.deepEqual(b.call('GET', '/teacher/students/' + asha.user.id + '/asanas', { token: t.token }), { status: 404, body: { detail: 'no_student' } });
  assert.deepEqual(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }), { status: 401, body: { detail: 'bad_login' } });
  assert.equal(me(b, t.token).status, 200, 'everyone else as before');
});

test('a sign-up sent again with its request id gets the first answer: the same account, a token that works, one row', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const first = join(b, '9000000002', 'Asha', { requestId: 'r-1' });
  assert.equal(first.status, 200);
  const again = join(b, '+91 90000 00002', 'Asha', { requestId: 'r-1' }); // the number typed another way
  assert.deepEqual(again, first);
  assert.equal(me(b, again.body.token).body.user.name, 'Asha');
  assert.equal(column(b, 'users', 'phone').filter((p) => p === '+919000000002').length, 1);
  assert.equal(column(b, 'tokens', 'user_id').filter((id) => id === first.body.user.id).length, 1);
  assert.deepEqual(join(b, '9000000002', 'Asha', { requestId: 'r-2' }), { status: 409, body: { detail: 'phone_taken' } }, 'a new id is a new sign-up');
  assert.equal(join(b, '9000000003', 'Bela', { requestId: 'r-1' }).body.user.name, 'Bela', 'the id is kept per number');
  b.state.offsetMs += 11 * MIN;
  assert.equal(join(b, '9000000002', 'Asha', { requestId: 'r-1' }).body.detail, 'phone_taken', 'kept ten minutes');
});

test('a sign-up refused is answered again the same for its request id, and a new id is asked afresh', () => {
  const b = freshBackend();
  teacherAndCode(b);
  assert.equal(join(b, '9000000002', 'Asha', { requestId: 'r-1', code: 'WRONG2' }).body.detail, 'bad_group_code');
  assert.equal(join(b, '9000000002', 'Asha', { requestId: 'r-1' }).body.detail, 'bad_group_code', 'the same id is the same sign-up');
  assert.equal(join(b, '9000000002', 'Asha', { requestId: 'r-2' }).status, 200);
});

test('a login refused is answered again for its request id without counting another wrong try; busy is never kept', () => {
  const b = freshBackend();
  teacherAndCode(b);
  signup(b, '9000000002', { name: 'Asha' });
  const login = (requestId, password) => b.call('POST', '/auth/login', { requestId, body: { phone: '9000000002', password } });
  for (let i = 0; i < 8; i++) assert.deepEqual(login('l-1', 'wrong!'), { status: 401, body: { detail: 'bad_login' } }, 'try ' + (i + 1));
  assert.equal(login('l-2', 'secret1').status, 200, 'one wrong try counted, not eight');
  b.state.lockFree = false;
  assert.equal(login('l-3', 'secret1').body.detail, 'busy');
  b.state.lockFree = true;
  assert.equal(login('l-3', 'secret1').status, 200, 'busy passes, so it is not kept');
  for (let i = 0; i < 5; i++) login('l-4' + i, 'wrong!');
  assert.equal(login('l-5', 'secret1').body.detail, 'too_many_attempts');
  b.state.offsetMs += 16 * MIN;
  assert.equal(login('l-5', 'secret1').status, 200, 'too_many_attempts passes with time, so it is not kept');
});

test('a new password for a student sent again with its request id gets the same password, which works', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  const reset = (requestId) => b.call('POST', '/teacher/students/' + s.user.id + '/password', { token: t.token, requestId });
  const first = reset('p-1');
  assert.deepEqual(reset('p-1'), first);
  const login = (password) => b.call('POST', '/auth/login', { body: { phone: '9000000002', password } }).status;
  assert.equal(login(first.body.password), 200);
  assert.notEqual(reset('p-2').body.password, first.body.password, 'a new id is a new password');
});

for (const model of Object.keys(MODELS)) {
  test(`two copies of a new password at once give one password, and it works (${model})`, () => {
    const { b, other, t, code } = studio(model);
    const s = signup(b, '9000000002', { code, name: 'Asha' });
    const reset = (backend) => backend.call('POST', '/teacher/students/' + s.user.id + '/password', { token: t.token, requestId: 'p-1' });
    let second;
    // The teacher's second confirm, with the first's request id, arrives just before the first takes the lock.
    b.meanwhile({ lock: 1 }, () => { second = reset(other); });
    const first = reset(b);
    assert.equal(first.status, 200, JSON.stringify(first));
    assert.deepEqual(second, first);
    assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: first.body.password } }).status, 200);
    assert.deepEqual(reset(b), first, 'and a third copy after them');
  });

  for (const moment of [{ lock: 1 }, { lock: 2 }, { read: 'tokens' }]) {
    test(`two copies of a password change at once change it once and get one answer (${model}, the other at ${JSON.stringify(moment)})`, () => {
      const { b, other } = studio(model);
      const asha = signup(b, '9000000002', { name: 'Asha' });
      const token = b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret1' } }).body.token;
      const change = (backend) => backend.call('POST', '/me/password', { token, requestId: 'c-1',
        body: { current_password: 'secret1', new_password: 'secret2' } });
      let second;
      b.meanwhile(moment, () => { second = change(other); });
      const first = change(b);
      assert.deepEqual([first, second], [{ status: 200, body: { ok: true } }, { status: 200, body: { ok: true } }]);
      assert.equal(me(b, token).status, 200, 'this login stays signed in');
      assert.equal(me(b, asha.token).status, 401, 'the sign-up\'s login is signed out');
      assert.equal(b.call('POST', '/auth/login', { body: { phone: '9000000002', password: 'secret2' } }).status, 200);
    });
  }
}

test('a login sent again with its request id gets the first token and writes one', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const asha = signup(b, '9000000002', { name: 'Asha' });
  const login = (requestId, password = 'secret1') => b.call('POST', '/auth/login', { requestId, body: { phone: '9000000002', password } });
  const first = login('l-1');
  assert.equal(first.status, 200);
  assert.deepEqual(login('l-1'), first);
  assert.equal(column(b, 'tokens', 'user_id').filter((id) => id === asha.user.id).length, 2, 'the sign-up\'s and the login\'s');
  assert.equal(me(b, first.body.token).status, 200);
  assert.equal(login('l-2', 'wrong!').status, 401);
  assert.notEqual(login('l-3').body.token, first.body.token, 'a new id is a new login');
});

for (const model of Object.keys(MODELS)) {
  for (const moment of [{ read: 'users' }, { lock: 2 }]) {
    test(`two copies of a sign-up at once make one account and get one answer (${model}, the other at ${JSON.stringify(moment)})`, () => {
      const { b, other } = studio(model);
      let second;
      b.meanwhile(moment, () => { second = join(other, '9000000002', 'Asha', { requestId: 'r-1' }); });
      const first = join(b, '9000000002', 'Asha', { requestId: 'r-1' });
      assert.equal(first.status, 200, JSON.stringify(first));
      assert.deepEqual(second, first);
      assert.equal(column(b, 'users', 'phone').filter((p) => p === '+919000000002').length, 1);
      assert.equal(me(b, first.body.token).body.user.name, 'Asha');
    });
  }
}

test('an intake save holds the lock for two reads and a few writes, and deletes no rows', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const [s1, s2] = ['9000000002', '9000000003'].map((p) => signup(b, p));
  const save = (s, ratings) => {
    const before = { ...b.state.lockedCalls };
    const r = b.call('PUT', '/me/intake', { token: s.token, body: intake(33, ratings) });
    assert.equal(r.status, 200, JSON.stringify(r));
    return Object.fromEntries(Object.keys(before).map((k) => [k, b.state.lockedCalls[k] - before[k]]));
  };
  const costs = [save(s1, rated(ASKED.slice(0, 3), 2)), save(s2, rated(ASKED, 3)), save(s1, rated(ASKED, 4)), save(s1, rated(ASKED.slice(1, 2), 1)),
    save(s1, rated(ASKED.slice(0, 4), 3))];
  for (const cost of costs) {
    assert.equal(cost.read, 2, JSON.stringify(costs)); // the intake and its self-assessment, read afresh
    assert.ok(cost.write <= 3, JSON.stringify(costs));
    assert.equal(cost.structural, 0, JSON.stringify(costs));
  }
  const read = (s) => b.call('GET', '/me/intake', { token: s.token }).body.intake.ratings;
  assert.deepEqual(read(s1), rated(ASKED.slice(0, 4), 3).map((r) => ({ ...r, pain: 0 })));
  assert.deepEqual(read(s2), rated(ASKED, 3).map((r) => ({ ...r, pain: 0 })));
  const teacher = b.call('POST', '/auth/login', { body: { phone: '9000000001', password: 'secret1' } }).body.token;
  assert.deepEqual(b.call('GET', '/teacher/students', { token: teacher }).body.students.find((x) => x.id === s1.user.id).intake.ratings, read(s1));
});

// ---------- what a class sends at once: the lock holds only the tabs each write writes ----------

/** Asha, who checked in, and Bela, who did not, both of the class that ended a few minutes ago. */
function classOfTwo(model) {
  const { b, other, code } = studio(model);
  const asha = signup(b, '9000000002', { code, name: 'Asha' });
  const bela = signup(b, '9000000003', { code, name: 'Bela' });
  const id = classStarted(b, 60);
  b.state.offsetMs -= 50 * MIN;
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: asha.token, body: { phase: 'before', mood: 3 } }).status, 200);
  b.state.offsetMs += 50 * MIN;
  return { b, other, asha, bela, id };
}

/** Each student write a class sends at once: how a student sends it, and the rows it writes, [tab, column of whose]. */
const BURSTS = {
  'how class went': {
    send: (backend, s, id, requestId) => backend.call('POST', '/sessions/' + id + '/practice', { token: s.token, requestId,
      body: { entries: [{ item: 'vajrasana', reaction: 3, note: 'Knee ' + s.user.name }, { item: 'tadasana', reaction: 4 }] } }),
    rows: [['practice', 'user_id', 2]],
  },
  'a practice on one\'s own': {
    send: (backend, s, id, requestId) => backend.call('POST', '/me/solo', { token: s.token, requestId,
      body: { minutes: 15, entries: [{ item: 'vajrasana', hold_s: 60 }, { item: 'tadasana', reaction: 3 }] } }),
    rows: [['solo_sessions', 'user_id', 1], ['practice', 'user_id', 2]],
  },
  'a shared note': {
    send: (backend, s, id, requestId) => backend.call('POST', '/me/shared', { token: s.token, requestId, body: { text: 'Right knee clicks' } }),
    rows: [['shared_notes', 'user_id', 1]],
  },
  'feedback': {
    send: (backend, s, id, requestId) => backend.call('POST', '/feedback', { token: s.token, requestId, body: { screen: 'me', text: 'Lovely class' } }),
    rows: [['feedback', 'user_id', 1]],
  },
};

/** The rows of `tab` whose `col` is this student's. */
const theirs = (b, tab, col, s) => column(b, tab, col).filter((v) => v === s.user.id).length;

for (const model of Object.keys(MODELS)) {
  for (const moment of [{ read: 'users' }, { lock: 1 }]) {
    const when = JSON.stringify(moment);
    for (const [name, route] of Object.entries(BURSTS)) {
      test(`${name}: two students at once, each written once with ids of its own (${model}, the other at ${when})`, () => {
        const { b, other, asha, bela, id } = classOfTwo(model);
        let second;
        b.meanwhile(moment, () => { second = route.send(other, bela, id); });
        const first = route.send(b, asha, id);
        assert.equal(first.status, 200, JSON.stringify(first));
        assert.equal(second.status, 200, JSON.stringify(second));
        for (const [sheet, col, n] of route.rows) {
          assert.deepEqual([theirs(b, sheet, col, asha), theirs(b, sheet, col, bela)], [n, n], sheet);
          const ids = column(b, sheet, 'id');
          assert.equal(new Set(ids).size, ids.length, sheet + ': no id given twice');
        }
        if (name === 'how class went') {
          const before = (s) => tab(b, 'checkins').slice(1).filter((r) => r[0] === s.user.id && r[2] === 'before').length;
          assert.deepEqual([before(asha), before(bela)], [1, 1], 'Bela, who did not check in, is recorded as come, once');
        }
      });

      test(`${name}: two copies of one request id at once write once and get one answer (${model}, the other at ${when})`, () => {
        const { b, other, bela, id } = classOfTwo(model);
        let second;
        b.meanwhile(moment, () => { second = route.send(other, bela, id, 'r-1'); });
        const first = route.send(b, bela, id, 'r-1');
        assert.equal(first.status, 200, JSON.stringify(first));
        assert.deepEqual(second, first);
        for (const [sheet, col, n] of route.rows) assert.equal(theirs(b, sheet, col, bela), n, sheet);
        if (name === 'how class went') {
          assert.equal(tab(b, 'checkins').slice(1).filter((r) => r[0] === bela.user.id && r[2] === 'before').length, 1, 'recorded as come once');
        }
      });
    }
  }
}

test('what a class sends together reads, under the lock, only the tabs it writes', () => {
  const { b, asha, bela, id } = classOfTwo('believed');
  const under = (send) => {
    const before = { ...b.state.lockedCalls };
    assert.equal(send().status, 200);
    return Object.fromEntries(Object.keys(before).map((k) => [k, b.state.lockedCalls[k] - before[k]]));
  };
  // Read under the lock: the check-ins and the practice entries; the solo sessions and the practice entries; the tab.
  for (const [route, s, reads] of [['how class went', asha, 2], ['how class went', bela, 2], ['how class went', bela, 2],
    ['a practice on one\'s own', asha, 2], ['a shared note', asha, 1], ['feedback', asha, 1]]) {
    assert.equal(under(() => BURSTS[route].send(b, s, id)).read, reads, route);
  }
});
