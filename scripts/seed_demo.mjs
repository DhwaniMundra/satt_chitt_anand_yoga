// Writes a data file for the dev backend filled with SYNTHETIC demo data, for demos, tours and screenshots. Every
// person, check-in and comment is invented: never present the Insights screen of the demo as results.
//
//   node scripts/seed_demo.mjs data/demo.json
//
// Logins (password demo123): teacher 9800000001; students 9800000002 to 9800000006, each in a batch; 9800000007
// waits to be placed.
// People sign up through the API, as in the app; the two weeks of past classes, check-ins and practice on one's own,
// which the API cannot date in the past, are written straight into the Sheet's tabs.
import { existsSync, readFileSync } from 'node:fs';
import { addRow, DAY, MIN } from '../appsscript/test/helpers.mjs';
import { open } from './dev_backend.mjs';

const PASSWORD = 'demo123';
const SPAN = 20; // days of classes before today, since the students were placed
const STUDENTS = ['Asha Kulkarni', 'Meera Iyer', 'Rohan Desai', 'Kavita Joshi', 'Sunil Patil', 'Neha Rao']; // the last waits
// The teacher's placements and moves: (student by index, days ago, to, note). Asha moved up after a review.
const PLACEMENTS = [
  [0, 20, 'beginner', 'New to yoga; knees stiff in kneeling poses.'],
  [1, 20, 'intermediate', 'Has practised for years; steady in the standing poses.'],
  [2, 20, 'beginner', null],
  [3, 20, 'pain_management', 'Knee pain on stairs and when kneeling; start with supported poses.'],
  [4, 20, 'advanced', 'A long-time student; inversions with the teacher.'],
  [0, 5, 'intermediate', 'Reviewed: Vajrasana and Bhujangasana steady now, no knee pain; ready for longer holds.'],
];
const FEEDBACK = [
  ['Asha Kulkarni', 'I like seeing how I felt before and after each class.'],
  ['Rohan Desai', 'Join button is easy. I missed the link once because I opened WhatsApp first.'],
  ['Meera Iyer', 'Please add the Marathi names of the poses.'],
];
const IST_MS = 330 * MIN;
const CURRICULUM = JSON.parse(readFileSync(new URL('../content/curriculum.json', import.meta.url), 'utf8'));
// The teacher's feedback on an item: (student, by index in STUDENTS; item; days ago; text).
const TEACHER_FEEDBACK = [
  [0, 'vajrasana', 8, 'Keep a cushion under the ankles, and come out at the first sign of knee pain.'],
  [0, 'bhujangasana', 4, 'Lift with the back, not the hands; elbows close.'],
  [0, 'vajrasana', 2, 'Much steadier this week. Two minutes is enough for now.'],
  [0, 'setu_bandhasana', 1, 'Lower the hips halfway this week and let the back settle.'],
  [1, 'trikonasana', 3, 'Hand on the shin is fine; keep the chest open.'],
  [2, 'vakrasana', 2, 'Twist from the belly, not the shoulders; less is more for now.'],
  [3, 'pavanamuktasana', 2, 'Hands under the thigh worked well; keep it gentle, one knee at a time.'],
];
// How an item goes for a student over the two weeks, as [first reaction, latest reaction] (1 not yet to 4 at ease):
// most improve, some are steady from the start, some are still an effort, and a few dip. Asha's and Kavita's are fixed,
// for the tour.
const SHAPES = [[2, 4], [2, 3], [3, 4], [2, 4], [3, 3], [4, 4], [3, 3], [2, 2], [1, 2], [3, 2]];
const KAVITA_SHAPES = {
  pavanamuktasana: [2, 4], setu_bandhasana: [1, 3], shalabhasana: [2, 3], tadasana: [3, 4], makarasana: [3, 4], vakrasana: [2, 3],
  sectional_breathing: [3, 4], bhujangasana: [2, 3], nadi_shodhana: [3, 4], bhramari: [3, 4], shavasana: [4, 4],
};
const ASHA_SHAPES = {
  vajrasana: [2, 4], bhujangasana: [2, 4], trikonasana: [2, 3], vrikshasana: [1, 3], tadasana: [3, 3], shavasana: [4, 4],
  sectional_breathing: [3, 4], vakrasana: [2, 2], padahastasana: [2, 2], setu_bandhasana: [3, 2], kapalabhati: [3, 2],
};
// What Asha wrote after some classes, by item and days ago.
const ASHA_NOTES = {
  'vajrasana:12': 'Left knee pinched after a minute',
  'vajrasana:9': 'Still the left knee; came out early',
  'vajrasana:5': 'Cushion under the ankles helped',
  'trikonasana:3': 'Hand reached the shin today',
  'setu_bandhasana:3': 'Lower back tight; came down early',
  'padahastasana:6': 'Hamstrings still pull; bent knees',
};
// Practice on one's own: (student by index, days ago, minutes, [item, seconds held, reaction, pain, note]).
const SOLO = [
  [0, 11, 15, [['vajrasana', 45, 2, 1, 'Knee again after 45 seconds'], ['tadasana', 60, 3], ['bhujangasana', 20, 2]]],
  [0, 9, 20, [['vajrasana', 60, 2], ['tadasana', 60, 3], ['bhujangasana', 25, 3]]],
  [0, 6, 18, [['vajrasana', 80, 3], ['bhujangasana', 30, 3], ['trikonasana', 30, 2]]],
  [0, 4, 25, [['vajrasana', 100, 3, 0, 'Cushion, no pain'], ['bhujangasana', 30, 3], ['trikonasana', 30, 3], ['vrikshasana', 40, 2]]],
  [0, 2, 22, [['vajrasana', 120, 4, 0, 'Two minutes, no pain'], ['bhujangasana', 40, 4], ['trikonasana', 40, 3], ['vrikshasana', 45, 3]]],
  [1, 8, 30, [['trikonasana', 40, 3], ['nadi_shodhana', 300, 4], ['dhyana', 600, 3]]],
  [1, 3, 25, [['trikonasana', 45, 3], ['nadi_shodhana', 300, 4], ['dhyana', 600, 4]]],
  [3, 5, 12, [['pavanamuktasana', 60, 3, 0, 'Left knee fine with hands under the thigh'], ['makarasana', 120, 4]]],
];

