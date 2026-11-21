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
  assert.deepEqual(v.entries, [{ date: v.first, at: v.entries[0].at, kind: 'solo', hold_s: 30, reaction: null, pain: 1, note: 'Low back tight' }]);
  assert.equal(Date.parse(v.entries[0].at), b.clock() - 25 * 60000, 'the moment, for the phone to name the day in its own time zone');
});

test('a practice sent again with its request id is written once, even days later when the kept answer is long gone', () => {
  const { b, t, s } = student();
  const send = () => b.call('POST', '/me/solo', { token: s.token, requestId: 'run-1', body: { minutes: 20, entries: [{ item: 'vajrasana', reaction: 3 }] } });
  const first = send();
  assert.deepEqual(first, { status: 200, body: { ok: true, id: 1, saved: 1 } });
  b.state.offsetMs += 2 * DAY;
  b.cache.clear(); // the answer kept for a repeat lasts ten minutes at most, and the cache may drop it sooner
  assert.deepEqual(send(), first, 'the first answer again, from the row');
  const tab = (name) => b.ss.getSheetByName(name).rows().slice(1);
  assert.deepEqual([tab('solo_sessions').length, tab('practice').length], [1, 1]);
  assert.equal(b.call('POST', '/me/solo', { token: s.token, requestId: 'run-2', body: { minutes: 5, entries: [{ item: 'tadasana', reaction: 2 }] } }).body.id, 2,
    'another request id is another practice');
  const other = signup(b, '9000000003', { code: b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_code, name: 'Meera' });
  assert.equal(b.call('POST', '/me/solo', { token: other.token, requestId: 'run-1', body: { minutes: 5, entries: [{ item: 'tadasana', reaction: 2 }] } }).body.id, 3,
    'the same id from someone else is theirs');
});

test('a practice is dated by when it ended on the phone, if that is sane; else it ends now', () => {
  const { b, s } = student();
  const at = (endedAt) => {
    const r = b.call('POST', '/me/solo', { token: s.token, body: { minutes: 30, ended_at: endedAt, entries: [{ item: 'vajrasana', reaction: 3 }] } });
    assert.equal(r.status, 200, JSON.stringify(r));
    const row = b.ss.getSheetByName('solo_sessions').rows().at(-1);
    return [row[2].getTime(), row[3].getTime()];
  };
  const now = b.clock();
  const yesterday = new Date(now - DAY).toISOString();
  assert.deepEqual(at(yesterday), [now - DAY - 30 * 60000, now - DAY], 'sent a day late: it keeps its day');
  assert.deepEqual(at(new Date(now + 2 * 60000).toISOString()), [now - 30 * 60000, now], 'a phone clock a little ahead: now');
  assert.deepEqual(at(new Date(now + 60 * 60000).toISOString()), [now - 30 * 60000, now], 'far in the future: now');
  assert.deepEqual(at(new Date(now - 4 * DAY).toISOString()), [now - 30 * 60000, now], 'older than three days: now');
  assert.deepEqual(at('soon'), [now - 30 * 60000, now], 'no time: now');
  assert.deepEqual(at(null), [now - 30 * 60000, now]);
  const summary = b.call('GET', '/me/practice', { token: s.token, query: { days: 7 } }).body;
  assert.equal(summary.solo[0].at, new Date(now - DAY - 30 * 60000).toISOString().replace('.000Z', 'Z'), 'the late one on its own day');
  assert.deepEqual(summary.solo.map((x) => x.id), [1, 2, 3, 4, 5, 6]);
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
    const session = attend(b, s.user.id, 'beginner', ago, 3, 4);
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
  const session = attend(b, s.user.id, 'beginner', 2, 3, 4);
  for (const [id, item, reaction] of [[1, 'setu_bandhasana', 2], [2, 'vajrasana', 3]]) { // in class
    addRow(b, 'practice', { id, user_id: s.user.id, session_id: session, item, reaction, pain: 0, created_at: b.clock() - 2 * DAY,
      item_name: item, week: b.clock() - 2 * DAY });
  }
  solo(b, s.token, 20, [{ item: 'vajrasana', hold_s: 60 }, { item: 'bhujangasana', reaction: 3 }]);
  const en = b.call('GET', '/me/practice', { token: s.token, query: { days: 7 } }).body;
  assert.deepEqual(en.solo, [{ id: 1, date: en.solo[0].date, at: en.solo[0].at, minutes: 20, items: ['Vajrasana', 'Bhujangasana'] }]);
  assert.match(en.solo[0].at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  assert.match(en.solo[0].date, /^\d{4}-\d\d-\d\d$/);
  assert.equal(en.classes_joined, 1, 'practice on one\'s own is not a class');
  assert.deepEqual(en.items_on_own, [{ asana: 'Bhujangasana', times: 1, average_reaction: 3, pain_times: 0 },
    { asana: 'Vajrasana', times: 1, average_reaction: null, pain_times: 0 }], 'the most practised first, then by name');
  assert.deepEqual(en.items_in_class.map((i) => [i.asana, i.average_reaction]), [['Setu Bandhasana', 2], ['Vajrasana', 3]]);
  assert.ok(!en.items_on_own.some((i) => i.asana === 'Setu Bandhasana'), 'an item practised in class only is never one\'s own');
  const hi = b.call('GET', '/me/practice', { token: s.token, query: { days: 7, lang: 'hi' } }).body;
  assert.deepEqual(hi.solo[0].items, ['वज्रासन', 'भुजंगासन']);
});

test('a hold over an hour is kept as an hour, and the rest of the practice with it', () => {
  const { b, s } = student();
  const r = solo(b, s.token, 70, [{ item: 'vajrasana', hold_s: 3700, reaction: 3 }, { item: 'tadasana', hold_s: 30, reaction: 3 }]);
  assert.deepEqual(r, { status: 200, body: { ok: true, id: 1, saved: 2 } });
  const holds = (item) => b.call('GET', '/me/asanas/' + item, { token: s.token }).body.holds;
  assert.deepEqual([holds('vajrasana'), holds('tadasana')], [{ recent_seconds: 3600, longest_seconds: 3600 }, { recent_seconds: 30, longest_seconds: 30 }]);
});

test('the rules: something said, items from the library, a sensible length, members only', () => {
  const { b, s } = student();
  assert.deepEqual(solo(b, s.token, 5, [{ item: 'tadasana' }]), { status: 400, body: { detail: 'nothing_said' } });
  assert.deepEqual(solo(b, s.token, 5, [{ item: 'flying carpet', hold_s: 30 }]), { status: 400, body: { detail: 'unknown_item' } });
  assert.equal(solo(b, s.token, 241, [{ item: 'tadasana', hold_s: 30 }]).status, 422);
  assert.equal(solo(b, s.token, 5, [{ item: 'tadasana', hold_s: -1 }]).status, 422);
  assert.equal(solo(b, 'nope', 5, [{ item: 'tadasana', hold_s: 30 }]).status, 401);
  const pending = signup(b, '9000000003');
  assert.deepEqual(solo(b, pending.token, 5, [{ item: 'tadasana', hold_s: 30 }]), { status: 403, body: { detail: 'pending' } });
  assert.equal(b.ss.getSheetByName('solo_sessions').rows().length, 1, 'nothing written');
});
