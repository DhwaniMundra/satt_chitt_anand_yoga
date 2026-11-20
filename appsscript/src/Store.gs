// ---------- Store: one Sheet tab per table ----------
//
// Each tab has a header row; columns are found by header name, so the owner may add columns of her own. Text is
// written with a leading apostrophe, so Sheets keeps "+919876543210", "2E5K7Q" or "=..." exactly as typed instead of
// reading a number, a date or a formula. Times are real date cells (shown in India time); the API sends them as
// UTC ISO-8601 strings. Writes happen under the script lock; ids are the largest id + 1, worked out under that lock.
// Two types are for cells the owner types by hand: `clock`, a time of day kept as text ("07:00"), and `count`, the
// number a cell starts with, words after it aside ("5 breaths" is 5), null when there is none.

const TABLES_ = {
  // A student's batch (a key of the batches tab) and since when; empty until the teacher places them.
  users: [['id', 'int'], ['name', 'text'], ['phone', 'text'], ['role', 'text'], ['status', 'text'], ['pw_hash', 'text'],
    ['lang', 'text'], ['created_at', 'time'], ['batch', 'text?'], ['batch_since', 'time']],
  tokens: [['token_hash', 'text'], ['user_id', 'int'], ['created_at', 'time']],
  // A class of one batch; its own Meet link and curriculum, when set, win over the batch's.
  class_sessions: [['id', 'int'], ['batch', 'text'], ['starts_at', 'time'], ['duration_min', 'int'], ['meet_link', 'text?'],
    ['curriculum', 'text?'], ['updated_at', 'time']],
  // `class` and `class_date` copy the class's batch name and India date, for the owner's queries; the app uses session_id.
  checkins: [['user_id', 'int'], ['session_id', 'int'], ['phase', 'text'], ['mood', 'int'], ['created_at', 'time'],
    ['class', 'text'], ['class_date', 'date']],
  feedback: [['id', 'int'], ['user_id', 'int'], ['screen', 'text'], ['text', 'text'], ['created_at', 'time']],
  shared_notes: [['id', 'int'], ['user_id', 'int'], ['text', 'text'], ['created_at', 'time']],
  settings: [['key', 'text'], ['value', 'text?']],
  // A student's answers about themselves, for the teacher to place them in a batch: health data, hidden, and on the
  // Dashboard only as counts. `pain` like "knee, back".
  intake: [['user_id', 'int'], ['age', 'int'], ['height_cm', 'int'], ['weight_kg', 'int'], ['food', 'text'], ['meals', 'text?'],
    ['pain', 'text?'], ['pain_note', 'text?'], ['updated_at', 'time']],
  // The intake's self-assessment: how each assessment asana went, 1 (not yet) to 4 (at ease), pain 1 for strain or pain.
  intake_ratings: [['user_id', 'int'], ['item', 'text'], ['reaction', 'int'], ['pain', 'int']],
  // Each placement of a student in a batch, and each move between batches: the review history.
  batch_changes: [['id', 'int'], ['student_id', 'int'], ['from', 'text?'], ['to', 'text'], ['note', 'text?'], ['created_at', 'time']],
  // The batches: seeded by setup() from content/studio.json while the tab is empty, then the owner's to edit. `days`
  // like "mon, tue, wed", `time` like "07:00" in India; `curriculum` is its classes' default.
  batches: [['key', 'text'], ['name', 'text'], ['name_hi', 'text'], ['name_mr', 'text'], ['curriculum', 'text'], ['days', 'text'],
    ['time', 'clock'], ['duration_min', 'int'], ['meet_link', 'text?'], ['about', 'text'], ['about_hi', 'text'], ['about_mr', 'text']],
  // The curriculum: seeded by setup() from content/curriculum.json while the tabs are empty, then the owner's to edit.
  library: [['key', 'text'], ['type', 'text'], ['level', 'int'], ['sanskrit', 'text'], ['name', 'text'], ['english', 'text'],
    ['aliases', 'text'], ['source', 'text']],
  curricula: [['key', 'text'], ['name', 'text'], ['name_hi', 'text'], ['name_mr', 'text'], ['level', 'int'], ['about', 'text'],
    ['about_hi', 'text'], ['about_mr', 'text'], ['source', 'text']],
  curriculum_items: [['curriculum', 'text'], ['position', 'int'], ['item', 'text'], ['dose', 'count'], ['unit', 'text'], ['cue', 'text'],
    ['cue_hi', 'text'], ['cue_mr', 'text']],
  // How each item went for a student, in a class (session_id) or on their own (solo_id): reaction 1 (not yet) to 4
  // (at ease), pain 1 for strain or pain, and on their own the stopwatch's seconds (hold_s). `item_name` and `week`
  // (its Monday) copy the item's name and the week, for the owner's queries.
  practice: [['id', 'int'], ['user_id', 'int'], ['session_id', 'int'], ['item', 'text'], ['reaction', 'int'], ['pain', 'int'],
    ['note', 'text?'], ['created_at', 'time'], ['item_name', 'text'], ['week', 'date'], ['solo_id', 'int'], ['hold_s', 'int']],
  // A student's practice on their own; its items are rows of practice with this solo_id.
  solo_sessions: [['id', 'int'], ['user_id', 'int'], ['started_at', 'time'], ['ended_at', 'time']],
  // The teacher's word to one student about one item of the library.
  asana_feedback: [['id', 'int'], ['student_id', 'int'], ['item', 'text'], ['text', 'text'], ['created_at', 'time']],
};

