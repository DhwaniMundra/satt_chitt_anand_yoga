// The curriculum (seeded tabs, each class's plan) and how each item went after class.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { ROOT } from './fakes.mjs';
import { classStarted, freshBackend, MIN, signup, teacherAndCode, WEDNESDAY_6AM } from './helpers.mjs';

const CONTENT = JSON.parse(readFileSync(join(ROOT, '..', 'content', 'curriculum.json'), 'utf8'));
const TEACHER = JSON.parse(readFileSync(join(ROOT, '..', 'content', 'studio.json'), 'utf8')).teacher.short; // per language

/** A class that started `minutesAgo` minutes ago, a student who checked in before it, and the teacher. */
function classWithStudent(minutesAgo = 50) {
  const b = freshBackend();
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code, name: 'Asha' });
  const id = classStarted(b, minutesAgo);
  b.state.offsetMs -= (minutesAgo - 10) * MIN; // back to 10 minutes into the class, for the "before" check-in
  assert.equal(b.call('POST', '/sessions/' + id + '/checkin', { token: s.token, body: { phase: 'before', mood: 3 } }).status, 200);
  b.state.offsetMs += (minutesAgo - 10) * MIN;
  return { b, t, s, id };
}

const practice = (b, token, id, entries) => b.call('POST', '/sessions/' + id + '/practice', { token, body: { entries } });

test('setup seeds the curriculum tabs once, and leaves the owner\'s edits alone', () => {
  const b = freshBackend();
  const rows = (tab) => b.ss.getSheetByName(tab).rows().slice(1);
  const items = CONTENT.curricula.reduce((n, c) => n + c.items.length, 0);
  assert.equal(rows('library').length, CONTENT.library.length);
  assert.equal(rows('curricula').length, 3);
  assert.equal(rows('curriculum_items').length, items);
  assert.ok(b.ss.getSheetByName('curricula').notes['1:1'].startsWith('A mock curriculum for ' + TEACHER.en + ' to confirm.'));
  b.ss.getSheetByName('curricula').getRange(2, 2).setValue("'Foundations");
  b.context.setup();
  assert.equal(rows('curriculum_items').length, items);
  assert.equal(rows('curricula')[0][1], 'Foundations');
});

