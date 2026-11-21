// ---------- Reset: the Sheet's own menu, to clear test people or start the studio again ----------
// onOpen adds a "Satt Chitt Anand" menu to the Sheet. Each item says first what it removes and what stays, and asks;
// then it deletes rows under the script lock, as the app's writes do, and makes the app forget what it cached, so a
// removed person's phone is signed out at its next request, and the numbers it kept for them (phoneHeld_), so they can
// sign up again at once. Ids are never given again (newIds_): after a reset the next person's id follows the last one
// given, not 1. Rows are deleted whole, so every tab keeps its header and
// the Dashboard's formulas go on reading it. A person's rows are found by the person column of each tab in TABLES_
// (personTabs_), so a tab added later with a user_id or student_id column is cleared with the rest.

const TEST_NAME_ = 'TEST';
// How the dialogs name a row of each tab: [one, many].
const ROW_WORDS_ = {
  tokens: ['sign-in', 'sign-ins'],
  checkins: ['check-in', 'check-ins'],
  feedback: ['feedback message from the app', 'feedback messages from the app'],
  shared_notes: ['shared note', 'shared notes'],
  intake: ['intake', 'intakes'],
  intake_ratings: ['intake self-assessment answer', 'intake self-assessment answers'],
  batch_changes: ['batch placement or move', 'batch placements and moves'],
  practice: ['practice item (after class or on their own)', 'practice items (after class or on their own)'],
  solo_sessions: ['practice on their own', 'practices on their own'],
  asana_feedback: ['note from the teacher on an item', 'notes from the teacher on items'],
};

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Satt Chitt Anand')
    .addItem('Remove test people…', 'removeTestPeople')
    .addItem('Reset the studio…', 'resetStudio')
    .addSeparator()
    .addItem('New group code…', 'newGroupCode')
    .addToUi();
}

/** Every tab whose rows are one person's, with the column naming them: [[tab, column]]. */
function personTabs_() {
  return Object.keys(TABLES_)
    .map((name) => [name, TABLES_[name].map(([col]) => col).filter((col) => col === 'user_id' || col === 'student_id')[0]])
    .filter(([, col]) => col);
}

/** A name starting with TEST, in any case, spaces before it aside. */
function isTestName_(name) {
  return String(name === null || name === undefined ? '' : name).trim().toUpperCase().indexOf(TEST_NAME_) === 0;
}

/** What removing the people `pick` chooses would delete: their users rows, and their rows of each person tab. With
 * `everything`, every row of the person tabs, so rows left by someone deleted from users by hand go too. */
function removal_(db, pick, everything) {
  const people = db.t('users').rows.filter(pick);
  const ids = {};
  people.forEach((u) => {
    ids[u.id] = true;
  });
  const rows = {};
  personTabs_().forEach(([name, col]) => {
    rows[name] = db.t(name).rows.filter((r) => everything || ids[r[col]] === true);
  });
  return { people: people, rows: rows };
}

/** A removal as counts: {people, teacher (one of them is the teacher), rows: {tab: count}, total}. */
function removalCounts_(removal) {
  const rows = {};
  let total = 0;
  Object.keys(removal.rows).forEach((name) => {
    rows[name] = removal.rows[name].length;
    total += rows[name];
  });
  return { people: removal.people.length, teacher: removal.people.some((u) => u.role === 'teacher'), rows: rows, total: total };
}

/** Runs `fn` under the script lock with the Sheet read afresh (a flush first, as Context_.lock does), then flushes and
 * starts a new cache generation, so no request goes on using a login token or setting cached before. */
function menuLock_(db, fn) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) throw new Error('The app is busy writing to the Sheet. Try again in a minute.');
  try {
    SpreadsheetApp.flush();
    db.dropAll();
    return fn();
  } finally {
    try {
      SpreadsheetApp.flush();
      bumpCacheGeneration_();
    } finally {
      db.dropAll();
      lock.releaseLock();
    }
  }
}

