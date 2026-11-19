// The intake: a student's answers about themselves, for the teacher to place them in a batch. Health data: only the
// student and the teacher read it.
import assert from 'node:assert/strict';
import test from 'node:test';
import { freshBackend, signup, teacherAndCode } from './helpers.mjs';

const answers = (over = {}) => Object.assign({
  age: 52, height_cm: 160, weight_kg: 68, food: 'vegetarian', meals: '  Poha, dal-rice, rotis  ', pain: 'Knee, back', pain_note: 'Left knee on stairs',
  ratings: [{ item: 'tadasana', reaction: 4 }, { item: 'vajrasana', reaction: 1, pain: 1 }, { item: 'trikonasana' }],
}, over);

test('a waiting student fills the intake; the teacher sees it, with the batch it points to', () => {
  const b = freshBackend();
  const { t } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  assert.deepEqual(b.call('GET', '/me/intake', { token: s.token }).body, { intake: null });
  const r = b.call('PUT', '/me/intake', { token: s.token, body: answers() });
  assert.equal(r.status, 200, JSON.stringify(r));
  const intake = r.body.intake;
  assert.deepEqual([intake.age, intake.height_cm, intake.weight_kg, intake.food, intake.meals], [52, 160, 68, 'vegetarian', 'Poha, dal-rice, rotis']);
  assert.deepEqual([intake.pain, intake.pain_note], [['knee', 'back'], 'Left knee on stairs']);
  assert.deepEqual(intake.ratings, [{ item: 'tadasana', reaction: 4, pain: 0 }, { item: 'vajrasana', reaction: 1, pain: 1 }], 'nothing said: not kept');
  assert.equal(intake.suggested_batch, 'pain_management');
  const seen = b.call('GET', '/teacher/students', { token: t.token }).body.students.find((x) => x.id === s.user.id);
  assert.deepEqual(seen.intake, intake);
  const again = b.call('PUT', '/me/intake', { token: s.token, body: answers({ pain: null, pain_note: null, ratings: [{ item: 'tadasana', reaction: 3 }] }) });
  assert.deepEqual([again.body.intake.pain, again.body.intake.ratings.length], [[], 1], 'a second send replaces the first');
  assert.equal(b.ss.getSheetByName('intake').rows().length, 2, 'one row per student');
});

test('the batch the answers point to: pain, Pain management; mostly steady, Intermediate; else Beginner; never Advanced', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const s = signup(b, '9000000002');
  const suggest = (over) => b.call('PUT', '/me/intake', { token: s.token, body: answers(Object.assign({ pain: null }, over)) }).body.intake.suggested_batch;
  const all = (reaction, pain = 0) => ['tadasana', 'vrikshasana', 'trikonasana', 'vajrasana', 'bhujangasana', 'paschimottanasana']
    .map((item) => ({ item, reaction, pain }));
  assert.equal(suggest({ ratings: all(4) }), 'intermediate');
  assert.equal(suggest({ ratings: all(2) }), 'beginner');
  assert.equal(suggest({ ratings: all(3).slice(0, 3) }), 'beginner', 'too few answered to say');
  assert.equal(suggest({ ratings: all(4, 1) }), 'pain_management', 'strain or pain in the self-assessment');
  assert.equal(suggest({ pain: 'neck', ratings: all(4) }), 'pain_management');
});

test('the answers are checked', () => {
  const b = freshBackend();
  teacherAndCode(b);
  const s = signup(b, '9000000002');
  const send = (over) => b.call('PUT', '/me/intake', { token: s.token, body: answers(over) });
  assert.equal(send({ age: 3 }).status, 422);
  assert.equal(send({ height_cm: 300 }).status, 422);
  assert.equal(send({ food: 'fruitarian' }).status, 422);
  assert.equal(send({ ratings: [{ item: 'tadasana', reaction: 5 }] }).status, 422);
  assert.deepEqual(send({ pain: 'knee, elbow' }).body, { detail: 'bad_pain_area' });
  assert.deepEqual(send({ ratings: [{ item: 'shirshasana', reaction: 2 }] }).body, { detail: 'unknown_item' }, 'only the assessment asanas');
  assert.equal(b.ss.getSheetByName('intake').rows().length, 1, 'nothing written');
});

test('only the student and the teacher read it', () => {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002');
  const other = signup(b, '9000000003', { code });
  b.call('PUT', '/me/intake', { token: s.token, body: answers() });
  assert.deepEqual(b.call('GET', '/me/intake', { token: other.token }).body, { intake: null }, 'their own, never another\'s');
  assert.deepEqual(b.call('GET', '/teacher/students', { token: other.token }), { status: 403, body: { detail: 'teacher_only' } });
  assert.deepEqual(b.call('PUT', '/me/intake', { token: t.token, body: answers() }), { status: 403, body: { detail: 'students_only' } });
  assert.equal(b.call('GET', '/me/intake').status, 401);
  assert.ok(b.ss.getSheetByName('intake').isSheetHidden() && b.ss.getSheetByName('intake_ratings').isSheetHidden());
});
