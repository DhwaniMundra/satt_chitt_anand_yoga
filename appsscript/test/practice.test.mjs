// The routes for Gemma on the phone: the practice summary (practice_summary() of companion.py, from
// backend/tests/test_companion.py) and shared notes (the new routes' tests on the on-device branch).
import assert from 'node:assert/strict';
import test from 'node:test';
import { attend, freshBackend, signup, teacherAndCode } from './helpers.mjs';

function classmates(b) {
  const { t, code } = teacherAndCode(b);
  const asha = signup(b, '9000000002', { code, name: 'Asha Kulkarni' });
  const ravi = signup(b, '9000000003', { code, name: 'Ravi' });
  return { t, code, asha, ravi };
}

test('the practice summary does the sums for one student', () => {
  const b = freshBackend();
  const { asha, ravi } = classmates(b);
  attend(b, asha.user.id, 'hatha', 1, 3, 4);
  attend(b, asha.user.id, 'hatha', 3, 3, 5);
  attend(b, asha.user.id, 'pranayama', 2, 2, null);
  attend(b, asha.user.id, 'hatha', 20, 1, 1); // outside the week
  attend(b, ravi.user.id, 'hatha', 1, 5, 5); // someone else's, in the same class
  const week = b.call('GET', '/me/practice', { token: asha.token, query: { days: 7 } }).body;
  assert.equal(week.classes_joined, 3);
  assert.equal(week.average_mood_before, 2.7); // round(8 / 3, 1)
  assert.equal(week.average_mood_after, 4.5);
  assert.deepEqual(week.by_class['Hatha Yoga'], { times: 2, average_mood_before: 3, average_mood_after: 4.5 });
  assert.equal(week.by_class.Pranayama.average_mood_after, null);
  assert.deepEqual(Object.keys(week.by_class), ['Hatha Yoga', 'Pranayama']); // in the order first met, oldest first
  assert.deepEqual(Object.keys(week), ['period_days', 'classes_joined', 'mood_scale', 'average_mood_before', 'average_mood_after', 'by_class', 'classes']);
  assert.equal(week.mood_scale, '1 very low to 5 great');
  assert.deepEqual(week.classes.map((c) => [c.class, c.mood_before, c.mood_after]), [['Hatha Yoga', 3, 5], ['Pranayama', 2, null], ['Hatha Yoga', 3, 4]]);
  assert.match(week.classes[0].date, /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d\d (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$/);
});

test('the practice route is the summary for the signed-in student only', () => {
  const b = freshBackend();
  const { asha, ravi } = classmates(b);
  attend(b, asha.user.id, 'hatha', 1, 3, 4);
  attend(b, asha.user.id, 'hatha', 3, 3, 5);
  attend(b, asha.user.id, 'pranayama', 20, 2, null);
  const practice = (token, query) => b.call('GET', '/me/practice', { token, query });
  const week = practice(asha.token, { days: '7' }).body;
  assert.equal(week.classes_joined, 2);
  assert.equal(week.average_mood_after, 4.5);
  assert.equal(practice(asha.token, { days: '30' }).body.classes_joined, 3);
  assert.equal(practice(ravi.token, { days: '7' }).body.classes_joined, 0); // only one's own
  assert.equal(practice('', { days: '7' }).status, 401);
  assert.equal(practice(asha.token).body.period_days, 7); // a week unless asked
  assert.equal(practice(asha.token, { days: '400' }).body.period_days, 90);
  assert.equal(practice(asha.token, { days: '0' }).body.period_days, 1);
  assert.equal(b.call('GET', '/me/practice?days=30', { token: asha.token }).body.classes_joined, 3);
  assert.equal(practice(asha.token, { days: 'week' }).status, 422);
  assert.equal(practice(asha.token, { lang: 'de' }).status, 422);
});

test('the practice is for members and the teacher', () => {
  const b = freshBackend();
  const { t } = classmates(b);
  const pending = signup(b, '9000000004', { name: 'Meera' });
  assert.deepEqual(b.call('GET', '/me/practice', { token: pending.token }), { status: 403, body: { detail: 'pending' } });
  assert.deepEqual(b.call('GET', '/me/practice', { token: pending.token, query: { days: 'bad' } }).body, { detail: 'pending' }); // who, before what
  const teacher = b.call('GET', '/me/practice', { token: t.token }).body;
  assert.deepEqual(new Set(Object.keys(teacher)),
    new Set(['period_days', 'classes_joined', 'mood_scale', 'average_mood_before', 'average_mood_after', 'by_class', 'classes']));
  assert.equal(teacher.average_mood_before, null);
  assert.deepEqual(teacher.by_class, {});
});

test('the practice names classes in the student’s language', () => {
  const b = freshBackend();
  const { asha } = classmates(b);
  attend(b, asha.user.id, 'hatha', 1, 3, 4);
  const names = (lang) => Object.keys(b.call('GET', '/me/practice', { token: asha.token, query: { days: '7', lang } }).body.by_class);
  assert.deepEqual(names('hi'), ['हठ योग']);
  assert.deepEqual(names('mr'), ['हठयोग']);
  assert.deepEqual(names('en'), ['Hatha Yoga']);
});

test('averages round as Python’s round(x, 1) does', () => {
  const b = freshBackend();
  // Python: round(2.25, 1) == 2.2, round(2.75, 1) == 2.8, round(8 / 3, 1) == 2.7, round(3.35, 1) == 3.4
  const cases = [[2.25, 2.2], [2.75, 2.8], [1.25, 1.2], [4.75, 4.8], [3.25, 3.2], [8 / 3, 2.7], [3.35, 3.4], [4.5, 4.5], [2.125, 2.1], [3, 3]];
  for (const [x, want] of cases) assert.equal(b.evaluate('round1_(' + x + ')'), want, String(x));
  const { asha } = classmates(b);
  for (const [days, before] of [[1, 2], [2, 2], [3, 3], [4, 2]]) attend(b, asha.user.id, 'hatha', days, before, null); // mean 2.25
  assert.equal(b.call('GET', '/me/practice', { token: asha.token }).body.average_mood_before, 2.2);
});

test('a shared note reaches the teacher, and only that note', () => {
  const b = freshBackend();
  const { t, asha } = classmates(b);
  const shared = b.call('POST', '/me/shared', { token: asha.token, body: { text: ' My left knee hurts in Vajrasana. ' } }).body;
  assert.equal(shared.ok, true);
  assert.ok(Number.isInteger(shared.id));
  const again = b.call('POST', '/me/shared', { token: asha.token, body: { text: 'My left knee hurts in Vajrasana.' } }).body;
  assert.equal(again.id, shared.id); // a retried share is not a second note
  b.call('POST', '/me/shared', { token: asha.token, body: { text: 'Sore wrist' } });
  const notes = b.call('GET', '/teacher/shared', { token: t.token }).body.shared;
  assert.deepEqual(notes.map((n) => [n.user_id, n.name, n.text]),
    [[asha.user.id, 'Asha Kulkarni', 'Sore wrist'], [asha.user.id, 'Asha Kulkarni', 'My left knee hurts in Vajrasana.']]); // newest first
  assert.deepEqual(Object.keys(notes[0]), ['id', 'user_id', 'name', 'text', 'created_at']);
  assert.equal(b.call('GET', '/teacher/shared', { token: asha.token }).status, 403); // students cannot read them
});

test('the teacher sees the last fifty shared notes', () => {
  const b = freshBackend();
  const { t, asha } = classmates(b);
  for (let i = 0; i < 55; i++) b.call('POST', '/me/shared', { token: asha.token, body: { text: 'note ' + i } });
  const notes = b.call('GET', '/teacher/shared', { token: t.token }).body.shared;
  assert.equal(notes.length, 50);
  assert.equal(notes[0].text, 'note 54');
});

test('sharing is for approved students and checks the note', () => {
  const b = freshBackend();
  const { t, asha } = classmates(b);
  const pending = signup(b, '9000000004', { name: 'Meera' });
  const share = (token, text) => b.call('POST', '/me/shared', { token, body: { text } });
  assert.equal(share(pending.token, 'x').body.detail, 'pending');
  assert.equal(share(t.token, 'x').body.detail, 'pending');
  assert.equal(share(asha.token, '').status, 422);
  assert.deepEqual(share(asha.token, '   '), { status: 422, body: { detail: 'empty_note' } });
  assert.equal(share(asha.token, 'x'.repeat(501)).status, 422);
  assert.equal(share(asha.token, 'x'.repeat(500)).status, 200);
  assert.equal(share(t.token, '').status, 422); // the note is checked before the role, as FastAPI does
});
