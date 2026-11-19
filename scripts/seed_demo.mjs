// Writes a data file for the dev backend filled with SYNTHETIC demo data, for demos, tours and screenshots. Every
// person, check-in and comment is invented: never present the Insights screen of the demo as results.
//
//   node scripts/seed_demo.mjs data/demo.json
//
// Logins (password demo123): teacher 9800000001; students 9800000002 to 9800000006; 9800000007 waits for approval.
// People sign up through the API, as in the app; the two weeks of past classes, check-ins and practice on one's own,
// which the API cannot date in the past, are written straight into the Sheet's tabs.
import { existsSync, readFileSync } from 'node:fs';
import { addRow, DAY, MIN } from '../appsscript/test/helpers.mjs';
import { open } from './dev_backend.mjs';

const PASSWORD = 'demo123';
const STUDENTS = ['Asha Kulkarni', 'Meera Iyer', 'Rohan Desai', 'Kavita Joshi', 'Sunil Patil', 'Neha Rao']; // the last waits
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
];
// How an item goes for a student over the two weeks, as [first reaction, latest reaction] (1 not yet to 4 at ease):
// most improve, some are steady from the start, some are still an effort, and a few dip. Asha's are fixed, for the tour.
const SHAPES = [[2, 4], [2, 3], [3, 4], [2, 4], [3, 3], [4, 4], [3, 3], [2, 2], [1, 2], [3, 2]];
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
  [3, 5, 12, [['shashankasana', 60, 4], ['makarasana', 90, 4]]],
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
  ok(b.call('PUT', '/teacher/settings', { token: teacher.token, body: { default_meet_link: 'https://meet.google.com/abc-defg-hij' } }));
  const students = STUDENTS.map((name, i) => {
    const waits = i === STUDENTS.length - 1;
    return { name, ...signup(name, '98000000' + String(i + 2).padStart(2, '0'), 'student', waits ? '' : groupCode, i % 3 ? 'en' : 'hi') };
  });

  // The last two weeks of classes, at 8:00 in India, each with a curriculum (Intermediate on Vinyasa days), most
  // students joining most days and saying after class how most items went, each item along its own shape. Asha joins
  // every class.
  const studio = JSON.parse(b.evaluate('JSON.stringify(STUDIO)'));
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
  const today = Math.floor((b.clock() + IST_MS) / DAY);
  let id = b.ss.getSheetByName('class_sessions').rows().slice(1).reduce((top, r) => Math.max(top, Number(r[0]) || 0), 0) + 1;
  let entry = 1;
  const asha = students[0];
  const shapes = {};
  const shape = (s, item) => {
    const key = s.user.id + ':' + item;
    if (!shapes[key]) shapes[key] = (s === asha && ASHA_SHAPES[item]) || pick(SHAPES);
    return shapes[key];
  };
  for (let ago = 13; ago >= 1; ago--) {
    const day = today - ago;
    const start = day * DAY - IST_MS + 8 * 60 * MIN;
    const key = studio.weekly[days[(day + 3) % 7]]; // 1 Jan 1970 was a Thursday
    const name = studio.classes.find((c) => c.key === key).name.en;
    const curriculum = key === 'vinyasa' ? 'intermediate' : 'beginner';
    const week = (day - ((day + 3) % 7)) * DAY - IST_MS;
    addRow(b, 'class_sessions', { id, class_key: key, starts_at: start, duration_min: 55, curriculum, updated_at: start });
    students.filter((s) => s.user.status === 'approved').forEach((s) => {
      if (s !== asha && rng() < 0.3) return;
      const before = pick([2, 3, 3, 3, 4]);
      const row = { user_id: s.user.id, session_id: id, class: name, class_date: day * DAY - IST_MS };
      addRow(b, 'checkins', { ...row, phase: 'before', mood: before, created_at: start - 3 * MIN });
      if (s !== asha && rng() >= 0.8) return;
      addRow(b, 'checkins', { ...row, phase: 'after', mood: Math.min(5, before + pick([0, 1, 1, 2])), created_at: start + 60 * MIN });
      plans[curriculum].forEach((item) => {
        const note = s === asha ? ASHA_NOTES[item + ':' + ago] : undefined;
        if (!note && rng() < (s === asha ? 0.1 : 0.25)) return; // not every item gets an answer
        const [first, latest] = shape(s, item);
        const reaction = Math.round(first + ((latest - first) * (13 - ago)) / 12 + (rng() - 0.5) * 0.6);
        const dipping = latest < first && ago <= 4;
        const pain = s === asha ? (item === 'vajrasana' && ago >= 9) || (item === 'setu_bandhasana' && ago === 3) : (dipping && rng() < 0.4) || rng() < 0.01;
        addRow(b, 'practice', { id: entry++, user_id: s.user.id, session_id: id, item, reaction: Math.min(4, Math.max(1, reaction)),
          pain: pain ? 1 : 0, note, created_at: start + 60 * MIN, item_name: names[item], week: new Date(week) });
      });
    });
    id++;
  }
  SOLO.forEach(([who, ago, minutes, items], i) => {
    const day = today - ago;
    const started = day * DAY - IST_MS + 19 * 60 * MIN; // 7 in the evening
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