const LOCK_WAIT_MS_ = 20000;
const CACHE_TTL_S_ = 600;

/** The Sheet as one request sees it: each tab read once, on first use, and kept in step with this request's writes. */
class Db_ {
  constructor() {
    this._ss = null;
    this.tables = {};
    this._settings = null;
    this.changedCache = false; // set by writes that make cached values stale; the lock bumps the cache generation
  }

  ss() {
    if (!this._ss) this._ss = SpreadsheetApp.getActiveSpreadsheet();
    return this._ss;
  }

  t(name) {
    if (!this.tables[name]) {
      const sheet = this.ss().getSheetByName(name);
      if (!sheet) throw new HttpError_(500, 'not_set_up');
      this.tables[name] = new Table_(sheet, name);
    }
    return this.tables[name];
  }

  dropAll() {
    this.tables = {};
    this._settings = null;
  }

  /** Reads one tab afresh on its next use: under a lock that keeps the other reads, the tab it writes. */
  forget(name) {
    delete this.tables[name];
  }

  settings() {
    if (this._settings) return this._settings;
    const key = cacheKey_('settings');
    const hit = cacheGet_(key);
    if (hit) {
      this._settings = JSON.parse(hit);
    } else {
      const out = {};
      this.t('settings').rows.forEach((r) => {
        if (r.key && r.value !== null && r.value !== '') out[r.key] = r.value;
      });
      this._settings = out;
      cachePut_(key, JSON.stringify(out));
    }
    return this._settings;
  }

  setting(key) {
    const value = this.settings()[key];
    return value === undefined ? null : value;
  }

  /** Under the lock. */
  setSetting(key, value) {
    const table = this.t('settings');
    const row = table.rows.filter((r) => r.key === key)[0];
    if (row) table.update(row, { value: value });
    else table.insert([{ key: key, value: value }]);
    this.settings()[key] = value;
    this.changedCache = true;
  }
}

class Table_ {
  constructor(sheet, name) {
    this.sheet = sheet;
    this.schema = TABLES_[name];
    const values = sheet.getDataRange().getValues();
    const header = values[0].map((h) => String(h).trim());
    this.cols = {};
    this.schema.forEach(([col]) => {
      const i = header.indexOf(col);
      if (i < 0) throw new HttpError_(500, 'not_set_up');
      this.cols[col] = i;
    });
    const indexes = this.schema.map(([col]) => this.cols[col]);
    this.first = Math.min.apply(null, indexes);
    this.last = Math.max.apply(null, indexes);
    this.lastRow = values.length;
    this.rows = [];
    for (let r = 1; r < values.length; r++) {
      const line = values[r];
      if (line.every((v) => v === '' || v === null)) continue;
      const row = { _row: r + 1 };
      this.schema.forEach(([col, type]) => {
        row[col] = decode_(line[this.cols[col]], type);
      });
      this.rows.push(row);
    }
  }

  nextId() {
    return this.rows.reduce((top, r) => (r.id > top ? r.id : top), 0) + 1;
  }

  /** Appends rows (objects keyed by column name); returns them as stored. */
  insert(objects) {
    if (!objects.length) return [];
    const lines = objects.map((o) => {
      const line = [];
      for (let i = this.first; i <= this.last; i++) line.push('');
      this.schema.forEach(([col, type]) => {
        line[this.cols[col] - this.first] = encode_(o[col], type);
      });
      return line;
    });
    const start = this.lastRow + 1;
    const end = start + lines.length - 1;
    const max = this.sheet.getMaxRows();
    if (end > max) this.sheet.insertRowsAfter(max, end - max + 100);
    this.sheet.getRange(start, this.first + 1, lines.length, this.last - this.first + 1).setValues(lines);
    const added = objects.map((o, i) => {
      const row = { _row: start + i };
      this.schema.forEach(([col, type]) => {
        row[col] = decode_(encode_(o[col], type), type, true);
      });
      return row;
    });
    this.rows = this.rows.concat(added);
    this.lastRow = end;
    return added;
  }

