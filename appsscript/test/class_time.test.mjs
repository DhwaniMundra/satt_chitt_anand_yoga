// A class's own time, set by the teacher from the app: its start on its own date and its length; what the students
// see, what the week's making leaves alone, what is refused, and the reset that gives the class back to its batch.
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, attend, DAY, freshBackend, MIN, signup, teacherAndCode, WEDNESDAY_6AM } from './helpers.mjs';

const HOUR = 60 * MIN;

/** Wednesday 6:00 in India: the teacher, and Asha in the beginners' batch, whose class is at 7:00. */
function studio(now = WEDNESDAY_6AM) {
  const b = freshBackend({ now });
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  return { b, t, s, code };
}

const teacherDay = (b, t) => b.call('GET', '/teacher/home', { token: t.token }).body;
const move = (b, t, id, time, minutes) => b.call('PUT', '/teacher/sessions/' + id + '/time', { token: t.token, body: { time, duration_min: minutes } });
const beginners = (b, t) => teacherDay(b, t).sessions.find((x) => x.batch.key === 'beginner');
const ist = (iso) => new Date(Date.parse(iso) + 330 * MIN).toISOString().slice(11, 16);

test('the teacher gives a class a time of its own: the students see it, and the week\'s making leaves it there', () => {
  const { b, t, s } = studio();
  const before = beginners(b, t);
  assert.deepEqual([ist(before.starts_at), before.duration_min, before.time_set], ['07:00', 55, false]);
  const r = move(b, t, before.id, '10:15', 30);
  assert.equal(r.status, 200, JSON.stringify(r));
  assert.deepEqual([r.body.id, ist(r.body.starts_at), r.body.duration_min, r.body.time_set], [before.id, '10:15', 30, true]);
  assert.equal(r.body.starts_at.slice(0, 10), before.starts_at.slice(0, 10), 'on its own date');
  const home = b.call('GET', '/home', { token: s.token }).body;
  assert.deepEqual([home.sessions[0].id, ist(home.sessions[0].starts_at), home.sessions[0].duration_min], [before.id, '10:15', 30]);
  const [header, ...rows] = b.ss.getSheetByName('class_sessions').rows();
  assert.equal(rows.find((x) => x[0] === before.id)[header.indexOf('time_set_by')], 'teacher', 'marked in its row');

  b.cache.clear(); // the week is made again, as after ten minutes
  b.context.onEdit({});
  assert.equal(ist(beginners(b, t).starts_at), '10:15', 'not moved back to the batch\'s time');
  const sheet = b.ss.getSheetByName('batches');
  sheet.getRange(2, sheet.rows()[0].indexOf('time') + 1).setValue("'06:30"); // the owner changes the batch's time
  b.context.onEdit({});
  const after = teacherDay(b, t).sessions.find((x) => x.batch.key === 'beginner');
  assert.deepEqual([after.id, ist(after.starts_at)], [before.id, '10:15'], 'nor to its new time');
  const thursday = b.call('GET', '/home', { token: s.token }).body.sessions.find((x) => x.id !== before.id);
  assert.equal(ist(thursday.starts_at), '06:30', 'the next day\'s class follows the batch\'s new time');
  assert.equal(b.ss.getSheetByName('class_sessions').rows().slice(1).filter((x) => x[1] === 'beginner' &&
    x[2].getTime() >= WEDNESDAY_6AM && x[2].getTime() < WEDNESDAY_6AM + 18 * HOUR).length, 1, 'still one class that day');
});