/** Under the lock: removes the people `pick` chooses and their rows (every row of the person tabs, with
 * `everything`); the counts. Their numbers are forgotten first, then their sign-ins and their other rows go, and their
 * users rows last, so a removal cut short leaves no one signed in and can simply be run again. */
function removePeople_(db, pick, everything) {
  return menuLock_(db, () => removeLocked_(db, pick, everything));
}

function removeLocked_(db, pick, everything) {
  const removal = removal_(db, pick, everything);
  forgetPhones_(removal.people, everything);
  personTabs_().forEach(([name]) => db.t(name).remove(removal.rows[name]));
  db.t('users').remove(removal.people);
  return removalCounts_(removal);
}

/** Under the lock: what the teacher set on the batches and the classes put back as setup() leaves it: each batch's
 * everyday Meet link emptied, and each class's own link and curriculum, and a time the teacher gave a class back to its
 * batch's on the class's date, so a class follows its batch again. The batches' names, days and times, the curriculum
 * tabs and the settings stay. The rows changed. */
function clearTeacherSettings_(db) {
  let changed = 0;
  const table = db.t('batches');
  table.rows.filter((r) => r.meet_link).forEach((r) => {
    table.update(r, { meet_link: null });
    changed++;
  });
  const batches = batches_({ db: db });
  const classes = db.t('class_sessions');
  classes.rows.filter((r) => r.meet_link || r.curriculum || r.time_set_by).forEach((r) => {
    const changes = { meet_link: null, curriculum: null };
    const batch = batches[r.batch];
    if (r.time_set_by) {
      changes.time_set_by = null;
      if (batch && batch.start_min !== null) {
        changes.starts_at = istMidnight_(istDay_(r.starts_at)) + batch.start_min * 60000;
        changes.duration_min = batch.duration_min;
      }
    }
    classes.update(r, changes);
    changed++;
  });
  return changed;
}

/** Everyone whose name starts with TEST, and every row of theirs; the counts. */
function removeTestPeople_(db) {
  return removePeople_(db, (u) => isTestName_(u.name));
}

/** Everyone, the teacher too, and every row of the person tabs, and what the teacher set on the batches and classes
 * (clearTeacherSettings_); the counts, with `cleared`, the batch and class rows put back. The batches, the curriculum,
 * the classes, the settings and the Dashboard stay, as setup() left them, so the teacher code works again. */
function resetStudio_(db) {
  return menuLock_(db, () => Object.assign(removeLocked_(db, () => true, true), { cleared: clearTeacherSettings_(db) }));
}

/** A new group code, as the teacher can make from the app; the code. */
function newGroupCode_(db) {
  return menuLock_(db, () => {
    const code = newCode_();
    db.setSetting('group_code', code);
    return code;
  });
}

function count_(n, one, many) {
  return n + ' ' + (n === 1 ? one : many);
}

/** "4 sign-ins, 10 check-ins and 2 shared notes", the tabs with any. */
function rowsText_(counts) {
  const parts = Object.keys(counts.rows).filter((name) => counts.rows[name]).map((name) => {
    const words = ROW_WORDS_[name] || [name + ' row', name + ' rows'];
    return count_(counts.rows[name], words[0], words[1]);
  });
  return parts.length > 1 ? parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1] : parts.join('');
}

// ---------- the menu's items: thin wrappers that ask, then call the functions above ----------

