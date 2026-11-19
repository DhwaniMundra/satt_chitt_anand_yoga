// ---------- Setup: the tabs, the codes and the Dashboard ----------
// Run setup() once from the script editor (it asks for permission the first time). Running it again is safe: it adds
// what is missing and leaves the data, the codes, the batches, the curriculum and an existing Dashboard alone.

const DATA_TABS_ = ['users', 'class_sessions', 'checkins', 'practice', 'solo_sessions', 'asana_feedback', 'batch_changes', 'feedback',
  'shared_notes', 'tokens', 'settings'];
const CURRICULUM_TABS_ = ['library', 'curricula', 'curriculum_items'];
const OWNER_TABS_ = ['batches'].concat(CURRICULUM_TABS_); // the owner's to edit: no warning on hand edits
const HIDDEN_TABS_ = ['tokens', 'settings']; // login-token hashes and the codes: nothing to browse
const SETTING_NOTES_ = [
  ['teacher_code', 'The one-time code the teacher signs up with. It stops working once the teacher has an account.'],
  ['group_code', 'Students sign up with this code, from the class\'s WhatsApp invite; the teacher then places them in a batch. The teacher can change it in the app.'],
  ['group_link', 'The WhatsApp group invite link, set by the teacher in the app.'],
];
const TIME_FORMAT_ = 'yyyy-mm-dd hh:mm:ss';
const DATE_FORMAT_ = 'yyyy-mm-dd';

function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  let codes;
  try {
    ss.setSpreadsheetTimeZone('Asia/Kolkata');
    DATA_TABS_.concat(OWNER_TABS_).forEach((name) => ensureTab_(ss, name));
    seedBatches_(ss);
    seedCurriculum_(ss);
    codes = ensureSettings_(ss);
    if (!ss.getSheetByName('Dashboard')) writeDashboard_(ss);
    arrangeTabs_(ss);
    SpreadsheetApp.flush();
    bumpCacheGeneration_();
  } finally {
    lock.releaseLock();
  }
  const message = 'Set up. Teacher sign-up code: ' + codes.teacher_code + ' (for ' + STUDIO.teacher.short.en + ', used once). Group code: ' +
    codes.group_code + '. Both are kept in the hidden "settings" tab (View > Hidden sheets). ' +
    'Next: Deploy > New deployment > Web app, Execute as Me, Who has access Anyone.';
  Logger.log(message);
  return message;
}

/** A tab with its header row; columns the code needs and the tab lacks are added at the end. */
function ensureTab_(ss, name) {
  const columns = TABLES_[name];
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  const width = Math.max(sheet.getLastColumn(), 1);
  const header = sheet.getRange(1, 1, 1, width).getValues()[0].map((h) => String(h).trim());
  const empty = header.every((h) => h === '');
  const missing = columns.map(([c]) => c).filter((c) => header.indexOf(c) < 0);
  if (missing.length) {
    const at = empty ? 1 : width + 1;
    if (at + missing.length - 1 > sheet.getMaxColumns()) sheet.insertColumnsAfter(sheet.getMaxColumns(), at + missing.length - 1 - sheet.getMaxColumns());
    sheet.getRange(1, at, 1, missing.length).setValues([missing]);
  }
  const names = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map((h) => String(h).trim());
  sheet.getRange(1, 1, 1, names.length).setFontWeight('bold');
  sheet.setFrozenRows(1);
  columns.forEach(([col, type]) => {
    if (type !== 'time' && type !== 'date') return;
    const rows = sheet.getMaxRows() - 1;
    if (rows > 0) sheet.getRange(2, names.indexOf(col) + 1, rows, 1).setNumberFormat(type === 'time' ? TIME_FORMAT_ : DATE_FORMAT_);
  });
  return sheet;
}

/** The batches tab, filled from content/studio.json while it is empty; after that the Sheet's rows are the batches. */
function seedBatches_(ss) {
  const table = new Table_(ss.getSheetByName('batches'), 'batches');
  if (table.rows.length) return;
  table.insert(STUDIO.batches.map((b) => ({ key: b.key, name: b.name.en, name_hi: b.name.hi, name_mr: b.name.mr, curriculum: b.curriculum,
    days: b.days.join(', '), time: b.time, duration_min: b.duration_min, meet_link: null, about: b.about.en, about_hi: b.about.hi,
    about_mr: b.about.mr })));
}

