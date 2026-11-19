// The dev and demo backend: the Apps Script bundle (appsscript/dist/Code.gs), the same file the live web app runs, run
// in Node on the fake Google services of appsscript/test, with its Sheet kept in a JSON file.
//
//   node scripts/dev_backend.mjs data/dev.json      serve on port 8000 (PORT, HOST); a missing file is set up afresh
//
// It answers as the live web app does: a POST of the envelope gets a 302 to a one-time /echo address, which the client
// then fetches with GET. A plain GET answers the health check. A new Sheet's teacher sign-up code is SCA_TEACHER_CODE,
// else the one setup() made, printed at start.
//
// For the tour scripts, never the app: POST /dev/class {"class_key": "hatha", "minutes_from_now": -47} adds a 55-minute
// class at that time (here, one under way), so the check-ins are open whatever the time of day.
import { randomUUID } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FakeSheet, loadBackend } from '../appsscript/test/fakes.mjs';
import { classStarted, setSetting, setting } from '../appsscript/test/helpers.mjs';

const isDate = (v) => Object.prototype.toString.call(v) === '[object Date]';

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

function serve(b, host, port) {
  const replies = new Map(); // one-time /echo keys -> the envelope to answer with
  const send = (res, status, text) => res.writeHead(status, { 'Content-Type': 'application/json' }).end(text);
  createServer((req, res) => {
    const url = new URL(req.url, 'http://' + req.headers.host);
    if (req.method === 'GET') {
      if (url.pathname !== '/echo') return send(res, 200, b.context.doGet().getContent());
      const reply = replies.get(url.search.slice(1));
      replies.delete(url.search.slice(1));
      return reply ? send(res, 200, reply) : send(res, 404, '');
    }
    if (req.method !== 'POST') return send(res, 405, '');
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const text = Buffer.concat(chunks).toString('utf8');
      const writes = b.ss.writes;
      let reply;
      if (url.pathname === '/dev/class') {
        const { class_key: key, minutes_from_now: minutes } = JSON.parse(text);
        reply = JSON.stringify({ id: classStarted(b, -minutes, key) });
        b.context.onEdit({});
      } else {
        reply = b.context.doPost({ postData: { contents: text, type: 'application/json' } }).getContent();
        logCall(text, reply);
      }
      if (b.ss.writes !== writes) b.save();
      if (url.pathname === '/dev/class') return send(res, 200, reply);
      const key = randomUUID();
      replies.set(key, reply);
      setTimeout(() => replies.delete(key), 60000).unref();
      res.writeHead(302, { Location: 'http://' + req.headers.host + '/echo?' + key }).end();
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
