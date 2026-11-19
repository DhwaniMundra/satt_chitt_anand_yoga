// Small fakes of the Apps Script services the backend uses, enough to run dist/Code.gs in Node with no Google account.
// The fake Sheet behaves like Sheets where it matters: a fixed grid (writing outside it fails), and text that looks
// like a number, a boolean, a date or a formula is read as one unless it starts with an apostrophe.
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
  getValues() {
    const out = [];
    for (let r = 0; r < this.rows; r++) {
      const line = [];
      for (let c = 0; c < this.cols; c++) {
        const v = this.sheet.cell(this.row + r, this.col + c);
        line.push(v && typeof v === 'object' && 'formula' in v ? '' : v instanceof Date ? new Date(v.getTime()) : v);
      }
      out.push(line);
    }
    return out;
  }
  getValue() { return this.getValues()[0][0]; }
  setValues(values) {
    if (values.length !== this.rows || values.some((line) => line.length !== this.cols)) {
      throw new Error('The number of rows or columns in the data does not match the range.');
    }
    values.forEach((line, r) => line.forEach((v, c) => this.sheet.setCell(this.row + r, this.col + c, sheetsValue(v))));
    return this;
  }
  setValue(v) {
    for (let r = 0; r < this.rows; r++) for (let c = 0; c < this.cols; c++) this.sheet.setCell(this.row + r, this.col + c, sheetsValue(v));
    return this;
  }
  setFormula(f) { this.sheet.setCell(this.row, this.col, { formula: f }); return this; }
  setNumberFormat() { return this; }
  setFontWeight() { return this; }
  setFontSize() { return this; }
  setNote(note) { this.sheet.notes[this.row + ':' + this.col] = note; return this; }
}

export class FakeSheet {
  constructor(ss, name) {
    Object.assign(this, { ss, name, maxRows: 1000, maxCols: 26, data: [], notes: {}, hidden: false, protections: [] });
  }
  getName() { return this.name; }
  cell(r, c) { return (this.data[r - 1] || [])[c - 1] ?? ''; }
  setCell(r, c, v) {
    if (!this.data[r - 1]) this.data[r - 1] = [];
    this.data[r - 1][c - 1] = v;
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
  insertRowsAfter(after, n) { this.data.splice(after, 0, ...Array.from({ length: n }, () => [])); this.maxRows += n; return this; }
  insertColumnsAfter(after, n) { this.maxCols += n; return this; }
  deleteRow(r) { this.data.splice(r - 1, 1); this.maxRows -= 1; this.ss.writes++; return this; }
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
  clearContents() { this.data = []; return this; }
  setFrozenRows() { return this; }
  hideSheet() { this.hidden = true; return this; }
  isSheetHidden() { return this.hidden; }
  protect() {
    const p = { description: '', warningOnly: false, setDescription(d) { this.description = d; return this; },
      setWarningOnly(w) { this.warningOnly = w; return this; } };
    this.protections.push(p);
    return p;
  }
  getProtections() { return this.protections; }
  /** The tab as plain rows, for tests. */
  rows() { return this.getDataRange().getValues(); }
}

export class FakeSpreadsheet {
  constructor() {
    this.sheets = [];
    this.timeZone = 'America/Los_Angeles';
    this.writes = 0;
    this.sheets.push(new FakeSheet(this, 'Sheet1'));
    this.active = this.sheets[0];
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

/** A fresh backend: the bundle loaded into its own context with fake services. */
export function loadBackend({ code } = {}) {
  const ss = new FakeSpreadsheet();
  // The clock: real time moved by offsetMs, or a fixed moment when frozenMs is set.
  const state = { offsetMs: 0, frozenMs: null, lockFree: true, lockHeld: 0, locks: 0, logs: [], digests: 0 };
  const clock = () => (state.frozenMs !== null ? state.frozenMs : Date.now()) + state.offsetMs;
  // Date, shifted by state.offsetMs, shared with the tests so Date objects compare across the boundary.
  class ShiftedDate extends Date {
    constructor(...args) { if (args.length === 0) super(clock()); else super(...args); }
    static now() { return clock(); }
  }
  const cache = new FakeCache(clock);
  const lock = {
    tryLock() { if (!state.lockFree) return false; state.lockHeld++; state.locks++; return true; },
    waitLock() { if (!this.tryLock()) throw new Error('Lock timeout'); },
    releaseLock() { state.lockHeld = Math.max(0, state.lockHeld - 1); },
  };
  const toSigned = (buf) => Array.from(buf, (b) => (b > 127 ? b - 256 : b));
  const services = {
    SpreadsheetApp: {
      getActiveSpreadsheet: () => ss,
      flush: () => {},
      ProtectionType: { SHEET: 'SHEET', RANGE: 'RANGE' },
    },
    LockService: { getScriptLock: () => lock },
    CacheService: { getScriptCache: () => cache },
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
  const context = vm.createContext(services);
  vm.runInContext(code ?? readFileSync(join(ROOT, 'dist', 'Code.gs'), 'utf8'), context, { filename: 'Code.gs' });
  const evaluate = (expression) => vm.runInContext(expression, context);

  /** One call through the envelope, as the app will make it: {status, body}. */
  function call(method, path, { query, token, body } = {}) {
    const envelope = { method, path, query: query || {}, token: token || '', body: body === undefined ? null : body };
    const out = context.doPost({ postData: { contents: JSON.stringify(envelope), type: 'application/json' } });
    if (out.mime !== 'JSON') throw new Error('not JSON output');
    return JSON.parse(out.getContent());
  }

  return { ss, state, cache, context, evaluate, call, Date: ShiftedDate, clock };
}
