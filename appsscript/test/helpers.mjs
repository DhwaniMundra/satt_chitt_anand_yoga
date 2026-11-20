// Shared steps for the tests: a set-up backend, sign-ups, and rows written straight into the fake Sheet, for past
// classes the API cannot create.
import assert from 'node:assert/strict';
import { loadBackend } from './fakes.mjs';

export const MIN = 60000;
export const DAY = 86400000;

/** Wednesday 18 November 2026, 6:00 in India: before the day's class, with the next seven days' classes all ahead. */
export const WEDNESDAY_6AM = Date.parse('2026-11-18T00:30:00Z');

/** The moment the tests run at, so none reads the real clock: WEDNESDAY_6AM, or SCA_TEST_NOW (an ISO time) to check
 * the suite at another moment of the day or week. A test about a particular moment pins it with freshBackend({ now }). */
export const NOW = process.env.SCA_TEST_NOW ? Date.parse(process.env.SCA_TEST_NOW) : WEDNESDAY_6AM;

/** A backend with its clock frozen at [now]; a test moves it on with state.offsetMs. [staleReads] as in loadBackend. */
export function testBackend({ code, now = NOW, staleReads } = {}) {
  return loadBackend({ code, now, staleReads });
}

/** A backend after setup(), with the teacher code known. */
export function freshBackend({ teacherCode = 'TEACH123', now, staleReads } = {}) {
  const b = testBackend({ now, staleReads });
  b.context.setup();
  if (teacherCode !== null) setSetting(b, 'teacher_code', teacherCode);
  return b;
}

export function settingsRows(b) {
  return b.ss.getSheetByName('settings').rows();
}

export function setting(b, key) {
  const row = settingsRows(b).find((r) => r[0] === key);
  return row ? row[1] : null;
}

/** The owner typing a value into the settings tab by hand (which fires the onEdit trigger). */
export function setSetting(b, key, value) {
  const sheet = b.ss.getSheetByName('settings');
  const rows = sheet.rows();
  const i = rows.findIndex((r) => r[0] === key);
  sheet.getRange(i + 1, 2).setValue("'" + value);
  b.context.onEdit({}); // what a hand edit triggers
}

/** A sign-up through the API. A student signs up with the group code and waits; given a `code` (as the teacher passes
 * it on), the student is then placed in `batch` too, as the teacher would, so tests of what members do start there. */
export function signup(b, phone, { role = 'student', code = '', name, batch = 'beginner' } = {}) {
  const r = b.call('POST', '/auth/signup', {
    body: { name: name || role + ' ' + phone, phone, password: 'secret1', role, code: code || (role === 'student' ? setting(b, 'group_code') : '') },
  });
  assert.equal(r.status, 200, JSON.stringify(r));
  if (role === 'student' && code) return { token: r.body.token, user: place(b, r.body.user.id, batch) };
  return { token: r.body.token, user: r.body.user };
}

/** A student placed in `batch` by a hand edit of the users tab, as the teacher's placement leaves them, 90 days ago,
 * so the classes a test makes in the past are their batch's; the user. */
export function place(b, userId, batch) {
  const sheet = b.ss.getSheetByName('users');
  const header = sheet.rows()[0];
  const row = sheet.rows().findIndex((r) => r[0] === userId) + 1;
  sheet.getRange(row, header.indexOf('batch') + 1).setValue("'" + batch);
  sheet.getRange(row, header.indexOf('batch_since') + 1).setValue(new Date(b.clock() - 90 * DAY));
  sheet.getRange(row, header.indexOf('status') + 1).setValue("'approved");
  b.context.onEdit({});
  return userRow(b, userId);
}

function userRow(b, userId) {
  const sheet = b.ss.getSheetByName('users');
  const [header, ...rows] = sheet.rows();
  const r = rows.find((x) => x[0] === userId);
  const v = (k) => r[header.indexOf(k)];
  return { id: v('id'), name: v('name'), phone: v('phone'), role: v('role'), status: v('status'), lang: v('lang'), batch: v('batch'),
    batch_since: v('batch_since') ? new Date(v('batch_since')).toISOString().replace('.000', '') : null };
}

export function teacherAndCode(b) {
  const t = signup(b, '9000000001', { role: 'teacher', code: 'TEACH123' });
  const code = b.call('GET', '/teacher/home', { token: t.token }).body.settings.group_code;
  return { t, code };
}

/** Appends a row to a tab, values by header name, encoded as the backend encodes them. */
export function addRow(b, tab, values) {
  const sheet = b.ss.getSheetByName(tab);
  const header = sheet.rows()[0];
  const line = header.map((h) => {
    const v = values[h];
    if (v === undefined || v === null) return '';
    if (typeof v === 'string') return "'" + v;
    if (typeof v === 'number' && /_at$|_date$/.test(h)) return new Date(v);
    return v;
  });
  const row = sheet.getLastRow() + 1;
  sheet.getRange(row, 1, 1, line.length).setValues([line]);
  return row;
}

function nextId(b, tab) {
  const rows = b.ss.getSheetByName(tab).rows().slice(1).filter((r) => r[0] !== '');
  return rows.reduce((top, r) => Math.max(top, Number(r[0])), 0) + 1;
}

/** A 55-minute class that started `minutesAgo` minutes ago; its id. */
export function classStarted(b, minutesAgo, batch = 'beginner') {
  const id = nextId(b, 'class_sessions');
  const start = Math.floor((b.clock() - minutesAgo * MIN) / 1000) * 1000;
  addRow(b, 'class_sessions', { id, batch, starts_at: start, duration_min: 55, updated_at: b.clock() });
  return id;
}

/** A class `daysAgo` days ago that `userId` joined, with moods. Classmates share the class. */
export function attend(b, userId, batch, daysAgo, before, after) {
  const start = Math.floor((b.clock() - daysAgo * DAY) / 60000) * 60000;
  const sessions = b.ss.getSheetByName('class_sessions').rows().slice(1);
  let session = sessions.find((r) => r[1] === batch && r[2] instanceof Date && r[2].getTime() === start);
  let id;
  if (session) id = session[0];
  else {
    id = nextId(b, 'class_sessions');
    addRow(b, 'class_sessions', { id, batch, starts_at: start, duration_min: 55, updated_at: start });
  }
  addRow(b, 'checkins', { user_id: userId, session_id: id, phase: 'before', mood: before, created_at: start });
  if (after !== null && after !== undefined) addRow(b, 'checkins', { user_id: userId, session_id: id, phase: 'after', mood: after, created_at: start });
  return id;
}
