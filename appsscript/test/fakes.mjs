// Small fakes of the Apps Script services the backend uses, enough to run dist/Code.gs in Node with no Google account.
// The fake Sheet behaves like Sheets where it matters: a fixed grid (writing outside it fails), and text that looks
// like a number, a boolean, a date or a formula is read as one unless it starts with an apostrophe.
//
// Two requests at once. Each call() is one execution, as each request to the web app is. meanwhile() runs another
// request (from twin(), a second copy of Code.gs over the same Sheet, cache, properties and lock) in the middle of the
// next one: right after its first read of a tab, or before its n-th tryLock. If the first holds the lock just then,
// the other waits until it lets go, as a real request would.
//
// Stale reads (loadBackend({ staleReads: { flushRefreshes } }), or SCA_STALE_READS=1 for the whole suite): how we
// believe SpreadsheetApp behaves when two executions overlap: a tab read before the lock can miss rows another
// execution wrote (sign-ups sent at once to the web app then share an id), while one read only under the lock stays
// right. An execution's first read of a tab's cells takes a copy of all of them (Apps Script's look-ahead cache fetches
// more than it is asked for, to answer the reads that follow); every later getValues() of that tab in the same
// execution is answered from the copy, which follows the execution's own writes but not anyone else's. The tab's size
// (getLastRow, getDataRange's dimensions) is always read afresh. So a tab read before the lock and again under it
// comes back with the rows another execution added meanwhile as empty rows, which the backend skips, and with rows
// another execution deleted still in place: the next id is one already given, a number already signed up is free, and
// a row number points at someone else's row. SpreadsheetApp.flush() drops the copies when flushRefreshes is true (what
// we believe); false is the worst case, a flush that refreshes nothing, where only a tab first read under the lock is
// read right.
import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

/** What Sheets makes of a value written with setValue(s). */
export function sheetsValue(v) {
  if (v === null || v === undefined) return '';
  if (typeof v !== 'string') return v instanceof Date ? new Date(v.getTime()) : v;
  if (v.startsWith("'")) return v.slice(1);
  if (v === '') return '';
  if (v.startsWith('=')) return { formula: v };
  const t = v.trim();
  if (/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(t)) return Number(t);
  if (/^(true|false)$/i.test(t)) return t.toUpperCase() === 'TRUE';
  if (/^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?Z?)?$/.test(t)) return new Date(t);
  return v;
}

function a1ToIndex(a1) {
  const m = /^([A-Z]*)(\d*)$/.exec(a1);
  let col = 0;
  for (const ch of m[1]) col = col * 26 + ch.charCodeAt(0) - 64;
  return { row: m[2] ? Number(m[2]) : null, col: col || null };
}

export class FakeRange {
  constructor(sheet, row, col, rows, cols) {
    if (row < 1 || col < 1 || rows < 1 || cols < 1 || row + rows - 1 > sheet.maxRows || col + cols - 1 > sheet.maxCols) {
      throw new Error('The coordinates of the range are outside the dimensions of the sheet.');
    }
    Object.assign(this, { sheet, row, col, rows, cols });
  }
  getRow() { return this.row; }
  getColumn() { return this.col; }
  /** The range's values in `data` (a tab's cells, by row). */
  valuesIn(data) {
    const out = [];
    for (let r = 0; r < this.rows; r++) {
      const line = [];
      const cells = data[this.row + r - 1] || [];
      for (let c = 0; c < this.cols; c++) {
        const v = cells[this.col + c - 1] ?? '';
        line.push(v && typeof v === 'object' && 'formula' in v ? '' : v instanceof Date ? new Date(v.getTime()) : v);
      }
      out.push(line);
    }
    return out;
  }
  getValues() {
    const out = this.valuesIn(this.sheet.view());
    this.sheet.ss.called('read', this.sheet);
    return out;
  }
  getValue() { return this.getValues()[0][0]; }
  setValues(values) {
    if (values.length !== this.rows || values.some((line) => line.length !== this.cols)) {
      throw new Error('The number of rows or columns in the data does not match the range.');
    }
    values.forEach((line, r) => line.forEach((v, c) => this.sheet.setCell(this.row + r, this.col + c, sheetsValue(v))));
    this.sheet.ss.called('write', this.sheet);
    return this;
  }
  setValue(v) {
    for (let r = 0; r < this.rows; r++) for (let c = 0; c < this.cols; c++) this.sheet.setCell(this.row + r, this.col + c, sheetsValue(v));
    this.sheet.ss.called('write', this.sheet);
    return this;
  }
  setFormula(f) { this.sheet.setCell(this.row, this.col, { formula: f }); this.sheet.ss.called('write', this.sheet); return this; }
  setNumberFormat() { return this; }
  setFontWeight() { return this; }
  setFontSize() { return this; }
  setNote(note) { this.sheet.notes[this.row + ':' + this.col] = note; return this; }
}