/** The menu's "Remove test people…". */
function removeTestPeople() {
  const ui = SpreadsheetApp.getUi();
  const title = 'Remove test people';
  const db = new Db_();
  const removal = removal_(db, (u) => isTestName_(u.name));
  const plan = removalCounts_(removal);
  if (!plan.people) {
    ui.alert(title, 'No one\'s name starts with TEST, so there is no one to remove.', ui.ButtonSet.OK);
    return;
  }
  const list = removal.people.map((u) => '• ' + u.name + ' (' + u.phone + (u.role === 'teacher' ? ', the teacher' : '') + ')').join('\n');
  const text = 'Remove ' + count_(plan.people, 'person whose name starts', 'people whose names start') + ' with TEST' +
    (plan.total ? ', and the ' + count_(plan.total, 'row', 'rows') + ' that are theirs?' : '? They have no other rows.') + '\n\n' +
    list + '\n\n' + (plan.total ? 'Their rows: ' + rowsText_(plan) + '.\n\n' : '') +
    'Everyone else and their rows stay, as do the batches, the curriculum, the classes and the settings. ' +
    'A phone signed in as one of these people is signed out.' +
    (plan.teacher ? ' The teacher code works again, for the teacher to sign up anew.' : '') + '\n\nThis cannot be undone.';
  if (ui.alert(title, text, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const done = removeTestPeople_(db);
  ui.alert(title, 'Removed ' + count_(done.people, 'person', 'people') + ' and ' + count_(done.total, 'row', 'rows') + '.', ui.ButtonSet.OK);
}

/** The menu's "Reset the studio…": asks twice, the second time for RESET typed in. */
function resetStudio() {
  const ui = SpreadsheetApp.getUi();
  const title = 'Reset the studio';
  const plan = removalCounts_(removal_(new Db_(), () => true, true));
  if (!plan.people && !plan.total) {
    ui.alert(title, 'No one has signed up and there are no rows of anyone\'s: the studio is as setup left it.', ui.ButtonSet.OK);
    return;
  }
  const text = 'This removes everyone signed up (' + count_(plan.people, 'person', 'people') +
    (plan.teacher ? ', the teacher among them' : '') + ') and every row they made (' + count_(plan.total, 'row', 'rows') + ')' +
    (plan.total ? ': ' + rowsText_(plan) : '') + '. Every phone is signed out.\n\n' +
    'The Meet links the teacher set go too, each batch\'s and each class\'s own, and the curriculum and the time chosen ' +
    'for a class, so each class follows its batch again, as setup left them.\n\n' +
    'What stays: the batches (their names, days and times), the curriculum (library, curricula, curriculum_items), the ' +
    'classes (class_sessions), the settings (the teacher code, the group code, the group link and the app link) and the ' +
    'Dashboard. Afterwards the teacher signs up again with the same teacher code, and students with the same group ' +
    'code.\n\nThis cannot be undone. Go on?';
  if (ui.alert(title, text, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const typed = ui.prompt(title, 'To remove ' + count_(plan.people, 'person', 'people') + ' and ' + count_(plan.total, 'row', 'rows') +
    ', type RESET and click OK.', ui.ButtonSet.OK_CANCEL);
  if (typed.getSelectedButton() !== ui.Button.OK) return;
  if (typed.getResponseText().trim() !== 'RESET') {
    ui.alert(title, 'Nothing was removed: the box did not say RESET.', ui.ButtonSet.OK);
    return;
  }
  const done = resetStudio_(new Db_());
  ui.alert(title, 'The studio is reset: ' + count_(done.people, 'person', 'people') + ' and ' + count_(done.total, 'row', 'rows') +
    ' were removed, and the Meet links, curricula and class times the teacher set cleared. The teacher can sign up again with the ' +
    'teacher code (in the hidden settings tab), and students with the group code.', ui.ButtonSet.OK);
}

/** The menu's "New group code…". */
function newGroupCode() {
  const ui = SpreadsheetApp.getUi();
  const title = 'New group code';
  const ask = 'Make a new group code? Students sign up with it. The current code stops working, so an invite already ' +
    'sent with it no longer lets anyone sign up; everyone already signed up stays signed in.';
  if (ui.alert(title, ask, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;
  const code = newGroupCode_(new Db_());
  ui.alert(title, 'The new group code is ' + code + '. The teacher sees it in the app, and the invite shared from the app carries it.',
    ui.ButtonSet.OK);
}