  update(row, changes) {
    Object.keys(changes).forEach((col) => {
      const type = this.schema.filter(([c]) => c === col)[0][1];
      this.sheet.getRange(row._row, this.cols[col] + 1).setValue(encode_(changes[col], type));
      row[col] = changes[col];
    });
  }

  remove(rows) {
    const gone = rows.map((r) => r._row).sort((a, b) => b - a);
    gone.forEach((n) => this.sheet.deleteRow(n));
    this.rows = this.rows.filter((r) => gone.indexOf(r._row) < 0);
    this.rows.forEach((r) => {
      r._row -= gone.filter((n) => n < r._row).length;
    });
    this.lastRow -= gone.length;
  }
}

function isDate_(v) {
  return Object.prototype.toString.call(v) === '[object Date]';
}

const TEXT_TYPES_ = ['text', 'text?', 'clock'];

function encode_(value, type) {
  if (value === null || value === undefined) return '';
  if (TEXT_TYPES_.indexOf(type) >= 0) return value === '' ? '' : "'" + String(value);
  if (type === 'int' || type === 'count') return Number(value);
  return new Date(Math.floor(value / 1000) * 1000); // time, date: milliseconds since 1970, kept to the second as the API sends them
}

/** A cell as the app's value: text, a number, or milliseconds for times. `own` marks a value just encoded. */
function decode_(value, type, own) {
  if (own && TEXT_TYPES_.indexOf(type) >= 0 && typeof value === 'string' && value.charAt(0) === "'") value = value.slice(1);
  if (type === 'clock') return clockText_(value);
  if (type === 'count') return countOf_(value);
  if (type === 'text' || type === 'text?') {
    if (value === '' || value === null) return type === 'text?' ? null : '';
    return isDate_(value) ? isoTime_(value.getTime()) : String(value);
  }
  if (type === 'int') return value === '' || value === null ? null : Number(value);
  if (value === '' || value === null) return null;
  if (isDate_(value)) return Math.round(value.getTime() / 1000) * 1000;
  if (typeof value === 'number') return Math.round(((value - 25569) * 86400000 - IST_OFFSET_MS_) / 1000) * 1000; // a serial day number
  const parsed = Date.parse(String(value));
  return isNaN(parsed) ? null : parsed;
}

/** A time of day as the Sheet shows it, "07:00": the text as typed; for a cell Sheets took as a time, the time it
 * shows in the spreadsheet's time zone (a time-only cell is dated 30 December 1899, when India's offset was +5:21:10,
 * so its hours and minutes are never worked out from a fixed offset); for a number, what was typed: 7.15 is 07:15,
 * 17.3 is 17:30 and 7 is 07:00, and a number below 1 is a time kept as a fraction of a day (0.75 is 18:00). */
function clockText_(value) {
  if (isDate_(value)) return Utilities.formatDate(value, SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), 'HH:mm');
  if (typeof value === 'number') {
    const hours = Math.floor(value);
    const hundredths = Math.round((value - hours) * 100);
    // hours.minutes; past .59, hundredths of an hour (7.75 is 07:45)
    const typed = hours * 60 + (hundredths < 60 ? hundredths : Math.round(hundredths * 0.6));
    return clockOf_((value < 1 ? Math.round(value * 1440) : typed) % 1440);
  }
  return value === null ? '' : String(value);
}

/** The number a count cell typed by hand starts with: 5, "5 breaths", "१० श्वास", 2.5 and "2.5 min" are 5, 5, 10, 2.5
 * and 2.5; null for an empty or worded cell ("slowly"). */
function countOf_(value) {
  if (typeof value === 'number') return value >= 0 ? value : null;
  const m = /^\s*(\d+(?:\.\d+)?)/.exec(latinDigits_(value === null ? '' : value));
  return m ? Number(m[1]) : null;
}

// ---------- the cache ----------
// CacheService keeps login-token lookups and the settings for ten minutes. Every key carries a generation; anything
// that could make a cached value wrong (a settings change, a logout, a password reset, a manual edit) starts a new
// generation after its writes are flushed, so no request reads a value older than the last write.

function cache_() {
  return CacheService.getScriptCache();
}

let CACHE_GENERATION_ = null;

function cacheKey_(suffix) {
  if (CACHE_GENERATION_ === null) {
    let gen = cache_().get('gen');
    if (!gen) {
      gen = Utilities.getUuid().slice(0, 8);
      cache_().put('gen', gen, 21600);
    }
    CACHE_GENERATION_ = gen;
  }
  return CACHE_GENERATION_ + ':' + suffix;
}

function bumpCacheGeneration_() {
  CACHE_GENERATION_ = Utilities.getUuid().slice(0, 8);
  cache_().put('gen', CACHE_GENERATION_, 21600);
}

function cacheGet_(key) {
  return cache_().get(key);
}

function cachePut_(key, value) {
  cache_().put(key, value, CACHE_TTL_S_);
}