export class FakeSheet {
  constructor(ss, name) {
    Object.assign(this, { ss, name, maxRows: 1000, maxCols: 26, frozenRows: 0, data: [], notes: {}, hidden: false, protections: [] });
  }
  getName() { return this.name; }
  /** The cells as the running execution reads them: the tab's own, or in the stale-read mode its copy of them. */
  view() {
    const copies = this.ss.copies();
    if (!copies) return this.data;
    if (!copies.has(this)) copies.set(this, this.data.map((line) => (line ? line.slice() : line)));
    return copies.get(this);
  }
  /** The tab's cells, and the running execution's copy of them if it has one: its own writes change both. */
  stores() {
    const copies = this.ss.copies();
    const copy = copies && copies.get(this);
    return copy ? [this.data, copy] : [this.data];
  }
  setCell(r, c, v) {
    for (const data of this.stores()) {
      if (!data[r - 1]) data[r - 1] = [];
      data[r - 1][c - 1] = v;
    }
    this.ss.writes++;
  }
  getLastRow() {
    for (let r = this.data.length; r > 0; r--) if ((this.data[r - 1] || []).some((v) => v !== '' && v !== undefined)) return r;
    return 0;
  }
  getLastColumn() {
    let last = 0;
    this.data.forEach((line) => (line || []).forEach((v, c) => { if (v !== '' && v !== undefined) last = Math.max(last, c + 1); }));
    return last;
  }
  getMaxRows() { return this.maxRows; }
  getMaxColumns() { return this.maxCols; }
  insertRowsAfter(after, n) {
    for (const data of this.stores()) data.splice(after, 0, ...Array.from({ length: n }, () => []));
    this.maxRows += n;
    this.ss.called('structural', this);
    return this;
  }
  insertColumnsAfter(after, n) { this.maxCols += n; return this; }
  deleteRow(r) { return this.deleteRows(r, 1); }
  deleteRows(r, n) {
    if (r < 1 || n < 1 || r + n - 1 > this.maxRows) throw new Error('Those rows are out of bounds.');
    if (this.maxRows - n <= this.frozenRows) throw new Error('Sorry, it is not possible to delete all non-frozen rows.');
    for (const data of this.stores()) data.splice(r - 1, n);
    this.maxRows -= n;
    this.ss.writes++;
    this.ss.called('structural', this);
    return this;
  }
  getDataRange() { return new FakeRange(this, 1, 1, Math.max(this.getLastRow(), 1), Math.max(this.getLastColumn(), 1)); }
  getRange(a, b, c, d) {
    if (typeof a === 'string') {
      const [from, to] = a.split(':');
      const p = a1ToIndex(from);
      const q = to ? a1ToIndex(to) : p;
      const row = p.row || 1;
      const col = p.col || 1;
      const lastRow = q.row || this.maxRows;
      const lastCol = q.col || this.maxCols;
      return new FakeRange(this, row, col, lastRow - row + 1, lastCol - col + 1);
    }
    return new FakeRange(this, a, b, c || 1, d || 1);
  }
  clearContents() {
    for (const data of this.stores()) data.length = 0;
    return this;
  }
  setFrozenRows(n) { this.frozenRows = n; return this; }
  hideSheet() { this.hidden = true; return this; }
  isSheetHidden() { return this.hidden; }
  protect() {
    const p = { description: '', warningOnly: false, setDescription(d) { this.description = d; return this; },
      setWarningOnly(w) { this.warningOnly = w; return this; } };
    this.protections.push(p);
    return p;
  }
  getProtections() { return this.protections; }
  /** The tab as plain rows, for tests: what the Sheet holds, whatever an execution has read. */
  rows() { return this.getDataRange().valuesIn(this.data); }
}