test('the curricula in the student\'s language, items in order', () => {
  const b = freshBackend();
  const { code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  assert.equal(b.call('GET', '/curricula').status, 401);
  const hi = b.call('GET', '/curricula', { token: s.token, query: { lang: 'hi' } }).body;
  assert.deepEqual(hi.curricula.map((c) => c.name), ['शुरुआती', 'मध्यम', 'उन्नत']);
  const beginner = hi.curricula[0];
  assert.deepEqual(beginner.items.slice(0, 3).map((i) => i.item), ['sectional_breathing', 'omkar', 'tadasana']);
  assert.deepEqual(beginner.items[3], { item: 'vrikshasana', dose: 5, unit: 'breaths', cue: 'दोनों ओर। पैर पिंडली या जाँघ पर, घुटने पर कभी नहीं।' });
  const vajrasana = hi.library.find((i) => i.key === 'vajrasana');
  assert.deepEqual(vajrasana, { key: 'vajrasana', type: 'asana', level: 1, sanskrit: 'वज्रासन', name: 'Vajrasana', english: 'Thunderbolt pose',
    aliases: ['vajrasan', 'vajra', 'diamond pose', 'thunderbolt', 'kneeling pose'] });
  const shirshasana = (lang) => b.call('GET', '/curricula', { token: s.token, query: { lang } }).body.curricula[2].items.find((i) => i.item === 'shirshasana');
  assert.ok(shirshasana('en').cue.startsWith('With ' + TEACHER.en + ' only.'), 'the teacher named as the studio names him');
  assert.ok(shirshasana('mr').cue.startsWith('फक्त ' + TEACHER.mr + ' यांच्यासोबत.'));
});

test('a class follows its own curriculum, else the last one used for its kind, else Beginner', () => {
  const b = freshBackend({ now: WEDNESDAY_6AM }); // the week ahead holds two Hatha classes
  const { t, code } = teacherAndCode(b);
  const s = signup(b, '9000000002', { code });
  const week = b.call('GET', '/teacher/home', { token: t.token }).body.sessions;
  assert.ok(week.every((x) => x.curriculum === 'beginner'));
  const hatha = week.filter((x) => x.class.key === 'hatha');
  assert.equal(hatha.length, 2); // Friday, then Monday
  const set = (id, curriculum, token = t.token) => b.call('PUT', '/teacher/sessions/' + id + '/curriculum', { token, body: { curriculum } });
  assert.deepEqual(set(hatha[0].id, 'intermediate').body, { ok: true, curriculum: 'intermediate' });
  const after = b.call('GET', '/home', { token: s.token }).body.sessions;
  const plan = (id) => after.find((x) => x.id === id).curriculum;
  assert.equal(plan(hatha[0].id), 'intermediate');
  assert.equal(plan(hatha[1].id), 'intermediate', 'the next Hatha class follows the last one');
  assert.ok(after.filter((x) => x.class.key !== 'hatha').every((x) => x.curriculum === 'beginner'));
  assert.equal(set(hatha[1].id, 'advanced').status, 200);
  assert.equal(b.call('GET', '/home', { token: s.token }).body.sessions.find((x) => x.id === hatha[0].id).curriculum, 'intermediate');
  assert.deepEqual(set(hatha[0].id, 'expert').body, { detail: 'no_curriculum' });
  assert.deepEqual(set(hatha[0].id, 'advanced', s.token), { status: 403, body: { detail: 'teacher_only' } });
});

test('after class, a student says how each item went; a second send replaces the first', () => {
  const { b, t, s, id } = classWithStudent();
  const r = practice(b, s.token, id, [
    { item: 'vajrasana', reaction: 2, pain: 1, note: '  Left knee pinched ' },
    { item: 'tadasana', reaction: 4 },
    { item: 'trikonasana' }, // nothing said: not kept
  ]);
  assert.deepEqual(r, { status: 200, body: { ok: true, saved: 2 } });
  const tab = () => b.ss.getSheetByName('practice').rows().slice(1);
  assert.deepEqual(tab().map((row) => [row[3], row[4], row[5], row[6], row[8]]),
    [['vajrasana', 2, 1, 'Left knee pinched', 'Vajrasana'], ['tadasana', 4, 0, '', 'Tadasana']]);
  assert.equal(new Date(tab()[0][9].getTime() + 330 * MIN).getUTCDay(), 1, 'the week is its Monday, in India');
  assert.equal(practice(b, s.token, id, [{ item: 'vajrasana', reaction: 3 }]).body.saved, 1);
  assert.deepEqual(tab().map((row) => [row[3], row[4]]), [['vajrasana', 3]]);
  assert.deepEqual(b.call('GET', '/home', { token: s.token }).body.after_checkin.said,
    { mood: null, items: [{ item: 'vajrasana', reaction: 3, pain: 0, note: null }] }, 'what was said, to change it');
  assert.equal(practice(b, t.token, id, []).body.detail, 'checkin_closed');
});

test('the after-class window and the checks on what is sent', () => {
  const { b, t, s, id } = classWithStudent(20); // 35 minutes before the end: too early
  assert.equal(practice(b, s.token, id, [{ item: 'vajrasana', reaction: 3 }]).body.detail, 'checkin_closed');
  b.state.offsetMs += 30 * MIN;
  assert.equal(practice(b, s.token, id, [{ item: 'vajrasana', reaction: 3 }]).status, 200);
  const other = signup(b, '9000000003', { code: b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_code });
  assert.equal(practice(b, other.token, id, []).body.detail, 'checkin_closed', 'did not check in before class');
  assert.equal(practice(b, s.token, id, [{ item: 'flying carpet', reaction: 3 }]).body.detail, 'unknown_item');
  const bad = practice(b, s.token, id, [{ item: 'vajrasana', reaction: 5, pain: 2 }, 'x']).body.detail;
  assert.deepEqual(bad.map((e) => e.type + ' ' + e.loc.join('.')),
    ['less_than_equal body.entries.0.reaction', 'less_than_equal body.entries.0.pain', 'model_type body.entries.1']);
  assert.equal(practice(b, s.token, id, 'vajrasana').body.detail[0].type, 'list_type');
  b.state.offsetMs += 13 * 60 * MIN;
  assert.equal(practice(b, s.token, id, [{ item: 'vajrasana', reaction: 3 }]).body.detail, 'checkin_closed');
});

test('the teacher\'s review of a class: counts per item, strain or pain first, then notes', () => {
  const { b, t, s, id } = classWithStudent();
  const code = b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_code;
  const m = signup(b, '9000000003', { code, name: 'Meera' });
  b.state.offsetMs -= 40 * MIN;
  b.call('POST', '/sessions/' + id + '/checkin', { token: m.token, body: { phase: 'before', mood: 2 } });
  b.state.offsetMs += 40 * MIN;
  practice(b, s.token, id, [{ item: 'tadasana', reaction: 4, note: 'Steady today' }, { item: 'vajrasana', reaction: 2, pain: 1, note: 'Knee' }]);
  practice(b, m.token, id, [{ item: 'tadasana', reaction: 3 }, { item: 'vajrasana', reaction: 3 }]);
  const review = b.call('GET', '/teacher/sessions/' + id + '/practice', { token: t.token }).body;
  assert.equal(review.curriculum, 'beginner');
  assert.equal(review.joined, 2);
  assert.equal(review.answered, 2);
  assert.equal(review.items.length, CONTENT.curricula[0].items.length);
  assert.deepEqual(review.items[0], { item: 'vajrasana', reactions: [0, 1, 1, 0], pain: [{ name: 'Asha', note: 'Knee' }], notes: [] });
  const tadasana = review.items.find((i) => i.item === 'tadasana');
  assert.deepEqual(tadasana, { item: 'tadasana', reactions: [0, 0, 1, 1], pain: [], notes: [{ name: 'Asha', text: 'Steady today' }] });
  assert.deepEqual(review.items[1].item, 'sectional_breathing', 'then the plan in order');
  assert.equal(b.call('GET', '/teacher/sessions/' + id + '/practice', { token: s.token }).status, 403);
});