test('a class over for the day starts again later today, ten minutes long: check-in and after-class open at once', () => {
  const { b, t, s } = studio();
  b.state.offsetMs += 13 * HOUR; // 19:00: the day's classes are over, and the teacher's day is Thursday's
  const day = teacherDay(b, t);
  assert.ok(day.sessions.every((x) => x.starts_at.slice(0, 10) === '2026-11-19'), 'Thursday\'s');
  const over = day.earlier.find((x) => x.batch.key === 'beginner');
  assert.deepEqual([ist(over.starts_at), over.joined], ['07:00', 0], 'today\'s, to give a later time');
  assert.equal(day.earlier.length, 4);
  assert.equal(move(b, t, over.id, '19:05', 10).status, 200);
  const today = teacherDay(b, t);
  assert.deepEqual(today.sessions.map((x) => [x.id, ist(x.starts_at)]), [[over.id, '19:05']], 'the teacher\'s day is today again');
  assert.equal(today.earlier.length, 3);
  assert.equal(b.call('POST', '/sessions/' + over.id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  b.state.offsetMs += 6 * MIN; // 19:06, a minute in
  const home = b.call('GET', '/home', { token: s.token }).body;
  assert.equal(home.after_class.id, over.id, 'after class is open from the start');
  assert.equal(b.call('POST', '/sessions/' + over.id + '/checkin', { token: s.token, body: { phase: 'after', mood: 4 } }).status, 200);
  assert.equal(move(b, t, over.id, '20:00', 30).body.detail, 'class_answered', 'said how it went: it stays');
});

test('check-ins before a class move with it; answers after it, or practice said about it, keep it where it was', () => {
  const { b, t, s } = studio();
  const id = beginners(b, t).id;
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  const moved = move(b, t, id, '11:00', 55);
  assert.deepEqual([moved.status, moved.body.joined], [200, 1], 'the check-in comes along');
  const [header, ...rows] = b.ss.getSheetByName('checkins').rows();
  assert.equal(rows[0][header.indexOf('session_id')], id);
  const other = teacherDay(b, t).sessions.find((x) => x.batch.key === 'intermediate').id;
  addRow(b, 'practice', { id: 1, user_id: s.user.id, session_id: other, item: 'vajrasana', reaction: 3, pain: 0, created_at: b.clock(),
    item_name: 'Vajrasana', week: b.clock() });
  b.context.onEdit({});
  assert.deepEqual(move(b, t, other, '12:00', 55), { status: 400, body: { detail: 'class_answered' } });
});

test('the rules: a time on the clock, 10 minutes to 3 hours, no overlap with the batch\'s other classes, not an earlier day, the teacher only', () => {
  const { b, t, s } = studio();
  const id = beginners(b, t).id;
  for (const time of ['25:00', '7.30', 'seven', '12:60', '']) {
    const r = move(b, t, id, time, 30);
    assert.ok(r.status === 400 || r.status === 422, time + ': ' + JSON.stringify(r));
    if (r.status === 400) assert.equal(r.body.detail, 'bad_time');
  }
  assert.equal(move(b, t, id, '७:३०', 30).status, 200, 'Devanagari digits read as typed');
  assert.equal(move(b, t, id, '7:30', 9).status, 422);
  assert.equal(move(b, t, id, '7:30', 181).status, 422);
  assert.equal(move(b, t, id, '7:30', 180).status, 200);
  addRow(b, 'class_sessions', { id: 900, batch: 'beginner', starts_at: Date.parse('2026-11-18T07:30:00Z'), duration_min: 30, updated_at: b.clock() });
  b.context.onEdit({}); // a second class that day, 13:00 to 13:30 in India, added by hand
  assert.deepEqual(move(b, t, id, '12:30', 45), { status: 400, body: { detail: 'class_overlap' } });
  assert.equal(move(b, t, id, '12:30', 30).status, 200, 'ending as the other starts');
  assert.equal(move(b, t, teacherDay(b, t).sessions.find((x) => x.batch.key === 'intermediate').id, '13:00', 30).status, 200,
    'another batch\'s class may share the time');
  const past = attend(b, s.user.id, 'beginner', 1, 3, 4);
  assert.deepEqual(move(b, t, past, '18:00', 30), { status: 400, body: { detail: 'class_past' } });
  assert.equal(move(b, t, 99999, '18:00', 30).status, 404);
  assert.equal(b.call('PUT', '/teacher/sessions/' + id + '/time', { token: s.token, body: { time: '18:00', duration_min: 30 } }).status, 403);
});

test('a time already over is refused: 6:30 typed at 15:00 for the 18:30 class; one under way, or later, is not', () => {
  const { b, t } = studio(WEDNESDAY_6AM + 9 * HOUR); // 15:00
  const id = teacherDay(b, t).sessions.find((x) => x.batch.key === 'pain_management').id; // 17:30
  assert.deepEqual(move(b, t, id, '6:30', 55), { status: 400, body: { detail: 'class_past' } });
  assert.deepEqual(move(b, t, id, '14:00', 60), { status: 400, body: { detail: 'class_past' } }, 'ending as now: over');
  assert.equal(ist(teacherDay(b, t).sessions.find((x) => x.id === id).starts_at), '17:30', 'left as it was');
  assert.equal(move(b, t, id, '14:55', 10).status, 200, 'started five minutes ago, five to go: under way');
  assert.equal(move(b, t, id, '18:30', 45).status, 200);
});

test('a move is written once for its request id, and runs under the lock', () => {
  const { b, t } = studio();
  const id = beginners(b, t).id;
  const send = () => b.call('PUT', '/teacher/sessions/' + id + '/time', { token: t.token, requestId: 'move-1', body: { time: '15:00', duration_min: 20 } });
  const locks = b.state.locks;
  const first = send();
  assert.equal(b.state.locks, locks + 1);
  assert.deepEqual(send(), first);
});

test('a reset gives each class the teacher moved back to its batch\'s time', () => {
  const { b, t } = studio();
  const day = teacherDay(b, t).sessions;
  assert.equal(move(b, t, day[0].id, '10:15', 30).status, 200);
  assert.equal(move(b, t, day[1].id, '11:40', 20).status, 200);
  const out = JSON.parse(b.evaluate('JSON.stringify(resetStudio_(new Db_()))'));
  assert.equal(out.cleared, 2);
  const teacher = signup(b, '9000000009', { role: 'teacher', code: 'TEACH123' });
  const again = teacherDay(b, teacher);
  assert.deepEqual(again.sessions.slice(0, 2).map((x) => [x.id, ist(x.starts_at), x.duration_min, x.time_set]),
    [[day[0].id, '07:00', 55, false], [day[1].id, '08:00', 55, false]]);
});

test('the time of a class of the coming days moves on its own date', () => {
  const { b, t } = studio(WEDNESDAY_6AM + 13 * HOUR);
  const thursday = teacherDay(b, t).sessions[0];
  assert.equal(thursday.starts_at.slice(0, 10), '2026-11-19');
  const r = move(b, t, thursday.id, '05:30', 15);
  assert.equal(r.body.starts_at, '2026-11-19T00:00:00Z', '5:30 on Thursday in India');
  assert.ok(Date.parse(r.body.starts_at) - b.clock() < DAY);
});