export class FakeSpreadsheet {
  constructor() {
    this.sheets = [];
    this.timeZone = 'America/Los_Angeles';
    this.writes = 0;
    this.sheets.push(new FakeSheet(this, 'Sheet1'));
    this.active = this.sheets[0];
    this.staleReads = null; // { flushRefreshes } in the stale-read mode
    this.executions = []; // the requests running, the innermost last: each one's copies of the tabs it has read
    this.called = () => {}; // each read, write, structural change and flush, for loadBackend's counts and meanwhile()
  }
  /** The running execution's copies of the tabs, in the stale-read mode; else null. */
  copies() { return this.staleReads && this.executions.length ? this.executions[this.executions.length - 1] : null; }
  flush() {
    this.called('flush');
    const copies = this.copies();
    if (copies && this.staleReads.flushRefreshes) copies.clear();
  }
  getSheetByName(name) { return this.sheets.find((s) => s.name === name) || null; }
  getSheets() { return this.sheets.slice(); }
  insertSheet(name) {
    if (this.getSheetByName(name)) throw new Error('A sheet with the name "' + name + '" already exists.');
    const sheet = new FakeSheet(this, name);
    this.sheets.push(sheet);
    return sheet;
  }
  deleteSheet(sheet) { this.sheets = this.sheets.filter((s) => s !== sheet); }
  setActiveSheet(sheet) { this.active = sheet; return sheet; }
  moveActiveSheet(position) {
    this.sheets = this.sheets.filter((s) => s !== this.active);
    this.sheets.splice(position - 1, 0, this.active);
  }
  setSpreadsheetTimeZone(tz) { this.timeZone = tz; }
  getSpreadsheetTimeZone() { return this.timeZone; }
}

/** Utilities.formatDate for the one pattern the backend uses, "HH:mm", in a time zone with its history (Asia/Kolkata
 * was +5:21:10 in 1899), as Java's time zone data has it. */
function formatDate(date, timeZone, pattern) {
  if (pattern !== 'HH:mm') throw new Error('only HH:mm is faked');
  return new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date);
}

export class FakeCache {
  constructor(clock) { this.map = new Map(); this.clock = clock; }
  get(key) {
    const hit = this.map.get(key);
    if (!hit || hit.until <= this.clock()) return null;
    return hit.value;
  }
  put(key, value, seconds = 600) {
    if (typeof value !== 'string') throw new Error('Cache values are strings');
    if (key.length > 250) throw new Error('Cache key too long');
    this.map.set(key, { value, until: this.clock() + Math.min(seconds, 21600) * 1000 });
  }
  remove(key) { this.map.delete(key); }
  clear() { this.map.clear(); }
}

/** PropertiesService's script properties: strings by key, kept for good. */
export class FakeProperties {
  constructor() { this.map = new Map(); }
  getProperty(key) { return this.map.has(key) ? this.map.get(key) : null; }
  setProperty(key, value) {
    if (String(value).length > 9000) throw new Error('Property value too long');
    this.map.set(key, String(value));
    return this;
  }
  deleteProperty(key) { this.map.delete(key); return this; }
  getKeys() { return [...this.map.keys()]; }
  getProperties() { return Object.fromEntries(this.map); }
}

