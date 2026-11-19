// Practice on a student's own: a stopwatch per item, how it went, and where it shows: each item's history and the
// practice summary.
import assert from 'node:assert/strict';
import test from 'node:test';
import { addRow, attend, DAY, freshBackend, signup, teacherAndCode } from './helpers.mjs';

function student() {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  return { b, t, s };
}

const solo = (b, token, minutes, entries) => b.call('POST', '/me/solo', { token, body: { minutes, entries } });

test('a session on one\'s own keeps each item timed or said, dated by the server', () => {
  const { b, s } = student();
  const r = solo(b, s.token, 25, [
    { item: 'vajrasana', hold_s: 90, reaction: 3 },
    { item: 'bhujangasana', hold_s: 30, pain: 1, note: '  Low back tight ' },
    { item: 'tadasana' }, // nothing timed or said: not kept
  ]);
  assert.deepEqual(r, { status: 200, body: { ok: true, id: 1, saved: 2 } });
  const [session] = b.ss.getSheetByName('solo_sessions').rows().slice(1);
  assert.equal(session[3].getTime() - session[2].getTime(), 25 * 60000, 'it ended now and began 25 minutes ago');
  const v = b.call('GET', '/me/asanas/bhujangasana', { token: s.token }).body;
  assert.deepEqual([v.in_class, v.solo, v.holds, v.strain_or_pain.times], [0, 1, { recent_seconds: 30, longest_seconds: 30 }, 1]);
  assert.deepEqual(v.entries, [{ date: v.first, kind: 'solo', hold_s: 30, reaction: null, pain: 1, note: 'Low back tight' }]);
});

test('the holds: the latest and the longest', () => {
  const { b, s } = student();
  for (const hold of [45, 120, 100]) {
    assert.equal(solo(b, s.token, 10, [{ item: 'vajrasana', hold_s: hold }]).status, 200);
    b.state.offsetMs += DAY;
  }
  const v = b.call('GET', '/me/asanas/vajrasana', { token: s.token }).body;
  assert.deepEqual(v.holds, { recent_seconds: 100, longest_seconds: 120 });
  assert.deepEqual(v.entries.map((e) => e.hold_s), [100, 120, 45], 'newest first');
  assert.equal(v.reaction_trend, null, 'timed but not rated: no trend');
});

test('an item\'s history mixes classes and practice on one\'s own, in order', () => {
  const { b, t, s } = student();
  [4, 2].forEach((ago, i) => {
    const session = attend(b, s.user.id, 'hatha', ago, 3, 4);
    addRow(b, 'practice', { id: i + 1, user_id: s.user.id, session_id: session, item: 'vajrasana', reaction: 2, pain: 0,
      created_at: b.clock() - ago * DAY, item_name: 'Vajrasana', week: b.clock() - ago * DAY });
  });
  b.context.onEdit({});
  assert.equal(solo(b, s.token, 15, [{ item: 'vajrasana', hold_s: 60, reaction: 4 }, { item: 'tadasana', reaction: 3 }]).status, 200);
  const v = b.call('GET', '/me/asanas/vajrasana', { token: s.token }).body;
  assert.deepEqual([v.in_class, v.solo], [2, 1]);
  assert.deepEqual(v.entries.map((e) => [e.kind, e.reaction]), [['solo', 4], ['class', 2], ['class', 2]]);
  assert.deepEqual(v.reaction_trend, { early_average: 2, recent_average: 4, each: 1 });
  const items = b.call('GET', '/me/asanas', { token: s.token }).body.items;
  assert.deepEqual(items.map((i) => [i.item, i.in_class, i.solo]), [['vajrasana', 2, 1], ['tadasana', 0, 1]], 'the most practised first');
  const review = b.call('GET', '/teacher/students/' + s.user.id + '/asanas/vajrasana', { token: t.token }).body;
  assert.equal(review.solo, 1, 'the teacher sees it too');
});

test('the practice summary lists the sessions on one\'s own, with the item names in the language asked', () => {
  const { b, s } = student();
  solo(b, s.token, 20, [{ item: 'vajrasana', hold_s: 60 }, { item: 'bhujangasana', reaction: 3 }]);
  const en = b.call('GET', '/me/practice', { token: s.token, query: { days: 7 } }).body;
  assert.deepEqual(en.solo, [{ date: en.solo[0].date, minutes: 20, items: ['Vajrasana', 'Bhujangasana'] }]);
  assert.match(en.solo[0].date, /^\d{4}-\d\d-\d\d$/);
  assert.equal(en.classes_joined, 0, 'practice on one\'s own is not a class');
  const hi = b.call('GET', '/me/practice', { token: s.token, query: { days: 7, lang: 'hi' } }).body;
  assert.deepEqual(hi.solo[0].items, ['वज्रासन', 'भुजंगासन']);
});

test('the rules: something said, items from the library, a sensible length, members only', () => {
  const { b, s } = student();
  assert.deepEqual(solo(b, s.token, 5, [{ item: 'tadasana' }]), { status: 400, body: { detail: 'nothing_said' } });
  assert.deepEqual(solo(b, s.token, 5, [{ item: 'flying carpet', hold_s: 30 }]), { status: 400, body: { detail: 'unknown_item' } });
  assert.equal(solo(b, s.token, 241, [{ item: 'tadasana', hold_s: 30 }]).status, 422);
  assert.equal(solo(b, s.token, 5, [{ item: 'tadasana', hold_s: 3601 }]).status, 422);
  assert.equal(solo(b, 'nope', 5, [{ item: 'tadasana', hold_s: 30 }]).status, 401);
  const pending = signup(b, '9000000003');
  assert.deepEqual(solo(b, pending.token, 5, [{ item: 'tadasana', hold_s: 30 }]), { status: 403, body: { detail: 'pending' } });
  assert.equal(b.ss.getSheetByName('solo_sessions').rows().length, 1, 'nothing written');
});