/** The curriculum tabs, filled from content/curriculum.json while they are empty, with "{teacher}" in its text
 * written as the studio names the teacher; after that the Sheet's rows are the curriculum. The curricula tab's first
 * cell notes where the mock curriculum comes from. */
function seedCurriculum_(ss) {
  const pick = (text) => LANGS_.map((lang) => fill_(text[lang], { teacher: STUDIO.teacher.short[lang] }));
  const rows = {
    library: CURRICULUM.library.map((i) => ({ key: i.key, type: i.type, level: i.level, sanskrit: i.sanskrit, name: i.name,
      english: i.english, aliases: i.aliases.join(', '), source: i.source })),
    curricula: CURRICULUM.curricula.map((c) => {
      const [name, nameHi, nameMr] = pick(c.name);
      const [about, aboutHi, aboutMr] = pick(c.about);
      return { key: c.key, name: name, name_hi: nameHi, name_mr: nameMr, level: c.level, about: about, about_hi: aboutHi,
        about_mr: aboutMr, source: c.source };
    }),
    curriculum_items: CURRICULUM.curricula.reduce((all, c) => all.concat(c.items.map((it, i) => {
      const [cue, cueHi, cueMr] = pick(it.cue);
      return { curriculum: c.key, position: i + 1, item: it.item, dose: it.dose, unit: it.unit, cue: cue, cue_hi: cueHi, cue_mr: cueMr };
    })), []),
  };
  CURRICULUM_TABS_.forEach((name) => {
    const table = new Table_(ss.getSheetByName(name), name);
    if (!table.rows.length) table.insert(rows[name]);
  });
  ss.getSheetByName('curricula').getRange(1, 1).setNote(fill_(CURRICULUM.about, { teacher: STUDIO.teacher.short.en }));
}

/** The teacher and group codes, made once, and a row (with a note) for each setting. */
function ensureSettings_(ss) {
  const sheet = ss.getSheetByName('settings');
  if (sheet.getRange(1, 3).getValue() === '') sheet.getRange(1, 3).setValue('about').setFontWeight('bold');
  const table = new Table_(sheet, 'settings');
  const have = {};
  table.rows.forEach((r) => {
    have[r.key] = r;
  });
  if (!have.teacher_code || !have.teacher_code.value) setRow_(table, have, 'teacher_code', newCode_(8));
  if (!have.group_code || !have.group_code.value) setRow_(table, have, 'group_code', newCode_());
  SETTING_NOTES_.forEach(([key, note]) => {
    if (!have[key]) setRow_(table, have, key, null);
    sheet.getRange(have[key]._row, 3).setValue(encode_(note, 'text'));
  });
  return { teacher_code: have.teacher_code.value, group_code: have.group_code.value };
}

function setRow_(table, have, key, value) {
  if (have[key]) table.update(have[key], { value: value });
  else have[key] = table.insert([{ key: key, value: value }])[0];
}

function arrangeTabs_(ss) {
  const ours = { Dashboard: true };
  DATA_TABS_.concat(OWNER_TABS_).forEach((name) => {
    ours[name] = true;
  });
  const dashboard = ss.getSheetByName('Dashboard');
  ss.setActiveSheet(dashboard);
  ss.moveActiveSheet(1);
  DATA_TABS_.forEach((name) => {
    const sheet = ss.getSheetByName(name);
    if (HIDDEN_TABS_.indexOf(name) >= 0) sheet.hideSheet();
    if (sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET).length === 0) {
      sheet.protect().setDescription('Written by the app: Sheets asks before a hand edit').setWarningOnly(true);
    }
  });
  ss.getSheets().forEach((sheet) => {
    if (!ours[sheet.getName()] && sheet.getLastRow() === 0 && sheet.getLastColumn() === 0) ss.deleteSheet(sheet); // the empty Sheet1
  });
}

/** Column letters of a tab by header name, as the tab is now. */
function columnLetters_(ss, name) {
  const sheet = ss.getSheetByName(name);
  const header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const out = {};
  header.forEach((h, i) => {
    out[String(h).trim()] = columnLetter_(i + 1);
  });
  out._last = columnLetter_(header.length);
  return out;
}