/** The stale-read mode from the environment: SCA_STALE_READS=1 for what we believe, =worst for a flush that refreshes
 * nothing. */
function staleReadsFromEnv() {
  const mode = process.env.SCA_STALE_READS;
  return mode ? { flushRefreshes: mode !== 'worst' } : null;
}

/** A fresh backend: the bundle loaded into its own context with fake services. Its clock is real time, or the
 * moment [now] (ms) when given, as in the tests. [staleReads] turns on the stale-read mode (above). */
export function loadBackend({ code, now, staleReads = staleReadsFromEnv() } = {}) {
  const ss = new FakeSpreadsheet();
  ss.staleReads = staleReads || null;
  // The clock: real time, or the frozen moment frozenMs; either moved by offsetMs.
  const state = { offsetMs: 0, frozenMs: now === undefined ? null : now, lockFree: true, lockHeld: 0, locks: 0, logs: [], digests: 0 };
  const clock = () => (state.frozenMs !== null ? state.frozenMs : Date.now()) + state.offsetMs;
  // Date, shifted by state.offsetMs, shared with the tests so Date objects compare across the boundary.
  class ShiftedDate extends Date {
    constructor(...args) { if (args.length === 0) super(clock()); else super(...args); }
    static now() { return clock(); }
  }
  const cache = new FakeCache(clock);
  const props = new FakeProperties();
  // The Sheet's calls by kind (read: a getValues; write: a setValue(s); structural: rows inserted or deleted; flush),
  // all of them and those made while the lock was held: what a route costs, and how long it holds everyone else up.
  const counts = () => ({ read: 0, write: 0, structural: 0, flush: 0 });
  state.calls = counts();
  state.lockedCalls = counts();
  // meanwhile(): the other requests waiting for a moment of the outermost one, and those waiting for the lock.
  state.meanwhile = [];
  state.afterRelease = [];
  state.locksInRequest = 0;
  const fire = (event) => {
    if (ss.executions.length !== 1) return; // only the outermost request's moments
    const i = state.meanwhile.findIndex((m) => (m.read !== undefined && m.read === event.read) || (m.lock !== undefined && m.lock === event.lock));
    if (i < 0) return;
    const [m] = state.meanwhile.splice(i, 1);
    if (state.lockHeld > 0) state.afterRelease.push(m.other); // the other request waits for the lock
    else m.other();
  };
  ss.called = (kind, sheet) => {
    state.calls[kind]++;
    if (state.lockHeld > 0) state.lockedCalls[kind]++;
    if (kind === 'read') fire({ read: sheet.name });
  };
  const lock = {
    tryLock() {
      if (ss.executions.length === 1) fire({ lock: ++state.locksInRequest });
      if (!state.lockFree) return false;
      state.lockHeld++;
      state.locks++;
      return true;
    },
    waitLock() { if (!this.tryLock()) throw new Error('Lock timeout'); },
    releaseLock() {
      state.lockHeld = Math.max(0, state.lockHeld - 1);
      if (state.lockHeld === 0) state.afterRelease.splice(0).forEach((other) => other());
    },
  };
  const toSigned = (buf) => Array.from(buf, (b) => (b > 127 ? b - 256 : b));
  // The owner at the Sheet's menu: each dialog is kept in state.dialogs and answered from state.answers, a button for
  // an alert, [button, text] for a prompt; with none left, an alert is closed with OK and a prompt cancelled.
  state.menus = [];
  state.dialogs = [];
  state.answers = [];
  const Button = { OK: 'OK', CANCEL: 'CANCEL', YES: 'YES', NO: 'NO', CLOSE: 'CLOSE' };
  const ui = {
    Button,
    ButtonSet: { OK: 'OK', OK_CANCEL: 'OK_CANCEL', YES_NO: 'YES_NO', YES_NO_CANCEL: 'YES_NO_CANCEL' },
    createMenu(caption) {
      return { caption, items: [], addItem(c, fn) { this.items.push([c, fn]); return this; },
        addSeparator() { this.items.push(['-']); return this; }, addToUi() { state.menus.push(this); } };
    },
    alert(title, prompt, buttons) {
      state.dialogs.push({ kind: 'alert', title, prompt, buttons });
      return state.answers.length ? state.answers.shift() : Button.OK;
    },
    prompt(title, prompt, buttons) {
      state.dialogs.push({ kind: 'prompt', title, prompt, buttons });
      const [button, text] = state.answers.length ? state.answers.shift() : [Button.CANCEL, ''];
      return { getSelectedButton: () => button, getResponseText: () => text };
    },
  };
  const services = {
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ss,
      getUi: () => ui,
      flush: () => ss.flush(),
      ProtectionType: { SHEET: 'SHEET', RANGE: 'RANGE' },
    },
    LockService: { getScriptLock: () => lock },
    CacheService: { getScriptCache: () => cache },
    PropertiesService: { getScriptProperties: () => props },
    Utilities: {
      DigestAlgorithm: { SHA_256: 'SHA_256' },
      Charset: { UTF_8: 'UTF_8' },
      computeDigest(algorithm, value) {
        if (algorithm !== 'SHA_256') throw new Error('only SHA_256 is faked');
        state.digests++;
        const data = typeof value === 'string' ? Buffer.from(value, 'utf8') : Buffer.from(value.map((b) => b & 255));
        return toSigned(createHash('sha256').update(data).digest());
      },
      getUuid: () => randomUUID(),
      formatDate,
    },
    ContentService: {
      MimeType: { JSON: 'JSON' },
      createTextOutput(content) {
        return { content, mime: 'TEXT', setMimeType(m) { this.mime = m; return this; }, getContent() { return this.content; } };
      },
    },
    Logger: { log: (...args) => { state.logs.push(args.join(' ')); } },
    console: { error: (...args) => state.logs.push('ERROR ' + args.join(' ')) },
    Date: ShiftedDate,
  };
  const source = code ?? readFileSync(join(ROOT, 'dist', 'Code.gs'), 'utf8');

  /** One execution: what `fn` reads of the Sheet is its own (see staleReads), as is each request to the web app. */
  function execution(fn) {
    if (ss.executions.length === 0) state.locksInRequest = 0;
    ss.executions.push(new Map());
    try {
      return fn();
    } finally {
      ss.executions.pop();
    }
  }

  /** Runs `other` while the next request runs: right after that request's first read of tab `read`, or just before
   * its `lock`-th tryLock; if it holds the lock just then, as soon as it lets go. */
  function meanwhile({ read, lock: n }, other) {
    state.meanwhile.push({ read, lock: n, other });
  }

  /** Code.gs loaded into a context of its own over these services: a backend, or a twin of one. */
  function instance() {
    const context = vm.createContext({ ...services });
    vm.runInContext(source, context, { filename: 'Code.gs' });
    const evaluate = (expression) => vm.runInContext(expression, context);

    /** One call through the envelope, as the app will make it, as one execution: {status, body}. */
    function call(method, path, { query, token, body, requestId } = {}) {
      const envelope = { method, path, query: query || {}, token: token || '', body: body === undefined ? null : body };
      if (requestId) envelope.request_id = requestId;
      const out = execution(() => context.doPost({ postData: { contents: JSON.stringify(envelope), type: 'application/json' } }));
      if (out.mime !== 'JSON') throw new Error('not JSON output');
      return JSON.parse(out.getContent());
    }

    /** Another copy of the backend over the same Sheet, cache, properties, lock and clock: a second request's own
     * execution, for meanwhile(). */
    const twin = () => instance();

    return { ss, state, cache, props, context, evaluate, call, execution, meanwhile, twin, Date: ShiftedDate, clock };
  }

  return instance();
}
