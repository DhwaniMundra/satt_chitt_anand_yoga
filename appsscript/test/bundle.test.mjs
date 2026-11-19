// The paste bundle itself: it is up to date with the sources, it loads, setup() builds the Sheet, and the main path
// (sign up, log in, the Today screen) works through the envelope.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { bundle, CODE_PATH, MANIFEST_PATH } from '../scripts/build.mjs';
import { loadBackend, ROOT } from './fakes.mjs';
import { freshBackend, setting, signup } from './helpers.mjs';

test('dist/ is the build of src/ and studio.json', () => {
  const { code, manifest } = bundle();
  assert.equal(readFileSync(CODE_PATH, 'utf8'), code, 'run node appsscript/scripts/build.mjs');
  assert.equal(readFileSync(MANIFEST_PATH, 'utf8'), manifest);
});

test('the studio and curriculum constants are their content files, in a fresh build too', () => {
  const b = loadBackend({ code: bundle().code });
  const content = (file) => JSON.parse(readFileSync(join(ROOT, '..', 'content', file), 'utf8'));
  assert.deepEqual(JSON.parse(b.evaluate('JSON.stringify(STUDIO)')), content('studio.json'));
  assert.deepEqual(JSON.parse(b.evaluate('JSON.stringify(CURRICULUM)')), content('curriculum.json'));
});

test('the bundle asks for this spreadsheet only', () => {
  const code = readFileSync(CODE_PATH, 'utf8');
  assert.match(code.slice(0, 200), /@OnlyCurrentDoc/);
  assert.doesNotMatch(code, /DriveApp|UrlFetchApp|GmailApp|openById|openByUrl/);
  const manifest = JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'));
  assert.deepEqual(manifest.oauthScopes, ['https://www.googleapis.com/auth/spreadsheets.currentonly']);
  assert.equal(manifest.timeZone, 'Asia/Kolkata');
  assert.deepEqual(manifest.webapp, { executeAs: 'USER_DEPLOYING', access: 'ANYONE_ANONYMOUS' });
});

test('setup builds the tabs, makes the codes once, and can run again', () => {
  const b = loadBackend();
  const message = b.context.setup();
  const names = b.ss.getSheets().map((s) => s.getName());
  assert.equal(names[0], 'Dashboard');
  for (const tab of ['users', 'class_sessions', 'checkins', 'feedback', 'shared_notes', 'tokens', 'settings', 'classes', 'practice',
    'library', 'curricula', 'curriculum_items']) {
    assert.ok(names.includes(tab), tab);
  }
  assert.ok(!names.includes('Sheet1'), 'the empty first tab is removed');
  assert.equal(b.ss.timeZone, 'Asia/Kolkata');
  assert.deepEqual(b.ss.getSheetByName('users').rows()[0],
    ['id', 'name', 'phone', 'role', 'status', 'pw_hash', 'lang', 'created_at']);
  assert.ok(b.ss.getSheetByName('settings').isSheetHidden() && b.ss.getSheetByName('tokens').isSheetHidden());
  const teacherCode = setting(b, 'teacher_code');
  const groupCode = setting(b, 'group_code');
  assert.match(teacherCode, /^[A-HJ-NP-Z2-9]{8}$/);
  assert.match(groupCode, /^[A-HJ-NP-Z2-9]{6}$/);
  assert.ok(message.includes(teacherCode) && message.includes(groupCode));
  b.context.setup();
  assert.equal(setting(b, 'teacher_code'), teacherCode);
  assert.equal(setting(b, 'group_code'), groupCode);
  assert.equal(b.ss.getSheets().length, names.length);
});

test('a GET answers the health check in the envelope', () => {
  const b = loadBackend();
  const out = b.context.doGet({ parameter: {} });
  assert.deepEqual(JSON.parse(out.getContent()), { status: 200, body: { ok: true, assistant: 'off', model: null } });
});

test('sign up, log in and the Today screen', () => {
  const b = freshBackend();
  const teacher = signup(b, '9000000001', { role: 'teacher', code: 'teach123' });
  assert.equal(teacher.user.phone, '+919000000001');
  const groupCode = b.call('GET', '/teacher/home', { token: teacher.token }).body.settings.group_code;
  const student = signup(b, '98765 43210', { code: groupCode.toLowerCase() });
  assert.equal(student.user.status, 'approved');
  const login = b.call('POST', '/auth/login', { body: { phone: '+91 98765 43210', password: 'secret1' } });
  assert.equal(login.status, 200);
  const home = b.call('GET', '/home', { token: login.body.token, query: { lang: 'hi' } });
  assert.equal(home.status, 200);
  assert.equal(home.body.sessions.length, 7);
  assert.equal(home.body.studio.name, 'सत् चित् आनंद योग');
  assert.match(home.body.sessions[0].starts_at, /^\d{4}-\d\d-\d\dT02:30:00Z$/); // 8:00 in India
  assert.equal(b.ss.getSheetByName('class_sessions').rows().length, 8);
  assert.equal(b.call('GET', '/home', { token: 'nope' }).status, 401);
});