function columnLetter_(n) {
  let s = '';
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

/** The Dashboard's blocks: [the cell its formula starts in (the title goes above), title, note, formula, number formats]. */
function dashboardBlocks_(ss) {
  const u = columnLetters_(ss, 'users');
  const c = columnLetters_(ss, 'checkins');
  const f = columnLetters_(ss, 'feedback');
  const n = columnLetters_(ss, 'shared_notes');
  const p = columnLetters_(ss, 'practice');
  const m = columnLetters_(ss, 'batch_changes');
  const users = 'users!A1:' + u._last;
  const checkins = 'checkins!A1:' + c._last;
  const col = (tab, letter) => tab + '!' + letter + '2:' + letter;
  const names = '{' + col('users', u.id) + ', ' + col('users', u.name) + '}';
  const nameOf = (tab, letter) => 'ARRAYFORMULA(IFERROR(VLOOKUP(' + col(tab, letter) + ', ' + names + ', 2, FALSE), ""))';
  return [
    ['A5', 'Students by status', 'Students only, not the teacher.',
      '=IFERROR(QUERY(' + users + ', "select ' + u.status + ', count(' + u.id + ') where ' + u.role + " = 'student' group by " +
        u.status + ' label ' + u.status + " 'status', count(" + u.id + ") 'students'\", 1), \"No students yet\")", {}],
    ['H5', 'Students per batch', 'Approved students in each batch.',
      '=IFERROR(QUERY(' + users + ', "select ' + u.batch + ', count(' + u.id + ') where ' + u.role + " = 'student' and " + u.status +
        " = 'approved' group by " + u.batch + ' label ' + u.batch + " 'batch', count(" + u.id + ") 'students'\", 1), \"No students yet\")", {}],
    ['K5', 'Batch changes', 'The latest 8 placements and moves, newest first; the batch_changes tab has them all.',
      '=IFERROR(QUERY({' + [col('batch_changes', m.created_at), nameOf('batch_changes', m.student_id), col('batch_changes', m.from),
        col('batch_changes', m.to), col('batch_changes', m.note)].join(', ') + "}, \"select Col1, Col2, Col3, Col4, Col5 where Col1 is not " +
        "null order by Col1 desc limit 8 label Col1 'when', Col2 'student', Col3 'from', Col4 'to', Col5 'note'\", 0), \"No batch changes yet\")",
      { 'K6:K13': 'yyyy-mm-dd' }],
    ['D5', 'Mood per class', 'Average mood after and before class, all classes so far. 1 very low to 5 great.',
      '=IFERROR(QUERY(' + checkins + ', "select ' + c.class + ', avg(' + c.mood + ') where ' + c.user_id + ' is not null group by ' +
        c.class + ' pivot ' + c.phase + '", 1), "No check-ins yet")', { 'E6:F13': '0.0' }],
    ['A16', 'Students', 'Every student, newest first, with their batch and the number of classes they checked in to.',
      '=IFERROR(QUERY({' + [col('users', u.name), col('users', u.phone), col('users', u.status), col('users', u.batch), col('users', u.lang),
        'ARRAYFORMULA(IF(' + col('users', u.id) + ' = "", , COUNTIFS(' + col('checkins', c.user_id) + ', ' + col('users', u.id) + ', ' +
          col('checkins', c.phase) + ', "before")))', col('users', u.created_at), col('users', u.role)].join(', ') +
        "}, \"select Col1, Col2, Col3, Col4, Col5, Col6, Col7 where Col8 = 'student' order by Col7 desc label Col1 'name', Col2 'phone', " +
        "Col3 'status', Col4 'batch', Col5 'language', Col6 'classes joined', Col7 'signed up'\", 0), \"No students yet\")", { 'G17:G': DATE_FORMAT_ }],
    ['H16', 'Attendance per class', 'Students who checked in before each class, newest first.',
      '=IFERROR(QUERY(' + checkins + ', "select ' + c.class_date + ', ' + c.class + ', count(' + c.user_id + ') where ' + c.phase +
        " = 'before' group by " + c.class_date + ', ' + c.class + ' order by ' + c.class_date + ' desc label count(' + c.user_id +
        ") 'joined'\", 1), \"No check-ins yet\")", { 'H17:H': 'ddd d mmm yyyy' }],
    ['L16', 'Mood by class and date', 'Average mood after and before each class, newest first.',
      '=IFERROR(QUERY(' + checkins + ', "select ' + c.class_date + ', ' + c.class + ', avg(' + c.mood + ') where ' + c.user_id +
        ' is not null group by ' + c.class_date + ', ' + c.class + ' pivot ' + c.phase + ' order by ' + c.class_date +
        ' desc", 1), "No check-ins yet")', { 'L17:L': 'ddd d mmm yyyy', 'N17:O': '0.0' }],
    ['Q16', 'Feedback', 'What students wrote from the app, newest first.',
      '=IFERROR(QUERY({' + [col('feedback', f.created_at), nameOf('feedback', f.user_id), col('feedback', f.screen),
        col('feedback', f.text)].join(', ') + "}, \"select Col1, Col2, Col3, Col4 where Col1 is not null order by Col1 desc " +
        "label Col1 'when', Col2 'student', Col3 'screen', Col4 'feedback'\", 0), \"No feedback yet\")", { 'Q17:Q': 'yyyy-mm-dd hh:mm' }],
    ['V16', 'Shared notes', 'Notes students chose to share with the teacher from the companion, newest first.',
      '=IFERROR(QUERY({' + [col('shared_notes', n.created_at), nameOf('shared_notes', n.user_id), col('shared_notes', n.text)].join(', ') +
        "}, \"select Col1, Col2, Col3 where Col1 is not null order by Col1 desc label Col1 'when', Col2 'student', Col3 'note'\", 0), " +
        '"No shared notes yet")', { 'V17:V': 'yyyy-mm-dd hh:mm' }],
    ['Z16', 'Strain or pain, last 14 days', 'Items a student marked "felt strain or pain", after class or on their own, newest first.',
      '=IFERROR(QUERY({' + [col('practice', p.created_at), nameOf('practice', p.user_id), col('practice', p.item_name),
        col('practice', p.note), col('practice', p.pain)].join(', ') + "}, \"select Col1, Col2, Col3, Col4 where Col5 = 1 and Col1 >= " +
        "datetime '\" & TEXT(TODAY() - 14, \"yyyy-mm-dd hh:mm:ss\") & \"' order by Col1 desc label Col1 'when', Col2 'student', " +
        "Col3 'item', Col4 'note'\", 0), \"No strain or pain in the last 14 days\")", { 'Z17:Z': 'yyyy-mm-dd hh:mm' }],
    ['AE16', 'Reactions per item, week by week', 'Average reaction, after class or on their own: 1 not yet, 2 with effort, 3 steady, 4 at ease. ' +
      'One column per week, headed by its Monday.',
      '=IFERROR(QUERY(practice!A1:' + p._last + ', "select ' + p.item_name + ', avg(' + p.reaction + ') where ' + p.reaction +
        ' is not null group by ' + p.item_name + ' pivot ' + p.week + '", 1), "No reactions yet")', { 'AF17:CB': '0.0', 'AF16:CB16': 'd mmm' }],
  ];
}

function writeDashboard_(ss) {
  const sheet = ss.insertSheet('Dashboard');
  if (sheet.getMaxColumns() < 80) sheet.insertColumnsAfter(sheet.getMaxColumns(), 80 - sheet.getMaxColumns());
  sheet.getRange('A1').setValue('Satt Chitt Anand: the studio at a glance').setFontWeight('bold').setFontSize(14);
  sheet.getRange('A2').setValue('Each block is one formula over the tabs; click its first cell to read or change it. Times are ' +
    'India time. Add blocks of your own anywhere: setup() never rewrites this tab (delete it and run setup again for a fresh one).');
  dashboardBlocks_(ss).forEach(([cell, title, note, formula, formats]) => {
    const anchor = sheet.getRange(cell);
    const row = anchor.getRow();
    const column = anchor.getColumn();
    sheet.getRange(row - 1, column).setValue(title).setFontWeight('bold');
    sheet.getRange(row - 1, column).setNote(note);
    sheet.getRange(row, column).setFormula(formula);
    Object.keys(formats).forEach((range) => sheet.getRange(range).setNumberFormat(formats[range]));
  });
}
