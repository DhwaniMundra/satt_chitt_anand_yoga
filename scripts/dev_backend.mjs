// The dev and demo backend: the Apps Script bundle (appsscript/dist/Code.gs), the same file the live web app runs, run
// in Node on the fake Google services of appsscript/test, with its Sheet kept in a JSON file.
//
//   node scripts/dev_backend.mjs data/dev.json      serve on port 8000 (PORT, HOST); a missing file is set up afresh
//
// It answers as the live web app does: a POST of the envelope gets a 302 to a one-time /echo address, which the client
// then fetches with GET; fetched again, that address answers the health check, as any plain GET does. A new Sheet's
// teacher sign-up code is SCA_TEACHER_CODE, else the one setup() made, printed at start. SCA_DELAY_MS holds each answer
// back that long, as the live web app takes a second or more, to see the app's loading states.
//
// For the tour scripts, never the app: POST /dev/class {"batch": "intermediate", "minutes_from_now": -47} adds a
// 55-minute class of that batch at that time (here, one under way), so the check-ins are open whatever the time of day;
// POST /dev/joined {"phone": "9800000002", "starts_at": "2026-11-19T02:30:00Z", "mood": 2} has that student join their
// batch's class that began then, as if they had checked in before it, so they can say how it went.
//
// And for the two-phone test, the troubles of a real network: POST /dev/trouble {"path": "/auth/signup", "times": 1,
// "drop": true} has the next call to that path (or to any, with "*") run but its answer lost (the connection closed);
// {"status": 503, "html": true} answers it with that status and a page instead, without running it; {"delay_ms": 3000}
// holds its answer back that long. Each trouble lasts `times` calls; POST /dev/trouble {} clears them.
import { randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FakeSheet, loadBackend } from '../appsscript/test/fakes.mjs';
import { addRow, classStarted, DAY, MIN, setSetting, setting } from '../appsscript/test/helpers.mjs';

const isDate = (v) => Object.prototype.toString.call(v) === '[object Date]';
const DELAY_MS = Number(process.env.SCA_DELAY_MS || 0);

/** The backend with its Sheet in `file`: read back when the file exists, else set up and saved. */
export function open(file, teacherCode) {
  const b = loadBackend();
  b.save = () => {
    const sheets = b.ss.sheets.map((s) => ({
      name: s.name, maxRows: s.maxRows, maxCols: s.maxCols, notes: s.notes, hidden: s.hidden,
      data: Array.from(s.data, (line) => Array.from(line || [], (v) => (v === undefined || v === null ? '' : isDate(v) ? { $date: v.getTime() } : v))),
    }));
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file + '.tmp', JSON.stringify({ timeZone: b.ss.timeZone, sheets }));
    renameSync(file + '.tmp', file);
  };
  if (existsSync(file)) {
    const saved = JSON.parse(readFileSync(file, 'utf8'), (key, v) => (v && typeof v === 'object' && '$date' in v ? new Date(v.$date) : v));
    b.ss.timeZone = saved.timeZone;
    b.ss.sheets = saved.sheets.map((s) => Object.assign(new FakeSheet(b.ss, s.name), s));
  } else {
    b.context.setup();
    if (teacherCode) setSetting(b, 'teacher_code', teacherCode);
    b.save();
  }
  return b;
}

/** The before-class check-in of the student with this number to their batch's class that began at `start` (ms). */
function joined(b, phone, start, mood) {
  const rows = (tab) => b.ss.getSheetByName(tab).rows();
  const [head, ...users] = rows('users');
  const user = users.find((u) => String(u[head.indexOf('phone')]) === '+91' + phone);
  const batch = user[head.indexOf('batch')];
  const session = rows('class_sessions').slice(1).find((r) => r[1] === batch && isDate(r[2]) && r[2].getTime() === start);
  const [bhead, ...batches] = rows('batches');
  const name = batches.find((r) => r[bhead.indexOf('key')] === batch)[bhead.indexOf('name')];
  const ist = 330 * MIN;
  addRow(b, 'checkins', { user_id: user[0], session_id: session[0], phase: 'before', mood, created_at: start - 3 * MIN, class: name,
    class_date: Math.floor((start + ist) / DAY) * DAY - ist });
  return session[0];
}