/** mulberry32: the same demo on every run. */
function random(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function main(file) {
  if (existsSync(file)) {
    console.error(file + ' exists; delete it first so the demo starts clean');
    process.exit(1);
  }
  const b = open(file, 'DEMO1994');
  const ok = (r) => {
    if (r.status !== 200) throw new Error(JSON.stringify(r));
    return r.body;
  };
  const signup = (name, phone, role, code, lang) =>
    ok(b.call('POST', '/auth/signup', { body: { name, phone, password: PASSWORD, role, code, lang } }));

  const teacher = signup('Ramit (demo)', '9800000001', 'teacher', 'DEMO1994', 'en');
  const groupCode = ok(b.call('GET', '/teacher/home', { token: teacher.token })).settings.group_code;
  const studio = JSON.parse(b.evaluate('JSON.stringify(STUDIO)'));
  ['abc-defg-hij', 'bcd-efgh-ijk', 'cde-fghi-jkl', 'def-ghij-klm'].forEach((code, i) => {
    ok(b.call('PUT', '/teacher/batches/' + studio.batches[i].key, { token: teacher.token, body: { meet_link: 'https://meet.google.com/' + code } }));
  });
  const students = STUDENTS.map((name, i) =>
    ({ name, ...signup(name, '98000000' + String(i + 2).padStart(2, '0'), 'student', groupCode, i % 3 ? 'en' : 'hi') }));
  const today = Math.floor((b.clock() + IST_MS) / DAY);
  const evening = (ago) => (today - ago) * DAY - IST_MS + 19 * 60 * MIN;
  PLACEMENTS.forEach(([who, ago, to, note], i) => {
    const s = students[who];
    addRow(b, 'batch_changes', { id: i + 1, student_id: s.user.id, from: s.batch, to, note, created_at: evening(ago) });
    s.batch = to;
    s.since = evening(ago);
  });
  const users = b.ss.getSheetByName('users');
  const header = users.rows()[0];
  students.filter((s) => s.batch).forEach((s) => {
    const row = users.rows().findIndex((r) => r[0] === s.user.id) + 1;
    users.getRange(row, header.indexOf('status') + 1).setValue("'approved");
    users.getRange(row, header.indexOf('batch') + 1).setValue("'" + s.batch);
    users.getRange(row, header.indexOf('batch_since') + 1).setValue(new Date(s.since));
  });
  /** The batch a student was in `ago` days ago, at class time. */
  const batchOn = (s, ago) => PLACEMENTS.filter(([who, when]) => students[who] === s && when > ago).map(([, , to]) => to).pop();

  // The last SPAN days of each batch's classes, each with its batch's curriculum; most students joining most of their
  // batch's classes and saying after class how most items went, each item along its own shape. Asha and Kavita join
  // every class.
  const plans = {};
  CURRICULUM.curricula.forEach((c) => {
    plans[c.key] = c.items.map((i) => i.item);
  });
  const names = {};
  CURRICULUM.library.forEach((i) => {
    names[i.key] = i.name;
  });
  const days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  const rng = random(7);
  const pick = (list) => list[Math.floor(rng() * list.length)];
  let id = b.ss.getSheetByName('class_sessions').rows().slice(1).reduce((top, r) => Math.max(top, Number(r[0]) || 0), 0) + 1;
  let entry = 1;
  const asha = students[0];
  const kavita = students[3];
  const shapes = {};
  const shape = (s, item) => {
    const key = s.user.id + ':' + item;
    if (!shapes[key]) shapes[key] = (s === asha && ASHA_SHAPES[item]) || (s === kavita && KAVITA_SHAPES[item]) || pick(SHAPES);
    return shapes[key];
  };
  for (let ago = SPAN; ago >= 1; ago--) studio.batches.forEach((batch) => {
    const day = today - ago;
    if (batch.days.indexOf(days[(day + 3) % 7]) < 0) return; // 1 Jan 1970 was a Thursday
    const [hour, minute] = batch.time.split(':').map(Number);
    const start = day * DAY - IST_MS + (hour * 60 + minute) * MIN;
    const name = batch.name.en;
    const curriculum = batch.curriculum;
    const week = (day - ((day + 3) % 7)) * DAY - IST_MS;
    addRow(b, 'class_sessions', { id, batch: batch.key, starts_at: start, duration_min: batch.duration_min, curriculum, updated_at: start });
    students.filter((s) => batchOn(s, ago) === batch.key).forEach((s) => {
      if (s !== asha && s !== kavita && rng() < 0.3) return;
      const before = pick([2, 3, 3, 3, 4]);
      const row = { user_id: s.user.id, session_id: id, class: name, class_date: day * DAY - IST_MS };
      addRow(b, 'checkins', { ...row, phase: 'before', mood: before, created_at: start - 3 * MIN });
      if (s !== asha && s !== kavita && rng() >= 0.8) return;
      addRow(b, 'checkins', { ...row, phase: 'after', mood: Math.min(5, before + pick([0, 1, 1, 2])), created_at: start + 60 * MIN });
      plans[curriculum].forEach((item) => {
        const note = s === asha ? ASHA_NOTES[item + ':' + ago] : undefined;
        if (!note && rng() < (s === asha || s === kavita ? 0.1 : 0.25)) return; // not every item gets an answer
        const [first, latest] = shape(s, item);
        const reaction = Math.round(first + ((latest - first) * (SPAN - ago)) / (SPAN - 1) + (rng() - 0.5) * 0.6);
        const dipping = latest < first && ago <= 4;
        const pain = s === asha ? (item === 'vajrasana' && ago >= 9) || (item === 'setu_bandhasana' && ago === 3)
          : s === kavita ? ['pavanamuktasana', 'setu_bandhasana'].includes(item) && ago >= 8 : (dipping && rng() < 0.4) || rng() < 0.01;
        addRow(b, 'practice', { id: entry++, user_id: s.user.id, session_id: id, item, reaction: Math.min(4, Math.max(1, reaction)),
          pain: pain ? 1 : 0, note, created_at: start + 60 * MIN, item_name: names[item], week: new Date(week) });
      });
    });
    id++;
  });
  SOLO.forEach(([who, ago, minutes, items], i) => {
    const day = today - ago;
    const started = evening(ago); // 7 in the evening
    const ended = started + minutes * MIN;
    addRow(b, 'solo_sessions', { id: i + 1, user_id: students[who].user.id, started_at: started, ended_at: ended });
    items.forEach(([item, hold, reaction, pain, note]) => {
      addRow(b, 'practice', { id: entry++, user_id: students[who].user.id, solo_id: i + 1, item, hold_s: hold, reaction, pain: pain || 0,
        note, created_at: ended, item_name: names[item], week: new Date((day - ((day + 3) % 7)) * DAY - IST_MS) });
    });
  });
  TEACHER_FEEDBACK.forEach(([who, item, ago, text], i) => {
    addRow(b, 'asana_feedback', { id: i + 1, student_id: students[who].user.id, item, text, created_at: b.clock() - ago * DAY });
  });
  for (const [name, text] of FEEDBACK) {
    ok(b.call('POST', '/feedback', { token: students.find((s) => s.name === name).token, body: { screen: 'me', text } }));
  }
  b.context.onEdit({});
  b.save();
  console.log('demo data written to ' + file);
}

main(process.argv[2] || 'data/demo.json');
