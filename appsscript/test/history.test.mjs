// Each student's history per item, worked out in code, and the teacher's feedback on an item.
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, attend, DAY, freshBackend, signup, teacherAndCode } from './helpers.mjs';

/** A teacher, a student, and the student's reactions to Vajrasana over five past classes, oldest first. */
function withHistory() {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  const days = [9, 7, 5, 3, 1];
  const said = [[2, 1, 'Knee pinched'], [2, 1, null], [3, 0, null], [3, 0, 'Cushion helped'], [4, 0, null]];
  let id = 1;
  days.forEach((ago, i) => {
    const session = attend(b, s.user.id, 'hatha', ago, 3, 4);
    const [reaction, pain, note] = said[i];
    addRow(b, 'practice', { id: id++, user_id: s.user.id, session_id: session, item: 'vajrasana', reaction, pain, note,
      created_at: b.clock() - ago * DAY, item_name: 'Vajrasana', week: b.clock() - ago * DAY });
  });
  const tadasana = attend(b, s.user.id, 'hatha', 2, 3, 4);
  addRow(b, 'practice', { id: id++, user_id: s.user.id, session_id: tadasana, item: 'tadasana', reaction: 3, pain: 0,
    created_at: b.clock() - 2 * DAY, item_name: 'Tadasana', week: b.clock() - 2 * DAY });
  b.context.onEdit({});
  return { b, t, s };
}

test('a student\'s history of one item: the trend, strain or pain, the notes, every entry', () => {
  const { b, s } = withHistory();
  const v = b.call('GET', '/me/asanas/vajrasana', { token: s.token }).body;
  assert.equal(v.item, 'vajrasana');
  assert.equal(v.in_class, 5);
  assert.deepEqual(v.reaction_trend, { early_average: 2, recent_average: 3.5, each: 2 }); // 5 reactions: the first 2 and the last 2
  assert.deepEqual(v.strain_or_pain.times, 2);
  assert.equal(v.teacher_said, null);
  assert.deepEqual(v.your_notes.map((n) => n.text), ['Knee pinched', 'Cushion helped']);
  assert.deepEqual(v.entries.map((e) => e.reaction), [4, 3, 3, 2, 2], 'newest first');
  assert.match(v.first, /^\d{4}-\d\d-\d\d$/);
  assert.ok(v.first < v.last);
  const none = b.call('GET', '/me/asanas/padmasana', { token: s.token }).body;
  assert.deepEqual([none.in_class, none.reaction_trend, none.entries.length], [0, null, 0]);
});

test('the list of a student\'s items, strain or pain first', () => {
  const { b, s } = withHistory();
  const items = b.call('GET', '/me/asanas', { token: s.token }).body.items;
  assert.deepEqual(items.map((i) => [i.item, i.in_class, i.pain_times]), [['vajrasana', 5, 2], ['tadasana', 1, 0]]);
  assert.equal(items[1].reaction_trend, null, 'one reaction is no trend');
});

test('the teacher reads a student\'s history and writes feedback on an item, which the student sees', () => {
  const { b, t, s } = withHistory();
  const path = '/teacher/students/' + s.user.id;
  assert.deepEqual(b.call('GET', path + '/asanas', { token: t.token }).body.items.map((i) => i.item), ['vajrasana', 'tadasana']);
  assert.equal(b.call('GET', path + '/asanas/vajrasana', { token: t.token }).body.in_class, 5);
  const said = (item, text, token = t.token) => b.call('POST', path + '/feedback', { token, body: { item, text } });
  assert.equal(said('vajrasana', '  Keep the cushion; come out at the first sign of knee pain. ').body.ok, true);
  b.state.offsetMs += 1000;
  assert.equal(said('vajrasana', 'Much steadier this week.').status, 200);
  assert.equal(said('padmasana', 'Not yet for you: the knees first.').status, 200);
  const v = b.call('GET', '/me/asanas/vajrasana', { token: s.token }).body;
  assert.equal(v.teacher_said.text, 'Much steadier this week.');
  assert.deepEqual(v.feedback.map((f) => f.text), ['Much steadier this week.', 'Keep the cushion; come out at the first sign of knee pain.']);
  const items = b.call('GET', '/me/asanas', { token: s.token }).body.items;
  assert.deepEqual(items.map((i) => i.item), ['vajrasana', 'padmasana', 'tadasana'], 'strain or pain, then the teacher\'s word, then the rest');
  assert.deepEqual([items[1].in_class, items[1].last], [0, null], 'an item with feedback only is listed too');
  assert.equal(said('flying carpet', 'x').body.detail, 'unknown_item');
  assert.equal(said('vajrasana', '').status, 422);
  assert.deepEqual(said('vajrasana', 'x', s.token), { status: 403, body: { detail: 'teacher_only' } });
  assert.deepEqual(b.call('GET', '/teacher/students/' + t.user.id + '/asanas', { token: t.token }), { status: 404, body: { detail: 'no_student' } });
  assert.equal(b.call('GET', '/teacher/students/' + s.user.id + '/asanas', { token: s.token }).status, 403);
});

test('a pending student has no history yet', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const p = signup(b, '9000000003');
  assert.deepEqual(b.call('GET', '/me/asanas', { token: p.token }), { status: 403, body: { detail: 'pending' } });
});