/** The first trouble queued for this envelope's path, used once more, or null. */
function troubleFor(troubles, envelope) {
  let path;
  try {
    path = String(JSON.parse(envelope).path || '').split('?')[0];
  } catch {
    return null;
  }
  const trouble = troubles.find((t) => t.times > 0 && (t.path === '*' || t.path === path));
  if (trouble) trouble.times -= 1;
  return trouble || null;
}

function serve(b, host, port) {
  const replies = new Map(); // one-time /echo keys -> the envelope to answer with
  let troubles = []; // from POST /dev/trouble
  const send = (res, status, text) => res.writeHead(status, { 'Content-Type': 'application/json' }).end(text);
  createServer((req, res) => {
    const url = new URL(req.url, 'http://' + req.headers.host);
    if (req.method === 'GET') {
      const reply = url.pathname === '/echo' && replies.get(url.search.slice(1));
      replies.delete(url.search.slice(1));
      return send(res, 200, reply || b.context.doGet().getContent());
    }
    if (req.method !== 'POST') return send(res, 405, '');
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const text = Buffer.concat(chunks).toString('utf8');
      const writes = b.ss.writes;
      let reply;
      let held = DELAY_MS;
      if (url.pathname === '/dev/class') {
        const { batch, minutes_from_now: minutes } = JSON.parse(text);
        reply = JSON.stringify({ id: classStarted(b, -minutes, batch) });
        b.context.onEdit({});
      } else if (url.pathname === '/dev/joined') {
        const { phone, starts_at: startsAt, mood } = JSON.parse(text);
        reply = JSON.stringify({ session_id: joined(b, phone, Date.parse(startsAt), mood) });
        b.context.onEdit({});
      } else if (url.pathname === '/dev/trouble') {
        const trouble = JSON.parse(text || '{}');
        troubles = trouble.path ? troubles.filter((t) => t.times > 0).concat([Object.assign({ times: 1 }, trouble)]) : [];
        reply = JSON.stringify({ troubles: troubles.length });
      } else {
        const trouble = troubleFor(troubles, text);
        if (trouble && trouble.status) {
          console.log('trouble: HTTP ' + trouble.status + ' for ' + trouble.path);
          return res.writeHead(trouble.status, { 'Content-Type': trouble.html ? 'text/html' : 'application/json' })
            .end(trouble.html ? '<html><body>Service Unavailable</body></html>' : '');
        }
        reply = b.context.doPost({ postData: { contents: text, type: 'application/json' } }).getContent();
        logCall(text, reply);
        if (trouble && trouble.drop) {
          if (b.ss.writes !== writes) b.save();
          console.log('trouble: the answer to ' + trouble.path + ' is lost');
          return req.socket.destroy();
        }
        held = trouble && trouble.delay_ms ? trouble.delay_ms : DELAY_MS;
      }
      if (b.ss.writes !== writes) b.save();
      if (url.pathname.startsWith('/dev/')) return send(res, 200, reply);
      const key = randomUUID();
      replies.set(key, reply);
      setTimeout(() => replies.delete(key), 60000).unref();
      setTimeout(() => res.writeHead(302, { Location: 'http://' + req.headers.host + '/echo?' + key }).end(), held);
    });
  }).listen(port, host, () => console.log('dev backend on http://' + host + ':' + port));
}

function logCall(envelope, reply) {
  let call;
  try {
    const e = JSON.parse(envelope);
    call = e.method + ' ' + e.path;
  } catch {
    call = 'not JSON';
  }
  console.log(new Date().toISOString().slice(11, 19) + ' ' + call + ' -> ' + JSON.parse(reply).status);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const file = process.argv[2];
  if (!file) {
    console.error('usage: node scripts/dev_backend.mjs <data file>');
    process.exit(2);
  }
  const fresh = !existsSync(file);
  const b = open(file, process.env.SCA_TEACHER_CODE);
  if (fresh) console.log('new Sheet in ' + file + '; teacher sign-up code ' + setting(b, 'teacher_code'));
  serve(b, process.env.HOST || '0.0.0.0', Number(process.env.PORT || 8000));
}
